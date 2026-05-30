from __future__ import annotations

import json
import socket
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from security_observatory.case_followup import SCHEMA_VERSION
from security_observatory.cases import build_security_cases
from security_observatory.dashboard_server import DashboardHandler
from security_observatory.model import Finding
from security_observatory.storage import ObservatoryDB


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http_json(port: int, path: str, *, body: dict[str, object] | None = None, method: str | None = None) -> tuple[int, dict[str, object]]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method=method or ("POST" if body is not None else "GET"),
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urlopen(request, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


@pytest.fixture
def harness(tmp_path: Path):
    home = tmp_path / "observatory"
    assets_dir = tmp_path / "assets"
    repo_root = tmp_path / "repo"
    (home / "db").mkdir(parents=True)
    assets_dir.mkdir()
    repo_root.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    finding = Finding(repo="repo", scanner="semgrep", severity="critical", category="code-security", title="Unsafe SQL", file="app.py", line=2)
    cases = build_security_cases([finding], [{"scanner": "semgrep", "available": True, "findings": 1}], {"repo": "repo", "repo_path": str(repo_root), "scan_id": "repo-20260101T000000Z"})
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


def test_ai_followup_prompt_preview_apply_and_history(harness: dict[str, object]):
    port = int(harness["port"])
    case_id = str(harness["case_id"])

    status, prompt = _http_json(port, "/api/ai-follow-up/prompt?repo=repo&action=verify_findings&scope=critical")
    assert status == HTTPStatus.OK
    assert prompt["case_count"] == 1
    assert "Do not fix code" in prompt["prompt"]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "repo": "repo",
        "scan_id": "repo-20260101T000000Z",
        "action": "verify_findings",
        "scope": "critical",
        "summary": {"cases_reviewed": 1},
        "resolutions": [
            {
                "case_id": case_id,
                "disposition": "docs_example",
                "confidence": "high",
                "reason": "The unsafe SQL is in documentation as an intentionally bad example.",
                "evidence": [{"path": "docs/security.md", "line": 12, "interpretation": "example section"}],
                "recommended_next_step": "Mark false positive.",
            }
        ],
    }
    status, preview = _http_json(
        port,
        "/api/ai-follow-up/resolutions/preview",
        body={"payload": payload, "expectedRepo": "repo", "expectedScope": "critical"},
    )
    assert status == HTTPStatus.OK
    assert preview["valid"] is True
    assert preview["summary"]["will_apply"] == 1

    status, apply = _http_json(port, "/api/ai-follow-up/resolutions/apply", body={"runId": preview["run_id"]})
    assert status == HTTPStatus.OK
    assert apply["applied"] == 1

    status, runs = _http_json(port, f"/api/ai-follow-up/resolution-runs?repo={quote('repo')}")
    assert status == HTTPStatus.OK
    assert runs["items"][0]["status"] == "applied"

    db = ObservatoryDB(Path(harness["db_path"]))
    try:
        assert db.case_decisions_map()[case_id]["status"] == "false_positive"
    finally:
        db.close()
