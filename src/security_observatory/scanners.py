from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, Callable
import json
import os
import re
import signal
import shutil
import subprocess
import time

from .ai_static import scan_ai_static
from .behavioral import MAX_BEHAVIORAL_ARTIFACT_BYTES, MAX_BEHAVIORAL_FILES, MAX_BEHAVIORAL_PACKAGES, BehavioralDriftTarget
from .catalog import current_scan_profiles, current_security_packs, current_tool_catalog, legacy_scanner_catalog_map, scanner_catalog_compat
from .credentials import env_with_credentials, is_supported as keychain_is_supported
from .managed_tools import resolve_managed_scanner_binary
from .model import DEFAULT_EXCLUDES, Finding, ScannerStatus, read_json_safely, sanitize_json, write_json
from .verification import PROOF_CHECKSUM_PINNED, PROOF_UNVERIFIED, PROOF_USER_OWNED
from .normalize import (
    _checkov,
    _generic_ai,
    _gitleaks,
    _grype,
    _install_hooks,
    _legitify,
    _malcontent,
    _osv,
    _semgrep,
    _trivy,
    _trufflehog,
    _workflow_audit,
)
from .platform_posture import sanitize_legitify_payload
from .surface_scanners import INSTALL_HOOK_SCANNER, WORKFLOW_SCANNER, scan_install_hooks, scan_workflow_surfaces


SCANNER_CATALOG: dict[str, dict[str, Any]] = legacy_scanner_catalog_map()


@dataclass(frozen=True)
class ScannerResult:
    status: ScannerStatus
    findings: list[Finding]
    sbom_created: bool = False


CommandBuilder = Callable[[Path, Path, Path], list[str]]
Normalizer = Callable[[Any, str], list[Finding]]
ScannerRun = Callable[[Path, str, Path, Path], ScannerResult]


@dataclass(frozen=True)
class ScannerAdapter:
    """One co-located description of a scanner.

    Adding or correcting a scanner is a single edit to ``SCANNER_REGISTRY``: the
    command line, timeout, the exit codes that mean "ran and found something",
    the normalizer, and (for built-in or otherwise bespoke scanners) the run
    strategy all live on this one object. Every dispatch site — ``run_scanner``,
    ``_command``, ``_timeout``, ``EXIT_CODES_WITH_FINDINGS``, and ``normalize``
    — reads from here, so a scanner can no longer be wired into one facet but
    silently missing from another.

    ``run`` is ``None`` for the generic external-binary path (subprocess +
    timeout + exit-code interpretation + normalize). Built-in scanners
    (``ai-static``, the install-hook and workflow scanners) and scanners with a
    bespoke lifecycle (``legitify``) carry their own ``run`` callable instead.
    """

    name: str
    timeout: int = 300
    exit_codes_with_findings: frozenset[int] = frozenset()
    command: CommandBuilder | None = None
    normalizer: Normalizer | None = None
    run: ScannerRun | None = None


def normalizer_for(scanner: str) -> Normalizer | None:
    """Return the normalizer for ``scanner`` from the one registry, or ``None``.

    ``normalize.normalize`` defers to this so the normalization dispatch shares
    the single scanner-adapter source of truth instead of its own table.
    """
    adapter = SCANNER_REGISTRY.get(scanner)
    return adapter.normalizer if adapter else None


def _normalize(scanner: str, data: Any, repo_name: str) -> list[Finding]:
    normalizer = normalizer_for(scanner)
    return normalizer(data, repo_name) if normalizer else []


def scanner_catalog() -> list[dict[str, Any]]:
    return scanner_catalog_compat()


def tool_catalog(
    *,
    detect_install_state: bool = False,
    managed_tool_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    return current_tool_catalog(
        detect_install_state=detect_install_state,
        managed_tool_records=managed_tool_records,
    )


def security_pack_catalog(
    *,
    detect_install_state: bool = False,
    managed_tool_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    return current_security_packs(
        detect_install_state=detect_install_state,
        managed_tool_records=managed_tool_records,
    )


def scan_profile_catalog(
    *,
    detect_install_state: bool = False,
    managed_tool_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    return current_scan_profiles(
        detect_install_state=detect_install_state,
        managed_tool_records=managed_tool_records,
    )


def scanner_names_for_profile(args: Any) -> list[str]:
    if args.full:
        return [
            "ai-static",
            "install-hooks",
            "workflow-audit",
            "semgrep",
            "gitleaks",
            "trufflehog",
            "trivy",
            "osv-scanner",
            "syft",
            "grype",
            "checkov",
            "medusa",
        ]
    selected: list[str] = []
    if args.ai:
        selected.extend(["ai-static", "medusa"])
    if getattr(args, "code", False):
        selected.extend(["semgrep"])
    if args.deps:
        selected.extend(["install-hooks", "trivy", "osv-scanner", "syft", "grype"])
    if args.secrets:
        selected.extend(["gitleaks", "trufflehog", "trivy"])
    if args.iac:
        selected.extend(["workflow-audit", "trivy", "checkov"])
    if getattr(args, "trust", False) or getattr(args, "trust_cache_only", False):
        selected.extend(["syft"])
    if getattr(args, "behavioral_drift", False):
        selected.extend(["syft"])
    if getattr(args, "platform_posture", False):
        selected.extend(["legitify"])
    if args.quick:
        selected.extend(["ai-static", "install-hooks", "workflow-audit", "semgrep", "gitleaks", "osv-scanner"])
    if not selected:
        selected.extend(["ai-static", "install-hooks", "workflow-audit", "semgrep", "gitleaks", "trivy", "osv-scanner", "syft", "grype", "checkov"])
    return list(dict.fromkeys(selected))


def run_scanner(scanner: str, repo: Path, repo_name: str, scan_dir: Path, rules_dir: Path) -> ScannerResult:
    adapter = SCANNER_REGISTRY.get(scanner)
    if adapter is None:
        raise ValueError(f"Unknown scanner: {scanner}")
    if adapter.run is not None:
        return adapter.run(repo, repo_name, scan_dir, rules_dir)
    return _run_external_scanner(adapter, repo, repo_name, scan_dir, rules_dir)


def _run_ai_static_scanner(repo: Path, repo_name: str, scan_dir: Path, rules_dir: Path) -> ScannerResult:
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    findings = scan_ai_static(repo, repo_name)
    raw = scan_dir / "ai-static.json"
    write_json(raw, [finding.to_dict() for finding in findings])
    status = ScannerStatus(
        scanner="ai-static",
        available=True,
        command=["built-in"],
        started_at=started,
        finished_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=round(time.monotonic() - t0, 3),
        findings=len(findings),
        raw_report=str(raw),
        exit_code=0,
    )
    return ScannerResult(status, findings)


def _run_install_hook_scanner(repo: Path, repo_name: str, scan_dir: Path, rules_dir: Path) -> ScannerResult:
    return _run_builtin_json_scanner(INSTALL_HOOK_SCANNER, repo, repo_name, scan_dir, scan_install_hooks)


def _run_workflow_scanner(repo: Path, repo_name: str, scan_dir: Path, rules_dir: Path) -> ScannerResult:
    return _run_builtin_json_scanner(WORKFLOW_SCANNER, repo, repo_name, scan_dir, scan_workflow_surfaces)


def _run_legitify_adapter(repo: Path, repo_name: str, scan_dir: Path, rules_dir: Path) -> ScannerResult:
    return _run_legitify_scanner(repo, repo_name, scan_dir)


def _run_external_scanner(adapter: ScannerAdapter, repo: Path, repo_name: str, scan_dir: Path, rules_dir: Path) -> ScannerResult:
    scanner = adapter.name
    assert adapter.command is not None  # external adapters always build a command
    command = adapter.command(repo, scan_dir, rules_dir)
    resolution = resolve_managed_scanner_binary(scanner)
    started = datetime.now(timezone.utc).isoformat()
    if resolution.state == "tampered":
        status = ScannerStatus(
            scanner=scanner,
            available=False,
            command=command,
            started_at=started,
            status="skipped",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=resolution.reason or f"Managed {scanner} binary failed its pre-execution integrity check.",
            proof_level=PROOF_UNVERIFIED,
        )
        return ScannerResult(status, [])
    if resolution.state == "ok" and resolution.binary_path is not None:
        command = [str(resolution.binary_path), *command[1:]]
    binary = command[0]
    managed = resolution.state == "ok"
    proof_level = (resolution.proof_level or PROOF_CHECKSUM_PINNED) if managed else PROOF_USER_OWNED
    status = ScannerStatus(
        scanner=scanner,
        available=managed or bool(shutil.which(binary)),
        command=command,
        started_at=started,
        proof_level=proof_level,
    )
    if not status.available:
        status.finished_at = datetime.now(timezone.utc).isoformat()
        status.error = f"{binary} is not installed or not on PATH."
        status.proof_level = None
        return ScannerResult(status, [])

    t0 = time.monotonic()
    env = os.environ.copy()
    env.update({"SEMGREP_SEND_METRICS": "off", "SEMGREP_ENABLE_VERSION_CHECK": "0"})
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(repo),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(timeout=adapter.timeout)
        status.exit_code = proc.returncode
        _write_outputs(scanner, scan_dir, stdout, stderr)
        if proc.returncode != 0 and proc.returncode not in adapter.exit_codes_with_findings:
            status.error = (stderr or stdout or f"{scanner} failed").strip()[:4000]
    except subprocess.TimeoutExpired as exc:
        _kill_process_group(proc)
        stdout, stderr = proc.communicate() if proc else ("", "")
        _write_outputs(scanner, scan_dir, stdout, stderr)
        status.exit_code = 124
        status.error = f"{scanner} timed out after {exc.timeout} seconds."
    except BaseException:
        _kill_process_group(proc)
        raise
    finally:
        status.finished_at = datetime.now(timezone.utc).isoformat()
        status.duration_seconds = round(time.monotonic() - t0, 3)

    raw_path = _raw_path(scanner, scan_dir)
    sarif_path = scan_dir / f"{scanner}.sarif"
    sbom_path = scan_dir / "sbom.cyclonedx.json"
    if raw_path.exists():
        status.raw_report = str(raw_path)
    if sarif_path.exists():
        status.sarif_report = str(sarif_path)
    if scanner == "syft" and sbom_path.exists():
        status.sbom_report = str(sbom_path)
        status.findings = 0
        return ScannerResult(status, [], sbom_created=True)

    findings = _normalize(scanner, read_json_safely(raw_path), repo_name)
    status.findings = len(findings)
    return ScannerResult(status, findings, sbom_created=sbom_path.exists())


def _run_builtin_json_scanner(
    scanner: str,
    repo: Path,
    repo_name: str,
    scan_dir: Path,
    scanner_fn: Callable[[Path, str], dict[str, Any]],
) -> ScannerResult:
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    raw = scan_dir / f"{scanner}.json"
    payload = scanner_fn(repo, repo_name)
    write_json(raw, payload)
    findings = _normalize(scanner, payload, repo_name)
    status = ScannerStatus(
        scanner=scanner,
        available=True,
        command=["built-in", scanner],
        started_at=started,
        finished_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=round(time.monotonic() - t0, 3),
        findings=len(findings),
        raw_report=str(raw),
        exit_code=0,
        status="checked",
    )
    return ScannerResult(status, findings)


def run_behavioral_drift_scanner(
    repo_name: str,
    scan_dir: Path,
    targets: list[BehavioralDriftTarget] | list[dict[str, Any]],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    binary: str | None = None,
) -> ScannerResult:
    started = datetime.now(timezone.utc).isoformat()
    target_dicts = [target.to_dict() if hasattr(target, "to_dict") else dict(target) for target in targets]
    queued_targets = [target for target in target_dicts if target.get("status") == "queued"]
    resolved_binary = binary or _malcontent_binary()
    command_preview = _malcontent_diff_command(resolved_binary or "malcontent", "OLD_ARTIFACT", "NEW_ARTIFACT")
    status = ScannerStatus(
        scanner="malcontent",
        available=bool(resolved_binary) or not queued_targets,
        command=command_preview,
        started_at=started,
        status="not_checked" if not queued_targets else "running",
    )
    raw_path = _raw_path("malcontent", scan_dir)
    checks: list[dict[str, Any]] = []
    t0 = time.monotonic()

    if queued_targets and not resolved_binary:
        for target in target_dicts:
            if target.get("status") == "queued":
                target["status"] = "not_checked"
                target["reason"] = "malcontent is not installed or not on PATH."
            checks.append(target)
        payload = _malcontent_payload(checks)
        write_json(raw_path, payload)
        status.raw_report = str(raw_path)
        status.status = "not_checked"
        status.finished_at = datetime.now(timezone.utc).isoformat()
        status.duration_seconds = round(time.monotonic() - t0, 3)
        return ScannerResult(status, _normalize("malcontent", payload, repo_name))

    for target in target_dicts:
        if target.get("status") != "queued":
            checks.append(target)
            continue
        command = _malcontent_diff_command(
            resolved_binary or "malcontent",
            str(target.get("old_artifact") or ""),
            str(target.get("new_artifact") or ""),
        )
        check = {**target, "command": command}
        try:
            proc = runner(
                command,
                cwd=str(scan_dir),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=_timeout("malcontent"),
            )
        except subprocess.TimeoutExpired as exc:
            check.update(
                {
                    "status": "not_checked",
                    "reason": f"malcontent timed out after {exc.timeout} seconds.",
                }
            )
            checks.append(check)
            continue

        check["exit_code"] = proc.returncode
        if proc.returncode != 0:
            check.update(
                {
                    "status": "not_checked",
                    "reason": "malcontent could not complete this artifact diff; the scan continued.",
                    "stderr": (proc.stderr or "")[:4000],
                }
            )
            checks.append(check)
            continue
        check["status"] = "checked"
        check["reason"] = "malcontent compared the old and new artifacts."
        check["malcontent"] = _json_from_text(proc.stdout)
        if proc.stderr.strip():
            check["stderr"] = proc.stderr.strip()[:4000]
        checks.append(check)

    payload = _malcontent_payload(checks)
    write_json(raw_path, payload)
    findings = _normalize("malcontent", payload, repo_name)
    status.raw_report = str(raw_path)
    status.findings = len(findings)
    status.status = "checked" if any(check.get("status") == "checked" for check in checks) else "not_checked"
    status.exit_code = 0
    status.finished_at = datetime.now(timezone.utc).isoformat()
    status.duration_seconds = round(time.monotonic() - t0, 3)
    return ScannerResult(status, findings)


def _command(scanner: str, repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    adapter = SCANNER_REGISTRY.get(scanner)
    if adapter is None or adapter.command is None:
        raise ValueError(f"Unknown scanner: {scanner}")
    return adapter.command(repo, scan_dir, rules_dir)


def _semgrep_command(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    excludes = [item for pair in [(f"--exclude={name}",) for name in DEFAULT_EXCLUDES] for item in pair]
    return [
        "semgrep",
        "scan",
        "--config",
        str(rules_dir / "semgrep"),
        "--json",
        "--metrics=off",
        "--disable-version-check",
        *excludes,
        str(repo),
    ]


def _gitleaks_command(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    return [
        "gitleaks",
        "detect",
        "--source",
        str(repo),
        "--report-format",
        "json",
        "--report-path",
        str(scan_dir / "gitleaks.json"),
        "--redact",
        "--no-banner",
        "--max-target-megabytes",
        "2",
        "--timeout",
        str(_timeout("gitleaks")),
    ]


def _trufflehog_command(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    return [
        "trufflehog",
        "filesystem",
        "--json",
        "--no-update",
        "--concurrency=2",
        "--force-skip-binaries",
        "--force-skip-archives",
        "--exclude-paths",
        str(_exclude_paths_file(scan_dir)),
        str(repo),
    ]


def _trivy_command(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    skip = [arg for name in DEFAULT_EXCLUDES for arg in ("--skip-dirs", str(repo / name))]
    return [
        "trivy",
        "fs",
        "--format",
        "json",
        "--quiet",
        "--skip-version-check",
        "--parallel",
        "2",
        "--scanners",
        "vuln,secret,misconfig",
        *skip,
        str(repo),
    ]


def _osv_command(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    return ["osv-scanner", "--recursive", "--format", "json", "--output", str(scan_dir / "osv-scanner.json"), str(repo)]


def _syft_command(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    return ["syft", f"dir:{repo}", "-o", f"cyclonedx-json={scan_dir / 'sbom.cyclonedx.json'}", "-o", f"syft-json={scan_dir / 'syft.json'}", "--quiet"]


def _grype_command(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    sbom = scan_dir / "sbom.cyclonedx.json"
    target = f"sbom:{sbom}" if sbom.exists() else f"dir:{repo}"
    return ["grype", target, "-o", "json", "--file", str(scan_dir / "grype.json"), "--quiet"]


def _checkov_command(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    skip = ",".join(DEFAULT_EXCLUDES)
    return ["checkov", "-d", str(repo), "-o", "json", "--quiet", "--skip-path", skip]


def _medusa_command(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    exclude_args = [arg for name in DEFAULT_EXCLUDES for arg in ("--exclude", name)]
    return ["medusa", "scan", "--quick", "--format", "json", "--output", str(scan_dir / "medusa-report"), str(repo), *exclude_args]


def _malcontent_command(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    return _malcontent_diff_command(_malcontent_binary() or "malcontent", "OLD_ARTIFACT", "NEW_ARTIFACT")


def _legitify_command_builder(repo: Path, scan_dir: Path, rules_dir: Path) -> list[str]:
    return _legitify_command(repo, scan_dir, target="[repository]")


def _run_legitify_scanner(repo: Path, repo_name: str, scan_dir: Path) -> ScannerResult:
    started = datetime.now(timezone.utc).isoformat()
    command_preview = _legitify_command(repo, scan_dir, target="[repository]")
    command = command_preview
    binary = command[0]
    raw_path = _raw_path("legitify", scan_dir)
    status = ScannerStatus(scanner="legitify", available=bool(shutil.which(binary)), command=command_preview, started_at=started)
    t0 = time.monotonic()

    if not status.available:
        status.status = "skipped"
        status.finished_at = datetime.now(timezone.utc).isoformat()
        status.duration_seconds = round(time.monotonic() - t0, 3)
        status.error = "legitify is not installed or not on PATH."
        _write_legitify_skip(raw_path, status.error)
        status.raw_report = str(raw_path)
        return ScannerResult(status, [])

    target = _legitify_target(repo)
    if not target:
        status.status = "skipped"
        status.finished_at = datetime.now(timezone.utc).isoformat()
        status.duration_seconds = round(time.monotonic() - t0, 3)
        status.error = "No platform repository target was found. Set SECURITY_OBSERVATORY_PLATFORM_REPO to owner/repo."
        _write_legitify_skip(raw_path, status.error)
        status.raw_report = str(raw_path)
        return ScannerResult(status, [])

    env = _legitify_env(os.environ)
    token = _legitify_token(env)
    if not token:
        status.status = "skipped"
        status.finished_at = datetime.now(timezone.utc).isoformat()
        status.duration_seconds = round(time.monotonic() - t0, 3)
        status.error = (
            "SCM_TOKEN is not set. Open the DëvSec dashboard → Tool Catalog → "
            "legitify, paste a GitHub Personal Access Token, and click Store. "
            "(Or set SCM_TOKEN in the environment.)"
        )
        _write_legitify_skip(raw_path, status.error)
        status.raw_report = str(raw_path)
        return ScannerResult(status, [])

    env["SCM_TOKEN"] = token
    command = _legitify_command(repo, scan_dir, target=target)
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(repo),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(timeout=_timeout("legitify"))
        status.exit_code = proc.returncode
        data = _legitify_output(scan_dir, raw_path, stdout)
        sanitized = sanitize_legitify_payload(data)
        _write_sanitized_legitify_json(raw_path, sanitized)
        if proc.returncode != 0 and not _legitify_has_records(sanitized):
            status.error = _legitify_error(scan_dir, stderr, stdout)
    except subprocess.TimeoutExpired as exc:
        _kill_process_group(proc)
        stdout, stderr = proc.communicate() if proc else ("", "")
        status.exit_code = 124
        status.error = f"legitify timed out after {exc.timeout} seconds."
        _write_legitify_skip(raw_path, status.error)
    except BaseException:
        _kill_process_group(proc)
        raise
    finally:
        status.finished_at = datetime.now(timezone.utc).isoformat()
        status.duration_seconds = round(time.monotonic() - t0, 3)

    findings = _normalize("legitify", read_json_safely(raw_path), repo_name)
    status.raw_report = str(raw_path)
    status.findings = len(findings)
    if status.error:
        status.status = "partial" if findings else "skipped"
    else:
        status.status = "checked"
    return ScannerResult(status, findings)


def _exclude_paths_file(scan_dir: Path) -> Path:
    path = scan_dir / "scanner-exclude-paths.txt"
    patterns = [rf"(^|/){re.escape(name)}(/|$)" for name in DEFAULT_EXCLUDES]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(patterns) + "\n", encoding="utf-8")
    return path


def _legitify_command(repo: Path, scan_dir: Path, *, target: str | None = None) -> list[str]:
    scm = os.environ.get("SECURITY_OBSERVATORY_PLATFORM_SCM", "github").strip() or "github"
    namespaces = os.environ.get("SECURITY_OBSERVATORY_PLATFORM_NAMESPACES", "repository,actions").strip() or "repository,actions"
    resolved_target = target or _legitify_target(repo)
    command = [
        "legitify",
        "analyze",
        "--scm",
        scm,
        "--namespace",
        namespaces,
        "--output-format",
        "json",
        "--output-scheme",
        "flattened",
        "--output-file",
        str(scan_dir / "legitify.json"),
        "--error-file",
        str(scan_dir / "legitify-error.log"),
    ]
    if resolved_target:
        command.extend(["--repo", resolved_target])
    return command


def _legitify_target(repo: Path) -> str | None:
    configured = os.environ.get("SECURITY_OBSERVATORY_PLATFORM_REPO") or os.environ.get("LEGITIFY_REPO")
    if configured and configured.strip():
        return configured.strip().removeprefix("https://github.com/").removesuffix(".git").strip("/")
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "config", "--get", "remote.origin.url"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return _repo_target_from_remote(proc.stdout.strip())


def _repo_target_from_remote(remote: str) -> str | None:
    if not remote:
        return None
    text = remote.strip()
    if text.startswith("git@") and ":" in text:
        text = text.split(":", 1)[1]
    else:
        text = re.sub(r"^[a-z]+://", "", text)
        if "@" in text.split("/", 1)[0]:
            text = text.split("@", 1)[1]
        parts = text.split("/", 1)
        text = parts[1] if len(parts) == 2 else text
    text = text.removesuffix(".git").strip("/")
    segments = [segment for segment in text.split("/") if segment]
    if len(segments) < 2:
        return None
    scm = os.environ.get("SECURITY_OBSERVATORY_PLATFORM_SCM", "github").strip().casefold()
    if scm == "github":
        return "/".join(segments[:2])
    return "/".join(segments)


def _legitify_env(source: os._Environ[str] | dict[str, str]) -> dict[str, str]:
    """Copy ``source`` and overlay SCM_TOKEN from the macOS Keychain if stored.

    The Keychain is consulted via ``credentials.env_with_credentials`` under the
    ``legitify:SCM_TOKEN`` account written by the SetupCard. If no entry exists
    (or the host isn't macOS), the env is left as-is, which preserves the
    pre-Keychain behaviour where SCM_TOKEN was set in the shell or via
    ``security-scan`` wrapper scripts. The Keychain wins over the inherited
    env var so that the value the user just stored from the dashboard takes
    effect immediately, without restarting the shell.
    """
    base: dict[str, str] = dict(source)
    if not keychain_is_supported():
        return base
    return env_with_credentials(base, "legitify", {"SCM_TOKEN": "SCM_TOKEN"})


def _legitify_token(env: dict[str, str]) -> str | None:
    for name in ("SCM_TOKEN", "SECURITY_OBSERVATORY_SCM_TOKEN", "LEGITIFY_TOKEN"):
        value = env.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _write_legitify_skip(raw_path: Path, reason: str) -> None:
    write_json(
        raw_path,
        {
            "schema_version": 1,
            "scanner": "legitify",
            "type": "platform-posture-snapshot",
            "content": {
                "summary": {"records": 0, "failed": 0, "passed": 0, "skipped": 0},
                "records": [],
                "status": "skipped",
                "reason": reason,
            },
        },
    )


def _write_sanitized_legitify_json(raw_path: Path, payload: dict[str, Any]) -> None:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _legitify_output(scan_dir: Path, raw_path: Path, stdout: str) -> Any:
    if raw_path.exists() and raw_path.stat().st_size > 0:
        return read_json_safely(raw_path)
    if stdout.strip():
        return _json_from_text(stdout)
    error_path = scan_dir / "legitify-error.log"
    if error_path.exists() and error_path.stat().st_size > 0:
        return {"error": error_path.read_text(encoding="utf-8", errors="replace")[:4000]}
    return {}


def _legitify_has_records(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    content = data.get("content")
    if not isinstance(content, dict):
        return False
    records = content.get("records")
    return isinstance(records, list) and bool(records)


def _legitify_error(scan_dir: Path, stderr: str, stdout: str) -> str:
    error_path = scan_dir / "legitify-error.log"
    if error_path.exists() and error_path.stat().st_size > 0:
        return error_path.read_text(encoding="utf-8", errors="replace").strip()[:4000]
    return (stderr or stdout or "legitify failed").strip()[:4000]


def _kill_process_group(proc: subprocess.Popen[str] | None) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _raw_path(scanner: str, scan_dir: Path) -> Path:
    if scanner == "syft":
        return scan_dir / "syft.json"
    if scanner == "malcontent":
        return scan_dir / "malcontent.json"
    return scan_dir / f"{scanner}.json"


def _write_outputs(scanner: str, scan_dir: Path, stdout: str, stderr: str) -> None:
    scan_dir.mkdir(parents=True, exist_ok=True)
    raw_path = _raw_path(scanner, scan_dir)
    if scanner == "medusa":
        report_dir = scan_dir / "medusa-report"
        candidates = sorted(report_dir.rglob("*.json")) if report_dir.exists() else []
        if candidates:
            data = read_json_safely(candidates[0])
            write_json(raw_path, data)
            return
    if scanner in {"gitleaks", "osv-scanner", "syft", "grype"} and raw_path.exists():
        data = read_json_safely(raw_path)
        write_json(raw_path, data)
        return
    if stdout.strip():
        data = None
        try:
            data = read_json_safely(_write_temp(scan_dir, scanner, stdout))
        finally:
            write_json(raw_path, data if data is not None else {"stdout": stdout})
    elif stderr.strip() and scanner == "checkov":
        write_json(raw_path, {"stderr": stderr})
    elif not raw_path.exists():
        write_json(raw_path, {})


def _write_temp(scan_dir: Path, scanner: str, text: str) -> Path:
    path = scan_dir / f".{scanner}.stdout.tmp"
    path.write_text(text, encoding="utf-8", errors="replace")
    return path


def _timeout(scanner: str) -> int:
    adapter = SCANNER_REGISTRY.get(scanner)
    return adapter.timeout if adapter else 300


def _malcontent_binary() -> str | None:
    return shutil.which("malcontent") or shutil.which("mal")


def _malcontent_diff_command(binary: str, old_artifact: str, new_artifact: str) -> list[str]:
    return [
        binary,
        "diff",
        "--format=json",
        "--min-risk",
        "medium",
        "--file-risk-increase",
        "--max-files",
        str(MAX_BEHAVIORAL_FILES),
        "--max-image-size",
        str(MAX_BEHAVIORAL_ARTIFACT_BYTES),
        old_artifact,
        new_artifact,
    ]


def _json_from_text(text: str) -> Any:
    try:
        return json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        return {"stdout": text}


def _malcontent_payload(checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "scanner": "malcontent",
        "schema_version": 1,
        "bounds": {
            "max_packages": MAX_BEHAVIORAL_PACKAGES,
            "max_artifact_bytes": MAX_BEHAVIORAL_ARTIFACT_BYTES,
            "max_files": MAX_BEHAVIORAL_FILES,
        },
        "checks": sanitize_json(checks),
    }


# The one place a scanner is described. Every per-scanner facet — command,
# timeout, exit-codes-that-mean-findings, normalizer, run strategy — is a field
# on its single entry here, so adding a scanner is one co-located edit and a
# scanner cannot be half-wired into one dispatch site but missing from another.
# ``run`` is ``None`` for the generic external-binary path; built-in and bespoke
# scanners carry their own run callable. Built-ins have no external ``command``.
SCANNER_REGISTRY: dict[str, ScannerAdapter] = {
    "ai-static": ScannerAdapter(name="ai-static", run=_run_ai_static_scanner),
    INSTALL_HOOK_SCANNER: ScannerAdapter(
        name=INSTALL_HOOK_SCANNER,
        run=_run_install_hook_scanner,
        normalizer=_install_hooks,
    ),
    WORKFLOW_SCANNER: ScannerAdapter(
        name=WORKFLOW_SCANNER,
        run=_run_workflow_scanner,
        normalizer=_workflow_audit,
    ),
    "semgrep": ScannerAdapter(
        name="semgrep",
        timeout=600,
        exit_codes_with_findings=frozenset({1}),
        command=_semgrep_command,
        normalizer=_semgrep,
    ),
    "gitleaks": ScannerAdapter(
        name="gitleaks",
        timeout=300,
        exit_codes_with_findings=frozenset({1}),
        command=_gitleaks_command,
        normalizer=_gitleaks,
    ),
    "trufflehog": ScannerAdapter(
        name="trufflehog",
        timeout=600,
        exit_codes_with_findings=frozenset({183}),
        command=_trufflehog_command,
        normalizer=_trufflehog,
    ),
    "trivy": ScannerAdapter(
        name="trivy",
        timeout=900,
        exit_codes_with_findings=frozenset({1}),
        command=_trivy_command,
        normalizer=_trivy,
    ),
    "osv-scanner": ScannerAdapter(
        name="osv-scanner",
        timeout=600,
        exit_codes_with_findings=frozenset({1}),
        command=_osv_command,
        normalizer=_osv,
    ),
    "syft": ScannerAdapter(
        name="syft",
        timeout=300,
        command=_syft_command,
    ),
    "grype": ScannerAdapter(
        name="grype",
        timeout=600,
        exit_codes_with_findings=frozenset({1}),
        command=_grype_command,
        normalizer=_grype,
    ),
    "checkov": ScannerAdapter(
        name="checkov",
        timeout=600,
        exit_codes_with_findings=frozenset({1}),
        command=_checkov_command,
        normalizer=_checkov,
    ),
    "medusa": ScannerAdapter(
        name="medusa",
        timeout=180,
        exit_codes_with_findings=frozenset({1}),
        command=_medusa_command,
        normalizer=partial(_generic_ai, "medusa"),
    ),
    "malcontent": ScannerAdapter(
        name="malcontent",
        timeout=900,
        command=_malcontent_command,
        normalizer=_malcontent,
    ),
    "legitify": ScannerAdapter(
        name="legitify",
        timeout=600,
        exit_codes_with_findings=frozenset({1}),
        command=_legitify_command_builder,
        normalizer=_legitify,
        run=_run_legitify_adapter,
    ),
}


# Backwards-compatible view of the exit codes that mean "the scanner ran and
# found something", derived from the one registry rather than maintained as a
# parallel dict. Scanners with no special exit code are omitted (any non-zero
# exit is treated as an error), matching the historical ``.get(scanner, set())``.
EXIT_CODES_WITH_FINDINGS: dict[str, set[int]] = {
    name: set(adapter.exit_codes_with_findings)
    for name, adapter in SCANNER_REGISTRY.items()
    if adapter.exit_codes_with_findings
}
