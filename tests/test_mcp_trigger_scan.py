"""Tests for the guarded scan-trigger MCP tool (devsec-mcp-rw only).

The tool wraps the existing append-only scan path. These tests never run real
scanners — ``_scan_repo`` is monkeypatched — so they exercise the *contract*:
write-mode-only registration, repo-name (never raw-path) resolution, the fixed
profile enum, the per-repo cooldown, local-offline args, and refusal of a
poisoned/malicious scan target.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from security_observatory import mcp_server
from security_observatory.cli import profile_name
from security_observatory.mcp_server import (
    SCAN_COOLDOWN_SECONDS,
    SCAN_PROFILES,
    RepoNotFoundError,
    _scan_args,
    _scan_cooldown_remaining,
    _trigger_scan,
    create_server,
)
from security_observatory.cases import build_security_cases
from security_observatory.model import Finding
from security_observatory.scanners import scanner_names_for_profile
from security_observatory.storage import ObservatoryDB


REPO_NAME = "demo-repo"
REPO_PATH = "/Users/dummyuser/Dev/Projects/demo-repo"


def _seed_scan(db: ObservatoryDB, tmp_path: Path, *, started_at: str) -> None:
    finding = Finding(
        repo=REPO_NAME,
        scanner="semgrep",
        severity="high",
        category="code-security",
        title="Unsafe deserialization",
        file=f"{REPO_PATH}/app.py",
        line=2,
        fingerprint="finding-1",
    )
    cases = build_security_cases(
        [finding],
        [{"scanner": "semgrep", "available": True, "findings": 1}],
        {"repo": REPO_NAME},
    )
    db.save_scan(
        scan_id="demo-20260101T000000Z",
        repo_name=REPO_NAME,
        repo_path=REPO_PATH,
        started_at=started_at,
        finished_at=started_at,
        profile="quick",
        health_score=70,
        status="ok",
        scanner_statuses=[{"scanner": "semgrep", "available": True, "findings": 1}],
        findings=[finding],
        report_path=str(tmp_path / "report.json"),
        cases=cases,
    )


def _make_db(tmp_path: Path) -> ObservatoryDB:
    return ObservatoryDB(tmp_path / "db" / "observatory.sqlite")


def _old_timestamp() -> str:
    # Comfortably outside the cooldown window.
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat()


# ---------------------------------------------------------------------------
# Registration — write mode only
# ---------------------------------------------------------------------------


def test_trigger_scan_registered_only_in_write_mode(tmp_path):
    read_only = {t.name for t in asyncio.run(create_server(home=tmp_path).list_tools())}
    write_mode = {t.name for t in asyncio.run(create_server(home=tmp_path, allow_case_decisions=True).list_tools())}
    assert "trigger_scan" not in read_only
    assert "trigger_scan" in write_mode


def test_dashboard_http_surface_does_not_expose_trigger_scan():
    """The dashboard is a separate HTTP server that never mounts MCP tools.

    Structural confirmation: the dashboard module neither imports the MCP server
    factory nor references the scan-trigger tool, so it cannot leak over HTTP.
    """
    import security_observatory.dashboard_server as dashboard

    source = Path(dashboard.__file__).read_text(encoding="utf-8")
    assert "trigger_scan" not in source
    assert "mcp_server" not in source
    assert "create_server" not in source
    assert not hasattr(dashboard, "trigger_scan")


# ---------------------------------------------------------------------------
# Routing through the existing scan path
# ---------------------------------------------------------------------------


def test_trigger_scan_routes_through_scan_repo(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path, started_at=_old_timestamp())
    finally:
        db.close()

    captured: dict = {}

    def fake_scan_repo(repo_path, args, home):
        captured["repo_path"] = repo_path
        captured["args"] = args
        captured["home"] = home
        return {
            "scan_id": "demo-rescan",
            "started_at": "2026-02-01T00:00:00+00:00",
            "finished_at": "2026-02-01T00:01:00+00:00",
            "health_score": 88,
            "status": "ok",
            "scanners": [{"scanner": "semgrep"}, {"scanner": "gitleaks"}],
            "findings": [{"id": 1}],
        }

    monkeypatch.setattr(mcp_server, "_scan_repo", fake_scan_repo)

    result = _trigger_scan(_make_db(tmp_path), tmp_path, repo=REPO_NAME, profile="quick")

    assert result["outcome"] == "completed"
    assert result["scan_id"] == "demo-rescan"
    assert result["scanner_count"] == 2
    assert result["finding_count"] == 1
    assert result["health_score"] == 88
    assert result["status"] == "ok"
    # The recorded repo path is used — never a caller-supplied string.
    assert captured["repo_path"] == Path(REPO_PATH)
    # Local-offline invariants hold on the args handed to the scan path.
    args = captured["args"]
    assert args.quick is True
    assert args.trust is False
    assert args.trust_cache_only is False
    assert args.behavioral_drift is False
    assert args.platform_posture is False
    assert args.full is False


def test_trigger_scan_default_profile_is_local_and_offline(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path, started_at=_old_timestamp())
    finally:
        db.close()
    captured: dict = {}
    monkeypatch.setattr(
        mcp_server,
        "_scan_repo",
        lambda repo_path, args, home: captured.update(args=args) or {"scan_id": "x", "scanners": [], "findings": []},
    )
    _trigger_scan(_make_db(tmp_path), tmp_path, repo=REPO_NAME, profile="default")
    args = captured["args"]
    assert args.quick is False
    assert profile_name(args) == "default"
    # No network-egress scanner is selected.
    assert "legitify" not in scanner_names_for_profile(args)


# ---------------------------------------------------------------------------
# Cooldown / rate limiting
# ---------------------------------------------------------------------------


def test_trigger_scan_rate_limited_within_cooldown(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path, started_at=dt.datetime.now(dt.timezone.utc).isoformat())
    finally:
        db.close()

    def explode(*args, **kwargs):
        raise AssertionError("scan_repo must not run during cooldown")

    monkeypatch.setattr(mcp_server, "_scan_repo", explode)

    result = _trigger_scan(_make_db(tmp_path), tmp_path, repo=REPO_NAME, profile="quick")
    assert result["outcome"] == "rate_limited"
    assert 0 < result["retry_after_seconds"] <= SCAN_COOLDOWN_SECONDS
    assert result["cooldown_seconds"] == SCAN_COOLDOWN_SECONDS


def test_cooldown_remaining_helper():
    now = dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    recent = {"started_at": (now - dt.timedelta(minutes=3)).isoformat()}
    old = {"started_at": (now - dt.timedelta(minutes=30)).isoformat()}
    assert _scan_cooldown_remaining(recent, now=now) > 0
    assert _scan_cooldown_remaining(old, now=now) == 0
    assert _scan_cooldown_remaining(None, now=now) == 0
    assert _scan_cooldown_remaining({"started_at": "not-a-date"}, now=now) == 0


# ---------------------------------------------------------------------------
# Profile enum
# ---------------------------------------------------------------------------


def test_trigger_scan_rejects_unknown_profile(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path, started_at=_old_timestamp())
    finally:
        db.close()

    def explode(*args, **kwargs):
        raise AssertionError("scan_repo must not run for a rejected profile")

    monkeypatch.setattr(mcp_server, "_scan_repo", explode)

    for bad in ("full", "trust", "deps", "", "QUICK; rm -rf /"):
        with pytest.raises(ValueError) as exc:
            _trigger_scan(_make_db(tmp_path), tmp_path, repo=REPO_NAME, profile=bad)
        assert "profile" in str(exc.value).lower()


def test_scan_profiles_are_local_offline_only():
    for profile in SCAN_PROFILES:
        args = _scan_args(profile)
        assert args.trust is False
        assert args.trust_cache_only is False
        assert args.behavioral_drift is False
        assert args.platform_posture is False


# ---------------------------------------------------------------------------
# Poisoned input — a malicious / raw scan target is refused
# ---------------------------------------------------------------------------


def test_trigger_scan_refuses_poisoned_or_raw_target(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path, started_at=_old_timestamp())
    finally:
        db.close()

    def explode(*args, **kwargs):
        raise AssertionError("scan_repo must not run for an unresolved target")

    monkeypatch.setattr(mcp_server, "_scan_repo", explode)

    poisoned_targets = [
        "/etc",
        "/etc/passwd",
        "../../other-repo",
        "/Users/victim/.ssh",
        "; rm -rf /",
        REPO_PATH,  # the absolute recorded path is NOT a valid repo *name*
        "unknown-repo",
    ]
    for target in poisoned_targets:
        with pytest.raises(RepoNotFoundError):
            _trigger_scan(_make_db(tmp_path), tmp_path, repo=target, profile="quick")


def test_trigger_scan_call_tool_surface_refuses_bad_target(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    try:
        _seed_scan(db, tmp_path, started_at=_old_timestamp())
    finally:
        db.close()

    from mcp.server.fastmcp.exceptions import ToolError

    monkeypatch.setattr(
        mcp_server,
        "_scan_repo",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not scan")),
    )
    server = create_server(home=tmp_path, allow_case_decisions=True)
    with pytest.raises(ToolError):
        asyncio.run(server.call_tool("trigger_scan", {"repo": "/etc/passwd", "profile": "quick"}))
