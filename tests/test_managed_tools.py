from __future__ import annotations

from io import BytesIO
from pathlib import Path
import hashlib
import json
import platform
import tarfile

from security_observatory.managed_tools import (
    APPROVED_MANAGED_INSTALL_TOOL_IDS,
    MANAGED_INSTALL_PROOF_TARGETS,
    ManagedToolInstallError,
    build_tool_install_preview,
    install_managed_tool_files,
    managed_install_root,
    managed_tool_evidence,
    marker_payload_from_record,
    ownership_marker_path,
    uninstall_managed_tool_files,
    upsert_manifest_record,
)
from security_observatory.scanners import security_pack_catalog, tool_catalog
from security_observatory.storage import ObservatoryDB


EXPECTED_PLATFORM_KEYS = frozenset({"darwin-arm64", "darwin-x64", "linux-arm64", "linux-x64"})


def test_every_approved_managed_tool_has_full_proof_target():
    assert APPROVED_MANAGED_INSTALL_TOOL_IDS, "Approved managed-install set must not be empty."
    for tool_id in APPROVED_MANAGED_INSTALL_TOOL_IDS:
        target = MANAGED_INSTALL_PROOF_TARGETS.get(tool_id)
        assert target is not None, f"{tool_id} is approved but has no proof target."
        for key in (
            "tool_id",
            "label",
            "binary",
            "managed_package",
            "target_version",
            "target_version_label",
            "source",
            "release_base_url",
            "network_access",
            "version_check_args",
            "version_check_timeout_seconds",
            "download_timeout_seconds",
            "max_download_bytes",
            "assets",
        ):
            assert key in target, f"{tool_id} proof target is missing {key}."
        assert target["tool_id"] == tool_id
        assert str(target["release_base_url"]).startswith("https://github.com/"), (
            f"{tool_id} release_base_url must point at an official GitHub release."
        )
        assets = target["assets"]
        assert isinstance(assets, dict)
        assert set(assets) == EXPECTED_PLATFORM_KEYS, (
            f"{tool_id} must publish assets for {sorted(EXPECTED_PLATFORM_KEYS)}, got {sorted(assets)}."
        )
        for platform_key, asset in assets.items():
            assert "asset_name" in asset and asset["asset_name"], f"{tool_id}/{platform_key} missing asset_name."
            sha = asset.get("sha256", "")
            assert len(sha) == 64 and all(ch in "0123456789abcdef" for ch in sha.lower()), (
                f"{tool_id}/{platform_key} sha256 must be 64 lowercase hex chars."
            )


def test_build_tool_install_preview_offers_execution_for_every_approved_tool():
    for tool_id in APPROVED_MANAGED_INSTALL_TOOL_IDS:
        target = MANAGED_INSTALL_PROOF_TARGETS[tool_id]
        tool = {
            "id": tool_id,
            "install_state": "missing",
            "lifecycle": "available",
            "install": {"binary": target["binary"]},
        }
        preview = build_tool_install_preview(tool)
        assert preview["action"] == "managed-install-preview", f"{tool_id} preview must offer install."
        assert preview["execution_available"] is True, f"{tool_id} must be executable from preview."
        assert preview["approved_managed_proof"] is True
        assert preview["target_version"] == target["target_version"]
        assert preview["target_version_label"] == target["target_version_label"]


def test_tool_catalog_marks_verified_devsec_managed_tool(tmp_path: Path, monkeypatch):
    home = tmp_path / "observatory"
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))
    record = _managed_gitleaks_record(home)
    _write_binary_and_marker(record)
    upsert_manifest_record(record, home=home)

    catalog = {item["id"]: item for item in tool_catalog(detect_install_state=True, managed_tool_records=[record])}
    gitleaks = catalog["gitleaks"]

    assert gitleaks["install_state"] == "managed"
    assert gitleaks["install"]["owner"] == "devsec"
    assert gitleaks["install"]["uninstall_posture"] == "devsec-managed"
    assert "Managed" in gitleaks["derived_labels"]["install"]
    assert "DevSec managed" in gitleaks["derived_labels"]["install"]
    assert gitleaks["managed_ownership"]["verified"] is True
    assert gitleaks["install_preview"]["action"] == "managed-uninstall-preview"
    assert gitleaks["install_preview"]["execution_available"] is True


def test_unverified_managed_tool_falls_back_to_detected_path_tool(tmp_path: Path, monkeypatch):
    home = tmp_path / "observatory"
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))
    monkeypatch.setattr("security_observatory.catalog.shutil.which", lambda binary: f"/usr/local/bin/{binary}")
    record = _managed_gitleaks_record(home)
    upsert_manifest_record(record, home=home)

    catalog = {item["id"]: item for item in tool_catalog(detect_install_state=True, managed_tool_records=[record])}
    gitleaks = catalog["gitleaks"]

    assert gitleaks["install_state"] == "detected"
    assert gitleaks["managed_ownership"]["verified"] is False
    assert "Managed install marker is missing or unreadable." in gitleaks["managed_ownership"]["problems"]
    assert gitleaks["install_preview"]["action"] == "managed-install-preview"
    assert gitleaks["install_preview"]["leaves_detected_tools_alone"] is True


def test_security_pack_catalog_aggregates_disabled_pack_previews(monkeypatch):
    monkeypatch.setattr("security_observatory.catalog.shutil.which", lambda binary: None)

    packs = {item["id"]: item for item in security_pack_catalog(detect_install_state=True)}

    starter = packs["starter"]
    assert starter["install_preview"]["action"] == "pack-install-preview"
    assert starter["install_preview"]["execution_available"] is False
    assert any(preview["tool_id"] == "gitleaks" for preview in starter["install_preview"]["tool_previews"])

    external_surface = packs["external-surface"]
    assert external_surface["mvp_state"] == "coming-soon"
    assert external_surface["install_preview"]["action"] == "none"
    assert external_surface["install_preview"]["tool_previews"] == []


def test_managed_tool_record_persists_sqlite_and_manifest(tmp_path: Path, monkeypatch):
    home = tmp_path / "observatory"
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))
    db = ObservatoryDB(tmp_path / "observatory.db")
    try:
        record = db.record_managed_tool(
            tool_id="gitleaks",
            version="1.0.0",
            install_root=str(managed_install_root("gitleaks", "1.0.0", home)),
            binary_path=str(managed_install_root("gitleaks", "1.0.0", home) / "bin" / "gitleaks"),
            source="unit-test",
            installer_version="test",
            version_check_status="passed",
        )
        saved = db.list_managed_tools()
    finally:
        db.close()

    assert saved == [record]
    manifest = json.loads((home / "tools" / "managed-tools.json").read_text(encoding="utf-8"))
    assert manifest["tools"][0]["ownership_id"] == record["ownership_id"]
    assert manifest["tools"][0]["tool_id"] == "gitleaks"


def test_managed_gitleaks_install_writes_owned_copy_and_manifest(tmp_path: Path, monkeypatch):
    home = tmp_path / "observatory"
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))
    archive = _gitleaks_archive("gitleaks 8.30.1\n")
    _patch_target_asset(monkeypatch, archive)

    install_record = install_managed_tool_files(
        "gitleaks",
        artifact_fetcher=lambda _url, _timeout, _limit: archive,
    )
    db = ObservatoryDB(tmp_path / "observatory.db")
    try:
        record = db.record_managed_tool(
            tool_id=str(install_record["tool_id"]),
            version=str(install_record["version"]),
            install_root=str(install_record["install_root"]),
            binary_path=str(install_record["binary_path"]),
            source=str(install_record["source"]),
            checksum=str(install_record["checksum"]),
            installer_version=str(install_record["installer_version"]),
            ownership_id=str(install_record["ownership_id"]),
            installed_at=str(install_record["installed_at"]),
            version_check_status=str(install_record["version_check_status"]),
            version_check_output=str(install_record["version_check_output"]),
            version_checked_at=str(install_record["version_checked_at"]),
            metadata=dict(install_record["metadata"]),
        )
    finally:
        db.close()

    evidence = managed_tool_evidence(record)
    assert evidence.verified is True
    assert Path(str(record["binary_path"])).exists()
    assert (home / "tools" / "bin" / "gitleaks").is_symlink()
    assert "gitleaks 8.30.1" in str(record["version_check_output"])


def test_managed_uninstall_removes_only_verified_owned_copy(tmp_path: Path, monkeypatch):
    home = tmp_path / "observatory"
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))
    record = _managed_gitleaks_record(home)
    _write_binary_and_marker(record)
    upsert_manifest_record(record, home=home)
    (home / "tools" / "bin").mkdir(parents=True)
    (home / "tools" / "bin" / "gitleaks").symlink_to(Path(str(record["binary_path"])))
    system_tool = tmp_path / "usr-local-bin" / "gitleaks"
    system_tool.parent.mkdir()
    system_tool.write_text("user-owned\n", encoding="utf-8")

    removal = uninstall_managed_tool_files(record, home=home)

    assert removal["left_detected_tools_alone"] is True
    assert not Path(str(record["install_root"])).exists()
    assert not (home / "tools" / "bin" / "gitleaks").exists()
    assert system_tool.read_text(encoding="utf-8") == "user-owned\n"


def test_managed_uninstall_refuses_unverified_detected_tool(tmp_path: Path, monkeypatch):
    home = tmp_path / "observatory"
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))
    record = _managed_gitleaks_record(home)
    system_tool = tmp_path / "usr-local-bin" / "gitleaks"
    system_tool.parent.mkdir()
    system_tool.write_text("user-owned\n", encoding="utf-8")

    try:
        uninstall_managed_tool_files(record, home=home)
    except ManagedToolInstallError as exc:
        assert "Refusing to uninstall" in str(exc)
    else:
        raise AssertionError("Expected uninstall to refuse missing ownership evidence.")

    assert system_tool.read_text(encoding="utf-8") == "user-owned\n"


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


def _write_binary_and_marker(record: dict[str, object]) -> None:
    binary_path = Path(str(record["binary_path"]))
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_text("#!/usr/bin/env bash\nprintf 'gitleaks 1.0.0\\n'\n", encoding="utf-8")
    binary_path.chmod(0o755)
    marker = ownership_marker_path(str(record["install_root"]))
    marker.write_text(json.dumps(marker_payload_from_record(record), indent=2) + "\n", encoding="utf-8")


def _gitleaks_archive(version_output: str) -> bytes:
    payload = f"#!/usr/bin/env bash\nprintf {json.dumps(version_output)}\n".encode("utf-8")
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("gitleaks")
        info.size = len(payload)
        info.mode = 0o755
        archive.addfile(info, BytesIO(payload))
    return buffer.getvalue()


def _patch_target_asset(monkeypatch, archive: bytes) -> None:
    target = dict(MANAGED_INSTALL_PROOF_TARGETS["gitleaks"])
    key = _current_platform_key()
    target["assets"] = {
        key: {
            "asset_name": "gitleaks-test.tar.gz",
            "sha256": hashlib.sha256(archive).hexdigest(),
        }
    }
    monkeypatch.setitem(MANAGED_INSTALL_PROOF_TARGETS, "gitleaks", target)


def _current_platform_key() -> str:
    os_name = platform.system().casefold()
    arch = platform.machine().casefold()
    return f"{'darwin' if os_name == 'darwin' else 'linux'}-{'arm64' if arch in {'arm64', 'aarch64'} else 'x64'}"
