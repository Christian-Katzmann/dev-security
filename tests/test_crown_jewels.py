"""Human-labeled crown jewels (Honeygraph step 2.1).

Crown jewels are declared, never inferred: an absent or malformed file yields no
labels (graceful, unattended-safe), labels match nodes by identity, and marking
is pure (returns new frozen nodes, never mutates inputs).
"""

import json

from security_observatory.asset_graph import AssetNode
from security_observatory.crown_jewels import (
    CrownJewelLabel,
    load_crown_jewel_labels,
    mark_crown_jewels,
    parse_crown_jewel_labels,
)


def _node(node_type, identity_key, crown=False):
    return AssetNode(
        node_type=node_type,
        identity_key=identity_key,
        label=identity_key,
        confidence="weak",
        is_crown_jewel=crown,
    )


def test_absent_file_yields_no_labels(tmp_path):
    assert load_crown_jewel_labels(tmp_path) == []


def test_empty_file_yields_no_labels(tmp_path):
    (tmp_path / ".devsec").mkdir()
    (tmp_path / ".devsec" / "crown-jewels.json").write_text("", encoding="utf-8")
    assert load_crown_jewel_labels(tmp_path) == []


def test_malformed_json_is_graceful(tmp_path):
    (tmp_path / ".devsec").mkdir()
    (tmp_path / ".devsec" / "crown-jewels.json").write_text("{ not json", encoding="utf-8")
    assert load_crown_jewel_labels(tmp_path) == []


def test_load_object_and_string_entries(tmp_path):
    (tmp_path / ".devsec").mkdir()
    payload = {
        "_comment": "ignored",
        "crown_jewels": [
            {"identity_key": "aws_db_instance.customers", "node_type": "datastore"},
            "config/prod-secrets.env",
            {"note": "no identity"},  # dropped
        ],
    }
    (tmp_path / ".devsec" / "crown-jewels.json").write_text(json.dumps(payload), encoding="utf-8")
    labels = load_crown_jewel_labels(tmp_path)
    assert CrownJewelLabel("aws_db_instance.customers", "datastore") in labels
    assert CrownJewelLabel("config/prod-secrets.env", None) in labels
    assert len(labels) == 2


def test_top_level_list_is_accepted():
    labels = parse_crown_jewel_labels(["a", {"identity_key": "b"}])
    assert labels == [CrownJewelLabel("a", None), CrownJewelLabel("b", None)]


def test_unknown_node_type_is_dropped_not_the_label():
    # A typo'd node_type would match nothing; keep the label, drop the bad type.
    labels = parse_crown_jewel_labels([{"identity_key": "x", "node_type": "databse"}])
    assert labels == [CrownJewelLabel("x", None)]


def test_duplicate_entries_deduped():
    labels = parse_crown_jewel_labels(["a", "a", {"identity_key": "a"}])
    assert labels == [CrownJewelLabel("a", None)]


def test_mark_matches_by_identity_and_type():
    nodes = [
        _node("datastore", "aws_db_instance.customers"),
        _node("resource", "aws_db_instance.customers"),  # same key, wrong type
        _node("secret", "config/prod-secrets.env"),
    ]
    labels = [
        CrownJewelLabel("aws_db_instance.customers", "datastore"),
        CrownJewelLabel("config/prod-secrets.env", None),
    ]
    marked = {(n.node_type, n.identity_key): n.is_crown_jewel for n in mark_crown_jewels(nodes, labels)}
    assert marked[("datastore", "aws_db_instance.customers")] is True
    assert marked[("resource", "aws_db_instance.customers")] is False  # type didn't match
    assert marked[("secret", "config/prod-secrets.env")] is True


def test_mark_is_pure_no_mutation():
    node = _node("datastore", "d")
    mark_crown_jewels([node], [CrownJewelLabel("d", None)])
    assert node.is_crown_jewel is False  # input untouched


def test_mark_with_no_labels_keeps_nodes_unmarked():
    nodes = [_node("secret", "a"), _node("component", "b")]
    marked = mark_crown_jewels(nodes, [])
    assert all(not n.is_crown_jewel for n in marked)


def test_committed_repo_crown_jewels_file_is_valid():
    # The repo's own .devsec/crown-jewels.json must always parse (it ships empty).
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    labels = load_crown_jewel_labels(repo_root)
    assert isinstance(labels, list)
