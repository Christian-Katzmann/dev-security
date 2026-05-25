"""Lock the Tier 5R confirmation phrase across backend, frontend, and doctrine."""
from __future__ import annotations

from pathlib import Path

from security_observatory.dashboard_server import _rotation_confirmation_phrase


REPO_ROOT = Path(__file__).resolve().parents[1]


def _frontend_confirmation_phrase(secret: str, *, emergency: bool = False) -> str:
    source = (REPO_ROOT / "dashboard-ui" / "src" / "dashboardData.ts").read_text(
        encoding="utf-8"
    )
    needle = "emergency-mode" if emergency else "irreversible provider-side change"
    line = next(
        item.strip()
        for item in source.splitlines()
        if item.strip().startswith("return `Yes, rotate") and needle in item
    )
    template = line.removeprefix("return `").removesuffix("`;")
    return template.replace("\\`", "`").replace("${secret}", secret)


def _doctrine_confirmation_phrase(secret: str, *, emergency: bool = False) -> str:
    source = (REPO_ROOT / "docs" / "agent-safety.md").read_text(encoding="utf-8")
    source = source.split("## Tier 5R - Rotate a Credential", 1)[1]
    marker = (
        "**Emergency rotation confirmation phrase:**"
        if emergency
        else "**Confirmation phrase:**"
    )
    line = next(item for item in source.splitlines() if item.startswith(marker))
    template = line.removeprefix(marker).strip().strip("`").strip()
    return template.replace("<SECRET>", secret)


def test_tier_5r_confirmation_phrase_does_not_drift():
    secret = "AUTH_SECRET"
    backend = _rotation_confirmation_phrase(secret)

    assert _frontend_confirmation_phrase(secret) == backend
    assert _doctrine_confirmation_phrase(secret) == backend


def test_tier_5r_emergency_confirmation_phrase_does_not_drift():
    secret = "ANTHROPIC_ADMIN_KEY"
    backend = _rotation_confirmation_phrase(secret, emergency=True)

    assert _frontend_confirmation_phrase(secret, emergency=True) == backend
    assert _doctrine_confirmation_phrase(secret, emergency=True) == backend
