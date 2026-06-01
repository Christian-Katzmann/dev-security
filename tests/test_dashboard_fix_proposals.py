"""HTTP surface for the hands-off code-fix flow (S-043).

The propose → clean-room-review → land subsystem was previously reachable only
through the `devsec-mcp-rw` adapter. These tests exercise the dashboard surface
that makes it honest and reachable:

- ``GET /api/fix-proposals`` lists the persisted proposals (no diff body, no
  finding text).
- ``GET /api/fix-proposals/<id>`` returns the diff, the clean-room verdict, and
  the diff-class invariant checklist — and carries no finding text.
- ``POST /api/fix-proposals/<id>/land`` delegates to ``decide_landing`` so a
  dashboard land decision is authorized only where the proven boundary already
  allows it: an approved, allowlisted, hash-matching proposal lands; a
  non-approved, protected-branch, or non-allowlisted proposal is refused with no
  auto-merge.

Loopback-only server, mirroring the scan-diff / rotation HTTP harnesses.
"""

from __future__ import annotations

import json
import socket
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from security_observatory.dashboard_server import DashboardHandler
from security_observatory.fix_proposals import (
    FIX_PROPOSAL_SCHEMA_VERSION,
    classify_fix_class,
    diff_sha256,
    propose_fix,
    record_clean_room_review,
)
from security_observatory.storage import ObservatoryDB


DEP_BUMP_DIFF = (
    "diff --git a/package.json b/package.json\n"
    "index 1111111..2222222 100644\n"
    "--- a/package.json\n"
    "+++ b/package.json\n"
    "@@ -8,7 +8,7 @@\n"
    '   "dependencies": {\n'
    '-    "left-pad": "1.3.0"\n'
    '+    "left-pad": "1.3.1"\n'
    "   }\n"
)

SOURCE_CHANGE_DIFF = (
    "diff --git a/src/app.py b/src/app.py\n"
    "--- a/src/app.py\n"
    "+++ b/src/app.py\n"
    "@@ -1,2 +1,2 @@\n"
    '-print("old")\n'
    '+print("new")\n'
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _request(port: int, path: str, *, method: str = "GET") -> tuple[int, dict[str, object]]:
    headers = {}
    if method != "GET":
        headers["Content-Type"] = "application/json"
    request = Request(f"http://127.0.0.1:{port}{path}", method=method, headers=headers)
    try:
        with urlopen(request, timeout=5) as resp:
            body = resp.read()
            return resp.status, json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read()
        return exc.code, json.loads(body) if body else {}


def _seed_scan(db: ObservatoryDB) -> None:
    db.save_scan(
        scan_id="scan-1",
        repo_name="demo",
        repo_path="/tmp/demo",
        started_at="2026-05-30T10:00:00+00:00",
        finished_at="2026-05-30T10:01:00+00:00",
        profile="quick",
        health_score=70,
        status="ok",
        scanner_statuses=[],
        findings=[],
        report_path="report.json",
    )


@pytest.fixture
def harness(tmp_path: Path):
    home = tmp_path / "observatory"
    assets_dir = tmp_path / "assets"
    (home / "db").mkdir(parents=True)
    assets_dir.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    db_path = home / "db" / "observatory.sqlite"

    db = ObservatoryDB(db_path)
    try:
        _seed_scan(db)
        # An auto-merge-eligible dependency bump on a real feature branch.
        dep = propose_fix(
            db,
            repo="demo",
            diff=DEP_BUMP_DIFF,
            head_branch="fix/bump-left-pad",
            title="Bump left-pad 1.3.0 → 1.3.1",
            case_id="case-dep-001",
        )
        # A source-code change — never in the auto-merge allowlist.
        source = propose_fix(
            db,
            repo="demo",
            diff=SOURCE_CHANGE_DIFF,
            head_branch="fix/source-edit",
            title="Edit application source",
            case_id="case-src-001",
        )
        # A proposal whose head is a protected branch. propose_fix refuses to
        # create one, so we seed it directly to prove the land gate re-checks.
        protected_cls = classify_fix_class(DEP_BUMP_DIFF)
        protected = db.save_fix_proposal(
            {
                "id": "fix_demo_protected_0001",
                "schema_version": FIX_PROPOSAL_SCHEMA_VERSION,
                "repo_name": "demo",
                "repo_path": "/tmp/demo",
                "case_id": None,
                "base_branch": "develop",
                "head_branch": "main",
                "title": "Bump left-pad on a protected branch",
                "diff": DEP_BUMP_DIFF,
                "diff_sha256": diff_sha256(DEP_BUMP_DIFF),
                "fix_class": protected_cls.fix_class,
                "auto_merge_eligible": protected_cls.auto_merge_eligible,
                "classification": protected_cls.to_dict(),
                "source": "test",
                "status": "proposed",
                "clean_room_status": "pending",
            }
        )
    finally:
        db.close()

    handler = type(
        "BoundHandler",
        (DashboardHandler,),
        {"db_path": db_path, "assets_dir": assets_dir},
    )
    port = _free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield {
            "port": port,
            "db_path": db_path,
            "dep_id": dep["id"],
            "source_id": source["id"],
            "protected_id": protected["id"],
        }
    finally:
        httpd.shutdown()


def _approve(db_path: Path, proposal_id: str) -> None:
    db = ObservatoryDB(db_path)
    try:
        record = db.get_fix_proposal(proposal_id)
        record_clean_room_review(
            db,
            proposal_id=proposal_id,
            approved=True,
            diff_sha256=str(record["diff_sha256"]),
            checked_invariants=["all invariants hold on the diff"],
            reviewer="clean-room-bot",
        )
    finally:
        db.close()


def test_list_route_returns_seeded_proposals(harness):
    status, payload = _request(harness["port"], "/api/fix-proposals")
    assert status == HTTPStatus.OK
    ids = {item["id"] for item in payload["items"]}
    assert harness["dep_id"] in ids
    assert harness["source_id"] in ids
    # The list is a trimmed projection: no diff body leaks into the list view.
    for item in payload["items"]:
        assert "diff" not in item
        assert "diff_stat" in item


def test_detail_route_exposes_diff_and_clean_room_without_finding_text(harness):
    status, payload = _request(harness["port"], f"/api/fix-proposals/{harness['dep_id']}")
    assert status == HTTPStatus.OK
    assert "left-pad" in payload["diff"]
    assert payload["clean_room"]["status"] == "pending"
    # The diff-class invariant checklist is present and describes the diff.
    assert payload["clean_room"]["invariants"]
    # The clean-room fence holds across the surface: no finding text anywhere.
    assert "finding" not in json.dumps(payload).lower()


def test_detail_route_404_for_unknown_proposal(harness):
    status, payload = _request(harness["port"], "/api/fix-proposals/fix_demo_missing_0000")
    assert status == HTTPStatus.NOT_FOUND
    assert "error" in payload


def test_land_route_auto_merges_approved_allowlisted_proposal(harness):
    _approve(harness["db_path"], harness["dep_id"])
    status, payload = _request(
        harness["port"], f"/api/fix-proposals/{harness['dep_id']}/land", method="POST"
    )
    assert status == HTTPStatus.OK
    assert payload["outcome"] == "auto_merge"
    assert payload["auto_merge"] is True
    assert payload["fix_class"] == "dependency_bump"


def test_land_route_refuses_non_approved_proposal(harness):
    # No clean-room approval recorded → no auto-merge.
    status, payload = _request(
        harness["port"], f"/api/fix-proposals/{harness['dep_id']}/land", method="POST"
    )
    assert status == HTTPStatus.OK
    assert payload["outcome"] == "requires_human"
    assert payload["auto_merge"] is False


def test_land_route_refuses_non_allowlisted_class(harness):
    _approve(harness["db_path"], harness["source_id"])
    status, payload = _request(
        harness["port"], f"/api/fix-proposals/{harness['source_id']}/land", method="POST"
    )
    assert status == HTTPStatus.OK
    assert payload["outcome"] == "requires_human"
    assert payload["auto_merge"] is False
    assert payload["fix_class"] == "source_change"


def test_land_route_blocks_protected_branch(harness):
    _approve(harness["db_path"], harness["protected_id"])
    status, payload = _request(
        harness["port"], f"/api/fix-proposals/{harness['protected_id']}/land", method="POST"
    )
    assert status == HTTPStatus.OK
    assert payload["outcome"] == "blocked"
    assert payload["auto_merge"] is False
