import json
import sqlite3

import pytest

from security_observatory import lifecycle
from security_observatory.cases import (
    apply_consequence_priority,
    build_recovery_playbooks,
    build_security_cases,
)
from security_observatory.dashboard_pages import build_ai_prompt, raw_report_fallback
from security_observatory.enrichment import correlate_dependency_findings
from security_observatory.model import Finding, SecurityCase
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


def test_recovery_playbooks_group_cases_by_class():
    findings = [
        Finding(repo="repo", scanner="gitleaks", severity="critical", category="secrets", title="Generic API Key", file=".env", line=3),
        Finding(repo="repo", scanner="gitleaks", severity="critical", category="secrets", title="Stripe live key", file="config/prod.yaml", line=11),
        Finding(repo="repo", scanner="trivy", severity="high", category="dependencies", title="CVE-2026-1000 in lodash", file="package-lock.json"),
        Finding(repo="repo", scanner="trivy", severity="high", category="dependencies", title="CVE-2026-2222 in axios", file="package-lock.json"),
        Finding(repo="repo", scanner="trivy", severity="medium", category="iac", title="S3 bucket is public", file="infra/main.tf", line=42),
        Finding(repo="repo", scanner="medusa", severity="high", category="ai-risk", title="MCP shell tool grant", file=".claude/mcp.json", line=8),
    ]

    cases = build_security_cases(findings, [], {"repo": "repo"})
    playbooks = build_recovery_playbooks(cases)

    by_id = {playbook["id"]: playbook for playbook in playbooks}
    assert set(by_id) == {
        "rotate-leaked-secret",
        "upgrade-vulnerable-dependency",
        "tighten-iac-exposure",
        "harden-ai-agent-config",
    }, "one playbook per case-class, not one per finding"

    # six findings condensed into four cards (one per class).
    assert len(playbooks) == 4

    # secrets playbook gathers both secret cases and instantiates the template with their files.
    secrets = by_id["rotate-leaked-secret"]
    assert secrets["case_count"] == 2
    assert secrets["title"] == "Rotate leaked secrets and scrub history"
    assert sorted(secrets["affected_files"]) == [".env", "config/prod.yaml"]
    secret_steps_joined = "\n".join(secrets["steps"])
    assert ".env" in secret_steps_joined and "config/prod.yaml" in secret_steps_joined
    assert "Rerun the matching DëvSec secrets check" in secret_steps_joined
    assert secrets["severity"] == "critical"
    assert secrets["estimated_minutes"] > 0
    assert secrets["estimate_label"].startswith("~ ")
    item_titles = [item["title"] for item in secrets["items"]]
    assert "Possible exposed credential in .env" in item_titles[0] or "Possible exposed credential" in item_titles[0]

    # dependency playbook gathers both CVE cases and only renders one card.
    deps = by_id["upgrade-vulnerable-dependency"]
    assert deps["case_count"] == 2
    assert "package-lock.json" in deps["affected_files"]

    # critical class sorts ahead of the elevated/warning classes.
    assert playbooks[0]["id"] == "rotate-leaked-secret"


def test_recovery_playbooks_returns_empty_when_no_open_cases():
    assert build_recovery_playbooks([]) == []


def test_recovery_playbooks_skips_suppressed_and_info_cases():
    cases = [
        {
            "case_id": "case-1",
            "category": "secrets",
            "severity": "critical",
            "action_level": "fix_now",
            "title": "Possible exposed credential in .env",
            "affected_files": [".env"],
            "scanners": ["gitleaks"],
            "suppressed": True,
        },
        {
            "case_id": "case-2",
            "category": "dependencies",
            "severity": "medium",
            "action_level": "info",
            "title": "Informational advisory",
            "affected_files": ["package-lock.json"],
            "scanners": ["trivy"],
        },
        {
            "case_id": "case-3",
            "category": "dependencies",
            "severity": "high",
            "action_level": "fix_now",
            "title": "axios CVE",
            "affected_files": ["package-lock.json"],
            "scanners": ["trivy"],
        },
    ]

    playbooks = build_recovery_playbooks(cases)

    assert len(playbooks) == 1
    assert playbooks[0]["id"] == "upgrade-vulnerable-dependency"
    assert playbooks[0]["case_count"] == 1


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


def test_save_scan_redacts_token_for_typed_and_dict_cases(tmp_path):
    """save_scan can never persist an un-redacted case (S-022).

    A token-like string must be redacted in the stored ``cases_json`` whether the
    case arrives as a typed ``SecurityCase`` or as a raw dict. The dict path is
    routed through ``SecurityCase(**case)`` so ``__post_init__`` redaction and the
    action_level/confidence whitelist always run — the old ``dict(case)`` branch
    that skipped them is gone.
    """
    token = "ghp_0123456789abcdefghij0123"
    typed_case = SecurityCase(
        case_id="case-typed",
        title=f"Exposed key {token}",
        plain_english_risk=f"Leaked {token} in config",
        action_level="fix_now",
        confidence="high",
        category="secrets",
        severity="critical",
        affected_files=[".env"],
        evidence=[{"note": f"value {token}"}],
        scanners=["gitleaks"],
        fix_steps=[f"Rotate {token}"],
        agent_prompt=f"Handle {token}",
        source_fingerprints=["fp-typed"],
    )
    dict_case = {
        "case_id": "case-dict",
        "title": f"Exposed key {token}",
        "plain_english_risk": f"Leaked {token}",
        # A dict bypassing __post_init__ could also smuggle an invalid action
        # level past the whitelist; prove that is normalized too.
        "action_level": "definitely-not-valid",
        "confidence": "high",
        "category": "secrets",
        "severity": "critical",
        "affected_files": [".env"],
        "evidence": [],
        "scanners": ["gitleaks"],
        "fix_steps": [f"Rotate {token}"],
        "agent_prompt": "",
        "source_fingerprints": ["fp-dict"],
    }
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="secrets",
            health_score=10,
            status="ok",
            scanner_statuses=[],
            findings=[],
            report_path=str(tmp_path / "r.json"),
            cases=[typed_case, dict_case],
        )
        stored = db.conn.execute(
            "select cases_json from scans where id = ?",
            ("repo-20260101T000000Z",),
        ).fetchone()["cases_json"]
        cases = json.loads(stored)
    finally:
        db.close()

    assert token not in stored
    assert "[REDACTED]" in stored
    # The dict path was rebuilt through SecurityCase: its invalid action_level
    # fell back to the whitelist default rather than being persisted verbatim.
    by_id = {case["case_id"]: case for case in cases}
    assert by_id["case-dict"]["action_level"] == "verify"
    assert by_id["case-typed"]["action_level"] == "fix_now"


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
            human_authorized=True,
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
    assert summary["repos"][0]["case_counts"]["action_level"].get("fix_now", 0) == 0
    assert summary["active_cases"] == []
    assert summary["suppressed_cases"][0]["case_id"] == cases[0].case_id
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


# ---------------------------------------------------------------------------
# Case lifecycle (S-020 / S-035): one canonical state machine
# ---------------------------------------------------------------------------


def test_lifecycle_canonical_vocabulary_and_mapping():
    # The new intermediate state lives in the canonical module.
    assert lifecycle.IN_PROGRESS in lifecycle.DECISION_STATUSES
    assert lifecycle.IN_PROGRESS in lifecycle.LIFECYCLE_STATES
    assert lifecycle.IN_PROGRESS in lifecycle.MCP_PRESENTATION_STATES
    # Suppression set is unchanged — only false_positive + accepted_risk hide a case.
    assert lifecycle.SUPPRESSING_STATUSES == {"false_positive", "accepted_risk"}
    assert not lifecycle.is_suppressing("in_progress")
    # MCP presentation fold: resolved is the display fold of fixed + false_positive.
    assert lifecycle.mcp_status_label("fixed") == "resolved"
    assert lifecycle.mcp_status_label("false_positive") == "resolved"
    assert lifecycle.mcp_status_label("verified") == "verified"
    assert lifecycle.mcp_status_label(None) == "open"
    assert lifecycle.mcp_status_label("in_progress") == "in_progress"
    # Rich, diff-aware lifecycle state surfaces the verifying beat and proof-bound closure.
    assert lifecycle.lifecycle_state("fixed") == "in_progress"
    assert lifecycle.lifecycle_state("fixed", diff_status="resolved") == "resolved"
    assert lifecycle.lifecycle_state(None, diff_status="resolved") == "resolved"
    assert lifecycle.lifecycle_state(None) == "open"


def test_lifecycle_allowed_transitions():
    # open → in_progress → resolved is the headline loop; reopening is allowed.
    assert lifecycle.can_transition("open", "in_progress")
    assert lifecycle.can_transition("in_progress", "resolved")
    assert lifecycle.can_transition("resolved", "open")
    # A resolved case cannot jump straight back to a human disposition without reopening.
    assert not lifecycle.can_transition("resolved", "verified")


def test_set_case_decision_accepts_in_progress(tmp_path):
    cases = build_security_cases(
        [Finding(repo="repo", scanner="semgrep", severity="medium", category="code-security", title="Unsafe eval", file="app.py", line=4)],
        [],
        {"repo": "repo"},
    )
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        decision = db.set_case_decision(case_id=cases[0].case_id, repo_name="repo", status="in_progress", note="Fix pushed, awaiting rescan.")
        assert decision["status"] == "in_progress"
        # in_progress is non-suppressing, so the case stays visible.
        assert cases[0].case_id in db.case_decisions_map()
    finally:
        db.close()


def test_legacy_case_decision_status_constraint_is_widened(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        # Recreate the OLD (narrow) four-value constraint and seed one decision row.
        conn.executescript(
            """
            create table case_decisions (
              case_id text primary key,
              repo_name text not null,
              status text not null check(status in ('verified', 'false_positive', 'accepted_risk', 'fixed')),
              note text,
              created_at text not null,
              updated_at text not null
            );
            insert into case_decisions (case_id, repo_name, status, note, created_at, updated_at)
              values ('case-legacy', 'repo', 'verified', 'old row', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00');
            """
        )
        conn.commit()
    finally:
        conn.close()

    db = ObservatoryDB(db_path)
    try:
        # Pre-existing decision row survived the widen (no destructive rebuild of data).
        assert db.case_decisions_map()["case-legacy"]["status"] == "verified"
        # The new in_progress value is now accepted by the widened constraint.
        db.conn.execute(
            "update case_decisions set status = 'in_progress' where case_id = 'case-legacy'"
        )
        db.conn.commit()
    finally:
        db.close()


def test_rescan_binds_resolved_case_with_closure_proof(tmp_path):
    """A rescan that no longer finds a case closes it with proof bound to the
    closing scan — closure proof, not closure by disappearance (S-035)."""
    open_finding = Finding(repo="repo", scanner="semgrep", severity="high", category="code-security", title="Unsafe parser", file="app.py", line=12)
    closing_finding = Finding(repo="repo", scanner="gitleaks", severity="critical", category="secrets", title="Generic API Key", file=".env", line=3)
    scanner_statuses = [{"scanner": "semgrep", "available": True, "findings": 1}]
    first_cases = build_security_cases([open_finding, closing_finding], scanner_statuses, {"repo": "repo"})
    second_cases = build_security_cases([open_finding], scanner_statuses, {"repo": "repo"})
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z", repo_name="repo", repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00", finished_at="2026-01-01T00:01:00+00:00",
            profile="quick", health_score=60, status="ok", scanner_statuses=scanner_statuses,
            findings=[open_finding, closing_finding], report_path=str(tmp_path / "r1.json"), cases=first_cases,
        )
        db.save_scan(
            scan_id="repo-20260102T000000Z", repo_name="repo", repo_path="/tmp/repo",
            started_at="2026-01-02T00:00:00+00:00", finished_at="2026-01-02T00:01:00+00:00",
            profile="quick", health_score=85, status="ok", scanner_statuses=scanner_statuses,
            findings=[open_finding], report_path=str(tmp_path / "r2.json"), cases=second_cases,
        )
        summary = db.dashboard_payload()
    finally:
        db.close()

    resolved_case = next(case for case in first_cases if "credential" in case.title)
    cases_by_id = {case["case_id"]: case for case in summary["cases"]}
    closed = cases_by_id[resolved_case.case_id]
    # Bound to the scan that closed it, and reads a proof-bound resolved lifecycle state.
    assert closed["change_status"] == "resolved"
    assert closed["resolved_by_scan_id"] == "repo-20260102T000000Z"
    assert closed["lifecycle_state"] == "resolved"
    assert "scan repo-20260102T000000Z" in closed["next_step"]


def test_fixed_case_still_present_reads_in_progress(tmp_path):
    """A case marked fixed but still found by the latest scan reads in_progress
    (verifying / awaiting rescan proof) on the dashboard."""
    finding = Finding(repo="repo", scanner="semgrep", severity="medium", category="code-security", title="Unsafe eval", file="app.py", line=4)
    cases = build_security_cases([finding], [], {"repo": "repo"})
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z", repo_name="repo", repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00", finished_at="2026-01-01T00:01:00+00:00",
            profile="quick", health_score=70, status="ok",
            scanner_statuses=[{"scanner": "semgrep", "available": True, "findings": 1}],
            findings=[finding], report_path=str(tmp_path / "r.json"), cases=cases,
        )
        db.set_case_decision(case_id=cases[0].case_id, repo_name="repo", status="fixed", note="Patched.")
        summary = db.dashboard_payload()
    finally:
        db.close()

    case = next(item for item in summary["cases"] if item["case_id"] == cases[0].case_id)
    assert case["lifecycle_state"] == "in_progress"


# ---------------------------------------------------------------------------
# Consequence boost + ordering (Honeygraph step 2.2)
# ---------------------------------------------------------------------------


def _ordering_case(case_id, title, severity, action_level, consequence=None):
    case = SecurityCase(
        case_id=case_id,
        title=title,
        plain_english_risk="r",
        action_level=action_level,
        confidence="medium",
        category="code-security",
        severity=severity,
        affected_files=[],
        evidence=[],
        scanners=["semgrep"],
        fix_steps=[],
        agent_prompt="p",
        source_fingerprints=[case_id],
    )
    case.consequence = consequence
    return case


def test_strong_consequence_boosts_and_reorders_above_higher_severity():
    # A medium finding that reaches a crown jewel on a strong path...
    reacher = _ordering_case(
        "reacher",
        "aaa medium that reaches the crown jewel",
        "medium",
        "verify",
        consequence={
            "reaches_crown_jewel": True,
            "confidence": "strong",
            "distance": 2,
            "blast_radius": 4,
            "crown_jewels_defined": True,
            "crown_jewel": {"identity_key": "db", "label": "the customer database"},
        },
    )
    # ...vs a high finding that reaches nothing.
    bystander = _ordering_case("bystander", "zzz high that reaches nothing", "high", "verify")

    ordered = apply_consequence_priority([bystander, reacher])

    # The reacher is promoted to fix_now and now sorts first; the high finding is
    # still visible at verify — never hidden, just out-ranked by consequence.
    assert reacher.action_level == "fix_now"
    assert bystander.action_level == "verify"
    assert [case.case_id for case in ordered] == ["reacher", "bystander"]


def test_consequence_tiebreak_does_not_override_severity_within_a_bucket():
    # Same action bucket; a high finding that reaches nothing must still sort ahead
    # of a low finding that reaches a crown jewel weakly (severity stays dominant).
    high = _ordering_case("high", "zzz high reaches nothing", "high", "verify")
    low = _ordering_case(
        "low",
        "aaa low reaches weakly",
        "low",
        "verify",
        consequence={
            "reaches_crown_jewel": True,
            "confidence": "weak",
            "distance": 1,
            "blast_radius": 1,
            "crown_jewels_defined": True,
            "crown_jewel": {"identity_key": "db", "label": "the customer database"},
        },
    )

    ordered = apply_consequence_priority([low, high])

    assert low.action_level == "verify"  # weak path never promotes
    assert [case.case_id for case in ordered] == ["high", "low"]


def test_no_consequence_cases_keep_todays_order():
    a = _ordering_case("a", "aaa", "medium", "verify")
    b = _ordering_case("b", "bbb", "medium", "verify")

    ordered = apply_consequence_priority([b, a])

    # Pure-additive: with no consequence, order falls back to the title tiebreak,
    # exactly as build_security_cases sorts today.
    assert [case.case_id for case in ordered] == ["a", "b"]
    assert a.priority_reasons == []
    assert b.priority_reasons == []


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
