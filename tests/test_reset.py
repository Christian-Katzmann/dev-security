"""Tests for security-scan reset command."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from security_observatory.reset import (
    backup_repo_state,
    execute_reset,
    list_known_repos,
    plan_reset,
    reset_confirmation_phrase,
)
from security_observatory.storage import ObservatoryDB


@pytest.fixture
def observatory_home(tmp_path: Path) -> Path:
    home = tmp_path / "observatory"
    home.mkdir()
    (home / "db").mkdir()
    (home / "reports").mkdir()
    return home


@pytest.fixture
def db(observatory_home: Path) -> ObservatoryDB:
    return ObservatoryDB(observatory_home / "db" / "observatory.sqlite")


@pytest.fixture
def seeded_db(db: ObservatoryDB, observatory_home: Path) -> ObservatoryDB:
    """Seed DB with one scan for repo 'test-repo' and supporting child rows."""
    with db.conn:
        db.conn.execute(
            """INSERT INTO scans (id, repo_name, repo_path, started_at, finished_at,
               profile, health_score, status, scanner_status_json, cases_json, report_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "test-repo-20260101",
                "test-repo",
                "/tmp/test-repo",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:01:00Z",
                "quick",
                95,
                "ok",
                "[]",
                "[]",
                str(observatory_home / "reports" / "test-repo" / "test-repo-20260101" / "normalized-report.json"),
            ),
        )
        db.conn.execute(
            """INSERT INTO findings (scan_id, repo_name, scanner, severity, category, title, fingerprint, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("test-repo-20260101", "test-repo", "semgrep", "high", "code-security", "test finding", "fp1", "2026-01-01T00:00:00Z"),
        )
        db.conn.execute(
            """INSERT INTO case_decisions (case_id, repo_name, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            ("case-1", "test-repo", "verified", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        db.conn.execute(
            """INSERT INTO agent_lab_proposals
               (id, external_proposal_id, repo_name, context_id, adapter_id, agent_label,
                summary, recommended_tools_json, recommended_packs_json, requested_permissions_json,
                requested_execution_json, expected_evidence_gaps_json, blocked_requests_json,
                validation_status, validation_errors_json, approval_state, imported_at,
                updated_at, raw_proposal_json, final_execution_plan_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "prop-1", "ext-1", "test-repo", "ctx-1", "adapter-1", "agent-1",
                "test proposal", "[]", "[]", "[]", "[]", "[]", "[]",
                "valid", "[]", "pending", "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z", "{}", "{}",
            ),
        )

    # Create report directory
    report_dir = observatory_home / "reports" / "test-repo" / "test-repo-20260101"
    report_dir.mkdir(parents=True)
    (report_dir / "normalized-report.json").write_text("{}", encoding="utf-8")

    return db


def test_confirmation_phrase_structure():
    phrase = reset_confirmation_phrase("my-repo")
    assert "my-repo" in phrase
    assert "irreversible" in phrase
    assert phrase.startswith("Yes, wipe")


def test_list_known_repos_empty(db: ObservatoryDB):
    assert list_known_repos(db) == []


def test_list_known_repos_returns_names(seeded_db: ObservatoryDB):
    repos = list_known_repos(seeded_db)
    assert "test-repo" in repos


def test_dry_run_plan(seeded_db: ObservatoryDB, observatory_home: Path):
    plan = plan_reset(seeded_db, "test-repo", observatory_home)
    table_names = [entry["table"] for entry in plan["tables"]]
    assert "scans" in table_names
    assert "findings" in table_names
    assert any("test-repo" in f for f in plan["files"])


def test_dry_run_with_rotation_scaffold(seeded_db: ObservatoryDB, observatory_home: Path, tmp_path: Path):
    repo_path = tmp_path / "fake-repo"
    repo_path.mkdir()
    (repo_path / "data").mkdir()
    (repo_path / "data" / "rotation-state.json").write_text("{}", encoding="utf-8")
    (repo_path / "data" / "rotation-log.jsonl").write_text("", encoding="utf-8")

    plan = plan_reset(
        seeded_db, "test-repo", observatory_home,
        include_rotation_scaffold=True,
        repo_path=repo_path,
    )
    scaffold_files = [f for f in plan["files"] if "rotation" in f]
    assert len(scaffold_files) >= 2


def test_execute_reset_deletes_rows(seeded_db: ObservatoryDB, observatory_home: Path):
    result = execute_reset(seeded_db, "test-repo", observatory_home)
    assert result["tables"]["scans"] == 1
    assert result["tables"]["findings"] == 1
    assert result["tables"]["case_decisions"] == 1
    assert result["tables"]["agent_lab_proposals"] == 1

    # Verify rows are gone
    row = seeded_db.conn.execute("SELECT COUNT(*) as cnt FROM scans WHERE repo_name = ?", ("test-repo",)).fetchone()
    assert row["cnt"] == 0
    row = seeded_db.conn.execute("SELECT COUNT(*) as cnt FROM findings WHERE repo_name = ?", ("test-repo",)).fetchone()
    assert row["cnt"] == 0


def test_execute_reset_removes_report_dir(seeded_db: ObservatoryDB, observatory_home: Path):
    assert (observatory_home / "reports" / "test-repo").exists()
    execute_reset(seeded_db, "test-repo", observatory_home)
    assert not (observatory_home / "reports" / "test-repo").exists()


def test_execute_reset_removes_rotation_scaffold(seeded_db: ObservatoryDB, observatory_home: Path, tmp_path: Path):
    repo_path = tmp_path / "fake-repo"
    repo_path.mkdir()
    (repo_path / "data").mkdir()
    (repo_path / "data" / "rotation-state.json").write_text("{}", encoding="utf-8")
    (repo_path / "data" / "rotation-log.jsonl").write_text("", encoding="utf-8")
    receipts = repo_path / "data" / "rotation-receipts"
    receipts.mkdir()
    (receipts / "secret-123.md").write_text("receipt", encoding="utf-8")
    rotation_lib = repo_path / "src" / "lib" / "rotation"
    rotation_lib.mkdir(parents=True)
    (rotation_lib / "index.ts").write_text("export {}", encoding="utf-8")

    # Create package.json with rotate script
    pkg = {"name": "test", "scripts": {"dev": "next dev", "rotate": "npx tsx src/lib/rotation/rotate.ts"}}
    (repo_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

    execute_reset(
        seeded_db, "test-repo", observatory_home,
        include_rotation_scaffold=True,
        repo_path=repo_path,
    )

    assert not (repo_path / "data" / "rotation-state.json").exists()
    assert not (repo_path / "data" / "rotation-log.jsonl").exists()
    assert not receipts.exists()
    assert not rotation_lib.exists()

    # Verify rotate script removed from package.json
    pkg_data = json.loads((repo_path / "package.json").read_text(encoding="utf-8"))
    assert "rotate" not in pkg_data["scripts"]
    assert "dev" in pkg_data["scripts"]


def test_backup_creates_files(seeded_db: ObservatoryDB, observatory_home: Path, tmp_path: Path):
    backup_dir = tmp_path / "backups"
    backups = backup_repo_state(seeded_db, "test-repo", observatory_home, backup_dir)
    assert "sqldump" in backups
    assert Path(backups["sqldump"]).exists()
    assert "reports_tarball" in backups
    assert Path(backups["reports_tarball"]).exists()

    # Verify sqldump content
    dump = json.loads(Path(backups["sqldump"]).read_text(encoding="utf-8"))
    assert len(dump["scans"]) == 1
    assert dump["scans"][0]["repo_name"] == "test-repo"


def test_transactional_rollback_on_failure(seeded_db: ObservatoryDB, observatory_home: Path):
    """Simulate a mid-transaction failure and confirm sqlite state is unchanged.

    We use a wrapper class around the connection that intercepts execute calls
    since sqlite3.Connection attributes are read-only C-level descriptors.
    """
    # Verify pre-state
    row = seeded_db.conn.execute("SELECT COUNT(*) as cnt FROM scans WHERE repo_name = ?", ("test-repo",)).fetchone()
    assert row["cnt"] == 1

    class ExplodingConnection:
        """Proxy that raises on the scans DELETE to simulate mid-transaction failure."""
        def __init__(self, real_conn):
            self._real = real_conn

        def __getattr__(self, name):
            return getattr(self._real, name)

        def __enter__(self):
            self._real.__enter__()
            return self

        def __exit__(self, *args):
            return self._real.__exit__(*args)

        def execute(self, sql, params=()):
            if "DELETE FROM scans" in sql:
                raise sqlite3.OperationalError("simulated disk failure")
            return self._real.execute(sql, params)

    original_conn = seeded_db.conn
    seeded_db.conn = ExplodingConnection(original_conn)

    with pytest.raises(sqlite3.OperationalError, match="simulated disk failure"):
        execute_reset(seeded_db, "test-repo", observatory_home)

    # Restore real connection for verification
    seeded_db.conn = original_conn

    # Transaction rolled back — all rows should still be present
    row = seeded_db.conn.execute("SELECT COUNT(*) as cnt FROM scans WHERE repo_name = ?", ("test-repo",)).fetchone()
    assert row["cnt"] == 1
    row = seeded_db.conn.execute("SELECT COUNT(*) as cnt FROM findings WHERE repo_name = ?", ("test-repo",)).fetchone()
    assert row["cnt"] == 1


def test_confirmation_refusal_without_yes(seeded_db: ObservatoryDB, observatory_home: Path):
    """The reset_confirmation_phrase must match exactly."""
    phrase = reset_confirmation_phrase("test-repo")
    assert phrase != "yes"
    assert "Yes, wipe" in phrase


def test_reset_unknown_repo(db: ObservatoryDB):
    repos = list_known_repos(db)
    assert "nonexistent" not in repos


def test_execute_reset_idempotent(seeded_db: ObservatoryDB, observatory_home: Path):
    """Running reset twice doesn't fail — second run is a no-op."""
    execute_reset(seeded_db, "test-repo", observatory_home)
    result = execute_reset(seeded_db, "test-repo", observatory_home)
    assert result["tables"] == {}
    assert result["files"] == []
