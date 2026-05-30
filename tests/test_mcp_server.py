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

from security_observatory.case_followup import SCHEMA_VERSION
from security_observatory.cases import build_security_cases
from security_observatory.mcp_server import (
    DEVSEC_MCP_INSTRUCTIONS,
    DEVSEC_MCP_RW_INSTRUCTIONS,
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
    _rotation_history,
    _rotation_status,
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
        "raw_findings",
        "findings",
        "cases",
        "recovery_playbook",
        "dependency_trust",
        "rotation_status",
        "rotation_history",
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


def test_write_tools_are_opt_in_only(tmp_path):
    read_only_server = create_server(home=tmp_path)
    rw_server = create_server(home=tmp_path, allow_case_decisions=True)

    read_only_names = {tool.name for tool in asyncio.run(read_only_server.list_tools())}
    rw_names = {tool.name for tool in asyncio.run(rw_server.list_tools())}
    write_tools = {
        "trigger_scan",
        "case_followup_prompt",
        "preview_case_resolutions",
        "apply_case_resolutions",
    }

    assert read_only_names.isdisjoint(write_tools)
    assert write_tools.issubset(rw_names)
    assert rw_names == read_only_names | write_tools
    assert read_only_server.instructions == DEVSEC_MCP_INSTRUCTIONS
    assert rw_server.instructions == DEVSEC_MCP_RW_INSTRUCTIONS
    assert "case-decision write mode" in rw_server.instructions
    assert "read-only and stdio-only" not in rw_server.instructions


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
            # Critical secrets case: the severity gate requires explicit human
            # authorization to suppress (a dashboard click in production).
            human_authorized=True,
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
# rotation_status / rotation_history — read-only wrappers over the
# secrets-rotation skill's on-disk state files.
# ---------------------------------------------------------------------------


def _seed_repo_with_rotation_state(
    db: ObservatoryDB,
    tmp_path: Path,
    *,
    state: dict | str | None = None,
    log_lines: list[dict | str] | None = None,
) -> Path:
    """Seed a scan whose `repo_path` is a real on-disk directory and (optionally)
    write a rotation-state.json + rotation-log.jsonl into it.

    Returns the repo path so individual tests can read it back if needed.
    """
    repo_dir = tmp_path / "repos" / "rotation-demo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    _seed_scan(db, tmp_path, repo_path=str(repo_dir))
    data_dir = repo_dir / "data"
    if state is not None:
        data_dir.mkdir(parents=True, exist_ok=True)
        if isinstance(state, str):
            (data_dir / "rotation-state.json").write_text(state, encoding="utf-8")
        else:
            (data_dir / "rotation-state.json").write_text(
                json.dumps(state), encoding="utf-8"
            )
    if log_lines is not None:
        data_dir.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for entry in log_lines:
            if isinstance(entry, str):
                lines.append(entry)
            else:
                lines.append(json.dumps(entry))
        (data_dir / "rotation-log.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    return repo_dir


def test_rotation_status_no_rotation_setup_returns_empty_list(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_repo_with_rotation_state(db, tmp_path)  # no state file
        result = _rotation_status(db, REPO_NAME)
    finally:
        db.close()
    assert result == []


def test_rotation_status_returns_normalized_shape(tmp_path):
    db = _make_db(tmp_path)
    # Use a "recent" timestamp computed at test time so the cadence/overdue
    # assertion below stays stable as the calendar advances (we'd otherwise
    # drift into overdue once now > seeded_date + cadence_days).
    recent = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=2)
    recent_iso = recent.isoformat()
    state = {
        "version": 1,
        "repo_name": REPO_NAME,
        "scaffolded_at": "2026-04-01T00:00:00+00:00",
        "scaffolded_version": "v0.2",
        "secrets": [
            {
                "name": "AUTH_SECRET",
                "class": "A",
                "cadence_days": 30,
                "last_rotated_at": recent_iso,
            },
            {
                "name": "ANTHROPIC_API_KEY",
                "class": "B-API",
                "cadence_days": 90,
            },
        ],
        "rotations": [
            {
                "rotation_id": "rot-auth-001",
                "secret_name": "AUTH_SECRET",
                "secret_class": "A",
                "status": "ROTATED",
                "started_at": recent_iso,
                "last_updated_at": recent_iso,
                "completed_at": recent_iso,
                "log": [],
            },
            {
                "rotation_id": "rot-anth-001",
                "secret_name": "ANTHROPIC_API_KEY",
                "secret_class": "B-API",
                "status": "IN_GRACE",
                "started_at": recent_iso,
                "last_updated_at": recent_iso,
                "completed_at": recent_iso,
                "revoke_scheduled_at": "2099-01-01T00:00:00+00:00",
                "log": [],
            },
        ],
    }
    try:
        _seed_repo_with_rotation_state(db, tmp_path, state=state)
        result = _rotation_status(db, REPO_NAME)
    finally:
        db.close()
    by_name = {row["secret"]: row for row in result}
    assert set(by_name) == {"AUTH_SECRET", "ANTHROPIC_API_KEY"}
    expected_keys = {
        "secret",
        "class",
        "rotation_warning",
        "soak_window_minutes",
        "console_url",
        "status",
        "last_rotated_at",
        "days_since_rotation",
        "cadence_days",
        "next_rotation_due",
        "rotation_id",
        "in_grace_until",
        "needs_attention",
        "manually_marked",
        "override_kind",
        "emergency_mode",
    }
    for row in result:
        assert set(row.keys()) == expected_keys
    auth = by_name["AUTH_SECRET"]
    assert auth["class"] == "A"
    assert auth["status"] == "ROTATED"
    assert auth["rotation_id"] == "rot-auth-001"
    assert auth["cadence_days"] == 30
    assert auth["last_rotated_at"] == recent_iso
    assert auth["days_since_rotation"] == 2
    assert auth["next_rotation_due"]  # computed; exact value tied to recent_iso
    assert auth["in_grace_until"] is None
    # 2 days < 30 day cadence; rotated cleanly → no attention needed.
    assert auth["needs_attention"] is False
    anth = by_name["ANTHROPIC_API_KEY"]
    assert anth["status"] == "IN_GRACE"
    assert anth["in_grace_until"] == "2099-01-01T00:00:00+00:00"
    # JSON-serializable end-to-end (MCP transport requirement).
    json.dumps(result)


def test_rotation_status_corrupted_state_returns_partial(tmp_path):
    db = _make_db(tmp_path)
    # Garbage JSON — the tool must not raise; it must surface "unknown".
    try:
        _seed_repo_with_rotation_state(db, tmp_path, state="{not valid json")
        result = _rotation_status(db, REPO_NAME)
    finally:
        db.close()
    assert result, "corrupt state must surface as at least one unknown entry"
    assert any(row["status"] == "unknown" for row in result)
    # Unknown rows still satisfy the schema contract.
    for row in result:
        assert "secret" in row and "status" in row and "needs_attention" in row
    json.dumps(result)


def test_rotation_status_corrupted_partial_state_returns_known_plus_unknowns(tmp_path):
    """Mixed-shape state file: one good secret entry, one malformed; expect both
    surfaced — the good one with real data, the malformed one as unknown."""
    db = _make_db(tmp_path)
    state = {
        "version": 1,
        "repo_name": REPO_NAME,
        "scaffolded_at": "2026-04-01T00:00:00+00:00",
        "scaffolded_version": "v0.2",
        "secrets": [
            {"name": "AUTH_SECRET", "class": "A", "cadence_days": 30},
            "this is not a dict",  # malformed entry
        ],
        "rotations": [],
    }
    try:
        _seed_repo_with_rotation_state(db, tmp_path, state=state)
        result = _rotation_status(db, REPO_NAME)
    finally:
        db.close()
    statuses = [row["status"] for row in result]
    assert "NEVER" in statuses  # the good secret with no rotations yet
    assert "unknown" in statuses  # the malformed entry surfaced


def test_rotation_history_no_log_returns_empty_list(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_repo_with_rotation_state(db, tmp_path)
        result = _rotation_history(db, REPO_NAME)
    finally:
        db.close()
    assert result == []


def test_rotation_history_returns_recent_first(tmp_path):
    db = _make_db(tmp_path)
    log_lines = [
        {
            "at": "2026-05-20T14:00:00+00:00",
            "rotation_id": "rot-1",
            "secret_name": "AUTH_SECRET",
            "step": "VERIFY_PROD",
            "outcome": "succeeded",
            "duration_ms": 1200,
        },
        {
            "at": "2026-05-22T10:00:00+00:00",
            "rotation_id": "rot-2",
            "secret_name": "ANTHROPIC_API_KEY",
            "step": "HEALTH_CHECK",
            "outcome": "started",
        },
        {
            "at": "2026-05-23T09:20:00+00:00",
            "rotation_id": "rot-2",
            "secret_name": "ANTHROPIC_API_KEY",
            "step": "SOAK",
            "outcome": "succeeded",
            "duration_ms": 900_000,
            "note": "soak window clean",
        },
    ]
    try:
        _seed_repo_with_rotation_state(db, tmp_path, log_lines=log_lines)
        result = _rotation_history(db, REPO_NAME)
    finally:
        db.close()
    assert [item["rotation_id"] for item in result] == ["rot-2", "rot-2", "rot-1"]
    assert result[0]["step"] == "SOAK"
    assert result[0]["outcome"] == "succeeded"
    assert result[0]["note"] == "soak window clean"
    # Schema contract.
    for item in result:
        assert {"timestamp", "secret", "rotation_id", "step", "outcome"}.issubset(item)
    json.dumps(result)


def test_rotation_history_limit_caps(tmp_path):
    db = _make_db(tmp_path)
    log_lines = [
        {
            "at": f"2026-05-01T00:{i:02d}:00+00:00",
            "rotation_id": f"rot-{i}",
            "secret_name": "AUTH_SECRET",
            "step": "HEALTH_CHECK",
            "outcome": "started",
        }
        for i in range(60)
    ]
    try:
        _seed_repo_with_rotation_state(db, tmp_path, log_lines=log_lines)
        result_default = _rotation_history(db, REPO_NAME)
        result_capped = _rotation_history(db, REPO_NAME, limit=999)
        result_explicit = _rotation_history(db, REPO_NAME, limit=5)
    finally:
        db.close()
    assert len(result_default) == 20
    assert len(result_capped) == 60  # 60 events, cap=100 doesn't truncate
    assert len(result_explicit) == 5


def test_rotation_history_skips_malformed_lines(tmp_path):
    db = _make_db(tmp_path)
    log_lines: list[dict | str] = [
        {
            "at": "2026-05-20T14:00:00+00:00",
            "rotation_id": "rot-1",
            "secret_name": "AUTH_SECRET",
            "step": "PREFLIGHT",
            "outcome": "succeeded",
        },
        "not json at all",
        {
            "at": "2026-05-20T14:10:00+00:00",
            "rotation_id": "rot-1",
            "secret_name": "AUTH_SECRET",
            "step": "ACQUIRE",
            "outcome": "succeeded",
        },
    ]
    try:
        _seed_repo_with_rotation_state(db, tmp_path, log_lines=log_lines)
        result = _rotation_history(db, REPO_NAME)
    finally:
        db.close()
    # Two good lines, one malformed dropped silently.
    assert len(result) == 2
    assert all(item["rotation_id"] == "rot-1" for item in result)


def test_rotation_tools_repo_not_found_raises_clear_error(tmp_path):
    db = _make_db(tmp_path)
    try:
        with pytest.raises(RepoNotFoundError) as exc_status:
            _rotation_status(db, "ghost-repo")
        with pytest.raises(RepoNotFoundError) as exc_history:
            _rotation_history(db, "ghost-repo")
    finally:
        db.close()
    assert "ghost-repo" in str(exc_status.value)
    assert "ghost-repo" in str(exc_history.value)


# ---------------------------------------------------------------------------
# Path-leak invariant — the security-critical assertion
# ---------------------------------------------------------------------------


def test_no_absolute_paths_in_output(tmp_path):
    db = _make_db(tmp_path)
    # Use the rotation-aware seeder so we also exercise rotation_status /
    # rotation_history for the path-leak invariant. The repo path is a real
    # tmp directory; the state file is seeded with one secret + one rotation.
    state = {
        "version": 1,
        "repo_name": REPO_NAME,
        "scaffolded_at": "2026-04-01T00:00:00+00:00",
        "scaffolded_version": "v0.2",
        "secrets": [
            {"name": "AUTH_SECRET", "class": "A", "cadence_days": 30},
        ],
        "rotations": [
            {
                "rotation_id": "rot-leak-test",
                "secret_name": "AUTH_SECRET",
                "secret_class": "A",
                "status": "ROTATED",
                "started_at": "2026-05-20T13:50:00+00:00",
                "last_updated_at": "2026-05-20T14:00:00+00:00",
                "completed_at": "2026-05-20T14:00:00+00:00",
                "log": [],
            },
        ],
    }
    log_lines = [
        {
            "at": "2026-05-20T14:00:00+00:00",
            "rotation_id": "rot-leak-test",
            "secret_name": "AUTH_SECRET",
            "step": "VERIFY_PROD",
            "outcome": "succeeded",
            # Intentionally embed an absolute home path in a note to confirm
            # the tool doesn't rewrite note bodies — but ALSO doesn't surface
            # the note path as if it were a typed path field. The invariant
            # here is that no typed *path* field returns an absolute path;
            # free-form notes pass through as-is (the skill is responsible
            # for what it writes there).
            "note": "ok",
        },
    ]
    try:
        _seed_repo_with_rotation_state(
            db, tmp_path, state=state, log_lines=log_lines,
        )
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
        rotation_rows = _rotation_status(db, REPO_NAME)
        history_rows = _rotation_history(db, REPO_NAME)
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

    assert rotation_rows, "fixture should produce rotation status rows"
    for row in rotation_rows:
        for key in ("last_rotated_at", "next_rotation_due", "in_grace_until", "rotation_id"):
            _scan(row.get(key))

    assert history_rows, "fixture should produce rotation history events"
    for event in history_rows:
        for key in ("timestamp", "rotation_id", "step", "outcome"):
            _scan(event.get(key))


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


def test_call_tool_case_followup_prompt_in_write_mode(tmp_path):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path)
    finally:
        db.close()

    server = create_server(home=tmp_path, allow_case_decisions=True)
    result = asyncio.run(
        server.call_tool(
            "case_followup_prompt",
            {"repo": REPO_NAME, "action": "verify_findings", "scope": "critical"},
        )
    )
    prompt = _tool_result_value(result)

    assert prompt["repo"] == REPO_NAME
    assert prompt["action"] == "verify_findings"
    assert prompt["scope"] == "critical"
    assert prompt["case_count"] == 1
    assert prompt["case_ids"]
    assert SCHEMA_VERSION in prompt["prompt"]
    assert "Do not fix code." in prompt["prompt"]


def test_call_tool_preview_and_apply_case_resolutions_in_write_mode(tmp_path):
    db = _make_db(tmp_path)
    try:
        seeded_cases = _seed_scan(db, tmp_path)
        target = next(case for case in seeded_cases if case.category == "code-security")
        case_id = target.case_id
    finally:
        db.close()

    payload = {
        "schema_version": SCHEMA_VERSION,
        "repo": REPO_NAME,
        "scan_id": SCAN_ID,
        "action": "verify_findings",
        "scope": "selected_cases",
        "summary": {"cases_reviewed": 1},
        "resolutions": [
            {
                "case_id": case_id,
                "disposition": "confirmed_real",
                "confidence": "high",
                "reason": "The unsafe deserialization call is in live application code.",
                "evidence": [
                    {
                        "path": "app/api/decode.py",
                        "line": 17,
                        "interpretation": "pickle.loads handles request data.",
                    }
                ],
            }
        ],
    }

    server = create_server(home=tmp_path, allow_case_decisions=True)
    preview_result = asyncio.run(
        server.call_tool(
            "preview_case_resolutions",
            {
                "payload": payload,
                "expected_repo": REPO_NAME,
                "expected_scope": "selected_cases",
                "expected_case_ids": [case_id],
            },
        )
    )
    preview = _tool_result_value(preview_result)

    assert preview["valid"] is True
    assert preview["source"] == "mcp_write"
    assert preview["summary"]["will_apply"] == 1

    apply_result = asyncio.run(
        server.call_tool("apply_case_resolutions", {"run_id": preview["run_id"]})
    )
    applied = _tool_result_value(apply_result)

    assert applied["applied"] == 1
    assert applied["left_open"] == 0
    assert applied["rejected"] == 0
    assert applied["case_ids"] == [case_id]

    db = _make_db(tmp_path)
    try:
        assert db.case_decisions_map()[case_id]["status"] == "verified"
    finally:
        db.close()


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


def _tool_result_value(result):
    structured = _structured_content(result)
    return structured.get("result", structured)
