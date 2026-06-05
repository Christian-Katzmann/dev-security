from __future__ import annotations

from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from pathlib import Path
from urllib import request
import json
import threading

import pytest

from security_observatory.asset_graph import AssetEdge
from security_observatory.consequence import (
    apply_active_incidents,
    blast_radius_from,
    suggest_placement_node,
)
from security_observatory.dashboard_server import DashboardHandler
from security_observatory.honey_keys import (
    build_decoy_snippets,
    generate_honey_key,
    hash_honey_key,
    honey_key_is_well_formed,
    validate_collector_base_url,
)
from security_observatory.model import SecurityCase
from security_observatory.sbom import SBOMComponent
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


def test_local_decoy_callback_stays_on_loopback_base():
    secret = "signing-secret"
    material = generate_honey_key(secret)
    snippets = build_decoy_snippets(
        base_url="http://127.0.0.1:8876",
        name="Local decoy",
        token=material.token,
        token_id=material.token_id,
        signing_secret=secret,
    )
    # Default (local) placement keeps the callback on loopback — a trip means
    # "something local touched it", never a remote attacker.
    for snippet in snippets.values():
        assert "http://127.0.0.1:8876/api/honey/trigger" in snippet
        assert "collector.example.com" not in snippet


def test_deployed_decoy_callback_points_at_operator_collector():
    secret = "signing-secret"
    material = generate_honey_key(secret)
    snippets = build_decoy_snippets(
        base_url="http://127.0.0.1:8876",
        name="Deployed decoy",
        token=material.token,
        token_id=material.token_id,
        signing_secret=secret,
        trigger_base_url="https://collector.example.com",
    )
    # Deployed placement bakes the operator's reachable collector into the
    # callback instead of loopback — the only way a remote trip can reach DëvSec.
    for snippet in snippets.values():
        assert "https://collector.example.com/api/honey/trigger" in snippet
        assert "https://collector.example.com/api/honey/open/" in snippet
        assert "127.0.0.1" not in snippet


def test_validate_collector_base_url_accepts_https_and_strips_slash():
    assert validate_collector_base_url("https://collector.example.com/") == "https://collector.example.com"
    assert validate_collector_base_url("  http://canary.internal:9000  ") == "http://canary.internal:9000"


def test_validate_collector_base_url_rejects_junk():
    for bad in ("", "collector.example.com", "ftp://x", "javascript:alert(1)", "not a url"):
        with pytest.raises(ValueError):
            validate_collector_base_url(bad)


def test_create_honey_key_deployed_mode_persists_collector_and_points_decoy(tmp_path):
    base_url, stop = _start_server(tmp_path)
    try:
        created = _post_json(
            f"{base_url}/api/honey/keys",
            {
                "repoPath": str(tmp_path / "repo"),
                "repoName": "repo",
                "name": "Deployed canary",
                "placementMode": "deployed",
                "triggerBaseUrl": "https://collector.example.com/",
            },
        )
        # Deployed mode is honestly recorded and the callback targets the collector.
        assert created["placement_mode"] == "deployed"
        assert created["trigger_base_url"] == "https://collector.example.com"
        assert created["key"]["trigger_base_url"] == "https://collector.example.com"
        for snippet in created["snippets"].values():
            assert "https://collector.example.com/api/honey/trigger" in snippet
            assert "127.0.0.1" not in snippet
        # A bad collector URL is rejected; a deployed request without one is rejected.
        assert _post_json_expect_error(
            f"{base_url}/api/honey/keys",
            {"repoName": "repo", "placementMode": "deployed", "triggerBaseUrl": "not-a-url"},
        ) == 400
        assert _post_json_expect_error(
            f"{base_url}/api/honey/keys",
            {"repoName": "repo", "placementMode": "deployed"},
        ) == 400
    finally:
        stop()


def test_create_honey_key_defaults_to_local_loopback_callback(tmp_path):
    base_url, stop = _start_server(tmp_path)
    try:
        created = _post_json(
            f"{base_url}/api/honey/keys",
            {"repoPath": str(tmp_path / "repo"), "repoName": "repo", "name": "Local canary"},
        )
        assert created["placement_mode"] == "local"
        assert created["trigger_base_url"] is None
        assert created["key"]["trigger_base_url"] is None
        for snippet in created["snippets"].values():
            assert "/api/honey/trigger" in snippet
            assert "collector.example.com" not in snippet
    finally:
        stop()


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


# ---------------------------------------------------------------------------
# Tripwire bridge (Step 2.1): trigger → flip the case → light the path
# ---------------------------------------------------------------------------


def _sbom_component(name: str, version: str, *, ecosystem: str = "npm") -> SBOMComponent:
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


def _dependency_case(case_id: str, fingerprint: str, *, title: str) -> SecurityCase:
    return SecurityCase(
        case_id=case_id,
        title=title,
        plain_english_risk="A dependency has a known weakness.",
        action_level="fix_now",
        confidence="high",
        category="dependencies",
        severity="high",
        affected_files=["package-lock.json"],
        evidence=[{"scanner": "trivy", "title": title, "location": "package-lock.json", "component_fingerprint": fingerprint}],
        scanners=["trivy"],
        fix_steps=["Upgrade it."],
        agent_prompt="Upgrade the dependency.",
        source_fingerprints=[fingerprint],
    )


def _save_two_node_scan(db: ObservatoryDB, *, scan_id: str = "scan-1", repo: str = "repo"):
    """Persist a scan whose graph is `web <- (depends_on) - app`, plus two cases:
    one AT the web node (guarded) and one unrelated. Returns (web_node_id, fingerprints)."""
    web = _sbom_component("web-server", "1.0.0")
    app = _sbom_component("app", "2.0.0")
    case_web = _dependency_case("case-web", web.component_fingerprint, title="web-server vulnerability")
    case_other = SecurityCase(
        case_id="case-other",
        title="Risky code in lib/other.py",
        plain_english_risk="A risky code path.",
        action_level="verify",
        confidence="medium",
        category="code-security",
        severity="medium",
        affected_files=["lib/other.py"],
        evidence=[{"scanner": "semgrep", "title": "risky", "location": "lib/other.py:3"}],
        scanners=["semgrep"],
        fix_steps=["Fix it."],
        agent_prompt="Fix the code.",
        source_fingerprints=["other-fp"],
    )
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
        findings=[],
        report_path="/tmp/repo/report.json",
        cases=[case_web, case_other],
        sbom_components=[web, app],
    )
    # app depends_on web => a blast from web reaches app (depends_on walks reversed).
    db.replace_asset_edges(
        scan_id=scan_id,
        repo_name=repo,
        edges=[
            AssetEdge(
                src_identity_key=app.component_fingerprint,
                dst_identity_key=web.component_fingerprint,
                edge_type="depends_on",
                confidence="strong",
                reason="app depends on web-server",
            )
        ],
    )
    web_node_id = db.conn.execute(
        "select id from asset_nodes where scan_id = ? and identity_key = ?",
        (scan_id, web.component_fingerprint),
    ).fetchone()["id"]
    return web_node_id, {"web": web.component_fingerprint, "app": app.component_fingerprint}


def test_blast_radius_path_uses_real_edges():
    """The illuminated path is real graph data, not a guess: it follows the edges."""
    nodes = [
        _node(1, "web-fp", "web-server"),
        _node(2, "app-fp", "app"),
        _node(3, "cli-fp", "cli"),
        _node(4, "lonely-fp", "unconnected"),
    ]
    # app depends_on web, cli depends_on app => from web the blast reaches app then cli.
    edges = [_edge("depends_on", 2, 1), _edge("depends_on", 3, 2)]

    blast = blast_radius_from(("component", "web-fp"), nodes, edges)

    assert blast is not None
    assert blast["blast_radius"] == 2
    reached = {step["identity_key"]: step["distance"] for step in blast["reachable"]}
    assert reached == {"app-fp": 1, "cli-fp": 2}  # lonely-fp is NOT reachable
    # Every illuminated edge is a real edge between two reachable endpoints.
    edge_pairs = {(e["src_identity_key"], e["dst_identity_key"]) for e in blast["edges"]}
    assert edge_pairs == {("web-fp", "app-fp"), ("app-fp", "cli-fp")}


def test_blast_radius_from_returns_none_for_unknown_node():
    assert blast_radius_from(("component", "ghost"), [_node(1, "web-fp", "web")], []) is None


def test_apply_active_incidents_flips_only_the_node_case():
    """The case AT the guarded node flips; a case on the blast path does NOT."""
    case_at_node = {
        "case_id": "c1",
        "action_level": "fix_now",
        "affected_files": [],
        "evidence": [{"component_fingerprint": "web-fp"}],
        "rotation_surfaces": [],
        "priority_reasons": [],
    }
    downstream_case = {
        "case_id": "c2",
        "action_level": "verify",
        "affected_files": [],
        "evidence": [{"component_fingerprint": "app-fp"}],  # app is on the path, not the node
        "rotation_surfaces": [],
        "priority_reasons": [],
    }
    incident = {
        "node_type": "component",
        "identity_key": "web-fp",
        "node": {"node_type": "component", "identity_key": "web-fp", "label": "web-server"},
        "path": [{"identity_key": "app-fp", "distance": 1}],
        "edges": [{"src_identity_key": "web-fp", "dst_identity_key": "app-fp"}],
        "event_id": "evt-1",
        "honey_key_id": "key-1",
        "triggered_at": "2026-01-01T00:00:00+00:00",
        "blast_radius": 1,
    }

    flipped = apply_active_incidents([case_at_node, downstream_case], [incident])

    assert flipped == ["c1"]
    assert case_at_node["action_level"] == "active_incident"
    assert case_at_node["active_incident"]["path"] == [{"identity_key": "app-fp", "distance": 1}]
    assert "intrusion near this node" in case_at_node["active_incident"]["message"]
    # No copy claims the specific finding was exploited.
    assert "exploited" not in case_at_node["active_incident"]["message"].split("not that")[0]
    # The case on the blast path is illuminated but NOT escalated.
    assert downstream_case["action_level"] == "verify"
    assert "active_incident" not in downstream_case


def test_trigger_on_bound_node_flips_that_case_and_lights_the_path(tmp_path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        web_node_id, fingerprints = _save_two_node_scan(db)
        secret = db.honey_signing_secret()
        material = generate_honey_key(secret)
        db.create_honey_key(
            key_id=material.token_id,
            project_id="repo",
            repo_id="/tmp/repo",
            name="Decoy guarding web-server",
            token_hash=material.token_hash,
            placement_path=".devsec/honeykeys/decoy.env",
            asset_node_id=web_node_id,
        )
        raw_key = dict(db.conn.execute("select * from honey_keys where id = ?", (material.token_id,)).fetchone())
        event = db.record_honey_key_trigger(
            honey_key=raw_key,
            ip_address="127.0.0.1",
            user_agent="pytest",
            method="POST",
            path="/api/honey/trigger",
            headers={"User-Agent": "pytest"},
            body_summary=None,
            confidence=0.98,
            source_type="api_call",
        )
        payload = db.dashboard_payload()
        export = db.scan_export("scan-1")
    finally:
        db.close()

    # The incident snapshot was pinned at trip time with the real blast path.
    incident_row = export  # alias for clarity below
    cases_by_id = {case["case_id"]: case for case in payload["cases"]}
    web_case = cases_by_id["case-web"]
    assert web_case["action_level"] == "active_incident"
    assert web_case["active_incident"]["node"]["identity_key"] == fingerprints["web"]
    path_ids = {step["identity_key"] for step in web_case["active_incident"]["path"]}
    assert fingerprints["app"] in path_ids  # the blast path is real graph data
    assert "exploited" not in web_case["active_incident"]["message"].split("not that")[0]

    # The unrelated case is untouched (no false flip along/near the node).
    assert cases_by_id["case-other"]["action_level"] == "verify"

    # The same flip is visible in the single-scan export view.
    export_cases = {case["case_id"]: case for case in incident_row["cases"]}
    assert export_cases["case-web"]["action_level"] == "active_incident"
    assert export_cases["case-other"]["action_level"] == "verify"


def test_trigger_on_unbound_key_records_event_without_false_case_flip(tmp_path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        _save_two_node_scan(db)
        secret = db.honey_signing_secret()
        material = generate_honey_key(secret)
        db.create_honey_key(
            key_id=material.token_id,
            project_id="repo",
            repo_id="/tmp/repo",
            name="Free-floating decoy",
            token_hash=material.token_hash,
            placement_path=".devsec/honeykeys/decoy.env",
            # NOTE: no asset_node_id — this key guards no node.
        )
        raw_key = dict(db.conn.execute("select * from honey_keys where id = ?", (material.token_id,)).fetchone())
        db.record_honey_key_trigger(
            honey_key=raw_key,
            ip_address="127.0.0.1",
            user_agent="pytest",
            method="POST",
            path="/api/honey/trigger",
            headers={"User-Agent": "pytest"},
            body_summary=None,
            confidence=0.98,
            source_type="api_call",
        )
        payload = db.dashboard_payload()
        node_incidents = db.active_node_incidents()
    finally:
        db.close()

    # The event was recorded (project goes red, generic honey case appears)...
    assert payload["honey_key_events"][0]["honey_key_id"] == material.token_id
    assert any(case["title"] == "Honey Key triggered" for case in payload["cases"])
    # ...but no real finding/case was falsely flipped to active_incident.
    flipped = [case for case in payload["cases"] if case.get("action_level") == "active_incident"]
    assert flipped == []
    assert node_incidents == []


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
        (dashboard, 2937, "target_path.relative_to(repo_path)"),
        (dashboard, 2944, "if target_path.exists():"),
        (dashboard, 2945, "Placement file already exists."),
        (dashboard, 2846, "except sqlite3.IntegrityError:"),
        (dashboard, 2847, "Honey Key already exists."),
        (dashboard, 2960, "Honey Key belongs to a different repo."),
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
    for lineno in (2937, 2944, 2945, 2846, 2847, 2960):
        assert f":{lineno}" in doc, (
            f"docs/honey-keys.md Guard Map no longer cites dashboard_server.py:{lineno}"
        )
