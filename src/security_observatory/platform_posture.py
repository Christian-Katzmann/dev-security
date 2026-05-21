from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import hashlib
import json
import re

from .model import Finding, normalize_severity, redact_text


SNAPSHOT_SCHEMA_VERSION = 1
FAILED_STATUS = "FAILED"
PASSED_STATUS = "PASSED"
SKIPPED_STATUS = "SKIPPED"

IMPORTANT_REGRESSION_RULES = (
    (
        ("missing_default_branch_protection", "branch protection"),
        "Default branch protection was disabled",
        "high",
        "The default branch was protected before, but the latest platform posture scan reports that protection is now missing.",
    ),
    (
        ("token_default_permissions_is_read_write", "token permission", "workflow token"),
        "Default workflow token permissions widened",
        "high",
        "The workflow token was previously least-privilege, but the latest platform posture scan reports read-write defaults.",
    ),
    (
        ("actions_can_approve_pull_requests", "approve pull requests"),
        "Workflow approval permissions widened",
        "high",
        "GitHub Actions can now approve pull requests, which can weaken review controls.",
    ),
    (
        ("requires_status_checks", "status checks"),
        "Required status checks were weakened",
        "medium",
        "Required checks passed before, but the latest platform posture scan reports that merge checks are no longer enforced.",
    ),
    (
        ("code_review_not_required", "require code review"),
        "Code review protection was weakened",
        "high",
        "Code review was previously enforced, but the latest platform posture scan reports that review is no longer required.",
    ),
)


def sanitize_legitify_payload(data: Any) -> dict[str, Any]:
    records = platform_posture_records(data)
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "scanner": "legitify",
        "type": "platform-posture-snapshot",
        "content": {
            "summary": _summary(records),
            "records": records,
        },
    }


def build_platform_posture_snapshot(
    data: Any,
    *,
    repo_name: str,
    scanner_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    records = platform_posture_records(data)
    status = _snapshot_status(records, scanner_status)
    reason = _status_reason(status, scanner_status)
    summary = _summary(records)
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "repo_name": repo_name,
        "scanner": "legitify",
        "source": "legitify",
        "target": "repository",
        "status": status,
        "reason": reason,
        "summary": summary,
        "records": records,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    snapshot["snapshot_fingerprint"] = platform_posture_snapshot_fingerprint(snapshot)
    return _sanitize_snapshot(snapshot)


def platform_posture_records(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []

    content = data.get("content")
    if isinstance(content, dict) and isinstance(content.get("records"), list):
        return [_sanitize_record(record) for record in content["records"] if isinstance(record, dict)]

    records: list[dict[str, Any]] = []
    for policy_key, policy in _iter_legitify_policies(data):
        policy_info = policy.get("policyInfo") if isinstance(policy.get("policyInfo"), dict) else {}
        violations = policy.get("violations") if isinstance(policy.get("violations"), list) else []
        for violation in violations:
            if not isinstance(violation, dict):
                continue
            records.append(_record_from_legitify_policy(str(policy_key), policy_info, violation))
    return records


def platform_posture_regression_findings(
    repo_name: str,
    current_snapshot: dict[str, Any] | None,
    previous_snapshot: dict[str, Any] | None,
) -> list[Finding]:
    if not current_snapshot or not previous_snapshot:
        return []
    current_records = [_sanitize_record(item) for item in current_snapshot.get("records", []) if isinstance(item, dict)]
    previous_by_key = {
        _record_identity(record): _sanitize_record(record)
        for record in previous_snapshot.get("records", [])
        if isinstance(record, dict)
    }
    findings: list[Finding] = []
    for record in current_records:
        if str(record.get("status") or "").upper() != FAILED_STATUS:
            continue
        previous = previous_by_key.get(_record_identity(record))
        if not previous or str(previous.get("status") or "").upper() != PASSED_STATUS:
            continue
        rule = _regression_rule(record)
        if not rule:
            continue
        title, severity, reason = rule
        policy_title = str(record.get("title") or record.get("policy_name") or "platform policy")
        before = f"{policy_title}: {PASSED_STATUS.lower()}"
        after = f"{policy_title}: {FAILED_STATUS.lower()}"
        fingerprint = _drift_fingerprint(repo_name, record, title)
        remediation = _text(record.get("remediation")) or "Review the platform setting and restore the stricter repository protection."
        findings.append(
            Finding(
                repo=repo_name,
                scanner="legitify-drift",
                severity=severity,
                category="platform-posture",
                title=title,
                file=_text(record.get("resource_label")) or _text(record.get("namespace")) or "platform",
                remediation=remediation,
                behavior_category="platform-posture",
                evidence_summary=f"{reason} This is a change-aware alert from the previous saved platform posture snapshot.",
                before_behavior=before,
                after_behavior=after,
                fingerprint=fingerprint,
            )
        )
    return findings


def platform_posture_snapshot_fingerprint(snapshot: dict[str, Any]) -> str:
    records = snapshot.get("records") if isinstance(snapshot, dict) else []
    stable_records = [
        {
            "policy_key": record.get("policy_key"),
            "resource_ref": record.get("resource_ref"),
            "status": str(record.get("status") or "").upper(),
        }
        for record in records
        if isinstance(record, dict)
    ]
    payload = json.dumps(sorted(stable_records, key=lambda item: json.dumps(item, sort_keys=True)), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _iter_legitify_policies(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    content = data.get("content")
    if isinstance(content, dict) and all(isinstance(value, dict) for value in content.values()):
        return [
            (str(key), value)
            for key, value in content.items()
            if isinstance(value, dict) and isinstance(value.get("policyInfo"), dict)
        ]
    policies: list[tuple[str, dict[str, Any]]] = []
    _collect_policy_objects(data, policies)
    return policies


def _collect_policy_objects(value: Any, policies: list[tuple[str, dict[str, Any]]]) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_policy_objects(item, policies)
        return
    if not isinstance(value, dict):
        return
    if isinstance(value.get("policyInfo"), dict) and isinstance(value.get("violations"), list):
        info = value["policyInfo"]
        key = _text(info.get("fullyQualifiedPolicyName")) or _text(info.get("policyName")) or f"policy-{len(policies) + 1}"
        policies.append((key, value))
        return
    for item in value.values():
        _collect_policy_objects(item, policies)


def _record_from_legitify_policy(policy_key: str, policy_info: dict[str, Any], violation: dict[str, Any]) -> dict[str, Any]:
    policy_name = _text(policy_info.get("policyName")) or policy_key.rsplit(".", 1)[-1]
    status = str(violation.get("status") or "UNKNOWN").strip().upper() or "UNKNOWN"
    resource_type = _text(violation.get("violationEntityType")) or _text(policy_info.get("namespace")) or "platform-resource"
    return _sanitize_record(
        {
            "policy_key": _text(policy_info.get("fullyQualifiedPolicyName")) or policy_key,
            "policy_name": policy_name,
            "title": _text(policy_info.get("title")) or policy_name.replace("_", " ").title(),
            "severity": normalize_severity(policy_info.get("severity") or "medium"),
            "namespace": _text(policy_info.get("namespace")),
            "status": status,
            "resource_type": resource_type,
            "resource_ref": _resource_ref(violation),
            "resource_label": resource_type,
            "description": _text(policy_info.get("description")),
            "remediation": _joined_text(policy_info.get("remediationSteps")),
        }
    )


def _sanitize_record(record: dict[str, Any]) -> dict[str, Any]:
    policy_key = _text(record.get("policy_key")) or _text(record.get("fullyQualifiedPolicyName")) or "platform-policy"
    policy_name = _text(record.get("policy_name")) or policy_key.rsplit(".", 1)[-1]
    status = str(record.get("status") or "UNKNOWN").strip().upper() or "UNKNOWN"
    resource_type = _text(record.get("resource_type")) or _text(record.get("violationEntityType")) or "platform-resource"
    resource_ref = _text(record.get("resource_ref")) or _hash_ref("resource", resource_type, policy_key)
    return {
        "policy_key": _identifier(policy_key),
        "policy_name": _identifier(policy_name),
        "title": redact_text(_text(record.get("title")) or policy_name.replace("_", " ").title()),
        "severity": normalize_severity(record.get("severity") or "medium"),
        "namespace": _identifier(_text(record.get("namespace")) or ""),
        "status": status,
        "resource_type": _identifier(resource_type),
        "resource_ref": resource_ref,
        "resource_label": _identifier(_text(record.get("resource_label")) or resource_type),
        "description": redact_text(_text(record.get("description")) or ""),
        "remediation": redact_text(_text(record.get("remediation")) or ""),
    }


def _resource_ref(violation: dict[str, Any]) -> str:
    aux = violation.get("aux") if isinstance(violation.get("aux"), dict) else {}
    return _hash_ref(
        "resource",
        violation.get("violationEntityType"),
        violation.get("canonicalLink"),
        aux.get("entityId"),
        aux.get("entityName"),
    )


def _hash_ref(prefix: str, *values: Any) -> str:
    text = "|".join(str(value) for value in values if value)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_namespace: dict[str, int] = {}
    for record in records:
        status = str(record.get("status") or "UNKNOWN").upper()
        severity = normalize_severity(record.get("severity"))
        namespace = _text(record.get("namespace")) or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        if status == FAILED_STATUS:
            by_severity[severity] = by_severity.get(severity, 0) + 1
            by_namespace[namespace] = by_namespace.get(namespace, 0) + 1
    return {
        "records": len(records),
        "failed": by_status.get(FAILED_STATUS, 0),
        "passed": by_status.get(PASSED_STATUS, 0),
        "skipped": by_status.get(SKIPPED_STATUS, 0),
        "by_status": by_status,
        "failed_by_severity": by_severity,
        "failed_by_namespace": by_namespace,
    }


def _sanitize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    clean = dict(snapshot)
    if clean.get("reason"):
        clean["reason"] = redact_text(str(clean["reason"]))
    return clean


def _snapshot_status(records: list[dict[str, Any]], scanner_status: dict[str, Any] | None) -> str:
    scanner_state = str((scanner_status or {}).get("status") or "").casefold()
    if "skip" in scanner_state:
        return "skipped"
    if (scanner_status or {}).get("error") or (scanner_status and not scanner_status.get("available", True)):
        return "partial" if records else "skipped"
    if records:
        return "checked"
    return "empty"


def _status_reason(status: str, scanner_status: dict[str, Any] | None) -> str:
    if scanner_status and scanner_status.get("error"):
        return str(scanner_status["error"])
    if status == "checked":
        return "legitify returned sanitized platform posture records."
    if status == "empty":
        return "legitify ran, but no platform posture records were saved."
    if status == "partial":
        return "legitify returned partial platform posture records."
    return "Platform posture was not checked."


def _regression_rule(record: dict[str, Any]) -> tuple[str, str, str] | None:
    haystack = " ".join(
        str(record.get(key) or "")
        for key in ("policy_key", "policy_name", "title", "description")
    ).casefold()
    compact = re.sub(r"[^a-z0-9]+", "_", haystack)
    for tokens, title, severity, reason in IMPORTANT_REGRESSION_RULES:
        for token in tokens:
            token_text = token.casefold()
            token_compact = re.sub(r"[^a-z0-9]+", "_", token_text)
            if token_text in haystack or token_compact in compact:
                return title, severity, reason
    return None


def _drift_fingerprint(repo_name: str, record: dict[str, Any], title: str) -> str:
    key = "|".join(
        [
            repo_name,
            "legitify-drift",
            title,
            str(record.get("policy_key") or ""),
            str(record.get("resource_ref") or ""),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def _record_identity(record: dict[str, Any]) -> str:
    return "|".join([str(record.get("policy_key") or ""), str(record.get("resource_ref") or "")])


def _joined_text(value: Any) -> str | None:
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip()) or None
    return _text(value)


def _identifier(value: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", "", value).strip()[:240]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
