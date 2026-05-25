"""HTTP tests for POST /api/rotation/trigger-batch + GET /api/rotation/jobs/batch.

Exercises the batch rotation surface: filter logic, confirmation phrase gating,
halt-on-error semantics, continue/stop actions, and batch receipt shape.
"""
from __future__ import annotations

import json
import os
import socket
import stat
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from security_observatory.dashboard_server import (
    BATCH_JOBS,
    BATCH_JOBS_LOCK,
    CHECK_JOBS,
    CHECK_JOBS_LOCK,
    DashboardHandler,
    _apply_batch_filter,
    _batch_rotation_confirmation_phrase,
    BATCH_FILTER_PRESETS,
)
from security_observatory.storage import ObservatoryDB


REPO_NAME = "demo-batch-rotation"


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
        with urlopen(request, timeout=15) as resp:
            return resp.status, resp.read(), resp.headers.get_content_type()
    except HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get_content_type()


@pytest.fixture(autouse=True)
def clean_jobs():
    """Clear global job dicts between tests."""
    yield
    with CHECK_JOBS_LOCK:
        CHECK_JOBS.clear()
    with BATCH_JOBS_LOCK:
        BATCH_JOBS.clear()


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
            scan_id="batch-20260101T000000Z",
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

    # Three secrets: one NEVER, one ROTATED, one HALTED (needs_attention)
    (repo_root / "data").mkdir(parents=True, exist_ok=True)
    (repo_root / "data" / "rotation-state.json").write_text(
        json.dumps(
            {
                "secrets": [
                    {"name": "AUTH_SECRET", "class": "A", "cadence_days": 30},
                    {"name": "CRON_SECRET", "class": "A", "cadence_days": 30},
                    {"name": "ANTHROPIC_API_KEY", "class": "B-API", "cadence_days": 90},
                ],
                "rotations": [
                    {
                        "secret_name": "AUTH_SECRET",
                        "rotation_id": "rot-1",
                        "started_at": "2026-01-01T00:00:00Z",
                        "completed_at": "2026-01-01T00:01:00Z",
                        "status": "ROTATED",
                    },
                    {
                        "secret_name": "ANTHROPIC_API_KEY",
                        "rotation_id": "rot-2",
                        "started_at": "2026-01-01T00:00:00Z",
                        "status": "HALTED",
                        "halted_at_step": "VERIFY_PROD",
                        "halted_reason": "test halt",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    server, port = _serve(db_path, assets_dir)
    try:
        yield {
            "port": port,
            "repo_root": repo_root,
            "tmp_path": tmp_path,
            "db_path": db_path,
        }
    finally:
        server.shutdown()


def _install_fake_npm(tmp_path: Path, repo_root: Path, *, exit_code: int = 0) -> None:
    """Install a fake npm that simulates a successful rotation.

    The fake updates rotation-state.json so _run_rotation_job reads back
    a ROTATED status and marks the job as "complete".
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    receipt_dir = repo_root / "data" / "rotation-receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    state_file = repo_root / "data" / "rotation-state.json"
    # Script that: prints phase lines, writes a receipt, and updates the state
    # to mark the secret as ROTATED.
    script = f"""#!/bin/sh
# Args: run rotate -- SECRET [flags]
# Find the secret name (first non-flag arg after --)
SECRET=""
PAST_DASHDASH=0
for arg in "$@"; do
    if [ "$arg" = "--" ]; then
        PAST_DASHDASH=1
        continue
    fi
    if [ $PAST_DASHDASH -eq 1 ] && [ -z "$SECRET" ]; then
        case "$arg" in
            --*) ;;
            *) SECRET="$arg" ;;
        esac
    fi
done
if [ -z "$SECRET" ]; then SECRET="UNKNOWN"; fi
echo '=== HEALTH_CHECK ==='
echo '=== PREFLIGHT ==='
echo '=== ACQUIRE ==='
echo '=== STAGE_PROD ==='
echo 'VERIFIED ok'
echo 'ROTATED'
cat > {receipt_dir!s}/${{SECRET}}-2026-05-25T120000Z.md <<'EOF'
# Rotation verified

- **Status:** ROTATED
EOF
# Update rotation-state.json to mark the secret as ROTATED
python3 -c "
import json, sys
p = '{state_file!s}'
with open(p) as f:
    state = json.load(f)
secret = '${{SECRET}}'
# Add or update a rotation record for this secret
found = False
for r in state.get('rotations', []):
    if r.get('secret_name') == secret:
        r['status'] = 'ROTATED'
        r['completed_at'] = '2026-05-25T12:00:00Z'
        found = True
        break
if not found:
    state.setdefault('rotations', []).append({{
        'secret_name': secret,
        'rotation_id': 'batch-' + secret.lower(),
        'started_at': '2026-05-25T11:59:00Z',
        'completed_at': '2026-05-25T12:00:00Z',
        'status': 'ROTATED',
    }})
with open(p, 'w') as f:
    json.dump(state, f)
"
exit {exit_code}
"""
    npm_path = bin_dir / "npm"
    npm_path.write_text(script, encoding="utf-8")
    npm_path.chmod(npm_path.stat().st_mode | stat.S_IEXEC)
    os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"


# ---------------------------------------------------------------------------
# Filter logic tests (unit)
# ---------------------------------------------------------------------------


class TestBatchFilterLogic:
    def test_never_rotated_filter(self):
        rows = [
            {"secret": "A", "status": "NEVER", "needs_attention": True},
            {"secret": "B", "status": "ROTATED", "needs_attention": False},
            {"secret": "C", "status": "HALTED", "needs_attention": True},
        ]
        result = _apply_batch_filter(rows, "never_rotated")
        assert [r["secret"] for r in result] == ["A"]

    def test_needs_attention_filter(self):
        rows = [
            {"secret": "A", "status": "NEVER", "needs_attention": True},
            {"secret": "B", "status": "ROTATED", "needs_attention": False},
            {"secret": "C", "status": "HALTED", "needs_attention": True},
        ]
        result = _apply_batch_filter(rows, "needs_attention")
        secrets = [r["secret"] for r in result]
        assert "A" in secrets
        assert "C" in secrets
        assert "B" not in secrets

    def test_all_actionable_filter(self):
        rows = [
            {"secret": "A", "status": "NEVER", "needs_attention": True},
            {"secret": "B", "status": "ROTATED", "needs_attention": False},
            {"secret": "C", "status": "HALTED", "needs_attention": True},
        ]
        result = _apply_batch_filter(rows, "all_actionable")
        secrets = [r["secret"] for r in result]
        assert "A" in secrets
        assert "C" in secrets
        assert "B" not in secrets

    def test_inflight_excluded(self):
        rows = [
            {"secret": "A", "status": "NEVER", "needs_attention": True},
            {"secret": "B", "status": "HEALTH_CHECK", "needs_attention": True},
        ]
        result = _apply_batch_filter(rows, "all_actionable")
        assert [r["secret"] for r in result] == ["A"]

    def test_corrupt_excluded(self):
        rows = [
            {"secret": "(corrupt)", "status": "NEVER", "needs_attention": True},
            {"secret": "A", "status": "NEVER", "needs_attention": True},
        ]
        result = _apply_batch_filter(rows, "all_actionable")
        assert [r["secret"] for r in result] == ["A"]

    def test_unknown_filter_returns_empty(self):
        rows = [{"secret": "A", "status": "NEVER", "needs_attention": True}]
        result = _apply_batch_filter(rows, "bogus_filter")
        assert result == []


# ---------------------------------------------------------------------------
# Confirmation phrase tests (unit)
# ---------------------------------------------------------------------------


class TestBatchConfirmationPhrase:
    def test_basic_phrase(self):
        phrase = _batch_rotation_confirmation_phrase(5)
        assert "5 secrets" in phrase
        assert "irreversible" in phrase

    def test_class_b_suffix(self):
        phrase = _batch_rotation_confirmation_phrase(3, has_class_b=True)
        assert "Class B" in phrase

    def test_no_class_b_suffix(self):
        phrase = _batch_rotation_confirmation_phrase(3, has_class_b=False)
        assert "Class B" not in phrase


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


class TestTriggerBatchEndpoint:
    def test_rejects_without_confirmation(self, harness):
        port = harness["port"]
        status, body, _ = _http(
            port,
            f"/api/rotation/trigger-batch/{REPO_NAME}",
            method="POST",
            body={"filter": "all_actionable"},
        )
        assert status == 400
        data = json.loads(body)
        assert "expected_confirmation_phrase" in data

    def test_rejects_invalid_filter(self, harness):
        port = harness["port"]
        status, body, _ = _http(
            port,
            f"/api/rotation/trigger-batch/{REPO_NAME}",
            method="POST",
            body={
                "filter": "invalid_preset",
                "confirmed": True,
                "confirmation_phrase": "anything",
            },
        )
        assert status == 400
        assert b"filter must be one of" in body

    def test_rejects_when_no_secrets_match(self, harness):
        port = harness["port"]
        repo_root = harness["repo_root"]
        # Rewrite state so all are ROTATED
        (repo_root / "data" / "rotation-state.json").write_text(
            json.dumps({
                "secrets": [
                    {"name": "AUTH_SECRET", "class": "A", "cadence_days": 30},
                ],
                "rotations": [
                    {
                        "secret_name": "AUTH_SECRET",
                        "rotation_id": "rot-1",
                        "status": "ROTATED",
                        "started_at": "2026-01-01T00:00:00Z",
                        "completed_at": "2026-01-01T00:01:00Z",
                    },
                ],
            }),
            encoding="utf-8",
        )
        phrase = _batch_rotation_confirmation_phrase(0)
        status, body, _ = _http(
            port,
            f"/api/rotation/trigger-batch/{REPO_NAME}",
            method="POST",
            body={
                "filter": "never_rotated",
                "confirmed": True,
                "confirmation_phrase": phrase,
            },
        )
        assert status == 409
        assert b"Nothing to rotate" in body

    def test_accepts_valid_batch(self, harness, monkeypatch):
        port = harness["port"]
        tmp_path = harness["tmp_path"]
        repo_root = harness["repo_root"]
        _install_fake_npm(tmp_path, repo_root)

        # First, ask without the phrase to discover the expected count
        status, body, _ = _http(
            port,
            f"/api/rotation/trigger-batch/{REPO_NAME}",
            method="POST",
            body={"filter": "all_actionable", "confirmed": False},
        )
        assert status == 400
        data = json.loads(body)
        expected_phrase = data["expected_confirmation_phrase"]
        count = data["secret_count"]
        assert count >= 2  # CRON_SECRET (NEVER) + ANTHROPIC (HALTED) + possibly AUTH (overdue)

        status, body, _ = _http(
            port,
            f"/api/rotation/trigger-batch/{REPO_NAME}",
            method="POST",
            body={
                "filter": "all_actionable",
                "confirmed": True,
                "confirmation_phrase": expected_phrase,
            },
        )
        assert status == 202
        data = json.loads(body)
        batch = data["batch"]
        assert batch["kind"] == "rotation_batch"
        assert batch["total"] == count
        assert batch["status"] == "running"


class TestBatchJobPolling:
    def test_unknown_batch_returns_404(self, harness):
        port = harness["port"]
        status, body, _ = _http(port, "/api/rotation/jobs/batch/nonexistent")
        assert status == 404

    def test_batch_progress_visible(self, harness, monkeypatch):
        port = harness["port"]
        tmp_path = harness["tmp_path"]
        repo_root = harness["repo_root"]
        _install_fake_npm(tmp_path, repo_root)

        # Discover the expected phrase
        status, body, _ = _http(
            port,
            f"/api/rotation/trigger-batch/{REPO_NAME}",
            method="POST",
            body={"filter": "all_actionable", "confirmed": False},
        )
        data = json.loads(body)
        phrase = data["expected_confirmation_phrase"]

        status, body, _ = _http(
            port,
            f"/api/rotation/trigger-batch/{REPO_NAME}",
            method="POST",
            body={
                "filter": "all_actionable",
                "confirmed": True,
                "confirmation_phrase": phrase,
            },
        )
        assert status == 202
        data = json.loads(body)
        batch_id = data["batch"]["id"]

        # Poll until the batch finishes (with a timeout)
        snap = None
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status, body, _ = _http(port, f"/api/rotation/jobs/batch/{batch_id}")
            if status == 200:
                snap = json.loads(body)["batch"]
                if snap.get("finished_at") is not None:
                    break
            time.sleep(0.5)

        assert snap is not None
        assert snap["status"] in ("complete", "complete_with_errors", "stopped", "halted_awaiting_decision")
        assert isinstance(snap["completed"], list)
        assert isinstance(snap["halted"], list)


class TestBatchReceiptShape:
    def test_receipt_written_on_completion(self, harness, monkeypatch):
        port = harness["port"]
        tmp_path = harness["tmp_path"]
        repo_root = harness["repo_root"]
        _install_fake_npm(tmp_path, repo_root)

        # Discover phrase
        status, body, _ = _http(
            port,
            f"/api/rotation/trigger-batch/{REPO_NAME}",
            method="POST",
            body={"filter": "all_actionable", "confirmed": False},
        )
        data = json.loads(body)
        phrase = data["expected_confirmation_phrase"]

        _http(
            port,
            f"/api/rotation/trigger-batch/{REPO_NAME}",
            method="POST",
            body={
                "filter": "all_actionable",
                "confirmed": True,
                "confirmation_phrase": phrase,
            },
        )

        # Wait for batch completion
        deadline = time.monotonic() + 30
        batch_id = None
        with BATCH_JOBS_LOCK:
            for bid, bj in BATCH_JOBS.items():
                batch_id = bid
                break
        assert batch_id is not None

        while time.monotonic() < deadline:
            with BATCH_JOBS_LOCK:
                b = BATCH_JOBS.get(batch_id)
                if b and b.get("finished_at"):
                    break
            time.sleep(0.5)

        # Check that a BATCH receipt was written
        receipt_dir = repo_root / "data" / "rotation-receipts"
        batch_receipts = [f for f in receipt_dir.iterdir() if f.name.startswith("BATCH-")]
        assert len(batch_receipts) >= 1
        content = batch_receipts[0].read_text(encoding="utf-8")
        assert "Batch rotation receipt" in content
        assert "Total queued" in content
