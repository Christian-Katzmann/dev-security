"""IaC resource-graph recovery from Checkov (step 1.3 of the Honeygraph campaign).

Dependency edges (step 1.2) connect component -> component; these resource edges
are the ones that let a *secret* reach a *datastore*, which is what makes
"blast radius to a crown jewel" mean anything. The tests pin the honest scope:

  - Checkov's per-check ``resource`` + ``code_block`` are parsed into real
    per-resource identities, data stores are classified, and cross-resource
    references are recovered from the HCL text;
  - a resource that references a data store becomes a ``stored_in`` edge, and a
    secret committed in an IaC file becomes a ``reachable_from`` edge — both
    ``weak`` (recovered from text, partial coverage);
  - the richer per-resource nodes replace the coarse file-level fallback, but a
    Checkov failure (no resources) still yields the coarse node from findings;
  - a repo with no IaC produces no resources and no edges — not a crash;
  - end to end, the edges persist and the secret -> resource -> datastore path is
    traversable in the stored graph.
"""

from __future__ import annotations

import json
from pathlib import Path

from security_observatory.asset_graph import derive_asset_nodes
from security_observatory.iac import (
    DATASTORE_RESOURCE_TYPES,
    IaCResource,
    derive_iac_resource_edges,
    is_datastore_resource_type,
    load_checkov_resources,
    parse_checkov_resources,
)
from security_observatory.model import Finding
from security_observatory.storage import ObservatoryDB


# A realistic Terraform Checkov result: an app server whose HCL references a
# private RDS database (a data store), plus the database's own resource. The
# reference ``aws_db_instance.prod.endpoint`` inside the app's code block is the
# relationship we recover.
def _checkov_fixture() -> dict:
    return {
        "check_type": "terraform",
        "results": {
            "failed_checks": [
                {
                    "check_id": "CKV_AWS_24",
                    "check_name": "Ensure no hard-coded secrets exist in EC2 user data",
                    "resource": "aws_instance.app",
                    "file_path": "/infra/main.tf",
                    "file_abs_path": "/repo/infra/main.tf",
                    "file_line_range": [1, 6],
                    "code_block": [
                        [1, 'resource "aws_instance" "app" {'],
                        [2, '  ami           = "ami-123"'],
                        [3, "  user_data     = <<EOF"],
                        [4, "    DB_HOST=${aws_db_instance.prod.endpoint}"],
                        [5, "  EOF"],
                        [6, "}"],
                    ],
                    "severity": None,
                    "guideline": "https://docs.example/CKV_AWS_24",
                },
                {
                    "check_id": "CKV_AWS_16",
                    "check_name": "Ensure all data stored in RDS is encrypted",
                    "resource": "aws_db_instance.prod",
                    "file_path": "/infra/main.tf",
                    "file_abs_path": "/repo/infra/main.tf",
                    "file_line_range": [8, 12],
                    "code_block": [
                        [8, 'resource "aws_db_instance" "prod" {'],
                        [9, '  identifier = "prod"'],
                        [10, "  password   = var.db_password"],
                        [11, "  encrypted  = false"],
                        [12, "}"],
                    ],
                    "severity": None,
                    "guideline": "https://docs.example/CKV_AWS_16",
                },
            ],
            "passed_checks": [],
        },
    }


# ---------------------------------------------------------------------------
# Datastore classification
# ---------------------------------------------------------------------------


def test_datastore_classification_covers_the_big_three_clouds():
    assert is_datastore_resource_type("aws_db_instance")
    assert is_datastore_resource_type("google_sql_database_instance")
    assert is_datastore_resource_type("azurerm_storage_account")
    # Compute / networking resources are not data stores.
    assert not is_datastore_resource_type("aws_instance")
    assert not is_datastore_resource_type("aws_security_group")
    assert not is_datastore_resource_type("")
    assert "aws_s3_bucket" in DATASTORE_RESOURCE_TYPES


# ---------------------------------------------------------------------------
# Parsing (pure)
# ---------------------------------------------------------------------------


def test_parses_resources_classifies_datastore_and_recovers_reference():
    resources = parse_checkov_resources(_checkov_fixture())
    by_address = {resource.address: resource for resource in resources}

    assert set(by_address) == {"aws_instance.app", "aws_db_instance.prod"}

    db = by_address["aws_db_instance.prod"]
    assert db.is_datastore is True
    assert db.node_type == "datastore"
    assert db.resource_type == "aws_db_instance"
    assert db.name == "prod"
    assert db.file_path == "/infra/main.tf"

    app = by_address["aws_instance.app"]
    assert app.is_datastore is False
    assert app.node_type == "resource"
    # The app's HCL references the database — recovered from the code block text.
    assert "aws_db_instance.prod" in app.references


def test_parses_top_level_list_shape_and_module_addresses():
    # Checkov emits a JSON list when several frameworks run; module resources
    # carry a ``module.<name>`` prefix on the address.
    data = [
        {
            "check_type": "terraform",
            "results": {
                "failed_checks": [
                    {
                        "resource": "module.data.aws_dynamodb_table.sessions",
                        "file_path": "/mod/main.tf",
                        "code_block": [[1, 'resource "aws_dynamodb_table" "sessions" {}']],
                    }
                ],
                "passed_checks": [],
            },
        }
    ]
    resources = parse_checkov_resources(data)
    assert len(resources) == 1
    resource = resources[0]
    assert resource.address == "module.data.aws_dynamodb_table.sessions"
    assert resource.resource_type == "aws_dynamodb_table"
    assert resource.is_datastore is True


def test_reference_in_passed_check_only_datastore_still_resolves():
    # The data store may only appear in passed_checks (nothing flagged it) while
    # the referencing resource failed. We must still know the data store exists.
    data = {
        "results": {
            "failed_checks": [
                {
                    "resource": "aws_instance.app",
                    "file_path": "/main.tf",
                    "code_block": [[1, "  bucket = aws_s3_bucket.assets.id"]],
                }
            ],
            "passed_checks": [
                {
                    "resource": "aws_s3_bucket.assets",
                    "file_path": "/main.tf",
                    "code_block": [[1, 'resource "aws_s3_bucket" "assets" {}']],
                }
            ],
        }
    }
    resources = parse_checkov_resources(data)
    edges = derive_iac_resource_edges(resources)
    assert any(
        edge.src_identity_key == "aws_instance.app"
        and edge.dst_identity_key == "aws_s3_bucket.assets"
        and edge.edge_type == "stored_in"
        for edge in edges
    )


def test_empty_or_garbage_checkov_yields_no_resources():
    assert parse_checkov_resources(None) == []
    assert parse_checkov_resources({}) == []
    assert parse_checkov_resources({"results": {}}) == []
    assert parse_checkov_resources("not json") == []


# ---------------------------------------------------------------------------
# Edge derivation
# ---------------------------------------------------------------------------


def test_resource_referencing_datastore_becomes_stored_in_edge():
    resources = parse_checkov_resources(_checkov_fixture())
    edges = derive_iac_resource_edges(resources)

    stored_in = [edge for edge in edges if edge.edge_type == "stored_in"]
    assert len(stored_in) == 1
    edge = stored_in[0]
    assert edge.src_identity_key == "aws_instance.app"
    assert edge.dst_identity_key == "aws_db_instance.prod"
    assert edge.confidence == "weak"  # recovered from text, never claimed strong
    assert "data store" in edge.reason


def test_secret_in_iac_file_becomes_reachable_from_edge():
    resources = parse_checkov_resources(_checkov_fixture())
    # gitleaks reports the file without a leading slash; normalization bridges it.
    edges = derive_iac_resource_edges(resources, secret_files=["infra/main.tf"])

    reachable = [edge for edge in edges if edge.edge_type == "reachable_from"]
    assert {edge.dst_identity_key for edge in reachable} == {
        "aws_instance.app",
        "aws_db_instance.prod",
    }
    for edge in reachable:
        assert edge.src_identity_key == "infra/main.tf"
        assert edge.confidence == "weak"


def test_no_references_yields_no_edges():
    resources = [
        IaCResource(
            address="aws_instance.app",
            resource_type="aws_instance",
            name="app",
            file_path="/main.tf",
            is_datastore=False,
            references=(),
        )
    ]
    assert derive_iac_resource_edges(resources) == []
    assert derive_iac_resource_edges(resources, secret_files=[]) == []


def test_reference_to_non_datastore_resource_is_not_a_stored_in_edge():
    # An app referencing a security group is a real reference but not a data
    # store, so it must not produce a stored_in edge (scope is data stores).
    data = {
        "results": {
            "failed_checks": [
                {
                    "resource": "aws_instance.app",
                    "file_path": "/main.tf",
                    "code_block": [[1, "  vpc_security_group_ids = [aws_security_group.web.id]"]],
                },
                {
                    "resource": "aws_security_group.web",
                    "file_path": "/main.tf",
                    "code_block": [[1, 'resource "aws_security_group" "web" {}']],
                },
            ],
            "passed_checks": [],
        }
    }
    resources = parse_checkov_resources(data)
    assert derive_iac_resource_edges(resources) == []


# ---------------------------------------------------------------------------
# Node derivation: rich resources replace coarse fallback
# ---------------------------------------------------------------------------


def test_iac_resources_become_per_resource_and_datastore_nodes():
    resources = parse_checkov_resources(_checkov_fixture())
    nodes = derive_asset_nodes(iac_resources=resources)
    by_identity = {node.identity_key: node for node in nodes}

    assert by_identity["aws_db_instance.prod"].node_type == "datastore"
    assert by_identity["aws_db_instance.prod"].confidence == "weak"
    assert by_identity["aws_instance.app"].node_type == "resource"


def test_rich_resources_suppress_coarse_file_level_node():
    resources = parse_checkov_resources(_checkov_fixture())
    findings = [
        Finding(repo="repo", scanner="checkov", severity="medium", category="iac",
                title="RDS not encrypted", file="/infra/main.tf", line=11),
    ]
    nodes = derive_asset_nodes(findings=findings, iac_resources=resources)
    resource_nodes = {node.identity_key for node in nodes if node.node_type in ("resource", "datastore")}

    # The per-resource addresses are present; the coarse file path is NOT, because
    # the file is covered by the richer resources.
    assert "aws_instance.app" in resource_nodes
    assert "aws_db_instance.prod" in resource_nodes
    assert "/infra/main.tf" not in resource_nodes


def test_checkov_failure_falls_back_to_coarse_file_node():
    # No recovered resources (e.g. a Checkov timeout that still produced a
    # finding): node derivation must still mint the coarse file-level resource.
    findings = [
        Finding(repo="repo", scanner="checkov", severity="medium", category="iac",
                title="RDS not encrypted", file="infra/main.tf", line=11),
    ]
    nodes = derive_asset_nodes(findings=findings, iac_resources=[])
    resource_nodes = {node.identity_key for node in nodes if node.node_type == "resource"}
    assert resource_nodes == {"infra/main.tf"}


def test_no_iac_yields_no_resource_nodes_and_no_crash():
    nodes = derive_asset_nodes(
        findings=[
            Finding(repo="repo", scanner="gitleaks", severity="high", category="secrets",
                    title="key", file=".env", line=1),
        ],
        iac_resources=[],
    )
    assert all(node.node_type not in ("resource", "datastore") for node in nodes)


# ---------------------------------------------------------------------------
# load_checkov_resources (file IO + partial-scan resilience)
# ---------------------------------------------------------------------------


def test_load_checkov_resources_reads_scan_dir(tmp_path: Path):
    (tmp_path / "checkov.json").write_text(json.dumps(_checkov_fixture()), encoding="utf-8")
    resources = load_checkov_resources(tmp_path)
    assert {resource.address for resource in resources} == {
        "aws_instance.app",
        "aws_db_instance.prod",
    }


def test_load_checkov_resources_missing_file_is_empty(tmp_path: Path):
    # A Checkov failure / no-IaC repo leaves no checkov.json — partial scan, not a crash.
    assert load_checkov_resources(tmp_path) == []


# ---------------------------------------------------------------------------
# End to end: nodes + edges persisted, secret -> resource -> datastore traversable
# ---------------------------------------------------------------------------


def test_secret_reaches_datastore_through_persisted_graph(tmp_path: Path):
    db = ObservatoryDB(tmp_path / "scan.sqlite")
    try:
        resources = parse_checkov_resources(_checkov_fixture())
        findings = [
            Finding(repo="repo", scanner="gitleaks", severity="critical", category="secrets",
                    title="hard-coded DB password", file="infra/main.tf", line=10),
        ]
        db.save_scan(
            scan_id="s1",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="quick",
            health_score=70,
            status="ok",
            scanner_statuses=[],
            findings=findings,
            report_path="/tmp/repo/report.json",
            iac_resources=resources,
        )
        secret_files = ["infra/main.tf"]
        edges = derive_iac_resource_edges(resources, secret_files=secret_files)
        written = db.replace_asset_edges(scan_id="s1", repo_name="repo", edges=edges)
        assert written >= 2  # secret->app, secret->db, app->db (>=2 resolve)

        nodes = {node["identity_key"]: node for node in db.list_asset_nodes(scan_id="s1")}
        assert nodes["infra/main.tf"]["node_type"] == "secret"
        assert nodes["aws_db_instance.prod"]["node_type"] == "datastore"

        stored = db.list_asset_edges(scan_id="s1")

        # Reconstruct the adjacency by identity and confirm the secret reaches the
        # datastore (secret -> resource -> datastore, or secret -> datastore).
        id_by_identity = {node["identity_key"]: node["id"] for node in db.list_asset_nodes(scan_id="s1")}
        identity_by_id = {node_id: identity for identity, node_id in id_by_identity.items()}
        adjacency: dict[str, set[str]] = {}
        for edge in stored:
            src = identity_by_id[edge["src_node_id"]]
            dst = identity_by_id[edge["dst_node_id"]]
            adjacency.setdefault(src, set()).add(dst)

        # BFS from the secret node.
        reachable: set[str] = set()
        frontier = ["infra/main.tf"]
        while frontier:
            current = frontier.pop()
            for nxt in adjacency.get(current, set()):
                if nxt not in reachable:
                    reachable.add(nxt)
                    frontier.append(nxt)
        assert "aws_db_instance.prod" in reachable
    finally:
        db.close()
