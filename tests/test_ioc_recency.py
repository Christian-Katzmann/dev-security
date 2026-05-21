from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os

from security_observatory import cli as cli_module
from security_observatory.cases import build_security_cases
from security_observatory.model import Finding
from security_observatory.recency import (
    enrich_ioc_findings_with_rotation_advice,
    enumerate_rotation_surfaces,
    probe_install_recency,
)
from security_observatory.storage import ObservatoryDB


NOW = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)


def test_install_recency_probe_detects_recent_node_modules_package(tmp_path: Path):
    repo = tmp_path / "repo"
    package_json = repo / "node_modules" / "@scope" / "pkg" / "package.json"
    package_json.parent.mkdir(parents=True)
    package_json.write_text('{"name":"@scope/pkg"}\n', encoding="utf-8")
    _touch(repo / "node_modules" / ".package-lock.json", NOW - timedelta(hours=2))
    _touch(package_json, NOW - timedelta(hours=1))

    assessment = probe_install_recency(repo, ["@scope/pkg"], now=NOW, home=tmp_path / "home")
    fact = assessment.fact_for_package("@scope/pkg")

    assert assessment.project.confidence == "strong"
    assert fact.confidence == "strong"
    assert fact.package_last_install_signal_at is not None
    assert any("node_modules package.json" in item for item in fact.evidence)


def test_install_recency_probe_handles_unknown_stale_and_lockfile_only(tmp_path: Path):
    never_built = tmp_path / "never-built"
    never_built.mkdir()
    never = probe_install_recency(never_built, ["pkg"], now=NOW, home=tmp_path / "home")
    assert never.fact_for_package("pkg").confidence == "unknown"

    stale = tmp_path / "stale"
    _touch(stale / "node_modules" / "pkg" / "package.json", NOW - timedelta(days=60))
    stale_fact = probe_install_recency(stale, ["pkg"], now=NOW, home=tmp_path / "home").fact_for_package("pkg")
    assert stale_fact.confidence == "unknown"
    assert stale_fact.last_install_signal_at is not None

    lockfile_only = tmp_path / "lockfile-only"
    _touch(lockfile_only / "package-lock.json", NOW - timedelta(hours=4))
    weak_fact = probe_install_recency(lockfile_only, ["pkg"], now=NOW, home=tmp_path / "home").fact_for_package("pkg")
    assert weak_fact.confidence == "weak"
    assert weak_fact.package_last_install_signal_at is None


def test_rotation_surface_enumerator_lists_paths_without_values(tmp_path: Path):
    repo = tmp_path / "repo"
    _write(repo / ".env", "PLACEHOLDER=not-a-token\n")
    _write(repo / ".env.local", "LOCAL_PLACEHOLDER=not-a-token\n")
    _write(repo / ".envrc", "export PLACEHOLDER=not-a-token\n")
    _write(repo / ".npmrc", "//registry.example.test/:_authToken=not-a-token\n")
    _write(repo / ".pypirc", "[distutils]\n")
    _write(repo / "mcp.json", json.dumps({"servers": {"demo": {"env": {"NAME": "placeholder"}}}}))
    _write(repo / "mcp.local.json", "{}\n")
    _write(repo / "wrangler.toml", "[vars]\nNAME = \"placeholder\"\n")
    _write(repo / "vercel.json", json.dumps({"env": {"NAME": "placeholder"}}))
    _write(repo / ".github" / "workflows" / "deploy.yml", "env:\n  TOKEN: ${{ secrets.DEPLOY_TOKEN }}\n")
    _write(repo / ".aws" / "credentials", "[default]\nprofile=placeholder\n")
    _write(repo / ".ssh" / "config", "Host example\n  HostName example.test\n")

    surfaces = enumerate_rotation_surfaces(repo)
    rendered = "\n".join(surfaces)

    assert ".env" in surfaces
    assert ".env.local" in surfaces
    assert ".envrc" in surfaces
    assert ".npmrc" in surfaces
    assert ".pypirc" in surfaces
    assert "mcp.json" in surfaces
    assert "mcp.local.json" in surfaces
    assert "wrangler.toml" in surfaces
    assert "vercel.json" in surfaces
    assert ".github/workflows/deploy.yml" in surfaces
    assert ".aws/credentials" in surfaces
    assert ".ssh/config" in surfaces
    assert "DEPLOY_TOKEN" not in rendered
    assert "placeholder" not in rendered
    assert "not-a-token" not in rendered


def test_ioc_case_copy_strong_weak_and_unknown_recency(tmp_path: Path):
    strong_repo = tmp_path / "strong"
    _write(strong_repo / ".env", "PLACEHOLDER=not-a-token\n")
    _touch(strong_repo / "node_modules" / "@scope" / "pkg" / "package.json", NOW - timedelta(hours=1))
    strong_case = _case_for_repo(strong_repo, now=NOW)

    assert "Probably executed" in strong_case.plain_english_risk
    assert strong_case.rotation_surfaces == [".env"]
    assert any("provider first" in step for step in strong_case.fix_steps)

    weak_repo = tmp_path / "weak"
    _write(weak_repo / ".env", "PLACEHOLDER=not-a-token\n")
    _touch(weak_repo / "package-lock.json", NOW - timedelta(hours=1))
    weak_case = _case_for_repo(weak_repo, now=NOW)

    assert "Probably executed" not in weak_case.plain_english_risk
    assert "weak" in weak_case.plain_english_risk
    assert weak_case.rotation_surfaces == []

    unknown_repo = tmp_path / "unknown"
    unknown_repo.mkdir()
    unknown_case = _case_for_repo(unknown_repo, now=NOW)

    assert "Probably executed" not in unknown_case.plain_english_risk
    assert "No recent local install evidence" in unknown_case.plain_english_risk
    assert unknown_case.rotation_surfaces == []


def test_strong_rotation_guidance_persists_and_cli_handoff_dry_run(tmp_path: Path, monkeypatch, capsys):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _write(repo / ".env", "PLACEHOLDER=not-a-token\n")
    _touch(repo / "node_modules" / "@scope" / "pkg" / "package.json", NOW - timedelta(hours=1))
    finding = enrich_ioc_findings_with_rotation_advice([_ioc_finding()], repo, now=NOW)[0]
    cases = build_security_cases([finding], [{"scanner": "ioc-watch", "available": True, "findings": 1}], {"repo": "repo", "repo_path": str(repo)})

    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id="repo-20260520T000000Z",
            repo_name="repo",
            repo_path=str(repo),
            started_at="2026-05-20T12:00:00+00:00",
            finished_at="2026-05-20T12:01:00+00:00",
            profile="ioc",
            health_score=40,
            status="ok",
            scanner_statuses=[{"scanner": "ioc-watch", "available": True, "findings": 1}],
            findings=[finding],
            report_path=str(home / "reports" / "repo" / "normalized-report.json"),
            cases=cases,
        )
        exported = db.scan_export("repo-20260520T000000Z")
    finally:
        db.close()

    assert exported is not None
    assert exported["findings"][0]["install_recency_confidence"] == "strong"
    assert exported["cases"][0]["rotation_surfaces"] == [".env"]

    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))
    exit_code = cli_module.main(["handoff", "repo-20260520T000000Z", "--dry-run"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Probably executed - rotate the following surfaces" in output
    assert ".env" in output
    assert "rotate at the provider first" in output


def _case_for_repo(repo: Path, *, now: datetime):
    finding = enrich_ioc_findings_with_rotation_advice([_ioc_finding()], repo, now=now)[0]
    cases = build_security_cases([finding], [{"scanner": "ioc-watch", "available": True, "findings": 1}], {"repo": repo.name, "repo_path": str(repo)})
    assert len(cases) == 1
    return cases[0]


def _ioc_finding() -> Finding:
    return Finding(
        repo="repo",
        scanner="ioc-watch",
        severity="critical",
        category="supply-chain-ioc",
        title="@scope/pkg 1.2.3 matched named campaign IOC",
        file="package-lock.json",
        package_name="@scope/pkg",
        package_version="1.2.3",
        package_ecosystem="npm",
        ioc_pack_id="test-campaign",
        ioc_source="Fixture Campaign",
        ioc_match_type="exact match",
        ioc_indicator="@scope/pkg@1.2.3",
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _touch(path: Path, when: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("{}\n", encoding="utf-8")
    stamp = when.timestamp()
    os.utime(path, (stamp, stamp))
