"""Smoke + per-tool tests for the read-only MCP adapter.

These tests exercise the underlying tool functions directly (cheap, sync) and
also walk the FastMCP server's protocol surface for tool listing — together
covering shape correctness, filter behavior, error responses, and the no-
absolute-paths invariant.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
from pathlib import Path

import pytest

# The MCP SDK is an optional dependency (uv sync --extra mcp). If it isn't
# installed (developer running pytest without the extra), skip this module
# cleanly rather than crashing the entire test collection.
pytest.importorskip("mcp")

from security_observatory.cases import build_security_cases
from security_observatory.mcp_server import (
    DEVSEC_MCP_INSTRUCTIONS,
    RepoNotFoundError,
    SUPPORTED_CASE_STATUSES,
    SUPPORTED_SEVERITIES,
    _cases,
    _dependency_trust,
    _findings,
    _honey_keys,
    _latest_scan,
    _list_repos,
    _recovery_playbook,
    _scan_history,
    create_server,
    observatory_home,
)
from security_observatory.model import Finding
from security_observatory.storage import ObservatoryDB


REPO_NAME = "demo-repo"
REPO_PATH = "/Users/dummyuser/Dev/Projects/demo-repo"
SCAN_ID = "demo-20260101T000000Z"
STARTED_AT = "2026-01-01T00:00:00+00:00"


def _make_db(tmp_path: Path) -> ObservatoryDB:
    return ObservatoryDB(tmp_path / "db" / "observatory.sqlite")


def _seed_scan(
    db: ObservatoryDB,
    tmp_path: Path,
    *,
    scan_id: str = SCAN_ID,
    repo_name: str = REPO_NAME,
    repo_path: str = REPO_PATH,
    started_at: str = STARTED_AT,
    finished_at: str = "2026-01-01T00:01:00+00:00",
    health_score: int = 42,
    status: str = "warn",
) -> None:
    findings = [
        Finding(
            repo=repo_name,
            scanner="gitleaks",
            severity="critical",
            category="secrets",
            title="Hardcoded AWS access key",
            file=f"{repo_path}/config/secrets.py",
            line=42,
            remediation="Rotate the leaked credential at the provider before changing code.",
            evidence_summary="AWS access key matches the AKIA prefix in config/secrets.py.",
            fingerprint="finding-secrets-1",
        ),
        Finding(
            repo=repo_name,
            scanner="osv-scanner",
            severity="high",
            category="dependencies",
            title="CVE-2026-1000 in lodash",
            file=f"{repo_path}/package-lock.json",
            remediation="Upgrade lodash to >= 4.17.22.",
            vulnerability_id="CVE-2026-1000",
            package_name="lodash",
            package_version="4.17.20",
            package_ecosystem="npm",
            package_url="pkg:npm/lodash@4.17.20",
            fixed_version="4.17.22",
            fingerprint="finding-deps-1",
        ),
        Finding(
            repo=repo_name,
            scanner="semgrep",
            severity="medium",
            category="code-security",
            title="Unsafe deserialization",
            file=f"{repo_path}/app/api/decode.py",
            line=17,
            remediation="Replace pickle.loads with a safe serializer.",
            fingerprint="finding-code-1",
        ),
    ]
    cases = build_security_cases(
        findings,
        [
            {"scanner": "gitleaks", "available": True, "findings": 1},
            {"scanner": "osv-scanner", "available": True, "findings": 1},
            {"scanner": "semgrep", "available": True, "findings": 1},
        ],
        {"repo": repo_name},
    )
    db.save_scan(
        scan_id=scan_id,
        repo_name=repo_name,
        repo_path=repo_path,
        started_at=started_at,
        finished_at=finished_at,
        profile="default",
        health_score=health_score,
        status=status,
        scanner_statuses=[
            {"scanner": "gitleaks", "available": True, "findings": 1},
            {"scanner": "osv-scanner", "available": True, "findings": 1},
            {"scanner": "semgrep", "available": True, "findings": 1},
        ],
        findings=findings,
        report_path=str(tmp_path / "reports" / f"{scan_id}.json"),
        cases=cases,
        dependency_trust_enrichments=[
            {
                "component_fingerprint": "lodash-fp",
                "component_package_key": "npm:lodash",
                "package_name": "lodash",
                "package_version": "4.17.20",
                "package_ecosystem": "npm",
                "package_url": "pkg:npm/lodash@4.17.20",
                "source_repo": "lodash/lodash",
                "source_repo_url": "https://github.com/lodash/lodash",
                "source_repo_confidence": "high",
                "source_repo_reason": "purl resolves to github",
                "scorecard_score": 7.8,
                "scorecard_status": "ok",
                "criticality_score": 0.91,
                "criticality_status": "ok",
                "checked_at": "2026-01-01T00:00:30+00:00",
                "freshness": "fresh",
                "status": "ok",
                "cache_key": "lodash@4.17.20",
                "error": None,
            }
        ],
    )
    return cases


# ---------------------------------------------------------------------------
# Tool listing — protocol surface
# ---------------------------------------------------------------------------


def test_server_lists_expected_tools(tmp_path):
    server = create_server(home=tmp_path)
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "list_repos",
        "honey_keys",
        "latest_scan",
        "scan_history",
        "findings",
        "cases",
        "recovery_playbook",
        "dependency_trust",
    }
    for tool in tools:
        assert tool.description, f"tool {tool.name!r} has no description"
        assert isinstance(tool.inputSchema, dict)
        assert tool.inputSchema.get("type") == "object"


def test_server_instructions_reference_doctrine(tmp_path):
    server = create_server(home=tmp_path)
    assert server.instructions == DEVSEC_MCP_INSTRUCTIONS
    assert "Action: <fix_now|verify|watch|info> · Severity" in server.instructions
    assert "docs/agent-voice.md" in server.instructions
    assert "docs/agent-safety.md" in server.instructions
    assert "read-only and stdio-only" in server.instructions


def test_create_server_uses_env_home_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(tmp_path))
    assert observatory_home() == tmp_path
    server = create_server()
    assert server is not None


# ---------------------------------------------------------------------------
# list_repos
# ---------------------------------------------------------------------------


def test_list_repos_empty_db(tmp_path):
    # No DB file on disk — must not raise, must return [].
    server = create_server(home=tmp_path)
    result = asyncio.run(server.call_tool("list_repos", {}))
    structured = _structured_content(result)
    assert structured == {"result": []}
    # Also exercise the underlying function with no DB.
    assert _list_repos(None) == []


def test_list_repos_with_seeded_data(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
        result = _list_repos(db)
    finally:
        db.close()
    assert len(result) == 1
    entry = result[0]
    assert entry["name"] == REPO_NAME
    assert entry["scan_count"] == 1
    assert entry["last_scan_at"] == STARTED_AT


# ---------------------------------------------------------------------------
# honey_keys
# ---------------------------------------------------------------------------


def test_honey_keys_empty_returns_list(tmp_path):
    assert _honey_keys(None) == []
    db = _make_db(tmp_path)
    try:
        assert _honey_keys(db) == []
    finally:
        db.close()


def test_honey_keys_returns_normalized_shape(tmp_path):
    db = _make_db(tmp_path)
    try:
        db.create_honey_key(
            key_id="hny_demo_1",
            project_id=REPO_NAME,
            repo_id=REPO_NAME,
            name="Deploy token",
            token_hash="hash-demo-1",
            placement_path=".env.backup",
        )
        result = _honey_keys(db)
    finally:
        db.close()
    assert len(result) == 1
    assert result[0] == {
        "id": "hny_demo_1",
        "project_id": REPO_NAME,
        "status": "active",
        "placed_at": result[0]["placed_at"],
        "placement_repo": REPO_NAME,
        "trigger_count": 0,
        "last_triggered_at": None,
        "severity_if_triggered": None,
    }
    json.dumps(result)


def test_honey_keys_includes_trigger_event(tmp_path):
    db = _make_db(tmp_path)
    try:
        key = db.create_honey_key(
            key_id="hny_demo_2",
            project_id=REPO_NAME,
            repo_id=REPO_NAME,
            name="CI token",
            token_hash="hash-demo-2",
            placement_path=".github/workflows/build.yml",
        )
        db.create_honey_key(
            key_id="hny_demo_3",
            project_id=REPO_NAME,
            repo_id=REPO_NAME,
            name="Older token",
            token_hash="hash-demo-3",
            placement_path=".env.example",
        )
        db.record_honey_key_trigger(
            honey_key={**key, "token_hash": "hash-demo-2"},
            ip_address="127.0.0.1",
            user_agent="pytest",
            method="POST",
            path="/api/honey/trigger",
            headers={"User-Agent": "pytest"},
            body_summary=None,
            confidence=0.98,
            source_type="api_call",
        )
        result = _honey_keys(db)
    finally:
        db.close()
    assert [item["id"] for item in result][:2] == ["hny_demo_2", "hny_demo_3"]
    triggered = result[0]
    assert triggered["status"] == "triggered"
    assert triggered["trigger_count"] == 1
    assert triggered["last_triggered_at"]
    assert triggered["severity_if_triggered"] == "critical"


# ---------------------------------------------------------------------------
# latest_scan
# ---------------------------------------------------------------------------


def test_latest_scan_returns_summary(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
        summary = _latest_scan(db, REPO_NAME)
    finally:
        db.close()
    assert summary["scan_id"] == SCAN_ID
    assert summary["started_at"] == STARTED_AT
    assert summary["scanner_count"] == 3
    assert summary["finding_count"] == 3
    assert summary["health_score"] == 42
    assert summary["status"] == "warn"


def test_latest_scan_repo_not_found_raises_clear_error(tmp_path):
    db = _make_db(tmp_path)
    try:
        with pytest.raises(RepoNotFoundError) as exc:
            _latest_scan(db, "nonexistent-repo")
    finally:
        db.close()
    assert "nonexistent-repo" in str(exc.value)


# ---------------------------------------------------------------------------
# scan_history
# ---------------------------------------------------------------------------


def test_scan_history_empty_raises(tmp_path):
    db = _make_db(tmp_path)
    try:
        with pytest.raises(RepoNotFoundError) as exc:
            _scan_history(db, REPO_NAME)
    finally:
        db.close()
    assert REPO_NAME in str(exc.value)


def test_scan_history_returns_recent_first(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(
            db,
            tmp_path,
            scan_id="demo-20260101T000000Z",
            started_at="2026-01-01T00:00:00+00:00",
            health_score=42,
            status="warn",
        )
        _seed_scan(
            db,
            tmp_path,
            scan_id="demo-20260102T000000Z",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            health_score=88,
            status="ok",
        )
        result = _scan_history(db, REPO_NAME, limit=10)
    finally:
        db.close()
    assert [item["scan_id"] for item in result] == [
        "demo-20260102T000000Z",
        "demo-20260101T000000Z",
    ]
    assert result[0]["health_score"] == 88
    assert result[0]["finding_count"] == 3
    assert result[0]["status"] == "ok"


def test_scan_history_limit_caps(tmp_path):
    db = _make_db(tmp_path)
    try:
        for index in range(55):
            _seed_scan(
                db,
                tmp_path,
                scan_id=f"demo-20260101T00{index:02d}00Z",
                started_at=f"2026-01-01T00:{index:02d}:00+00:00",
            )
        result = _scan_history(db, REPO_NAME, limit=999)
    finally:
        db.close()
    assert len(result) == 50


# ---------------------------------------------------------------------------
# findings
# ---------------------------------------------------------------------------


def test_findings_returns_normalized_shape(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
        result = _findings(db, REPO_NAME, severity=None, limit=50)
    finally:
        db.close()
    assert len(result) == 3
    # The shape must be JSON-serializable end-to-end.
    json.dumps(result)
    keys = {"id", "title", "severity", "category", "scanner", "path", "line", "evidence_excerpt"}
    for item in result:
        assert set(item.keys()) == keys
        assert isinstance(item["id"], int)
        assert item["severity"] in SUPPORTED_SEVERITIES


def test_findings_severity_filter_works(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
        critical = _findings(db, REPO_NAME, severity="critical", limit=50)
        medium = _findings(db, REPO_NAME, severity="medium", limit=50)
    finally:
        db.close()
    assert len(critical) == 1
    assert critical[0]["category"] == "secrets"
    assert len(medium) == 1
    assert medium[0]["category"] == "code-security"


def test_findings_unknown_severity_raises_value_error(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
        with pytest.raises(ValueError) as exc:
            _findings(db, REPO_NAME, severity="catastrophic", limit=50)
    finally:
        db.close()
    assert "catastrophic" in str(exc.value)


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------


def test_cases_returns_action_level_shape(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
        result = _cases(db, REPO_NAME, status=None)
    finally:
        db.close()
    assert result, "expected at least one open case from seeded scan"
    expected_keys = {
        "id",
        "title",
        "plain_english_risk",
        "severity",
        "category",
        "action_level",
        "confidence",
        "affected_files",
        "suggested_steps",
        "agent_handoff_prompt",
        "status",
    }
    for case in result:
        assert set(case.keys()) == expected_keys
        assert case["action_level"] in {"fix_now", "verify", "watch", "info"}
        assert case["agent_handoff_prompt"], "every case should carry an agent prompt"
        assert isinstance(case["suggested_steps"], list)
        assert case["status"] == "open"


def test_cases_status_filter_defaults_to_open(tmp_path):
    db = _make_db(tmp_path)
    try:
        seeded_cases = _seed_scan(db, tmp_path)
        # Mark one case as accepted_risk so we have a non-open case in the DB.
        target = next(c for c in seeded_cases if c.category == "secrets")
        db.set_case_decision(
            case_id=target.case_id,
            repo_name=REPO_NAME,
            status="accepted_risk",
            note="Test fixture: synthetic credential.",
        )
        default_result = _cases(db, REPO_NAME, status=None)
        explicit_open = _cases(db, REPO_NAME, status="open")
        accepted = _cases(db, REPO_NAME, status="accepted_risk")
    finally:
        db.close()
    assert {c["status"] for c in default_result} == {"open"}
    assert [c["id"] for c in default_result] == [c["id"] for c in explicit_open]
    assert len(accepted) == 1
    assert accepted[0]["status"] == "accepted_risk"
    assert accepted[0]["category"] == "secrets"


def test_cases_unknown_status_raises_value_error(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
        with pytest.raises(ValueError) as exc:
            _cases(db, REPO_NAME, status="parked")
    finally:
        db.close()
    assert "parked" in str(exc.value)
    assert all(status in str(exc.value) for status in SUPPORTED_CASE_STATUSES)


def test_cases_repo_not_found_raises_repo_error(tmp_path):
    db = _make_db(tmp_path)
    try:
        with pytest.raises(RepoNotFoundError):
            _cases(db, "ghost-repo", status=None)
    finally:
        db.close()


def test_cases_accepts_explicit_scan_id(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(
            db,
            tmp_path,
            scan_id="demo-old",
            started_at="2026-01-01T00:00:00+00:00",
        )
        _seed_scan(
            db,
            tmp_path,
            scan_id="demo-new",
            started_at="2026-01-02T00:00:00+00:00",
            health_score=99,
        )
        result = _cases(db, REPO_NAME, status=None, scan_id="demo-old")
    finally:
        db.close()
    assert result
    assert all(case["status"] == "open" for case in result)


def test_cases_rejects_scan_id_from_other_repo(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
        _seed_scan(
            db,
            tmp_path,
            scan_id="other-repo-scan",
            repo_name="other-repo",
            repo_path="/Users/dummyuser/Dev/Projects/other-repo",
        )
        with pytest.raises(ValueError) as exc:
            _cases(db, REPO_NAME, status=None, scan_id="other-repo-scan")
    finally:
        db.close()
    assert "other-repo-scan" in str(exc.value)
    assert REPO_NAME in str(exc.value)


# ---------------------------------------------------------------------------
# recovery_playbook
# ---------------------------------------------------------------------------


def test_recovery_playbook_returns_template(tmp_path):
    result = _recovery_playbook("secrets")
    assert result["category"] == "secrets"
    assert result["title"] == "Rotate leaked secrets and scrub history"
    assert result["estimated_minutes"] > 0
    assert result["steps"], "playbook must have at least one step"
    assert "{files}" not in " ".join(result["steps"]), "placeholder must be filled in"
    assert result["agent_prompt"]


def test_recovery_playbook_unknown_category_raises(tmp_path):
    with pytest.raises(ValueError) as exc:
        _recovery_playbook("not-a-real-category")
    assert "not-a-real-category" in str(exc.value)


# ---------------------------------------------------------------------------
# dependency_trust
# ---------------------------------------------------------------------------


def test_dependency_trust_returns_shape(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
        result = _dependency_trust(db, REPO_NAME)
    finally:
        db.close()
    assert len(result) == 1
    entry = result[0]
    assert entry["package"] == "lodash"
    assert entry["version"] == "4.17.20"
    assert entry["trust_score"] == 7.8
    assert "https://github.com/lodash/lodash" in entry["sources"]
    assert entry["last_updated"] == "2026-01-01T00:00:30+00:00"


def test_dependency_trust_repo_not_found_raises(tmp_path):
    db = _make_db(tmp_path)
    try:
        with pytest.raises(RepoNotFoundError):
            _dependency_trust(db, "ghost-repo")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Path-leak invariant — the security-critical assertion
# ---------------------------------------------------------------------------


def test_no_absolute_paths_in_output(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
        db.create_honey_key(
            key_id="hny_path_redaction",
            project_id=REPO_NAME,
            repo_id=REPO_PATH,
            name="Path redaction key",
            token_hash="hash-path-redaction",
            placement_path=".env",
        )
        finding_rows = _findings(db, REPO_NAME, severity=None, limit=50)
        case_rows = _cases(db, REPO_NAME, status="open")
        honey_rows = _honey_keys(db)
    finally:
        db.close()

    forbidden_prefixes = ("/Users/", "/home/", "/root/")

    def _scan(value):
        if value is None:
            return
        text = str(value)
        for prefix in forbidden_prefixes:
            assert not text.startswith(prefix), (
                f"output leaked absolute path prefix {prefix!r}: {text!r}"
            )

    assert finding_rows, "fixture should produce findings"
    for finding in finding_rows:
        _scan(finding["path"])
        # Spot-check the seeded absolute path is now repo-relative.
        if finding["category"] == "secrets":
            assert finding["path"] == "config/secrets.py"

    assert case_rows, "fixture should produce cases"
    for case in case_rows:
        for file_path in case["affected_files"]:
            _scan(file_path)

    assert honey_rows, "fixture should produce honey keys"
    for key in honey_rows:
        _scan(key["placement_repo"])


# ---------------------------------------------------------------------------
# FastMCP call_tool surface — verifies error responses go through the protocol
# ---------------------------------------------------------------------------


def test_repo_not_found_returns_clear_error(tmp_path):
    from mcp.server.fastmcp.exceptions import ToolError

    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
    finally:
        db.close()
    server = create_server(home=tmp_path)
    # FastMCP converts tool exceptions into a ToolError (sent to the client as an
    # MCP error response, not a Python traceback). The agent sees a clear,
    # named-repo error rather than a sqlite stack trace.
    with pytest.raises(ToolError) as exc:
        asyncio.run(server.call_tool("latest_scan", {"repo": "ghost-repo"}))
    assert "ghost-repo" in str(exc.value)


def test_call_tool_findings_returns_results(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
    finally:
        db.close()
    server = create_server(home=tmp_path)
    result = asyncio.run(server.call_tool("findings", {"repo": REPO_NAME, "severity": "critical"}))
    structured = _structured_content(result)
    assert "result" in structured
    items = structured["result"]
    assert len(items) == 1
    assert items[0]["category"] == "secrets"
    assert items[0]["path"] == "config/secrets.py"


# ---------------------------------------------------------------------------
# helpers for the FastMCP call_tool result shape
# ---------------------------------------------------------------------------


def _structured_content(result) -> dict:
    """Pull the structured content out of FastMCP's call_tool return.

    FastMCP returns either a CallToolResult, or a (content, structured) tuple
    depending on the version. We accept both rather than pinning a version.
    """
    if isinstance(result, tuple) and len(result) == 2:
        _, structured = result
        return structured or {}
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except (TypeError, ValueError):
                continue
    return {}
