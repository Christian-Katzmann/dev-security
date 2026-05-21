from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json


@dataclass(frozen=True, slots=True)
class SBOMComponent:
    name: str | None
    version: str | None
    ecosystem: str | None
    component_type: str | None
    package_url: str | None
    license: str | None
    supplier: str | None
    source_path: str | None
    bom_ref: str | None = None
    source_format: str = "unknown"
    source_file: str | None = None
    component_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "component_fingerprint",
            component_fingerprint(
                package_url=self.package_url,
                ecosystem=self.ecosystem,
                component_type=self.component_type,
                name=self.name,
                version=self.version,
                bom_ref=self.bom_ref,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def component_fingerprint(
    *,
    package_url: str | None,
    ecosystem: str | None,
    component_type: str | None,
    name: str | None,
    version: str | None,
    bom_ref: str | None = None,
) -> str:
    if package_url:
        identity = f"purl|{package_url.strip()}"
    elif any((ecosystem, component_type, name, version)):
        identity = "|".join(
            [
                "component",
                _identity_part(ecosystem),
                _identity_part(component_type),
                _identity_part(name),
                _identity_part(version),
            ]
        )
    else:
        identity = f"bom-ref|{_identity_part(bom_ref)}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def load_sbom_components(scan_dir: Path) -> list[SBOMComponent]:
    for source_format, path in (
        ("cyclonedx", scan_dir / "sbom.cyclonedx.json"),
        ("syft", scan_dir / "syft.json"),
    ):
        components = parse_sbom_components(_read_json(path), source_format=source_format, source_file=str(path))
        if components:
            return components
    return []


def parse_sbom_components(
    data: Any,
    *,
    source_format: str | None = None,
    source_file: str | None = None,
) -> list[SBOMComponent]:
    if not isinstance(data, dict):
        return []

    detected_format = source_format or _detect_format(data)
    records = _component_records(data, detected_format)
    components: list[SBOMComponent] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        component = _parse_syft_component(record, source_file) if detected_format == "syft" else _parse_cyclonedx_component(record, source_file)
        if component:
            components.append(component)
    return components


def _parse_cyclonedx_component(record: dict[str, Any], source_file: str | None) -> SBOMComponent | None:
    name = _clean_text(record.get("name"))
    version = _clean_text(record.get("version"))
    package_url = _clean_text(record.get("purl"))
    component_type = _clean_text(record.get("type"))
    return SBOMComponent(
        name=name,
        version=version,
        ecosystem=_ecosystem_from_purl(package_url),
        component_type=component_type,
        package_url=package_url,
        license=_extract_license(record.get("licenses")),
        supplier=_extract_name(record.get("supplier")),
        source_path=_extract_cyclonedx_source_path(record),
        bom_ref=_clean_text(record.get("bom-ref")),
        source_format="cyclonedx",
        source_file=source_file,
    )


def _parse_syft_component(record: dict[str, Any], source_file: str | None) -> SBOMComponent | None:
    name = _clean_text(record.get("name"))
    version = _clean_text(record.get("version"))
    package_url = _clean_text(record.get("purl"))
    component_type = _clean_text(record.get("type"))
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return SBOMComponent(
        name=name,
        version=version,
        ecosystem=_ecosystem_from_purl(package_url) or component_type,
        component_type=component_type,
        package_url=package_url,
        license=_extract_license(record.get("licenses")),
        supplier=_extract_syft_supplier(record, metadata),
        source_path=_extract_syft_source_path(record),
        bom_ref=_clean_text(record.get("id")),
        source_format="syft",
        source_file=source_file,
    )


def _component_records(data: dict[str, Any], source_format: str) -> list[Any]:
    if source_format == "syft":
        records = data.get("artifacts")
    else:
        records = data.get("components")
    return records if isinstance(records, list) else []


def _detect_format(data: dict[str, Any]) -> str:
    if isinstance(data.get("artifacts"), list):
        return "syft"
    return "cyclonedx"


def _read_json(path: Path) -> Any:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def _extract_license(value: Any) -> str | None:
    if isinstance(value, str):
        return _clean_text(value)
    if not isinstance(value, list):
        return None

    licenses: list[str] = []
    for item in value:
        license_text: str | None = None
        if isinstance(item, str):
            license_text = _clean_text(item)
        elif isinstance(item, dict):
            if item.get("expression"):
                license_text = _clean_text(item.get("expression"))
            elif isinstance(item.get("license"), dict):
                license_data = item["license"]
                license_text = _clean_text(license_data.get("id") or license_data.get("name"))
            else:
                license_text = _clean_text(item.get("spdxExpression") or item.get("value") or item.get("id") or item.get("name"))
        if license_text and license_text not in licenses:
            licenses.append(license_text)
    return "; ".join(licenses) if licenses else None


def _extract_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return _clean_text(value.get("name") or value.get("url") or value.get("email"))
    if isinstance(value, list):
        for item in value:
            name = _extract_name(item)
            if name:
                return name
        return None
    return _clean_text(value)


def _extract_syft_supplier(record: dict[str, Any], metadata: dict[str, Any]) -> str | None:
    return (
        _extract_name(record.get("supplier"))
        or _extract_name(metadata.get("supplier"))
        or _extract_name(metadata.get("author"))
        or _extract_name(metadata.get("authors"))
        or _extract_name(metadata.get("maintainers"))
        or _extract_name(metadata.get("publisher"))
    )


def _extract_cyclonedx_source_path(record: dict[str, Any]) -> str | None:
    evidence = record.get("evidence")
    if isinstance(evidence, dict):
        occurrences = evidence.get("occurrences")
        if isinstance(occurrences, list):
            for occurrence in occurrences:
                if isinstance(occurrence, dict):
                    path = _clean_text(occurrence.get("location"))
                    if path:
                        return path

    properties = record.get("properties")
    if isinstance(properties, list):
        for item in properties:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").lower()
            if "location" in name and name.endswith(":path"):
                path = _clean_text(item.get("value"))
                if path:
                    return path
    return None


def _extract_syft_source_path(record: dict[str, Any]) -> str | None:
    locations = record.get("locations")
    if isinstance(locations, list):
        for location in locations:
            if isinstance(location, dict):
                path = _clean_text(location.get("path"))
                if path:
                    return path
    location = record.get("location")
    return _clean_text(location.get("path")) if isinstance(location, dict) else None


def _ecosystem_from_purl(package_url: str | None) -> str | None:
    if not package_url or not package_url.startswith("pkg:"):
        return None
    tail = package_url[4:]
    ecosystem = tail.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    return _clean_text(ecosystem)


def _identity_part(value: str | None) -> str:
    return (value or "").strip().casefold()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
