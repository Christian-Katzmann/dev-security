from security_observatory.cases import build_security_cases
from security_observatory.dashboard_server import build_ai_prompt, raw_report_fallback
from security_observatory.enrichment import correlate_dependency_findings
from security_observatory.model import Finding
from security_observatory.sbom import SBOMComponent
from security_observatory.storage import ObservatoryDB


def test_duplicate_dependency_findings_become_one_case():
    findings = [
        Finding(repo="repo", scanner="trivy", severity="high", category="dependencies", title="CVE-2026-1000 in lodash", file="package-lock.json"),
        Finding(repo="repo", scanner="osv-scanner", severity="high", category="dependencies", title="CVE-2026-1000 in lodash", file="package-lock.json"),
        Finding(repo="repo", scanner="grype", severity="critical", category="dependencies", title="CVE-2026-1000 in lodash", file="package-lock.json"),
    ]

    cases = build_security_cases(findings, [], {"repo": "repo"})

    assert len(cases) == 1
    assert cases[0].title == "lodash dependency vulnerability CVE-2026-1000"
    assert cases[0].severity == "critical"
    assert cases[0].confidence == "high"
    assert cases[0].scanners == ["grype", "osv-scanner", "trivy"]
    assert len(cases[0].source_fingerprints) == 3


def test_secret_findings_become_fix_now_cases():
    cases = build_security_cases(
        [
            Finding(
                repo="repo",
                scanner="gitleaks",
                severity="critical",
                category="secrets",
                title="Generic API Key",
                file=".env",
                line=3,
            )
        ],
        [],
        {"repo": "repo"},
    )

    assert cases[0].action_level == "fix_now"
    assert "credential may be exposed" in cases[0].plain_english_risk
    assert "Rotate or revoke" in " ".join(cases[0].fix_steps)


def test_missing_scanner_evidence_is_reflected_in_report():
    report = raw_report_fallback(
        {
            "scan_id": "repo-20260101T000000Z",
            "repo": "repo",
            "repo_path": "/tmp/repo",
            "report_path": None,
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:01:00+00:00",
            "profile": "deps",
            "health_score": 90,
            "status": "partial",
            "scanners": [
                {"scanner": "trivy", "available": True, "findings": 0},
                {"scanner": "grype", "available": False, "error": "not installed"},
            ],
            "findings": [],
        }
    )

    assert report["evidence_gaps"][0]["scanner"] == "grype"
    assert report["evidence_gaps"][0]["reason"] == "not installed"
    assert report["evidence_gaps"][0]["tool_id"] == "grype"
    assert report["evidence_gaps"][0]["recommended_pack_ids"] == ["dependencies"]
    assert report["evidence_gaps"][0]["recommended_profile_id"] == "deps"
    assert report["cases"] == []
    assert report["findings"] == []


def test_ai_prompt_is_case_first_with_evidence_verification_and_fix_steps():
    prompt = build_ai_prompt(
        {
            "scan_id": "repo-20260101T000000Z",
            "repo": "repo",
            "repo_path": "/tmp/repo",
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:01:00+00:00",
            "profile": "deps",
            "health_score": 70,
            "status": "ok",
            "scanners": [{"scanner": "trivy", "available": True, "findings": 1}],
            "findings": [
                {
                    "scanner": "trivy",
                    "severity": "high",
                    "category": "dependencies",
                    "title": "CVE-2026-1000 in lodash",
                    "file": "package-lock.json",
                    "line": None,
                    "remediation": "Upgrade lodash.",
                    "fingerprint": "abc123",
                }
            ],
        }
    )

    assert "Cases to verify and fix" in prompt
    assert "lodash dependency vulnerability CVE-2026-1000" in prompt
    assert "Evidence:" in prompt
    assert "trivy: CVE-2026-1000 in lodash at package-lock.json" in prompt
    assert "Verification steps:" in prompt
    assert "Fix steps:" in prompt
    assert "Upgrade lodash." in prompt


def test_cases_are_persisted_and_exported(tmp_path):
    finding = Finding(repo="repo", scanner="gitleaks", severity="critical", category="secrets", title="Generic API Key", file=".env", line=3)
    cases = build_security_cases([finding], [{"scanner": "gitleaks", "available": True, "findings": 1}], {"repo": "repo"})
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="secrets",
            health_score=60,
            status="ok",
            scanner_statuses=[{"scanner": "gitleaks", "available": True, "findings": 1}],
            findings=[finding],
            report_path=str(tmp_path / "normalized-report.json"),
            cases=cases,
        )
        decision = db.set_case_decision(
            case_id=cases[0].case_id,
            repo_name="repo",
            status="false_positive",
            note="Synthetic fixture value.",
        )
        scan = db.scan_export("repo-20260101T000000Z")
        summary = db.dashboard_payload()
    finally:
        db.close()

    assert decision is not None
    assert decision["status"] == "false_positive"
    assert scan is not None
    assert scan["cases"][0]["action_level"] == "fix_now"
    assert scan["cases"][0]["decision"]["note"] == "Synthetic fixture value."
    assert summary["repos"][0]["case_counts"]["action_level"]["fix_now"] == 1
    assert summary["cases"][0]["title"] == scan["cases"][0]["title"]
    assert summary["cases"][0]["decision"]["status"] == "false_positive"
    assert summary["case_decisions"][0]["case_id"] == cases[0].case_id


def test_fixed_case_still_appears_when_latest_scan_finds_it_again(tmp_path):
    finding = Finding(repo="repo", scanner="semgrep", severity="high", category="code-security", title="Unsafe parser", file="app.py", line=12)
    cases = build_security_cases([finding], [{"scanner": "semgrep", "available": True, "findings": 1}], {"repo": "repo"})
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="quick",
            health_score=80,
            status="ok",
            scanner_statuses=[{"scanner": "semgrep", "available": True, "findings": 1}],
            findings=[finding],
            report_path=str(tmp_path / "normalized-report.json"),
            cases=cases,
        )
        db.set_case_decision(case_id=cases[0].case_id, repo_name="repo", status="fixed")
        summary = db.dashboard_payload()
    finally:
        db.close()

    assert summary["cases"]
    assert summary["cases"][0]["case_id"] == cases[0].case_id
    assert summary["cases"][0]["decision"]["status"] == "fixed"


def test_dashboard_marks_new_recurring_and_resolved_cases(tmp_path):
    recurring = Finding(repo="repo", scanner="semgrep", severity="high", category="code-security", title="Unsafe parser", file="app.py", line=12)
    resolved = Finding(repo="repo", scanner="gitleaks", severity="critical", category="secrets", title="Generic API Key", file=".env", line=3)
    new = Finding(repo="repo", scanner="osv-scanner", severity="high", category="dependencies", title="CVE-2026-1000 in lodash", file="package-lock.json")
    scanner_statuses = [{"scanner": "semgrep", "available": True, "findings": 1}]
    first_cases = build_security_cases([recurring, resolved], scanner_statuses, {"repo": "repo"})
    second_cases = build_security_cases([recurring, new], scanner_statuses, {"repo": "repo"})
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="quick",
            health_score=70,
            status="ok",
            scanner_statuses=scanner_statuses,
            findings=[recurring, resolved],
            report_path=str(tmp_path / "first-report.json"),
            cases=first_cases,
        )
        db.save_scan(
            scan_id="repo-20260102T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            profile="quick",
            health_score=82,
            status="ok",
            scanner_statuses=scanner_statuses,
            findings=[recurring, new],
            report_path=str(tmp_path / "second-report.json"),
            cases=second_cases,
        )
        summary = db.dashboard_payload()
    finally:
        db.close()

    repo = summary["repos"][0]
    cases_by_id = {case["case_id"]: case for case in summary["cases"]}
    recurring_case = next(case for case in second_cases if case.title == "Unsafe parser")
    new_case = next(case for case in second_cases if "lodash" in case.title)
    resolved_case = next(case for case in first_cases if "credential" in case.title)

    assert repo["previous_scan_id"] == "repo-20260101T000000Z"
    assert repo["previous_health"] == 70
    assert repo["health_delta"] == 12
    assert repo["case_delta"] == {"new": 1, "recurring": 1, "resolved": 1}
    assert cases_by_id[recurring_case.case_id]["change_status"] == "recurring"
    assert cases_by_id[new_case.case_id]["change_status"] == "new"
    assert cases_by_id[resolved_case.case_id]["change_status"] == "resolved"
    assert cases_by_id[resolved_case.case_id]["resolved_by_scan_id"] == "repo-20260102T000000Z"


def test_package_upgrade_can_introduce_dependency_vulnerability(tmp_path):
    first_components = [_component("lodash", "4.17.20")]
    second_components = [_component("lodash", "4.18.0")]
    introduced = correlate_dependency_findings(
        [
            Finding(
                repo="repo",
                scanner="trivy",
                severity="high",
                category="dependencies",
                title="CVE-2026-2000 in lodash",
                file="package-lock.json",
                vulnerability_id="CVE-2026-2000",
                package_name="lodash",
                package_version="4.18.0",
                package_ecosystem="npm",
                package_url="pkg:npm/lodash@4.18.0",
            )
        ],
        second_components,
    )
    second_cases = build_security_cases(introduced, [{"scanner": "trivy", "available": True, "findings": 1}], {"repo": "repo"})
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
            cases=[],
            sbom_components=first_components,
        )
        db.save_scan(
            scan_id="repo-20260102T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            profile="deps",
            health_score=80,
            status="ok",
            scanner_statuses=[{"scanner": "trivy", "available": True, "findings": 1}],
            findings=introduced,
            report_path=str(tmp_path / "second-report.json"),
            cases=second_cases,
            sbom_components=second_components,
        )
        summary = db.dashboard_payload()
    finally:
        db.close()

    case = next(item for item in summary["cases"] if "lodash" in item["title"])
    repo = summary["repos"][0]
    assert case["change_status"] == "new"
    assert case["risk_movement"] == "vulnerability-introduced"
    assert "changed from 4.17.20 to 4.18.0" in case["risk_movement_reason"]
    assert repo["dependency_delta"]["risk_counts"]["vulnerability-introduced"] == 1


def test_package_upgrade_can_fix_dependency_vulnerability(tmp_path):
    first_components = [_component("lodash", "4.17.20")]
    second_components = [_component("lodash", "4.17.21")]
    fixed_finding = correlate_dependency_findings(
        [
            Finding(
                repo="repo",
                scanner="osv-scanner",
                severity="high",
                category="dependencies",
                title="CVE-2026-3000 in lodash",
                file="package-lock.json",
                remediation="Upgrade lodash to 4.17.21.",
                vulnerability_id="CVE-2026-3000",
                package_name="lodash",
                package_version="4.17.20",
                package_ecosystem="npm",
                package_url="pkg:npm/lodash@4.17.20",
                fixed_version="4.17.21",
            )
        ],
        first_components,
    )
    first_cases = build_security_cases(fixed_finding, [{"scanner": "osv-scanner", "available": True, "findings": 1}], {"repo": "repo"})
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="deps",
            health_score=80,
            status="ok",
            scanner_statuses=[{"scanner": "osv-scanner", "available": True, "findings": 1}],
            findings=fixed_finding,
            report_path=str(tmp_path / "first-report.json"),
            cases=first_cases,
            sbom_components=first_components,
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
            scanner_statuses=[{"scanner": "osv-scanner", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "second-report.json"),
            cases=[],
            sbom_components=second_components,
        )
        summary = db.dashboard_payload()
    finally:
        db.close()

    case = next(item for item in summary["cases"] if item.get("change_status") == "resolved")
    repo = summary["repos"][0]
    assert case["risk_movement"] == "vulnerability-fixed"
    assert "changed from 4.17.20 to 4.17.21" in case["risk_movement_reason"]
    assert "latest scan no longer finds this issue" in case["plain_english_risk"]
    assert repo["dependency_delta"]["risk_counts"]["vulnerability-fixed"] == 1


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
