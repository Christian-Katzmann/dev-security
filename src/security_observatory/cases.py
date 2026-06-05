from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable
import hashlib
import re

from .catalog import SECURITY_PACK_DEFINITIONS, current_scan_profiles, scanner_catalog_compat
from .model import Finding, SEVERITY_ORDER, SecurityCase, normalize_severity
from .priority import PriorityDecision, decide_action_level, with_consequence
from .recency import rotation_surfaces_from_json


DEPENDENCY_SCANNERS = {"trivy", "osv-scanner", "grype"}
SECRET_SCANNERS = {"gitleaks", "trufflehog", "trivy"}
VULN_ID_RE = re.compile(r"\b(?:CVE-\d{4}-\d+|GHSA-[A-Za-z0-9-]+|PYSEC-\d{4}-\d+|OSV-\d+)\b", re.IGNORECASE)
PACKAGE_RE = re.compile(r"\bin\s+([A-Za-z0-9_.:/@+-]+)\b")


@dataclass(frozen=True)
class _RecoveryPlaybookTemplate:
    id: str
    title: str
    summary: str
    step_templates: tuple[str, ...]
    base_minutes: int = 12
    minutes_per_extra_case: int = 5


_RECOVERY_PLAYBOOK_TEMPLATES: dict[str, _RecoveryPlaybookTemplate] = {
    "rotate-leaked-secret": _RecoveryPlaybookTemplate(
        id="rotate-leaked-secret",
        title="Rotate leaked secrets and scrub history",
        summary="Real-looking credentials may have leaked. Rotate the live value first, then clean the source and check history.",
        step_templates=(
            "Confirm whether the exposed values in {files} are real credentials without printing them in logs or chat.",
            "Rotate or revoke the credential at the provider before changing code.",
            "Remove the source of the secret from {files} and replace it with an env var or secret-manager reference.",
            "Check whether the credential appeared in git history and clean it up if needed.",
            "Rerun the matching DëvSec secrets check to confirm the source is gone.",
        ),
        base_minutes=20,
        minutes_per_extra_case=8,
    ),
    "upgrade-vulnerable-dependency": _RecoveryPlaybookTemplate(
        id="upgrade-vulnerable-dependency",
        title="Upgrade vulnerable dependencies",
        summary="Known vulnerabilities in declared packages. Upgrade to a safe version and rerun the test suite.",
        step_templates=(
            "Confirm where each affected package is declared in {files} and which version is installed.",
            "Upgrade to the smallest safe version that fixes the issue and reinstall.",
            "Run the project's dependency install and test commands to catch regressions.",
            "If no fix exists, decide whether the package is reachable and document the temporary risk.",
            "Rerun the matching DëvSec dependency check.",
        ),
        base_minutes=15,
        minutes_per_extra_case=4,
    ),
    "harden-ai-agent-config": _RecoveryPlaybookTemplate(
        id="harden-ai-agent-config",
        title="Narrow AI/agent permissions",
        summary="AI prompts, MCP servers, or agent tool configs may expand attack surface beyond intent.",
        step_templates=(
            "Open each referenced agent config in {files} and confirm which tools, files, or networks it can reach.",
            "Remove unsafe tool grants — shell access, broad file write, secret-bearing env passthrough.",
            "Tighten prompts so untrusted input cannot redirect agent behavior.",
            "Rerun the matching DëvSec AI check.",
        ),
        base_minutes=12,
        minutes_per_extra_case=4,
    ),
    "tighten-iac-exposure": _RecoveryPlaybookTemplate(
        id="tighten-iac-exposure",
        title="Tighten infrastructure exposure",
        summary="Infrastructure-as-code settings may be more open than they need to be.",
        step_templates=(
            "Open each flagged infrastructure file in {files} and confirm the setting is in use.",
            "Tighten access to the smallest safe scope.",
            "Run the infrastructure validation or plan command before applying changes.",
            "Rerun the matching DëvSec IaC check.",
        ),
        base_minutes=15,
        minutes_per_extra_case=6,
    ),
    "restore-platform-posture": _RecoveryPlaybookTemplate(
        id="restore-platform-posture",
        title="Restore platform guardrails",
        summary="Branch protection, workflow tokens, or SCM admin settings may have weakened.",
        step_templates=(
            "Open the repository or organization settings referenced in {files}.",
            "Restore the stricter branch, review, workflow-token, webhook, or admin-access policy.",
            "Rerun the platform posture check and confirm the policy passes.",
        ),
        base_minutes=10,
        minutes_per_extra_case=4,
    ),
    "harden-workflow-surface": _RecoveryPlaybookTemplate(
        id="harden-workflow-surface",
        title="Harden workflow supply-chain surfaces",
        summary="GitHub Actions or CI workflows have risky supply-chain or token surfaces.",
        step_templates=(
            "Open each workflow file in {files} and confirm whether it runs on trusted or untrusted events.",
            "Pin external actions to reviewed commit SHAs and remove fetch-and-exec shell patterns.",
            "Reduce workflow token permissions to the smallest named scopes.",
            "Rerun the workflow surface check.",
        ),
        base_minutes=15,
        minutes_per_extra_case=5,
    ),
    "review-install-hook": _RecoveryPlaybookTemplate(
        id="review-install-hook",
        title="Review install-time package hooks",
        summary="Dependencies can run code at install time. High-risk hooks need a closer look.",
        step_templates=(
            "Open each referenced install hook in {files} and read the exact command it runs.",
            "Remove remote shell execution, credential-file writes, and unexplained dynamic downloads from install time.",
            "If the hook is a legitimate native build, document the reason and add a narrow allow-list entry.",
            "Rerun the install-hook check.",
        ),
        base_minutes=10,
        minutes_per_extra_case=4,
    ),
    "verify-package-drift": _RecoveryPlaybookTemplate(
        id="verify-package-drift",
        title="Verify package drift",
        summary="A dependency artifact changed behavior or version without a clear source-manifest change.",
        step_templates=(
            "Compare the old and new package artifacts referenced by {files}.",
            "Check release notes, provenance, and installer scripts before accepting the upgrade.",
            "If the change is unexplained, hold or revert the lockfile movement and regenerate it from an explicit manifest change.",
            "Rerun the matching DëvSec drift check.",
        ),
        base_minutes=15,
        minutes_per_extra_case=5,
    ),
    "respond-to-named-campaign": _RecoveryPlaybookTemplate(
        id="respond-to-named-campaign",
        title="Respond to named-campaign indicators",
        summary="IOC pack evidence implicates a package, namespace, or domain that appears in this repo's dependency evidence.",
        step_templates=(
            "Confirm the package, version, namespace, or domain referenced in {files} matches the advisory.",
            "Compare local install-recency and rotation surfaces against the advisory before deciding what to rotate.",
            "If the match is real and recent, rotate the enumerated repo-specific surfaces at the provider first; if not, record the decision with a short reason.",
            "Rerun the matching DëvSec IOC check.",
        ),
        base_minutes=18,
        minutes_per_extra_case=6,
    ),
    "fix-code-finding": _RecoveryPlaybookTemplate(
        id="fix-code-finding",
        title="Fix risky code patterns",
        summary="Code patterns the scanners flagged as unsafe. Verify reachability and apply the smallest safe fix.",
        step_templates=(
            "Open the code referenced in {files} and confirm the risky path can actually run.",
            "Trace how user input, files, network data, or agent tools reach this code.",
            "Apply the smallest safe code change that removes the risky behavior.",
            "Add or run a test that proves the unsafe path is blocked.",
            "Rerun the matching DëvSec scanner.",
        ),
        base_minutes=15,
        minutes_per_extra_case=5,
    ),
}

_PLAYBOOK_BY_CATEGORY: dict[str, str] = {
    "secrets": "rotate-leaked-secret",
    "dependencies": "upgrade-vulnerable-dependency",
    "ai-risk": "harden-ai-agent-config",
    "iac": "tighten-iac-exposure",
    "platform-posture": "restore-platform-posture",
    "workflow": "harden-workflow-surface",
    "install-hooks": "review-install-hook",
    "behavioral-drift": "verify-package-drift",
    "silent-upgrade": "verify-package-drift",
    "supply-chain-ioc": "respond-to-named-campaign",
    "code-security": "fix-code-finding",
}

_DEFAULT_PLAYBOOK_ID = "fix-code-finding"


def build_security_cases(
    findings: Iterable[Finding | dict[str, Any]],
    scanners: Iterable[dict[str, Any]],
    scan_metadata: dict[str, Any] | None = None,
    dependency_trust: Iterable[dict[str, Any] | Any] | None = None,
) -> list[SecurityCase]:
    """Group raw scanner findings into human-readable remediation cases."""
    metadata = scan_metadata or {}
    normalized = [_finding_dict(finding) for finding in findings]
    trust_index = _dependency_trust_index(dependency_trust or [])
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in normalized:
        groups[_cluster_key(finding)].append(finding)

    cases = [_case_from_group(items, metadata, trust_index) for items in groups.values()]
    return sorted(cases, key=_case_sort_key)


_ACTION_LEVEL_RANK = {"fix_now": 0, "verify": 1, "watch": 2, "info": 3}
_CONSEQUENCE_CONFIDENCE_RANK = {"unknown": 0, "weak": 1, "strong": 2}


def _consequence_sort_key(case: SecurityCase) -> tuple:
    """Reachable-consequence tiebreak, finer than the severity-label sort above it.

    A case that can reach a crown jewel sorts ahead of one that reaches nothing,
    preferring stronger paths, then nearer ones, then a larger blast radius. Cases
    with no consequence — or that reach no crown jewel — all collapse to one neutral
    key, so they fall through to the title tiebreak and keep exactly today's order.
    A pure-additive break: it never reorders across severity, only within it.
    """
    consequence = case.consequence
    if not isinstance(consequence, dict) or not consequence.get("reaches_crown_jewel"):
        return (1,)
    conf_rank = _CONSEQUENCE_CONFIDENCE_RANK.get(str(consequence.get("confidence") or "unknown").lower(), 0)
    distance = consequence.get("distance")
    distance = distance if isinstance(distance, int) else 1_000_000
    blast = consequence.get("blast_radius") if isinstance(consequence.get("blast_radius"), int) else 0
    return (0, -conf_rank, distance, -blast)


def _case_sort_key(case: SecurityCase) -> tuple:
    return (
        _ACTION_LEVEL_RANK.get(case.action_level, 9),
        -SEVERITY_ORDER.get(case.severity, 0),
        _consequence_sort_key(case),
        case.title.lower(),
    )


def apply_consequence_priority(cases: list[SecurityCase]) -> list[SecurityCase]:
    """Apply the reachable-consequence boost, then re-order.

    Run AFTER ``attach_consequences`` has set ``case.consequence``. The boost is
    additive: a strong path to a crown jewel can raise a case to ``fix_now`` (with a
    plain-English reason), a weak path only explains, and a case with no consequence
    is untouched and keeps its current rank. Severity stays the dominant sort key, so
    a reordered low-severity finding never hides a high-severity one.
    """
    for case in cases:
        if not isinstance(case.consequence, dict):
            continue
        decision = with_consequence(
            PriorityDecision(case.action_level, list(case.priority_reasons)),
            case.consequence,
        )
        case.action_level = decision.action_level
        case.priority_reasons = decision.reasons
    return sorted(cases, key=_case_sort_key)


def scanner_evidence_gaps(scanners: Iterable[dict[str, Any]], profile: str | None = None) -> list[dict[str, Any]]:
    scanner_index = {str(item.get("scanner")): item for item in scanner_catalog_compat()}
    profile_index = {str(item.get("id")): item for item in current_scan_profiles()}
    pack_labels = {definition.id.value: definition.label for definition in SECURITY_PACK_DEFINITIONS}
    active_profile = profile_index.get(str(profile or ""))
    gaps = []
    for scanner in scanners:
        if not isinstance(scanner, dict):
            continue
        if scanner.get("available") and not scanner.get("error"):
            continue
        name = str(scanner.get("scanner") or "unknown scanner")
        reason = scanner.get("error") or "tool was not available"
        metadata = scanner_index.get(name, {})
        profile_ids = [str(item) for item in metadata.get("profile_ids", []) if str(item).strip()]
        recommended_pack_ids = _ordered_gap_pack_ids(metadata, active_profile)
        recommended_profile_id = _recommended_profile_id(profile_ids, active_profile)
        gap: dict[str, Any] = {
            "scanner": name,
            "reason": str(reason),
        }
        if metadata.get("tool_id"):
            gap["tool_id"] = metadata["tool_id"]
            gap["tool_label"] = metadata.get("label") or name
            gap["tool_page"] = {"id": metadata["tool_id"], "label": metadata.get("label") or name}
        if profile_ids:
            gap["profile_ids"] = profile_ids
        if recommended_profile_id:
            gap["recommended_profile_id"] = recommended_profile_id
        if recommended_pack_ids:
            gap["recommended_pack_ids"] = recommended_pack_ids
            gap["pack_pages"] = [{"id": pack_id, "label": pack_labels.get(pack_id, pack_id)} for pack_id in recommended_pack_ids]
        if metadata.get("next_step"):
            gap["next_step"] = metadata["next_step"]
        gaps.append(gap)
    return gaps


def _ordered_gap_pack_ids(metadata: dict[str, Any], active_profile: dict[str, Any] | None) -> list[str]:
    pack_ids = [str(item) for item in metadata.get("recommended_pack_ids", []) if str(item).strip()]
    if not pack_ids:
        return []
    active_pack_ids = [str(item) for item in (active_profile or {}).get("recommended_pack_ids", []) if str(item).strip()]
    ordered = [pack_id for pack_id in active_pack_ids if pack_id in pack_ids]
    ordered.extend(pack_id for pack_id in pack_ids if pack_id not in ordered)
    return ordered


def _recommended_profile_id(profile_ids: list[str], active_profile: dict[str, Any] | None) -> str | None:
    if active_profile and active_profile.get("id") in profile_ids:
        return str(active_profile["id"])
    return profile_ids[0] if profile_ids else None


def _finding_dict(finding: Finding | dict[str, Any]) -> dict[str, Any]:
    if isinstance(finding, Finding):
        return finding.to_dict()
    item = dict(finding)
    item["severity"] = normalize_severity(item.get("severity"))
    return item


def _dependency_trust_index(records: Iterable[dict[str, Any] | Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        if hasattr(record, "to_dict"):
            data = record.to_dict()
        elif isinstance(record, dict):
            data = dict(record)
        else:
            continue
        for key in _trust_keys(data):
            index.setdefault(key, data)
    return index


def _trust_for_findings(findings: list[dict[str, Any]], trust_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for finding in findings:
        for key in _trust_keys(finding):
            if key in trust_index:
                return trust_index[key]
    return None


def _trust_keys(item: dict[str, Any]) -> list[str]:
    keys = []
    for field, prefix in (
        ("component_package_key", "component-package"),
        ("component_fingerprint", "component-fingerprint"),
        ("package_url", "package-url"),
        ("package_name", "package-name"),
        ("name", "package-name"),
    ):
        value = item.get(field)
        if value:
            keys.append(f"{prefix}:{str(value).casefold()}")
    return keys


def _cluster_key(finding: dict[str, Any]) -> str:
    category = str(finding.get("category") or "unknown")
    title = _clean(str(finding.get("title") or "untitled"))
    file = _clean(str(finding.get("file") or ""))
    line = str(finding.get("line") or "")

    if category == "secrets":
        if file and line:
            return f"secret:{file}:{line}"
        if file:
            return f"secret:{file}:{title}"
        return f"secret:{title}"

    if category == "dependencies" or str(finding.get("scanner")) in DEPENDENCY_SCANNERS:
        vulnerability, package = _dependency_identity(finding)
        if vulnerability and package:
            return f"dependency:{vulnerability}:{package}"
        if vulnerability:
            return f"dependency:{vulnerability}:{title}"
        return f"dependency:{title}:{file}"

    if category == "supply-chain-ioc":
        pack = _clean(str(finding.get("ioc_pack_id") or "pack"))
        indicator = _clean(str(finding.get("ioc_indicator") or title))
        match_type = _clean(str(finding.get("ioc_match_type") or "match"))
        return f"ioc:{pack}:{match_type}:{indicator}:{file}"

    if category == "silent-upgrade":
        package_key = _clean(str(finding.get("component_package_key") or finding.get("package_name") or title))
        previous_version = _clean(str(finding.get("old_version") or ""))
        current_version = _clean(str(finding.get("new_version") or finding.get("package_version") or ""))
        return f"silent-upgrade:{package_key}:{previous_version}:{current_version}:{file}"

    if file and line:
        return f"location:{category}:{file}:{line}:{title}"
    if file:
        return f"file:{category}:{file}:{title}"
    return f"title:{category}:{title}"


def _case_from_group(findings: list[dict[str, Any]], metadata: dict[str, Any], trust_index: dict[str, dict[str, Any]]) -> SecurityCase:
    severity = _max_severity(findings)
    category = _primary_category(findings)
    scanners = sorted({str(item.get("scanner")) for item in findings if item.get("scanner")})
    affected_files = sorted({str(item.get("file")) for item in findings if item.get("file")})
    source_fingerprints = sorted({str(item.get("fingerprint")) for item in findings if item.get("fingerprint")})
    vulnerability, package = _dependency_identity(findings[0])
    title = _case_title(category, findings, vulnerability, package)
    confidence = _confidence(category, findings, scanners, vulnerability, package)
    evidence = [_evidence_item(item) for item in findings]
    rotation_context = _rotation_context(category, findings)
    fix_steps = _fix_steps(category, findings, vulnerability, package, rotation_context)
    plain_english_risk = _plain_english_risk(category, severity, affected_files, vulnerability, package, findings, rotation_context)
    case_id = _case_id(metadata, category, title, source_fingerprints)
    agent_prompt = _agent_prompt(title, plain_english_risk, evidence, fix_steps)
    trust = _trust_for_findings(findings, trust_index)
    priority = decide_action_level(
        {
            "category": category,
            "severity": severity,
            "confidence": confidence,
            "scanners": scanners,
            "title": title,
            "plain_english_risk": plain_english_risk,
            "remediation": "\n".join(fix_steps),
            "evidence": evidence,
            "source_fingerprints": source_fingerprints,
        },
        trust,
    )

    return SecurityCase(
        case_id=case_id,
        title=title,
        plain_english_risk=plain_english_risk,
        action_level=priority.action_level,
        confidence=confidence,
        category=category,
        severity=severity,
        affected_files=affected_files,
        evidence=evidence,
        scanners=scanners,
        fix_steps=fix_steps,
        agent_prompt=agent_prompt,
        source_fingerprints=source_fingerprints,
        priority_reasons=priority.reasons,
        install_recency=rotation_context.get("install_recency"),
        rotation_surfaces=rotation_context.get("rotation_surfaces") or [],
    )


def _case_id(metadata: dict[str, Any], category: str, title: str, source_fingerprints: list[str]) -> str:
    repo = str(metadata.get("repo") or metadata.get("repo_name") or "")
    stable_key = "|".join([repo, category, title, *source_fingerprints])
    digest = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:16]
    return f"case-{digest}"


def _dependency_identity(finding: dict[str, Any]) -> tuple[str | None, str | None]:
    direct_vulnerability = finding.get("vulnerability_id")
    direct_package = finding.get("package_name")
    if direct_vulnerability or direct_package:
        return (
            str(direct_vulnerability).upper() if direct_vulnerability else None,
            str(direct_package).lower() if direct_package else None,
        )
    title = str(finding.get("title") or "")
    vulnerability_match = VULN_ID_RE.search(title)
    vulnerability = vulnerability_match.group(0).upper() if vulnerability_match else None
    package_match = PACKAGE_RE.search(title)
    package = package_match.group(1).lower() if package_match else None
    return vulnerability, package


def _case_title(category: str, findings: list[dict[str, Any]], vulnerability: str | None, package: str | None) -> str:
    first = findings[0]
    file = first.get("file")
    if category == "secrets":
        return f"Possible exposed credential in {file}" if file else "Possible exposed credential"
    if category == "dependencies" and vulnerability and package:
        return f"{package} dependency vulnerability {vulnerability}"
    if category == "dependencies" and package:
        return f"{package} dependency vulnerability"
    if category == "supply-chain-ioc":
        package_name = first.get("package_name")
        match_type = first.get("ioc_match_type")
        if package_name and match_type:
            return f"{package_name} named-campaign {match_type}"
        if package_name:
            return f"{package_name} named-campaign match"
    if category == "silent-upgrade":
        package_name = first.get("package_name")
        if package_name:
            return f"{package_name} silent dependency change"
        return "Silent dependency change"
    return str(first.get("title") or "Security case")


def _plain_english_risk(
    category: str,
    severity: str,
    affected_files: list[str],
    vulnerability: str | None,
    package: str | None,
    findings: list[dict[str, Any]],
    rotation_context: dict[str, Any] | None = None,
) -> str:
    location = f" in {affected_files[0]}" if affected_files else ""
    if category == "secrets":
        return f"A credential may be exposed{location}. If it is real, someone could use it to access a service as this project or its owner."
    if category == "dependencies":
        package_text = f" on {package}" if package else ""
        vuln_text = f" ({vulnerability})" if vulnerability else ""
        match = _strongest_component_match(findings)
        match_text = ""
        if match.get("confidence") == "strong":
            version = f" version {match['version']}" if match.get("version") else ""
            match_text = f" The scanner tied this to {match.get('name') or package or 'the package'}{version} in the package list."
        elif match.get("confidence") == "weak":
            match_text = " The scanner found a likely package match, but it is not strong proof."
        elif match.get("confidence") == "uncertain":
            match_text = " Several package-list entries could match, so the exact affected package is uncertain."
        return f"The project depends{package_text} on code with a known weakness{vuln_text}. If the vulnerable part is used, an attacker may be able to abuse it.{match_text}"
    if category == "iac":
        return f"Infrastructure settings may be too open or unsafe{location}. This can expose data, services, or cloud permissions."
    if category == "platform-posture":
        return f"Repository platform settings may have weakened{location}. This can make unsafe merges, broad workflow tokens, or risky SCM access easier."
    if category == "workflow":
        return f"A GitHub Actions workflow has a risky supply-chain surface{location}. This can expose tokens or let untrusted code run in automation."
    if category == "install-hooks":
        return f"A dependency install hook can run code during installation{location}. This is not automatically malicious, but high-risk hook behavior deserves review before trusting the package."
    if category == "ai-risk":
        return f"AI or agent configuration may let untrusted input, tools, or files influence behavior{location}. That can lead to unsafe actions or data exposure."
    if category == "behavioral-drift":
        first = findings[0]
        package_text = f" in {first.get('package_name')}" if first.get("package_name") else ""
        old_version = first.get("old_version")
        new_version = first.get("new_version")
        version_text = f" from {old_version} to {new_version}" if old_version and new_version else ""
        return f"A dependency artifact{package_text} changed behavior{version_text}. This is a reason to investigate the upgrade, not proof that the package is compromised."
    if category == "silent-upgrade":
        first = findings[0]
        package_text = f" {first.get('package_name')}" if first.get("package_name") else ""
        old_version = first.get("old_version")
        new_version = first.get("new_version")
        version_text = f" from {old_version} to {new_version}" if old_version and new_version else ""
        evidence = f" {first.get('evidence_summary')}" if first.get("evidence_summary") else ""
        return f"Dependency{package_text} changed in the saved SBOM{version_text} without a matching source-manifest dependency change.{evidence} Verify or revert the lockfile movement; this is a supply-chain signal, not proof of compromise."
    if category == "supply-chain-ioc":
        first = findings[0]
        match_type = str(first.get("ioc_match_type") or "IOC match")
        pack = str(first.get("ioc_source") or first.get("ioc_pack_id") or "an IOC pack")
        package_text = f" {first.get('package_name')}" if first.get("package_name") else ""
        version_text = f" {first.get('package_version')}" if first.get("package_version") else ""
        base = f"The project has a {match_type}{package_text}{version_text} from {pack}. This is named-campaign evidence, so verify recent execution and follow the advisory context before changing code."
        recency = (rotation_context or {}).get("install_recency") if isinstance(rotation_context, dict) else None
        confidence = str((recency or {}).get("confidence") or "unknown")
        if confidence == "strong":
            return f"{base} Probably executed: local install evidence is recent, so repo-specific credential surfaces should be rotated if this match is real."
        if confidence == "weak":
            return f"{base} Recent execution evidence is weak, so treat this as a check-first case rather than a rotation recommendation."
        return f"{base} No recent local install evidence was found, so keep the IOC visible without claiming it executed."
    if category == "system":
        return "The scan itself found an environment or tooling issue. Fixing it improves trust in future security results."
    if severity in {"critical", "high"}:
        return f"Scanner evidence points to risky code{location}. A reviewer should confirm whether users can reach it and patch it if real."
    return f"Scanner evidence points to a possible security weakness{location}. It should be checked and either fixed or marked as not applicable."


def _confidence(
    category: str,
    findings: list[dict[str, Any]],
    scanners: list[str],
    vulnerability: str | None,
    package: str | None,
) -> str:
    if len(scanners) > 1:
        return "high"
    if category == "dependencies" and vulnerability and package:
        return "high"
    if category == "supply-chain-ioc":
        return "high" if any(item.get("ioc_match_type") == "exact match" for item in findings) else "medium"
    if category == "silent-upgrade":
        return "medium"
    if category == "platform-posture" and any(scanner.startswith("legitify") for scanner in scanners):
        return "high"
    if category in {"workflow", "install-hooks"} and any(item.get("severity") in {"critical", "high"} for item in findings):
        return "high"
    if category == "secrets" and any(item.get("file") for item in findings):
        return "medium"
    if any(item.get("file") and item.get("line") for item in findings):
        return "medium"
    return "low"


def _fix_steps(
    category: str,
    findings: list[dict[str, Any]],
    vulnerability: str | None,
    package: str | None,
    rotation_context: dict[str, Any] | None = None,
) -> list[str]:
    scanner_steps = [str(item.get("remediation")) for item in findings if item.get("remediation")]
    if category == "secrets":
        return [
            "Check whether the exposed value is a real credential without printing it in logs or chat.",
            "Rotate or revoke the credential before changing code.",
            "Remove the source of the secret and add a safe environment-variable or secret-manager path.",
            "Check whether the credential appeared in commit history and clean it up if needed.",
        ]
    if category == "dependencies":
        package_text = package or "the affected package"
        steps = [
            f"Confirm where {package_text} is declared and whether the vulnerable version is installed.",
            "Upgrade to a safe version, preferring the smallest version change that fixes the issue.",
            "Run the dependency install and test commands for this project.",
            "If no fix exists, decide whether the package is reachable and document the temporary risk.",
        ]
        return _merge_steps(steps, scanner_steps)
    if category == "iac":
        steps = [
            "Open the referenced infrastructure file and confirm the setting is actually used.",
            "Tighten access to the smallest safe scope.",
            "Run the infrastructure validation or plan command before applying changes.",
        ]
        return _merge_steps(steps, scanner_steps)
    if category == "platform-posture":
        steps = [
            "Open the repository or organization settings in the SCM platform.",
            "Restore the stricter branch, review, workflow-token, webhook, or admin-access setting.",
            "Rerun the platform posture check and confirm the policy passes.",
        ]
        return _merge_steps(steps, scanner_steps)
    if category == "workflow":
        steps = [
            "Open the referenced workflow line and confirm whether it runs on trusted or untrusted events.",
            "Pin external actions to reviewed commit SHAs and remove fetch-and-exec shell patterns.",
            "Reduce workflow token permissions to the smallest named scopes and document any write scope.",
            "If this is known-good, add a narrow .devsec/workflow-allowlist.yaml entry with a clear reason.",
        ]
        return _merge_steps(steps, scanner_steps)
    if category == "install-hooks":
        steps = [
            "Open the referenced install hook and read the exact command it runs.",
            "Remove remote shell execution, credential-file writes, and unexplained dynamic downloads from install time.",
            "For legitimate native builds or local installers, document the reason and add a narrow .devsec/install-hook-allowlist.yaml entry only when needed.",
        ]
        return _merge_steps(steps, scanner_steps)
    if category == "behavioral-drift":
        steps = [
            "Review the old and new package artifacts and confirm the behavior change is expected for this release.",
            "Check release notes, source provenance, and installer scripts before accepting the upgrade.",
            "If the behavior is unexplained, hold the upgrade and inspect the package maintainer or registry history.",
        ]
        return _merge_steps(steps, scanner_steps)
    if category == "silent-upgrade":
        package_text = findings[0].get("package_name") or "the changed package"
        steps = [
            f"Check whether {package_text} changed only in the lockfile or saved SBOM evidence.",
            "Verify the change is expected from a trusted dependency update, installer run, or lockfile refresh.",
            "If it is unexplained, revert the lockfile movement or regenerate it from an explicit manifest change.",
            "Record the decision as verified, accepted risk, false positive, or fixed after review.",
        ]
        return _merge_steps(steps, scanner_steps)
    if category == "supply-chain-ioc":
        recency = (rotation_context or {}).get("install_recency") if isinstance(rotation_context, dict) else None
        surfaces = (rotation_context or {}).get("rotation_surfaces") or []
        steps = [
            "Confirm the package, version, namespace, or domain really appears in this repo's saved dependency evidence.",
            "Read the advisory or pack source and compare it with the local finding.",
            "If the match is expected or not exploitable here, record the case decision with a short reason.",
        ]
        if isinstance(recency, dict) and recency.get("confidence") == "strong":
            if surfaces:
                steps.insert(
                    2,
                    "Rotate the enumerated repo-specific surfaces at the provider first, update local config last, and never commit rotated values.",
                )
            else:
                steps.insert(2, "No repo-specific credential surfaces were enumerated; keep provider-side checks explicit and evidence-based.")
        else:
            steps.insert(2, "Review local install-recency evidence before deciding whether credential work is needed.")
        return _merge_steps(steps, scanner_steps)
    steps = [
        "Open the referenced code and confirm the risky path can actually run.",
        "Trace how user input, files, network data, or agent tools reach this code.",
        "Apply the smallest safe code change that removes the risky behavior.",
        "Add or run a test that proves the unsafe path is blocked.",
    ]
    return _merge_steps(steps, scanner_steps)


def _agent_prompt(title: str, risk: str, evidence: list[dict[str, Any]], fix_steps: list[str]) -> str:
    evidence_lines = [f"- {item['scanner']}: {item['title']} at {item['location']}" for item in evidence]
    fix_lines = [f"- {step}" for step in fix_steps]
    return "\n".join(
        [
            f"Case: {title}",
            f"Risk: {risk}",
            "Evidence:",
            *(evidence_lines or ["- No scanner evidence was attached."]),
            "Verification steps:",
            "- Inspect the referenced files and confirm the scanner result is real.",
            "- Decide whether this is exploitable in this project, not just theoretically possible.",
            "Fix steps:",
            *fix_lines,
        ]
    )


def _evidence_item(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "scanner": finding.get("scanner") or "unknown",
        "severity": finding.get("severity") or "medium",
        "category": finding.get("category") or "unknown",
        "title": finding.get("title") or "Untitled finding",
        "location": _location(finding),
        "remediation": finding.get("remediation"),
        "fingerprint": finding.get("fingerprint"),
        "vulnerability_id": finding.get("vulnerability_id"),
        "package_name": finding.get("package_name"),
        "package_version": finding.get("package_version"),
        "package_ecosystem": finding.get("package_ecosystem"),
        "package_url": finding.get("package_url"),
        "fixed_version": finding.get("fixed_version"),
        "component_fingerprint": finding.get("component_fingerprint"),
        "component_package_key": finding.get("component_package_key"),
        "component_match_confidence": finding.get("component_match_confidence"),
        "component_match_reason": finding.get("component_match_reason"),
        "old_version": finding.get("old_version"),
        "new_version": finding.get("new_version"),
        "behavior_category": finding.get("behavior_category"),
        "evidence_summary": finding.get("evidence_summary"),
        "before_behavior": finding.get("before_behavior"),
        "after_behavior": finding.get("after_behavior"),
        "ioc_pack_id": finding.get("ioc_pack_id"),
        "ioc_source": finding.get("ioc_source"),
        "ioc_advisory_url": finding.get("ioc_advisory_url"),
        "ioc_confidence": finding.get("ioc_confidence"),
        "ioc_match_type": finding.get("ioc_match_type"),
        "ioc_indicator": finding.get("ioc_indicator"),
        "install_recency_confidence": finding.get("install_recency_confidence"),
        "last_install_signal_at": finding.get("last_install_signal_at"),
        "install_recency_evidence": finding.get("install_recency_evidence"),
        "rotation_surfaces_json": finding.get("rotation_surfaces_json"),
    }


def _rotation_context(category: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    if category != "supply-chain-ioc":
        return {"install_recency": None, "rotation_surfaces": []}
    confidence = _best_recency_confidence(findings)
    last_install_signal_at = _latest_text(item.get("last_install_signal_at") for item in findings)
    evidence = _dedupe_text(
        piece.strip()
        for item in findings
        for piece in str(item.get("install_recency_evidence") or "").split(";")
        if piece.strip()
    )
    surfaces = _dedupe_text(
        surface
        for item in findings
        for surface in rotation_surfaces_from_json(item.get("rotation_surfaces_json"))
    )
    install_recency = {
        "confidence": confidence,
        "last_install_signal_at": last_install_signal_at,
        "evidence": evidence,
    }
    return {
        "install_recency": install_recency,
        "rotation_surfaces": surfaces if confidence == "strong" else [],
    }


def _best_recency_confidence(findings: list[dict[str, Any]]) -> str:
    ranks = {"unknown": 0, "weak": 1, "strong": 2}
    best = "unknown"
    for finding in findings:
        value = str(finding.get("install_recency_confidence") or "unknown")
        if ranks.get(value, 0) > ranks.get(best, 0):
            best = value
    return best


def _latest_text(values: Iterable[Any]) -> str | None:
    clean = [str(value) for value in values if value]
    return max(clean) if clean else None


def _dedupe_text(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    clean: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        clean.append(text)
    return clean


def _strongest_component_match(findings: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = {"strong": 3, "weak": 2, "uncertain": 1, "missing": 0}
    best: dict[str, Any] = {}
    best_rank = -1
    for finding in findings:
        confidence = str(finding.get("component_match_confidence") or "missing")
        rank = ranked.get(confidence, 0)
        if rank <= best_rank:
            continue
        best_rank = rank
        best = {
            "confidence": confidence,
            "name": finding.get("package_name"),
            "version": finding.get("package_version"),
            "reason": finding.get("component_match_reason"),
        }
    return best


def _location(finding: dict[str, Any]) -> str:
    file = finding.get("file") or "repository"
    line = finding.get("line")
    return f"{file}:{line}" if line else str(file)


def _max_severity(findings: list[dict[str, Any]]) -> str:
    return max((normalize_severity(item.get("severity")) for item in findings), key=lambda item: SEVERITY_ORDER.get(item, 0))


def _primary_category(findings: list[dict[str, Any]]) -> str:
    categories = [str(item.get("category") or "unknown") for item in findings]
    return max(set(categories), key=categories.count)


def _merge_steps(default_steps: list[str], scanner_steps: list[str]) -> list[str]:
    merged = list(default_steps)
    for step in scanner_steps:
        if step not in merged:
            merged.append(step)
    return merged


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def build_recovery_playbooks(cases: Iterable[SecurityCase | dict[str, Any]]) -> list[dict[str, Any]]:
    """Group security cases by playbook class and instantiate per-class templates.

    The Recovery playbooks surface renders one playbook per class with the matching
    open cases as items inside it — never one card per finding. Step templates carry a
    `{files}` placeholder which is filled in with the union of affected files across
    the cases in the playbook. The "Rerun matching DëvSec check" action is the last
    step of every template.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        data = case.to_dict() if hasattr(case, "to_dict") else dict(case)
        if data.get("suppressed"):
            continue
        if str(data.get("action_level") or "") == "info":
            continue
        category = str(data.get("category") or "")
        playbook_id = _PLAYBOOK_BY_CATEGORY.get(category, _DEFAULT_PLAYBOOK_ID)
        grouped[playbook_id].append(data)

    playbooks: list[dict[str, Any]] = []
    for playbook_id, items in grouped.items():
        template = _RECOVERY_PLAYBOOK_TEMPLATES.get(playbook_id, _RECOVERY_PLAYBOOK_TEMPLATES[_DEFAULT_PLAYBOOK_ID])
        files = _aggregate_playbook_files(items)
        files_text = _format_files_text(files)
        steps = [step.replace("{files}", files_text) for step in template.step_templates]
        extra_cases = max(0, len(items) - 1)
        estimated_minutes = template.base_minutes + extra_cases * template.minutes_per_extra_case
        severity = _max_playbook_severity(items)
        scanners = sorted({str(scanner) for item in items for scanner in (item.get("scanners") or []) if scanner})
        items_payload = [_playbook_item_payload(item) for item in items]
        items_payload.sort(key=lambda entry: (SEVERITY_ORDER.get(entry["severity"], 0) * -1, entry["title"].lower()))
        playbooks.append(
            {
                "id": playbook_id,
                "title": template.title,
                "summary": template.summary,
                "severity": severity,
                "scanners": scanners,
                "estimated_minutes": estimated_minutes,
                "estimate_label": f"~ {estimated_minutes} min",
                "steps": steps,
                "case_count": len(items),
                "affected_files": files,
                "items": items_payload,
            }
        )

    playbooks.sort(
        key=lambda playbook: (
            -SEVERITY_ORDER.get(playbook["severity"], 0),
            -playbook["case_count"],
            playbook["title"].lower(),
        )
    )
    return playbooks


def _aggregate_playbook_files(items: list[dict[str, Any]], max_files: int = 6) -> list[str]:
    seen: set[str] = set()
    files: list[str] = []
    for item in items:
        for file in item.get("affected_files") or []:
            text = str(file).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            files.append(text)
            if len(files) >= max_files:
                return files
    return files


def _format_files_text(files: list[str]) -> str:
    if not files:
        return "the affected files"
    if len(files) == 1:
        return files[0]
    if len(files) == 2:
        return f"{files[0]} and {files[1]}"
    head = ", ".join(files[:-1])
    return f"{head}, and {files[-1]}"


def _playbook_item_payload(case: dict[str, Any]) -> dict[str, Any]:
    affected_files = [str(item) for item in (case.get("affected_files") or []) if item]
    location = affected_files[0] if affected_files else "repository"
    scan_id = case.get("scan_id")
    return {
        "case_id": str(case.get("case_id") or case.get("id") or ""),
        "repo": str(case.get("repo") or case.get("repo_name") or ""),
        "title": str(case.get("title") or "Security case"),
        "severity": normalize_severity(case.get("severity")),
        "category": str(case.get("category") or "unknown"),
        "action_level": str(case.get("action_level") or "verify"),
        "scan_id": str(scan_id) if scan_id else None,
        "location": location,
        "affected_files": affected_files,
        "scanners": sorted({str(scanner) for scanner in (case.get("scanners") or []) if scanner}),
    }


def _max_playbook_severity(items: list[dict[str, Any]]) -> str:
    if not items:
        return "medium"
    return max(
        (normalize_severity(item.get("severity")) for item in items),
        key=lambda value: SEVERITY_ORDER.get(value, 0),
    )
