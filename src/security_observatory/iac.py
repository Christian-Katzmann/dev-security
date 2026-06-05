"""IaC resource-graph recovery from Checkov output.

DëvSec runs Checkov and (until now) kept only the list of *failed policy checks*,
throwing away the one thing that makes "blast radius to a crown jewel" mean
anything: which resources exist, which of them are data stores, and which
resources reference a data store. Dependency edges (step 1.2) connect
component -> component; only these resource edges let a *secret* node reach a
*datastore* node.

What Checkov actually gives us (the honest scope):

  Checkov's ``-o json`` output does NOT expose its internal (networkx) resource
  graph. What it *does* carry, per check, is enough to rebuild the load-bearing
  slice of that graph without a brittle full-graph parse:

    - ``resource``    -> the Terraform resource address, e.g. ``aws_db_instance.main``
    - ``file_path`` / ``file_abs_path``
    - ``code_block``  -> the resource's own HCL source as ``[line_no, text]`` pairs

  We use the address as a *real per-resource identity* (instead of the coarse
  file-level identity step 1.1 mints), classify data-store resource types, and
  recover cross-resource references by reading the HCL in ``code_block`` for
  references to other known resource addresses.

Honesty (campaign-wide ``unknown`` / ``weak`` / ``strong``): every edge here is
``weak``. The reference itself is real (it is literally in the source), but we
recover it from text rather than a resolved graph, and Checkov only reports
resources it ran a check on, so coverage is partial. ``weak`` is real enough to
rank on and never presented as certainty — which is exactly what Phase 2's
weakest-link rule needs (a consequence path through an IaC edge stays ``weak``
and never auto-promotes).

Edge orientation is *blast-propagation* direction — ``src`` compromised => ``dst``
reachable — so a per-finding traversal that follows edges forward answers
"what can this node reach":

  - ``resource -> datastore``  as ``stored_in``     (the resource keeps/reads data in the store)
  - ``secret   -> resource``   as ``reachable_from`` (the secret in that IaC file unlocks the resource)

A repo with no IaC yields no resources and no edges: correct, not a failure.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .asset_graph import AssetEdge


#: Resource types whose primary job is to *hold data worth protecting*. A node
#: derived from one of these becomes a ``datastore`` (a candidate crown jewel in
#: step 2.1) instead of a generic ``resource``. Curated, not exhaustive — adding
#: a type here is the one-line way to teach DëvSec a new data store. Secret/key
#: stores (Secrets Manager, KMS, Key Vault) count: they hold crown-jewel-grade
#: material, and "a resource can reach the secret store" is exactly a blast path.
DATASTORE_RESOURCE_TYPES: frozenset[str] = frozenset(
    {
        # AWS
        "aws_db_instance",
        "aws_rds_cluster",
        "aws_rds_cluster_instance",
        "aws_dynamodb_table",
        "aws_dynamodb_global_table",
        "aws_s3_bucket",
        "aws_elasticache_cluster",
        "aws_elasticache_replication_group",
        "aws_redshift_cluster",
        "aws_docdb_cluster",
        "aws_neptune_cluster",
        "aws_memorydb_cluster",
        "aws_qldb_ledger",
        "aws_timestreamwrite_table",
        "aws_efs_file_system",
        "aws_ebs_volume",
        "aws_secretsmanager_secret",
        "aws_ssm_parameter",
        "aws_kms_key",
        # GCP
        "google_sql_database_instance",
        "google_sql_database",
        "google_storage_bucket",
        "google_bigtable_instance",
        "google_bigquery_dataset",
        "google_spanner_instance",
        "google_spanner_database",
        "google_firestore_database",
        "google_redis_instance",
        "google_secret_manager_secret",
        # Azure
        "azurerm_storage_account",
        "azurerm_sql_database",
        "azurerm_mssql_database",
        "azurerm_cosmosdb_account",
        "azurerm_postgresql_server",
        "azurerm_postgresql_flexible_server",
        "azurerm_mysql_server",
        "azurerm_mysql_flexible_server",
        "azurerm_mariadb_server",
        "azurerm_redis_cache",
        "azurerm_key_vault",
    }
)

#: A reference token in HCL: ``aws_db_instance.main`` (we capture only the
#: ``type.name`` head; attribute tails like ``.endpoint`` are ignored).
_REFERENCE_TOKEN = re.compile(r"\b([a-z][a-z0-9_]*\.[A-Za-z_][A-Za-z0-9_-]*)")


@dataclass(frozen=True, slots=True)
class IaCResource:
    """A single IaC resource recovered from Checkov, identified by its address.

    ``address`` is the Terraform resource address (``aws_db_instance.main``, or
    ``module.db.aws_db_instance.main`` for a module resource) and is the node
    ``identity_key``. ``references`` are the *other* resource addresses this
    resource's HCL mentions — the recovered edges of the graph.
    """

    address: str
    resource_type: str
    name: str
    file_path: str | None
    is_datastore: bool
    references: tuple[str, ...] = ()

    @property
    def node_type(self) -> str:
        return "datastore" if self.is_datastore else "resource"


def is_datastore_resource_type(resource_type: str) -> bool:
    return (resource_type or "").strip() in DATASTORE_RESOURCE_TYPES


def load_checkov_resources(scan_dir: Path) -> list[IaCResource]:
    """Recover IaC resources from the Checkov output a scan already wrote.

    Reads ``<scan_dir>/checkov.json`` (the same raw file the normalizer consumes)
    and returns the resources plus their cross-resource references. A missing,
    empty, or unparseable file — a Checkov failure, timeout, or a repo with no
    IaC — yields ``[]`` so the surrounding scan stays partial rather than
    crashing.
    """
    data = _read_json(scan_dir / "checkov.json")
    if data is None:
        return []
    return parse_checkov_resources(data)


def parse_checkov_resources(data: Any) -> list[IaCResource]:
    """Parse Checkov JSON into :class:`IaCResource` objects, references resolved.

    Pure and side-effect free (mirrors :func:`sbom.parse_sbom_dependency_edges`)
    so it is trivially testable. Handles both Checkov shapes: a single result
    object (one framework) and a top-level list of them (multiple frameworks).
    Both ``failed_checks`` and ``passed_checks`` are read so a clean data store
    that no policy flagged still becomes a known reference target.
    """
    # First pass: collect each resource's address + accumulated HCL source. The
    # same resource appears once per check, so we merge code blocks by address.
    code_by_address: dict[str, list[str]] = {}
    file_by_address: dict[str, str | None] = {}
    for check in _iter_checks(data):
        address = _clean(check.get("resource"))
        if not address or "." not in address:
            continue
        lines = code_by_address.setdefault(address, [])
        lines.extend(_code_block_lines(check.get("code_block")))
        if address not in file_by_address:
            file_by_address[address] = _clean(check.get("file_path")) or _clean(
                check.get("file_abs_path")
            )

    # Build an alias map so a reference written as the short ``type.name`` head
    # resolves to a full address (covers both plain and module-prefixed forms).
    alias_to_address: dict[str, str] = {}
    for address in code_by_address:
        alias_to_address.setdefault(_type_name_head(address), address)

    # Second pass: resolve references by intersecting each resource's source
    # tokens with the known addresses (never minting a phantom target).
    resources: list[IaCResource] = []
    for address, lines in code_by_address.items():
        resource_type, name = _split_address(address)
        source = "\n".join(lines)
        references: list[str] = []
        seen: set[str] = set()
        for token in _REFERENCE_TOKEN.findall(source):
            target = alias_to_address.get(token)
            if target and target != address and target not in seen:
                seen.add(target)
                references.append(target)
        resources.append(
            IaCResource(
                address=address,
                resource_type=resource_type,
                name=name,
                file_path=file_by_address.get(address),
                is_datastore=is_datastore_resource_type(resource_type),
                references=tuple(references),
            )
        )
    resources.sort(key=lambda resource: resource.address)
    return resources


def derive_iac_resource_edges(
    resources: Iterable[IaCResource],
    *,
    secret_files: Iterable[str] | None = None,
) -> list[AssetEdge]:
    """Turn recovered IaC resources into ``stored_in`` / ``reachable_from`` edges.

    Two relationships, both oriented in blast-propagation direction and both
    ``weak`` (recovered from source text, partial coverage):

      - ``resource -> datastore`` (``stored_in``) when a resource's HCL references
        a data-store resource. This is the load-bearing crown-jewel path.
      - ``secret -> resource`` (``reachable_from``) when a secret-bearing file is
        the same IaC file that declares a resource — the secret can unlock it.

    ``secret_files`` are the *original* secret-node identity keys (the file paths
    gitleaks/trufflehog reported), so the emitted edge addresses the existing
    secret node exactly; matching is done on a normalized copy to bridge the
    leading-slash difference between Checkov and the secret scanners. Endpoints
    that don't resolve to a stored node are skipped downstream by
    :meth:`storage.replace_asset_edges`, so emitting an edge is always safe.
    """
    resources = list(resources)
    by_address = {resource.address: resource for resource in resources}
    edges: list[AssetEdge] = []
    seen: set[tuple[str, str, str]] = set()

    # resource -> datastore (stored_in)
    for resource in resources:
        for ref_address in resource.references:
            target = by_address.get(ref_address)
            if target is None or not target.is_datastore or target.address == resource.address:
                continue
            key = (resource.address, target.address, "stored_in")
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                AssetEdge(
                    src_identity_key=resource.address,
                    dst_identity_key=target.address,
                    edge_type="stored_in",
                    confidence="weak",
                    reason=(
                        f"{resource.address} references the data store {target.address} "
                        f"in its IaC definition, so compromising {resource.name} can reach {target.name}."
                    ),
                )
            )

    # secret -> resource (reachable_from)
    if secret_files:
        resources_by_norm: dict[str, list[IaCResource]] = {}
        for resource in resources:
            if resource.file_path:
                resources_by_norm.setdefault(_normalize_path(resource.file_path), []).append(resource)
        for secret_file in secret_files:
            secret_file = (secret_file or "").strip()
            if not secret_file:
                continue
            for resource in resources_by_norm.get(_normalize_path(secret_file), []):
                key = (secret_file, resource.address, "reachable_from")
                if key in seen:
                    continue
                seen.add(key)
                edges.append(
                    AssetEdge(
                        src_identity_key=secret_file,
                        dst_identity_key=resource.address,
                        edge_type="reachable_from",
                        confidence="weak",
                        reason=(
                            f"A secret in {secret_file} sits in the IaC file that defines "
                            f"{resource.address}, so the secret can unlock {resource.name}."
                        ),
                    )
                )

    return edges


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _iter_checks(data: Any) -> Iterable[dict[str, Any]]:
    """Yield every check dict from whatever shape Checkov emitted."""
    blocks = data if isinstance(data, list) else [data]
    for block in blocks:
        if not isinstance(block, dict):
            continue
        results = block.get("results")
        if not isinstance(results, dict):
            continue
        for key in ("failed_checks", "passed_checks"):
            checks = results.get(key)
            if isinstance(checks, list):
                for check in checks:
                    if isinstance(check, dict):
                        yield check


def _code_block_lines(code_block: Any) -> list[str]:
    """Flatten Checkov's ``code_block`` ([[line_no, text], ...]) to its text."""
    if not isinstance(code_block, list):
        return []
    lines: list[str] = []
    for entry in code_block:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            text = entry[1]
            if isinstance(text, str):
                lines.append(text)
        elif isinstance(entry, str):
            lines.append(entry)
    return lines


def _split_address(address: str) -> tuple[str, str]:
    """Return ``(resource_type, name)`` from a resource address.

    Works for plain (``aws_db_instance.main``) and module-prefixed
    (``module.db.aws_db_instance.main``) addresses — the type is always the
    second-to-last segment and the name the last.
    """
    parts = address.split(".")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return address, address


def _type_name_head(address: str) -> str:
    resource_type, name = _split_address(address)
    return f"{resource_type}.{name}"


def _normalize_path(path: str | None) -> str:
    """Collapse the leading-slash / ``./`` difference between scanners."""
    text = (path or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _read_json(path: Path) -> Any:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
