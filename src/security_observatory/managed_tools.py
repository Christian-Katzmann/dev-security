from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from io import BytesIO
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
import uuid


MANIFEST_VERSION = 1
INSTALLER_VERSION = "security-observatory-managed-tools-v1"

GITLEAKS_VERSION = "8.30.1"
TRIVY_VERSION = "0.70.0"
SYFT_VERSION = "1.44.0"
GRYPE_VERSION = "0.112.0"

APPROVED_MANAGED_INSTALL_TOOL_IDS = frozenset({"gitleaks", "trivy", "syft", "grype"})

# Each entry below is a vetted release manifest. release_base_url, asset_name,
# and sha256 are pinned against the official upstream release page; bump them
# together when raising target_version. All sha256s vetted on 2026-05-22.
#
# Two near-candidates intentionally excluded:
#   - semgrep: no binary release artifacts on GitHub (pip/Homebrew only).
#   - osv-scanner: ships plain per-arch binaries, not tarballs, so the
#     _extract_binary_from_tarball path cannot install them as-is.
# Re-evaluate when those upstream release shapes change.
MANAGED_INSTALL_PROOF_TARGETS: dict[str, dict[str, Any]] = {
    # Source: https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1
    "gitleaks": {
        "tool_id": "gitleaks",
        "label": "Gitleaks",
        "binary": "gitleaks",
        "managed_package": "gitleaks",
        "target_version": GITLEAKS_VERSION,
        "target_version_label": f"Gitleaks v{GITLEAKS_VERSION}",
        "source": "devsec-managed-proof",
        "release_base_url": f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}",
        "network_access": True,
        "version_check_args": ("version",),
        "version_check_timeout_seconds": 5,
        "download_timeout_seconds": 30,
        "max_download_bytes": 40_000_000,
        "assets": {
            "darwin-arm64": {
                "asset_name": f"gitleaks_{GITLEAKS_VERSION}_darwin_arm64.tar.gz",
                "sha256": "b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5",
            },
            "darwin-x64": {
                "asset_name": f"gitleaks_{GITLEAKS_VERSION}_darwin_x64.tar.gz",
                "sha256": "dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709",
            },
            "linux-arm64": {
                "asset_name": f"gitleaks_{GITLEAKS_VERSION}_linux_arm64.tar.gz",
                "sha256": "e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080",
            },
            "linux-x64": {
                "asset_name": f"gitleaks_{GITLEAKS_VERSION}_linux_x64.tar.gz",
                "sha256": "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
            },
        },
    },
    # Source: https://github.com/aquasecurity/trivy/releases/tag/v0.70.0
    # sha256s pulled from the upstream trivy_0.70.0_checksums.txt.
    "trivy": {
        "tool_id": "trivy",
        "label": "Trivy",
        "binary": "trivy",
        "managed_package": "trivy",
        "target_version": TRIVY_VERSION,
        "target_version_label": f"Trivy v{TRIVY_VERSION}",
        "source": "devsec-managed-proof",
        "release_base_url": f"https://github.com/aquasecurity/trivy/releases/download/v{TRIVY_VERSION}",
        "network_access": True,
        "version_check_args": ("--version",),
        "version_check_timeout_seconds": 5,
        "download_timeout_seconds": 60,
        "max_download_bytes": 60_000_000,
        "assets": {
            "darwin-arm64": {
                "asset_name": f"trivy_{TRIVY_VERSION}_macOS-ARM64.tar.gz",
                "sha256": "68e543c51dcc96e1c344053a4fde9660cf602c25565d9f09dc17dd41e13b838a",
            },
            "darwin-x64": {
                "asset_name": f"trivy_{TRIVY_VERSION}_macOS-64bit.tar.gz",
                "sha256": "52d531452b19e7593da29366007d02a810e1e0080d02f9cf6a1afb46c35aaa93",
            },
            "linux-arm64": {
                "asset_name": f"trivy_{TRIVY_VERSION}_Linux-ARM64.tar.gz",
                "sha256": "2f6bb988b553a1bbac6bdd1ce890f5e412439564e17522b88a4541b4f364fc8d",
            },
            "linux-x64": {
                "asset_name": f"trivy_{TRIVY_VERSION}_Linux-64bit.tar.gz",
                "sha256": "8b4376d5d6befe5c24d503f10ff136d9e0c49f9127a4279fd110b727929a5aa9",
            },
        },
    },
    # Source: https://github.com/anchore/syft/releases/tag/v1.44.0
    # sha256s pulled from the upstream syft_1.44.0_checksums.txt.
    "syft": {
        "tool_id": "syft",
        "label": "Syft",
        "binary": "syft",
        "managed_package": "syft",
        "target_version": SYFT_VERSION,
        "target_version_label": f"Syft v{SYFT_VERSION}",
        "source": "devsec-managed-proof",
        "release_base_url": f"https://github.com/anchore/syft/releases/download/v{SYFT_VERSION}",
        "network_access": True,
        "version_check_args": ("version",),
        "version_check_timeout_seconds": 5,
        "download_timeout_seconds": 45,
        "max_download_bytes": 40_000_000,
        "assets": {
            "darwin-arm64": {
                "asset_name": f"syft_{SYFT_VERSION}_darwin_arm64.tar.gz",
                "sha256": "24e4d34078ae81da7c82539616f0ccac3e226cf4f74a38ce6fb3463619e50a55",
            },
            "darwin-x64": {
                "asset_name": f"syft_{SYFT_VERSION}_darwin_amd64.tar.gz",
                "sha256": "c40ece5407927327f94f35901727dbc604b46857e04f04ec94a310845fb71bde",
            },
            "linux-arm64": {
                "asset_name": f"syft_{SYFT_VERSION}_linux_arm64.tar.gz",
                "sha256": "6f6cdcdc695721d91ce756e3b5bc3e3416599c464101f5e32e9c3f33054ee6d9",
            },
            "linux-x64": {
                "asset_name": f"syft_{SYFT_VERSION}_linux_amd64.tar.gz",
                "sha256": "0e91737aee2b5baf1d255b959630194a302335d848ff97bb07921eb6205b5f5a",
            },
        },
    },
    # Source: https://github.com/anchore/grype/releases/tag/v0.112.0
    # sha256s pulled from the upstream grype_0.112.0_checksums.txt.
    "grype": {
        "tool_id": "grype",
        "label": "Grype",
        "binary": "grype",
        "managed_package": "grype",
        "target_version": GRYPE_VERSION,
        "target_version_label": f"Grype v{GRYPE_VERSION}",
        "source": "devsec-managed-proof",
        "release_base_url": f"https://github.com/anchore/grype/releases/download/v{GRYPE_VERSION}",
        "network_access": True,
        "version_check_args": ("version",),
        "version_check_timeout_seconds": 5,
        "download_timeout_seconds": 45,
        "max_download_bytes": 40_000_000,
        "assets": {
            "darwin-arm64": {
                "asset_name": f"grype_{GRYPE_VERSION}_darwin_arm64.tar.gz",
                "sha256": "58c3c372e334c27e5bd5031cfb5ae85dbe5e782478d52fb5515ea413b6d47da4",
            },
            "darwin-x64": {
                "asset_name": f"grype_{GRYPE_VERSION}_darwin_amd64.tar.gz",
                "sha256": "2fd7862e20ba43589b84919f05a5e6dd3a5b12d3860aed467bc4dc427926f6eb",
            },
            "linux-arm64": {
                "asset_name": f"grype_{GRYPE_VERSION}_linux_arm64.tar.gz",
                "sha256": "7fdeccf065965cc59386c656e5fcc1eb1bdf820e2433000bca7f010b8e6da155",
            },
            "linux-x64": {
                "asset_name": f"grype_{GRYPE_VERSION}_linux_amd64.tar.gz",
                "sha256": "acb14a030010fe9bdb9594b4ae108d9d14ef2f926d936aa0916dc62c89c058ea",
            },
        },
    },
}


class ManagedToolInstallError(ValueError):
    """Raised when a managed install or uninstall would cross a safety boundary."""


@dataclass(frozen=True, slots=True)
class ManagedToolEvidence:
    tool_id: str
    ownership_id: str | None
    verified: bool
    status: str
    install_root: str | None
    binary_path: str | None
    version: str | None
    source: str | None
    checksum: str | None
    installer_version: str | None
    installed_at: str | None
    manifest_path: str
    marker_path: str | None
    evidence: tuple[str, ...]
    problems: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "ownership_id": self.ownership_id,
            "verified": self.verified,
            "status": self.status,
            "install_root": self.install_root,
            "binary_path": self.binary_path,
            "version": self.version,
            "source": self.source,
            "checksum": self.checksum,
            "installer_version": self.installer_version,
            "installed_at": self.installed_at,
            "manifest_path": self.manifest_path,
            "marker_path": self.marker_path,
            "evidence": list(self.evidence),
            "problems": list(self.problems),
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def observatory_home(home: str | Path | None = None) -> Path:
    if home is not None:
        return Path(home).expanduser()
    return Path(os.environ.get("SECURITY_OBSERVATORY_HOME", "~/.security-observatory")).expanduser()


def managed_tools_root(home: str | Path | None = None) -> Path:
    return observatory_home(home) / "tools"


def managed_tools_bin_dir(home: str | Path | None = None) -> Path:
    return managed_tools_root(home) / "bin"


def managed_tools_manifest_path(home: str | Path | None = None) -> Path:
    return managed_tools_root(home) / "managed-tools.json"


def managed_install_root(tool_id: str, version: str, home: str | Path | None = None) -> Path:
    return managed_tools_root(home) / safe_tool_id(tool_id) / safe_version(version)


def managed_binary_path(tool_id: str, version: str, binary: str, home: str | Path | None = None) -> Path:
    return managed_install_root(tool_id, version, home) / "bin" / binary


def ownership_marker_path(install_root: str | Path) -> Path:
    return Path(install_root).expanduser() / ".devsec-managed-tool.json"


def new_ownership_id(tool_id: str) -> str:
    return f"devsec-{safe_tool_id(tool_id)}-{uuid.uuid4().hex[:12]}"


def install_managed_tool_files(
    tool_id: str,
    *,
    home: str | Path | None = None,
    ownership_id: str | None = None,
    artifact_fetcher: Callable[[str, int, int], bytes] | None = None,
    system: str | None = None,
    machine: str | None = None,
) -> dict[str, Any]:
    target = _approved_target(tool_id)
    version = str(target["target_version"])
    binary = str(target["binary"])
    asset = _asset_for_platform(target, system=system, machine=machine)
    asset_name = str(asset["asset_name"])
    release_base_url = str(target.get("release_base_url") or "").rstrip("/")
    if not release_base_url:
        raise ManagedToolInstallError(f"{tool_id} managed install target is missing its release base URL.")
    asset_url = f"{release_base_url}/{asset_name}"
    expected_sha256 = str(asset["sha256"])
    download_timeout = int(target.get("download_timeout_seconds") or 30)
    max_bytes = int(target.get("max_download_bytes") or 40_000_000)
    root = managed_install_root(tool_id, version, home)
    final_binary = managed_binary_path(tool_id, version, binary, home)
    shim_path = managed_tools_bin_dir(home) / binary
    ownership = ownership_id or new_ownership_id(tool_id)

    if root.exists():
        raise ManagedToolInstallError(f"A DëvSec-managed {tool_id} install already exists at {root}.")

    downloader = artifact_fetcher or download_bytes
    archive_bytes = downloader(asset_url, download_timeout, max_bytes)
    checksum = hashlib.sha256(archive_bytes).hexdigest()
    if checksum != expected_sha256:
        raise ManagedToolInstallError(
            f"Downloaded {asset_name} failed checksum verification; expected {expected_sha256}, got {checksum}."
        )

    staging_parent = root.parent
    staging_parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=f".{safe_version(version)}-", dir=str(staging_parent)))
    try:
        extracted_binary = _extract_binary_from_tarball(archive_bytes, binary, staging_root)
        version_check = run_managed_version_check(extracted_binary, target)
        if version_check["status"] != "passed":
            raise ManagedToolInstallError(version_check["output"] or f"{tool_id} version check failed.")
        if root.exists():
            raise ManagedToolInstallError(f"A DëvSec-managed {tool_id} install already exists at {root}.")
        staging_root.rename(root)
        write_managed_shim(final_binary, binary, home=home)
        installed_at = utc_now()
        record = {
            "ownership_id": ownership,
            "tool_id": tool_id,
            "version": version,
            "install_root": str(root),
            "binary_path": str(final_binary),
            "source": str(target.get("source") or "devsec-managed-proof"),
            "checksum": f"sha256:{checksum}",
            "installer_version": INSTALLER_VERSION,
            "installed_at": installed_at,
            "active": True,
            "version_check_status": "passed",
            "version_check_output": version_check["output"],
            "version_checked_at": installed_at,
            "metadata": {
                "artifact_name": asset_name,
                "source_url": asset_url,
                "network_access": bool(target.get("network_access")),
                "shim_path": str(shim_path),
            },
        }
        write_ownership_marker(record, home=home)
        return record
    except Exception:
        shutil.rmtree(staging_root, ignore_errors=True)
        if root.exists() and not ownership_marker_path(root).exists():
            shutil.rmtree(root, ignore_errors=True)
        raise


def uninstall_managed_tool_files(record: dict[str, Any], *, home: str | Path | None = None) -> dict[str, Any]:
    tool_id = str(record.get("tool_id") or "")
    target = _approved_target(tool_id)
    evidence = managed_tool_evidence(record, home=home)
    if not evidence.verified:
        problems = "; ".join(evidence.problems) or "ownership evidence is incomplete"
        raise ManagedToolInstallError(f"Refusing to uninstall {tool_id}: {problems}.")

    install_root = Path(str(evidence.install_root)).expanduser().resolve()
    managed_root = managed_tools_root(home).expanduser().resolve()
    if not _path_is_inside(install_root, managed_root):
        raise ManagedToolInstallError("Refusing to uninstall: install root is outside the DëvSec managed tools directory.")

    binary_path = Path(str(evidence.binary_path)).expanduser().resolve()
    if not _path_is_inside(binary_path, install_root):
        raise ManagedToolInstallError("Refusing to uninstall: binary path is outside the recorded install root.")

    marker = ownership_marker_path(install_root)
    if not marker.exists():
        raise ManagedToolInstallError("Refusing to uninstall: DëvSec ownership marker is missing.")

    removed_paths: list[str] = []
    binary = str(target["binary"])
    shim_path = managed_tools_bin_dir(home) / binary
    if shim_path.is_symlink():
        shim_target = shim_path.resolve(strict=False)
        if shim_target == binary_path or _path_is_inside(shim_target, install_root):
            shim_path.unlink()
            removed_paths.append(str(shim_path))
    elif shim_path.exists():
        raise ManagedToolInstallError(f"Refusing to remove non-symlink managed shim at {shim_path}.")

    shutil.rmtree(install_root)
    removed_paths.append(str(install_root))
    return {
        "tool_id": tool_id,
        "ownership_id": evidence.ownership_id,
        "removed_paths": removed_paths,
        "left_detected_tools_alone": True,
    }


def run_managed_version_check(binary_path: str | Path, target: dict[str, Any] | None = None) -> dict[str, Any]:
    args = tuple(target.get("version_check_args", ("--version",))) if target else ("--version",)
    timeout = int(target.get("version_check_timeout_seconds", 5)) if target else 5
    command = [str(Path(binary_path).expanduser()), *[str(arg) for arg in args]]
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "failed",
            "command": command,
            "timeout_seconds": timeout,
            "output": str(exc),
        }
    output = (proc.stdout or proc.stderr or "").strip()[:1000]
    return {
        "status": "passed" if proc.returncode == 0 else "failed",
        "command": command,
        "timeout_seconds": timeout,
        "exit_code": proc.returncode,
        "output": output,
    }


def download_bytes(url: str, timeout_seconds: int, max_bytes: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "security-observatory/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ManagedToolInstallError(f"Downloaded artifact exceeded the {max_bytes} byte safety limit.")
                chunks.append(chunk)
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise ManagedToolInstallError(f"Could not download managed tool artifact: {exc}") from exc
    return b"".join(chunks)


def write_ownership_marker(record: dict[str, Any], *, home: str | Path | None = None) -> Path:
    install_root = Path(str(record.get("install_root") or "")).expanduser()
    binary_path = Path(str(record.get("binary_path") or "")).expanduser()
    if not _path_is_inside(install_root, managed_tools_root(home)):
        raise ManagedToolInstallError("Refusing to write ownership marker outside the DëvSec managed tools directory.")
    if not _path_is_inside(binary_path, install_root):
        raise ManagedToolInstallError("Refusing to write ownership marker for a binary outside the install root.")
    marker = ownership_marker_path(install_root)
    marker.write_text(json.dumps(marker_payload_from_record(record), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return marker


def write_managed_shim(binary_path: str | Path, binary: str, *, home: str | Path | None = None) -> Path:
    shim_path = managed_tools_bin_dir(home) / binary
    shim_path.parent.mkdir(parents=True, exist_ok=True)
    final_binary = Path(binary_path).expanduser().resolve()
    if shim_path.is_symlink():
        target = shim_path.resolve(strict=False)
        if not _path_is_inside(target, managed_tools_root(home)):
            raise ManagedToolInstallError(f"Refusing to overwrite non-DëvSec shim at {shim_path}.")
        shim_path.unlink()
    elif shim_path.exists():
        raise ManagedToolInstallError(f"Refusing to overwrite non-symlink managed shim at {shim_path}.")
    shim_path.symlink_to(final_binary)
    return shim_path


def safe_tool_id(tool_id: str) -> str:
    cleaned = "".join(char for char in tool_id.strip().casefold() if char.isalnum() or char in {"-", "_", "."})
    if not cleaned or cleaned.startswith("."):
        raise ValueError("Managed tool id must be a safe relative name.")
    return cleaned


def safe_version(version: str) -> str:
    cleaned = "".join(char for char in version.strip() if char.isalnum() or char in {"-", "_", "."})
    if not cleaned or cleaned.startswith("."):
        raise ValueError("Managed tool version must be a safe relative name.")
    return cleaned


def load_managed_tools_manifest(path: str | Path | None = None, *, home: str | Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path).expanduser() if path else managed_tools_manifest_path(home)
    if not manifest_path.exists():
        return {"version": MANIFEST_VERSION, "tools": []}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": MANIFEST_VERSION, "tools": []}
    if not isinstance(payload, dict):
        return {"version": MANIFEST_VERSION, "tools": []}
    tools = payload.get("tools")
    if not isinstance(tools, list):
        tools = []
    return {"version": payload.get("version") or MANIFEST_VERSION, "tools": [item for item in tools if isinstance(item, dict)]}


def write_managed_tools_manifest(
    manifest: dict[str, Any],
    path: str | Path | None = None,
    *,
    home: str | Path | None = None,
) -> Path:
    manifest_path = Path(path).expanduser() if path else managed_tools_manifest_path(home)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": MANIFEST_VERSION,
        "tools": [dict(item) for item in manifest.get("tools", []) if isinstance(item, dict)],
        "updated_at": utc_now(),
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def upsert_manifest_record(
    record: dict[str, Any],
    path: str | Path | None = None,
    *,
    home: str | Path | None = None,
) -> dict[str, Any]:
    manifest = load_managed_tools_manifest(path, home=home)
    manifest_record = manifest_record_from_db_record(record)
    ownership_id = manifest_record["ownership_id"]
    tools = [item for item in manifest.get("tools", []) if item.get("ownership_id") != ownership_id]
    tools.append(manifest_record)
    manifest["tools"] = sorted(tools, key=lambda item: (str(item.get("tool_id") or ""), str(item.get("ownership_id") or "")))
    write_managed_tools_manifest(manifest, path, home=home)
    return manifest_record


def load_active_managed_tool_records(home: str | Path | None = None) -> list[dict[str, Any]]:
    db_path = observatory_home(home) / "db" / "observatory.sqlite"
    if not db_path.exists():
        return []
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select *
            from managed_tool_installations
            where active = 1
            order by tool_id asc, installed_at desc, ownership_id asc
            """
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        if conn is not None:
            conn.close()
    return [_managed_tool_record_from_row(row) for row in rows]


def manifest_record_from_db_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "ownership_id": str(record.get("ownership_id") or ""),
        "tool_id": str(record.get("tool_id") or ""),
        "version": str(record.get("version") or ""),
        "install_root": str(record.get("install_root") or ""),
        "binary_path": str(record.get("binary_path") or ""),
        "source": str(record.get("source") or ""),
        "checksum": record.get("checksum"),
        "installer_version": str(record.get("installer_version") or ""),
        "installed_at": str(record.get("installed_at") or ""),
        "active": bool(record.get("active", True)),
        "version_check_status": str(record.get("version_check_status") or ""),
        "version_check_output": record.get("version_check_output"),
        "version_checked_at": record.get("version_checked_at"),
    }


def _managed_tool_record_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["active"] = bool(data.get("active"))
    try:
        data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
    except json.JSONDecodeError:
        data["metadata"] = {}
    return data


def marker_payload_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "ownership_id": str(record.get("ownership_id") or ""),
        "tool_id": str(record.get("tool_id") or ""),
        "version": str(record.get("version") or ""),
        "install_root": str(record.get("install_root") or ""),
        "binary_path": str(record.get("binary_path") or ""),
        "source": str(record.get("source") or ""),
        "installer_version": str(record.get("installer_version") or ""),
        "installed_at": str(record.get("installed_at") or ""),
    }


def managed_tool_evidence_by_tool(
    records: Iterable[dict[str, Any]],
    *,
    home: str | Path | None = None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, ManagedToolEvidence]:
    manifest_payload = manifest if manifest is not None else load_managed_tools_manifest(home=home)
    evidence_by_tool: dict[str, ManagedToolEvidence] = {}
    for record in records:
        evidence = managed_tool_evidence(record, home=home, manifest=manifest_payload)
        current = evidence_by_tool.get(evidence.tool_id)
        if current is None or (evidence.verified and not current.verified):
            evidence_by_tool[evidence.tool_id] = evidence
    return evidence_by_tool


def managed_tool_evidence(
    record: dict[str, Any],
    *,
    home: str | Path | None = None,
    manifest: dict[str, Any] | None = None,
) -> ManagedToolEvidence:
    manifest_path = managed_tools_manifest_path(home)
    manifest_payload = manifest if manifest is not None else load_managed_tools_manifest(home=home)
    manifest_record = _manifest_record_for(record, manifest_payload)
    problems: list[str] = []
    evidence: list[str] = []

    tool_id = str(record.get("tool_id") or "")
    ownership_id = str(record.get("ownership_id") or "") or None
    install_root = _optional_path_text(record.get("install_root"))
    binary_path = _optional_path_text(record.get("binary_path"))
    marker_path = str(ownership_marker_path(install_root)) if install_root else None

    if not record.get("active", True):
        problems.append("SQLite ownership row is inactive.")
    else:
        evidence.append("SQLite active ownership row exists.")

    if not tool_id:
        problems.append("SQLite ownership row is missing tool id.")
    if not ownership_id:
        problems.append("SQLite ownership row is missing ownership id.")
    if not install_root:
        problems.append("SQLite ownership row is missing install root.")
    if not binary_path:
        problems.append("SQLite ownership row is missing binary path.")

    if manifest_record is None:
        problems.append("Managed-tools manifest does not contain the same ownership id.")
    elif _manifest_matches_record(manifest_record, record):
        evidence.append("Managed-tools manifest agrees with SQLite ownership row.")
    else:
        problems.append("Managed-tools manifest disagrees with SQLite ownership row.")

    if install_root and binary_path:
        if _path_is_inside(Path(binary_path), Path(install_root)):
            evidence.append("Binary path resolves inside recorded install root.")
        else:
            problems.append("Binary path is outside recorded install root.")
        if _path_is_inside(Path(install_root), managed_tools_root(home)):
            evidence.append("Install root is inside the DëvSec managed tools directory.")
        else:
            problems.append("Install root is outside the DëvSec managed tools directory.")
        if Path(binary_path).exists():
            evidence.append("Managed binary exists on disk.")
        else:
            problems.append("Managed binary does not exist on disk.")

    marker_payload = _read_marker(marker_path)
    if marker_path and marker_payload is None:
        problems.append("Managed install marker is missing or unreadable.")
    elif marker_payload and _marker_matches_record(marker_payload, record):
        evidence.append("Managed install marker agrees with SQLite ownership row.")
    else:
        problems.append("Managed install marker disagrees with SQLite ownership row.")

    version_status = str(record.get("version_check_status") or "").casefold()
    if version_status == "passed":
        evidence.append("Last local version check passed.")
    else:
        problems.append("Last local version check has not passed.")

    verified = not problems
    return ManagedToolEvidence(
        tool_id=tool_id,
        ownership_id=ownership_id,
        verified=verified,
        status="verified" if verified else "unverified",
        install_root=install_root,
        binary_path=binary_path,
        version=_optional_text(record.get("version")),
        source=_optional_text(record.get("source")),
        checksum=_optional_text(record.get("checksum")),
        installer_version=_optional_text(record.get("installer_version")),
        installed_at=_optional_text(record.get("installed_at")),
        manifest_path=str(manifest_path),
        marker_path=marker_path,
        evidence=tuple(evidence),
        problems=tuple(problems),
    )


def build_tool_install_preview(tool: dict[str, Any], managed_evidence: ManagedToolEvidence | None = None) -> dict[str, Any]:
    tool_id = str(tool.get("id") or "")
    install_state = str(tool.get("install_state") or "")
    lifecycle = str(tool.get("lifecycle") or "")
    install = tool.get("install") if isinstance(tool.get("install"), dict) else {}
    approved_target = MANAGED_INSTALL_PROOF_TARGETS.get(tool_id)
    detected_binary = install.get("binary")

    if install_state == "built-in":
        return _no_action_preview(tool_id, install_state, "Built-in tools do not need external installation.")
    if lifecycle == "coming-soon" or install_state == "coming-soon":
        return _no_action_preview(tool_id, install_state, "This catalog entry is display-only in the MVP.")

    if install_state == "managed" and managed_evidence:
        return {
            "tool_id": tool_id,
            "install_state": install_state,
            "action": "managed-uninstall-preview",
            "preview_available": True,
            "execution_available": tool_id in APPROVED_MANAGED_INSTALL_TOOL_IDS,
            "execution_reason": "Available only for verified DëvSec-owned copies of the approved managed proof tool.",
            "managed": True,
            "ownership": managed_evidence.to_dict(),
            "install_root": managed_evidence.install_root,
            "binary_path": managed_evidence.binary_path,
            "owned_paths": _owned_paths(managed_evidence.install_root, managed_evidence.binary_path, detected_binary),
            "network_access": False,
            "version_check": _version_check(tool_id, managed_evidence.binary_path, approved_target),
            "uninstall_boundary": "Only files under the matching DëvSec managed install root and marker may be removed.",
            "leaves_detected_tools_alone": True,
            "pack_install_supported": False,
            "notes": ["Detected PATH tools are user-owned context and are not removed by managed uninstall."],
        }

    if approved_target:
        version = str(approved_target["target_version"])
        root = managed_install_root(tool_id, version)
        binary_path = managed_binary_path(tool_id, version, str(approved_target["binary"]))
        shim_path = managed_tools_bin_dir() / str(approved_target["binary"])
        return {
            "tool_id": tool_id,
            "install_state": install_state,
            "action": "managed-install-preview",
            "preview_available": True,
            "execution_available": True,
            "execution_reason": "Available only for approved DëvSec managed-install proof tools.",
            "managed": False,
            "approved_managed_proof": True,
            "target_version": version,
            "target_version_label": approved_target.get("target_version_label", version),
            "install_method": "devsec-managed-copy",
            "install_root": str(root),
            "binary_path": str(binary_path),
            "shim_path": str(shim_path),
            "owned_paths": [str(root), str(binary_path), str(shim_path), str(ownership_marker_path(root))],
            "network_access": bool(approved_target.get("network_access")),
            "version_check": _version_check(tool_id, str(binary_path), approved_target),
            "uninstall_boundary": "Uninstall may remove only matching ownership-id files under the DëvSec tools directory.",
            "leaves_detected_tools_alone": True,
            "detected_user_binary": detected_binary if install_state == "detected" else None,
            "pack_install_supported": False,
            "notes": ["DëvSec will not relink, overwrite, upgrade, or uninstall a user-owned PATH copy."],
        }

    reason = (
        "Detected tools are user-owned and are not managed by DëvSec."
        if install_state == "detected"
        else "No managed installer is approved for this tool in the MVP."
    )
    return _no_action_preview(tool_id, install_state, reason)


def _no_action_preview(tool_id: str, install_state: str, reason: str) -> dict[str, Any]:
    return {
        "tool_id": tool_id,
        "install_state": install_state,
        "action": "none",
        "preview_available": False,
        "execution_available": False,
        "execution_reason": reason,
        "managed": False,
        "pack_install_supported": False,
        "leaves_detected_tools_alone": True,
        "notes": [reason],
    }


def _owned_paths(install_root: str | None, binary_path: str | None, binary: Any) -> list[str]:
    paths = [item for item in (install_root, binary_path) if item]
    if install_root:
        paths.append(str(ownership_marker_path(install_root)))
    if binary:
        paths.append(str(managed_tools_bin_dir() / str(binary)))
    return paths


def _version_check(tool_id: str, binary_path: str | None, target: dict[str, Any] | None) -> dict[str, Any]:
    args = tuple(target.get("version_check_args", ("--version",))) if target else ("--version",)
    return {
        "required": True,
        "command": [binary_path or tool_id, *args],
        "timeout_seconds": int(target.get("version_check_timeout_seconds", 5)) if target else 5,
    }


def _approved_target(tool_id: str) -> dict[str, Any]:
    if tool_id not in APPROVED_MANAGED_INSTALL_TOOL_IDS:
        raise ManagedToolInstallError(f"{tool_id or 'unknown tool'} is not approved for managed install in the MVP.")
    target = MANAGED_INSTALL_PROOF_TARGETS.get(tool_id)
    if not target:
        raise ManagedToolInstallError(f"{tool_id} does not have a managed install target.")
    return target


def _asset_for_platform(
    target: dict[str, Any],
    *,
    system: str | None = None,
    machine: str | None = None,
) -> dict[str, Any]:
    key = _platform_key(system or platform.system(), machine or platform.machine())
    assets = target.get("assets") if isinstance(target.get("assets"), dict) else {}
    asset = assets.get(key)
    if not isinstance(asset, dict):
        raise ManagedToolInstallError(f"Managed install is not supported on this platform ({key}).")
    return asset


def _platform_key(system: str, machine: str) -> str:
    os_name = system.strip().casefold()
    arch = machine.strip().casefold()
    if os_name == "darwin":
        os_name = "darwin"
    elif os_name == "linux":
        os_name = "linux"
    else:
        raise ManagedToolInstallError(f"Managed install is not supported on {system}.")

    if arch in {"arm64", "aarch64"}:
        arch_name = "arm64"
    elif arch in {"x86_64", "amd64", "x64"}:
        arch_name = "x64"
    else:
        raise ManagedToolInstallError(f"Managed install is not supported on {machine}.")
    return f"{os_name}-{arch_name}"


def _extract_binary_from_tarball(archive_bytes: bytes, binary: str, staging_root: Path) -> Path:
    target = staging_root / "bin" / binary
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:gz") as archive:
            member = next(
                (
                    item
                    for item in archive.getmembers()
                    if item.isfile() and Path(item.name).name == binary
                ),
                None,
            )
            if member is None:
                raise ManagedToolInstallError(f"Downloaded artifact did not contain a {binary} executable.")
            source = archive.extractfile(member)
            if source is None:
                raise ManagedToolInstallError(f"Downloaded artifact could not extract {binary}.")
            with source, target.open("wb") as handle:
                shutil.copyfileobj(source, handle)
    except (tarfile.TarError, OSError) as exc:
        raise ManagedToolInstallError(f"Downloaded artifact could not be unpacked safely: {exc}") from exc
    target.chmod(0o755)
    return target


def _manifest_record_for(record: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any] | None:
    ownership_id = str(record.get("ownership_id") or "")
    for item in manifest.get("tools", []):
        if isinstance(item, dict) and str(item.get("ownership_id") or "") == ownership_id:
            return item
    return None


def _manifest_matches_record(manifest_record: dict[str, Any], record: dict[str, Any]) -> bool:
    for key in ("ownership_id", "tool_id", "version", "install_root", "binary_path"):
        if str(manifest_record.get(key) or "") != str(record.get(key) or ""):
            return False
    return bool(manifest_record.get("active", True)) == bool(record.get("active", True))


def _marker_matches_record(marker: dict[str, Any], record: dict[str, Any]) -> bool:
    for key in ("ownership_id", "tool_id", "version", "install_root", "binary_path"):
        if str(marker.get(key) or "") != str(record.get(key) or ""):
            return False
    return True


def _read_marker(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    marker_path = Path(path)
    if not marker_path.exists():
        return None
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _path_is_inside(path: Path, root: Path) -> bool:
    try:
        path.expanduser().resolve().relative_to(root.expanduser().resolve())
    except (OSError, ValueError):
        return False
    return True


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_path_text(value: Any) -> str | None:
    text = _optional_text(value)
    return str(Path(text).expanduser()) if text else None
