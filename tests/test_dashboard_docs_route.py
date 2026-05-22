import socket
import threading
from http import HTTPStatus
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from http.server import ThreadingHTTPServer

from security_observatory.dashboard_server import DashboardHandler


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(tmp_path: Path):
    port = _free_port()
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    handler = type(
        "BoundHandler",
        (DashboardHandler,),
        {"db_path": tmp_path / "db.sqlite", "assets_dir": assets_dir},
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _http(port: int, path: str) -> tuple[int, bytes, str]:
    try:
        with urlopen(Request(f"http://127.0.0.1:{port}{path}"), timeout=5) as resp:
            return resp.status, resp.read(), resp.headers.get_content_type()
    except HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get_content_type()


def test_docs_route_serves_real_in_repo_markdown(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    assert (repo_root / "docs" / "iocs.md").is_file(), "fixture missing"

    server, port = _serve(tmp_path)
    try:
        status, body, content_type = _http(port, "/docs/iocs.md")
    finally:
        server.shutdown()

    assert status == HTTPStatus.OK
    assert content_type == "text/markdown"
    assert body.startswith((repo_root / "docs" / "iocs.md").read_bytes()[:32])


def test_docs_route_404s_when_file_missing(tmp_path):
    server, port = _serve(tmp_path)
    try:
        status, _body, _ct = _http(port, "/docs/does-not-exist.md")
    finally:
        server.shutdown()
    assert status == HTTPStatus.NOT_FOUND


def test_docs_route_rejects_path_traversal(tmp_path):
    server, port = _serve(tmp_path)
    try:
        status, _body, _ct = _http(port, "/docs/../pyproject.toml")
    finally:
        server.shutdown()
    assert status == HTTPStatus.NOT_FOUND
