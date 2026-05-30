"""MCP adapter for the local Security Observatory.

The default ``devsec-mcp`` server exposes eleven read-only tools over stdio so
local agents (Claude Desktop, Cursor, Codex, etc.) can ask focused questions
about scan history without an HTTP listener, write paths, or cloud round-trip.

The explicit ``devsec-mcp-rw`` entrypoint keeps the same stdio-only transport
and adds only the guarded AI case-resolution prompt/preview/apply tools.

See mcp/README.md for connection instructions and the deliberate hard limits.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .case_followup import (
    apply_case_resolutions as _apply_case_resolutions,
    build_case_followup_prompt as _build_case_followup_prompt,
    validate_case_resolutions as _validate_case_resolutions,
)
from .cli import build_parser as _build_scan_parser, scan_repo as _scan_repo
from .fix_proposals import (
    clean_room_review_packet as _clean_room_review_packet,
    decide_landing as _decide_landing,
    propose_fix as _propose_fix,
    record_clean_room_review as _record_clean_room_review,
)
from .cases import (
    _DEFAULT_PLAYBOOK_ID,
    _PLAYBOOK_BY_CATEGORY,
    _RECOVERY_PLAYBOOK_TEMPLATES,
)
from .rotation import (
    read_rotation_history as _read_rotation_history,
    read_rotation_status as _read_rotation_status,
)
from .storage import ObservatoryDB


logger = logging.getLogger("security_observatory.mcp")

SUPPORTED_SEVERITIES = ("critical", "high", "medium", "low", "info")
SUPPORTED_CASE_STATUSES = ("open", "verified", "accepted_risk", "resolved")
SUPPORTED_CATEGORIES = tuple(sorted(_PLAYBOOK_BY_CATEGORY.keys()))
# Scan-trigger contract (docs/rw-extend-spec.md §1): the only profiles the AI may
# request, both local and network-free. Anything outside the enum is refused.
SCAN_PROFILES = ("quick", "default")
# Per-repo cooldown for AI-triggered scans. Bounds scan-spam / resource abuse.
# Manual CLI scans are unaffected — this only rate-limits the MCP trigger.
SCAN_COOLDOWN_SECONDS = 600
_READ_ONLY_BOUNDARY = (
    "Respect the MCP boundary: this adapter is read-only and stdio-only. It can report scan history, "
    "cases, raw findings, playbooks, dependency trust, Honey Key state, and rotation state for repos "
    "where the secrets-rotation skill is scaffolded. It cannot delete raw findings, mark cases resolved, "
    "modify the store, install scanners, or rotate credentials — rotation triggering happens through "
    "the dashboard or the /devsec-rotate slash command, not through MCP."
)
_WRITE_MODE_BOUNDARY = (
    "Respect the MCP write boundary: this adapter was launched in explicit case-decision write mode "
    "and remains stdio-only. It can build AI case follow-up prompts, preview devsec.case_resolutions.v1 "
    "JSON, apply validated case decisions through the audited case-resolution path, and trigger a "
    "guarded local-offline scan of an already-scanned repo (by name, fixed profile, rate-limited). "
    "Suppressing a high/critical case never auto-applies — it is held for explicit human confirmation. "
    "It can also record a code-fix proposal on a new branch and run it through a clean-room reviewer that "
    "sees only the diff and the invariants (never the finding text); only narrow low-risk classes "
    "(action SHA pins, single patch/minor dependency bumps, lockfile patches) reach auto-merge on a "
    "recorded clean-room approval, and every other class stops for a human. "
    "It cannot delete raw findings, delete scans, scan an arbitrary filesystem path, rotate credentials, "
    "execute SQL, install tools, write repository files, or merge to a protected branch."
)
DEVSEC_MCP_INSTRUCTIONS = f"""You are the DëvSec security helper. Speak like a calm operational security analyst, not a chatbot, hype product, or fake tactical persona.

Purpose: help the user understand local scan history, act safely, and verify closure. DëvSec is local-first: scan evidence and history stay on the user's machine unless they choose otherwise.

For cases, lead with: Action: <fix_now|verify|watch|info> · Severity: <critical|high|medium|low|info>. Use "raw findings" only for scanner-level evidence rows.

Default structure:
1. Status: what happened.
2. Impact: practical consequence in plain language.
3. Evidence: file path, package version, rule, raw finding ID, confidence, scan scope, or source.
4. Action: the next concrete step.
5. Verification: how closure is confirmed.

Rules:
- Bind every claim to evidence.
- Separate confirmed facts from uncertainty.
- Say "clear within scan scope," not "secure."
- Say "no evidence found," not "no breach occurred," unless logs prove it.
- Use active verbs: revoke, rotate, remove, patch, upgrade, restrict, isolate, review, verify, rescan, escalate.
- For critical cases, use short sentences and ordered steps.
- Never shame the developer.
- No panic, softness, jokes, casual filler, exclamation marks, or emoji.
- Exception: use ⚠ only for an actively triggered Honey Key.
- {_READ_ONLY_BOUNDARY}

Full doctrine: docs/agent-voice.md. Safety tiers and refusal language: docs/agent-safety.md."""
DEVSEC_MCP_RW_INSTRUCTIONS = DEVSEC_MCP_INSTRUCTIONS.replace(
    _READ_ONLY_BOUNDARY,
    _WRITE_MODE_BOUNDARY,
)


class RepoNotFoundError(ValueError):
    """Raised when a requested repo has no scan history in the local DB."""


def observatory_home() -> Path:
    return Path(os.environ.get("SECURITY_OBSERVATORY_HOME", "~/.security-observatory")).expanduser()


def _db_path(home: Path) -> Path:
    return home / "db" / "observatory.sqlite"


def _open_db(home: Path) -> ObservatoryDB | None:
    path = _db_path(home)
    if not path.exists():
        return None
    return ObservatoryDB(path)


def _require_db(db: ObservatoryDB | None) -> ObservatoryDB:
    if db is None:
        raise RepoNotFoundError(
            "No DëvSec database found. Run a scan before using MCP case tools."
        )
    return db


def _redact_path(value: Any, repo_path: str | None = None) -> str | None:
    """Return a path that never leaks the user's absolute home prefix.

    Repo-relative when possible; otherwise anonymized with ~ in place of $HOME.
    Falls back to stripping the user segment from /Users/<name>/... so the
    output never contains the operator's name.
    """
    if value is None:
        return None
    text = str(value)
    if not text:
        return text
    if repo_path:
        try:
            repo = Path(repo_path).expanduser().resolve()
            candidate = Path(text)
            if candidate.is_absolute():
                try:
                    rel = candidate.resolve().relative_to(repo)
                    return str(rel)
                except ValueError:
                    pass
        except (OSError, RuntimeError):
            pass
    try:
        home = str(Path.home())
        if text.startswith(home + os.sep) or text == home:
            return "~" + text[len(home):]
    except (OSError, RuntimeError):
        pass
    for prefix in ("/Users/", "/home/", "/root/"):
        if text.startswith(prefix):
            parts = Path(text).parts
            if len(parts) >= 4:
                return "~/" + str(Path(*parts[3:]))
            return "~"
    return text


def _redact_files(values: Any, repo_path: str | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for value in values:
        redacted = _redact_path(value, repo_path)
        if redacted:
            out.append(redacted)
    return out


def _placement_repo(value: Any, project_id: Any) -> str:
    raw = str(value or "")
    if raw == "~":
        return str(project_id or "")
    if raw.startswith((os.sep, "~/")):
        return Path(raw).name or (_redact_path(raw) or str(project_id or ""))
    text = _redact_path(raw) or str(project_id or "")
    if text.startswith(os.sep):
        return Path(text).name or text
    return text


def _evidence_excerpt(row: dict[str, Any]) -> str | None:
    for key in ("evidence_summary", "remediation", "title"):
        value = row.get(key)
        if value:
            text = str(value).strip()
            if not text:
                continue
            return text if len(text) <= 240 else text[:237] + "..."
    return None


def _finding_payload(row: dict[str, Any], repo_path: str | None) -> dict[str, Any]:
    return {
        "id": int(row["id"]) if row.get("id") is not None else None,
        "title": str(row.get("title") or ""),
        "severity": str(row.get("severity") or "medium"),
        "category": str(row.get("category") or "unknown"),
        "scanner": str(row.get("scanner") or ""),
        "path": _redact_path(row.get("file"), repo_path),
        "line": int(row["line"]) if row.get("line") is not None else None,
        "evidence_excerpt": _evidence_excerpt(row),
    }


def _case_status_label(case: dict[str, Any]) -> str:
    decision = case.get("decision") or {}
    raw = str(decision.get("status") or "").lower()
    if raw in ("false_positive", "fixed"):
        return "resolved"
    if raw in ("verified", "accepted_risk"):
        return raw
    return "open"


def _case_payload(case: dict[str, Any], repo_path: str | None) -> dict[str, Any]:
    return {
        "id": str(case.get("case_id") or case.get("id") or ""),
        "title": str(case.get("title") or "Security case"),
        "plain_english_risk": str(case.get("plain_english_risk") or ""),
        "severity": str(case.get("severity") or "medium"),
        "category": str(case.get("category") or "unknown"),
        "action_level": str(case.get("action_level") or "verify"),
        "confidence": str(case.get("confidence") or "medium"),
        "affected_files": _redact_files(case.get("affected_files"), repo_path),
        "suggested_steps": [str(step) for step in (case.get("fix_steps") or []) if step],
        "agent_handoff_prompt": str(case.get("agent_prompt") or ""),
        "status": _case_status_label(case),
    }


def _trust_payload(row: dict[str, Any]) -> dict[str, Any]:
    sources: list[str] = []
    for key in ("source_repo_url", "source_repo"):
        value = row.get(key)
        if value and str(value) not in sources:
            sources.append(str(value))
    return {
        "package": row.get("package_name"),
        "version": row.get("package_version"),
        "trust_score": row.get("scorecard_score"),
        "sources": sources,
        "last_updated": row.get("checked_at"),
    }


def _honey_severity(
    key: dict[str, Any],
    project_statuses: dict[str, dict[str, Any]],
) -> str | None:
    trigger_count = int(key.get("trigger_count") or 0)
    if trigger_count <= 0 and not key.get("last_triggered_at"):
        return None
    project = project_statuses.get(str(key.get("project_id"))) or {}
    if project.get("status") == "red" or key.get("status") == "triggered":
        return "critical"
    return "high"


def _honey_key_payload(
    key: dict[str, Any],
    project_statuses: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": str(key.get("id") or ""),
        "project_id": str(key.get("project_id") or ""),
        "status": str(key.get("status") or "active"),
        "placed_at": key.get("created_at"),
        "placement_repo": _placement_repo(key.get("repo_id"), key.get("project_id")),
        "trigger_count": int(key.get("trigger_count") or 0),
        "last_triggered_at": key.get("last_triggered_at"),
        "severity_if_triggered": _honey_severity(key, project_statuses),
    }


def _list_repos(db: ObservatoryDB | None) -> list[dict[str, Any]]:
    if db is None:
        return []
    rows = db.conn.execute(
        """
        select repo_name as name,
               max(started_at) as last_scan_at,
               count(*) as scan_count
        from scans
        group by repo_name
        order by last_scan_at desc, name asc
        """
    ).fetchall()
    return [
        {
            "name": row["name"],
            "last_scan_at": row["last_scan_at"],
            "scan_count": int(row["scan_count"]),
        }
        for row in rows
    ]


def _honey_keys(db: ObservatoryDB | None) -> list[dict[str, Any]]:
    if db is None:
        return []
    # Touch events as part of the public contract: trigger counts and recency
    # must reflect the event stream, even when an old key row is incomplete.
    events = db.list_honey_key_events(limit=100)
    last_event_by_key: dict[str, dict[str, Any]] = {}
    trigger_counts: dict[str, int] = {}
    for event in events:
        key_id = str(event.get("honey_key_id") or "")
        if not key_id:
            continue
        trigger_counts[key_id] = trigger_counts.get(key_id, 0) + 1
        last_event_by_key.setdefault(key_id, event)
    project_statuses = db.project_statuses()
    payloads = []
    for key in db.list_honey_keys():
        key_id = str(key.get("id") or "")
        last_event = last_event_by_key.get(key_id)
        normalized = dict(key)
        normalized["trigger_count"] = max(
            int(normalized.get("trigger_count") or 0),
            trigger_counts.get(key_id, 0),
        )
        if last_event and not normalized.get("last_triggered_at"):
            normalized["last_triggered_at"] = last_event.get("triggered_at")
        payloads.append(_honey_key_payload(normalized, project_statuses))
    payloads.sort(
        key=lambda item: (
            int(item["trigger_count"]) > 0 or item["status"] == "triggered",
            item.get("last_triggered_at") or item.get("placed_at") or "",
        ),
        reverse=True,
    )
    return payloads[:100]


def _latest_scan(db: ObservatoryDB | None, repo: str) -> dict[str, Any]:
    if db is None:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    scan = db.latest_scan_for_repo(repo)
    if not scan:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    finding_count_row = db.conn.execute(
        "select count(*) as n from findings where scan_id = ?",
        (scan["id"],),
    ).fetchone()
    scanner_statuses = []
    try:
        import json as _json
        scanner_statuses = _json.loads(scan.get("scanner_status_json") or "[]")
    except (TypeError, ValueError):
        scanner_statuses = []
    return {
        "scan_id": scan["id"],
        "started_at": scan["started_at"],
        "finished_at": scan["finished_at"],
        "scanner_count": len(scanner_statuses) if isinstance(scanner_statuses, list) else 0,
        "finding_count": int(finding_count_row["n"]) if finding_count_row else 0,
        "health_score": int(scan["health_score"]),
        "status": scan["status"],
    }


def _scan_history(db: ObservatoryDB | None, repo: str, limit: int = 10) -> list[dict[str, Any]]:
    if db is None:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    try:
        bounded_limit = int(limit)
    except (TypeError, ValueError):
        bounded_limit = 10
    bounded_limit = max(1, min(bounded_limit, 50))
    rows = db.conn.execute(
        """
        select s.id as scan_id,
               s.started_at,
               s.finished_at,
               s.health_score,
               s.status,
               count(f.id) as finding_count
        from scans s
        left join findings f on f.scan_id = s.id
        where s.repo_name = ?
        group by s.id, s.started_at, s.finished_at, s.health_score, s.status
        order by s.started_at desc
        limit ?
        """,
        (repo, bounded_limit),
    ).fetchall()
    if not rows:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    return [
        {
            "scan_id": row["scan_id"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "health_score": int(row["health_score"]),
            "finding_count": int(row["finding_count"]),
            "status": row["status"],
        }
        for row in rows
    ]


def _findings(
    db: ObservatoryDB | None,
    repo: str,
    severity: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    if db is None:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    scan = db.latest_scan_for_repo(repo)
    if not scan:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    if severity is not None:
        severity_normalized = severity.lower()
        if severity_normalized not in SUPPORTED_SEVERITIES:
            raise ValueError(
                f"Unknown severity {severity!r}. Use one of: {', '.join(SUPPORTED_SEVERITIES)}"
            )
    else:
        severity_normalized = None
    try:
        bounded_limit = int(limit)
    except (TypeError, ValueError):
        bounded_limit = 50
    bounded_limit = max(1, min(bounded_limit, 500))
    params: list[Any] = [scan["id"]]
    where_severity = ""
    if severity_normalized:
        where_severity = "and severity = ?"
        params.append(severity_normalized)
    params.append(bounded_limit)
    rows = db.conn.execute(
        f"""
        select id, title, severity, category, scanner, file, line,
               evidence_summary, remediation
        from findings
        where scan_id = ? {where_severity}
        order by id asc
        limit ?
        """,
        params,
    ).fetchall()
    return [_finding_payload(dict(row), scan.get("repo_path")) for row in rows]


def _cases(
    db: ObservatoryDB | None,
    repo: str,
    status: str | None,
    scan_id: str | None = None,
) -> list[dict[str, Any]]:
    if db is None:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    if scan_id:
        export = db.scan_export(scan_id)
        if not export or export.get("repo") != repo:
            raise ValueError(f"Scan {scan_id!r} was not found for repo {repo!r}")
        scan = {
            "id": export["scan_id"],
            "repo_path": export.get("repo_path"),
        }
    else:
        scan = db.latest_scan_for_repo(repo)
        if not scan:
            raise RepoNotFoundError(f"No scans found for repo {repo!r}")
        export = db.scan_export(scan["id"])
    requested = (status or "open").lower()
    if requested not in SUPPORTED_CASE_STATUSES:
        raise ValueError(
            f"Unknown status {status!r}. Use one of: {', '.join(SUPPORTED_CASE_STATUSES)}"
        )
    if not export:
        return []
    cases = export.get("cases", [])
    repo_path = export.get("repo_path") or scan.get("repo_path")
    payloads = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        if _case_status_label(case) != requested:
            continue
        payloads.append(_case_payload(case, repo_path))
    return payloads


def _recovery_playbook(category: str) -> dict[str, Any]:
    normalized = (category or "").strip().lower()
    if not normalized:
        raise ValueError(
            f"category is required. Use one of: {', '.join(SUPPORTED_CATEGORIES)}"
        )
    if normalized not in _PLAYBOOK_BY_CATEGORY:
        raise ValueError(
            f"Unknown category {category!r}. Use one of: {', '.join(SUPPORTED_CATEGORIES)}"
        )
    template_id = _PLAYBOOK_BY_CATEGORY.get(normalized, _DEFAULT_PLAYBOOK_ID)
    template = _RECOVERY_PLAYBOOK_TEMPLATES[template_id]
    steps = [step.replace("{files}", "the affected files") for step in template.step_templates]
    agent_prompt = (
        f"Work through the {template.title} playbook for {normalized} raw findings. "
        "Read each step before acting and confirm impact in the repo before changing code. "
        + " ".join(steps)
    )
    return {
        "category": normalized,
        "title": template.title,
        "steps": steps,
        "estimated_minutes": template.base_minutes,
        "agent_prompt": agent_prompt,
    }


def _dependency_trust(db: ObservatoryDB | None, repo: str) -> list[dict[str, Any]]:
    if db is None:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    scan = db.latest_scan_for_repo(repo)
    if not scan:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    rows = db.list_dependency_trust_enrichments(scan_id=scan["id"], repo_name=repo)
    return [_trust_payload(row) for row in rows]


# ---------------------------------------------------------------------------
# Rotation tools — thin wrappers over rotation.py. The shared module owns the
# state-file parsing and normalization; this layer just resolves the repo's
# on-disk path via the scan record (so the MCP and the dashboard speak the
# same repo vocabulary) and proxies the result.
# ---------------------------------------------------------------------------


def _resolve_repo_path(db: ObservatoryDB | None, repo: str) -> str:
    """Return the on-disk path for ``repo`` or raise RepoNotFoundError.

    The MCP doesn't track "repos with rotation set up" — it tracks scanned
    repos. The rotation tools reuse the scan record's `repo_path` as the
    authoritative resolver so the agent's repo vocabulary stays consistent
    across all tools.
    """
    if db is None:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    scan = db.latest_scan_for_repo(repo)
    if not scan:
        raise RepoNotFoundError(f"No scans found for repo {repo!r}")
    repo_path = scan.get("repo_path")
    if not repo_path:
        raise RepoNotFoundError(f"No repo path on file for repo {repo!r}")
    return str(repo_path)


def _scan_args(profile: str) -> Any:
    """Build a bounded scan args namespace for an AI-triggered scan.

    Reuses the CLI parser so every flag scan_repo reads exists with its real
    default, then forces the local-offline invariants: no network egress
    (dependency-trust, connected platform-posture, behavioral-drift artifact
    fetches) regardless of profile. ``profile`` is already validated against
    ``SCAN_PROFILES`` by the caller.
    """
    args = _build_scan_parser().parse_args([])
    args.trust = False
    args.trust_cache_only = False
    args.behavioral_drift = False
    args.platform_posture = False
    args.full = False
    # "quick" → low-cost local scanners; "default" → the standard local scanner
    # set (all flags off makes scanner_names_for_profile fall through to it).
    args.quick = profile == "quick"
    return args


def _scan_cooldown_remaining(latest_scan: dict[str, Any] | None, *, now: datetime | None = None) -> int:
    """Seconds left on the per-repo cooldown, or 0 if a scan may run now."""
    if not latest_scan:
        return 0
    started_raw = latest_scan.get("started_at")
    if not started_raw:
        return 0
    try:
        started = datetime.fromisoformat(str(started_raw))
    except ValueError:
        return 0
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    remaining = SCAN_COOLDOWN_SECONDS - (current - started).total_seconds()
    return int(remaining) if remaining > 0 else 0


def _trigger_scan(
    db: ObservatoryDB | None,
    home: Path,
    *,
    repo: str,
    profile: str = "quick",
) -> dict[str, Any]:
    """Trigger a guarded local-offline scan of an allowlisted repo.

    Constraints (docs/rw-extend-spec.md §1): ``repo`` is a NAME resolved to its
    recorded path via the scan history (never a raw caller-supplied path);
    ``profile`` is a fixed enum; the scan is rate-limited per repo; and it routes
    through the existing append-only ``scan_repo`` path, not a reimplementation.
    No parameter is derived from finding text.
    """
    db = _require_db(db)
    clean_profile = str(profile or "").strip().lower()
    if clean_profile not in SCAN_PROFILES:
        raise ValueError(
            f"Unknown scan profile {profile!r}. Use one of: {', '.join(SCAN_PROFILES)}"
        )
    # Resolve the repo NAME to its recorded path. Raises RepoNotFoundError when
    # the repo has no scan history — so the AI can only re-scan repos already in
    # the local store, never an arbitrary filesystem path injected from text.
    repo_path = _resolve_repo_path(db, repo)
    latest = db.latest_scan_for_repo(repo)
    remaining = _scan_cooldown_remaining(latest)
    if remaining > 0:
        return {
            "outcome": "rate_limited",
            "repo": repo,
            "retry_after_seconds": remaining,
            "cooldown_seconds": SCAN_COOLDOWN_SECONDS,
            "last_scan_started_at": (latest or {}).get("started_at"),
        }
    args = _scan_args(clean_profile)
    summary = _scan_repo(Path(repo_path), args, home)
    scanners = summary.get("scanners") or []
    findings = summary.get("findings") or []
    return {
        "outcome": "completed",
        "repo": repo,
        "profile": clean_profile,
        "scan_id": summary.get("scan_id"),
        "started_at": summary.get("started_at"),
        "finished_at": summary.get("finished_at"),
        "scanner_count": len(scanners) if isinstance(scanners, list) else 0,
        "finding_count": len(findings) if isinstance(findings, list) else 0,
        "health_score": summary.get("health_score"),
        "status": summary.get("status"),
    }


def _rotation_status(db: ObservatoryDB | None, repo: str) -> list[dict[str, Any]]:
    """Return per-secret rotation status for ``repo`` via the shared parser."""
    repo_path = _resolve_repo_path(db, repo)
    return _read_rotation_status(repo_path)


def _rotation_history(
    db: ObservatoryDB | None,
    repo: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return rotation log events for ``repo`` via the shared parser."""
    repo_path = _resolve_repo_path(db, repo)
    return _read_rotation_history(repo_path, limit)


def _case_followup_prompt(
    db: ObservatoryDB | None,
    *,
    repo: str,
    action: str = "verify_findings",
    scope: str = "critical",
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    return _build_case_followup_prompt(
        _require_db(db),
        repo_name=repo,
        action=action,
        scope=scope,
        case_ids=case_ids or [],
    )


def _preview_case_resolutions(
    db: ObservatoryDB | None,
    *,
    payload: dict[str, Any],
    expected_repo: str | None = None,
    expected_scope: str | None = None,
    expected_case_ids: list[str] | None = None,
) -> dict[str, Any]:
    return _validate_case_resolutions(
        _require_db(db),
        payload,
        expected_repo=expected_repo,
        expected_scope=expected_scope,
        expected_case_ids=expected_case_ids,
        source="mcp_write",
        persist=True,
    )


def _apply_case_resolution_payload(
    db: ObservatoryDB | None,
    *,
    payload: dict[str, Any] | None = None,
    run_id: str | None = None,
    expected_repo: str | None = None,
    expected_scope: str | None = None,
    expected_case_ids: list[str] | None = None,
) -> dict[str, Any]:
    if run_id:
        payload_or_run_id: dict[str, Any] | str = run_id
    elif isinstance(payload, dict):
        payload_or_run_id = payload
    else:
        raise ValueError("Provide either run_id or payload.")
    return _apply_case_resolutions(
        _require_db(db),
        payload_or_run_id,
        expected_repo=expected_repo,
        expected_scope=expected_scope,
        expected_case_ids=expected_case_ids,
        source="mcp_write",
    )


def create_server(
    home: Path | None = None,
    *,
    allow_case_decisions: bool = False,
) -> FastMCP:
    """Build a FastMCP server bound to the observatory at ``home``.

    Exposed in factory form so tests can point at a temp directory and the
    runtime entrypoint can read the SECURITY_OBSERVATORY_HOME env var.
    """
    resolved = home or observatory_home()
    server = FastMCP(
        "devsec",
        instructions=(
            DEVSEC_MCP_RW_INSTRUCTIONS
            if allow_case_decisions
            else DEVSEC_MCP_INSTRUCTIONS
        ),
    )

    def _with_db(action):
        db = _open_db(resolved)
        try:
            return action(db)
        finally:
            if db is not None:
                db.close()

    @server.tool()
    def list_repos() -> list[dict[str, Any]]:
        """List repositories with scan history in the local observatory.

        Returns one entry per repo with its most-recent scan timestamp and
        total scan count. Returns an empty list when no scans have been run.
        """
        return _with_db(_list_repos)

    @server.tool()
    def honey_keys() -> list[dict[str, Any]]:
        """List Honey Keys with placement and trigger state.

        Returns up to 100 keys sorted triggered-first, then by recency. Each
        row includes project id, status, placement repo, trigger count, last
        trigger timestamp, and a minimal severity if a key was touched.
        """
        return _with_db(_honey_keys)

    @server.tool()
    def latest_scan(repo: str) -> dict[str, Any]:
        """Return the most recent scan summary for ``repo``.

        Includes scan id, timing, scanner and finding counts, the health score,
        and overall status. Raises if the repo has no scan history.
        """
        return _with_db(lambda db: _latest_scan(db, repo))

    @server.tool()
    def scan_history(repo: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return previous scans for ``repo``, most recent first.

        ``limit`` defaults to 10 and is capped at 50. Raises if the repo has
        no scan history.
        """
        return _with_db(lambda db: _scan_history(db, repo, limit))

    @server.tool()
    def raw_findings(
        repo: str,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return raw findings from the most recent scan of ``repo``.

        Raw findings are scanner-level evidence. Cases are the user-facing
        grouped work items. Filter by severity (critical | high | medium | low
        | info) or omit for all. ``limit`` caps the result count (default 50,
        max 500). Paths are repo-relative; absolute home-directory paths are
        never returned.
        """
        return _with_db(lambda db: _findings(db, repo, severity, limit))

    @server.tool()
    def findings(
        repo: str,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Compatibility alias for ``raw_findings``.

        Prefer ``raw_findings`` in new prompts and clients. This tool remains
        for existing MCP consumers that already call ``findings``.
        """
        return _with_db(lambda db: _findings(db, repo, severity, limit))

    @server.tool()
    def cases(
        repo: str,
        status: str | None = None,
        scan_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return action-level cases for a scan of ``repo``.

        Cases are the project's primary unit of value: each is a grouped,
        plain-English explanation with suggested steps and an agent handoff
        prompt. Filter ``status`` by open | verified | accepted_risk |
        resolved (default open). Pass ``scan_id`` to inspect a previous scan;
        otherwise the latest scan is used.
        """
        return _with_db(lambda db: _cases(db, repo, status, scan_id))

    @server.tool()
    def recovery_playbook(category: str) -> dict[str, Any]:
        """Return the recovery playbook for a finding ``category``.

        Categories come from the case-builder vocabulary: secrets,
        dependencies, ai-risk, iac, platform-posture, workflow, install-hooks,
        behavioral-drift, silent-upgrade, supply-chain-ioc, code-security.
        Returns title, steps, estimated minutes, and a ready-to-paste agent
        prompt. No DB access required.
        """
        return _recovery_playbook(category)

    @server.tool()
    def dependency_trust(repo: str) -> list[dict[str, Any]]:
        """Return dependency trust records for the most recent scan of ``repo``.

        Each entry covers a single package with its OpenSSF-style score,
        upstream-repo sources, and the last enrichment timestamp. Returns an
        empty list when no trust data has been collected for the repo.
        """
        return _with_db(lambda db: _dependency_trust(db, repo))

    @server.tool()
    def rotation_status(repo: str) -> list[dict[str, Any]]:
        """Return per-secret rotation state for ``repo``.

        Reads the secrets-rotation skill's `data/rotation-state.json` inside
        the repo. Each entry: secret name, class (A | B-API | B-human | C),
        current status (NEVER | HEALTH_CHECK | … | ROTATED | IN_GRACE |
        HALTED), last rotation timestamp, days since rotation, configured
        cadence, next-rotation-due timestamp, the in-flight rotation_id (if
        any), in_grace_until (set when the old key is still valid in the
        grace window), a needs_attention flag (true for failed terminals
        or overdue cadence), manually_marked (true when the rotation's
        terminal status came from an operator override rather than the
        pipeline), and override_kind (the CLI flag used, e.g.
        ``--mark-rotated``, or null for pipeline-completed rotations).
        Returns an empty list for repos that have scan history but no
        rotation skill scaffolded — the dashboard reads that empty result
        as the signal to show a "Set up rotation" CTA. Raises
        RepoNotFoundError when the repo has no scan history.
        """
        return _with_db(lambda db: _rotation_status(db, repo))

    @server.tool()
    def rotation_history(repo: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent rotation events for ``repo``, most-recent first.

        Reads the secrets-rotation skill's `data/rotation-log.jsonl` inside
        the repo. Each event: timestamp, secret, rotation_id, step (e.g.,
        HEALTH_CHECK, PREFLIGHT, ACQUIRE, STAGE_CANARY, DEPLOY_CANARY,
        VERIFY_CANARY, STAGE_PROD, DEPLOY_PROD, VERIFY_PROD, SOAK, GRACE,
        REVOKE, HALT, ROLLBACK), outcome (started | succeeded | halted |
        skipped), optional plain-English note, and optional duration in ms.
        Default `limit` is 20; capped at 100. Returns an empty list when no
        log file exists. Raises RepoNotFoundError when the repo has no scan
        history.
        """
        return _with_db(lambda db: _rotation_history(db, repo, limit))

    if allow_case_decisions:

        @server.tool()
        def trigger_scan(repo: str, profile: str = "quick") -> dict[str, Any]:
            """Trigger a guarded local-offline scan of an already-scanned repo.

            ``repo`` is a repo NAME from ``list_repos`` (never a filesystem path);
            it resolves to the repo's recorded path. ``profile`` is one of
            ``quick`` (low-cost local scanners) or ``default`` (the standard local
            scanner set) — no other value, no scanner names, no flags. The scan is
            network-free and rate-limited per repo (10-minute cooldown); a trigger
            inside the cooldown returns a structured ``rate_limited`` outcome with
            the seconds remaining. It runs the existing append-only scan path and
            returns the new scan summary (scan_id, timing, counts, health, status).
            It cannot scan an arbitrary path, take scan parameters from finding
            text, reach the network, or delete/alter prior scans or decisions.
            """
            return _with_db(
                lambda db: _trigger_scan(db, resolved, repo=repo, profile=profile)
            )

        @server.tool()
        def case_followup_prompt(
            repo: str,
            action: str = "verify_findings",
            scope: str = "critical",
            case_ids: list[str] | None = None,
        ) -> dict[str, Any]:
            """Build a bounded AI follow-up prompt for selected open cases.

            This is a write-mode tool because it is paired with preview/apply,
            but it does not mutate the store. ``action`` and ``scope`` use the
            same values as the dashboard AI follow-up panel.
            """
            return _with_db(
                lambda db: _case_followup_prompt(
                    db,
                    repo=repo,
                    action=action,
                    scope=scope,
                    case_ids=case_ids,
                )
            )

        @server.tool()
        def preview_case_resolutions(
            payload: dict[str, Any],
            expected_repo: str | None = None,
            expected_scope: str | None = None,
            expected_case_ids: list[str] | None = None,
        ) -> dict[str, Any]:
            """Validate and audit AI case-resolution JSON without applying it.

            Accepts ``devsec.case_resolutions.v1`` payloads only. The preview
            is stored as an audit run and returns item-level warnings, mapped
            decisions, and apply counts.
            """
            return _with_db(
                lambda db: _preview_case_resolutions(
                    db,
                    payload=payload,
                    expected_repo=expected_repo,
                    expected_scope=expected_scope,
                    expected_case_ids=expected_case_ids,
                )
            )

        @server.tool()
        def apply_case_resolutions(
            payload: dict[str, Any] | None = None,
            run_id: str | None = None,
            expected_repo: str | None = None,
            expected_scope: str | None = None,
            expected_case_ids: list[str] | None = None,
        ) -> dict[str, Any]:
            """Apply validated AI case resolutions through the audited path.

            Pass a ``run_id`` returned by ``preview_case_resolutions`` to apply
            a reviewed preview, or pass a fresh ``payload`` to validate and
            apply in one call. Only supported case decisions are written.
            """
            return _with_db(
                lambda db: _apply_case_resolution_payload(
                    db,
                    payload=payload,
                    run_id=run_id,
                    expected_repo=expected_repo,
                    expected_scope=expected_scope,
                    expected_case_ids=expected_case_ids,
                )
            )

        @server.tool()
        def propose_fix(
            repo: str,
            diff: str,
            head_branch: str,
            title: str,
            case_id: str | None = None,
            base_branch: str = "main",
        ) -> dict[str, Any]:
            """Record a code-fix proposal on a new, non-protected branch.

            ``repo`` is a repo NAME with scan history (never a filesystem path).
            The unified ``diff`` is classified from its own bytes into a fix class;
            only narrow low-risk classes (action SHA pins, single patch/minor
            dependency bumps, lockfile patches) are auto-merge-eligible. A proposal
            that targets a protected branch — or whose ``head_branch`` equals
            ``base_branch`` — is refused: a fix opens a branch/PR, it never commits
            to a protected branch directly. Returns the audited proposal record
            (id, fix class, auto-merge eligibility, branches). This records the
            proposal; opening the actual branch/PR is the orchestrating command's
            git work.
            """
            return _with_db(
                lambda db: _propose_fix(
                    _require_db(db),
                    repo=repo,
                    diff=diff,
                    head_branch=head_branch,
                    title=title,
                    case_id=case_id,
                    base_branch=base_branch,
                    source="mcp_write",
                )
            )

        @server.tool()
        def clean_room_review_packet(proposal_id: str) -> dict[str, Any]:
            """Return the clean-room review packet for a fix proposal — diff only.

            This is the surface the *separate* clean-room reviewer agent is handed.
            It contains the diff, the diff-derived fix class, the changed files, and
            the invariant checklist — and, by construction, no finding/case text:
            the packet is rebuilt from the stored diff bytes and never reads the
            proposal's case id, title, or any finding context. Echo the returned
            ``diff_sha256`` back when recording the verdict.
            """
            return _with_db(
                lambda db: _clean_room_review_packet(_require_db(db), proposal_id=proposal_id)
            )

        @server.tool()
        def record_clean_room_review(
            proposal_id: str,
            approved: bool,
            diff_sha256: str,
            checked_invariants: list[str] | None = None,
            reviewer: str | None = None,
            notes: str | None = None,
        ) -> dict[str, Any]:
            """Record the clean-room reviewer's verdict in the audit trail.

            ``diff_sha256`` must be the hash from the review packet; the verdict is
            refused if it does not match the diff on file, so an approval can never
            be attributed to a different diff. Recording an approval is a
            precondition for ``land_fix`` to authorize an auto-merge.
            """
            return _with_db(
                lambda db: _record_clean_room_review(
                    _require_db(db),
                    proposal_id=proposal_id,
                    approved=approved,
                    diff_sha256=diff_sha256,
                    checked_invariants=checked_invariants,
                    reviewer=reviewer,
                    notes=notes,
                )
            )

        @server.tool()
        def land_fix(proposal_id: str) -> dict[str, Any]:
            """Decide whether a proposal may auto-merge, and record the decision.

            Returns ``auto_merge`` only when a clean-room approval is recorded
            against the exact diff on file and that diff re-derives to an
            auto-merge-eligible class on a real (non-protected) branch. Anything
            else returns ``requires_human`` (or ``blocked``). The fix class is
            recomputed from the diff bytes here, so a mislabeled proposal cannot
            reach auto-merge. Authorizing the merge does not perform it — the
            physical ``gh``/git merge stays with the orchestrating command.
            """
            return _with_db(lambda db: _decide_landing(_require_db(db), proposal_id=proposal_id))

    return server


def main() -> None:
    """Console entrypoint for ``devsec-mcp``. Stdio transport only."""
    logging.basicConfig(
        stream=sys.stderr,
        level=os.environ.get("DEVSEC_MCP_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    server = create_server()
    server.run()


def main_rw() -> None:
    """Console entrypoint for ``devsec-mcp-rw``. Stdio transport only."""
    logging.basicConfig(
        stream=sys.stderr,
        level=os.environ.get("DEVSEC_MCP_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    server = create_server(allow_case_decisions=True)
    server.run()


if __name__ == "__main__":
    main()
