from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
import json
import re

from .model import DEFAULT_EXCLUDES, Finding


DEFAULT_RECENCY_WINDOW_DAYS = 14
RECENCY_CONFIDENCES = {"strong", "weak", "unknown"}
_CONFIDENCE_RANK = {"unknown": 0, "weak": 1, "strong": 2}
_LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock"}
_WORKFLOW_SUFFIXES = {".yml", ".yaml"}
_CACHE_SCAN_LIMIT = 2000


@dataclass(frozen=True, slots=True)
class InstallSignal:
    observed_at: str
    source: str
    path: str
    confidence: str
    package_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class InstallRecencyFact:
    confidence: str = "unknown"
    last_install_signal_at: str | None = None
    project_last_install_signal_at: str | None = None
    package_last_install_signal_at: str | None = None
    package_name: str | None = None
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = list(self.evidence)
        return data


@dataclass(frozen=True, slots=True)
class InstallRecencyAssessment:
    project: InstallRecencyFact
    packages: dict[str, InstallRecencyFact] = field(default_factory=dict)

    def fact_for_package(self, package_name: str | None) -> InstallRecencyFact:
        if not package_name:
            return self.project
        return self.packages.get(_package_key(package_name), self.project)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project.to_dict(),
            "packages": {key: fact.to_dict() for key, fact in self.packages.items()},
        }


def probe_install_recency(
    repo: Path,
    packages: Iterable[str | None] = (),
    *,
    window_days: int = DEFAULT_RECENCY_WINDOW_DAYS,
    now: datetime | None = None,
    home: Path | None = None,
) -> InstallRecencyAssessment:
    """Inspect local install evidence without invoking package managers."""
    repo = repo.expanduser().resolve()
    resolved_home = (home or Path.home()).expanduser()
    package_names = sorted({_clean_package_name(name) for name in packages if _clean_package_name(name)})
    current_time = _ensure_aware(now or datetime.now(timezone.utc))
    safe_window = max(1, int(window_days or DEFAULT_RECENCY_WINDOW_DAYS))

    project_signals = _project_install_signals(repo)
    package_signals: dict[str, list[InstallSignal]] = {name: [] for name in package_names}
    for package_name in package_names:
        package_signals[package_name].extend(_node_package_signals(repo, package_name))
        package_signals[package_name].extend(_pnpm_package_signals(repo, package_name))
        package_signals[package_name].extend(_python_cache_package_signals(resolved_home, package_name))

    npm_project, npm_packages = _npm_log_signals(resolved_home, repo, package_names)
    project_signals.extend(npm_project)
    for package_name, signals in npm_packages.items():
        package_signals.setdefault(package_name, []).extend(signals)

    all_signals = [*project_signals, *(signal for signals in package_signals.values() for signal in signals)]
    project_fact = _fact_from_signals(
        all_signals,
        package_name=None,
        window_days=safe_window,
        now=current_time,
        project_last=_latest_at(project_signals),
        package_last=None,
    )

    package_facts = {}
    weak_project_signals = [_downgrade_project_signal(signal) for signal in project_signals]
    for package_name in package_names:
        signals = [*package_signals.get(package_name, []), *weak_project_signals]
        package_facts[_package_key(package_name)] = _fact_from_signals(
            signals,
            package_name=package_name,
            window_days=safe_window,
            now=current_time,
            project_last=project_fact.project_last_install_signal_at,
            package_last=_latest_at(package_signals.get(package_name, [])),
        )

    return InstallRecencyAssessment(project=project_fact, packages=package_facts)


def enumerate_rotation_surfaces(repo: Path) -> list[str]:
    """Return repo-local paths that may hold credentials; never return values."""
    repo = repo.expanduser().resolve()
    if not repo.exists():
        return []

    surfaces: set[str] = set()
    for path in _walk_repo_files(repo):
        name = path.name
        relative = _relative_path(path, repo)
        if _is_env_surface(name) or name in {".npmrc", ".pypirc", "mcp.json", "mcp.local.json"}:
            surfaces.add(relative)
            continue
        if _is_project_aws_or_ssh_surface(path, repo):
            surfaces.add(relative)
            continue
        if _is_workflow_file(path, repo) and _file_contains(path, "secrets."):
            surfaces.add(relative)
            continue
        if name == "wrangler.toml" and _file_matches(path, (r"(?m)^\s*\[env(?:\.|\])", r"(?m)^\s*\[vars\]")):
            surfaces.add(relative)
            continue
        if name == "vercel.json" and _file_matches(path, (r'"env"\s*:',)):
            surfaces.add(relative)

    return sorted(surfaces)


def enrich_ioc_findings_with_rotation_advice(
    findings: Iterable[Finding],
    repo: Path,
    *,
    window_days: int = DEFAULT_RECENCY_WINDOW_DAYS,
    home: Path | None = None,
    now: datetime | None = None,
) -> list[Finding]:
    ioc_findings = list(findings)
    if not ioc_findings:
        return []
    packages = [finding.package_name for finding in ioc_findings if finding.package_name]
    assessment = probe_install_recency(repo, packages, window_days=window_days, home=home, now=now)
    surfaces = enumerate_rotation_surfaces(repo)
    surfaces_json = json.dumps(surfaces, sort_keys=True) if surfaces else None

    for finding in ioc_findings:
        fact = assessment.fact_for_package(finding.package_name)
        finding.install_recency_confidence = fact.confidence
        finding.last_install_signal_at = fact.last_install_signal_at
        finding.install_recency_evidence = "; ".join(fact.evidence[:6]) or None
        if fact.confidence == "strong":
            finding.rotation_surfaces_json = surfaces_json
            finding.remediation = _strong_recency_remediation(finding, surfaces)
        elif fact.confidence == "weak":
            finding.rotation_surfaces_json = None
            finding.remediation = _weak_recency_remediation(finding)
        else:
            finding.rotation_surfaces_json = None
            finding.remediation = _unknown_recency_remediation(finding)
    return ioc_findings


def rotation_surfaces_from_json(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return sorted({str(item) for item in value if str(item).strip()})
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return sorted({str(item) for item in parsed if str(item).strip()})


def _project_install_signals(repo: Path) -> list[InstallSignal]:
    signals: list[InstallSignal] = []
    package_lock = repo / "node_modules" / ".package-lock.json"
    if package_lock.exists():
        _append_mtime_signal(signals, package_lock, repo, source="node_modules package lock", confidence="strong")
    for name in _LOCKFILES:
        path = repo / name
        if path.exists():
            _append_mtime_signal(signals, path, repo, source="lockfile mtime", confidence="weak")
    return signals


def _node_package_signals(repo: Path, package_name: str) -> list[InstallSignal]:
    signals: list[InstallSignal] = []
    package_json = _node_package_json(repo, package_name)
    if package_json.exists():
        _append_mtime_signal(
            signals,
            package_json,
            repo,
            source="node_modules package.json",
            confidence="strong",
            package_name=package_name,
        )
    return signals


def _pnpm_package_signals(repo: Path, package_name: str) -> list[InstallSignal]:
    signals: list[InstallSignal] = []
    fragments = _package_fragments(package_name)
    roots = [repo / "node_modules" / ".pnpm", repo / ".pnpm-store"]
    for root in roots:
        if not root.exists():
            continue
        scanned = 0
        for path in _safe_walk(root):
            scanned += 1
            if scanned > _CACHE_SCAN_LIMIT:
                break
            if any(fragment in path.name.casefold() for fragment in fragments):
                _append_mtime_signal(
                    signals,
                    path,
                    repo,
                    source="pnpm store mtime",
                    confidence="strong",
                    package_name=package_name,
                )
                break
    return signals


def _python_cache_package_signals(home: Path, package_name: str) -> list[InstallSignal]:
    package_key = package_name.casefold().replace("_", "-")
    if package_name.startswith("@") or "/" in package_name:
        return []
    signals: list[InstallSignal] = []
    for root in (home / ".cache" / "pip", home / ".cache" / "uv"):
        if not root.exists():
            continue
        scanned = 0
        for path in _safe_walk(root):
            scanned += 1
            if scanned > _CACHE_SCAN_LIMIT:
                break
            text = path.name.casefold().replace("_", "-")
            if package_key in text:
                _append_mtime_signal(
                    signals,
                    path,
                    home,
                    source="python package cache mtime",
                    confidence="strong",
                    package_name=package_name,
                )
                break
    return signals


def _npm_log_signals(
    home: Path,
    repo: Path,
    package_names: list[str],
) -> tuple[list[InstallSignal], dict[str, list[InstallSignal]]]:
    root = home / ".npm" / "_logs"
    if not root.exists():
        return [], {}
    try:
        logs = sorted((path for path in root.iterdir() if path.is_file()), key=lambda path: path.stat().st_mtime, reverse=True)[:100]
    except OSError:
        return [], {}

    project_signals: list[InstallSignal] = []
    package_signals: dict[str, list[InstallSignal]] = {package_name: [] for package_name in package_names}
    repo_terms = {str(repo), repo.name}
    for log in logs:
        try:
            text = log.read_text(encoding="utf-8", errors="replace")[-50_000:]
        except OSError:
            continue
        lowered = text.casefold()
        if any(term and term.casefold() in lowered for term in repo_terms):
            _append_mtime_signal(project_signals, log, home, source="npm install log", confidence="strong")
        for package_name in package_names:
            if any(fragment in lowered for fragment in _package_fragments(package_name)):
                _append_mtime_signal(
                    package_signals.setdefault(package_name, []),
                    log,
                    home,
                    source="npm package log",
                    confidence="strong",
                    package_name=package_name,
                )
    return project_signals, package_signals


def _fact_from_signals(
    signals: list[InstallSignal],
    *,
    package_name: str | None,
    window_days: int,
    now: datetime,
    project_last: str | None,
    package_last: str | None,
) -> InstallRecencyFact:
    last = _latest_at(signals)
    if not signals or not last:
        return InstallRecencyFact(package_name=package_name, project_last_install_signal_at=project_last, package_last_install_signal_at=package_last)

    cutoff = now - timedelta(days=window_days)
    recent = [signal for signal in signals if _parse_time(signal.observed_at) and _parse_time(signal.observed_at) >= cutoff]
    if not recent:
        confidence = "unknown"
        selected = sorted(signals, key=lambda signal: signal.observed_at, reverse=True)[:4]
    else:
        confidence = max((signal.confidence for signal in recent), key=lambda value: _CONFIDENCE_RANK.get(value, 0))
        selected = sorted(recent, key=lambda signal: signal.observed_at, reverse=True)[:6]
    evidence = tuple(_signal_label(signal) for signal in selected)
    return InstallRecencyFact(
        confidence=confidence if confidence in RECENCY_CONFIDENCES else "unknown",
        last_install_signal_at=last,
        project_last_install_signal_at=project_last,
        package_last_install_signal_at=package_last,
        package_name=package_name,
        evidence=evidence,
    )


def _append_mtime_signal(
    signals: list[InstallSignal],
    path: Path,
    root: Path,
    *,
    source: str,
    confidence: str,
    package_name: str | None = None,
) -> None:
    try:
        observed_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return
    signals.append(
        InstallSignal(
            observed_at=observed_at,
            source=source,
            path=_relative_path(path, root),
            confidence=confidence if confidence in RECENCY_CONFIDENCES else "weak",
            package_name=package_name,
        )
    )


def _node_package_json(repo: Path, package_name: str) -> Path:
    parts = [part for part in package_name.split("/") if part]
    return repo.joinpath("node_modules", *parts, "package.json")


def _downgrade_project_signal(signal: InstallSignal) -> InstallSignal:
    return InstallSignal(
        observed_at=signal.observed_at,
        source=signal.source,
        path=signal.path,
        confidence="weak",
        package_name=signal.package_name,
    )


def _latest_at(signals: Iterable[InstallSignal]) -> str | None:
    values = [signal.observed_at for signal in signals if signal.observed_at]
    return max(values) if values else None


def _signal_label(signal: InstallSignal) -> str:
    package = f" for {signal.package_name}" if signal.package_name else ""
    return f"{signal.source}{package} at {signal.path} ({signal.observed_at})"


def _strong_recency_remediation(finding: Finding, surfaces: list[str]) -> str:
    subject = finding.package_name or finding.ioc_indicator or "this IOC match"
    surface_text = ", ".join(surfaces) if surfaces else "no repo-specific credential surfaces were enumerated"
    return (
        f"Probably executed: local install evidence for {subject} is recent. "
        f"Rotate the following surfaces at the provider first, update local config last, and never commit rotated values: {surface_text}."
    )


def _weak_recency_remediation(finding: Finding) -> str:
    subject = finding.package_name or finding.ioc_indicator or "this IOC match"
    return f"Recent execution evidence for {subject} is weak. Verify local install history before deciding whether credential work is needed."


def _unknown_recency_remediation(finding: Finding) -> str:
    subject = finding.package_name or finding.ioc_indicator or "this IOC match"
    return f"No recent local install evidence was found for {subject}. Preserve the IOC match and verify advisory context before changing code."


def _walk_repo_files(repo: Path) -> list[Path]:
    return [path for path in _safe_walk(repo) if path.is_file()]


def _safe_walk(root: Path) -> Iterable[Path]:
    stack = [root]
    while stack:
        path = stack.pop()
        if path.name in DEFAULT_EXCLUDES:
            continue
        try:
            if path.is_dir():
                stack.extend(sorted(path.iterdir(), key=lambda item: item.name.lower(), reverse=True))
                continue
        except OSError:
            continue
        yield path


def _is_env_surface(name: str) -> bool:
    return name == ".env" or name == ".envrc" or name.startswith(".env.")


def _is_project_aws_or_ssh_surface(path: Path, repo: Path) -> bool:
    try:
        parts = path.relative_to(repo).parts
    except ValueError:
        return False
    if ".aws" in parts and path.name in {"credentials", "config"}:
        return True
    if ".ssh" in parts and (path.name == "config" or path.name.startswith("id_")):
        return True
    return False


def _is_workflow_file(path: Path, repo: Path) -> bool:
    try:
        relative = path.relative_to(repo)
    except ValueError:
        return False
    return len(relative.parts) >= 3 and relative.parts[0] == ".github" and relative.parts[1] == "workflows" and path.suffix.lower() in _WORKFLOW_SUFFIXES


def _file_contains(path: Path, needle: str) -> bool:
    try:
        return needle.casefold() in path.read_text(encoding="utf-8", errors="replace").casefold()
    except OSError:
        return False


def _file_matches(path: Path, patterns: tuple[str, ...]) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(re.search(pattern, text) for pattern in patterns)


def _package_fragments(package_name: str) -> set[str]:
    lowered = package_name.casefold()
    return {
        lowered,
        lowered.replace("/", "+"),
        lowered.replace("/", "%2f"),
        lowered.replace("@", ""),
        lowered.replace("@", "").replace("/", "-"),
    }


def _package_key(package_name: str) -> str:
    return package_name.casefold()


def _clean_package_name(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return _ensure_aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
