"""Tests for the fix-proposal MCP tools (devsec-mcp-rw only).

These exercise the *surface contract*: the propose/review/land tools are
registered only in write mode, never on the read-only adapter or the dashboard
HTTP surface, and the call-tool path refuses a proposal that targets a
protected branch.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from security_observatory.cases import build_security_cases
from security_observatory.mcp_server import create_server
from security_observatory.model import Finding
from security_observatory.storage import ObservatoryDB


REPO = "demo-repo"
FIX_TOOLS = {"propose_fix", "clean_room_review_packet", "record_clean_room_review", "land_fix"}


def _seed(tmp_path: Path) -> None:
    db = ObservatoryDB(tmp_path / "db" / "observatory.sqlite")
    try:
        finding = Finding(
            repo=REPO,
            scanner="trivy",
            severity="high",
            category="dependencies",
            title="Vulnerable requests",
            file="requirements.txt",
            line=1,
            fingerprint="finding-1",
        )
        cases = build_security_cases(
            [finding],
            [{"scanner": "trivy", "available": True, "findings": 1}],
            {"repo": REPO},
        )
        db.save_scan(
            scan_id="scan-1",
            repo_name=REPO,
            repo_path=str(tmp_path / REPO),
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:30+00:00",
            profile="quick",
            health_score=70,
            status="ok",
            scanner_statuses=[{"scanner": "trivy", "available": True, "findings": 1}],
            findings=[finding],
            report_path=str(tmp_path / "report.json"),
            cases=cases,
        )
    finally:
        db.close()


DEP_BUMP_DIFF = """diff --git a/requirements.txt b/requirements.txt
--- a/requirements.txt
+++ b/requirements.txt
@@ -1,1 +1,1 @@
-requests==2.31.0
+requests==2.32.4
"""


def test_fix_tools_registered_only_in_write_mode(tmp_path):
    read_only = {t.name for t in asyncio.run(create_server(home=tmp_path).list_tools())}
    write_mode = {t.name for t in asyncio.run(create_server(home=tmp_path, allow_case_decisions=True).list_tools())}
    assert FIX_TOOLS.isdisjoint(read_only)
    assert FIX_TOOLS.issubset(write_mode)


def test_dashboard_http_surface_does_not_expose_fix_tools():
    import security_observatory.dashboard_server as dashboard

    source = Path(dashboard.__file__).read_text(encoding="utf-8")
    for name in FIX_TOOLS:
        assert name not in source
    assert "fix_proposals" not in source
    assert "mcp_server" not in source


def test_call_tool_propose_refuses_protected_branch(tmp_path):
    _seed(tmp_path)
    from mcp.server.fastmcp.exceptions import ToolError

    server = create_server(home=tmp_path, allow_case_decisions=True)
    with pytest.raises(ToolError):
        asyncio.run(
            server.call_tool(
                "propose_fix",
                {"repo": REPO, "diff": DEP_BUMP_DIFF, "head_branch": "main", "title": "x"},
            )
        )


def test_call_tool_propose_review_land_round_trip(tmp_path):
    _seed(tmp_path)
    server = create_server(home=tmp_path, allow_case_decisions=True)

    proposed = asyncio.run(
        server.call_tool(
            "propose_fix",
            {
                "repo": REPO,
                "diff": DEP_BUMP_DIFF,
                "head_branch": "fix/devsec-bump-requests",
                "title": "Bump requests to the patched version",
            },
        )
    )
    record = _structured(proposed)
    assert record["fix_class"] == "dependency_bump"
    assert record["auto_merge_eligible"] is True
    proposal_id = record["id"]

    packet = _structured(asyncio.run(server.call_tool("clean_room_review_packet", {"proposal_id": proposal_id})))
    assert "case_id" not in packet
    assert packet["fix_class"] == "dependency_bump"

    asyncio.run(
        server.call_tool(
            "record_clean_room_review",
            {"proposal_id": proposal_id, "approved": True, "diff_sha256": packet["diff_sha256"]},
        )
    )
    decision = _structured(asyncio.run(server.call_tool("land_fix", {"proposal_id": proposal_id})))
    assert decision["outcome"] == "auto_merge"
    assert decision["auto_merge"] is True


def _structured(result):
    """FastMCP call_tool returns (content, structured) across versions."""
    if isinstance(result, tuple):
        for part in result:
            if isinstance(part, dict):
                return part
    return result
