from __future__ import annotations

from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from pathlib import Path
from urllib import request
import json
import threading

from security_observatory.dashboard_server import DashboardHandler
from security_observatory.honey_keys import generate_honey_key, hash_honey_key, honey_key_is_well_formed
from security_observatory.storage import ObservatoryDB


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
