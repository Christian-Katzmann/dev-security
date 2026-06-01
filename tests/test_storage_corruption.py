"""Tests for ObservatoryDB corruption recovery.

A corrupt local history DB (disk full mid-write, an interrupted scan, stray
bytes) must degrade to a calm, recoverable state — never a raw traceback. The
corrupt file is preserved (quarantined), never deleted, because it is the user's
local security data. See .adx/risks.json (local-security-data).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from security_observatory.storage import ObservatoryDB


GARBAGE = b"this is not a sqlite database, just stray bytes\x00\xff" * 8


def _db_path(tmp_path: Path) -> Path:
    path = tmp_path / "db" / "observatory.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_recovers_from_corrupt_file(tmp_path: Path) -> None:
    path = _db_path(tmp_path)
    path.write_bytes(GARBAGE)

    db = ObservatoryDB(path)
    try:
        # Recovery signal is exposed so callers can craft a trust-preserving
        # message instead of surfacing a stack trace.
        assert db.recovered_from_corruption is True
        assert db.quarantined_path is not None
        assert db.quarantined_path.exists()
        assert db.quarantined_path.name.startswith("observatory.sqlite.corrupt-")

        # The corrupt bytes are preserved exactly — never deleted, never altered.
        assert db.quarantined_path.read_bytes() == GARBAGE

        # The live path is now a fresh, usable DB: schema present, queryable, and
        # the full dashboard read path works without raising.
        assert path.exists()
        assert db.conn.execute("select count(*) from scans").fetchone()[0] == 0
        assert isinstance(db.dashboard_payload(), dict)
    finally:
        db.close()


def test_recovered_db_is_persistently_healthy(tmp_path: Path) -> None:
    path = _db_path(tmp_path)
    path.write_bytes(GARBAGE)

    first = ObservatoryDB(path)
    first.close()

    # Reopening the replacement DB must not re-trigger recovery: the fresh file
    # is genuinely healthy, so a second open is an ordinary happy-path open.
    second = ObservatoryDB(path)
    try:
        assert second.recovered_from_corruption is False
        assert second.quarantined_path is None
    finally:
        second.close()


def test_healthy_db_is_never_quarantined(tmp_path: Path) -> None:
    path = _db_path(tmp_path)

    # Fresh DB.
    first = ObservatoryDB(path)
    first.close()
    # Reopen an existing, valid DB.
    second = ObservatoryDB(path)
    try:
        assert second.recovered_from_corruption is False
        assert second.quarantined_path is None
    finally:
        second.close()

    # No quarantine artifacts were created for healthy databases.
    assert not list(path.parent.glob("*.corrupt-*"))


def test_stale_sidecars_are_cleared_on_recovery(tmp_path: Path) -> None:
    path = _db_path(tmp_path)
    path.write_bytes(GARBAGE)
    # A stale rollback journal beside a corrupt DB would otherwise be replayed
    # into the fresh replacement and re-corrupt it.
    journal = path.with_name(f"{path.name}-journal")
    journal.write_bytes(b"stale journal bytes")

    db = ObservatoryDB(path)
    try:
        assert db.recovered_from_corruption is True
        assert not journal.exists()
        # The replacement DB is valid and queryable.
        assert db.conn.execute("select count(*) from scans").fetchone()[0] == 0
    finally:
        db.close()


def test_environmental_failure_is_not_quarantined(tmp_path: Path) -> None:
    # A path that is a directory raises sqlite3.OperationalError ("unable to open
    # database file"). That is environmental, not corruption — the bytes are not
    # known to be bad (this also models a locked DB held by a concurrent writer).
    # Quarantining here would destroy healthy data, so the error must propagate
    # untouched and nothing must be moved aside.
    import sqlite3

    path = tmp_path / "db" / "observatory.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir()

    with pytest.raises(sqlite3.OperationalError):
        ObservatoryDB(path)

    assert not list(path.parent.glob("*.corrupt-*"))


def test_corrupt_cases_json_row_degrades_dashboard_payload(tmp_path: Path) -> None:
    # A hand-edited / truncated cases_json column must degrade to a warning, not
    # crash the dashboard read path (S-023). The bad row's cases are skipped; the
    # rest of the payload still renders. Reverting any guard to a bare json.loads
    # makes dashboard_payload() raise JSONDecodeError here.
    path = _db_path(tmp_path)
    db = ObservatoryDB(path)
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path=str(tmp_path / "repo"),
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="quick",
            health_score=70,
            status="ok",
            scanner_statuses=[],
            findings=[],
            report_path=str(tmp_path / "normalized-report.json"),
            cases=[],
        )
        # Corrupt the stored cases JSON the way a disk-full mid-write or a manual
        # edit would: valid SQLite row, invalid JSON in the cases column.
        with db.conn:
            db.conn.execute(
                "update scans set cases_json = ? where id = ?",
                ("{not valid json", "repo-20260101T000000Z"),
            )

        payload = db.dashboard_payload()
        assert isinstance(payload, dict)
        # The corrupt row contributed no cases, but the repo is still present.
        assert any(repo.get("repo") == "repo" for repo in payload.get("repos") or [])
    finally:
        db.close()


def test_mcp_read_path_surfaces_recovery(tmp_path: Path) -> None:
    # The MCP read path must not silently return "no scans yet" after a corrupt
    # store was quarantined and rebuilt (S-003). _with_db raises a calm, named
    # recovery signal that FastMCP delivers to the client as a ToolError, not a
    # traceback or an empty result.
    pytest.importorskip("mcp")
    from mcp.server.fastmcp.exceptions import ToolError

    from security_observatory.mcp_server import HistoryRecoveredError, create_server

    db_path = tmp_path / "db" / "observatory.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(GARBAGE)

    server = create_server(home=tmp_path)
    with pytest.raises(ToolError) as exc:
        asyncio.run(server.call_tool("list_repos", {}))
    message = str(exc.value)
    assert "quarantined" in message.lower()
    assert "preserved" in message.lower()
    # The corrupt file was preserved on disk, never deleted.
    assert list(db_path.parent.glob("observatory.sqlite.corrupt-*"))

    # The recovery signal is a typed, named error — not a bare RuntimeError.
    assert issubclass(HistoryRecoveredError, RuntimeError)
