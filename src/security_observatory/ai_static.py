from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

from .model import DEFAULT_EXCLUDES, Finding


AI_CONFIG_NAMES = {
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    ".clinerules",
    ".windsurfrules",
    "mcp.json",
    ".mcp.json",
}

AI_CONFIG_DIRS = {
    ".codex",
    ".claude",
    ".cursor",
    ".continue",
    ".roo",
    ".vscode",
    ".windsurf",
}

PROMPT_INJECTION_RE = re.compile(
    r"(?i)(ignore (all )?(previous|prior) instructions|system prompt|developer message|"
    r"exfiltrat(e|ion)|leak (the )?(secret|token|key)|send .*?(env|secrets?)|"
    r"hidden instruction|prompt injection|tool poisoning)"
)
DANGEROUS_COMMAND_RE = re.compile(r"(?i)\b(curl|wget|nc|netcat|bash -c|sh -c|rm -rf|chmod 777|osascript)\b")
PLAINTEXT_HTTP_RE = re.compile(r"(?i)\bhttp://[^\s\"'<>]+")
UNPINNED_RUNNER_RE = re.compile(r"(?i)\b(npx|uvx|bunx|pipx)\b")
BROAD_AUTO_APPROVAL_RE = re.compile(
    r"(?i)(auto[-_ ]?approve\s*(all|\*)|always[-_ ]?allow|allow\s*all|approval[-_ ]?mode\s*[:=]\s*(never|none)|"
    r"dangerously[-_ ]?skip[-_ ]?permissions|skip[-_ ]?permissions|disable[-_ ]?approval)"
)
WORKSPACE_WIDE_PERMISSION_RE = re.compile(
    r"(?i)(workspace[-_ ]?wide|full[-_ ]?access|write\s+all\s+files|read\s+all\s+files|"
    r"danger[-_ ]?full[-_ ]?access|allow\s*[:=]\s*\*|permissions?\s*[:=]\s*\*)"
)
SHELL_COMMANDS = {"bash", "sh", "zsh", "fish", "powershell", "pwsh", "cmd", "python", "python3", "node", "ruby", "perl"}
NETWORK_OR_WRITE_COMMANDS = {
    "curl",
    "wget",
    "nc",
    "netcat",
    "ssh",
    "scp",
    "rsync",
    "git",
    "tee",
    "rm",
    "mv",
    "cp",
    "chmod",
    "chown",
}
CAPABLE_MCP_ARG_RE = re.compile(
    r"(?i)(server[-_]?filesystem|filesystem|file[-_]?system|shell|terminal|fetch|browser|playwright|puppeteer|firecrawl|brave[-_]?search)"
)
HIDDEN_UNICODE = {
    "\u200b": "zero-width space",
    "\u200c": "zero-width non-joiner",
    "\u200d": "zero-width joiner",
    "\ufeff": "byte-order mark",
    "\u202e": "right-to-left override",
    "\u2066": "left-to-right isolate",
    "\u2067": "right-to-left isolate",
    "\u2068": "first-strong isolate",
    "\u2069": "pop directional isolate",
}


def scan_ai_static(repo: Path, repo_name: str) -> list[Finding]:
    findings: list[Finding] = []
    for path in _candidate_files(repo):
        rel = str(path.relative_to(repo))
        text = path.read_text(encoding="utf-8", errors="replace")
        findings.extend(_scan_text(repo_name, rel, text))
        if path.suffix.lower() == ".json" or path.name.endswith(".json"):
            findings.extend(_scan_json(repo_name, rel, text))
    return findings


def _candidate_files(repo: Path) -> list[Path]:
    out: list[Path] = []
    for path in repo.rglob("*"):
        try:
            rel_parts = path.relative_to(repo).parts
        except ValueError:
            continue
        # Match exclude/config names against the path RELATIVE to the repo root,
        # not the absolute path. Otherwise a repo that happens to live under
        # /tmp/ (e.g. pytest's tmp_path on Linux CI runners) gets every file
        # silently dropped because "tmp" is in DEFAULT_EXCLUDES.
        if any(part in DEFAULT_EXCLUDES for part in rel_parts):
            continue
        if not path.is_file():
            continue
        if path.name in AI_CONFIG_NAMES or any(part in AI_CONFIG_DIRS for part in rel_parts):
            if path.stat().st_size <= 2_000_000:
                out.append(path)
    return out


def _scan_text(repo_name: str, rel: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    structured_json = _looks_json_file(rel)
    for char, label in HIDDEN_UNICODE.items():
        if char in text:
            line = text[: text.index(char)].count("\n") + 1
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="ai-static",
                    severity="high",
                    category="ai-risk",
                    title=f"Hidden Unicode control character in AI-facing config ({label})",
                    file=rel,
                    line=line,
                    remediation="Remove invisible control characters from agent instructions and MCP/tool descriptions.",
                )
            )
    for index, line in enumerate(text.splitlines(), start=1):
        if PROMPT_INJECTION_RE.search(line):
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="ai-static",
                    severity="medium",
                    category="ai-risk",
                    title="AI-facing file contains prompt-injection language",
                    file=rel,
                    line=index,
                    remediation="Treat this as untrusted content or move it out of agent-readable instructions.",
                )
            )
        if not structured_json and DANGEROUS_COMMAND_RE.search(line) and ("mcp" in rel.lower() or "agent" in rel.lower() or ".vscode" in rel.lower()):
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="ai-static",
                    severity="high",
                    category="ai-risk",
                    title="AI/editor configuration references a dangerous shell-capable command",
                    file=rel,
                    line=index,
                    remediation="Pin and constrain agent/editor commands; avoid network shell pipelines and broad filesystem mutation.",
                )
            )
        if not structured_json and PLAINTEXT_HTTP_RE.search(line) and ("mcp" in rel.lower() or "agent" in rel.lower() or ".vscode" in rel.lower()):
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="ai-static",
                    severity="medium",
                    category="ai-risk",
                    title="AI/editor configuration references plaintext HTTP",
                    file=rel,
                    line=index,
                    remediation="Use HTTPS or keep the endpoint explicitly local and isolated.",
                )
            )
        if not structured_json and UNPINNED_RUNNER_RE.search(line) and not _runner_line_is_pinned(line):
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="ai-static",
                    severity="medium",
                    category="ai-risk",
                    title="Agent command uses a package runner without an obvious pinned version",
                    file=rel,
                    line=index,
                    remediation="Pin package versions for package-runner based MCP servers and agent tools.",
                )
            )
        if not structured_json and BROAD_AUTO_APPROVAL_RE.search(line):
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="ai-static",
                    severity="critical",
                    category="ai-risk",
                    title="Agent/editor config appears to enable broad auto-approval",
                    file=rel,
                    line=index,
                    remediation="Require human approval for destructive commands, network access, and writes outside the repo.",
                )
            )
        if not structured_json and WORKSPACE_WIDE_PERMISSION_RE.search(line):
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="ai-static",
                    severity="high",
                    category="ai-risk",
                    title="Agent/editor config appears to grant broad workspace permissions",
                    file=rel,
                    line=index,
                    remediation="Limit agent permissions to explicit tools, commands, and repo-local paths.",
                )
            )
    return findings


def _scan_json(repo_name: str, rel: str, text: str) -> list[Finding]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    findings: list[Finding] = []
    haystack = json.dumps(data, sort_keys=True)
    lower = haystack.lower()
    if _has_broad_auto_approval(data) or "dangerouslyskippermissions" in lower or '"autoapprove": true' in lower or '"allowall": true' in lower:
        findings.append(
            Finding(
                repo=repo_name,
                scanner="ai-static",
                severity="critical",
                category="ai-risk",
                title="Agent/editor config appears to enable broad auto-approval",
                file=rel,
                remediation="Require human approval for destructive commands, network access, and writes outside the repo.",
            )
        )
    if _has_workspace_wide_permissions(data):
        findings.append(
            Finding(
                repo=repo_name,
                scanner="ai-static",
                severity="high",
                category="ai-risk",
                title="Agent/editor config appears to grant broad workspace permissions",
                file=rel,
                remediation="Limit agent permissions to explicit tools, commands, and repo-local paths.",
            )
        )
    if '"http://' in lower or PLAINTEXT_HTTP_RE.search(haystack):
        findings.append(
            Finding(
                repo=repo_name,
                scanner="ai-static",
                severity="medium",
                category="ai-risk",
                title="MCP or editor config references plaintext HTTP",
                file=rel,
                remediation="Use HTTPS or a local-only endpoint with an explicit trust boundary.",
            )
        )
    for command_info in _command_entries(data):
        command = command_info["command"]
        args = command_info["args"]
        if _is_shell_or_capable_command(command, args):
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="ai-static",
                    severity="high",
                    category="ai-risk",
                    title="MCP or agent config starts a shell, network, or file-write capable command",
                    file=rel,
                    remediation="Wrap powerful MCP commands with the narrowest possible arguments and approval requirements.",
                )
            )
        if command in {"npx", "uvx", "pipx", "bunx"} and not _runner_args_are_pinned(command, args):
            findings.append(
                Finding(
                    repo=repo_name,
                    scanner="ai-static",
                    severity="medium",
                    category="ai-risk",
                    title="MCP command uses a package runner without an obvious pinned version",
                    file=rel,
                    remediation="Pin package versions for MCP servers and agent tools to reduce supply-chain drift.",
                )
            )
    return findings


def _looks_json_file(rel: str) -> bool:
    return rel.lower().endswith(".json")


def _command_entries(data: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if isinstance(data, dict):
        if isinstance(data.get("command"), str):
            entries.append({"command": _base_command(data["command"]), "args": _as_args(data.get("args"))})
        for value in data.values():
            entries.extend(_command_entries(value))
    elif isinstance(data, list):
        for item in data:
            entries.extend(_command_entries(item))
    return entries


def _base_command(value: str) -> str:
    return Path(value.strip().split()[0]).name.lower() if value.strip() else ""


def _as_args(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return value.split()
    return []


def _is_shell_or_capable_command(command: str, args: list[str]) -> bool:
    joined = " ".join([command, *args]).lower()
    return (
        command in SHELL_COMMANDS
        or command in NETWORK_OR_WRITE_COMMANDS
        or bool(DANGEROUS_COMMAND_RE.search(joined))
        or bool(CAPABLE_MCP_ARG_RE.search(joined))
    )


def _runner_line_is_pinned(line: str) -> bool:
    parts = line.split()
    for index, part in enumerate(parts):
        runner = Path(part).name.lower()
        if runner in {"npx", "uvx", "pipx", "bunx"}:
            return _runner_args_are_pinned(runner, parts[index + 1 :])
    return True


def _runner_args_are_pinned(command: str, args: list[str]) -> bool:
    package = _runner_package(command, args)
    if not package:
        return False
    if command in {"npx", "bunx"}:
        return _npm_spec_is_pinned(package)
    if command == "uvx":
        return "==" in package or "@" in package or re.search(r"[<>=~!]=?", package) is not None
    if command == "pipx":
        return "==" in package or re.search(r"[<>=~!]=?", package) is not None
    return False


def _runner_package(command: str, args: list[str]) -> str | None:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if not arg:
            continue
        if command == "pipx" and arg in {"run", "install"}:
            continue
        if arg in {"--package", "-p", "--from", "--index-url", "--extra-index-url"}:
            skip_next = arg not in {"--package", "-p", "--from"}
            if arg in {"--package", "-p", "--from"}:
                continue
        if arg.startswith("-"):
            continue
        return arg
    return None


def _npm_spec_is_pinned(package: str) -> bool:
    if package.startswith("@"):
        return "@" in package[1:]
    return "@" in package


def _has_broad_auto_approval(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in {"autoapprove", "auto_approve", "auto-approve", "alwaysallow", "allowall", "dangerouslyskippermissions"}:
                if item is True or item == "*" or item == ["*"]:
                    return True
            if key_text in {"approvalmode", "approval_mode", "approval-mode"} and str(item).lower() in {"never", "none", "auto"}:
                return True
            if _has_broad_auto_approval(item):
                return True
    elif isinstance(value, list):
        return any(_has_broad_auto_approval(item) for item in value)
    elif isinstance(value, str):
        return bool(BROAD_AUTO_APPROVAL_RE.search(value))
    return False


def _has_workspace_wide_permissions(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in {"allow", "permissions", "allowedtools", "allowed_tools"}:
                if item == "*" or item == ["*"]:
                    return True
                if isinstance(item, list) and any(_permission_is_workspace_wide(str(entry)) for entry in item):
                    return True
            if key_text in {"workspace", "workspaceaccess", "workspace_access"} and str(item).lower() in {"*", "all", "full"}:
                return True
            if key_text in {"danger-full-access", "danger_full_access", "fullaccess", "full_access"} and item is True:
                return True
            if _has_workspace_wide_permissions(item):
                return True
    elif isinstance(value, list):
        return any(_has_workspace_wide_permissions(item) for item in value)
    elif isinstance(value, str):
        return _permission_is_workspace_wide(value) or bool(WORKSPACE_WIDE_PERMISSION_RE.search(value))
    return False


def _permission_is_workspace_wide(value: str) -> bool:
    compact = value.replace(" ", "").lower()
    return compact in {"*", "read(*)", "write(*)", "bash(*)", "edit(*)", "filesystem(*)"} or "**" in compact
