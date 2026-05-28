from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import re


SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
FAIL_LEVELS = {"low": 1, "medium": 2, "high": 3, "critical": 4}

DEFAULT_EXCLUDES = (
    ".git",
    ".claude",
    ".codex",
    ".vercel",
    ".turbo",
    ".cache",
    "node_modules",
    "dist",
    "build",
    ".next",
    "out",
    "coverage",
    "venv",
    ".venv",
    "vendor",
    "target",
    "tmp",
    "temp",
    "logs",
    "__generated__",
)

SECRET_KEY_RE = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|access[_-]?key|api[_-]?key|credential|auth)",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(
    r"(?i)\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|[A-Za-z0-9_=-]{32,})\b"
)


@dataclass(slots=True)
class Finding:
    repo: str
    scanner: str
    severity: str
    category: str
    title: str
    file: str | None = None
    line: int | None = None
    remediation: str | None = None
    vulnerability_id: str | None = None
    package_name: str | None = None
    package_version: str | None = None
    package_ecosystem: str | None = None
    package_url: str | None = None
    fixed_version: str | None = None
    component_fingerprint: str | None = None
    component_package_key: str | None = None
    component_match_confidence: str | None = None
    component_match_reason: str | None = None
    old_version: str | None = None
    new_version: str | None = None
    behavior_category: str | None = None
    evidence_summary: str | None = None
    before_behavior: str | None = None
    after_behavior: str | None = None
    ioc_pack_id: str | None = None
    ioc_source: str | None = None
    ioc_advisory_url: str | None = None
    ioc_confidence: str | None = None
    ioc_match_type: str | None = None
    ioc_indicator: str | None = None
    install_recency_confidence: str | None = None
    last_install_signal_at: str | None = None
    install_recency_evidence: str | None = None
    rotation_surfaces_json: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    fingerprint: str | None = None

    def __post_init__(self) -> None:
        self.severity = normalize_severity(self.severity)
        self.title = redact_text(self.title or "Untitled finding")
        if self.remediation:
            self.remediation = redact_text(self.remediation)
        for field_name in (
            "vulnerability_id",
            "package_name",
            "package_version",
            "package_ecosystem",
            "package_url",
            "fixed_version",
            "component_fingerprint",
            "component_package_key",
            "component_match_confidence",
            "component_match_reason",
            "old_version",
            "new_version",
            "behavior_category",
            "evidence_summary",
            "before_behavior",
            "after_behavior",
            "ioc_pack_id",
            "ioc_source",
            "ioc_advisory_url",
            "ioc_confidence",
            "ioc_match_type",
            "ioc_indicator",
            "install_recency_confidence",
            "last_install_signal_at",
            "install_recency_evidence",
            "rotation_surfaces_json",
        ):
            value = getattr(self, field_name)
            if value:
                setattr(self, field_name, redact_text(value))
        if not self.fingerprint:
            key = "|".join(
                [
                    self.repo,
                    self.scanner,
                    self.severity,
                    self.category,
                    self.title,
                    self.file or "",
                    str(self.line or ""),
                ]
            )
            self.fingerprint = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SecurityCase:
    case_id: str
    title: str
    plain_english_risk: str
    action_level: str
    confidence: str
    category: str
    severity: str
    affected_files: list[str]
    evidence: list[dict[str, Any]]
    scanners: list[str]
    fix_steps: list[str]
    agent_prompt: str
    source_fingerprints: list[str]
    priority_reasons: list[str] = field(default_factory=list)
    install_recency: dict[str, Any] | None = None
    rotation_surfaces: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = redact_text(self.title or "Security case")
        self.plain_english_risk = redact_text(self.plain_english_risk or "")
        self.action_level = self.action_level if self.action_level in {"fix_now", "verify", "watch", "info"} else "verify"
        self.confidence = self.confidence if self.confidence in {"high", "medium", "low"} else "medium"
        self.category = self.category or "unknown"
        self.severity = normalize_severity(self.severity)
        self.affected_files = [redact_text(item) for item in self.affected_files if item]
        self.evidence = sanitize_json(self.evidence)
        self.scanners = sorted({scanner for scanner in self.scanners if scanner})
        self.fix_steps = [redact_text(step) for step in self.fix_steps if step]
        self.agent_prompt = redact_text(self.agent_prompt or "")
        self.source_fingerprints = sorted({fingerprint for fingerprint in self.source_fingerprints if fingerprint})
        self.priority_reasons = [redact_text(reason) for reason in self.priority_reasons if reason]
        self.install_recency = sanitize_json(self.install_recency) if isinstance(self.install_recency, dict) else None
        self.rotation_surfaces = sorted({redact_text(item) for item in self.rotation_surfaces if item})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScannerStatus:
    scanner: str
    available: bool
    command: list[str]
    started_at: str
    status: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    duration_seconds: float | None = None
    findings: int = 0
    raw_report: str | None = None
    sarif_report: str | None = None
    sbom_report: str | None = None
    error: str | None = None
    proof_level: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data.get("error"):
            data["error"] = redact_text(data["error"])
        return data


def normalize_severity(value: Any) -> str:
    if value is None:
        return "medium"
    text = str(value).strip().lower()
    aliases = {
        "error": "high",
        "warning": "medium",
        "warn": "medium",
        "note": "info",
        "negligible": "info",
        "unknown": "medium",
        "moderate": "medium",
    }
    return aliases.get(text, text if text in SEVERITY_ORDER else "medium")


def utc_now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slugify(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return safe or "repo"


def redact_text(value: str) -> str:
    return TOKEN_RE.sub("[REDACTED]", value)


def sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if SECRET_KEY_RE.search(str(key)):
                clean[key] = "[REDACTED]"
            else:
                clean[key] = sanitize_json(item)
        return clean
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def read_json_safely(path: Path) -> Any:
    if not path.exists() or path.stat().st_size == 0:
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                items.append({"message": redact_text(line)})
        return items


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_json(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def score_findings(findings: list[Finding], sbom_created: bool = False) -> int:
    seen: set[str] = set()
    penalties = {
        "secrets": 0.0,
        "ai-risk": 0.0,
        "critical": 0.0,
        "high": 0.0,
        "medium": 0.0,
        "low": 0.0,
    }
    for finding in findings:
        if finding.fingerprint in seen:
            continue
        seen.add(finding.fingerprint or "")
        if finding.category == "secrets":
            penalties["secrets"] += 40
        elif finding.category == "ai-risk":
            penalties["ai-risk"] += 15
        elif finding.severity == "critical":
            penalties["critical"] += 25
        elif finding.severity == "high":
            penalties["high"] += 10
        elif finding.severity == "medium":
            penalties["medium"] += 2
        elif finding.severity == "low":
            penalties["low"] += 0.5
    capped_penalty = (
        min(penalties["secrets"], 80)
        + min(penalties["ai-risk"], 45)
        + penalties["critical"]
        + min(penalties["high"], 60)
        + min(penalties["medium"], 25)
        + min(penalties["low"], 10)
    )
    if not sbom_created:
        capped_penalty += 3
    return max(0, min(100, round(100 - capped_penalty)))


def severity_counts(findings: list[Finding]) -> dict[str, int]:
    counts = {name: 0 for name in ("critical", "high", "medium", "low", "info")}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts
