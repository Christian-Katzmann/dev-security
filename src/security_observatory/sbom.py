from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import json

from .asset_graph import AssetEdge


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


def load_sbom_dependency_edges(scan_dir: Path) -> list[AssetEdge]:
    """Recover ``depends_on`` edges from the same SBOM that produced the nodes.

    DëvSec runs Syft to emit both CycloneDX and Syft-native SBOMs, then (until
    now) kept only the flat component list. The *dependency graph* — which
    package pulls in which — sits in that same output and was thrown away. This
    reads it back as :class:`asset_graph.AssetEdge` objects addressed by
    ``component_fingerprint``, so :meth:`storage.replace_asset_edges` can wire
    them to the component nodes already stored for the scan (no new nodes).

    We walk the same format-preference order as :func:`load_sbom_components`
    (CycloneDX first, then Syft) and derive the edges from the *same* file that
    yielded the components, so every edge endpoint resolves to a real node. An
    SBOM with no dependency block simply yields no edges — never a crash.
    """
    for source_format, path in (
        ("cyclonedx", scan_dir / "sbom.cyclonedx.json"),
        ("syft", scan_dir / "syft.json"),
    ):
        data = _read_json(path)
        components = parse_sbom_components(data, source_format=source_format, source_file=str(path))
        if components:
            return parse_sbom_dependency_edges(data, components, source_format=source_format)
    return []


def parse_sbom_dependency_edges(
    data: Any,
    components: list[SBOMComponent],
    *,
    source_format: str | None = None,
) -> list[AssetEdge]:
    """Parse declared dependency relationships into ``depends_on`` edges.

    ``data`` is the raw SBOM JSON; ``components`` is the already-parsed component
    list (so edge endpoints reuse the exact ``component_fingerprint`` identities
    the nodes carry). Both CycloneDX ``dependencies`` and Syft
    ``artifactRelationships`` are *declared* graphs, so the edges they yield are
    ``strong`` — we never fabricate a weak/heuristic link here (no inference is
    done; that confidence tier stays reserved for a future heuristic linker).

    Edges are deduped on ``(source, destination)`` and self-loops are dropped. A
    reference that does not map to a parsed component (e.g. the synthetic root
    node CycloneDX puts in ``metadata.component``) is skipped rather than minting
    a phantom node.
    """
    if not isinstance(data, dict):
        return []

    detected_format = source_format or _detect_format(data)
    ref_to_fingerprint: dict[str, str] = {}
    ref_to_label: dict[str, str] = {}
    for component in components:
        if not component.bom_ref:
            continue
        ref_to_fingerprint.setdefault(component.bom_ref, component.component_fingerprint)
        ref_to_label.setdefault(component.bom_ref, _component_display_name(component))

    if detected_format == "syft":
        pairs = _syft_dependency_pairs(data)
    else:
        pairs = _cyclonedx_dependency_pairs(data)

    edges: list[AssetEdge] = []
    seen: set[tuple[str, str]] = set()
    for src_ref, dst_ref in pairs:
        src_fingerprint = ref_to_fingerprint.get(src_ref)
        dst_fingerprint = ref_to_fingerprint.get(dst_ref)
        if not src_fingerprint or not dst_fingerprint:
            continue
        if src_fingerprint == dst_fingerprint:
            continue
        key = (src_fingerprint, dst_fingerprint)
        if key in seen:
            continue
        seen.add(key)
        src_label = ref_to_label.get(src_ref) or src_ref
        dst_label = ref_to_label.get(dst_ref) or dst_ref
        edges.append(
            AssetEdge(
                src_identity_key=src_fingerprint,
                dst_identity_key=dst_fingerprint,
                edge_type="depends_on",
                confidence="strong",
                reason=f"{src_label} declares a dependency on {dst_label} in the SBOM dependency graph.",
            )
        )
    return edges


def _cyclonedx_dependency_pairs(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Yield (depender_ref, dependency_ref) from a CycloneDX ``dependencies`` block."""
    dependencies = data.get("dependencies")
    if not isinstance(dependencies, list):
        return []
    pairs: list[tuple[str, str]] = []
    for entry in dependencies:
        if not isinstance(entry, dict):
            continue
        ref = _clean_text(entry.get("ref"))
        depends_on = entry.get("dependsOn")
        if not ref or not isinstance(depends_on, list):
            continue
        for dependency in depends_on:
            dependency_ref = _clean_text(dependency)
            if dependency_ref:
                pairs.append((ref, dependency_ref))
    return pairs


def _syft_dependency_pairs(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Yield (depender_ref, dependency_ref) from Syft ``artifactRelationships``.

    Syft serialises a ``dependency-of`` relationship as ``{parent, child}`` where
    the *parent* is a dependency of the *child* — so the child is the depender.
    Other relationship types (``contains``, ``ownership-by-file-overlap``,
    ``evident-by``) are not dependency edges and are ignored.
    """
    relationships = data.get("artifactRelationships")
    if not isinstance(relationships, list):
        return []
    pairs: list[tuple[str, str]] = []
    for relationship in relationships:
        if not isinstance(relationship, dict):
            continue
        if _clean_text(relationship.get("type")) != "dependency-of":
            continue
        parent = _clean_text(relationship.get("parent"))
        child = _clean_text(relationship.get("child"))
        if parent and child:
            pairs.append((child, parent))
    return pairs


def _component_display_name(component: SBOMComponent) -> str:
    if component.name and component.version:
        return f"{component.name}@{component.version}"
    if component.name:
        return component.name
    return component.package_url or component.bom_ref or "component"


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
