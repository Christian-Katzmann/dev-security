from security_observatory.enrichment import DependencyTrustRecord
from security_observatory.model import Finding
from security_observatory.priority import action_level_for, decide_action_level


def test_secrets_are_fix_now():
    finding = Finding(repo="repo", scanner="gitleaks", severity="critical", category="secrets", title="API key")

    assert action_level_for(finding) == "fix_now"


def test_known_exploited_dependency_is_fix_now_even_without_network_during_scan():
    finding = Finding(repo="repo", scanner="trivy", severity="medium", category="dependencies", title="CVE-2024-12345 in pkg")
    enrichment = {"cisa_kev": {"status": "checked", "known_exploited": True}}

    decision = decide_action_level(finding, enrichment)

    assert decision.action_level == "fix_now"
    assert "exploitation" in decision.reasons[0]


def test_high_dependency_with_fix_available_is_fix_now():
    finding = Finding(
        repo="repo",
        scanner="osv-scanner",
        severity="high",
        category="dependencies",
        title="CVE-2024-12345 in pkg",
        remediation="Upgrade pkg to 1.2.3.",
    )

    assert action_level_for(finding) == "fix_now"


def test_low_confidence_scanner_only_issue_is_watch_or_verify():
    low = {"severity": "low", "category": "code-security", "scanner": "semgrep", "confidence": "low", "title": "possible issue"}
    medium = {"severity": "medium", "category": "code-security", "scanner": "semgrep", "confidence": "low", "title": "possible issue"}

    assert action_level_for(low) == "watch"
    assert action_level_for(medium) == "verify"


def test_low_hygiene_high_criticality_dependency_gets_verify_reason():
    finding = Finding(repo="repo", scanner="osv-scanner", severity="low", category="dependencies", title="Minor issue in busy-package")
    trust = {
        "source_repo": "github.com/example/busy-package",
        "scorecard_score": 3.2,
        "scorecard_status": "checked",
        "criticality_score": 0.82,
        "criticality_status": "checked",
        "freshness": "fresh",
    }

    decision = decide_action_level(finding, trust)

    assert decision.action_level == "verify"
    assert any("Project hygiene looks weak" in reason for reason in decision.reasons)
    assert any("Ecosystem importance is high" in reason for reason in decision.reasons)
    assert any("deserves a human check" in reason for reason in decision.reasons)


def test_stale_dependency_trust_is_explained_but_does_not_boost():
    finding = Finding(repo="repo", scanner="osv-scanner", severity="low", category="dependencies", title="Minor issue in stale-package")
    trust = {
        "source_repo": "github.com/example/stale-package",
        "scorecard_score": 2.0,
        "scorecard_status": "checked",
        "criticality_score": 0.9,
        "criticality_status": "checked",
        "freshness": "stale",
    }

    decision = decide_action_level(finding, trust)

    assert decision.action_level == "watch"
    assert any("stale" in reason for reason in decision.reasons)


def test_no_dependency_enrichment_keeps_severity_priority():
    finding = Finding(repo="repo", scanner="osv-scanner", severity="low", category="dependencies", title="Minor issue in package")

    decision = decide_action_level(finding)

    assert decision.action_level == "watch"
    assert decision.reasons == ["low-confidence scanner-only signal"]


def test_missing_dependency_trust_data_is_not_a_penalty():
    finding = Finding(repo="repo", scanner="osv-scanner", severity="low", category="dependencies", title="Minor issue in unknown package")
    trust = {
        "source_repo": None,
        "scorecard_score": None,
        "scorecard_status": "not_checked",
        "criticality_score": None,
        "criticality_status": "unavailable",
        "freshness": "unknown",
    }

    decision = decide_action_level(finding, trust)

    assert decision.action_level == "watch"
    assert any("not counted against this repo" in reason for reason in decision.reasons)
    assert not any("deserves a human check" in reason for reason in decision.reasons)


def test_high_severity_is_not_silently_overridden_by_trust_data():
    finding = Finding(repo="repo", scanner="osv-scanner", severity="high", category="dependencies", title="High issue in busy-package")
    trust = {
        "scorecard_score": 2.0,
        "scorecard_status": "checked",
        "criticality_score": 0.95,
        "criticality_status": "checked",
        "freshness": "fresh",
    }

    decision = decide_action_level(finding, trust)

    assert decision.action_level == "verify"
    assert decision.reasons[0] == "high severity needs confirmation or a fix path"
    assert any("Project hygiene looks weak" in reason for reason in decision.reasons)


def test_dependency_trust_record_object_gets_same_priority_reasoning():
    finding = Finding(repo="repo", scanner="osv-scanner", severity="low", category="dependencies", title="Minor issue in busy-package")
    trust = DependencyTrustRecord(
        component_fingerprint=None,
        component_package_key="npm|busy-package",
        package_name="busy-package",
        package_version="1.0.0",
        package_ecosystem="npm",
        package_url="pkg:npm/busy-package@1.0.0",
        source_repo="github.com/example/busy-package",
        source_repo_url="https://github.com/example/busy-package",
        source_repo_confidence="strong",
        source_repo_reason="Component metadata includes repository.",
        scorecard_score=3.0,
        scorecard_status="checked",
        criticality_score=0.8,
        criticality_status="checked",
        checked_at="2026-01-01T00:00:00+00:00",
        freshness="fresh",
        status="fresh",
        cache_key="github.com/example/busy-package",
    )

    decision = decide_action_level(finding, trust)

    assert decision.action_level == "verify"
    assert any("maintenance signals look weak" in reason for reason in decision.reasons)
