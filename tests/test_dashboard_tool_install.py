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


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def harness(tmp_path: Path):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    handler = type(
        "BoundHandler",
        (DashboardHandler,),
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


@pytest.fixture(autouse=True)
def fail_if_package_manager_process_is_started(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_process_start(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("guardrail tests must not start a package-manager subprocess")

    monkeypatch.setattr("security_observatory.dashboard_server.subprocess.run", deny_process_start)


def _post_json(port: int, path: str, body: dict[str, object]) -> tuple[int, bytes, str]:
    data = json.dumps(body).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Content-Length": str(len(data))},
    )
    try:
        with urlopen(request, timeout=5) as resp:
            return resp.status, resp.read(), resp.headers.get_content_type()
    except HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get_content_type()


def test_package_install_requires_confirmation(harness: int):
    status, body, _content_type = _post_json(
        harness,
        "/api/tools/install-via-pkg",
        {"toolId": "legitify"},
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert b"Confirm package install" in body


def test_package_install_rejects_unknown_tool(harness: int):
    status, body, _content_type = _post_json(
        harness,
        "/api/tools/install-via-pkg",
        {"toolId": "not-a-real-tool", "confirmPackageInstall": True},
    )

    assert status == HTTPStatus.NOT_FOUND
    assert b"not in catalog" in body


def test_package_install_rejects_manual_method(harness: int):
    # malcontent has install.method == "manual" and is not eligible for
    # /api/tools/install-via-pkg; the dispatcher should refuse it cleanly.
    status, body, _content_type = _post_json(
        harness,
        "/api/tools/install-via-pkg",
        {"toolId": "malcontent", "confirmPackageInstall": True},
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert b"install method 'manual' cannot be automated" in body


def test_homebrew_install_missing_brew_prereq(
    harness: int,
    monkeypatch: pytest.MonkeyPatch,
):
    # `legitify` is a homebrew tool; if brew is not on PATH the server should
    # 500 with the brew install hint before any subprocess starts.
    monkeypatch.setattr(
        "security_observatory.dashboard_server.shutil.which",
        lambda program: None,
    )

    status, body, _content_type = _post_json(
        harness,
        "/api/tools/install-via-pkg",
        {"toolId": "legitify", "confirmPackageInstall": True},
    )

    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert b"Homebrew is not installed" in body


def test_uv_tool_install_missing_uv_prereq(
    harness: int,
    monkeypatch: pytest.MonkeyPatch,
):
    # `checkov` is a uv-tool tool; if uv is not on PATH the server should
    # 500 with the uv install hint before any subprocess starts.
    monkeypatch.setattr(
        "security_observatory.dashboard_server.shutil.which",
        lambda program: None,
    )

    status, body, _content_type = _post_json(
        harness,
        "/api/tools/install-via-pkg",
        {"toolId": "checkov", "confirmPackageInstall": True},
    )

    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert b"uv is not installed" in body


def test_recheck_install_state_returns_tool(harness: int):
    # The "Mark installed" affordance for manual-install tools hits this
    # endpoint to re-run install-state detection without launching any
    # subprocess. malcontent's binary is unlikely to be on PATH during tests,
    # so the refreshed state should remain `missing`, but the response shape
    # must contain a tool envelope.
    status, body, content_type = _post_json(
        harness,
        "/api/tools/recheck-install-state",
        {"toolId": "malcontent"},
    )

    assert status == HTTPStatus.OK
    assert content_type == "application/json"
    payload = json.loads(body)
    assert payload["tool"]["id"] == "malcontent"
    assert "install_state" in payload["tool"]


def test_recheck_install_state_requires_tool_id(harness: int):
    status, body, _content_type = _post_json(
        harness,
        "/api/tools/recheck-install-state",
        {},
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert b"Tool id is required" in body


def test_recheck_install_state_rejects_unknown_tool(harness: int):
    status, body, _content_type = _post_json(
        harness,
        "/api/tools/recheck-install-state",
        {"toolId": "not-a-real-tool"},
    )

    assert status == HTTPStatus.NOT_FOUND
    assert b"not in catalog" in body
