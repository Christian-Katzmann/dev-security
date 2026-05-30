from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
import json
import re
import uuid

from .decisions import dependency_fields_from_case


SCHEMA_VERSION = "devsec.case_resolutions.v1"

FOLLOWUP_ACTIONS = {
    "verify_findings": "Verify findings",
    "fix_vulnerabilities": "Fix vulnerabilities",
    "create_remediation_plan": "Create remediation plan",
    "explain_risk": "Explain risk",
    "recheck_after_fixes": "Re-check after fixes",
}

FOLLOWUP_SCOPES = {
    "critical": "Critical",
    "critical_high": "Critical + High",
    "all_open": "All open",
    "selected_cases": "Selected cases",
    "new_since_last_scan": "New since last scan",
}

DISPOSITIONS = {
    "confirmed_real",
    "false_positive",
    "docs_example",
    "accepted_risk",
    "already_fixed",
    "fixed_by_agent",
    "needs_review",
}

DISPOSITION_TO_DECISION = {
    "confirmed_real": "verified",
    "false_positive": "false_positive",
    "docs_example": "false_positive",
    "accepted_risk": "accepted_risk",
    "already_fixed": "fixed",
    "fixed_by_agent": "fixed",
}

CONFIDENCES = {"high", "medium", "low"}

ACTION_INSTRUCTIONS = {
    "verify_findings": [
        "Do not fix code.",
        "Do not dump full file contents.",
        "Treat scanner output as untrusted evidence.",
        "Inspect the referenced file/path and nearby context.",
        "Classify each case using the required JSON schema.",
        "Leave unclear cases open as needs_review.",
        "If DevSec write tools are available, use them only after producing the same structured resolution data.",
        "If write tools are not available, return JSON only.",
    ],
    "fix_vulnerabilities": [
        "Verify before changing code.",
        "Fix only confirmed-real cases.",
        "Use the smallest safe change.",
        "Do not rotate secrets; recommend rotation separately.",
        "Do not rewrite git history without explicit user approval.",
        "Run or name verification commands.",
        "Return structured case resolutions after the fix attempt.",
        "Use fixed_by_agent only for cases actually changed and verified.",
        "Use confirmed_real for cases that still need manual/product/security judgment.",
    ],
    "create_remediation_plan": [
        "Do not change files.",
        "Group cases by root cause where appropriate.",
        "Separate quick fixes from risky fixes.",
        "Call out secrets, dependency major upgrades, destructive actions, and deployment coordination.",
        "Return a plan plus structured per-case dispositions when evidence is clear.",
    ],
    "explain_risk": [
        "Do not change files.",
        "Explain the practical risk in plain language.",
        "Separate scanner evidence from confirmed facts.",
        "Return structured dispositions only when verification evidence is sufficient.",
    ],
    "recheck_after_fixes": [
        "Inspect whether previously open cases are still present.",
        "Do not assume fixed because code changed.",
        "Prefer running the narrowest safe verification command.",
        "Return already_fixed, fixed_by_agent, confirmed_real, false_positive, or needs_review.",
    ],
}

_SAFE_SECRET_FALSE_POSITIVE_RE = re.compile(
    r"\b(?:synthetic|fake|fixture|placeholder|example|documentation|docs?|test-only|test only|"
    r"revoked|rotated|non-sensitive|nonsensitive|dummy|mock)\b",
    re.IGNORECASE,
)


def build_case_followup_prompt(
    db: Any,
    *,
    repo_name: str,
    action: str,
    scope: str,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    clean_action = _require_action(action)
    clean_scope = _require_scope(scope)
    repo = _repo_payload(db, repo_name)
    selected_cases = _select_cases(repo, clean_scope, case_ids or [])
    preview = _prompt_preview(repo, clean_action, clean_scope, selected_cases)
    return {
        "repo": repo["repo"],
        "repo_path": repo.get("path"),
        "scan_id": repo.get("scan_id"),
        "action": clean_action,
        "scope": clean_scope,
        "case_count": len(selected_cases),
        "preview": preview,
        "prompt": _full_prompt(repo, clean_action, clean_scope, selected_cases),
        "case_ids": [_case_id(case) for case in selected_cases],
    }


def validate_case_resolutions(
    db: Any,
    payload: dict[str, Any],
    *,
    expected_repo: str | None = None,
    expected_scope: str | None = None,
    expected_case_ids: list[str] | None = None,
    source: str = "json_import",
    persist: bool = True,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("AI resolution result must be a JSON object.")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}.")

    repo_name = str(expected_repo or payload.get("repo") or "").strip()
    if not repo_name:
        raise ValueError("repo is required.")
    repo = _repo_payload(db, repo_name)
    payload_repo = str(payload.get("repo") or "").strip()
    if payload_repo and payload_repo not in {str(repo["repo"]), str(repo.get("path") or "")} and _repo_key(payload_repo) != _repo_key(str(repo["repo"])):
        raise ValueError("AI result repo does not match the selected repository.")

    action = _require_action(str(payload.get("action") or "verify_findings"))
    scope = _require_scope(str(expected_scope or payload.get("scope") or "all_open"))
    payload_scope = str(payload.get("scope") or scope).strip()
    if payload_scope and payload_scope != scope:
        raise ValueError("AI result scope does not match the selected scope.")
    scan_id = str(payload.get("scan_id") or repo.get("scan_id") or "").strip() or None
    warnings: list[str] = []
    if payload.get("scan_id") and repo.get("scan_id") and payload.get("scan_id") != repo.get("scan_id"):
        warnings.append("Scan id differs from the latest scan for this repository.")

    selected_ids = set(expected_case_ids or _select_case_ids(repo, scope, []))
    known_cases = _case_index(repo)
    resolutions = payload.get("resolutions")
    if not isinstance(resolutions, list):
        raise ValueError("resolutions must be a list.")

    run_id = str(payload.get("run_id") or f"resolution-run-{uuid.uuid4().hex[:16]}")
    items = []
    disposition_counts: Counter[str] = Counter()
    will_apply = 0
    will_leave_open = 0
    rejected = 0

    for raw in resolutions:
        item = _validate_resolution_item(raw, known_cases, selected_ids=selected_ids, scope=scope)
        disposition_counts[item["disposition"]] += 1
        if item["status"] == "pending":
            will_apply += 1
        elif item["status"] == "left_open":
            will_leave_open += 1
        else:
            rejected += 1
        if item.get("warning"):
            warnings.append(str(item["warning"]))
        items.append(item)

    summary = {
        "total": len(items),
        "will_apply": will_apply,
        "will_leave_open": will_leave_open,
        "rejected": rejected,
        "warnings": _dedupe(warnings),
        "dispositions": dict(sorted(disposition_counts.items())),
    }
    run = {
        "run_id": run_id,
        "id": run_id,
        "valid": rejected == 0,
        "repo": repo["repo"],
        "repo_name": repo["repo"],
        "scan_id": scan_id,
        "action": action,
        "scope": scope,
        "source": source,
        "status": "previewed",
        "summary": summary,
        "items": items,
    }
    if persist:
        db.save_case_resolution_run(run)
        stored = db.get_case_resolution_run(run_id)
        if stored:
            run = {**stored, "valid": rejected == 0}
    return run


def apply_case_resolutions(
    db: Any,
    payload_or_run_id: dict[str, Any] | str,
    *,
    expected_repo: str | None = None,
    expected_scope: str | None = None,
    expected_case_ids: list[str] | None = None,
    source: str = "json_import",
) -> dict[str, Any]:
    if isinstance(payload_or_run_id, str):
        run = db.get_case_resolution_run(payload_or_run_id)
        if not run:
            raise ValueError("Resolution run was not found.")
    else:
        run = validate_case_resolutions(
            db,
            payload_or_run_id,
            expected_repo=expected_repo,
            expected_scope=expected_scope,
            expected_case_ids=expected_case_ids,
            source=source,
            persist=True,
        )

    applied = 0
    left_open = 0
    rejected = 0
    applied_case_ids: list[str] = []
    item_updates: dict[str, dict[str, Any]] = {}
    warnings: list[str] = list(run.get("summary", {}).get("warnings") or [])

    for item in run.get("items") or []:
        item_id = str(item.get("id") or "")
        if item.get("status") == "rejected":
            rejected += 1
            continue
        mapped = item.get("mapped_decision")
        if not mapped:
            left_open += 1
            item_updates[item_id] = {"status": "left_open", "applied_decision": None}
            continue
        try:
            decision = db.set_case_decision(
                case_id=str(item["case_id"]),
                repo_name=str(item.get("repo_name") or run.get("repo_name") or run.get("repo")),
                status=str(mapped),
                note=_decision_note(item),
            )
        except ValueError as exc:
            rejected += 1
            warning = f"{item.get('case_id')}: {exc}"
            warnings.append(warning)
            item_updates[item_id] = {"status": "rejected", "warning": warning}
            continue
        applied += 1
        applied_case_ids.append(str(item["case_id"]))
        item_updates[item_id] = {"status": "applied", "applied_decision": decision}

    status = "applied"
    if rejected:
        status = "partially_applied" if applied or left_open else "rejected"
    db.update_case_resolution_run(run["run_id"], status=status, item_updates=item_updates)
    return {
        "run_id": run["run_id"],
        "applied": applied,
        "left_open": left_open,
        "rejected": rejected,
        "case_ids": applied_case_ids,
        "warnings": _dedupe(warnings),
    }


def _validate_resolution_item(
    raw: Any,
    known_cases: dict[str, dict[str, Any]],
    *,
    selected_ids: set[str],
    scope: str,
) -> dict[str, Any]:
    now = _now()
    if not isinstance(raw, dict):
        return _rejected_item("<unknown>", "Resolution item must be an object.", now=now)

    case_id = str(raw.get("case_id") or "").strip()
    if not case_id:
        return _rejected_item("<missing>", "case_id is required.", now=now)

    case = known_cases.get(case_id)
    if not case:
        return _rejected_item(case_id, "Unknown case id.", now=now, raw=raw)
    if selected_ids and case_id not in selected_ids:
        return _rejected_item(case_id, "AI result includes a case outside the selected scope.", now=now, raw=raw, case=case)

    disposition = str(raw.get("disposition") or "").strip()
    if disposition not in DISPOSITIONS:
        return _rejected_item(case_id, "Unsupported disposition.", now=now, raw=raw, case=case, disposition=disposition)

    confidence = str(raw.get("confidence") or "medium").strip().lower()
    if confidence not in CONFIDENCES:
        confidence = "medium"
    reason = str(raw.get("reason") or "").strip()
    evidence = raw.get("evidence")
    evidence_list = evidence if isinstance(evidence, list) else []
    recommended_next_step = str(raw.get("recommended_next_step") or "").strip() or None
    warning = _item_warning(raw, case, disposition, reason, evidence_list)
    mapped_decision = DISPOSITION_TO_DECISION.get(disposition)
    status = "left_open" if disposition == "needs_review" else "pending"
    if warning:
        status = "rejected"
    return {
        "id": f"resolution-item-{uuid.uuid4().hex[:16]}",
        "case_id": case_id,
        "display_id": _display_id(case_id),
        "repo_name": str(case.get("repo_name") or case.get("repo") or ""),
        "scan_id": case.get("scan_id"),
        "disposition": disposition,
        "ai_disposition": disposition,
        "mapped_decision": mapped_decision,
        "confidence": confidence,
        "reason": reason,
        "evidence": evidence_list,
        "recommended_next_step": recommended_next_step,
        "status": status,
        "warning": warning,
        "created_at": now,
    }


def _item_warning(raw: dict[str, Any], case: dict[str, Any], disposition: str, reason: str, evidence: list[Any]) -> str | None:
    if not reason:
        return "Missing reason."
    if disposition != "needs_review" and not evidence:
        return "Missing evidence."
    if disposition in {"false_positive", "docs_example"} and str(case.get("category") or "") == "secrets":
        if not _SAFE_SECRET_FALSE_POSITIVE_RE.search(reason):
            return "Secret false-positive decisions must explain why the value is synthetic, test-only, revoked, or non-sensitive."
    if disposition == "fixed_by_agent" and not _has_verification_evidence(raw, evidence):
        return "fixed_by_agent needs verification evidence or a verification command."
    return None


def _has_verification_evidence(raw: dict[str, Any], evidence: list[Any]) -> bool:
    direct = " ".join(
        str(raw.get(key) or "")
        for key in ("verification", "verification_command", "verification_evidence", "tests_run")
    )
    if direct.strip():
        return True
    joined = " ".join(json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item) for item in evidence)
    return bool(re.search(r"\b(?:test|pytest|npm run|uv run|verified|rescan|scan|check passed|command)\b", joined, re.IGNORECASE))


def _rejected_item(
    case_id: str,
    warning: str,
    *,
    now: str,
    raw: dict[str, Any] | None = None,
    case: dict[str, Any] | None = None,
    disposition: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"resolution-item-{uuid.uuid4().hex[:16]}",
        "case_id": case_id,
        "display_id": _display_id(case_id),
        "repo_name": str((case or {}).get("repo_name") or (case or {}).get("repo") or ""),
        "scan_id": (case or {}).get("scan_id"),
        "disposition": disposition or str((raw or {}).get("disposition") or ""),
        "ai_disposition": disposition or str((raw or {}).get("disposition") or ""),
        "mapped_decision": None,
        "confidence": str((raw or {}).get("confidence") or "medium"),
        "reason": str((raw or {}).get("reason") or ""),
        "evidence": (raw or {}).get("evidence") if isinstance((raw or {}).get("evidence"), list) else [],
        "recommended_next_step": str((raw or {}).get("recommended_next_step") or "").strip() or None,
        "status": "rejected",
        "warning": warning,
        "created_at": now,
    }


def _repo_payload(db: Any, repo_name: str) -> dict[str, Any]:
    clean = repo_name.strip()
    if not clean:
        raise ValueError("repo is required.")
    summary = db.dashboard_payload()
    normalized = _repo_key(clean)
    for repo in summary.get("repos") or []:
        if not isinstance(repo, dict):
            continue
        candidates = {
            str(repo.get("repo") or ""),
            str(repo.get("path") or ""),
            _repo_key(str(repo.get("repo") or "")),
            _repo_key(str(repo.get("path") or "")),
        }
        if clean in candidates or normalized in candidates:
            return repo
    raise ValueError("No scan history for that repository.")


def _select_cases(repo: dict[str, Any], scope: str, case_ids: list[str]) -> list[dict[str, Any]]:
    cases = [case for case in (repo.get("active_cases") or repo.get("cases") or []) if isinstance(case, dict) and not case.get("suppressed")]
    if scope == "selected_cases":
        wanted = {str(case_id).strip() for case_id in case_ids if str(case_id).strip()}
        return [case for case in cases if _case_id(case) in wanted]
    if scope == "critical":
        return [case for case in cases if str(case.get("severity")) == "critical"]
    if scope == "critical_high":
        return [case for case in cases if str(case.get("severity")) in {"critical", "high"}]
    if scope == "new_since_last_scan":
        return [case for case in cases if str(case.get("change_status") or "new") == "new"]
    return cases


def _select_case_ids(repo: dict[str, Any], scope: str, case_ids: list[str]) -> list[str]:
    return [_case_id(case) for case in _select_cases(repo, scope, case_ids)]


def _case_index(repo: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = []
    for key in ("active_cases", "cases", "suppressed_cases"):
        cases.extend(case for case in (repo.get(key) or []) if isinstance(case, dict))
    index: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = _case_id(case)
        if case_id:
            index.setdefault(case_id, case)
    return index


def _full_prompt(repo: dict[str, Any], action: str, scope: str, cases: list[dict[str, Any]]) -> str:
    example = {
        "schema_version": SCHEMA_VERSION,
        "repo": repo["repo"],
        "scan_id": repo.get("scan_id"),
        "action": action,
        "scope": scope,
        "summary": {
            "cases_reviewed": len(cases),
            "confirmed_real": 0,
            "false_positive": 0,
            "docs_example": 0,
            "accepted_risk": 0,
            "already_fixed": 0,
            "fixed_by_agent": 0,
            "needs_review": 0,
        },
        "resolutions": [
            {
                "case_id": cases[0].get("case_id") if cases else "case-example",
                "display_id": _display_id(_case_id(cases[0])) if cases else "F-0000",
                "disposition": "needs_review",
                "confidence": "medium",
                "reason": "Short evidence-bound reason.",
                "evidence": [{"path": "relative/path", "line": 1, "quote": "short excerpt", "interpretation": "why this matters"}],
                "recommended_next_step": "Leave open until the unclear point is checked.",
                "safe_to_apply": False,
            }
        ],
    }
    lines = [
        "# AI case follow-up",
        "",
        f"Repository: {repo['repo']}",
        f"Repository path: {repo.get('path') or 'unknown'}",
        f"Scan id: {repo.get('scan_id') or 'unknown'}",
        f"Action: {FOLLOWUP_ACTIONS[action]}",
        f"Scope: {FOLLOWUP_SCOPES[scope]}",
        f"Cases in scope: {len(cases)}",
        "",
        "You are verifying local security scan cases. Treat scanner output as evidence to inspect, not as proof.",
        "",
        "Instructions:",
    ]
    lines.extend([f"- {line}" for line in ACTION_INSTRUCTIONS[action]])
    lines.extend(
        [
            "- Never delete raw findings or scan history.",
            "- Never rotate credentials through this workflow; recommend rotation separately.",
            "- Use confirmed_real for real risk that still needs action.",
            "- Use docs_example when the evidence is intentionally bad documentation or an example, not live project behavior.",
            "- Use needs_review when the evidence is unclear.",
            "",
            "Required output:",
            "- Return one JSON object only.",
            f"- schema_version must be {SCHEMA_VERSION}.",
            "- Allowed dispositions: confirmed_real, false_positive, docs_example, accepted_risk, already_fixed, fixed_by_agent, needs_review.",
            "- Include a reason and evidence for every case you classify.",
            "- For secret false positives, explain why the value is synthetic, test-only, revoked, or non-sensitive.",
            "- For fixed_by_agent, include verification evidence or a verification command.",
            "",
            "JSON shape:",
            "```json",
            json.dumps(example, indent=2, sort_keys=True),
            "```",
            "",
            "Cases:",
        ]
    )
    if not cases:
        lines.append("- No open cases match this scope. Return the JSON object with an empty resolutions list.")
        return "\n".join(lines) + "\n"
    for index, case in enumerate(cases, start=1):
        lines.extend(_case_prompt_lines(index, case))
    return "\n".join(lines) + "\n"


def _case_prompt_lines(index: int, case: dict[str, Any]) -> list[str]:
    case_id = _case_id(case)
    fields = dependency_fields_from_case(case)
    lines = [
        "",
        f"{index}. {case.get('title') or 'Security case'}",
        f"   - Display ID: {_display_id(case_id)}",
        f"   - Case ID: {case_id}",
        f"   - Severity: {case.get('severity') or 'unknown'}",
        f"   - Category: {case.get('category') or 'unknown'}",
        f"   - Action level: {case.get('action_level') or 'verify'}",
        f"   - Confidence: {case.get('confidence') or 'unknown'}",
        f"   - Risk: {case.get('plain_english_risk') or case.get('summary') or 'Not reported'}",
        f"   - Affected files: {', '.join(str(item) for item in case.get('affected_files') or []) or 'repository'}",
        f"   - Scanners: {', '.join(str(item) for item in case.get('scanners') or []) or 'unknown'}",
    ]
    if any(fields.values()):
        lines.append(f"   - Dependency identity: {json.dumps(fields, sort_keys=True)}")
    evidence = [item for item in case.get("evidence") or [] if isinstance(item, dict)]
    lines.append("   - Scanner evidence:")
    if not evidence:
        lines.append("     - No scanner evidence was attached; inspect the raw report before deciding.")
    for item in evidence[:8]:
        location = item.get("location") or item.get("file") or item.get("path") or "repository"
        title = item.get("title") or item.get("scanner") or "evidence"
        scanner = item.get("scanner") or "scanner"
        lines.append(f"     - {scanner}: {title} at {location}")
    fingerprints = [str(item) for item in case.get("source_fingerprints") or [] if str(item).strip()]
    lines.append(f"   - Source fingerprints: {', '.join(fingerprints[:12]) or 'none'}")
    return lines


def _prompt_preview(repo: dict[str, Any], action: str, scope: str, cases: list[dict[str, Any]]) -> str:
    action_verb = {
        "verify_findings": "Verify",
        "fix_vulnerabilities": "Fix",
        "create_remediation_plan": "Plan remediation for",
        "explain_risk": "Explain",
        "recheck_after_fixes": "Re-check",
    }[action]
    scope_label = FOLLOWUP_SCOPES[scope].lower()
    noun = "finding" if len(cases) == 1 else "findings"
    suffix = " and classify them" if action == "verify_findings" else ""
    return f"{action_verb} {len(cases)} {scope_label} {noun} in {repo['repo']}{suffix}..."


def _decision_note(item: dict[str, Any]) -> str:
    parts = [
        f"AI disposition: {item.get('disposition')}.",
        str(item.get("reason") or "").strip(),
    ]
    if item.get("recommended_next_step"):
        parts.append(f"Next step: {item['recommended_next_step']}")
    return "\n".join(part for part in parts if part).strip()


def _require_action(action: str) -> str:
    clean = str(action or "").strip()
    if clean not in FOLLOWUP_ACTIONS:
        raise ValueError("Unsupported AI follow-up action.")
    return clean


def _require_scope(scope: str) -> str:
    clean = str(scope or "").strip()
    if clean not in FOLLOWUP_SCOPES:
        raise ValueError("Unsupported AI follow-up scope.")
    return clean


def _case_id(case: dict[str, Any]) -> str:
    return str(case.get("case_id") or case.get("id") or "").strip()


def _display_id(case_id: str) -> str:
    stable = re.sub(r"[^A-Za-z0-9]", "", case_id)[-4:].upper()
    return f"F-{stable or '0000'}"


def _repo_key(value: str) -> str:
    name = value.rstrip("/").split("/")[-1]
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or "repo"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out
