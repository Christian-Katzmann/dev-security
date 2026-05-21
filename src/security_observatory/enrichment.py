from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import csv
import gzip
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .model import Finding, redact_text


CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://api.first.org/data/v1/epss"
SCORECARD_API_TEMPLATE = "https://api.scorecard.dev/projects/{repo}"
CRITICALITY_OBJECTS_URL = (
    "https://storage.googleapis.com/storage/v1/b/ossf-criticality-score/o"
    "?fields=items(name,updated)&maxResults=1000"
)
CRITICALITY_OBJECT_BASE_URL = "https://storage.googleapis.com/ossf-criticality-score/"
SCORECARD_CACHE_MAX_AGE = timedelta(days=7)
CRITICALITY_CACHE_MAX_AGE = timedelta(days=30)

CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
GHSA_RE = re.compile(r"\bGHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}\b", re.IGNORECASE)
OSV_RE = re.compile(
    r"\b(?:OSV|PYSEC|RUSTSEC|GO|MAL|GSD|BIT)-\d{4}[-.][0-9A-Za-z_.-]+\b",
    re.IGNORECASE,
)
PACKAGE_RE = re.compile(
    r"(?:\bin\s+|\bpackage\s+|\bpkg(?:name)?[=:]\s*)(@?[A-Za-z0-9][A-Za-z0-9_.:/@+-]*)",
    re.IGNORECASE,
)
FIXED_VERSION_RE = re.compile(
    r"\b(?:fixed|patched|resolved|upgrade(?:d)?|update(?:d)?)\s+(?:[A-Za-z0-9_.:/@+-]+\s+)?(?:in|to|at|with)?\s*"
    r"(?:version\s*)?([<>=~^]*\s*[0-9][A-Za-z0-9.*_+~:-]*(?:\s*(?:,|or|and)\s*[<>=~^]*\s*[0-9][A-Za-z0-9.*_+~:-]*)*)",
    re.IGNORECASE,
)
GITHUB_REPO_RE = re.compile(
    r"^(?:https?://|git\+https://|ssh://git@|git@)?github\.com[:/](?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)"
    r"(?:\.git)?(?:[/?#].*)?$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class DependencyEnrichment:
    vulnerability_ids: list[str] = field(default_factory=list)
    vulnerability_id_types: dict[str, str] = field(default_factory=dict)
    package_name: str | None = None
    fixed_version: str | None = None
    fix_available: bool = False
    cisa_kev: dict[str, Any] = field(default_factory=lambda: {"status": "not_checked", "known_exploited": None})
    epss: dict[str, Any] = field(default_factory=lambda: {"status": "not_checked"})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DependencyComponentMatch:
    confidence: str
    reason: str
    component_fingerprint: str | None = None
    component_package_key: str | None = None
    component: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceRepoResolution:
    source_repo: str | None
    source_repo_url: str | None
    confidence: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TrustLookupResult:
    status: str
    score: float | None = None
    checked_at: str | None = None
    freshness: str = "unavailable"
    source: str | None = None
    reason: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DependencyTrustRecord:
    component_fingerprint: str | None
    component_package_key: str | None
    package_name: str | None
    package_version: str | None
    package_ecosystem: str | None
    package_url: str | None
    source_repo: str | None
    source_repo_url: str | None
    source_repo_confidence: str
    source_repo_reason: str
    scorecard_score: float | None
    scorecard_status: str
    criticality_score: float | None
    criticality_status: str
    checked_at: str | None
    freshness: str
    status: str
    cache_key: str | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def enrich_dependency_finding(
    finding: Finding | dict[str, Any],
    raw: Any | None = None,
    *,
    cache_dir: Path | None = None,
    check_cisa_kev: bool = False,
    check_epss: bool = False,
) -> DependencyEnrichment:
    """Extract dependency facts without making scan completion depend on network calls."""
    texts = _texts_from(finding, raw)
    ids = extract_vulnerability_ids(*texts)
    fixed_version = extract_fixed_version(finding, raw)
    enrichment = DependencyEnrichment(
        vulnerability_ids=ids,
        vulnerability_id_types={vuln_id: vulnerability_id_type(vuln_id) for vuln_id in ids},
        package_name=extract_package_name(finding, raw),
        fixed_version=fixed_version,
        fix_available=bool(fixed_version),
    )
    if check_cisa_kev:
        enrichment.cisa_kev = cisa_kev_lookup(ids, cache_dir=cache_dir, allow_network=True)
    if check_epss:
        enrichment.epss = epss_lookup([vuln_id for vuln_id in ids if vulnerability_id_type(vuln_id) == "CVE"], allow_network=True)
    return enrichment


def enrich_dependency_trust(
    components: list[Any],
    *,
    cache_dir: Path,
    allow_network: bool = False,
    now: datetime | None = None,
    scorecard_max_cache_age: timedelta = SCORECARD_CACHE_MAX_AGE,
    criticality_max_cache_age: timedelta = CRITICALITY_CACHE_MAX_AGE,
    criticality_data_path: Path | None = None,
    timeout_seconds: float = 6.0,
) -> list[DependencyTrustRecord]:
    """Attach optional, cache-backed project trust facts to SBOM components.

    The default scan path does not call this function. Callers must explicitly
    opt in because fresh Scorecard and criticality data can require network
    access and because unknown source repositories are normal for many packages.
    """
    checked_now = now or datetime.now(timezone.utc)
    scorecard_cache: dict[str, TrustLookupResult] = {}
    criticality_cache: dict[str, TrustLookupResult] = {}
    records: list[DependencyTrustRecord] = []

    for component in components:
        component_dict = _component_dict(component)
        resolution = resolve_source_repo(component_dict)
        if not resolution.source_repo:
            records.append(_unknown_source_trust_record(component_dict, resolution, checked_now))
            continue

        source_repo = resolution.source_repo
        if source_repo not in scorecard_cache:
            scorecard_cache[source_repo] = scorecard_lookup(
                source_repo,
                cache_dir=cache_dir,
                allow_network=allow_network,
                now=checked_now,
                max_cache_age=scorecard_max_cache_age,
                timeout_seconds=timeout_seconds,
            )
        if source_repo not in criticality_cache:
            criticality_cache[source_repo] = criticality_lookup(
                source_repo,
                cache_dir=cache_dir,
                allow_network=allow_network,
                now=checked_now,
                max_cache_age=criticality_max_cache_age,
                criticality_data_path=criticality_data_path,
                timeout_seconds=timeout_seconds,
            )
        records.append(
            _trust_record(
                component_dict,
                resolution,
                scorecard_cache[source_repo],
                criticality_cache[source_repo],
                checked_now,
            )
        )
    return records


def resolve_source_repo(component: Any) -> SourceRepoResolution:
    """Resolve the GitHub source repo for a component when evidence is strong.

    Fallback behavior is deliberately conservative: if the component only gives
    a registry package name such as an npm or PyPI package, Observatory marks
    the source as unknown instead of treating missing project trust data as a
    negative signal.
    """
    data = _component_dict(component)
    package_url = _normalize_purl(data.get("package_url"))
    purl_type, purl_path = _purl_type_and_path(package_url)

    if purl_type == "github" and purl_path:
        repo = _repo_from_owner_repo_path(purl_path)
        if repo:
            return _source_resolution(repo, "strong", "Package URL directly names a GitHub repository.")

    if purl_type in {"golang", "go"} and purl_path.startswith("github.com/"):
        repo = _repo_from_github_path(purl_path)
        if repo:
            return _source_resolution(repo, "strong", "Go package URL starts with a GitHub module path.")

    for key in ("source_repo", "repository", "repository_url", "vcs_url", "homepage"):
        repo = _normalize_github_repo(data.get(key))
        if repo:
            return _source_resolution(repo, "strong", f"Component metadata includes {key}.")

    ecosystem = _component_value(data.get("ecosystem") or purl_type)
    name = str(data.get("name") or "").strip()
    if ecosystem in {"go", "golang"}:
        repo = _normalize_github_repo(name)
        if repo:
            return _source_resolution(repo, "strong", "Go package name starts with a GitHub module path.")

    return SourceRepoResolution(
        source_repo=None,
        source_repo_url=None,
        confidence="unknown",
        reason="No reliable GitHub source repository was available in the package metadata.",
    )


def scorecard_lookup(
    source_repo: str,
    *,
    cache_dir: Path,
    allow_network: bool = False,
    now: datetime | None = None,
    max_cache_age: timedelta = SCORECARD_CACHE_MAX_AGE,
    timeout_seconds: float = 6.0,
) -> TrustLookupResult:
    checked_now = now or datetime.now(timezone.utc)
    repo = _normalize_github_repo(source_repo)
    if not repo:
        return TrustLookupResult(status="unknown_source", checked_at=checked_now.isoformat(), freshness="unknown", reason="not a GitHub repo")

    cache_path = _trust_cache_path(cache_dir, "scorecard", repo)
    cached = _read_trust_cache(cache_path, now=checked_now, max_cache_age=max_cache_age)
    if cached and cached[1] == "fresh":
        return _scorecard_result_from_cache(cached[0], freshness="fresh")
    if not allow_network:
        if cached:
            return _scorecard_result_from_cache(cached[0], freshness="stale")
        return TrustLookupResult(
            status="unavailable",
            checked_at=checked_now.isoformat(),
            freshness="unavailable",
            source=_scorecard_url(repo),
            reason="Scorecard cache is empty and network enrichment was not requested.",
        )

    payload = _fetch_json(_scorecard_url(repo), timeout_seconds=timeout_seconds)
    score = _float(payload.get("score")) if isinstance(payload, dict) else None
    if payload is not None and score is not None:
        cache_payload = {
            "source": _scorecard_url(repo),
            "repo": repo,
            "score": score,
            "checked_at": checked_now.isoformat(),
            "payload": payload,
        }
        _write_trust_cache(cache_path, cache_payload)
        return TrustLookupResult(
            status="checked",
            score=score,
            checked_at=checked_now.isoformat(),
            freshness="fresh",
            source=_scorecard_url(repo),
        )
    if cached:
        return _scorecard_result_from_cache(cached[0], freshness="stale", reason="Scorecard refresh failed; using stale cache.")
    return TrustLookupResult(
        status="unavailable",
        checked_at=checked_now.isoformat(),
        freshness="unavailable",
        source=_scorecard_url(repo),
        reason="Scorecard data unavailable.",
    )


def criticality_lookup(
    source_repo: str,
    *,
    cache_dir: Path,
    allow_network: bool = False,
    now: datetime | None = None,
    max_cache_age: timedelta = CRITICALITY_CACHE_MAX_AGE,
    criticality_data_path: Path | None = None,
    timeout_seconds: float = 6.0,
) -> TrustLookupResult:
    checked_now = now or datetime.now(timezone.utc)
    repo = _normalize_github_repo(source_repo)
    if not repo:
        return TrustLookupResult(status="unknown_source", checked_at=checked_now.isoformat(), freshness="unknown", reason="not a GitHub repo")

    cache_path = _trust_cache_path(cache_dir, "criticality", repo)
    cached = _read_trust_cache(cache_path, now=checked_now, max_cache_age=max_cache_age)
    if cached and cached[1] == "fresh":
        return _criticality_result_from_cache(cached[0], freshness="fresh")
    if criticality_data_path is not None:
        score = _criticality_score_from_csv_bytes(_read_bytes(criticality_data_path), repo)
        if score is not None:
            cache_payload = {
                "source": str(criticality_data_path),
                "repo": repo,
                "score": score,
                "checked_at": checked_now.isoformat(),
            }
            _write_trust_cache(cache_path, cache_payload)
            return TrustLookupResult(
                status="checked",
                score=score,
                checked_at=checked_now.isoformat(),
                freshness="fresh",
                source=str(criticality_data_path),
            )
        if cached:
            return _criticality_result_from_cache(cached[0], freshness="stale", reason="Static criticality data did not include this repo.")
        return TrustLookupResult(
            status="not_found",
            checked_at=checked_now.isoformat(),
            freshness="unavailable",
            source=str(criticality_data_path),
            reason="Repository was not found in the criticality data.",
        )
    if not allow_network:
        if cached:
            return _criticality_result_from_cache(cached[0], freshness="stale")
        return TrustLookupResult(
            status="unavailable",
            checked_at=checked_now.isoformat(),
            freshness="unavailable",
            source="OpenSSF Criticality Score public data",
            reason="Criticality cache is empty and network enrichment was not requested.",
        )

    score, source, reason = _fetch_criticality_score_from_public_data(repo, timeout_seconds=timeout_seconds)
    if score is not None:
        cache_payload = {
            "source": source,
            "repo": repo,
            "score": score,
            "checked_at": checked_now.isoformat(),
        }
        _write_trust_cache(cache_path, cache_payload)
        return TrustLookupResult(
            status="checked",
            score=score,
            checked_at=checked_now.isoformat(),
            freshness="fresh",
            source=source,
        )
    if cached:
        return _criticality_result_from_cache(cached[0], freshness="stale", reason=reason or "Criticality refresh failed; using stale cache.")
    status = "not_found" if reason and "not found" in reason.lower() else "unavailable"
    return TrustLookupResult(
        status=status,
        checked_at=checked_now.isoformat(),
        freshness="unavailable",
        source=source,
        reason=reason or "Criticality data unavailable.",
    )


def correlate_dependency_findings(
    findings: list[Finding],
    components: list[Any],
) -> list[Finding]:
    """Attach explainable SBOM component matches to dependency findings."""
    component_dicts = [_component_dict(component) for component in components]
    for finding in findings:
        if finding.category != "dependencies":
            continue
        _fill_dependency_facts(finding)
        match = match_dependency_finding_to_component(finding, component_dicts)
        finding.component_fingerprint = match.component_fingerprint
        finding.component_package_key = match.component_package_key
        finding.component_match_confidence = match.confidence
        finding.component_match_reason = match.reason
    return findings


def match_dependency_finding_to_component(
    finding: Finding | dict[str, Any],
    components: list[Any],
) -> DependencyComponentMatch:
    component_dicts = [_component_dict(component) for component in components]
    if not component_dicts:
        return DependencyComponentMatch(confidence="missing", reason="No package list was available for this scan.")

    finding_purl = _normalize_purl(_get(finding, "package_url"))
    finding_purl_base = _purl_without_version(finding_purl)
    finding_name = _component_value(_get(finding, "package_name") or extract_package_name(finding))
    finding_version = _component_value(_get(finding, "package_version"))
    finding_ecosystem = _component_value(_get(finding, "package_ecosystem") or _ecosystem_from_purl(finding_purl))

    if finding_purl:
        for component in component_dicts:
            component_purl = _normalize_purl(component.get("package_url"))
            if component_purl and component_purl == finding_purl:
                return _component_match(component, "strong", "Exact package URL matched the package list.")

        for component in component_dicts:
            component_purl = _normalize_purl(component.get("package_url"))
            if component_purl and _purl_without_version(component_purl) == finding_purl_base:
                component_version = _component_value(component.get("version"))
                if finding_version and component_version and finding_version == component_version:
                    return _component_match(component, "strong", "Package URL and installed version matched the package list.")
                return _component_match(component, "weak", "Package URL name matched, but the version was missing or different.")

    candidates = []
    for component in component_dicts:
        component_name = _component_value(component.get("name"))
        component_version = _component_value(component.get("version"))
        component_ecosystem = _component_value(component.get("ecosystem") or _ecosystem_from_purl(component.get("package_url")))
        if finding_name and finding_version and finding_ecosystem:
            if component_name == finding_name and component_version == finding_version and component_ecosystem == finding_ecosystem:
                return _component_match(component, "strong", "Package name, ecosystem, and version matched the package list.")
        if finding_name and finding_version and component_name == finding_name and component_version == finding_version:
            candidates.append((component, "Package name and version matched, but the ecosystem was not confirmed."))
        elif finding_name and finding_ecosystem and component_name == finding_name and component_ecosystem == finding_ecosystem:
            candidates.append((component, "Package name and ecosystem matched, but the installed version was not confirmed."))

    if len(candidates) == 1:
        component, reason = candidates[0]
        return _component_match(component, "weak", reason)
    if len(candidates) > 1:
        return DependencyComponentMatch(confidence="uncertain", reason="Multiple package-list entries looked similar, so the exact package match is uncertain.")
    return DependencyComponentMatch(confidence="missing", reason="No package-list entry matched this dependency finding.")


def extract_vulnerability_ids(*values: Any) -> list[str]:
    text = "\n".join(_stringify(value) for value in values if value is not None)
    ids: list[str] = []
    for regex in (CVE_RE, GHSA_RE, OSV_RE):
        ids.extend(match.group(0).upper() for match in regex.finditer(text))
    return sorted(dict.fromkeys(ids))


def vulnerability_id_type(vulnerability_id: str) -> str:
    value = vulnerability_id.upper()
    if CVE_RE.fullmatch(value):
        return "CVE"
    if GHSA_RE.fullmatch(value):
        return "GHSA"
    return "OSV"


def extract_package_name(finding: Finding | dict[str, Any], raw: Any | None = None) -> str | None:
    direct = _first_text(
        _deep_get(raw, "PkgName"),
        _deep_get(raw, "pkgName"),
        _deep_get(raw, "package.name"),
        _deep_get(raw, "artifact.name"),
        _deep_get(raw, "Package"),
        _deep_get(raw, "name"),
        _get(finding, "package_name"),
    )
    if direct:
        return _clean_package(direct)
    for text in _texts_from(finding, raw):
        match = PACKAGE_RE.search(text)
        if match:
            return _clean_package(match.group(1))
    return None


def extract_fixed_version(finding: Finding | dict[str, Any], raw: Any | None = None) -> str | None:
    direct = _first_text(
        _deep_get(raw, "FixedVersion"),
        _deep_get(raw, "fixedVersion"),
        _deep_get(raw, "fix.version"),
        _deep_get(raw, "fix.versions"),
        _deep_get(raw, "advisory.fixed_version"),
        _get(finding, "fixed_version"),
    )
    if direct:
        return _clean_version_text(direct)
    for text in _texts_from(finding, raw):
        match = FIXED_VERSION_RE.search(text)
        if match:
            return _clean_version_text(match.group(1))
    return None


def _fill_dependency_facts(finding: Finding) -> None:
    enrichment = enrich_dependency_finding(finding)
    if not finding.vulnerability_id and enrichment.vulnerability_ids:
        finding.vulnerability_id = enrichment.vulnerability_ids[0]
    if not finding.package_name and enrichment.package_name:
        finding.package_name = enrichment.package_name
    if not finding.fixed_version and enrichment.fixed_version:
        finding.fixed_version = enrichment.fixed_version
    if finding.package_url and not finding.package_ecosystem:
        finding.package_ecosystem = _ecosystem_from_purl(finding.package_url)


def _component_match(component: dict[str, Any], confidence: str, reason: str) -> DependencyComponentMatch:
    return DependencyComponentMatch(
        confidence=confidence,
        reason=reason,
        component_fingerprint=_first_text(component.get("component_fingerprint")),
        component_package_key=_component_package_key(component),
        component=component,
    )


def _component_dict(component: Any) -> dict[str, Any]:
    if isinstance(component, dict):
        return dict(component)
    if hasattr(component, "to_dict"):
        data = component.to_dict()
        return dict(data) if isinstance(data, dict) else {}
    return {}


def _normalize_purl(value: Any) -> str | None:
    text = _first_text(value)
    if not text or not text.startswith("pkg:"):
        return None
    return urllib.parse.unquote(text).strip()


def _ecosystem_from_purl(package_url: Any) -> str | None:
    purl = _normalize_purl(package_url)
    if not purl:
        return None
    tail = purl[4:]
    return tail.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0] or None


def _purl_without_version(package_url: str | None) -> str | None:
    if not package_url:
        return None
    base = package_url.split("?", 1)[0].split("#", 1)[0]
    if "@" not in base:
        return base
    head, tail = base.rsplit("@", 1)
    return head if "/" not in tail else base


def _component_package_key(component: dict[str, Any]) -> str | None:
    package_url = _normalize_purl(component.get("package_url"))
    if package_url:
        return f"purl|{_purl_without_version(package_url).casefold()}"
    ecosystem = _component_value(component.get("ecosystem"))
    component_type = _component_value(component.get("component_type"))
    name = _component_value(component.get("name"))
    if any((ecosystem, component_type, name)):
        return "|".join(["component", ecosystem, component_type, name])
    bom_ref = _component_value(component.get("bom_ref"))
    if bom_ref:
        return f"bom-ref|{bom_ref}"
    fingerprint = _component_value(component.get("component_fingerprint"))
    return f"fingerprint|{fingerprint}" if fingerprint else None


def _component_value(value: Any) -> str:
    return str(value or "").strip().casefold()


def cisa_kev_lookup(
    vulnerability_ids: list[str],
    *,
    cache_dir: Path | None = None,
    allow_network: bool = False,
    timeout_seconds: float = 4.0,
    max_cache_age: timedelta = timedelta(hours=24),
) -> dict[str, Any]:
    cves = sorted({item.upper() for item in vulnerability_ids if vulnerability_id_type(item) == "CVE"})
    if not cves:
        return {"status": "not_checked", "known_exploited": None, "matched_ids": [], "reason": "no CVE id"}

    payload = _read_fresh_kev_cache(cache_dir, max_cache_age)
    if payload is None and allow_network:
        payload = _fetch_json(CISA_KEV_URL, timeout_seconds=timeout_seconds)
        if payload is not None and cache_dir is not None:
            _write_kev_cache(cache_dir, payload)
    if payload is None:
        return {"status": "not_checked", "known_exploited": None, "matched_ids": [], "reason": "KEV data unavailable"}

    known = {
        str(item.get("cveID", "")).upper(): item
        for item in payload.get("vulnerabilities", [])
        if isinstance(item, dict) and item.get("cveID")
    }
    matched = [cve for cve in cves if cve in known]
    return {
        "status": "checked",
        "known_exploited": bool(matched),
        "matched_ids": matched,
        "source": CISA_KEV_URL,
    }


def epss_lookup(
    cve_ids: list[str],
    *,
    allow_network: bool = False,
    timeout_seconds: float = 4.0,
) -> dict[str, Any]:
    cves = sorted({item.upper() for item in cve_ids if CVE_RE.fullmatch(item.upper())})
    if not cves:
        return {"status": "not_checked", "reason": "no CVE id"}
    if not allow_network:
        return {"status": "not_checked", "reason": "EPSS lookup not requested"}

    url = f"{EPSS_URL}?{urllib.parse.urlencode({'cve': ','.join(cves)})}"
    payload = _fetch_json(url, timeout_seconds=timeout_seconds)
    if payload is None:
        return {"status": "not_checked", "reason": "EPSS data unavailable"}
    scores: dict[str, float] = {}
    for item in payload.get("data", []):
        if not isinstance(item, dict) or not item.get("cve"):
            continue
        try:
            scores[str(item["cve"]).upper()] = float(item.get("epss", 0))
        except (TypeError, ValueError):
            continue
    return {"status": "checked", "scores": scores, "source": EPSS_URL}


def _unknown_source_trust_record(
    component: dict[str, Any],
    resolution: SourceRepoResolution,
    now: datetime,
) -> DependencyTrustRecord:
    return DependencyTrustRecord(
        component_fingerprint=_first_text(component.get("component_fingerprint")),
        component_package_key=_component_package_key(component),
        package_name=_first_text(component.get("name")),
        package_version=_first_text(component.get("version")),
        package_ecosystem=_first_text(component.get("ecosystem")),
        package_url=_first_text(component.get("package_url")),
        source_repo=None,
        source_repo_url=None,
        source_repo_confidence=resolution.confidence,
        source_repo_reason=resolution.reason,
        scorecard_score=None,
        scorecard_status="not_checked",
        criticality_score=None,
        criticality_status="not_checked",
        checked_at=now.isoformat(),
        freshness="unknown",
        status="unknown_source",
        cache_key=None,
    )


def _trust_record(
    component: dict[str, Any],
    resolution: SourceRepoResolution,
    scorecard: TrustLookupResult,
    criticality: TrustLookupResult,
    now: datetime,
) -> DependencyTrustRecord:
    status = _combined_trust_status(scorecard, criticality)
    freshness = _combined_freshness(scorecard, criticality)
    checked_at = _latest_checked_at(scorecard.checked_at, criticality.checked_at) or now.isoformat()
    error = "; ".join(
        reason
        for reason in (scorecard.reason or scorecard.error, criticality.reason or criticality.error)
        if reason and reason != "Repository was not found in the criticality data."
    )
    return DependencyTrustRecord(
        component_fingerprint=_first_text(component.get("component_fingerprint")),
        component_package_key=_component_package_key(component),
        package_name=_first_text(component.get("name")),
        package_version=_first_text(component.get("version")),
        package_ecosystem=_first_text(component.get("ecosystem")),
        package_url=_first_text(component.get("package_url")),
        source_repo=resolution.source_repo,
        source_repo_url=resolution.source_repo_url,
        source_repo_confidence=resolution.confidence,
        source_repo_reason=resolution.reason,
        scorecard_score=scorecard.score,
        scorecard_status=scorecard.status,
        criticality_score=criticality.score,
        criticality_status=criticality.status,
        checked_at=checked_at,
        freshness=freshness,
        status=status,
        cache_key=resolution.source_repo,
        error=error or None,
    )


def _combined_trust_status(scorecard: TrustLookupResult, criticality: TrustLookupResult) -> str:
    statuses = {scorecard.status, criticality.status}
    if statuses == {"checked"}:
        return "checked"
    if "checked" in statuses:
        return "stale" if "stale" in {scorecard.freshness, criticality.freshness} else "partial"
    if "stale" in {scorecard.freshness, criticality.freshness}:
        return "stale"
    if statuses <= {"not_found", "unavailable"} and "not_found" in statuses:
        return "unavailable"
    return "unavailable"


def _combined_freshness(scorecard: TrustLookupResult, criticality: TrustLookupResult) -> str:
    freshnesses = {scorecard.freshness, criticality.freshness}
    if "stale" in freshnesses:
        return "stale"
    if "fresh" in freshnesses:
        return "fresh"
    if "unknown" in freshnesses:
        return "unknown"
    return "unavailable"


def _latest_checked_at(*values: str | None) -> str | None:
    clean = sorted(value for value in values if value)
    return clean[-1] if clean else None


def _source_resolution(source_repo: str, confidence: str, reason: str) -> SourceRepoResolution:
    repo = _normalize_github_repo(source_repo)
    if not repo:
        return SourceRepoResolution(None, None, "unknown", "GitHub source repository could not be normalized.")
    return SourceRepoResolution(
        source_repo=repo,
        source_repo_url=f"https://{repo}",
        confidence=confidence,
        reason=reason,
    )


def _normalize_github_repo(value: Any) -> str | None:
    text = _first_text(value)
    if not text:
        return None
    text = text.strip()
    if text.startswith("github.com/"):
        candidate = text
    else:
        candidate = text.removeprefix("git+")
    match = GITHUB_REPO_RE.match(candidate)
    if not match:
        return None
    owner = match.group("owner").strip()
    repo = match.group("repo").strip().removesuffix(".git")
    if not owner or not repo:
        return None
    return f"github.com/{owner}/{repo}"


def _purl_type_and_path(package_url: str | None) -> tuple[str | None, str]:
    purl = _normalize_purl(package_url)
    if not purl:
        return None, ""
    body = purl[4:].split("?", 1)[0].split("#", 1)[0]
    if "/" not in body:
        return body.casefold(), ""
    purl_type, path = body.split("/", 1)
    if "@" in path:
        path = path.rsplit("@", 1)[0]
    return purl_type.casefold(), path.strip("/")


def _repo_from_owner_repo_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        return None
    return _normalize_github_repo(f"github.com/{parts[0]}/{parts[1]}")


def _repo_from_github_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 3 or parts[0].casefold() != "github.com":
        return None
    return _normalize_github_repo("/".join(parts[:3]))


def _scorecard_url(source_repo: str) -> str:
    return SCORECARD_API_TEMPLATE.format(repo=urllib.parse.quote(source_repo, safe="/."))


def _trust_cache_path(cache_dir: Path, namespace: str, source_repo: str) -> Path:
    return cache_dir / namespace / f"{source_repo}.json"


def _read_trust_cache(path: Path, *, now: datetime, max_cache_age: timedelta) -> tuple[dict[str, Any], str] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    checked_at = _parse_datetime(data.get("checked_at")) or datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    freshness = "fresh" if now - checked_at <= max_cache_age else "stale"
    return data, freshness


def _write_trust_cache(path: Path, payload: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    except OSError:
        return


def _scorecard_result_from_cache(
    payload: dict[str, Any],
    *,
    freshness: str,
    reason: str | None = None,
) -> TrustLookupResult:
    score = _float(payload.get("score"))
    return TrustLookupResult(
        status="checked" if freshness == "fresh" else "checked",
        score=score,
        checked_at=_first_text(payload.get("checked_at")),
        freshness=freshness,
        source=_first_text(payload.get("source")),
        reason=reason,
    )


def _criticality_result_from_cache(
    payload: dict[str, Any],
    *,
    freshness: str,
    reason: str | None = None,
) -> TrustLookupResult:
    score = _float(payload.get("score"))
    return TrustLookupResult(
        status="checked" if score is not None else "unavailable",
        score=score,
        checked_at=_first_text(payload.get("checked_at")),
        freshness=freshness,
        source=_first_text(payload.get("source")),
        reason=reason,
    )


def _fetch_criticality_score_from_public_data(
    source_repo: str,
    *,
    timeout_seconds: float,
) -> tuple[float | None, str | None, str | None]:
    objects = _fetch_json(CRITICALITY_OBJECTS_URL, timeout_seconds=timeout_seconds)
    object_name = _latest_criticality_object(objects)
    if not object_name:
        return None, CRITICALITY_OBJECTS_URL, "Criticality public data index unavailable."
    object_url = f"{CRITICALITY_OBJECT_BASE_URL}{urllib.parse.quote(object_name, safe='/')}"
    payload = _fetch_bytes(object_url, timeout_seconds=timeout_seconds)
    if payload is None:
        return None, object_url, "Criticality public data unavailable."
    score = _criticality_score_from_csv_bytes(payload, source_repo)
    if score is None:
        return None, object_url, "Repository was not found in the criticality data."
    return score, object_url, None


def _latest_criticality_object(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    candidates = [
        item
        for item in items
        if str(item.get("name") or "").casefold().endswith((".csv", ".csv.gz"))
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (str(item.get("updated") or ""), str(item.get("name") or "")))
    return _first_text(candidates[-1].get("name"))


def _criticality_score_from_csv_bytes(payload: bytes | None, source_repo: str) -> float | None:
    if not payload:
        return None
    if payload[:2] == b"\x1f\x8b":
        try:
            payload = gzip.decompress(payload)
        except OSError:
            return None
    text = payload.decode("utf-8", errors="replace")
    reader = csv.DictReader(text.splitlines())
    for row in reader:
        repo = _normalize_github_repo(row.get("repo.url") or row.get("repo_url") or row.get("url") or row.get("repo"))
        if repo != source_repo:
            continue
        return _float(row.get("default_score") or row.get("original_pike_score") or row.get("criticality_score"))
    return None


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    text = _first_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _texts_from(finding: Finding | dict[str, Any], raw: Any | None) -> list[str]:
    return [
        text
        for text in (
            _get(finding, "title"),
            _get(finding, "remediation"),
            _stringify(raw) if raw is not None else None,
        )
        if text
    ]


def _get(source: Finding | dict[str, Any], key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _deep_get(source: Any, path: str) -> Any:
    current = source
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item)
        if value is not None and str(value).strip():
            return redact_text(str(value).strip())
    return None


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Finding):
        return json.dumps(value.to_dict(), sort_keys=True)
    try:
        return redact_text(json.dumps(value, sort_keys=True))
    except TypeError:
        return redact_text(str(value))


def _clean_package(value: str) -> str:
    return value.strip().strip(".,;:()[]{}\"'")


def _clean_version_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().strip(".,;:()[]{}\"'")


def _kev_cache_path(cache_dir: Path | None) -> Path | None:
    if cache_dir is None:
        return None
    return cache_dir / "cisa-kev.json"


def _read_fresh_kev_cache(cache_dir: Path | None, max_cache_age: timedelta) -> dict[str, Any] | None:
    path = _kev_cache_path(cache_dir)
    if path is None or not path.exists():
        return None
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    if age > max_cache_age:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_kev_cache(cache_dir: Path, payload: dict[str, Any]) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (_kev_cache_path(cache_dir) or cache_dir / "cisa-kev.json").write_text(
            json.dumps(payload, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        return


def _fetch_json(url: str, *, timeout_seconds: float) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers={"User-Agent": "security-observatory/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _fetch_bytes(url: str, *, timeout_seconds: float) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": "security-observatory/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.read()
    except (OSError, TimeoutError, urllib.error.URLError):
        return None
