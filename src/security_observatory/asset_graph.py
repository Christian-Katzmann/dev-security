"""Asset-graph primitives: nodes, edges, and scan-time node derivation.

DëvSec has always stored a flat inventory — components, secrets, rotation
surfaces, IaC findings — with no relationships between them. The asset graph is
the missing layer: the *things worth protecting* (nodes) and how they connect
(edges). This module owns the node/edge vocabulary and derives the node set from
data the scanner already collects. Edge recovery (the harder half) lands in the
following campaign steps; the dataclass shape for edges lives here so the whole
graph contract sits in one place.

Honesty rule (campaign-wide): every node and every edge carries a confidence of
``unknown`` / ``weak`` / ``strong``. We never invent certainty. For a *node*,
confidence answers "how sure are we this is a real, identified asset":

  - a component listed in the SBOM            -> ``strong``  (declared, fingerprinted)
  - a secret a scanner actually found in a file -> ``strong`` (a tool saw it)
  - a rotation *surface* (a file that *may* hold credentials) -> ``weak``
  - a coarse IaC resource (file-level, not yet resource-level) -> ``weak``

Node identity reuses DëvSec's existing identities so the graph lines up with how
findings already cluster into cases (see ``cases._cluster_key``):

  - component -> ``sbom.component_fingerprint`` (stable per purl / name+version)
  - secret    -> the secret-bearing file path (matches ``secret:{file}`` clusters)
  - resource  -> the IaC file path (coarse for now; refined to real resource ids
                 when Checkov's resource graph is recovered)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .recency import rotation_surfaces_from_json


# Canonical vocabularies. The SQLite CHECK constraints in ``storage.py`` are
# GENERATED from these tuples (see ``storage.ASSET_NODE_TYPE_CHECK`` et al.), so
# the schema and this source-of-truth cannot silently drift — a test in
# ``tests/test_asset_graph.py`` guards the binding.
#
# All five node types are valid in the schema (the campaign's node_type enum),
# but this step derives only ``secret``, ``component``, and ``resource``:
#   - ``datastore`` is reserved for IaC resource-type classification (a database
#     resource), which needs the resource graph recovered in a later step.
#   - ``endpoint`` is reserved and deferred — nothing DëvSec collects cheaply
#     produces endpoints yet, so we mint none rather than guess.
NODE_TYPES: tuple[str, ...] = ("secret", "component", "resource", "datastore", "endpoint")
EDGE_TYPES: tuple[str, ...] = ("unlocks", "depends_on", "reachable_from", "stored_in")
CONFIDENCE_LEVELS: tuple[str, ...] = ("unknown", "weak", "strong")

#: Node types this step actually derives (a subset of ``NODE_TYPES``).
DERIVED_NODE_TYPES: tuple[str, ...] = ("component", "secret", "resource")

_CONFIDENCE_RANK = {level: rank for rank, level in enumerate(CONFIDENCE_LEVELS)}

# Scanners whose secret findings mark a real, located secret (strong identity).
# Mirrors ``cases.SECRET_SCANNERS`` without importing it, to avoid a cycle.
_SECRET_SCANNERS = {"gitleaks", "trufflehog", "trivy"}


@dataclass(frozen=True, slots=True)
class AssetNode:
    """A thing worth protecting, identified within a single scan.

    Identity is ``(node_type, identity_key)``; the database assigns the numeric
    ``id`` on insert. ``is_crown_jewel`` defaults to 0 and is only ever set by a
    human-edited label file in a later step — never inferred here.
    """

    node_type: str
    identity_key: str
    label: str
    confidence: str
    is_crown_jewel: bool = False

    def __post_init__(self) -> None:
        if self.node_type not in NODE_TYPES:
            raise ValueError(f"unknown node_type: {self.node_type!r}")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"unknown confidence: {self.confidence!r}")


@dataclass(frozen=True, slots=True)
class AssetEdge:
    """A directed relationship between two asset nodes, by node identity.

    Edges are addressed by the endpoints' ``identity_key`` (not numeric id) so a
    derivation step can emit them without knowing the ids the database will
    assign; ``storage.replace_asset_edges`` resolves identities to ids within the
    scan. ``reason`` is plain English a non-coder can read.
    """

    src_identity_key: str
    dst_identity_key: str
    edge_type: str
    confidence: str
    reason: str

    def __post_init__(self) -> None:
        if self.edge_type not in EDGE_TYPES:
            raise ValueError(f"unknown edge_type: {self.edge_type!r}")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"unknown confidence: {self.confidence!r}")


def stronger_confidence(a: str, b: str) -> str:
    """Return the higher-confidence of two labels (strong > weak > unknown)."""
    return a if _CONFIDENCE_RANK.get(a, 0) >= _CONFIDENCE_RANK.get(b, 0) else b


def derive_asset_nodes(
    *,
    components: Iterable[dict[str, Any]] | None = None,
    findings: Iterable[Any] | None = None,
    rotation_surfaces: Iterable[str] | None = None,
    iac_resources: Iterable[Any] | None = None,
) -> list[AssetNode]:
    """Derive the asset-node set from data a scan already produced.

    Pure and side-effect free so it is trivially testable and reusable. Inputs
    are the same artifacts ``storage.save_scan`` already holds:

      - ``components``: SBOM component dicts (``component_fingerprint`` + name/
        version) -> ``component`` nodes (strong).
      - ``findings``: ``Finding`` objects or dicts. Secret findings
        (category ``secrets``) -> ``secret`` nodes keyed by file (strong). IaC
        findings (Checkov) -> ``resource`` nodes keyed by file (weak, coarse) —
        but only for files no richer ``iac_resources`` entry already covers.
        Any finding carrying ``rotation_surfaces_json`` contributes those paths
        as ``secret`` surfaces too.
      - ``rotation_surfaces``: extra secret-bearing paths (weak), e.g. from a
        fresh ``recency.enumerate_rotation_surfaces`` call.
      - ``iac_resources``: recovered Checkov resources (``iac.IaCResource`` or
        dicts) — *real per-resource* identity. A data-store resource becomes a
        ``datastore`` node, any other becomes a ``resource`` node, each keyed by
        its resource address (weak). This is the seam that upgrades the coarse,
        file-level resource node into the per-resource graph Phase 2 traverses;
        when it is empty (a Checkov failure, or no IaC), node derivation falls
        back to the coarse file-level ``resource`` nodes from the findings.

    A scan with no SBOM and no IaC simply yields a smaller set (secrets only, or
    nothing) — never a crash. Nodes are deduped on ``(node_type, identity_key)``;
    on collision the stronger confidence wins. The returned list is sorted for a
    deterministic insertion / assertion order.
    """
    # Accumulate into a dict so repeated identities merge instead of duplicating.
    nodes: dict[tuple[str, str], AssetNode] = {}

    def _add(node_type: str, identity_key: str, label: str, confidence: str) -> None:
        identity_key = (identity_key or "").strip()
        if not identity_key:
            return
        key = (node_type, identity_key)
        existing = nodes.get(key)
        if existing is None:
            nodes[key] = AssetNode(
                node_type=node_type,
                identity_key=identity_key,
                label=(label or identity_key).strip() or identity_key,
                confidence=confidence,
            )
            return
        # Same asset seen again: keep the stronger confidence, prefer a real label.
        merged_confidence = stronger_confidence(existing.confidence, confidence)
        merged_label = existing.label or (label or identity_key)
        if merged_confidence != existing.confidence or merged_label != existing.label:
            nodes[key] = AssetNode(
                node_type=existing.node_type,
                identity_key=existing.identity_key,
                label=merged_label,
                confidence=merged_confidence,
            )

    for component in components or []:
        fingerprint = _text(component.get("component_fingerprint"))
        if not fingerprint:
            continue
        _add("component", fingerprint, _component_label(component), "strong")

    # Real per-resource / datastore nodes recovered from Checkov's resource graph
    # (see ``iac.parse_checkov_resources``). We track which IaC files these cover
    # so the coarse file-level fallback below does not also mint a competing
    # ``resource`` node for the same file.
    covered_iac_files: set[str] = set()
    for resource in iac_resources or []:
        address, file_path, is_datastore = _iac_resource_fields(resource)
        if not address:
            continue
        _add("datastore" if is_datastore else "resource", address, address, "weak")
        if file_path:
            covered_iac_files.add(_normalize_iac_path(file_path))

    for finding in findings or []:
        item = _finding_dict(finding)
        category = _text(item.get("category"))
        file_path = _text(item.get("file"))
        if category == "secrets":
            # A scanner located a secret in this file: strong, identified asset.
            if file_path and _text(item.get("scanner")) in _SECRET_SCANNERS:
                _add("secret", file_path, file_path, "strong")
            elif file_path:
                _add("secret", file_path, file_path, "strong")
        elif category == "iac" and _text(item.get("scanner")) == "checkov":
            # Coarse, file-level resource identity — the fallback used only when
            # the richer per-resource graph above did not cover this file (e.g. a
            # Checkov timeout that still produced findings).
            if file_path and _normalize_iac_path(file_path) not in covered_iac_files:
                _add("resource", file_path, file_path, "weak")
        # Findings may carry rotation surfaces (e.g. IOC findings) — secret-bearing
        # files that *may* hold credentials: weak until a scanner confirms one.
        for surface in rotation_surfaces_from_json(item.get("rotation_surfaces_json")):
            _add("secret", surface, surface, "weak")

    for surface in rotation_surfaces or []:
        surface = _text(surface)
        if surface:
            _add("secret", surface, surface, "weak")

    return sorted(nodes.values(), key=lambda node: (node.node_type, node.identity_key))


def _component_label(component: dict[str, Any]) -> str:
    name = _text(component.get("name"))
    version = _text(component.get("version"))
    if name and version:
        return f"{name}@{version}"
    if name:
        return name
    return _text(component.get("package_url")) or _text(component.get("component_fingerprint")) or "component"


def _iac_resource_fields(resource: Any) -> tuple[str, str, bool]:
    """Read ``(address, file_path, is_datastore)`` from an IaC resource.

    Accepts either an ``iac.IaCResource`` (the scan path) or a plain dict (tests
    and serialized inputs), so node derivation stays decoupled from the IaC
    module's concrete type.
    """
    if isinstance(resource, dict):
        address = _text(resource.get("address"))
        file_path = _text(resource.get("file_path"))
        is_datastore = bool(resource.get("is_datastore"))
        return address, file_path, is_datastore
    address = _text(getattr(resource, "address", None))
    file_path = _text(getattr(resource, "file_path", None))
    is_datastore = bool(getattr(resource, "is_datastore", False))
    return address, file_path, is_datastore


def _normalize_iac_path(path: str) -> str:
    """Collapse the leading-slash / ``./`` difference between scanners.

    Mirrors ``iac._normalize_path`` so the coarse-fallback suppression compares
    Checkov finding paths (``/infra/main.tf``) and recovered resource file paths
    on equal footing.
    """
    text = (path or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def _finding_dict(finding: Any) -> dict[str, Any]:
    if isinstance(finding, dict):
        return finding
    to_dict = getattr(finding, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return {
        "category": getattr(finding, "category", None),
        "scanner": getattr(finding, "scanner", None),
        "file": getattr(finding, "file", None),
        "rotation_surfaces_json": getattr(finding, "rotation_surfaces_json", None),
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
