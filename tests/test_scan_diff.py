"""Arbitrary scan-to-scan diff (S-039).

The dashboard's base/head picker drives `ObservatoryDB.scan_diff`, which reuses
the per-repo delta engine to compare *any* two saved scans — not just a scan and
its immediate predecessor. These tests pin the directional health delta and the
new / recurring / resolved case sets, including the closure-proof binding on a
resolved case.
"""

from security_observatory.model import SecurityCase
from security_observatory.storage import ObservatoryDB


def _save(db, *, scan_id, started_at, health, cases):
    db.save_scan(
        scan_id=scan_id,
        repo_name="repo",
        repo_path="/tmp/repo",
        started_at=started_at,
        finished_at=started_at,
        profile="quick",
        health_score=health,
        status="ok",
        scanner_statuses=[{"scanner": "semgrep", "available": True, "findings": len(cases)}],
        findings=[],
        report_path="report.json",
        cases=cases,
    )


def _case(case_id, title):
    return SecurityCase(
        case_id=case_id,
        title=title,
        plain_english_risk="",
        action_level="fix_now",
        confidence="high",
        category="secrets",
        severity="high",
        affected_files=[],
        evidence=[],
        scanners=["semgrep"],
        fix_steps=[],
        agent_prompt="",
        source_fingerprints=[],
    )


def test_scan_diff_compares_two_arbitrary_scans(tmp_path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        # Three scans for the same repo. base=s1, head=s3 skips the immediate
        # predecessor (s2) entirely — the capability the UI now surfaces.
        _save(db, scan_id="s1", started_at="2026-05-28T10:00:00+00:00", health=60,
              cases=[_case("A", "Token in env"), _case("B", "Weak hash")])
        _save(db, scan_id="s2", started_at="2026-05-29T10:00:00+00:00", health=72,
              cases=[_case("A", "Token in env")])
        _save(db, scan_id="s3", started_at="2026-05-30T10:00:00+00:00", health=84,
              cases=[_case("A", "Token in env"), _case("C", "Open redirect")])

        diff = db.scan_diff("s1", "s3")
    finally:
        db.close()

    assert diff is not None
    assert diff["base"]["scan_id"] == "s1"
    assert diff["head"]["scan_id"] == "s3"
    assert diff["same_repo"] is True
    # base health 60 -> head health 84.
    assert diff["health_delta"] == 24
    # vs the base (A, B): A recurs, C is new, B is resolved.
    assert diff["counts"] == {"new": 1, "recurring": 1, "resolved": 1}
    assert {c["case_id"] for c in diff["new_cases"]} == {"C"}
    assert {c["case_id"] for c in diff["recurring_cases"]} == {"A"}

    resolved = diff["resolved_cases"]
    assert {c["case_id"] for c in resolved} == {"B"}
    # Closure-proof binding (S-035): the resolved case names the scan that closed it.
    assert resolved[0]["resolved_by_scan_id"] == "s3"
    assert resolved[0]["lifecycle_state"] == "resolved"
    assert "scan s3" in resolved[0]["next_step"]


def test_scan_diff_returns_none_for_unknown_scan(tmp_path):
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        _save(db, scan_id="s1", started_at="2026-05-28T10:00:00+00:00", health=60,
              cases=[_case("A", "Token in env")])
        assert db.scan_diff("s1", "does-not-exist") is None
        assert db.scan_diff("missing", "s1") is None
    finally:
        db.close()
