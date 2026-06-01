from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import unquote
import re

from .lifecycle import DECISION_STATUSES, SUPPRESSING_STATUSES
from .model import redact_text


# The canonical case-decision vocabulary lives in ``lifecycle.py`` (the single
# source of truth). These names are re-exported aliases so existing importers
# (storage, case_followup, …) keep working — every reference resolves to the
# lifecycle module, never a second independent definition.
CASE_DECISION_STATUSES = DECISION_STATUSES
SUPPRESSING_DECISION_STATUSES = SUPPRESSING_STATUSES
# Suppressing a case at these severities hides a serious finding, so it can
# never auto-apply through an automated/AI path — it requires explicit human
# confirmation (see storage.set_case_decision and the case-resolution apply path).
GATED_SUPPRESSION_SEVERITIES = {"high", "critical"}
VEX_STATUSES = {"affected", "not_affected", "fixed", "under_investigation"}

DEFAULT_VEX_STATUS_BY_DECISION = {
    "verified": "affected",
    "false_positive": "not_affected",
    "accepted_risk": "affected",
    "fixed": "fixed",
    # A fix is applied but not yet rescan-proven — the vulnerability is still
    # treated as affected until closure is verified.
    "in_progress": "under_investigation",
}

VULNERABILITY_RE = re.compile(r"\b(?:CVE-\d{4}-\d+|GHSA-[A-Za-z0-9-]+|PYSEC-\d{4}-\d+|OSV-\d+)\b", re.IGNORECASE)
PACKAGE_RE = re.compile(r"\bin\s+([A-Za-z0-9_.:/@+-]+)\b")


def default_vex_status(decision_status: str | None) -> str | None:
    return DEFAULT_VEX_STATUS_BY_DECISION.get(_status_text(decision_status))


def normalize_vex_status(value: Any, decision_status: str | None = None) -> str | None:
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if text in VEX_STATUSES:
        return text
    return default_vex_status(decision_status)


def normalize_case_decision(decision: dict[str, Any]) -> dict[str, Any]:
    data = dict(decision)
    status = _status_text(data.get("status"))
    data["status"] = status
    data["vex_status"] = normalize_vex_status(data.get("vex_status"), status)
    justification = _reason_text(data.get("vex_justification") or data.get("vex_reason") or data.get("note"))
    data["vex_justification"] = justification
    data["vex_reason"] = justification
    return data


def dependency_identity_from_case(case: dict[str, Any]) -> dict[str, str | None]:
    evidence = [item for item in case.get("evidence", []) if isinstance(item, dict)]
    vulnerability = _first_text(case.get("vulnerability_id"), *(item.get("vulnerability_id") for item in evidence))
    package_name = _first_text(case.get("package_name"), *(item.get("package_name") for item in evidence))
    package_version = _first_text(case.get("package_version"), *(item.get("package_version") for item in evidence))
    package_ecosystem = _first_text(case.get("package_ecosystem"), *(item.get("package_ecosystem") for item in evidence))
    package_url = _first_text(case.get("package_url"), *(item.get("package_url") for item in evidence))
    component_package_key = _first_text(
        case.get("component_package_key"),
        *(item.get("component_package_key") for item in evidence),
    )
    fixed_version = _first_text(case.get("fixed_version"), *(item.get("fixed_version") for item in evidence))

    title = str(case.get("title") or "")
    if not vulnerability:
        match = VULNERABILITY_RE.search(title)
        vulnerability = match.group(0) if match else None
    if not package_name:
        match = PACKAGE_RE.search(title)
        package_name = match.group(1) if match else None
    if not package_name and package_url:
        package_name = _package_name_from_url(package_url)
    if not package_ecosystem and package_url:
        package_ecosystem = _ecosystem_from_package_url(package_url)

    return {
        "vulnerability_id": _normalize_vulnerability(vulnerability),
        "package_name": _clean_package_name(package_name),
        "package_version": _optional_text(package_version),
        "package_ecosystem": _clean_ecosystem(package_ecosystem),
        "package_url": _optional_text(package_url),
        "component_package_key": _optional_text(component_package_key),
        "fixed_version": _optional_text(fixed_version),
    }


def dependency_identity_from_finding(finding: dict[str, Any]) -> dict[str, str | None]:
    return dependency_identity_from_case(
        {
            "title": finding.get("title"),
            "vulnerability_id": finding.get("vulnerability_id"),
            "package_name": finding.get("package_name"),
            "package_version": finding.get("package_version"),
            "package_ecosystem": finding.get("package_ecosystem"),
            "package_url": finding.get("package_url"),
            "component_package_key": finding.get("component_package_key"),
            "fixed_version": finding.get("fixed_version"),
            "evidence": [],
        }
    )


def dependency_fields_from_case(case: dict[str, Any]) -> dict[str, str | None]:
    if not _is_dependency_case(case):
        return {}
    return dependency_identity_from_case(case)


def is_suppressing_decision(decision: dict[str, Any] | None) -> bool:
    if not decision:
        return False
    return _status_text(decision.get("status")) in SUPPRESSING_DECISION_STATUSES


def dependency_decision_matches_case(decision: dict[str, Any], case: dict[str, Any]) -> bool:
    if not _is_dependency_case(case):
        return False
    return _dependency_decision_matches_identity(decision, dependency_identity_from_case(case))


def dependency_decision_matches_finding(decision: dict[str, Any], finding: dict[str, Any]) -> bool:
    if str(finding.get("category") or "").casefold() != "dependencies":
        return False
    return _dependency_decision_matches_identity(decision, dependency_identity_from_finding(finding))


def assemble_suppression(
    cases: Iterable[dict[str, Any]],
    findings: Iterable[dict[str, Any]],
    decisions: dict[str, dict[str, Any]] | Iterable[dict[str, Any]],
) -> dict[str, Any]:
    decision_map = _decision_map(decisions)
    all_cases: list[dict[str, Any]] = []
    active_cases: list[dict[str, Any]] = []
    suppressed_cases: list[dict[str, Any]] = []
    suppressed_by_fingerprint: dict[str, dict[str, Any]] = {}

    for raw_case in cases:
        case = dict(raw_case)
        case_id = _case_identity(case)
        exact_decision = decision_map.get(case_id)
        if exact_decision and "decision" not in case:
            case["decision"] = exact_decision
        suppression = suppression_for_case(case, decision_map)
        if suppression:
            matched_decision_id = str(suppression.get("case_id") or "")
            if matched_decision_id in decision_map and "decision" not in case:
                case["decision"] = decision_map[matched_decision_id]
            case["suppressed"] = True
            case["suppression"] = suppression
            suppressed_cases.append(case)
            for fingerprint in case.get("source_fingerprints", []):
                if fingerprint:
                    suppressed_by_fingerprint[str(fingerprint)] = suppression
        else:
            case["suppressed"] = False
            active_cases.append(case)
        all_cases.append(case)

    all_findings: list[dict[str, Any]] = []
    active_findings: list[dict[str, Any]] = []
    suppressed_findings: list[dict[str, Any]] = []
    for raw_finding in findings:
        finding = dict(raw_finding)
        suppression = suppressed_by_fingerprint.get(str(finding.get("fingerprint") or ""))
        if not suppression:
            suppression = suppression_for_finding(finding, decision_map)
        if suppression:
            finding["suppressed"] = True
            finding["suppression"] = suppression
            suppressed_findings.append(finding)
        else:
            finding["suppressed"] = False
            active_findings.append(finding)
        all_findings.append(finding)

    suppressed_counts = suppression_counts(suppressed_cases, suppressed_findings)
    return {
        "cases": all_cases,
        "active_cases": active_cases,
        "suppressed_cases": suppressed_cases,
        "findings": all_findings,
        "active_findings": active_findings,
        "suppressed_findings": suppressed_findings,
        "suppressed_counts": suppressed_counts,
    }


def suppression_for_case(case: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    exact_decision = _case_decision(case, decisions)
    if is_suppressing_decision(exact_decision) and _repo_matches(exact_decision or {}, case):
        return _suppression_payload(exact_decision, matched_by="case_id")

    if not _is_dependency_case(case):
        return None
    for decision in decisions.values():
        if not is_suppressing_decision(decision):
            continue
        if not _repo_matches(decision, case):
            continue
        if not _reason_text(decision.get("vex_justification") or decision.get("vex_reason") or decision.get("note")):
            continue
        if dependency_decision_matches_case(decision, case):
            return _suppression_payload(decision, matched_by="dependency_identity")
    return None


def suppression_for_finding(finding: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for decision in decisions.values():
        if not is_suppressing_decision(decision):
            continue
        if not _repo_matches(decision, finding):
            continue
        if not _reason_text(decision.get("vex_justification") or decision.get("vex_reason") or decision.get("note")):
            continue
        if dependency_decision_matches_finding(decision, finding):
            return _suppression_payload(decision, matched_by="dependency_identity")
    return None


def suppression_counts(suppressed_cases: list[dict[str, Any]], suppressed_findings: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: dict[tuple[str, str, str], dict[str, Any]] = {}
    for kind, items in (("cases", suppressed_cases), ("findings", suppressed_findings)):
        for item in items:
            suppression = item.get("suppression") if isinstance(item, dict) else None
            if not isinstance(suppression, dict):
                continue
            reason = str(suppression.get("reason") or "Suppressed by case decision.")
            decision_status = str(suppression.get("decision_status") or suppression.get("status") or "unknown")
            vex_status = str(suppression.get("vex_status") or "unknown")
            key = (reason, decision_status, vex_status)
            entry = reasons.setdefault(
                key,
                {
                    "reason": reason,
                    "decision_status": decision_status,
                    "vex_status": vex_status,
                    "cases": 0,
                    "findings": 0,
                },
            )
            entry[kind] += 1
    return {
        "cases": len(suppressed_cases),
        "findings": len(suppressed_findings),
        "reasons": sorted(reasons.values(), key=lambda item: (str(item["reason"]).casefold(), str(item["vex_status"]))),
    }


def _dependency_decision_matches_identity(decision: dict[str, Any], identity: dict[str, str | None]) -> bool:
    decision_identity = {
        "vulnerability_id": _normalize_vulnerability(decision.get("vulnerability_id")),
        "package_name": _clean_package_name(decision.get("package_name")),
        "package_ecosystem": _clean_ecosystem(decision.get("package_ecosystem")),
        "package_url": _optional_text(decision.get("package_url")),
        "component_package_key": _optional_text(decision.get("component_package_key")),
    }
    vulnerability = identity.get("vulnerability_id")
    package_name = identity.get("package_name")
    if not decision_identity["vulnerability_id"] or not decision_identity["package_name"]:
        return False
    if not vulnerability or not package_name:
        return False
    if decision_identity["vulnerability_id"] != vulnerability:
        return False
    if decision_identity["package_name"] != package_name:
        return False
    decision_ecosystem = decision_identity.get("package_ecosystem")
    target_ecosystem = identity.get("package_ecosystem")
    if decision_ecosystem and target_ecosystem and decision_ecosystem != target_ecosystem:
        return False
    decision_key = decision_identity.get("component_package_key")
    target_key = identity.get("component_package_key")
    if decision_key and target_key and decision_key.casefold() != target_key.casefold():
        return False
    decision_purl = _package_url_without_version(decision_identity.get("package_url"))
    target_purl = _package_url_without_version(identity.get("package_url"))
    if decision_purl and target_purl and decision_purl != target_purl:
        return False
    return True


def _suppression_payload(decision: dict[str, Any] | None, *, matched_by: str) -> dict[str, Any] | None:
    if not decision:
        return None
    normalized = normalize_case_decision(decision)
    reason = _reason_text(normalized.get("vex_justification") or normalized.get("note"))
    if not reason:
        reason = _default_suppression_reason(normalized)
    return {
        "case_id": normalized.get("case_id"),
        "repo_name": normalized.get("repo_name"),
        "status": normalized.get("status"),
        "decision_status": normalized.get("status"),
        "vex_status": normalized.get("vex_status"),
        "vex_justification": reason,
        "vex_reason": reason,
        "reason": reason,
        "vulnerability_id": normalized.get("vulnerability_id"),
        "package_name": normalized.get("package_name"),
        "package_ecosystem": normalized.get("package_ecosystem"),
        "package_url": normalized.get("package_url"),
        "component_package_key": normalized.get("component_package_key"),
        "matched_by": matched_by,
        "updated_at": normalized.get("updated_at"),
    }


def _default_suppression_reason(decision: dict[str, Any]) -> str:
    status = _status_text(decision.get("status"))
    if status == "false_positive":
        return "Marked as a false positive."
    if status == "accepted_risk":
        return "Risk accepted for this project."
    return "Suppressed by case decision."


def _case_decision(case: dict[str, Any], decisions: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if isinstance(case.get("decision"), dict):
        return normalize_case_decision(case["decision"])
    case_id = _case_identity(case)
    return decisions.get(case_id)


def _decision_map(decisions: dict[str, dict[str, Any]] | Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(decisions, dict):
        values = decisions.values()
    else:
        values = decisions
    mapped: dict[str, dict[str, Any]] = {}
    for decision in values:
        if not isinstance(decision, dict):
            continue
        normalized = normalize_case_decision(decision)
        case_id = str(normalized.get("case_id") or "").strip()
        if case_id:
            mapped[case_id] = normalized
    return mapped


def _repo_matches(decision: dict[str, Any], item: dict[str, Any]) -> bool:
    decision_repo = _optional_text(decision.get("repo_name"))
    item_repo = _optional_text(item.get("repo_name") or item.get("repo"))
    if decision_repo and item_repo:
        return decision_repo == item_repo
    return True


def _is_dependency_case(case: dict[str, Any]) -> bool:
    if str(case.get("category") or "").casefold() == "dependencies":
        return True
    identity = dependency_identity_from_case(case)
    return bool(identity.get("vulnerability_id") and identity.get("package_name"))


def _case_identity(case: dict[str, Any]) -> str:
    return str(case.get("case_id") or case.get("id") or "").strip()


def _status_text(value: Any) -> str:
    return str(value or "").strip().casefold()


def _reason_text(value: Any) -> str | None:
    text = _optional_text(value)
    return redact_text(text)[:1000] if text else None


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = _optional_text(value)
        if text:
            return text
    return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_vulnerability(value: Any) -> str | None:
    text = _optional_text(value)
    return text.upper() if text else None


def _clean_package_name(value: Any) -> str | None:
    text = _optional_text(value)
    return text.casefold() if text else None


def _clean_ecosystem(value: Any) -> str | None:
    text = _optional_text(value)
    return text.casefold() if text else None


def _package_url_without_version(package_url: Any) -> str | None:
    text = _optional_text(package_url)
    if not text:
        return None
    base = text.split("?", 1)[0].split("#", 1)[0]
    if "@" not in base:
        return base.casefold()
    head, tail = base.rsplit("@", 1)
    return (head if "/" not in tail else base).casefold()


def _ecosystem_from_package_url(package_url: Any) -> str | None:
    text = _optional_text(package_url)
    if not text or not text.startswith("pkg:"):
        return None
    return text[4:].split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].casefold() or None


def _package_name_from_url(package_url: Any) -> str | None:
    text = _optional_text(package_url)
    if not text or not text.startswith("pkg:") or "/" not in text:
        return None
    body = text[4:].split("/", 1)[1].split("?", 1)[0].split("#", 1)[0]
    if "@" in body:
        head, tail = body.rsplit("@", 1)
        body = body if "/" in tail else head
    return unquote(body).casefold() or None
