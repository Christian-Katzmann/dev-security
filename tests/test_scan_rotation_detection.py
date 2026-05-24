"""Scan-time rotation-state detection.

Verifies that scan_repo's returned report carries a `rotation_state` block so
the dashboard can render the RotationStatusCard without an extra round-trip,
and that the block flips between scaffolded/unscaffolded based on what's on
disk in the target repo.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from security_observatory import cli as cli_module
from security_observatory.scanners import ScannerResult
from security_observatory.model import ScannerStatus


def _quick_args() -> SimpleNamespace:
    return SimpleNamespace(
        quick=True,
        code=False,
        ai=False,
        deps=False,
        secrets=False,
        iac=False,
        full=False,
    )


def _fake_scanner(_scanner, _repo, _repo_name, _scan_dir, _rules_dir):
    return ScannerResult(
        status=ScannerStatus(
            scanner="semgrep",
            available=True,
            command=["semgrep"],
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
        ),
        findings=[],
        sbom_created=False,
    )


def test_scan_repo_includes_rotation_state_unscaffolded(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"

    monkeypatch.setattr(cli_module, "scanner_names_for_profile", lambda args: ["semgrep"])
    monkeypatch.setattr(cli_module, "run_scanner", _fake_scanner)

    report = cli_module.scan_repo(repo, _quick_args(), home)
    assert "rotation_state" in report
    assert report["rotation_state"]["scaffolded"] is False
    assert report["rotation_state"]["secret_count"] == 0


def test_scan_repo_includes_rotation_state_scaffolded(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "data").mkdir()
    (repo / "data" / "rotation-state.json").write_text(
        json.dumps(
            {
                "secrets": [
                    {"name": "AUTH_SECRET", "class": "A", "cadence_days": 30}
                ],
                "rotations": [],
            }
        ),
        encoding="utf-8",
    )
    home = tmp_path / "home"

    monkeypatch.setattr(cli_module, "scanner_names_for_profile", lambda args: ["semgrep"])
    monkeypatch.setattr(cli_module, "run_scanner", _fake_scanner)

    report = cli_module.scan_repo(repo, _quick_args(), home)
    assert report["rotation_state"]["scaffolded"] is True
    assert report["rotation_state"]["secret_count"] == 1
    # An unrotated newly-scaffolded secret needs attention.
    assert report["rotation_state"]["needs_attention_count"] == 1
