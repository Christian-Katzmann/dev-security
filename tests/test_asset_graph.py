"""Asset-graph foundation: schema, node derivation, identity, and the edge seam.

Step 1.1 of the Honeygraph campaign. The asset graph is two new SQLite tables
(``asset_nodes`` / ``asset_edges``) plus scan-time node derivation from data
DëvSec already collects. These tests pin the contract the later steps build on:

  - the tables exist on a fresh DB and an existing DB gains them with no data loss;
  - derivation turns components / secrets / IaC findings into confidence-scored
    nodes, with identity stable across versions and distinct on a version change;
  - a scan with no SBOM and no IaC still yields a valid (smaller) node set;
  - the schema CHECK enums stay bound to the Python vocabularies (drift guard);
  - ``replace_asset_edges`` resolves endpoints by identity (the 1.2/1.3 seam).
"""

from pathlib import Path
import re
import sqlite3

import pytest

from security_observatory import asset_graph
from security_observatory.asset_graph import (
    AssetEdge,
    AssetNode,
    CONFIDENCE_LEVELS,
    EDGE_TYPES,
    NODE_TYPES,
    derive_asset_nodes,
)
from security_observatory.model import Finding
from security_observatory.sbom import SBOMComponent
from security_observatory.storage import (
    ASSET_CONFIDENCE_CHECK,
    ASSET_EDGE_TYPE_CHECK,
    ASSET_NODE_TYPE_CHECK,
    ObservatoryDB,
)


def _component(name: str, version: str, *, ecosystem: str = "npm") -> SBOMComponent:
    return SBOMComponent(
        name=name,
        version=version,
        ecosystem=ecosystem,
        component_type="library",
        package_url=f"pkg:{ecosystem}/{name}@{version}",
        license=None,
        supplier=None,
        source_path=None,
    )


def _save_scan(db: ObservatoryDB, *, scan_id: str, repo: str = "repo", **kwargs) -> None:
    kwargs.setdefault("findings", [])
    db.save_scan(
        scan_id=scan_id,
        repo_name=repo,
        repo_path="/tmp/repo",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        profile="quick",
        health_score=80,
        status="ok",
        scanner_statuses=[],
        report_path="/tmp/repo/report.json",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Schema creation + additive migration (no data loss on an existing DB)
# ---------------------------------------------------------------------------


def _table_columns(db: ObservatoryDB, table: str) -> set[str]:
    return {row["name"] for row in db.conn.execute(f"pragma table_info({table})").fetchall()}


def test_fresh_db_has_asset_tables(tmp_path):
    db = ObservatoryDB(tmp_path / "fresh.sqlite")
    try:
        node_cols = _table_columns(db, "asset_nodes")
        assert {
            "id", "scan_id", "repo_name", "node_type", "identity_key",
            "label", "is_crown_jewel", "confidence", "created_at",
        } <= node_cols
        edge_cols = _table_columns(db, "asset_edges")
        assert {
            "id", "scan_id", "repo_name", "src_node_id", "dst_node_id",
            "edge_type", "confidence", "reason", "created_at",
        } <= edge_cols
    finally:
        db.close()


def test_existing_db_gains_asset_tables_with_data_intact(tmp_path):
    """An older history DB without the asset tables gains them on next open."""
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            create table scans (
              id text primary key, repo_name text not null, repo_path text not null,
              started_at text not null, finished_at text, profile text not null,
              health_score integer not null, status text not null,
              scanner_status_json text not null, cases_json text not null default '[]',
              report_path text
            );
            insert into scans (id, repo_name, repo_path, started_at, profile, health_score, status, scanner_status_json)
              values ('repo-20260101T000000Z', 'repo', '/tmp/repo', '2026-01-01T00:00:00+00:00', 'quick', 80, 'ok', '[]');
            """
        )
        conn.commit()
    finally:
        conn.close()

    db = ObservatoryDB(db_path)
    try:
        # The pre-existing scan row survived, and the new tables now exist.
        assert db.conn.execute("select count(*) from scans").fetchone()[0] == 1
        assert db.list_asset_nodes() == []
        assert db.list_asset_edges() == []
    finally:
        db.close()


def test_is_crown_jewel_defaults_to_zero(tmp_path):
    db = ObservatoryDB(tmp_path / "cj.sqlite")
    try:
        _save_scan(db, scan_id="s1", findings=[
            Finding(repo="repo", scanner="gitleaks", severity="high", category="secrets",
                    title="AWS key", file=".env", line=3),
        ])
        nodes = db.list_asset_nodes(scan_id="s1")
        assert nodes and all(node["is_crown_jewel"] == 0 for node in nodes)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Node derivation (pure function)
# ---------------------------------------------------------------------------


def test_derives_component_secret_and_resource_nodes():
    components = [_component("left-pad", "1.3.0").to_dict()]
    findings = [
        Finding(repo="repo", scanner="gitleaks", severity="high", category="secrets",
                title="AWS key", file="config/.env", line=3),
        Finding(repo="repo", scanner="checkov", severity="medium", category="iac",
                title="S3 bucket public", file="infra/main.tf", line=10),
    ]
    nodes = derive_asset_nodes(components=components, findings=findings)
    by_type = {node.node_type: node for node in nodes}

    assert by_type["component"].confidence == "strong"
    assert by_type["component"].label == "left-pad@1.3.0"
    assert by_type["secret"].node_type == "secret"
    assert by_type["secret"].identity_key == "config/.env"
    assert by_type["secret"].confidence == "strong"
    assert by_type["resource"].identity_key == "infra/main.tf"
    assert by_type["resource"].confidence == "weak"


def test_rotation_surfaces_become_weak_secret_nodes():
    nodes = derive_asset_nodes(rotation_surfaces=[".env", "deploy/.npmrc"])
    assert {node.identity_key for node in nodes} == {".env", "deploy/.npmrc"}
    assert all(node.node_type == "secret" and node.confidence == "weak" for node in nodes)


def test_confirmed_secret_beats_rotation_surface_on_same_file():
    """A scanner-found secret (strong) and a rotation surface (weak) on the same
    file collapse to one node carrying the stronger confidence."""
    findings = [
        Finding(repo="repo", scanner="trufflehog", severity="high", category="secrets",
                title="token", file=".env", line=1),
    ]
    nodes = derive_asset_nodes(findings=findings, rotation_surfaces=[".env"])
    secrets = [node for node in nodes if node.node_type == "secret"]
    assert len(secrets) == 1
    assert secrets[0].confidence == "strong"


def test_every_node_confidence_is_in_the_honesty_vocabulary():
    components = [_component("a", "1.0").to_dict()]
    findings = [
        Finding(repo="repo", scanner="gitleaks", severity="high", category="secrets",
                title="k", file=".env"),
        Finding(repo="repo", scanner="checkov", severity="low", category="iac",
                title="r", file="main.tf"),
    ]
    nodes = derive_asset_nodes(components=components, findings=findings,
                               rotation_surfaces=["other.env"])
    assert nodes
    assert all(node.confidence in CONFIDENCE_LEVELS for node in nodes)


def test_no_sbom_and_no_iac_yields_smaller_set_not_a_crash():
    # Only a secret finding — no components, no IaC. Valid, smaller node set.
    findings = [
        Finding(repo="repo", scanner="gitleaks", severity="high", category="secrets",
                title="k", file=".env"),
    ]
    nodes = derive_asset_nodes(findings=findings)
    assert [node.node_type for node in nodes] == ["secret"]

    # Truly empty inputs are also fine — an empty graph, not an exception.
    assert derive_asset_nodes() == []


def test_secret_finding_without_file_is_skipped():
    findings = [
        Finding(repo="repo", scanner="gitleaks", severity="high", category="secrets",
                title="floating secret", file=None),
    ]
    assert derive_asset_nodes(findings=findings) == []


# ---------------------------------------------------------------------------
# Identity stability — the property the whole graph rests on
# ---------------------------------------------------------------------------


def test_same_component_version_has_stable_identity():
    one = derive_asset_nodes(components=[_component("left-pad", "1.3.0").to_dict()])
    two = derive_asset_nodes(components=[_component("left-pad", "1.3.0").to_dict()])
    assert one[0].identity_key == two[0].identity_key


def test_version_change_yields_distinct_identity():
    old = derive_asset_nodes(components=[_component("left-pad", "1.3.0").to_dict()])
    new = derive_asset_nodes(components=[_component("left-pad", "1.4.0").to_dict()])
    assert old[0].identity_key != new[0].identity_key


def test_component_identity_is_the_sbom_fingerprint():
    component = _component("left-pad", "1.3.0")
    node = derive_asset_nodes(components=[component.to_dict()])[0]
    assert node.identity_key == component.component_fingerprint


# ---------------------------------------------------------------------------
# Persistence through save_scan
# ---------------------------------------------------------------------------


def test_save_scan_persists_nodes_tied_to_scan_and_repo(tmp_path):
    db = ObservatoryDB(tmp_path / "persist.sqlite")
    try:
        _save_scan(
            db,
            scan_id="scan-1",
            repo="acme",
            findings=[
                Finding(repo="acme", scanner="gitleaks", severity="high",
                        category="secrets", title="k", file=".env", line=2),
            ],
            sbom_components=[_component("left-pad", "1.3.0")],
        )
        nodes = db.list_asset_nodes(scan_id="scan-1")
        assert {node["node_type"] for node in nodes} == {"secret", "component"}
        assert all(node["scan_id"] == "scan-1" and node["repo_name"] == "acme" for node in nodes)
    finally:
        db.close()


def test_resaving_a_scan_replaces_its_nodes(tmp_path):
    db = ObservatoryDB(tmp_path / "replace.sqlite")
    try:
        _save_scan(db, scan_id="s", sbom_components=[_component("a", "1.0")])
        assert len(db.list_asset_nodes(scan_id="s")) == 1
        # Re-run the same scan id with different inputs: nodes are replaced, not stacked.
        _save_scan(db, scan_id="s", sbom_components=[_component("a", "1.0"), _component("b", "2.0")])
        assert len(db.list_asset_nodes(scan_id="s")) == 2
    finally:
        db.close()


def test_scan_with_no_sbom_or_iac_persists_without_crashing(tmp_path):
    db = ObservatoryDB(tmp_path / "minimal.sqlite")
    try:
        _save_scan(db, scan_id="s", findings=[], sbom_components=[])
        assert db.list_asset_nodes(scan_id="s") == []
    finally:
        db.close()


def test_node_type_check_constraint_is_enforced(tmp_path):
    db = ObservatoryDB(tmp_path / "check.sqlite")
    try:
        _save_scan(db, scan_id="s")  # create the scan row for the FK
        with pytest.raises(sqlite3.IntegrityError):
            db.conn.execute(
                "insert into asset_nodes (scan_id, repo_name, node_type, identity_key, label, confidence, created_at)"
                " values ('s', 'repo', 'not_a_type', 'k', 'k', 'strong', '2026-01-01T00:00:00+00:00')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            db.conn.execute(
                "insert into asset_nodes (scan_id, repo_name, node_type, identity_key, label, confidence, created_at)"
                " values ('s', 'repo', 'secret', 'k', 'k', 'definitely', '2026-01-01T00:00:00+00:00')"
            )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# The edge seam for steps 1.2 / 1.3
# ---------------------------------------------------------------------------


def test_replace_asset_edges_resolves_endpoints_by_identity(tmp_path):
    db = ObservatoryDB(tmp_path / "edges.sqlite")
    try:
        _save_scan(
            db,
            scan_id="s",
            sbom_components=[_component("app", "1.0"), _component("left-pad", "1.3.0")],
        )
        nodes = {node["label"]: node for node in db.list_asset_nodes(scan_id="s")}
        app_key = nodes["app@1.0"]["identity_key"]
        leftpad_key = nodes["left-pad@1.3.0"]["identity_key"]

        written = db.replace_asset_edges(
            scan_id="s",
            repo_name="repo",
            edges=[
                AssetEdge(
                    src_identity_key=app_key,
                    dst_identity_key=leftpad_key,
                    edge_type="depends_on",
                    confidence="strong",
                    reason="app declares left-pad as a direct dependency",
                ),
            ],
        )
        assert written == 1
        edges = db.list_asset_edges(scan_id="s")
        assert len(edges) == 1
        assert edges[0]["src_node_id"] == nodes["app@1.0"]["id"]
        assert edges[0]["dst_node_id"] == nodes["left-pad@1.3.0"]["id"]
        assert edges[0]["edge_type"] == "depends_on"
    finally:
        db.close()


def test_replace_asset_edges_skips_edges_with_unknown_endpoints(tmp_path):
    db = ObservatoryDB(tmp_path / "skip.sqlite")
    try:
        _save_scan(db, scan_id="s", sbom_components=[_component("app", "1.0")])
        nodes = db.list_asset_nodes(scan_id="s")
        app_key = nodes[0]["identity_key"]
        written = db.replace_asset_edges(
            scan_id="s",
            repo_name="repo",
            edges=[
                AssetEdge(src_identity_key=app_key, dst_identity_key="ghost-node",
                          edge_type="depends_on", confidence="weak", reason="dangling"),
            ],
        )
        assert written == 0
        assert db.list_asset_edges(scan_id="s") == []
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Drift guards: the schema CHECK enums stay bound to the Python vocabularies
# ---------------------------------------------------------------------------


def _values_in_check(check_sql: str) -> set[str]:
    return set(re.findall(r"'([^']+)'", check_sql))


def test_node_type_check_is_derived_from_node_types():
    assert _values_in_check(ASSET_NODE_TYPE_CHECK) == set(NODE_TYPES)


def test_edge_type_check_is_derived_from_edge_types():
    assert _values_in_check(ASSET_EDGE_TYPE_CHECK) == set(EDGE_TYPES)


def test_confidence_check_is_derived_from_confidence_levels():
    assert _values_in_check(ASSET_CONFIDENCE_CHECK) == set(CONFIDENCE_LEVELS)


def test_dataclasses_reject_unknown_vocabulary():
    with pytest.raises(ValueError):
        AssetNode(node_type="bogus", identity_key="k", label="k", confidence="strong")
    with pytest.raises(ValueError):
        AssetNode(node_type="secret", identity_key="k", label="k", confidence="certain")
    with pytest.raises(ValueError):
        AssetEdge(src_identity_key="a", dst_identity_key="b",
                  edge_type="teleports", confidence="strong", reason="x")
