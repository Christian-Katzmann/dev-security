from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import hashlib
import json
import re
import tomllib

from .model import Finding


DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
    "bundleDependencies",
    "bundledDependencies",
)
PYPROJECT_DEPENDENCY_KEYS = ("dependencies",)
PYPROJECT_OPTIONAL_DEPENDENCY_KEYS = ("optional-dependencies",)


@dataclass(frozen=True, slots=True)
class ManifestDependency:
    manifest_path: str
    ecosystem: str
    name: str
    declaration: str
    normalized_declaration: str
    scope: str
    manifest_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_dependency_manifests(repo: Path) -> list[ManifestDependency]:
    """Read source manifests only; lockfile parsing stays with SBOM generation."""
    manifests: list[ManifestDependency] = []
    for path in _candidate_manifests(repo):
        if path.name == "package.json":
            manifests.extend(_parse_package_json(repo, path))
        elif path.name == "pyproject.toml":
            manifests.extend(_parse_pyproject(repo, path))
        elif path.name == "requirements.txt":
            manifests.extend(_parse_requirements(repo, path))
    return manifests


def detect_silent_upgrades(
    *,
    repo_name: str,
    scan_id: str,
    current_components: list[Any],
    previous_components: list[dict[str, Any]],
    current_manifest_entries: list[Any],
    previous_manifest_entries: list[Any],
) -> list[Finding]:
    changes = _component_changes(current_components, previous_components)
    annotate_dependency_changes(changes, current_manifest_entries, previous_manifest_entries)
    findings: list[Finding] = []
    for change in changes:
        signal = change.get("silent_upgrade")
        if not isinstance(signal, dict) or signal.get("status") != "flagged":
            continue
        current = change.get("current_component") if isinstance(change.get("current_component"), dict) else {}
        previous = change.get("previous_component") if isinstance(change.get("previous_component"), dict) else {}
        component = current or previous
        package = str(change.get("name") or component.get("name") or "Unknown package")
        title = f"{package} silent {signal.get('kind', 'dependency')} change"
        findings.append(
            Finding(
                repo=repo_name,
                scanner="silent-upgrade",
                severity="medium",
                category="silent-upgrade",
                title=title,
                file=_source_file_for_change(change),
                remediation="Verify the lockfile change was expected or revert it with the smallest safe dependency update.",
                package_name=_optional_text(change.get("name")),
                package_version=_optional_text(change.get("current_version") or change.get("previous_version")),
                package_ecosystem=_optional_text(change.get("ecosystem")),
                package_url=_optional_text(change.get("package_url")),
                component_fingerprint=_optional_text(component.get("component_fingerprint")),
                component_package_key=_optional_text(change.get("package_key")),
                component_match_confidence="strong" if signal.get("kind") == "direct" else "weak",
                component_match_reason=str(signal.get("reason") or ""),
                old_version=_optional_text(change.get("previous_version")),
                new_version=_optional_text(change.get("current_version")),
                evidence_summary=str(signal.get("reason") or "A package changed without a matching manifest dependency change."),
                fingerprint=_silent_finding_fingerprint(scan_id, change, signal),
            )
        )
    return findings


def annotate_dependency_changes(
    changes: list[dict[str, Any]],
    current_manifest_entries: list[Any],
    previous_manifest_entries: list[Any],
) -> None:
    current_index = _manifest_index(current_manifest_entries)
    previous_index = _manifest_index(previous_manifest_entries)
    manifests_unchanged = _manifest_signature(current_manifest_entries) == _manifest_signature(previous_manifest_entries)

    for change in changes:
        change["silent_upgrade"] = _silent_upgrade_signal(change, current_index, previous_index, manifests_unchanged)


def _candidate_manifests(repo: Path) -> list[Path]:
    candidates: list[Path] = []
    for name in ("package.json", "pyproject.toml", "requirements.txt"):
        path = repo / name
        if path.is_file():
            candidates.append(path)
    return candidates


def _parse_package_json(repo: Path, path: Path) -> list[ManifestDependency]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    fingerprint = _manifest_fingerprint(path)
    entries: list[ManifestDependency] = []
    for section in DEPENDENCY_SECTIONS:
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for raw_name, raw_decl in deps.items():
            name = _clean_package_name(raw_name)
            declaration = _optional_text(raw_decl)
            if not name or declaration is None:
                continue
            entries.append(
                ManifestDependency(
                    manifest_path=_relative_path(path, repo),
                    ecosystem="npm",
                    name=name,
                    declaration=declaration,
                    normalized_declaration=_normalize_declaration(declaration),
                    scope=section,
                    manifest_fingerprint=fingerprint,
                )
            )
    return entries


def _parse_pyproject(repo: Path, path: Path) -> list[ManifestDependency]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    fingerprint = _manifest_fingerprint(path)
    entries: list[ManifestDependency] = []
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    for key in PYPROJECT_DEPENDENCY_KEYS:
        value = project.get(key)
        if isinstance(value, list):
            entries.extend(_python_dependency_entries(repo, path, value, "pypi", key, fingerprint))
    for key in PYPROJECT_OPTIONAL_DEPENDENCY_KEYS:
        optional = project.get(key)
        if isinstance(optional, dict):
            for group, values in optional.items():
                if isinstance(values, list):
                    entries.extend(_python_dependency_entries(repo, path, values, "pypi", f"{key}.{group}", fingerprint))

    tool = data.get("tool") if isinstance(data.get("tool"), dict) else {}
    poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}
    for section in ("dependencies", "dev-dependencies"):
        deps = poetry.get(section)
        if isinstance(deps, dict):
            entries.extend(_poetry_dependency_entries(repo, path, deps, section, fingerprint))
    groups = poetry.get("group") if isinstance(poetry.get("group"), dict) else {}
    for group, group_data in groups.items():
        if not isinstance(group_data, dict):
            continue
        deps = group_data.get("dependencies")
        if isinstance(deps, dict):
            entries.extend(_poetry_dependency_entries(repo, path, deps, f"group.{group}.dependencies", fingerprint))
    return entries


def _parse_requirements(repo: Path, path: Path) -> list[ManifestDependency]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    fingerprint = _manifest_fingerprint(path)
    entries: list[ManifestDependency] = []
    for line in lines:
        text = _strip_inline_comment(line).strip()
        if not text or text.startswith(("-", "git+", "http://", "https://")):
            continue
        name, declaration = _python_requirement_parts(text)
        if not name:
            continue
        entries.append(
            ManifestDependency(
                manifest_path=_relative_path(path, repo),
                ecosystem="pypi",
                name=name,
                declaration=declaration or text,
                normalized_declaration=_normalize_declaration(declaration or text),
                scope="requirements",
                manifest_fingerprint=fingerprint,
            )
        )
    return entries


def _python_dependency_entries(
    repo: Path,
    path: Path,
    values: list[Any],
    ecosystem: str,
    scope: str,
    fingerprint: str,
) -> list[ManifestDependency]:
    entries: list[ManifestDependency] = []
    for value in values:
        text = _optional_text(value)
        if not text:
            continue
        name, declaration = _python_requirement_parts(text)
        if not name:
            continue
        entries.append(
            ManifestDependency(
                manifest_path=_relative_path(path, repo),
                ecosystem=ecosystem,
                name=name,
                declaration=declaration or text,
                normalized_declaration=_normalize_declaration(declaration or text),
                scope=scope,
                manifest_fingerprint=fingerprint,
            )
        )
    return entries


def _poetry_dependency_entries(
    repo: Path,
    path: Path,
    deps: dict[Any, Any],
    scope: str,
    fingerprint: str,
) -> list[ManifestDependency]:
    entries: list[ManifestDependency] = []
    for raw_name, raw_decl in deps.items():
        name = _clean_package_name(raw_name)
        if not name or name == "python":
            continue
        declaration = _poetry_declaration(raw_decl)
        entries.append(
            ManifestDependency(
                manifest_path=_relative_path(path, repo),
                ecosystem="pypi",
                name=name,
                declaration=declaration,
                normalized_declaration=_normalize_declaration(declaration),
                scope=scope,
                manifest_fingerprint=fingerprint,
            )
        )
    return entries


def _component_changes(current_components: list[Any], previous_components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = _component_snapshot(current_components)
    previous = _component_snapshot(previous_components)
    changes: list[dict[str, Any]] = []
    for package_key in sorted(current.keys() - previous.keys()):
        changes.append(_change(package_key, ["added"], current[package_key], None))
    for package_key in sorted(current.keys() & previous.keys()):
        current_component = current[package_key]
        previous_component = previous[package_key]
        if _component_value(current_component.get("version")) == _component_value(previous_component.get("version")):
            continue
        change_types = ["version-changed"]
        comparison = _compare_versions(previous_component.get("version"), current_component.get("version"))
        if comparison is not None and comparison < 0:
            change_types.append("upgraded")
        elif comparison is not None and comparison > 0:
            change_types.append("downgraded")
        changes.append(_change(package_key, change_types, current_component, previous_component))
    return changes


def _change(
    package_key: str,
    change_types: list[str],
    current: dict[str, Any] | None,
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    component = current or previous or {}
    return {
        "package_key": package_key,
        "change_type": change_types[0],
        "change_types": change_types,
        "name": component.get("name"),
        "ecosystem": component.get("ecosystem"),
        "component_type": component.get("component_type"),
        "package_url": component.get("package_url"),
        "source_path": component.get("source_path"),
        "previous_version": previous.get("version") if previous else None,
        "current_version": current.get("version") if current else None,
        "previous_component": previous,
        "current_component": current,
    }


def _silent_upgrade_signal(
    change: dict[str, Any],
    current_index: dict[tuple[str, str], dict[str, Any]],
    previous_index: dict[tuple[str, str], dict[str, Any]],
    manifests_unchanged: bool,
) -> dict[str, Any]:
    if "added" not in change.get("change_types", []) and not _is_major_version_jump(change):
        return {"status": "not-silent", "reason": "Only new packages and major-version jumps are treated as silent-upgrade signals."}

    key = _manifest_key_for_change(change)
    if not key:
        return {"status": "unknown", "reason": "Package metadata is too incomplete to compare with source manifests."}

    current_entry = current_index.get(key)
    previous_entry = previous_index.get(key)
    if current_entry:
        if previous_entry and current_entry.get("normalized_declaration") == previous_entry.get("normalized_declaration"):
            return {
                "status": "flagged",
                "kind": "direct",
                "label": "Silent direct upgrade",
                "reason": f"{change.get('name') or 'This package'} changed in the saved SBOM while its manifest declaration stayed unchanged.",
                "manifest_path": current_entry.get("manifest_path"),
                "manifest_scope": current_entry.get("scope"),
                "manifest_declaration": current_entry.get("declaration"),
            }
        return {
            "status": "explained",
            "kind": "direct",
            "label": "Manifest changed",
            "reason": "The manifest declaration changed, so the lockfile movement is not treated as silent.",
            "manifest_path": current_entry.get("manifest_path"),
            "manifest_scope": current_entry.get("scope"),
            "manifest_declaration": current_entry.get("declaration"),
        }

    if previous_entry:
        return {
            "status": "explained",
            "kind": "direct",
            "label": "Manifest removed",
            "reason": "The direct manifest declaration changed, so the lockfile movement is not treated as silent.",
            "manifest_path": previous_entry.get("manifest_path"),
            "manifest_scope": previous_entry.get("scope"),
            "manifest_declaration": previous_entry.get("declaration"),
        }

    if not current_index and not previous_index:
        return {
            "status": "unknown",
            "kind": "transitive",
            "label": "Manifest not checked",
            "reason": "No source manifest dependency history was available for this package change.",
        }

    if manifests_unchanged:
        return {
            "status": "flagged",
            "kind": "transitive",
            "label": "Silent transitive upgrade",
            "reason": f"{change.get('name') or 'This transitive package'} changed in the saved SBOM while source manifests stayed semantically unchanged.",
        }
    return {
        "status": "explained",
        "kind": "transitive",
        "label": "Manifest changed",
        "reason": "Source manifests changed between scans, so this transitive lockfile movement is not treated as silent.",
    }


def _component_snapshot(components: list[Any]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for component in components:
        data = _component_dict(component)
        package_key = _component_package_key(data)
        if not package_key:
            continue
        public = {
            "package_key": package_key,
            "name": data.get("name"),
            "version": data.get("version"),
            "ecosystem": data.get("ecosystem") or _ecosystem_from_package_url(data.get("package_url")),
            "component_type": data.get("component_type"),
            "package_url": data.get("package_url"),
            "source_path": data.get("source_path"),
            "component_fingerprint": data.get("component_fingerprint"),
        }
        existing = snapshot.get(package_key)
        if not existing or _component_sort_key(public) < _component_sort_key(existing):
            snapshot[package_key] = public
    return snapshot


def _component_dict(component: Any) -> dict[str, Any]:
    if isinstance(component, dict):
        return dict(component)
    if hasattr(component, "to_dict"):
        data = component.to_dict()
        return dict(data) if isinstance(data, dict) else {}
    return {}


def _component_package_key(component: dict[str, Any]) -> str | None:
    package_url = _optional_text(component.get("package_url"))
    if package_url:
        return f"purl|{_package_url_without_version(package_url).casefold()}"
    ecosystem = _component_value(component.get("ecosystem") or _ecosystem_from_package_url(component.get("package_url")))
    component_type = _component_value(component.get("component_type"))
    name = _component_value(component.get("name"))
    if any((ecosystem, component_type, name)):
        return "|".join(["component", ecosystem, component_type, name])
    fingerprint = _component_value(component.get("component_fingerprint"))
    return f"fingerprint|{fingerprint}" if fingerprint else None


def _manifest_index(entries: list[Any]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        data = _entry_dict(entry)
        ecosystem = _component_value(data.get("ecosystem"))
        name = _clean_package_name(data.get("name"))
        if not ecosystem or not name:
            continue
        index.setdefault((ecosystem, name), data)
    return index


def _manifest_signature(entries: list[Any]) -> tuple[tuple[str, str, str, str, str], ...]:
    values = []
    for entry in entries:
        data = _entry_dict(entry)
        values.append(
            (
                _component_value(data.get("manifest_path")),
                _component_value(data.get("ecosystem")),
                _clean_package_name(data.get("name")),
                _component_value(data.get("scope")),
                _normalize_declaration(data.get("declaration") or data.get("normalized_declaration") or ""),
            )
        )
    return tuple(sorted(values))


def _entry_dict(entry: Any) -> dict[str, Any]:
    if isinstance(entry, dict):
        return dict(entry)
    if hasattr(entry, "to_dict"):
        data = entry.to_dict()
        return dict(data) if isinstance(data, dict) else {}
    return {}


def _manifest_key_for_change(change: dict[str, Any]) -> tuple[str, str] | None:
    component = change.get("current_component") or change.get("previous_component") or {}
    if not isinstance(component, dict):
        component = {}
    ecosystem = _component_value(change.get("ecosystem") or component.get("ecosystem") or _ecosystem_from_package_url(change.get("package_url")))
    name = _clean_package_name(change.get("name") or component.get("name"))
    if not ecosystem or not name:
        return None
    if ecosystem in {"python"}:
        ecosystem = "pypi"
    return (ecosystem, name)


def _is_major_version_jump(change: dict[str, Any]) -> bool:
    if "version-changed" not in change.get("change_types", []):
        return False
    previous_major = _major_version(change.get("previous_version"))
    current_major = _major_version(change.get("current_version"))
    return previous_major is not None and current_major is not None and current_major > previous_major


def _major_version(version: Any) -> int | None:
    text = str(version or "").strip()
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


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
    text = str(value or "").strip()
    if not text:
        return None
    tokens: list[int | str] = []
    for token in re.split(r"[._+\-:~]+", text):
        if not token:
            continue
        tokens.append(int(token) if token.isdigit() else token.casefold())
    return tokens or None


def _python_requirement_parts(value: str) -> tuple[str | None, str | None]:
    text = value.strip()
    match = re.match(r"(?P<name>[A-Za-z0-9_.-]+(?:\[[^\]]+\])?)\s*(?P<spec>.*)$", text)
    if not match:
        return None, None
    name = _clean_package_name(match.group("name").split("[", 1)[0])
    spec = match.group("spec").strip()
    return name, spec or text


def _poetry_declaration(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _normalize_declaration(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().casefold())


def _clean_package_name(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if not text:
        return ""
    if text.startswith("@"):
        return text
    return re.sub(r"[-_.]+", "-", text)


def _component_sort_key(component: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(component.get("name") or "").casefold(),
        str(component.get("version") or "").casefold(),
        str(component.get("source_path") or "").casefold(),
        str(component.get("package_url") or "").casefold(),
    )


def _package_url_without_version(package_url: str) -> str:
    base = package_url.split("?", 1)[0].split("#", 1)[0]
    if "@" not in base:
        return base
    head, tail = base.rsplit("@", 1)
    return head if "/" not in tail else base


def _ecosystem_from_package_url(package_url: Any) -> str | None:
    text = _optional_text(package_url)
    if not text or not text.startswith("pkg:"):
        return None
    ecosystem = text[4:].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    return ecosystem or None


def _manifest_fingerprint(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _silent_finding_fingerprint(scan_id: str, change: dict[str, Any], signal: dict[str, Any]) -> str:
    key = "|".join(
        [
            scan_id,
            str(change.get("package_key") or ""),
            str(change.get("previous_version") or ""),
            str(change.get("current_version") or ""),
            str(signal.get("kind") or ""),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _source_file_for_change(change: dict[str, Any]) -> str | None:
    signal = change.get("silent_upgrade") if isinstance(change.get("silent_upgrade"), dict) else {}
    manifest_path = signal.get("manifest_path") if isinstance(signal, dict) else None
    return _optional_text(change.get("source_path") or manifest_path)


def _strip_inline_comment(line: str) -> str:
    return line.split("#", 1)[0]


def _relative_path(path: Path, repo: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()


def _component_value(value: Any) -> str:
    return str(value or "").strip().casefold()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
