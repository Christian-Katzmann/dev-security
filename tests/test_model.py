import pytest

from security_observatory.model import Finding, SecurityCase, redact_text, score_findings


# Each case is (locator, secret_value): the human-readable key/label that must
# survive, and the secret value that must be stripped out of stored evidence.
# Real secret shapes the TOKEN_RE is meant to catch: AWS key id, GitHub PAT,
# OpenAI key, Slack token, and a generic 32+ char API key/hash.
_SECRET_SHAPES = [
    ("aws_access_key_id: ", "AKIAIOSFODNN7EXAMPLE"),
    ("github personal access token: ", "ghp_abcdefghijklmnopqrst1234567890"),
    ("openai api key: ", "sk-abcdefghijklmnopqrstuvwx"),
    ("slack bot token: ", "xoxb-1234567890-abcdefghijkl"),
    ("session secret: ", "0123456789abcdef0123456789abcdef0123"),
]


@pytest.mark.parametrize("locator, secret", _SECRET_SHAPES)
def test_redact_text_strips_secret_value_but_keeps_locator(locator, secret):
    cleaned = redact_text(f"{locator}{secret}")

    # The secret value is gone — this is the privacy guarantee that protects
    # stored findings and evidence from leaking live credentials.
    assert secret not in cleaned
    assert "[REDACTED]" in cleaned
    # The locator/key survives so the finding stays actionable after redaction.
    assert locator.rstrip() in cleaned


def test_redact_text_leaves_non_secret_text_untouched():
    # A redaction regression in the other direction — nuking ordinary prose — would
    # destroy the locators the case relies on. Plain text must pass through verbatim.
    text = "Rotate the credential in config/prod.env at line 12, then rerun the secrets check."
    assert redact_text(text) == text


def test_redact_text_strips_secret_embedded_mid_sentence():
    raw = "Found token ghp_abcdefghijklmnopqrst1234567890 committed in app/config.py."
    cleaned = redact_text(raw)
    assert "ghp_abcdefghijklmnopqrst1234567890" not in cleaned
    assert "Found token [REDACTED] committed in app/config.py." == cleaned


def test_secret_penalty_is_heavy():
    findings = [Finding(repo="r", scanner="gitleaks", severity="critical", category="secrets", title="secret")]
    assert score_findings(findings, sbom_created=True) == 60


def test_fingerprints_deduplicate_score():
    finding = Finding(repo="r", scanner="semgrep", severity="high", category="code-security", title="x", file="a.py", line=1)
    duplicate = Finding(repo="r", scanner="semgrep", severity="high", category="code-security", title="x", file="a.py", line=1)
    assert finding.fingerprint == duplicate.fingerprint
    assert score_findings([finding, duplicate], sbom_created=True) == 90


def _case(confidence: str) -> SecurityCase:
    return SecurityCase(
        case_id="c1",
        title="Example case",
        plain_english_risk="A risk.",
        action_level="verify",
        confidence=confidence,
        category="code-security",
        severity="medium",
        affected_files=["a.py"],
        evidence=[],
        scanners=["semgrep"],
        fix_steps=["look"],
        agent_prompt="fix it",
        source_fingerprints=["abc"],
    )


def test_unknown_confidence_is_not_coerced_to_medium():
    # The confident-falsehood guard (S-032): an "unknown" confidence must read as
    # "unknown", never silently upgraded to "medium" — a case must not look more
    # certain than its evidence.
    assert _case("unknown").confidence == "unknown"


@pytest.mark.parametrize("value", ["high", "medium", "low"])
def test_known_confidence_levels_are_preserved(value):
    assert _case(value).confidence == value


@pytest.mark.parametrize("value", ["", "bogus", "very-high"])
def test_unclassifiable_confidence_falls_back_to_unknown_not_medium(value):
    # An unclassifiable confidence is honest about its uncertainty ("unknown"),
    # not optimistic ("medium"). This is the load-bearing honesty property.
    assert _case(value).confidence == "unknown"
