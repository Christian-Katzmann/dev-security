"""HTTP tests for POST /api/rotation/trigger + GET /api/rotation/jobs.

These exercise the Tier 5R refuse-by-default surface: confirmation phrase
gating, the `--no-soak` acknowledgement gate, secret-name validation, the
DASHBOARD_TRIGGER audit-log line that lands in `data/rotation-log.jsonl`,
and the polled-job snapshot shape (without actually shelling out to npm —
we substitute a fake `npm` on PATH so the subprocess returns immediately
and the test can read the receipt the fake produced).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import socket
import stat
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from security_observatory.dashboard_server import (
    CHECK_JOBS,
    CHECK_JOBS_LOCK,
    DashboardHandler,
    _rotation_confirmation_phrase,
)
from security_observatory.storage import ObservatoryDB


REPO_NAME = "demo-rotation-trigger"


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


def _http(
    port: int,
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
) -> tuple[int, bytes, str]:
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(data))
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urlopen(request, timeout=5) as resp:
            return resp.status, resp.read(), resp.headers.get_content_type()
    except HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get_content_type()


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db_path = db_dir / "observatory.sqlite"
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    repo_root = tmp_path / "fake-repo"
    repo_root.mkdir()

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

    # Seed a rotation state with one ROTATED secret so trigger requests pass
    # the "is this secret tracked?" gate without further fixture work.
    completed = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=2)).isoformat()
    (repo_root / "data").mkdir(parents=True, exist_ok=True)
    (repo_root / "data" / "rotation-state.json").write_text(
        json.dumps(
            {
                "secrets": [{"name": "AUTH_SECRET", "class": "A", "cadence_days": 30}],
                "rotations": [
                    {
                        "secret_name": "AUTH_SECRET",
                        "rotation_id": "rot-existing",
                        "started_at": completed,
                        "completed_at": completed,
                        "status": "ROTATED",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    server, port = _serve(db_path, assets_dir)
    try:
        yield {"port": port, "repo_root": repo_root, "tmp_path": tmp_path}
    finally:
        server.shutdown()


def _install_fake_npm(tmp_path: Path, repo_root: Path, *, exit_code: int = 0, write_receipt: bool = True) -> None:
    """Drop a fake `npm` on PATH. Behaves like a noop rotate that writes a receipt.

    The test does NOT exercise the real rotation pipeline (the skill is shelled
    out to from a real session). What we need is a deterministic stand-in so we
    can prove the dashboard wires the subprocess + receipt fetch correctly.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    receipt_dir = repo_root / "data" / "rotation-receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / "AUTH_SECRET-2026-05-24T120000Z.md"
    script = (
        "#!/bin/sh\n"
        "echo '=== HEALTH_CHECK ==='\n"
        "echo '=== PREFLIGHT ==='\n"
        "echo '=== ACQUIRE ==='\n"
        "echo '=== STAGE_PROD ==='\n"
        "echo 'VERIFIED ok'\n"
    )
    if write_receipt:
        script += (
            f"cat > {receipt_path!s} <<'EOF'\n"
            "# Rotation verified — `AUTH_SECRET`\n\n"
            "- **Status:** ROTATED\n"
            "- **Action: completed · Severity: info**\n"
            "- **Provider check:** ✓ Class A self-generated\n"
            "- **Application probe:** ✓ stub probe returned ok\n"
            "- **Soak test:** ✓ 15 min window, 0 new auth-related errors above baseline\n"
            "- **Old key status:** replaced\n"
            "- **Audit trail:** rotation_id `fake-test-uuid`, events emitted to `rotation-log.jsonl`\n"
            "- **New key fingerprint:** `sha256:deadbeef…`\n\n"
            "Scope of this verification: stub. Outside scope: stub.\n"
            "EOF\n"
        )
    script += f"exit {exit_code}\n"
    npm_path = bin_dir / "npm"
    npm_path.write_text(script, encoding="utf-8")
    os.chmod(npm_path, npm_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def npm_on_path(harness, monkeypatch: pytest.MonkeyPatch):
    _install_fake_npm(harness["tmp_path"], harness["repo_root"])
    bin_dir = harness["tmp_path"] / "bin"
    monkeypatch.setenv("PATH", f"{bin_dir!s}:{os.environ.get('PATH', '')}")
    return harness


# ---------------------------------------------------------------------------
# Confirmation gating
# ---------------------------------------------------------------------------


def test_trigger_refuses_without_confirmation(harness):
    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/trigger/{REPO_NAME}",
        method="POST",
        body={"secret": "AUTH_SECRET"},
    )
    assert status == HTTPStatus.BAD_REQUEST
    payload = json.loads(body)
    assert "confirmation phrase" in payload["error"].lower()
    assert payload["expected_confirmation_phrase"] == (
        _rotation_confirmation_phrase("AUTH_SECRET")
    )


def test_trigger_refuses_wrong_phrase(harness):
    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/trigger/{REPO_NAME}",
        method="POST",
        body={
            "secret": "AUTH_SECRET",
            "confirmed": True,
            "confirmation_phrase": "Yes do it.",
        },
    )
    assert status == HTTPStatus.BAD_REQUEST
    payload = json.loads(body)
    assert payload["expected_confirmation_phrase"] == (
        "Yes, rotate `AUTH_SECRET` and accept the irreversible provider-side change."
    )


def test_trigger_refuses_invalid_secret_name(harness):
    status, _body, _ct = _http(
        harness["port"],
        f"/api/rotation/trigger/{REPO_NAME}",
        method="POST",
        body={
            "secret": "lowercase",
            "confirmed": True,
            "confirmation_phrase": _rotation_confirmation_phrase("lowercase"),
        },
    )
    assert status == HTTPStatus.BAD_REQUEST


def test_trigger_refuses_no_soak_without_ack(harness):
    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/trigger/{REPO_NAME}",
        method="POST",
        body={
            "secret": "AUTH_SECRET",
            "confirmed": True,
            "confirmation_phrase": _rotation_confirmation_phrase("AUTH_SECRET"),
            "options": {"no_soak": True},
        },
    )
    assert status == HTTPStatus.BAD_REQUEST
    payload = json.loads(body)
    assert "no-soak" in payload["error"].lower()


def test_trigger_refuses_unknown_secret(harness):
    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/trigger/{REPO_NAME}",
        method="POST",
        body={
            "secret": "NOT_TRACKED",
            "confirmed": True,
            "confirmation_phrase": _rotation_confirmation_phrase("NOT_TRACKED"),
        },
    )
    assert status == HTTPStatus.NOT_FOUND
    payload = json.loads(body)
    assert "NOT_TRACKED" in payload["error"] or "isn't tracked" in payload["error"]
    assert "AUTH_SECRET" in payload["known_secrets"]


def test_trigger_404s_for_unknown_repo(harness):
    status, _body, _ct = _http(
        harness["port"],
        "/api/rotation/trigger/no-such-repo",
        method="POST",
        body={
            "secret": "AUTH_SECRET",
            "confirmed": True,
            "confirmation_phrase": _rotation_confirmation_phrase("AUTH_SECRET"),
        },
    )
    assert status == HTTPStatus.NOT_FOUND


def test_trigger_409s_when_rotation_not_scaffolded(tmp_path: Path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db_path = db_dir / "observatory.sqlite"
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    repo_root = tmp_path / "fake-repo"
    repo_root.mkdir()
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
        status, _body, _ct = _http(
            port,
            f"/api/rotation/trigger/{REPO_NAME}",
            method="POST",
            body={
                "secret": "AUTH_SECRET",
                "confirmed": True,
                "confirmation_phrase": _rotation_confirmation_phrase("AUTH_SECRET"),
            },
        )
        assert status == HTTPStatus.CONFLICT
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# Audit log + job lifecycle
# ---------------------------------------------------------------------------


def _wait_terminal(port: int, job_id: str, *, timeout: float = 5.0) -> dict:
    """Poll the job endpoint until the snapshot becomes terminal."""
    import time as _time

    deadline = _time.time() + timeout
    last: dict | None = None
    while _time.time() < deadline:
        status, body, _ct = _http(port, f"/api/rotation/jobs/{job_id}")
        assert status == HTTPStatus.OK
        last = json.loads(body)["job"]
        if last["status"] in ("complete", "halted", "failed"):
            return last
        _time.sleep(0.1)
    assert last is not None
    raise AssertionError(f"Job {job_id} did not reach terminal state: {last}")


def test_trigger_writes_dashboard_trigger_audit_event(npm_on_path):
    harness = npm_on_path
    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/trigger/{REPO_NAME}",
        method="POST",
        body={
            "secret": "AUTH_SECRET",
            "confirmed": True,
            "confirmation_phrase": _rotation_confirmation_phrase("AUTH_SECRET"),
        },
    )
    assert status == HTTPStatus.ACCEPTED
    payload = json.loads(body)
    job = payload["job"]
    assert job["kind"] == "rotation"
    assert job["secret"] == "AUTH_SECRET"

    # Wait for the fake-npm subprocess to finish.
    terminal = _wait_terminal(harness["port"], job["id"])
    assert terminal["status"] == "complete"
    assert terminal["receipt_filename"] == "AUTH_SECRET-2026-05-24T120000Z.md"
    assert terminal["receipt_url"].endswith(
        "AUTH_SECRET-2026-05-24T120000Z.md"
    )
    assert terminal["phase"] == "verified"
    assert terminal["exit_code"] == 0

    # The DASHBOARD_TRIGGER line landed in the audit log.
    log_path = harness["repo_root"] / "data" / "rotation-log.jsonl"
    lines = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    triggers = [event for event in lines if event.get("step") == "DASHBOARD_TRIGGER"]
    assert len(triggers) == 1
    audit = triggers[0]
    assert audit["secret_name"] == "AUTH_SECRET"
    assert audit["outcome"] == "initiated"
    assert "job_id" in audit["note"]
    assert audit["options"]["no_soak"] is False


def test_trigger_job_snapshot_404s_for_unknown_id(harness):
    status, _body, _ct = _http(harness["port"], "/api/rotation/jobs/no-such-id")
    assert status == HTTPStatus.NOT_FOUND


def test_trigger_audit_event_surfaces_in_rotation_history(npm_on_path):
    harness = npm_on_path
    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/trigger/{REPO_NAME}",
        method="POST",
        body={
            "secret": "AUTH_SECRET",
            "confirmed": True,
            "confirmation_phrase": _rotation_confirmation_phrase("AUTH_SECRET"),
        },
    )
    assert status == HTTPStatus.ACCEPTED
    job = json.loads(body)["job"]
    _wait_terminal(harness["port"], job["id"])

    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/history/{REPO_NAME}?limit=5",
    )
    assert status == HTTPStatus.OK
    events = json.loads(body)["events"]
    steps = [event.get("step") for event in events]
    assert "DASHBOARD_TRIGGER" in steps


# ---------------------------------------------------------------------------
# Concurrency gate (409 when rotation already in flight)
# ---------------------------------------------------------------------------


def test_trigger_409s_when_rotation_state_is_inflight(harness):
    """If rotation-state.json shows an in-flight status, the trigger is refused."""
    repo_root = harness["repo_root"]
    (repo_root / "data" / "rotation-state.json").write_text(
        json.dumps(
            {
                "secrets": [{"name": "AUTH_SECRET", "class": "A", "cadence_days": 30}],
                "rotations": [
                    {
                        "secret_name": "AUTH_SECRET",
                        "rotation_id": "rot-inflight",
                        "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                        "completed_at": None,
                        "status": "IN_SOAK",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    status, body, _ct = _http(
        harness["port"],
        f"/api/rotation/trigger/{REPO_NAME}",
        method="POST",
        body={
            "secret": "AUTH_SECRET",
            "confirmed": True,
            "confirmation_phrase": _rotation_confirmation_phrase("AUTH_SECRET"),
        },
    )
    assert status == HTTPStatus.CONFLICT
    payload = json.loads(body)
    assert "already in progress" in payload["error"].lower()
    assert "IN_SOAK" in payload["error"]


def test_trigger_409s_when_check_jobs_has_running_job(harness):
    """If CHECK_JOBS already holds a non-terminal job for this repo+secret, refuse."""
    fake_job_id = "fake-running-01"
    with CHECK_JOBS_LOCK:
        CHECK_JOBS[fake_job_id] = {
            "id": fake_job_id,
            "kind": "rotation",
            "status": "running",
            "repo": REPO_NAME,
            "secret": "AUTH_SECRET",
        }
    try:
        status, body, _ct = _http(
            harness["port"],
            f"/api/rotation/trigger/{REPO_NAME}",
            method="POST",
            body={
                "secret": "AUTH_SECRET",
                "confirmed": True,
                "confirmation_phrase": _rotation_confirmation_phrase("AUTH_SECRET"),
            },
        )
        assert status == HTTPStatus.CONFLICT
        payload = json.loads(body)
        assert "already in progress" in payload["error"].lower()
        assert payload["job_id"] == fake_job_id
    finally:
        with CHECK_JOBS_LOCK:
            CHECK_JOBS.pop(fake_job_id, None)
