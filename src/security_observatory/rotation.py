"""Shared rotation-state helpers.

Reads the secrets-rotation skill's on-disk state files (`data/rotation-state.json`,
`data/rotation-log.jsonl`, `data/rotation-receipts/*.md`) and normalises them into
the locked dashboard/MCP shape. Both `mcp_server.py` (read-only stdio tools) and
`dashboard_server.py` (HTTP endpoints + scan-time detection) consume this module
so one parser owns the on-disk contract.

No DB access here. Repo→path resolution stays a caller concern because MCP uses
the scan record's `repo_path` and the dashboard uses the in-summary `path` field.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger("security_observatory.rotation")


# ---------------------------------------------------------------------------
# Locked status vocabulary — mirrored in the dashboard's RotationStatusCard.
# Failure terminals + NEVER/unknown drive `needs_attention` so the UI can
# highlight what's waiting on the operator without re-interpreting strings.
# ---------------------------------------------------------------------------

ROTATION_FAILURE_STATUSES = frozenset(
    {
        "HALTED",
        "HEALTH_CHECK_FAILED",
        "CANARY_VERIFY_FAILED",
        "SOAK_FAILED",
        "ROLLED_BACK",
    }
)

ROTATION_INFLIGHT_STATUSES = frozenset(
    {
        "HEALTH_CHECK",
        "PREFLIGHT",
        "ACQUIRED",
        "WAITING_FOR_PASTE",
        "STAGED_CANARY",
        "DEPLOYED_CANARY",
        "IN_CANARY_VERIFY",
        "VERIFIED_CANARY",
        "STAGED_PROD",
        "DEPLOYED_PROD",
        "VERIFIED",
        "IN_SOAK",
        "SOAKED",
    }
)

ROTATION_TERMINAL_STATUSES = ROTATION_FAILURE_STATUSES | frozenset(
    {
        "IN_GRACE",
        "MANUAL",
        "ROLLED_BACK",
        "ROTATED",
    }
)

# Stacks the v0.2 skill knows how to scaffold. Anything else → "Stack not
# supported yet" message in the dashboard, no shell-out attempted.
SUPPORTED_STACKS = ("vercel", "python-cli")
GLOBAL_ROTATION_CATALOG_PATH = (
    Path.home() / ".claude" / "skills" / "secrets-rotation" / "catalog.json"
)
LOCAL_ROTATION_CATALOG_PATH = Path("src/lib/rotation/catalog.local.json")


def state_file_path(repo_path: Path | str) -> Path:
    return Path(repo_path).expanduser() / "data" / "rotation-state.json"


def history_file_path(repo_path: Path | str) -> Path:
    return Path(repo_path).expanduser() / "data" / "rotation-log.jsonl"


def receipts_dir(repo_path: Path | str) -> Path:
    return Path(repo_path).expanduser() / "data" / "rotation-receipts"


# ---------------------------------------------------------------------------
# Status normalisation
# ---------------------------------------------------------------------------


def _parse_iso(value: Any) -> _dt.datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _dt.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _add_days_iso(value: Any, days: Any) -> str | None:
    base = _parse_iso(value)
    if base is None:
        return None
    try:
        delta_days = int(days)
    except (TypeError, ValueError):
        return None
    return (base + _dt.timedelta(days=delta_days)).isoformat()


def _days_since(value: Any) -> int | None:
    base = _parse_iso(value)
    if base is None:
        return None
    now = _dt.datetime.now(_dt.timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=_dt.timezone.utc)
    return max((now - base).days, 0)


def _normalized_status_entry(
    secret_name: str,
    *,
    secret_class: str | None = None,
    rotation_warning: str | None = None,
    soak_window_minutes: int | None = None,
    console_url: str | None = None,
    status: str = "NEVER",
    last_rotated_at: Any = None,
    cadence_days: Any = None,
    rotation_id: str | None = None,
    in_grace_until: str | None = None,
    manually_marked: bool = False,
    override_kind: str | None = None,
    emergency_mode: bool = False,
) -> dict[str, Any]:
    next_due = (
        _add_days_iso(last_rotated_at, cadence_days)
        if last_rotated_at and cadence_days
        else None
    )
    days_since = _days_since(last_rotated_at)
    overdue = (
        days_since is not None
        and isinstance(cadence_days, int)
        and days_since > cadence_days
    )
    needs_attention = (
        status in ROTATION_FAILURE_STATUSES
        or status in {"NEVER", "unknown"}
        or overdue
    )
    return {
        "secret": secret_name,
        "class": secret_class,
        "rotation_warning": rotation_warning,
        "soak_window_minutes": soak_window_minutes,
        "console_url": console_url,
        "status": status,
        "last_rotated_at": str(last_rotated_at) if last_rotated_at else None,
        "days_since_rotation": days_since,
        "cadence_days": int(cadence_days) if isinstance(cadence_days, int) else None,
        "next_rotation_due": next_due,
        "rotation_id": rotation_id,
        "in_grace_until": in_grace_until,
        "needs_attention": bool(needs_attention),
        "manually_marked": bool(manually_marked),
        "override_kind": override_kind,
        "emergency_mode": bool(emergency_mode),
    }


def _latest_rotation_for(
    rotations: list[dict[str, Any]], secret_name: str
) -> dict[str, Any] | None:
    matches = [
        rec
        for rec in rotations
        if isinstance(rec, dict)
        and str(rec.get("secret_name") or "") == secret_name
    ]
    if not matches:
        return None
    matches.sort(key=lambda r: str(r.get("started_at") or ""), reverse=True)
    return matches[0]


@lru_cache(maxsize=128)
def _read_catalog_entries(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.is_file():
        return ()
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("rotation_catalog: failed to read %s: %s", path, exc)
        return ()
    entries = parsed.get("entries") if isinstance(parsed, dict) else None
    if not isinstance(entries, list):
        logger.warning("rotation_catalog: %s has no entries array", path)
        return ()
    return tuple(entry for entry in entries if isinstance(entry, dict))


def _catalog_entry_matches(entry: dict[str, Any], secret_name: str) -> bool:
    name = entry.get("name")
    if isinstance(name, str) and name == secret_name:
        return True
    pattern = entry.get("name_regex")
    if not isinstance(pattern, str) or not pattern.strip():
        return False
    try:
        return re.search(pattern, secret_name) is not None
    except re.error as exc:
        logger.warning("rotation_catalog: invalid name_regex %r: %s", pattern, exc)
        return False


def _matching_catalog_entry(
    entries: tuple[dict[str, Any], ...],
    secret_name: str,
) -> dict[str, Any] | None:
    for entry in entries:
        name = entry.get("name")
        if isinstance(name, str) and name == secret_name:
            return entry
    for entry in entries:
        name = entry.get("name")
        if isinstance(name, str):
            continue
        if _catalog_entry_matches(entry, secret_name):
            return entry
    return None


def _rotation_catalog_entry(repo_path: Path | str, secret_name: str) -> dict[str, Any]:
    root = Path(repo_path).expanduser()
    local_path = root / LOCAL_ROTATION_CATALOG_PATH
    merged: dict[str, Any] = {}
    for entries in (
        _read_catalog_entries(GLOBAL_ROTATION_CATALOG_PATH),
        _read_catalog_entries(local_path),
    ):
        entry = _matching_catalog_entry(entries, secret_name)
        if entry:
            merged.update(entry)
    return merged


def _catalog_rotation_warning(entry: dict[str, Any]) -> str | None:
    warning = entry.get("rotation_warning")
    if isinstance(warning, str) and warning.strip():
        return warning.strip()
    return None


def _catalog_soak_window_minutes(entry: dict[str, Any]) -> int | None:
    value = entry.get("soak_window_minutes")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _catalog_console_url(entry: dict[str, Any]) -> str | None:
    url = entry.get("console_url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def read_rotation_status(repo_path: Path | str) -> list[dict[str, Any]]:
    """Return per-secret rotation status for the repo at ``repo_path``.

    Empty list when the state file is absent — i.e. rotation isn't scaffolded
    yet. Corrupt files yield "unknown" rows so callers can surface that the
    operator's state file is broken instead of pretending everything is fine.
    Known secrets are enriched with catalog warning/default-soak metadata when
    available; per-repo catalog.local.json entries take precedence over the
    global secrets-rotation catalog.
    """
    state_path = state_file_path(repo_path)
    if not state_path.exists():
        return []
    try:
        raw = state_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("rotation_status: failed to read %s: %s", state_path, exc)
        return [_normalized_status_entry("(unreadable)", status="unknown")]
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        logger.warning(
            "rotation_status: state file %s is not valid JSON: %s", state_path, exc
        )
        return [_normalized_status_entry("(corrupt)", status="unknown")]
    if not isinstance(parsed, dict):
        logger.warning(
            "rotation_status: state file %s has unexpected shape", state_path
        )
        return [_normalized_status_entry("(corrupt)", status="unknown")]

    secrets_raw = parsed.get("secrets")
    rotations_raw = parsed.get("rotations") or []
    rotations: list[dict[str, Any]] = [
        rec for rec in rotations_raw if isinstance(rec, dict)
    ]
    rows: list[dict[str, Any]] = []
    unknown_count = 0
    if not isinstance(secrets_raw, list):
        logger.warning(
            "rotation_status: state file %s missing secrets array", state_path
        )
        secrets_raw = []
        unknown_count += 1
    for entry in secrets_raw:
        if not isinstance(entry, dict):
            unknown_count += 1
            continue
        name = entry.get("name")
        if not name:
            unknown_count += 1
            continue
        name_str = str(name)
        catalog_entry = _rotation_catalog_entry(repo_path, name_str)
        latest = _latest_rotation_for(rotations, name_str) or {}
        status = str(latest.get("status")) if latest.get("status") else "NEVER"
        last_rotated_at = (
            latest.get("completed_at")
            or latest.get("last_updated_at")
            or entry.get("last_rotated_at")
        )
        rows.append(
            _normalized_status_entry(
                name_str,
                secret_class=entry.get("class"),
                rotation_warning=_catalog_rotation_warning(catalog_entry),
                soak_window_minutes=_catalog_soak_window_minutes(catalog_entry),
                console_url=_catalog_console_url(catalog_entry),
                status=status,
                last_rotated_at=last_rotated_at,
                cadence_days=entry.get("cadence_days"),
                rotation_id=latest.get("rotation_id"),
                in_grace_until=latest.get("revoke_scheduled_at"),
                manually_marked=bool(latest.get("manually_marked")),
                override_kind=latest.get("override_kind"),
                emergency_mode=bool(latest.get("emergency_mode")),
            )
        )
    for _ in range(unknown_count):
        rows.append(_normalized_status_entry("(corrupt)", status="unknown"))
    return rows


def read_rotation_history(
    repo_path: Path | str, limit: int = 20
) -> list[dict[str, Any]]:
    """Return rotation log events for the repo, most-recent first."""
    try:
        bounded_limit = int(limit)
    except (TypeError, ValueError):
        bounded_limit = 20
    bounded_limit = max(1, min(bounded_limit, 100))
    log_path = history_file_path(repo_path)
    if not log_path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with log_path.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except (TypeError, ValueError) as exc:
                    logger.warning(
                        "rotation_history: malformed line %d in %s: %s",
                        line_no, log_path, exc,
                    )
                    continue
                if not isinstance(entry, dict):
                    continue
                events.append(
                    {
                        "timestamp": entry.get("at"),
                        "secret": str(entry.get("secret_name") or ""),
                        "rotation_id": entry.get("rotation_id"),
                        "step": entry.get("step"),
                        "outcome": entry.get("outcome"),
                        "note": entry.get("note"),
                        "duration_ms": entry.get("duration_ms"),
                        "override_kind": entry.get("override_kind"),
                    }
                )
    except OSError as exc:
        logger.warning("rotation_history: failed to read %s: %s", log_path, exc)
        return []
    events.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=True)
    return events[:bounded_limit]


# ---------------------------------------------------------------------------
# State/history consistency
# ---------------------------------------------------------------------------


def _read_state_rotations(repo_path: Path | str) -> list[dict[str, Any]]:
    state_path = state_file_path(repo_path)
    if not state_path.exists():
        return []
    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return []
    if not isinstance(parsed, dict):
        return []
    rotations_raw = parsed.get("rotations") or []
    return [rec for rec in rotations_raw if isinstance(rec, dict)]


def _read_history_events(repo_path: Path | str) -> list[dict[str, Any]]:
    log_path = history_file_path(repo_path)
    if not log_path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with log_path.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except (TypeError, ValueError) as exc:
                    logger.warning(
                        "rotation_consistency: malformed line %d in %s: %s",
                        line_no,
                        log_path,
                        exc,
                    )
                    continue
                if isinstance(parsed, dict):
                    events.append(parsed)
    except OSError as exc:
        logger.warning("rotation_consistency: failed to read %s: %s", log_path, exc)
        return []
    events.sort(key=lambda e: str(e.get("at") or ""), reverse=True)
    return events


def _terminal_status_from_event(event: dict[str, Any]) -> set[str]:
    step = str(event.get("step") or "").upper()
    outcome = str(event.get("outcome") or "").lower()
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    if step == "OPERATOR_OVERRIDE" and outcome == "succeeded":
        resulting = str(details.get("resulting_status") or "")
        return {resulting} if resulting in ROTATION_TERMINAL_STATUSES else set()
    if outcome == "halted":
        if step == "HEALTH_CHECK":
            return {"HEALTH_CHECK_FAILED"}
        if step == "VERIFY_CANARY":
            return {"CANARY_VERIFY_FAILED"}
        if step == "SOAK":
            return {"SOAK_FAILED"}
        return {"HALTED"}
    if step == "GRACE" and outcome in {"started", "succeeded"}:
        return {"IN_GRACE"}
    if step == "REVOKE" and outcome == "succeeded":
        return {"ROTATED"}
    if step == "ROLLBACK" and outcome == "succeeded":
        return {"ROLLED_BACK"}
    return set()


def rotation_consistency_check(repo_path: Path | str) -> dict[str, Any]:
    """Compare terminal state rows with the append-only rotation trail.

    The state file is the dashboard/MCP source of truth. The JSONL trail is the
    trust trail. A warning here means the operator should inspect the rotation
    receipt/history before treating the status row as authoritative.
    """
    rows = read_rotation_status(repo_path)
    events = _read_history_events(repo_path)
    rotations = _read_state_rotations(repo_path)
    warnings: list[dict[str, Any]] = []

    state_rotation_ids = {
        str(rec.get("rotation_id"))
        for rec in rotations
        if rec.get("rotation_id")
    }
    state_secret_names = {
        str(row.get("secret"))
        for row in rows
        if row.get("secret") and str(row.get("secret")) not in {"(corrupt)", "(unreadable)"}
    }
    event_rotation_ids = {
        str(event.get("rotation_id"))
        for event in events
        if event.get("rotation_id")
    }

    warned_history_records: set[tuple[str, str]] = set()
    for event in events:
        step = str(event.get("step") or "")
        rotation_id = str(event.get("rotation_id") or "")
        secret = str(event.get("secret_name") or "")
        if step == "DASHBOARD_TRIGGER" and not rotation_id:
            continue
        if rotation_id and rotation_id not in state_rotation_ids:
            key = (rotation_id, secret)
            if key not in warned_history_records:
                warnings.append(
                    {
                        "kind": "history_missing_state_record",
                        "secret": secret or None,
                        "rotation_id": rotation_id,
                        "detail": "Rotation history has events with no matching state record.",
                    }
                )
                warned_history_records.add(key)
        elif not rotation_id and secret and secret not in state_secret_names:
            key = ("", secret)
            if key not in warned_history_records:
                warnings.append(
                    {
                        "kind": "history_unknown_secret",
                        "secret": secret,
                        "rotation_id": None,
                        "detail": "Rotation history references a secret missing from state.",
                    }
                )
                warned_history_records.add(key)

    for rec in rotations:
        rotation_id = str(rec.get("rotation_id") or "")
        if rotation_id and rotation_id not in event_rotation_ids:
            warnings.append(
                {
                    "kind": "state_missing_history",
                    "secret": rec.get("secret_name"),
                    "rotation_id": rotation_id,
                    "state_status": rec.get("status"),
                    "detail": "Rotation state has a record with no matching history events.",
                }
            )

    latest_row_by_secret = {
        str(row.get("secret")): row
        for row in rows
        if row.get("secret") and str(row.get("status") or "") in ROTATION_TERMINAL_STATUSES
    }
    for secret, row in latest_row_by_secret.items():
        state_status = str(row.get("status") or "")
        matching = [
            event
            for event in events
            if str(event.get("secret_name") or "") == secret
            and _terminal_status_from_event(event)
        ]
        if not matching:
            continue
        latest_event = matching[0]
        history_statuses = _terminal_status_from_event(latest_event)
        if state_status not in history_statuses:
            warnings.append(
                {
                    "kind": "status_mismatch",
                    "secret": secret,
                    "rotation_id": latest_event.get("rotation_id"),
                    "state_status": state_status,
                    "history_status": sorted(history_statuses),
                    "history_step": latest_event.get("step"),
                    "detail": "Latest terminal state does not match the terminal history event.",
                }
            )

    return {"ok": not warnings, "warnings": warnings}


# ---------------------------------------------------------------------------
# Receipt files
# ---------------------------------------------------------------------------


def list_receipts(repo_path: Path | str) -> list[dict[str, Any]]:
    """Return metadata about every verification receipt in the repo.

    Each entry: ``{"filename": "<name>.md", "modified_at": "<iso>"}``. Filename
    only (no absolute path) so callers never have to redact before serving.
    """
    directory = receipts_dir(repo_path)
    if not directory.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for entry in directory.iterdir():
        if not entry.is_file() or entry.suffix.lower() != ".md":
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        items.append(
            {
                "filename": entry.name,
                "modified_at": _dt.datetime.fromtimestamp(
                    stat.st_mtime, _dt.timezone.utc
                ).isoformat(),
            }
        )
    items.sort(key=lambda item: str(item.get("modified_at") or ""), reverse=True)
    return items


# Safe filename: <secret>-<iso-ish-timestamp>.md. The skill writes names like
# "AUTH_SECRET-2026-05-20T140000Z.md". We allow letters, digits, ., _, and -.
# No slashes, no relative segments — the regex is what blocks path traversal.
_SAFE_RECEIPT_NAME_RE = __import__("re").compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.md$")


def read_receipt(repo_path: Path | str, filename: str) -> str | None:
    """Return the markdown contents of a single verification receipt.

    Returns None when the filename fails validation, escapes the receipts
    directory, or simply doesn't exist. Callers should map None → 404.
    """
    if not filename or not _SAFE_RECEIPT_NAME_RE.match(filename):
        return None
    directory = receipts_dir(repo_path)
    if not directory.is_dir():
        return None
    try:
        candidate = (directory / filename).resolve()
        directory_resolved = directory.resolve()
    except OSError:
        return None
    try:
        candidate.relative_to(directory_resolved)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    try:
        return candidate.read_text(encoding="utf-8")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Stack detection (drives "Set up rotation" CTA gating)
# ---------------------------------------------------------------------------


def detect_stack(repo_path: Path | str) -> str | None:
    """Return the rotation skill's stack label for the repo, or None.

    Recognised labels: ``"vercel"`` (Next.js / Vercel-deployable Node app) and
    ``"python-cli"`` (Python project with a CLI entry). Returns None when the
    stack isn't one the skill can scaffold today — the dashboard renders a
    "stack not supported yet" message instead of the scaffolding CTA.
    """
    root = Path(repo_path).expanduser()
    if not root.is_dir():
        return None

    package_json = root / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        deps = {}
        if isinstance(data, dict):
            for field in ("dependencies", "devDependencies"):
                value = data.get(field)
                if isinstance(value, dict):
                    deps.update(value)
        if "next" in deps or (root / "vercel.json").is_file():
            return "vercel"

    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file():
        try:
            content = (root / "pyproject.toml").read_text(encoding="utf-8")
        except OSError:
            content = ""
        if (
            "[project.scripts]" in content
            or "[tool.poetry.scripts]" in content
            or "console_scripts" in content
            or (root / "setup.py").is_file()
        ):
            return "python-cli"
    return None


def detect_rotation_state(repo_path: Path | str) -> dict[str, Any]:
    """Return a compact rotation-state signal for one repo.

    Shape:

    ```
    {
      "scaffolded": bool,             # data/rotation-state.json exists
      "stack": "vercel" | "python-cli" | None,
      "stack_supported": bool,        # stack is in SUPPORTED_STACKS
      "secret_count": int,            # 0 when not scaffolded
      "needs_attention_count": int,   # 0 when not scaffolded
      "in_grace_count": int,          # 0 when not scaffolded
      "last_event_at": str | None,    # from rotation-log.jsonl, ISO timestamp
    }
    ```

    Cheap to compute (one stat + at most two file reads) so it's safe to call
    on every dashboard refresh and every scan.
    """
    root = Path(repo_path).expanduser()
    scaffolded = state_file_path(root).exists()
    stack = detect_stack(root) if root.is_dir() else None
    signal: dict[str, Any] = {
        "scaffolded": scaffolded,
        "stack": stack,
        "stack_supported": stack in SUPPORTED_STACKS if stack else False,
        "secret_count": 0,
        "needs_attention_count": 0,
        "in_grace_count": 0,
        "last_event_at": None,
    }
    if not scaffolded:
        return signal
    rows = read_rotation_status(root)
    signal["secret_count"] = len(rows)
    signal["needs_attention_count"] = sum(1 for row in rows if row.get("needs_attention"))
    signal["in_grace_count"] = sum(
        1 for row in rows if str(row.get("status") or "") == "IN_GRACE"
    )
    history = read_rotation_history(root, limit=1)
    if history:
        signal["last_event_at"] = history[0].get("timestamp")
    return signal


__all__ = (
    "ROTATION_FAILURE_STATUSES",
    "ROTATION_INFLIGHT_STATUSES",
    "ROTATION_TERMINAL_STATUSES",
    "SUPPORTED_STACKS",
    "state_file_path",
    "history_file_path",
    "receipts_dir",
    "read_rotation_status",
    "read_rotation_history",
    "rotation_consistency_check",
    "list_receipts",
    "read_receipt",
    "detect_stack",
    "detect_rotation_state",
)
