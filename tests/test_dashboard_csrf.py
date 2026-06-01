"""CSRF / Origin hardening and the re-armed suppression gate on the dashboard's
mutating loopback HTTP surface (S-001).

These tests pin the non-negotiable trust property: a browser-borne cross-site or
DNS-rebinding POST cannot drive the dashboard's mutating API, and in particular
cannot suppress a high/critical case. `human_authorized=True` is no longer
inferred from "a POST arrived" — it requires a positive, CSRF-surviving
confirmation token. The honey-key trigger callback is deliberately exempt so the
decoy still beacons cross-origin.
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

from security_observatory.cases import build_security_cases
from security_observatory.dashboard_server import DashboardHandler
from security_observatory.model import Finding
from security_observatory.storage import ObservatoryDB


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _request(
    port: int,
    path: str,
    *,
    method: str | None = None,
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    raw_body: bytes | None = None,
) -> tuple[int, dict[str, object]]:
    data: bytes | None
    if raw_body is not None:
        data = raw_body
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
    else:
        data = None
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method=method or ("POST" if data is not None else "GET"),
        headers=headers or {},
    )
    try:
        with urlopen(request, timeout=5) as resp:
            payload = resp.read()
            return resp.status, json.loads(payload) if payload else {}
    except HTTPError as exc:
        payload = exc.read()
        return exc.code, json.loads(payload) if payload else {}


@pytest.fixture
def harness(tmp_path: Path):
    home = tmp_path / "observatory"
    assets_dir = tmp_path / "assets"
    repo_root = tmp_path / "repo"
    (home / "db").mkdir(parents=True)
    assets_dir.mkdir()
    repo_root.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    finding = Finding(
        repo="repo",
        scanner="semgrep",
        severity="critical",
        category="code-security",
        title="Unsafe SQL",
        file="app.py",
        line=2,
    )
    cases = build_security_cases(
        [finding],
        [{"scanner": "semgrep", "available": True, "findings": 1}],
        {"repo": "repo", "repo_path": str(repo_root), "scan_id": "repo-20260101T000000Z"},
    )
    db_path = home / "db" / "observatory.sqlite"
    db = ObservatoryDB(db_path)
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path=str(repo_root),
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="quick",
            health_score=70,
            status="ok",
            scanner_statuses=[{"scanner": "semgrep", "available": True, "findings": 1}],
            findings=[finding],
            report_path=str(tmp_path / "normalized-report.json"),
            cases=cases,
        )
    finally:
        db.close()

    handler = type("BoundHandler", (DashboardHandler,), {"db_path": db_path, "assets_dir": assets_dir})
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"port": port, "db_path": db_path, "case_id": cases[0].case_id}
    finally:
        server.shutdown()


def _confirm_token(port: int) -> str:
    status, payload = _request(port, "/api/csrf-token")
    assert status == HTTPStatus.OK
    return str(payload["token"])


def _is_suppressed(db_path: Path, case_id: str) -> bool:
    db = ObservatoryDB(db_path)
    try:
        return case_id in db.case_decisions_map()
    finally:
        db.close()


def test_forged_cross_origin_post_is_rejected_and_cannot_suppress_critical(harness):
    port = int(harness["port"])
    case_id = str(harness["case_id"])

    # A malicious page in the operator's browser forges the suppression POST.
    # The browser stamps it with a foreign Origin / cross-site Sec-Fetch-Site it
    # cannot lie about — even if it somehow learned the confirmation token.
    status, payload = _request(
        port,
        "/api/case-decision",
        body={"caseId": case_id, "repoName": "repo", "status": "false_positive", "note": "forged"},
        headers={
            "Content-Type": "application/json",
            "Origin": "http://evil.example",
            "Sec-Fetch-Site": "cross-site",
            "X-DevSec-Confirm": _confirm_token(port),
        },
    )

    assert status == HTTPStatus.FORBIDDEN
    assert "error" in payload
    # The non-negotiable: the critical case stays unsuppressed in storage.
    assert not _is_suppressed(Path(harness["db_path"]), case_id)


def test_same_origin_with_confirmation_token_suppresses_critical(harness):
    port = int(harness["port"])
    case_id = str(harness["case_id"])

    status, payload = _request(
        port,
        "/api/case-decision",
        body={"caseId": case_id, "repoName": "repo", "status": "false_positive", "note": "Confirmed example."},
        headers={
            "Content-Type": "application/json",
            "Origin": f"http://127.0.0.1:{port}",
            "Sec-Fetch-Site": "same-origin",
            "X-DevSec-Confirm": _confirm_token(port),
        },
    )

    assert status == HTTPStatus.OK
    assert payload["decision"]["status"] == "false_positive"
    assert _is_suppressed(Path(harness["db_path"]), case_id)


def test_same_origin_without_token_cannot_suppress_critical(harness):
    port = int(harness["port"])
    case_id = str(harness["case_id"])

    # Same-origin (so the CSRF guard passes) but with no confirmation token: the
    # re-armed gate refuses to infer human authorization from POST arrival alone.
    status, payload = _request(
        port,
        "/api/case-decision",
        body={"caseId": case_id, "repoName": "repo", "status": "false_positive", "note": "no token"},
        headers={"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"},
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert "human" in payload["error"].casefold()
    assert not _is_suppressed(Path(harness["db_path"]), case_id)


def test_missing_json_content_type_is_rejected(harness):
    port = int(harness["port"])
    case_id = str(harness["case_id"])

    # Same-origin, valid token, but a CSRF-friendly content type: rejected with a
    # clean JSON 415 rather than crashing the JSON parser.
    status, payload = _request(
        port,
        "/api/case-decision",
        raw_body=json.dumps({"caseId": case_id, "repoName": "repo", "status": "false_positive"}).encode("utf-8"),
        headers={
            "Content-Type": "text/plain",
            "Origin": f"http://127.0.0.1:{port}",
            "X-DevSec-Confirm": _confirm_token(port),
        },
    )

    assert status == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    assert "application/json" in payload["error"]
    assert not _is_suppressed(Path(harness["db_path"]), case_id)


def test_honey_trigger_is_exempt_from_cross_origin_guard(harness):
    port = int(harness["port"])

    # A honeytoken embedded in a URL must beacon on a cross-origin call by
    # design, so the trigger callback is deliberately exempt from the guard.
    status, payload = _request(
        port,
        "/api/honey/trigger",
        body={"api_key": "devsec_hny_unknown_token"},
        headers={
            "Content-Type": "application/json",
            "Origin": "http://evil.example",
            "Sec-Fetch-Site": "cross-site",
        },
    )

    assert status == HTTPStatus.ACCEPTED
    assert payload["accepted"] is True
