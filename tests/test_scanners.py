from pathlib import Path

from security_observatory import catalog as catalog_model
from security_observatory.model import DEFAULT_EXCLUDES
from security_observatory.scanners import _command, run_scanner, scanner_catalog, tool_catalog


def test_trufflehog_uses_local_friendly_exclusions(tmp_path: Path):
    command = _command("trufflehog", Path("/repo"), tmp_path, Path("/rules"))

    assert "--concurrency=2" in command
    assert "--force-skip-binaries" in command
    assert "--force-skip-archives" in command
    exclude_path = Path(command[command.index("--exclude-paths") + 1])
    content = exclude_path.read_text(encoding="utf-8")
    for name in DEFAULT_EXCLUDES:
        assert name in content


def test_scanner_catalog_includes_fixable_doctor_steps():
    catalog = {item["scanner"]: item for item in scanner_catalog()}

    assert catalog["ai-static"]["built_in"] is True
    assert "brew install semgrep" in catalog["semgrep"]["install"]
    assert "uv tool install checkov" in catalog["checkov"]["install"]
    assert catalog["gitleaks"]["area"] == "Secrets"


def test_tool_catalog_preserves_legacy_scanner_contract():
    catalog = {item["id"]: item for item in tool_catalog()}
    semgrep = catalog["semgrep"]

    assert semgrep["kind"] == "scanner"
    assert semgrep["scanner_key"] == "semgrep"
    assert semgrep["legacy_scanner"]["scanner"] == "semgrep"
    assert semgrep["legacy_scanner"]["install"] == "./install-security-observatory.sh or brew install semgrep"
    assert semgrep["policy"]["local_only"] is True
    assert semgrep["policy"]["allowed_for_agent_lab"] is True
    assert semgrep["install_state"] == "missing"


def test_tool_catalog_derives_safety_labels_from_policy():
    catalog = {item["id"]: item for item in tool_catalog()}

    ai_static = catalog["ai-static"]
    assert ai_static["derived_labels"]["safety"] == ["Local", "No credentials", "Read-only"]
    assert ai_static["derived_labels"]["install"] == ["Built in", "DevSec managed"]
    assert ai_static["derived_labels"]["agent_lab"] == "Agent Lab allowed"

    osv = catalog["osv-scanner"]
    assert osv["policy"]["network_access"] == "required"
    assert "Network required" in osv["derived_labels"]["safety"]
    assert "Approval required" in osv["derived_labels"]["safety"]
    assert osv["derived_labels"]["agent_lab"] == "Agent Lab blocked"


def test_tool_catalog_includes_external_surface_display_only_placeholder():
    catalog = {item["id"]: item for item in tool_catalog(detect_install_state=True)}
    external_surface = catalog["external-surface"]

    assert external_surface["kind"] == "workflow"
    assert external_surface["category"] == "external-surface"
    assert external_surface["lifecycle"] == "coming-soon"
    assert external_surface["install_state"] == "coming-soon"
    assert external_surface["install"]["method"] == "none"
    assert external_surface["install"]["owner"] == "not-applicable"
    assert external_surface["install"]["detection"] == "none"
    assert external_surface["install"]["uninstall_posture"] == "not-supported"
    assert external_surface["policy"]["local_only"] is False
    assert external_surface["policy"]["network_access"] == "required"
    assert external_surface["policy"]["external_targets"] == "user-provided"
    assert external_surface["policy"]["needs_approval"] is True
    assert external_surface["policy"]["allowed_for_agent_lab"] is False
    assert external_surface["policy"]["default_enabled"] is False
    assert "scanner_key" not in external_surface
    assert "legacy_scanner" not in external_surface
    assert "Display only" in external_surface["derived_labels"]["safety"]
    assert "Coming soon" in external_surface["derived_labels"]["install"]
    assert external_surface["derived_labels"]["agent_lab"] == "Agent Lab blocked"
    assert {
        "pack_id": "external-surface",
        "role": "coming-soon",
        "default_enabled": False,
    } in external_surface["packs"]
    assert "external-surface" not in {item["scanner"] for item in scanner_catalog()}


def test_tool_catalog_can_resolve_detected_path_tools(monkeypatch):
    def fake_which(binary: str) -> str | None:
        return f"/usr/local/bin/{binary}" if binary in {"semgrep", "legitify"} else None

    monkeypatch.setattr("security_observatory.catalog.shutil.which", fake_which)

    catalog = {item["id"]: item for item in tool_catalog(detect_install_state=True)}
    semgrep = catalog["semgrep"]

    assert semgrep["install_state"] == "detected"
    assert "Detected locally" in semgrep["derived_labels"]["install"]
    assert semgrep["derived_labels"]["agent_lab"] == "Agent Lab allowed"

    syft = catalog["syft"]
    assert syft["install_state"] == "missing"
    assert "Missing" in syft["derived_labels"]["install"]
    assert syft["derived_labels"]["agent_lab"] == "Agent Lab blocked"

    legitify = catalog["legitify"]
    assert legitify["install_state"] == "not-configured"
    assert "Needs setup" in legitify["derived_labels"]["install"]
    assert legitify["derived_labels"]["agent_lab"] == "Agent Lab blocked"


def test_tool_catalog_install_state_labels_cover_contract_states():
    states = {
        catalog_model.ToolInstallState.DETECTED: ("Detected locally", "Agent Lab allowed"),
        catalog_model.ToolInstallState.MANAGED: ("Managed", "Agent Lab allowed"),
        catalog_model.ToolInstallState.MISSING: ("Missing", "Agent Lab blocked"),
        catalog_model.ToolInstallState.UNAVAILABLE: ("Unavailable", "Agent Lab blocked"),
        catalog_model.ToolInstallState.COMING_SOON: ("Coming soon", "Agent Lab blocked"),
    }

    for install_state, (expected_label, expected_agent_lab) in states.items():
        entry = _contract_entry(
            install_state,
            lifecycle=catalog_model.ToolLifecycle.COMING_SOON
            if install_state == catalog_model.ToolInstallState.COMING_SOON
            else catalog_model.ToolLifecycle.AVAILABLE,
            owner=catalog_model.ToolInstallOwner.DEVSEC
            if install_state == catalog_model.ToolInstallState.MANAGED
            else catalog_model.ToolInstallOwner.USER,
        )

        labels = catalog_model.derive_tool_labels(entry)

        assert expected_label in labels.install
        assert labels.agent_lab == expected_agent_lab
        if install_state == catalog_model.ToolInstallState.MANAGED:
            assert "DevSec managed" in labels.install
        if install_state == catalog_model.ToolInstallState.COMING_SOON:
            assert "Display only" in labels.safety


def test_run_scanner_uses_runtime_binary_detection_not_catalog_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr("security_observatory.scanners.shutil.which", lambda binary: None)

    result = run_scanner("semgrep", tmp_path, "repo", tmp_path / "scan", tmp_path / "rules")

    assert result.status.available is False
    assert result.status.error == "semgrep is not installed or not on PATH."


def _contract_entry(
    install_state: catalog_model.ToolInstallState,
    *,
    lifecycle: catalog_model.ToolLifecycle = catalog_model.ToolLifecycle.AVAILABLE,
    owner: catalog_model.ToolInstallOwner = catalog_model.ToolInstallOwner.USER,
) -> catalog_model.ToolCatalogEntry:
    return catalog_model.ToolCatalogEntry(
        id=f"contract-{install_state.value}",
        kind=catalog_model.ToolKind.SCANNER,
        label="Contract scanner",
        summary="Focused contract fixture.",
        category=catalog_model.ToolCategory.CODE_SECURITY,
        lifecycle=lifecycle,
        install_state=install_state,
        install=catalog_model.ToolInstallContract(
            method=catalog_model.ToolInstallMethod.MANUAL,
            owner=owner,
            detection=catalog_model.ToolInstallDetection.NONE,
            instructions="No install action.",
            next_step="No run action.",
            uninstall_posture=catalog_model.ToolUninstallPosture.NOT_SUPPORTED,
        ),
        policy=catalog_model.ToolPolicy(
            local_only=True,
            writes_files=False,
            network_access=catalog_model.NetworkAccess.NONE,
            external_targets=catalog_model.ExternalTargets.NONE,
            uses_credentials=catalog_model.CredentialUse.NONE,
            destructive_action=False,
            needs_approval=False,
            allowed_for_agent_lab=True,
            stores_results_locally=True,
            sends_source_off_machine=False,
            requires_human_setup=False,
            default_enabled=False,
        ),
        capabilities=catalog_model.ToolCapabilities(
            finding_categories=("contract",),
            evidence_types=(catalog_model.EvidenceType.SOURCE_PATTERN,),
            scan_profiles=("contract",),
        ),
        packs=(
            catalog_model.ToolPackMembership(
                pack_id=catalog_model.ToolPackId.STARTER,
                role=catalog_model.ToolPackRole.OPTIONAL,
                default_enabled=False,
            ),
        ),
        profiles=("contract",),
    )
