from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
import csv
import io
import json

from .model import DEFAULT_EXCLUDES, Finding
from .recency import rotation_surfaces_from_json


VALID_ECOSYSTEMS = {"npm", "pypi", "other"}
IOC_SCANNER = "ioc-watch"
IOC_CATEGORY = "supply-chain-ioc"


@dataclass(frozen=True, slots=True)
class IOCIndicator:
    ecosystem: str
    name: str | None = None
    versions: tuple[str, ...] = ()
    namespace_prefix: str | None = None
    domain: str | None = None
    confidence: str | None = None
    source_file: str | None = None
    source_line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["versions"] = list(self.versions)
        return data


@dataclass(frozen=True, slots=True)
class IOCPack:
    pack_id: str
    source: str
    published_at: str | None
    advisory_url: str | None
    confidence: str
    indicators: tuple[IOCIndicator, ...] = ()
    source_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["id"] = data.pop("pack_id")
        data["indicators"] = [indicator.to_dict() for indicator in self.indicators]
        return data


@dataclass(frozen=True, slots=True)
class IOCLoadIssue:
    path: str
    message: str
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class IOCLoadResult:
    packs: tuple[IOCPack, ...] = ()
    issues: tuple[IOCLoadIssue, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "packs": [pack.to_dict() for pack in self.packs],
            "issues": [issue.to_dict() for issue in self.issues],
        }


def starter_pack_dir() -> Path:
    return Path(__file__).resolve().parent / "iocs" / "starter"


def default_pack_sources() -> list[Path]:
    return [starter_pack_dir()]


def load_ioc_packs(sources: Iterable[Path | str]) -> IOCLoadResult:
    packs: list[IOCPack] = []
    issues: list[IOCLoadIssue] = []
    for source in sources:
        path = Path(source).expanduser()
        if not path.exists():
            issues.append(IOCLoadIssue(str(path), "IOC pack path does not exist."))
            continue
        candidates = _candidate_pack_files(path)
        for candidate in candidates:
            result = _load_pack_file(candidate)
            packs.extend(result.packs)
            issues.extend(result.issues)
    return IOCLoadResult(tuple(packs), tuple(issues))


def pack_from_record(record: dict[str, Any]) -> IOCPack:
    indicators = tuple(indicator_from_record(item) for item in record.get("indicators", []) if isinstance(item, dict))
    return IOCPack(
        pack_id=str(record.get("id") or record.get("pack_id") or "").strip(),
        source=str(record.get("source") or "Unknown source").strip(),
        published_at=_optional_text(record.get("published_at")),
        advisory_url=_optional_text(record.get("advisory_url")),
        confidence=str(record.get("confidence") or "medium").strip() or "medium",
        indicators=indicators,
        source_file=_optional_text(record.get("source_file")),
    )


def indicator_from_record(record: dict[str, Any]) -> IOCIndicator:
    return IOCIndicator(
        ecosystem=_ecosystem(record.get("ecosystem")),
        name=_optional_text(record.get("name")),
        versions=tuple(_string_list(record.get("versions"))),
        namespace_prefix=_optional_text(record.get("namespace_prefix")),
        domain=_optional_text(record.get("domain")),
        confidence=_optional_text(record.get("confidence")),
        source_file=_optional_text(record.get("source_file")),
        source_line=_optional_int(record.get("source_line")),
    )


def match_ioc_packs(
    *,
    packs: Iterable[IOCPack | dict[str, Any]],
    components: Iterable[dict[str, Any] | Any],
    repo: Path,
    repo_name: str,
) -> list[Finding]:
    normalized_packs = [pack if isinstance(pack, IOCPack) else pack_from_record(pack) for pack in packs]
    component_dicts = [_component_dict(component) for component in components]
    findings: list[Finding] = []

    for pack in normalized_packs:
        for indicator in pack.indicators:
            if indicator.domain:
                continue
            for component in component_dicts:
                if not _ecosystem_matches(indicator.ecosystem, component.get("ecosystem")):
                    continue
                name = _optional_text(component.get("name"))
                version = _optional_text(component.get("version"))
                if indicator.name and indicator.versions and _same_name(name, indicator.name) and version in indicator.versions:
                    findings.append(_finding_for_component(pack, indicator, component, repo_name, "exact match", "critical"))
                if indicator.namespace_prefix and name and name.casefold().startswith(indicator.namespace_prefix.casefold()):
                    findings.append(_finding_for_component(pack, indicator, component, repo_name, "namespace watch", "high"))

    domain_indicators = [
        (pack, indicator)
        for pack in normalized_packs
        for indicator in pack.indicators
        if indicator.domain
    ]
    if domain_indicators:
        domain_evidence = collect_domain_watch_evidence(repo)
        for pack, indicator in domain_indicators:
            domain = indicator.domain or ""
            for evidence in domain_evidence:
                if domain.casefold() in evidence["text"].casefold():
                    findings.append(_finding_for_domain(pack, indicator, evidence, repo_name))

    return list({finding.fingerprint: finding for finding in findings}.values())


def ioc_match_payload(finding: Finding | dict[str, Any]) -> dict[str, Any]:
    data = finding.to_dict() if isinstance(finding, Finding) else dict(finding)
    return {
        "repo_name": data.get("repo_name") or data.get("repo"),
        "repo_path": data.get("repo_path"),
        "scan_id": data.get("scan_id"),
        "affected_package": data.get("package_name"),
        "affected_version": data.get("package_version"),
        "ecosystem": data.get("package_ecosystem"),
        "source_path": data.get("file"),
        "severity": data.get("severity"),
        "title": data.get("title"),
        "match_type": data.get("ioc_match_type"),
        "confidence": data.get("ioc_confidence"),
        "indicator": data.get("ioc_indicator"),
        "pack_id": data.get("ioc_pack_id"),
        "source_pack": data.get("ioc_source"),
        "advisory_url": data.get("ioc_advisory_url"),
        "remediation": data.get("remediation"),
        "install_recency_confidence": data.get("install_recency_confidence"),
        "last_install_signal_at": data.get("last_install_signal_at"),
        "install_recency_evidence": data.get("install_recency_evidence"),
        "rotation_surfaces": rotation_surfaces_from_json(data.get("rotation_surfaces_json")),
        "fingerprint": data.get("fingerprint"),
    }


def collect_domain_watch_evidence(repo: Path) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    repo = repo.expanduser()
    for path in _walk_watch_files(repo):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        if path.name == "package.json":
            scripts = _package_json_scripts(text)
            if scripts:
                evidence.append({"file": _relative_path(path, repo), "kind": "package-json-scripts", "text": "\n".join(scripts)})
            continue
        if _is_workflow_file(path, repo):
            run_blocks = _workflow_run_blocks(text)
            evidence.append({"file": _relative_path(path, repo), "kind": "workflow-run-blocks", "text": "\n".join(run_blocks) if run_blocks else text})
            continue
        evidence.append({"file": _relative_path(path, repo), "kind": "lockfile", "text": text})
    return evidence


def _candidate_pack_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        item
        for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in {".yaml", ".yml"}
    )


def _load_pack_file(path: Path) -> IOCLoadResult:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return IOCLoadResult(issues=(IOCLoadIssue(str(path), f"Could not read IOC pack: {exc}"),))
    try:
        raw = _parse_pack_yaml(text)
    except ValueError as exc:
        return IOCLoadResult(issues=(IOCLoadIssue(str(path), str(exc)),))
    pack, issues = _validate_pack(raw, path)
    return IOCLoadResult(packs=(pack,) if pack else (), issues=tuple(issues))


def _parse_pack_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list: str | None = None
    current_item: dict[str, Any] | None = None
    pending_list_field: str | None = None

    for line_number, original in enumerate(text.splitlines(), start=1):
        line = _strip_comment(original).rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and not stripped.startswith("- "):
            key, separator, value = stripped.partition(":")
            if not separator:
                raise ValueError(f"Line {line_number}: expected key: value.")
            key = key.strip()
            if key == "indicators" and not value.strip():
                data[key] = []
                current_list = key
                current_item = None
                pending_list_field = None
            else:
                data[key] = _parse_scalar(value.strip())
                current_list = None
                current_item = None
                pending_list_field = None
            continue

        if current_list != "indicators":
            raise ValueError(f"Line {line_number}: nested values are only supported under indicators.")

        if stripped.startswith("- "):
            rest = stripped[2:].strip()
            if pending_list_field and current_item is not None and ":" not in rest:
                current_item[pending_list_field].append(_parse_scalar(rest))
                continue
            current_item = {"__line__": line_number}
            data.setdefault("indicators", []).append(current_item)
            pending_list_field = None
            if rest:
                _assign_yaml_field(current_item, rest, line_number)
                key = rest.partition(":")[0].strip()
                if current_item.get(key) == []:
                    pending_list_field = key
            continue

        if current_item is None:
            raise ValueError(f"Line {line_number}: indicator field found before an indicator item.")
        _assign_yaml_field(current_item, stripped, line_number)
        key = stripped.partition(":")[0].strip()
        pending_list_field = key if current_item.get(key) == [] else None

    return data


def _assign_yaml_field(target: dict[str, Any], text: str, line_number: int) -> None:
    key, separator, value = text.partition(":")
    if not separator:
        raise ValueError(f"Line {line_number}: expected indicator key: value.")
    key = key.strip()
    value = value.strip()
    target[key] = [] if not value else _parse_scalar(value)


def _parse_scalar(value: str) -> Any:
    if not value:
        return ""
    if value in {"[]", "[ ]"}:
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_clean_yaml_string(item) for item in next(csv.reader([inner], skipinitialspace=True))]
    lowered = value.lower()
    if lowered in {"null", "none", "~"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"
    return _clean_yaml_string(value)


def _clean_yaml_string(value: Any) -> str:
    text = str(value).strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    return text


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def _validate_pack(raw: dict[str, Any], path: Path) -> tuple[IOCPack | None, list[IOCLoadIssue]]:
    issues: list[IOCLoadIssue] = []
    pack_id = _optional_text(raw.get("id") or raw.get("pack_id"))
    if not pack_id:
        return None, [IOCLoadIssue(str(path), "IOC pack is missing id.")]
    raw_indicators = raw.get("indicators")
    if raw_indicators is None:
        return None, [IOCLoadIssue(str(path), "IOC pack is missing indicators[].")]
    if not isinstance(raw_indicators, list):
        return None, [IOCLoadIssue(str(path), "IOC pack indicators must be a list.")]

    indicators: list[IOCIndicator] = []
    confidence = _optional_text(raw.get("confidence")) or "medium"
    for item in raw_indicators:
        if not isinstance(item, dict):
            issues.append(IOCLoadIssue(str(path), "Indicator must be a mapping."))
            continue
        line = _optional_int(item.get("__line__"))
        ecosystem = _ecosystem(item.get("ecosystem"))
        name = _optional_text(item.get("name"))
        versions = tuple(_string_list(item.get("versions")))
        namespace_prefix = _optional_text(item.get("namespace_prefix"))
        domain = _optional_text(item.get("domain"))
        indicator_confidence = _optional_text(item.get("confidence")) or confidence
        if ecosystem not in VALID_ECOSYSTEMS:
            issues.append(IOCLoadIssue(str(path), f"Unsupported ecosystem {ecosystem!r}.", line))
            continue
        if not any((name, namespace_prefix, domain)):
            issues.append(IOCLoadIssue(str(path), "Indicator needs name, namespace_prefix, or domain.", line))
            continue
        if name and not versions and not namespace_prefix:
            issues.append(IOCLoadIssue(str(path), "Named package indicators need versions[].", line))
            continue
        indicators.append(
            IOCIndicator(
                ecosystem=ecosystem,
                name=name,
                versions=versions,
                namespace_prefix=namespace_prefix,
                domain=domain,
                confidence=indicator_confidence,
                source_file=str(path),
                source_line=line,
            )
        )

    pack = IOCPack(
        pack_id=pack_id,
        source=_optional_text(raw.get("source")) or pack_id,
        published_at=_optional_text(raw.get("published_at")),
        advisory_url=_optional_text(raw.get("advisory_url")),
        confidence=confidence,
        indicators=tuple(indicators),
        source_file=str(path),
    )
    return pack, issues


def _finding_for_component(
    pack: IOCPack,
    indicator: IOCIndicator,
    component: dict[str, Any],
    repo_name: str,
    match_type: str,
    severity: str,
) -> Finding:
    name = _optional_text(component.get("name")) or indicator.name or indicator.namespace_prefix or "package"
    version = _optional_text(component.get("version"))
    version_text = f" {version}" if version else ""
    title = f"{name}{version_text} matched named campaign IOC"
    remediation = (
        f"Review {pack.source} and inspect whether this package was installed or executed recently."
        if pack.advisory_url
        else "Inspect whether this package was installed or executed recently."
    )
    return Finding(
        repo=repo_name,
        scanner=IOC_SCANNER,
        severity=severity,
        category=IOC_CATEGORY,
        title=title,
        file=_optional_text(component.get("source_path")) or _optional_text(component.get("source_file")),
        remediation=remediation,
        package_name=name,
        package_version=version,
        package_ecosystem=_optional_text(component.get("ecosystem")) or indicator.ecosystem,
        package_url=_optional_text(component.get("package_url")),
        component_fingerprint=_optional_text(component.get("component_fingerprint")),
        component_package_key=_component_package_key(component),
        component_match_confidence="strong" if match_type == "exact match" else "weak",
        component_match_reason=match_type,
        evidence_summary=f"{match_type}: {indicator.name or indicator.namespace_prefix}",
        ioc_pack_id=pack.pack_id,
        ioc_source=pack.source,
        ioc_advisory_url=pack.advisory_url,
        ioc_confidence=indicator.confidence or pack.confidence,
        ioc_match_type=match_type,
        ioc_indicator=_indicator_label(indicator, version),
    )


def _finding_for_domain(pack: IOCPack, indicator: IOCIndicator, evidence: dict[str, str], repo_name: str) -> Finding:
    domain = indicator.domain or "domain"
    return Finding(
        repo=repo_name,
        scanner=IOC_SCANNER,
        severity="high",
        category=IOC_CATEGORY,
        title=f"{domain} matched named campaign domain watch",
        file=evidence.get("file"),
        remediation=f"Inspect the referenced {evidence.get('kind') or 'local evidence'} and confirm whether the domain is expected.",
        package_ecosystem=indicator.ecosystem,
        component_match_confidence="weak",
        component_match_reason="domain watch",
        evidence_summary=f"domain watch in {evidence.get('kind') or 'local evidence'}",
        ioc_pack_id=pack.pack_id,
        ioc_source=pack.source,
        ioc_advisory_url=pack.advisory_url,
        ioc_confidence=indicator.confidence or pack.confidence,
        ioc_match_type="domain watch",
        ioc_indicator=domain,
    )


def _walk_watch_files(repo: Path) -> list[Path]:
    if not repo.exists():
        return []
    files: list[Path] = []
    stack = [repo]
    while stack:
        path = stack.pop()
        if path.name in DEFAULT_EXCLUDES:
            continue
        try:
            if path.is_dir():
                stack.extend(sorted(path.iterdir(), key=lambda item: item.name.lower(), reverse=True))
                continue
            if path.stat().st_size > 2_000_000:
                continue
        except OSError:
            continue
        if path.name == "package.json" or path.name in {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock"} or _is_workflow_file(path, repo):
            files.append(path)
    return files


def _package_json_scripts(text: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return []
    return [str(value) for value in scripts.values() if value is not None]


def _workflow_run_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("run:"):
            value = stripped.partition(":")[2].strip()
            if value and value not in {"|", ">"}:
                blocks.append(value)
                continue
            base_indent = len(line) - len(line.lstrip(" "))
            collected: list[str] = []
            for follow in lines[index + 1 :]:
                if not follow.strip():
                    continue
                indent = len(follow) - len(follow.lstrip(" "))
                if indent <= base_indent:
                    break
                collected.append(follow.strip())
            if collected:
                blocks.append("\n".join(collected))
    return blocks


def _is_workflow_file(path: Path, repo: Path) -> bool:
    try:
        relative = path.relative_to(repo)
    except ValueError:
        return False
    return len(relative.parts) >= 3 and relative.parts[0] == ".github" and relative.parts[1] == "workflows" and path.suffix.lower() in {".yml", ".yaml"}


def _component_dict(component: dict[str, Any] | Any) -> dict[str, Any]:
    if hasattr(component, "to_dict"):
        return component.to_dict()
    return dict(component)


def _component_package_key(component: dict[str, Any]) -> str | None:
    name = _optional_text(component.get("name"))
    ecosystem = _optional_text(component.get("ecosystem") or component.get("component_type"))
    if not name:
        return None
    return f"{(ecosystem or 'unknown').casefold()}|{name.casefold()}"


def _indicator_label(indicator: IOCIndicator, matched_version: str | None = None) -> str:
    if indicator.domain:
        return indicator.domain
    if indicator.namespace_prefix:
        return indicator.namespace_prefix
    if indicator.name:
        versions = ", ".join(indicator.versions) if indicator.versions else matched_version or ""
        return f"{indicator.name}@{versions}" if versions else indicator.name
    return "indicator"


def _ecosystem(value: Any) -> str:
    text = _optional_text(value)
    if not text:
        return "other"
    normalized = text.strip().lower()
    return normalized if normalized in VALID_ECOSYSTEMS else normalized


def _ecosystem_matches(indicator_ecosystem: str, component_ecosystem: Any) -> bool:
    if indicator_ecosystem == "other":
        return True
    return indicator_ecosystem == (_optional_text(component_ecosystem) or "").casefold()


def _same_name(left: str | None, right: str | None) -> bool:
    return bool(left and right and left.casefold() == right.casefold())


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
