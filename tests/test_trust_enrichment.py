from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import json

from security_observatory import cli as cli_module
from security_observatory import enrichment as enrichment_module
from security_observatory.enrichment import enrich_dependency_trust, resolve_source_repo, scorecard_lookup
from security_observatory.scanners import scanner_names_for_profile
from security_observatory.sbom import SBOMComponent
from security_observatory.storage import ObservatoryDB


def test_source_repo_resolution_uses_strong_github_purl():
    resolution = resolve_source_repo(
        {
            "name": "scorecard",
            "version": "5.0.0",
            "ecosystem": "github",
            "package_url": "pkg:github/ossf/scorecard@5.0.0",
        }
    )

    assert resolution.source_repo == "github.com/ossf/scorecard"
    assert resolution.source_repo_url == "https://github.com/ossf/scorecard"
    assert resolution.confidence == "strong"
    assert "Package URL" in resolution.reason


def test_unknown_source_repo_is_visible_but_not_bad_hygiene(tmp_path: Path):
    records = enrich_dependency_trust(
        [
            {
                "name": "lodash",
                "version": "4.17.21",
                "ecosystem": "npm",
                "package_url": "pkg:npm/lodash@4.17.21",
                "component_fingerprint": "lodash-fp",
            }
        ],
        cache_dir=tmp_path,
        allow_network=False,
        now=_now(),
    )

    assert len(records) == 1
    record = records[0]
    assert record.status == "unknown_source"
    assert record.freshness == "unknown"
    assert record.source_repo is None
    assert record.source_repo_confidence == "unknown"
    assert record.scorecard_score is None
    assert record.criticality_score is None
    assert record.scorecard_status == "not_checked"
    assert record.criticality_status == "not_checked"


def test_scorecard_cache_only_marks_stale_data(tmp_path: Path):
    cache_path = tmp_path / "scorecard" / "github.com" / "ossf" / "scorecard.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        json.dumps(
            {
                "source": "https://api.scorecard.dev/projects/github.com/ossf/scorecard",
                "repo": "github.com/ossf/scorecard",
                "score": 8.6,
                "checked_at": (_now() - timedelta(days=10)).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    result = scorecard_lookup(
        "github.com/ossf/scorecard",
        cache_dir=tmp_path,
        allow_network=False,
        now=_now(),
        max_cache_age=timedelta(days=1),
    )

    assert result.score == 8.6
    assert result.freshness == "stale"
    assert result.status == "checked"


def test_cache_only_with_known_source_makes_unavailable_data_visible(tmp_path: Path):
    records = enrich_dependency_trust(
        [
            {
                "name": "scorecard",
                "version": "5.0.0",
                "ecosystem": "github",
                "package_url": "pkg:github/ossf/scorecard@5.0.0",
                "component_fingerprint": "scorecard-fp",
            }
        ],
        cache_dir=tmp_path,
        allow_network=False,
        now=_now(),
    )

    record = records[0]
    assert record.source_repo == "github.com/ossf/scorecard"
    assert record.status == "unavailable"
    assert record.freshness == "unavailable"
    assert record.scorecard_status == "unavailable"
    assert record.criticality_status == "unavailable"
    assert "cache is empty" in (record.error or "")


def test_network_trust_enrichment_uses_static_mock_payloads_and_writes_cache(tmp_path: Path, monkeypatch):
    def fake_fetch_json(url: str, *, timeout_seconds: float):
        if "api.scorecard.dev" in url:
            return {"score": 9.1, "date": "2026-05-04T09:50:31Z"}
        if "storage.googleapis.com/storage/v1" in url:
            return {"items": [{"name": "2026-05-01/criticality.csv", "updated": "2026-05-01T00:00:00Z"}]}
        return None

    def fake_fetch_bytes(url: str, *, timeout_seconds: float):
        return b"repo.url,default_score\nhttps://github.com/ossf/scorecard,0.82\n"

    monkeypatch.setattr(enrichment_module, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(enrichment_module, "_fetch_bytes", fake_fetch_bytes)

    records = enrich_dependency_trust(
        [
            {
                "name": "scorecard",
                "version": "5.0.0",
                "ecosystem": "github",
                "package_url": "pkg:github/ossf/scorecard@5.0.0",
                "component_fingerprint": "scorecard-fp",
            }
        ],
        cache_dir=tmp_path,
        allow_network=True,
        now=_now(),
    )

    record = records[0]
    assert record.status == "checked"
    assert record.freshness == "fresh"
    assert record.scorecard_score == 9.1
    assert record.criticality_score == 0.82
    assert record.checked_at == _now().isoformat()
    assert (tmp_path / "scorecard" / "github.com" / "ossf" / "scorecard.json").exists()
    assert (tmp_path / "criticality" / "github.com" / "ossf" / "scorecard.json").exists()


def test_storage_persists_dependency_trust_records(tmp_path: Path):
    component = SBOMComponent(
        name="scorecard",
        version="5.0.0",
        ecosystem="github",
        component_type="library",
        package_url="pkg:github/ossf/scorecard@5.0.0",
        license="Apache-2.0",
        supplier=None,
        source_path="go.mod",
    )
    trust = enrich_dependency_trust(
        [component],
        cache_dir=tmp_path / "cache",
        allow_network=False,
        now=_now(),
    )[0]
    trust.source_repo = "github.com/ossf/scorecard"
    trust.source_repo_url = "https://github.com/ossf/scorecard"
    trust.source_repo_confidence = "strong"
    trust.status = "stale"
    trust.freshness = "stale"
    trust.scorecard_score = 8.1
    trust.scorecard_status = "checked"
    trust.criticality_score = 0.7
    trust.criticality_status = "checked"
    trust.cache_key = "github.com/ossf/scorecard"

    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260101T000000Z",
            repo_name="repo",
            repo_path="/tmp/repo",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            profile="trust-cache-only",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(tmp_path / "report.json"),
            sbom_components=[component],
            dependency_trust_enrichments=[trust],
        )
        rows = db.list_dependency_trust_enrichments(scan_id="repo-20260101T000000Z")
        payload = db.dashboard_payload()
    finally:
        db.close()

    assert len(rows) == 1
    assert rows[0]["source_repo"] == "github.com/ossf/scorecard"
    assert rows[0]["scorecard_score"] == 8.1
    assert rows[0]["criticality_score"] == 0.7
    assert rows[0]["freshness"] == "stale"
    assert rows[0]["status"] == "stale"
    assert payload["repos"][0]["dependency_trust"][0]["source_repo"] == "github.com/ossf/scorecard"


def test_trust_profile_runs_syft_without_changing_default_profiles():
    trust_args = _args(trust=True)
    default_args = _args()

    assert scanner_names_for_profile(trust_args) == ["syft"]
    assert cli_module.profile_name(trust_args) == "trust"
    assert "syft" in scanner_names_for_profile(default_args)
    assert cli_module.profile_name(default_args) == "default"


def _args(**overrides: bool) -> SimpleNamespace:
    values = {
        "quick": False,
        "code": False,
        "ai": False,
        "deps": False,
        "trust": False,
        "trust_cache_only": False,
        "secrets": False,
        "iac": False,
        "full": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _now() -> datetime:
    return datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)
