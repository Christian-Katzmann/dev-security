"""HTTP-level tests for the credential-storage endpoints.

Covers the dispatch + JSON contract without touching the real Keychain — the
underlying ``credentials`` module is exercised end-to-end by
``tests/test_credentials.py`` on macOS. These tests stub the four module-level
functions so they run on every platform and never trigger a Keychain prompt
during CI.
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


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(autouse=True)
def stub_keychain(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """In-memory stub for the Keychain-backed credential layer."""

    store: dict[str, dict[str, str]] = {}

    def _list(tool_id: str) -> list[str]:
        return sorted(store.get(tool_id, {}))

    def _list_all() -> dict[str, list[str]]:
        return {tool: sorted(keys) for tool, keys in store.items() if keys}

    def _store(tool_id: str, key: str, value: str) -> None:
        store.setdefault(tool_id, {})[key] = value

    def _delete(tool_id: str, key: str) -> bool:
        existed = key in store.get(tool_id, {})
        if existed:
            del store[tool_id][key]
            if not store[tool_id]:
                del store[tool_id]
        return existed

    monkeypatch.setattr(dashboard_server, "keychain_is_supported", lambda: True)
    monkeypatch.setattr(dashboard_server, "list_credentials", _list)
    monkeypatch.setattr(dashboard_server, "list_all_credentials", _list_all)
    monkeypatch.setattr(dashboard_server, "store_credential", _store)
    monkeypatch.setattr(dashboard_server, "delete_credential", _delete)
    return store


@pytest.fixture
def harness(tmp_path: Path):
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


def test_store_credential_returns_stored_flag_without_value(harness: int):
    status, payload = _request(
        harness,
        "/api/tools/legitify/credentials",
        method="POST",
        body={"key": "SCM_TOKEN", "value": "ghp_secret_value_123"},
    )
    assert status == HTTPStatus.OK
    assert isinstance(payload, dict)
    assert payload["stored"] is True
    assert payload["tool_id"] == "legitify"
    assert payload["key"] == "SCM_TOKEN"
    assert payload["keys"] == ["SCM_TOKEN"]
    # The endpoint must never echo the value back to the caller.
    assert "value" not in payload
    assert "ghp_secret_value_123" not in json.dumps(payload)


def test_list_credential_keys_for_tool(harness: int, stub_keychain: dict[str, dict[str, str]]):
    stub_keychain.update({"legitify": {"SCM_TOKEN": "x", "BACKUP": "y"}})
    status, payload = _request(harness, "/api/tools/legitify/credentials/keys", method="GET")
    assert status == HTTPStatus.OK
    assert isinstance(payload, dict)
    assert payload["tool_id"] == "legitify"
    assert sorted(payload["keys"]) == ["BACKUP", "SCM_TOKEN"]


def test_list_all_credentials_returns_tool_map(harness: int, stub_keychain: dict[str, dict[str, str]]):
    stub_keychain.update({"legitify": {"SCM_TOKEN": "x"}})
    status, payload = _request(harness, "/api/tools/credentials", method="GET")
    assert status == HTTPStatus.OK
    assert isinstance(payload, dict)
    assert payload["tools"] == {"legitify": ["SCM_TOKEN"]}


def test_delete_credential_reports_existence(harness: int, stub_keychain: dict[str, dict[str, str]]):
    stub_keychain.update({"legitify": {"SCM_TOKEN": "x"}})
    status, payload = _request(
        harness, "/api/tools/legitify/credentials/SCM_TOKEN", method="DELETE"
    )
    assert status == HTTPStatus.OK
    assert isinstance(payload, dict)
    assert payload["deleted"] is True
    assert payload["keys"] == []

    # Second delete is a clean no-op.
    status, payload = _request(
        harness, "/api/tools/legitify/credentials/SCM_TOKEN", method="DELETE"
    )
    assert status == HTTPStatus.OK
    assert isinstance(payload, dict)
    assert payload["deleted"] is False


def test_store_requires_key_and_value(harness: int):
    status, payload = _request(
        harness,
        "/api/tools/legitify/credentials",
        method="POST",
        body={"key": "SCM_TOKEN"},
    )
    assert status == HTTPStatus.BAD_REQUEST
    assert isinstance(payload, dict)
    assert "required" in payload["error"]


def test_invalid_tool_id_route_is_rejected(harness: int):
    # Any character outside the allow-list (here: percent-encoded space)
    # never reaches the credential layer — the route regex rejects it and
    # the standard dispatcher returns 404.
    status, _payload = _request(
        harness,
        "/api/tools/bad%20id/credentials",
        method="POST",
        body={"key": "K", "value": "v"},
    )
    assert status == HTTPStatus.NOT_FOUND
