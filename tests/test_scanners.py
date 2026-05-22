import json
from pathlib import Path

from security_observatory import catalog as catalog_model
from security_observatory.managed_tools import (
    managed_install_root,
    marker_payload_from_record,
    ownership_marker_path,
)
from security_observatory.model import DEFAULT_EXCLUDES
from security_observatory.scanners import _command, run_scanner, scan_profile_catalog, scanner_catalog, tool_catalog
from security_observatory.storage import ObservatoryDB


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
    assert catalog["gitleaks"]["recommended_pack_ids"] == ["starter", "secrets"]
    assert catalog["gitleaks"]["tool_id"] == "gitleaks"


def test_scan_profile_catalog_points_profiles_to_security_packs():
    profiles = {item["id"]: item for item in scan_profile_catalog()}

    assert profiles["quick"]["primary_pack_ids"] == ["starter"]
    assert profiles["quick"]["recommended_pack_ids"] == ["starter"]
    assert "gitleaks" in profiles["quick"]["scanner_keys"]
    assert profiles["secrets"]["primary_pack_ids"] == ["secrets"]
    assert profiles["deps"]["primary_pack_ids"] == ["dependencies"]
    assert profiles["full"]["primary_pack_ids"] == ["starter", "secrets", "dependencies", "ai-agent"]
    assert profiles["iac"]["recommended_pack_ids"] == ["iac"]


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


def test_every_catalog_entry_has_a_real_documentation_link():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    docs_root = repo_root / "docs"

    missing: list[str] = []
    bad_homepage: list[str] = []
    bad_docs_path: list[str] = []
    for entry in catalog_model.CURRENT_TOOL_CATALOG:
        if entry.id == "external-surface":
            continue
        if not entry.docs_path and not entry.homepage_url:
            missing.append(entry.id)
        if entry.homepage_url and not entry.homepage_url.startswith(("http://", "https://")):
            bad_homepage.append(entry.id)
        if entry.docs_path:
            # docs_path must be an absolute path that the dashboard server can
            # serve, and the corresponding file must actually exist on disk so
            # the "Read documentation" link doesn't 404.
            if not entry.docs_path.startswith("/docs/"):
                bad_docs_path.append(f"{entry.id}: {entry.docs_path}")
                continue
            relative = entry.docs_path.removeprefix("/docs/")
            if not (docs_root / relative).is_file():
                bad_docs_path.append(f"{entry.id}: {entry.docs_path}")

    assert not missing, f"Catalog entries with no docs link: {missing}"
    assert not bad_homepage, f"homepage_url must be an absolute http(s) URL: {bad_homepage}"
    assert not bad_docs_path, (
        f"docs_path must start with /docs/ and resolve to a real file in docs/: {bad_docs_path}"
    )


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


def test_run_scanner_uses_verified_managed_gitleaks_when_path_is_empty(tmp_path: Path, monkeypatch):
    home = tmp_path / "observatory"
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr("security_observatory.scanners.shutil.which", lambda binary: None)
    seed = _managed_gitleaks_record(home)
    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        record = db.record_managed_tool(
            tool_id=str(seed["tool_id"]),
            version=str(seed["version"]),
            install_root=str(seed["install_root"]),
            binary_path=str(seed["binary_path"]),
            source=str(seed["source"]),
            checksum=str(seed["checksum"]),
            installer_version=str(seed["installer_version"]),
            ownership_id=str(seed["ownership_id"]),
            installed_at=str(seed["installed_at"]),
            version_check_status=str(seed["version_check_status"]),
            version_check_output="gitleaks 1.0.0",
            version_checked_at="2026-05-21T00:00:00+00:00",
        )
    finally:
        db.close()
    binary_path = Path(str(record["binary_path"]))
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_text("#!/bin/sh\nprintf '[]\\n'\n", encoding="utf-8")
    binary_path.chmod(0o755)
    marker = ownership_marker_path(str(record["install_root"]))
    marker.write_text(json.dumps(marker_payload_from_record(record), indent=2) + "\n", encoding="utf-8")

    result = run_scanner("gitleaks", tmp_path, "repo", tmp_path / "scan", tmp_path / "rules")

    assert result.status.available is True
    assert result.status.command[0] == str(binary_path.resolve())
    assert result.status.error is None


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


def _managed_gitleaks_record(home: Path) -> dict[str, object]:
    root = managed_install_root("gitleaks", "1.0.0", home)
    return {
        "ownership_id": "devsec-gitleaks-test",
        "tool_id": "gitleaks",
        "version": "1.0.0",
        "install_root": str(root),
        "binary_path": str(root / "bin" / "gitleaks"),
        "source": "unit-test",
        "checksum": "sha256:test",
        "installer_version": "test",
        "installed_at": "2026-05-21T00:00:00+00:00",
        "active": True,
        "version_check_status": "passed",
    }
