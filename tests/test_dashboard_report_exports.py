import sqlite3

from security_observatory.cases import build_security_cases
from security_observatory.dashboard_pages import build_ai_prompt, prompt_report_page, raw_report_fallback, raw_report_page
from security_observatory.model import Finding
from security_observatory.storage import ObservatoryDB


def test_scan_export_reconstructs_report_data(tmp_path):
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
            findings=[
                Finding(
                    repo="repo",
                    scanner="semgrep",
                    severity="high",
                    category="code-security",
                    title="Unsafe parser",
                    file="app.py",
                    line=12,
                    remediation="Use a safe parser.",
                )
            ],
            report_path=str(tmp_path / "missing-normalized-report.json"),
        )
        scan = db.scan_export("repo-20260101T000000Z")
    finally:
        db.close()

    assert scan is not None
    report = raw_report_fallback(scan)
    assert report["scan_id"] == "repo-20260101T000000Z"
    assert report["severity_counts"]["high"] == 1
    assert report["category_counts"]["code-security"] == 1
    assert report["cases"][0]["title"] == "Unsafe parser"


def test_dashboard_payload_exposes_detection_backed_tool_catalog(tmp_path, monkeypatch):
    def fake_which(binary: str) -> str | None:
        return f"/usr/local/bin/{binary}" if binary == "semgrep" else None

    monkeypatch.setattr("security_observatory.catalog.shutil.which", fake_which)

    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        summary = db.dashboard_payload()
    finally:
        db.close()

    catalog = {item["id"]: item for item in summary["tool_catalog"]}
    packs = {item["id"]: item for item in summary["security_packs"]}
    profiles = {item["id"]: item for item in summary["scan_profiles"]}
    assert summary["scanner_catalog"]
    assert packs["starter"]["primary_profile"] == "quick"
    assert profiles["quick"]["recommended_pack_ids"] == ["starter"]
    assert profiles["quick"]["recommended_packs"][0]["id"] == "starter"
    assert catalog["semgrep"]["install_state"] == "detected"
    assert "Detected locally" in catalog["semgrep"]["derived_labels"]["install"]
    assert catalog["semgrep"]["policy"]["allowed_for_agent_lab"] is True
    assert catalog["semgrep"]["legacy_scanner"]["scanner"] == "semgrep"
    assert catalog["external-surface"]["install_state"] == "coming-soon"
    assert "Display only" in catalog["external-surface"]["derived_labels"]["safety"]
    assert "Coming soon" in catalog["external-surface"]["derived_labels"]["install"]
    assert catalog["external-surface"]["derived_labels"]["agent_lab"] == "Agent Lab blocked"


def test_ai_prompt_instructs_verification_before_fixes():
    prompt = build_ai_prompt(
        {
            "scan_id": "repo-20260101T000000Z",
            "repo": "repo",
            "repo_path": "/tmp/repo",
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:01:00+00:00",
            "profile": "quick",
            "health_score": 80,
            "status": "ok",
            "scanners": [],
            "findings": [
                {
                    "scanner": "semgrep",
                    "severity": "high",
                    "category": "code-security",
                    "title": "Unsafe parser",
                    "file": "app.py",
                    "line": 12,
                    "remediation": "Use a safe parser.",
                    "fingerprint": "abc123",
                }
            ],
        }
    )

    assert "First verify each case" in prompt
    assert "Code vulnerabilities" in prompt
    assert "app.py:12" in prompt
    assert "fix plan ordered by action level" in prompt


def test_prompt_report_page_has_dashboard_return_and_case_content():
    page = prompt_report_page(
        {
            "scan_id": "repo-20260101T000000Z",
            "repo": "repo",
            "repo_path": "/tmp/repo",
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:01:00+00:00",
            "profile": "quick",
            "health_score": 80,
            "status": "ok",
            "scanners": [],
            "findings": [
                {
                    "scanner": "semgrep",
                    "severity": "high",
                    "category": "code-security",
                    "title": "Unsafe parser",
                    "file": "app.py",
                    "line": 12,
                    "remediation": "Use a safe parser.",
                    "fingerprint": "abc123",
                }
            ],
        }
    )

    assert "Back To Dashboard" in page
    assert "AI Handoff Prompt" in page
    assert "Unsafe parser" in page
    assert "Download Markdown" in page


def test_raw_report_page_has_dashboard_return_and_json_content():
    page = raw_report_page(
        {
            "scan_id": "repo-20260101T000000Z",
            "repo": "repo",
            "repo_path": "/tmp/repo",
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:01:00+00:00",
            "profile": "quick",
            "health_score": 80,
            "status": "ok",
            "scanners": [],
            "findings": [],
        }
    )

    assert "Back To Dashboard" in page
    assert "Full Report" in page
    assert "&quot;scan_id&quot;" in page


def test_existing_case_decisions_migrate_with_default_vex_status(tmp_path):
    db_path = tmp_path / "observatory.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            create table case_decisions (
              case_id text primary key,
              repo_name text not null,
              status text not null,
              note text,
              created_at text not null,
              updated_at text not null
            )
            """
        )
        conn.execute(
            "insert into case_decisions values (?, ?, ?, ?, ?, ?)",
            (
                "case-legacy",
                "repo",
                "false_positive",
                "Synthetic fixture is not used at runtime.",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    db = ObservatoryDB(db_path)
    try:
        decision = db.case_decisions_map()["case-legacy"]
    finally:
        db.close()

    assert decision["status"] == "false_positive"
    assert decision["vex_status"] == "not_affected"
    assert decision["vex_reason"] == "Synthetic fixture is not used at runtime."


def test_same_package_cve_dependency_decision_suppresses_active_report_counts(tmp_path):
    first = _dependency_finding(
        scanner="trivy",
        package="lodash",
        vulnerability="CVE-2026-1000",
        file="package-lock.json",
        fingerprint="first-lodash",
    )
    second = _dependency_finding(
        scanner="osv-scanner",
        package="lodash",
        vulnerability="CVE-2026-1000",
        file="pnpm-lock.yaml",
        fingerprint="second-lodash",
    )
    first_cases = build_security_cases([first], [{"scanner": "trivy", "available": True, "findings": 1}], {"repo": "repo"})
    second_cases = build_security_cases([second], [{"scanner": "osv-scanner", "available": True, "findings": 1}], {"repo": "repo"})
    assert first_cases[0].case_id != second_cases[0].case_id

    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        _save_dependency_scan(db, tmp_path, "repo-20260101T000000Z", [first], first_cases)
        decision = db.set_case_decision(
            case_id=first_cases[0].case_id,
            repo_name="repo",
            status="false_positive",
            note="The vulnerable lodash path is not present in this app bundle.",
            human_authorized=True,
        )
        _save_dependency_scan(db, tmp_path, "repo-20260102T000000Z", [second], second_cases)
        summary = db.dashboard_payload()
        scan = db.scan_export("repo-20260102T000000Z")
    finally:
        db.close()

    assert decision is not None
    assert decision["vex_status"] == "not_affected"
    assert decision["vex_reason"] == "The vulnerable lodash path is not present in this app bundle."
    assert summary["repos"][0]["counts"].get("high", 0) == 0
    assert summary["repos"][0]["raw_counts"]["high"] == 1
    assert summary["repos"][0]["case_counts"]["severity"] == {}
    assert summary["repos"][0]["suppressed_counts"]["findings"] == 1
    assert summary["suppressed_findings"][0]["package_name"] == "lodash"
    assert summary["suppressed_cases"][0]["suppression"]["matched_by"] == "dependency_identity"
    assert summary["suppression_reasons"][0]["reason"] == "The vulnerable lodash path is not present in this app bundle."
    assert scan is not None
    assert scan["active_findings"] == []
    assert scan["suppressed_findings"][0]["fingerprint"] == "second-lodash"

    report = raw_report_fallback(scan)
    assert report["severity_counts"].get("high", 0) == 0
    assert report["raw_severity_counts"]["high"] == 1
    assert report["suppressed_counts"]["findings"] == 1


def test_dependency_suppression_requires_human_reason(tmp_path):
    finding = _dependency_finding(
        scanner="trivy",
        package="lodash",
        vulnerability="CVE-2026-1000",
        file="package-lock.json",
        fingerprint="lodash-needs-reason",
    )
    cases = build_security_cases([finding], [{"scanner": "trivy", "available": True, "findings": 1}], {"repo": "repo"})
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        _save_dependency_scan(db, tmp_path, "repo-20260101T000000Z", [finding], cases)
        try:
            # human_authorized=True clears the severity gate so this exercises
            # the separate dependency-justification guard.
            db.set_case_decision(case_id=cases[0].case_id, repo_name="repo", status="false_positive", human_authorized=True)
        except ValueError as exc:
            error = str(exc)
        else:
            error = ""
    finally:
        db.close()

    assert "human-readable justification" in error


def test_dependency_suppression_does_not_hide_unrelated_package_with_same_cve(tmp_path):
    lodash = _dependency_finding(
        scanner="trivy",
        package="lodash",
        vulnerability="CVE-2026-1000",
        file="package-lock.json",
        fingerprint="lodash-cve",
    )
    express = _dependency_finding(
        scanner="osv-scanner",
        package="express",
        vulnerability="CVE-2026-1000",
        file="pnpm-lock.yaml",
        fingerprint="express-cve",
    )
    lodash_cases = build_security_cases([lodash], [{"scanner": "trivy", "available": True, "findings": 1}], {"repo": "repo"})
    express_cases = build_security_cases([express], [{"scanner": "osv-scanner", "available": True, "findings": 1}], {"repo": "repo"})

    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        _save_dependency_scan(db, tmp_path, "repo-20260101T000000Z", [lodash], lodash_cases)
        db.set_case_decision(
            case_id=lodash_cases[0].case_id,
            repo_name="repo",
            status="false_positive",
            note="The vulnerable lodash path is not present in this app bundle.",
            human_authorized=True,
        )
        _save_dependency_scan(db, tmp_path, "repo-20260102T000000Z", [express], express_cases)
        summary = db.dashboard_payload()
        scan = db.scan_export("repo-20260102T000000Z")
    finally:
        db.close()

    assert summary["repos"][0]["counts"]["high"] == 1
    assert summary["repos"][0]["suppressed_counts"]["findings"] == 0
    assert summary["suppressed_findings"] == []
    assert scan is not None
    assert scan["active_findings"][0]["package_name"] == "express"
    assert scan["suppressed_findings"] == []


def _dependency_finding(*, scanner: str, package: str, vulnerability: str, file: str, fingerprint: str) -> Finding:
    return Finding(
        repo="repo",
        scanner=scanner,
        severity="high",
        category="dependencies",
        title=f"{vulnerability} in {package}",
        file=file,
        remediation=f"Upgrade {package}.",
        vulnerability_id=vulnerability,
        package_name=package,
        package_version="1.0.0",
        package_ecosystem="npm",
        package_url=f"pkg:npm/{package}@1.0.0",
        fingerprint=fingerprint,
    )


def _save_dependency_scan(db: ObservatoryDB, tmp_path, scan_id: str, findings: list[Finding], cases) -> None:
    db.save_scan(
        scan_id=scan_id,
        repo_name="repo",
        repo_path="/tmp/repo",
        started_at=scan_id.replace("repo-", "").replace("Z", "+00:00"),
        finished_at=scan_id.replace("repo-", "").replace("Z", "+00:00"),
        profile="deps",
        health_score=80,
        status="ok",
        scanner_statuses=[{"scanner": findings[0].scanner if findings else "osv-scanner", "available": True, "findings": len(findings)}],
        findings=findings,
        report_path=str(tmp_path / f"{scan_id}.json"),
        cases=cases,
    )
