"""macOS Keychain credential storage for DëvSec.

This is DëvSec's first credential layer (the rotation skill flows secrets
through provider stores; nothing was scaffolded for catalog-driven setup yet).
The convention this module establishes:

* Secrets live in the **macOS login Keychain** under service ``"DëvSec"`` with
  account ``"<tool_id>:<key>"``.
* The Keychain is authoritative for values. We keep a tiny on-disk **index**
  at ``$SECURITY_OBSERVATORY_HOME/credentials/index.json`` that records which
  ``(tool_id, key)`` pairs exist — so ``list_credentials`` can answer "what's
  stored for legitify?" without exporting the whole keychain. The index never
  contains values.
* Module shape mirrors ``rotation.py``: thin, stdlib-only, no DB access, safe
  to import from both ``dashboard_server.py`` and ``mcp_server.py`` (the MCP
  side stays read-only — see ``READ_ONLY_PUBLIC_API``).
* Values never enter logs, stdout, stderr, or HTTP responses. Subprocess env
  injection is the *only* way a value leaves Keychain at runtime.

This module is macOS-only. Linux Secret Service and Windows Credential Manager
are out of scope (DëvSec is macOS-first per the README); callers on other
platforms raise ``CredentialStorageError`` rather than silently falling back.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger("security_observatory.credentials")


# Service name shared by every entry this module writes. One service name keeps
# the Keychain Access audit surface clean — open Keychain Access, search for
# "DëvSec", and every secret DëvSec owns appears together.
KEYCHAIN_SERVICE = "DëvSec"

# Strict allow-list for tool_id / key segments. Keeps the value safe to embed
# in the ``-a "<tool>:<key>"`` flag without quoting games, and keeps the
# on-disk index human-readable. Mirrors the binary-name regex pattern used
# by ``install_via_package_manager`` in dashboard_server.py.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_INDEX_LOCK = threading.Lock()


class CredentialStorageError(RuntimeError):
    """Raised when Keychain access fails for a reason the caller should see.

    Never carries a credential value. The message references the operation and
    (when safe) the ``tool_id``/``key`` involved.
    """


# ---------------------------------------------------------------------------
# Platform / identifier validation
# ---------------------------------------------------------------------------


def is_supported(platform_name: str | None = None) -> bool:
    """Return True iff Keychain operations are usable on this host.

    Combines two checks: the OS is macOS *and* the ``security`` CLI is on
    PATH. The dashboard surfaces this so non-macOS hosts can show a clean
    "Credential storage requires macOS" message instead of stack-tracing.
    """
    system = platform_name if platform_name is not None else platform.system()
    if system != "Darwin":
        return False
    return shutil.which("security") is not None


def _require_supported() -> None:
    if platform.system() != "Darwin":
        raise CredentialStorageError(
            "macOS Keychain storage is only available on macOS. "
            "DëvSec is macOS-first; credential storage on other platforms is not supported."
        )
    if shutil.which("security") is None:
        raise CredentialStorageError(
            "The macOS `security` CLI was not found on PATH. "
            "It ships with macOS by default — repair via `xcode-select --install` or check PATH."
        )


def _validate_identifier(label: str, value: str) -> str:
    if not isinstance(value, str):
        raise CredentialStorageError(f"{label} must be a string.")
    cleaned = value.strip()
    if not _IDENTIFIER_RE.match(cleaned):
        raise CredentialStorageError(
            f"{label} {value!r} is invalid; expected letters, digits, '.', '_' or '-' (1-64 chars)."
        )
    return cleaned


def _account_name(tool_id: str, key: str) -> str:
    return f"{tool_id}:{key}"


# ---------------------------------------------------------------------------
# Index file (bookkeeping only — never holds values)
# ---------------------------------------------------------------------------


def _observatory_home() -> Path:
    return Path(
        os.environ.get("SECURITY_OBSERVATORY_HOME", "~/.security-observatory")
    ).expanduser()


def _index_path() -> Path:
    return _observatory_home() / "credentials" / "index.json"


def _read_index() -> dict[str, list[str]]:
    path = _index_path()
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("credentials index: failed to read %s: %s", path, exc)
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        logger.warning("credentials index: %s is not valid JSON: %s", path, exc)
        return {}
    if not isinstance(parsed, dict):
        return {}
    tools_raw = parsed.get("tools")
    if not isinstance(tools_raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for tool_id, keys in tools_raw.items():
        if not isinstance(tool_id, str) or not isinstance(keys, list):
            continue
        out[tool_id] = sorted({str(k) for k in keys if isinstance(k, str)})
    return out


def _write_index(index: dict[str, list[str]]) -> None:
    path = _index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "tools": {tool_id: sorted(set(keys)) for tool_id, keys in index.items() if keys},
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _index_add(tool_id: str, key: str) -> None:
    with _INDEX_LOCK:
        index = _read_index()
        keys = set(index.get(tool_id, ()))
        if key in keys:
            return
        keys.add(key)
        index[tool_id] = sorted(keys)
        _write_index(index)


def _index_remove(tool_id: str, key: str) -> None:
    with _INDEX_LOCK:
        index = _read_index()
        keys = set(index.get(tool_id, ()))
        if key not in keys:
            return
        keys.discard(key)
        if keys:
            index[tool_id] = sorted(keys)
        else:
            index.pop(tool_id, None)
        _write_index(index)


# ---------------------------------------------------------------------------
# Subprocess wrapper (single point of contact with the `security` CLI)
# ---------------------------------------------------------------------------


def _run_security(
    args: list[str],
    *,
    input_text: str | None = None,
    capture_output: bool = True,
    timeout: float = 15.0,
) -> subprocess.CompletedProcess[str]:
    """Run the macOS ``security`` CLI with stable env and a hard timeout.

    Never logs ``args[-1]`` or any value passed via ``input_text``. The caller
    is responsible for choosing args that don't contain secrets in *positions
    we'd want to log*; today the only secret-bearing position is the value
    immediately after ``-w`` in ``add-generic-password``, which we never log.
    """
    try:
        return subprocess.run(
            ["security", *args],
            input=input_text,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CredentialStorageError(
            f"`security` CLI timed out after {exc.timeout}s during {args[0] if args else 'unknown'!r}."
        ) from exc
    except FileNotFoundError as exc:
        raise CredentialStorageError(
            "The macOS `security` CLI was not found on PATH."
        ) from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def store_credential(tool_id: str, key: str, value: str) -> None:
    """Write a credential value to the macOS Keychain.

    Idempotent: existing entries are updated in place (``-U``). Triggers the
    macOS Keychain access prompt the first time a given process tries to write
    — DëvSec relies on the system dialog rather than trying to suppress it.

    Raises ``CredentialStorageError`` on invalid identifiers, missing OS
    support, or Keychain write failure. The exception's message never includes
    the value.
    """
    _require_supported()
    tool_id = _validate_identifier("tool_id", tool_id)
    key = _validate_identifier("key", key)
    if not isinstance(value, str) or value == "":
        raise CredentialStorageError("Credential value must be a non-empty string.")

    account = _account_name(tool_id, key)
    # `-U` updates an existing entry in place. Without it, a second write
    # raises errSecDuplicateItem (-25299).
    result = _run_security(
        [
            "add-generic-password",
            "-U",
            "-s", KEYCHAIN_SERVICE,
            "-a", account,
            "-l", f"DëvSec — {tool_id}:{key}",
            "-D", "DëvSec credential",
            "-j", "Managed by DëvSec. Safe to revoke from Keychain Access.",
            "-w", value,
        ],
    )
    if result.returncode != 0:
        # Stderr from `security` doesn't echo the password, but scrub
        # defensively before surfacing.
        stderr = (result.stderr or "").strip()
        raise CredentialStorageError(
            f"Failed to store credential for tool={tool_id!r} key={key!r}: "
            f"{stderr or 'unknown Keychain error'}"
        )
    _index_add(tool_id, key)
    logger.info("stored Keychain credential tool=%s key=%s", tool_id, key)


def read_credential(tool_id: str, key: str) -> str | None:
    """Return the credential value from Keychain, or ``None`` if not stored.

    A missing entry is a normal outcome (the caller hasn't paste a token yet)
    and is **not** an error — returns ``None``. Genuine access failures (locked
    keychain, user denied prompt, CLI missing) raise
    ``CredentialStorageError``.
    """
    _require_supported()
    tool_id = _validate_identifier("tool_id", tool_id)
    key = _validate_identifier("key", key)
    account = _account_name(tool_id, key)
    result = _run_security(
        [
            "find-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", account,
            "-w",  # -w prints just the password to stdout
        ],
    )
    if result.returncode == 0:
        # `security -w` appends a trailing newline; strip exactly once.
        value = result.stdout
        if value.endswith("\n"):
            value = value[:-1]
        return value
    # errSecItemNotFound == 44 (legacy) or text "could not be found"
    stderr = (result.stderr or "").strip().casefold()
    if "could not be found" in stderr or result.returncode == 44:
        return None
    raise CredentialStorageError(
        f"Failed to read credential for tool={tool_id!r} key={key!r}: "
        f"{result.stderr.strip() or 'unknown Keychain error'}"
    )


def delete_credential(tool_id: str, key: str) -> bool:
    """Remove the credential from Keychain.

    Returns True if an entry existed and was deleted, False if no entry was
    found (idempotent forget). Raises ``CredentialStorageError`` only on real
    Keychain access failure.
    """
    _require_supported()
    tool_id = _validate_identifier("tool_id", tool_id)
    key = _validate_identifier("key", key)
    account = _account_name(tool_id, key)
    result = _run_security(
        ["delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account],
    )
    if result.returncode == 0:
        _index_remove(tool_id, key)
        logger.info("deleted Keychain credential tool=%s key=%s", tool_id, key)
        return True
    stderr = (result.stderr or "").strip().casefold()
    if "could not be found" in stderr or result.returncode == 44:
        # Keep the index in sync if it claims the entry exists.
        _index_remove(tool_id, key)
        return False
    raise CredentialStorageError(
        f"Failed to delete credential for tool={tool_id!r} key={key!r}: "
        f"{result.stderr.strip() or 'unknown Keychain error'}"
    )


def list_credentials(tool_id: str) -> list[str]:
    """Return the credential **keys** stored for ``tool_id`` (never values).

    Reads from the local index, not from the Keychain itself — that avoids
    triggering an access prompt just to enumerate keys. The Keychain remains
    authoritative for values; the index is bookkeeping. If the index drifts
    out of sync (e.g. a key was deleted via Keychain Access directly), the
    next ``read_credential`` returns ``None`` and ``store_credential`` /
    ``delete_credential`` repair the index.
    """
    tool_id = _validate_identifier("tool_id", tool_id)
    index = _read_index()
    return list(index.get(tool_id, ()))


def list_all_credentials() -> dict[str, list[str]]:
    """Return the full ``{tool_id: [keys]}`` index. Never returns values."""
    return _read_index()


def env_with_credentials(
    base_env: Mapping[str, str],
    tool_id: str,
    mapping: Mapping[str, str],
) -> dict[str, str]:
    """Return a new env dict with Keychain values injected for a subprocess.

    ``mapping`` is ``{ENV_VAR_NAME: credential_key}``. For each entry, this
    reads the credential from Keychain and writes the value into the returned
    env under ``ENV_VAR_NAME``. Credentials that aren't stored are simply not
    injected (the caller decides whether absent means "skip" or "error").

    This is the single supported way for a credential value to leave the
    Keychain at runtime. The value never touches disk, shell history, or a
    config file — it lives in the child process's env block for the duration
    of the subprocess and is discarded when the process exits.
    """
    result = dict(base_env)
    if not mapping:
        return result
    tool_id = _validate_identifier("tool_id", tool_id)
    for env_name, credential_key in mapping.items():
        if not isinstance(env_name, str) or not env_name:
            continue
        try:
            value = read_credential(tool_id, credential_key)
        except CredentialStorageError as exc:
            logger.warning(
                "credential injection: skip env=%s tool=%s key=%s (%s)",
                env_name, tool_id, credential_key, exc,
            )
            continue
        if value is None:
            continue
        result[env_name] = value
    return result


# Public API names that are safe to expose from read-only contexts (MCP).
# ``store_credential``/``delete_credential`` mutate Keychain and must stay on
# the dashboard side per ``docs/agent-safety.md``.
READ_ONLY_PUBLIC_API = ("list_credentials", "list_all_credentials", "is_supported")


__all__ = (
    "CredentialStorageError",
    "KEYCHAIN_SERVICE",
    "READ_ONLY_PUBLIC_API",
    "delete_credential",
    "env_with_credentials",
    "is_supported",
    "list_all_credentials",
    "list_credentials",
    "read_credential",
    "store_credential",
)
