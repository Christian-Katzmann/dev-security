from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re
import tomllib

from .model import DEFAULT_EXCLUDES


INSTALL_HOOK_SCANNER = "install-hooks"
WORKFLOW_SCANNER = "workflow-audit"

INSTALL_HOOK_ALLOWLIST = ".devsec/install-hook-allowlist.yaml"
WORKFLOW_ALLOWLIST = ".devsec/workflow-allowlist.yaml"

INSTALL_HOOK_NAMES = {"preinstall", "install", "postinstall"}
WORKFLOW_SUFFIXES = {".yml", ".yaml"}
MAX_SURFACE_FILE_BYTES = 1_000_000

_FETCH_PIPE_SHELL_RE = re.compile(r"\b(?:curl|wget)\b[^\n|]*\|[^\n]*(?:\b(?:ba)?sh\b)", re.IGNORECASE)
_BASE64_PIPE_SHELL_RE = re.compile(r"\bbase64\b[^\n|]*(?:-d|--decode)[^\n|]*\|[^\n]*(?:\b(?:ba)?sh\b)", re.IGNORECASE)
_FETCH_THEN_EVAL_RE = re.compile(r"\b(?:curl|wget|fetch)\b[\s\S]*\beval\b|\beval\b[\s\S]*\b(?:curl|wget|fetch)\b", re.IGNORECASE)
_TMP_WRITE_EXEC_RE = re.compile(r"/tmp/[A-Za-z0-9._-]{6,}[\s\S]*(?:chmod|(?:ba)?sh\b|exec\b|\./)", re.IGNORECASE)
_INSTALL_CONFIG_WRITE_RE = re.compile(r"(?:>|>>|\btee\b|\bsed\b|\brm\b|\bmv\b)[^\n]*(?:~/\.npmrc|~/\.pypirc)|(?:~/\.npmrc|~/\.pypirc)[^\n]*(?:>|>>|\btee\b|\bsed\b|\brm\b|\bmv\b)", re.IGNORECASE)
_DYNAMIC_ARTIFACT_RE = re.compile(r"\b(?:curl|wget|fetch)\b[\s\S]*(?:https?://|ftp://)[\s\S]*(?:\.tar\.gz|\.tgz|\.zip|\.dmg|\.pkg|\.node|\.wasm|\.so|\.dll|\.bin|chmod|tar\b|unzip\b)", re.IGNORECASE)
_NODE_OPTIONS_RE = re.compile(r"(?:^|[\s;&])NODE_OPTIONS\s*=", re.IGNORECASE)
_CHILD_PROCESS_RE = re.compile(r"\bchild_process\b|\brequire\([\"']node:child_process[\"']\)|\brequire\([\"']child_process[\"']\)", re.IGNORECASE)
_NESTED_INSTALL_RE = re.compile(r"\b(?:npm|pnpm|yarn)\s+run\s+install:[A-Za-z0-9_.:-]+", re.IGNORECASE)
_LOCAL_SUBPROJECT_INSTALL_RE = re.compile(r"\b(?:npm|pnpm|yarn)\b[^\n]*(?:--prefix|--filter|--dir|--cwd|cd\s+\./)[^\n]*\binstall\b", re.IGNORECASE)
_PNPM_ENFORCER_RE = re.compile(r"\bpnpm\b[^\n]*(?:--frozen-lockfile|--prefer-offline|fetch\s+--offline)", re.IGNORECASE)
_NODE_GYP_RE = re.compile(r"\bnode-gyp\b[^\n]*\brebuild\b", re.IGNORECASE)
_NATIVE_BUILD_RE = re.compile(r"\b(?:node-gyp|cmake|make|gcc|clang|cargo\s+build|maturin|setuptools-rust)\b", re.IGNORECASE)
_CHECKSUM_RE = re.compile(r"\b(?:sha256|sha512|checksum|shasum|integrity|sigstore|cosign)\b", re.IGNORECASE)
_SHELL_OUT_RE = re.compile(r"\b(?:bash|sh)\s+-c\b|\b(?:python|node|perl|ruby)\s+-e\b|\bnpx\s+(?!--yes\s+tsx\b)", re.IGNORECASE)

_USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^#\s]+)", re.IGNORECASE)
_RUN_RE = re.compile(r"^\s*(?:-\s*)?run:\s*(.*)$", re.IGNORECASE)
_SECRET_REF_RE = re.compile(r"\$\{\{\s*secrets\.[^}]+}}", re.IGNORECASE)
_SECRET_EXFIL_RE = re.compile(r"\b(?:base64|xxd|od)\b|\becho\b[^\n|]*\||\b(?:curl|wget|nc|openssl\s+s_client)\b|https?://", re.IGNORECASE)
_UNTRUSTED_INPUT_RE = re.compile(r"\$\{\{\s*github\.event\.[^}]+(?:body|title)\s*}}", re.IGNORECASE)
_PERMISSIONS_WRITE_RE = re.compile(r"^\s*([A-Za-z0-9_-]+):\s*(write|write-all)\b", re.IGNORECASE)


@dataclass(frozen=True)
class AllowlistEntry:
    rule: str
    path: str
    reason: str
    line: int | None = None


@dataclass(frozen=True)
class Allowlist:
    path: str
    entries: tuple[AllowlistEntry, ...]
    issues: tuple[dict[str, Any], ...]


def scan_install_hooks(repo: Path, repo_name: str) -> dict[str, Any]:
    """Classify package-manager and Python install-time hooks using local files only."""
    repo = repo.resolve()
    allowlist = _load_allowlist(repo / INSTALL_HOOK_ALLOWLIST)
    hooks: list[dict[str, Any]] = []

    for path in _walk_surface_files(repo):
        if path.name == "package.json":
            hooks.extend(_package_json_hooks(repo, path))
        elif path.name == "pyproject.toml":
            hooks.extend(_pyproject_hooks(repo, path))
        elif path.name == "setup.py":
            hooks.extend(_setup_py_hooks(repo, path))

    hooks = [_apply_allowlist(hook, allowlist) for hook in hooks]
    return {
        "schema_version": 1,
        "scanner": INSTALL_HOOK_SCANNER,
        "repo": repo_name,
        "allowlist": _allowlist_payload(allowlist),
        "hooks": hooks,
        "summary": _severity_summary(hooks),
    }


def scan_workflow_surfaces(repo: Path, repo_name: str) -> dict[str, Any]:
    """Audit GitHub Actions workflow surfaces with deterministic local rules."""
    repo = repo.resolve()
    allowlist = _load_allowlist(repo / WORKFLOW_ALLOWLIST)
    findings: list[dict[str, Any]] = []

    workflow_root = repo / ".github" / "workflows"
    if workflow_root.exists():
        for path in sorted(workflow_root.glob("*")):
            if path.suffix.lower() not in WORKFLOW_SUFFIXES or not path.is_file():
                continue
            findings.extend(_workflow_file_findings(repo, path))

    findings = [_apply_allowlist(finding, allowlist) for finding in findings]
    return {
        "schema_version": 1,
        "scanner": WORKFLOW_SCANNER,
        "repo": repo_name,
        "allowlist": _allowlist_payload(allowlist),
        "findings": findings,
        "summary": _severity_summary(findings),
    }


def actionable_install_hook_records(payload: Any) -> list[dict[str, Any]]:
    records = payload.get("hooks") if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return []
    return [
        record
        for record in records
        if isinstance(record, dict)
        and not record.get("allowlisted")
        and str(record.get("severity") or "").casefold() in {"critical", "high"}
    ]


def actionable_workflow_records(payload: Any) -> list[dict[str, Any]]:
    records = payload.get("findings") if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return []
    return [
        record
        for record in records
        if isinstance(record, dict)
        and not record.get("allowlisted")
        and str(record.get("severity") or "").casefold() in {"critical", "high", "medium"}
    ]


def _package_json_hooks(repo: Path, path: Path) -> list[dict[str, Any]]:
    text = _read_text(path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return []

    hooks = []
    for hook_name in sorted(INSTALL_HOOK_NAMES):
        if hook_name not in scripts:
            continue
        command = str(scripts.get(hook_name) or "")
        line = _line_for_key(text, hook_name)
        hooks.append(_install_record(repo, path, line, "package-json-script", hook_name, command))
    return hooks


def _pyproject_hooks(repo: Path, path: Path) -> list[dict[str, Any]]:
    text = _read_text(path)
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    hooks: list[dict[str, Any]] = []
    build_backend = _deep_get(data, ("build-system", "build-backend"))
    if isinstance(build_backend, str) and build_backend.strip():
        hooks.append(
            _install_record(
                repo,
                path,
                _line_for_text(text, build_backend),
                "python-build-backend",
                "build-backend",
                build_backend,
                default_info="Python build backend is declared for source builds.",
            )
        )
    for key_path, value in _walk_toml_values(data):
        lower_path = ".".join(key_path).casefold()
        if not any(token in lower_path for token in ("hook", "script", "command", "install")):
            continue
        for command in _string_values(value):
            if not command.strip():
                continue
            hooks.append(
                _install_record(
                    repo,
                    path,
                    _line_for_text(text, command),
                    "python-build-hook",
                    ".".join(key_path),
                    command,
                )
            )
    return _dedupe_records(hooks)


def _setup_py_hooks(repo: Path, path: Path) -> list[dict[str, Any]]:
    hooks = []
    for line_number, line in enumerate(_read_text(path).splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not re.search(r"\b(?:cmdclass|install|subprocess|os\.system|check_call|check_output|curl|wget|eval)\b", stripped):
            continue
        hooks.append(_install_record(repo, path, line_number, "setup-py-install", "setup.py", stripped))
    return _dedupe_records(hooks)


def _install_record(
    repo: Path,
    path: Path,
    line: int | None,
    source: str,
    hook: str,
    command: str,
    *,
    default_info: str | None = None,
) -> dict[str, Any]:
    classification = _classify_install_command(command, repo=repo, path=path, default_info=default_info)
    rel_path = _relative_path(path, repo)
    return {
        "path": rel_path,
        "line": line,
        "source": source,
        "hook": hook,
        "command": command,
        **classification,
        "fingerprint": _record_fingerprint(INSTALL_HOOK_SCANNER, rel_path, line, classification["rule"], command),
    }


def _classify_install_command(command: str, *, repo: Path, path: Path, default_info: str | None = None) -> dict[str, Any]:
    text = command.strip()
    referenced_text = _referenced_node_script_text(text, repo, path)
    combined = f"{text}\n{referenced_text}".strip()
    if _FETCH_PIPE_SHELL_RE.search(combined):
        return _classification("critical", "high", "install-fetch-pipe-shell", "Install hook pipes a remote script into a shell.", "Replace remote shell execution with a pinned, checksum-verified artifact or checked-in installer.")
    if _BASE64_PIPE_SHELL_RE.search(combined):
        return _classification("critical", "high", "install-base64-shell", "Install hook decodes base64 and executes it.", "Remove encoded shell execution from install time and inspect the package source.")
    if _FETCH_THEN_EVAL_RE.search(combined):
        return _classification("critical", "high", "install-fetch-eval", "Install hook fetches code and evaluates it.", "Do not evaluate downloaded code during installation; pin and review any required artifact.")
    if _TMP_WRITE_EXEC_RE.search(combined):
        return _classification("critical", "medium", "install-temp-exec", "Install hook writes and executes a temporary file.", "Replace temporary execution with a reviewed in-repo script or remove the installer behavior.")
    if _INSTALL_CONFIG_WRITE_RE.search(combined):
        return _classification("critical", "high", "install-config-write", "Install hook modifies npm or PyPI credentials/config.", "Remove install-time writes to ~/.npmrc or ~/.pypirc and verify no credentials were exposed.")

    if _PNPM_ENFORCER_RE.search(combined):
        return _classification("info", "high", "install-pnpm-enforcer", "Install hook enforces pnpm install policy.", "Keep the command documented so reviewers know it is a policy guard.")
    if _LOCAL_SUBPROJECT_INSTALL_RE.search(combined):
        return _classification("info", "medium", "install-local-subproject", "Install hook chains into a local subproject.", "Confirm the subproject path stays inside the repository.")
    if _DYNAMIC_ARTIFACT_RE.search(combined):
        return _classification("high", "medium", "install-dynamic-artifact", "Install hook downloads a compiled or executable artifact.", "Pin the artifact, verify its checksum, and document the trusted publisher.")
    if _NODE_OPTIONS_RE.search(combined):
        return _classification("high", "medium", "install-node-options", "Install hook changes NODE_OPTIONS during installation.", "Avoid changing Node runtime options during install unless the reason is documented and narrow.")
    if _CHILD_PROCESS_RE.search(combined):
        return _classification("high", "medium", "install-child-process", "Install hook invokes child_process.", "Review the child process invocation and replace shell execution with fixed arguments where possible.")
    if _SHELL_OUT_RE.search(combined):
        return _classification("high", "medium", "install-unaudited-shellout", "Install hook shells out to an unaudited interpreter or binary.", "Replace the shell-out with a reviewed local script or document the trusted binary.")
    if _NESTED_INSTALL_RE.search(combined):
        return _classification("medium", "medium", "install-nested-installer", "Install hook runs another installer script.", "Review the nested installer and keep it visible in the install-hook report.")
    if _NODE_GYP_RE.search(combined) and not _CHECKSUM_RE.search(combined):
        return _classification("medium", "medium", "install-node-gyp-no-checksum", "Install hook rebuilds native code without a published checksum.", "Document why the native build is expected and how the source is verified.")
    if _NATIVE_BUILD_RE.search(combined) and not _CHECKSUM_RE.search(combined):
        return _classification("medium", "medium", "install-native-build-no-checksum", "Install hook runs native build tooling without a published checksum.", "Document the native build path and verify the source provenance.")
    if default_info:
        return _classification("info", "medium", "install-python-build-backend", default_info, "Confirm the backend is expected for source builds.")
    return _classification("medium", "low", "install-unknown-pattern", "Install hook uses a pattern Observatory does not classify yet.", "Review the command manually and add a narrow allow-list entry only when it is known-good.")


def _workflow_file_findings(repo: Path, path: Path) -> list[dict[str, Any]]:
    text = _read_text(path)
    lines = text.splitlines()
    findings: list[dict[str, Any]] = []

    for line_number, line in enumerate(lines, start=1):
        match = _USES_RE.match(line)
        if match and _is_unpinned_action(match.group(1)):
            findings.append(
                _workflow_record(
                    repo,
                    path,
                    line_number,
                    "workflow-unpinned-action",
                    "high",
                    "Workflow uses an action without a commit SHA pin.",
                    f"Pin {match.group(1)} to a reviewed commit SHA.",
                    evidence=match.group(1),
                    confidence="high",
                )
            )

    for block in _workflow_run_blocks(lines):
        body = block["body"]
        line_number = block["line"]
        if _FETCH_PIPE_SHELL_RE.search(body) or re.search(r"\bbash\s+<\s*<\(\s*curl\b", body, re.IGNORECASE):
            findings.append(
                _workflow_record(
                    repo,
                    path,
                    line_number,
                    "workflow-fetch-exec",
                    "critical",
                    "Workflow run block fetches and executes remote code.",
                    "Pin and verify downloaded artifacts instead of piping remote scripts into a shell.",
                    evidence=body,
                    confidence="high",
                )
            )
        if _SECRET_REF_RE.search(body) and _SECRET_EXFIL_RE.search(body):
            findings.append(
                _workflow_record(
                    repo,
                    path,
                    line_number,
                    "workflow-secret-exfil",
                    "critical",
                    "Workflow run block transforms or sends a secret.",
                    "Keep secrets inside trusted actions or provider-native secret handling; never echo, encode, or send them manually.",
                    evidence=body,
                    confidence="high",
                )
            )
        if _UNTRUSTED_INPUT_RE.search(body):
            findings.append(
                _workflow_record(
                    repo,
                    path,
                    line_number,
                    "workflow-untrusted-input-run",
                    "critical",
                    "Workflow run block executes untrusted event text.",
                    "Pass untrusted event fields through files or action inputs instead of interpolating them into shell.",
                    evidence=body,
                    confidence="high",
                )
            )

    if _has_pull_request_target(lines) and _has_fork_checkout(lines):
        findings.append(
            _workflow_record(
                repo,
                path,
                _line_for_pattern(lines, r"pull_request_target") or 1,
                "workflow-pr-target-fork-checkout",
                "medium",
                "pull_request_target workflow checks out fork-controlled code.",
                "Avoid checking out fork refs under pull_request_target, or isolate it from privileged tokens.",
                evidence="pull_request_target with fork checkout",
                confidence="medium",
            )
        )

    findings.extend(_workflow_permission_findings(repo, path, lines))
    return _dedupe_records(findings)


def _workflow_permission_findings(repo: Path, path: Path, lines: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    permission_block_indent: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if not stripped or stripped.startswith("#"):
            continue

        if re.match(r"^permissions:\s*write-all\b", stripped, re.IGNORECASE):
            if not _has_justification(lines, index):
                findings.append(
                    _workflow_record(
                        repo,
                        path,
                        index + 1,
                        "workflow-permissions-write-all",
                        "high",
                        "Workflow grants write-all token permissions without justification.",
                        "Replace write-all with the smallest named permissions, or add a clear justification comment.",
                        evidence=stripped,
                        confidence="high",
                    )
                )
            permission_block_indent = None
            continue

        if re.match(r"^permissions:\s*$", stripped, re.IGNORECASE):
            permission_block_indent = indent
            continue

        if permission_block_indent is not None and indent <= permission_block_indent:
            permission_block_indent = None

        if permission_block_indent is None:
            continue

        match = _PERMISSIONS_WRITE_RE.match(line)
        if not match or match.group(1).casefold() == "contents" and match.group(2).casefold() == "read":
            continue
        if _has_justification(lines, index):
            continue
        findings.append(
            _workflow_record(
                repo,
                path,
                index + 1,
                "workflow-permissions-write",
                "high",
                f"Workflow grants {match.group(1)} write permission without justification.",
                "Keep workflow token permissions read-only by default and justify each write scope.",
                evidence=stripped,
                confidence="medium",
            )
        )
    return findings


def _workflow_record(
    repo: Path,
    path: Path,
    line: int,
    rule: str,
    severity: str,
    title: str,
    remediation: str,
    *,
    evidence: str,
    confidence: str,
) -> dict[str, Any]:
    rel_path = _relative_path(path, repo)
    return {
        "path": rel_path,
        "line": line,
        "rule": rule,
        "severity": severity,
        "confidence": confidence,
        "title": title,
        "remediation": remediation,
        "evidence": evidence.strip(),
        "fingerprint": _record_fingerprint(WORKFLOW_SCANNER, rel_path, line, rule, evidence),
    }


def _classification(severity: str, confidence: str, rule: str, title: str, remediation: str) -> dict[str, str]:
    return {
        "severity": severity,
        "confidence": confidence,
        "rule": rule,
        "title": title,
        "remediation": remediation,
    }


def _walk_surface_files(repo: Path) -> list[Path]:
    if not repo.exists():
        return []
    files: list[Path] = []
    stack = [repo]
    while stack:
        current = stack.pop()
        if current.name in DEFAULT_EXCLUDES:
            continue
        try:
            if current.is_dir():
                stack.extend(sorted(current.iterdir(), key=lambda item: item.name.lower(), reverse=True))
                continue
            if current.stat().st_size > MAX_SURFACE_FILE_BYTES:
                continue
        except OSError:
            continue
        if current.name in {"package.json", "pyproject.toml", "setup.py"}:
            files.append(current)
    return files


def _workflow_run_blocks(lines: list[str]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        match = _RUN_RE.match(line)
        if not match:
            continue
        value = match.group(1).strip()
        if value and value not in {"|", ">"}:
            blocks.append({"line": index + 1, "body": value})
            continue
        base_indent = len(line) - len(line.lstrip(" "))
        collected: list[str] = []
        start_line = index + 1
        for follow_index, follow in enumerate(lines[index + 1 :], start=index + 2):
            if not follow.strip():
                continue
            indent = len(follow) - len(follow.lstrip(" "))
            if indent <= base_indent:
                break
            if not collected:
                start_line = follow_index
            collected.append(follow.strip())
        if collected:
            blocks.append({"line": start_line, "body": "\n".join(collected)})
    return blocks


def _is_unpinned_action(value: str) -> bool:
    action = value.strip().strip("\"'")
    if not action or action.startswith(("./", "../", "docker://")):
        return False
    if "@" not in action:
        return False
    ref = action.rsplit("@", 1)[1]
    return not bool(re.fullmatch(r"[a-f0-9]{40}", ref, re.IGNORECASE))


def _has_pull_request_target(lines: list[str]) -> bool:
    return any(re.search(r"\bpull_request_target\b", line) for line in lines)


def _has_fork_checkout(lines: list[str]) -> bool:
    for index, line in enumerate(lines):
        if not re.search(r"uses:\s*actions/checkout@", line, re.IGNORECASE):
            continue
        block = "\n".join(lines[index : index + 10])
        if re.search(r"github\.event\.pull_request\.head\.(?:sha|ref|repo\.full_name)", block, re.IGNORECASE):
            return True
    return False


def _has_justification(lines: list[str], index: int) -> bool:
    window = [lines[index]]
    for offset in (1, 2):
        if index - offset >= 0:
            window.append(lines[index - offset])
    return any("#" in line and re.search(r"\b(?:justification|reason|needed because|why)\b", line, re.IGNORECASE) for line in window)


def _referenced_node_script_text(command: str, repo: Path, package_json: Path) -> str:
    matches = re.findall(r"(?:^|[\s;&])node\s+([A-Za-z0-9_./@-]+\.m?js)\b", command)
    snippets: list[str] = []
    base = package_json.parent
    for match in matches[:3]:
        target = (base / match).resolve()
        try:
            target.relative_to(repo)
        except ValueError:
            continue
        if not target.exists() or target.stat().st_size > MAX_SURFACE_FILE_BYTES:
            continue
        snippets.append(_read_text(target))
    return "\n".join(snippets)


def _load_allowlist(path: Path) -> Allowlist:
    if not path.exists():
        return Allowlist(str(path), (), ())
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return Allowlist(str(path), (), ({"path": str(path), "message": f"Could not read allow-list: {exc}"},))

    raw_entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    issues: list[dict[str, Any]] = []
    for line_number, original in enumerate(text.splitlines(), start=1):
        line = _strip_comment(original).rstrip()
        if not line.strip() or line.strip() == "entries:":
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            current = {"__line__": line_number}
            raw_entries.append(current)
            rest = stripped[2:].strip()
            if rest:
                _assign_yaml_field(current, rest, line_number)
            continue
        if current is None:
            issues.append({"path": str(path), "line": line_number, "message": "Allow-list fields must be under entries[]."})
            continue
        _assign_yaml_field(current, stripped, line_number)

    entries: list[AllowlistEntry] = []
    for item in raw_entries:
        line = _optional_int(item.get("__line__"))
        rule = _optional_text(item.get("rule"))
        entry_path = _optional_text(item.get("path"))
        reason = _optional_text(item.get("reason"))
        if not rule or not entry_path:
            issues.append({"path": str(path), "line": line, "message": "Allow-list entries require rule and path."})
            continue
        if not reason:
            issues.append({"path": str(path), "line": line, "message": f"Allow-list entry for {rule} at {entry_path} is missing a reason."})
        entries.append(AllowlistEntry(rule=rule, path=entry_path, reason=reason or "", line=_optional_int(item.get("line"))))
    return Allowlist(str(path), tuple(entries), tuple(issues))


def _apply_allowlist(record: dict[str, Any], allowlist: Allowlist) -> dict[str, Any]:
    for entry in allowlist.entries:
        if entry.rule not in {"*", str(record.get("rule") or "")}:
            continue
        if not _path_matches(entry.path, str(record.get("path") or "")):
            continue
        if entry.line is not None and entry.line != record.get("line"):
            continue
        if not entry.reason:
            return {**record, "allowlisted": False, "allowlist_error": "Matching allow-list entry is missing a reason."}
        return {**record, "allowlisted": True, "allowlist_reason": entry.reason}
    return {**record, "allowlisted": False}


def _path_matches(entry_path: str, record_path: str) -> bool:
    entry = _normalize_path(entry_path)
    record = _normalize_path(record_path)
    return entry == record or entry.endswith(f"/{record}") or record.endswith(f"/{entry}")


def _allowlist_payload(allowlist: Allowlist) -> dict[str, Any]:
    return {
        "path": allowlist.path,
        "entries": [{"rule": entry.rule, "path": entry.path, "line": entry.line, "reason": entry.reason} for entry in allowlist.entries],
        "issues": list(allowlist.issues),
    }


def _severity_summary(records: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"critical": 0, "high": 0, "medium": 0, "info": 0, "allowlisted": 0}
    for record in records:
        if record.get("allowlisted"):
            summary["allowlisted"] += 1
            continue
        severity = str(record.get("severity") or "medium").casefold()
        summary[severity] = summary.get(severity, 0) + 1
    return summary


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for record in records:
        key = (record.get("path"), record.get("line"), record.get("rule"), record.get("hook"), record.get("evidence"), record.get("command"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _walk_toml_values(value: Any, key_path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    items: list[tuple[tuple[str, ...], Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk_toml_values(child, (*key_path, str(key))))
        return items
    if isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk_toml_values(child, (*key_path, str(index))))
        return items
    items.append((key_path, value))
    return items


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, (str, int, float))]
    return []


def _deep_get(source: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = source
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _line_for_key(text: str, key: str) -> int | None:
    pattern = re.compile(rf"[\"']{re.escape(key)}[\"']\s*:")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            return line_number
    return None


def _line_for_text(text: str, needle: str) -> int | None:
    if not needle:
        return None
    for line_number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return line_number
    return None


def _line_for_pattern(lines: list[str], pattern: str) -> int | None:
    regex = re.compile(pattern, re.IGNORECASE)
    for line_number, line in enumerate(lines, start=1):
        if regex.search(line):
            return line_number
    return None


def _assign_yaml_field(target: dict[str, Any], text: str, line_number: int) -> None:
    key, separator, value = text.partition(":")
    if not separator:
        target.setdefault("__errors__", []).append(f"Line {line_number}: expected key: value.")
        return
    target[key.strip()] = _parse_scalar(value.strip())


def _parse_scalar(value: str) -> Any:
    if not value:
        return ""
    lowered = value.casefold()
    if lowered in {"null", "none", "~"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    return _clean_yaml_string(value)


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def _clean_yaml_string(value: Any) -> str:
    text = str(value).strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _relative_path(path: Path, repo: Path) -> str:
    try:
        return str(path.relative_to(repo))
    except ValueError:
        return str(path)


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def _record_fingerprint(scanner: str, path: str, line: int | None, rule: str, evidence: str) -> str:
    import hashlib

    key = "|".join([scanner, path, str(line or ""), rule, evidence.strip()])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
