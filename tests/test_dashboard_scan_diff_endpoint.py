"""HTTP surface for arbitrary scan diff (S-039).

`GET /api/scan-diff?base=<id>&head=<id>` lets the dashboard's base/head picker
compare any two saved scans. The route validates both ids are present, returns
404 when a scan is unknown, and otherwise hands back the `ObservatoryDB.scan_diff`
payload. Loopback-only server, mirroring the existing GET-resilience harness.
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
from security_observatory.model import SecurityCase
from security_observatory.storage import ObservatoryDB


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(port: int, path: str) -> tuple[int, dict[str, object]]:
    request = Request(f"http://127.0.0.1:{port}{path}", method="GET")
    try:
        with urlopen(request, timeout=5) as resp:
            payload = resp.read()
            return resp.status, json.loads(payload) if payload else {}
    except HTTPError as exc:
        payload = exc.read()
        return exc.code, json.loads(payload) if payload else {}


def _case(case_id: str, title: str) -> SecurityCase:
    return SecurityCase(
        case_id=case_id,
        title=title,
        plain_english_risk="",
        action_level="fix_now",
        confidence="high",
        category="secrets",
        severity="high",
        affected_files=[],
        evidence=[],
        scanners=["semgrep"],
        fix_steps=[],
        agent_prompt="",
        source_fingerprints=[],
    )


@pytest.fixture
def server(tmp_path: Path):
    home = tmp_path / "observatory"
    assets_dir = tmp_path / "assets"
    (home / "db").mkdir(parents=True)
    assets_dir.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    db_path = home / "db" / "observatory.sqlite"

    db = ObservatoryDB(db_path)
    try:
        for scan_id, started_at, health, cases in (
            ("s1", "2026-05-28T10:00:00+00:00", 60, [_case("A", "Token in env"), _case("B", "Weak hash")]),
            ("s2", "2026-05-30T10:00:00+00:00", 84, [_case("A", "Token in env"), _case("C", "Open redirect")]),
        ):
            db.save_scan(
                scan_id=scan_id,
                repo_name="repo",
                repo_path="/tmp/repo",
                started_at=started_at,
                finished_at=started_at,
                profile="quick",
                health_score=health,
                status="ok",
                scanner_statuses=[{"scanner": "semgrep", "available": True, "findings": len(cases)}],
                findings=[],
                report_path="report.json",
                cases=cases,
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
        yield port
    finally:
        httpd.shutdown()


def test_scan_diff_endpoint_carries_base_and_head(server):
    status, payload = _get(int(server), "/api/scan-diff?base=s1&head=s2")
    assert status == HTTPStatus.OK
    assert payload["base"]["scan_id"] == "s1"
    assert payload["head"]["scan_id"] == "s2"
    assert payload["health_delta"] == 24
    assert payload["counts"] == {"new": 1, "recurring": 1, "resolved": 1}


def test_scan_diff_endpoint_requires_both_ids(server):
    status, payload = _get(int(server), "/api/scan-diff?head=s2")
    assert status == HTTPStatus.BAD_REQUEST
    assert "error" in payload


def test_scan_diff_endpoint_404_for_unknown_scan(server):
    status, payload = _get(int(server), "/api/scan-diff?base=s1&head=missing")
    assert status == HTTPStatus.NOT_FOUND
    assert "error" in payload
