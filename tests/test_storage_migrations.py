"""Versioned-migration round trip for the SQLite history store (S-026).

PRAGMA ``user_version`` is the single migration counter. An old-shape database
(pre-``user_version``, narrow CHECK constraints) must migrate to the current
version on first open with every row intact, and a second open must be a no-op —
the version gate, not a string-sentinel, decides whether the destructive rebuild
runs.
"""

from pathlib import Path
import re
import sqlite3
from unittest.mock import patch

import pytest

from security_observatory import lifecycle
from security_observatory.storage import (
    CASE_DECISION_STATUS_CHECK,
    SCHEMA,
    SCHEMA_USER_VERSION,
    ObservatoryDB,
)


def _build_legacy_db(db_path: Path) -> None:
    """Write a pre-S-026 database: user_version 0, narrow status constraints."""
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
            -- Narrow (old) case-resolution constraints, missing the suppression-gate states.
            create table case_resolution_runs (
              id text primary key, repo_name text not null, scan_id text, action text not null,
              scope text not null, source text not null, imported_at text not null, applied_at text,
              status text not null check(status in ('previewed', 'applied', 'partially_applied', 'rejected')),
              summary_json text not null default '{}'
            );
            create table case_resolution_items (
              id text primary key, run_id text not null, case_id text not null, repo_name text not null,
              scan_id text, ai_disposition text not null, mapped_decision text, confidence text not null,
              reason text not null, evidence_json text not null default '[]', recommended_next_step text,
              applied_decision_json text,
              status text not null check(status in ('pending', 'applied', 'left_open', 'rejected')),
              warning text, created_at text not null
            );
            -- Narrow (old) case_decisions: no 'in_progress', no later-added columns.
            create table case_decisions (
              case_id text primary key, repo_name text not null,
              status text not null check(status in ('verified', 'false_positive', 'accepted_risk', 'fixed')),
              note text, created_at text not null, updated_at text not null
            );
            insert into scans (id, repo_name, repo_path, started_at, profile, health_score, status, scanner_status_json)
              values ('repo-20260101T000000Z', 'repo', '/tmp/repo', '2026-01-01T00:00:00+00:00', 'quick', 80, 'ok', '[]');
            insert into case_resolution_runs (id, repo_name, action, scope, source, imported_at, status)
              values ('run-legacy', 'repo', 'verify_findings', 'all_open', 'cli', '2026-01-01T00:00:00+00:00', 'applied');
            insert into case_resolution_items
              (id, run_id, case_id, repo_name, ai_disposition, confidence, reason, status, created_at)
              values ('item-legacy', 'run-legacy', 'case-legacy', 'repo', 'confirmed_real', 'high', 'ok', 'applied', '2026-01-01T00:00:00+00:00');
            insert into case_decisions (case_id, repo_name, status, note, created_at, updated_at)
              values ('case-legacy', 'repo', 'fixed', 'historic', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00');
            """
        )
        conn.commit()
        assert conn.execute("pragma user_version").fetchone()[0] == 0
    finally:
        conn.close()


def _user_version(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("pragma user_version").fetchone()[0]
    finally:
        conn.close()


def test_legacy_db_migrates_to_current_version_with_data_intact(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    _build_legacy_db(db_path)

    db = ObservatoryDB(db_path)
    try:
        assert db.conn.execute("pragma user_version").fetchone()[0] == SCHEMA_USER_VERSION
        # Every seeded row survived the destructive rebuild.
        assert db.conn.execute("select count(*) from scans").fetchone()[0] == 1
        assert db.get_case_resolution_run("run-legacy") is not None
        assert db.conn.execute(
            "select status from case_decisions where case_id = 'case-legacy'"
        ).fetchone()["status"] == "fixed"
        # The widened constraints now accept the suppression-gate / lifecycle states.
        db.conn.execute("update case_resolution_runs set status = 'requires_confirmation' where id = 'run-legacy'")
        db.conn.execute("update case_resolution_items set status = 'requires_human_confirmation' where id = 'item-legacy'")
        db.conn.execute("update case_decisions set status = 'in_progress' where case_id = 'case-legacy'")
        db.conn.commit()
    finally:
        db.close()

    assert _user_version(db_path) == SCHEMA_USER_VERSION


def test_reopen_is_idempotent_and_does_not_rebuild(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    _build_legacy_db(db_path)

    # First open performs the migration.
    ObservatoryDB(db_path).close()
    assert _user_version(db_path) == SCHEMA_USER_VERSION

    # Second open must short-circuit on the version gate: the destructive rebuild
    # is never called again. Patching it to fail proves the gate, not a sentinel,
    # is what prevents a re-rebuild.
    with patch.object(
        ObservatoryDB,
        "_migrate_resolution_status_constraints",
        side_effect=AssertionError("rebuild must not run on an up-to-date database"),
    ) as rebuild_spy:
        db = ObservatoryDB(db_path)
        try:
            assert db.conn.execute("pragma user_version").fetchone()[0] == SCHEMA_USER_VERSION
            assert db.get_case_resolution_run("run-legacy") is not None
        finally:
            db.close()
    rebuild_spy.assert_not_called()


def test_fresh_db_is_stamped_to_current_version(tmp_path):
    db = ObservatoryDB(tmp_path / "fresh.sqlite")
    try:
        assert db.conn.execute("pragma user_version").fetchone()[0] == SCHEMA_USER_VERSION
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Drift guard: the case_decisions CHECK must derive from lifecycle, not a
# hand-maintained literal. These fail the moment the SQL and the canonical set
# disagree — including the migrated-table mirror, which shares the constant.
# ---------------------------------------------------------------------------


def _statuses_in_check(check_sql: str) -> set[str]:
    return set(re.findall(r"'([^']+)'", check_sql))


def test_check_clause_is_derived_from_decision_statuses():
    assert _statuses_in_check(CASE_DECISION_STATUS_CHECK) == set(lifecycle.DECISION_STATUSES)


def test_schema_embeds_the_derived_check_not_a_literal():
    # The substitution must have run (no leftover sentinel) and the rendered
    # clause must be present verbatim in the schema the DB is built from.
    assert "__CASE_DECISION_STATUS_CHECK__" not in SCHEMA
    assert CASE_DECISION_STATUS_CHECK in SCHEMA


def test_fresh_db_accepts_every_decision_status_and_rejects_unknown(tmp_path):
    db = ObservatoryDB(tmp_path / "check.sqlite")
    try:
        for index, status in enumerate(sorted(lifecycle.DECISION_STATUSES)):
            db.conn.execute(
                "insert into case_decisions (case_id, repo_name, status, created_at, updated_at)"
                " values (?, 'repo', ?, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')",
                (f"case-{index}", status),
            )
        db.conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db.conn.execute(
                "insert into case_decisions (case_id, repo_name, status, created_at, updated_at)"
                " values ('case-bogus', 'repo', 'not_a_real_status',"
                " '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')"
            )
    finally:
        db.close()
