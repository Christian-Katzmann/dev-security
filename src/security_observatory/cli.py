from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json
import os
import shutil
import sys

from . import __version__
from .case_followup import apply_case_resolutions, build_case_followup_prompt, validate_case_resolutions
from .credentials import (
    CredentialStorageError,
    KEYCHAIN_SERVICE,
    is_supported as keychain_is_supported,
    list_all_credentials,
)
from .dashboard_server import build_ai_prompt, serve_dashboard
from .discovery import discover_repos
from .iocs import ioc_match_payload, match_ioc_packs
from .model import FAIL_LEVELS, SEVERITY_ORDER, slugify
from .recency import DEFAULT_RECENCY_WINDOW_DAYS, enrich_ioc_findings_with_rotation_advice
from .reset import (
    backup_repo_state,
    execute_reset,
    list_known_repos,
    plan_reset,
    reset_confirmation_phrase,
)
from .managed_tools import managed_tool_evidence, resolve_managed_scanner_binary
from .scan_orchestrator import build_parser, import_ioc_feeds, package_root, profile_name, scan_repo
from .scanners import scanner_catalog
from .verification import proof_level_label
from .storage import ObservatoryDB


def observatory_home() -> Path:
    return Path(os.environ.get("SECURITY_OBSERVATORY_HOME", "~/.security-observatory")).expanduser()


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
    if args.target == "cases":
        return cases_command(args, home)
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


def cases_command(args: argparse.Namespace, home: Path) -> int:
    subcommand = (args.ioc_target or "").strip()
    if subcommand == "prompt":
        return cases_prompt(args, home)
    if subcommand == "import-resolutions":
        return cases_import_resolutions(args, home)
    print(
        "Usage:\n"
        "  security-scan cases prompt --repo <repo> --action verify_findings --scope critical\n"
        "  security-scan cases import-resolutions --repo <repo> --input resolutions.json --preview\n"
        "  security-scan cases import-resolutions --repo <repo> --input resolutions.json --apply",
        file=sys.stderr,
    )
    return 2


def cases_prompt(args: argparse.Namespace, home: Path) -> int:
    if not args.repo:
        print("Use --repo to choose a repository with scan history.", file=sys.stderr)
        return 2
    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        try:
            prompt = build_case_followup_prompt(
                db,
                repo_name=args.repo,
                action=args.action or "verify_findings",
                scope=args.scope or "critical",
                case_ids=list(args.case_ids or []),
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    finally:
        db.close()

    if args.json:
        print(json.dumps(prompt, indent=2, sort_keys=True))
        return 0
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(str(prompt["prompt"]) + "\n", encoding="utf-8")
        print(f"Wrote AI follow-up prompt for {prompt['case_count']} case{'s' if prompt['case_count'] != 1 else ''} to {output_path}.")
        return 0
    print(str(prompt["prompt"]), end="")
    return 0


def cases_import_resolutions(args: argparse.Namespace, home: Path) -> int:
    if not args.repo:
        print("Use --repo to choose a repository with scan history.", file=sys.stderr)
        return 2
    if not args.input:
        print("Use --input to choose the AI resolution JSON file.", file=sys.stderr)
        return 2
    if args.preview and args.apply:
        print("Use either --preview or --apply, not both.", file=sys.stderr)
        return 2
    input_path = Path(args.input).expanduser()
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Resolution input not found: {input_path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"Resolution input is not valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("Resolution input must be a JSON object.", file=sys.stderr)
        return 2

    db = ObservatoryDB(home / "db" / "observatory.sqlite")
    try:
        try:
            if args.apply:
                result = apply_case_resolutions(
                    db,
                    payload,
                    expected_repo=args.repo,
                    expected_scope=args.scope,
                    expected_case_ids=list(args.case_ids or []),
                    source="cli",
                    # The CLI apply path is scriptable/unattended, so it is treated
                    # like the automated path: high/critical suppressions are held
                    # for confirmation unless the operator explicitly opts in.
                    human_authorized=bool(getattr(args, "confirm_suppression", False)),
                )
            else:
                result = validate_case_resolutions(
                    db,
                    payload,
                    expected_repo=args.repo,
                    expected_scope=args.scope,
                    expected_case_ids=list(args.case_ids or []),
                    source="cli",
                    persist=True,
                )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    finally:
        db.close()

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.apply:
        needs_confirmation = int(result.get("requires_confirmation", 0))
        print(
            f"Applied {result['applied']} case resolution{'s' if result['applied'] != 1 else ''}; "
            f"left open {result['left_open']}; rejected {result['rejected']}; "
            f"awaiting human confirmation {needs_confirmation}."
        )
        if needs_confirmation:
            print(
                "High/critical suppressions are held for a human. Confirm them in the "
                "dashboard, or re-run with --confirm-suppression to authorize this batch."
            )
        warnings = result.get("warnings") or []
    else:
        summary = result.get("summary", {})
        print(
            f"Previewed {summary.get('total', 0)} case resolution{'s' if summary.get('total', 0) != 1 else ''}; "
            f"will apply {summary.get('will_apply', 0)}, leave open {summary.get('will_leave_open', 0)}, "
            f"reject {summary.get('rejected', 0)}, await confirmation {summary.get('requires_confirmation', 0)}."
        )
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
    _print_managed_tools_doctor_section(home)
    return 0


def _print_managed_tools_doctor_section(home: Path) -> None:
    """Report DëvSec-managed copies and their proof of origin.

    Proof level describes where the binary came from, not that it is safe — see
    docs/binary-trust.md. User-owned PATH tools are listed above by location and
    are intentionally not governed by this proof policy.
    """
    try:
        db = ObservatoryDB(home / "db" / "observatory.sqlite")
        try:
            records = db.list_managed_tools()
        finally:
            db.close()
    except Exception:
        return
    if not records:
        return
    print("DëvSec-managed tools (proof of origin, not safety):")
    for record in records:
        evidence = managed_tool_evidence(record, home=home)
        tool_id = str(record.get("tool_id") or "")
        version = str(record.get("version") or "")
        label = proof_level_label(evidence.proof_level or "checksum-pinned")
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        baseline = "integrity baseline recorded" if metadata.get("binary_sha256") else "no integrity baseline (reinstall to capture)"
        # Re-hash the binary the same way a scan would, so doctor never reports
        # "verified" for a copy that execution would refuse as tampered.
        resolution = resolve_managed_scanner_binary(tool_id, home=home)
        if resolution.state == "tampered":
            trust = "TAMPERED — on-disk binary does not match the install baseline; refused at scan time"
        elif evidence.verified:
            trust = "verified"
        else:
            trust = "UNVERIFIED: " + "; ".join(evidence.problems)
        print(f"  {tool_id} {version}: {label} · {trust} · {baseline}")


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
