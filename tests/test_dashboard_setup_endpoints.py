"""HTTP-level tests for the setup-card endpoints.

Verifies routing, JSON contract, and probe-result envelope. Tool-config
persistence is exercised via a tmp HOME; the probe handler is stubbed so we
don't shell out during the test (the runner module itself is covered by
``tests/test_setup_runner.py``).
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

from security_observatory import dashboard_server
from security_observatory.setup_runner import ProbeResult


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(tmp_path / "obs-home"))
    return tmp_path / "obs-home"


@pytest.fixture
def harness(tmp_path: Path, isolated_home: Path):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    handler = type(
        "BoundHandler",
        (dashboard_server.DashboardHandler,),
        {"db_path": tmp_path / "observatory.sqlite", "assets_dir": assets_dir},
    )
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()


def _request(
    port: int,
    path: str,
    *,
    method: str,
    body: dict[str, object] | None = None,
) -> tuple[int, dict[str, object] | bytes]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if data is not None:
        headers["Content-Length"] = str(len(data))
    request = Request(f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=5) as resp:
            payload = resp.read()
            try:
                return resp.status, json.loads(payload)
            except json.JSONDecodeError:
                return resp.status, payload
    except HTTPError as exc:
        payload = exc.read()
        try:
            return exc.code, json.loads(payload)
        except json.JSONDecodeError:
            return exc.code, payload


def test_setup_config_roundtrip(harness: int):
    # Save
    status, payload = _request(
        harness,
        "/api/tools/malcontent/setup/config",
        method="POST",
        body={"values": {"artifact_cache_dir": "/tmp/x"}},
    )
    assert status == HTTPStatus.OK
    assert payload["stored"] is True
    assert payload["values"] == {"artifact_cache_dir": "/tmp/x"}

    # Read
    status, payload = _request(harness, "/api/tools/malcontent/setup/config", method="GET")
    assert status == HTTPStatus.OK
    assert payload["values"] == {"artifact_cache_dir": "/tmp/x"}

    # Forget
    status, payload = _request(harness, "/api/tools/malcontent/setup/config", method="DELETE")
    assert status == HTTPStatus.OK
    assert payload["removed"] is True
    assert payload["values"] == {}


def test_setup_config_rejects_non_object_body(harness: int):
    status, payload = _request(
        harness,
        "/api/tools/malcontent/setup/config",
        method="POST",
        body={"values": "not-an-object"},
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert "object" in payload["error"]


def test_setup_probe_runs_runner_and_returns_envelope(
    harness: int, monkeypatch: pytest.MonkeyPatch
):
    fake = ProbeResult(
        success=True,
        summary="Probe succeeded.",
        output="line1\nline2",
        command="legitify analyze --repository Legit-Labs/legitify",
        returncode=0,
        duration_seconds=None,
    )

    def fake_run(tool_id: str) -> ProbeResult:  # noqa: ARG001
        return fake

    monkeypatch.setattr(dashboard_server, "run_setup_probe", fake_run)
    status, payload = _request(harness, "/api/tools/legitify/setup/probe", method="POST")
    assert status == HTTPStatus.OK
    assert payload["tool_id"] == "legitify"
    assert payload["success"] is True
    assert payload["summary"] == "Probe succeeded."
    assert "legitify analyze" in payload["command"]


def test_setup_probe_returns_400_for_unknown_tool(
    harness: int, monkeypatch: pytest.MonkeyPatch
):
    from security_observatory.setup_runner import SetupRunnerError

    def fake_run(tool_id: str) -> ProbeResult:  # noqa: ARG001
        raise SetupRunnerError("Tool 'nope' is not in the catalog.")

    monkeypatch.setattr(dashboard_server, "run_setup_probe", fake_run)
    status, payload = _request(harness, "/api/tools/nope/setup/probe", method="POST")
    assert status == HTTPStatus.BAD_REQUEST
    assert "not in the catalog" in payload["error"]


def test_setup_routes_reject_malformed_tool_id(harness: int):
    status, _payload = _request(
        harness,
        "/api/tools/bad%20id/setup/probe",
        method="POST",
    )
    assert status == HTTPStatus.NOT_FOUND
