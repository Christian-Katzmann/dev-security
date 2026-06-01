"""Read-path resilience for the dashboard's GET surface (S-006).

`do_GET` must mirror the `do_POST` / `do_DELETE` convention: any unhandled
exception in a GET route — a corrupt history DB surfacing from
`ObservatoryDB(...)`, or a bug in `dashboard_payload` — becomes a clean JSON 500
with a body, never a raw `BaseHTTPRequestHandler` traceback or a dropped socket.
Removing the wrapper makes these tests fail.
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

import security_observatory.dashboard_server as dashboard_server
from security_observatory.dashboard_server import DashboardHandler


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


@pytest.fixture
def server(tmp_path: Path):
    home = tmp_path / "observatory"
    assets_dir = tmp_path / "assets"
    (home / "db").mkdir(parents=True)
    assets_dir.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    db_path = home / "db" / "observatory.sqlite"

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


def test_get_route_exception_returns_clean_json_500(server, monkeypatch):
    port = int(server)

    # Force the payload builder a GET route depends on to throw — modelling a
    # corrupt-DB surfacing or a dashboard_payload bug. Without the do_GET
    # try/except, this would surface as an unhandled handler error / dropped
    # socket rather than a structured response.
    def _boom(self):  # noqa: ANN001 - test stub
        raise RuntimeError("read path blew up")

    monkeypatch.setattr(
        dashboard_server.ObservatoryDB, "dashboard_payload", _boom, raising=True
    )

    status, payload = _get(port, "/api/summary")

    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    # A real JSON body, not a traceback.
    assert "error" in payload
    assert "read path blew up" in payload["error"]
