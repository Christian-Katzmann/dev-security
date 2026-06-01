import os
import sys

from security_observatory.cases import build_security_cases, scanner_evidence_gaps
from security_observatory.normalize import normalize
from security_observatory.scanners import run_scanner


def test_normalizes_semgrep_result():
    data = {
        "results": [
            {
                "path": "app.py",
                "start": {"line": 12},
                "check_id": "x",
                "extra": {"severity": "ERROR", "message": "bad thing"},
            }
        ]
    }
    findings = normalize("semgrep", data, "repo")
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].file == "app.py"


def test_normalizes_gitleaks_as_secret_without_value():
    findings = normalize("gitleaks", [{"RuleID": "generic-api-key", "File": ".env", "StartLine": 1}], "repo")
    assert findings[0].category == "secrets"
    assert findings[0].severity == "critical"


def test_trivy_ignores_non_object_secret_entries():
    data = {
        "Results": [
            {
                "Target": ".env",
                "Secrets": [
                    "summary text from scanner",
                    {"Title": "API key", "Severity": "CRITICAL", "StartLine": 3},
                ],
            }
        ]
    }

    findings = normalize("trivy", data, "repo")

    assert len(findings) == 1
    assert findings[0].category == "secrets"
    assert findings[0].file == ".env"
    assert findings[0].line == 3


def test_multi_scanner_findings_are_conserved_through_normalize_and_cases():
    """Every raw finding from several scanners must survive normalize -> case-build.

    This is the count-conservation invariant: the fingerprints entering case-build
    equal the union of source_fingerprints across the cases. None silently vanish and
    none are invented. Deleting or short-circuiting any finding inside normalize.py
    drops the normalized total below the raw count and fails the first assertion.
    """
    # Real scanner output shapes: two scanners, two findings each, plus a third for
    # breadth — six distinct raw findings across code, dependency, and secret classes.
    semgrep_payload = {
        "results": [
            {
                "path": "app.py",
                "start": {"line": 12},
                "check_id": "py.eval-injection",
                "extra": {"severity": "ERROR", "message": "Avoid eval on request data"},
            },
            {
                "path": "api/handlers.py",
                "start": {"line": 30},
                "check_id": "py.sql-injection",
                "extra": {"severity": "WARNING", "message": "Possible SQL injection in query"},
            },
        ]
    }
    trivy_payload = {
        "Results": [
            {
                "Target": "package-lock.json",
                "Vulnerabilities": [
                    {"VulnerabilityID": "CVE-2026-1000", "PkgName": "lodash", "InstalledVersion": "4.17.20", "Severity": "HIGH"},
                    {"VulnerabilityID": "CVE-2026-2222", "PkgName": "axios", "InstalledVersion": "0.21.0", "Severity": "CRITICAL"},
                ],
            }
        ]
    }
    gitleaks_payload = [
        {"RuleID": "aws-access-key", "Description": "AWS access key", "File": "config/prod.env", "StartLine": 3},
        {"RuleID": "github-pat", "Description": "GitHub personal access token", "File": ".env", "StartLine": 7},
    ]

    raw_count = len(semgrep_payload["results"]) + len(trivy_payload["Results"][0]["Vulnerabilities"]) + len(gitleaks_payload)

    findings = (
        normalize("semgrep", semgrep_payload, "repo")
        + normalize("trivy", trivy_payload, "repo")
        + normalize("gitleaks", gitleaks_payload, "repo")
    )

    # 1. normalize conserves count: every raw entry becomes exactly one finding.
    assert len(findings) == raw_count

    fingerprints_in = {finding.fingerprint for finding in findings}
    assert len(fingerprints_in) == raw_count, "fixture findings must have distinct fingerprints"

    cases = build_security_cases(
        findings,
        [
            {"scanner": "semgrep", "available": True, "findings": 2},
            {"scanner": "trivy", "available": True, "findings": 2},
            {"scanner": "gitleaks", "available": True, "findings": 2},
        ],
        {"repo": "repo"},
    )

    accounted = set()
    for case in cases:
        accounted.update(case.source_fingerprints)

    # 2. case-build conserves: every input fingerprint is accounted for in a case, and
    #    no fingerprint is invented. Equality is the load-bearing assertion — a regression
    #    that drops a group (or fabricates one) breaks it in either direction.
    assert accounted == fingerprints_in


def test_malformed_scanner_payload_surfaces_as_degraded_not_silent_zero(tmp_path, monkeypatch):
    """A scanner that emits non-empty but unparseable output must surface as degraded.

    The honesty guarantee: malformed evidence is a tracked error with zero usable
    findings, never an empty-but-clean result that reads as "this scanner found
    nothing wrong." A regression that swallowed the failure (clearing the error or
    claiming the scanner succeeded) would fail the error/gap assertions below.
    """
    # A stand-in `checkov` that writes non-empty, non-JSON output and exits hard.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "checkov"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "sys.stdout.write('{ this is not valid json and it is not empty ')\n"
        "sys.exit(2)\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + (os.environ.get("PATH") or ""))

    repo = tmp_path / "repo"
    repo.mkdir()
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    result = run_scanner("checkov", repo, "repo", scan_dir, rules_dir)

    # The tool was found and ran (non-empty output) ...
    assert result.status.available is True
    # ... but the malformed payload produced no usable findings ...
    assert result.findings == []
    assert result.status.findings == 0
    # ... and that zero is tracked as an error, not a silent clean pass.
    assert result.status.error, "a failed scanner must record an error, not report a clean zero"

    # The degradation is visible to the report as an evidence gap, not swallowed.
    gaps = scanner_evidence_gaps([result.status.to_dict()], profile="iac")
    assert any(gap.get("scanner") == "checkov" for gap in gaps)
