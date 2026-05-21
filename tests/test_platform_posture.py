from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json

from security_observatory.model import ScannerStatus
from security_observatory.normalize import normalize
from security_observatory.platform_posture import (
    build_platform_posture_snapshot,
    platform_posture_regression_findings,
)
from security_observatory.scanners import run_scanner, scanner_names_for_profile
from security_observatory.storage import ObservatoryDB


def test_platform_posture_is_explicit_opt_in_profile():
    base = _args()
    assert "legitify" not in scanner_names_for_profile(base)

    quick = _args(quick=True)
    assert "legitify" not in scanner_names_for_profile(quick)

    full = _args(full=True)
    assert "legitify" not in scanner_names_for_profile(full)

    platform = _args(platform_posture=True)
    assert scanner_names_for_profile(platform) == ["legitify"]


def test_legitify_missing_credentials_is_skipped_without_findings(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECURITY_OBSERVATORY_PLATFORM_REPO", "owner/repo")
    monkeypatch.delenv("SCM_TOKEN", raising=False)
    monkeypatch.delenv("SECURITY_OBSERVATORY_SCM_TOKEN", raising=False)
    monkeypatch.delenv("LEGITIFY_TOKEN", raising=False)
    monkeypatch.setattr("security_observatory.scanners.shutil.which", lambda binary: "/usr/bin/legitify" if binary == "legitify" else None)

    result = run_scanner("legitify", tmp_path, "repo", tmp_path / "scan", tmp_path / "rules")

    assert result.status.available is True
    assert result.status.status == "skipped"
    assert "SCM_TOKEN" in (result.status.error or "")
    assert "owner/repo" not in " ".join(result.status.command)
    assert result.findings == []
    assert (tmp_path / "scan" / "legitify.json").exists()


def test_legitify_normalization_uses_platform_category_and_sanitized_records():
    payload = _legitify_payload("FAILED", aux={"entityId": "123", "entityName": "private-repo", "token": "ghp_abcdefghijklmnopqrstuvwx"})

    findings = normalize("legitify", payload, "repo")
    snapshot = build_platform_posture_snapshot(
        payload,
        repo_name="repo",
        scanner_status=ScannerStatus(scanner="legitify", available=True, command=["legitify"], started_at="now").to_dict(),
    )

    assert len(findings) == 1
    assert findings[0].category == "platform-posture"
    assert findings[0].scanner == "legitify"
    assert findings[0].title == "Default Branch Should Be Protected"
    assert snapshot["summary"]["failed"] == 1
    assert snapshot["records"][0]["resource_ref"].startswith("resource:")
    assert "private-repo" not in json.dumps(snapshot)
    assert "ghp_" not in json.dumps(snapshot)


def test_platform_posture_drift_detects_branch_protection_regression():
    previous = build_platform_posture_snapshot(_legitify_payload("PASSED"), repo_name="repo", scanner_status={"scanner": "legitify", "available": True})
    current = build_platform_posture_snapshot(_legitify_payload("FAILED"), repo_name="repo", scanner_status={"scanner": "legitify", "available": True})

    findings = platform_posture_regression_findings("repo", current, previous)

    assert len(findings) == 1
    assert findings[0].scanner == "legitify-drift"
    assert findings[0].category == "platform-posture"
    assert findings[0].title == "Default branch protection was disabled"


def test_storage_persists_platform_posture_snapshot(tmp_path: Path):
    snapshot = build_platform_posture_snapshot(_legitify_payload("PASSED"), repo_name="repo", scanner_status={"scanner": "legitify", "available": True})
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="platform-posture",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "legitify", "available": True, "status": "checked", "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "report.json"),
            platform_posture_snapshot=snapshot,
        )
        saved = db.latest_platform_posture_snapshot("repo", scan_id="repo-20260101T000000Z")
        summary = db.dashboard_payload()
    finally:
        db.close()

    assert saved is not None
    assert saved["status"] == "checked"
    assert saved["summary"]["passed"] == 1
    assert summary["repos"][0]["platform_posture"]["snapshot_fingerprint"] == snapshot["snapshot_fingerprint"]


def _args(**overrides):
    values = {
        "full": False,
        "ai": False,
        "code": False,
        "deps": False,
        "secrets": False,
        "iac": False,
        "trust": False,
        "trust_cache_only": False,
        "behavioral_drift": False,
        "platform_posture": False,
        "quick": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _legitify_payload(status: str, aux: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "type": "flattened",
        "content": {
            "data.repository.missing_default_branch_protection": {
                "policyInfo": {
                    "title": "Default Branch Should Be Protected",
                    "description": "Branch protection is not enabled for this repository's default branch.",
                    "policyName": "missing_default_branch_protection",
                    "fullyQualifiedPolicyName": "data.repository.missing_default_branch_protection",
                    "severity": "MEDIUM",
                    "remediationSteps": ["Enable branch protection for the default branch."],
                    "namespace": "repository",
                },
                "violations": [
                    {
                        "violationEntityType": "repository",
                        "canonicalLink": "https://github.com/acme/private-repo",
                        "aux": aux or {"entityId": "123", "entityName": "private-repo"},
                        "status": status,
                    }
                ],
            }
        },
    }
