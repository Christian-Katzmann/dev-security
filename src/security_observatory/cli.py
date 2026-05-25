from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import argparse
import json
import os
import shutil
import sys

from . import __version__
from .behavioral import select_behavioral_drift_targets
from .cases import build_security_cases, scanner_evidence_gaps
from .credentials import (
    CredentialStorageError,
    KEYCHAIN_SERVICE,
    is_supported as keychain_is_supported,
    list_all_credentials,
)
from .dashboard_server import build_ai_prompt, serve_dashboard
from .discovery import discover_repos
from .enrichment import correlate_dependency_findings, enrich_dependency_trust
from .iocs import default_pack_sources, ioc_match_payload, load_ioc_packs, match_ioc_packs
from .model import FAIL_LEVELS, SEVERITY_ORDER, Finding, score_findings, severity_counts, slugify, utc_now_slug, write_json
from .model import read_json_safely
from .platform_posture import build_platform_posture_snapshot, platform_posture_regression_findings
from .recency import DEFAULT_RECENCY_WINDOW_DAYS, enrich_ioc_findings_with_rotation_advice
from .reset import (
    backup_repo_state,
    execute_reset,
    list_known_repos,
    plan_reset,
    reset_confirmation_phrase,
)
from .rotation import detect_rotation_state
from .scanners import run_behavioral_drift_scanner, run_scanner, scanner_catalog, scanner_names_for_profile
from .sbom import load_sbom_components
from .silent_upgrades import detect_silent_upgrades, parse_dependency_manifests
from .storage import ObservatoryDB


def observatory_home() -> Path:
    return Path(os.environ.get("SECURITY_OBSERVATORY_HOME", "~/.security-observatory")).expanduser()


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
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.trust and args.trust_cache_only:
        print("Use either --trust or --trust-cache-only, not both.", file=sys.stderr)
        return 2
    home = observatory_home()
    ensure_layout(home)

    if args.target == "ioc":
        return ioc_command(args, home)
    if args.target in {"dashboard", "serve"}:
        return dashboard(args, home)
    if args.target in {"doctor", "check"}:
        return doctor(home)
    if args.target in {"handoff", "ai-prompt"}:
        return handoff_prompt(args, home)
    if args.target in {"template", "github-template"}:
        return print_template()
    if args.target in {"schedule", "cron"}:
        return print_schedule_help()
    if args.target == "vex-export":
        return vex_export(args, home)
    if args.target == "vex-import":
        return vex_import(args, home)
    if args.target == "credentials":
        return credentials_command(args)
    if args.target == "reset":
        return reset_command(args, home)

    repos = resolve_targets(args)
    if not repos:
        print("No repositories found to scan.")
        return 2

    summaries = [scan_repo(repo, args, home) for repo in repos]
    if args.json:
        print(json.dumps(summaries, indent=2, sort_keys=True))
    else:
        print_human_summary(summaries, home)
    return fail_code(summaries, args.fail_on)


def ensure_layout(home: Path) -> None:
    for name in ("reports", "db", "cache", "repos", "logs"):
        (home / name).mkdir(parents=True, exist_ok=True)


def resolve_targets(args: argparse.Namespace) -> list[Path]:
    if args.all_repos:
        return discover_repos(Path(args.dev_root), args.limit)
    if args.target == "ioc":
        target = Path(args.ioc_target or ".").expanduser()
        return [target.resolve()]
    target = Path(args.target or ".").expanduser()
    return [target.resolve()]


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


def print_human_summary(summaries: list[dict[str, Any]], home: Path) -> None:
    print("\nSecurity Observatory")
    print(f"Local store: {home}")
    print("")
    print(f"{'Repo':28} {'Health':>6} {'Crit':>5} {'High':>5} {'Med':>5} {'Secrets':>7} {'AI-risk':>7}")
    print("-" * 74)
    for summary in summaries:
        counts = summary["severity_counts"]
        cats = summary["category_counts"]
        print(
            f"{summary['repo'][:28]:28} {summary['health_score']:>6} "
            f"{counts.get('critical', 0):>5} {counts.get('high', 0):>5} {counts.get('medium', 0):>5} "
            f"{cats.get('secrets', 0):>7} {cats.get('ai-risk', 0):>7}"
        )
    print("")
    for summary in summaries:
        unavailable = [item["scanner"] for item in summary["scanners"] if not item["available"]]
        if unavailable:
            print(f"{summary['repo']}: skipped unavailable scanners: {', '.join(unavailable)}")
        print(f"{summary['repo']}: normalized report {summary['report_path']}")


def fail_code(summaries: list[dict[str, Any]], fail_on: str | None) -> int:
    if not fail_on:
        return 0
    threshold = FAIL_LEVELS[fail_on]
    for summary in summaries:
        for finding in summary["findings"]:
            if SEVERITY_ORDER.get(finding["severity"], 0) >= threshold:
                return 3
    return 0


def ioc_command(args: argparse.Namespace, home: Path) -> int:
    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        load_result, packs = import_ioc_feeds(db, args)
        repos = resolve_targets(args)
        if not repos:
            print("No repositories found to scan.")
            return 2
        summaries = [
            ioc_repo_summary(db, repo, packs, recency_window_days=getattr(args, "recency_window_days", DEFAULT_RECENCY_WINDOW_DAYS))
            for repo in repos
        ]
    finally:
        db.close()

    payload = {
        "packs": [pack.get("id") for pack in packs],
        "issues": [issue.to_dict() for issue in load_result.issues],
        "repos": summaries,
        "matches": [match for summary in summaries for match in summary["matches"]],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_ioc_summary(payload)
    return fail_code([{"findings": [match for summary in summaries for match in summary["findings"]]}], args.fail_on or "critical")


def import_ioc_feeds(db: ObservatoryDB, args: argparse.Namespace) -> tuple[Any, list[dict[str, Any]]]:
    sources = [Path(args.feed).expanduser()] if getattr(args, "feed", None) else default_pack_sources()
    load_result = load_ioc_packs(sources)
    pack_dicts = [pack.to_dict() for pack in load_result.packs]
    db.import_ioc_packs(pack_dicts)
    pack_ids = [pack["id"] for pack in pack_dicts]
    return load_result, db.list_ioc_packs(pack_ids=pack_ids)


def ioc_repo_summary(
    db: ObservatoryDB,
    repo: Path,
    packs: list[dict[str, Any]],
    *,
    recency_window_days: int = DEFAULT_RECENCY_WINDOW_DAYS,
) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    repo_name = slugify(repo.name)
    latest_scan = db.latest_scan_for_repo(repo_name)
    components = db.list_sbom_components(scan_id=str(latest_scan["id"]), repo_name=repo_name) if latest_scan else []
    findings = match_ioc_packs(packs=packs, components=components, repo=repo, repo_name=repo_name)
    findings = enrich_ioc_findings_with_rotation_advice(
        findings,
        repo,
        window_days=recency_window_days,
    )
    matches = []
    for finding in findings:
        item = ioc_match_payload(finding)
        item["repo_path"] = str(repo)
        item["scan_id"] = latest_scan["id"] if latest_scan else None
        matches.append(item)
    return {
        "repo": repo_name,
        "repo_path": str(repo),
        "scan_id": latest_scan["id"] if latest_scan else None,
        "component_count": len(components),
        "matches": matches,
        "findings": [finding.to_dict() for finding in findings],
    }


def print_ioc_summary(payload: dict[str, Any]) -> None:
    matches = payload.get("matches") or []
    issues = payload.get("issues") or []
    print("Security Observatory IOC Watch")
    print(f"Packs: {', '.join(payload.get('packs') or []) or 'none'}")
    print(f"Matches: {len(matches)}")
    for issue in issues:
        location = f"{issue.get('path')}:{issue.get('line')}" if issue.get("line") else issue.get("path")
        print(f"Pack issue: {location}: {issue.get('message')}")
    for match in matches:
        package = match.get("affected_package") or match.get("indicator") or "indicator"
        version = f" {match.get('affected_version')}" if match.get("affected_version") else ""
        print(f"- {match.get('repo_name')}: {package}{version} [{match.get('match_type')}] from {match.get('source_pack')}")


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


def dashboard(args: argparse.Namespace, home: Path) -> int:
    serve_dashboard(
        db_path=home / "db" / "observatory.sqlite",
        assets_dir=package_root() / "dashboard",
        port=args.port,
        open_browser=not args.no_open,
    )
    return 0


def handoff_prompt(args: argparse.Namespace, home: Path) -> int:
    scan_id = args.ioc_target or args.repo
    if not scan_id:
        print("Use security-scan handoff <scan-id> [--dry-run] [--output path].", file=sys.stderr)
        return 2
    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        scan = db.scan_export(scan_id)
    finally:
        db.close()
    if not scan:
        print(f"Scan not found: {scan_id}", file=sys.stderr)
        return 2
    prompt = build_ai_prompt(scan)
    if args.dry_run or not args.output:
        print(prompt)
        return 0
    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt + "\n", encoding="utf-8")
    print(f"Wrote AI handoff prompt to {output_path}.")
    return 0


def vex_export(args: argparse.Namespace, home: Path) -> int:
    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        document = db.export_vex_decisions(repo_name=args.repo, tool_version=__version__)
    finally:
        db.close()
    body = json.dumps(document, indent=2, sort_keys=True) + "\n"
    count = len(document.get("statements", [])) if isinstance(document.get("statements"), list) else 0
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(body, encoding="utf-8")
        print(f"Exported {count} VEX decision{'s' if count != 1 else ''} to {output_path}.")
    else:
        print(body, end="")
        print(f"Exported {count} VEX decision{'s' if count != 1 else ''}.", file=sys.stderr)
    return 0


def vex_import(args: argparse.Namespace, home: Path) -> int:
    if not args.input:
        print("Use --input to choose the VEX JSON file to import.", file=sys.stderr)
        return 2
    input_path = Path(args.input).expanduser()
    try:
        document = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"VEX input not found: {input_path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"VEX input is not valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(document, dict):
        print("VEX input must be a JSON object.", file=sys.stderr)
        return 2

    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        summary = db.import_vex_decisions(document, repo_name=args.repo)
    finally:
        db.close()

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    print(f"Imported {summary['imported']} VEX decision{'s' if summary['imported'] != 1 else ''}; skipped {summary['skipped']}.")
    warnings = summary.get("warnings") or []
    if warnings:
        print("Notes:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


OPTIONAL_DOCTOR_PROFILE_IDS = {"behavioral-drift", "platform-posture"}


def _doctor_missing_is_optional(item: dict[str, object]) -> bool:
    profile_ids = {str(profile) for profile in item.get("profile_ids", []) if str(profile).strip()}
    return bool(profile_ids) and profile_ids.issubset(OPTIONAL_DOCTOR_PROFILE_IDS)


def _print_missing_doctor_group(title: str, items: list[dict[str, object]], note: str | None = None) -> None:
    if not items:
        return
    print(title)
    if note:
        print(f"  {note}")
    for item in items:
        tool = str(item["scanner"])
        print(f"  {tool}: not installed")
        print(f"    fix: {item['install']}")


def doctor(home: Path) -> int:
    print("Security Observatory doctor")
    print(f"Store: {home}")
    print(f"Python: {sys.executable}")
    print(f"Homebrew: {shutil.which('brew') or 'not found'}")
    print(f"uv: {shutil.which('uv') or 'not found'}")
    missing_needed: list[dict[str, object]] = []
    missing_optional: list[dict[str, object]] = []
    for item in scanner_catalog():
        tool = str(item["scanner"])
        if item.get("built_in"):
            print(f"{tool}: built in")
            continue
        location = shutil.which(tool)
        if location:
            print(f"{tool}: {location}")
            continue
        if _doctor_missing_is_optional(item):
            missing_optional.append(item)
        else:
            missing_needed.append(item)
    _print_missing_doctor_group("Not installed (needed for common scans):", missing_needed)
    _print_missing_doctor_group(
        "Not installed (optional):",
        missing_optional,
        "These opt-in checks stay quiet unless you run their profile.",
    )
    return 0


def print_template() -> int:
    template = Path(__file__).resolve().parents[2] / "templates" / "security.yml"
    print(template.read_text(encoding="utf-8"))
    return 0


def credentials_command(args: argparse.Namespace) -> int:
    """Audit the credentials DëvSec has stored in the macOS Keychain.

    Keys-only view. Values never print here — to inspect a value, open
    Keychain Access.app and search for ``"DëvSec"``. To revoke a credential,
    delete it from Keychain Access or use the SetupCard's Forget button.
    """
    sub = (args.ioc_target or "list").strip().lower()
    if sub not in {"list", "ls"}:
        print(
            "Usage: security-scan credentials list\n"
            "       (values are never printed; open Keychain Access to inspect them)",
            file=sys.stderr,
        )
        return 2
    if not keychain_is_supported():
        print(
            "Credential storage requires macOS with the `security` CLI on PATH.",
            file=sys.stderr,
        )
        return 1
    try:
        index = list_all_credentials()
    except CredentialStorageError as exc:
        print(f"Failed to read credential index: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"service": KEYCHAIN_SERVICE, "tools": index}, indent=2, sort_keys=True))
        return 0

    print(f"Keychain service: {KEYCHAIN_SERVICE}")
    if not index:
        print("No credentials stored.")
        return 0
    for tool_id in sorted(index):
        keys = index[tool_id]
        print(f"  {tool_id}: {', '.join(keys) if keys else '(none)'}")
    return 0


def reset_command(args: argparse.Namespace, home: Path) -> int:
    repo = (args.ioc_target or "").strip()
    if not repo:
        print("Usage: security-scan reset <repo> [--include-rotation-scaffold] [--backup-to <path>] [--yes] [--dry-run]", file=sys.stderr)
        return 2

    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        known = list_known_repos(db)
        if repo not in known:
            print(f"Unknown repo: {repo}", file=sys.stderr)
            if known:
                print(f"Known repos: {', '.join(known)}", file=sys.stderr)
            return 2

        include_scaffold = "--include-rotation-scaffold" in (args._argv if hasattr(args, "_argv") else sys.argv)
        backup_to = _extract_flag_value("--backup-to", sys.argv)
        skip_confirm = args.dry_run or "--yes" in sys.argv

        # Resolve repo_path from latest scan record
        latest = db.latest_scan_for_repo(repo)
        repo_path = Path(latest["repo_path"]) if latest and latest.get("repo_path") else None

        plan = plan_reset(
            db, repo, home,
            include_rotation_scaffold=include_scaffold,
            repo_path=repo_path,
        )

        if args.dry_run:
            print(f"Dry run — reset plan for `{repo}`:")
            print()
            if plan["tables"]:
                print("  SQLite tables:")
                for entry in plan["tables"]:
                    print(f"    {entry['table']}: {entry['rows']} row{'s' if entry['rows'] != 1 else ''}")
            else:
                print("  SQLite tables: (nothing to delete)")
            print()
            if plan["files"]:
                print("  Filesystem paths:")
                for path in plan["files"]:
                    print(f"    {path}")
            else:
                print("  Filesystem paths: (nothing to delete)")
            return 0

        if not skip_confirm:
            expected = reset_confirmation_phrase(repo)
            print(f"This will permanently delete all observatory data for `{repo}`.")
            print(f"Type exactly: {expected}")
            try:
                answer = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.", file=sys.stderr)
                return 1
            if answer != expected:
                print("Confirmation phrase did not match. Aborted.", file=sys.stderr)
                return 1

        if backup_to:
            backup_dir = Path(backup_to).expanduser()
            backups = backup_repo_state(
                db, repo, home, backup_dir,
                include_rotation_scaffold=include_scaffold,
                repo_path=repo_path,
            )
            print(f"Backup written:")
            for kind, path in backups.items():
                print(f"  {kind}: {path}")
            print()

        result = execute_reset(
            db, repo, home,
            include_rotation_scaffold=include_scaffold,
            repo_path=repo_path,
        )

        print(f"Reset complete for `{repo}`.")
        if result["tables"]:
            print("  Deleted rows:")
            for table, count in result["tables"].items():
                print(f"    {table}: {count}")
        if result["files"]:
            print("  Removed paths:")
            for path in result["files"]:
                print(f"    {path}")
    finally:
        db.close()
    return 0


def _extract_flag_value(flag: str, argv: list[str]) -> str | None:
    try:
        idx = argv.index(flag)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    except ValueError:
        pass
    return None


def print_schedule_help() -> int:
    binary = shutil.which("security-scan") or "security-scan"
    print("Add a daily local scan with:")
    print(f"0 7 * * * {binary} --all-repos --quick >> ~/.security-observatory/logs/cron.log 2>&1")
    print("")
    print("For a lightweight watcher, use a launchd plist that runs the same command periodically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
