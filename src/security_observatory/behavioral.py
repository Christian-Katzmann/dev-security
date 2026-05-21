from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import hashlib
import re


MAX_BEHAVIORAL_PACKAGES = 5
MAX_BEHAVIORAL_ARTIFACT_BYTES = 50 * 1024 * 1024
MAX_BEHAVIORAL_FILES = 20_000


@dataclass(slots=True)
class BehavioralDriftTarget:
    repo_name: str
    scan_id: str
    previous_scan_id: str | None
    package_key: str
    package_name: str | None
    package_ecosystem: str | None
    package_url: str | None
    component_fingerprint: str | None
    old_version: str | None
    new_version: str | None
    version_direction: str | None
    old_artifact: str | None
    new_artifact: str | None
    old_artifact_size: int | None
    new_artifact_size: int | None
    status: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def select_behavioral_drift_targets(
    current_components: list[Any],
    previous_components: list[Any],
    *,
    repo_name: str,
    scan_id: str,
    previous_scan_id: str | None,
    artifact_cache_dir: Path,
    max_packages: int = MAX_BEHAVIORAL_PACKAGES,
    max_artifact_bytes: int = MAX_BEHAVIORAL_ARTIFACT_BYTES,
) -> list[BehavioralDriftTarget]:
    """Select changed dependency versions for bounded behavioral analysis.

    This does not fetch packages. It only resolves already-present local
    artifacts, which keeps the advanced check explicit and testable.
    """
    current_by_key = _component_snapshot(current_components)
    previous_by_key = _component_snapshot(previous_components)
    targets: list[BehavioralDriftTarget] = []

    for package_key in sorted(current_by_key.keys() & previous_by_key.keys()):
        current = current_by_key[package_key]
        previous = previous_by_key[package_key]
        old_version = _optional_text(previous.get("version"))
        new_version = _optional_text(current.get("version"))
        if _component_value(old_version) == _component_value(new_version):
            continue

        target = _target_for_version_change(
            current,
            previous,
            package_key=package_key,
            repo_name=repo_name,
            scan_id=scan_id,
            previous_scan_id=previous_scan_id,
            artifact_cache_dir=artifact_cache_dir,
            max_artifact_bytes=max_artifact_bytes,
        )
        targets.append(target)

    ready_count = 0
    bounded: list[BehavioralDriftTarget] = []
    for target in sorted(targets, key=_target_sort_key):
        if target.status != "queued":
            bounded.append(target)
            continue
        if ready_count >= max(0, max_packages):
            target.status = "not_checked"
            target.reason = f"Behavioral analysis is capped at {max_packages} changed package versions per scan."
        else:
            ready_count += 1
        bounded.append(target)
    return bounded


def _target_for_version_change(
    current: dict[str, Any],
    previous: dict[str, Any],
    *,
    package_key: str,
    repo_name: str,
    scan_id: str,
    previous_scan_id: str | None,
    artifact_cache_dir: Path,
    max_artifact_bytes: int,
) -> BehavioralDriftTarget:
    old_version = _optional_text(previous.get("version"))
    new_version = _optional_text(current.get("version"))
    old_artifact = _artifact_result(previous, artifact_cache_dir, max_artifact_bytes)
    new_artifact = _artifact_result(current, artifact_cache_dir, max_artifact_bytes)
    status = "queued"
    reason = "Ready for malcontent differential analysis."

    if not old_version:
        status = "not_checked"
        reason = "The previous package version is unavailable, so there is no old artifact to compare."
    elif not new_version:
        status = "not_checked"
        reason = "The new package version is unavailable, so there is no new artifact to compare."
    elif old_artifact["status"] != "ready":
        status = "not_checked"
        reason = str(old_artifact["reason"])
    elif new_artifact["status"] != "ready":
        status = "not_checked"
        reason = str(new_artifact["reason"])

    return BehavioralDriftTarget(
        repo_name=repo_name,
        scan_id=scan_id,
        previous_scan_id=previous_scan_id,
        package_key=package_key,
        package_name=_optional_text(current.get("name")) or _optional_text(previous.get("name")),
        package_ecosystem=_optional_text(current.get("ecosystem")) or _optional_text(previous.get("ecosystem")),
        package_url=_optional_text(current.get("package_url")) or _optional_text(previous.get("package_url")),
        component_fingerprint=_optional_text(current.get("component_fingerprint")) or _optional_text(previous.get("component_fingerprint")),
        old_version=old_version,
        new_version=new_version,
        version_direction=_version_direction(old_version, new_version),
        old_artifact=old_artifact["path"],
        new_artifact=new_artifact["path"],
        old_artifact_size=old_artifact["size"],
        new_artifact_size=new_artifact["size"],
        status=status,
        reason=reason,
    )


def _artifact_result(component: dict[str, Any], cache_dir: Path, max_artifact_bytes: int) -> dict[str, Any]:
    for candidate in _artifact_candidates(component, cache_dir):
        if not candidate.exists():
            continue
        size = _path_size(candidate, max_artifact_bytes)
        if size > max_artifact_bytes:
            return {
                "status": "not_checked",
                "path": str(candidate),
                "size": size,
                "reason": f"Artifact is larger than the {max_artifact_bytes} byte behavioral-analysis limit.",
            }
        return {"status": "ready", "path": str(candidate), "size": size, "reason": "Artifact is available."}
    return {
        "status": "not_checked",
        "path": None,
        "size": None,
        "reason": "No local artifact was available for this package version.",
    }


def _artifact_candidates(component: dict[str, Any], cache_dir: Path) -> list[Path]:
    candidates = []
    for field in ("artifact_path", "local_artifact_path", "artifact"):
        value = _optional_text(component.get(field))
        if value:
            candidates.append(Path(value).expanduser())

    name = _optional_text(component.get("name")) or _package_name_from_purl(component.get("package_url"))
    ecosystem = _optional_text(component.get("ecosystem")) or _ecosystem_from_purl(component.get("package_url")) or "unknown"
    version = _optional_text(component.get("version")) or "unknown"
    if name:
        base = cache_dir / _slug(ecosystem) / _slug(name) / _slug(version)
        candidates.extend(
            [
                base / "artifact",
                base / "artifact.tgz",
                base / "artifact.zip",
                base / "package.tgz",
                base / f"{_slug(name)}-{_slug(version)}.tgz",
            ]
        )

    package_url = _optional_text(component.get("package_url"))
    if package_url:
        digest = hashlib.sha256(package_url.encode("utf-8")).hexdigest()[:24]
        candidates.extend([cache_dir / "purl" / digest / "artifact", cache_dir / "purl" / f"{digest}.artifact"])
    return candidates


def _path_size(path: Path, max_artifact_bytes: int) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        total += item.stat().st_size
        if total > max_artifact_bytes:
            return total
    return total


def _component_snapshot(components: list[Any]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for component in components:
        data = _component_dict(component)
        package_key = _component_package_key(data)
        existing = snapshot.get(package_key)
        if not existing or _component_sort_key(data) < _component_sort_key(existing):
            snapshot[package_key] = data
    return snapshot


def _component_dict(component: Any) -> dict[str, Any]:
    if hasattr(component, "to_dict"):
        return component.to_dict()
    return dict(component) if isinstance(component, dict) else {}


def _component_package_key(component: dict[str, Any]) -> str:
    package_url = _optional_text(component.get("package_url"))
    if package_url:
        return f"purl|{_package_url_without_version(package_url).casefold()}"
    ecosystem = _component_value(component.get("ecosystem"))
    component_type = _component_value(component.get("component_type"))
    name = _component_value(component.get("name"))
    if any((ecosystem, component_type, name)):
        return "|".join(["component", ecosystem, component_type, name])
    bom_ref = _component_value(component.get("bom_ref"))
    if bom_ref:
        return f"bom-ref|{bom_ref}"
    return f"fingerprint|{_component_value(component.get('component_fingerprint'))}"


def _package_url_without_version(package_url: str) -> str:
    base = package_url.split("?", 1)[0].split("#", 1)[0]
    if "@" not in base:
        return base
    head, tail = base.rsplit("@", 1)
    return head if "/" not in tail else base


def _version_direction(old_version: str | None, new_version: str | None) -> str | None:
    comparison = _compare_versions(old_version, new_version)
    if comparison is None:
        return "changed"
    if comparison < 0:
        return "upgraded"
    if comparison > 0:
        return "downgraded"
    return None


def _compare_versions(previous: Any, current: Any) -> int | None:
    previous_tokens = _version_tokens(previous)
    current_tokens = _version_tokens(current)
    if previous_tokens is None or current_tokens is None:
        return None
    max_length = max(len(previous_tokens), len(current_tokens))
    padded_previous = [*previous_tokens, *([0] * (max_length - len(previous_tokens)))]
    padded_current = [*current_tokens, *([0] * (max_length - len(current_tokens)))]
    for previous_token, current_token in zip(padded_previous, padded_current):
        if previous_token == current_token:
            continue
        if isinstance(previous_token, int) and isinstance(current_token, int):
            return -1 if previous_token < current_token else 1
        if isinstance(previous_token, int):
            return 1
        if isinstance(current_token, int):
            return -1
        return -1 if str(previous_token) < str(current_token) else 1
    return 0


def _version_tokens(value: Any) -> list[int | str] | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    raw_tokens = re.findall(r"\d+|[a-z]+", text.lstrip("v"))
    if not raw_tokens or not any(token.isdigit() for token in raw_tokens):
        return None
    return [int(token) if token.isdigit() else token for token in raw_tokens]


def _target_sort_key(target: BehavioralDriftTarget) -> tuple[int, str, str]:
    status_rank = 0 if target.status == "queued" else 1
    return (status_rank, target.package_ecosystem or "", target.package_name or target.package_key)


def _component_sort_key(component: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(component.get("name") or "").casefold(),
        str(component.get("version") or "").casefold(),
        str(component.get("source_path") or "").casefold(),
        str(component.get("package_url") or "").casefold(),
    )


def _package_name_from_purl(value: Any) -> str | None:
    text = _optional_text(value)
    if not text or not text.startswith("pkg:"):
        return None
    body = text[4:].split("?", 1)[0].split("#", 1)[0]
    if "/" not in body:
        return None
    name = body.split("/", 1)[1].rsplit("@", 1)[0]
    return name or None


def _ecosystem_from_purl(value: Any) -> str | None:
    text = _optional_text(value)
    if not text or not text.startswith("pkg:"):
        return None
    return text[4:].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0] or None


def _slug(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return safe or "unknown"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _component_value(value: Any) -> str:
    return str(value or "").strip().casefold()
