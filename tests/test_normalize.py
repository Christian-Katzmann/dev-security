from security_observatory.normalize import normalize


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
