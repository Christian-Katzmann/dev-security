from __future__ import annotations

from security_observatory.catalog import (
    CURRENT_TOOL_CATALOG,
    SetupKind,
    SetupProbe,
    SetupProbeKind,
    ToolCatalogEntry,
    current_tool_catalog,
)


def _entry_by_id(entry_id: str) -> ToolCatalogEntry:
    return next(entry for entry in CURRENT_TOOL_CATALOG if entry.id == entry_id)


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
    assert serialised["setup_probe"] == {
        "kind": "shell",
        "spec": {
            "command": "legitify analyze --repository Legit-Labs/legitify",
            "env_from_credential": "SCM_TOKEN",
            "timeout_seconds": "60",
        },
    }

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
