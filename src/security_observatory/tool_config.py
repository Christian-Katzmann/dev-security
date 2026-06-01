"""On-disk persistence for non-credential tool setup values.

Extracted from ``setup_runner`` (step 2.1) so ``catalog`` can read a tool's
stored config without the catalog↔setup_runner import cycle. This is a leaf
module: it imports neither ``catalog`` nor ``setup_runner``, so both can depend
on it at module top level.

Config values are the non-secret half of tool setup (cache dirs, file paths,
config blocks). Secrets live in the Keychain via ``credentials``; these plain
values live as JSON under ``~/.security-observatory/config/<tool_id>.json``.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger("security_observatory.tool_config")


# Same character class as credentials / setup-probe identifiers — keeps
# tool_id / config-key safe to embed in filesystem paths without escaping games.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ToolConfigError(RuntimeError):
    """Raised when a tool-config identifier or key is invalid."""


def _validate_identifier(label: str, value: str) -> str:
    if not isinstance(value, str):
        raise ToolConfigError(f"{label} must be a string.")
    cleaned = value.strip()
    if not _IDENTIFIER_RE.match(cleaned):
        raise ToolConfigError(
            f"{label} {value!r} is invalid; expected letters, digits, '.', '_' or '-' (1-64 chars)."
        )
    return cleaned


def _observatory_home() -> Path:
    return Path(
        os.environ.get("SECURITY_OBSERVATORY_HOME", "~/.security-observatory")
    ).expanduser()


def _config_path(tool_id: str) -> Path:
    safe = _validate_identifier("tool_id", tool_id)
    return _observatory_home() / "config" / f"{safe}.json"


def _normalize_loaded_config(raw: Any) -> dict[str, str]:
    """Accept ``{values: {key: value}}`` envelope or a flat ``{key: value}`` dict."""
    if not isinstance(raw, dict):
        return {}
    values = raw.get("values") if isinstance(raw.get("values"), dict) else raw
    if not isinstance(values, dict):
        return {}
    return {
        str(k): str(v)
        for k, v in values.items()
        if isinstance(k, str) and isinstance(v, str)
    }


def read_tool_config(tool_id: str) -> dict[str, str]:
    """Return the stored setup config for ``tool_id``; ``{}`` if none.

    Accepts either a flat ``{key: value}`` payload or a ``{values: {...}}``
    envelope on disk so manually-edited files don't break the read.
    """
    path = _config_path(tool_id)
    if not path.is_file():
        return {}
    try:
        return _normalize_loaded_config(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        logger.warning("setup config: failed to parse %s: %s", path, exc)
        return {}


def write_tool_config(tool_id: str, values: Mapping[str, str]) -> dict[str, str]:
    """Replace the tool's stored config with ``values`` and return the result."""
    safe = _validate_identifier("tool_id", tool_id)
    cleaned: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        cleaned_key = _validate_identifier("config key", key)
        cleaned[cleaned_key] = value
    path = _config_path(safe)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"version": 1, "values": cleaned}, indent=2, sort_keys=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    return read_tool_config(safe)


def delete_tool_config(tool_id: str) -> bool:
    """Remove the tool's setup config. Returns True if a file was removed."""
    path = _config_path(tool_id)
    if not path.is_file():
        return False
    path.unlink()
    return True


__all__ = (
    "ToolConfigError",
    "delete_tool_config",
    "read_tool_config",
    "write_tool_config",
)
