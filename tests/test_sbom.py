from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json

from security_observatory import scan_orchestrator as scan_module
from security_observatory.model import ScannerStatus
from security_observatory.scanners import ScannerResult
from security_observatory.silent_upgrades import detect_silent_upgrades
from security_observatory.sbom import SBOMComponent, parse_sbom_components
from security_observatory.storage import ObservatoryDB


def test_cyclonedx_parser_extracts_normalized_component_fields():
    components = parse_sbom_components(_cyclonedx_fixture(), source_file="sbom.cyclonedx.json")

    assert len(components) == 1
    component = components[0]
    assert component.package_url == "pkg:npm/lodash@4.17.21"
    assert component.name == "lodash"
    assert component.version == "4.17.21"
    assert component.ecosystem == "npm"
    assert component.component_type == "library"
    assert component.license == "MIT"
    assert component.supplier == "OpenJS Foundation"
    assert component.source_path == "package-lock.json"
    assert component.source_format == "cyclonedx"
    assert component.source_file == "sbom.cyclonedx.json"


def test_syft_parser_extracts_normalized_component_fields():
    components = parse_sbom_components(
        {
            "artifacts": [
                {
                    "id": "artifact-1",
                    "name": "requests",
                    "version": "2.32.3",
                    "type": "python",
                    "purl": "pkg:pypi/requests@2.32.3",
                    "licenses": [{"value": "Apache-2.0"}],
                    "metadata": {"supplier": {"name": "Python Packaging Authority"}},
                    "locations": [{"path": "requirements.txt"}],
                }
            ]
        },
        source_file="syft.json",
    )

    assert len(components) == 1
    component = components[0]
    assert component.package_url == "pkg:pypi/requests@2.32.3"
    assert component.name == "requests"
    assert component.version == "2.32.3"
    assert component.ecosystem == "pypi"
    assert component.component_type == "python"
    assert component.license == "Apache-2.0"
    assert component.supplier == "Python Packaging Authority"
    assert component.source_path == "requirements.txt"
    assert component.source_format == "syft"


def test_parser_keeps_missing_optional_metadata_visible():
    components = parse_sbom_components(
        {
            "bomFormat": "CycloneDX",
            "components": [
                {
                    "type": "library",
                    "name": "mystery-package",
                }
            ],
        }
    )

    assert len(components) == 1
    component = components[0]
    assert component.name == "mystery-package"
    assert component.version is None
    assert component.package_url is None
    assert component.ecosystem is None
    assert component.license is None
    assert component.supplier is None
    assert component.source_path is None


def test_component_fingerprint_is_stable_for_same_package_version_and_changes_with_version():
    base = SBOMComponent(
        name="lodash",
        version="4.17.21",
        ecosystem="npm",
        component_type="library",
        package_url="pkg:npm/lodash@4.17.21",
        license="MIT",
        supplier="OpenJS Foundation",
        source_path="package-lock.json",
    )
    same_identity = SBOMComponent(
        name="lodash",
        version="4.17.21",
        ecosystem="npm",
        component_type="library",
        package_url="pkg:npm/lodash@4.17.21",
        license=None,
        supplier=None,
        source_path="packages/app/package-lock.json",
    )
    changed_version = SBOMComponent(
        name="lodash",
        version="4.17.20",
        ecosystem="npm",
        component_type="library",
        package_url="pkg:npm/lodash@4.17.20",
        license="MIT",
        supplier="OpenJS Foundation",
        source_path="package-lock.json",
    )

    assert base.component_fingerprint == same_identity.component_fingerprint
    assert base.component_fingerprint != changed_version.component_fingerprint


def test_storage_creates_schema_and_persists_components_with_scan_and_repo(tmp_path: Path):
    component = parse_sbom_components(_cyclonedx_fixture())[0]
    missing_metadata = parse_sbom_components({"components": [{"type": "library", "name": "unknown"}]})[0]
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        tables = {
            row["name"]
            for row in db.conn.execute(
                "select name from sqlite_master where type = 'table'",
            ).fetchall()
        }
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "normalized-report.json"),
            sbom_components=[component, missing_metadata],
        )
        rows = db.list_sbom_components(scan_id="repo-20260101T000000Z")
    finally:
        db.close()

    assert "sbom_components" in tables
    assert len(rows) == 2
    lodash = next(row for row in rows if row["name"] == "lodash")
    assert lodash["scan_id"] == "repo-20260101T000000Z"
    assert lodash["repo_name"] == "repo"
    assert lodash["package_url"] == "pkg:npm/lodash@4.17.21"
    assert lodash["license"] == "MIT"
    unknown = next(row for row in rows if row["name"] == "unknown")
    assert unknown["package_url"] is None
    assert unknown["license"] is None


def test_dashboard_payload_includes_repo_specific_dependency_delta(tmp_path: Path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "first-report.json"),
            sbom_components=[
                _component("lodash", "4.17.20", "MIT"),
                _component("requests", "2.32.3", "Apache-2.0", ecosystem="pypi"),
                _component("left-pad", "2.0.0", "MIT"),
                _component("mystery", "spring", "MIT"),
                _component("license-only", "1.0.0", "MIT"),
            ],
        )
        db.save_scan(
            scan_id="other-20260101T120000Z",
            repo_name="other",
            repo_path="/tmp/other",
            started_at="2026-01-01T12:00:00+00:00",
            finished_at="2026-01-01T12:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "other-report.json"),
            sbom_components=[_component("other-only", "9.9.9", "MIT")],
        )
        db.save_scan(
            scan_id="repo-20260102T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "second-report.json"),
            sbom_components=[
                _component("lodash", "4.18.0", "BSD-3-Clause"),
                _component("left-pad", "1.5.0", "MIT"),
                _component("mystery", "summer", "MIT"),
                _component("license-only", "1.0.0", "Apache-2.0"),
                _component("react", "19.0.1", "MIT"),
            ],
        )

        summary = db.dashboard_payload()
    finally:
        db.close()

    repo = next(item for item in summary["repos"] if item["repo"] == "repo")
    delta = repo["dependency_delta"]
    changes_by_name = {change["name"]: change for change in delta["changes"]}

    assert delta["status"] == "changed"
    assert delta["previous_scan_id"] == "repo-20260101T000000Z"
    assert delta["current_count"] == 5
    assert delta["previous_count"] == 5
    assert delta["counts"] == {
        "added": 1,
        "removed": 1,
        "upgraded": 1,
        "downgraded": 1,
        "version-changed": 3,
        "license-changed": 2,
    }
    assert "other-only" not in changes_by_name
    assert changes_by_name["react"]["change_type"] == "added"
    assert changes_by_name["requests"]["change_type"] == "removed"
    assert changes_by_name["lodash"]["change_type"] == "upgraded"
    assert changes_by_name["lodash"]["previous_version"] == "4.17.20"
    assert changes_by_name["lodash"]["current_version"] == "4.18.0"
    assert changes_by_name["lodash"]["previous_license"] == "MIT"
    assert changes_by_name["lodash"]["current_license"] == "BSD-3-Clause"
    assert "license-changed" in changes_by_name["lodash"]["change_types"]
    assert changes_by_name["left-pad"]["change_type"] == "downgraded"
    assert changes_by_name["mystery"]["change_type"] == "version-changed"
    assert changes_by_name["license-only"]["change_type"] == "license-changed"
    assert changes_by_name["license-only"]["version_changed"] is False
    assert changes_by_name["license-only"]["license_changed"] is True


def test_dashboard_dependency_delta_empty_states(tmp_path: Path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="first-20260101T000000Z",
            repo_name="first",
            repo_path="/tmp/first",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "first-only-report.json"),
            sbom_components=[_component("lodash", "4.17.21", "MIT")],
        )
        db.save_scan(
            scan_id="empty-20260101T000000Z",
            repo_name="empty",
            repo_path="/tmp/empty",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "empty-first-report.json"),
            sbom_components=[_component("requests", "2.32.3", "Apache-2.0", ecosystem="pypi")],
        )
        db.save_scan(
            scan_id="empty-20260102T000000Z",
            repo_name="empty",
            repo_path="/tmp/empty",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="partial",
            scanner_statuses=[{"scanner": "syft", "available": False, "findings": 0, "error": "syft missing"}],
            findings=[],
            report_path=str(tmp_path / "empty-second-report.json"),
            sbom_components=[],
        )

        summary = db.dashboard_payload()
    finally:
        db.close()

    first_delta = next(item for item in summary["repos"] if item["repo"] == "first")["dependency_delta"]
    empty_delta = next(item for item in summary["repos"] if item["repo"] == "empty")["dependency_delta"]

    assert first_delta["status"] == "first-scan"
    assert first_delta["previous_scan_id"] is None
    assert first_delta["changes"] == []
    assert empty_delta["status"] == "no-sbom"
    assert empty_delta["previous_scan_id"] == "empty-20260101T000000Z"
    assert empty_delta["current_count"] == 0
    assert empty_delta["previous_count"] == 1
    assert empty_delta["changes"] == []
    assert "did not save an SBOM" in empty_delta["comparison_explanation"]


def test_dependency_changes_without_vulnerability_findings_stay_visible(tmp_path: Path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "trivy", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "first-report.json"),
            sbom_components=[_component("plain-change", "1.0.0", "MIT")],
        )
        db.save_scan(
            scan_id="repo-20260102T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "trivy", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "second-report.json"),
            sbom_components=[_component("plain-change", "1.1.0", "MIT")],
        )

        summary = db.dashboard_payload()
    finally:
        db.close()

    delta = summary["repos"][0]["dependency_delta"]
    assert delta["status"] == "changed"
    assert delta["counts"]["version-changed"] == 1
    assert delta["cve_counts"]["no-cve"] == 1
    change = delta["changes"][0]
    assert change["name"] == "plain-change"
    assert change["cve_status"] == "no-cve"
    assert change["cve_label"] == "No CVE found"
    assert change["match_label"] == "Strong match"


def test_dependency_change_metadata_labels_missing_version_purl_and_unknown_ecosystem(tmp_path: Path):
    first_component = SBOMComponent(
        name="mystery",
        version=None,
        ecosystem=None,
        component_type="library",
        package_url=None,
        license="MIT",
        supplier=None,
        source_path="lockfile",
    )
    second_component = SBOMComponent(
        name="mystery",
        version=None,
        ecosystem=None,
        component_type="library",
        package_url=None,
        license="Apache-2.0",
        supplier=None,
        source_path="lockfile",
    )
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "first-report.json"),
            sbom_components=[first_component],
        )
        db.save_scan(
            scan_id="repo-20260102T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "second-report.json"),
            sbom_components=[second_component],
        )

        summary = db.dashboard_payload()
    finally:
        db.close()

    change = summary["repos"][0]["dependency_delta"]["changes"][0]
    assert change["change_type"] == "license-changed"
    assert change["match_confidence"] == "weak-match"
    assert change["cve_status"] == "not-checked"
    assert change["cve_label"] == "Not checked"
    assert change["metadata_warnings"] == ["Missing version", "Missing purl", "Unknown ecosystem"]


def test_silent_direct_dependency_added_without_manifest_change_is_flagged(tmp_path: Path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    manifest = [_manifest("npm", "left-pad", "^1.0.0")]
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "first-report.json"),
            sbom_components=[_component("base", "1.0.0", "MIT")],
            dependency_manifest_entries=manifest,
        )
        db.save_scan(
            scan_id="repo-20260102T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "second-report.json"),
            sbom_components=[_component("base", "1.0.0", "MIT"), _component("left-pad", "1.0.0", "MIT")],
            dependency_manifest_entries=manifest,
        )

        summary = db.dashboard_payload()
    finally:
        db.close()

    change = next(item for item in summary["repos"][0]["dependency_delta"]["changes"] if item["name"] == "left-pad")
    assert change["silent_upgrade"]["status"] == "flagged"
    assert change["silent_upgrade"]["kind"] == "direct"
    assert change["silent_upgrade"]["label"] == "Silent direct upgrade"


def test_silent_major_version_jump_emits_case_but_patch_upgrade_does_not():
    manifest = [_manifest("npm", "left-pad", "^1.0.0")]

    major_findings = detect_silent_upgrades(
        repo_name="repo",
        scan_id="repo-20260102T000000Z",
        current_components=[_component("left-pad", "2.0.0", "MIT")],
        previous_components=[_component("left-pad", "1.9.0", "MIT").to_dict()],
        current_manifest_entries=manifest,
        previous_manifest_entries=manifest,
    )
    patch_findings = detect_silent_upgrades(
        repo_name="repo",
        scan_id="repo-20260103T000000Z",
        current_components=[_component("left-pad", "1.9.1", "MIT")],
        previous_components=[_component("left-pad", "1.9.0", "MIT").to_dict()],
        current_manifest_entries=manifest,
        previous_manifest_entries=manifest,
    )

    assert len(major_findings) == 1
    assert major_findings[0].category == "silent-upgrade"
    assert major_findings[0].severity == "medium"
    assert "Verify" in major_findings[0].remediation
    assert patch_findings == []


def test_silent_transitive_dependency_added_without_manifest_involvement_is_flagged(tmp_path: Path):
    manifest = [_manifest("npm", "direct-app", "^1.0.0")]
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "first-report.json"),
            sbom_components=[_component("direct-app", "1.0.0", "MIT")],
            dependency_manifest_entries=manifest,
        )
        db.save_scan(
            scan_id="repo-20260102T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "second-report.json"),
            sbom_components=[_component("direct-app", "1.0.0", "MIT"), _component("transitive-lib", "3.0.0", "MIT")],
            dependency_manifest_entries=manifest,
        )

        summary = db.dashboard_payload()
    finally:
        db.close()

    change = next(item for item in summary["repos"][0]["dependency_delta"]["changes"] if item["name"] == "transitive-lib")
    assert change["silent_upgrade"]["status"] == "flagged"
    assert change["silent_upgrade"]["kind"] == "transitive"
    assert change["silent_upgrade"]["label"] == "Silent transitive upgrade"


def test_manifest_change_with_matching_lockfile_change_is_not_silent(tmp_path: Path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "first-report.json"),
            sbom_components=[_component("base", "1.0.0", "MIT")],
            dependency_manifest_entries=[],
        )
        db.save_scan(
            scan_id="repo-20260102T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "second-report.json"),
            sbom_components=[_component("base", "1.0.0", "MIT"), _component("left-pad", "1.0.0", "MIT")],
            dependency_manifest_entries=[_manifest("npm", "left-pad", "^1.0.0")],
        )

        summary = db.dashboard_payload()
    finally:
        db.close()

    change = next(item for item in summary["repos"][0]["dependency_delta"]["changes"] if item["name"] == "left-pad")
    assert change["silent_upgrade"]["status"] == "explained"
    assert change["silent_upgrade"]["label"] == "Manifest changed"


def test_scan_repo_persists_components_when_syft_writes_sbom(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"

    def fake_run_scanner(scanner, repo, repo_name, scan_dir, rules_dir):
        sbom_path = scan_dir / "sbom.cyclonedx.json"
        sbom_path.write_text(json.dumps(_cyclonedx_fixture()), encoding="utf-8")
        status = ScannerStatus(
            scanner="syft",
            available=True,
            command=["syft"],
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            sbom_report=str(sbom_path),
        )
        return ScannerResult(status=status, findings=[], sbom_created=True)

    monkeypatch.setattr(scan_module, "scanner_names_for_profile", lambda args: ["syft"])
    monkeypatch.setattr(scan_module, "run_scanner", fake_run_scanner)

    summary = scan_module.scan_repo(repo, _deps_args(), home)
    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        rows = db.list_sbom_components(repo_name="repo")
    finally:
        db.close()

    assert summary["status"] == "ok"
    assert len(rows) == 1
    assert rows[0]["scan_id"] == summary["scan_id"]
    assert rows[0]["repo_name"] == "repo"
    assert rows[0]["name"] == "lodash"


def test_scan_repo_handles_missing_syft_without_crashing(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"

    def fake_missing_syft(scanner, repo, repo_name, scan_dir, rules_dir):
        status = ScannerStatus(
            scanner="syft",
            available=False,
            command=["syft"],
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            error="syft is not installed or not on PATH.",
        )
        return ScannerResult(status=status, findings=[], sbom_created=False)

    monkeypatch.setattr(scan_module, "scanner_names_for_profile", lambda args: ["syft"])
    monkeypatch.setattr(scan_module, "run_scanner", fake_missing_syft)

    summary = scan_module.scan_repo(repo, _deps_args(), home)
    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        rows = db.list_sbom_components(repo_name="repo")
    finally:
        db.close()

    assert summary["status"] == "partial"
    assert rows == []


def test_scan_repo_persists_partial_sbom_when_syft_reports_error(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"

    def fake_failing_syft(scanner, repo, repo_name, scan_dir, rules_dir):
        sbom_path = scan_dir / "sbom.cyclonedx.json"
        sbom_path.write_text(
            json.dumps({"bomFormat": "CycloneDX", "components": [{"type": "library", "name": "partial-package"}]}),
            encoding="utf-8",
        )
        status = ScannerStatus(
            scanner="syft",
            available=True,
            command=["syft"],
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            sbom_report=str(sbom_path),
            error="syft exited after writing partial metadata.",
        )
        return ScannerResult(status=status, findings=[], sbom_created=True)

    monkeypatch.setattr(scan_module, "scanner_names_for_profile", lambda args: ["syft"])
    monkeypatch.setattr(scan_module, "run_scanner", fake_failing_syft)

    summary = scan_module.scan_repo(repo, _deps_args(), home)
    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        rows = db.list_sbom_components(repo_name="repo")
    finally:
        db.close()

    assert summary["status"] == "partial"
    assert len(rows) == 1
    assert rows[0]["name"] == "partial-package"
    assert rows[0]["package_url"] is None
    assert rows[0]["version"] is None


def _cyclonedx_fixture(version: str = "4.17.21") -> dict:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "components": [
            {
                "bom-ref": f"pkg:npm/lodash@{version}",
                "type": "library",
                "name": "lodash",
                "version": version,
                "purl": f"pkg:npm/lodash@{version}",
                "supplier": {"name": "OpenJS Foundation"},
                "licenses": [{"license": {"id": "MIT"}}],
                "properties": [{"name": "syft:location:0:path", "value": "package-lock.json"}],
            }
        ],
    }


def _deps_args() -> SimpleNamespace:
    return SimpleNamespace(
        quick=False,
        code=False,
        ai=False,
        deps=True,
        secrets=False,
        iac=False,
        full=False,
    )


def _component(
    name: str,
    version: str | None,
    license: str | None,
    *,
    ecosystem: str = "npm",
) -> SBOMComponent:
    package_url = f"pkg:{ecosystem}/{name}@{version}" if version else f"pkg:{ecosystem}/{name}"
    return SBOMComponent(
        name=name,
        version=version,
        ecosystem=ecosystem,
        component_type="library",
        package_url=package_url,
        license=license,
        supplier=None,
        source_path="lockfile",
    )


def _manifest(ecosystem: str, name: str, declaration: str) -> dict[str, str]:
    return {
        "manifest_path": "package.json" if ecosystem == "npm" else "requirements.txt",
        "ecosystem": ecosystem,
        "name": name,
        "declaration": declaration,
        "normalized_declaration": declaration.strip().casefold(),
        "scope": "dependencies",
        "manifest_fingerprint": "fixture-manifest",
    }
