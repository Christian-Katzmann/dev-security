from security_observatory.cases import build_security_cases
from security_observatory.model import Finding
from security_observatory.storage import ObservatoryDB


def test_vex_export_includes_accepted_and_not_affected_dependency_decisions(tmp_path):
    lodash = _dependency_finding(package="lodash", vulnerability="CVE-2026-1000", fingerprint="lodash-cve")
    express = _dependency_finding(package="express", vulnerability="GHSA-2026-abcd", fingerprint="express-ghsa")
    secret = Finding(repo="repo", scanner="gitleaks", severity="critical", category="secrets", title="Generic API Key", file=".env")
    cases = build_security_cases([lodash, express, secret], [{"scanner": "osv-scanner", "available": True, "findings": 2}], {"repo": "repo"})

    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        _save_scan(db, tmp_path, "repo-20260101T000000Z", [lodash, express, secret], cases)
        lodash_case = next(case for case in cases if "lodash" in case.title)
        express_case = next(case for case in cases if "express" in case.title)
        secret_case = next(case for case in cases if case.category == "secrets")
        db.set_case_decision(
            case_id=lodash_case.case_id,
            repo_name="repo",
            status="false_positive",
            note="The vulnerable lodash code is not reachable in this app.",
        )
        db.set_case_decision(
            case_id=express_case.case_id,
            repo_name="repo",
            status="accepted_risk",
            note="Temporarily accepted until the upstream patch lands.",
        )
        db.set_case_decision(case_id=secret_case.case_id, repo_name="repo", status="false_positive", note="Synthetic fixture.")
        document = db.export_vex_decisions(tool_version="test")
    finally:
        db.close()

    statements = document["statements"]
    statuses = {statement["status"] for statement in statements}
    products = {statement["products"][0]["@id"] for statement in statements}
    assert document["@context"] == "https://openvex.dev/ns/v0.2.0"
    assert len(statements) == 2
    assert statuses == {"not_affected", "affected"}
    assert "pkg:npm/lodash@1.0.0" in products
    assert "pkg:npm/express@1.0.0" in products
    assert all(statement["metadata"]["repo_name"] == "repo" for statement in statements)


def test_vex_import_applies_matching_decision_to_future_scans(tmp_path):
    document = {
        "@context": "https://openvex.dev/ns/v0.2.0",
        "statements": [
            {
                "vulnerability": {"name": "CVE-2026-1000"},
                "products": [{"@id": "pkg:npm/lodash@1.0.0"}],
                "status": "not_affected",
                "impact_statement": "The vulnerable lodash path is not shipped in this app.",
            }
        ],
    }
    finding = _dependency_finding(package="lodash", vulnerability="CVE-2026-1000", fingerprint="future-lodash")
    cases = build_security_cases([finding], [{"scanner": "osv-scanner", "available": True, "findings": 1}], {"repo": "repo"})

    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        result = db.import_vex_decisions(document, repo_name="repo")
        _save_scan(db, tmp_path, "repo-20260102T000000Z", [finding], cases)
        summary = db.dashboard_payload()
    finally:
        db.close()

    assert result["imported"] == 1
    assert result["skipped"] == 0
    assert summary["repos"][0]["counts"].get("high", 0) == 0
    assert summary["repos"][0]["raw_counts"]["high"] == 1
    assert summary["suppressed_cases"][0]["suppression"]["vex_status"] == "not_affected"
    assert summary["suppressed_cases"][0]["suppression"]["reason"] == "The vulnerable lodash path is not shipped in this app."
    assert summary["suppressed_findings"][0]["fingerprint"] == "future-lodash"


def test_vex_import_reads_cyclonedx_like_false_positive_alias(tmp_path):
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "components": [
            {"bom-ref": "pkg:pypi/django@5.0.0", "name": "django", "version": "5.0.0", "purl": "pkg:pypi/django@5.0.0"}
        ],
        "vulnerabilities": [
            {
                "id": "CVE-2026-2000",
                "analysis": {
                    "state": "false_positive",
                    "detail": "The affected optional parser is not installed.",
                },
                "affects": [{"ref": "pkg:pypi/django@5.0.0"}],
                "properties": [{"name": "security-observatory:repo_name", "value": "repo"}],
            }
        ],
    }
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        result = db.import_vex_decisions(document)
        decisions = db.case_decisions_map()
    finally:
        db.close()

    assert result["imported"] == 1
    decision = next(iter(decisions.values()))
    assert decision["status"] == "false_positive"
    assert decision["vex_status"] == "not_affected"
    assert decision["package_name"] == "django"
    assert decision["vex_reason"] == "The affected optional parser is not installed."


def test_vex_import_skips_unsupported_status_with_clear_note(tmp_path):
    document = {
        "statements": [
            {
                "vulnerability": {"name": "CVE-2026-1000"},
                "products": [{"@id": "pkg:npm/lodash@1.0.0"}],
                "status": "known_unknown",
                "impact_statement": "Unsupported status.",
            }
        ],
    }
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        result = db.import_vex_decisions(document, repo_name="repo")
    finally:
        db.close()

    assert result["imported"] == 0
    assert result["skipped"] == 1
    assert any("unsupported VEX status" in warning for warning in result["warnings"])


def _dependency_finding(*, package: str, vulnerability: str, fingerprint: str) -> Finding:
    return Finding(
        repo="repo",
        scanner="osv-scanner",
        severity="high",
        category="dependencies",
        title=f"{vulnerability} in {package}",
        file="package-lock.json",
        remediation=f"Upgrade {package}.",
        vulnerability_id=vulnerability,
        package_name=package,
        package_version="1.0.0",
        package_ecosystem="npm",
        package_url=f"pkg:npm/{package}@1.0.0",
        fingerprint=fingerprint,
    )


def _save_scan(db: ObservatoryDB, tmp_path, scan_id: str, findings: list[Finding], cases) -> None:
    db.save_scan(
        scan_id=scan_id,
        repo_name="repo",
        repo_path="/tmp/repo",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        profile="deps",
        health_score=80,
        status="ok",
        scanner_statuses=[{"scanner": "osv-scanner", "available": True, "findings": len(findings)}],
        findings=findings,
        report_path=str(tmp_path / f"{scan_id}.json"),
        cases=cases,
    )
