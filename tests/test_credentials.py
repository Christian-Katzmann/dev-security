"""Integration tests for the macOS Keychain credential layer.

These tests touch the **real** macOS login Keychain. They are gated on macOS
availability and the ``security`` CLI being on PATH — they skip cleanly on
Linux CI runners.

Each test uses a unique throwaway ``tool_id`` so it can't collide with real
DëvSec credentials on a developer's machine. Cleanup runs in a finally block
to make sure a failing assertion never leaves stray Keychain entries behind.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from security_observatory.credentials import (
    CredentialStorageError,
    delete_credential,
    env_with_credentials,
    is_supported,
    list_credentials,
    read_credential,
    store_credential,
)


pytestmark = pytest.mark.skipif(
    not is_supported(),
    reason="macOS Keychain integration tests require macOS + `security` CLI on PATH.",
)


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the credential index at a throwaway directory.

    The Keychain itself is shared with the user's real login keychain (there
    is no way to point ``security`` at a sandbox without creating a real
    keychain file). The throwaway tool_id below keeps test entries scoped.
    """
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def tool_id() -> str:
    """Unique per-test tool_id so concurrent runs and aborted runs can't collide."""
    return f"devsec-test-{uuid.uuid4().hex[:8]}"


def test_write_and_read_credential_roundtrip(isolated_home: Path, tool_id: str) -> None:
    """Storing a value and reading it back returns the same string."""

    key = "API_KEY"
    value = "secret-token-" + uuid.uuid4().hex
    try:
        store_credential(tool_id, key, value)
        assert read_credential(tool_id, key) == value

        # Overwrite with a new value — store_credential is idempotent.
        new_value = "rotated-token-" + uuid.uuid4().hex
        store_credential(tool_id, key, new_value)
        assert read_credential(tool_id, key) == new_value

        # Missing keys return None, not an exception.
        assert read_credential(tool_id, "NOT_STORED") is None
    finally:
        delete_credential(tool_id, key)


def test_delete_credential_returns_true_when_present_false_when_absent(
    isolated_home: Path, tool_id: str
) -> None:
    """Delete reports whether something was actually removed."""

    key = "PAT"
    value = "value-" + uuid.uuid4().hex
    try:
        store_credential(tool_id, key, value)
        assert delete_credential(tool_id, key) is True
        # Second delete is a no-op.
        assert delete_credential(tool_id, key) is False
        # And the value is gone.
        assert read_credential(tool_id, key) is None
    finally:
        # Defensive: make sure nothing lingers even if the test fails midway.
        delete_credential(tool_id, key)


def test_list_credentials_returns_keys_never_values(
    isolated_home: Path, tool_id: str
) -> None:
    """list_credentials surfaces what's stored without leaking values."""

    keys = ["TOKEN_A", "TOKEN_B"]
    values = {key: f"value-{uuid.uuid4().hex}" for key in keys}
    try:
        for key, value in values.items():
            store_credential(tool_id, key, value)

        listed = list_credentials(tool_id)
        assert sorted(listed) == sorted(keys)

        # Sanity: the index file on disk must not contain any value.
        index_path = isolated_home / "credentials" / "index.json"
        on_disk = index_path.read_text(encoding="utf-8")
        for value in values.values():
            assert value not in on_disk, (
                "Credential value leaked into the on-disk index file."
            )
    finally:
        for key in keys:
            delete_credential(tool_id, key)


def test_env_with_credentials_injects_values_for_subprocesses(
    isolated_home: Path, tool_id: str
) -> None:
    """The subprocess-env helper is the only path values leave Keychain."""

    key = "SCM_TOKEN"
    value = "scm-token-" + uuid.uuid4().hex
    try:
        store_credential(tool_id, key, value)
        base_env = {"PATH": os.environ.get("PATH", ""), "EXISTING": "keep"}
        env = env_with_credentials(base_env, tool_id, {"SCM_TOKEN": "SCM_TOKEN"})
        assert env["SCM_TOKEN"] == value
        # Base env is preserved, not replaced.
        assert env["EXISTING"] == "keep"
        assert "PATH" in env
        # The original base_env is not mutated.
        assert "SCM_TOKEN" not in base_env
    finally:
        delete_credential(tool_id, key)


def test_invalid_identifiers_raise_before_keychain_access(
    isolated_home: Path,
) -> None:
    """Identifier validation runs before any shell-out to `security`."""

    with pytest.raises(CredentialStorageError):
        store_credential("bad id with spaces", "KEY", "value")
    with pytest.raises(CredentialStorageError):
        read_credential("legit", "key with spaces")
    with pytest.raises(CredentialStorageError):
        delete_credential("legit", "")
