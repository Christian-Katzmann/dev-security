"""TTL pruning of terminal CHECK_JOBS entries (S-014).

A long-lived single-user dashboard server must not accumulate completed jobs
in memory forever. Terminal (complete/halted/failed) jobs are pruned after a
TTL; in-flight jobs and recently-finished jobs are retained so the
check-status poll contract (unknown/expired job → 404) is unchanged.
"""
from __future__ import annotations

import datetime as _dt

from security_observatory.dashboard_server import (
    CHECK_JOB_TTL_SECONDS,
    CHECK_JOBS,
    CHECK_JOBS_LOCK,
    job_snapshot,
    prune_terminal_check_jobs,
)


def _iso(dt: _dt.datetime) -> str:
    return dt.isoformat()


def _seed(jobs: dict[str, dict[str, object]]) -> None:
    with CHECK_JOBS_LOCK:
        CHECK_JOBS.clear()
        CHECK_JOBS.update(jobs)


def _clear() -> None:
    with CHECK_JOBS_LOCK:
        CHECK_JOBS.clear()


def test_stale_terminal_job_pruned_fresh_and_inflight_retained() -> None:
    now = _dt.datetime(2026, 6, 1, 12, 0, 0, tzinfo=_dt.timezone.utc)
    stale = now - _dt.timedelta(seconds=CHECK_JOB_TTL_SECONDS + 60)
    fresh = now - _dt.timedelta(seconds=30)
    try:
        _seed(
            {
                "stale-complete": {"id": "stale-complete", "status": "complete", "finished_at": _iso(stale)},
                "stale-failed": {"id": "stale-failed", "status": "failed", "finished_at": _iso(stale)},
                "fresh-complete": {"id": "fresh-complete", "status": "complete", "finished_at": _iso(fresh)},
                "in-flight": {"id": "in-flight", "status": "running", "started_at": _iso(stale)},
            }
        )
        pruned = prune_terminal_check_jobs(now=now)

        assert set(pruned) == {"stale-complete", "stale-failed"}
        with CHECK_JOBS_LOCK:
            remaining = set(CHECK_JOBS)
        # Fresh terminal job kept; in-flight job kept even though it started long ago.
        assert remaining == {"fresh-complete", "in-flight"}
    finally:
        _clear()


def test_terminal_job_without_timestamp_is_kept() -> None:
    """A terminal job we can't date is never pruned — pruning only drops jobs
    we can confidently prove are stale."""
    try:
        _seed({"no-stamp": {"id": "no-stamp", "status": "complete"}})
        pruned = prune_terminal_check_jobs()
        assert pruned == []
        with CHECK_JOBS_LOCK:
            assert "no-stamp" in CHECK_JOBS
    finally:
        _clear()


def test_job_snapshot_prunes_stale_terminal_jobs_on_poll() -> None:
    """The poll path triggers pruning: a stale terminal job is gone (→ 404),
    while a fresh job remains readable through the same call."""
    now = _dt.datetime.now(_dt.timezone.utc)
    stale = now - _dt.timedelta(seconds=CHECK_JOB_TTL_SECONDS + 120)
    try:
        _seed(
            {
                "stale": {"id": "stale", "status": "failed", "finished_at": stale.isoformat()},
                "live": {"id": "live", "status": "running", "started_at": now.isoformat()},
            }
        )
        # Polling any job prunes globally; the stale terminal job is dropped.
        assert job_snapshot("live") is not None
        assert job_snapshot("stale") is None  # pruned → missing-job 404 contract
        with CHECK_JOBS_LOCK:
            assert "stale" not in CHECK_JOBS
            assert "live" in CHECK_JOBS
    finally:
        _clear()
