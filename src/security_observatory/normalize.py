from __future__ import annotations

from typing import Any
import hashlib
import urllib.parse

from .model import Finding, normalize_severity
from .platform_posture import FAILED_STATUS, platform_posture_records
from .surface_scanners import INSTALL_HOOK_SCANNER, WORKFLOW_SCANNER, actionable_install_hook_records, actionable_workflow_records


def _line(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, list) and value and isinstance(value[0], int):
        return value[0]
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _severity_from_score(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return normalize_severity(value)
    if score >= 9:
        return "critical"
    if score >= 7:
        return "high"
    if score >= 4:
        return "medium"
    if score > 0:
        return "low"
    return "info"


def _dict_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item)
        text = _text(value)
        if text:
            return text
    return None


def _deep_get(source: Any, path: str) -> Any:
    current = source
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _ecosystem_from_purl(package_url: str | None) -> str | None:
    if not package_url or not package_url.startswith("pkg:"):
        return None
    tail = package_url[4:]
    return urllib.parse.unquote(tail.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]) or None


def _package_url_from(*values: Any) -> str | None:
    for value in values:
        text = _text(value)
        if text and text.startswith("pkg:"):
            return text
    return None


def normalize(scanner: str, data: Any, repo_name: str) -> list[Finding]:
    # Per-scanner normalization resolves from the single scanner-adapter registry
    # (security_observatory.scanners.SCANNER_REGISTRY), so this dispatch shares
    # one source of truth with command/timeout/exit-code handling instead of a
    # parallel if-chain. The import is deferred to keep this module free of a
    # top-level dependency on ``scanners``, which imports the normalizer
    # implementations defined below.
    from .scanners import normalizer_for

    normalizer = normalizer_for(scanner)
    return normalizer(data, repo_name) if normalizer else []


def _semgrep(data: Any, repo_name: str) -> list[Finding]:
    findings = []
    for item in _dict_items(_dict_value(data).get("results")):
        extra = _dict_value(item.get("extra"))
        findings.append(
            Finding(
                repo=repo_name,
                scanner="semgrep",
                severity=extra.get("severity", "medium"),
                category="code-security",
                title=extra.get("message") or item.get("check_id") or "Semgrep finding",
                file=item.get("path"),
                line=_line((item.get("start") or {}).get("line")),
                remediation=(extra.get("metadata") or {}).get("fix") or extra.get("fix"),
            )
        )
    return findings


def _gitleaks(data: Any, repo_name: str) -> list[Finding]:
    findings = []
    for item in _dict_items(data):
        findings.append(
            Finding(
                repo=repo_name,
                scanner="gitleaks",
                severity="critical",
                category="secrets",
                title=item.get("Description") or item.get("RuleID") or "Possible secret detected",
                file=item.get("File"),
                line=_line(item.get("StartLine")),
                remediation="Rotate the credential if real, then remove it from history or add a narrow allowlist entry.",
            )
        )
    return findings


def _trufflehog(data: Any, repo_name: str) -> list[Finding]:
    findings = []
    for item in _dict_items(data):
        source = _dict_value(_dict_value(item.get("SourceMetadata")).get("Data"))
        filesystem = _dict_value(source.get("Filesystem"))
        findings.append(
            Finding(
                repo=repo_name,
                scanner="trufflehog",
                severity="critical" if item.get("Verified") else "high",
                category="secrets",
                title=item.get("DetectorName") or "Possible secret detected",
                file=filesystem.get("file") or item.get("SourceName"),
                line=_line(filesystem.get("line")),
                remediation="Confirm whether this is a live credential. Rotate first; cleanup second.",
            )
        )
    return findings


def _trivy(data: Any, repo_name: str) -> list[Finding]:
    findings = []
    for result in _dict_items(_dict_value(data).get("Results")):
        target = result.get("Target")
        for item in _dict_items(result.get("Vulnerabilities")):
            fixed = item.get("FixedVersion")
            package_url = _package_url_from(
                _deep_get(item, "PkgIdentifier.PURL"),
                _deep_get(item, "PkgIdentifier.purl"),
                item.get("PURL"),
            )
            vuln_id = _text(item.get("VulnerabilityID"))
            package_name = _text(item.get("PkgName"))
            remediation = f"Upgrade {item.get('PkgName')} to {fixed}." if fixed else "Review the advisory and upgrade when a fixed version is available."
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="trivy",
                    severity=item.get("Severity", "medium"),
                    category="dependencies",
                    title=f"{vuln_id or 'Vulnerability'} in {package_name or 'package'}",
                    file=target,
                    remediation=remediation,
                    vulnerability_id=vuln_id,
                    package_name=package_name,
                    package_version=_text(item.get("InstalledVersion")),
                    package_ecosystem=_ecosystem_from_purl(package_url),
                    package_url=package_url,
                    fixed_version=_text(fixed),
                )
            )
        for item in _dict_items(result.get("Misconfigurations")):
            cause = _dict_value(item.get("CauseMetadata"))
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="trivy",
                    severity=item.get("Severity", "medium"),
                    category="iac",
                    title=item.get("Title") or item.get("ID") or "IaC misconfiguration",
                    file=cause.get("Resource") or target,
                    line=_line(cause.get("StartLine")),
                    remediation=item.get("Resolution"),
                )
            )
        for item in _dict_items(result.get("Secrets")):
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="trivy",
                    severity=item.get("Severity", "critical"),
                    category="secrets",
                    title=item.get("Title") or item.get("RuleID") or "Secret detected",
                    file=target,
                    line=_line(item.get("StartLine")),
                    remediation="Rotate the credential if real and remove the source.",
                )
            )
    return findings


def _osv(data: Any, repo_name: str) -> list[Finding]:
    findings = []
    for result in _dict_items(_dict_value(data).get("results")):
        source = _dict_value(result.get("source")).get("path") or result.get("path")
        for package in _dict_items(result.get("packages")):
            package_data = _dict_value(package.get("package"))
            package_name = _text(package_data.get("name")) or "package"
            package_url = _package_url_from(package_data.get("purl"), package.get("purl"))
            ecosystem = _text(package_data.get("ecosystem")) or _ecosystem_from_purl(package_url)
            package_version = _first_text(package_data.get("version"), package.get("version"))
            for vuln in _dict_items(package.get("vulnerabilities")):
                severity_items = _dict_items(vuln.get("severity"))
                severity = "high" if not severity_items else _severity_from_score(severity_items[0].get("score", "high"))
                vuln_id = _text(vuln.get("id"))
                findings.append(
                    Finding(
                        repo=repo_name,
                        scanner="osv-scanner",
                        severity=severity,
                        category="dependencies",
                        title=f"{vuln_id or 'OSV vulnerability'} in {package_name}",
                        file=source,
                        remediation="Upgrade to a non-vulnerable version listed by OSV.",
                        vulnerability_id=vuln_id,
                        package_name=package_name,
                        package_version=package_version,
                        package_ecosystem=ecosystem,
                        package_url=package_url,
                    )
                )
    return findings


def _grype(data: Any, repo_name: str) -> list[Finding]:
    findings = []
    for match in _dict_items(_dict_value(data).get("matches")):
        vulnerability = _dict_value(match.get("vulnerability"))
        artifact = _dict_value(match.get("artifact"))
        locations = artifact.get("locations") or []
        first_location = _dict_items(locations)[0] if _dict_items(locations) else {}
        package_url = _package_url_from(artifact.get("purl"))
        vuln_id = _text(vulnerability.get("id"))
        fixed_version = _first_text(_deep_get(match, "vulnerability.fix.versions"), _deep_get(match, "relatedVulnerabilities.fix.versions"))
        findings.append(
            Finding(
                repo=repo_name,
                scanner="grype",
                severity=vulnerability.get("severity", "medium"),
                category="dependencies",
                title=f"{vuln_id or 'Vulnerability'} in {artifact.get('name', 'package')}",
                file=first_location.get("path"),
                remediation=_dict_items(match.get("details"))[0].get("description") if _dict_items(match.get("details")) else None,
                vulnerability_id=vuln_id,
                package_name=_text(artifact.get("name")),
                package_version=_text(artifact.get("version")),
                package_ecosystem=_ecosystem_from_purl(package_url) or _text(artifact.get("type")),
                package_url=package_url,
                fixed_version=fixed_version,
            )
        )
    return findings


def _checkov(data: Any, repo_name: str) -> list[Finding]:
    failed = _dict_value(_dict_value(data).get("results")).get("failed_checks")
    findings = []
    for item in _dict_items(failed):
        findings.append(
            Finding(
                repo=repo_name,
                scanner="checkov",
                severity=normalize_severity(item.get("severity") or "medium"),
                category="iac",
                title=item.get("check_name") or item.get("check_id") or "IaC policy failure",
                file=item.get("file_path"),
                line=_line(item.get("file_line_range")),
                remediation=item.get("guideline"),
            )
        )
    return findings


def _legitify(data: Any, repo_name: str) -> list[Finding]:
    findings = []
    for record in platform_posture_records(data):
        if str(record.get("status") or "").upper() != FAILED_STATUS:
            continue
        title = _text(record.get("title")) or _text(record.get("policy_name")) or "Platform posture policy failed"
        remediation = _text(record.get("remediation")) or "Review the platform setting and restore the stricter repository protection."
        description = _text(record.get("description"))
        resource_label = _text(record.get("resource_label")) or _text(record.get("namespace")) or "platform"
        evidence_summary = f"{title}: {description}" if description else title
        findings.append(
            Finding(
                repo=repo_name,
                scanner="legitify",
                severity=record.get("severity") or "medium",
                category="platform-posture",
                title=title,
                file=resource_label,
                remediation=remediation,
                behavior_category="platform-policy",
                evidence_summary=evidence_summary,
                fingerprint=_platform_posture_fingerprint(repo_name, record),
            )
        )
    return findings


def _generic_ai(scanner: str, data: Any, repo_name: str) -> list[Finding]:
    findings = []
    containers: list[Any] = []
    if isinstance(data, dict):
        for key in ("findings", "results", "issues", "vulnerabilities"):
            if isinstance(data.get(key), list):
                containers.extend(data[key])
    elif isinstance(data, list):
        containers = data
    for item in containers:
        if not isinstance(item, dict):
            continue
        findings.append(
            Finding(
                repo=repo_name,
                scanner=scanner,
                severity=item.get("severity") or item.get("level") or "medium",
                category="ai-risk",
                title=item.get("title") or item.get("message") or item.get("rule_id") or "AI-agent security finding",
                file=item.get("file") or item.get("path"),
                line=_line(item.get("line")),
                remediation=item.get("remediation") or item.get("recommendation"),
            )
        )
    return findings


def _install_hooks(data: Any, repo_name: str) -> list[Finding]:
    findings = []
    for record in actionable_install_hook_records(data):
        allowlist_note = f" Allow-list note: {record.get('allowlist_error')}" if record.get("allowlist_error") else ""
        hook = _text(record.get("hook")) or "install hook"
        title = _text(record.get("title")) or f"{hook} install hook needs review"
        evidence = _text(record.get("command"))
        findings.append(
            Finding(
                repo=repo_name,
                scanner=INSTALL_HOOK_SCANNER,
                severity=record.get("severity") or "high",
                category="install-hooks",
                title=title,
                file=_text(record.get("path")),
                line=_line(record.get("line")),
                remediation=_text(record.get("remediation")) or "Review the install-time command and remove unsafe execution.",
                behavior_category=_text(record.get("rule")),
                evidence_summary=f"{hook}: {evidence or title}.{allowlist_note}",
                fingerprint=_text(record.get("fingerprint")),
            )
        )
    return findings


def _workflow_audit(data: Any, repo_name: str) -> list[Finding]:
    findings = []
    for record in actionable_workflow_records(data):
        allowlist_note = f" Allow-list note: {record.get('allowlist_error')}" if record.get("allowlist_error") else ""
        title = _text(record.get("title")) or "Workflow surface needs review"
        evidence = _text(record.get("evidence"))
        findings.append(
            Finding(
                repo=repo_name,
                scanner=WORKFLOW_SCANNER,
                severity=record.get("severity") or "medium",
                category="workflow",
                title=title,
                file=_text(record.get("path")),
                line=_line(record.get("line")),
                remediation=_text(record.get("remediation")) or "Review the workflow surface and narrow the risky behavior.",
                behavior_category=_text(record.get("rule")),
                evidence_summary=f"{record.get('rule') or 'workflow'}: {evidence or title}.{allowlist_note}",
                fingerprint=_text(record.get("fingerprint")),
            )
        )
    return findings


def _malcontent(data: Any, repo_name: str) -> list[Finding]:
    findings = []
    for check in _dict_items(_dict_value(data).get("checks")):
        if check.get("status") != "checked":
            continue
        package_name = _text(check.get("package_name")) or "package"
        old_version = _text(check.get("old_version"))
        new_version = _text(check.get("new_version"))
        package_label = f"{package_name} {old_version or '?'} -> {new_version or '?'}"
        for behavior in _malcontent_behavior_records(check.get("malcontent"))[:20]:
            category = _behavior_category(behavior)
            after = _behavior_after(behavior)
            before = _behavior_before(behavior)
            evidence_summary = (
                f"{package_label}: before: {before}. after: {after}. "
                "This is evidence for investigation, not proof of compromise."
            )
            severity = _malcontent_severity(behavior)
            file = _first_text(
                _ci_get(behavior, "path"),
                _ci_get(behavior, "rel_path"),
                _ci_get(behavior, "relpath"),
                _ci_get(behavior, "full_path"),
                _ci_get(behavior, "fullpath"),
                _ci_get(behavior, "name"),
            )
            title = f"New {category} behavior in {package_name}"
            fingerprint = _behavior_fingerprint(repo_name, check, category, file, after)
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="malcontent",
                    severity=severity,
                    category="behavioral-drift",
                    title=title,
                    file=file,
                    remediation="Review the package diff and release provenance before trusting the new version. Do not treat behavioral drift alone as proof of compromise.",
                    package_name=_text(check.get("package_name")),
                    package_version=new_version,
                    package_ecosystem=_text(check.get("package_ecosystem")),
                    package_url=_text(check.get("package_url")),
                    component_fingerprint=_text(check.get("component_fingerprint")),
                    component_package_key=_text(check.get("package_key")),
                    old_version=old_version,
                    new_version=new_version,
                    behavior_category=category,
                    evidence_summary=evidence_summary,
                    before_behavior=before,
                    after_behavior=after,
                    fingerprint=fingerprint,
                )
            )
    return findings


def _malcontent_behavior_records(payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    _collect_malcontent_behaviors(payload, {}, records)
    seen = set()
    deduped = []
    for record in records:
        key = (
            _first_text(_ci_get(record, "path"), _ci_get(record, "rel_path"), _ci_get(record, "name")) or "",
            _behavior_category(record),
            _behavior_after(record),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _collect_malcontent_behaviors(value: Any, context: dict[str, Any], records: list[dict[str, Any]]) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_malcontent_behaviors(item, context, records)
        return
    if not isinstance(value, dict):
        if isinstance(value, str) and value.strip():
            records.append({**context, "name": value})
        return

    current = {**context}
    for source_key, target_key in (
        ("path", "path"),
        ("rel_path", "path"),
        ("relpath", "path"),
        ("relative_path", "path"),
        ("full_path", "path"),
        ("fullpath", "path"),
        ("risk_level", "risk_level"),
        ("risklevel", "risk_level"),
        ("previous_risk_level", "previous_risk_level"),
        ("previousrisklevel", "previous_risk_level"),
    ):
        value_at_key = _ci_get(value, source_key)
        if value_at_key is not None:
            current[target_key] = value_at_key

    behavior_list = _ci_get(value, "behaviors")
    capability_list = _ci_get(value, "capabilities")
    emitted = False
    for child in _list_value(behavior_list) + _list_value(capability_list):
        if isinstance(child, dict):
            records.append({**current, **child})
        elif child:
            records.append({**current, "name": child})
        emitted = True

    if not emitted and _looks_like_behavior(value):
        records.append({**current, **value})

    for key, child in value.items():
        if str(key).casefold().replace("_", "") in {"behaviors", "capabilities"}:
            continue
        if isinstance(child, (dict, list)):
            _collect_malcontent_behaviors(child, current, records)


def _looks_like_behavior(value: dict[str, Any]) -> bool:
    compact_keys = {str(key).casefold().replace("_", "") for key in value}
    return bool(
        compact_keys
        & {
            "rule",
            "rulename",
            "behavior",
            "category",
            "capability",
            "description",
            "risklevel",
            "risk",
        }
    )


def _behavior_category(behavior: dict[str, Any]) -> str:
    explicit = _first_text(_ci_get(behavior, "category"), _ci_get(behavior, "class"), _ci_get(behavior, "type"))
    text = " ".join(
        str(value)
        for value in (
            explicit,
            _ci_get(behavior, "name"),
            _ci_get(behavior, "rule"),
            _ci_get(behavior, "rule_name"),
            _ci_get(behavior, "description"),
            _ci_get(behavior, "capability"),
        )
        if value
    ).casefold()
    if any(token in text for token in ("socket", "http", "dns", "network", "connect", "download", "curl", "wget")):
        return "network"
    if any(token in text for token in ("exec", "process", "shell", "spawn", "command", "fork")):
        return "process execution"
    if any(token in text for token in ("write", "chmod", "filesystem", "file ", "path", "delete")):
        return "file system"
    if any(token in text for token in ("credential", "secret", "token", "keychain", "password")):
        return "credential access"
    if any(token in text for token in ("persistence", "launchagent", "cron", "startup")):
        return "persistence"
    if any(token in text for token in ("obfuscat", "packed", "encoded", "eval")):
        return "obfuscation"
    return explicit or "suspicious"


def _behavior_before(behavior: dict[str, Any]) -> str:
    before = _first_text(_ci_get(behavior, "before"), _ci_get(behavior, "previous"), _ci_get(behavior, "previous_behavior"))
    if before:
        return before
    previous_risk = _first_text(_ci_get(behavior, "previous_risk_level"), _ci_get(behavior, "previousrisklevel"))
    if previous_risk:
        return f"previous artifact risk was {previous_risk}"
    return "no comparable behavior was reported in the previous artifact"


def _behavior_after(behavior: dict[str, Any]) -> str:
    return (
        _first_text(
            _ci_get(behavior, "after"),
            _ci_get(behavior, "description"),
            _ci_get(behavior, "summary"),
            _ci_get(behavior, "name"),
            _ci_get(behavior, "rule_name"),
            _ci_get(behavior, "rule"),
            _ci_get(behavior, "capability"),
        )
        or "malcontent reported a higher-risk behavior in the new artifact"
    )


def _malcontent_severity(behavior: dict[str, Any]) -> str:
    risk = _first_text(
        _ci_get(behavior, "risk_level"),
        _ci_get(behavior, "risklevel"),
        _ci_get(behavior, "level"),
        _ci_get(behavior, "severity"),
    )
    if risk:
        return normalize_severity(risk)
    score = _ci_get(behavior, "risk_score") or _ci_get(behavior, "riskscore")
    return _severity_from_score(score)


def _behavior_fingerprint(repo_name: str, check: dict[str, Any], category: str, file: str | None, after: str) -> str:
    key = "|".join(
        [
            repo_name,
            "malcontent",
            _text(check.get("package_key")) or "",
            _text(check.get("old_version")) or "",
            _text(check.get("new_version")) or "",
            category,
            file or "",
            after,
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _ci_get(source: dict[str, Any], key: str) -> Any:
    compact_key = key.casefold().replace("_", "")
    for source_key, value in source.items():
        if str(source_key).casefold().replace("_", "") == compact_key:
            return value
    return None


def _list_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _platform_posture_fingerprint(repo_name: str, record: dict[str, Any]) -> str:
    key = "|".join(
        [
            repo_name,
            "legitify",
            _text(record.get("policy_key")) or "",
            _text(record.get("resource_ref")) or "",
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
