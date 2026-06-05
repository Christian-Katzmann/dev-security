from __future__ import annotations

from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from pathlib import Path
from urllib import request
import json
import threading

from security_observatory.consequence import suggest_placement_node
from security_observatory.dashboard_server import DashboardHandler
from security_observatory.honey_keys import generate_honey_key, hash_honey_key, honey_key_is_well_formed
from security_observatory.storage import ObservatoryDB


def _node(node_id, identity, label, *, node_type="component", confidence="strong", crown=False):
    return {
        "id": node_id,
        "node_type": node_type,
        "identity_key": identity,
        "label": label,
        "confidence": confidence,
        "is_crown_jewel": 1 if crown else 0,
    }


def _edge(edge_type, src_id, dst_id, confidence="strong"):
    return {"edge_type": edge_type, "src_node_id": src_id, "dst_node_id": dst_id, "confidence": confidence}


def test_honey_key_generation_creates_unique_fake_keys(tmp_path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        secret = db.honey_signing_secret()
        first = generate_honey_key(secret)
        second = generate_honey_key(secret)
    finally:
        db.close()

    assert first.token != second.token
    assert first.token.startswith("devsec_hny_")
    assert second.token.startswith("devsec_hny_")
    assert honey_key_is_well_formed(first.token, secret)
    assert not first.token.startswith(("AKIA", "ghp_", "github_pat_", "sk-"))


def test_raw_honey_key_is_not_stored_in_plaintext(tmp_path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        secret = db.honey_signing_secret()
        material = generate_honey_key(secret)
        db.create_honey_key(
            key_id=material.token_id,
            project_id="repo",
            repo_id="/tmp/repo",
            name="Legacy key",
            token_hash=material.token_hash,
            placement_path=".env.backup",
        )
        row = db.conn.execute("select * from honey_keys where id = ?", (material.token_id,)).fetchone()
    finally:
        db.close()

    assert row is not None
    assert row["token_hash"] == hash_honey_key(material.token)
    assert material.token not in " ".join(str(value) for value in dict(row).values())


def test_valid_honey_key_trigger_creates_event_and_red_status(tmp_path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        secret = db.honey_signing_secret()
        material = generate_honey_key(secret)
        key = db.create_honey_key(
            key_id=material.token_id,
            project_id="repo",
            repo_id="/tmp/repo",
            name="Legacy key",
            token_hash=material.token_hash,
            placement_path=".env.backup",
        )
        db.record_honey_key_trigger(
            honey_key={**key, "token_hash": material.token_hash},
            ip_address="127.0.0.1",
            user_agent="pytest",
            method="POST",
            path="/api/honey/trigger",
            headers={"User-Agent": "pytest"},
            body_summary='{"keys":["api_key"],"sensitive_keys_redacted":["api_key"]}',
            confidence=0.98,
            source_type="api_call",
        )
        payload = db.dashboard_payload()
    finally:
        db.close()

    assert payload["honey_key_events"][0]["honey_key_id"] == material.token_id
    assert payload["project_statuses"][0]["status"] == "red"
    assert payload["repos"][0]["status"] == "critical"
    assert payload["cases"][0]["title"] == "Honey Key triggered"
    assert payload["honey_key_events"][0]["incident"]["investigating"] is False


def test_archived_honey_key_trigger_does_not_create_critical_status(tmp_path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        secret = db.honey_signing_secret()
        material = generate_honey_key(secret)
        db.create_honey_key(
            key_id=material.token_id,
            project_id="repo",
            repo_id="/tmp/repo",
            name="Legacy key",
            token_hash=material.token_hash,
            placement_path=".env.backup",
        )
        key = db.archive_honey_key(material.token_id)
        assert key is not None
        db.record_honey_key_trigger(
            honey_key={**key, "token_hash": material.token_hash},
            ip_address="127.0.0.1",
            user_agent="pytest",
            method="POST",
            path="/api/honey/trigger",
            headers={"User-Agent": "pytest"},
            body_summary=None,
            confidence=0.35,
            source_type="api_call",
        )
        payload = db.dashboard_payload()
    finally:
        db.close()

    assert payload["honey_key_events"]
    assert payload["project_statuses"][0]["status"] == "green"
    assert payload["repos"] == []


def test_honey_key_incident_checklist_survives_and_controls_closure(tmp_path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        secret = db.honey_signing_secret()
        material = generate_honey_key(secret)
        key = db.create_honey_key(
            key_id=material.token_id,
            project_id="repo",
            repo_id="/tmp/repo",
            name="Legacy key",
            token_hash=material.token_hash,
            placement_path=".env.backup",
        )
        event = db.record_honey_key_trigger(
            honey_key={**key, "token_hash": material.token_hash},
            ip_address="127.0.0.1",
            user_agent="pytest",
            method="POST",
            path="/api/honey/trigger",
            headers={"User-Agent": "pytest"},
            body_summary=None,
            confidence=0.98,
            source_type="api_call",
        )

        incident = db.set_honey_incident_step(event["id"], "investigating", True)
        summary = db.dashboard_payload()
        try:
            db.close_honey_incident(event["id"])
        except ValueError as exc:
            close_error = str(exc)
        else:
            raise AssertionError("Closing without archive/reset or note should fail")

        db.archive_honey_key(material.token_id)
        closed = db.close_honey_incident(event["id"])
        closed_summary = db.dashboard_payload()
    finally:
        db.close()

    assert incident["investigating"] is True
    assert summary["honey_key_events"][0]["incident"]["investigating"] is True
    assert summary["cases"][0]["title"] == "Honey Key triggered"
    assert "Archive/reset" in close_error
    assert closed["archived_reset"] is True
    assert closed["closed_at"]
    assert closed_summary["cases"] == []
    assert closed_summary["repos"] == []
    assert closed_summary["project_statuses"][0]["status"] == "green"


def test_trigger_endpoint_is_generic_for_invalid_tokens_and_redacts_metadata(tmp_path):
    base_url, stop = _start_server(tmp_path)
    try:
        create_payload = _post_json(
            f"{base_url}/api/honey/keys",
            {
                "repoPath": "/tmp/repo",
                "repoName": "repo",
                "name": "Legacy key",
                "placementPath": ".env.backup",
            },
        )
        raw_token = create_payload["raw_token"]

        invalid = _post_json(f"{base_url}/api/honey/trigger", {"api_key": "devsec_hny_unknown_bad_sig"})
        valid = _post_json(f"{base_url}/api/honey/trigger", {"api_key": raw_token, "password": "should-not-be-stored"})
        summary = _get_json(f"{base_url}/api/summary")
    finally:
        stop()

    assert invalid == {"accepted": True}
    assert valid == {"accepted": True}
    assert len(summary["honey_key_events"]) == 1
    assert summary["honey_key_events"][0]["body_summary"]
    assert raw_token not in json.dumps(summary)
    assert "password" in summary["honey_key_events"][0]["body_summary"]
    assert summary["repos"][0]["status"] == "critical"


def test_insert_endpoint_writes_decoy_file_without_overwriting_or_leaving_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    base_url, stop = _start_server(tmp_path)
    try:
        create_payload = _post_json(
            f"{base_url}/api/honey/keys",
            {
                "repoPath": str(repo),
                "repoName": "repo",
                "name": "Legacy key",
                "placementPath": ".env.backup",
            },
        )
        snippet = create_payload["snippets"][".env.backup"]
        default_rejected = _post_json_expect_error(
            f"{base_url}/api/honey/insert",
            {
                "id": create_payload["key"]["id"],
                "repoPath": str(repo),
                "placementPath": ".env.backup",
                "snippet": snippet,
                "confirmPlacement": True,
            },
        )
        inserted = _post_json(
            f"{base_url}/api/honey/insert",
            {
                "id": create_payload["key"]["id"],
                "repoPath": str(repo),
                "placementPath": ".devsec/honeykeys/test.env",
                "snippet": snippet,
                "confirmPlacement": True,
            },
        )
        advanced = _post_json(
            f"{base_url}/api/honey/insert",
            {
                "id": create_payload["key"]["id"],
                "repoPath": str(repo),
                "placementPath": ".env.backup",
                "snippet": snippet,
                "confirmPlacement": True,
                "advancedPlacement": True,
            },
        )
        overwrite_status = _post_json_expect_error(
            f"{base_url}/api/honey/insert",
            {
                "id": create_payload["key"]["id"],
                "repoPath": str(repo),
                "placementPath": ".devsec/honeykeys/test.env",
                "snippet": snippet,
                "confirmPlacement": True,
            },
        )
        traversal_status = _post_json_expect_error(
            f"{base_url}/api/honey/insert",
            {
                "id": create_payload["key"]["id"],
                "repoPath": str(repo),
                "placementPath": "../outside.env",
                "snippet": snippet,
                "confirmPlacement": True,
            },
        )
    finally:
        stop()

    assert default_rejected == 400
    assert inserted["relative_path"] == ".devsec/honeykeys/test.env"
    assert advanced["relative_path"] == ".env.backup"
    assert (repo / ".devsec" / "honeykeys" / "test.env").read_text(encoding="utf-8") == snippet
    assert (repo / ".env.backup").read_text(encoding="utf-8") == snippet
    assert create_payload["raw_token"] in (repo / ".devsec" / "honeykeys" / "test.env").read_text(encoding="utf-8")
    assert overwrite_status == 409
    assert traversal_status == 400


def test_honey_key_binds_to_asset_node(tmp_path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        secret = db.honey_signing_secret()
        material = generate_honey_key(secret)
        key = db.create_honey_key(
            key_id=material.token_id,
            project_id="repo",
            repo_id="/tmp/repo",
            name="Legacy key",
            token_hash=material.token_hash,
            placement_path=".devsec/honeykeys/decoy.env",
            asset_node_id=42,
        )
        fetched = db.get_honey_key(material.token_id)
    finally:
        db.close()

    assert key["asset_node_id"] == 42
    assert fetched["asset_node_id"] == 42


def test_suggest_placement_picks_top_consequence_node(tmp_path):
    # left-pad is a vulnerable dependency the crown-jewel app pulls in. depends_on
    # points consumer -> provider, so the blast walks back from the app to the dep:
    # guarding the dep (id=1) is what catches an intruder before the crown jewel.
    nodes = [
        _node(1, "vuln-fp", "left-pad (vulnerable dep)"),
        _node(2, "app-fp", "web app", crown=True),
        _node(3, "util-fp", "big-util (no crown reach)"),
        _node(4, "c4", "consumer-a"),
        _node(5, "c5", "consumer-b"),
    ]
    edges = [
        _edge("depends_on", 2, 1),  # app depends_on left-pad => left-pad reaches app
        _edge("depends_on", 4, 3),  # give big-util a larger raw blast (2) but no crown
        _edge("depends_on", 5, 3),
    ]

    suggestion = suggest_placement_node(nodes, edges)

    assert suggestion is not None
    assert suggestion.node["asset_node_id"] == 1
    assert suggestion.ranked_by == "crown_jewel_reachability"
    assert suggestion.consequence.reaches_crown_jewel is True
    assert suggestion.auto_plant_safe is True
    # Human-readable: the proposal leads with a label, never a bare fingerprint.
    assert "left-pad" in suggestion.node["label"]


def test_suggest_placement_falls_back_to_blast_radius_without_crown_jewel():
    nodes = [
        _node(1, "vuln-fp", "left-pad (vulnerable dep)"),
        _node(2, "app-fp", "web app"),  # no crown jewel labeled anywhere
        _node(3, "util-fp", "big-util"),
        _node(4, "c4", "consumer-a"),
        _node(5, "c5", "consumer-b"),
    ]
    edges = [
        _edge("depends_on", 2, 1),  # left-pad reaches 1 node
        _edge("depends_on", 4, 3),  # big-util reaches 2 nodes => larger blast
        _edge("depends_on", 5, 3),
    ]

    suggestion = suggest_placement_node(nodes, edges)

    assert suggestion is not None
    assert suggestion.ranked_by == "blast_radius"
    assert suggestion.node["asset_node_id"] == 3  # the largest raw blast radius
    assert suggestion.crown_jewels_defined is False
    assert any("crown-jewels.json" in warning for warning in suggestion.warnings)


def test_weak_confidence_node_is_not_offered_for_auto_placement():
    nodes = [
        _node(1, "vuln-fp", "left-pad (vulnerable dep)", confidence="weak"),
        _node(2, "app-fp", "web app", crown=True),
    ]
    edges = [_edge("depends_on", 2, 1, confidence="weak")]

    suggestion = suggest_placement_node(nodes, edges)

    assert suggestion is not None
    assert suggestion.node["asset_node_id"] == 1
    assert suggestion.auto_plant_safe is False
    assert any("'weak'" in warning for warning in suggestion.warnings)


def test_suggest_placement_returns_none_on_empty_graph():
    assert suggest_placement_node([], []) is None


def _start_server(tmp_path: Path):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "index.html").write_text("<!doctype html><title>test</title>", encoding="utf-8")
    db_path = tmp_path / "observatory.sqlite"
    handler = type("TestDashboardHandler", (DashboardHandler,), {"db_path": db_path, "assets_dir": assets_dir})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def stop() -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    return f"http://127.0.0.1:{server.server_port}", stop


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "pytest"}, method="POST")
    with request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json_expect_error(url: str, payload: dict[str, object]) -> int:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "pytest"}, method="POST")
    try:
        request.urlopen(req, timeout=5)
    except HTTPError as exc:
        return exc.code
    raise AssertionError("Expected HTTP error")


def _get_json(url: str) -> dict[str, object]:
    with request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_doc_guard_map_citations_resolve():
    """docs/honey-keys.md binds each Honey Key safety claim to an exact source
    line. The doc exists to be auditable, so it must not carry the line drift it
    was built to eliminate: this test fails if any cited line stops containing
    its named guard, or if the doc stops citing those lines. Drift in either the
    code or the doc breaks the build, forcing them back into agreement."""
    repo_root = Path(__file__).resolve().parents[1]
    dashboard = (repo_root / "src/security_observatory/dashboard_server.py").read_text(encoding="utf-8").splitlines()
    honey = (repo_root / "src/security_observatory/honey_keys.py").read_text(encoding="utf-8").splitlines()

    # (source lines, 1-based cited line, substring that line MUST still contain)
    cited_guards = [
        (dashboard, 2843, "target_path.relative_to(repo_path)"),
        (dashboard, 2850, "if target_path.exists():"),
        (dashboard, 2851, "Placement file already exists."),
        (dashboard, 2752, "except sqlite3.IntegrityError:"),
        (dashboard, 2753, "Honey Key already exists."),
        (dashboard, 2866, "Honey Key belongs to a different repo."),
        (honey, 41, "token_hash"),
        (honey, 57, "token_hash=hash_honey_key"),
        (honey, 86, "hashlib.sha256"),
        (honey, 86, "honeykey:v1:"),
    ]
    for lines, lineno, needle in cited_guards:
        assert needle in lines[lineno - 1], (
            f"line {lineno} no longer contains {needle!r}; update the Guard Map "
            f"in docs/honey-keys.md and this test together"
        )

    # The Guard Map must actually cite each dashboard_server.py guard line.
    doc = (repo_root / "docs" / "honey-keys.md").read_text(encoding="utf-8")
    for lineno in (2843, 2850, 2851, 2752, 2753, 2866):
        assert f":{lineno}" in doc, (
            f"docs/honey-keys.md Guard Map no longer cites dashboard_server.py:{lineno}"
        )
