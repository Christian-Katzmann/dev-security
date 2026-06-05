"""Dashboard UI-payload assembly (the ``/api/summary`` body).

Lifted out of ``ObservatoryDB`` (S-017): persistence owns the schema and the
queries, and this module owns the cross-layer assembly — embedding the live
scanner/tool/pack catalogs and turning raw rows into the per-repo UI payload.
That removes the persistence→scanner-orchestration import inversion (only this
higher layer imports ``scanners``) and gives the dashboard server a single,
testable assembly seam.

The per-repo fan-out is replaced by set-based batch reads (S-027): for every
data kind the assembly pulls one ``scan_id IN (...)`` / ``run_id IN (...)``
query from ``storage`` and joins it in memory, so the query count is O(1) in
repo count and the per-run ``case_resolution_items`` N+1 collapses to a single
pull. The output dict is byte-for-byte identical to the pre-refactor payload.
"""

from __future__ import annotations

from typing import Any
import json

from .consequence import apply_active_incidents
from .decisions import assemble_suppression, suppression_counts
from .rotation import detect_rotation_state, read_rotation_status
from .rotation_inference import infer_secret_name, load_catalog_secret_names
from .scanners import (
    scan_profile_catalog,
    scanner_catalog,
    security_pack_catalog,
    tool_catalog,
)
from .storage import (
    _attach_case_decision,
    _attach_dependency_risk_movement,
    _case_counts,
    _counts_by,
    _decode_cases,
    _dependency_delta,
    _dependency_risk_counts,
    _dependency_risk_movements,
    _honey_event_case,
    _latest_honey_events_by_project,
    _scan_delta,
)


def assemble_dashboard_payload(db: Any) -> dict[str, Any]:
    """Build the dashboard ``/api/summary`` payload from an ``ObservatoryDB``."""
    retention_days = db.honey_event_retention_days()
    db.prune_honey_key_events(retention_days=retention_days)
    case_decisions = db.case_decisions_map()
    managed_tool_records = db.list_managed_tools()
    # Tripwire bridge (Honeygraph 2): open incidents bound to an asset node, grouped
    # by repo. Each flips the case sitting AT its guarded node to active_incident and
    # lights the blast-radius path — applied per repo as the cases are assembled.
    node_incidents_by_repo: dict[str, list[dict[str, Any]]] = {}
    for incident in db.active_node_incidents():
        node_incidents_by_repo.setdefault(str(incident.get("project_id")), []).append(incident)

    latest = db.latest_scans()
    latest_scan_ids = [str(row["id"]) for row in latest]

    # One round-trip per data kind, keyed on the scan-id set (S-027). Previous
    # scans feed the SBOM/manifest delta, so their ids join the component pulls.
    previous_by_scan = db.previous_scans_for_latest(latest)
    previous_scan_ids = [str(prev["id"]) for prev in previous_by_scan.values() if prev]
    component_scan_ids = list(dict.fromkeys([*latest_scan_ids, *previous_scan_ids]))
    sbom_by_scan = db.sbom_components_for_scans(component_scan_ids)
    manifest_by_scan = db.dependency_manifest_entries_for_scans(component_scan_ids)
    findings_by_scan = db.findings_for_scans(latest_scan_ids)
    trust_by_scan = db.dependency_trust_for_scans(latest_scan_ids)
    posture_by_scan = db.platform_posture_for_scans(latest_scan_ids)
    global_resolution_runs, resolution_runs_by_repo = db.case_resolution_runs_for_dashboard(
        [row["repo_name"] for row in latest]
    )

    repos: list[dict[str, Any]] = []
    repo_indexes: dict[str, int] = {}
    case_change_by_scan: dict[str, dict[str, str]] = {}
    dependency_movement_by_scan: dict[str, dict[str, dict[str, Any]]] = {}
    resolved_cases_by_scan: dict[str, list[dict[str, Any]]] = {}
    scan_payloads: dict[str, dict[str, Any]] = {}
    for row in latest:
        scan_id = str(row["id"])
        previous = previous_by_scan.get(scan_id)
        current_findings = findings_by_scan.get(scan_id, [])
        delta = _scan_delta(row, previous)

        current_components = sbom_by_scan.get(scan_id, [])
        previous_components = sbom_by_scan.get(str(previous["id"]), []) if previous else []
        current_manifest_entries = manifest_by_scan.get(scan_id, [])
        previous_manifest_entries = manifest_by_scan.get(str(previous["id"]), []) if previous else []
        current_dependency_findings = [
            finding for finding in current_findings if finding.get("category") == "dependencies"
        ]
        dependency_delta = _dependency_delta(
            row,
            previous,
            current_components,
            previous_components,
            current_dependency_findings,
            current_manifest_entries,
            previous_manifest_entries,
        )

        case_change_by_scan[scan_id] = delta["case_changes"]
        dependency_movement_by_scan[scan_id] = _dependency_risk_movements(
            row, previous, delta, dependency_delta
        )
        dependency_delta["risk_counts"] = _dependency_risk_counts(dependency_movement_by_scan[scan_id])
        resolved_cases_by_scan[scan_id] = delta["resolved_cases"]

        current_cases = []
        for item in _decode_cases(row["cases_json"]):
            if not isinstance(item, dict):
                continue
            case = {"scan_id": row["id"], "repo": row["repo_name"], "repo_name": row["repo_name"], **item}
            case_id = str(case.get("case_id") or case.get("id") or "")
            case["change_status"] = case_change_by_scan.get(scan_id, {}).get(case_id, "new")
            _attach_dependency_risk_movement(case, dependency_movement_by_scan.get(scan_id, {}).get(case_id))
            _attach_case_decision(case, case_decisions)
            current_cases.append(case)

        apply_active_incidents(current_cases, node_incidents_by_repo.get(row["repo_name"], []))
        assembled = assemble_suppression(current_cases, current_findings, case_decisions)
        scan_payloads[scan_id] = assembled
        active_cases = assembled["active_cases"]
        active_findings = assembled["active_findings"]
        repo_indexes[row["repo_name"]] = len(repos)
        repos.append(
            {
                "scan_id": row["id"],
                "repo": row["repo_name"],
                "path": row["repo_path"],
                "health": row["health_score"],
                "last_scan": row["finished_at"],
                "status": row["status"],
                "profile": row["profile"],
                "report_path": row["report_path"],
                "counts": _counts_by(active_findings, "severity"),
                "categories": _counts_by(active_findings, "category"),
                "raw_counts": _counts_by(assembled["findings"], "severity"),
                "raw_categories": _counts_by(assembled["findings"], "category"),
                "scanners": json.loads(row["scanner_status_json"]),
                "cases": active_cases,
                "active_cases": active_cases,
                "suppressed_cases": assembled["suppressed_cases"],
                "case_counts": _case_counts(active_cases),
                "suppressed_counts": assembled["suppressed_counts"],
                "suppression_reasons": assembled["suppressed_counts"]["reasons"],
                "previous_scan_id": delta["previous_scan_id"],
                "previous_health": delta["previous_health"],
                "health_delta": delta["health_delta"],
                "case_delta": {
                    "new": sum(1 for case in active_cases if case.get("change_status") == "new"),
                    "recurring": sum(1 for case in active_cases if case.get("change_status") == "recurring"),
                    "resolved": delta["resolved_count"],
                },
                "dependency_delta": dependency_delta,
                "dependency_trust": trust_by_scan.get(scan_id, []),
                "platform_posture": posture_by_scan.get(scan_id),
                "case_resolution_runs": resolution_runs_by_repo.get(row["repo_name"], []),
            }
        )

    findings: list[dict[str, Any]] = []
    active_findings = []
    suppressed_findings = []
    cases: list[dict[str, Any]] = []
    active_cases = []
    suppressed_cases = []
    honey_keys = db.list_honey_keys()
    honey_events = db.list_honey_key_events(limit=100)
    project_statuses = db.project_statuses()
    active_honey_events = [event for event in honey_events if not (event.get("incident") or {}).get("closed_at")]
    latest_events_by_project = _latest_honey_events_by_project(active_honey_events)
    keys_by_project: dict[str, list[dict[str, Any]]] = {}
    for key in honey_keys:
        keys_by_project.setdefault(str(key["project_id"]), []).append(key)
    for project_id, status in project_statuses.items():
        if status.get("status") == "red":
            event = latest_events_by_project.get(project_id)
            if not event:
                continue
            if project_id in repo_indexes:
                repo = repos[repo_indexes[project_id]]
                repo["health"] = 0
                repo["status"] = "critical"
                repo["counts"]["critical"] = int(repo["counts"].get("critical", 0)) + 1
                repo["categories"]["honeytokens"] = int(repo["categories"].get("honeytokens", 0)) + 1
            else:
                first_key = (keys_by_project.get(project_id) or [{}])[0]
                repos.append(
                    {
                        "scan_id": None,
                        "repo": project_id,
                        "path": first_key.get("repo_id") or project_id,
                        "health": 0,
                        "last_scan": status.get("last_event_at"),
                        "status": "critical",
                        "profile": "honey-keys",
                        "report_path": None,
                        "counts": {"critical": 1},
                        "categories": {"honeytokens": 1},
                        "scanners": [],
                        "cases": [],
                        "active_cases": [],
                        "suppressed_cases": [],
                        "case_counts": {"action_level": {"fix_now": 1}, "severity": {"critical": 1}, "category": {"honeytokens": 1}},
                        "suppressed_counts": {"cases": 0, "findings": 0, "reasons": []},
                        "suppression_reasons": [],
                    }
                )
                repo_indexes[project_id] = len(repos) - 1
            case = _honey_event_case(event)
            _attach_case_decision(case, case_decisions)
            cases.append(case)
            active_cases.append(case)

    history = db.recent_scan_history(limit=200)
    if latest_scan_ids:
        for row in latest:
            scan_id = str(row["id"])
            assembled = scan_payloads.get(scan_id, {})
            findings.extend(assembled.get("findings", []))
            active_findings.extend(assembled.get("active_findings", []))
            suppressed_findings.extend(assembled.get("suppressed_findings", []))
            cases.extend(assembled.get("cases", []))
            active_cases.extend(assembled.get("active_cases", []))
            suppressed_cases.extend(assembled.get("suppressed_cases", []))
            for resolved_case in resolved_cases_by_scan.get(scan_id, []):
                resolved_case_id = str(resolved_case.get("case_id") or resolved_case.get("id") or "")
                _attach_dependency_risk_movement(
                    resolved_case, dependency_movement_by_scan.get(scan_id, {}).get(resolved_case_id)
                )
                _attach_case_decision(resolved_case, case_decisions)
                cases.append(resolved_case)
        findings = findings[:500]
        active_findings = active_findings[:500]
        suppressed_findings = suppressed_findings[:500]
    aggregate_suppressed_counts = suppression_counts(suppressed_cases, suppressed_findings)
    return {
        "repos": repos,
        "history": history,
        "findings": findings,
        "active_findings": active_findings,
        "suppressed_findings": suppressed_findings,
        "cases": cases,
        "active_cases": active_cases,
        "suppressed_cases": suppressed_cases,
        "suppressed_counts": aggregate_suppressed_counts,
        "suppression_reasons": aggregate_suppressed_counts["reasons"],
        "case_decisions": list(case_decisions.values()),
        "honey_keys": honey_keys,
        "honey_key_events": honey_events,
        "project_statuses": list(project_statuses.values()),
        "honey_event_retention_days": retention_days,
        "scanner_catalog": scanner_catalog(),
        "tool_catalog": tool_catalog(detect_install_state=True, managed_tool_records=managed_tool_records),
        "security_packs": security_pack_catalog(detect_install_state=True, managed_tool_records=managed_tool_records),
        "scan_profiles": scan_profile_catalog(detect_install_state=True, managed_tool_records=managed_tool_records),
        "managed_tools": managed_tool_records,
        "agent_lab_proposals": db.list_agent_lab_proposals(limit=50),
        "case_resolution_runs": global_resolution_runs,
    }


def enrich_repos_with_rotation(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach per-repo rotation state and inferred secret names, in place.

    Lives here rather than in ``rotation_inference`` because it is payload
    assembly, not inference: it reads each repo's on-disk rotation state
    (``rotation``) and folds it into the dashboard payload alongside the rest of
    the per-repo UI shape. ``rotation_inference`` stays a pure, I/O-free guesser
    that this loop calls. Read fresh on each request because rotation state
    lives outside the DB (in each repo's ``data/`` directory).
    """
    catalog_names_cache: list[str] | None = None
    for repo in payload.get("repos") or []:
        repo_path_raw = repo.get("path")
        if not repo_path_raw:
            continue
        try:
            repo["rotation_state"] = detect_rotation_state(repo_path_raw)
        except OSError:
            repo["rotation_state"] = {
                "scaffolded": False,
                "stack": None,
                "stack_supported": False,
                "secret_count": 0,
                "needs_attention_count": 0,
                "in_grace_count": 0,
                "last_event_at": None,
            }
        # Enrich secrets-category cases with `inferred_secret_name` so
        # the case card can pre-fill the rotation modal. We only infer
        # when rotation is scaffolded — otherwise the affordance won't
        # render anyway. Candidate names come from the repo's tracked
        # secrets first; fall back to the global catalog so cases for
        # never-yet-rotated secrets still get a sensible guess.
        if not repo["rotation_state"].get("scaffolded"):
            continue
        try:
            rotation_rows = read_rotation_status(repo_path_raw)
        except OSError:
            rotation_rows = []
        candidate_names = [
            str(row.get("secret")) for row in rotation_rows if row.get("secret")
        ]
        if not candidate_names:
            if catalog_names_cache is None:
                catalog_names_cache = load_catalog_secret_names()
            candidate_names = list(catalog_names_cache)
        if not candidate_names:
            continue
        for case in repo.get("active_cases") or repo.get("cases") or []:
            if not isinstance(case, dict):
                continue
            if str(case.get("category") or "") != "secrets":
                continue
            inferred = infer_secret_name(case, candidate_names)
            if inferred:
                case["inferred_secret_name"] = inferred
    return payload
