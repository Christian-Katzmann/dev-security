import json
from pathlib import Path

import pytest

from security_observatory.rotation_inference import (
    DEFAULT_CATALOG_PATH,
    infer_secret_name,
    load_catalog_secret_names,
)


CATALOG_NAMES = [
    "AUTH_SECRET",
    "CRON_SECRET",
    "MCP_API_KEY",
    "CACHE_REVALIDATE_SECRET",
    "NEXTAUTH_SECRET",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "TURSO_AUTH_TOKEN",
    "BLOB_READ_WRITE_TOKEN",
    "GITHUB_CLIENT_SECRET",
    "RESEND_API_KEY",
]


def _secrets_case(title: str, *, file: str = ".env", evidence_titles: list[str] | None = None, remediation: str | None = None) -> dict:
    return {
        "category": "secrets",
        "title": title,
        "affected_files": [file] if file else [],
        "evidence": [
            {
                "scanner": "gitleaks",
                "title": ev_title,
                "remediation": remediation,
                "location": f"{file}:1" if file else "",
            }
            for ev_title in (evidence_titles or [title])
        ],
        "fix_steps": [],
    }


def test_non_secret_category_returns_none():
    case = _secrets_case("Generic API Key")
    case["category"] = "dependencies"
    assert infer_secret_name(case, CATALOG_NAMES) is None


def test_exact_envvar_match_in_title():
    case = _secrets_case("ANTHROPIC_API_KEY found in .env", file=".env")
    assert infer_secret_name(case, CATALOG_NAMES) == "ANTHROPIC_API_KEY"


def test_exact_envvar_match_in_remediation_wins():
    case = _secrets_case(
        title="Detected a Generic API Key",
        file=".env",
        evidence_titles=["Generic API Key"],
        remediation="Rotate the value of OPENAI_API_KEY and remove it from .env",
    )
    assert infer_secret_name(case, CATALOG_NAMES) == "OPENAI_API_KEY"


def test_provider_hint_anthropic():
    case = _secrets_case("Anthropic API Key detected", file=".env")
    assert infer_secret_name(case, CATALOG_NAMES) == "ANTHROPIC_API_KEY"


def test_provider_hint_openai():
    case = _secrets_case("OpenAI API key in file", file="src/.env.local")
    assert infer_secret_name(case, CATALOG_NAMES) == "OPENAI_API_KEY"


def test_provider_hint_github_client_secret():
    case = _secrets_case("GitHub client secret leaked", file=".env")
    assert infer_secret_name(case, CATALOG_NAMES) == "GITHUB_CLIENT_SECRET"


def test_generic_github_pat_does_not_match_client_secret():
    # gitleaks's "github-pat" / "GitHub Personal Access Token" is NOT a client
    # secret; we should refuse to infer GITHUB_CLIENT_SECRET from a PAT match.
    case = _secrets_case("GitHub Personal Access Token detected", file=".env")
    assert infer_secret_name(case, CATALOG_NAMES) is None


def test_nextauth_secret_pattern():
    case = _secrets_case("NextAuth secret in source", file="src/lib/auth.ts")
    assert infer_secret_name(case, CATALOG_NAMES) == "NEXTAUTH_SECRET"


def test_auth_secret_word_boundary():
    case = _secrets_case("AUTH_SECRET hardcoded in repo")
    assert infer_secret_name(case, CATALOG_NAMES) == "AUTH_SECRET"


def test_generic_api_key_returns_none():
    case = _secrets_case("Generic API Key", file=".env")
    assert infer_secret_name(case, CATALOG_NAMES) is None


def test_no_candidate_names_disables_inference():
    case = _secrets_case("Anthropic API Key detected", file=".env")
    assert infer_secret_name(case, []) is None


def test_candidate_restriction_excludes_unknown_names():
    # The pattern would match ANTHROPIC_API_KEY, but the repo only tracks
    # AUTH_SECRET — so we refuse to infer something the repo can't rotate.
    case = _secrets_case("Anthropic API Key detected", file=".env")
    assert infer_secret_name(case, ["AUTH_SECRET"]) is None


def test_default_universe_when_candidates_none():
    case = _secrets_case("Anthropic API Key detected", file=".env")
    # No candidates passed — falls back to the provider-hint universe.
    assert infer_secret_name(case, None) == "ANTHROPIC_API_KEY"


def test_empty_corpus_returns_none():
    case = {
        "category": "secrets",
        "title": "",
        "affected_files": [],
        "evidence": [],
        "fix_steps": [],
    }
    assert infer_secret_name(case, CATALOG_NAMES) is None


def test_longest_name_wins_on_tie():
    # If two candidate names both appear, the longer one wins so e.g.
    # NEXTAUTH_SECRET beats a hypothetical AUTH_SECRET substring inside it.
    case = _secrets_case("Found NEXTAUTH_SECRET in env file")
    assert infer_secret_name(case, ["AUTH_SECRET", "NEXTAUTH_SECRET"]) == "NEXTAUTH_SECRET"


def test_load_catalog_secret_names_reads_entries(tmp_path: Path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({
        "entries": [
            {"name": "FOO_KEY", "class": "A"},
            {"name": "BAR_TOKEN", "class": "B-API"},
            {"class": "C"},  # missing name — skipped
            "not-a-dict",    # skipped
        ],
    }), encoding="utf-8")
    assert load_catalog_secret_names(catalog) == ["FOO_KEY", "BAR_TOKEN"]


def test_load_catalog_secret_names_missing_file_returns_empty(tmp_path: Path):
    assert load_catalog_secret_names(tmp_path / "nope.json") == []


def test_load_catalog_secret_names_corrupt_returns_empty(tmp_path: Path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text("{not valid json", encoding="utf-8")
    assert load_catalog_secret_names(catalog) == []


def test_default_catalog_path_points_to_skills_directory():
    # Sanity check the path is what the rest of the rotation surfaces expect.
    assert DEFAULT_CATALOG_PATH.name == "catalog.json"
    assert "secrets-rotation" in str(DEFAULT_CATALOG_PATH)
