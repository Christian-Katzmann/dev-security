"""Application-layer scan pipeline.

Home of ``scan_repo`` — the single, append-only scan path that the CLI, the
MCP server, and the dashboard all drive. It used to live in ``cli.py``, which
forced two non-CLI subsystems (``mcp_server`` and ``dashboard_server``) to
import the command-line entry point just to run a scan, creating a
``cli ↔ dashboard_server`` import cycle and an ``mcp → cli`` reach.

This module owns the scan pipeline and the parser/profile resolution it needs
to stand alone. It imports only domain/pipeline layers (``model``,
``scanners``, ``storage``, …) and **none** of the entry-point modules
(``cli``, ``mcp_server``, ``dashboard_server``), so it can be the shared
service all three import without re-introducing a cycle.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import argparse

from . import __version__
from .behavioral import select_behavioral_drift_targets
from .cases import build_security_cases, scanner_evidence_gaps
from .enrichment import correlate_dependency_findings, enrich_dependency_trust
from .iocs import default_pack_sources, ioc_match_payload, load_ioc_packs, match_ioc_packs
from .model import Finding, score_findings, severity_counts, slugify, utc_now_slug, write_json
from .model import read_json_safely
from .platform_posture import build_platform_posture_snapshot, platform_posture_regression_findings
from .recency import DEFAULT_RECENCY_WINDOW_DAYS, enrich_ioc_findings_with_rotation_advice
from .rotation import detect_rotation_state
from .scanners import run_behavioral_drift_scanner, run_scanner, scanner_names_for_profile
from .sbom import load_sbom_components
from .silent_upgrades import detect_silent_upgrades, parse_dependency_manifests
from .storage import ObservatoryDB


def package_root() -> Path:
    return Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="security-scan",
        description="Local-first security observability for repositories.",
    )
    parser.add_argument("target", nargs="?", help="Repository path to scan, or a command such as dashboard.")
    parser.add_argument("ioc_target", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("--all-repos", action="store_true", help="Discover and scan git repositories under ~/Dev.")
    parser.add_argument("--dev-root", default="~/Dev", help="Root used by --all-repos. Default: ~/Dev.")
    parser.add_argument("--quick", action="store_true", help="Run low-cost scanners: AI static checks, Semgrep, Gitleaks, OSV.")
    parser.add_argument("--code", action="store_true", help="Run code vulnerability checks.")
    parser.add_argument("--ai", action="store_true", help="Run AI-agent/MCP/editor/repo-poisoning checks.")
    parser.add_argument("--deps", action="store_true", help="Run dependency/SBOM scanners.")
    parser.add_argument("--trust", action="store_true", help="Opt into network-backed dependency trust enrichment after SBOM generation.")
    parser.add_argument("--trust-cache-only", action="store_true", help="Attach dependency trust data from the local cache without network access.")
    parser.add_argument("--behavioral-drift", action="store_true", help="Opt into bounded malcontent checks for changed dependency versions with local artifacts.")
    parser.add_argument("--platform-posture", action="store_true", help="Opt into connected legitify checks for SCM branch protection and workflow posture.")
    parser.add_argument("--secrets", action="store_true", help="Run secret scanners.")
    parser.add_argument("--iac", action="store_true", help="Run IaC/cloud config scanners.")
    parser.add_argument("--full", action="store_true", help="Run every configured scanner.")
    parser.add_argument("--fail-on", choices=["low", "medium", "high", "critical"], help="Exit non-zero if this severity or worse is found.")
    parser.add_argument("--feed", help="IOC pack file or directory used by security-scan ioc and default IOC matching.")
    parser.add_argument("--recency-window-days", type=int, default=DEFAULT_RECENCY_WINDOW_DAYS, help="Days used for IOC install-recency checks. Default: 14.")
    parser.add_argument("--json", action="store_true", help="Print the normalized scan summary as JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Print generated output without writing it, for commands that support it.")
    parser.add_argument("--limit", type=int, help="Limit repos scanned with --all-repos.")
    parser.add_argument("--port", type=int, default=8765, help="Dashboard port.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser for dashboard.")
    parser.add_argument("--repo", help="Repository name for local VEX import/export decisions.")
    parser.add_argument("--input", "-i", help="Input JSON path for vex-import.")
    parser.add_argument("--output", "-o", help="Output JSON path for vex-export.")
    parser.add_argument("--action", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--scope", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--case-id", dest="case_ids", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument("--preview", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--confirm-suppression", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # Reset-only flags. Hidden from --help so they don't clutter the scan
    # surface; reset_command surfaces them via its own usage line.
    parser.add_argument("--include-rotation-scaffold", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--backup-to", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)
    return parser


def profile_name(args: argparse.Namespace) -> str:
    enabled = [
        name
        for name in ("quick", "code", "ai", "deps", "trust", "trust_cache_only", "behavioral_drift", "platform_posture", "secrets", "iac", "full")
        if getattr(args, name, False)
    ]
    enabled = [
        "trust-cache-only"
        if name == "trust_cache_only"
        else "behavioral-drift"
        if name == "behavioral_drift"
        else "platform-posture"
        if name == "platform_posture"
        else name
        for name in enabled
    ]
    return "+".join(enabled) if enabled else "default"


def import_ioc_feeds(db: ObservatoryDB, args: argparse.Namespace) -> tuple[Any, list[dict[str, Any]]]:
    sources = [Path(args.feed).expanduser()] if getattr(args, "feed", None) else default_pack_sources()
    load_result = load_ioc_packs(sources)
    pack_dicts = [pack.to_dict() for pack in load_result.packs]
    db.import_ioc_packs(pack_dicts)
    pack_ids = [pack["id"] for pack in pack_dicts]
    return load_result, db.list_ioc_packs(pack_ids=pack_ids)


def _ioc_status(findings: list[Finding], load_result: Any, raw_report: Path) -> dict[str, Any]:
    issues = [issue.to_dict() for issue in load_result.issues]
    error = "; ".join(
        f"{issue['path']}{':' + str(issue['line']) if issue.get('line') else ''}: {issue['message']}"
        for issue in issues
    )
    now = datetime.now(timezone.utc).isoformat()
    return {
        "scanner": "ioc-watch",
        "available": True,
        "command": ["built-in", "ioc-watch"],
        "started_at": now,
        "finished_at": now,
        "status": "checked",
        "exit_code": 0,
        "findings": len(findings),
        "raw_report": str(raw_report),
        "error": error or None,
    }


def scan_repo(
    repo: Path,
    args: argparse.Namespace,
    home: Path,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    scanner_names: list[str] | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    repo_name = slugify(repo.name)
    scan_id = f"{repo_name}-{utc_now_slug()}"
    scan_dir = home / "reports" / repo_name / scan_id
    scan_dir.mkdir(parents=True, exist_ok=True)
    scanners = list(dict.fromkeys(scanner_names or scanner_names_for_profile(args)))
    rules_dir = package_root() / "rules"

    all_findings: list[Finding] = []
    statuses = []
    sbom_created = False
    for index, scanner in enumerate(scanners, start=1):
        if progress_callback:
            progress_callback({"event": "scanner_started", "scanner": scanner, "index": index, "total": len(scanners)})
        result = run_scanner(scanner, repo, repo_name, scan_dir, rules_dir)
        statuses.append(result.status.to_dict())
        all_findings.extend(result.findings)
        sbom_created = sbom_created or result.sbom_created
        if progress_callback:
            progress_callback(
                {
                    "event": "scanner_finished",
                    "scanner": scanner,
                    "index": index,
                    "total": len(scanners),
                    "findings": len(result.findings),
                    "available": result.status.available,
                    "error": result.status.error,
                }
            )

    sbom_components = load_sbom_components(scan_dir)
    sbom_created = sbom_created or bool(sbom_components)
    dependency_manifest_entries = parse_dependency_manifests(repo)
    dependency_trust = []
    if getattr(args, "trust", False) or getattr(args, "trust_cache_only", False):
        if progress_callback:
            progress_callback({"event": "trust_enrichment_started", "components": len(sbom_components)})
        dependency_trust = enrich_dependency_trust(
            sbom_components,
            cache_dir=home / "cache" / "dependency-trust",
            allow_network=bool(getattr(args, "trust", False) and not getattr(args, "trust_cache_only", False)),
        )
        if progress_callback:
            progress_callback({"event": "trust_enrichment_finished", "records": len(dependency_trust)})

    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    behavioral_drift = None
    platform_posture = None
    try:
        previous_scan = db.previous_scan_for_repo(repo_name, started_at)
        previous_components = (
            db.list_sbom_components(scan_id=str(previous_scan["id"]), repo_name=repo_name)
            if previous_scan
            else []
        )
        previous_manifest_entries = (
            db.list_dependency_manifest_entries(scan_id=str(previous_scan["id"]), repo_name=repo_name)
            if previous_scan
            else []
        )
        all_findings.extend(
            detect_silent_upgrades(
                repo_name=repo_name,
                scan_id=scan_id,
                current_components=sbom_components,
                previous_components=previous_components,
                current_manifest_entries=dependency_manifest_entries,
                previous_manifest_entries=previous_manifest_entries,
            )
        )
        ioc_result, ioc_packs = import_ioc_feeds(db, args)
        if "legitify" in scanners:
            legitify_status = next((item for item in statuses if item.get("scanner") == "legitify"), None)
            platform_posture = build_platform_posture_snapshot(
                read_json_safely(scan_dir / "legitify.json"),
                repo_name=repo_name,
                scanner_status=legitify_status,
            )
            previous_platform_posture = db.latest_platform_posture_snapshot(repo_name, before_started_at=started_at)
            all_findings.extend(platform_posture_regression_findings(repo_name, platform_posture, previous_platform_posture))

        if getattr(args, "behavioral_drift", False):
            targets = select_behavioral_drift_targets(
                sbom_components,
                previous_components,
                repo_name=repo_name,
                scan_id=scan_id,
                previous_scan_id=str(previous_scan["id"]) if previous_scan else None,
                artifact_cache_dir=home / "cache" / "behavioral-artifacts",
            )
            if progress_callback:
                progress_callback({"event": "behavioral_drift_started", "targets": len(targets)})
            result = run_behavioral_drift_scanner(repo_name, scan_dir, targets)
            statuses.append(result.status.to_dict())
            all_findings.extend(result.findings)
            behavioral_drift = read_json_safely(scan_dir / "malcontent.json")
            if progress_callback:
                progress_callback({"event": "behavioral_drift_finished", "findings": len(result.findings)})

        ioc_findings = match_ioc_packs(packs=ioc_packs, components=sbom_components, repo=repo, repo_name=repo_name)
        ioc_findings = enrich_ioc_findings_with_rotation_advice(
            ioc_findings,
            repo,
            window_days=getattr(args, "recency_window_days", DEFAULT_RECENCY_WINDOW_DAYS),
        )
        all_findings.extend(ioc_findings)
        ioc_report_path = scan_dir / "ioc-watch.json"
        write_json(
            ioc_report_path,
            {
                "packs": [pack.get("id") for pack in ioc_packs],
                "issues": [issue.to_dict() for issue in ioc_result.issues],
                "matches": [ioc_match_payload(finding) for finding in ioc_findings],
            },
        )
        statuses.append(_ioc_status(ioc_findings, ioc_result, ioc_report_path))

        unique_findings = list({finding.fingerprint: finding for finding in all_findings}.values())
        unique_findings = correlate_dependency_findings(unique_findings, sbom_components)
        health = score_findings(unique_findings, sbom_created=sbom_created or "syft" not in scanners)
        finished_at = datetime.now(timezone.utc).isoformat()
        status = "ok" if not any(item.get("error") or not item.get("available") for item in statuses) else "partial"
        counts = severity_counts(unique_findings)
        category_counts: dict[str, int] = {}
        for finding in unique_findings:
            category_counts[finding.category] = category_counts.get(finding.category, 0) + 1
        cases = build_security_cases(
            unique_findings,
            statuses,
            {"repo": repo_name, "repo_path": str(repo), "scan_id": scan_id},
            dependency_trust,
        )
    except BaseException:
        db.close()
        raise

    report_path = scan_dir / "normalized-report.json"
    report = {
        "scan_id": scan_id,
        "repo": repo_name,
        "repo_path": str(repo),
        "report_path": str(report_path),
        "started_at": started_at,
        "finished_at": finished_at,
        "profile": profile_name(args),
        "health_score": health,
        "status": status,
        "severity_counts": counts,
        "category_counts": category_counts,
        "scanners": statuses,
        "evidence_gaps": scanner_evidence_gaps(statuses, profile=profile_name(args)),
        "cases": [case.to_dict() for case in cases],
        "findings": [finding.to_dict() for finding in unique_findings],
        "ioc_matches": [ioc_match_payload(finding) for finding in unique_findings if finding.category == "supply-chain-ioc"],
        "dependency_manifests": [entry.to_dict() for entry in dependency_manifest_entries],
        "dependency_trust": [record.to_dict() for record in dependency_trust],
    }
    if behavioral_drift is not None:
        report["behavioral_drift"] = behavioral_drift
    if platform_posture is not None:
        report["platform_posture"] = platform_posture
    # Rotation-state detection: cheap stat + at most two file reads. Lets the
    # dashboard render the RotationStatusCard from the scan output without a
    # second round-trip. The skill itself writes the underlying state files.
    report["rotation_state"] = detect_rotation_state(repo)
    write_json(report_path, report)

    try:
        db.save_scan(
            scan_id=scan_id,
            repo_name=repo_name,
            repo_path=str(repo),
            started_at=started_at,
            finished_at=finished_at,
            profile=profile_name(args),
            health_score=health,
            status=status,
            scanner_statuses=statuses,
            findings=unique_findings,
            report_path=str(report_path),
            cases=cases,
            sbom_components=sbom_components,
            dependency_manifest_entries=dependency_manifest_entries,
            dependency_trust_enrichments=dependency_trust,
            platform_posture_snapshot=platform_posture,
        )
    finally:
        db.close()
    return report
