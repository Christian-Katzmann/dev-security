from security_observatory.model import Finding, score_findings


def test_secret_penalty_is_heavy():
    findings = [Finding(repo="r", scanner="gitleaks", severity="critical", category="secrets", title="secret")]
    assert score_findings(findings, sbom_created=True) == 60


def test_fingerprints_deduplicate_score():
    finding = Finding(repo="r", scanner="semgrep", severity="high", category="code-security", title="x", file="a.py", line=1)
    duplicate = Finding(repo="r", scanner="semgrep", severity="high", category="code-security", title="x", file="a.py", line=1)
    assert finding.fingerprint == duplicate.fingerprint
    assert score_findings([finding, duplicate], sbom_created=True) == 90
