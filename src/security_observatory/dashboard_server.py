from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from argparse import Namespace
from datetime import datetime, timezone
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import threading
import uuid
import webbrowser

from .cases import build_recovery_playbooks
from .consequence import suggest_placement_node
from .agent_lab import (
    AGENT_PROPOSAL_MAX_BYTES,
    AgentLabExecutionError,
    AgentLabProposalValidationError,
    build_agent_context_payload,
    build_agent_execution_preview,
    proposal_from_import_payload,
    validate_agent_proposal,
)
from .case_followup import (
    apply_case_resolutions,
    build_case_followup_prompt,
    validate_case_resolutions,
)
from .credentials import (
    CredentialStorageError,
    KEYCHAIN_SERVICE,
    delete_credential,
    is_supported as keychain_is_supported,
    list_all_credentials,
    list_credentials,
    store_credential,
)
from .setup_runner import (
    SetupRunnerError,
    delete_tool_config,
    read_tool_config,
    run_setup_probe,
    write_tool_config,
)
from .tool_config import ToolConfigError
from .discovery import discover_repos
from .docs_render import render_markdown
from .fix_proposals import decide_landing, invariants_for
from .honey_keys import (
    DEFAULT_PLACEMENT_PATHS,
    build_decoy_snippets,
    extract_honey_key_from_request,
    generate_honey_key,
    hash_honey_key,
    honey_key_is_well_formed,
    open_url_is_valid,
    project_id_for_repo_path,
    sanitize_headers,
    summarize_body,
)
from .managed_tools import (
    ManagedToolInstallError,
    install_managed_tool_files,
    managed_tool_evidence,
    uninstall_managed_tool_files,
)
from .rotation import (
    ROTATION_INFLIGHT_STATUSES,
    SUPPORTED_STACKS,
    detect_rotation_state,
    detect_stack,
    list_receipts,
    read_receipt,
    read_rotation_history,
    read_rotation_status,
    rotation_consistency_check,
)
from .dashboard_payload import enrich_repos_with_rotation
from .scan_orchestrator import scan_repo
from .scanners import scan_profile_catalog, scanner_names_for_profile, security_pack_catalog, tool_catalog
from .storage import ObservatoryDB
from .reset import (
    backup_scan_results,
    execute_scan_results_reset,
    list_scan_result_repos,
    plan_scan_results_reset,
    reset_scan_results_confirmation_phrase,
)


from .dashboard_pages import (
    build_ai_prompt,
    raw_report_export,
    report_page,
    _docs_page_shell,
    _docs_title,
)

CHECK_JOBS: dict[str, dict[str, object]] = {}
CHECK_JOBS_LOCK = threading.Lock()
_TERMINAL_JOB_STATUSES = frozenset({"complete", "halted", "failed"})
# Terminal jobs are pruned this long after they finish so a very long-lived
# single-user server doesn't accumulate completed jobs unboundedly. The window
# is generous: a polling client reads a finished job's outcome long before it
# expires, so the check-status contract (live + recently-finished jobs visible,
# unknown/expired → 404) is unchanged.
CHECK_JOB_TTL_SECONDS = 3600

BATCH_JOBS: dict[str, dict[str, object]] = {}
BATCH_JOBS_LOCK = threading.Lock()

# Sec-name regex: ENV-style identifiers only. The skill itself rejects anything
# else, but we want the dashboard to refuse before shelling out.
_SAFE_SECRET_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SAFE_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Cap stdout tail kept in memory per job. The receipt is the source of truth;
# the tail exists for live progress, not as an archival log.
_ROTATION_STDOUT_TAIL_MAX = 200

# Wall-clock cap on a single rotation. The skill's own SOAK is ~15 min by
# default; the canary + verify path adds a few minutes. 45 min leaves headroom
# for the longest-supported soak (60 min) plus pipeline overhead.
_ROTATION_SUBPROCESS_TIMEOUT_SECONDS = 60 * 60
_ROTATION_JOB_REDISCOVERY_WINDOW_SECONDS = _ROTATION_SUBPROCESS_TIMEOUT_SECONDS * 2


def _rotation_confirmation_phrase(secret: str, *, emergency: bool = False) -> str:
    """Mirror the Tier 5R confirmation phrase from docs/agent-safety.md.

    Surfaces (dashboard modal, /devsec-rotate) must send back this exact string
    or the trigger endpoint refuses. The single source of truth lives in the
    safety doctrine; this helper is the literal Python rendering of it.
    """
    if emergency:
        return (
            f"Yes, rotate `{secret}` emergency-mode and accept that the old key "
            "dies immediately with no grace."
        )
    return f"Yes, rotate `{secret}` and accept the irreversible provider-side change."


def _batch_rotation_confirmation_phrase(count: int, *, has_class_b: bool = False) -> str:
    suffix = (
        " This includes provider-side changes for Class B secrets."
        if has_class_b
        else ""
    )
    return (
        f"Yes, rotate {count} secrets and accept the irreversible provider-side changes."
        + suffix
    )


# Batch filter presets — each returns a predicate over rotation-status rows.
BATCH_FILTER_PRESETS = {
    "never_rotated": lambda row: str(row.get("status") or "") == "NEVER",
    "needs_attention": lambda row: bool(row.get("needs_attention")),
    "all_actionable": lambda row: (
        str(row.get("status") or "") == "NEVER" or bool(row.get("needs_attention"))
    ),
}


def _apply_batch_filter(
    rows: list[dict[str, Any]], preset: str
) -> list[dict[str, Any]]:
    predicate = BATCH_FILTER_PRESETS.get(preset)
    if not predicate:
        return []
    return [
        row for row in rows
        if predicate(row)
        and str(row.get("status") or "") not in ROTATION_INFLIGHT_STATUSES
        and str(row.get("secret") or "") not in {"(corrupt)", "(unreadable)"}
    ]


def _append_rotation_audit_event(repo_path: Path, event: dict[str, Any]) -> None:
    """Append one event to ``data/rotation-log.jsonl``.

    The rotation skill owns this file at runtime; the dashboard appends a single
    ``DASHBOARD_TRIGGER`` line before the subprocess starts so the audit trail
    captures human-clicked triggers even if npm never launches. Failures here
    must NOT block the rotation — they only mean we lose the audit line.
    """
    log_path = Path(repo_path) / "data" / "rotation-log.jsonl"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"at": utc_now(), **event}
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
    except OSError:
        pass


def _terminal_phase_from_status(status: str) -> str:
    """Map the skill's status vocabulary to the dashboard's coarse phase."""
    if status in ("ROTATED", "IN_GRACE"):
        return "verified"
    if status in (
        "HALTED",
        "HEALTH_CHECK_FAILED",
        "CANARY_VERIFY_FAILED",
        "SOAK_FAILED",
        "ROLLED_BACK",
    ):
        return "halted"
    return "unknown"


def _rotation_job_phase_from_status(status: str) -> str:
    return {
        "HEALTH_CHECK": "health_check",
        "PREFLIGHT": "preflight",
        "ACQUIRED": "acquire",
        "WAITING_FOR_PASTE": "waiting_for_paste",
        "STAGED_CANARY": "stage_canary",
        "DEPLOYED_CANARY": "stage_canary",
        "IN_CANARY_VERIFY": "verify_canary",
        "VERIFIED_CANARY": "verify_canary",
        "STAGED_PROD": "stage_prod",
        "DEPLOYED_PROD": "stage_prod",
        "VERIFIED": "verify_prod",
        "IN_SOAK": "soak",
        "SOAKED": "soak",
    }.get(status, "unknown")


def _latest_receipt_filename_for(repo_path: Path, secret: str) -> str | None:
    """Return the newest receipt file whose name starts with ``<secret>-``."""
    directory = Path(repo_path) / "data" / "rotation-receipts"
    if not directory.is_dir():
        return None
    candidates: list[tuple[float, str]] = []
    for entry in directory.iterdir():
        if not entry.is_file() or entry.suffix.lower() != ".md":
            continue
        if not entry.name.startswith(f"{secret}-"):
            continue
        try:
            candidates.append((entry.stat().st_mtime, entry.name))
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _run_rotation_job(
    job_id: str,
    repo_path: Path,
    secret: str,
    command: list[str],
    repo_name: str,
    stdin_text: str | None = None,
) -> None:
    """Run ``npm run rotate -- <SECRET> ...`` and stream progress into CHECK_JOBS.

    The job updates four channels:
      - ``phase`` / ``message`` — coarse pipeline phase for the progress panel.
      - ``stdout_tail`` — last N lines of npm output (capped) for diagnostics.
      - ``events_seen`` — count of new entries in ``data/rotation-log.jsonl``;
        the frontend can re-fetch ``/api/rotation/history`` when it grows.
      - ``receipt_filename`` / ``receipt_url`` — set when the skill writes a
        verification receipt for the rotated secret.

    Cancellation is not supported in v1 — the pipeline is safe-to-abandon and a
    tear-down path would add complexity without value yet.
    """
    update_job(
        job_id,
        status="running",
        phase="initiated",
        message="Shelling out to the rotation skill.",
        started_at=utc_now(),
    )
    npm = shutil.which("npm")
    if not npm:
        update_job(
            job_id,
            status="failed",
            phase="halted",
            message="`npm` was not found on PATH. Install Node.js and retry.",
            error="npm not on PATH",
            finished_at=utc_now(),
        )
        return

    history_path = Path(repo_path) / "data" / "rotation-log.jsonl"
    initial_events = _count_jsonl_lines(history_path)

    try:
        process = subprocess.Popen(
            [npm, *command[1:]] if command[0] == "npm" else command,
            cwd=str(repo_path),
            stdin=subprocess.PIPE if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        update_job(
            job_id,
            status="failed",
            phase="halted",
            message=f"Could not start the rotation subprocess: {exc}",
            error=str(exc),
            finished_at=utc_now(),
        )
        return

    tail: list[str] = []
    deadline = _dt_now_monotonic() + _ROTATION_SUBPROCESS_TIMEOUT_SECONDS
    try:
        assert process.stdout is not None  # for type checkers
        if stdin_text is not None:
            try:
                assert process.stdin is not None
                process.stdin.write(f"{stdin_text}\n")
                process.stdin.close()
                update_job(
                    job_id,
                    phase="waiting_for_paste",
                    message=(
                        "Pasted value submitted to the rotation skill. Waiting for"
                        " verification."
                    ),
                    paste_submitted_at=utc_now(),
                )
            except OSError as exc:
                process.kill()
                update_job(
                    job_id,
                    status="failed",
                    phase="halted",
                    message=f"Could not submit pasted value to rotation subprocess: {exc}",
                    error=str(exc),
                    finished_at=utc_now(),
                )
                return
        for raw_line in process.stdout:
            line = raw_line.rstrip()
            if line:
                tail.append(line)
                if len(tail) > _ROTATION_STDOUT_TAIL_MAX:
                    del tail[: len(tail) - _ROTATION_STDOUT_TAIL_MAX]
                phase, message = _classify_stdout_line(line)
                update_payload: dict[str, object] = {
                    "stdout_tail": list(tail),
                    "events_seen": _count_jsonl_lines(history_path) - initial_events,
                }
                if phase:
                    update_payload["phase"] = phase
                if message:
                    update_payload["message"] = message
                update_job(job_id, **update_payload)
            if _dt_now_monotonic() > deadline:
                process.kill()
                update_job(
                    job_id,
                    status="failed",
                    phase="halted",
                    message=(
                        "Rotation subprocess exceeded the dashboard time cap"
                        f" ({_ROTATION_SUBPROCESS_TIMEOUT_SECONDS // 60} min)."
                        " Verify state with `npm run rotate --status`."
                    ),
                    error="timeout",
                    finished_at=utc_now(),
                )
                return
        exit_code = process.wait()
    except Exception as exc:
        update_job(
            job_id,
            status="failed",
            phase="halted",
            message=f"Subprocess error: {exc}",
            error=str(exc),
            finished_at=utc_now(),
        )
        return

    # The receipt is the load-bearing trust signal; fish out the newest one for
    # the rotated secret regardless of exit code (HALTs also write a receipt).
    receipt_filename = _latest_receipt_filename_for(repo_path, secret)
    receipt_url: str | None = None
    if receipt_filename:
        receipt_url = (
            f"/api/rotation/receipts/{quote_path(repo_name)}/"
            f"{quote_path(receipt_filename)}"
        )

    # Re-read rotation-state to map the final status to our coarse phase.
    final_status: str | None = None
    for row in read_rotation_status(repo_path):
        if isinstance(row, dict) and row.get("secret") == secret:
            final_status = str(row.get("status") or "")
            break

    terminal_phase = "verified"
    if exit_code != 0:
        terminal_phase = "halted"
    elif final_status:
        terminal_phase = _terminal_phase_from_status(final_status)

    if exit_code == 0 and final_status == "WAITING_FOR_PASTE":
        update_job(
            job_id,
            status="running",
            phase="waiting_for_paste",
            message=(
                "Waiting for a provider-console paste. Use Resume + paste to"
                " continue this rotation."
            ),
            stdout_tail=list(tail),
            exit_code=exit_code,
            events_seen=_count_jsonl_lines(history_path) - initial_events,
            receipt_filename=receipt_filename,
            receipt_url=receipt_url,
            verification_status=final_status,
            finished_at=None,
        )
        return

    if exit_code == 0 and terminal_phase == "verified":
        outcome_status = "complete"
        outcome_message = "Rotation completed. Verification receipt available."
    elif exit_code == 0 and terminal_phase == "halted":
        # Skill exits 0 after a clean HALT when recovery info is preserved.
        outcome_status = "halted"
        outcome_message = "Rotation halted. The receipt names the recovery step."
    else:
        outcome_status = "failed"
        outcome_message = (
            "Rotation subprocess exited non-zero. Inspect stdout_tail and the"
            " receipt (if any) for the failure mode."
        )

    update_job(
        job_id,
        status=outcome_status,
        phase=terminal_phase,
        message=outcome_message,
        stdout_tail=list(tail),
        exit_code=exit_code,
        events_seen=_count_jsonl_lines(history_path) - initial_events,
        receipt_filename=receipt_filename,
        receipt_url=receipt_url,
        verification_status=final_status,
        finished_at=utc_now(),
    )


def _batch_job_snapshot(batch_id: str) -> dict[str, object] | None:
    with BATCH_JOBS_LOCK:
        batch = BATCH_JOBS.get(batch_id)
        return dict(batch) if batch else None


def _update_batch_job(batch_id: str, **updates: object) -> None:
    with BATCH_JOBS_LOCK:
        if batch_id in BATCH_JOBS:
            BATCH_JOBS[batch_id].update(updates)


def _run_batch_rotation(
    batch_id: str,
    repo_path: Path,
    repo_name: str,
) -> None:
    """Sequential batch rotation worker.

    Iterates the queue one secret at a time, shelling out to
    `npm run rotate -- <SECRET>` for each. Between rotations, checks
    if the batch was stopped or if the previous rotation halted.
    """
    import time as _time

    with BATCH_JOBS_LOCK:
        batch = BATCH_JOBS.get(batch_id)
        if not batch:
            return
        queue: list[str] = list(batch.get("queue") or [])  # type: ignore[arg-type]

    completed: list[dict[str, object]] = []
    halted_secrets: list[dict[str, object]] = []

    for idx, secret in enumerate(queue):
        # Check if batch was stopped externally
        with BATCH_JOBS_LOCK:
            batch = BATCH_JOBS.get(batch_id)
            if not batch:
                return
            if batch.get("status") == "stopped":
                return
            # If we returned from a halt-wait and the user chose stop,
            # the status will already be "stopped".
            if batch.get("halted_awaiting_decision"):
                # Wait for the operator's continue/stop decision (polled)
                pass

        # Wait loop for operator decision after a halt
        while True:
            with BATCH_JOBS_LOCK:
                b = BATCH_JOBS.get(batch_id)
                if not b:
                    return
                if b.get("status") == "stopped":
                    return
                if not b.get("halted_awaiting_decision"):
                    break
            _time.sleep(1)

        _update_batch_job(
            batch_id,
            current_secret=secret,
            position=idx + 1,
            status="running",
        )

        # Skip secrets that already have an in-flight job
        if _active_rotation_job(repo_name, secret):
            halted_secrets.append({
                "secret": secret,
                "reason": "already in-flight",
                "job_id": None,
            })
            _update_batch_job(batch_id, halted=list(halted_secrets))
            continue

        # Check that the secret isn't currently in an in-flight state on disk
        rows = read_rotation_status(repo_path)
        row = next(
            (r for r in rows if r.get("secret") == secret),
            None,
        )
        if row and str(row.get("status") or "") in ROTATION_INFLIGHT_STATUSES:
            halted_secrets.append({
                "secret": secret,
                "reason": f"in-flight status: {row.get('status')}",
                "job_id": None,
            })
            _update_batch_job(batch_id, halted=list(halted_secrets))
            continue

        # Build and run the sub-rotation
        command = ["npm", "run", "rotate", "--", secret]
        job_id = uuid.uuid4().hex[:12]
        job: dict[str, object] = {
            "id": job_id,
            "kind": "rotation",
            "status": "queued",
            "repo": repo_name,
            "repo_path": str(repo_path),
            "secret": secret,
            "command": " ".join(command),
            "options": {
                "no_soak": False,
                "skip_health_check": False,
                "soak_minutes": None,
                "test_mode": False,
                "acknowledged_skipping_soak": False,
                "acknowledged_skipping_health_check": False,
                "emergency_mode": False,
                "acknowledged_cached_caller_risk": False,
            },
            "phase": "queued",
            "message": f"Queued in batch {batch_id}; about to shell out.",
            "stdout_tail": [],
            "events_seen": 0,
            "started_at": utc_now(),
            "finished_at": None,
            "exit_code": None,
            "error": None,
            "receipt_filename": None,
            "receipt_url": None,
            "verification_status": None,
            "batch_id": batch_id,
        }
        with CHECK_JOBS_LOCK:
            CHECK_JOBS[job_id] = job

        _update_batch_job(batch_id, current_job_id=job_id)

        _append_rotation_audit_event(
            repo_path,
            {
                "rotation_id": None,
                "secret_name": secret,
                "step": "DASHBOARD_TRIGGER",
                "outcome": "initiated",
                "note": (
                    f"batch sub-rotation; batch_id={batch_id}; "
                    f"job_id={job_id}; command={' '.join(command)}"
                ),
            },
        )

        # Run synchronously — sequential, not parallel
        _run_rotation_job(job_id, repo_path, secret, command, repo_name)

        # Read the outcome
        snapshot = job_snapshot(job_id)
        sub_status = str(snapshot.get("status") or "") if snapshot else "failed"

        if sub_status == "complete":
            completed.append({
                "secret": secret,
                "job_id": job_id,
                "receipt_filename": snapshot.get("receipt_filename") if snapshot else None,
            })
            _update_batch_job(batch_id, completed=list(completed))
        else:
            halted_secrets.append({
                "secret": secret,
                "reason": str(snapshot.get("message") or sub_status) if snapshot else sub_status,
                "job_id": job_id,
            })
            _update_batch_job(batch_id, halted=list(halted_secrets))

            # Halt-on-error: pause and await operator decision
            _update_batch_job(
                batch_id,
                halted_awaiting_decision=True,
                status="halted_awaiting_decision",
            )

            # Wait for operator continue/stop
            deadline = _time.monotonic() + _ROTATION_SUBPROCESS_TIMEOUT_SECONDS
            while _time.monotonic() < deadline:
                with BATCH_JOBS_LOCK:
                    b = BATCH_JOBS.get(batch_id)
                    if not b:
                        return
                    if b.get("status") == "stopped":
                        return
                    if not b.get("halted_awaiting_decision"):
                        break
                _time.sleep(1)
            else:
                # Timed out waiting for decision — stop the batch
                _update_batch_job(
                    batch_id,
                    status="stopped",
                    halted_awaiting_decision=False,
                    finished_at=utc_now(),
                )
                _write_batch_receipt(batch_id, repo_path)
                return

    # All done
    final_status = "complete" if not halted_secrets else "complete_with_errors"
    _update_batch_job(
        batch_id,
        status=final_status,
        current_secret=None,
        current_job_id=None,
        finished_at=utc_now(),
        halted_awaiting_decision=False,
    )
    _write_batch_receipt(batch_id, repo_path)


def _write_batch_receipt(batch_id: str, repo_path: Path) -> None:
    """Write a batch-level receipt to the rotation receipts directory."""
    snapshot = _batch_job_snapshot(batch_id)
    if not snapshot:
        return

    completed = snapshot.get("completed") or []
    halted = snapshot.get("halted") or []
    queue = snapshot.get("queue") or []
    repo = str(snapshot.get("repo") or "")
    started = str(snapshot.get("started_at") or "")
    finished = str(snapshot.get("finished_at") or utc_now())
    status = str(snapshot.get("status") or "")

    lines = [
        f"# Batch rotation receipt — `{repo}`",
        "",
        f"- **Batch ID:** `{batch_id}`",
        f"- **Status:** {status}",
        f"- **Filter:** {snapshot.get('filter')}",
        f"- **Started:** {started}",
        f"- **Finished:** {finished}",
        f"- **Total queued:** {len(queue)}",  # type: ignore[arg-type]
        f"- **Completed:** {len(completed)}",  # type: ignore[arg-type]
        f"- **Halted/skipped:** {len(halted)}",  # type: ignore[arg-type]
        "",
    ]

    if completed:
        lines.append("## Completed")
        lines.append("")
        for item in completed:  # type: ignore[union-attr]
            receipt = item.get("receipt_filename") or "(no receipt)"  # type: ignore[union-attr]
            lines.append(f"- `{item.get('secret')}` — receipt: `{receipt}`")  # type: ignore[union-attr]
        lines.append("")

    if halted:
        lines.append("## Halted / skipped")
        lines.append("")
        for item in halted:  # type: ignore[union-attr]
            lines.append(f"- `{item.get('secret')}` — {item.get('reason')}")  # type: ignore[union-attr]
        lines.append("")

    remaining = [s for s in queue if s not in {  # type: ignore[union-attr]
        c.get("secret") for c in completed  # type: ignore[union-attr]
    } and s not in {
        h.get("secret") for h in halted  # type: ignore[union-attr]
    }]
    if remaining:
        lines.append("## Not attempted (batch stopped before reaching these)")
        lines.append("")
        for s in remaining:
            lines.append(f"- `{s}`")
        lines.append("")

    lines.append(
        "This batch rotation was initiated from the DëvSec dashboard. "
        "Per-secret verification receipts are in the individual files above."
    )
    lines.append("")

    markdown = "\n".join(lines)
    receipts_directory = repo_path / "data" / "rotation-receipts"
    try:
        receipts_directory.mkdir(parents=True, exist_ok=True)
        stamp = started.replace(":", "").replace(".", "-")[:19] if started else "unknown"
        filename = f"BATCH-{stamp}.md"
        (receipts_directory / filename).write_text(markdown, encoding="utf-8")
        _update_batch_job(batch_id, batch_receipt=filename)
    except OSError:
        pass


def _parse_event_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _history_event_is_terminal(event: dict[str, object]) -> bool:
    step = str(event.get("step") or "").upper()
    outcome = str(event.get("outcome") or "").lower()
    return (
        step in {"OPERATOR_OVERRIDE", "ROLLBACK"}
        or outcome == "halted"
        or (step == "REVOKE" and outcome == "succeeded")
        or (step == "GRACE" and outcome in {"started", "succeeded"})
    )


def _recent_enough_for_rediscovery(
    event: dict[str, object],
    *,
    now: datetime | None = None,
) -> bool:
    timestamp = _parse_event_timestamp(event.get("timestamp"))
    if timestamp is None:
        return False
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age = (reference - timestamp).total_seconds()
    return 0 <= age <= _ROTATION_JOB_REDISCOVERY_WINDOW_SECONDS


def _latest_scanned_repos(db_path: Path) -> list[dict[str, object]]:
    db = ObservatoryDB(db_path)
    try:
        rows = db.conn.execute(
            """
            select s.repo_name, s.repo_path
            from scans s
            join (
              select repo_name, max(started_at) as started_at
              from scans
              group by repo_name
            ) last on last.repo_name = s.repo_name and last.started_at = s.started_at
            order by s.repo_name asc
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def _discovered_rotation_job_id(repo_name: str, secret: str, rotation_id: object) -> str:
    seed = str(rotation_id or f"{repo_name}-{secret}")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", seed).strip("-")[:32]
    return f"discovered-{safe or uuid.uuid4().hex[:12]}"


def _active_rotation_job(repo_name: str, secret: str) -> dict[str, object] | None:
    with CHECK_JOBS_LOCK:
        for job in CHECK_JOBS.values():
            if (
                job.get("kind") == "rotation"
                and job.get("repo") == repo_name
                and job.get("secret") == secret
                and job.get("status") not in _TERMINAL_JOB_STATUSES
            ):
                return dict(job)
    return None


def _rediscover_rotation_jobs(
    db_path: Path,
    *,
    now: datetime | None = None,
) -> int:
    """Rehydrate recent in-flight rotation jobs after a dashboard restart."""
    discovered = 0
    for scan in _latest_scanned_repos(db_path):
        repo_name = str(scan.get("repo_name") or "").strip()
        repo_path_raw = scan.get("repo_path")
        if not repo_name or not repo_path_raw:
            continue
        repo_path = Path(str(repo_path_raw)).expanduser()
        rows = read_rotation_status(repo_path)
        history = read_rotation_history(repo_path, limit=100)
        for row in rows:
            secret = str(row.get("secret") or "")
            status = str(row.get("status") or "")
            if not secret or status not in ROTATION_INFLIGHT_STATUSES:
                continue
            rotation_id = row.get("rotation_id")
            latest_event = next(
                (
                    event
                    for event in history
                    if (
                        rotation_id
                        and str(event.get("rotation_id") or "") == str(rotation_id)
                    )
                    or str(event.get("secret") or "") == secret
                ),
                None,
            )
            if latest_event is None:
                continue
            if _history_event_is_terminal(latest_event):
                continue
            if not _recent_enough_for_rediscovery(latest_event, now=now):
                continue
            if _active_rotation_job(repo_name, secret):
                continue

            job_id = _discovered_rotation_job_id(repo_name, secret, rotation_id)
            job: dict[str, object] = {
                "id": job_id,
                "kind": "rotation",
                "status": "running",
                "repo": repo_name,
                "repo_path": str(repo_path),
                "secret": secret,
                "command": "rediscovered from data/rotation-log.jsonl",
                "options": {
                    "no_soak": False,
                    "skip_health_check": False,
                    "soak_minutes": None,
                    "test_mode": False,
                    "acknowledged_skipping_soak": False,
                    "acknowledged_skipping_health_check": False,
                },
                "phase": _rotation_job_phase_from_status(status),
                "message": f"Rediscovered in-flight rotation from disk ({status}).",
                "stdout_tail": [],
                "events_seen": _count_jsonl_lines(repo_path / "data" / "rotation-log.jsonl"),
                "started_at": latest_event.get("timestamp") or utc_now(),
                "finished_at": None,
                "exit_code": None,
                "error": None,
                "receipt_filename": None,
                "receipt_url": None,
                "verification_status": status,
            }
            with CHECK_JOBS_LOCK:
                if job_id not in CHECK_JOBS:
                    CHECK_JOBS[job_id] = job
                    discovered += 1
    return discovered


def _count_jsonl_lines(path: Path) -> int:
    """Cheap line-count of a JSONL file. Returns 0 when absent or unreadable."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())
    except OSError:
        return 0


def _classify_stdout_line(line: str) -> tuple[str | None, str | None]:
    """Map a npm-output line to (phase, message) updates for the job.

    The skill prints phase headers like ``=== HEALTH_CHECK ===`` and JSON-style
    event lines. We don't parse exhaustively; the receipt does that. This is
    just enough to show the operator coarse progress in the dashboard.
    """
    trimmed = line.strip()
    upper = trimmed.upper()
    phase_map = {
        "HEALTH_CHECK": ("health_check", "Pre-rotation health check."),
        "PREFLIGHT": ("preflight", "Preflight checks."),
        "ACQUIRE": ("acquire", "Acquiring the new value."),
        "WAITING_FOR_PASTE": (
            "waiting_for_paste",
            "Waiting for a provider-console paste.",
        ),
        "STAGE_CANARY": ("stage_canary", "Staging to canary."),
        "VERIFY_CANARY": ("verify_canary", "Verifying canary."),
        "STAGE_PROD": ("stage_prod", "Staging to production."),
        "VERIFY_PROD": ("verify_prod", "Verifying production."),
        "SOAK": ("soak", "Soaking — watching for auth-related errors."),
        "GRACE": ("grace", "Holding old value during the grace window."),
        "REVOKE": ("revoke", "Revoking the old value at the provider."),
    }
    for key, value in phase_map.items():
        if key in upper:
            return value
    if "HALT" in upper or "HALTED" in upper:
        return ("halted", trimmed[:200])
    if "VERIFIED" in upper or "ROTATED" in upper:
        return ("verified", trimmed[:200])
    return (None, None)


def _dt_now_monotonic() -> float:
    """Monotonic clock for subprocess deadlines."""
    import time as _time

    return _time.monotonic()


def quote_path(value: str) -> str:
    """URL-encode one path segment (filenames, repo names)."""
    from urllib.parse import quote as _quote

    return _quote(value, safe="")


SCANNER_LABELS = {
    "ai-static": "Inspecting AI and agent configuration",
    "install-hooks": "Classifying install-time package hooks",
    "workflow-audit": "Auditing GitHub Actions supply-chain surfaces",
    "semgrep": "Checking code vulnerability patterns",
    "gitleaks": "Looking for leaked secrets",
    "trufflehog": "Looking deeper for exposed credentials",
    "trivy": "Checking filesystem, dependencies, secrets, and config",
    "osv-scanner": "Checking open-source dependency advisories",
    "syft": "Building a dependency inventory",
    "grype": "Checking dependency vulnerability reachability",
    "checkov": "Reviewing infrastructure exposure",
    "medusa": "Checking AI agent and MCP attack paths",
    "legitify": "Checking connected platform posture",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dashboard_environment_signal() -> dict[str, Any]:
    """Runtime hints the dashboard needs to surface gates honestly.

    Mirrors scanners._legitify_token: any of these env vars satisfies the
    platform-posture token requirement. Stays in the server layer because
    storage shouldn't know about the runtime environment.
    """
    token_env_names = ("SCM_TOKEN", "SECURITY_OBSERVATORY_SCM_TOKEN", "LEGITIFY_TOKEN")
    scm_token_present = any((os.environ.get(name) or "").strip() for name in token_env_names)
    return {"scm_token_present": scm_token_present}


def _job_is_expired_terminal(job: dict[str, object], *, now: datetime, ttl_seconds: int) -> bool:
    """True if ``job`` is terminal and finished longer ago than the TTL.

    In-flight (non-terminal) jobs are never expired. A terminal job with no
    parseable timestamp is kept (we can't prove its age), so pruning only ever
    drops jobs we can confidently date as stale.
    """
    if str(job.get("status") or "") not in _TERMINAL_JOB_STATUSES:
        return False
    stamp = job.get("finished_at") or job.get("started_at")
    if not stamp:
        return False
    try:
        finished = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return False
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=timezone.utc)
    return (now - finished).total_seconds() >= ttl_seconds


def prune_terminal_check_jobs(
    *, now: datetime | None = None, ttl_seconds: int = CHECK_JOB_TTL_SECONDS
) -> list[str]:
    """Drop terminal CHECK_JOBS entries older than the TTL. Lock-safe.

    Live and recently-finished jobs are retained, so the check-status poll
    contract is unchanged for any job a client could still be watching.
    Returns the ids that were pruned.
    """
    current = now or datetime.now(timezone.utc)
    with CHECK_JOBS_LOCK:
        expired = [
            job_id
            for job_id, job in CHECK_JOBS.items()
            if _job_is_expired_terminal(job, now=current, ttl_seconds=ttl_seconds)
        ]
        for job_id in expired:
            del CHECK_JOBS[job_id]
    return expired


def job_snapshot(job_id: str) -> dict[str, object] | None:
    # Poll path is the natural heartbeat: prune stale terminal jobs whenever a
    # client checks status, bounding in-memory growth on a long-lived server.
    prune_terminal_check_jobs()
    with CHECK_JOBS_LOCK:
        job = CHECK_JOBS.get(job_id)
        return dict(job) if job else None


def update_job(job_id: str, **updates: object) -> None:
    with CHECK_JOBS_LOCK:
        if job_id in CHECK_JOBS:
            CHECK_JOBS[job_id].update(updates)


def args_for_audits(audits: list[str]) -> Namespace:
    args = Namespace(
        quick="quick" in audits,
        code="code" in audits,
        ai="ai" in audits,
        deps="deps" in audits,
        secrets="secrets" in audits,
        iac="iac" in audits,
        platform_posture="platform-posture" in audits,
        full="full" in audits,
    )
    if not any((args.quick, args.code, args.ai, args.deps, args.secrets, args.iac, args.platform_posture, args.full)):
        args.quick = True
    return args


def format_location(finding: dict[str, object]) -> str:
    file = finding.get("file") or "repository"
    line = finding.get("line")
    return f"{file}:{line}" if line else str(file)


def run_check_job(
    job_id: str,
    db_path: Path,
    repo_path: Path,
    args: Namespace,
    *,
    scanner_names: list[str] | None = None,
    agent_lab_proposal_id: str | None = None,
    agent_lab_preview: dict[str, Any] | None = None,
) -> None:
    scanners = list(dict.fromkeys(scanner_names or scanner_names_for_profile(args)))
    total = max(len(scanners), 1)
    update_job(
        job_id,
        status="running",
        progress=2,
        message="Preparing local scan",
        currentStep=None,
        startedAt=utc_now(),
    )

    def progress(event: dict[str, object]) -> None:
        index = int(event.get("index", 1))
        scanner = str(event.get("scanner", "scanner"))
        label = SCANNER_LABELS.get(scanner, scanner)
        if event.get("event") == "scanner_started":
            percent = max(5, round(((index - 1) / total) * 90))
            update_job(job_id, progress=percent, message=label, currentStep=label, currentScanner=scanner)
        else:
            percent = min(95, round((index / total) * 90))
            if event.get("error"):
                label = f"{label} skipped or incomplete"
            update_job(job_id, progress=percent, message=label, currentStep=label, currentScanner=scanner)

    try:
        scan = scan_repo(repo_path, args, db_path.parent.parent, progress_callback=progress, scanner_names=scanners)
        if agent_lab_proposal_id:
            _record_agent_lab_execution_result(
                db_path,
                agent_lab_proposal_id,
                agent_lab_preview or {},
                {
                    "job_id": job_id,
                    "mode": "approved_run",
                    "status": "complete",
                    "scan_id": scan.get("scan_id"),
                    "report_path": scan.get("report_path"),
                    "started_at": scan.get("started_at"),
                    "finished_at": scan.get("finished_at"),
                    "profile": scan.get("profile"),
                    "scanner_statuses": scan.get("scanners") or [],
                    "evidence_gaps": scan.get("evidence_gaps") or [],
                },
            )
        update_job(
            job_id,
            status="complete",
            progress=100,
            message="Check complete",
            currentStep=None,
            currentScanner=None,
            scan=scan,
            finishedAt=utc_now(),
        )
    except Exception as exc:
        if agent_lab_proposal_id:
            _record_agent_lab_execution_result(
                db_path,
                agent_lab_proposal_id,
                agent_lab_preview or {},
                {
                    "job_id": job_id,
                    "mode": "approved_run",
                    "status": "failed",
                    "error": str(exc),
                    "finished_at": utc_now(),
                },
            )
        update_job(
            job_id,
            status="failed",
            progress=100,
            message="Check failed",
            error=str(exc),
            currentStep=None,
            currentScanner=None,
            finishedAt=utc_now(),
        )


def _record_agent_lab_execution_result(
    db_path: Path,
    proposal_id: str,
    preview: dict[str, Any],
    execution: dict[str, Any],
) -> None:
    db = ObservatoryDB(db_path)
    try:
        proposal = db.get_agent_lab_proposal(proposal_id)
        if not proposal:
            return
        plan = dict(proposal.get("final_execution_plan") or {})
        plan.setdefault("version", "agent-lab.execution-plan.v1")
        plan["approval_state"] = proposal.get("approval_state")
        if preview:
            plan["last_preview"] = preview
        plan["last_execution"] = execution
        _update_agent_lab_plan_item_statuses(plan, execution)
        db.update_agent_lab_execution_plan(proposal_id=proposal_id, final_execution_plan=plan)
    finally:
        db.close()


def _update_agent_lab_plan_item_statuses(plan: dict[str, Any], execution: dict[str, Any]) -> None:
    items = plan.get("items")
    if not isinstance(items, list):
        return
    status = str(execution.get("status") or "")
    evidence_gaps = [item for item in execution.get("evidence_gaps") or [] if isinstance(item, dict)]
    scan_id = execution.get("scan_id")
    report_path = execution.get("report_path")
    item_status = {
        "queued": "queued_for_execution",
        "complete": "executed_with_evidence_gaps" if evidence_gaps else "executed",
        "failed": "execution_failed",
    }.get(status, status or "unknown")
    for item in items:
        if not isinstance(item, dict):
            continue
        item["status"] = item_status
        if scan_id:
            item["scan_id"] = scan_id
        if report_path:
            item["report_path"] = report_path


# Catalog-declared install methods this server can drive automatically. Each
# entry is a tiny dispatch record consumed by `install_via_package_manager`.
# Binary names come from the catalog contract, not user input — the regex
# below makes the shell-injection refusal explicit anyway.
_PACKAGE_BINARY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

# Credential-route path matchers. The tool_id and key segments are constrained
# to the same character class enforced by `credentials._validate_identifier`,
# so a malformed URL is rejected at the routing layer before the validator
# runs again deeper in.
_CREDENTIAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CREDENTIALS_TOOL_PATH_RE = re.compile(
    r"^/api/tools/(?P<tool_id>[A-Za-z0-9][A-Za-z0-9._-]{0,63})/credentials/?$"
)
_CREDENTIALS_KEYS_PATH_RE = re.compile(
    r"^/api/tools/(?P<tool_id>[A-Za-z0-9][A-Za-z0-9._-]{0,63})/credentials/keys/?$"
)
_CREDENTIALS_KEY_PATH_RE = re.compile(
    r"^/api/tools/(?P<tool_id>[A-Za-z0-9][A-Za-z0-9._-]{0,63})"
    r"/credentials/(?P<key>[A-Za-z0-9][A-Za-z0-9._-]{0,63})/?$"
)

# Setup-card endpoints. The tool_id constraint matches the credential routes
# so the routing layer rejects malformed URLs before the runner sees them.
_SETUP_PROBE_PATH_RE = re.compile(
    r"^/api/tools/(?P<tool_id>[A-Za-z0-9][A-Za-z0-9._-]{0,63})/setup/probe/?$"
)
_SETUP_CONFIG_PATH_RE = re.compile(
    r"^/api/tools/(?P<tool_id>[A-Za-z0-9][A-Za-z0-9._-]{0,63})/setup/config/?$"
)

# Code-fix proposal surface (S-043). The id is the slug minted when a proposal
# is recorded (`fix_<repo>_<ts>_<hash12>`): word chars only, so the routing
# layer rejects a malformed URL before any DB lookup runs. The land route shares
# the same id class plus a trailing `/land`.
_FIX_PROPOSAL_ID_RE = re.compile(r"^/api/fix-proposals/(?P<proposal_id>[A-Za-z0-9._-]{1,200})/?$")
_FIX_PROPOSAL_LAND_RE = re.compile(
    r"^/api/fix-proposals/(?P<proposal_id>[A-Za-z0-9._-]{1,200})/land/?$"
)


def _fix_proposal_summary(record: dict[str, Any]) -> dict[str, Any]:
    """List-row projection of a fix proposal — no diff body, no finding text."""
    diff = str(record.get("diff") or "")
    added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
    classification = record.get("classification") or {}
    return {
        "id": record.get("id"),
        "repo_name": record.get("repo_name"),
        "title": record.get("title"),
        "case_id": record.get("case_id"),
        "base_branch": record.get("base_branch"),
        "head_branch": record.get("head_branch"),
        "fix_class": record.get("fix_class"),
        "auto_merge_eligible": bool(record.get("auto_merge_eligible")),
        "status": record.get("status"),
        "clean_room_status": record.get("clean_room_status"),
        "landing_outcome": record.get("landing_outcome"),
        "changed_files": classification.get("changed_files") or [],
        "diff_stat": {"added": added, "removed": removed},
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
    }


def _fix_proposal_detail(record: dict[str, Any]) -> dict[str, Any]:
    """Detail projection: diff + clean-room verdict + the diff-class invariants.

    The ``invariants`` are the fixed checklist a clean-room reviewer verifies for
    this fix class — every one a statement about the diff, never the finding that
    motivated it. Nothing here carries finding text; the proposal store holds
    none, and this surface reads it as-is.
    """
    fix_class = str(record.get("fix_class") or "unknown")
    return {
        "proposal": _fix_proposal_summary(record),
        "diff": str(record.get("diff") or ""),
        "diff_sha256": record.get("diff_sha256"),
        "clean_room": {
            "status": record.get("clean_room_status"),
            "reviewer": record.get("clean_room_reviewer"),
            "reviewed_at": record.get("clean_room_reviewed_at"),
            "notes": record.get("clean_room_notes"),
            "checked_invariants": record.get("clean_room_checked_invariants") or [],
            "invariants": invariants_for(fix_class),
        },
        "landing": {
            "outcome": record.get("landing_outcome"),
            "reasons": record.get("landing_reasons") or [],
            "decided_at": record.get("landing_decided_at"),
        },
    }

_PACKAGE_MANAGER_DISPATCH: dict[str, dict[str, Any]] = {
    "homebrew": {
        "program": "brew",
        "args": ("install", "{binary}"),
        "env": {
            "HOMEBREW_NO_AUTO_UPDATE": "1",
            "HOMEBREW_NO_ANALYTICS": "1",
            "HOMEBREW_NO_ENV_HINTS": "1",
        },
        "timeout": 600,
        "missing_prereq_hint": "Homebrew is not installed. Install Homebrew first: https://brew.sh",
    },
    "uv-tool": {
        "program": "uv",
        "args": ("tool", "install", "{binary}"),
        "env": {},
        "timeout": 600,
        "missing_prereq_hint": (
            "uv is not installed. Install uv first: "
            "https://docs.astral.sh/uv/getting-started/installation/"
        ),
    },
}


# Loopback hostnames the dashboard accepts as its own origin. The server only
# ever binds 127.0.0.1, so a request whose Origin host is anything else came
# from a foreign site (classic CSRF) or a DNS-rebinding page pointing a
# attacker-controlled name at loopback — neither is the operator's own tab.
_LOOPBACK_ORIGIN_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# Per-process confirmation token. It is minted once per server process and only
# ever handed out on a same-origin read (`GET /api/csrf-token`); the same-origin
# policy stops a cross-site page from reading that response, so possession of
# the token positively attests the request came from a real dashboard session.
# This is what `human_authorized` now means on the dashboard path — a positive,
# CSRF-surviving intent signal, not "a POST happened to arrive."
_DASHBOARD_CSRF_TOKEN = secrets.token_urlsafe(32)

# Mutating routes deliberately exempt from the cross-origin guard. A honeytoken
# embedded in a URL must beacon on a cross-origin GET/POST by design — guarding
# it would break the decoy. This is the single, intentional hole in the guard.
_CSRF_EXEMPT_PATHS = frozenset({"/api/honey/trigger"})


def _is_json_content_type(content_type: str | None) -> bool:
    """True for ``application/json`` (ignoring any ``; charset=…`` suffix)."""
    if not content_type:
        return False
    return content_type.split(";", 1)[0].strip().casefold() == "application/json"


def _match_exact(path):
    return lambda parsed: () if parsed.path == path else None


def _match_exact_parsed(path):
    return lambda parsed: (parsed,) if parsed.path == path else None


def _match_rstrip_parsed(path):
    return lambda parsed: (parsed,) if parsed.path.rstrip("/") == path else None


def _match_prefix(prefix):
    return lambda parsed: (parsed.path.removeprefix(prefix),) if parsed.path.startswith(prefix) else None


def _match_prefix_strip(prefix):
    return lambda parsed: (parsed.path.removeprefix(prefix).strip("/"),) if parsed.path.startswith(prefix) else None


def _match_prefix_parsed(prefix):
    return lambda parsed: (parsed,) if parsed.path.startswith(prefix) else None


def _match_docs():
    return lambda parsed: (parsed.path,) if parsed.path.startswith("/docs/") and parsed.path.endswith(".md") else None


def _match_regex_groups(pattern, *names):
    def matcher(parsed):
        found = pattern.match(parsed.path)
        return tuple(found.group(name) for name in names) if found else None
    return matcher


def assemble_summary_payload(db) -> dict[str, object]:
    """Build the /api/summary payload, including per-repo rotation enrichment.

    Lifted out of the GET request handler so the route stays a thin seam and
    the assembly logic (dashboard payload + corruption-recovery notice +
    environment signal + recovery playbooks + per-repo rotation state and
    inferred secret names) is independently readable and testable.
    """
    payload = db.dashboard_payload()
    # Honest recovery: if the history DB was corrupt, ObservatoryDB
    # quarantined it and started fresh. Surface that so an emptied
    # dashboard reads as a preserved-and-recovered event, not silent
    # data loss. Conditional, so healthy-path responses are unchanged.
    if db.recovered_from_corruption:
        payload["history_recovery"] = {
            "status": "recovered",
            "message": (
                "Your scan history could not be read and was quarantined. "
                "The previous database is preserved on this machine; a "
                "fresh history was started."
            ),
            "quarantined_path": (
                str(db.quarantined_path) if db.quarantined_path else None
            ),
        }
    payload["environment"] = dashboard_environment_signal()
    payload["recovery_playbooks"] = build_recovery_playbooks(payload.get("active_cases") or [])
    # Per-repo rotation signal — drives the RotationStatusCard on every repo
    # view, including the "Set up rotation" CTA for repos without scaffolding.
    # The enrichment loop lives in dashboard_payload (payload assembly), so this
    # route stays a thin seam over the assembly + cross-cutting decorations.
    enrich_repos_with_rotation(payload)
    return payload


class DashboardHandler(SimpleHTTPRequestHandler):
    db_path: Path
    assets_dir: Path

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.assets_dir), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def send_json(self, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json_error(self, status: int, message: str, **extra: object) -> None:
        body = json.dumps({"error": message, **extra}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_accepted_json(self, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(202)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_no_content(self) -> None:
        self.send_response(204)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def send_html(self, html_body: str) -> None:
        body = html_body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_download(self, body: bytes, *, content_type: str, filename: str) -> None:
        safe_filename = re.sub(r"[^A-Za-z0-9_.-]+", "-", filename).strip("-") or "security-report"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{safe_filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_repo_doc(self, path: str) -> None:
        # docs/ lives at the repo root; the package sits at src/security_observatory/.
        repo_root = Path(__file__).resolve().parents[2]
        docs_root = (repo_root / "docs").resolve()
        candidate = (docs_root / path.removeprefix("/docs/")).resolve()
        if not candidate.is_file() or (docs_root not in candidate.parents and candidate != docs_root):
            self.send_error(404, "Doc not found.")
            return
        try:
            source = candidate.read_text(encoding="utf-8")
        except OSError:
            self.send_error(404, "Doc not found.")
            return
        rendered = render_markdown(source)
        title = _docs_title(source, candidate.stem)
        page = _docs_page_shell(title=title, body=rendered, source_path=str(candidate.relative_to(repo_root)))
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _origin_is_same_site(self) -> bool:
        """True if a state-mutating request demonstrably came from the operator's
        own dashboard tab.

        A browser stamps every cross-origin request with an ``Origin`` (and a
        ``Sec-Fetch-Site``) header it will not let script forge, so a foreign
        value is a reliable tell of a cross-site or DNS-rebinding attack. A
        non-browser client (the CLI, tests, curl) sends neither header; those
        were never the CSRF threat — a browser cannot omit ``Origin`` on a
        cross-origin request — so a request with no provenance hints is allowed.
        """
        sec_fetch_site = self.headers.get("Sec-Fetch-Site")
        if sec_fetch_site is not None and sec_fetch_site not in {"same-origin", "none"}:
            return False
        origin = self.headers.get("Origin")
        if origin in (None, "", "null"):
            return True
        parsed = urlparse(origin)
        if parsed.scheme != "http" or parsed.hostname not in _LOOPBACK_ORIGIN_HOSTS:
            return False
        try:
            return parsed.port == self.server.server_port
        except ValueError:
            return False

    def _guard_mutation(self, parsed) -> bool:
        """Gate every mutating ``do_POST``/``do_DELETE`` before it dispatches.

        Rejects cross-origin requests with a clean JSON ``403`` and body-bearing
        requests that are not ``application/json`` with a clean JSON ``415`` —
        the two defenses the lens report found entirely absent. Returns ``True``
        when the request may proceed. The honey-key trigger is exempt by design.
        """
        if parsed.path in _CSRF_EXEMPT_PATHS:
            return True
        if not self._origin_is_same_site():
            self.send_json_error(403, "Cross-origin request rejected.")
            return False
        if self.command == "POST" and not _is_json_content_type(self.headers.get("Content-Type")):
            self.send_json_error(415, "Mutating requests must use Content-Type: application/json.")
            return False
        return True

    def _human_confirmation_present(self) -> bool:
        """Whether this request carries the valid per-process confirmation token.

        This is the positive intent signal that re-arms the suppression gate:
        ``human_authorized`` is true only when the request echoes the token that
        a real dashboard session fetched same-origin — never merely because a
        POST arrived.
        """
        supplied = self.headers.get("X-DevSec-Confirm") or ""
        return bool(supplied) and secrets.compare_digest(supplied, _DASHBOARD_CSRF_TOKEN)

    def do_GET(self) -> None:
        # Mirror the do_POST / do_DELETE convention: any unhandled error in a GET
        # route — notably a corrupt history DB surfacing from ObservatoryDB(...)
        # — becomes a calm JSON 500 instead of a raw traceback or a broken
        # socket. ObservatoryDB now self-heals genuine corruption, so this is the
        # backstop for everything else.
        try:
            self._handle_get()
        except Exception as exc:  # noqa: BLE001 - last-resort guard for any GET route
            self.send_json_error(500, str(exc))

    # ------------------------------------------------------------------
    # Route table
    #
    # do_GET/do_POST/do_DELETE dispatch through these ordered tables instead
    # of long if/elif chains. Each entry pairs a matcher (see the module-level
    # _match_* helpers) with the name of the handler method to call. A matcher
    # returns the positional args to hand the handler — often empty, sometimes
    # the parsed URL or a path segment — or None when the path does not match.
    # Order matters: a more specific prefix must precede one that would also
    # swallow it (e.g. /api/rotation/jobs/batch/ before /api/rotation/jobs/).
    # ------------------------------------------------------------------
    _GET_ROUTES = [
        (_match_exact("/api/csrf-token"), "_get_csrf_token"),
        (_match_docs(), "serve_repo_doc"),
        (_match_exact("/favicon.ico"), "_get_favicon"),
        (_match_exact("/api/summary"), "_get_summary"),
        (_match_exact("/api/tool-catalog"), "_get_tool_catalog"),
        (_match_exact("/api/security-packs"), "_get_security_packs"),
        (_match_exact("/api/scan-profiles"), "_get_scan_profiles"),
        (_match_exact_parsed("/api/agent-lab/context"), "_get_agent_lab_context"),
        (_match_exact_parsed("/api/agent-lab/proposals"), "_get_agent_lab_proposals"),
        (_match_exact_parsed("/api/agent-lab/proposals/execution-preview"), "preview_agent_lab_proposal_execution"),
        (_match_exact_parsed("/api/ai-follow-up/prompt"), "serve_ai_followup_prompt"),
        (_match_exact_parsed("/api/ai-follow-up/resolution-runs"), "serve_ai_followup_resolution_runs"),
        (_match_exact_parsed("/api/install-preview"), "_get_install_preview"),
        (_match_exact_parsed("/api/honey/keys"), "_get_honey_keys"),
        (_match_exact_parsed("/api/honey/suggest-placement"), "_get_honey_suggest_placement"),
        (_match_prefix_parsed("/api/honey/open/"), "_get_honey_open"),
        (_match_exact_parsed("/api/honey/trigger"), "_get_honey_trigger"),
        (_match_exact("/api/projects"), "_get_projects"),
        (_match_exact_parsed("/api/check-status"), "_get_check_status"),
        (_match_prefix("/api/rotation/status/"), "serve_rotation_status"),
        (_match_prefix_parsed("/api/rotation/history/"), "_get_rotation_history"),
        (_match_prefix("/api/rotation/receipts/"), "serve_rotation_receipt"),
        (_match_prefix_strip("/api/rotation/jobs/batch/"), "serve_rotation_batch_job"),
        (_match_prefix_strip("/api/rotation/jobs/"), "serve_rotation_job"),
        (_match_exact("/api/tools/credentials"), "serve_all_credential_keys"),
        (_match_regex_groups(_CREDENTIALS_KEYS_PATH_RE, "tool_id"), "serve_credential_keys"),
        (_match_regex_groups(_SETUP_CONFIG_PATH_RE, "tool_id"), "serve_tool_setup_config"),
        (_match_rstrip_parsed("/report"), "_get_report_page"),
        (_match_exact_parsed("/api/report"), "_get_report_download"),
        (_match_exact_parsed("/api/scan-diff"), "_get_scan_diff"),
        (_match_rstrip_parsed("/api/fix-proposals"), "_get_fix_proposals"),
        (_match_regex_groups(_FIX_PROPOSAL_ID_RE, "proposal_id"), "serve_fix_proposal_detail"),
    ]

    _POST_ROUTES = [
        (_match_exact("/api/case-decision"), "save_case_decision"),
        (_match_exact("/api/ai-follow-up/resolutions/preview"), "preview_ai_followup_resolutions"),
        (_match_exact("/api/ai-follow-up/resolutions/apply"), "apply_ai_followup_resolutions"),
        (_match_exact("/api/agent-lab/proposals"), "import_agent_lab_proposal"),
        (_match_exact("/api/agent-lab/proposals/decision"), "save_agent_lab_proposal_decision"),
        (_match_exact("/api/agent-lab/proposals/run"), "run_agent_lab_proposal"),
        (_match_exact("/api/honey/keys"), "create_honey_key"),
        (_match_exact("/api/honey/archive"), "archive_honey_key"),
        (_match_exact("/api/honey/incident-step"), "update_honey_incident_step"),
        (_match_exact("/api/honey/incident-close"), "close_honey_incident"),
        (_match_exact("/api/honey/insert"), "insert_honey_key_file"),
        (_match_exact_parsed("/api/honey/trigger"), "_post_honey_trigger"),
        (_match_exact("/api/managed-tools/install"), "install_managed_tool"),
        (_match_exact("/api/managed-tools/uninstall"), "uninstall_managed_tool"),
        (_match_exact("/api/tools/install-via-pkg"), "install_via_package_manager"),
        (_match_exact("/api/tools/recheck-install-state"), "recheck_install_state"),
        (_match_exact("/api/reset/scan-results/preview"), "preview_scan_results_reset"),
        (_match_exact("/api/reset/scan-results"), "reset_scan_results"),
        (_match_prefix("/api/rotation/scaffold/"), "serve_rotation_scaffold_handoff"),
        (_match_prefix("/api/rotation/trigger-batch/"), "serve_rotation_trigger_batch"),
        (_match_prefix_strip("/api/rotation/jobs/batch/"), "serve_rotation_batch_job"),
        (_match_prefix("/api/rotation/trigger/"), "serve_rotation_trigger"),
        (_match_prefix_strip("/api/rotation/paste/"), "serve_rotation_paste"),
        (_match_regex_groups(_FIX_PROPOSAL_LAND_RE, "proposal_id"), "decide_fix_landing"),
        (_match_regex_groups(_CREDENTIALS_TOOL_PATH_RE, "tool_id"), "store_tool_credential"),
        (_match_regex_groups(_SETUP_PROBE_PATH_RE, "tool_id"), "run_tool_setup_probe"),
        (_match_regex_groups(_SETUP_CONFIG_PATH_RE, "tool_id"), "save_tool_setup_config"),
        (_match_exact("/api/run-check"), "_post_run_check"),
    ]

    _DELETE_ROUTES = [
        (_match_regex_groups(_CREDENTIALS_KEY_PATH_RE, "tool_id", "key"), "delete_tool_credential"),
        (_match_regex_groups(_SETUP_CONFIG_PATH_RE, "tool_id"), "forget_tool_setup_config"),
    ]

    def _dispatch(self, routes) -> bool:
        """Walk an ordered route table and invoke the first matching handler.

        Returns True when a route handled the request, False when none matched
        (the caller then applies the verb's default — the static-file fallback
        for GET, a 404 for POST/DELETE).
        """
        parsed = urlparse(self.path)
        for matcher, handler_name in routes:
            args = matcher(parsed)
            if args is not None:
                getattr(self, handler_name)(*args)
                return True
        return False

    def _handle_get(self) -> None:
        if self._dispatch(self._GET_ROUTES):
            return
        if urlparse(self.path).path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def _get_csrf_token(self) -> None:
        # Same-origin read only: the same-origin policy stops a cross-site
        # page from reading this response, so the token it hands back is a
        # secret the operator's own tab can prove it holds on mutating calls.
        self.send_json({"token": _DASHBOARD_CSRF_TOKEN})

    def _get_favicon(self) -> None:
        icon_path = self.assets_dir / "favicon.png"
        if not icon_path.exists():
            self.send_response(204)
            self.end_headers()
            return
        body = icon_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _get_summary(self) -> None:
        db = ObservatoryDB(self.db_path)
        try:
            payload = assemble_summary_payload(db)
        finally:
            db.close()
        self.send_json(payload)

    def _get_tool_catalog(self) -> None:
        db = ObservatoryDB(self.db_path)
        try:
            managed_tool_records = db.list_managed_tools()
        finally:
            db.close()
        self.send_json({"items": tool_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)})

    def _get_security_packs(self) -> None:
        db = ObservatoryDB(self.db_path)
        try:
            managed_tool_records = db.list_managed_tools()
        finally:
            db.close()
        self.send_json({"items": security_pack_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)})

    def _get_scan_profiles(self) -> None:
        db = ObservatoryDB(self.db_path)
        try:
            managed_tool_records = db.list_managed_tools()
        finally:
            db.close()
        self.send_json({"items": scan_profile_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)})

    def _get_agent_lab_context(self, parsed) -> None:
        query = parse_qs(parsed.query)
        repo_path = query.get("repoPath", query.get("repo_path", [""]))[0] or None
        repo_name = query.get("repoName", query.get("repo_name", [""]))[0] or None
        db = ObservatoryDB(self.db_path)
        try:
            payload = build_agent_context_payload(db, repo_path=repo_path, repo_name=repo_name)
        finally:
            db.close()
        self.send_json(payload)

    def _get_agent_lab_proposals(self, parsed) -> None:
        query = parse_qs(parsed.query)
        repo_name = query.get("repoName", query.get("repo_name", [""]))[0] or None
        approval_state = query.get("approvalState", query.get("approval_state", [""]))[0] or None
        db = ObservatoryDB(self.db_path)
        try:
            proposals = db.list_agent_lab_proposals(repo_name=repo_name, approval_state=approval_state, limit=100)
        finally:
            db.close()
        self.send_json({"items": proposals})

    def _get_install_preview(self, parsed) -> None:
        query = parse_qs(parsed.query)
        tool_id = query.get("toolId", query.get("tool_id", [""]))[0]
        pack_id = query.get("packId", query.get("pack_id", [""]))[0]
        db = ObservatoryDB(self.db_path)
        try:
            managed_tool_records = db.list_managed_tools()
        finally:
            db.close()
        if tool_id:
            catalog = tool_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
            item = next((tool for tool in catalog if tool.get("id") == tool_id), None)
            if not item:
                self.send_error(404, "Tool not found.")
                return
            self.send_json({"preview": item.get("install_preview"), "tool": item})
            return
        if pack_id:
            packs = security_pack_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
            item = next((pack for pack in packs if pack.get("id") == pack_id), None)
            if not item:
                self.send_error(404, "Security Pack not found.")
                return
            self.send_json({"preview": item.get("install_preview"), "pack": item})
            return
        self.send_error(400, "toolId or packId is required.")

    def _get_honey_keys(self, parsed) -> None:
        query = parse_qs(parsed.query)
        project_id = query.get("projectId", [""])[0] or None
        db = ObservatoryDB(self.db_path)
        try:
            self.send_json({"keys": db.list_honey_keys(project_id=project_id), "placement_paths": list(DEFAULT_PLACEMENT_PATHS)})
        finally:
            db.close()

    def _get_honey_suggest_placement(self, parsed) -> None:
        """Propose the top-consequence node to guard with a decoy.

        Read-only: nothing is minted, bound, or written here. It returns the node to
        guard (by human-readable label, never asking a human to author a 24-hex
        fingerprint), why it ranks highest, whether it is solid enough to pre-offer
        for auto-placement, and a preview of the decoy content. The actual mint +
        bind happens when the human POSTs /api/honey/keys with this assetNodeId, and
        planting still requires the confirm-before-write rail on /api/honey/insert.
        """
        query = parse_qs(parsed.query)
        repo_path = (query.get("repoPath", [""])[0] or "").strip()
        repo_name = (query.get("repoName", [""])[0] or "").strip()
        if not repo_name and repo_path:
            repo_name = Path(repo_path).name
        if not repo_name:
            self.send_error(400, "repoName or repoPath is required to suggest a placement.")
            return
        db = ObservatoryDB(self.db_path)
        try:
            scan = db.latest_scan_for_repo(repo_name)
            if not scan:
                self.send_json({
                    "suggestion": None,
                    "reason_none": f"No scan found for '{repo_name}'. Run a scan to build the asset graph first.",
                })
                return
            scan_id = str(scan["id"])
            nodes = db.list_asset_nodes(scan_id=scan_id)
            edges = db.list_asset_edges(scan_id=scan_id)
            suggestion = suggest_placement_node(nodes, edges)
            if suggestion is None:
                self.send_json({
                    "suggestion": None,
                    "reason_none": "This scan built no asset-graph nodes, so there is nothing to guard yet.",
                })
                return
            signing_secret = db.honey_signing_secret()
        finally:
            db.close()

        # Decoy content preview: minted in-memory and NOT stored. It shows the human
        # the shape of the decoy file to confirm; the real, tracked Honey Key is
        # generated only when they create it via POST /api/honey/keys.
        preview_material = generate_honey_key(signing_secret)
        decoy_preview = build_decoy_snippets(
            base_url=self.request_base_url(),
            name=f"Decoy for {suggestion.node['label']}",
            token=preview_material.token,
            token_id=preview_material.token_id,
            signing_secret=signing_secret,
        )
        self.send_json({
            "suggestion": suggestion.to_dict(),
            "recommended_placement_path": _suggested_decoy_path(suggestion.node["label"]),
            "decoy_preview": decoy_preview,
            "notice": (
                "This is a proposal. No Honey Key is minted and no file is written "
                "until you create the decoy and confirm placement. The preview content "
                "uses a throwaway token; the real Honey Key is generated when you "
                "create it."
            ),
        })

    def _get_honey_open(self, parsed) -> None:
        token_id = parsed.path.removeprefix("/api/honey/open/").strip("/")
        query = parse_qs(parsed.query)
        signature = query.get("sig", [""])[0]
        db = ObservatoryDB(self.db_path)
        try:
            signing_secret = db.honey_signing_secret()
            key = db.get_honey_key(token_id)
            if key and open_url_is_valid(signing_secret, token_id, signature):
                headers = sanitize_headers(dict(self.headers.items()))
                db.record_honey_key_trigger(
                    honey_key=key,
                    ip_address=self.client_address[0] if self.client_address else None,
                    user_agent=self.headers.get("User-Agent"),
                    method="GET",
                    path=self.path,
                    headers=headers,
                    body_summary=None,
                    confidence=0.92,
                    source_type="url_open",
                )
        finally:
            db.close()
        self.send_no_content()

    def _get_honey_trigger(self, parsed) -> None:
        self.trigger_honey_key(parsed, method="GET")

    def _get_projects(self) -> None:
        root = Path(os.environ.get("SECURITY_OBSERVATORY_PROJECTS_ROOT", "~/Dev/Projects")).expanduser()
        repos = [{"name": repo.name, "path": str(repo)} for repo in discover_repos(root)]
        self.send_json({"root": str(root), "repos": repos})

    def _get_check_status(self, parsed) -> None:
        job_id = parse_qs(parsed.query).get("jobId", [""])[0]
        job = job_snapshot(job_id)
        if not job:
            self.send_error(404, "Check job not found.")
            return
        self.send_json({"job": job})

    def _get_rotation_history(self, parsed) -> None:
        repo_name = parsed.path.removeprefix("/api/rotation/history/")
        limit_raw = parse_qs(parsed.query).get("limit", ["20"])[0]
        self.serve_rotation_history(repo_name, limit_raw)

    def _get_report_page(self, parsed) -> None:
        query = parse_qs(parsed.query)
        scan_id = query.get("scanId", [""])[0]
        kind = query.get("kind", ["prompt"])[0]
        if kind not in {"raw", "prompt"}:
            self.send_error(400, "Report kind must be raw or prompt.")
            return
        db = ObservatoryDB(self.db_path)
        try:
            scan = db.scan_export(scan_id)
        finally:
            db.close()
        if not scan:
            self.send_error(404, "Scan report not found.")
            return
        self.send_html(report_page(scan, kind))

    def _get_report_download(self, parsed) -> None:
        query = parse_qs(parsed.query)
        scan_id = query.get("scanId", [""])[0]
        kind = query.get("kind", ["raw"])[0]
        if kind not in {"raw", "prompt"}:
            self.send_error(400, "Report kind must be raw or prompt.")
            return
        db = ObservatoryDB(self.db_path)
        try:
            scan = db.scan_export(scan_id)
        finally:
            db.close()
        if not scan:
            self.send_error(404, "Scan report not found.")
            return
        if kind == "raw":
            body = raw_report_export(scan)
            self.send_download(body, content_type="application/json; charset=utf-8", filename=f"{scan_id}-raw-report.json")
            return
        prompt = build_ai_prompt(scan).encode("utf-8")
        self.send_download(prompt, content_type="text/markdown; charset=utf-8", filename=f"{scan_id}-ai-next-steps-prompt.md")

    def _get_scan_diff(self, parsed) -> None:
        # Arbitrary scan-to-scan diff: the dashboard's base/head picker
        # passes any two saved scan ids, not just a scan and its immediate
        # predecessor. The history series itself ships inside /api/summary
        # (`summary.history`); this route adds the on-demand comparison.
        query = parse_qs(parsed.query)
        base_id = query.get("base", [""])[0]
        head_id = query.get("head", [""])[0]
        if not base_id or not head_id:
            self.send_json_error(400, "scan-diff requires base and head scan ids.")
            return
        db = ObservatoryDB(self.db_path)
        try:
            diff = db.scan_diff(base_id, head_id)
        finally:
            db.close()
        if diff is None:
            self.send_json_error(404, "One or both scans were not found.")
            return
        self.send_json(diff)

    def _get_fix_proposals(self, parsed) -> None:
        # The hands-off code-fix flow (propose -> clean-room review -> land)
        # was previously reachable only through the MCP rw adapter. This
        # read surface lists the persisted proposals so a dashboard-only
        # operator can see them. It exposes no finding text — the proposal
        # store never holds any — and adds no land path of its own (see the
        # POST route below, which delegates to the proven `decide_landing`).
        query = parse_qs(parsed.query)
        repo_name = query.get("repoName", query.get("repo_name", [""]))[0] or None
        status_filter = query.get("status", [""])[0] or None
        db = ObservatoryDB(self.db_path)
        try:
            proposals = db.list_fix_proposals(repo_name=repo_name, status=status_filter, limit=100)
        finally:
            db.close()
        self.send_json({"items": [_fix_proposal_summary(item) for item in proposals]})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not self._guard_mutation(parsed):
            return
        if not self._dispatch(self._POST_ROUTES):
            self.send_error(404)

    def _post_honey_trigger(self, parsed) -> None:
        self.trigger_honey_key(parsed, method="POST")

    def _post_run_check(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            repo_path = Path(str(payload.get("repoPath", ""))).expanduser().resolve()
            audits = [str(item) for item in payload.get("audits", [])]
            if not repo_path.is_dir():
                self.send_error(400, "Repo path does not exist.")
                return
            args = args_for_audits(audits)
            scanners = scanner_names_for_profile(args)
            job_id = uuid.uuid4().hex[:12]
            job = {
                "id": job_id,
                "status": "queued",
                "progress": 0,
                "message": "Queued",
                "repoName": repo_path.name,
                "repoPath": str(repo_path),
                "audits": audits or ["quick"],
                "steps": [SCANNER_LABELS.get(scanner, scanner) for scanner in scanners],
                "currentStep": None,
                "currentScanner": None,
                "startedAt": utc_now(),
                "finishedAt": None,
                "error": None,
            }
            with CHECK_JOBS_LOCK:
                CHECK_JOBS[job_id] = job
            thread = threading.Thread(target=run_check_job, args=(job_id, self.db_path, repo_path, args), daemon=True)
            thread.start()
            self.send_json({"job": job_snapshot(job_id)})
        except Exception as exc:
            self.send_error(500, str(exc))

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if not self._guard_mutation(parsed):
            return
        if not self._dispatch(self._DELETE_ROUTES):
            self.send_error(404)

    def install_managed_tool(self) -> None:
        try:
            payload = self.read_json_body()
            tool_id = str(payload.get("toolId") or payload.get("tool_id") or "").strip()
            if not payload.get("confirmManagedInstall"):
                self.send_error(400, "Confirm managed install before downloading a DëvSec-owned tool.")
                return
            install_record = install_managed_tool_files(tool_id)
            db = ObservatoryDB(self.db_path)
            try:
                record = db.record_managed_tool(
                    tool_id=str(install_record["tool_id"]),
                    version=str(install_record["version"]),
                    install_root=str(install_record["install_root"]),
                    binary_path=str(install_record["binary_path"]),
                    source=str(install_record["source"]),
                    checksum=str(install_record["checksum"]),
                    installer_version=str(install_record["installer_version"]),
                    ownership_id=str(install_record["ownership_id"]),
                    installed_at=str(install_record["installed_at"]),
                    active=True,
                    version_check_status=str(install_record["version_check_status"]),
                    version_check_output=str(install_record.get("version_check_output") or ""),
                    version_checked_at=str(install_record["version_checked_at"]),
                    metadata=dict(install_record.get("metadata") or {}),
                )
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            tool = _catalog_tool(tool_id, managed_tool_records)
            self.send_json(
                {
                    "managed_tool": record,
                    "tool": tool,
                    "preview": (tool or {}).get("install_preview"),
                }
            )
        except ManagedToolInstallError as exc:
            self.send_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def uninstall_managed_tool(self) -> None:
        try:
            payload = self.read_json_body()
            tool_id = str(payload.get("toolId") or payload.get("tool_id") or "gitleaks").strip()
            ownership_id = str(payload.get("ownershipId") or payload.get("ownership_id") or "").strip()
            if not payload.get("confirmManagedUninstall"):
                self.send_error(400, "Confirm managed uninstall before removing a DëvSec-owned tool.")
                return

            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
                record = _managed_record_for_uninstall(managed_tool_records, tool_id=tool_id, ownership_id=ownership_id)
                if record is None:
                    self.send_error(404, "DëvSec-owned managed tool not found.")
                    return
                removal = uninstall_managed_tool_files(record)
                deactivated = db.deactivate_managed_tool(str(record["ownership_id"]))
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            tool = _catalog_tool(tool_id, managed_tool_records)
            self.send_json(
                {
                    "removed": removal,
                    "managed_tool": deactivated,
                    "tool": tool,
                    "preview": (tool or {}).get("install_preview"),
                }
            )
        except ManagedToolInstallError as exc:
            self.send_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def install_via_package_manager(self) -> None:
        # Catalog declares each tool's install method. For automatable methods
        # (homebrew, uv-tool) we dispatch to the matching package manager with
        # the same binary-name regex validation and timeout. The binary name is
        # part of the catalog contract — not user input — so the dispatched
        # command is never shell-injectable.
        #
        # Manual-install tools (method=manual) do not flow through this
        # endpoint; they use /api/tools/recheck-install-state after the user
        # installs the tool out-of-band.
        dispatch: dict[str, Any] | None = None
        try:
            payload = self.read_json_body()
            tool_id = str(payload.get("toolId") or payload.get("tool_id") or "").strip()
            if not payload.get("confirmPackageInstall"):
                self.send_error(400, "Confirm package install before running the package manager.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            tool = _catalog_tool(tool_id, managed_tool_records)
            if tool is None:
                self.send_error(404, f"Tool {tool_id!r} not in catalog.")
                return
            install = tool.get("install") or {}
            method = str(install.get("method") or "")
            dispatch = _PACKAGE_MANAGER_DISPATCH.get(method)
            if dispatch is None:
                self.send_error(
                    400,
                    f"Tool {tool_id!r} install method {method!r} cannot be automated. "
                    "Supported methods: " + ", ".join(sorted(_PACKAGE_MANAGER_DISPATCH)) + ".",
                )
                return
            binary = str(install.get("binary") or "").strip()
            if not _PACKAGE_BINARY_RE.match(binary):
                self.send_error(400, f"Refusing to run {dispatch['program']} with binary name {binary!r}.")
                return
            program_path = shutil.which(dispatch["program"])
            if not program_path:
                self.send_error(500, dispatch["missing_prereq_hint"])
                return
            env = {**os.environ, **dispatch["env"]}
            args = [program_path, *(arg.format(binary=binary) for arg in dispatch["args"])]
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=dispatch["timeout"],
                env=env,
            )
            success = result.returncode == 0
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            refreshed = _catalog_tool(tool_id, managed_tool_records)
            command_label = " ".join([dispatch["program"], *(arg.format(binary=binary) for arg in dispatch["args"])])
            self.send_json({
                "tool": refreshed,
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": command_label,
            })
        except subprocess.TimeoutExpired:
            label = dispatch["program"] if dispatch else "package install"
            timeout = dispatch["timeout"] if dispatch else 600
            self.send_error(504, f"{label} install timed out after {timeout}s.")
        except Exception as exc:
            self.send_error(500, str(exc))

    def recheck_install_state(self) -> None:
        # For manual-install tools (and any other tool the user wants to
        # re-detect), this endpoint just re-runs the catalog's install-state
        # detection and returns the refreshed entry. No subprocess; no
        # filesystem polling; the user clicks "Mark installed" after running
        # the manual command and the catalog re-discovers the binary on PATH.
        try:
            payload = self.read_json_body()
            tool_id = str(payload.get("toolId") or payload.get("tool_id") or "").strip()
            if not tool_id:
                self.send_error(400, "Tool id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
            finally:
                db.close()
            tool = _catalog_tool(tool_id, managed_tool_records)
            if tool is None:
                self.send_error(404, f"Tool {tool_id!r} not in catalog.")
                return
            self.send_json({"tool": tool})
        except Exception as exc:
            self.send_error(500, str(exc))

    # ------------------------------------------------------------------
    # Credentials (Keychain) endpoints
    #
    # GET    /api/tools/credentials                  → full {tool_id: [keys]} map
    # GET    /api/tools/<id>/credentials/keys        → list of keys for one tool
    # POST   /api/tools/<id>/credentials             → store {key, value}
    # DELETE /api/tools/<id>/credentials/<key>       → forget one credential
    #
    # **Never returns values.** The frontend POSTs a value once, the backend
    # writes to Keychain, and from that point only `is_stored` and key names
    # cross the wire. Values only leave Keychain via the subprocess-env helper
    # in `credentials.env_with_credentials` (used by scanners.py in Step 2.2).
    # ------------------------------------------------------------------

    def _credentials_unavailable(self) -> bool:
        if keychain_is_supported():
            return False
        self.send_json_error(
            503,
            "Credential storage requires macOS with the `security` CLI on PATH.",
            service=KEYCHAIN_SERVICE,
        )
        return True

    def serve_all_credential_keys(self) -> None:
        if self._credentials_unavailable():
            return
        try:
            self.send_json({"service": KEYCHAIN_SERVICE, "tools": list_all_credentials()})
        except CredentialStorageError as exc:
            self.send_json_error(500, str(exc))

    def serve_credential_keys(self, tool_id: str) -> None:
        if self._credentials_unavailable():
            return
        if not _CREDENTIAL_ID_RE.match(tool_id):
            self.send_json_error(400, "Invalid tool id.")
            return
        try:
            keys = list_credentials(tool_id)
        except CredentialStorageError as exc:
            self.send_json_error(400, str(exc))
            return
        self.send_json({"service": KEYCHAIN_SERVICE, "tool_id": tool_id, "keys": keys})

    def store_tool_credential(self, tool_id: str) -> None:
        if self._credentials_unavailable():
            return
        if not _CREDENTIAL_ID_RE.match(tool_id):
            self.send_json_error(400, "Invalid tool id.")
            return
        try:
            payload = self.read_json_body()
        except json.JSONDecodeError:
            self.send_json_error(400, "Request body must be JSON.")
            return
        key_raw = payload.get("key") or payload.get("name") or ""
        value_raw = payload.get("value") or ""
        if not isinstance(key_raw, str) or not isinstance(value_raw, str):
            self.send_json_error(400, "key and value must be strings.")
            return
        key = key_raw.strip()
        if not key or not value_raw:
            self.send_json_error(400, "key and value are required.")
            return
        try:
            store_credential(tool_id, key, value_raw)
        except CredentialStorageError as exc:
            self.send_json_error(400, str(exc))
            return
        # Never echo the value — only that it landed.
        self.send_json(
            {
                "service": KEYCHAIN_SERVICE,
                "tool_id": tool_id,
                "key": key,
                "stored": True,
                "keys": list_credentials(tool_id),
            }
        )

    def delete_tool_credential(self, tool_id: str, key: str) -> None:
        if self._credentials_unavailable():
            return
        if not _CREDENTIAL_ID_RE.match(tool_id) or not _CREDENTIAL_ID_RE.match(key):
            self.send_json_error(400, "Invalid tool id or key.")
            return
        try:
            existed = delete_credential(tool_id, key)
        except CredentialStorageError as exc:
            self.send_json_error(400, str(exc))
            return
        self.send_json(
            {
                "service": KEYCHAIN_SERVICE,
                "tool_id": tool_id,
                "key": key,
                "deleted": existed,
                "keys": list_credentials(tool_id),
            }
        )

    # ------------------------------------------------------------------
    # Setup-card endpoints (probe + per-tool config)
    #
    # POST   /api/tools/<id>/setup/probe   → run setup_probe, return result
    # GET    /api/tools/<id>/setup/config  → read stored {key: value} config
    # POST   /api/tools/<id>/setup/config  → replace stored config (body: {values})
    # DELETE /api/tools/<id>/setup/config  → forget stored config
    #
    # Credentials and probe outputs flow through here, so the same care applies
    # as the credential endpoints: never log values; truncate probe output.
    # ------------------------------------------------------------------

    def run_tool_setup_probe(self, tool_id: str) -> None:
        if not _CREDENTIAL_ID_RE.match(tool_id):
            self.send_json_error(400, "Invalid tool id.")
            return
        try:
            result = run_setup_probe(tool_id)
        except SetupRunnerError as exc:
            self.send_json_error(400, str(exc))
            return
        # 200 for both pass and fail — probe failure is a normal outcome the
        # frontend renders inline. Reserve non-2xx for routing/validation gaps.
        self.send_json({"tool_id": tool_id, **result.to_dict()})

    def serve_tool_setup_config(self, tool_id: str) -> None:
        if not _CREDENTIAL_ID_RE.match(tool_id):
            self.send_json_error(400, "Invalid tool id.")
            return
        try:
            values = read_tool_config(tool_id)
        except ToolConfigError as exc:
            self.send_json_error(400, str(exc))
            return
        self.send_json({"tool_id": tool_id, "values": values})

    def save_tool_setup_config(self, tool_id: str) -> None:
        if not _CREDENTIAL_ID_RE.match(tool_id):
            self.send_json_error(400, "Invalid tool id.")
            return
        try:
            payload = self.read_json_body()
        except json.JSONDecodeError:
            self.send_json_error(400, "Request body must be JSON.")
            return
        values_raw = payload.get("values")
        if not isinstance(values_raw, dict):
            self.send_json_error(400, "Body must include `values` as a JSON object.")
            return
        cleaned: dict[str, str] = {}
        for key, value in values_raw.items():
            if not isinstance(key, str) or not isinstance(value, str):
                self.send_json_error(400, "All config keys and values must be strings.")
                return
            cleaned[key] = value
        try:
            stored = write_tool_config(tool_id, cleaned)
        except ToolConfigError as exc:
            self.send_json_error(400, str(exc))
            return
        self.send_json({"tool_id": tool_id, "values": stored, "stored": True})

    def forget_tool_setup_config(self, tool_id: str) -> None:
        if not _CREDENTIAL_ID_RE.match(tool_id):
            self.send_json_error(400, "Invalid tool id.")
            return
        try:
            removed = delete_tool_config(tool_id)
        except ToolConfigError as exc:
            self.send_json_error(400, str(exc))
            return
        self.send_json({"tool_id": tool_id, "values": {}, "removed": removed})

    def save_case_decision(self) -> None:
        try:
            payload = self.read_json_body()
            case_id = str(payload.get("caseId") or payload.get("case_id") or "").strip()
            repo_name = str(payload.get("repoName") or payload.get("repo_name") or "").strip()
            status = str(payload.get("status") or "open").strip()
            note = str(payload.get("note") or "").strip()
            vex_status = str(payload.get("vexStatus") or payload.get("vex_status") or "").strip() or None
            vex_justification = str(payload.get("vexJustification") or payload.get("vex_justification") or payload.get("vexReason") or payload.get("vex_reason") or "").strip() or None
            if not case_id:
                self.send_error(400, "Case id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                decision = db.set_case_decision(
                    case_id=case_id,
                    repo_name=repo_name or "repository",
                    status=status,
                    note=note,
                    vex_status=vex_status,
                    vex_justification=vex_justification,
                    vulnerability_id=str(payload.get("vulnerabilityId") or payload.get("vulnerability_id") or "").strip() or None,
                    package_name=str(payload.get("packageName") or payload.get("package_name") or "").strip() or None,
                    package_version=str(payload.get("packageVersion") or payload.get("package_version") or "").strip() or None,
                    package_ecosystem=str(payload.get("packageEcosystem") or payload.get("package_ecosystem") or "").strip() or None,
                    package_url=str(payload.get("packageUrl") or payload.get("package_url") or "").strip() or None,
                    component_package_key=str(payload.get("componentPackageKey") or payload.get("component_package_key") or "").strip() or None,
                    fixed_version=str(payload.get("fixedVersion") or payload.get("fixed_version") or "").strip() or None,
                    # Human confirmation is the per-session token the dashboard
                    # session fetched same-origin and echoed back — not the mere
                    # fact that a POST arrived. A cross-origin page cannot read
                    # the token, so it cannot attest a high/critical suppression.
                    human_authorized=self._human_confirmation_present(),
                )
            finally:
                db.close()
            self.send_json({"decision": decision})
        except ValueError as exc:
            self.send_json_error(400, str(exc))
        except Exception as exc:
            self.send_json_error(500, str(exc))

    def serve_ai_followup_prompt(self, parsed) -> None:
        query = parse_qs(parsed.query)
        repo = query.get("repo", query.get("repoName", query.get("repo_name", [""])))[0]
        action = query.get("action", ["verify_findings"])[0]
        scope = query.get("scope", ["critical"])[0]
        case_ids = query.get("caseId", []) + query.get("case_id", [])
        db = ObservatoryDB(self.db_path)
        try:
            try:
                prompt = build_case_followup_prompt(
                    db,
                    repo_name=repo,
                    action=action,
                    scope=scope,
                    case_ids=case_ids,
                )
            except ValueError as exc:
                self.send_json_error(400, str(exc))
                return
        finally:
            db.close()
        self.send_json(prompt)

    def serve_ai_followup_resolution_runs(self, parsed) -> None:
        query = parse_qs(parsed.query)
        repo = query.get("repo", query.get("repoName", query.get("repo_name", [""])))[0] or None
        try:
            limit = int(query.get("limit", ["50"])[0])
        except ValueError:
            limit = 50
        db = ObservatoryDB(self.db_path)
        try:
            runs = db.list_case_resolution_runs(repo_name=repo, limit=limit)
        finally:
            db.close()
        self.send_json({"items": runs})

    def preview_ai_followup_resolutions(self) -> None:
        try:
            request = self._ai_followup_resolution_request()
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json_error(400, str(exc))
            return
        db = ObservatoryDB(self.db_path)
        try:
            try:
                preview = validate_case_resolutions(
                    db,
                    request["payload"],
                    expected_repo=request.get("expected_repo"),
                    expected_scope=request.get("expected_scope"),
                    expected_case_ids=request.get("expected_case_ids"),
                )
            except ValueError as exc:
                self.send_json_error(400, str(exc))
                return
        finally:
            db.close()
        self.send_json(preview)

    def apply_ai_followup_resolutions(self) -> None:
        try:
            request = self._ai_followup_resolution_request(allow_run_id=True)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json_error(400, str(exc))
            return
        db = ObservatoryDB(self.db_path)
        try:
            try:
                result = apply_case_resolutions(
                    db,
                    request["run_id"] if request.get("run_id") else request["payload"],
                    expected_repo=request.get("expected_repo"),
                    expected_scope=request.get("expected_scope"),
                    expected_case_ids=request.get("expected_case_ids"),
                )
            except ValueError as exc:
                self.send_json_error(400, str(exc))
                return
        finally:
            db.close()
        self.send_json(result)

    def _ai_followup_resolution_request(self, *, allow_run_id: bool = False) -> dict[str, Any]:
        payload = self.read_json_body(max_bytes=1_000_000)
        run_id = str(payload.get("runId") or payload.get("run_id") or "").strip()
        if allow_run_id and run_id:
            return {"run_id": run_id, "payload": {}}

        ai_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else None
        if ai_payload is None and isinstance(payload.get("text"), str):
            try:
                parsed_text = json.loads(str(payload["text"]))
            except json.JSONDecodeError as exc:
                raise ValueError(f"AI result must be valid JSON: {exc.msg}") from exc
            if not isinstance(parsed_text, dict):
                raise ValueError("AI result must be a JSON object.")
            ai_payload = parsed_text
        if ai_payload is None:
            ai_payload = payload
        expected_case_ids_raw = payload.get("expectedCaseIds") or payload.get("expected_case_ids") or []
        expected_case_ids = [str(item).strip() for item in expected_case_ids_raw if str(item).strip()] if isinstance(expected_case_ids_raw, list) else []
        return {
            "payload": ai_payload,
            "expected_repo": str(payload.get("expectedRepo") or payload.get("expected_repo") or "").strip() or None,
            "expected_scope": str(payload.get("expectedScope") or payload.get("expected_scope") or "").strip() or None,
            "expected_case_ids": expected_case_ids,
        }

    def import_agent_lab_proposal(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > AGENT_PROPOSAL_MAX_BYTES:
                self.send_json_error(400, "Agent Lab proposal is too large.", max_bytes=AGENT_PROPOSAL_MAX_BYTES)
                return
            body = self.rfile.read(length) if length else b"{}"
            if len(body) > AGENT_PROPOSAL_MAX_BYTES:
                self.send_json_error(400, "Agent Lab proposal is too large.", max_bytes=AGENT_PROPOSAL_MAX_BYTES)
                return
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except json.JSONDecodeError as exc:
                self.send_json_error(400, "Request body must be JSON.", errors=[exc.msg])
                return
            proposal = proposal_from_import_payload(payload)
            db = ObservatoryDB(self.db_path)
            try:
                managed_tool_records = db.list_managed_tools()
                validated = validate_agent_proposal(proposal, managed_tool_records=managed_tool_records)
                saved = db.save_agent_lab_proposal(validated)
            finally:
                db.close()
            self.send_json({"proposal": saved})
        except AgentLabProposalValidationError as exc:
            self.send_json_error(400, "Agent Lab proposal failed validation.", errors=exc.errors)
        except Exception as exc:
            self.send_error(500, str(exc))

    def preview_agent_lab_proposal_execution(self, parsed: Any) -> None:
        query = parse_qs(parsed.query)
        proposal_id = str(query.get("proposalId", query.get("proposal_id", query.get("id", [""])))[0] or "").strip()
        mode = str(query.get("mode", ["dry_run_preview"])[0] or "dry_run_preview").strip()
        if not proposal_id:
            self.send_json_error(400, "Agent Lab proposal id is required.")
            return
        try:
            db = ObservatoryDB(self.db_path)
            try:
                proposal = db.get_agent_lab_proposal(proposal_id)
                if not proposal:
                    self.send_json_error(404, "Agent Lab proposal not found.")
                    return
                preview = build_agent_execution_preview(
                    proposal,
                    managed_tool_records=db.list_managed_tools(),
                    requested_mode=mode,
                )
                plan = dict(proposal.get("final_execution_plan") or {})
                plan["last_preview"] = preview
                proposal = db.update_agent_lab_execution_plan(proposal_id=proposal_id, final_execution_plan=plan)
            finally:
                db.close()
            self.send_json({"preview": preview, "proposal": proposal})
        except AgentLabExecutionError as exc:
            self.send_json_error(400, "Agent Lab proposal cannot be routed.", errors=exc.errors)
        except ValueError as exc:
            self.send_json_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def save_agent_lab_proposal_decision(self) -> None:
        try:
            payload = self.read_json_body()
            proposal_id = str(payload.get("proposalId") or payload.get("proposal_id") or payload.get("id") or "").strip()
            approval_state = str(payload.get("approvalState") or payload.get("approval_state") or payload.get("decision") or "").strip()
            if not proposal_id:
                self.send_json_error(400, "Agent Lab proposal id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                proposal = db.set_agent_lab_proposal_approval(
                    proposal_id=proposal_id,
                    approval_state=approval_state,
                    note=str(payload.get("note") or "").strip() or None,
                    decided_by=str(payload.get("decidedBy") or payload.get("decided_by") or "").strip() or None,
                )
            finally:
                db.close()
            self.send_json({"proposal": proposal})
        except ValueError as exc:
            self.send_json_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def run_agent_lab_proposal(self) -> None:
        try:
            payload = self.read_json_body()
            proposal_id = str(payload.get("proposalId") or payload.get("proposal_id") or payload.get("id") or "").strip()
            mode = str(payload.get("mode") or "dry_run_preview").strip()
            execute = bool(payload.get("execute")) or mode == "approved_run"
            if not proposal_id:
                self.send_json_error(400, "Agent Lab proposal id is required.")
                return

            db = ObservatoryDB(self.db_path)
            try:
                proposal = db.get_agent_lab_proposal(proposal_id)
                if not proposal:
                    self.send_json_error(404, "Agent Lab proposal not found.")
                    return
                preview = build_agent_execution_preview(
                    proposal,
                    managed_tool_records=db.list_managed_tools(),
                    requested_mode="approved_run" if execute else "dry_run_preview",
                    require_approval=execute,
                )
                if not execute:
                    plan = dict(proposal.get("final_execution_plan") or {})
                    plan["last_preview"] = preview
                    proposal = db.update_agent_lab_execution_plan(proposal_id=proposal_id, final_execution_plan=plan)
                    self.send_json({"preview": preview, "proposal": proposal})
                    return
            finally:
                db.close()

            repo_path = Path(str(proposal.get("repo_path") or "")).expanduser().resolve()
            if not repo_path.is_dir():
                self.send_json_error(400, "Agent Lab proposal repo path does not exist.")
                return
            scanner_names = [str(item) for item in preview.get("scanner_names") or [] if str(item).strip()]
            if not scanner_names:
                self.send_json_error(400, "Agent Lab proposal has no DëvSec scanner route.")
                return
            profile_ids = [str(item) for item in preview.get("scan_profile_ids") or [] if str(item).strip()]
            args = args_for_audits(profile_ids)
            job_id = uuid.uuid4().hex[:12]
            job = {
                "id": job_id,
                "status": "queued",
                "source": "agent-lab",
                "proposalId": proposal_id,
                "progress": 0,
                "message": "Queued Agent Lab scan",
                "repoName": repo_path.name,
                "repoPath": str(repo_path),
                "audits": profile_ids or ["quick"],
                "steps": [SCANNER_LABELS.get(scanner, scanner) for scanner in scanner_names],
                "currentStep": None,
                "currentScanner": None,
                "startedAt": utc_now(),
                "finishedAt": None,
                "error": None,
                "executionPreview": preview,
            }
            with CHECK_JOBS_LOCK:
                CHECK_JOBS[job_id] = job
            _record_agent_lab_execution_result(
                self.db_path,
                proposal_id,
                preview,
                {
                    "job_id": job_id,
                    "mode": "approved_run",
                    "status": "queued",
                    "started_at": job["startedAt"],
                    "scanner_names": scanner_names,
                },
            )
            thread = threading.Thread(
                target=run_check_job,
                args=(job_id, self.db_path, repo_path, args),
                kwargs={
                    "scanner_names": scanner_names,
                    "agent_lab_proposal_id": proposal_id,
                    "agent_lab_preview": preview,
                },
                daemon=True,
            )
            thread.start()
            self.send_accepted_json({"job": job_snapshot(job_id), "preview": preview})
        except AgentLabExecutionError as exc:
            self.send_json_error(400, "Agent Lab proposal cannot be routed.", errors=exc.errors)
        except ValueError as exc:
            self.send_json_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def create_honey_key(self) -> None:
        try:
            payload = self.read_json_body()
            repo_path = str(payload.get("repoPath") or "").strip()
            repo_name = str(payload.get("repoName") or Path(repo_path).name or "repository").strip()
            project_id = str(payload.get("projectId") or project_id_for_repo_path(repo_path or repo_name))
            name = str(payload.get("name") or "Legacy internal API key").strip()[:120]
            placement_path = str(payload.get("placementPath") or DEFAULT_PLACEMENT_PATHS[0]).strip()[:240]
            note = str(payload.get("note") or "").strip()[:500] or None
            created_by = str(payload.get("createdBy") or "").strip()[:120] or None
            asset_node_id = _coerce_asset_node_id(payload.get("assetNodeId"))
            if asset_node_id is _INVALID_ASSET_NODE_ID:
                self.send_error(400, "assetNodeId must be a positive integer asset node id.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                signing_secret = db.honey_signing_secret()
                material = generate_honey_key(signing_secret)
                key = db.create_honey_key(
                    key_id=material.token_id,
                    project_id=project_id,
                    repo_id=repo_path or None,
                    name=name,
                    token_hash=material.token_hash,
                    placement_path=placement_path,
                    note=note,
                    created_by=created_by,
                    asset_node_id=asset_node_id,
                )
                snippets = build_decoy_snippets(
                    base_url=self.request_base_url(),
                    name=name,
                    token=material.token,
                    token_id=material.token_id,
                    signing_secret=signing_secret,
                )
                self.send_json(
                    {
                        "key": key,
                        "raw_token": material.token,
                        "snippets": snippets,
                        "notice": "Honey Keys are fake, powerless decoy secrets. They alert you when touched. They do not prevent breaches by themselves.",
                    }
                )
            finally:
                db.close()
        except sqlite3.IntegrityError:
            self.send_error(409, "Honey Key already exists.")
        except Exception as exc:
            self.send_error(500, str(exc))

    def archive_honey_key(self) -> None:
        try:
            payload = self.read_json_body()
            key_id = str(payload.get("id") or "").strip()
            if not key_id:
                self.send_error(400, "Honey Key id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                key = db.archive_honey_key(key_id)
            finally:
                db.close()
            if not key:
                self.send_error(404, "Honey Key not found.")
                return
            self.send_json({"key": key})
        except Exception as exc:
            self.send_error(500, str(exc))

    def update_honey_incident_step(self) -> None:
        try:
            payload = self.read_json_body()
            event_id = str(payload.get("eventId") or payload.get("event_id") or "").strip()
            step = str(payload.get("step") or "").strip()
            complete = bool(payload.get("complete"))
            if not event_id:
                self.send_error(400, "Honey Key event id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                incident = db.set_honey_incident_step(event_id, step, complete)
            finally:
                db.close()
            self.send_json({"incident": incident})
        except ValueError as exc:
            self.send_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def close_honey_incident(self) -> None:
        try:
            payload = self.read_json_body()
            event_id = str(payload.get("eventId") or payload.get("event_id") or "").strip()
            note = str(payload.get("acceptedRiskNote") or payload.get("accepted_risk_note") or "").strip()
            if not event_id:
                self.send_error(400, "Honey Key event id is required.")
                return
            db = ObservatoryDB(self.db_path)
            try:
                incident = db.close_honey_incident(event_id, note)
            finally:
                db.close()
            self.send_json({"incident": incident})
        except ValueError as exc:
            self.send_error(400, str(exc))
        except Exception as exc:
            self.send_error(500, str(exc))

    def insert_honey_key_file(self) -> None:
        try:
            payload = self.read_json_body()
            key_id = str(payload.get("id") or "").strip()
            repo_path = Path(str(payload.get("repoPath") or "")).expanduser().resolve()
            placement_path = str(payload.get("placementPath") or "").strip()
            snippet = str(payload.get("snippet") or "")
            confirmed = bool(payload.get("confirmPlacement"))
            advanced_placement = bool(payload.get("advancedPlacement"))

            if not key_id:
                self.send_error(400, "Honey Key id is required.")
                return
            if not confirmed:
                self.send_error(400, "Confirm safe placement before writing the decoy file.")
                return
            if not repo_path.is_dir():
                self.send_error(400, "Repo path does not exist.")
                return
            if not placement_path or Path(placement_path).is_absolute():
                self.send_error(400, "Placement path must be relative to the repo.")
                return
            if len(snippet.encode("utf-8")) > 64_000:
                self.send_error(400, "Decoy snippet is too large.")
                return

            target_path = (repo_path / placement_path).resolve()
            try:
                target_path.relative_to(repo_path)
            except ValueError:
                self.send_error(400, "Placement path must stay inside the repo.")
                return
            if not _is_safe_honeykeys_path(placement_path) and not advanced_placement:
                self.send_error(400, "Default insertions must use .devsec/honeykeys/. Enable advanced placement for realistic decoy filenames.")
                return
            if target_path.exists():
                self.send_error(409, "Placement file already exists. Choose a new decoy path so DëvSec does not overwrite real project files.")
                return

            db = ObservatoryDB(self.db_path)
            try:
                signing_secret = db.honey_signing_secret()
                token = extract_honey_key_from_request(path="", query={}, headers={}, body=snippet.encode("utf-8"))
                if not token or not honey_key_is_well_formed(token, signing_secret):
                    self.send_error(400, "Decoy snippet does not contain a valid Honey Key.")
                    return
                key = db.find_honey_key_by_hash(hash_honey_key(token))
                if not key or str(key["id"]) != key_id:
                    self.send_error(400, "Decoy snippet does not match this Honey Key.")
                    return
                if key.get("repo_id") and Path(str(key["repo_id"])).expanduser().resolve() != repo_path:
                    self.send_error(400, "Honey Key belongs to a different repo.")
                    return
            finally:
                db.close()

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(snippet, encoding="utf-8")
            try:
                os.chmod(target_path, 0o600)
            except OSError:
                pass
            self.send_json({"path": str(target_path), "relative_path": placement_path})
        except Exception as exc:
            self.send_error(500, str(exc))

    # ------------------------------------------------------------------
    # Rotation endpoints — read-only views over the secrets-rotation skill's
    # on-disk state plus a guarded "Set up rotation" handoff. The Step 2.2
    # POST /api/rotation/trigger writer endpoint lives in a later step.
    # ------------------------------------------------------------------

    def _resolve_repo_for_rotation(self, repo_name: str) -> Path | None:
        """Resolve ``repo_name`` (URL-tail) → on-disk ``Path`` or None.

        Same vocabulary as the MCP rotation tools: looks up the latest scan
        record for the repo and uses its ``repo_path``. Returns None when the
        repo has no scan history (the caller maps None → 404).
        """
        name = repo_name.strip().strip("/")
        if not name:
            return None
        # URL-decoded names sometimes carry a single trailing slash; strip
        # nothing else — repo names are validated against scan-history
        # vocabulary, not against a filesystem glob.
        db = ObservatoryDB(self.db_path)
        try:
            scan = db.latest_scan_for_repo(name)
        finally:
            db.close()
        if not scan:
            return None
        repo_path = scan.get("repo_path")
        if not repo_path:
            return None
        try:
            return Path(str(repo_path)).expanduser()
        except (OSError, RuntimeError):
            return None

    def serve_rotation_status(self, repo_name: str) -> None:
        """Serve ``GET /api/rotation/status/<repo>``.

        Each secret row includes ``manually_marked``/``override_kind`` for
        operator overrides plus catalog-derived ``rotation_warning``,
        ``soak_window_minutes``, and ``console_url`` metadata for the trigger
        modal. WAITING_FOR_PASTE rows are enriched with the active dashboard
        ``job_id`` so the paste-resume endpoint has a safe key.
        """
        repo_path = self._resolve_repo_for_rotation(repo_name)
        if repo_path is None:
            self.send_json_error(404, "No scan history for that repo yet.")
            return
        rows = read_rotation_status(repo_path)
        clean_repo = repo_name.strip().strip("/")
        rows = [dict(row, active_job_id=None) for row in rows]
        for row in rows:
            if row.get("status") != "WAITING_FOR_PASTE":
                continue
            secret = str(row.get("secret") or "")
            active_job = _active_rotation_job(clean_repo, secret)
            if active_job:
                row["active_job_id"] = active_job.get("id")
        receipts = list_receipts(repo_path)
        signal = detect_rotation_state(repo_path)
        consistency = rotation_consistency_check(repo_path)
        self.send_json(
            {
                "repo": clean_repo,
                "rotation_state": signal,
                "secrets": rows,
                "receipts": receipts,
                "consistency": consistency,
            }
        )

    def serve_rotation_history(self, repo_name: str, limit_raw: str) -> None:
        repo_path = self._resolve_repo_for_rotation(repo_name)
        if repo_path is None:
            self.send_json_error(404, "No scan history for that repo yet.")
            return
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            limit = 20
        events = read_rotation_history(repo_path, limit)
        self.send_json(
            {
                "repo": repo_name.strip().strip("/"),
                "events": events,
            }
        )

    def serve_fix_proposal_detail(self, proposal_id: str) -> None:
        """Serve ``GET /api/fix-proposals/<id>`` — diff + clean-room verdict.

        Surfaces the stored diff, the recorded clean-room status/invariants, and
        the diff-class invariant checklist. It never exposes finding text: the
        proposal store holds none, and the invariants describe the diff, not the
        motivating finding.
        """
        db = ObservatoryDB(self.db_path)
        try:
            record = db.get_fix_proposal(proposal_id)
        finally:
            db.close()
        if not record:
            self.send_json_error(404, "Fix proposal not found.")
            return
        self.send_json(_fix_proposal_detail(record))

    def decide_fix_landing(self, proposal_id: str) -> None:
        """Serve ``POST /api/fix-proposals/<id>/land``.

        Delegates to ``fix_proposals.decide_landing`` so a dashboard land
        decision is authorized only where the proven boundary already allows it
        — clean-room ``approved``, matching ``diff_sha256``, allowlisted fix
        class; protected branches and non-eligible classes are refused. The
        dashboard adds no new path to land code the MCP rw tool could not.
        """
        db = ObservatoryDB(self.db_path)
        try:
            try:
                outcome = decide_landing(db, proposal_id=proposal_id)
            except ValueError as exc:
                self.send_json_error(404, str(exc))
                return
        finally:
            db.close()
        self.send_json(outcome)

    def serve_rotation_receipt(self, tail: str) -> None:
        """Serve ``/api/rotation/receipts/<repo>/<filename>`` as markdown.

        Path-traversal safety: the filename is validated by the shared
        ``read_receipt`` helper (regex + resolve+relative_to check). The repo
        segment is resolved through the scan history, not raw user input, so
        a hostile ``..`` cannot redirect us outside known repos.
        """
        cleaned = tail.strip().strip("/")
        if "/" not in cleaned:
            self.send_json_error(400, "Receipt path must be <repo>/<filename>.")
            return
        repo_name, _, filename = cleaned.partition("/")
        if not repo_name or not filename:
            self.send_json_error(400, "Receipt path must be <repo>/<filename>.")
            return
        repo_path = self._resolve_repo_for_rotation(repo_name)
        if repo_path is None:
            self.send_json_error(404, "No scan history for that repo yet.")
            return
        content = read_receipt(repo_path, filename)
        if content is None:
            self.send_error(404, "Verification receipt not found.")
            return
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def serve_rotation_scaffold_handoff(self, repo_name: str) -> None:
        """Return scaffolding instructions for repos missing rotation setup.

        v0.1 is a guided handoff, not a literal subprocess: the secrets-rotation
        skill runs inside a Claude Code session (interactive — confirms tier,
        secret classifications, scaffold plan), so the dashboard cannot launch
        it headlessly without losing those gates. Instead the dashboard returns
        the exact command + working directory and the UI shows them with a
        copy button. Once the skill graduates to a non-interactive
        bootstrapping mode the handoff payload can grow a ``job_id`` field
        and the dashboard can shell out for real.
        """
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError):
            self.send_json_error(400, "Request body must be valid JSON.")
            return
        if not bool(payload.get("confirmed")):
            self.send_json_error(
                400,
                "Confirm the scaffold handoff before requesting setup instructions.",
            )
            return
        repo_path = self._resolve_repo_for_rotation(repo_name)
        if repo_path is None:
            self.send_json_error(404, "No scan history for that repo yet.")
            return
        if not repo_path.is_dir():
            self.send_json_error(404, "Repo path is no longer on disk.")
            return
        if read_rotation_status(repo_path):
            self.send_json_error(
                409,
                "Rotation is already scaffolded for this repo.",
            )
            return
        stack = detect_stack(repo_path)
        supported = stack in SUPPORTED_STACKS if stack else False
        if not supported:
            self.send_json(
                {
                    "supported": False,
                    "stack": stack,
                    "message": (
                        "This repo's stack isn't supported for automated"
                        " rotation yet. Currently supported: Next.js + Vercel,"
                        " Python CLI."
                    ),
                }
            )
            return
        self.send_json(
            {
                "supported": True,
                "stack": stack,
                "working_directory": str(repo_path),
                "command": "claude /secrets-rotation",
                "next_steps": [
                    "Open a terminal in the repo above.",
                    "Run `claude` to start Claude Code in that directory.",
                    "Type `/secrets-rotation` and follow the prompts.",
                    "The skill will discover secrets, classify them, and ask"
                    " for confirmation before writing any files.",
                ],
                "why_not_shelled_out": (
                    "Scaffolding asks interactive questions (tier, secret"
                    " classifications). The dashboard hands off the command"
                    " instead of running it blindly so those gates stay in"
                    " place."
                ),
            }
        )

    # ------------------------------------------------------------------
    # POST /api/rotation/trigger/<repo>  +  GET /api/rotation/jobs/<id>
    #
    # Refuse-by-default Tier 5R action. The HTTP body MUST carry the exact
    # confirmation phrase from docs/agent-safety.md (Tier 5R section). The
    # dashboard shell-outs to `npm run rotate -- <SECRET> [flags]` inside
    # the repo's working directory. Pipeline progress is exposed through the
    # existing polled-job pattern — POST returns a job_id, GET /api/rotation/
    # jobs/<id> returns the current snapshot. The rotation skill writes the
    # verification receipt to `data/rotation-receipts/<name>.md`; once the
    # subprocess exits the job points at the newest receipt for the secret
    # so the frontend can render it verbatim.
    #
    # MCP boundary: rotation triggering does NOT go through MCP. This is the
    # only write surface; the slash command path mirrors it.
    # ------------------------------------------------------------------

    def serve_rotation_trigger(self, repo_name: str) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError):
            self.send_json_error(400, "Request body must be valid JSON.")
            return
        secret = str(payload.get("secret") or "").strip()
        if not _SAFE_SECRET_NAME_RE.match(secret):
            self.send_json_error(
                400,
                "Provide a secret name matching ^[A-Z][A-Z0-9_]*$.",
            )
            return
        options_raw_early = payload.get("options")
        options_early = options_raw_early if isinstance(options_raw_early, dict) else {}
        emergency_mode = bool(options_early.get("emergency_mode"))

        confirmed = bool(payload.get("confirmed"))
        confirmation_phrase = str(payload.get("confirmation_phrase") or "").strip()
        expected_phrase = _rotation_confirmation_phrase(secret, emergency=emergency_mode)
        if not confirmed or confirmation_phrase != expected_phrase:
            self.send_json_error(
                400,
                "Rotation requires the Tier 5R confirmation phrase from docs/agent-safety.md.",
                expected_confirmation_phrase=expected_phrase,
            )
            return

        options_raw = payload.get("options")
        options = options_raw if isinstance(options_raw, dict) else {}
        no_soak = bool(options.get("no_soak"))
        ack_skipping_soak = bool(options.get("acknowledged_skipping_soak"))
        if no_soak and not ack_skipping_soak:
            self.send_json_error(
                400,
                "--no-soak skips the post-rotation soak gate. Set"
                " options.acknowledged_skipping_soak=true to proceed.",
            )
            return
        skip_health_check = bool(options.get("skip_health_check"))
        ack_skipping_health = bool(options.get("acknowledged_skipping_health_check"))
        if skip_health_check and not ack_skipping_health:
            self.send_json_error(
                400,
                "--skip-health-check bypasses the pre-rotation baseline check. Set"
                " options.acknowledged_skipping_health_check=true to proceed.",
            )
            return
        soak_minutes_raw = options.get("soak_minutes")
        soak_minutes: int | None
        if soak_minutes_raw is None:
            soak_minutes = None
        else:
            try:
                soak_minutes = int(soak_minutes_raw)
            except (TypeError, ValueError):
                self.send_json_error(400, "options.soak_minutes must be an integer.")
                return
            if not 10 <= soak_minutes <= 60:
                self.send_json_error(
                    400,
                    "options.soak_minutes must be between 10 and 60.",
                )
                return
        test_mode = bool(options.get("test_mode"))
        ack_cached_caller_risk = bool(options.get("acknowledged_cached_caller_risk"))
        if emergency_mode and not ack_cached_caller_risk:
            self.send_json_error(
                400,
                "Emergency mode skips the grace window and revokes the old key"
                " immediately. Cached callers will fail loudly. Set"
                " options.acknowledged_cached_caller_risk=true to proceed.",
            )
            return

        repo_path = self._resolve_repo_for_rotation(repo_name)
        if repo_path is None:
            self.send_json_error(404, "No scan history for that repo yet.")
            return
        if not repo_path.is_dir():
            self.send_json_error(404, "Repo path is no longer on disk.")
            return

        rows = read_rotation_status(repo_path)
        known_secrets = {row.get("secret") for row in rows if isinstance(row, dict)}
        if not rows:
            self.send_json_error(
                409,
                "Rotation isn't set up for this repo. Use 'Set up rotation' first.",
            )
            return
        if secret not in known_secrets:
            self.send_json_error(
                404,
                f"Secret {secret!r} isn't tracked by rotation in this repo.",
                known_secrets=sorted(s for s in known_secrets if isinstance(s, str)),
            )
            return

        # --- concurrency gate: refuse if this secret already has in-flight work ---
        clean_repo = repo_name.strip().strip("/")
        active_job = _active_rotation_job(clean_repo, secret)
        for row in rows:
            if row.get("secret") == secret and row.get("status") in ROTATION_INFLIGHT_STATUSES:
                extra = {"job_id": active_job["id"]} if active_job else {}
                self.send_json_error(
                    409,
                    f"Rotation for {secret!r} is already in progress (status: {row['status']}).",
                    **extra,
                )
                return
        if active_job:
            self.send_json_error(
                409,
                f"Rotation for {secret!r} is already in progress"
                f" (job_id: {active_job['id']}).",
                job_id=active_job["id"],
            )
            return

        command = ["npm", "run", "rotate", "--", secret]
        if test_mode:
            command.append("--test")
        if no_soak:
            command.append("--no-soak")
        if skip_health_check:
            command.append("--skip-health-check")
        if soak_minutes is not None:
            command.extend(["--soak-minutes", str(soak_minutes)])
        if emergency_mode:
            command.append("--emergency")

        job_id = uuid.uuid4().hex[:12]
        job: dict[str, object] = {
            "id": job_id,
            "kind": "rotation",
            "status": "queued",
            "repo": clean_repo,
            "repo_path": str(repo_path),
            "secret": secret,
            "command": " ".join(command),
            "options": {
                "no_soak": no_soak,
                "skip_health_check": skip_health_check,
                "soak_minutes": soak_minutes,
                "test_mode": test_mode,
                "acknowledged_skipping_soak": ack_skipping_soak,
                "acknowledged_skipping_health_check": ack_skipping_health,
                "emergency_mode": emergency_mode,
                "acknowledged_cached_caller_risk": ack_cached_caller_risk,
            },
            "phase": "queued",
            "message": "Queued; about to shell out to the rotation skill.",
            "stdout_tail": [],
            "events_seen": 0,
            "started_at": utc_now(),
            "finished_at": None,
            "exit_code": None,
            "error": None,
            "receipt_filename": None,
            "receipt_url": None,
            "verification_status": None,
        }
        with CHECK_JOBS_LOCK:
            CHECK_JOBS[job_id] = job

        # Audit-trail line written BEFORE the subprocess starts so the trigger
        # is visible in `rotation_history` even if npm itself never runs.
        _append_rotation_audit_event(
            repo_path,
            {
                "rotation_id": None,
                "secret_name": secret,
                "step": "DASHBOARD_TRIGGER",
                "outcome": "initiated",
                "note": f"dashboard trigger; job_id={job_id}; command={' '.join(command)}",
                "options": job["options"],
            },
        )

        thread = threading.Thread(
            target=_run_rotation_job,
            args=(job_id, repo_path, secret, command, clean_repo),
            daemon=True,
        )
        thread.start()
        self.send_accepted_json({"job": job_snapshot(job_id)})

    # ------------------------------------------------------------------
    # POST /api/rotation/trigger-batch/<repo>
    # GET  /api/rotation/jobs/batch/<id>
    #
    # Sequential batch rotation. Applies a filter preset to the repo's
    # rotation status, builds a queue, and rotates each secret one at a
    # time. Halt-on-error: if any sub-rotation halts, the batch stops and
    # the operator chooses continue/stop via POST /api/rotation/jobs/batch/
    # <id>/continue or /stop.
    # ------------------------------------------------------------------

    def serve_rotation_trigger_batch(self, repo_name: str) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError):
            self.send_json_error(400, "Request body must be valid JSON.")
            return

        preset = str(payload.get("filter") or "all_actionable").strip()
        if preset not in BATCH_FILTER_PRESETS:
            self.send_json_error(
                400,
                f"filter must be one of: {', '.join(sorted(BATCH_FILTER_PRESETS))}.",
            )
            return

        confirmed = bool(payload.get("confirmed"))
        confirmation_phrase = str(payload.get("confirmation_phrase") or "").strip()

        repo_path = self._resolve_repo_for_rotation(repo_name)
        if repo_path is None:
            self.send_json_error(404, "No scan history for that repo yet.")
            return
        if not repo_path.is_dir():
            self.send_json_error(404, "Repo path is no longer on disk.")
            return

        rows = read_rotation_status(repo_path)
        if not rows:
            self.send_json_error(
                409,
                "Rotation isn't set up for this repo. Use 'Set up rotation' first.",
            )
            return

        queue_rows = _apply_batch_filter(rows, preset)
        if not queue_rows:
            self.send_json_error(
                409,
                "No secrets match the filter. Nothing to rotate.",
                filter=preset,
            )
            return

        has_class_b = any(
            str(r.get("class") or "").startswith("B") for r in queue_rows
        )
        expected_phrase = _batch_rotation_confirmation_phrase(
            len(queue_rows), has_class_b=has_class_b
        )
        if not confirmed or confirmation_phrase != expected_phrase:
            self.send_json_error(
                400,
                "Batch rotation requires the batch confirmation phrase.",
                expected_confirmation_phrase=expected_phrase,
                secret_count=len(queue_rows),
                has_class_b=has_class_b,
            )
            return

        clean_repo = repo_name.strip().strip("/")
        queue_secrets = [str(r.get("secret") or "") for r in queue_rows]

        batch_id = uuid.uuid4().hex[:12]
        batch_job: dict[str, object] = {
            "id": batch_id,
            "kind": "rotation_batch",
            "status": "running",
            "repo": clean_repo,
            "repo_path": str(repo_path),
            "filter": preset,
            "queue": queue_secrets,
            "completed": [],
            "halted": [],
            "current_secret": None,
            "current_job_id": None,
            "position": 0,
            "total": len(queue_secrets),
            "halt_on_error": True,
            "halted_awaiting_decision": False,
            "started_at": utc_now(),
            "finished_at": None,
            "batch_receipt": None,
        }
        with BATCH_JOBS_LOCK:
            BATCH_JOBS[batch_id] = batch_job

        _append_rotation_audit_event(
            repo_path,
            {
                "rotation_id": None,
                "secret_name": None,
                "step": "DASHBOARD_BATCH_TRIGGER",
                "outcome": "initiated",
                "note": (
                    f"batch trigger; batch_id={batch_id}; filter={preset}; "
                    f"count={len(queue_secrets)}; secrets={','.join(queue_secrets)}"
                ),
            },
        )

        thread = threading.Thread(
            target=_run_batch_rotation,
            args=(batch_id, repo_path, clean_repo),
            daemon=True,
        )
        thread.start()
        self.send_accepted_json({"batch": _batch_job_snapshot(batch_id)})

    def serve_rotation_batch_job(self, tail: str) -> None:
        cleaned = tail.strip().strip("/")
        # Support /api/rotation/jobs/batch/<id>/continue and /stop
        if "/" in cleaned:
            batch_id, _, action = cleaned.partition("/")
            if action == "continue":
                return self._batch_continue(batch_id)
            if action == "stop":
                return self._batch_stop(batch_id)
            self.send_json_error(400, "Unknown batch action.")
            return
        batch_id = cleaned
        if not batch_id:
            self.send_json_error(400, "Provide a batch job id.")
            return
        snapshot = _batch_job_snapshot(batch_id)
        if not snapshot:
            self.send_json_error(404, "Batch job not found.")
            return
        self.send_json({"batch": snapshot})

    def _batch_continue(self, batch_id: str) -> None:
        with BATCH_JOBS_LOCK:
            batch = BATCH_JOBS.get(batch_id)
            if not batch:
                self.send_json_error(404, "Batch job not found.")
                return
            if not batch.get("halted_awaiting_decision"):
                self.send_json_error(409, "Batch is not halted awaiting a decision.")
                return
            batch["halted_awaiting_decision"] = False
            batch["status"] = "running"
        self.send_json({"batch": _batch_job_snapshot(batch_id)})

    def _batch_stop(self, batch_id: str) -> None:
        with BATCH_JOBS_LOCK:
            batch = BATCH_JOBS.get(batch_id)
            if not batch:
                self.send_json_error(404, "Batch job not found.")
                return
            batch["halted_awaiting_decision"] = False
            batch["status"] = "stopped"
            batch["finished_at"] = utc_now()
        repo_path = Path(str(batch.get("repo_path") or ""))
        if repo_path.is_dir():
            _write_batch_receipt(batch_id, repo_path)
        self.send_json({"batch": _batch_job_snapshot(batch_id)})

    def serve_rotation_paste(self, job_id: str) -> None:
        """Resume a WAITING_FOR_PASTE rotation by stdin-feeding the skill.

        The URL key is the dashboard job id, not a filesystem path. The repo path
        comes from the existing CHECK_JOBS snapshot, which was created either by
        the guarded trigger endpoint or by startup rediscovery from scan history.
        The pasted secret value is never written to CHECK_JOBS or the audit log.
        """
        if not _SAFE_JOB_ID_RE.match(job_id):
            self.send_json_error(400, "Provide a valid rotation job_id.")
            return
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError):
            self.send_json_error(400, "Request body must be valid JSON.")
            return
        raw_value = payload.get("paste_value", payload.get("value"))
        if not isinstance(raw_value, str) or not raw_value.strip():
            self.send_json_error(400, "paste_value is required.")
            return
        paste_value = raw_value.strip()
        if len(paste_value.encode("utf-8")) > 16_384:
            self.send_json_error(400, "paste_value is too large.")
            return

        with CHECK_JOBS_LOCK:
            job = dict(CHECK_JOBS.get(job_id) or {})
        if not job or str(job.get("kind") or "") != "rotation":
            self.send_json_error(404, "Rotation job not found.")
            return
        if str(job.get("status") or "") in _TERMINAL_JOB_STATUSES:
            self.send_json_error(409, "Rotation job is already terminal.")
            return

        secret = str(job.get("secret") or "").strip()
        if not _SAFE_SECRET_NAME_RE.match(secret):
            self.send_json_error(409, "Rotation job has an invalid secret name.")
            return
        repo_path = Path(str(job.get("repo_path") or "")).expanduser()
        if not repo_path.is_dir():
            self.send_json_error(404, "Repo path is no longer on disk.")
            return

        rows = read_rotation_status(repo_path)
        row = next(
            (
                item
                for item in rows
                if isinstance(item, dict) and item.get("secret") == secret
            ),
            None,
        )
        current_status = str(row.get("status") or "") if row else ""
        if current_status != "WAITING_FOR_PASTE":
            self.send_json_error(
                409,
                "Rotation is not waiting for a paste.",
                current_status=current_status or None,
            )
            return

        clean_repo = str(job.get("repo") or repo_path.name).strip().strip("/")
        with CHECK_JOBS_LOCK:
            live_job = CHECK_JOBS.get(job_id)
            if not live_job:
                self.send_json_error(404, "Rotation job not found.")
                return
            if live_job.get("paste_in_progress"):
                self.send_json_error(409, "A pasted value is already being processed.")
                return
            live_job.update(
                {
                    "status": "running",
                    "phase": "waiting_for_paste",
                    "message": "Starting the resume command with the pasted value.",
                    "paste_in_progress": True,
                    "paste_submitted_at": utc_now(),
                    "finished_at": None,
                    "error": None,
                }
            )

        command = ["npm", "run", "rotate", "--", secret]
        _append_rotation_audit_event(
            repo_path,
            {
                "rotation_id": row.get("rotation_id") if row else None,
                "secret_name": secret,
                "step": "DASHBOARD_PASTE",
                "outcome": "submitted",
                "note": f"dashboard paste resume; job_id={job_id}; command={' '.join(command)}",
            },
        )
        thread = threading.Thread(
            target=_run_rotation_job,
            args=(job_id, repo_path, secret, command, clean_repo, paste_value),
            daemon=True,
        )
        thread.start()
        self.send_accepted_json({"job": job_snapshot(job_id)})

    def serve_rotation_job(self, job_id: str) -> None:
        if not job_id:
            self.send_json_error(400, "Provide a rotation job_id.")
            return
        snapshot = job_snapshot(job_id)
        if not snapshot or str(snapshot.get("kind") or "") != "rotation":
            self.send_json_error(404, "Rotation job not found.")
            return
        self.send_json({"job": snapshot})

    def trigger_honey_key(self, parsed, *, method: str) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(min(length, 64_000)) if length else b""
        header_dict = dict(self.headers.items())
        token = extract_honey_key_from_request(
            path=self.path,
            query=parse_qs(parsed.query),
            headers=header_dict,
            body=body,
        )
        db = ObservatoryDB(self.db_path)
        try:
            signing_secret = db.honey_signing_secret()
            if token and honey_key_is_well_formed(token, signing_secret):
                key = db.find_honey_key_by_hash(hash_honey_key(token))
                if key:
                    db.record_honey_key_trigger(
                        honey_key=key,
                        ip_address=self.client_address[0] if self.client_address else None,
                        user_agent=self.headers.get("User-Agent"),
                        method=method,
                        path=self.path,
                        headers=sanitize_headers(header_dict),
                        body_summary=summarize_body(body, self.headers.get("Content-Type")),
                        confidence=0.98 if key.get("status") != "archived" else 0.35,
                        source_type="api_call",
                    )
        finally:
            db.close()
        self.send_accepted_json({"accepted": True})

    def read_json_body(self, *, max_bytes: int = 64_000) -> dict[str, object]:
        # Defense in depth behind `_guard_mutation`: a JSON body must declare
        # itself as JSON. A forged form/`text/plain` POST (the CSRF-friendly
        # content types that dodge a CORS preflight) is refused here too, so the
        # requirement holds even if a future caller skips the dispatch guard.
        if not _is_json_content_type(self.headers.get("Content-Type")):
            raise ValueError("Mutating requests must use Content-Type: application/json.")
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(min(length, max_bytes)) if length else b"{}"
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def observatory_home(self) -> Path:
        if self.db_path.parent.name == "db":
            return self.db_path.parent.parent
        return Path(os.environ.get("SECURITY_OBSERVATORY_HOME", "~/.security-observatory")).expanduser()

    def preview_scan_results_reset(self) -> None:
        try:
            payload = self.read_json_body()
            scope, repos = self._scan_reset_scope(payload)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json_error(400, str(exc))
            return

        db = ObservatoryDB(self.db_path)
        try:
            plan = plan_scan_results_reset(db, self.observatory_home(), repos=repos)
        except ValueError as exc:
            self.send_json_error(400, str(exc))
            return
        finally:
            db.close()

        repo = repos[0] if scope == "repo" and repos else None
        self.send_json(
            {
                "plan": plan,
                "confirmation_phrase": reset_scan_results_confirmation_phrase(scope, repo),
                "backup_default": str(self.observatory_home() / "backups" / "scan-result-reset"),
            }
        )

    def reset_scan_results(self) -> None:
        try:
            payload = self.read_json_body()
            scope, repos = self._scan_reset_scope(payload)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json_error(400, str(exc))
            return

        repo = repos[0] if scope == "repo" and repos else None
        expected = reset_scan_results_confirmation_phrase(scope, repo)
        if str(payload.get("confirmation") or "") != expected:
            self.send_json_error(400, "Confirmation phrase did not match.", expected_confirmation=expected)
            return

        db = ObservatoryDB(self.db_path)
        try:
            home = self.observatory_home()
            plan = plan_scan_results_reset(db, home, repos=repos)
            backups: dict[str, str] = {}
            if bool(payload.get("keepBackup", True)):
                backups = backup_scan_results(
                    db,
                    home,
                    home / "backups" / "scan-result-reset",
                    repos=repos,
                )
            result = execute_scan_results_reset(db, home, repos=repos)
        except ValueError as exc:
            self.send_json_error(400, str(exc))
            return
        finally:
            db.close()

        self.send_json({"plan": plan, "backup": backups, "result": result})

    def _scan_reset_scope(self, payload: dict[str, object]) -> tuple[str, list[str] | None]:
        scope = str(payload.get("scope") or "all").strip()
        if scope == "all":
            return scope, None
        if scope != "repo":
            raise ValueError("Reset scope must be `all` or `repo`.")
        repo_name = str(payload.get("repoName") or "").strip()
        if not repo_name:
            raise ValueError("repoName is required for a repo-scoped reset.")
        db = ObservatoryDB(self.db_path)
        try:
            known = set(list_scan_result_repos(db))
        finally:
            db.close()
        if repo_name not in known:
            raise ValueError("Repo has no local scan results to reset.")
        return scope, [repo_name]

    def request_base_url(self) -> str:
        host = self.headers.get("Host") or f"127.0.0.1:{self.server.server_port}"
        return f"http://{host}"


def _is_safe_honeykeys_path(path: str) -> bool:
    clean = Path(path)
    parts = clean.parts
    return len(parts) >= 3 and parts[0] == ".devsec" and parts[1] == "honeykeys"


# Sentinel distinguishing "no assetNodeId given" (None, fine) from "a value was
# given but it isn't a usable node id" (reject with 400).
_INVALID_ASSET_NODE_ID = object()


def _coerce_asset_node_id(raw: Any) -> int | None | object:
    """Parse an optional bound-node id. None/blank => unbound; junk => sentinel."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return _INVALID_ASSET_NODE_ID
    return value if value > 0 else _INVALID_ASSET_NODE_ID


def _suggested_decoy_path(label: str) -> str:
    """A safe default decoy path under .devsec/honeykeys/, named after the node."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(label).lower()).strip("-")[:48] or "decoy"
    return f".devsec/honeykeys/{slug}.env"


def _catalog_tool(tool_id: str, managed_tool_records: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            tool
            for tool in tool_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
            if tool.get("id") == tool_id
        ),
        None,
    )


def _managed_record_for_uninstall(
    records: list[dict[str, Any]],
    *,
    tool_id: str,
    ownership_id: str,
) -> dict[str, Any] | None:
    candidates = [
        record
        for record in records
        if str(record.get("tool_id") or "") == tool_id
        and (not ownership_id or str(record.get("ownership_id") or "") == ownership_id)
    ]
    verified = [record for record in candidates if managed_tool_evidence(record).verified]
    if len(verified) == 1:
        return verified[0]
    if ownership_id and candidates:
        return candidates[0]
    return None


def serve_dashboard(db_path: Path, assets_dir: Path, port: int, open_browser: bool) -> None:
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"db_path": db_path, "assets_dir": assets_dir})
    try:
        _rediscover_rotation_jobs(db_path)
    except Exception as exc:
        print(f"Rotation job rediscovery skipped: {exc}")
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Security Observatory dashboard: {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
