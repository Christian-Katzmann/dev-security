"""Reachable-consequence scoring (Honeygraph step 2.1).

The honesty contract Phase 2 rests on:

  - a finding reaches a crown jewel through a *strong* path -> strong consequence;
  - the same reach through *one weak edge* -> weak consequence (weakest-link rule);
  - no crown jewels labeled -> "unknown", not "zero" and not a crash;
  - a node that reaches no crown jewel -> a definite "reaches nothing".

Plus the two orientation facts the graph encodes: ``reachable_from`` / ``stored_in``
follow forward (secret -> resource -> datastore), and ``depends_on`` is walked
*backward* (a compromised provider reaches the things that depend on it).
"""

from security_observatory.asset_graph import AssetEdge, AssetNode
from security_observatory.consequence import (
    ACTIVE_INCIDENT_MESSAGE,
    attach_consequences,
    build_graph_payload,
    case_node_identities,
    compute_node_consequences,
)
from security_observatory.model import SecurityCase


def _node(node_type, identity_key, confidence="strong", crown=False):
    return AssetNode(
        node_type=node_type,
        identity_key=identity_key,
        label=identity_key,
        confidence=confidence,
        is_crown_jewel=crown,
    )


def _edge(src, dst, edge_type, confidence="strong"):
    return AssetEdge(
        src_identity_key=src,
        dst_identity_key=dst,
        edge_type=edge_type,
        confidence=confidence,
        reason=f"{src} -> {dst}",
    )


# ---------------------------------------------------------------------------
# The four acceptance scenarios
# ---------------------------------------------------------------------------


def test_strong_path_reaches_crown_jewel():
    nodes = [
        _node("secret", "app/.env", "strong"),
        _node("resource", "aws_instance.api", "strong"),
        _node("datastore", "aws_db_instance.customers", "strong", crown=True),
    ]
    edges = [
        _edge("app/.env", "aws_instance.api", "reachable_from", "strong"),
        _edge("aws_instance.api", "aws_db_instance.customers", "stored_in", "strong"),
    ]
    result = compute_node_consequences(nodes, edges)
    secret = result[("secret", "app/.env")]
    assert secret.reaches_crown_jewel is True
    assert secret.distance == 2
    assert secret.confidence == "strong"
    assert secret.blast_radius == 2  # resource + datastore
    assert secret.crown_jewel["identity_key"] == "aws_db_instance.customers"
    # Path runs from the finding node to the crown jewel.
    assert [step["identity_key"] for step in secret.path] == [
        "app/.env",
        "aws_instance.api",
        "aws_db_instance.customers",
    ]
    # Each non-start step records the edge taken to arrive (for "a → unlocks → b").
    assert "via" not in secret.path[0]
    assert secret.path[1]["via"] == "reachable_from"
    assert secret.path[2]["via"] == "stored_in"


def test_one_weak_edge_makes_consequence_weak():
    nodes = [
        _node("secret", "app/.env", "strong"),
        _node("resource", "aws_instance.api", "strong"),
        _node("datastore", "aws_db_instance.customers", "strong", crown=True),
    ]
    edges = [
        # A single weak hop on an otherwise strong path.
        _edge("app/.env", "aws_instance.api", "reachable_from", "weak"),
        _edge("aws_instance.api", "aws_db_instance.customers", "stored_in", "strong"),
    ]
    result = compute_node_consequences(nodes, edges)
    secret = result[("secret", "app/.env")]
    assert secret.reaches_crown_jewel is True
    assert secret.confidence == "weak"  # weakest link wins


def test_no_crown_jewels_is_unknown_not_zero():
    nodes = [
        _node("secret", "app/.env", "strong"),
        _node("resource", "aws_instance.api", "strong"),
    ]
    edges = [_edge("app/.env", "aws_instance.api", "reachable_from", "strong")]
    result = compute_node_consequences(nodes, edges)
    secret = result[("secret", "app/.env")]
    assert secret.reaches_crown_jewel is False
    assert secret.crown_jewels_defined is False
    assert secret.confidence == "unknown"
    assert secret.distance is None
    # Blast radius is still honest data even with nothing labeled.
    assert secret.blast_radius == 1


def test_node_unreachable_to_any_crown_jewel():
    nodes = [
        _node("secret", "app/.env", "strong"),
        _node("datastore", "aws_db_instance.customers", "strong", crown=True),
    ]
    edges = []  # no path between them
    result = compute_node_consequences(nodes, edges)
    secret = result[("secret", "app/.env")]
    assert secret.reaches_crown_jewel is False
    assert secret.crown_jewels_defined is True  # a crown jewel exists, just not reachable
    assert secret.distance is None
    assert secret.blast_radius == 0


# ---------------------------------------------------------------------------
# Edge orientation
# ---------------------------------------------------------------------------


def test_depends_on_is_walked_backward():
    # app depends_on a vulnerable library. Compromising the library reaches the
    # app, so blast propagates provider -> consumer (the reverse of depends_on).
    nodes = [
        _node("component", "fp-app", "strong", crown=True),
        _node("component", "fp-vuln-lib", "strong"),
    ]
    edges = [_edge("fp-app", "fp-vuln-lib", "depends_on", "strong")]
    result = compute_node_consequences(nodes, edges)
    lib = result[("component", "fp-vuln-lib")]
    assert lib.reaches_crown_jewel is True
    assert lib.distance == 1
    # And the app itself does not "reach" the lib it depends on.
    app = result[("component", "fp-app")]
    assert app.reaches_crown_jewel is False
    assert app.blast_radius == 0


def test_equal_distance_prefers_stronger_weakest_link():
    # Two 2-hop paths to the crown jewel: one all-strong, one with a weak hop.
    nodes = [
        _node("secret", "s", "strong"),
        _node("resource", "via_strong", "strong"),
        _node("resource", "via_weak", "strong"),
        _node("datastore", "crown", "strong", crown=True),
    ]
    edges = [
        _edge("s", "via_strong", "reachable_from", "strong"),
        _edge("via_strong", "crown", "stored_in", "strong"),
        _edge("s", "via_weak", "reachable_from", "weak"),
        _edge("via_weak", "crown", "stored_in", "strong"),
    ]
    result = compute_node_consequences(nodes, edges)
    secret = result[("secret", "s")]
    assert secret.distance == 2
    assert secret.confidence == "strong"
    assert [step["identity_key"] for step in secret.path] == ["s", "via_strong", "crown"]


# ---------------------------------------------------------------------------
# Case <-> node mapping + attachment
# ---------------------------------------------------------------------------


def _case(**overrides):
    base = dict(
        case_id="case-1",
        title="t",
        plain_english_risk="r",
        action_level="verify",
        confidence="medium",
        category="secrets",
        severity="high",
        affected_files=[],
        evidence=[],
        scanners=["gitleaks"],
        fix_steps=[],
        agent_prompt="p",
        source_fingerprints=["fp1"],
    )
    base.update(overrides)
    return SecurityCase(**base)


def test_case_node_identities_cover_components_and_files():
    case = _case(
        affected_files=["app/.env"],
        evidence=[{"component_fingerprint": "fp-lib"}],
    )
    keys = case_node_identities(case)
    assert ("component", "fp-lib") in keys
    assert ("secret", "app/.env") in keys
    assert ("resource", "app/.env") in keys


def test_attach_consequences_sets_secret_case():
    case = _case(category="secrets", affected_files=["app/.env"])
    nodes = [
        _node("secret", "app/.env", "strong"),
        _node("datastore", "aws_db_instance.customers", "strong", crown=True),
    ]
    edges = [_edge("app/.env", "aws_db_instance.customers", "reachable_from", "strong")]
    attach_consequences([case], nodes, edges)
    assert case.consequence is not None
    assert case.consequence["reaches_crown_jewel"] is True
    assert case.consequence["distance"] == 1


def test_attach_consequences_leaves_unmapped_case_untouched():
    # A case whose node isn't in the graph must rank exactly as before -> None.
    case = _case(category="iac", affected_files=["infra/unknown.tf"])
    nodes = [_node("secret", "app/.env", "strong", crown=True)]
    attach_consequences([case], nodes, [])
    assert case.consequence is None


def test_attach_consequences_no_graph_is_noop():
    case = _case(affected_files=["app/.env"])
    attach_consequences([case], [], [])
    assert case.consequence is None


# ---------------------------------------------------------------------------
# Storage round-trip: consequence over the persisted (numeric-id) edge shape
# ---------------------------------------------------------------------------


def test_consequence_from_persisted_graph(tmp_path):
    from security_observatory.iac import IaCResource, derive_iac_resource_edges
    from security_observatory.crown_jewels import CrownJewelLabel
    from security_observatory.model import Finding
    from security_observatory.storage import ObservatoryDB

    secret = Finding(
        repo="repo",
        scanner="gitleaks",
        severity="high",
        category="secrets",
        title="AWS key",
        file="infra/main.tf",
        line=3,
    )
    resources = [
        IaCResource(
            address="aws_instance.api",
            resource_type="aws_instance",
            name="api",
            file_path="infra/main.tf",
            is_datastore=False,
            references=("aws_db_instance.customers",),
        ),
        IaCResource(
            address="aws_db_instance.customers",
            resource_type="aws_db_instance",
            name="customers",
            file_path="infra/main.tf",
            is_datastore=True,
        ),
    ]
    edges = derive_iac_resource_edges(resources, secret_files=["infra/main.tf"])

    db = ObservatoryDB(tmp_path / "scan.sqlite")
    try:
        db.save_scan(
            scan_id="s1",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="quick",
            health_score=80,
            status="ok",
            scanner_statuses=[],
            findings=[secret],
            report_path="/tmp/repo/report.json",
            iac_resources=resources,
            crown_jewels=[CrownJewelLabel("aws_db_instance.customers", "datastore")],
        )
        db.replace_asset_edges(scan_id="s1", repo_name="repo", edges=edges)

        node_rows = db.list_asset_nodes(scan_id="s1", repo_name="repo")
        edge_rows = db.list_asset_edges(scan_id="s1", repo_name="repo")
        # The datastore node persisted as a crown jewel.
        crowns = [r for r in node_rows if r["is_crown_jewel"]]
        assert [r["identity_key"] for r in crowns] == ["aws_db_instance.customers"]

        result = compute_node_consequences(node_rows, edge_rows)
        secret_conseq = result[("secret", "infra/main.tf")]
        assert secret_conseq.reaches_crown_jewel is True
        assert secret_conseq.confidence == "weak"  # IaC edges are weak
        assert secret_conseq.crown_jewel["identity_key"] == "aws_db_instance.customers"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Graph view payload (Honeygraph 2 — the blast-radius graph view)
# ---------------------------------------------------------------------------


def _graph_fixture():
    """A 3-node chain ending in a crown jewel: secret -> resource -> datastore."""
    nodes = [
        _node("secret", "app/.env", "strong"),
        _node("resource", "aws_instance.api", "strong"),
        _node("datastore", "aws_db_instance.customers", "strong", crown=True),
    ]
    edges = [
        _edge("app/.env", "aws_instance.api", "reachable_from", "strong"),
        _edge("aws_instance.api", "aws_db_instance.customers", "stored_in", "strong"),
    ]
    return nodes, edges


def test_build_graph_payload_scores_nodes_and_keeps_edges():
    nodes, edges = _graph_fixture()
    payload = build_graph_payload(nodes, edges)

    assert payload["crown_jewels_defined"] is True
    assert len(payload["nodes"]) == 3
    assert len(payload["edges"]) == 2

    secret = next(n for n in payload["nodes"] if n["identity_key"] == "app/.env")
    # The entry node reaches the crown jewel two hops away, touching two assets.
    assert secret["reaches_crown_jewel"] is True
    assert secret["blast_radius"] == 2
    assert secret["distance_to_crown_jewel"] == 2
    assert secret["consequence_confidence"] == "strong"

    jewel = next(n for n in payload["nodes"] if n["node_type"] == "datastore")
    assert jewel["is_crown_jewel"] is True

    # Edges carry identity-key endpoints the front end + incident path join on.
    first = payload["edges"][0]
    assert first["src_identity_key"] == "app/.env"
    assert first["dst_identity_key"] == "aws_instance.api"
    assert first["edge_type"] == "reachable_from"


def test_build_graph_payload_no_crown_jewel_is_honest():
    nodes = [_node("component", "pkg:a", "strong"), _node("component", "pkg:b", "strong")]
    edges = [_edge("pkg:a", "pkg:b", "depends_on", "strong")]
    payload = build_graph_payload(nodes, edges)
    assert payload["crown_jewels_defined"] is False
    assert all(n["reaches_crown_jewel"] is False for n in payload["nodes"])
    assert payload["active_incident"] is None


def test_build_graph_payload_scopes_incident_to_this_graph():
    nodes, edges = _graph_fixture()
    in_graph = {
        "event_id": "evt-1",
        "honey_key_id": "key-1",
        "triggered_at": "2026-06-06T00:00:00Z",
        "node_type": "secret",
        "identity_key": "app/.env",
        "node": {"node_type": "secret", "identity_key": "app/.env", "label": "app/.env"},
        "path": [],
        "edges": [],
        "blast_radius": 2,
        "reaches_crown_jewel": True,
    }
    out_of_graph = {
        "event_id": "evt-2",
        "node_type": "secret",
        "identity_key": "other-repo/.env",
        "node": {"identity_key": "other-repo/.env"},
    }
    payload = build_graph_payload(nodes, edges, [in_graph, out_of_graph])

    # Only the trip whose node is in THIS graph lights a path.
    assert len(payload["active_incidents"]) == 1
    incident = payload["active_incident"]
    assert incident["identity_key"] == "app/.env"
    # The honest-language constant rides along so the view can never drift from it.
    assert incident["message"] == ACTIVE_INCIDENT_MESSAGE


def test_build_graph_payload_empty_graph_is_empty_not_error():
    payload = build_graph_payload([], [])
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert payload["active_incident"] is None
    assert payload["crown_jewels_defined"] is False
