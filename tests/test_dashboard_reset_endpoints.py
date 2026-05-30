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
from security_observatory.storage import ObservatoryDB


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http(port: int, path: str, *, body: dict[str, object]) -> tuple[int, dict[str, object]]:
    data = json.dumps(body).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Content-Length": str(len(data))},
    )
    try:
        with urlopen(request, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


@pytest.fixture
def harness(tmp_path: Path):
    home = tmp_path / "observatory"
    db_dir = home / "db"
    reports = home / "reports" / "demo-repo" / "demo-20260101"
    assets_dir = tmp_path / "assets"
    repo_root = tmp_path / "demo-repo"
    db_dir.mkdir(parents=True)
    reports.mkdir(parents=True)
    assets_dir.mkdir()
    repo_root.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (reports / "normalized-report.json").write_text("{}", encoding="utf-8")
    (repo_root / "app.py").write_text("print('untouched')\n", encoding="utf-8")

    db_path = db_dir / "observatory.sqlite"
    db = ObservatoryDB(db_path)
    try:
        with db.conn:
            db.conn.execute(
                """INSERT INTO scans (id, repo_name, repo_path, started_at, finished_at,
                   profile, health_score, status, scanner_status_json, cases_json, report_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "demo-20260101",
                    "demo-repo",
                    str(repo_root),
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:01:00Z",
                    "quick",
                    88,
                    "ok",
                    "[]",
                    "[]",
                    str(reports / "normalized-report.json"),
                ),
            )
            db.conn.execute(
                """INSERT INTO findings (scan_id, repo_name, scanner, severity, category, title, fingerprint, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("demo-20260101", "demo-repo", "semgrep", "high", "code-security", "Demo", "fp1", "2026-01-01T00:00:00Z"),
            )
            db.conn.execute(
                """INSERT INTO honey_keys
                   (id, project_id, repo_id, name, token_prefix, token_hash, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("hk-1", "demo-repo", "demo-repo", "Decoy", "devsec_", "hash", "active", "2026-01-01T00:00:00Z"),
            )
    finally:
        db.close()

    handler = type("BoundHandler", (DashboardHandler,), {"db_path": db_path, "assets_dir": assets_dir})
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {"port": port, "db_path": db_path, "home": home, "repo_root": repo_root}
    finally:
        server.shutdown()


def test_preview_scan_results_reset(harness: dict[str, object]):
    status, payload = _http(
        int(harness["port"]),
        "/api/reset/scan-results/preview",
        body={"scope": "repo", "repoName": "demo-repo"},
    )

    assert status == HTTPStatus.OK
    assert payload["confirmation_phrase"] == "RESET SCAN RESULTS FOR demo-repo"
    assert payload["plan"]["repos"] == ["demo-repo"]
    assert any(row["table"] == "findings" for row in payload["plan"]["tables"])
    assert "scanned repositories" in payload["plan"]["preserved"]


def test_execute_scan_results_reset_with_backup_preserves_repo_and_honey(harness: dict[str, object]):
    status, payload = _http(
        int(harness["port"]),
        "/api/reset/scan-results",
        body={
            "scope": "repo",
            "repoName": "demo-repo",
            "keepBackup": True,
            "confirmation": "RESET SCAN RESULTS FOR demo-repo",
        },
    )

    assert status == HTTPStatus.OK
    assert Path(payload["backup"]["scan_results_json"]).exists()
    assert not (Path(harness["home"]) / "reports" / "demo-repo").exists()
    assert (Path(harness["repo_root"]) / "app.py").read_text(encoding="utf-8") == "print('untouched')\n"

    db = ObservatoryDB(Path(harness["db_path"]))
    try:
        assert db.conn.execute("SELECT COUNT(*) as cnt FROM scans").fetchone()["cnt"] == 0
        assert db.conn.execute("SELECT COUNT(*) as cnt FROM findings").fetchone()["cnt"] == 0
        assert db.conn.execute("SELECT COUNT(*) as cnt FROM honey_keys").fetchone()["cnt"] == 1
    finally:
        db.close()


def test_execute_scan_results_reset_requires_confirmation(harness: dict[str, object]):
    status, payload = _http(
        int(harness["port"]),
        "/api/reset/scan-results",
        body={"scope": "repo", "repoName": "demo-repo", "confirmation": "yes"},
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert "Confirmation" in payload["error"]
