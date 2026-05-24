from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
import json
import re

from .cases import scanner_evidence_gaps
from .model import redact_text, sanitize_json
from .scanners import scan_profile_catalog, security_pack_catalog, tool_catalog
from .storage import ObservatoryDB


AGENT_CONTEXT_SCHEMA_VERSION = "agent-lab.context.v1"
AGENT_PROPOSAL_SCHEMA_VERSION = "agent-lab.proposal.v1"
AGENT_PROPOSAL_MAX_BYTES = 64_000
AGENT_LAB_ALLOWED_SCAN_PROFILE_IDS = ("quick", "code", "ai", "deps", "secrets", "iac")
AGENT_LAB_BLOCKED_ACTIONS = (
    "arbitrary_command",
    "pack_execution",
    "external_surface_scan",
    "provider_oauth",
    "install_tool",
    "uninstall_tool",
    "policy_override",
    "direct_scanner_execution",
)
AGENT_LAB_ALLOWED_ADAPTER_IDS = ("codex", "claude-code", "local-agent", "manual-json")
AGENT_LAB_ALLOWED_PROPOSAL_ACTIONS = ("run_scan_profile",)
AGENT_LAB_ALLOWED_EXECUTION_MODES = ("dry_run_preview", "approved_run")
AGENT_LAB_EXECUTION_PLAN_VERSION = "agent-lab.execution-plan.v1"
AGENT_LAB_RUNNABLE_INSTALL_STATES = {"built-in", "managed", "detected"}
AGENT_LAB_ALLOWED_PERMISSIONS = (
    "local_repo_read",
    "read_devsec_context",
    "read_scan_history",
    "write_devsec_reports",
)

_PROPOSAL_TOP_LEVEL_KEYS = {
    "schema_version",
    "proposal_id",
    "source",
    "context",
    "summary",
    "recommended_tools",
    "recommended_packs",
    "requested_execution",
    "requested_permissions",
    "expected_evidence_gaps",
    "blocked_requests",
    "notes",
}
_PROPOSAL_REQUIRED_KEYS = {
    "schema_version",
    "proposal_id",
    "source",
    "context",
    "summary",
    "recommended_tools",
    "recommended_packs",
    "requested_execution",
    "requested_permissions",
}
_SOURCE_KEYS = {"adapter_id", "agent_label", "created_at"}
_SOURCE_REQUIRED_KEYS = {"adapter_id", "agent_label"}
_CONTEXT_KEYS = {"context_id", "context_hash", "repo_path"}
_CONTEXT_REQUIRED_KEYS = {"context_id", "repo_path"}
_RECOMMENDED_TOOL_KEYS = {"tool_id", "reason", "expected_benefit", "safety_labels"}
_RECOMMENDED_PACK_KEYS = {"pack_id", "reason", "runnable"}
_EXECUTION_KEYS = {"action", "scan_profile_id", "tool_ids", "mode", "requires_approval", "reason"}
_EVIDENCE_GAP_KEYS = {"tool_id", "reason", "user_message"}
_BLOCKED_REQUEST_KEYS = {"reason", "detail"}


class AgentLabProposalValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("Agent Lab proposal validation failed")
        self.errors = errors


class AgentLabExecutionError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("Agent Lab execution routing failed")
        self.errors = errors


def build_agent_context_payload(
    db: ObservatoryDB,
    *,
    repo_path: str | None = None,
    repo_name: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build the bounded Agent Lab context export for user-mediated planners."""

    created = created_at or datetime.now(timezone.utc).isoformat()
    managed_tool_records = db.list_managed_tools()
    tools = tool_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
    packs = security_pack_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
    profiles = scan_profile_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
    repo = _repo_summary(db, repo_path=repo_path, repo_name=repo_name)
    tool_index = {str(item.get("id")): item for item in tools}
    scanner_tool_index = {
        str(item.get("scanner_key")): item
        for item in tools
        if item.get("scanner_key")
    }
    allowed_tool_ids = [
        tool_id
        for tool_id, item in tool_index.items()
        if _agent_lab_tool_allowed(item)
    ]
    allowed_tool_id_set = set(allowed_tool_ids)
    allowed_scan_profile_ids = [
        profile_id
        for profile_id in AGENT_LAB_ALLOWED_SCAN_PROFILE_IDS
        if any(str(item.get("id")) == profile_id for item in profiles)
    ]
    payload: dict[str, Any] = {
        "schema_version": AGENT_CONTEXT_SCHEMA_VERSION,
        "created_at": created,
        "product": {
            "name": "DëvSec",
            "component": "Agent Lab",
            "version": _product_version(),
        },
        "repo": repo,
        "tool_catalog": [
            _tool_context(item, agent_lab_allowed=str(item.get("id")) in allowed_tool_id_set)
            for item in tools
        ],
        "security_packs": [_pack_context(item) for item in packs],
        "scan_profiles": [
            _scan_profile_context(
                item,
                scanner_tool_index=scanner_tool_index,
                allowed_scan_profile_ids=allowed_scan_profile_ids,
                allowed_tool_ids=allowed_tool_id_set,
            )
            for item in profiles
        ],
        "scan_history_summary": _scan_history_summary(db, repo),
        "allowed_scan_profile_ids": allowed_scan_profile_ids,
        "allowed_tool_ids": allowed_tool_ids,
        "blocked_tool_ids": [tool_id for tool_id in tool_index if tool_id not in allowed_tool_id_set],
        "blocked_actions": list(AGENT_LAB_BLOCKED_ACTIONS),
        "non_runnable_pack_rules": {
            "packs_are_runnable": False,
            "allowed_pack_use": "recommendation_only",
            "execution_must_target": "scan_profile_id",
        },
        "policy_boundaries": {
            "packs_are_runnable": False,
            "external_surface_is_display_only": True,
            "proposal_actions_must_use_known_ids": True,
            "proposal_import_is_untrusted": True,
            "provider_oauth_is_deferred": True,
            "raw_reports_are_excluded": True,
            "scanner_evidence_is_authoritative": True,
            "agent_advice_is_not_evidence": True,
            "execution_requires_user_approval": True,
        },
    }
    digest = _context_digest(payload)
    payload["context_hash"] = f"sha256:{digest}"
    payload["context_id"] = f"ctx_{_slug(repo.get('name'))}_{_compact_time(created)}_{digest[:12]}"
    return payload


def proposal_from_import_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("schema_version") == AGENT_PROPOSAL_SCHEMA_VERSION:
        return payload
    if isinstance(payload, dict):
        for key in ("proposal", "proposalJson", "proposal_json"):
            if key not in payload:
                continue
            candidate = payload[key]
            if isinstance(candidate, dict):
                return candidate
            if isinstance(candidate, str):
                return _proposal_from_json_text(candidate)
    if isinstance(payload, str):
        return _proposal_from_json_text(payload)
    raise AgentLabProposalValidationError(["Import must be proposal JSON, not free-form text."])


def validate_agent_proposal(
    proposal: dict[str, Any],
    *,
    managed_tool_records: list[dict[str, Any]] | None = None,
    imported_at: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    imported = imported_at or datetime.now(timezone.utc).isoformat()
    if not isinstance(proposal, dict):
        raise AgentLabProposalValidationError(["Proposal must be a JSON object."])

    _reject_unknown_keys(proposal, _PROPOSAL_TOP_LEVEL_KEYS, "proposal", errors)
    _require_keys(proposal, _PROPOSAL_REQUIRED_KEYS, "proposal", errors)
    if proposal.get("schema_version") != AGENT_PROPOSAL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {AGENT_PROPOSAL_SCHEMA_VERSION}.")

    source = _dict_field(proposal, "source", errors)
    _reject_unknown_keys(source, _SOURCE_KEYS, "source", errors)
    _require_keys(source, _SOURCE_REQUIRED_KEYS, "source", errors)
    adapter_id = _text(source.get("adapter_id"), limit=80)
    if adapter_id not in AGENT_LAB_ALLOWED_ADAPTER_IDS:
        errors.append("source.adapter_id must be one of codex, claude-code, local-agent, or manual-json.")
    agent_label = _text(source.get("agent_label"), limit=120) or adapter_id or "Agent"
    agent_created_at = _text(source.get("created_at"), limit=80) or None

    context = _dict_field(proposal, "context", errors)
    _reject_unknown_keys(context, _CONTEXT_KEYS, "context", errors)
    _require_keys(context, _CONTEXT_REQUIRED_KEYS, "context", errors)
    context_id = _text(context.get("context_id"), limit=160)
    context_hash = _text(context.get("context_hash"), limit=120)
    repo_path = _text(context.get("repo_path"), limit=500)
    if not context_id:
        errors.append("context.context_id is required.")
    if context_hash and not context_hash.startswith("sha256:"):
        errors.append("context.context_hash must start with sha256: when provided.")

    external_proposal_id = _text(proposal.get("proposal_id"), limit=160)
    if not external_proposal_id:
        errors.append("proposal_id is required.")
    summary = _text(proposal.get("summary"), limit=1200)
    if not summary:
        errors.append("summary is required.")

    indexes = _proposal_catalog_indexes(managed_tool_records)
    recommended_tools = _normalize_recommended_tools(proposal.get("recommended_tools"), indexes, errors)
    recommended_packs = _normalize_recommended_packs(proposal.get("recommended_packs"), indexes, errors)
    requested_execution = _normalize_requested_execution(proposal.get("requested_execution"), indexes, errors)
    requested_permissions = _normalize_requested_permissions(proposal.get("requested_permissions"), errors)
    evidence_gaps = _normalize_expected_evidence_gaps(proposal.get("expected_evidence_gaps"), indexes, errors)
    blocked_requests = _normalize_blocked_requests(proposal.get("blocked_requests"), errors)
    notes = _text(proposal.get("notes"), limit=2000) or None

    if not requested_execution:
        errors.append("requested_execution must include at least one run_scan_profile item.")

    if errors:
        raise AgentLabProposalValidationError(_dedupe(errors))

    raw_proposal = sanitize_json(proposal)
    final_plan = {
        "version": AGENT_LAB_EXECUTION_PLAN_VERSION,
        "approval_required": True,
        "approval_state": "pending",
        "items": requested_execution,
    }
    record_id = _proposal_record_id(adapter_id, external_proposal_id, context_id, raw_proposal)
    return {
        "id": record_id,
        "external_proposal_id": external_proposal_id,
        "repo_name": Path(repo_path).name if repo_path else "repository",
        "repo_path": repo_path,
        "context_id": context_id,
        "context_hash": context_hash,
        "adapter_id": adapter_id,
        "agent_label": agent_label,
        "agent_created_at": agent_created_at,
        "summary": summary,
        "recommended_tools": recommended_tools,
        "recommended_packs": recommended_packs,
        "requested_permissions": requested_permissions,
        "requested_execution": requested_execution,
        "expected_evidence_gaps": evidence_gaps,
        "blocked_requests": blocked_requests,
        "notes": notes,
        "validation_status": "valid",
        "validation_errors": [],
        "approval_state": "pending",
        "imported_at": imported,
        "updated_at": imported,
        "raw_proposal": raw_proposal,
        "final_execution_plan": final_plan,
    }


def build_agent_execution_preview(
    proposal: dict[str, Any],
    *,
    managed_tool_records: list[dict[str, Any]] | None = None,
    requested_mode: str = "dry_run_preview",
    require_approval: bool = False,
) -> dict[str, Any]:
    """Convert a validated proposal record into a DëvSec scan routing plan."""

    mode = str(requested_mode or "dry_run_preview").strip() or "dry_run_preview"
    errors: list[str] = []
    if mode not in AGENT_LAB_ALLOWED_EXECUTION_MODES:
        errors.append("Execution mode must be dry_run_preview or approved_run.")

    approval_state = str(proposal.get("approval_state") or "").strip().lower() or "pending"
    if require_approval and approval_state != "approved":
        errors.append("Agent Lab execution requires an approved proposal.")

    indexes = _proposal_catalog_indexes(managed_tool_records)
    requested_items = _execution_items_from_proposal(proposal)
    if not requested_items:
        errors.append("Agent Lab proposal has no execution items.")

    scanner_names: list[str] = []
    profile_ids: list[str] = []
    preview_items: list[dict[str, Any]] = []
    evidence_gaps: list[dict[str, Any]] = []
    blocked_items: list[dict[str, Any]] = []

    for index, item in enumerate(requested_items):
        preview = _execution_item_preview(index, item, indexes)
        preview_items.append(preview)
        profile_id = str(preview.get("scan_profile_id") or "")
        if profile_id and profile_id not in profile_ids:
            profile_ids.append(profile_id)
        for scanner in preview.get("scanner_names") or []:
            if scanner not in scanner_names:
                scanner_names.append(scanner)
        for gap in preview.get("evidence_gaps") or []:
            if isinstance(gap, dict):
                evidence_gaps.append(gap)
        for blocked in preview.get("blocked") or []:
            if isinstance(blocked, dict):
                blocked_items.append(blocked)

    if require_approval and blocked_items:
        errors.append("Agent Lab execution contains policy-blocked items.")
    if require_approval and not scanner_names:
        errors.append("Agent Lab execution has no DëvSec scanner route.")
    if errors:
        raise AgentLabExecutionError(_dedupe(errors))

    return {
        "version": AGENT_LAB_EXECUTION_PLAN_VERSION,
        "proposal_id": proposal.get("id"),
        "approval_state": approval_state,
        "requested_mode": mode,
        "execution_surface": "existing_devsec_scan_pipeline",
        "dry_run": mode == "dry_run_preview",
        "can_execute": approval_state == "approved" and bool(scanner_names) and not blocked_items,
        "requires_approval": True,
        "scan_profile_ids": profile_ids,
        "scanner_names": scanner_names,
        "items": preview_items,
        "evidence_gaps": evidence_gaps,
        "blocked_items": blocked_items,
        "policy_gates": {
            "proposal_must_be_valid": proposal.get("validation_status") == "valid",
            "proposal_must_be_approved_for_run": True,
            "packs_are_runnable": False,
            "external_surface_is_display_only": True,
            "arbitrary_commands_allowed": False,
            "uses_existing_scan_pipeline": True,
        },
    }


def _repo_summary(db: ObservatoryDB, *, repo_path: str | None, repo_name: str | None) -> dict[str, Any]:
    clean_path = str(repo_path or "").strip() or None
    clean_name = str(repo_name or "").strip() or None
    if clean_path and not clean_name:
        clean_name = Path(clean_path).name
    if not clean_path and clean_name:
        latest = db.latest_scan_for_repo(clean_name)
        if latest:
            clean_path = str(latest.get("repo_path") or "") or None
    if not clean_path and not clean_name:
        latest = _latest_scan(db)
        if latest:
            clean_path = str(latest.get("repo_path") or "") or None
            clean_name = str(latest.get("repo_name") or "") or None
    return {
        "name": clean_name or "repository",
        "path": clean_path,
    }


def _latest_scan(db: ObservatoryDB) -> dict[str, Any] | None:
    row = db.conn.execute(
        """
        select *
        from scans
        order by started_at desc
        limit 1
        """
    ).fetchone()
    return dict(row) if row else None


def _tool_context(item: dict[str, Any], *, agent_lab_allowed: bool) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "label": item.get("label"),
        "summary": item.get("summary"),
        "category": item.get("category"),
        "scanner_key": item.get("scanner_key"),
        "lifecycle": item.get("lifecycle"),
        "install_state": item.get("install_state"),
        "policy": item.get("policy") or {},
        "derived_labels": item.get("derived_labels") or {},
        "capabilities": item.get("capabilities") or {},
        "packs": item.get("packs") or [],
        "profiles": item.get("profiles") or [],
        "docs_path": item.get("docs_path"),
        "homepage_url": item.get("homepage_url"),
        "agent_lab": {
            "allowed": agent_lab_allowed,
            "label": (item.get("derived_labels") or {}).get("agent_lab"),
        },
    }


def _pack_context(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "label": item.get("label"),
        "summary": item.get("summary"),
        "mvp_state": item.get("mvp_state"),
        "visibility": item.get("visibility"),
        "primary_profile": item.get("primary_profile"),
        "secondary_profiles": item.get("secondary_profiles") or [],
        "status_counts": item.get("status_counts") or {},
        "ready_count": item.get("ready_count", 0),
        "missing_count": item.get("missing_count", 0),
        "display_only_count": item.get("display_only_count", 0),
        "tools": [
            {
                "id": tool.get("id"),
                "label": tool.get("label"),
                "summary": tool.get("summary"),
                "role": tool.get("role"),
                "install_state": tool.get("install_state"),
                "lifecycle": tool.get("lifecycle"),
                "derived_labels": tool.get("derived_labels") or {},
            }
            for tool in item.get("tools", [])
            if isinstance(tool, dict)
        ],
        "agent_lab": {
            "recommendation_only": True,
            "runnable": False,
            "execution_surface": "scan_profile",
        },
    }


def _scan_profile_context(
    item: dict[str, Any],
    *,
    scanner_tool_index: dict[str, dict[str, Any]],
    allowed_scan_profile_ids: list[str],
    allowed_tool_ids: set[str],
) -> dict[str, Any]:
    scanner_keys = [str(scanner) for scanner in item.get("scanner_keys", []) if str(scanner).strip()]
    profile_tool_ids = [
        str(tool["id"])
        for scanner in scanner_keys
        for tool in [scanner_tool_index.get(scanner)]
        if tool and tool.get("id")
    ]
    blocked_tool_ids = [tool_id for tool_id in profile_tool_ids if tool_id not in allowed_tool_ids]
    return {
        "id": item.get("id"),
        "label": item.get("label"),
        "command": item.get("command"),
        "summary": item.get("summary"),
        "scanner_keys": scanner_keys,
        "tool_ids": profile_tool_ids,
        "allowed_tool_ids": [tool_id for tool_id in profile_tool_ids if tool_id in allowed_tool_ids],
        "blocked_tool_ids": blocked_tool_ids,
        "recommended_pack_ids": item.get("recommended_pack_ids") or [],
        "notes": item.get("notes") or [],
        "agent_lab": {
            "allowed": item.get("id") in allowed_scan_profile_ids,
            "requires_approval": True,
            "packs_runnable": False,
        },
    }


def _scan_history_summary(db: ObservatoryDB, repo: dict[str, Any]) -> dict[str, Any]:
    repo_name = str(repo.get("name") or "").strip()
    latest = db.latest_scan_for_repo(repo_name) if repo_name else None
    if not latest:
        return {
            "latest_scan_id": None,
            "latest_profile": None,
            "latest_status": "not_scanned",
            "latest_finished_at": None,
            "health_score": None,
            "severity_counts": {},
            "category_counts": {},
            "evidence_gap_counts": {"total": 0, "tools": {}, "profiles": {}},
            "scanner_status_counts": {},
        }
    scan = db.scan_export(str(latest["id"])) or {}
    active_findings = [item for item in scan.get("active_findings", []) if isinstance(item, dict)]
    scanner_statuses = [item for item in scan.get("scanners", []) if isinstance(item, dict)]
    evidence_gaps = scanner_evidence_gaps(scanner_statuses, profile=str(scan.get("profile") or latest.get("profile") or ""))
    return {
        "latest_scan_id": scan.get("scan_id") or latest.get("id"),
        "latest_profile": scan.get("profile") or latest.get("profile"),
        "latest_status": scan.get("status") or latest.get("status"),
        "latest_finished_at": scan.get("finished_at") or latest.get("finished_at"),
        "health_score": scan.get("health_score") or latest.get("health_score"),
        "severity_counts": _counts_by(active_findings, "severity"),
        "category_counts": _counts_by(active_findings, "category"),
        "evidence_gap_counts": _evidence_gap_counts(evidence_gaps),
        "scanner_status_counts": _scanner_status_counts(scanner_statuses),
    }


def _agent_lab_tool_allowed(item: dict[str, Any]) -> bool:
    labels = item.get("derived_labels") if isinstance(item.get("derived_labels"), dict) else {}
    return labels.get("agent_lab") == "Agent Lab allowed"


def _execution_items_from_proposal(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    final_plan = proposal.get("final_execution_plan")
    if isinstance(final_plan, dict):
        items = final_plan.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    requested = proposal.get("requested_execution")
    if isinstance(requested, list):
        return [item for item in requested if isinstance(item, dict)]
    return []


def _execution_item_preview(index: int, item: dict[str, Any], indexes: dict[str, Any]) -> dict[str, Any]:
    action = _text(item.get("action"), limit=80)
    profile_id = _text(item.get("scan_profile_id"), limit=120)
    profile = indexes["profiles"].get(profile_id)
    scanner_names: list[str] = []
    routed_tools: list[dict[str, Any]] = []
    evidence_gaps: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    if action != "run_scan_profile":
        blocked.append(_blocked_execution_item(index, None, profile_id, "unsupported_action"))
    if profile_id not in indexes["allowed_profile_ids"] or not profile:
        blocked.append(_blocked_execution_item(index, None, profile_id, "scan_profile_not_allowed"))

    profile_tool_ids = [str(tool_id) for tool_id in (profile or {}).get("tool_ids", [])]
    requested_tool_ids = _list_of_text(item.get("tool_ids"), limit=120, max_items=30)
    if not requested_tool_ids:
        requested_tool_ids = [
            tool_id
            for tool_id in profile_tool_ids
            if _tool_policy_allows_agent_lab(indexes["tools"].get(tool_id) or {})
        ]

    for tool_id in requested_tool_ids:
        tool = indexes["tools"].get(tool_id)
        if not tool:
            blocked.append(_blocked_execution_item(index, tool_id, profile_id, "unknown_tool"))
            continue
        scanner_key = _text(tool.get("scanner_key"), limit=120)
        install_state = _text(tool.get("install_state"), limit=80)
        tool_preview = {
            "tool_id": tool_id,
            "tool_label": tool.get("label") or tool_id,
            "scanner": scanner_key or None,
            "scan_profile_id": profile_id,
            "install_state": install_state,
            "lifecycle": tool.get("lifecycle"),
            "safety_labels": (tool.get("derived_labels") or {}).get("safety") or [],
            "policy": tool.get("policy") or {},
        }
        if tool_id not in profile_tool_ids:
            blocked.append(_blocked_execution_item(index, tool_id, profile_id, "tool_not_in_scan_profile"))
            routed_tools.append({**tool_preview, "status": "blocked"})
            continue
        if not _tool_policy_allows_agent_lab(tool):
            blocked.append(_blocked_execution_item(index, tool_id, profile_id, "agent_lab_policy_blocked"))
            routed_tools.append({**tool_preview, "status": "blocked"})
            continue
        if not scanner_key:
            blocked.append(_blocked_execution_item(index, tool_id, profile_id, "no_scanner_route"))
            routed_tools.append({**tool_preview, "status": "blocked"})
            continue

        if scanner_key not in scanner_names:
            scanner_names.append(scanner_key)
        if install_state not in AGENT_LAB_RUNNABLE_INSTALL_STATES:
            evidence_gaps.append(_execution_evidence_gap(tool, scanner_key, profile_id, install_state))
            routed_tools.append({**tool_preview, "status": "will_record_evidence_gap"})
        else:
            routed_tools.append({**tool_preview, "status": "routable"})

    status = "routable" if scanner_names and not blocked else "blocked" if blocked else "no_routable_tools"
    if evidence_gaps and status == "routable":
        status = "routable_with_expected_gaps"
    return {
        "index": index,
        "action": action,
        "scan_profile_id": profile_id,
        "profile_label": (profile or {}).get("label") or item.get("profile_label"),
        "mode": _text(item.get("mode"), limit=80) or "dry_run_preview",
        "reason": _text(item.get("reason"), limit=800),
        "status": status,
        "scanner_names": scanner_names,
        "tools": routed_tools,
        "evidence_gaps": evidence_gaps,
        "blocked": blocked,
    }


def _execution_evidence_gap(
    tool: dict[str, Any],
    scanner_key: str,
    profile_id: str,
    install_state: str,
) -> dict[str, Any]:
    reason = "tool is not installed or not ready locally"
    if install_state == "not-configured":
        reason = "tool needs local setup before it can run"
    elif install_state == "coming-soon":
        reason = "tool is display-only in the MVP"
    elif install_state == "unavailable":
        reason = "tool is unavailable in this environment"
    return {
        "scanner": scanner_key,
        "tool_id": tool.get("id"),
        "tool_label": tool.get("label") or scanner_key,
        "scan_profile_id": profile_id,
        "profile_ids": [profile_id] if profile_id else [],
        "gap_type": "tool_not_runnable",
        "install_state": install_state,
        "reason": reason,
        "source": "agent_lab_execution_preview",
    }


def _blocked_execution_item(
    index: int,
    tool_id: str | None,
    profile_id: str | None,
    reason: str,
) -> dict[str, Any]:
    return {
        "index": index,
        "tool_id": tool_id,
        "scan_profile_id": profile_id,
        "reason": reason,
        "source": "agent_lab_policy_gate",
    }


def _proposal_from_json_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        raise AgentLabProposalValidationError(["Import must be raw JSON, not Markdown-wrapped content."])
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise AgentLabProposalValidationError([f"Proposal JSON is invalid: {exc.msg}."]) from exc
    if not isinstance(parsed, dict):
        raise AgentLabProposalValidationError(["Proposal JSON must be one object."])
    return parsed


def _proposal_catalog_indexes(managed_tool_records: list[dict[str, Any]] | None) -> dict[str, Any]:
    tools = tool_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
    packs = security_pack_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
    profiles = scan_profile_catalog(detect_install_state=True, managed_tool_records=managed_tool_records)
    tool_index = {str(item.get("id")): item for item in tools if item.get("id")}
    scanner_tool_index = {
        str(item.get("scanner_key")): item
        for item in tools
        if item.get("scanner_key")
    }
    profile_index: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        profile_id = str(profile.get("id") or "")
        scanner_keys = [str(item) for item in profile.get("scanner_keys", []) if str(item).strip()]
        tool_ids = [
            str(tool["id"])
            for scanner in scanner_keys
            for tool in [scanner_tool_index.get(scanner)]
            if tool and tool.get("id")
        ]
        profile_index[profile_id] = {**profile, "tool_ids": tool_ids}
    return {
        "tools": tool_index,
        "packs": {str(item.get("id")): item for item in packs if item.get("id")},
        "profiles": profile_index,
        "allowed_profile_ids": {
            profile_id
            for profile_id in AGENT_LAB_ALLOWED_SCAN_PROFILE_IDS
            if profile_id in profile_index
        },
    }


def _normalize_recommended_tools(value: Any, indexes: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    items = _list_of_dicts(value, "recommended_tools", errors, max_items=30)
    normalized = []
    for index, item in enumerate(items):
        label = f"recommended_tools[{index}]"
        _reject_unknown_keys(item, _RECOMMENDED_TOOL_KEYS, label, errors)
        tool_id = _text(item.get("tool_id"), limit=120)
        tool = indexes["tools"].get(tool_id)
        if not tool:
            errors.append(f"{label}.tool_id is unknown.")
            continue
        if not _tool_policy_allows_agent_lab(tool):
            errors.append(f"{label}.tool_id is blocked for Agent Lab.")
            continue
        agent_labels = _list_of_text(item.get("safety_labels"), limit=80, max_items=12)
        canonical_labels = list((tool.get("derived_labels") or {}).get("safety") or [])
        if agent_labels and any(label not in canonical_labels for label in agent_labels):
            errors.append(f"{label}.safety_labels must match DëvSec catalog labels.")
        normalized.append(
            {
                "tool_id": tool_id,
                "label": tool.get("label"),
                "reason": _text(item.get("reason"), limit=600),
                "expected_benefit": _text(item.get("expected_benefit"), limit=600),
                "policy": tool.get("policy") or {},
                "safety_labels": canonical_labels,
                "agent_safety_labels": agent_labels,
                "install_state": tool.get("install_state"),
                "lifecycle": tool.get("lifecycle"),
            }
        )
    return normalized


def _normalize_recommended_packs(value: Any, indexes: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    items = _list_of_dicts(value, "recommended_packs", errors, max_items=20)
    normalized = []
    for index, item in enumerate(items):
        label = f"recommended_packs[{index}]"
        _reject_unknown_keys(item, _RECOMMENDED_PACK_KEYS, label, errors)
        pack_id = _text(item.get("pack_id"), limit=120)
        pack = indexes["packs"].get(pack_id)
        if not pack:
            errors.append(f"{label}.pack_id is unknown.")
            continue
        if item.get("runnable") is not False:
            errors.append(f"{label}.runnable must be false because packs are not executable in MVP.")
        normalized.append(
            {
                "pack_id": pack_id,
                "label": pack.get("label"),
                "reason": _text(item.get("reason"), limit=600),
                "runnable": False,
                "mvp_state": pack.get("mvp_state"),
            }
        )
    return normalized


def _normalize_requested_execution(value: Any, indexes: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    items = _list_of_dicts(value, "requested_execution", errors, max_items=12)
    normalized = []
    for index, item in enumerate(items):
        label = f"requested_execution[{index}]"
        _reject_unknown_keys(item, _EXECUTION_KEYS, label, errors)
        action = _text(item.get("action"), limit=80)
        if action not in AGENT_LAB_ALLOWED_PROPOSAL_ACTIONS:
            errors.append(f"{label}.action must be run_scan_profile.")
            continue
        profile_id = _text(item.get("scan_profile_id"), limit=120)
        profile = indexes["profiles"].get(profile_id)
        if profile_id not in indexes["allowed_profile_ids"] or not profile:
            errors.append(f"{label}.scan_profile_id is not allowed for Agent Lab.")
            continue
        mode = _text(item.get("mode"), limit=80) or "dry_run_preview"
        if mode not in AGENT_LAB_ALLOWED_EXECUTION_MODES:
            errors.append(f"{label}.mode must be dry_run_preview or approved_run.")
        requested_tool_ids = _list_of_text(item.get("tool_ids"), limit=120, max_items=30)
        profile_tool_ids = [str(tool_id) for tool_id in profile.get("tool_ids", [])]
        if not requested_tool_ids:
            requested_tool_ids = [
                tool_id
                for tool_id in profile_tool_ids
                if _tool_policy_allows_agent_lab(indexes["tools"].get(tool_id) or {})
            ]
        for tool_id in requested_tool_ids:
            tool = indexes["tools"].get(tool_id)
            if not tool:
                errors.append(f"{label}.tool_ids contains unknown tool_id {tool_id}.")
                continue
            if tool_id not in profile_tool_ids:
                errors.append(f"{label}.tool_ids contains {tool_id}, which is not in scan profile {profile_id}.")
            if not _tool_policy_allows_agent_lab(tool):
                errors.append(f"{label}.tool_ids contains Agent Lab blocked tool_id {tool_id}.")
        normalized.append(
            {
                "action": action,
                "scan_profile_id": profile_id,
                "profile_label": profile.get("label"),
                "tool_ids": requested_tool_ids,
                "mode": mode,
                "requires_approval": True,
                "reason": _text(item.get("reason"), limit=800),
                "status": "pending_approval",
            }
        )
    return normalized


def _normalize_requested_permissions(value: Any, errors: list[str]) -> list[str]:
    permissions = _list_of_text(value, limit=80, max_items=20)
    unknown = [item for item in permissions if item not in AGENT_LAB_ALLOWED_PERMISSIONS]
    if unknown:
        errors.append("requested_permissions contains permissions outside the Agent Lab MVP allowlist.")
    return permissions


def _normalize_expected_evidence_gaps(value: Any, indexes: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    items = _list_of_dicts(value, "expected_evidence_gaps", errors, max_items=20)
    normalized = []
    for index, item in enumerate(items):
        label = f"expected_evidence_gaps[{index}]"
        _reject_unknown_keys(item, _EVIDENCE_GAP_KEYS, label, errors)
        tool_id = _text(item.get("tool_id"), limit=120)
        if tool_id and tool_id not in indexes["tools"]:
            errors.append(f"{label}.tool_id is unknown.")
        normalized.append(
            {
                "tool_id": tool_id,
                "reason": _text(item.get("reason"), limit=160),
                "user_message": _text(item.get("user_message"), limit=600),
            }
        )
    return normalized


def _normalize_blocked_requests(value: Any, errors: list[str]) -> list[dict[str, Any]]:
    items = _list_of_dicts(value, "blocked_requests", errors, max_items=20)
    normalized = []
    for index, item in enumerate(items):
        label = f"blocked_requests[{index}]"
        _reject_unknown_keys(item, _BLOCKED_REQUEST_KEYS, label, errors)
        normalized.append(
            {
                "reason": _text(item.get("reason"), limit=160),
                "detail": _text(item.get("detail"), limit=600),
            }
        )
    return normalized


def _tool_policy_allows_agent_lab(tool: dict[str, Any]) -> bool:
    policy = tool.get("policy") if isinstance(tool.get("policy"), dict) else {}
    if not policy.get("allowed_for_agent_lab"):
        return False
    if str(tool.get("id") or "") == "external-surface":
        return False
    if str(tool.get("lifecycle") or "") in {"coming-soon", "deprecated", "hidden"}:
        return False
    if policy.get("destructive_action") or policy.get("writes_files"):
        return False
    if policy.get("external_targets") != "none":
        return False
    if policy.get("uses_credentials") == "required":
        return False
    return True


def _dict_field(value: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    item = value.get(key)
    if isinstance(item, dict):
        return item
    errors.append(f"{key} must be an object.")
    return {}


def _list_of_dicts(value: Any, field: str, errors: list[str], *, max_items: int) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{field} must be a list.")
        return []
    if len(value) > max_items:
        errors.append(f"{field} may contain at most {max_items} items.")
        return []
    clean = []
    for index, item in enumerate(value):
        if isinstance(item, dict):
            clean.append(item)
        else:
            errors.append(f"{field}[{index}] must be an object.")
    return clean


def _list_of_text(value: Any, *, limit: int, max_items: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    return [_text(item, limit=limit) for item in value[:max_items] if _text(item, limit=limit)]


def _reject_unknown_keys(value: dict[str, Any], allowed: set[str], field: str, errors: list[str]) -> None:
    unknown = sorted(str(key) for key in value if str(key) not in allowed)
    if unknown:
        errors.append(f"{field} contains unsupported fields: {', '.join(unknown)}.")


def _require_keys(value: dict[str, Any], required: set[str], field: str, errors: list[str]) -> None:
    missing = sorted(key for key in required if key not in value)
    if missing:
        errors.append(f"{field} is missing required fields: {', '.join(missing)}.")


def _text(value: Any, *, limit: int) -> str:
    if value is None:
        return ""
    return redact_text(str(value).strip())[:limit]


def _proposal_record_id(adapter_id: str, external_id: str, context_id: str, proposal: Any) -> str:
    digest = sha256(json.dumps(proposal, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"alp_{_slug(adapter_id)}_{_slug(external_id)[:40]}_{_slug(context_id)[:24]}_{digest[:12]}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    clean = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        clean.append(item)
    return clean


def _counts_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _evidence_gap_counts(gaps: list[dict[str, Any]]) -> dict[str, Any]:
    tools: dict[str, int] = {}
    profiles: dict[str, int] = {}
    for gap in gaps:
        tool_id = str(gap.get("tool_id") or gap.get("scanner") or "unknown")
        tools[tool_id] = tools.get(tool_id, 0) + 1
        for profile_id in gap.get("profile_ids", []) or []:
            profile = str(profile_id)
            profiles[profile] = profiles.get(profile, 0) + 1
    return {"total": len(gaps), "tools": tools, "profiles": profiles}


def _scanner_status_counts(statuses: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"checked": 0, "unavailable": 0, "error": 0}
    for status in statuses:
        if status.get("available") and not status.get("error"):
            counts["checked"] += 1
        elif status.get("error"):
            counts["error"] += 1
        else:
            counts["unavailable"] += 1
    return counts


def _context_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _compact_time(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "", value)[:15] or "time"


def _slug(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "repository").strip().lower()).strip("-")
    return text or "repository"


def _product_version() -> str:
    try:
        return version("security-observatory")
    except PackageNotFoundError:
        return "0.1.0"
