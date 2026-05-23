import {ReactNode} from 'react';
import {
  Database,
  FileCode2,
  Gauge,
  GitBranch,
  KeyRound,
  Layers3,
  Shield,
  ShieldCheck,
  TerminalSquare,
} from 'lucide-react';
import {
  DashboardSummary,
  ScannerDoctorItem,
  SecurityPackCatalogItem,
  ToolCatalogItem,
  ToolCategory,
  ToolInstallPreview,
  ToolInstallState,
  ToolLifecycle,
  ToolPackId,
} from '../../dashboardData';
import {humanizeKey, scannerStatusTone, topScannerItems} from '../../uiHelpers';
import {Tone} from '../../uiTypes';

// --- Types ---

export type CatalogStatusFilter = 'all' | 'ready' | 'setup' | 'missing' | 'advanced' | 'coming-soon';

export type CatalogMutationState = {
  toolId: string;
  kind: 'install' | 'uninstall';
  status: 'running' | 'complete' | 'error';
  message: string;
} | null;

// --- Label maps ---

export const catalogCategoryLabels: Record<ToolCategory, string> = {
  'code-security': 'Code security',
  secrets: 'Secrets',
  dependencies: 'Dependencies',
  'supply-chain': 'Supply chain',
  infrastructure: 'Infrastructure',
  'ai-agent': 'AI agent',
  'platform-posture': 'Platform posture',
  'external-surface': 'External surface',
  'defense-intel': 'Defense intel',
};

export const catalogCategoryOrder: ToolCategory[] = [
  'code-security',
  'secrets',
  'dependencies',
  'supply-chain',
  'ai-agent',
  'defense-intel',
  'infrastructure',
  'platform-posture',
  'external-surface',
];

export const catalogPackLabels: Record<ToolPackId, string> = {
  starter: 'Starter',
  secrets: 'Secrets',
  dependencies: 'Dependencies',
  'ai-agent': 'AI Agent',
  iac: 'IaC',
  'platform-posture': 'Platform Posture',
  'advanced-dependency': 'Advanced Dependency',
  'external-surface': 'External Surface',
};

export const catalogPackOrder: ToolPackId[] = [
  'starter',
  'secrets',
  'dependencies',
  'ai-agent',
  'iac',
  'platform-posture',
  'advanced-dependency',
  'external-surface',
];

export const catalogStatusFilters: {id: CatalogStatusFilter; label: string}[] = [
  {id: 'all', label: 'All'},
  {id: 'ready', label: 'Ready'},
  {id: 'setup', label: 'Needs setup'},
  {id: 'missing', label: 'Missing'},
  {id: 'advanced', label: 'Advanced'},
  {id: 'coming-soon', label: 'Coming soon'},
];

export const catalogInstallLabels: Record<ToolInstallState, string> = {
  'built-in': 'Built in',
  managed: 'DëvSec managed',
  detected: 'Detected locally',
  missing: 'Missing',
  unavailable: 'Unavailable',
  'not-configured': 'Needs setup',
  'coming-soon': 'Display only',
};

export const catalogLifecycleLabels: Record<ToolLifecycle, string> = {
  available: 'Available',
  beta: 'Beta',
  advanced: 'Advanced',
  'coming-soon': 'Coming soon',
  deprecated: 'Deprecated',
  hidden: 'Hidden',
};

export const catalogInstallMethodLabels: Record<ToolCatalogItem['install']['method'], string> = {
  'built-in': 'Built in',
  homebrew: 'Homebrew',
  'uv-tool': 'uv tool',
  manual: 'Manual setup',
  'docker-optional': 'Docker optional',
  'managed-future': 'DëvSec managed future',
  none: 'None',
};

export const catalogInstallOwnerLabels: Record<ToolCatalogItem['install']['owner'], string> = {
  devsec: 'DëvSec',
  external: 'External project',
  user: 'User-owned local install',
  'not-applicable': 'Not applicable',
};

export const catalogInstallDetectionLabels: Record<ToolCatalogItem['install']['detection'], string> = {
  'built-in': 'Built in',
  'path-binary': 'Binary on PATH',
  'config-preflight': 'Config preflight',
  'cache-preflight': 'Cache preflight',
  'registry-future': 'Managed registry future',
  none: 'None',
};

export const catalogUninstallLabels: Record<ToolCatalogItem['install']['uninstall_posture'], string> = {
  'not-needed': 'No uninstall needed',
  'devsec-managed': 'DëvSec-managed cleanup',
  'user-owned': 'User-owned; DëvSec will not remove it',
  'manual-only': 'Manual cleanup only',
  'not-supported': 'No uninstall action',
};

export const catalogNetworkLabels: Record<ToolCatalogItem['policy']['network_access'], string> = {
  none: 'No network required',
  optional: 'Optional network',
  required: 'Network required',
};

export const catalogTargetLabels: Record<ToolCatalogItem['policy']['external_targets'], string> = {
  none: 'No external target',
  'repo-derived': 'Repository-derived target',
  'user-provided': 'User-provided target',
};

export const catalogCredentialLabels: Record<ToolCatalogItem['policy']['uses_credentials'], string> = {
  none: 'No credentials',
  optional: 'Optional credentials',
  required: 'Needs credentials',
};

export const catalogEvidenceLabels: Record<ToolCatalogItem['capabilities']['evidence_types'][number], string> = {
  'source-pattern': 'Source code patterns',
  'secret-match': 'Secret matches',
  'dependency-advisory': 'Dependency advisories',
  sbom: 'SBOM inventory',
  'iac-policy': 'Infrastructure policy',
  'workflow-policy': 'Workflow policy',
  'install-hook': 'Install hooks',
  'ai-config': 'AI-agent config',
  'platform-posture': 'Platform posture',
  'behavior-diff': 'Behavior changes',
  'ioc-match': 'IOC matches',
  'external-observation': 'External observation',
};

// --- Pure helpers ---
//
// These functions are kept outside useCatalogData on purpose. They read a tool
// or pack and derive a label, tone, or copy fragment — they never capture
// React state. That makes them easy to test (no renderer needed) and keeps the
// hook focused on the data it actually owns: catalog items, packs, runtime
// map, and the install/uninstall mutation state machine.

export function catalogRuntimeMap(summary: DashboardSummary): Map<string, ScannerDoctorItem> {
  return new Map(topScannerItems(summary).map((item) => [item.scanner, item]));
}

export function catalogStatusBucket(item: ToolCatalogItem): CatalogStatusFilter {
  if (item.lifecycle === 'coming-soon' || item.install_state === 'coming-soon') return 'coming-soon';
  if (item.lifecycle === 'advanced') return 'advanced';
  if (item.install_state === 'missing') return 'missing';
  if (item.install_state === 'not-configured' || item.install_state === 'unavailable') return 'setup';
  if (item.install_state === 'built-in' || item.install_state === 'managed' || item.install_state === 'detected') return 'ready';
  return 'all';
}

export function catalogStatusTone(item: ToolCatalogItem, runtime?: ScannerDoctorItem): Tone {
  if (runtime?.status === 'error') return 'crit';
  if (item.lifecycle === 'coming-soon' || item.install_state === 'coming-soon') return 'neutral';
  if (item.install_state === 'missing' || item.install_state === 'not-configured') return 'info';
  if (item.install_state === 'unavailable') return 'warn';
  if (item.lifecycle === 'advanced') return 'info';
  if (item.install_state === 'built-in' || item.install_state === 'managed' || item.install_state === 'detected') return 'low';
  return 'neutral';
}

export function catalogIcon(category: ToolCategory): ReactNode {
  if (category === 'code-security') return <FileCode2 size={18} />;
  if (category === 'secrets') return <KeyRound size={18} />;
  if (category === 'dependencies') return <Database size={18} />;
  if (category === 'supply-chain') return <GitBranch size={18} />;
  if (category === 'infrastructure') return <Layers3 size={18} />;
  if (category === 'ai-agent') return <TerminalSquare size={18} />;
  if (category === 'platform-posture') return <ShieldCheck size={18} />;
  if (category === 'external-surface') return <Gauge size={18} />;
  return <Shield size={18} />;
}

export function catalogPackIconCategory(pack: ToolPackId): ToolCategory {
  if (pack === 'external-surface') return 'external-surface';
  if (pack === 'ai-agent') return 'ai-agent';
  if (pack === 'iac') return 'infrastructure';
  if (pack === 'platform-posture') return 'platform-posture';
  if (pack === 'secrets') return 'secrets';
  if (pack === 'dependencies' || pack === 'advanced-dependency') return 'dependencies';
  return 'code-security';
}

export function securityPackTone(pack: SecurityPackCatalogItem): Tone {
  if (pack.mvp_state !== 'real') return 'neutral';
  if (pack.missing_count > 0) return 'info';
  return 'low';
}

export function securityPackStateLabel(pack: SecurityPackCatalogItem): string {
  if (pack.mvp_state !== 'real') return 'Display only';
  if (pack.missing_count > 0) return 'Setup gaps';
  return 'Ready';
}

export function securityPackSearchText(pack: SecurityPackCatalogItem): string {
  return [
    pack.id,
    pack.label,
    pack.summary,
    pack.mvp_state,
    pack.visibility,
    pack.primary_profile,
    ...pack.secondary_profiles,
    ...pack.tools.flatMap((tool) => [tool.id, tool.label, tool.summary, tool.install_state, tool.lifecycle, tool.role]),
  ].filter(Boolean).join(' ').toLowerCase();
}

export function catalogSearchText(item: ToolCatalogItem): string {
  return [
    item.id,
    item.label,
    item.summary,
    item.description,
    catalogCategoryLabels[item.category],
    item.scanner_key,
    item.lifecycle,
    item.install_state,
    ...item.profiles,
    ...item.derived_labels.safety,
    ...item.derived_labels.install,
    item.derived_labels.agent_lab,
    ...item.packs.map((pack) => catalogPackLabels[pack.pack_id]),
  ].filter(Boolean).join(' ').toLowerCase();
}

export function isAdvancedCatalogItem(item: ToolCatalogItem): boolean {
  return item.lifecycle === 'advanced' || item.packs.some((pack) => pack.pack_id === 'advanced-dependency' || pack.pack_id === 'platform-posture');
}

export function shouldShowAdvancedCatalogItem(
  item: ToolCatalogItem,
  search: string,
  category: ToolCategory | 'all',
  pack: ToolPackId | 'all',
  status: CatalogStatusFilter,
): boolean {
  if (!isAdvancedCatalogItem(item)) return true;
  if (search.trim()) return true;
  if (status === 'advanced') return true;
  if (category === 'infrastructure' || category === 'platform-posture') return true;
  return pack === 'advanced-dependency' || pack === 'platform-posture' || pack === 'iac';
}

export function catalogStatusLabel(item: ToolCatalogItem, runtime?: ScannerDoctorItem): string {
  return runtime?.status === 'error' ? 'Error' : catalogInstallLabels[item.install_state];
}

export function catalogRuntimeTone(runtime?: ScannerDoctorItem): Tone {
  if (!runtime) return 'info';
  return scannerStatusTone(runtime.status);
}

export function catalogRuntimeLabel(item: ToolCatalogItem, runtime?: ScannerDoctorItem): string {
  if (runtime) return runtime.status.replace('-', ' ');
  if (item.scanner_key) return 'Not run';
  return catalogLifecycleLabels[item.lifecycle];
}

export function catalogRuntimeCopy(item: ToolCatalogItem, runtime?: ScannerDoctorItem): string {
  if (!item.scanner_key) {
    return item.lifecycle === 'coming-soon'
      ? 'This entry is product education only. It has no runtime path in this version.'
      : 'This entry is not joined to a scanner runtime yet.';
  }
  if (!runtime) return 'No scan has reported runtime status for this tool in the selected scope.';
  if (runtime.status === 'ran') {
    const repoCopy = runtime.repoNames.length ? ` across ${runtime.repoNames.join(', ')}` : '';
    return `${runtime.findings} finding${runtime.findings === 1 ? '' : 's'} reported${repoCopy}.`;
  }
  return runtime.action;
}

export function catalogStateCopy(item: ToolCatalogItem, runtime?: ScannerDoctorItem): {title: string; detail: string; action: string; tone: Tone} {
  if (runtime?.status === 'error') {
    return {
      title: 'Runtime error from last scan',
      detail: runtime.error ?? 'The scanner reported an error in the selected scope.',
      action: 'Fix the scanner error, then rerun the matching profile before trusting this coverage.',
      tone: 'crit',
    };
  }
  if (item.lifecycle === 'coming-soon' || item.install_state === 'coming-soon') {
    return {
      title: 'Display-only future coverage',
      detail: 'This placeholder explains future coverage. It cannot collect targets, install tooling, run scans, or trigger Agent Lab.',
      action: item.category === 'external-surface'
        ? 'External Surface stays idle until target approval controls exist.'
        : 'Wait for a future release before treating this as active coverage.',
      tone: 'neutral',
    };
  }
  if (item.install_state === 'built-in') {
    return {
      title: 'Built into DëvSec',
      detail: 'No external binary or install step is needed. DëvSec owns the scanner logic.',
      action: 'Use the existing profile picker when you want this check included in a scan.',
      tone: 'low',
    };
  }
  if (item.install_state === 'managed') {
    return {
      title: 'DëvSec-managed install',
      detail: 'DëvSec owns this install path, so future update and cleanup controls can be tied to a managed-tool record.',
      action: 'Install and uninstall controls remain disabled here until backend ownership proof is wired.',
      tone: 'low',
    };
  }
  if (item.install_state === 'detected') {
    return {
      title: 'Detected locally',
      detail: 'The tool was found on this Mac, but it was installed outside DëvSec.',
      action: 'DëvSec may use it in scans, but will not claim it can upgrade or remove the tool.',
      tone: 'low',
    };
  }
  if (item.install_state === 'missing') {
    return {
      title: 'Supported, not installed',
      detail: 'This is a setup gap, not evidence that the repository is unsafe.',
      action: item.install.instructions ?? item.install.next_step ?? 'Install the tool outside the catalog, then rerun the matching scan.',
      tone: 'info',
    };
  }
  if (item.install_state === 'unavailable') {
    return {
      title: 'Unavailable in this context',
      detail: 'Installation alone is not enough for this check right now.',
      action: item.install.next_step ?? 'Resolve the environment or prerequisite blocker before expecting this tool to run.',
      tone: 'warn',
    };
  }
  if (item.install_state === 'not-configured') {
    return {
      title: 'Needs setup',
      detail: 'The tool needs credentials, local artifacts, cache data, or repository context before it can produce useful evidence.',
      action: item.install.next_step ?? 'Complete the setup requirement, then rerun the matching profile.',
      tone: 'info',
    };
  }
  return {
    title: catalogLifecycleLabels[item.lifecycle],
    detail: 'No extra availability detail has been published for this state yet.',
    action: item.install.next_step ?? 'Review setup and safety details before running checks.',
    tone: 'neutral',
  };
}

export function catalogPolicySummary(item: ToolCatalogItem): string {
  if (catalogStatusBucket(item) === 'coming-soon') {
    return 'Display-only future coverage. It cannot collect targets, install tooling, run scans, or trigger Agent Lab in this version.';
  }
  const notes = [
    item.policy.local_only && item.policy.network_access === 'none' ? 'Runs locally' : catalogNetworkLabels[item.policy.network_access],
    catalogCredentialLabels[item.policy.uses_credentials],
    item.policy.writes_files ? 'writes files' : 'read-only',
  ];
  if (item.policy.needs_approval) notes.push('approval required');
  if (!item.policy.allowed_for_agent_lab) notes.push('Agent Lab blocked');
  return `${notes.join(', ')}.`;
}

export function catalogCapabilityLabels(item: ToolCatalogItem): string[] {
  const categories = item.capabilities.finding_categories.map((category) => humanizeKey(category));
  const evidence = item.capabilities.evidence_types.map((type) => catalogEvidenceLabels[type] ?? humanizeKey(type));
  return [...new Set([...categories, ...evidence])];
}

export function catalogProfileRole(item: ToolCatalogItem, profile: string): string {
  const normalized = profile.toLowerCase();
  if (item.lifecycle === 'coming-soon') return 'Future';
  if (item.lifecycle === 'advanced' || normalized.includes('iac') || normalized.includes('platform') || normalized.includes('full')) return 'Advanced';
  if (item.policy.default_enabled && (normalized === 'default' || normalized === 'quick')) return 'Default';
  return 'Opt-in';
}

export function catalogProfileTone(item: ToolCatalogItem, profile: string): Tone {
  const role = catalogProfileRole(item, profile);
  if (role === 'Default') return 'low';
  if (role === 'Future') return 'neutral';
  return role === 'Advanced' ? 'info' : 'neutral';
}

export function catalogRunReady(item: ToolCatalogItem): boolean {
  if (item.lifecycle === 'coming-soon' || item.lifecycle === 'deprecated' || item.lifecycle === 'hidden') return false;
  return item.install_state === 'built-in' || item.install_state === 'managed' || item.install_state === 'detected';
}

export function catalogDisplayLabels(item: ToolCatalogItem): string[] {
  const labels = [
    ...item.derived_labels.safety,
    ...item.derived_labels.install,
    item.derived_labels.agent_lab,
  ]
    .filter(Boolean)
    .map((label) => label === 'DevSec managed' || label === 'Managed' ? 'DëvSec managed' : label);
  return [...new Set(labels)];
}

export function previewCanInstall(preview?: ToolInstallPreview): boolean {
  return Boolean(preview?.tool_id && preview.action === 'managed-install-preview' && preview.execution_available);
}

// State-aware action verb for catalog cards and banner CTAs. Built-in and
// already-detected tools never get an "Install plugin" label — there is
// nothing for the user to install. Display-only tools have no action surface.
export type CatalogCardAction = 'install' | 'view' | 'display-only';

export function catalogCardAction(tool: ToolCatalogItem): CatalogCardAction {
  if (tool.lifecycle === 'coming-soon' || tool.install_state === 'coming-soon') return 'display-only';
  if (previewCanInstall(tool.install_preview)) return 'install';
  return 'view';
}

export function previewCanUninstall(preview?: ToolInstallPreview): boolean {
  return Boolean(preview?.tool_id && preview.action === 'managed-uninstall-preview' && preview.execution_available && preview.ownership?.ownership_id);
}

export function previewTone(preview?: ToolInstallPreview): Tone {
  if (!preview?.preview_available) return 'neutral';
  if (preview.action === 'managed-uninstall-preview') return 'warn';
  if (preview.execution_available) return 'low';
  return 'info';
}

export function previewActionLabel(preview?: ToolInstallPreview): string {
  if (!preview?.preview_available) return 'No managed action';
  if (preview.action === 'managed-install-preview') return 'Managed install preview';
  if (preview.action === 'managed-uninstall-preview') return 'Managed uninstall preview';
  if (preview.action === 'pack-install-preview') return 'Pack install preview';
  return humanizeKey(preview.action);
}

export function previewOwnedPaths(preview: ToolInstallPreview): string[] {
  return (preview.owned_paths ?? [preview.install_root, preview.binary_path, preview.shim_path])
    .filter((path): path is string => Boolean(path));
}
