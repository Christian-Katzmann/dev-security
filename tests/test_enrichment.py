import security_observatory.enrichment as enrichment_module
from security_observatory.enrichment import (
    _fill_dependency_facts,
    cisa_kev_lookup,
    enrich_dependency_finding,
    extract_fixed_version,
    extract_package_name,
    extract_vulnerability_ids,
    match_dependency_finding_to_component,
)
from security_observatory.model import Finding


def test_extracts_dependency_ids_package_and_fixed_version():
    finding = Finding(
        repo="repo",
        scanner="trivy",
        severity="high",
        category="dependencies",
        title="CVE-2024-12345 and GHSA-abcd-efgh-ijkl in lodash",
        remediation="Upgrade lodash to 4.17.21.",
    )
    raw = {"VulnerabilityID": "PYSEC-2024-12", "PkgName": "lodash", "FixedVersion": "4.17.21"}

    enrichment = enrich_dependency_finding(finding, raw)

    assert enrichment.vulnerability_ids == ["CVE-2024-12345", "GHSA-ABCD-EFGH-IJKL", "PYSEC-2024-12"]
    assert enrichment.vulnerability_id_types["CVE-2024-12345"] == "CVE"
    assert enrichment.package_name == "lodash"
    assert enrichment.fixed_version == "4.17.21"
    assert enrichment.fix_available is True


def test_extractors_work_from_normalized_text_without_raw_report():
    text = "GHSA-1234-abcd-5678 in @scope/pkg is fixed in >=2.0.1"

    assert extract_vulnerability_ids(text) == ["GHSA-1234-ABCD-5678"]
    assert extract_package_name({"title": text}) == "@scope/pkg"
    assert extract_fixed_version({"remediation": text}) == ">=2.0.1"


def test_cisa_kev_unavailable_is_not_treated_as_not_exploited(tmp_path):
    result = cisa_kev_lookup(["CVE-2024-12345"], cache_dir=tmp_path, allow_network=False)

    assert result["status"] == "not_checked"
    assert result["known_exploited"] is None


def test_default_scan_path_never_enables_kev_or_epss(monkeypatch):
    """The default scan path (``_fill_dependency_facts``) must pass neither
    online-check flag, so KEV/EPSS stay designed-but-not-wired (S-008). If a
    future change wires them on without an explicit opt-in, the network
    lookups would fire here and this test fails.
    """
    def _boom(*_args, **_kwargs):  # pragma: no cover - only runs on regression
        raise AssertionError("default scan path must not perform KEV/EPSS network lookups")

    monkeypatch.setattr(enrichment_module, "cisa_kev_lookup", _boom)
    monkeypatch.setattr(enrichment_module, "epss_lookup", _boom)

    finding = Finding(
        repo="repo",
        scanner="trivy",
        severity="high",
        category="dependencies",
        title="CVE-2024-12345 in lodash",
        remediation="Upgrade lodash to 4.17.21.",
    )
    _fill_dependency_facts(finding)

    # And the enrichment helper itself defaults both flags off.
    result = enrich_dependency_finding(finding)
    assert result.cisa_kev == {"status": "not_checked", "known_exploited": None}
    assert result.epss == {"status": "not_checked"}


def test_cisa_kev_uses_local_cache(tmp_path):
    (tmp_path / "cisa-kev.json").write_text(
        '{"vulnerabilities": [{"cveID": "CVE-2024-12345"}]}',
        encoding="utf-8",
    )

    result = cisa_kev_lookup(["CVE-2024-12345"], cache_dir=tmp_path, allow_network=False)

    assert result["status"] == "checked"
    assert result["known_exploited"] is True
    assert result["matched_ids"] == ["CVE-2024-12345"]


def test_strong_component_match_uses_exact_package_url():
    finding = Finding(
        repo="repo",
        scanner="trivy",
        severity="high",
        category="dependencies",
        title="CVE-2026-1000 in lodash",
        package_name="lodash",
        package_version="4.17.20",
        package_ecosystem="npm",
        package_url="pkg:npm/lodash@4.17.20",
    )

    match = match_dependency_finding_to_component(finding, [_component("lodash", "4.17.20", "npm")])

    assert match.confidence == "strong"
    assert match.component_fingerprint == "lodash-4.17.20"
    assert "Exact package URL" in match.reason


def test_weak_component_match_does_not_claim_proof_without_ecosystem():
    finding = Finding(
        repo="repo",
        scanner="grype",
        severity="high",
        category="dependencies",
        title="CVE-2026-1000 in lodash",
        package_name="lodash",
        package_version="4.17.20",
    )

    match = match_dependency_finding_to_component(finding, [_component("lodash", "4.17.20", "npm")])

    assert match.confidence == "weak"
    assert "not confirmed" in match.reason


def test_package_rename_ambiguity_is_labeled_uncertain():
    finding = Finding(
        repo="repo",
        scanner="grype",
        severity="high",
        category="dependencies",
        title="CVE-2026-1000 in renamed-package",
        package_name="renamed-package",
        package_version="1.0.0",
    )

    match = match_dependency_finding_to_component(
        finding,
        [
            _component("renamed-package", "1.0.0", "npm"),
            _component("renamed-package", "1.0.0", "pypi"),
        ],
    )

    assert match.confidence == "uncertain"
    assert "exact package match is uncertain" in match.reason


def test_missing_version_keeps_package_url_match_weak():
    finding = Finding(
        repo="repo",
        scanner="trivy",
        severity="high",
        category="dependencies",
        title="CVE-2026-1000 in lodash",
        package_name="lodash",
        package_url="pkg:npm/lodash",
    )

    match = match_dependency_finding_to_component(finding, [_component("lodash", "4.17.20", "npm")])

    assert match.confidence == "weak"
    assert "version was missing or different" in match.reason


def test_missing_purl_can_still_match_by_name_ecosystem_and_version():
    finding = Finding(
        repo="repo",
        scanner="osv-scanner",
        severity="high",
        category="dependencies",
        title="CVE-2026-1000 in lodash",
        package_name="lodash",
        package_version="4.17.20",
        package_ecosystem="npm",
    )
    component = _component("lodash", "4.17.20", "npm")
    component.pop("package_url")

    match = match_dependency_finding_to_component(finding, [component])

    assert match.confidence == "strong"
    assert "Package name, ecosystem, and version matched" in match.reason


def test_unknown_ecosystem_is_a_weak_component_match():
    finding = Finding(
        repo="repo",
        scanner="grype",
        severity="high",
        category="dependencies",
        title="CVE-2026-1000 in lodash",
        package_name="lodash",
        package_version="4.17.20",
    )
    component = _component("lodash", "4.17.20", "npm")
    component["ecosystem"] = None
    component.pop("package_url")

    match = match_dependency_finding_to_component(finding, [component])

    assert match.confidence == "weak"
    assert "ecosystem was not confirmed" in match.reason


def test_missing_component_match_is_explicit():
    finding = Finding(
        repo="repo",
        scanner="osv-scanner",
        severity="high",
        category="dependencies",
        title="CVE-2026-1000 in lodash",
        package_name="lodash",
        package_version="4.17.20",
        package_ecosystem="npm",
    )

    match = match_dependency_finding_to_component(finding, [_component("react", "19.0.1", "npm")])

    assert match.confidence == "missing"
    assert "No package-list entry matched" in match.reason


def _component(name: str, version: str, ecosystem: str) -> dict[str, str]:
    return {
        "name": name,
        "version": version,
        "ecosystem": ecosystem,
        "component_type": "library",
        "package_url": f"pkg:{ecosystem}/{name}@{version}",
        "component_fingerprint": f"{name}-{version}",
    }
