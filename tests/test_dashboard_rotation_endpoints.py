"""End-to-end HTTP tests for the dashboard rotation endpoints.

The dashboard is a real ThreadingHTTPServer. These tests spin it up against a
temp-dir DB + a fake repo on disk so each endpoint's contract — status, history,
receipt serving with path-traversal safety, and the guarded scaffold handoff —
is exercised against the same code path the browser hits.
"""
from __future__ import annotations

import datetime as _dt
import json
import socket
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from security_observatory.dashboard_server import CHECK_JOBS, CHECK_JOBS_LOCK, DashboardHandler
from security_observatory.storage import ObservatoryDB


REPO_NAME = "demo-rotation-repo"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(db_path: Path, assets_dir: Path):
    port = _free_port()
    handler = type(
        "BoundHandler",
        (DashboardHandler,),
        {"db_path": db_path, "assets_dir": assets_dir},
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _http(port: int, path: str, *, method: str = "GET", body: dict | None = None) -> tuple[int, bytes, str]:
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(data))
    request = Request(f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=5) as resp:
            return resp.status, resp.read(), resp.headers.get_content_type()
    except HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get_content_type()


@pytest.fixture
def harness(tmp_path: Path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db_path = db_dir / "observatory.sqlite"
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    repo_root = tmp_path / "fake-repo"
    repo_root.mkdir()
    # Seed a scan record so the repo→path resolver returns repo_root.
    db = ObservatoryDB(db_path)
    try:
        db.save_scan(
            scan_id="demo-20260101T000000Z",
            repo_name=REPO_NAME,
            repo_path=str(repo_root),
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="quick",
            health_score=80,
            status="ok",
            scanner_statuses=[],
            findings=[],
            report_path=str(tmp_path / "report.json"),
        )
    finally:
        db.close()
    server, port = _serve(db_path, assets_dir)
    try:
        yield {"port": port, "repo_root": repo_root}
    finally:
        server.shutdown()


def _seed_state(repo_root: Path, payload: dict) -> None:
    (repo_root / "data").mkdir(parents=True, exist_ok=True)
    (repo_root / "data" / "rotation-state.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _seed_log(repo_root: Path, events: list[dict]) -> None:
    (repo_root / "data").mkdir(parents=True, exist_ok=True)
    (repo_root / "data" / "rotation-log.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events), encoding="utf-8"
    )


def _seed_receipt(repo_root: Path, filename: str, body: str) -> None:
    receipts = repo_root / "data" / "rotation-receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / filename).write_text(body, encoding="utf-8")


def _seed_local_catalog(repo_root: Path, entries: list[dict]) -> None:
    catalog_dir = repo_root / "src" / "lib" / "rotation"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / "catalog.local.json").write_text(
        json.dumps({"entries": entries}), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# /api/rotation/status/<repo>
# ---------------------------------------------------------------------------


def test_status_endpoint_returns_empty_when_no_scaffold(harness):
    status, body, content_type = _http(harness["port"], f"/api/rotation/status/{REPO_NAME}")
    assert status == HTTPStatus.OK
    payload = json.loads(body)
    assert payload["repo"] == REPO_NAME
    assert payload["secrets"] == []
    assert payload["rotation_state"]["scaffolded"] is False
    assert content_type == "application/json"


def test_status_endpoint_returns_seeded_secrets(harness):
    completed = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=2)).isoformat()
    _seed_local_catalog(
        harness["repo_root"],
        [
            {
                "name": "AUTH_SECRET",
                "rotation_warning": "Local AUTH_SECRET warning.",
                "soak_window_minutes": 25,
                "console_url": "https://example.test/auth-secret",
            }
        ],
    )
    _seed_state(
        harness["repo_root"],
        {
            "secrets": [{"name": "AUTH_SECRET", "class": "A", "cadence_days": 30}],
            "rotations": [
                {
                    "secret_name": "AUTH_SECRET",
                    "rotation_id": "rot-1",
                    "started_at": completed,
                    "completed_at": completed,
                    "status": "ROTATED",
                }
            ],
        },
    )
    _seed_log(
        harness["repo_root"],
        [
            {
                "at": completed,
                "rotation_id": "rot-1",
                "secret_name": "AUTH_SECRET",
                "step": "REVOKE",
                "outcome": "succeeded",
            }
        ],
    )
    status, body, _ct = _http(harness["port"], f"/api/rotation/status/{REPO_NAME}")
    assert status == HTTPStatus.OK
    payload = json.loads(body)
    assert payload["rotation_state"]["scaffolded"] is True
    assert payload["secrets"][0]["secret"] == "AUTH_SECRET"
    assert payload["secrets"][0]["status"] == "ROTATED"
    assert payload["secrets"][0]["rotation_warning"] == "Local AUTH_SECRET warning."
    assert payload["secrets"][0]["soak_window_minutes"] == 25
    assert payload["secrets"][0]["console_url"] == "https://example.test/auth-secret"
    assert payload["secrets"][0]["active_job_id"] is None
    assert payload["consistency"]["ok"] is True


def test_status_endpoint_attaches_waiting_paste_job_id(harness):
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    job_id = "job-waiting-paste"
    _seed_state(
        harness["repo_root"],
        {
            "secrets": [{"name": "ANTHROPIC_API_KEY", "class": "B-human", "cadence_days": 90}],
            "rotations": [
                {
                    "secret_name": "ANTHROPIC_API_KEY",
                    "rotation_id": "rot-waiting",
                    "started_at": now,
                    "last_updated_at": now,
                    "status": "WAITING_FOR_PASTE",
                }
            ],
        },
    )
    with CHECK_JOBS_LOCK:
        CHECK_JOBS[job_id] = {
            "id": job_id,
            "kind": "rotation",
            "status": "running",
            "repo": REPO_NAME,
            "repo_path": str(harness["repo_root"]),
            "secret": "ANTHROPIC_API_KEY",
        }
    try:
        status, body, _ct = _http(harness["port"], f"/api/rotation/status/{REPO_NAME}")
        assert status == HTTPStatus.OK
        payload = json.loads(body)
        assert payload["secrets"][0]["status"] == "WAITING_FOR_PASTE"
        assert payload["secrets"][0]["active_job_id"] == job_id
    finally:
        with CHECK_JOBS_LOCK:
            CHECK_JOBS.pop(job_id, None)


def test_status_endpoint_surfaces_consistency_warning(harness):
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    _seed_state(
        harness["repo_root"],
        {
            "secrets": [{"name": "AUTH_SECRET", "class": "A", "cadence_days": 30}],
            "rotations": [
                {
                    "secret_name": "AUTH_SECRET",
                    "rotation_id": "rot-1",
                    "started_at": now,
                    "completed_at": now,
                    "status": "ROTATED",
                }
            ],
        },
    )
    _seed_log(
        harness["repo_root"],
        [
            {
                "at": now,
                "rotation_id": "rot-1",
                "secret_name": "AUTH_SECRET",
                "step": "HEALTH_CHECK",
                "outcome": "halted",
            }
        ],
    )
    status, body, _ct = _http(harness["port"], f"/api/rotation/status/{REPO_NAME}")

    assert status == HTTPStatus.OK
    payload = json.loads(body)
    assert payload["consistency"]["ok"] is False
    assert payload["consistency"]["warnings"][0]["kind"] == "status_mismatch"


def test_status_endpoint_404s_for_unknown_repo(harness):
    status, _body, _ct = _http(harness["port"], "/api/rotation/status/no-such-repo")
    assert status == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# /api/rotation/history/<repo>
# ---------------------------------------------------------------------------


def test_history_endpoint_returns_recent_first(harness):
    _seed_log(
        harness["repo_root"],
        [
            {"at": "2026-05-01T10:00:00+00:00", "secret_name": "AUTH_SECRET", "step": "ACQUIRED", "outcome": "succeeded"},
            {"at": "2026-05-03T10:00:00+00:00", "secret_name": "AUTH_SECRET", "step": "SOAK", "outcome": "succeeded"},
        ],
    )
    status, body, _ct = _http(harness["port"], f"/api/rotation/history/{REPO_NAME}?limit=5")
    assert status == HTTPStatus.OK
    payload = json.loads(body)
    assert [event["timestamp"] for event in payload["events"]] == [
        "2026-05-03T10:00:00+00:00",
        "2026-05-01T10:00:00+00:00",
    ]


def test_history_endpoint_404s_for_unknown_repo(harness):
    status, _body, _ct = _http(harness["port"], "/api/rotation/history/no-such-repo")
    assert status == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# /api/rotation/receipts/<repo>/<filename>
# ---------------------------------------------------------------------------


def test_receipt_endpoint_serves_markdown(harness):
    _seed_receipt(
        harness["repo_root"],
        "AUTH_SECRET-2026-05-20T120000Z.md",
        "# Rotation verified — `AUTH_SECRET`\n",
    )
    status, body, content_type = _http(
        harness["port"],
        f"/api/rotation/receipts/{REPO_NAME}/AUTH_SECRET-2026-05-20T120000Z.md",
    )
    assert status == HTTPStatus.OK
    assert content_type == "text/markdown"
    assert b"Rotation verified" in body


def test_receipt_endpoint_rejects_path_traversal(harness):
    # Receipt file exists outside the receipts dir.
    (harness["repo_root"] / "data").mkdir(parents=True, exist_ok=True)
    (harness["repo_root"] / "data" / "secret.md").write_text("# elsewhere", encoding="utf-8")
    # Without urllib's normalization the dashboard sees the literal "..".
    # We use raw byte path to be sure traversal is rejected at the handler.
    status, _body, _ct = _http(
        harness["port"],
        f"/api/rotation/receipts/{REPO_NAME}/..%2Fsecret.md",
    )
    assert status == HTTPStatus.NOT_FOUND
    status, _body, _ct = _http(
        harness["port"],
        f"/api/rotation/receipts/{REPO_NAME}/AUTH_SECRET.txt",
    )
    assert status == HTTPStatus.NOT_FOUND


def test_receipt_endpoint_404s_for_unknown_repo(harness):
    status, _body, _ct = _http(
        harness["port"],
        "/api/rotation/receipts/no-such-repo/AUTH_SECRET-2026-05-20T120000Z.md",
    )
    assert status == HTTPStatus.NOT_FOUND


def test_receipt_endpoint_400s_for_missing_filename(harness):
    status, _body, _ct = _http(harness["port"], f"/api/rotation/receipts/{REPO_NAME}/")
    # Trailing slash with no filename should be a clear client error.
    assert status == HTTPStatus.BAD_REQUEST


# ---------------------------------------------------------------------------
# /api/rotation/scaffold/<repo>
# ---------------------------------------------------------------------------


def test_scaffold_handoff_requires_confirmation(harness):
    status, _body, _ct = _http(
        harness["port"],
        f"/api/rotation/scaffold/{REPO_NAME}",
        method="POST",
        body={},
    )
    assert status == HTTPStatus.BAD_REQUEST


def test_scaffold_handoff_returns_command_for_supported_stack(harness):
    (harness["repo_root"] / "package.json").write_text(
        json.dumps({"dependencies": {"next": "14.0.0"}}), encoding="utf-8"
    )
    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/scaffold/{REPO_NAME}",
        method="POST",
        body={"confirmed": True},
    )
    assert status == HTTPStatus.OK
    payload = json.loads(body)
    assert payload["supported"] is True
    assert payload["stack"] == "vercel"
    assert payload["command"] == "claude /secrets-rotation"
    assert payload["working_directory"] == str(harness["repo_root"])
    assert isinstance(payload["next_steps"], list)


def test_scaffold_handoff_reports_unsupported_stack(harness):
    (harness["repo_root"] / "README.md").write_text("nothing here", encoding="utf-8")
    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/scaffold/{REPO_NAME}",
        method="POST",
        body={"confirmed": True},
    )
    assert status == HTTPStatus.OK
    payload = json.loads(body)
    assert payload["supported"] is False


def test_scaffold_handoff_409s_when_already_scaffolded(harness):
    _seed_state(
        harness["repo_root"],
        {
            "secrets": [{"name": "AUTH_SECRET", "class": "A", "cadence_days": 30}],
            "rotations": [],
        },
    )
    (harness["repo_root"] / "package.json").write_text(
        json.dumps({"dependencies": {"next": "14.0.0"}}), encoding="utf-8"
    )
    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/scaffold/{REPO_NAME}",
        method="POST",
        body={"confirmed": True},
    )
    assert status == HTTPStatus.CONFLICT


# ---------------------------------------------------------------------------
# /api/summary — per-repo rotation_state enrichment
# ---------------------------------------------------------------------------


def test_summary_endpoint_attaches_rotation_state_per_repo(harness):
    _seed_state(
        harness["repo_root"],
        {
            "secrets": [{"name": "AUTH_SECRET", "class": "A", "cadence_days": 30}],
            "rotations": [],
        },
    )
    status, body, _ct = _http(harness["port"], "/api/summary")
    assert status == HTTPStatus.OK
    payload = json.loads(body)
    repo = next(item for item in payload["repos"] if item["repo"] == REPO_NAME)
    assert repo["rotation_state"]["scaffolded"] is True
    assert repo["rotation_state"]["secret_count"] == 1
