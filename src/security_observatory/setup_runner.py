"""Run a catalog tool's ``setup_probe`` and persist tool-side setup config.

The SetupCard (``dashboard-ui/src/components/catalog/SetupCard.tsx``) is the
first consumer. Two responsibilities:

1. **Probe execution.** Read the tool's ``setup_probe`` from the catalog and
   run it. Returns ``{success, output, returncode, command}``. The probe types
   are: ``shell`` (subprocess), ``binary-version`` (subprocess), ``http``
   (single GET), ``directory-exists`` (filesystem check).
2. **Tool setup config persistence.** Non-credential setup values (a file
   path, a config block) live at ``~/.security-observatory/config/<tool>.toml``
   — separate from the Keychain, which holds only secret values. Reads,
   writes, deletes via three thin file-IO helpers.

The probe and the config store are deliberately stateless: every probe is a
fresh run, and every config read goes to disk. That keeps the surface tiny
and trivially testable, and matches the shape of ``rotation.py`` (the
module-layout precedent locked in by Step 1.2).

Credential values are only ever read from the Keychain at probe-run time and
injected into the child process env via ``credentials.env_with_credentials``.
They never leave that env block. The probe response includes truncated stdout
+ stderr; the caller is responsible for not echoing them if they could leak
provider-side error text containing user input.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .catalog import (
    SetupKind,
    SetupProbe,
    SetupProbeKind,
    ToolCatalogEntry,
    tool_catalog_entries,
)
from .credentials import env_with_credentials, is_supported as keychain_is_supported
from .tool_config import (
    ToolConfigError,
    delete_tool_config,
    read_tool_config,
    write_tool_config,
)

logger = logging.getLogger("security_observatory.setup_runner")


# Same character class as credentials / install endpoints — keeps tool_id /
# config-key safe to embed in filesystem paths without escaping games.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# Output truncation cap. The SetupCard shows 5 lines; the API returns 20 so
# the user can scroll the panel for failure forensics. Bytes cap defends
# against a probe that prints binary garbage.
_OUTPUT_MAX_LINES = 20
_OUTPUT_MAX_BYTES = 8192

# Hard ceiling on probe runtime. The catalog spec may request a shorter
# timeout via ``spec["timeout_seconds"]``; this is the upper bound regardless.
_PROBE_HARD_TIMEOUT_SECONDS = 120.0
_PROBE_DEFAULT_TIMEOUT_SECONDS = 60.0


class SetupRunnerError(RuntimeError):
    """Raised when the probe cannot run at all (catalog gap, missing config)."""


@dataclass(frozen=True, slots=True)
class ProbeResult:
    success: bool
    summary: str
    output: str
    command: str | None
    returncode: int | None
    duration_seconds: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "summary": self.summary,
            "output": self.output,
            "command": self.command,
            "returncode": self.returncode,
            "duration_seconds": self.duration_seconds,
        }


# ---------------------------------------------------------------------------
# Identifier + path helpers
# ---------------------------------------------------------------------------


def _validate_identifier(label: str, value: str) -> str:
    if not isinstance(value, str):
        raise SetupRunnerError(f"{label} must be a string.")
    cleaned = value.strip()
    if not _IDENTIFIER_RE.match(cleaned):
        raise SetupRunnerError(
            f"{label} {value!r} is invalid; expected letters, digits, '.', '_' or '-' (1-64 chars)."
        )
    return cleaned


def _truncate(output: str) -> str:
    if not output:
        return ""
    text = output if len(output.encode("utf-8")) <= _OUTPUT_MAX_BYTES else (
        output.encode("utf-8")[:_OUTPUT_MAX_BYTES].decode("utf-8", errors="replace")
    )
    lines = text.splitlines()
    if len(lines) > _OUTPUT_MAX_LINES:
        kept = lines[: _OUTPUT_MAX_LINES]
        kept.append(f"… ({len(lines) - _OUTPUT_MAX_LINES} more lines truncated)")
        return "\n".join(kept)
    return text


# ---------------------------------------------------------------------------
# Catalog lookup
# ---------------------------------------------------------------------------


def _find_entry(tool_id: str) -> ToolCatalogEntry:
    safe = _validate_identifier("tool_id", tool_id)
    for entry in tool_catalog_entries():
        if entry.id == safe:
            return entry
    raise SetupRunnerError(f"Tool {safe!r} is not in the catalog.")


# ---------------------------------------------------------------------------
# Probe execution
# ---------------------------------------------------------------------------


def run_setup_probe(tool_id: str) -> ProbeResult:
    """Run the tool's ``setup_probe`` and return a structured result."""
    entry = _find_entry(tool_id)
    probe = entry.setup_probe
    if entry.setup_kind == SetupKind.NONE or probe is None:
        raise SetupRunnerError(
            f"Tool {tool_id!r} has no setup probe; nothing to test."
        )

    kind = probe.kind
    try:
        if kind == SetupProbeKind.SHELL:
            return _run_shell_probe(entry, probe)
        if kind == SetupProbeKind.BINARY_VERSION:
            return _run_binary_version_probe(entry, probe)
        if kind == SetupProbeKind.DIRECTORY_EXISTS:
            return _run_directory_exists_probe(entry, probe)
        if kind == SetupProbeKind.HTTP:
            return _run_http_probe(entry, probe)
    except SetupRunnerError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("setup probe failed: %s", exc)
        return ProbeResult(
            success=False,
            summary=f"Probe crashed: {exc}",
            output="",
            command=None,
            returncode=None,
            duration_seconds=None,
        )
    raise SetupRunnerError(f"Unsupported setup_probe kind: {kind.value}")


def _resolve_timeout(spec: Mapping[str, str]) -> float:
    raw = spec.get("timeout_seconds")
    if not raw:
        return _PROBE_DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _PROBE_DEFAULT_TIMEOUT_SECONDS
    return max(1.0, min(value, _PROBE_HARD_TIMEOUT_SECONDS))


def _resolve_success_returncodes(spec: Mapping[str, str]) -> frozenset[int]:
    """Return the set of returncodes that should count as probe success.

    Defaults to ``{0}``. Some tools (legitify, semgrep) use exit 1 to signal
    "ran successfully but found things" — for a probe that only cares about
    whether the credential/binary works, that counts as success. The catalog
    spec carries a comma-separated string (``"0,1"``); we keep parsing lenient
    so a malformed value falls back to the conservative default.
    """
    raw = (spec.get("success_returncodes") or "").strip()
    if not raw:
        return frozenset({0})
    parsed: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            parsed.add(int(token))
        except ValueError:
            continue
    return frozenset(parsed) if parsed else frozenset({0})


def _run_shell_probe(entry: ToolCatalogEntry, probe: SetupProbe) -> ProbeResult:
    spec = probe.spec
    command = spec.get("command", "").strip()
    if not command:
        raise SetupRunnerError("shell probe missing 'command' in spec.")
    timeout = _resolve_timeout(spec)

    env = dict(os.environ)
    credential_key = spec.get("env_from_credential")
    env_var_name = spec.get("env_var", credential_key)
    if credential_key and env_var_name:
        if not keychain_is_supported():
            return ProbeResult(
                success=False,
                summary="Credential storage requires macOS with the `security` CLI on PATH.",
                output="",
                command=command,
                returncode=None,
                duration_seconds=None,
            )
        env = env_with_credentials(env, entry.id, {env_var_name: credential_key})
        if env_var_name not in env:
            return ProbeResult(
                success=False,
                summary=(
                    f"No credential stored for {entry.id} ({credential_key}). "
                    "Paste the value and click Store, then test again."
                ),
                output="",
                command=command,
                returncode=None,
                duration_seconds=None,
            )

    return _run_subprocess(
        command,
        env=env,
        timeout=timeout,
        success_returncodes=_resolve_success_returncodes(spec),
    )


def _run_binary_version_probe(entry: ToolCatalogEntry, probe: SetupProbe) -> ProbeResult:
    spec = probe.spec
    command = spec.get("command")
    if not command:
        binary = entry.install.binary or entry.id
        command = f"{binary} --version"
    return _run_subprocess(
        command,
        env=dict(os.environ),
        timeout=_resolve_timeout(spec),
        success_returncodes=_resolve_success_returncodes(spec),
    )


def _run_directory_exists_probe(entry: ToolCatalogEntry, probe: SetupProbe) -> ProbeResult:
    spec = probe.spec
    config_key = spec.get("config_key")
    if not config_key:
        raise SetupRunnerError("directory-exists probe missing 'config_key' in spec.")
    stored = read_tool_config(entry.id).get(config_key, "").strip()
    if not stored:
        return ProbeResult(
            success=False,
            summary=(
                f"No path stored under {config_key!r}. Save a directory path, then test again."
            ),
            output="",
            command=None,
            returncode=None,
            duration_seconds=None,
        )
    path = Path(stored).expanduser()
    if path.is_dir():
        return ProbeResult(
            success=True,
            summary=f"Directory exists: {path}",
            output=f"{path}\n",
            command=None,
            returncode=0,
            duration_seconds=None,
        )
    return ProbeResult(
        success=False,
        summary=f"Path is not a directory: {path}",
        output=f"{path}\n",
        command=None,
        returncode=None,
        duration_seconds=None,
    )


def _run_http_probe(entry: ToolCatalogEntry, probe: SetupProbe) -> ProbeResult:
    spec = probe.spec
    url = spec.get("url", "").strip()
    if not url.startswith(("http://", "https://")):
        raise SetupRunnerError("http probe requires a full URL in spec.url.")
    method = spec.get("method", "GET").upper()
    timeout = _resolve_timeout(spec)
    try:
        request = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            status = response.status
            body = response.read(_OUTPUT_MAX_BYTES).decode("utf-8", errors="replace")
        return ProbeResult(
            success=200 <= status < 300,
            summary=f"HTTP {method} {url} → {status}",
            output=_truncate(body),
            command=f"{method} {url}",
            returncode=status,
            duration_seconds=None,
        )
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return ProbeResult(
            success=False,
            summary=f"HTTP {method} {url} → {exc.code} {exc.reason}",
            output=_truncate(body),
            command=f"{method} {url}",
            returncode=exc.code,
            duration_seconds=None,
        )
    except urllib.error.URLError as exc:
        return ProbeResult(
            success=False,
            summary=f"HTTP {method} {url} failed: {exc.reason}",
            output="",
            command=f"{method} {url}",
            returncode=None,
            duration_seconds=None,
        )


# ---------------------------------------------------------------------------
# Subprocess wrapper
# ---------------------------------------------------------------------------


def _run_subprocess(
    command: str,
    *,
    env: Mapping[str, str],
    timeout: float,
    success_returncodes: frozenset[int] = frozenset({0}),
) -> ProbeResult:
    # Run via /bin/sh -c so catalog probes can use simple inline commands
    # (``legitify analyze --scm github --namespace repository …``). The
    # command is authored by the catalog, not by user input — it cannot be
    # steered by a paste.
    try:
        completed = subprocess.run(
            command,
            shell=True,
            executable=shutil.which("sh") or "/bin/sh",
            env=dict(env),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return ProbeResult(
            success=False,
            summary=f"Probe timed out after {exc.timeout:g}s.",
            output=_truncate((exc.stdout or "") + (exc.stderr or "")),
            command=command,
            returncode=None,
            duration_seconds=float(exc.timeout) if exc.timeout else None,
        )
    except OSError as exc:
        return ProbeResult(
            success=False,
            summary=f"Probe could not start: {exc}",
            output="",
            command=command,
            returncode=None,
            duration_seconds=None,
        )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined = stdout + ("\n" + stderr if stderr and stdout else stderr)
    success = completed.returncode in success_returncodes
    summary = (
        "Probe succeeded."
        if success
        else f"Probe exited {completed.returncode}."
    )
    return ProbeResult(
        success=success,
        summary=summary,
        output=_truncate(combined.strip()),
        command=command,
        returncode=completed.returncode,
        duration_seconds=None,
    )


__all__ = (
    "ProbeResult",
    "SetupRunnerError",
    "ToolConfigError",
    "delete_tool_config",
    "read_tool_config",
    "run_setup_probe",
    "write_tool_config",
)
