from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from typing import Any
import shutil


class ToolKind(StrEnum):
    SCANNER = "scanner"
    PLUGIN = "plugin"
    APP = "app"
    MCP_CONNECTOR = "mcp-connector"
    WORKFLOW = "workflow"


class ToolCategory(StrEnum):
    CODE_SECURITY = "code-security"
    SECRETS = "secrets"
    DEPENDENCIES = "dependencies"
    SUPPLY_CHAIN = "supply-chain"
    INFRASTRUCTURE = "infrastructure"
    AI_AGENT = "ai-agent"
    PLATFORM_POSTURE = "platform-posture"
    EXTERNAL_SURFACE = "external-surface"
    DEFENSE_INTEL = "defense-intel"


class ToolLifecycle(StrEnum):
    AVAILABLE = "available"
    BETA = "beta"
    ADVANCED = "advanced"
    COMING_SOON = "coming-soon"
    DEPRECATED = "deprecated"
    HIDDEN = "hidden"


class ToolInstallState(StrEnum):
    BUILT_IN = "built-in"
    MANAGED = "managed"
    DETECTED = "detected"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not-configured"
    COMING_SOON = "coming-soon"


class ToolInstallMethod(StrEnum):
    BUILT_IN = "built-in"
    HOMEBREW = "homebrew"
    UV_TOOL = "uv-tool"
    MANUAL = "manual"
    DOCKER_OPTIONAL = "docker-optional"
    MANAGED_FUTURE = "managed-future"
    NONE = "none"


class ToolInstallOwner(StrEnum):
    DEVSEC = "devsec"
    EXTERNAL = "external"
    USER = "user"
    NOT_APPLICABLE = "not-applicable"


class ToolInstallDetection(StrEnum):
    BUILT_IN = "built-in"
    PATH_BINARY = "path-binary"
    CONFIG_PREFLIGHT = "config-preflight"
    CACHE_PREFLIGHT = "cache-preflight"
    REGISTRY_FUTURE = "registry-future"
    NONE = "none"


class ToolUninstallPosture(StrEnum):
    NOT_NEEDED = "not-needed"
    DEVSEC_MANAGED = "devsec-managed"
    USER_OWNED = "user-owned"
    MANUAL_ONLY = "manual-only"
    NOT_SUPPORTED = "not-supported"


class NetworkAccess(StrEnum):
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"


class ExternalTargets(StrEnum):
    NONE = "none"
    REPO_DERIVED = "repo-derived"
    USER_PROVIDED = "user-provided"


class CredentialUse(StrEnum):
    NONE = "none"
    OPTIONAL = "optional"
    REQUIRED = "required"


class EvidenceType(StrEnum):
    SOURCE_PATTERN = "source-pattern"
    SECRET_MATCH = "secret-match"
    DEPENDENCY_ADVISORY = "dependency-advisory"
    SBOM = "sbom"
    IAC_POLICY = "iac-policy"
    WORKFLOW_POLICY = "workflow-policy"
    INSTALL_HOOK = "install-hook"
    AI_CONFIG = "ai-config"
    PLATFORM_POSTURE = "platform-posture"
    BEHAVIOR_DIFF = "behavior-diff"
    IOC_MATCH = "ioc-match"
    EXTERNAL_OBSERVATION = "external-observation"


class ToolPackId(StrEnum):
    STARTER = "starter"
    SECRETS = "secrets"
    DEPENDENCIES = "dependencies"
    AI_AGENT = "ai-agent"
    IAC = "iac"
    PLATFORM_POSTURE = "platform-posture"
    ADVANCED_DEPENDENCY = "advanced-dependency"
    EXTERNAL_SURFACE = "external-surface"


class ToolPackRole(StrEnum):
    INCLUDED = "included"
    OPTIONAL = "optional"
    COMING_SOON = "coming-soon"


@dataclass(frozen=True, slots=True)
class ToolInstallContract:
    method: ToolInstallMethod
    owner: ToolInstallOwner
    detection: ToolInstallDetection
    binary: str | None = None
    alternate_binaries: tuple[str, ...] = ()
    managed_package: str | None = None
    instructions: str | None = None
    next_step: str | None = None
    uninstall_posture: ToolUninstallPosture = ToolUninstallPosture.USER_OWNED


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    local_only: bool
    writes_files: bool
    network_access: NetworkAccess
    external_targets: ExternalTargets
    uses_credentials: CredentialUse
    destructive_action: bool
    needs_approval: bool
    allowed_for_agent_lab: bool
    stores_results_locally: bool
    sends_source_off_machine: bool
    requires_human_setup: bool
    default_enabled: bool


@dataclass(frozen=True, slots=True)
class ToolCapabilities:
    finding_categories: tuple[str, ...]
    evidence_types: tuple[EvidenceType, ...]
    scan_profiles: tuple[str, ...]
    requires_previous_scan: bool = False
    requires_artifacts: bool = False
    requires_repo_remote: bool = False


@dataclass(frozen=True, slots=True)
class ToolPackMembership:
    pack_id: ToolPackId
    role: ToolPackRole
    default_enabled: bool


@dataclass(frozen=True, slots=True)
class ToolDerivedLabels:
    safety: tuple[str, ...]
    install: tuple[str, ...]
    agent_lab: str


@dataclass(frozen=True, slots=True)
class ToolCatalogEntry:
    id: str
    kind: ToolKind
    label: str
    summary: str
    category: ToolCategory
    lifecycle: ToolLifecycle
    install_state: ToolInstallState
    install: ToolInstallContract
    policy: ToolPolicy
    capabilities: ToolCapabilities
    packs: tuple[ToolPackMembership, ...]
    profiles: tuple[str, ...]
    scanner_key: str | None = None
    legacy_scanner: dict[str, str | bool] | None = None
    description: str | None = None
    docs_path: str | None = "docs/scanners.md"
    homepage_url: str | None = None

    def with_install_state(self, install_state: ToolInstallState) -> ToolCatalogEntry:
        return replace(self, install_state=install_state)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.scanner_key and isinstance(data.get("legacy_scanner"), dict):
            data["legacy_scanner"] = {"scanner": self.scanner_key, **data["legacy_scanner"]}
        data["derived_labels"] = asdict(derive_tool_labels(self))
        return _plain(data)


RUNNABLE_LIFECYCLES = {ToolLifecycle.AVAILABLE, ToolLifecycle.BETA, ToolLifecycle.ADVANCED}
RUNNABLE_INSTALL_STATES = {ToolInstallState.BUILT_IN, ToolInstallState.MANAGED, ToolInstallState.DETECTED}


def tool_catalog_entries(*, detect_install_state: bool = False) -> list[ToolCatalogEntry]:
    entries = list(CURRENT_TOOL_CATALOG)
    if not detect_install_state:
        return entries
    return [entry.with_install_state(detect_install_state_for_tool(entry)) for entry in entries]


def current_tool_catalog(*, detect_install_state: bool = False) -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in tool_catalog_entries(detect_install_state=detect_install_state)]


def scanner_catalog_compat() -> list[dict[str, str | bool]]:
    return [{"scanner": scanner, **metadata} for scanner, metadata in legacy_scanner_catalog_map().items()]


def legacy_scanner_catalog_map() -> dict[str, dict[str, str | bool]]:
    catalog: dict[str, dict[str, str | bool]] = {}
    for entry in CURRENT_SCANNER_CATALOG:
        if not entry.scanner_key or not entry.legacy_scanner:
            continue
        catalog[entry.scanner_key] = dict(entry.legacy_scanner)
    return catalog


def detect_install_state_for_tool(entry: ToolCatalogEntry) -> ToolInstallState:
    if entry.lifecycle == ToolLifecycle.COMING_SOON:
        return ToolInstallState.COMING_SOON
    if entry.install.detection == ToolInstallDetection.BUILT_IN:
        return ToolInstallState.BUILT_IN
    if entry.install.detection == ToolInstallDetection.NONE:
        return entry.install_state

    candidates = tuple(item for item in (entry.install.binary, *entry.install.alternate_binaries) if item)
    if entry.install.detection == ToolInstallDetection.PATH_BINARY and candidates:
        detected = any(shutil.which(binary) for binary in candidates)
        if not detected:
            return ToolInstallState.MISSING
        if entry.policy.requires_human_setup or entry.capabilities.requires_artifacts or entry.capabilities.requires_repo_remote:
            return ToolInstallState.NOT_CONFIGURED
        return ToolInstallState.DETECTED

    return entry.install_state


def derive_tool_labels(entry: ToolCatalogEntry) -> ToolDerivedLabels:
    policy = entry.policy
    safety: list[str] = []
    install: list[str] = []

    if policy.local_only and policy.network_access == NetworkAccess.NONE:
        safety.append("Local")
    elif policy.network_access == NetworkAccess.OPTIONAL:
        safety.append("Optional network")
    elif policy.network_access == NetworkAccess.REQUIRED:
        safety.append("Network required")

    if policy.uses_credentials == CredentialUse.NONE:
        safety.append("No credentials")
    else:
        safety.append("Needs credentials")

    safety.append("Writes files" if policy.writes_files else "Read-only")
    if policy.destructive_action:
        safety.append("Destructive")
    if policy.needs_approval:
        safety.append("Approval required")
    if entry.lifecycle == ToolLifecycle.COMING_SOON or entry.install_state == ToolInstallState.COMING_SOON:
        safety.append("Display only")

    if entry.install_state == ToolInstallState.BUILT_IN:
        install.append("Built in")
    elif entry.install_state == ToolInstallState.MANAGED:
        install.append("Managed")
    elif entry.install_state == ToolInstallState.DETECTED:
        install.append("Detected locally")
    elif entry.install_state == ToolInstallState.MISSING:
        install.append("Missing")
    elif entry.install_state == ToolInstallState.UNAVAILABLE:
        install.append("Unavailable")
    elif entry.install_state == ToolInstallState.NOT_CONFIGURED:
        install.append("Needs setup")
    elif entry.install_state == ToolInstallState.COMING_SOON:
        install.append("Coming soon")

    if entry.install.owner == ToolInstallOwner.DEVSEC:
        install.append("DevSec managed")

    agent_lab = (
        "Agent Lab allowed"
        if policy.allowed_for_agent_lab and entry.lifecycle in RUNNABLE_LIFECYCLES and entry.install_state in RUNNABLE_INSTALL_STATES
        else "Agent Lab blocked"
    )
    return ToolDerivedLabels(safety=tuple(safety), install=tuple(install), agent_lab=agent_lab)


def _plain(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items() if item is not None}
    return value


def _profiles(profile: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in profile.split(",") if part.strip())


def _legacy(
    *,
    label: str,
    area: str,
    covers: str,
    profile: str,
    install: str,
    next_step: str,
    built_in: bool,
) -> dict[str, str | bool]:
    return {
        "label": label,
        "area": area,
        "covers": covers,
        "profile": profile,
        "install": install,
        "next_step": next_step,
        "built_in": built_in,
    }


def _built_in_install(instructions: str, next_step: str) -> ToolInstallContract:
    return ToolInstallContract(
        method=ToolInstallMethod.BUILT_IN,
        owner=ToolInstallOwner.DEVSEC,
        detection=ToolInstallDetection.BUILT_IN,
        instructions=instructions,
        next_step=next_step,
        uninstall_posture=ToolUninstallPosture.NOT_NEEDED,
    )


def _path_install(
    *,
    method: ToolInstallMethod,
    binary: str,
    instructions: str,
    next_step: str,
    uninstall_posture: ToolUninstallPosture = ToolUninstallPosture.USER_OWNED,
    alternate_binaries: tuple[str, ...] = (),
) -> ToolInstallContract:
    return ToolInstallContract(
        method=method,
        owner=ToolInstallOwner.USER,
        detection=ToolInstallDetection.PATH_BINARY,
        binary=binary,
        alternate_binaries=alternate_binaries,
        instructions=instructions,
        next_step=next_step,
        uninstall_posture=uninstall_posture,
    )


def _policy(
    *,
    local_only: bool,
    network_access: NetworkAccess,
    external_targets: ExternalTargets = ExternalTargets.NONE,
    uses_credentials: CredentialUse = CredentialUse.NONE,
    needs_approval: bool,
    allowed_for_agent_lab: bool,
    requires_human_setup: bool,
    default_enabled: bool,
) -> ToolPolicy:
    return ToolPolicy(
        local_only=local_only,
        writes_files=False,
        network_access=network_access,
        external_targets=external_targets,
        uses_credentials=uses_credentials,
        destructive_action=False,
        needs_approval=needs_approval,
        allowed_for_agent_lab=allowed_for_agent_lab,
        stores_results_locally=True,
        sends_source_off_machine=False,
        requires_human_setup=requires_human_setup,
        default_enabled=default_enabled,
    )


def _pack(pack_id: ToolPackId, role: ToolPackRole, default_enabled: bool) -> ToolPackMembership:
    return ToolPackMembership(pack_id=pack_id, role=role, default_enabled=default_enabled)


def _scanner_entry(
    *,
    scanner: str,
    label: str,
    area: str,
    covers: str,
    profile: str,
    install_text: str,
    next_step: str,
    built_in: bool,
    category: ToolCategory,
    lifecycle: ToolLifecycle,
    install_state: ToolInstallState,
    install: ToolInstallContract,
    policy: ToolPolicy,
    capabilities: ToolCapabilities,
    packs: tuple[ToolPackMembership, ...],
) -> ToolCatalogEntry:
    legacy = _legacy(
        label=label,
        area=area,
        covers=covers,
        profile=profile,
        install=install_text,
        next_step=next_step,
        built_in=built_in,
    )
    return ToolCatalogEntry(
        id=scanner,
        kind=ToolKind.SCANNER,
        label=label,
        summary=covers,
        category=category,
        lifecycle=lifecycle,
        install_state=install_state,
        install=install,
        policy=policy,
        capabilities=capabilities,
        packs=packs,
        profiles=_profiles(profile),
        scanner_key=scanner,
        legacy_scanner=legacy,
    )


EXTERNAL_SURFACE_PLACEHOLDER = ToolCatalogEntry(
    id="external-surface",
    kind=ToolKind.WORKFLOW,
    label="External Surface",
    summary="Coming Soon placeholder for safe, approval-gated checks of user-provided external targets.",
    description=(
        "Display-only MVP entry for future external surface monitoring. "
        "DëvSec does not collect targets, probe domains, or run external reconnaissance yet."
    ),
    category=ToolCategory.EXTERNAL_SURFACE,
    lifecycle=ToolLifecycle.COMING_SOON,
    install_state=ToolInstallState.COMING_SOON,
    install=ToolInstallContract(
        method=ToolInstallMethod.NONE,
        owner=ToolInstallOwner.NOT_APPLICABLE,
        detection=ToolInstallDetection.NONE,
        instructions="Coming Soon. No install action is available.",
        next_step="No run action is available in the MVP.",
        uninstall_posture=ToolUninstallPosture.NOT_SUPPORTED,
    ),
    policy=ToolPolicy(
        local_only=False,
        writes_files=False,
        network_access=NetworkAccess.REQUIRED,
        external_targets=ExternalTargets.USER_PROVIDED,
        uses_credentials=CredentialUse.NONE,
        destructive_action=False,
        needs_approval=True,
        allowed_for_agent_lab=False,
        stores_results_locally=True,
        sends_source_off_machine=False,
        requires_human_setup=False,
        default_enabled=False,
    ),
    capabilities=ToolCapabilities(
        finding_categories=("external-surface",),
        evidence_types=(EvidenceType.EXTERNAL_OBSERVATION,),
        scan_profiles=(),
    ),
    packs=(_pack(ToolPackId.EXTERNAL_SURFACE, ToolPackRole.COMING_SOON, False),),
    profiles=(),
    docs_path="docs/tool-catalog.md",
)


CURRENT_SCANNER_CATALOG: tuple[ToolCatalogEntry, ...] = (
    _scanner_entry(
        scanner="ioc-watch",
        label="IOC Watch",
        area="Named-campaign defense",
        covers="Local IOC packs matched against saved SBOM components, namespace watches, and known campaign domains.",
        profile="default, deps, full, ioc",
        install_text="Built in. No install needed.",
        next_step="Run security-scan ioc after an SBOM-backed dependency scan.",
        built_in=True,
        category=ToolCategory.DEFENSE_INTEL,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.BUILT_IN,
        install=_built_in_install("Built in. No install needed.", "Run security-scan ioc after an SBOM-backed dependency scan."),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=True,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("supply-chain-ioc",),
            evidence_types=(EvidenceType.IOC_MATCH,),
            scan_profiles=("default", "deps", "full", "ioc"),
            requires_previous_scan=True,
            requires_artifacts=True,
        ),
        packs=(
            _pack(ToolPackId.STARTER, ToolPackRole.OPTIONAL, False),
            _pack(ToolPackId.DEPENDENCIES, ToolPackRole.OPTIONAL, False),
        ),
    ),
    _scanner_entry(
        scanner="install-hooks",
        label="Install hook classifier",
        area="Supply-chain surfaces",
        covers="Package install scripts and Python build hooks classified by install-time execution risk.",
        profile="default, quick, deps, full",
        install_text="Built in. No install needed.",
        next_step="Run a default, quick, dependency, or full scan to include install-hook classification.",
        built_in=True,
        category=ToolCategory.SUPPLY_CHAIN,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.BUILT_IN,
        install=_built_in_install("Built in. No install needed.", "Run a default, quick, dependency, or full scan to include install-hook classification."),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=True,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("supply-chain", "install-hooks"),
            evidence_types=(EvidenceType.INSTALL_HOOK,),
            scan_profiles=("default", "quick", "deps", "full"),
        ),
        packs=(
            _pack(ToolPackId.STARTER, ToolPackRole.INCLUDED, True),
            _pack(ToolPackId.DEPENDENCIES, ToolPackRole.OPTIONAL, False),
        ),
    ),
    _scanner_entry(
        scanner="workflow-audit",
        label="Workflow surface audit",
        area="Supply-chain surfaces",
        covers="GitHub Actions pins, fetch-and-exec patterns, secret handling, token permissions, and pull_request_target risk.",
        profile="default, quick, iac, full",
        install_text="Built in. No install needed.",
        next_step="Run a default, quick, IaC, or full scan to include workflow surface findings.",
        built_in=True,
        category=ToolCategory.SUPPLY_CHAIN,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.BUILT_IN,
        install=_built_in_install("Built in. No install needed.", "Run a default, quick, IaC, or full scan to include workflow surface findings."),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=True,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("supply-chain", "workflow"),
            evidence_types=(EvidenceType.WORKFLOW_POLICY,),
            scan_profiles=("default", "quick", "iac", "full"),
        ),
        packs=(
            _pack(ToolPackId.STARTER, ToolPackRole.INCLUDED, True),
            _pack(ToolPackId.IAC, ToolPackRole.COMING_SOON, False),
        ),
    ),
    _scanner_entry(
        scanner="ai-static",
        label="Built-in AI static checks",
        area="AI agent/MCP",
        covers="Prompt files, MCP configs, agent-readable instructions, and risky local tool setup.",
        profile="quick, ai, full",
        install_text="Built in. No install needed.",
        next_step="Run a quick or AI scan to include this check.",
        built_in=True,
        category=ToolCategory.AI_AGENT,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.BUILT_IN,
        install=_built_in_install("Built in. No install needed.", "Run a quick or AI scan to include this check."),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=True,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("ai-risk", "mcp"),
            evidence_types=(EvidenceType.AI_CONFIG, EvidenceType.SOURCE_PATTERN),
            scan_profiles=("quick", "ai", "full"),
        ),
        packs=(
            _pack(ToolPackId.STARTER, ToolPackRole.INCLUDED, True),
            _pack(ToolPackId.AI_AGENT, ToolPackRole.INCLUDED, True),
        ),
    ),
    _scanner_entry(
        scanner="semgrep",
        label="Semgrep",
        area="Code security",
        covers="Code vulnerability patterns such as injection, unsafe parsing, and insecure defaults.",
        profile="quick, code, full",
        install_text="./install-security-observatory.sh or brew install semgrep",
        next_step="Install Semgrep, then rerun the code or quick scan.",
        built_in=False,
        category=ToolCategory.CODE_SECURITY,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="semgrep",
            instructions="./install-security-observatory.sh or brew install semgrep",
            next_step="Install Semgrep, then rerun the code or quick scan.",
        ),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=True,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("code-security",),
            evidence_types=(EvidenceType.SOURCE_PATTERN,),
            scan_profiles=("quick", "code", "full"),
        ),
        packs=(_pack(ToolPackId.STARTER, ToolPackRole.INCLUDED, True),),
    ),
    _scanner_entry(
        scanner="gitleaks",
        label="Gitleaks",
        area="Secrets",
        covers="Fast detection of exposed API keys, tokens, passwords, and private keys.",
        profile="quick, secrets, full",
        install_text="./install-security-observatory.sh or brew install gitleaks",
        next_step="Install Gitleaks, then rerun the secrets or quick scan.",
        built_in=False,
        category=ToolCategory.SECRETS,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="gitleaks",
            instructions="./install-security-observatory.sh or brew install gitleaks",
            next_step="Install Gitleaks, then rerun the secrets or quick scan.",
        ),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=True,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("secrets",),
            evidence_types=(EvidenceType.SECRET_MATCH,),
            scan_profiles=("quick", "secrets", "full"),
        ),
        packs=(
            _pack(ToolPackId.STARTER, ToolPackRole.INCLUDED, True),
            _pack(ToolPackId.SECRETS, ToolPackRole.INCLUDED, True),
        ),
    ),
    _scanner_entry(
        scanner="trufflehog",
        label="TruffleHog",
        area="Secrets",
        covers="Deeper second-opinion secret detection.",
        profile="secrets, full",
        install_text="./install-security-observatory.sh or brew install trufflehog",
        next_step="Install TruffleHog, then rerun the secrets or full scan.",
        built_in=False,
        category=ToolCategory.SECRETS,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="trufflehog",
            instructions="./install-security-observatory.sh or brew install trufflehog",
            next_step="Install TruffleHog, then rerun the secrets or full scan.",
        ),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=False,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("secrets",),
            evidence_types=(EvidenceType.SECRET_MATCH,),
            scan_profiles=("secrets", "full"),
        ),
        packs=(_pack(ToolPackId.SECRETS, ToolPackRole.INCLUDED, False),),
    ),
    _scanner_entry(
        scanner="trivy",
        label="Trivy",
        area="Dependencies / IaC",
        covers="Filesystem, dependency, secret, and infrastructure misconfiguration checks.",
        profile="deps, secrets, iac, full",
        install_text="./install-security-observatory.sh or brew install trivy",
        next_step="Install Trivy, then rerun the dependency, secrets, IaC, or full scan.",
        built_in=False,
        category=ToolCategory.DEPENDENCIES,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="trivy",
            instructions="./install-security-observatory.sh or brew install trivy",
            next_step="Install Trivy, then rerun the dependency, secrets, IaC, or full scan.",
        ),
        policy=_policy(
            local_only=False,
            network_access=NetworkAccess.OPTIONAL,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=True,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("dependencies", "secrets", "iac"),
            evidence_types=(EvidenceType.DEPENDENCY_ADVISORY, EvidenceType.SECRET_MATCH, EvidenceType.IAC_POLICY),
            scan_profiles=("deps", "secrets", "iac", "full"),
        ),
        packs=(
            _pack(ToolPackId.DEPENDENCIES, ToolPackRole.INCLUDED, True),
            _pack(ToolPackId.SECRETS, ToolPackRole.OPTIONAL, False),
            _pack(ToolPackId.IAC, ToolPackRole.COMING_SOON, False),
        ),
    ),
    _scanner_entry(
        scanner="osv-scanner",
        label="OSV-Scanner",
        area="Dependencies / SBOM",
        covers="Open-source dependency vulnerabilities from OSV advisories.",
        profile="quick, deps, full",
        install_text="./install-security-observatory.sh or brew install osv-scanner",
        next_step="Install OSV-Scanner, then rerun the dependency or quick scan.",
        built_in=False,
        category=ToolCategory.DEPENDENCIES,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="osv-scanner",
            instructions="./install-security-observatory.sh or brew install osv-scanner",
            next_step="Install OSV-Scanner, then rerun the dependency or quick scan.",
        ),
        policy=_policy(
            local_only=False,
            network_access=NetworkAccess.REQUIRED,
            needs_approval=True,
            allowed_for_agent_lab=False,
            requires_human_setup=False,
            default_enabled=True,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("dependencies",),
            evidence_types=(EvidenceType.DEPENDENCY_ADVISORY,),
            scan_profiles=("quick", "deps", "full"),
        ),
        packs=(
            _pack(ToolPackId.DEPENDENCIES, ToolPackRole.INCLUDED, True),
            _pack(ToolPackId.STARTER, ToolPackRole.OPTIONAL, False),
        ),
    ),
    _scanner_entry(
        scanner="syft",
        label="Syft",
        area="Dependencies / SBOM",
        covers="Software bill of materials generation.",
        profile="deps, full",
        install_text="./install-security-observatory.sh or brew install syft",
        next_step="Install Syft, then rerun the dependency or full scan.",
        built_in=False,
        category=ToolCategory.DEPENDENCIES,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="syft",
            instructions="./install-security-observatory.sh or brew install syft",
            next_step="Install Syft, then rerun the dependency or full scan.",
        ),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=True,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("dependencies", "sbom"),
            evidence_types=(EvidenceType.SBOM,),
            scan_profiles=("deps", "full"),
        ),
        packs=(_pack(ToolPackId.DEPENDENCIES, ToolPackRole.INCLUDED, True),),
    ),
    _scanner_entry(
        scanner="grype",
        label="Grype",
        area="Dependencies / SBOM",
        covers="Dependency vulnerability scanning from an SBOM or repository filesystem.",
        profile="deps, full",
        install_text="./install-security-observatory.sh or brew install grype",
        next_step="Install Grype, then rerun the dependency or full scan.",
        built_in=False,
        category=ToolCategory.DEPENDENCIES,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="grype",
            instructions="./install-security-observatory.sh or brew install grype",
            next_step="Install Grype, then rerun the dependency or full scan.",
        ),
        policy=_policy(
            local_only=False,
            network_access=NetworkAccess.OPTIONAL,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=True,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("dependencies",),
            evidence_types=(EvidenceType.DEPENDENCY_ADVISORY,),
            scan_profiles=("deps", "full"),
            requires_previous_scan=True,
        ),
        packs=(_pack(ToolPackId.DEPENDENCIES, ToolPackRole.INCLUDED, True),),
    ),
    _scanner_entry(
        scanner="checkov",
        label="Checkov",
        area="Infrastructure",
        covers="Terraform, Kubernetes, and cloud configuration policy checks.",
        profile="iac, full",
        install_text="./install-security-observatory.sh or uv tool install checkov",
        next_step="Install Checkov, then rerun the IaC or full scan.",
        built_in=False,
        category=ToolCategory.INFRASTRUCTURE,
        lifecycle=ToolLifecycle.ADVANCED,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.UV_TOOL,
            binary="checkov",
            instructions="./install-security-observatory.sh or uv tool install checkov",
            next_step="Install Checkov, then rerun the IaC or full scan.",
        ),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=False,
            allowed_for_agent_lab=False,
            requires_human_setup=False,
            default_enabled=False,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("iac", "infrastructure"),
            evidence_types=(EvidenceType.IAC_POLICY,),
            scan_profiles=("iac", "full"),
        ),
        packs=(_pack(ToolPackId.IAC, ToolPackRole.COMING_SOON, False),),
    ),
    _scanner_entry(
        scanner="medusa",
        label="Medusa",
        area="AI agent/MCP",
        covers="MCP, prompt injection, AI editor config, and repo-poisoning checks.",
        profile="ai, full",
        install_text="./install-security-observatory.sh or uv tool install medusa-security",
        next_step="Install Medusa, then rerun the AI or full scan.",
        built_in=False,
        category=ToolCategory.AI_AGENT,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.UV_TOOL,
            binary="medusa",
            instructions="./install-security-observatory.sh or uv tool install medusa-security",
            next_step="Install Medusa, then rerun the AI or full scan.",
        ),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=False,
            allowed_for_agent_lab=True,
            requires_human_setup=False,
            default_enabled=False,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("ai-risk", "mcp"),
            evidence_types=(EvidenceType.AI_CONFIG, EvidenceType.SOURCE_PATTERN),
            scan_profiles=("ai", "full"),
        ),
        packs=(_pack(ToolPackId.AI_AGENT, ToolPackRole.INCLUDED, False),),
    ),
    _scanner_entry(
        scanner="malcontent",
        label="malcontent",
        area="Behavioral drift",
        covers="Advanced diffing of old and new dependency artifacts for suspicious behavior changes.",
        profile="behavioral-drift",
        install_text="Install malcontent separately, then provide local package artifacts under the behavioral artifact cache.",
        next_step="Run security-scan --behavioral-drift after at least two SBOM-backed dependency scans.",
        built_in=False,
        category=ToolCategory.DEPENDENCIES,
        lifecycle=ToolLifecycle.ADVANCED,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.MANUAL,
            binary="malcontent",
            alternate_binaries=("mal",),
            instructions="Install malcontent separately, then provide local package artifacts under the behavioral artifact cache.",
            next_step="Run security-scan --behavioral-drift after at least two SBOM-backed dependency scans.",
            uninstall_posture=ToolUninstallPosture.MANUAL_ONLY,
        ),
        policy=_policy(
            local_only=True,
            network_access=NetworkAccess.NONE,
            needs_approval=True,
            allowed_for_agent_lab=False,
            requires_human_setup=True,
            default_enabled=False,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("behavioral-drift", "dependencies"),
            evidence_types=(EvidenceType.BEHAVIOR_DIFF,),
            scan_profiles=("behavioral-drift",),
            requires_previous_scan=True,
            requires_artifacts=True,
        ),
        packs=(_pack(ToolPackId.ADVANCED_DEPENDENCY, ToolPackRole.COMING_SOON, False),),
    ),
    _scanner_entry(
        scanner="legitify",
        label="legitify",
        area="Platform posture",
        covers="Optional connected checks for repository branch protection, Actions permissions, webhooks, and SCM settings.",
        profile="platform-posture",
        install_text="brew install legitify, then set SCM_TOKEN for the platform posture profile.",
        next_step="Run security-scan --platform-posture only when you want a token-backed platform check.",
        built_in=False,
        category=ToolCategory.PLATFORM_POSTURE,
        lifecycle=ToolLifecycle.ADVANCED,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="legitify",
            instructions="brew install legitify, then set SCM_TOKEN for the platform posture profile.",
            next_step="Run security-scan --platform-posture only when you want a token-backed platform check.",
            uninstall_posture=ToolUninstallPosture.MANUAL_ONLY,
        ),
        policy=_policy(
            local_only=False,
            network_access=NetworkAccess.REQUIRED,
            external_targets=ExternalTargets.REPO_DERIVED,
            uses_credentials=CredentialUse.REQUIRED,
            needs_approval=True,
            allowed_for_agent_lab=False,
            requires_human_setup=True,
            default_enabled=False,
        ),
        capabilities=ToolCapabilities(
            finding_categories=("platform-posture", "scm"),
            evidence_types=(EvidenceType.PLATFORM_POSTURE, EvidenceType.WORKFLOW_POLICY),
            scan_profiles=("platform-posture",),
            requires_repo_remote=True,
        ),
        packs=(_pack(ToolPackId.PLATFORM_POSTURE, ToolPackRole.COMING_SOON, False),),
    ),
)

CURRENT_TOOL_CATALOG: tuple[ToolCatalogEntry, ...] = (*CURRENT_SCANNER_CATALOG, EXTERNAL_SURFACE_PLACEHOLDER)
