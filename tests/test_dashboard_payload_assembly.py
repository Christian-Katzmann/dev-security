"""Behaviour + performance contract for the lifted dashboard-payload assembly.

Batch 16 (S-017/S-027) moved the ``/api/summary`` assembly out of
``ObservatoryDB`` into ``dashboard_payload.assemble_dashboard_payload`` and
replaced the per-repo query fan-out with set-based batch reads. Two guarantees
must hold:

1. **No payload-shape change.** The batched assembly must produce a dict that is
   deep-equal to the un-batched, per-repo assembly. We prove this by running the
   *same* assembly twice over the *same* seeded database: once against the real
   ``ObservatoryDB`` (set-based batch queries) and once against a reference proxy
   whose batch methods are reimplemented in terms of the untouched per-repo
   ``list_*`` / ``_previous_scan`` helpers — i.e. exactly the pre-refactor data
   access pattern. Reading one database twice keeps catalogs and timestamps
   identical, so any divergence is a genuine batching bug.

2. **Query count is O(1) in repo count (S-027).** A ``sqlite3`` trace over
   ``dashboard_payload`` on a 5-repo vs a 50-repo database must execute the same
   number of statements, and exactly one ``case_resolution_items`` query (the
   collapsed per-run N+1).
"""

from __future__ import annotations

from pathlib import Path

from security_observatory.dashboard_payload import assemble_dashboard_payload
from security_observatory.model import Finding
from security_observatory.storage import ObservatoryDB


FIXED_TS = "2026-01-01T00:00:00+00:00"


def _finding(repo: str, *, severity: str, category: str, title: str, **kwargs) -> Finding:
    return Finding(
        repo=repo,
        scanner=kwargs.pop("scanner", "fixture-scanner"),
        severity=severity,
        category=category,
        title=title,
        timestamp=FIXED_TS,
        **kwargs,
    )


def _component(name: str, version: str, license_: str, *, ecosystem: str = "npm") -> dict:
    return {
        "name": name,
        "version": version,
        "ecosystem": ecosystem,
        "component_type": "library",
        "package_url": f"pkg:{ecosystem}/{name}@{version}",
        "license": license_,
        "supplier": None,
        "source_path": "lockfile",
    }


def _manifest(name: str, declaration: str, *, ecosystem: str = "npm") -> dict:
    return {
        "manifest_path": "package.json" if ecosystem == "npm" else "requirements.txt",
        "ecosystem": ecosystem,
        "name": name,
        "declaration": declaration,
        "normalized_declaration": declaration.strip().casefold(),
        "scope": "dependencies",
        "manifest_fingerprint": f"fixture-manifest-{name}",
    }


def _trust(name: str, version: str) -> dict:
    return {
        "package_name": name,
        "package_version": version,
        "package_ecosystem": "npm",
        "package_url": f"pkg:npm/{name}@{version}",
        "source_repo": f"github.com/acme/{name}",
        "source_repo_url": f"https://github.com/acme/{name}",
        "source_repo_confidence": "strong",
        "scorecard_score": 7.5,
        "scorecard_status": "checked",
        "criticality_score": 0.6,
        "criticality_status": "checked",
        "status": "fresh",
        "freshness": "fresh",
        "cache_key": f"github.com/acme/{name}",
    }


def _posture(status: str) -> dict:
    return {
        "scanner": "legitify",
        "source": "legitify",
        "target": "repository",
        "status": "checked",
        "summary": {"failed": 1 if status == "FAILED" else 0, "passed": 2},
        "records": [{"resource_ref": "resource:branch", "status": status}],
    }


def _dependency_case(repo: str, case_id: str, name: str, version: str, severity: str) -> dict:
    return {
        "case_id": case_id,
        "repo": repo,
        "repo_name": repo,
        "title": f"Vulnerable dependency {name}",
        "category": "dependencies",
        "severity": severity,
        "action_level": "fix_now" if severity in {"critical", "high"} else "watch",
        "confidence": "high",
        "package_name": name,
        "package_version": version,
        "package_ecosystem": "npm",
        "package_url": f"pkg:npm/{name}@{version}",
        "plain_english_risk": f"{name} {version} has a known issue.",
    }


def _secrets_case(repo: str, case_id: str, severity: str) -> dict:
    return {
        "case_id": case_id,
        "repo": repo,
        "repo_name": repo,
        "title": "Exposed secret",
        "category": "secrets",
        "severity": severity,
        "action_level": "fix_now",
        "confidence": "medium",
        "plain_english_risk": "A credential may be exposed.",
    }


def _resolution_run(repo: str, run_id: str, scan_id: str, imported_at: str) -> dict:
    return {
        "run_id": run_id,
        "repo_name": repo,
        "scan_id": scan_id,
        "action": "preview",
        "scope": "repo",
        "source": "json_import",
        "status": "previewed",
        "imported_at": imported_at,
        "summary": {"will_apply": 1},
        "items": [
            {
                "id": f"{run_id}:item-1",
                "case_id": f"{repo}-dep-1",
                "repo_name": repo,
                "scan_id": scan_id,
                "ai_disposition": "suppress",
                "mapped_decision": "suppressed",
                "confidence": "medium",
                "reason": "Reviewed and accepted.",
                "status": "pending",
                "created_at": imported_at,
            }
        ],
    }


def _seed_rich_fixture(db: ObservatoryDB) -> None:
    """Three repos with varied history: two-scan deltas, a first-scan repo,
    cases (with a suppression decision), SBOM/manifest/trust/posture data, and
    resolution runs — every batched read path is exercised with real rows."""
    # alpha: two scans, dependency delta "changed", trust + posture, a suppressed case.
    db.save_scan(
        scan_id="alpha-scan-1",
        repo_name="alpha",
        repo_path="/tmp/alpha",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        profile="full",
        health_score=70,
        status="ok",
        scanner_statuses=[{"scanner": "syft", "available": True, "findings": 1}],
        findings=[_finding("alpha", severity="high", category="dependencies", title="lodash issue")],
        report_path="/tmp/alpha/r1.json",
        cases=[_dependency_case("alpha", "alpha-dep-1", "lodash", "4.17.20", "high")],
        sbom_components=[_component("lodash", "4.17.20", "MIT"), _component("left-pad", "1.0.0", "MIT")],
        dependency_manifest_entries=[_manifest("lodash", "^4.17.20")],
    )
    db.save_scan(
        scan_id="alpha-scan-2",
        repo_name="alpha",
        repo_path="/tmp/alpha",
        started_at="2026-01-02T00:00:00+00:00",
        finished_at="2026-01-02T00:01:00+00:00",
        profile="full",
        health_score=55,
        status="ok",
        scanner_statuses=[{"scanner": "syft", "available": True, "findings": 2}],
        findings=[
            _finding("alpha", severity="high", category="dependencies", title="lodash issue"),
            _finding("alpha", severity="low", category="secrets", title="stray token"),
        ],
        report_path="/tmp/alpha/r2.json",
        cases=[
            _dependency_case("alpha", "alpha-dep-1", "lodash", "4.18.0", "high"),
            _secrets_case("alpha", "alpha-sec-1", "low"),
        ],
        sbom_components=[_component("lodash", "4.18.0", "BSD-3-Clause"), _component("react", "19.0.1", "MIT")],
        dependency_manifest_entries=[_manifest("lodash", "^4.18.0"), _manifest("react", "^19.0.0")],
        dependency_trust_enrichments=[_trust("lodash", "4.18.0"), _trust("react", "19.0.1")],
        platform_posture_snapshot=_posture("FAILED"),
    )
    # bravo: two scans, no dependency data on the latter (no-sbom delta branch).
    db.save_scan(
        scan_id="bravo-scan-1",
        repo_name="bravo",
        repo_path="/tmp/bravo",
        started_at="2026-01-01T06:00:00+00:00",
        finished_at="2026-01-01T06:01:00+00:00",
        profile="quick",
        health_score=90,
        status="ok",
        scanner_statuses=[{"scanner": "gitleaks", "available": True, "findings": 0}],
        findings=[],
        report_path="/tmp/bravo/r1.json",
        cases=[],
        sbom_components=[_component("requests", "2.32.3", "Apache-2.0", ecosystem="pypi")],
    )
    db.save_scan(
        scan_id="bravo-scan-2",
        repo_name="bravo",
        repo_path="/tmp/bravo",
        started_at="2026-01-02T06:00:00+00:00",
        finished_at="2026-01-02T06:01:00+00:00",
        profile="quick",
        health_score=88,
        status="ok",
        scanner_statuses=[{"scanner": "gitleaks", "available": True, "findings": 1}],
        findings=[_finding("bravo", severity="medium", category="secrets", title="api key")],
        report_path="/tmp/bravo/r2.json",
        cases=[_secrets_case("bravo", "bravo-sec-1", "medium")],
        sbom_components=[],
    )
    # charlie: single scan (first-scan branch, no previous).
    db.save_scan(
        scan_id="charlie-scan-1",
        repo_name="charlie",
        repo_path="/tmp/charlie",
        started_at="2026-01-01T12:00:00+00:00",
        finished_at="2026-01-01T12:01:00+00:00",
        profile="full",
        health_score=100,
        status="ok",
        scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
        findings=[],
        report_path="/tmp/charlie/r1.json",
        cases=[_dependency_case("charlie", "charlie-dep-1", "axios", "1.6.0", "low")],
        sbom_components=[_component("axios", "1.6.0", "MIT")],
        dependency_manifest_entries=[_manifest("axios", "^1.6.0")],
        platform_posture_snapshot=_posture("PASSED"),
    )

    # A suppression decision (low severity → no human-confirmation gate) so the
    # suppression-assembly branch is exercised on the dashboard path.
    db.set_case_decision(
        case_id="charlie-dep-1",
        repo_name="charlie",
        status="accepted_risk",
        note="Accepted risk for now.",
    )

    # Resolution runs: per-repo (top-5) and global (top-50) both read these, and
    # their items collapse into a single batched query.
    db.save_case_resolution_run(_resolution_run("alpha", "alpha-run-1", "alpha-scan-2", "2026-01-02T01:00:00+00:00"))
    db.save_case_resolution_run(_resolution_run("alpha", "alpha-run-2", "alpha-scan-2", "2026-01-02T02:00:00+00:00"))
    db.save_case_resolution_run(_resolution_run("bravo", "bravo-run-1", "bravo-scan-2", "2026-01-02T07:00:00+00:00"))


class _UnbatchedReferenceDB:
    """Proxy that re-expresses the set-based batch reads as the pre-refactor
    per-repo lookups, using the untouched single-scan storage helpers.

    Everything else delegates to the real ``ObservatoryDB``. Feeding this to the
    *same* ``assemble_dashboard_payload`` reproduces the old per-repo data-access
    pattern, so a deep-equal against the real (batched) db proves the batching is
    behaviour-preserving.
    """

    def __init__(self, db: ObservatoryDB) -> None:
        self._db = db

    def __getattr__(self, name: str):
        return getattr(self._db, name)

    def previous_scans_for_latest(self, latest_rows):
        return {
            str(row["id"]): self._db._previous_scan(row["repo_name"], row["started_at"])
            for row in latest_rows
        }

    def findings_for_scans(self, scan_ids):
        return {
            str(scan_id): [
                dict(item)
                for item in self._db.conn.execute(
                    "select * from findings where scan_id = ? order by severity desc, id asc",
                    (str(scan_id),),
                ).fetchall()
            ]
            for scan_id in scan_ids
        }

    def sbom_components_for_scans(self, scan_ids):
        return {str(scan_id): self._db.list_sbom_components(scan_id=str(scan_id)) for scan_id in scan_ids}

    def dependency_manifest_entries_for_scans(self, scan_ids):
        return {
            str(scan_id): self._db.list_dependency_manifest_entries(scan_id=str(scan_id))
            for scan_id in scan_ids
        }

    def dependency_trust_for_scans(self, scan_ids):
        return {
            str(scan_id): self._db.list_dependency_trust_enrichments(scan_id=str(scan_id))
            for scan_id in scan_ids
        }

    def platform_posture_for_scans(self, scan_ids):
        result = {}
        for scan_id in scan_ids:
            rows = self._db.list_platform_posture_snapshots(scan_id=str(scan_id), limit=1)
            result[str(scan_id)] = rows[0] if rows else None
        return result

    def case_resolution_runs_for_dashboard(self, repo_names, *, global_limit=50, per_repo_limit=5):
        global_runs = self._db.list_case_resolution_runs(limit=global_limit)
        runs_by_repo = {
            repo: self._db.list_case_resolution_runs(repo_name=repo, limit=per_repo_limit)
            for repo in dict.fromkeys(repo_names)
        }
        return global_runs, runs_by_repo


def test_batched_payload_deep_equals_unbatched_assembly(tmp_path: Path) -> None:
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        _seed_rich_fixture(db)
        batched = assemble_dashboard_payload(db)
        unbatched = assemble_dashboard_payload(_UnbatchedReferenceDB(db))
    finally:
        db.close()

    # Sanity: the fixture actually produced a multi-repo, content-rich payload,
    # so the equality below is meaningful rather than two empty dicts.
    assert {repo["repo"] for repo in batched["repos"]} == {"alpha", "bravo", "charlie"}
    assert batched["repos"], "fixture should produce repos"
    assert any(repo.get("dependency_trust") for repo in batched["repos"])
    assert any(repo.get("platform_posture") for repo in batched["repos"])
    assert any(repo.get("case_resolution_runs") for repo in batched["repos"])
    assert batched["case_resolution_runs"], "global resolution runs should be present"

    assert batched == unbatched


def _seed_n_repos(db: ObservatoryDB, n: int) -> None:
    """n repos, each with two scans and one resolution run — minimal but enough
    to exercise every batched read path so the query count is comparable."""
    for index in range(n):
        repo = f"repo-{index:03d}"
        db.save_scan(
            scan_id=f"{repo}-scan-1",
            repo_name=repo,
            repo_path=f"/tmp/{repo}",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="full",
            health_score=80,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[_finding(repo, severity="low", category="dependencies", title="dep issue")],
            report_path=f"/tmp/{repo}/r1.json",
            cases=[_dependency_case(repo, f"{repo}-dep-1", "lodash", "4.17.20", "low")],
            sbom_components=[_component("lodash", "4.17.20", "MIT")],
            dependency_manifest_entries=[_manifest("lodash", "^4.17.20")],
        )
        db.save_scan(
            scan_id=f"{repo}-scan-2",
            repo_name=repo,
            repo_path=f"/tmp/{repo}",
            started_at="2026-01-02T00:00:00+00:00",
            finished_at="2026-01-02T00:01:00+00:00",
            profile="full",
            health_score=78,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[_finding(repo, severity="low", category="dependencies", title="dep issue")],
            report_path=f"/tmp/{repo}/r2.json",
            cases=[_dependency_case(repo, f"{repo}-dep-1", "lodash", "4.18.0", "low")],
            sbom_components=[_component("lodash", "4.18.0", "MIT")],
            dependency_manifest_entries=[_manifest("lodash", "^4.18.0")],
            dependency_trust_enrichments=[_trust("lodash", "4.18.0")],
            platform_posture_snapshot=_posture("PASSED"),
        )
        db.save_case_resolution_run(
            _resolution_run(repo, f"{repo}-run-1", f"{repo}-scan-2", "2026-01-02T01:00:00+00:00")
        )


def _trace_dashboard_queries(db: ObservatoryDB) -> list[str]:
    statements: list[str] = []
    db.conn.set_trace_callback(statements.append)
    try:
        db.dashboard_payload()
    finally:
        db.conn.set_trace_callback(None)
    return statements


def test_dashboard_payload_query_count_is_constant_in_repo_count(tmp_path: Path) -> None:
    small = ObservatoryDB(tmp_path / "small.sqlite")
    large = ObservatoryDB(tmp_path / "large.sqlite")
    try:
        _seed_n_repos(small, 5)
        _seed_n_repos(large, 50)
        small_statements = _trace_dashboard_queries(small)
        large_statements = _trace_dashboard_queries(large)
    finally:
        small.close()
        large.close()

    # O(1) in repo count: a 10x larger repo set runs the *same* number of
    # statements (the per-repo fan-out is now set-based).
    assert len(small_statements) == len(large_statements), (
        f"query count grew with repo count: 5 repos -> {len(small_statements)} "
        f"statements, 50 repos -> {len(large_statements)}"
    )

    # The per-run case_resolution_items N+1 is collapsed to a single pull.
    def _items_queries(statements: list[str]) -> int:
        return sum(1 for sql in statements if "case_resolution_items" in sql)

    assert _items_queries(small_statements) == 1
    assert _items_queries(large_statements) == 1

    # And the dependency/findings/trust/posture reads do not scale either.
    for table in ("from findings", "from sbom_components", "from dependency_trust_enrichments", "from platform_posture_snapshots"):
        small_count = sum(1 for sql in small_statements if table in sql)
        large_count = sum(1 for sql in large_statements if table in sql)
        assert small_count == large_count, f"'{table}' query count scaled with repo count"
