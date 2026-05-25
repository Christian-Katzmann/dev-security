from __future__ import annotations

import json
from pathlib import Path

import pytest

from security_observatory.catalog import (
    CURRENT_TOOL_CATALOG,
    SetupKind,
    SetupProbe,
    SetupProbeKind,
    ToolCatalogEntry,
    ToolInstallState,
    current_tool_catalog,
    detect_install_state_for_tool,
    tool_catalog_entries,
)


def _entry_by_id(entry_id: str) -> ToolCatalogEntry:
    return next(entry for entry in CURRENT_TOOL_CATALOG if entry.id == entry_id)


@pytest.fixture
def isolated_observatory_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point SECURITY_OBSERVATORY_HOME at a clean tmp dir for credential reads."""

    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(tmp_path))
    return tmp_path


def _seed_credential_index(home: Path, tool_id: str, keys: list[str]) -> None:
    path = home / "credentials" / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "tools": {tool_id: sorted(keys)}}, indent=2),
        encoding="utf-8",
    )


def test_schema_validates_entries_without_setup_fields() -> None:
    """Existing entries without setup metadata still satisfy the dataclass."""

    for entry in CURRENT_TOOL_CATALOG:
        assert isinstance(entry.setup_kind, SetupKind)
        if entry.setup_kind is SetupKind.NONE:
            assert entry.setup_requirement is None
            assert entry.setup_probe is None
        else:
            assert isinstance(entry.setup_requirement, str) and entry.setup_requirement
            assert isinstance(entry.setup_probe, SetupProbe)


def test_legitify_setup_spec_round_trips_through_to_dict() -> None:
    """legitify's populated setup spec survives `to_dict()` cleanly."""

    legitify = _entry_by_id("legitify")
    assert legitify.setup_kind is SetupKind.API_KEY
    assert legitify.setup_requirement is not None
    assert "repo" in legitify.setup_requirement
    assert "admin:repo_hook" in legitify.setup_requirement

    probe = legitify.setup_probe
    assert probe is not None
    assert probe.kind is SetupProbeKind.SHELL
    assert probe.spec["command"].startswith("legitify analyze")
    assert probe.spec["env_from_credential"] == "SCM_TOKEN"

    serialised = legitify.to_dict()
    assert serialised["setup_kind"] == "api-key"
    assert serialised["setup_requirement"] == legitify.setup_requirement
    probe_payload = serialised["setup_probe"]
    assert probe_payload["kind"] == "shell"
    spec = probe_payload["spec"]
    # The command targets a small public repo with a single namespace so the
    # probe stays fast (~15s on a warm token) and uses the same --repo flag
    # the production scanner uses.
    assert "legitify analyze" in spec["command"]
    assert "--repo Legit-Labs/legitify" in spec["command"]
    assert "--scm github" in spec["command"]
    assert "--namespace repository" in spec["command"]
    assert spec["env_from_credential"] == "SCM_TOKEN"
    # legitify exits 1 when it finds policy violations on the target repo —
    # that still proves the token authenticated, so it counts as success.
    assert spec["success_returncodes"] == "0,1"
    # Token-creation deep link preselects scopes + a friendly description.
    token_url = legitify.setup_token_create_url or ""
    assert token_url.startswith("https://github.com/settings/tokens/new")
    assert "scopes=repo,admin:repo_hook" in token_url

    # legitify's next_step copy no longer references the bare CLI env-var hint;
    # it now points at the catalog setup card flow.
    assert "setup card" in (legitify.install.next_step or "").lower()


def test_default_setup_kind_yields_clean_payload() -> None:
    """Tools without setup needs surface `setup_kind=none` and omit the optional fields."""

    payloads = current_tool_catalog()
    by_id = {item["id"]: item for item in payloads}

    # semgrep is a vanilla PATH-detected scanner with no setup requirement.
    semgrep = by_id["semgrep"]
    assert semgrep["setup_kind"] == "none"
    assert "setup_requirement" not in semgrep
    assert "setup_probe" not in semgrep

    # malcontent is the file-path case; the setup metadata should be present.
    malcontent = by_id["malcontent"]
    assert malcontent["setup_kind"] == "file-path"
    assert malcontent["setup_requirement"].startswith("Path to behavioral artifact cache")
    assert malcontent["setup_probe"] == {
        "kind": "directory-exists",
        "spec": {"config_key": "artifact_cache_dir"},
    }


def test_legitify_install_state_reflects_keychain_presence(
    isolated_observatory_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When SCM_TOKEN is stored in Keychain, legitify flips not-configured → detected."""

    # Pretend the legitify binary is on PATH so the install-state branch we
    # care about (PATH_BINARY + setup-aware) actually fires.
    monkeypatch.setattr(
        "security_observatory.catalog.shutil.which",
        lambda binary: f"/usr/local/bin/{binary}" if binary == "legitify" else None,
    )
    legitify = _entry_by_id("legitify")

    # Empty index → no credential → not-configured.
    assert detect_install_state_for_tool(legitify) is ToolInstallState.NOT_CONFIGURED

    # Seed the credential index (no real Keychain write — list_credentials
    # reads the on-disk index, not the Keychain).
    _seed_credential_index(isolated_observatory_home, "legitify", ["SCM_TOKEN"])
    assert detect_install_state_for_tool(legitify) is ToolInstallState.DETECTED

    # The full catalog walk should agree — and the next-step copy should be
    # rewritten to the "installed, just run" variant.
    payload = next(
        item for item in current_tool_catalog(detect_install_state=True)
        if item["id"] == "legitify"
    )
    assert payload["install_state"] == "detected"
    next_step = (payload["install"]["next_step"] or "").lower()
    assert "installed locally" in next_step


def test_malcontent_install_state_reflects_config_presence(
    isolated_observatory_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """File-path setup tools flip on a non-empty config_key value."""

    monkeypatch.setattr(
        "security_observatory.catalog.shutil.which",
        lambda binary: f"/usr/local/bin/{binary}" if binary in {"malcontent", "mal"} else None,
    )
    malcontent = _entry_by_id("malcontent")

    # No config file → not-configured.
    assert detect_install_state_for_tool(malcontent) is ToolInstallState.NOT_CONFIGURED

    # Seed a config value for the spec's config_key.
    from security_observatory.setup_runner import write_tool_config

    write_tool_config("malcontent", {"artifact_cache_dir": str(isolated_observatory_home / "cache")})
    assert detect_install_state_for_tool(malcontent) is ToolInstallState.DETECTED


def test_detect_install_state_uses_isolated_index(
    isolated_observatory_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """tool_catalog_entries() honours SECURITY_OBSERVATORY_HOME for credential lookup."""

    monkeypatch.setattr(
        "security_observatory.catalog.shutil.which",
        lambda binary: f"/usr/local/bin/{binary}" if binary == "legitify" else None,
    )

    # Sanity: with a clean tmp home, legitify is still not-configured.
    entries = {entry.id: entry for entry in tool_catalog_entries(detect_install_state=True)}
    assert entries["legitify"].install_state is ToolInstallState.NOT_CONFIGURED

    _seed_credential_index(isolated_observatory_home, "legitify", ["SCM_TOKEN"])
    entries = {entry.id: entry for entry in tool_catalog_entries(detect_install_state=True)}
    assert entries["legitify"].install_state is ToolInstallState.DETECTED
