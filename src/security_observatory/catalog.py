from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from typing import Any, Iterable
import shutil

from .managed_tools import ManagedToolEvidence, build_tool_install_preview, managed_tool_evidence_by_tool
from .tool_config import read_tool_config


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


class SetupKind(StrEnum):
    NONE = "none"
    ENV_VAR = "env-var"
    API_KEY = "api-key"
    OAUTH = "oauth"
    FILE_PATH = "file-path"
    CONFIG_BLOCK = "config-block"


class SetupProbeKind(StrEnum):
    SHELL = "shell"
    HTTP = "http"
    BINARY_VERSION = "binary-version"
    DIRECTORY_EXISTS = "directory-exists"


@dataclass(frozen=True, slots=True)
class SetupProbe:
    kind: SetupProbeKind
    spec: dict[str, str]


# DëvSec's own accent — used by built-in scanners and any tool without a
# vetted upstream brand color. Matches ``--mist-surface-700`` in
# ``dashboard-ui/src/index.css``, the existing chrome accent. Keeping it as
# a string here (rather than reaching for a token) keeps catalog.py free of
# UI-layer dependencies.
DEVSEC_ACCENT = "#3c4b48"


@dataclass(frozen=True, slots=True)
class ToolBranding:
    # Hex color sampled from the tool's wordmark, used as a 4px stripe on the
    # left edge of catalog cards and a 1px underline beneath the tool name on
    # the detail page. Discipline (docs/branding.md): logo + one accent only.
    # No background, font, or shape changes. Tools without a vetted upstream
    # mark fall back to the DëvSec neutral accent.
    accent_color: str
    # Filename under ``dashboard-ui/public/tool-logos/`` (e.g.
    # ``semgrep.svg``). ``None`` falls back to the category icon.
    logo: str | None = None


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
    docs_path: str | None = None
    homepage_url: str | None = None
    setup_kind: SetupKind = SetupKind.NONE
    setup_requirement: str | None = None
    setup_probe: SetupProbe | None = None
    # Provider deep-link rendered as "Generate a token →" in the SetupCard's
    # api-key branch. Keep scopes + description preselected in the URL so the
    # user lands on a pre-filled token page (e.g.
    # ``https://github.com/settings/tokens/new?scopes=repo,admin:repo_hook&description=...``).
    # ``None`` hides the link.
    setup_token_create_url: str | None = None
    branding: ToolBranding = ToolBranding(accent_color=DEVSEC_ACCENT)

    def with_install_state(self, install_state: ToolInstallState) -> ToolCatalogEntry:
        return replace(self, install_state=install_state)

    def with_runtime_install(
        self,
        install_state: ToolInstallState,
        *,
        owner: ToolInstallOwner | None = None,
        method: ToolInstallMethod | None = None,
        uninstall_posture: ToolUninstallPosture | None = None,
        managed_package: str | None = None,
    ) -> ToolCatalogEntry:
        install = replace(
            self.install,
            owner=owner or self.install.owner,
            method=method or self.install.method,
            uninstall_posture=uninstall_posture or self.install.uninstall_posture,
            managed_package=managed_package or self.install.managed_package,
        )
        return replace(self, install_state=install_state, install=install)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.scanner_key and isinstance(data.get("legacy_scanner"), dict):
            data["legacy_scanner"] = {"scanner": self.scanner_key, **data["legacy_scanner"]}
        data["derived_labels"] = asdict(derive_tool_labels(self))
        return _plain(data)


@dataclass(frozen=True, slots=True)
class SecurityPackDefinition:
    id: ToolPackId
    label: str
    summary: str
    mvp_state: str
    visibility: str
    primary_profile: str | None
    secondary_profiles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScanProfileDefinition:
    id: str
    label: str
    command: str
    summary: str
    scanner_keys: tuple[str, ...]
    primary_pack_ids: tuple[ToolPackId, ...] = ()
    supporting_pack_ids: tuple[ToolPackId, ...] = ()
    notes: tuple[str, ...] = ()


RUNNABLE_LIFECYCLES = {ToolLifecycle.AVAILABLE, ToolLifecycle.BETA, ToolLifecycle.ADVANCED}
RUNNABLE_INSTALL_STATES = {ToolInstallState.BUILT_IN, ToolInstallState.MANAGED, ToolInstallState.DETECTED}
SECURITY_PACK_DEFINITIONS: tuple[SecurityPackDefinition, ...] = (
    SecurityPackDefinition(
        id=ToolPackId.STARTER,
        label="Starter Pack",
        summary="Fast honest baseline across code, secrets, workflow, install-hook, and AI-agent risk.",
        mvp_state="real",
        visibility="default",
        primary_profile="quick",
        secondary_profiles=("default", "code", "secrets"),
    ),
    SecurityPackDefinition(
        id=ToolPackId.SECRETS,
        label="Secrets Pack",
        summary="Focused checks for exposed keys, tokens, passwords, and secret-like evidence.",
        mvp_state="real",
        visibility="default",
        primary_profile="secrets",
        secondary_profiles=("quick", "secrets+deps"),
    ),
    SecurityPackDefinition(
        id=ToolPackId.DEPENDENCIES,
        label="Dependencies Pack",
        summary="SBOM inventory, dependency advisory evidence, and named-campaign IOC context.",
        mvp_state="real",
        visibility="default",
        primary_profile="deps",
        secondary_profiles=("deps+trust-cache-only", "deps+trust"),
    ),
    SecurityPackDefinition(
        id=ToolPackId.AI_AGENT,
        label="AI Agent Pack",
        summary="Agent-readable files, MCP configuration, prompt-injection surfaces, and AI editor setup.",
        mvp_state="real",
        visibility="default",
        primary_profile="ai",
        secondary_profiles=("quick", "full"),
    ),
    SecurityPackDefinition(
        id=ToolPackId.IAC,
        label="IaC Pack",
        summary="Coming Soon bundle for Terraform, Kubernetes, GitHub Actions, and configuration-policy checks.",
        mvp_state="coming-soon",
        visibility="default-coming-soon",
        primary_profile=None,
    ),
    SecurityPackDefinition(
        id=ToolPackId.EXTERNAL_SURFACE,
        label="External Surface Pack",
        summary="Display-only Coming Soon placeholder for future approval-gated checks of external targets.",
        mvp_state="coming-soon",
        visibility="default-coming-soon",
        primary_profile=None,
    ),
    SecurityPackDefinition(
        id=ToolPackId.PLATFORM_POSTURE,
        label="Platform Posture Pack",
        summary="Advanced Coming Soon bundle for token-backed SCM and hosting posture checks.",
        mvp_state="coming-soon",
        visibility="advanced",
        primary_profile=None,
    ),
    SecurityPackDefinition(
        id=ToolPackId.ADVANCED_DEPENDENCY,
        label="Advanced Dependency Pack",
        summary="Advanced Coming Soon package-behavior investigation for suspicious dependency version changes.",
        mvp_state="coming-soon",
        visibility="advanced",
        primary_profile=None,
    ),
)
SCAN_PROFILE_DEFINITIONS: tuple[ScanProfileDefinition, ...] = (
    ScanProfileDefinition(
        id="quick",
        label="Quick scan",
        command="security-scan --quick",
        summary="Fast baseline across built-in checks, code patterns, secrets, workflow surfaces, and one dependency advisory pass.",
        scanner_keys=("ai-static", "install-hooks", "workflow-audit", "semgrep", "gitleaks", "osv-scanner"),
        primary_pack_ids=(ToolPackId.STARTER,),
        notes=("Use the Starter Pack page to see which optional helpers are missing before trusting a clean quick scan.",),
    ),
    ScanProfileDefinition(
        id="default",
        label="Default scan",
        command="security-scan .",
        summary="Balanced local scan when no specific profile is selected.",
        scanner_keys=("ai-static", "install-hooks", "workflow-audit", "semgrep", "gitleaks", "trivy", "osv-scanner", "syft", "grype", "checkov"),
        primary_pack_ids=(ToolPackId.STARTER,),
        supporting_pack_ids=(ToolPackId.SECRETS, ToolPackId.DEPENDENCIES, ToolPackId.IAC),
        notes=("This is still a scan profile, not a pack run mode.",),
    ),
    ScanProfileDefinition(
        id="code",
        label="Code scan",
        command="security-scan --code",
        summary="Code vulnerability pattern checks.",
        scanner_keys=("semgrep",),
        supporting_pack_ids=(ToolPackId.STARTER,),
    ),
    ScanProfileDefinition(
        id="secrets",
        label="Secrets scan",
        command="security-scan --secrets",
        summary="Focused secret evidence using the local secret scanners that are available.",
        scanner_keys=("gitleaks", "trufflehog", "trivy"),
        primary_pack_ids=(ToolPackId.SECRETS,),
        supporting_pack_ids=(ToolPackId.STARTER,),
    ),
    ScanProfileDefinition(
        id="deps",
        label="Dependency scan",
        command="security-scan --deps",
        summary="SBOM inventory, dependency advisories, and local supply-chain context.",
        scanner_keys=("install-hooks", "trivy", "osv-scanner", "syft", "grype"),
        primary_pack_ids=(ToolPackId.DEPENDENCIES,),
    ),
    ScanProfileDefinition(
        id="deps+trust-cache-only",
        label="Dependency trust from cache",
        command="security-scan --deps --trust-cache-only",
        summary="Dependency scan with locally cached trust context only.",
        scanner_keys=("install-hooks", "trivy", "osv-scanner", "syft", "grype"),
        primary_pack_ids=(ToolPackId.DEPENDENCIES,),
        notes=("No network trust enrichment is requested in this profile.",),
    ),
    ScanProfileDefinition(
        id="deps+trust",
        label="Dependency trust online",
        command="security-scan --deps --trust",
        summary="Dependency scan with network-backed trust enrichment.",
        scanner_keys=("install-hooks", "trivy", "osv-scanner", "syft", "grype"),
        primary_pack_ids=(ToolPackId.DEPENDENCIES,),
        notes=("This profile can contact upstream trust sources after the user opts in.",),
    ),
    ScanProfileDefinition(
        id="ai",
        label="AI agent scan",
        command="security-scan --ai",
        summary="AI-agent, MCP, editor, and repo-poisoning checks.",
        scanner_keys=("ai-static", "medusa"),
        primary_pack_ids=(ToolPackId.AI_AGENT,),
    ),
    ScanProfileDefinition(
        id="iac",
        label="IaC scan",
        command="security-scan --iac",
        summary="Workflow and infrastructure configuration checks; pack UX remains Coming Soon.",
        scanner_keys=("workflow-audit", "trivy", "checkov"),
        primary_pack_ids=(ToolPackId.IAC,),
    ),
    ScanProfileDefinition(
        id="platform-posture",
        label="Platform posture scan",
        command="security-scan --platform-posture",
        summary="Token-backed SCM posture checks for branch protection, Actions, and repository settings.",
        scanner_keys=("legitify",),
        primary_pack_ids=(ToolPackId.PLATFORM_POSTURE,),
        notes=("Requires explicit credential setup; this is never part of a pack run.",),
    ),
    ScanProfileDefinition(
        id="behavioral-drift",
        label="Behavioral drift scan",
        command="security-scan --behavioral-drift",
        summary="Advanced local artifact comparison for suspicious dependency behavior changes.",
        scanner_keys=("syft", "malcontent"),
        primary_pack_ids=(ToolPackId.ADVANCED_DEPENDENCY,),
        notes=("Requires previous SBOMs and local package artifacts.",),
    ),
    ScanProfileDefinition(
        id="ioc",
        label="IOC scan",
        command="security-scan ioc .",
        summary="Named-campaign IOC matching against saved local dependency and domain evidence.",
        scanner_keys=("ioc-watch",),
        supporting_pack_ids=(ToolPackId.DEPENDENCIES,),
    ),
    ScanProfileDefinition(
        id="full",
        label="Full scan",
        command="security-scan --full",
        summary="Every configured local scanner path; high-risk or credential-backed tools still require their own setup.",
        scanner_keys=("ai-static", "install-hooks", "workflow-audit", "semgrep", "gitleaks", "trufflehog", "trivy", "osv-scanner", "syft", "grype", "checkov", "medusa"),
        primary_pack_ids=(ToolPackId.STARTER, ToolPackId.SECRETS, ToolPackId.DEPENDENCIES, ToolPackId.AI_AGENT),
        supporting_pack_ids=(ToolPackId.IAC, ToolPackId.PLATFORM_POSTURE, ToolPackId.ADVANCED_DEPENDENCY),
        notes=("Full is still a scan profile; packs only explain and prepare capability.",),
    ),
)


def tool_catalog_entries(
    *,
    detect_install_state: bool = False,
    managed_tool_records: Iterable[dict[str, Any]] | None = None,
) -> list[ToolCatalogEntry]:
    entries = list(CURRENT_TOOL_CATALOG)
    if not detect_install_state:
        return entries
    managed_evidence = _managed_evidence_by_tool(managed_tool_records)
    resolved: list[ToolCatalogEntry] = []
    for entry in entries:
        install_state = detect_install_state_for_tool(entry, managed_evidence.get(entry.id))
        if install_state == ToolInstallState.MANAGED:
            updated = entry.with_runtime_install(
                ToolInstallState.MANAGED,
                owner=ToolInstallOwner.DEVSEC,
                method=ToolInstallMethod.MANAGED_FUTURE,
                uninstall_posture=ToolUninstallPosture.DEVSEC_MANAGED,
                managed_package=entry.install.managed_package or entry.id,
            )
        else:
            updated = entry.with_install_state(install_state)
        rewritten = _next_step_for_runtime_state(entry, install_state)
        if rewritten is not None and rewritten != updated.install.next_step:
            updated = replace(updated, install=replace(updated.install, next_step=rewritten))
        resolved.append(updated)
    return resolved


def _next_step_for_runtime_state(
    entry: ToolCatalogEntry,
    install_state: ToolInstallState,
) -> str | None:
    # Tools authored as "Install X, then rerun…" go stale the moment runtime
    # detection proves the tool is already on disk. Rewrite the next-step copy
    # so the catalog detail page doesn't ask the user to install something they
    # already have.
    if install_state == ToolInstallState.DETECTED:
        return f"{entry.label} is installed locally. Run a matching scan profile to include it."
    if install_state == ToolInstallState.MANAGED:
        return f"{entry.label} is managed by DëvSec. Run a matching scan profile to include it."
    return None


def current_tool_catalog(
    *,
    detect_install_state: bool = False,
    managed_tool_records: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    managed_evidence = _managed_evidence_by_tool(managed_tool_records)
    items: list[dict[str, Any]] = []
    for entry in tool_catalog_entries(
        detect_install_state=detect_install_state,
        managed_tool_records=managed_tool_records,
    ):
        item = entry.to_dict()
        evidence = managed_evidence.get(entry.id)
        if evidence:
            item["managed_ownership"] = evidence.to_dict()
        item["install_preview"] = build_tool_install_preview(item, evidence)
        items.append(item)
    return items


def current_security_packs(
    *,
    detect_install_state: bool = False,
    managed_tool_records: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    tools = current_tool_catalog(
        detect_install_state=detect_install_state,
        managed_tool_records=managed_tool_records,
    )
    return [_security_pack_payload(definition, tools) for definition in SECURITY_PACK_DEFINITIONS]


def current_scan_profiles(
    *,
    detect_install_state: bool = False,
    managed_tool_records: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    packs = {
        pack["id"]: pack
        for pack in current_security_packs(
            detect_install_state=detect_install_state,
            managed_tool_records=managed_tool_records,
        )
    }
    return [_scan_profile_payload(definition, packs) for definition in SCAN_PROFILE_DEFINITIONS]


def scanner_catalog_compat() -> list[dict[str, Any]]:
    return [{"scanner": scanner, **metadata} for scanner, metadata in legacy_scanner_catalog_map().items()]


def legacy_scanner_catalog_map() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for entry in CURRENT_SCANNER_CATALOG:
        if not entry.scanner_key or not entry.legacy_scanner:
            continue
        catalog[entry.scanner_key] = {
            **dict(entry.legacy_scanner),
            "tool_id": entry.id,
            "category": entry.category.value,
            "profile_ids": list(entry.capabilities.scan_profiles),
            "recommended_pack_ids": _pack_ids_for_entry(entry),
            "install_state": entry.install_state.value,
        }
    return catalog


def detect_install_state_for_tool(
    entry: ToolCatalogEntry,
    managed_evidence: ManagedToolEvidence | None = None,
) -> ToolInstallState:
    if entry.lifecycle == ToolLifecycle.COMING_SOON:
        return ToolInstallState.COMING_SOON
    if entry.install.detection == ToolInstallDetection.BUILT_IN:
        return ToolInstallState.BUILT_IN
    if entry.install.detection == ToolInstallDetection.NONE:
        return entry.install_state
    if managed_evidence and managed_evidence.verified:
        return ToolInstallState.MANAGED

    candidates = tuple(item for item in (entry.install.binary, *entry.install.alternate_binaries) if item)
    if entry.install.detection == ToolInstallDetection.PATH_BINARY and candidates:
        detected = any(shutil.which(binary) for binary in candidates)
        if not detected:
            return ToolInstallState.MISSING
        if entry.setup_kind != SetupKind.NONE:
            # Setup-aware tools (legitify PAT, malcontent artifact cache, …)
            # flip between not-configured and detected based on whether their
            # SetupCard inputs have been filled. The static
            # ``requires_human_setup`` flag stays as a fallback for tools that
            # haven't populated ``setup_kind`` yet.
            return (
                ToolInstallState.DETECTED
                if _is_setup_satisfied(entry)
                else ToolInstallState.NOT_CONFIGURED
            )
        if entry.policy.requires_human_setup or entry.capabilities.requires_artifacts or entry.capabilities.requires_repo_remote:
            return ToolInstallState.NOT_CONFIGURED
        return ToolInstallState.DETECTED

    return entry.install_state


def _is_setup_satisfied(entry: ToolCatalogEntry) -> bool:
    """Return True when the tool's SetupCard inputs are populated.

    The shape of "satisfied" depends on ``setup_kind``:

    * ``api-key`` / ``env-var`` / ``oauth`` — the Keychain holds an entry under
      ``(DëvSec, <tool_id>:<env_from_credential>)``. The probe spec carries the
      credential key name; we never read the value here, just check presence
      via the local credential index (no Keychain prompt).
    * ``file-path`` / ``config-block`` — the on-disk tool config file holds a
      non-empty value for the spec's ``config_key`` (file-path) or any value at
      all (config-block).
    * ``none`` — never reached (callers guard).
    """
    probe = entry.setup_probe
    if probe is None:
        return False
    spec = probe.spec or {}
    kind = entry.setup_kind
    if kind in (SetupKind.API_KEY, SetupKind.ENV_VAR, SetupKind.OAUTH):
        credential_key = spec.get("env_from_credential") or spec.get("env_var")
        if not credential_key:
            return False
        try:
            from .credentials import list_credentials
        except ImportError:  # pragma: no cover - defensive
            return False
        try:
            stored_keys = list_credentials(entry.id)
        except Exception:  # pragma: no cover - defensive
            return False
        return credential_key in stored_keys
    if kind == SetupKind.FILE_PATH:
        config_key = spec.get("config_key")
        if not config_key:
            return False
        stored = read_tool_config(entry.id).get(config_key, "").strip()
        return bool(stored)
    if kind == SetupKind.CONFIG_BLOCK:
        return bool(read_tool_config(entry.id))
    return False


def _managed_evidence_by_tool(managed_tool_records: Iterable[dict[str, Any]] | None) -> dict[str, ManagedToolEvidence]:
    if not managed_tool_records:
        return {}
    return managed_tool_evidence_by_tool(managed_tool_records)


def _security_pack_payload(definition: SecurityPackDefinition, tools: list[dict[str, Any]]) -> dict[str, Any]:
    included: list[dict[str, Any]] = []
    for tool in tools:
        membership = next(
            (
                pack
                for pack in tool.get("packs", [])
                if isinstance(pack, dict) and pack.get("pack_id") == definition.id.value
            ),
            None,
        )
        if not membership:
            continue
        included.append(
            {
                "id": tool["id"],
                "label": tool["label"],
                "summary": tool["summary"],
                "role": membership.get("role"),
                "default_enabled": bool(membership.get("default_enabled")),
                "install_state": tool.get("install_state"),
                "lifecycle": tool.get("lifecycle"),
                "derived_labels": tool.get("derived_labels"),
                "install_preview": tool.get("install_preview"),
            }
        )
    status_counts = _counts_by(included, "install_state")
    ready_count = sum(status_counts.get(state, 0) for state in ("built-in", "managed", "detected"))
    return {
        "id": definition.id.value,
        "label": definition.label,
        "summary": definition.summary,
        "mvp_state": definition.mvp_state,
        "visibility": definition.visibility,
        "primary_profile": definition.primary_profile,
        "secondary_profiles": list(definition.secondary_profiles),
        "status_counts": status_counts,
        "ready_count": ready_count,
        "missing_count": status_counts.get("missing", 0),
        "display_only_count": status_counts.get("coming-soon", 0),
        "tools": included,
        "install_preview": _pack_install_preview(definition, included, status_counts),
    }


def _scan_profile_payload(definition: ScanProfileDefinition, packs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    primary_pack_ids = [pack_id.value for pack_id in definition.primary_pack_ids]
    supporting_pack_ids = [pack_id.value for pack_id in definition.supporting_pack_ids]
    recommended_pack_ids = [*primary_pack_ids, *[pack_id for pack_id in supporting_pack_ids if pack_id not in primary_pack_ids]]
    return {
        "id": definition.id,
        "label": definition.label,
        "command": definition.command,
        "summary": definition.summary,
        "scanner_keys": list(definition.scanner_keys),
        "primary_pack_ids": primary_pack_ids,
        "supporting_pack_ids": supporting_pack_ids,
        "recommended_pack_ids": recommended_pack_ids,
        "recommended_packs": [_pack_reference(packs[pack_id]) for pack_id in recommended_pack_ids if pack_id in packs],
        "notes": list(definition.notes),
    }


def _pack_reference(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": pack.get("id"),
        "label": pack.get("label"),
        "mvp_state": pack.get("mvp_state"),
        "visibility": pack.get("visibility"),
        "ready_count": pack.get("ready_count", 0),
        "missing_count": pack.get("missing_count", 0),
        "display_only_count": pack.get("display_only_count", 0),
        "status_counts": pack.get("status_counts") or {},
    }


def _pack_ids_for_entry(entry: ToolCatalogEntry) -> list[str]:
    return [membership.pack_id.value for membership in entry.packs]


def _pack_install_preview(
    definition: SecurityPackDefinition,
    included: list[dict[str, Any]],
    status_counts: dict[str, int],
) -> dict[str, Any]:
    tool_previews = [
        preview
        for item in included
        for preview in [item.get("install_preview")]
        if isinstance(preview, dict) and preview.get("preview_available")
    ]
    if definition.mvp_state != "real":
        return {
            "pack_id": definition.id.value,
            "action": "none",
            "preview_available": False,
            "execution_available": False,
            "execution_reason": "Coming Soon packs are display-only in the MVP.",
            "pack_install_supported": False,
            "tool_previews": [],
            "status_counts": status_counts,
            "notes": ["No install, uninstall, run, target input, or Agent Lab action is available for this pack."],
        }
    return {
        "pack_id": definition.id.value,
        "action": "pack-install-preview",
        "preview_available": True,
        "execution_available": False,
        "execution_reason": "Broad pack install is deferred; the MVP only previews individual approved managed-tool actions.",
        "pack_install_supported": False,
        "tool_previews": tool_previews,
        "status_counts": status_counts,
        "notes": ["Packs remain curated guidance and do not create a second scan execution mode."],
    }


def _counts_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


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
    docs_path: str | None = None,
    homepage_url: str | None = None,
    setup_kind: SetupKind = SetupKind.NONE,
    setup_requirement: str | None = None,
    setup_probe: SetupProbe | None = None,
    setup_token_create_url: str | None = None,
    branding: ToolBranding = ToolBranding(accent_color=DEVSEC_ACCENT),
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
        docs_path=docs_path,
        homepage_url=homepage_url,
        setup_kind=setup_kind,
        setup_requirement=setup_requirement,
        setup_probe=setup_probe,
        setup_token_create_url=setup_token_create_url,
        branding=branding,
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
    docs_path="/docs/tool-catalog.md",
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
        docs_path="/docs/iocs.md",
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
        docs_path="/docs/install-hooks.md",
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
        docs_path="/docs/workflow-audit.md",
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
        docs_path="/docs/agent-lab.md",
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
        homepage_url="https://semgrep.dev/docs/",
        branding=ToolBranding(accent_color="#4D40A1", logo="semgrep.svg"),
    ),
    _scanner_entry(
        scanner="gitleaks",
        label="Gitleaks",
        area="Secrets",
        covers="Fast detection of exposed API keys, tokens, passwords, and private keys.",
        profile="quick, secrets, full",
        install_text="DëvSec can install this for you, or run ./install-security-observatory.sh or brew install gitleaks.",
        next_step="Install Gitleaks, then rerun the secrets or quick scan.",
        built_in=False,
        category=ToolCategory.SECRETS,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="gitleaks",
            instructions="DëvSec can install this for you, or run ./install-security-observatory.sh or brew install gitleaks.",
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
        homepage_url="https://github.com/gitleaks/gitleaks#readme",
        branding=ToolBranding(accent_color="#E2453C", logo="gitleaks.svg"),
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
        homepage_url="https://github.com/trufflesecurity/trufflehog#readme",
        branding=ToolBranding(accent_color="#FF4F00", logo="trufflehog.svg"),
    ),
    _scanner_entry(
        scanner="trivy",
        label="Trivy",
        area="Dependencies / IaC",
        covers="Filesystem, dependency, secret, and infrastructure misconfiguration checks.",
        profile="deps, secrets, iac, full",
        install_text="DëvSec can install this for you, or run ./install-security-observatory.sh or brew install trivy.",
        next_step="Install Trivy, then rerun the dependency, secrets, IaC, or full scan.",
        built_in=False,
        category=ToolCategory.DEPENDENCIES,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="trivy",
            instructions="DëvSec can install this for you, or run ./install-security-observatory.sh or brew install trivy.",
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
        homepage_url="https://trivy.dev/",
        branding=ToolBranding(accent_color="#1C7DD9", logo="trivy.svg"),
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
        homepage_url="https://google.github.io/osv-scanner/",
        branding=ToolBranding(accent_color="#1A73E8", logo="osv-scanner.svg"),
    ),
    _scanner_entry(
        scanner="syft",
        label="Syft",
        area="Dependencies / SBOM",
        covers="Software bill of materials generation.",
        profile="deps, full",
        install_text="DëvSec can install this for you, or run ./install-security-observatory.sh or brew install syft.",
        next_step="Install Syft, then rerun the dependency or full scan.",
        built_in=False,
        category=ToolCategory.DEPENDENCIES,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="syft",
            instructions="DëvSec can install this for you, or run ./install-security-observatory.sh or brew install syft.",
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
        homepage_url="https://github.com/anchore/syft#readme",
        branding=ToolBranding(accent_color="#E55B2B", logo="syft.svg"),
    ),
    _scanner_entry(
        scanner="grype",
        label="Grype",
        area="Dependencies / SBOM",
        covers="Dependency vulnerability scanning from an SBOM or repository filesystem.",
        profile="deps, full",
        install_text="DëvSec can install this for you, or run ./install-security-observatory.sh or brew install grype.",
        next_step="Install Grype, then rerun the dependency or full scan.",
        built_in=False,
        category=ToolCategory.DEPENDENCIES,
        lifecycle=ToolLifecycle.AVAILABLE,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="grype",
            instructions="DëvSec can install this for you, or run ./install-security-observatory.sh or brew install grype.",
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
        homepage_url="https://github.com/anchore/grype#readme",
        branding=ToolBranding(accent_color="#00ACC1", logo="grype.svg"),
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
        homepage_url="https://www.checkov.io/",
        branding=ToolBranding(accent_color="#6F4FF2", logo="checkov.svg"),
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
        homepage_url="https://github.com/Pantheon-Security/medusa#readme",
        branding=ToolBranding(accent_color="#1B5A6E", logo="medusa.svg"),
    ),
    _scanner_entry(
        scanner="malcontent",
        label="malcontent",
        area="Behavioral drift",
        covers="Advanced diffing of old and new dependency artifacts for suspicious behavior changes.",
        profile="behavioral-drift",
        install_text="Install malcontent separately, then provide local package artifacts under the behavioral artifact cache.",
        next_step="Set the behavioral artifact cache directory via the catalog setup card, then run security-scan --behavioral-drift after at least two SBOM-backed dependency scans.",
        built_in=False,
        category=ToolCategory.DEPENDENCIES,
        lifecycle=ToolLifecycle.ADVANCED,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.MANUAL,
            binary="malcontent",
            alternate_binaries=("mal",),
            instructions="Install malcontent separately, then provide local package artifacts under the behavioral artifact cache.",
            next_step="Set the behavioral artifact cache directory via the catalog setup card, then run security-scan --behavioral-drift after at least two SBOM-backed dependency scans.",
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
        homepage_url="https://github.com/chainguard-dev/malcontent#readme",
        setup_kind=SetupKind.FILE_PATH,
        setup_requirement="Path to behavioral artifact cache directory holding old and new dependency artifacts for diffing.",
        setup_probe=SetupProbe(
            kind=SetupProbeKind.DIRECTORY_EXISTS,
            spec={"config_key": "artifact_cache_dir"},
        ),
        branding=ToolBranding(accent_color="#4C44B3", logo="malcontent.svg"),
    ),
    _scanner_entry(
        scanner="legitify",
        label="legitify",
        area="Platform posture",
        covers="Optional connected checks for repository branch protection, Actions permissions, webhooks, and SCM settings.",
        profile="platform-posture",
        install_text="brew install legitify, then connect a GitHub Personal Access Token via the catalog setup card.",
        next_step="Connect a GitHub Personal Access Token (repo + admin:repo_hook scopes) via the catalog setup card, then run security-scan --platform-posture.",
        built_in=False,
        category=ToolCategory.PLATFORM_POSTURE,
        lifecycle=ToolLifecycle.ADVANCED,
        install_state=ToolInstallState.MISSING,
        install=_path_install(
            method=ToolInstallMethod.HOMEBREW,
            binary="legitify",
            instructions="brew install legitify, then connect a GitHub Personal Access Token via the catalog setup card.",
            next_step="Connect a GitHub Personal Access Token (repo + admin:repo_hook scopes) via the catalog setup card, then run security-scan --platform-posture.",
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
        docs_path="/docs/tools/legitify-setup.md",
        homepage_url="https://github.com/Legit-Labs/legitify#readme",
        setup_kind=SetupKind.API_KEY,
        setup_requirement="GitHub Personal Access Token with `repo` + `admin:repo_hook` scopes (stored locally in macOS Keychain).",
        setup_probe=SetupProbe(
            kind=SetupProbeKind.SHELL,
            spec={
                # Single namespace + one tiny public repo keeps the probe
                # under ~15s on a warm token. legitify exits 1 when it found
                # policy violations on the target (which is normal — the
                # repo isn't ours), so success_returncodes includes 1.
                # Auth failures surface as a non-{0,1} exit code or
                # stderr-only output, both of which the runner will flag.
                "command": (
                    "legitify analyze --scm github --namespace repository "
                    "--repo Legit-Labs/legitify --color false"
                ),
                "env_from_credential": "SCM_TOKEN",
                "timeout_seconds": "90",
                "success_returncodes": "0,1",
            },
        ),
        setup_token_create_url=(
            "https://github.com/settings/tokens/new"
            "?scopes=repo,admin:repo_hook"
            "&description=D%C3%ABvSec%20legitify"
        ),
        branding=ToolBranding(accent_color="#E63946", logo="legitify.svg"),
    ),
)

CURRENT_TOOL_CATALOG: tuple[ToolCatalogEntry, ...] = (*CURRENT_SCANNER_CATALOG, EXTERNAL_SURFACE_PLACEHOLDER)
