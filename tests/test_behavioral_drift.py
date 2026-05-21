from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import subprocess

from security_observatory import cli as cli_module
from security_observatory.behavioral import select_behavioral_drift_targets
from security_observatory.normalize import normalize
from security_observatory.scanners import run_behavioral_drift_scanner, scanner_names_for_profile
from security_observatory.sbom import SBOMComponent
from security_observatory.storage import ObservatoryDB


def test_behavioral_drift_profile_runs_only_syft_and_leaves_default_unchanged():
    behavioral_args = _args(behavioral_drift=True)
    default_args = _args()

    assert scanner_names_for_profile(behavioral_args) == ["syft"]
    assert cli_module.profile_name(behavioral_args) == "behavioral-drift"
    assert "malcontent" not in scanner_names_for_profile(default_args)


def test_behavioral_drift_selects_changed_versions_and_reports_missing_artifacts(tmp_path: Path):
    cache = tmp_path / "cache"
    _write_artifact(cache, "npm", "ready", "1.0.0", b"old")
    _write_artifact(cache, "npm", "ready", "1.1.0", b"new")
    _write_artifact(cache, "npm", "huge", "1.0.0", b"old")
    _write_artifact(cache, "npm", "huge", "1.1.0", b"x" * 12)

    targets = select_behavioral_drift_targets(
        current_components=[
            _component("ready", "1.1.0"),
            _component("same", "1.0.0"),
            _component("missing-old", "2.0.0"),
            _component("huge", "1.1.0"),
        ],
        previous_components=[
            _component("ready", "1.0.0"),
            _component("same", "1.0.0"),
            _component("missing-old", "1.0.0"),
            _component("huge", "1.0.0"),
            _component("removed", "1.0.0"),
        ],
        repo_name="repo",
        scan_id="repo-20260512T120000Z",
        previous_scan_id="repo-20260511T120000Z",
        artifact_cache_dir=cache,
        max_packages=5,
        max_artifact_bytes=10,
    )

    by_name = {target.package_name: target for target in targets}
    assert set(by_name) == {"ready", "missing-old", "huge"}
    assert by_name["ready"].status == "queued"
    assert by_name["ready"].old_version == "1.0.0"
    assert by_name["ready"].new_version == "1.1.0"
    assert by_name["missing-old"].status == "not_checked"
    assert by_name["missing-old"].reason == "No local artifact was available for this package version."
    assert by_name["huge"].status == "not_checked"
    assert "larger than" in by_name["huge"].reason


def test_behavioral_drift_package_count_limit_marks_extra_targets_not_checked(tmp_path: Path):
    cache = tmp_path / "cache"
    for name in ("a", "b"):
        _write_artifact(cache, "npm", name, "1.0.0", b"old")
        _write_artifact(cache, "npm", name, "1.1.0", b"new")

    targets = select_behavioral_drift_targets(
        current_components=[_component("a", "1.1.0"), _component("b", "1.1.0")],
        previous_components=[_component("a", "1.0.0"), _component("b", "1.0.0")],
        repo_name="repo",
        scan_id="repo-20260512T120000Z",
        previous_scan_id="repo-20260511T120000Z",
        artifact_cache_dir=cache,
        max_packages=1,
    )

    assert [target.status for target in targets].count("queued") == 1
    assert [target.status for target in targets].count("not_checked") == 1
    assert any("capped at 1" in target.reason for target in targets)


def test_malcontent_normalization_preserves_before_after_behavior():
    findings = normalize(
        "malcontent",
        {
            "checks": [
                {
                    "status": "checked",
                    "package_name": "postinstall-demo",
                    "package_ecosystem": "npm",
                    "package_url": "pkg:npm/postinstall-demo@1.1.0",
                    "package_key": "purl|pkg:npm/postinstall-demo",
                    "old_version": "1.0.0",
                    "new_version": "1.1.0",
                    "malcontent": {
                        "files": [
                            {
                                "path": "package/scripts/postinstall.js",
                                "previous_risk_level": "low",
                                "risk_level": "high",
                                "behaviors": [
                                    {
                                        "name": "exec shell",
                                        "description": "spawns a shell during package installation",
                                    }
                                ],
                            }
                        ]
                    },
                }
            ]
        },
        "repo",
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.scanner == "malcontent"
    assert finding.category == "behavioral-drift"
    assert finding.severity == "high"
    assert finding.package_name == "postinstall-demo"
    assert finding.old_version == "1.0.0"
    assert finding.new_version == "1.1.0"
    assert finding.behavior_category == "process execution"
    assert "not proof of compromise" in (finding.evidence_summary or "")
    assert finding.before_behavior == "previous artifact risk was low"
    assert finding.after_behavior == "spawns a shell during package installation"


def test_behavioral_drift_runner_keeps_malcontent_failure_non_fatal(tmp_path: Path):
    old_artifact = tmp_path / "old.tgz"
    new_artifact = tmp_path / "new.tgz"
    old_artifact.write_bytes(b"old")
    new_artifact.write_bytes(b"new")

    def fake_runner(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=2, stdout="", stderr="diff failed")

    result = run_behavioral_drift_scanner(
        "repo",
        tmp_path,
        [
            {
                "status": "queued",
                "package_name": "demo",
                "package_key": "component|npm|library|demo",
                "old_version": "1.0.0",
                "new_version": "1.1.0",
                "old_artifact": str(old_artifact),
                "new_artifact": str(new_artifact),
            }
        ],
        runner=fake_runner,
        binary="/usr/local/bin/malcontent",
    )

    assert result.status.status == "not_checked"
    assert result.status.error is None
    assert result.findings == []
    raw = (tmp_path / "malcontent.json").read_text(encoding="utf-8")
    assert "the scan continued" in raw


def test_storage_persists_behavioral_drift_fields(tmp_path: Path):
    finding = normalize(
        "malcontent",
        {
            "checks": [
                {
                    "status": "checked",
                    "package_name": "demo",
                    "old_version": "1.0.0",
                    "new_version": "1.1.0",
                    "malcontent": {"behaviors": [{"description": "opens a network socket", "risk_level": "high"}]},
                }
            ]
        },
        "repo",
    )[0]
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260512T120000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-05-12T12:00:00+00:00",
            finished_at="2026-05-12T12:01:00+00:00",
            profile="behavioral-drift",
            health_score=90,
            status="ok",
            scanner_statuses=[{"scanner": "malcontent", "available": True, "status": "checked", "findings": 1}],
            findings=[finding],
            report_path=str(tmp_path / "report.json"),
        )
        payload = db.dashboard_payload()
    finally:
        db.close()

    stored = payload["findings"][0]
    assert stored["old_version"] == "1.0.0"
    assert stored["new_version"] == "1.1.0"
    assert stored["behavior_category"] == "network"
    assert "not proof of compromise" in stored["evidence_summary"]


def _component(name: str, version: str) -> SBOMComponent:
    return SBOMComponent(
        name=name,
        version=version,
        ecosystem="npm",
        component_type="library",
        package_url=f"pkg:npm/{name}@{version}",
        license="MIT",
        supplier=None,
        source_path="package-lock.json",
    )


def _write_artifact(cache: Path, ecosystem: str, name: str, version: str, content: bytes) -> None:
    path = cache / ecosystem / name / version / "artifact"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _args(**overrides: bool) -> SimpleNamespace:
    values = {
        "quick": False,
        "code": False,
        "ai": False,
        "deps": False,
        "trust": False,
        "trust_cache_only": False,
        "behavioral_drift": False,
        "secrets": False,
        "iac": False,
        "full": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)
