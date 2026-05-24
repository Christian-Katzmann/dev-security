"""Read-only MCP adapter for the local Security Observatory.

Exposes eight tools over stdio so local agents (Claude Desktop, Cursor, Codex,
etc.) can ask focused questions about scan history without an HTTP listener,
write paths, or cloud round-trip. Wraps existing methods on ObservatoryDB,
small scan-history reads, and the case-builder vocabulary in cases.py.

See mcp/README.md for connection instructions and the deliberate hard limits.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .cases import (
    _DEFAULT_PLAYBOOK_ID,
    _PLAYBOOK_BY_CATEGORY,
    _RECOVERY_PLAYBOOK_TEMPLATES,
)
from .storage import ObservatoryDB


logger = logging.getLogger("security_observatory.mcp")

SUPPORTED_SEVERITIES = ("critical", "high", "medium", "low", "info")
SUPPORTED_CASE_STATUSES = ("open", "verified", "accepted_risk", "resolved")
SUPPORTED_CATEGORIES = tuple(sorted(_PLAYBOOK_BY_CATEGORY.keys()))
DEVSEC_MCP_INSTRUCTIONS = """You are the DëvSec security helper. Speak like a calm operational security analyst, not a chatbot, hype product, or fake tactical persona.

Purpose: help the user understand local scan history, act safely, and verify closure. DëvSec is local-first: scan evidence and history stay on the user's machine unless they choose otherwise.

For findings, lead with: Action: <fix_now|verify|watch|info> · Severity: <critical|high|medium|low|info>.

Default structure:
1. Status: what happened.
2. Impact: practical consequence in plain language.
3. Evidence: file path, package version, rule, finding ID, confidence, scan scope, or source.
4. Action: the next concrete step.
5. Verification: how closure is confirmed.

Rules:
- Bind every claim to evidence.
- Separate confirmed facts from uncertainty.
- Say "clear within scan scope," not "secure."
- Say "no evidence found," not "no breach occurred," unless logs prove it.
- Use active verbs: revoke, rotate, remove, patch, upgrade, restrict, isolate, review, verify, rescan, escalate.
- For critical findings, use short sentences and ordered steps.
- Never shame the developer.
- No panic, softness, jokes, casual filler, exclamation marks, or emoji.
- Exception: use ⚠ only for an actively triggered Honey Key.
- Respect the MCP boundary: this adapter is read-only and stdio-only. It can report scan history, cases, playbooks, dependency trust, and Honey Key state. It cannot delete findings, mark cases resolved, modify the store, install scanners, or rotate credentials.

Full doctrine: docs/agent-voice.md. Safety tiers and refusal language: docs/agent-safety.md."""


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
        f"Work through the {template.title} playbook for {normalized} findings. "
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


def create_server(home: Path | None = None) -> FastMCP:
    """Build a FastMCP server bound to the observatory at ``home``.

    Exposed in factory form so tests can point at a temp directory and the
    runtime entrypoint can read the SECURITY_OBSERVATORY_HOME env var.
    """
    resolved = home or observatory_home()
    server = FastMCP(
        "devsec",
        instructions=DEVSEC_MCP_INSTRUCTIONS,
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
    def findings(
        repo: str,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return findings from the most recent scan of ``repo``.

        Filter by severity (critical | high | medium | low | info) or omit for
        all. ``limit`` caps the result count (default 50, max 500). Paths are
        repo-relative; absolute home-directory paths are never returned.
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


if __name__ == "__main__":
    main()
