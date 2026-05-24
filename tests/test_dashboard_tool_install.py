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
def fail_if_brew_process_is_started(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_process_start(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("guardrail tests must not start Homebrew")

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


def test_homebrew_install_requires_confirmation(harness: int):
    status, body, _content_type = _post_json(
        harness,
        "/api/tools/install-via-pkg",
        {"toolId": "legitify"},
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert b"Confirm Homebrew install" in body


def test_homebrew_install_rejects_non_homebrew_tool(harness: int):
    status, body, _content_type = _post_json(
        harness,
        "/api/tools/install-via-pkg",
        {"toolId": "checkov", "confirmHomebrewInstall": True},
    )

    assert status == HTTPStatus.BAD_REQUEST
    assert b"is not a Homebrew install" in body


def test_homebrew_install_rejects_unknown_tool(harness: int):
    status, body, _content_type = _post_json(
        harness,
        "/api/tools/install-via-pkg",
        {"toolId": "not-a-real-tool", "confirmHomebrewInstall": True},
    )

    assert status == HTTPStatus.NOT_FOUND
    assert b"not in catalog" in body
