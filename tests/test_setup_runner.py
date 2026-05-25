"""Unit tests for setup_runner — probe execution and tool-config persistence.

The shell-probe tests don't touch a real tool binary. We point ``command`` at
``/bin/true`` or ``/bin/false`` so the harness can run on any host. The probe
contract is what we're verifying: structured ProbeResult, truncated output,
no credential leak on Keychain-unsupported hosts, identifier validation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from security_observatory.catalog import SetupKind, SetupProbe, SetupProbeKind
from security_observatory.setup_runner import (
    ProbeResult,
    SetupRunnerError,
    _truncate,
    delete_tool_config,
    read_tool_config,
    run_setup_probe,
    write_tool_config,
)


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Tool-config persistence
# ---------------------------------------------------------------------------


def test_write_read_delete_tool_config_roundtrip(isolated_home: Path) -> None:
    stored = write_tool_config("malcontent", {"artifact_cache_dir": "/tmp/x"})
    assert stored == {"artifact_cache_dir": "/tmp/x"}

    # Roundtrip through disk
    assert read_tool_config("malcontent") == {"artifact_cache_dir": "/tmp/x"}

    removed = delete_tool_config("malcontent")
    assert removed is True
    assert read_tool_config("malcontent") == {}


def test_write_tool_config_rejects_invalid_key(isolated_home: Path) -> None:
    with pytest.raises(SetupRunnerError):
        write_tool_config("malcontent", {"bad key!": "/tmp/x"})


def test_read_tool_config_handles_legacy_flat_payload(isolated_home: Path) -> None:
    """Manually-edited config files without the ``{values: ...}`` envelope still parse."""
    path = isolated_home / "config" / "malcontent.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"artifact_cache_dir": "/tmp/x"}', encoding="utf-8")
    assert read_tool_config("malcontent") == {"artifact_cache_dir": "/tmp/x"}


# ---------------------------------------------------------------------------
# Probe execution
# ---------------------------------------------------------------------------


def test_run_setup_probe_rejects_unknown_tool(isolated_home: Path) -> None:
    with pytest.raises(SetupRunnerError):
        run_setup_probe("no-such-tool")


def test_directory_exists_probe_pass(isolated_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_tool_config("malcontent", {"artifact_cache_dir": str(tmp_path)})
    result = run_setup_probe("malcontent")
    assert isinstance(result, ProbeResult)
    assert result.success is True
    assert "exists" in result.summary.lower()


def test_directory_exists_probe_fail_when_missing(isolated_home: Path) -> None:
    write_tool_config("malcontent", {"artifact_cache_dir": "/does/not/exist/anywhere"})
    result = run_setup_probe("malcontent")
    assert result.success is False
    assert "not a directory" in result.summary.lower()


def test_directory_exists_probe_fail_when_unset(isolated_home: Path) -> None:
    result = run_setup_probe("malcontent")
    assert result.success is False
    assert "no path stored" in result.summary.lower()


def test_shell_probe_runs_inline_command(
    isolated_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the shell-probe branch returns a structured ProbeResult."""
    from security_observatory import setup_runner

    fake_entry = type(
        "Entry",
        (),
        {
            "id": "demo",
            "install": type("Install", (), {"binary": "echo"})(),
            "setup_kind": SetupKind.API_KEY,
            "setup_probe": SetupProbe(
                kind=SetupProbeKind.SHELL,
                spec={"command": "echo hello"},
            ),
        },
    )

    def fake_find(tool_id: str):  # noqa: ARG001
        return fake_entry

    monkeypatch.setattr(setup_runner, "_find_entry", fake_find)
    result = run_setup_probe("demo")
    assert result.success is True
    assert "hello" in result.output


def test_truncate_respects_line_cap() -> None:
    raw = "\n".join(str(i) for i in range(50))
    out = _truncate(raw)
    assert "truncated" in out
    assert out.count("\n") <= 21  # 20 kept + truncation hint


def test_truncate_respects_byte_cap() -> None:
    raw = "x" * 20000
    out = _truncate(raw)
    assert len(out.encode("utf-8")) <= 9000  # bytes cap + small overhead


def test_shell_probe_honours_success_returncodes(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A probe that exits 1 still counts as success when the spec allows it.

    legitify exits 1 when it finds policy violations on the target repo —
    that proves the token works. Setting ``success_returncodes: "0,1"``
    teaches the runner to read both as success without losing the actual
    returncode in the result body.
    """
    from security_observatory import setup_runner

    fake_entry = type(
        "Entry",
        (),
        {
            "id": "demo",
            "install": type("Install", (), {"binary": "false"})(),
            "setup_kind": SetupKind.API_KEY,
            "setup_probe": SetupProbe(
                kind=SetupProbeKind.SHELL,
                spec={"command": "false", "success_returncodes": "0,1"},
            ),
        },
    )
    monkeypatch.setattr(setup_runner, "_find_entry", lambda _id: fake_entry)
    result = run_setup_probe("demo")
    assert result.success is True
    assert result.returncode == 1


def test_shell_probe_returncode_outside_allowed_set_fails(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exit code outside success_returncodes is still a failure."""
    from security_observatory import setup_runner

    fake_entry = type(
        "Entry",
        (),
        {
            "id": "demo",
            "install": type("Install", (), {"binary": "sh"})(),
            "setup_kind": SetupKind.API_KEY,
            "setup_probe": SetupProbe(
                kind=SetupProbeKind.SHELL,
                spec={"command": "exit 7", "success_returncodes": "0,1"},
            ),
        },
    )
    monkeypatch.setattr(setup_runner, "_find_entry", lambda _id: fake_entry)
    result = run_setup_probe("demo")
    assert result.success is False
    assert result.returncode == 7


def test_resolve_success_returncodes_handles_malformed_input() -> None:
    """Garbled or empty spec values fall back to the conservative default {0}."""
    from security_observatory.setup_runner import _resolve_success_returncodes

    assert _resolve_success_returncodes({}) == frozenset({0})
    assert _resolve_success_returncodes({"success_returncodes": ""}) == frozenset({0})
    assert _resolve_success_returncodes({"success_returncodes": "abc,,xy"}) == frozenset({0})
    assert _resolve_success_returncodes({"success_returncodes": "0, 1, 2"}) == frozenset({0, 1, 2})
