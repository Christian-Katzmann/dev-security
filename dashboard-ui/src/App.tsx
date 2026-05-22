import {CSSProperties, ReactNode, useCallback, useEffect, useMemo, useState} from 'react';
import CatalogHome from './components/catalog/CatalogHome';
import CatalogBrowse from './components/catalog/CatalogBrowse';
import CatalogToolPage from './components/catalog/CatalogToolPage';
import CatalogPackPage from './components/catalog/CatalogPackPage';
import {
  Activity,
  AlertTriangle,
  Archive,
  BarChart3,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleSlash,
  ClipboardList,
  Clock3,
  Copy,
  Database,
  Download,
  EyeOff,
  FileCode2,
  FileText,
  FolderGit2,
  Gauge,
  GitBranch,
  Home,
  KeyRound,
  Layers3,
  ListChecks,
  Lock,
  Pause,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Settings,
  Shield,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Stethoscope,
  TerminalSquare,
  X,
} from 'lucide-react';

import {
  AttentionBucket,
  CaseDecisionStatus,
  DashboardSummary,
  DisplayCase,
  HoneyIncident,
  HoneyKey,
  HoneyKeyEvent,
  HoneyKeyStatus,
  ProjectRepo,
  ProjectsPayload,
  ScannerDoctorItem,
  SecurityPackCatalogItem,
  SecurityPackTool,
  TargetSelection,
  ToolCatalogItem,
  ToolCategory,
  ToolInstallPreview,
  ToolInstallState,
  ToolLifecycle,
  ToolPackId,
  averageHealth,
  caseNeedsAttention,
  categoryLabel,
  dependencyCveCounts,
  dependencyChanges,
  dependencyDeltas,
  dependencyTrustRecords,
  displayCases,
  emptySummary,
  filterSummaryByTarget,
  formatDate,
  honeyKeyById,
  honeyKeyCounts,
  iocMatchFindings,
  latestOpenHoneyKeyEvent,
  latestRepoScan,
  latestScanTime,
  mergeProjectRepos,
  platformPostureFindings,
  platformPostureSnapshots,
  reportViewUrl,
  scanCompleteness,
  scannerCoverageSummary,
  scannerDoctorGroups,
  securityPackItems,
  severityTotal,
  suppressedDisplayCases,
  targetLabel,
  targetValue,
  totalFindings,
  toolCatalogItems,
} from './dashboardData';

type TabId = 'overview' | 'findings' | 'honey-keys' | 'scanners' | 'playbooks' | 'verification' | 'activity' | 'reports' | 'settings';
// Substate for the Tool Catalog tab. Four routes total — home is the root, the
// other three return via onBack to whichever route opened them ("from"). We
// keep state on App so reopening the tab restores the user's place; default is
// always 'home' on first mount.
type CatalogRoute =
  | {kind: 'home'}
  | {kind: 'browse'}
  | {kind: 'tool'; id: string; from: 'home' | 'browse'}
  | {kind: 'pack'; id: string; from: 'home' | 'browse'};
type AuditId = 'quick' | 'secrets' | 'code' | 'deps' | 'iac' | 'platform-posture' | 'ai' | 'full';
type Tone = 'low' | 'warn' | 'high' | 'crit' | 'info' | 'neutral';
type CatalogStatusFilter = 'all' | 'ready' | 'setup' | 'missing' | 'advanced' | 'coming-soon';
type CatalogMutationState = {
  toolId: string;
  kind: 'install' | 'uninstall';
  status: 'running' | 'complete' | 'error';
  message: string;
} | null;

type CompletedScan = {
  scan_id: string;
  health_score: number;
  status: string;
  profile: string;
  started_at: string;
  finished_at: string;
  report_path?: string;
  findings: unknown[];
  scanners: {available: boolean; error?: string | null; findings?: number; scanner: string}[];
};

type CheckJob = {
  id: string;
  status: 'queued' | 'running' | 'complete' | 'failed';
  progress: number;
  message: string;
  repoName: string;
  repoPath?: string;
  steps: string[];
  currentStep: string | null;
  error: string | null;
  summary?: DashboardSummary;
  scan?: CompletedScan;
};

type CreatedHoneyKey = {
  key: HoneyKey;
  raw_token: string;
  snippets: Record<string, string>;
  warning: string;
};

type ActivityItem = {
  id: string;
  at: string;
  date: Date | null;
  icon: ReactNode;
  label: string;
  sub: string;
  tone: Tone;
};

type PlaybookRecommendation = {
  id: string;
  title: string;
  body: string;
  trigger: string;
  steps: string[];
  estimate: string;
  caseItem?: DisplayCase;
};

const navGroups: {title: string; items: {id: TabId; label: string; icon: typeof Home}[]}[] = [
  {
    title: 'Workspace',
    items: [
      {id: 'overview', label: 'Overview', icon: Home},
      {id: 'findings', label: 'Findings', icon: ShieldAlert},
      {id: 'honey-keys', label: 'Honey keys', icon: ShieldCheck},
    ],
  },
  {
    title: 'Operate',
    items: [
      {id: 'scanners', label: 'Tool Catalog', icon: Search},
      {id: 'playbooks', label: 'Recovery playbooks', icon: BookOpen},
      {id: 'verification', label: 'Verification', icon: CheckCircle2},
    ],
  },
  {
    title: 'Records',
    items: [
      {id: 'activity', label: 'Activity', icon: Activity},
      {id: 'reports', label: 'Reports', icon: FileText},
    ],
  },
];

const tabTitles: Record<TabId, string> = {
  overview: 'Overview',
  findings: 'Findings',
  'honey-keys': 'Honey keys',
  scanners: 'Tool Catalog',
  playbooks: 'Recovery playbooks',
  verification: 'Verification',
  activity: 'Activity',
  reports: 'Reports',
  settings: 'Settings',
};

const customReposStorageKey = 'security-observatory-custom-repos';
const defaultAudits: AuditId[] = ['quick'];

const auditOptions: {id: AuditId; label: string; estimate: string; description: string}[] = [
  {id: 'quick', label: 'Quick safety sweep', estimate: '1-3 min', description: 'Fast baseline check across code, secrets, dependencies, and config.'},
  {id: 'secrets', label: 'Leaked secrets', estimate: '1-5 min', description: 'Looks for exposed keys, tokens, passwords, and private keys.'},
  {id: 'code', label: 'Code vulnerabilities', estimate: '1-4 min', description: 'Finds risky code patterns and insecure defaults.'},
  {id: 'deps', label: 'Dependency risks', estimate: '2-8 min', description: 'Checks packages for known vulnerabilities and outdated versions.'},
  {id: 'iac', label: 'Infrastructure exposure', estimate: '1-5 min', description: 'Reviews cloud and infrastructure config for unsafe exposure.'},
  {id: 'platform-posture', label: 'Connected platform', estimate: '1-5 min', description: 'Optional token-backed branch, workflow, and SCM posture checks.'},
  {id: 'ai', label: 'AI agent risks', estimate: '1-4 min', description: 'Checks prompts, MCP setup, tool permissions, and agent instructions.'},
  {id: 'full', label: 'Full repo audit', estimate: '5-20 min', description: 'Runs the deepest available scan across all categories.'},
];

const catalogCategoryLabels: Record<ToolCategory, string> = {
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

const catalogCategoryOrder: ToolCategory[] = [
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

const catalogPackLabels: Record<ToolPackId, string> = {
  starter: 'Starter',
  secrets: 'Secrets',
  dependencies: 'Dependencies',
  'ai-agent': 'AI Agent',
  iac: 'IaC',
  'platform-posture': 'Platform Posture',
  'advanced-dependency': 'Advanced Dependency',
  'external-surface': 'External Surface',
};

const catalogPackOrder: ToolPackId[] = [
  'starter',
  'secrets',
  'dependencies',
  'ai-agent',
  'iac',
  'platform-posture',
  'advanced-dependency',
  'external-surface',
];

const catalogStatusFilters: {id: CatalogStatusFilter; label: string}[] = [
  {id: 'all', label: 'All'},
  {id: 'ready', label: 'Ready'},
  {id: 'setup', label: 'Needs setup'},
  {id: 'missing', label: 'Missing'},
  {id: 'advanced', label: 'Advanced'},
  {id: 'coming-soon', label: 'Coming soon'},
];

const catalogInstallLabels: Record<ToolInstallState, string> = {
  'built-in': 'Built in',
  managed: 'DëvSec managed',
  detected: 'Detected locally',
  missing: 'Missing',
  unavailable: 'Unavailable',
  'not-configured': 'Needs setup',
  'coming-soon': 'Display only',
};

const catalogLifecycleLabels: Record<ToolLifecycle, string> = {
  available: 'Available',
  beta: 'Beta',
  advanced: 'Advanced',
  'coming-soon': 'Coming soon',
  deprecated: 'Deprecated',
  hidden: 'Hidden',
};

const catalogInstallMethodLabels: Record<ToolCatalogItem['install']['method'], string> = {
  'built-in': 'Built in',
  homebrew: 'Homebrew',
  'uv-tool': 'uv tool',
  manual: 'Manual setup',
  'docker-optional': 'Docker optional',
  'managed-future': 'DëvSec managed future',
  none: 'None',
};

const catalogInstallOwnerLabels: Record<ToolCatalogItem['install']['owner'], string> = {
  devsec: 'DëvSec',
  external: 'External project',
  user: 'User-owned local install',
  'not-applicable': 'Not applicable',
};

const catalogInstallDetectionLabels: Record<ToolCatalogItem['install']['detection'], string> = {
  'built-in': 'Built in',
  'path-binary': 'Binary on PATH',
  'config-preflight': 'Config preflight',
  'cache-preflight': 'Cache preflight',
  'registry-future': 'Managed registry future',
  none: 'None',
};

const catalogUninstallLabels: Record<ToolCatalogItem['install']['uninstall_posture'], string> = {
  'not-needed': 'No uninstall needed',
  'devsec-managed': 'DëvSec-managed cleanup',
  'user-owned': 'User-owned; DëvSec will not remove it',
  'manual-only': 'Manual cleanup only',
  'not-supported': 'No uninstall action',
};

const catalogNetworkLabels: Record<ToolCatalogItem['policy']['network_access'], string> = {
  none: 'No network required',
  optional: 'Optional network',
  required: 'Network required',
};

const catalogTargetLabels: Record<ToolCatalogItem['policy']['external_targets'], string> = {
  none: 'No external target',
  'repo-derived': 'Repository-derived target',
  'user-provided': 'User-provided target',
};

const catalogCredentialLabels: Record<ToolCatalogItem['policy']['uses_credentials'], string> = {
  none: 'No credentials',
  optional: 'Optional credentials',
  required: 'Needs credentials',
};

const catalogEvidenceLabels: Record<ToolCatalogItem['capabilities']['evidence_types'][number], string> = {
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

const severityMeta: Record<Tone, {label: string; dot: string; bg: string; fg: string}> = {
  low: {label: 'LOW', dot: 'var(--sev-low)', bg: 'rgba(138,163,154,0.20)', fg: '#3c4b48'},
  warn: {label: 'WARNING', dot: 'var(--sev-warn)', bg: '#f1dcbe', fg: '#7d4d10'},
  high: {label: 'ELEVATED', dot: 'var(--sev-high)', bg: '#ecc9b7', fg: '#6e3a1c'},
  crit: {label: 'CRITICAL', dot: 'var(--sev-crit)', bg: '#e8c6c0', fg: '#6c1f1f'},
  info: {label: 'INFO', dot: 'var(--sev-info)', bg: '#cfdbe9', fg: '#36506e'},
  neutral: {label: 'READY', dot: '#8d938f', bg: 'rgba(28,36,34,0.06)', fg: '#3c4b48'},
};

const placementTemplates = ['.env.backup', 'legacy-prod-config.json', 'internal-admin-notes.md'];
type IncidentStep = 'investigating' | 'secrets_rotated' | 'logs_reviewed' | 'archived_reset';
const incidentSteps: {id: IncidentStep; label: string; detail: string}[] = [
  {id: 'investigating', label: 'Investigating', detail: 'Check whether the repo was public, leaked, cloned, scraped, or accessed unexpectedly.'},
  {id: 'secrets_rotated', label: 'Real secrets rotated', detail: 'Rotate real credentials if exposure is plausible.'},
  {id: 'logs_reviewed', label: 'Logs reviewed', detail: 'Review commits, CI logs, deploy logs, integrations, and AI-agent activity.'},
  {id: 'archived_reset', label: 'Archived or reset', detail: 'Archive this Honey Key or place a fresh decoy after the investigation.'},
];

function basename(path: string): string {
  return path.split('/').filter(Boolean).at(-1) ?? path;
}

function loadCustomRepos(): ProjectRepo[] {
  try {
    const stored = window.localStorage.getItem(customReposStorageKey);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function formatDuration(startedAt?: string, finishedAt?: string): string {
  if (!startedAt || !finishedAt) return 'Just now';
  const seconds = Math.max(1, Math.round((new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
}

function incompleteToolCount(scan?: CompletedScan): number {
  return scan?.scanners.filter((scanner) => !scanner.available || scanner.error).length ?? 0;
}

function postureScore(summary: DashboardSummary): number {
  return Math.max(0, Math.min(10, averageHealth(summary) / 10));
}

function postureDelta(summary: DashboardSummary): number {
  const deltas = summary.repos.map((repo) => repo.health_delta).filter((value): value is number => typeof value === 'number');
  if (!deltas.length) return 0;
  return deltas.reduce((sum, value) => sum + value, 0) / deltas.length / 10;
}

function postureWeek(summary: DashboardSummary): {label: string; value: number}[] {
  const labels = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
  const history = [...summary.history].slice(-7);
  if (!history.length) {
    const score = postureScore(summary);
    return labels.map((label, index) => ({label, value: index === labels.length - 1 ? score : Math.max(0, score - (labels.length - index) * 0.2)}));
  }
  const values = history.map((item) => Math.max(0, Math.min(10, item.health_score / 10)));
  while (values.length < 7) values.unshift(values[0] ?? postureScore(summary));
  return values.slice(-7).map((value, index) => ({label: labels[index], value: Number(value.toFixed(1))}));
}

function toneForSeverity(value?: string): Tone {
  if (value === 'critical') return 'crit';
  if (value === 'high') return 'high';
  if (value === 'medium') return 'warn';
  if (value === 'low') return 'low';
  if (value === 'info') return 'info';
  return 'neutral';
}

function toneForCase(item: DisplayCase): Tone {
  return toneForSeverity(item.severity);
}

function relativeAge(value?: string | null): string {
  if (!value) return 'new';
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return value;
  const minutes = Math.max(1, Math.round((Date.now() - time) / 60000));
  if (minutes < 60) return `${minutes} m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h`;
  const days = Math.round(hours / 24);
  return `${days} d`;
}

function severityLabelForCase(item: DisplayCase): string {
  const tone = toneForCase(item);
  return severityMeta[tone].label;
}

function caseScanner(item: DisplayCase): string {
  return item.sources[0] ?? 'dashboard';
}

function displayId(item: DisplayCase, index: number): string {
  const stable = item.id.replace(/[^A-Za-z0-9]/g, '').slice(-4).toUpperCase();
  return `F-${stable || String(index + 1).padStart(4, '0')}`;
}

function activeCaseList(summary: DashboardSummary): DisplayCase[] {
  return displayCases(summary).filter(caseNeedsAttention);
}

function buildActivity(summary: DashboardSummary): ActivityItem[] {
  const items: ActivityItem[] = [];
  for (const event of summary.honey_key_events ?? []) {
    const date = new Date(event.triggered_at);
    const key = honeyKeyById(summary, event.honey_key_id);
    items.push({
      id: `honey-${event.id}`,
      at: timeLabel(event.triggered_at),
      date,
      icon: <ShieldAlert size={18} />,
      label: `Honey-key touched${key?.name ? ` · ${key.name}` : ''}`,
      sub: `${event.ip_address ?? 'unknown IP'} · ${event.reason}`,
      tone: event.incident?.closed_at ? 'warn' : 'crit',
    });
  }
  for (const item of activeCaseList(summary).slice(0, 20)) {
    const date = item.createdAt ? new Date(item.createdAt) : null;
    items.push({
      id: `case-${item.id}`,
      at: item.createdAt ? timeLabel(item.createdAt) : '--:--',
      date,
      icon: iconForCategory(item.category),
      label: `${caseScanner(item)} · ${item.title}`,
      sub: item.location,
      tone: toneForCase(item),
    });
  }
  for (const scan of summary.history.slice(-16)) {
    const finished = scan.finished_at ?? scan.started_at;
    const date = finished ? new Date(finished) : null;
    items.push({
      id: `scan-${scan.id}`,
      at: finished ? timeLabel(finished) : '--:--',
      date,
      icon: <RefreshCw size={18} />,
      label: `${scan.profile || 'Scan'} completed`,
      sub: `${scan.health_score}/100 health · ${scan.status}`,
      tone: scan.health_score < 70 ? 'warn' : 'low',
    });
  }
  for (const status of summary.project_statuses ?? []) {
    const date = status.last_event_at ? new Date(status.last_event_at) : null;
    items.push({
      id: `project-${status.project_id}`,
      at: status.last_event_at ? timeLabel(status.last_event_at) : '--:--',
      date,
      icon: <Gauge size={18} />,
      label: `${status.project_id} · ${status.status}`,
      sub: status.reason,
      tone: status.status === 'red' ? 'crit' : status.status === 'yellow' ? 'warn' : 'low',
    });
  }
  return items
    .sort((a, b) => (b.date?.getTime() ?? 0) - (a.date?.getTime() ?? 0))
    .slice(0, 36);
}

function timeLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
}

function iconForCategory(category?: string): ReactNode {
  if (category === 'dependencies' || category === 'behavioral-drift' || category === 'silent-upgrade') return <Database size={18} />;
  if (category === 'iac' || category === 'platform-posture') return <Layers3 size={18} />;
  if (category === 'secrets') return <KeyRound size={18} />;
  if (category === 'ai-risk') return <TerminalSquare size={18} />;
  return <ShieldAlert size={18} />;
}

function severityCounts(summary: DashboardSummary) {
  return {
    critical: severityTotal(summary, 'critical'),
    elevated: severityTotal(summary, 'high'),
    warning: severityTotal(summary, 'medium'),
    low: severityTotal(summary, 'low') + severityTotal(summary, 'info'),
  };
}

function buildPlaybooks(summary: DashboardSummary): PlaybookRecommendation[] {
  const cases = activeCaseList(summary);
  const mapped = cases.slice(0, 6).map((item, index): PlaybookRecommendation => {
    const category = item.category ?? 'security';
    const title = playbookTitle(item, category);
    return {
      id: item.id,
      title,
      body: item.nextStep,
      trigger: `${caseScanner(item)} · ${categoryLabel(category)}`,
      estimate: index === 0 ? '22 min' : item.bucket === 'fix-now' ? '12 min' : '4 min',
      caseItem: item,
      steps: playbookSteps(item),
    };
  });
  if (mapped.length) return mapped;
  return [
    {
      id: 'coverage-review',
      title: 'Review scan coverage',
      body: 'Confirm the checks that ran are enough for the repo before trusting a clean result.',
      trigger: 'verification · scanner-health',
      estimate: '4 min',
      steps: ['Review skipped checks', 'Install or rerun needed scanners', 'Run a quick sweep'],
    },
  ];
}

function playbookTitle(item: DisplayCase, category: string): string {
  if (category === 'dependencies') return 'Rotate vulnerable package';
  if (category === 'silent-upgrade') return 'Verify silent dependency change';
  if (category === 'secrets') return 'Rotate live secret + scrub history';
  if (category === 'iac') return 'Tighten infrastructure exposure';
  if (category === 'platform-posture') return 'Restore platform guardrails';
  if (category === 'ai-risk') return 'Narrow agent permissions';
  if (category === 'behavioral-drift') return 'Investigate package behavior drift';
  return item.title;
}

function playbookSteps(item: DisplayCase): string[] {
  return [
    `Capture evidence for ${item.location}`,
    item.nextStep,
    'Rerun the matching DëvSec check',
    'Record the case decision when verified',
  ];
}

function topScannerItems(summary: DashboardSummary): ScannerDoctorItem[] {
  return scannerDoctorGroups(summary).flatMap((group) => group.items);
}

function scannerStatusTone(status: ScannerDoctorItem['status']): Tone {
  if (status === 'ran') return 'low';
  if (status === 'not-run') return 'info';
  if (status === 'missing') return 'warn';
  return 'crit';
}

function catalogRuntimeMap(summary: DashboardSummary): Map<string, ScannerDoctorItem> {
  return new Map(topScannerItems(summary).map((item) => [item.scanner, item]));
}

function catalogStatusBucket(item: ToolCatalogItem): CatalogStatusFilter {
  if (item.lifecycle === 'coming-soon' || item.install_state === 'coming-soon') return 'coming-soon';
  if (item.lifecycle === 'advanced') return 'advanced';
  if (item.install_state === 'missing') return 'missing';
  if (item.install_state === 'not-configured' || item.install_state === 'unavailable') return 'setup';
  if (item.install_state === 'built-in' || item.install_state === 'managed' || item.install_state === 'detected') return 'ready';
  return 'all';
}

function catalogStatusTone(item: ToolCatalogItem, runtime?: ScannerDoctorItem): Tone {
  if (runtime?.status === 'error') return 'crit';
  if (item.lifecycle === 'coming-soon' || item.install_state === 'coming-soon') return 'neutral';
  if (item.install_state === 'missing' || item.install_state === 'not-configured') return 'info';
  if (item.install_state === 'unavailable') return 'warn';
  if (item.lifecycle === 'advanced') return 'info';
  if (item.install_state === 'built-in' || item.install_state === 'managed' || item.install_state === 'detected') return 'low';
  return 'neutral';
}

function safetyLabelTone(label: string): Tone {
  const normalized = label.toLowerCase();
  if (normalized.includes('sends source') || normalized.includes('destructive')) return 'crit';
  if (normalized.includes('network required') || normalized.includes('needs credentials') || normalized.includes('approval required') || normalized.includes('writes files')) return 'warn';
  if (normalized.includes('optional network') || normalized.includes('blocked')) return 'info';
  return normalized.includes('display only') ? 'neutral' : 'low';
}

function catalogIcon(category: ToolCategory): ReactNode {
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

function catalogPackIconCategory(pack: ToolPackId): ToolCategory {
  if (pack === 'external-surface') return 'external-surface';
  if (pack === 'ai-agent') return 'ai-agent';
  if (pack === 'iac') return 'infrastructure';
  if (pack === 'platform-posture') return 'platform-posture';
  if (pack === 'secrets') return 'secrets';
  if (pack === 'dependencies' || pack === 'advanced-dependency') return 'dependencies';
  return 'code-security';
}

function securityPackTone(pack: SecurityPackCatalogItem): Tone {
  if (pack.mvp_state !== 'real') return 'neutral';
  if (pack.missing_count > 0) return 'info';
  return 'low';
}

function securityPackStateLabel(pack: SecurityPackCatalogItem): string {
  if (pack.mvp_state !== 'real') return 'Display only';
  if (pack.missing_count > 0) return 'Setup gaps';
  return 'Ready';
}

function securityPackSearchText(pack: SecurityPackCatalogItem): string {
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

function catalogSearchText(item: ToolCatalogItem): string {
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

function isAdvancedCatalogItem(item: ToolCatalogItem): boolean {
  return item.lifecycle === 'advanced' || item.packs.some((pack) => pack.pack_id === 'advanced-dependency' || pack.pack_id === 'platform-posture');
}

function shouldShowAdvancedCatalogItem(item: ToolCatalogItem, search: string, category: ToolCategory | 'all', pack: ToolPackId | 'all', status: CatalogStatusFilter): boolean {
  if (!isAdvancedCatalogItem(item)) return true;
  if (search.trim()) return true;
  if (status === 'advanced') return true;
  if (category === 'infrastructure' || category === 'platform-posture') return true;
  return pack === 'advanced-dependency' || pack === 'platform-posture' || pack === 'iac';
}

function catalogStatusLabel(item: ToolCatalogItem, runtime?: ScannerDoctorItem): string {
  return runtime?.status === 'error' ? 'Error' : catalogInstallLabels[item.install_state];
}

function catalogRuntimeTone(runtime?: ScannerDoctorItem): Tone {
  if (!runtime) return 'info';
  return scannerStatusTone(runtime.status);
}

function catalogRuntimeLabel(item: ToolCatalogItem, runtime?: ScannerDoctorItem): string {
  if (runtime) return runtime.status.replace('-', ' ');
  if (item.scanner_key) return 'Not run';
  return catalogLifecycleLabels[item.lifecycle];
}

function catalogRuntimeCopy(item: ToolCatalogItem, runtime?: ScannerDoctorItem): string {
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

function catalogStateCopy(item: ToolCatalogItem, runtime?: ScannerDoctorItem): {title: string; detail: string; action: string; tone: Tone} {
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

function catalogPolicySummary(item: ToolCatalogItem): string {
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

function catalogCapabilityLabels(item: ToolCatalogItem): string[] {
  const categories = item.capabilities.finding_categories.map((category) => humanizeKey(category));
  const evidence = item.capabilities.evidence_types.map((type) => catalogEvidenceLabels[type] ?? humanizeKey(type));
  return [...new Set([...categories, ...evidence])];
}

function catalogProfileRole(item: ToolCatalogItem, profile: string): string {
  const normalized = profile.toLowerCase();
  if (item.lifecycle === 'coming-soon') return 'Future';
  if (item.lifecycle === 'advanced' || normalized.includes('iac') || normalized.includes('platform') || normalized.includes('full')) return 'Advanced';
  if (item.policy.default_enabled && (normalized === 'default' || normalized === 'quick')) return 'Default';
  return 'Opt-in';
}

function catalogProfileTone(item: ToolCatalogItem, profile: string): Tone {
  const role = catalogProfileRole(item, profile);
  if (role === 'Default') return 'low';
  if (role === 'Future') return 'neutral';
  return role === 'Advanced' ? 'info' : 'neutral';
}

function catalogRunReady(item: ToolCatalogItem): boolean {
  if (item.lifecycle === 'coming-soon' || item.lifecycle === 'deprecated' || item.lifecycle === 'hidden') return false;
  return item.install_state === 'built-in' || item.install_state === 'managed' || item.install_state === 'detected';
}

function catalogDisplayLabels(item: ToolCatalogItem): string[] {
  const labels = [
    ...item.derived_labels.safety,
    ...item.derived_labels.install,
    item.derived_labels.agent_lab,
  ]
    .filter(Boolean)
    .map((label) => label === 'DevSec managed' || label === 'Managed' ? 'DëvSec managed' : label);
  return [...new Set(labels)];
}

function previewCanInstall(preview?: ToolInstallPreview): boolean {
  return Boolean(preview?.tool_id && preview.action === 'managed-install-preview' && preview.execution_available);
}

function previewCanUninstall(preview?: ToolInstallPreview): boolean {
  return Boolean(preview?.tool_id && preview.action === 'managed-uninstall-preview' && preview.execution_available && preview.ownership?.ownership_id);
}

function previewTone(preview?: ToolInstallPreview): Tone {
  if (!preview?.preview_available) return 'neutral';
  if (preview.action === 'managed-uninstall-preview') return 'warn';
  if (preview.execution_available) return 'low';
  return 'info';
}

function previewActionLabel(preview?: ToolInstallPreview): string {
  if (!preview?.preview_available) return 'No managed action';
  if (preview.action === 'managed-install-preview') return 'Managed install preview';
  if (preview.action === 'managed-uninstall-preview') return 'Managed uninstall preview';
  if (preview.action === 'pack-install-preview') return 'Pack install preview';
  return humanizeKey(preview.action);
}

function previewOwnedPaths(preview: ToolInstallPreview): string[] {
  return (preview.owned_paths ?? [preview.install_root, preview.binary_path, preview.shim_path])
    .filter((path): path is string => Boolean(path));
}

async function responseErrorMessage(response: Response, fallback: string): Promise<string> {
  const text = await response.text();
  const cleanText = text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  return cleanText || fallback;
}

function humanizeKey(value: string): string {
  const acronyms: Record<string, string> = {
    ai: 'AI',
    api: 'API',
    cve: 'CVE',
    iac: 'IaC',
    ioc: 'IOC',
    mcp: 'MCP',
    osv: 'OSV',
    sbom: 'SBOM',
    scm: 'SCM',
    ssl: 'SSL',
    tls: 'TLS',
  };
  return value
    .split(/[-_]/g)
    .filter(Boolean)
    .map((part) => acronyms[part.toLowerCase()] ?? `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

function countRecord(record?: Record<string, number>): number {
  return Object.values(record ?? {}).reduce((sum, value) => sum + value, 0);
}

function textOrFallback(value: string | number | null | undefined, fallback = 'Not reported'): string {
  if (typeof value === 'number') return String(value);
  if (value?.trim()) return value.trim();
  return fallback;
}

function formatConfidenceValue(value: number): string {
  return `${Math.round(value <= 1 ? value * 100 : value)}%`;
}

function suppressionReasons(summary: DashboardSummary) {
  const direct = summary.suppression_reasons ?? summary.suppressed_counts?.reasons ?? [];
  const fromRepos = summary.repos.flatMap((repo) => repo.suppression_reasons ?? repo.suppressed_counts?.reasons ?? []);
  const grouped = new Map<string, {reason: string; decision_status: string; vex_status: string; cases: number; findings: number}>();
  for (const item of [...direct, ...fromRepos]) {
    const key = `${item.reason}:${item.decision_status}:${item.vex_status}`;
    const current = grouped.get(key) ?? {
      reason: item.reason,
      decision_status: item.decision_status,
      vex_status: item.vex_status,
      cases: 0,
      findings: 0,
    };
    current.cases += item.cases;
    current.findings += item.findings;
    grouped.set(key, current);
  }
  return [...grouped.values()].sort((a, b) => b.findings - a.findings || b.cases - a.cases);
}

function activeFindingCount(summary: DashboardSummary): number {
  return summary.active_findings?.length ?? summary.findings.filter((finding) => !finding.suppressed).length;
}

function suppressedFindingCount(summary: DashboardSummary): number {
  return summary.suppressed_findings?.length ?? summary.findings.filter((finding) => finding.suppressed).length;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [catalogRoute, setCatalogRoute] = useState<CatalogRoute>({kind: 'home'});
  const [summary, setSummary] = useState<DashboardSummary>(emptySummary);
  const [projectRepos, setProjectRepos] = useState<ProjectRepo[]>([]);
  const [customRepos, setCustomRepos] = useState<ProjectRepo[]>(() => loadCustomRepos());
  const [target, setTarget] = useState<TargetSelection>({type: 'dashboard'});
  const [isCheckOpen, setIsCheckOpen] = useState(false);
  const [selectedAudits, setSelectedAudits] = useState<AuditId[]>(defaultAudits);
  const [isRunningCheck, setIsRunningCheck] = useState(false);
  const [activeJob, setActiveJob] = useState<CheckJob | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [agentRunning, setAgentRunning] = useState(true);
  const [search, setSearch] = useState('');

  const loadSummary = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/summary', {cache: 'no-store'});
      if (!response.ok) throw new Error(`Dashboard API returned ${response.status}`);
      setSummary(await response.json());
      setUpdatedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load dashboard data');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    async function loadProjects() {
      try {
        const response = await fetch('/api/projects', {cache: 'no-store'});
        if (!response.ok) throw new Error(`Projects API returned ${response.status}`);
        const payload: ProjectsPayload = await response.json();
        setProjectRepos(payload.repos);
      } catch {
        setProjectRepos([]);
      }
    }
    void loadProjects();
  }, []);

  const targetRepos = mergeProjectRepos(projectRepos, customRepos, summary.repos);
  const scopedSummary = filterSummaryByTarget(summary, target);
  const activeCases = activeCaseList(scopedSummary);
  const posture = {
    score: postureScore(scopedSummary),
    delta: postureDelta(scopedSummary),
    week: postureWeek(scopedSummary),
  };

  useEffect(() => {
    setActiveJob(null);
    setRunError(null);
    if (target.type === 'dashboard') setIsCheckOpen(false);
  }, [target]);

  useEffect(() => {
    if (!activeJob || !isRunningCheck) return;
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`/api/check-status?jobId=${encodeURIComponent(activeJob.id)}`, {cache: 'no-store'});
        if (!response.ok) throw new Error('Unable to read check progress');
        const payload: {job: CheckJob} = await response.json();
        setActiveJob(payload.job);
        if (payload.job.status === 'complete') {
          if (payload.job.summary) setSummary(payload.job.summary);
          else await loadSummary();
          setUpdatedAt(new Date());
          setIsRunningCheck(false);
        }
        if (payload.job.status === 'failed') {
          setRunError(payload.job.error ?? 'Security check failed');
          setIsRunningCheck(false);
        }
      } catch (err) {
        setRunError(err instanceof Error ? err.message : 'Unable to read check progress');
        setIsRunningCheck(false);
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [activeJob, isRunningCheck, loadSummary]);

  function selectTarget(value: string) {
    if (value === 'add-repo') {
      const path = window.prompt('Paste the full path to the repo folder.');
      if (!path?.trim()) return;
      const cleanPath = path.trim().replace(/\/+$/, '');
      const repo = {name: basename(cleanPath), path: cleanPath};
      const nextCustom = mergeProjectRepos([], [...customRepos, repo], []);
      setCustomRepos(nextCustom);
      window.localStorage.setItem(customReposStorageKey, JSON.stringify(nextCustom));
      setTarget({type: 'repo', repo});
      return;
    }
    if (value === 'dashboard') {
      setTarget({type: 'dashboard'});
      return;
    }
    const path = value.replace(/^repo:/, '');
    const repo = targetRepos.find((item) => item.path === path);
    if (repo) setTarget({type: 'repo', repo});
  }

  function toggleAudit(auditId: AuditId) {
    setRunError(null);
    if (activeJob?.status === 'complete') setActiveJob(null);
    if (auditId === 'full') {
      setSelectedAudits(['full']);
      return;
    }
    setSelectedAudits((current) => {
      const withoutFull = current.filter((id) => id !== 'full');
      const next = withoutFull.includes(auditId) ? withoutFull.filter((id) => id !== auditId) : [...withoutFull, auditId];
      return next.length ? next : defaultAudits;
    });
  }

  async function runCheck(auditsOverride = selectedAudits) {
    if (target.type !== 'repo') {
      setRunError('Select a repo target before running checks.');
      setIsCheckOpen(true);
      return;
    }
    setIsRunningCheck(true);
    setActiveJob(null);
    setRunError(null);
    try {
      const response = await fetch('/api/run-check', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({repoPath: target.repo.path, audits: auditsOverride}),
      });
      if (!response.ok) throw new Error(await response.text());
      const payload: {job: CheckJob} = await response.json();
      setActiveJob(payload.job);
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Unable to run security check');
      setIsRunningCheck(false);
    }
  }

  function runFullCheck() {
    setSelectedAudits(['full']);
    setIsCheckOpen(true);
    void runCheck(['full']);
  }

  async function saveCaseDecision(caseId: string, repoName: string, status: CaseDecisionStatus | 'open', note: string) {
    setRunError(null);
    try {
      const response = await fetch('/api/case-decision', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({caseId, repoName, status, note}),
      });
      if (!response.ok) throw new Error(await response.text());
      await loadSummary();
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Unable to save case decision');
    }
  }

  const navCounts: Partial<Record<TabId, number>> = {
    findings: activeCases.length,
    'honey-keys': (scopedSummary.honey_keys ?? []).filter((key) => key.status === 'triggered').length,
    verification: topScannerItems(scopedSummary).filter((item) => item.status === 'missing' || item.status === 'error').length,
  };

  return (
    <div className="mist-viewport">
      <div className="mist-shell">
        <Sidebar
          active={activeTab}
          counts={navCounts}
          target={target}
          targetRepos={targetRepos}
          onTargetChange={selectTarget}
          onNav={setActiveTab}
          agentRunning={agentRunning}
        />
        <main className="mist-main">
          <Toolbar
            title={tabTitles[activeTab]}
            targetLabel={targetLabel(target)}
            posture={posture}
            search={search}
            setSearch={setSearch}
            isLoading={isLoading}
            error={error}
            agentRunning={agentRunning}
            setAgentRunning={setAgentRunning}
            onRunAll={runFullCheck}
            canRun={target.type === 'repo'}
          />
          {isCheckOpen && (
            <RunCheckSheet
              target={target}
              selectedAudits={selectedAudits}
              activeJob={activeJob}
              isRunningCheck={isRunningCheck}
              runError={runError}
              onToggleAudit={toggleAudit}
              onRun={() => void runCheck()}
              onClose={() => setIsCheckOpen(false)}
              onNewCheck={() => setActiveJob(null)}
              onViewResults={() => {
                setIsCheckOpen(false);
                setActiveTab('findings');
              }}
            />
          )}
          <div className="mist-content scroll-area">
            <ActiveView
              tab={activeTab}
              summary={scopedSummary}
              search={search}
              target={target}
              targetRepos={targetRepos}
              updatedAt={updatedAt}
              error={error}
              posture={posture}
              catalogRoute={catalogRoute}
              onCatalogRouteChange={setCatalogRoute}
              onOpenTab={setActiveTab}
              onChooseChecks={() => setIsCheckOpen(true)}
              onRunQuick={() => {
                setSelectedAudits(['quick']);
                setIsCheckOpen(true);
                void runCheck(['quick']);
              }}
              onCaseDecision={saveCaseDecision}
              onRefresh={loadSummary}
              onTargetChange={selectTarget}
            />
          </div>
        </main>
      </div>
    </div>
  );
}

function ActiveView({
  tab,
  summary,
  search,
  target,
  targetRepos,
  updatedAt,
  error,
  posture,
  catalogRoute,
  onCatalogRouteChange,
  onOpenTab,
  onChooseChecks,
  onRunQuick,
  onCaseDecision,
  onRefresh,
  onTargetChange,
}: {
  tab: TabId;
  summary: DashboardSummary;
  search: string;
  target: TargetSelection;
  targetRepos: ProjectRepo[];
  updatedAt: Date | null;
  error: string | null;
  posture: {score: number; delta: number; week: {label: string; value: number}[]};
  catalogRoute: CatalogRoute;
  onCatalogRouteChange: (route: CatalogRoute) => void;
  onOpenTab: (tab: TabId) => void;
  onChooseChecks: () => void;
  onRunQuick: () => void;
  onCaseDecision: (caseId: string, repoName: string, status: CaseDecisionStatus | 'open', note: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  onTargetChange: (value: string) => void;
}) {
  if (target.type === 'repo' && summary.repos.length === 0 && tab !== 'honey-keys' && tab !== 'settings') {
    return <EmptyRepoView repoName={target.repo.name} onRunQuick={onRunQuick} onChooseChecks={onChooseChecks} />;
  }
  if (tab === 'overview') return <OverviewView summary={summary} posture={posture} error={error} onOpenTab={onOpenTab} />;
  if (tab === 'findings') return <FindingsView summary={summary} search={search} onCaseDecision={onCaseDecision} />;
  if (tab === 'honey-keys') return <HoneyKeysView summary={summary} target={target} onRefresh={onRefresh} />;
  if (tab === 'scanners') return <CatalogRouter route={catalogRoute} onRouteChange={onCatalogRouteChange} />;
  if (tab === 'playbooks') return <PlaybooksView summary={summary} onChooseChecks={onChooseChecks} />;
  if (tab === 'verification') return <VerificationView summary={summary} onChooseChecks={onChooseChecks} />;
  if (tab === 'activity') return <ActivityView summary={summary} search={search} />;
  if (tab === 'reports') return <ReportsView summary={summary} />;
  return <SettingsView summary={summary} target={target} targetRepos={targetRepos} updatedAt={updatedAt} onTargetChange={onTargetChange} />;
}

// CatalogRouter — dispatches the Tool Catalog substate to the four route
// shells. Navigation between catalog routes uses callbacks (onOpenTool /
// onOpenPack / onOpenBrowse / onBack); no URL routing yet. The legacy
// CatalogView function below stays exported in this file for Step 1.2 to lift
// data hooks out of, but the tab no longer renders it during the rebuild.
function CatalogRouter({route, onRouteChange}: {route: CatalogRoute; onRouteChange: (route: CatalogRoute) => void}) {
  const originOf = (kind: CatalogRoute['kind']): 'home' | 'browse' => (kind === 'browse' ? 'browse' : 'home');
  if (route.kind === 'browse') {
    return (
      <CatalogBrowse
        onOpenTool={(id) => onRouteChange({kind: 'tool', id, from: 'browse'})}
        onBack={() => onRouteChange({kind: 'home'})}
      />
    );
  }
  if (route.kind === 'tool') {
    return (
      <CatalogToolPage
        toolId={route.id}
        onBack={() => onRouteChange(route.from === 'browse' ? {kind: 'browse'} : {kind: 'home'})}
      />
    );
  }
  if (route.kind === 'pack') {
    return (
      <CatalogPackPage
        packId={route.id}
        onBack={() => onRouteChange(route.from === 'browse' ? {kind: 'browse'} : {kind: 'home'})}
        onOpenTool={(id) => onRouteChange({kind: 'tool', id, from: originOf(route.kind)})}
      />
    );
  }
  return (
    <CatalogHome
      onOpenBrowse={() => onRouteChange({kind: 'browse'})}
      onOpenTool={(id) => onRouteChange({kind: 'tool', id, from: 'home'})}
      onOpenPack={(id) => onRouteChange({kind: 'pack', id, from: 'home'})}
    />
  );
}

function Sidebar({
  active,
  counts,
  target,
  targetRepos,
  onTargetChange,
  onNav,
  agentRunning,
}: {
  active: TabId;
  counts: Partial<Record<TabId, number>>;
  target: TargetSelection;
  targetRepos: ProjectRepo[];
  onTargetChange: (value: string) => void;
  onNav: (tab: TabId) => void;
  agentRunning: boolean;
}) {
  return (
    <aside className="mist-sidebar">
      <div className="dotgrid-dark mist-sidebar-texture" />
      <div className="workspace-card">
        <div className="workspace-mark"><ShieldCheck size={17} /></div>
        <div className="workspace-copy">
          <div className="workspace-title">{targetLabel(target)}</div>
          <select className="workspace-select" value={targetValue(target)} onChange={(event) => onTargetChange(event.target.value)}>
            <option value="dashboard">devsec · dashboard</option>
            {targetRepos.map((repo) => (
              <option key={repo.path} value={`repo:${repo.path}`}>devsec · {repo.name}</option>
            ))}
            <option value="add-repo">+ Add repo...</option>
          </select>
        </div>
        <ChevronDown size={15} className="muted-icon" />
      </div>
      <nav className="sidebar-nav">
        {navGroups.map((group) => (
          <div key={group.title} className="sidebar-group">
            <div className="sidebar-group-title">{group.title}</div>
            {group.items.map((item) => (
              <button key={item.id} type="button" className={`nav-row ${active === item.id ? 'active' : ''}`} onClick={() => onNav(item.id)}>
                <item.icon size={17} />
                <span>{item.label}</span>
                {!!counts[item.id] && <strong>{counts[item.id]}</strong>}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <button type="button" className={`nav-row ${active === 'settings' ? 'active' : ''}`} onClick={() => onNav('settings')}>
          <Settings size={17} />
          <span>Settings</span>
        </button>
        <div className="agent-card">
          <span className={`status-dot ${agentRunning ? 'live' : 'paused'}`} />
          <div>
            <strong>Agent {agentRunning ? 'live' : 'paused'}</strong>
            <span>{agentRunning ? 'tailing scanners' : 'tap resume'}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

function Toolbar({
  title,
  targetLabel,
  posture,
  search,
  setSearch,
  isLoading,
  error,
  agentRunning,
  setAgentRunning,
  onRunAll,
  canRun,
}: {
  title: string;
  targetLabel: string;
  posture: {score: number; delta: number};
  search: string;
  setSearch: (value: string) => void;
  isLoading: boolean;
  error: string | null;
  agentRunning: boolean;
  setAgentRunning: (value: boolean) => void;
  onRunAll: () => void;
  canRun: boolean;
}) {
  const searchPlaceholder = title === 'Tool Catalog' ? 'Search tools, packs' : 'Search findings, manifests';
  return (
    <header className="mist-toolbar">
      <div className="toolbar-title">
        <strong>{title}</strong>
        <span>{targetLabel}</span>
      </div>
      <div className="toolbar-spacer" />
      <div className="posture-pill">
        <span className={`status-dot ${error ? 'paused' : isLoading ? 'syncing' : 'live'}`} />
        <span>Posture</span>
        <strong>{posture.score.toFixed(1)}</strong>
        <em>{posture.delta >= 0 ? `+${posture.delta.toFixed(1)}` : posture.delta.toFixed(1)}</em>
      </div>
      <label className="toolbar-search">
        <Search size={16} />
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={searchPlaceholder} />
        <kbd>⌘K</kbd>
      </label>
      <IconButton label={agentRunning ? 'Pause agent' : 'Resume agent'} onClick={() => setAgentRunning(!agentRunning)}>
        {agentRunning ? <Pause size={15} /> : <Play size={15} />}
      </IconButton>
      <Button variant="secondary" size="sm" icon={<RefreshCw size={14} />} onClick={onRunAll} disabled={!canRun}>
        Run all
      </Button>
    </header>
  );
}

function RunCheckSheet({
  target,
  selectedAudits,
  activeJob,
  isRunningCheck,
  runError,
  onToggleAudit,
  onRun,
  onClose,
  onNewCheck,
  onViewResults,
}: {
  target: TargetSelection;
  selectedAudits: AuditId[];
  activeJob: CheckJob | null;
  isRunningCheck: boolean;
  runError: string | null;
  onToggleAudit: (audit: AuditId) => void;
  onRun: () => void;
  onClose: () => void;
  onNewCheck: () => void;
  onViewResults: () => void;
}) {
  return (
    <section className="run-sheet">
      <div className="run-sheet-head">
        <div>
          <Eyebrow>{activeJob?.status === 'complete' ? 'Security check complete' : 'Run security check'}</Eyebrow>
          <h2>{target.type === 'repo' ? target.repo.name : 'Choose a repo target'}</h2>
          <p>{activeJob?.status === 'complete' ? 'Latest local scan data has been saved.' : 'Choose the scanners to run. Existing backend behavior stays unchanged.'}</p>
        </div>
        <div className="run-actions">
          {activeJob?.status === 'complete' ? (
            <>
              <Button variant="secondary" onClick={onNewCheck}>New check</Button>
              <Button onClick={onViewResults}>View findings</Button>
            </>
          ) : (
            <>
              <Button variant="ghost" onClick={onClose} disabled={isRunningCheck}>Cancel</Button>
              <Button onClick={onRun} disabled={target.type !== 'repo' || isRunningCheck}>{isRunningCheck ? 'Checking...' : 'Start check'}</Button>
            </>
          )}
        </div>
      </div>
      {activeJob?.status !== 'complete' && (
        <div className="audit-grid">
          {auditOptions.map((option) => (
            <label key={option.id} className={`audit-tile ${selectedAudits.includes(option.id) ? 'selected' : ''}`}>
              <input type="checkbox" checked={selectedAudits.includes(option.id)} onChange={() => onToggleAudit(option.id)} disabled={isRunningCheck} />
              <span>{option.label}</span>
              <em>{option.estimate}</em>
              <p>{option.description}</p>
            </label>
          ))}
        </div>
      )}
      {activeJob && isRunningCheck && (
        <div className="job-progress">
          <div className="job-progress-head">
            <strong>{activeJob.currentStep ?? activeJob.message}</strong>
            <span>{Math.round(activeJob.progress)}%</span>
          </div>
          <div className="progress-track"><span style={{width: `${activeJob.progress}%`}} /></div>
          <div className="job-steps">
            {activeJob.steps.map((step) => <span key={step} className={step === activeJob.currentStep ? 'active' : ''}>{step}</span>)}
          </div>
        </div>
      )}
      {activeJob?.status === 'complete' && (
        <div className="complete-grid">
          <MetricBlock label="Health" value={String(activeJob.scan?.health_score ?? 100)} />
          <MetricBlock label="Saved issues" value={String(activeJob.scan?.findings.length ?? 0)} />
          <MetricBlock label="Missing checks" value={String(incompleteToolCount(activeJob.scan))} />
          <MetricBlock label="Duration" value={formatDuration(activeJob.scan?.started_at, activeJob.scan?.finished_at)} />
          {activeJob.scan?.scan_id && (
            <a className="report-link wide" href={reportViewUrl(activeJob.scan.scan_id, 'raw')}>Open raw report <ChevronRight size={15} /></a>
          )}
        </div>
      )}
      {runError && <div className="inline-error">{runError}</div>}
    </section>
  );
}

function OverviewView({summary, posture, error, onOpenTab}: {summary: DashboardSummary; posture: {score: number; delta: number; week: {label: string; value: number}[]}; error: string | null; onOpenTab: (tab: TabId) => void}) {
  const cases = activeCaseList(summary);
  const counts = severityCounts(summary);
  const honeyCounts = honeyKeyCounts(summary);
  const scanners = topScannerItems(summary);
  const catalogCount = toolCatalogItems(summary).length || scanners.length;
  const scannerHealthy = scanners.filter((item) => item.status === 'ran').length;
  const activities = buildActivity(summary);
  const lastScan = latestScanTime(summary);
  const headline = cases[0]
    ? `${severityLabelForCase(cases[0])}: ${cases[0].title}`
    : summary.repos.length
      ? 'Quiet overnight. No active cases from the checks that ran.'
      : 'Choose a repo and run a quick safety sweep.';
  return (
    <div className="view-stack">
      <section className="hero-digest">
        <div className="dotgrid-light hero-dots" />
        <div className="hero-copy">
          <Eyebrow onSurface>Today · {new Intl.DateTimeFormat(undefined, {weekday: 'long', month: 'long', day: 'numeric'}).format(new Date())}</Eyebrow>
          <h1>{headline}</h1>
          <div className="hero-actions">
            <Button variant="glassOnGlass" onClick={() => onOpenTab('findings')}>Open digest</Button>
            <Button variant="glass" icon={<Activity size={15} />} onClick={() => onOpenTab('activity')}>See activity</Button>
          </div>
        </div>
        <div className="hero-metrics">
          <Donut value={posture.score} />
          <div className="posture-big">
            <Eyebrow onSurface>Posture · 30 d</Eyebrow>
            <strong>{posture.score.toFixed(1)}</strong><span>/ 10</span>
            <em>{posture.delta >= 0 ? `+${posture.delta.toFixed(1)}` : posture.delta.toFixed(1)} vs previous</em>
          </div>
          <div className="hero-bars">
            <Eyebrow onSurface>Posture · 7 d</Eyebrow>
            <BarChart data={posture.week} onSurface />
          </div>
        </div>
      </section>

      <section className="kpi-grid">
        <KpiCard title="Open findings" value={String(totalFindings(summary))} detail={`${counts.critical + counts.elevated + counts.warning} non-low`} icon={<ShieldAlert size={18} />} onClick={() => onOpenTab('findings')} />
        <KpiCard title="Honey keys armed" value={String(honeyCounts.active)} detail={honeyCounts.triggered ? `${honeyCounts.triggered} tripped` : 'all quiet'} icon={<ShieldCheck size={18} />} onClick={() => onOpenTab('honey-keys')} />
        <KpiCard title="Tool Catalog" value={`${scannerHealthy} / ${Math.max(scanners.length, 1)}`} detail={`${catalogCount} catalog entries`} icon={<ScanIcon size={18} />} onClick={() => onOpenTab('scanners')} />
      </section>

      {error && <Notice tone="warn" icon={<AlertTriangle size={17} />} title="Dashboard data could not refresh" body="Saved data may be older than shown." />}

      <section className="split-grid wide-left">
        <PaperCard>
          <SectionHeader title="Open findings" right={<button onClick={() => onOpenTab('findings')}>All {cases.length} <ChevronRight size={14} /></button>} />
          <SeverityDistribution counts={counts} />
          <div className="soft-list">
            {cases.slice(0, 5).map((item, index) => <FindingLine key={item.id} item={item} index={index} onClick={() => onOpenTab('findings')} />)}
            {!cases.length && <EmptyLine title="No active cases" detail={lastScan ? `Latest scan ${formatDate(lastScan)}` : 'No scan has run yet'} />}
          </div>
        </PaperCard>
        <PaperCard>
          <SectionHeader title="Recent activity" right={<button onClick={() => onOpenTab('activity')}>All <ChevronRight size={14} /></button>} />
          <ActivityTimelineMini items={activities} />
          <div className="activity-list compact">
            {activities.slice(0, 6).map((item) => <ActivityRow key={item.id} item={item} />)}
            {!activities.length && <EmptyLine title="No activity yet" detail="Run a scan to build the local record." />}
          </div>
        </PaperCard>
      </section>
    </div>
  );
}

function FindingsView({summary, search, onCaseDecision}: {summary: DashboardSummary; search: string; onCaseDecision: (caseId: string, repoName: string, status: CaseDecisionStatus | 'open', note: string) => Promise<void>}) {
  const [severityFilter, setSeverityFilter] = useState<Tone | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const cases = displayCases(summary);
  const suppressed = suppressedDisplayCases(summary);
  const reasons = suppressionReasons(summary);
  const counts = severityCounts(summary);
  const categories = [...new Set(cases.map((item) => item.category).filter(Boolean) as string[])];
  const filtered = cases.filter((item) => {
    if (severityFilter !== 'all' && toneForCase(item) !== severityFilter) return false;
    if (categoryFilter !== 'all' && item.category !== categoryFilter) return false;
    if (search.trim()) {
      const haystack = `${item.title} ${item.why} ${item.location} ${item.nextStep} ${item.category ?? ''}`.toLowerCase();
      if (!haystack.includes(search.toLowerCase())) return false;
    }
    return true;
  });
  const shown = filtered.slice(0, 32);
  const selected = cases.find((item) => item.id === selectedId) ?? filtered[0] ?? null;

  return (
    <div className="view-stack">
      <section className="summary-strip">
        <MetricBlock label="Findings" value={String(cases.length)} detail="open · all sources" />
        <MetricBlock label="Critical" value={String(counts.critical)} tone="crit" />
        <MetricBlock label="Elevated" value={String(counts.elevated)} tone="high" />
        <MetricBlock label="Warning" value={String(counts.warning)} tone="warn" />
        <MetricBlock label="Low / info" value={String(counts.low)} tone="low" />
      </section>
      <PaperCard className="landscape-card">
        <SectionHeader title="Risk landscape · severity × age" right={<span>{cases.filter((item) => toneForCase(item) !== 'low' && relativeAge(item.createdAt).includes('d')).length} non-low findings aged past 24 h</span>} />
        <RiskLandscape items={cases} onPick={setSelectedId} />
      </PaperCard>
      <div className="chip-row">
        <Chip active={severityFilter === 'all'} onClick={() => setSeverityFilter('all')}>All severities</Chip>
        {(['crit', 'high', 'warn', 'low'] as const).map((tone) => (
          <Chip key={tone} active={severityFilter === tone} dot={severityMeta[tone].dot} onClick={() => setSeverityFilter(severityFilter === tone ? 'all' : tone)}>{severityMeta[tone].label}</Chip>
        ))}
        {categories.map((category) => <Chip key={category} active={categoryFilter === category} onClick={() => setCategoryFilter(categoryFilter === category ? 'all' : category)}>{categoryLabel(category)}</Chip>)}
      </div>
      <section className="view-stack tight">
        <PaperCard padded={false}>
          <FindingsTable items={shown} onPick={setSelectedId} />
          {filtered.length > shown.length && (
            <div className="table-note">
              Showing {shown.length} of {filtered.length}. Search or filter to narrow the full local result set.
            </div>
          )}
        </PaperCard>
        {selected ? <CaseDetailCard item={selected} onDecision={onCaseDecision} /> : <PaperCard><EmptyLine title="No active cases" detail="This target has no case matching the current filters." /></PaperCard>}
      </section>
      {!!suppressed.length && (
        <PaperCard>
          <SectionHeader title="Suppressed findings" right={<span>{suppressed.length} cases</span>} />
          <div className="soft-list">
            {suppressed.slice(0, 5).map((item, index) => <FindingLine key={item.id} item={item} index={index} muted />)}
          </div>
        </PaperCard>
      )}
      {!!reasons.length && <SuppressionReasonsCard reasons={reasons} />}
    </div>
  );
}

function HoneyKeysView({summary, target, onRefresh}: {summary: DashboardSummary; target: TargetSelection; onRefresh: () => Promise<void>}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState('Legacy internal API key');
  const [placementPath, setPlacementPath] = useState(placementTemplates[0]);
  const [note, setNote] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isArchiving, setIsArchiving] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedHoneyKey | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [confirmPlacement, setConfirmPlacement] = useState(false);
  const [advancedPlacement, setAdvancedPlacement] = useState(false);
  const [isInserting, setIsInserting] = useState(false);
  const [insertedPath, setInsertedPath] = useState<string | null>(null);
  const [savingIncident, setSavingIncident] = useState<string | null>(null);
  const keys = summary.honey_keys ?? [];
  const counts = honeyKeyCounts(summary);
  const latestEvent = latestOpenHoneyKeyEvent(summary);
  const latestEventKey = latestEvent ? honeyKeyById(summary, latestEvent.honey_key_id) : undefined;
  const selected = keys.find((key) => key.id === selectedId) ?? keys[0] ?? null;
  const selectedEvents = selected ? (summary.honey_key_events ?? []).filter((event) => event.honey_key_id === selected.id) : [];

  async function createHoneyKey() {
    if (target.type !== 'repo') return;
    setIsCreating(true);
    setError(null);
    setCreated(null);
    setInsertedPath(null);
    setConfirmPlacement(false);
    setAdvancedPlacement(false);
    try {
      const response = await fetch('/api/honey/keys', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({repoPath: target.repo.path, repoName: target.repo.name, name, placementPath, note}),
      });
      if (!response.ok) throw new Error(await response.text());
      const payload: CreatedHoneyKey = await response.json();
      setCreated(payload);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create Honey Key');
    } finally {
      setIsCreating(false);
    }
  }

  async function archiveHoneyKey(keyId: string) {
    setIsArchiving(keyId);
    setError(null);
    try {
      const response = await fetch('/api/honey/archive', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: keyId}),
      });
      if (!response.ok) throw new Error(await response.text());
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to archive Honey Key');
    } finally {
      setIsArchiving(null);
    }
  }

  async function updateIncidentStep(eventId: string, step: IncidentStep, complete: boolean) {
    setSavingIncident(`${eventId}:${step}`);
    setError(null);
    try {
      const response = await fetch('/api/honey/incident-step', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({eventId, step, complete}),
      });
      if (!response.ok) throw new Error(await response.text());
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update incident');
    } finally {
      setSavingIncident(null);
    }
  }

  async function closeIncident(event: HoneyKeyEvent) {
    const needsNote = !event.incident?.archived_reset;
    const acceptedRiskNote = needsNote ? window.prompt('Add an accepted-risk note before closing this incident.') : '';
    if (acceptedRiskNote === null) return;
    setSavingIncident(`${event.id}:close`);
    setError(null);
    try {
      const response = await fetch('/api/honey/incident-close', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({eventId: event.id, acceptedRiskNote}),
      });
      if (!response.ok) throw new Error(await response.text());
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to close incident');
    } finally {
      setSavingIncident(null);
    }
  }

  async function copyText(label: string, value: string) {
    await navigator.clipboard.writeText(value);
    setCopied(label);
    window.setTimeout(() => setCopied(null), 1800);
  }

  async function insertDecoyFile() {
    if (target.type !== 'repo' || !created) return;
    const snippet = created.snippets[placementPath] ?? created.snippets[Object.keys(created.snippets)[0]];
    if (!snippet) return;
    const safePlacementPath = `.devsec/honeykeys/${created.key.id}-${placementPath.replace(/[^A-Za-z0-9_.-]+/g, '-')}`;
    const insertPath = advancedPlacement ? placementPath : safePlacementPath;
    setIsInserting(true);
    setError(null);
    setInsertedPath(null);
    try {
      const response = await fetch('/api/honey/insert', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: created.key.id, repoPath: target.repo.path, placementPath: insertPath, snippet, confirmPlacement, advancedPlacement}),
      });
      if (!response.ok) throw new Error(await response.text());
      const payload: {path: string; relative_path: string} = await response.json();
      setInsertedPath(payload.relative_path);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to insert decoy file');
    } finally {
      setIsInserting(false);
    }
  }

  return (
    <div className="view-stack">
      <section className="summary-strip">
        <MetricBlock label="Armed" value={String(counts.active)} detail="placed across surfaces" icon={<ShieldCheck size={17} />} />
        <MetricBlock label="Tripped" value={String(counts.triggered)} detail={latestEvent ? `last trip · ${relativeAge(latestEvent.triggered_at)}` : 'last trip · none'} tone={counts.triggered ? 'crit' : 'neutral'} icon={<AlertTriangle size={17} />} />
        <MetricBlock label="Allow-listed hits" value={String((summary.honey_key_events ?? []).filter((event) => event.incident?.closed_at).length)} detail="closed incidents" icon={<CheckCircle2 size={17} />} />
        <MetricBlock label="Archived" value={String(counts.archived)} detail="retired / expired" icon={<Clock3 size={17} />} />
      </section>
      {latestEvent && (
        <section className="hero-alert">
          <div>
            <Eyebrow onSurface>Honey-key trip</Eyebrow>
            <h2>{latestEventKey?.name ?? latestEvent.honey_key_id}</h2>
            <p>{latestEvent.ip_address ?? 'Unknown IP'} · {latestEvent.user_agent ?? 'Unknown agent'}</p>
          </div>
          <Button variant="glassOnGlass" onClick={() => setSelectedId(latestEvent.honey_key_id)}>Open investigation</Button>
        </section>
      )}
      <PaperCard>
        <SectionHeader title="Tenure · how long each key has been quiet" right={<span>{keys.length ? `longest silence · ${Math.max(...keys.map((key) => quietDays(key)))} days` : 'No keys yet'}</span>} />
        <HoneyTenure keys={keys} onPick={setSelectedId} />
      </PaperCard>
      <section className="split-grid wide-left align-start">
        <div className="view-stack tight">
          <div className="section-title-row">
            <Eyebrow>Deployed Honey Keys · {keys.length} total</Eyebrow>
            <Button variant="secondary" size="sm" icon={<Plus size={14} />} onClick={() => document.getElementById('new-honey-key')?.scrollIntoView({block: 'center'})}>Place new key</Button>
          </div>
          {keys.map((key) => <HoneyKeyCard key={key.id} honeyKey={key} selected={selected?.id === key.id} onClick={() => setSelectedId(key.id)} onArchive={archiveHoneyKey} isArchiving={isArchiving === key.id} />)}
          {!keys.length && <PaperCard><EmptyLine title="No Honey Keys deployed" detail="Create a repo-targeted decoy to start the tripwire." /></PaperCard>}
        </div>
        <div className="view-stack tight">
          <HoneyCreatePanel
            target={target}
            name={name}
            setName={setName}
            placementPath={placementPath}
            setPlacementPath={setPlacementPath}
            note={note}
            setNote={setNote}
            isCreating={isCreating}
            onCreate={createHoneyKey}
            id="new-honey-key"
          />
          {selected && <HoneyDetailPanel honeyKey={selected} events={selectedEvents} />}
          {latestEvent && <HoneyEventEvidence event={latestEvent} />}
          {latestEvent && (
            <IncidentChecklist event={latestEvent} incident={latestEvent.incident} savingIncident={savingIncident} onToggle={updateIncidentStep} onClose={closeIncident} />
          )}
        </div>
      </section>
      {created && (
        <PaperCard>
          <SectionHeader title="Copy decoy snippet" right={<Button size="sm" variant="secondary" icon={<Copy size={14} />} onClick={() => copyText('raw-token', created.raw_token)}>{copied === 'raw-token' ? 'Copied' : 'Copy raw key'}</Button>} />
          <p className="muted-body">This is the only time the raw Honey Key is shown. DëvSec stores only a secure hash plus metadata.</p>
          <div className="snippet-grid">
            {Object.entries(created.snippets).map(([template, snippet]) => (
              <div key={template} className="snippet-card">
                <div><strong>{template}</strong><button onClick={() => copyText(template, snippet)}>{copied === template ? 'Copied' : 'Copy'}</button></div>
                <pre>{snippet}</pre>
              </div>
            ))}
          </div>
          {target.type === 'repo' && (
            <div className="safe-insert">
              <strong>Safe file insert</strong>
              <p>DëvSec can create an inert decoy file under <code>.devsec/honeykeys/</code>. It will not overwrite existing files or write outside the repo.</p>
              <label><input type="checkbox" checked={advancedPlacement} onChange={(event) => setAdvancedPlacement(event.target.checked)} /> Advanced placement: use <code>{placementPath}</code></label>
              <label><input type="checkbox" checked={confirmPlacement} onChange={(event) => setConfirmPlacement(event.target.checked)} /> I confirm this is a deliberate decoy placement.</label>
              <Button onClick={insertDecoyFile} disabled={!confirmPlacement || isInserting || Boolean(insertedPath)}>{isInserting ? 'Inserting...' : insertedPath ? 'Inserted' : 'Insert decoy file'}</Button>
              {insertedPath && <span>Created <code>{insertedPath}</code>. Review it before committing.</span>}
            </div>
          )}
        </PaperCard>
      )}
      {error && <Notice tone="crit" icon={<AlertTriangle size={17} />} title="Honey Key action failed" body={error} />}
    </div>
  );
}

function CatalogView({summary, search, onChooseChecks, onRefresh}: {summary: DashboardSummary; search: string; onChooseChecks: () => void; onRefresh: () => Promise<void>}) {
  const catalog = toolCatalogItems(summary);
  if (!catalog.length) return <ScannerDoctorFallback summary={summary} onChooseChecks={onChooseChecks} />;
  return <ToolCatalogBrowse summary={summary} catalog={catalog} search={search} onChooseChecks={onChooseChecks} onRefresh={onRefresh} />;
}

function ToolCatalogBrowse({
  summary,
  catalog,
  search,
  onChooseChecks,
  onRefresh,
}: {
  summary: DashboardSummary;
  catalog: ToolCatalogItem[];
  search: string;
  onChooseChecks: () => void;
  onRefresh: () => Promise<void>;
}) {
  const runtime = catalogRuntimeMap(summary);
  const packs = securityPackItems(summary);
  const [categoryFilter, setCategoryFilter] = useState<ToolCategory | 'all'>('all');
  const [packFilter, setPackFilter] = useState<ToolPackId | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<CatalogStatusFilter>('all');
  const [activeId, setActiveId] = useState<string | null>(catalog[0]?.id ?? null);
  const [activePackId, setActivePackId] = useState<ToolPackId | null>(packs[0]?.id ?? null);
  const [mutation, setMutation] = useState<CatalogMutationState>(null);
  const query = search.trim().toLowerCase();

  const installManagedTool = useCallback(async (toolId: string) => {
    setMutation({toolId, kind: 'install', status: 'running', message: 'Installing managed copy...'});
    try {
      const response = await fetch('/api/managed-tools/install', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({toolId, confirmManagedInstall: true}),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Managed install failed.'));
      await onRefresh();
      setMutation({toolId, kind: 'install', status: 'complete', message: 'Managed copy installed and catalog refreshed.'});
    } catch (err) {
      setMutation({toolId, kind: 'install', status: 'error', message: err instanceof Error ? err.message : 'Managed install failed.'});
    }
  }, [onRefresh]);

  const uninstallManagedTool = useCallback(async (toolId: string, ownershipId?: string | null) => {
    if (!ownershipId) {
      setMutation({toolId, kind: 'uninstall', status: 'error', message: 'DëvSec ownership evidence is missing, so uninstall is blocked.'});
      return;
    }
    setMutation({toolId, kind: 'uninstall', status: 'running', message: 'Removing managed copy...'});
    try {
      const response = await fetch('/api/managed-tools/uninstall', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({toolId, ownershipId, confirmManagedUninstall: true}),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Managed uninstall failed.'));
      await onRefresh();
      setMutation({toolId, kind: 'uninstall', status: 'complete', message: 'Managed copy removed; detected user-owned tools were left alone.'});
    } catch (err) {
      setMutation({toolId, kind: 'uninstall', status: 'error', message: err instanceof Error ? err.message : 'Managed uninstall failed.'});
    }
  }, [onRefresh]);

  const categories = useMemo(
    () => catalogCategoryOrder.filter((category) => catalog.some((item) => item.category === category && item.lifecycle !== 'hidden')),
    [catalog],
  );
  const packSummaries = useMemo(
    () => catalogPackOrder
      .map((packId) => {
        const matching = catalog.filter((item) => item.packs.some((pack) => pack.pack_id === packId));
        return {
          id: packId,
          label: catalogPackLabels[packId],
          count: matching.length,
          ready: matching.filter((item) => catalogStatusBucket(item) === 'ready').length,
          future: matching.filter((item) => item.packs.some((pack) => pack.pack_id === packId && pack.role === 'coming-soon')).length,
        };
      })
      .filter((pack) => pack.count > 0),
    [catalog],
  );
  const packCards = useMemo(
    () => catalogPackOrder
      .map((packId) => packs.find((pack) => pack.id === packId))
      .filter((pack): pack is SecurityPackCatalogItem => Boolean(pack)),
    [packs],
  );
  const filteredPacks = useMemo(
    () => packCards.filter((pack) => {
      return !query || securityPackSearchText(pack).includes(query);
    }),
    [packCards, query],
  );

  const activeCatalog = useMemo(
    () => catalog.filter((item) => item.lifecycle !== 'hidden' && catalogStatusBucket(item) !== 'coming-soon'),
    [catalog],
  );
  const futureCatalog = useMemo(
    () => catalog.filter((item) => item.lifecycle !== 'hidden' && catalogStatusBucket(item) === 'coming-soon'),
    [catalog],
  );
  const browseCatalog = statusFilter === 'coming-soon' ? futureCatalog : activeCatalog;
  const filteredCatalog = useMemo(
    () => browseCatalog.filter((item) => {
      if (!shouldShowAdvancedCatalogItem(item, search, categoryFilter, packFilter, statusFilter)) return false;
      if (categoryFilter !== 'all' && item.category !== categoryFilter) return false;
      if (packFilter !== 'all' && !item.packs.some((pack) => pack.pack_id === packFilter)) return false;
      if (statusFilter !== 'all' && catalogStatusBucket(item) !== statusFilter) return false;
      return !query || catalogSearchText(item).includes(query);
    }),
    [browseCatalog, categoryFilter, packFilter, query, search, statusFilter],
  );
  const futureMatches = useMemo(
    () => statusFilter === 'coming-soon' ? [] : futureCatalog.filter((item) => {
      if (categoryFilter !== 'all' && item.category !== categoryFilter) return false;
      if (packFilter !== 'all' && !item.packs.some((pack) => pack.pack_id === packFilter)) return false;
      return !query || catalogSearchText(item).includes(query);
    }),
    [categoryFilter, futureCatalog, packFilter, query, statusFilter],
  );

  useEffect(() => {
    const visible = [...filteredCatalog, ...futureMatches];
    if (activeId && visible.some((item) => item.id === activeId)) return;
    setActiveId(visible[0]?.id ?? catalog[0]?.id ?? null);
  }, [activeId, catalog, filteredCatalog, futureMatches]);

  useEffect(() => {
    if (!packCards.length) return;
    if (activePackId && packCards.some((pack) => pack.id === activePackId)) return;
    setActivePackId(packCards[0].id);
  }, [activePackId, packCards]);

  const active = catalog.find((item) => item.id === activeId) ?? filteredCatalog[0] ?? futureMatches[0] ?? catalog[0] ?? null;
  const activePack = packCards.find((pack) => pack.id === activePackId) ?? filteredPacks[0] ?? packCards[0] ?? null;
  const readyCount = activeCatalog.filter((item) => catalogStatusBucket(item) === 'ready').length;
  const setupCount = activeCatalog.filter((item) => catalogStatusBucket(item) === 'setup' || catalogStatusBucket(item) === 'missing').length;
  const riskyCount = catalog.filter((item) => item.derived_labels.safety.some((label) => safetyLabelTone(label) === 'warn' || safetyLabelTone(label) === 'crit')).length;
  const stateCounts = catalog.reduce<Record<ToolInstallState, number>>((counts, item) => {
    counts[item.install_state] += 1;
    return counts;
  }, {'built-in': 0, managed: 0, detected: 0, missing: 0, unavailable: 0, 'not-configured': 0, 'coming-soon': 0});

  return (
    <div className="view-stack catalog-view">
      <section className="catalog-hero">
        <div>
          <Eyebrow>Tool Catalog</Eyebrow>
          <h1>Security capability, with the safety rules visible.</h1>
          <p>Browse tools by job, local readiness, pack membership, and safety boundary before choosing a scan profile.</p>
        </div>
        <div className="catalog-hero-metrics">
          <MetricBlock label="Tools" value={String(catalog.length)} detail="catalog entries" />
          <MetricBlock label="Ready" value={String(readyCount)} detail="built in or detected" tone="low" />
          <MetricBlock label="Setup gaps" value={String(setupCount)} detail="missing or needs setup" tone={setupCount ? 'info' : 'low'} />
          <MetricBlock label="Bounded" value={String(riskyCount)} detail="network, credentials, approval" tone={riskyCount ? 'warn' : 'low'} />
        </div>
      </section>

      <section className="catalog-state-strip" aria-label="Catalog install states">
        {([
          ['built-in', 'Built in'],
          ['managed', 'DëvSec managed'],
          ['detected', 'Detected locally'],
          ['missing', 'Missing'],
          ['not-configured', 'Needs setup'],
          ['unavailable', 'Unavailable'],
          ['coming-soon', 'Display only'],
        ] as [ToolInstallState, string][]).map(([state, label]) => (
          <span key={state} className="catalog-state-chip">
            <strong>{stateCounts[state]}</strong>
            <span>{label}</span>
          </span>
        ))}
      </section>

      {!!packCards.length && (
        <section className="catalog-pack-pages">
          <div className="catalog-pack-page-list">
            <SectionHeader title="Security Packs" right={<span>{filteredPacks.length} shown</span>} />
            <div className="catalog-pack-page-grid">
              {filteredPacks.map((pack) => (
                <CatalogPackPageCard
                  key={pack.id}
                  pack={pack}
                  selected={activePack?.id === pack.id}
                  onClick={() => setActivePackId(pack.id)}
                />
              ))}
              {!filteredPacks.length && <PaperCard className="catalog-empty"><EmptyLine title="No packs match this view" detail="Adjust search or clear the pack filter to see the pack pages." /></PaperCard>}
            </div>
          </div>
          <PaperCard className="catalog-pack-side">
            {activePack ? (
              <CatalogSelectedPack
                pack={activePack}
                catalog={catalog}
                mutation={mutation}
                onChooseChecks={onChooseChecks}
                onSelectTool={(toolId) => setActiveId(toolId)}
                onInstallTool={installManagedTool}
                onUninstallTool={uninstallManagedTool}
              />
            ) : (
              <EmptyLine title="No pack selected" detail="Security Pack pages appear here when the API publishes them." />
            )}
          </PaperCard>
        </section>
      )}

      <section className="catalog-controls">
        <div className="catalog-filter-row">
          <span>Category</span>
          <Chip active={categoryFilter === 'all'} onClick={() => setCategoryFilter('all')}>All</Chip>
          {categories.map((category) => (
            <Chip key={category} active={categoryFilter === category} onClick={() => setCategoryFilter(category)}>
              {catalogCategoryLabels[category]}
            </Chip>
          ))}
        </div>
        <div className="catalog-filter-row">
          <span>Status</span>
          {catalogStatusFilters.map((status) => (
            <Chip key={status.id} active={statusFilter === status.id} onClick={() => setStatusFilter(status.id)}>
              {status.label}
            </Chip>
          ))}
        </div>
        <div className="catalog-filter-row">
          <span>Pack</span>
          <Chip active={packFilter === 'all'} onClick={() => setPackFilter('all')}>All</Chip>
          {catalogPackOrder.filter((packId) => packCards.length ? packCards.some((pack) => pack.id === packId) : packSummaries.some((pack) => pack.id === packId)).map((packId) => (
            <Chip key={packId} active={packFilter === packId} onClick={() => {
              setPackFilter(packId);
              setActivePackId(packId);
            }}>
              {catalogPackLabels[packId]}
            </Chip>
          ))}
        </div>
      </section>

      {!packCards.length && !!packSummaries.length && (
        <section className="catalog-pack-strip">
          {packSummaries.map((pack) => (
            <button key={pack.id} type="button" className={`catalog-pack-card ${packFilter === pack.id ? 'selected' : ''}`} onClick={() => setPackFilter(pack.id === packFilter ? 'all' : pack.id)}>
              <span>{catalogIcon(catalogPackIconCategory(pack.id))}</span>
              <strong>{pack.label}</strong>
              <div className="catalog-pack-meta">
                <em>{pack.ready ? `${pack.ready} ready` : `${pack.count} entries`}</em>
                {!!pack.future && <em>{pack.future} display only</em>}
              </div>
            </button>
          ))}
        </section>
      )}

      <section className="catalog-layout">
        <div className="catalog-grid">
          {filteredCatalog.length ? filteredCatalog.map((item) => (
            <CatalogToolCard key={item.id} item={item} runtime={item.scanner_key ? runtime.get(item.scanner_key) : undefined} selected={active?.id === item.id} onClick={() => setActiveId(item.id)} />
          )) : (
            <PaperCard className="catalog-empty">
              <EmptyLine title={statusFilter === 'coming-soon' ? 'No display-only entries match this view' : 'No tools match this view'} detail="Adjust category, status, pack, or search to widen the catalog." />
            </PaperCard>
          )}
        </div>
        <PaperCard className="catalog-side">
          {active ? (
            <CatalogSelectedTool
              summary={summary}
              item={active}
              runtime={active.scanner_key ? runtime.get(active.scanner_key) : undefined}
              mutation={mutation}
              onChooseChecks={onChooseChecks}
              onInstallTool={installManagedTool}
              onUninstallTool={uninstallManagedTool}
            />
          ) : (
            <EmptyLine title="No catalog entry selected" detail="Choose a tool card to see readiness and safety context." />
          )}
        </PaperCard>
      </section>

      {!!futureMatches.length && (
        <section className="catalog-future">
          <SectionHeader title="Future coverage" right={<span>{futureMatches.length} display-only</span>} />
          <p className="catalog-future-note">Display-only entries stay educational until DëvSec has the approval controls to run them safely.</p>
          <div className="catalog-future-grid">
            {futureMatches.map((item) => (
              <CatalogFutureCard key={item.id} item={item} selected={active?.id === item.id} onClick={() => setActiveId(item.id)} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function CatalogPackPageCard({pack, selected, onClick}: {pack: SecurityPackCatalogItem; selected: boolean; onClick: () => void}) {
  const category = catalogPackIconCategory(pack.id);
  return (
    <button type="button" className={`catalog-pack-page-card ${selected ? 'selected' : ''}`} data-category={category} aria-pressed={selected} onClick={onClick}>
      <span className="catalog-icon">{catalogIcon(category)}</span>
      <div>
        <div className="catalog-card-top">
          <SeverityPill tone={securityPackTone(pack)} label={securityPackStateLabel(pack)} />
          <em>{pack.tools.length} tools</em>
        </div>
        <strong>{pack.label}</strong>
        <p>{pack.summary}</p>
        <div className="catalog-pack-meta">
          <em>{pack.ready_count} ready</em>
          {!!pack.missing_count && <em>{pack.missing_count} missing</em>}
          {!!pack.display_only_count && <em>{pack.display_only_count} display only</em>}
        </div>
      </div>
    </button>
  );
}

function CatalogSelectedPack({
  pack,
  catalog,
  mutation,
  onChooseChecks,
  onSelectTool,
  onInstallTool,
  onUninstallTool,
}: {
  pack: SecurityPackCatalogItem;
  catalog: ToolCatalogItem[];
  mutation: CatalogMutationState;
  onChooseChecks: () => void;
  onSelectTool: (toolId: string) => void;
  onInstallTool: (toolId: string) => void | Promise<void>;
  onUninstallTool: (toolId: string, ownershipId?: string | null) => void | Promise<void>;
}) {
  const toolMap = useMemo(() => new Map(catalog.map((item) => [item.id, item])), [catalog]);
  const category = catalogPackIconCategory(pack.id);
  const isRealPack = pack.mvp_state === 'real';
  const profileNames = [pack.primary_profile, ...pack.secondary_profiles].filter((profile): profile is string => Boolean(profile));
  return (
    <div className="catalog-pack-page" data-category={category}>
      <div className="catalog-detail-head">
        <span className="catalog-icon large">{catalogIcon(category)}</span>
        <div>
          <Eyebrow>{isRealPack ? 'MVP Security Pack' : 'Coming Soon Security Pack'}</Eyebrow>
          <h2>{pack.label}</h2>
        </div>
      </div>
      <div className="catalog-detail-status">
        <SeverityPill tone={securityPackTone(pack)} label={securityPackStateLabel(pack)} />
        <SeverityPill tone={pack.visibility.includes('advanced') ? 'info' : 'neutral'} label={humanizeKey(pack.visibility)} />
      </div>
      <p className="catalog-detail-summary">{pack.summary}</p>

      <div className="catalog-pack-scoreboard">
        <MetricBlock label="Ready" value={String(pack.ready_count)} detail="built in, managed, or detected" tone="low" />
        <MetricBlock label="Missing" value={String(pack.missing_count)} detail="evidence gaps" tone={pack.missing_count ? 'info' : 'low'} />
        <MetricBlock label="Display only" value={String(pack.display_only_count)} detail="future coverage" />
      </div>

      <CatalogDetailSection title="Recommended scan profile" icon={<SlidersHorizontal size={15} />}>
        {isRealPack ? (
          <>
            <div className="catalog-profile-list">
              {profileNames.map((profile, index) => (
                <span key={profile} className={`catalog-profile-pill ${index === 0 ? 'low' : 'neutral'}`}>
                  <strong>{profile}</strong>
                  <em>{index === 0 ? 'Primary' : 'Secondary'}</em>
                </span>
              ))}
            </div>
            <p>Scan profiles stay as the execution surface; this pack explains and prepares the capability.</p>
            <Button icon={<SlidersHorizontal size={14} />} onClick={onChooseChecks} disabled={!profileNames.length}>Choose profile</Button>
          </>
        ) : (
          <Notice tone="info" icon={<CircleSlash size={16} />} title="Display only" body="This pack has no install, uninstall, target input, scan, or Agent Lab action in this version." />
        )}
      </CatalogDetailSection>

      <CatalogDetailSection title="Included tools" icon={<ClipboardList size={15} />}>
        <div className="catalog-pack-tool-list">
          {pack.tools.map((tool) => (
            <CatalogPackToolRow
              key={`${pack.id}:${tool.id}`}
              tool={tool}
              catalogTool={toolMap.get(tool.id)}
              onSelectTool={() => onSelectTool(tool.id)}
            />
          ))}
        </div>
      </CatalogDetailSection>

      <CatalogPackPreviewPanel
        pack={pack}
        catalog={catalog}
        mutation={mutation}
        onInstallTool={onInstallTool}
        onUninstallTool={onUninstallTool}
      />
    </div>
  );
}

function CatalogPackToolRow({tool, catalogTool, onSelectTool}: {tool: SecurityPackTool; catalogTool?: ToolCatalogItem; onSelectTool: () => void}) {
  const labels = tool.derived_labels?.safety?.slice(0, 3) ?? catalogTool?.derived_labels.safety.slice(0, 3) ?? [];
  const preview = tool.install_preview ?? catalogTool?.install_preview;
  return (
    <button type="button" className="catalog-pack-tool-row" onClick={onSelectTool}>
      <div>
        <strong>{tool.label}</strong>
        <span>{humanizeKey(tool.role)}{tool.default_enabled ? ' · default' : ''}</span>
      </div>
      <p>{tool.summary}</p>
      <div className="catalog-label-row">
        <CatalogLabel label={catalogInstallLabels[tool.install_state]} />
        {labels.map((label) => <CatalogLabel key={label} label={label} />)}
        {preview?.preview_available && <CatalogLabel label={previewActionLabel(preview)} />}
      </div>
      <ChevronRight size={16} />
    </button>
  );
}

function CatalogPackPreviewPanel({
  pack,
  catalog,
  mutation,
  onInstallTool,
  onUninstallTool,
}: {
  pack: SecurityPackCatalogItem;
  catalog: ToolCatalogItem[];
  mutation: CatalogMutationState;
  onInstallTool: (toolId: string) => void | Promise<void>;
  onUninstallTool: (toolId: string, ownershipId?: string | null) => void | Promise<void>;
}) {
  const preview = pack.install_preview;
  const toolPreviews = (preview.tool_previews ?? []).filter((item) => item.preview_available);
  const toolLabel = (toolId?: string) => catalog.find((item) => item.id === toolId)?.label ?? humanizeKey(toolId ?? 'tool');
  return (
    <CatalogDetailSection title="Install preview" icon={<Download size={15} />}>
      <Notice
        tone={pack.mvp_state === 'real' ? 'info' : 'neutral'}
        icon={pack.mvp_state === 'real' ? <Download size={16} /> : <CircleSlash size={16} />}
        title={pack.mvp_state === 'real' ? 'Pack install stays preview-only' : 'No pack install'}
        body={preview.execution_reason ?? 'Broad pack installation is not available in this version.'}
      />
      {!!preview.notes?.length && (
        <ul className="catalog-detail-list">
          {preview.notes.map((note) => <li key={note}><ListChecks size={14} /><span>{note}</span></li>)}
        </ul>
      )}
      {toolPreviews.length ? (
        <div className="catalog-managed-preview-list">
          {toolPreviews.map((toolPreview) => (
            <CatalogManagedPreview
              key={`${pack.id}:${toolPreview.tool_id}:${toolPreview.action}`}
              preview={toolPreview}
              toolLabel={toolLabel(toolPreview.tool_id)}
              mutation={mutation}
              onInstallTool={onInstallTool}
              onUninstallTool={onUninstallTool}
            />
          ))}
        </div>
      ) : (
        <span className="catalog-muted-line">No approved managed-tool action is available from this pack.</span>
      )}
    </CatalogDetailSection>
  );
}

function CatalogManagedPreview({
  preview,
  toolLabel,
  mutation,
  onInstallTool,
  onUninstallTool,
}: {
  preview: ToolInstallPreview;
  toolLabel: string;
  mutation: CatalogMutationState;
  onInstallTool: (toolId: string) => void | Promise<void>;
  onUninstallTool: (toolId: string, ownershipId?: string | null) => void | Promise<void>;
}) {
  const toolId = preview.tool_id ?? '';
  const currentMutation = mutation?.toolId === toolId ? mutation : null;
  const isBusy = currentMutation?.status === 'running';
  const paths = previewOwnedPaths(preview);
  return (
    <div className={`catalog-managed-preview ${previewTone(preview)}`}>
      <div className="catalog-managed-preview-head">
        <div>
          <SeverityPill tone={previewTone(preview)} label={previewActionLabel(preview)} />
          <strong>{toolLabel}</strong>
          <p>{preview.execution_reason ?? 'DëvSec has published a bounded managed-tool preview for this tool.'}</p>
        </div>
        <div className="catalog-managed-preview-actions">
          {previewCanInstall(preview) && (
            <Button size="sm" icon={<Download size={14} />} onClick={() => void onInstallTool(toolId)} disabled={isBusy}>Install managed copy</Button>
          )}
          {previewCanUninstall(preview) && (
            <Button size="sm" variant="secondary" icon={<RotateCcw size={14} />} onClick={() => void onUninstallTool(toolId, preview.ownership?.ownership_id)} disabled={isBusy}>Uninstall managed copy</Button>
          )}
        </div>
      </div>
      <div className="catalog-kv-grid">
        <KV label="Version" value={preview.target_version_label ?? preview.ownership?.version ?? preview.target_version ?? 'Not specified'} />
        <KV label="Network" value={preview.network_access ? 'Download required' : 'No network for action'} />
        <KV label="Detected tools" value={preview.leaves_detected_tools_alone ? 'Left alone' : 'Not reported'} />
        <KV label="Boundary" value={preview.uninstall_boundary ?? 'No file removal outside managed-tool ownership.'} />
      </div>
      {!!paths.length && (
        <ul className="catalog-path-list">
          {paths.slice(0, 4).map((path) => <li key={path}>{path}</li>)}
        </ul>
      )}
      {!!preview.notes?.length && <p className="catalog-action-help">{preview.notes.join(' ')}</p>}
      {currentMutation && <Notice tone={currentMutation.status === 'error' ? 'crit' : currentMutation.status === 'running' ? 'info' : 'low'} icon={currentMutation.status === 'error' ? <AlertTriangle size={16} /> : <RefreshCw size={16} />} title={currentMutation.status === 'running' ? 'Working' : currentMutation.status === 'complete' ? 'Updated' : 'Action blocked'} body={currentMutation.message} />}
    </div>
  );
}

function ScannerDoctorFallback({summary, onChooseChecks}: {summary: DashboardSummary; onChooseChecks: () => void}) {
  const scanners = topScannerItems(summary);
  const [activeId, setActiveId] = useState<string | null>(null);
  const active = scanners.find((item) => item.scanner === activeId) ?? scanners[0] ?? null;
  const ran = scanners.filter((item) => item.status === 'ran').length;
  const missing = scanners.filter((item) => item.status === 'missing' || item.status === 'error').length;
  return (
    <div className="view-stack">
      <section className="summary-strip">
        <MetricBlock label="Scanners" value={String(scanners.length)} detail="registered checks" />
        <MetricBlock label="Running on cadence" value={String(ran)} tone="low" />
        <MetricBlock label="Need attention" value={String(missing)} tone={missing ? 'warn' : 'low'} />
        <MetricBlock label="Findings" value={String(scanners.reduce((sum, item) => sum + item.findings, 0))} />
      </section>
      <section className="split-grid wide-left align-start">
        <div className="scanner-grid">
          {scanners.map((item) => <ScannerCard key={item.scanner} item={item} selected={active?.scanner === item.scanner} onClick={() => setActiveId(item.scanner)} />)}
        </div>
        <PaperCard>
          {active ? (
            <ScannerDetail item={active} onChooseChecks={onChooseChecks} />
          ) : (
            <EmptyLine title="No scanner catalog" detail="Run a scan to populate scanner coverage." />
          )}
        </PaperCard>
      </section>
    </div>
  );
}

function CatalogToolCard({item, runtime, selected, onClick}: {item: ToolCatalogItem; runtime?: ScannerDoctorItem; selected: boolean; onClick: () => void}) {
  const statusLabel = catalogStatusLabel(item, runtime);
  const safetyLabels = item.derived_labels.safety.slice(0, 3);
  return (
    <button type="button" className={`catalog-tool-card ${selected ? 'selected' : ''}`} data-category={item.category} aria-pressed={selected} onClick={onClick}>
      <div className="catalog-card-top">
        <span className="catalog-icon">{catalogIcon(item.category)}</span>
        <SeverityPill tone={catalogStatusTone(item, runtime)} label={statusLabel} />
      </div>
      <strong>{item.label}</strong>
      <p>{item.summary}</p>
      <div className="catalog-label-row">
        {safetyLabels.map((label) => <CatalogLabel key={label} label={label} />)}
      </div>
      <div className="catalog-pack-row">
        {item.packs.slice(0, 3).map((pack) => (
          <span key={`${item.id}:${pack.pack_id}`} className={pack.role === 'coming-soon' ? 'muted' : ''}>
            {catalogPackLabels[pack.pack_id]}
          </span>
        ))}
      </div>
      <div className="catalog-card-foot">
        <span>{item.profiles.slice(0, 2).join(', ') || catalogLifecycleLabels[item.lifecycle]}</span>
        <em>View details</em>
      </div>
    </button>
  );
}

function CatalogSelectedTool({
  summary,
  item,
  runtime,
  mutation,
  onChooseChecks,
  onInstallTool,
  onUninstallTool,
}: {
  summary: DashboardSummary;
  item: ToolCatalogItem;
  runtime?: ScannerDoctorItem;
  mutation: CatalogMutationState;
  onChooseChecks: () => void;
  onInstallTool: (toolId: string) => void | Promise<void>;
  onUninstallTool: (toolId: string, ownershipId?: string | null) => void | Promise<void>;
}) {
  const isDisplayOnly = catalogStatusBucket(item) === 'coming-soon';
  const statusLabel = catalogStatusLabel(item, runtime);
  const runtimeLabel = catalogRuntimeLabel(item, runtime);
  const capabilityLabels = catalogCapabilityLabels(item);
  const profileNames = [...new Set([...item.profiles, ...item.capabilities.scan_profiles])];
  const canOpenProfiles = !isDisplayOnly && profileNames.length > 0;
  const canRunNow = canOpenProfiles && catalogRunReady(item);
  const docsAvailable = Boolean(item.docs_path || item.homepage_url);
  const stateCopy = catalogStateCopy(item, runtime);
  const displayLabels = catalogDisplayLabels(item);
  return (
    <div className="catalog-detail">
      <div className="catalog-detail-head">
        <span className="catalog-icon large">{catalogIcon(item.category)}</span>
        <div>
          <Eyebrow>{catalogCategoryLabels[item.category]}</Eyebrow>
          <h2>{item.label}</h2>
        </div>
      </div>
      <div className="catalog-detail-status">
        <SeverityPill tone={catalogStatusTone(item, runtime)} label={statusLabel} />
        <SeverityPill tone={catalogRuntimeTone(runtime)} label={runtimeLabel} />
      </div>
      <p className="catalog-detail-summary">{item.description ?? item.summary}</p>
      <div className="catalog-label-row wrap">
        {displayLabels.map((label) => <CatalogLabel key={label} label={label} />)}
      </div>

      <CatalogDetailSection title="Purpose" icon={<FileText size={15} />}>
        <p>{item.summary}</p>
      </CatalogDetailSection>

      <CatalogDetailSection title="What it checks" icon={<ClipboardList size={15} />}>
        {capabilityLabels.length ? (
          <ul className="catalog-detail-list">
            {capabilityLabels.slice(0, 6).map((label) => (
              <li key={label}><ListChecks size={14} /><span>{label}</span></li>
            ))}
          </ul>
        ) : (
          <p>No capability labels have been published for this entry yet.</p>
        )}
        {!!item.capabilities.evidence_types.length && (
          <div className="catalog-label-row">
            {item.capabilities.evidence_types.map((type) => <CatalogLabel key={type} label={catalogEvidenceLabels[type] ?? humanizeKey(type)} />)}
          </div>
        )}
      </CatalogDetailSection>

      <CatalogDetailSection title="Current availability" icon={<Stethoscope size={15} />}>
        <CatalogStatePanel item={item} runtime={runtime} />
        <div className="catalog-runtime-line">
          <SeverityPill tone={catalogRuntimeTone(runtime)} label={runtimeLabel} />
          <span>{catalogRuntimeCopy(item, runtime)}</span>
        </div>
        <div className="catalog-kv-grid">
          <KV label="Latest scan" value={formatDate(latestScanTime(summary))} />
          <KV label="Findings" value={runtime ? String(runtime.findings) : 'Not reported'} />
          <KV label="Repos" value={runtime?.repoNames.join(', ') || 'No runtime evidence'} />
          <KV label="Command" value={runtime?.command?.join(' ') || item.install.binary || 'Not reported'} />
        </div>
        {runtime?.error && <Notice tone="crit" icon={<AlertTriangle size={16} />} title="Runtime error" body={runtime.error} />}
      </CatalogDetailSection>

      <CatalogDetailSection title="Safety and permissions" icon={<Lock size={15} />}>
        <p>{catalogPolicySummary(item)}</p>
        <div className="catalog-kv-grid">
          <KV label="Network" value={catalogNetworkLabels[item.policy.network_access]} />
          <KV label="Credentials" value={catalogCredentialLabels[item.policy.uses_credentials]} />
          <KV label="Target" value={catalogTargetLabels[item.policy.external_targets]} />
          <KV label="File writes" value={item.policy.writes_files ? 'Writes files' : 'Read-only'} />
          <KV label="Approval" value={item.policy.needs_approval ? 'Required' : 'Not required'} />
          <KV label="Agent Lab" value={item.derived_labels.agent_lab} />
        </div>
      </CatalogDetailSection>

      <CatalogDetailSection title="Scan profiles and packs" icon={<Layers3 size={15} />}>
        <div className="catalog-profile-list">
          {profileNames.length ? profileNames.map((profile) => (
            <span key={profile} className={`catalog-profile-pill ${catalogProfileTone(item, profile)}`}>
              <strong>{profile}</strong>
              <em>{catalogProfileRole(item, profile)}</em>
            </span>
          )) : <span className="catalog-muted-line">No active scan profile in this version.</span>}
        </div>
        <div className="catalog-pack-detail-list">
          {item.packs.length ? item.packs.map((pack) => (
            <span key={`${item.id}:${pack.pack_id}`} className={pack.role === 'coming-soon' ? 'muted' : ''}>
              {catalogPackLabels[pack.pack_id]} · {humanizeKey(pack.role)}{pack.default_enabled ? ' · default' : ''}
            </span>
          )) : <span>No pack membership</span>}
        </div>
      </CatalogDetailSection>

      <CatalogDetailSection title="Setup and ownership" icon={<Settings size={15} />}>
        <div className="catalog-kv-grid">
          <KV label="Install state" value={catalogInstallLabels[item.install_state]} />
          <KV label="Method" value={catalogInstallMethodLabels[item.install.method]} />
          <KV label="Owner" value={catalogInstallOwnerLabels[item.install.owner]} />
          <KV label="Detection" value={catalogInstallDetectionLabels[item.install.detection]} />
          <KV label="Binary" value={item.install.binary ?? 'Not required'} />
          <KV label="Uninstall" value={catalogUninstallLabels[item.install.uninstall_posture]} />
        </div>
        <div className="next-step">
          <Eyebrow>Next action</Eyebrow>
          <p>{item.install.next_step ?? runtime?.action ?? 'Open the matching scan profile when you are ready to verify this coverage.'}</p>
        </div>
      </CatalogDetailSection>

      <CatalogDetailSection title="Install preview" icon={<Download size={15} />}>
        {item.install_preview?.preview_available ? (
          <CatalogManagedPreview
            preview={item.install_preview}
            toolLabel={item.label}
            mutation={mutation}
            onInstallTool={onInstallTool}
            onUninstallTool={onUninstallTool}
          />
        ) : (
          <Notice tone="neutral" icon={<CircleSlash size={16} />} title="No managed action" body={item.install_preview?.execution_reason ?? 'No managed installer is approved for this tool in the MVP.'} />
        )}
      </CatalogDetailSection>

      <CatalogDetailSection title="Actions" icon={<Play size={15} />}>
        {isDisplayOnly ? (
          <Notice tone="info" icon={<CircleSlash size={16} />} title="Display only" body={stateCopy.action} />
        ) : (
          <>
            <div className="button-row wrap">
              <Button icon={<SlidersHorizontal size={14} />} onClick={onChooseChecks} disabled={!canOpenProfiles}>Choose profile</Button>
              <Button variant="secondary" icon={<Play size={14} />} onClick={onChooseChecks} disabled={!canRunNow}>Run checks</Button>
            </div>
            <p className="catalog-action-help">{stateCopy.action}</p>
          </>
        )}
      </CatalogDetailSection>

      <CatalogDetailSection title="Docs" icon={<BookOpen size={15} />}>
        {docsAvailable ? (
          <div className="catalog-doc-links">
            {item.docs_path && <a className="catalog-doc-link" href={item.docs_path}><BookOpen size={15} />DëvSec docs <ChevronRight size={15} /></a>}
            {item.homepage_url && <a className="catalog-doc-link" href={item.homepage_url} target="_blank" rel="noreferrer"><Archive size={15} />Tool homepage <ChevronRight size={15} /></a>}
          </div>
        ) : (
          <p>No documentation link has been published for this entry yet.</p>
        )}
      </CatalogDetailSection>
    </div>
  );
}

function CatalogStatePanel({item, runtime}: {item: ToolCatalogItem; runtime?: ScannerDoctorItem}) {
  const stateCopy = catalogStateCopy(item, runtime);
  return (
    <div className={`catalog-state-panel ${stateCopy.tone}`}>
      <div>
        <SeverityPill tone={stateCopy.tone} label={catalogStatusLabel(item, runtime)} />
        <strong>{stateCopy.title}</strong>
      </div>
      <p>{stateCopy.detail}</p>
      <span>{stateCopy.action}</span>
    </div>
  );
}

function CatalogFutureCard({item, selected, onClick}: {item: ToolCatalogItem; selected: boolean; onClick: () => void}) {
  return (
    <button type="button" className={`catalog-future-card ${selected ? 'selected' : ''}`} data-category={item.category} aria-pressed={selected} onClick={onClick}>
      <span className="catalog-icon">{catalogIcon(item.category)}</span>
      <div>
        <SeverityPill tone="neutral" label="Display only" />
        <strong>{item.label}</strong>
        <p>{item.summary}</p>
        <em>{item.category === 'external-surface' ? 'Target approval is not built yet, so this cannot collect domains or run external recon.' : item.install.next_step ?? 'No run action is available in this version.'}</em>
      </div>
    </button>
  );
}

function CatalogLabel({label}: {label: string}) {
  return <span className={`catalog-label ${safetyLabelTone(label)}`}>{label}</span>;
}

function CatalogDetailSection({title, icon, children}: {title: string; icon: ReactNode; children: ReactNode}) {
  return (
    <section className="catalog-detail-section">
      <h3>{icon}{title}</h3>
      {children}
    </section>
  );
}

function PlaybooksView({summary, onChooseChecks}: {summary: DashboardSummary; onChooseChecks: () => void}) {
  const playbooks = buildPlaybooks(summary);
  const [activeId, setActiveId] = useState(playbooks[0]?.id ?? '');
  const active = playbooks.find((item) => item.id === activeId) ?? playbooks[0];
  return (
    <div className="view-stack">
      <div className="playbook-grid">
        {playbooks.map((item) => (
          <button key={item.id} type="button" className={`playbook-tile ${active.id === item.id ? 'selected' : ''}`} onClick={() => setActiveId(item.id)}>
            <BookOpen size={22} />
            <span>{item.steps.length} steps · {item.estimate}</span>
            <strong>{item.title}</strong>
            <p>{item.body}</p>
            <em>{item.trigger}</em>
          </button>
        ))}
      </div>
      <PaperCard>
        <div className="playbook-detail">
          <div>
            <Eyebrow>Recovery playbook</Eyebrow>
            <h2>{active.title}</h2>
            <code>{active.trigger}</code>
            <p>{active.body}</p>
            <div className="button-row">
              {active.caseItem?.scanId && <a className="button primary" href={reportViewUrl(active.caseItem.scanId, 'prompt')}><Sparkles size={14} /> AI prompt</a>}
              {active.caseItem?.scanId && <a className="button secondary" href={reportViewUrl(active.caseItem.scanId, 'raw')}><FileText size={14} /> Raw report</a>}
              <Button variant="ghost" onClick={onChooseChecks}>Rerun checks</Button>
            </div>
            <ol className="step-list">
              {active.steps.map((step, index) => <li key={step}><span>{index + 1}</span><strong>{step}</strong></li>)}
            </ol>
          </div>
          <div className="playbook-meta">
            <MetricBlock label="Steps" value={String(active.steps.length)} />
            <MetricBlock label="Wall est." value={active.estimate} />
            <MetricBlock label="Source" value={active.caseItem ? caseScanner(active.caseItem) : 'verification'} />
          </div>
        </div>
      </PaperCard>
    </div>
  );
}

function VerificationView({summary, onChooseChecks}: {summary: DashboardSummary; onChooseChecks: () => void}) {
  const completeness = scanCompleteness(summary);
  const scanners = topScannerItems(summary);
  const coverage = scannerCoverageSummary(summary);
  const failed = scanners.filter((item) => item.status === 'missing' || item.status === 'error');
  return (
    <div className="view-stack">
      <section className={`verification-hero ${failed.length ? 'attention' : ''}`}>
        <div>
          <Eyebrow onSurface>Verification</Eyebrow>
          <h1>{failed.length ? `${failed.length} checks need attention.` : 'All available checks are accounted for.'}</h1>
          <p>{coverage}</p>
        </div>
        <Button variant="glassOnGlass" onClick={onChooseChecks}>Run checks</Button>
      </section>
      <section className="triple-grid">
        <CoverageCard title="Checks that ran" icon={<CheckCircle2 size={18} />} items={completeness.checksRan} empty="No completed checks reported." />
        <CoverageCard title="Skipped or missing" icon={<CircleSlash size={18} />} items={completeness.checksMissing} empty="No skipped checks reported." />
        <CoverageCard title="Cannot prove" icon={<Stethoscope size={18} />} items={completeness.cannotProve} empty="No limits reported." />
      </section>
      <PaperCard>
        <SectionHeader title="Scanner doctor" right={<span>{scanners.length} checks</span>} />
        <div className="doctor-grid">
          {scanners.map((item) => <DoctorRow key={item.scanner} item={item} />)}
        </div>
      </PaperCard>
    </div>
  );
}

function ActivityView({summary, search}: {summary: DashboardSummary; search: string}) {
  const activities = buildActivity(summary).filter((item) => {
    if (!search.trim()) return true;
    return `${item.label} ${item.sub}`.toLowerCase().includes(search.toLowerCase());
  });
  const honeyHits = (summary.honey_key_events ?? []).length;
  return (
    <div className="view-stack">
      <section className="summary-strip">
        <MetricBlock label="Audit history" value={String(summary.history.length)} detail="runs saved locally" />
        <MetricBlock label="Storage" value={`${Math.max(0.1, summary.history.length * 0.04).toFixed(1)} MB`} detail="local · sqlite" />
        <MetricBlock label="Findings · 7 d" value={String(totalFindings(summary))} detail={`${suppressedDisplayCases(summary).length} suppressed`} />
        <MetricBlock label="Honey hits" value={String(honeyHits)} tone={honeyHits ? 'warn' : 'low'} />
      </section>
      <section className="split-grid align-start">
        <PaperCard>
          <SectionHeader title="Audits · 24 h × 7 d" />
          <Heatmap history={summary.history} />
        </PaperCard>
        <PaperCard>
          <SectionHeader title="Event mix · 7 d" />
          <EventMix summary={summary} />
        </PaperCard>
      </section>
      <PaperCard padded={false}>
        <div className="event-feed-head">
          <Eyebrow>Event feed · Today</Eyebrow>
          <div className="chip-row compact"><Chip active>All</Chip><Chip>Scanner runs</Chip><Chip>Findings</Chip><Chip>Honey keys</Chip></div>
        </div>
        <div className="activity-list feed">
          {activities.map((item) => <ActivityRow key={item.id} item={item} showTone />)}
          {!activities.length && <div className="empty-feed"><EmptyLine title="No matching events" detail="The local event feed is quiet." /></div>}
        </div>
      </PaperCard>
    </div>
  );
}

function ReportsView({summary}: {summary: DashboardSummary}) {
  const latest = latestRepoScan(summary);
  const deps = dependencyDeltas(summary);
  const depChanges = dependencyChanges(summary);
  const trust = dependencyTrustRecords(summary);
  const platform = platformPostureFindings(summary);
  const platformSnapshots = platformPostureSnapshots(summary);
  const cveCounts = dependencyCveCounts(summary);
  const iocMatches = iocMatchFindings(summary);
  return (
    <div className="view-stack">
      <section className="report-hero">
        <div>
          <Eyebrow onSurface>Current report</Eyebrow>
          <h1>{latest ? `${latest.repo} · ${latest.profile}` : 'No scan reports yet'}</h1>
          <p>{latest ? `Finished ${formatDate(latest.last_scan)} · ${latest.health}/100 health` : 'Run a repo check to create the first local report.'}</p>
        </div>
        {latest?.scan_id && (
          <div className="hero-actions">
            <a className="button glass-on" href={reportViewUrl(latest.scan_id, 'raw')}><FileText size={14} /> Raw report</a>
            <a className="button glass" href={reportViewUrl(latest.scan_id, 'prompt')}><Sparkles size={14} /> AI prompt</a>
          </div>
        )}
      </section>
      <section className="triple-grid">
        <MetricCard title="Dependency deltas" value={String(depChanges.length)} detail={`${deps.length} repo comparisons`} />
        <MetricCard title="Known CVE state" value={String(cveCounts['has-cve'])} detail={`${cveCounts['not-checked']} not checked`} />
        <MetricCard title="Named-campaign matches" value={String(iocMatches.length)} detail={`${iocMatches.filter((finding) => finding.ioc_match_type === 'exact match').length} exact`} />
        <MetricCard title="Trust records" value={String(trust.length)} detail="dependency enrichment" />
      </section>
      <RepositorySnapshotCard summary={summary} />
      <PaperCard>
        <SectionHeader title="Saved scan reports" right={<span>{summary.history.length} total</span>} />
        <div className="report-table">
          {summary.history.slice().reverse().slice(0, 12).map((scan) => (
            <div key={scan.id} className="report-row">
              <div><strong>{scan.profile}</strong><span>{formatDate(scan.finished_at ?? scan.started_at)} · {scan.repo_name}</span></div>
              <MetricPill label="Health" value={scan.health_score} />
              <div className="report-actions">
                <a href={reportViewUrl(scan.id, 'raw')}>Raw</a>
                <a href={reportViewUrl(scan.id, 'prompt')}>Prompt</a>
              </div>
            </div>
          ))}
          {!summary.history.length && <EmptyLine title="No reports saved" detail="Completed checks will appear here." />}
        </div>
      </PaperCard>
      <section className="split-grid align-start">
        <PaperCard>
          <SectionHeader title="Supply chain changes" right={<span>{depChanges.length} records</span>} />
          <div className="data-table dependency-table">
            <div className="data-head"><span>Package</span><span>Change</span><span>Version</span><span>CVE</span></div>
            {depChanges.slice(0, 10).map((change) => (
              <div key={`${change.scan_id}-${change.package_key}`} className="data-row">
                <strong>{change.name ?? change.package_key}</strong>
                <span>{change.change_types?.join(', ') || change.change_type}</span>
                <span>{change.previous_version ?? 'none'} {'->'} {change.current_version ?? 'none'}</span>
                <span>{change.cve_label ?? change.cve_status ?? 'not checked'}</span>
              </div>
            ))}
            {!depChanges.length && <EmptyLine title="No dependency changes saved" detail="SBOM-backed scans will populate this section." />}
          </div>
        </PaperCard>
        <PaperCard>
          <SectionHeader title="Trust records" right={<span>{trust.length} packages</span>} />
          <div className="data-table trust-table">
            <div className="data-head"><span>Package</span><span>Scorecard</span><span>Criticality</span><span>Freshness</span></div>
            {trust.slice(0, 10).map((record) => (
              <div key={`${record.scan_id}-${record.component_package_key ?? record.component_fingerprint}`} className="data-row">
                <strong>{record.package_name ?? record.component_package_key ?? 'Package'}</strong>
                <span>{record.scorecard_score ?? 'n/a'} · {record.scorecard_status}</span>
                <span>{record.criticality_score ?? 'n/a'} · {record.criticality_status}</span>
                <span>{record.freshness}{record.error ? ` · ${record.error}` : ''}</span>
              </div>
            ))}
            {!trust.length && <EmptyLine title="No trust records saved" detail="Dependency enrichment is filled by optional SBOM/trust checks." />}
          </div>
        </PaperCard>
      </section>
      <PaperCard>
        <SectionHeader title="Named-campaign matches" right={<span>{iocMatches.length} IOC signals</span>} />
        <div className="data-table dependency-table">
          <div className="data-head"><span>Indicator</span><span>Match</span><span>Pack</span><span>Evidence</span></div>
          {iocMatches.slice(0, 10).map((finding) => (
            <div key={finding.fingerprint} className="data-row">
              <strong>{finding.package_name ?? finding.ioc_indicator ?? finding.title}<em>{finding.repo_name}</em></strong>
              <span>{finding.ioc_match_type ?? 'IOC match'} · {finding.ioc_confidence ?? 'unknown'}</span>
              <span>{finding.ioc_source ?? finding.ioc_pack_id ?? 'Unknown pack'}</span>
              <span>{finding.file ?? finding.ioc_advisory_url ?? 'Repository evidence'}</span>
            </div>
          ))}
          {!iocMatches.length && <EmptyLine title="No named-campaign matches" detail="IOC Watch found no exact, namespace, or domain matches in the latest evidence." />}
        </div>
      </PaperCard>
      <PlatformPostureCard snapshots={platformSnapshots} findings={platform} />
    </div>
  );
}

function RepositorySnapshotCard({summary}: {summary: DashboardSummary}) {
  return (
    <PaperCard>
      <SectionHeader title="Repository snapshots" right={<span>{summary.repos.length} current targets</span>} />
      <div className="data-table repo-table">
        <div className="data-head">
          <span>Repo</span><span>Health</span><span>Previous</span><span>Active</span><span>Raw</span><span>Suppressed</span><span>Reports</span>
        </div>
        {summary.repos.map((repo) => (
          <div key={`${repo.repo}-${repo.scan_id ?? repo.path}`} className="data-row">
            <strong>{repo.repo}<em>{repo.path}</em></strong>
            <span>{repo.health}/100</span>
            <span>{repo.previous_health ?? 'none'}{typeof repo.health_delta === 'number' ? ` (${repo.health_delta >= 0 ? '+' : ''}${repo.health_delta})` : ''}</span>
            <span>{countRecord(repo.counts)} findings</span>
            <span>{countRecord(repo.raw_counts)} raw</span>
            <span>{repo.suppressed_counts?.findings ?? 0} hidden</span>
            <span>{repo.scan_id ? <a href={reportViewUrl(repo.scan_id, 'raw')}>Raw</a> : 'No report'}</span>
          </div>
        ))}
        {!summary.repos.length && <EmptyLine title="No repository snapshots" detail="Run a scan to populate current repo state." />}
      </div>
    </PaperCard>
  );
}

function PlatformPostureCard({
  snapshots,
  findings,
}: {
  snapshots: ReturnType<typeof platformPostureSnapshots>;
  findings: ReturnType<typeof platformPostureFindings>;
}) {
  return (
    <PaperCard>
      <SectionHeader title="Platform posture" right={<span>{snapshots.length} snapshots · {findings.length} findings</span>} />
      <div className="data-table platform-table">
        <div className="data-head">
          <span>Target</span><span>Status</span><span>Records</span><span>Failed</span><span>Source</span>
        </div>
        {snapshots.map((snapshot) => (
          <div key={`${snapshot.scan_id}-${snapshot.target}-${snapshot.source}`} className="data-row">
            <strong>{snapshot.target}<em>{snapshot.repo_name}</em></strong>
            <span>{snapshot.status}{snapshot.reason ? ` · ${snapshot.reason}` : ''}</span>
            <span>{snapshot.summary?.records ?? 'n/a'}</span>
            <span>{snapshot.summary?.failed ?? 0}</span>
            <span>{snapshot.scanner} · {snapshot.source}</span>
          </div>
        ))}
        {findings.slice(0, 6).map((finding) => (
          <div key={finding.fingerprint} className="data-row">
            <strong>{finding.title}<em>{finding.file ?? finding.repo_name}</em></strong>
            <span>{finding.severity}</span>
            <span>{finding.category}</span>
            <span>{formatDate(finding.created_at)}</span>
            <span>{finding.scanner}</span>
          </div>
        ))}
        {!snapshots.length && !findings.length && <EmptyLine title="No platform posture saved" detail="Connected SCM posture checks are optional and stay local." />}
      </div>
    </PaperCard>
  );
}

function SettingsView({summary, target, targetRepos, updatedAt, onTargetChange}: {summary: DashboardSummary; target: TargetSelection; targetRepos: ProjectRepo[]; updatedAt: Date | null; onTargetChange: (value: string) => void}) {
  return (
    <div className="view-stack">
      <PaperCard>
        <SectionHeader title="Workspace" />
        <div className="settings-list">
          <SettingRow label="Target" sub="Controls which repo the dashboard scopes to.">
            <select value={targetValue(target)} onChange={(event) => onTargetChange(event.target.value)}>
              <option value="dashboard">Dashboard</option>
              {targetRepos.map((repo) => <option key={repo.path} value={`repo:${repo.path}`}>{repo.name}</option>)}
              <option value="add-repo">+ Add repo...</option>
            </select>
          </SettingRow>
          <SettingRow label="Last refresh" sub="Read from the local dashboard API.">
            <strong>{updatedAt ? updatedAt.toLocaleTimeString() : 'Never'}</strong>
          </SettingRow>
          <SettingRow label="Local records" sub="Stored under the DëvSec SQLite history store.">
            <strong>{summary.history.length} scans</strong>
          </SettingRow>
        </div>
      </PaperCard>
      <PaperCard>
        <SectionHeader title="Privacy and storage" />
        <div className="settings-list">
          <SettingRow label="Honey Key retention" sub="Security log data used only for triage.">
            <strong>{summary.honey_event_retention_days ?? 90} days</strong>
          </SettingRow>
          <SettingRow label="Generated reports" sub="Reports remain local unless you export or share them.">
            <Button variant="secondary" size="sm" icon={<Download size={14} />}>Export</Button>
          </SettingRow>
        </div>
      </PaperCard>
      <DataCoverageCard summary={summary} />
      <ProjectStatusesCard summary={summary} />
    </div>
  );
}

function DataCoverageCard({summary}: {summary: DashboardSummary}) {
  const rows = [
    ['Repository snapshots', summary.repos.length, 'current scan state'],
    ['History records', summary.history.length, 'saved scans'],
    ['Active findings', activeFindingCount(summary), 'shown in Findings'],
    ['Suppressed findings', suppressedFindingCount(summary), 'shown with reasons'],
    ['Cases', (summary.cases ?? []).length || (summary.active_cases ?? []).length + (summary.suppressed_cases ?? []).length, 'decision workflow'],
    ['Case decisions', (summary.case_decisions ?? []).length, 'stored review state'],
    ['Honey Keys', (summary.honey_keys ?? []).length, 'create, insert, archive'],
    ['Honey events', (summary.honey_key_events ?? []).length, 'incident evidence'],
    ['Scanner catalog', (summary.scanner_catalog ?? []).length || topScannerItems(summary).length, 'doctor coverage'],
    ['Dependency changes', dependencyChanges(summary).length, 'SBOM deltas'],
    ['Trust records', dependencyTrustRecords(summary).length, 'package enrichment'],
    ['Platform snapshots', platformPostureSnapshots(summary).length, 'connected posture'],
    ['Project statuses', (summary.project_statuses ?? []).length, 'local project health'],
  ];
  return (
    <PaperCard>
      <SectionHeader title="Data coverage" right={<span>real API payload</span>} />
      <div className="data-table coverage-table">
        <div className="data-head"><span>Dataset</span><span>Records</span><span>Surface</span></div>
        {rows.map(([label, count, surface]) => (
          <div key={String(label)} className="data-row">
            <strong>{label}</strong>
            <span>{count}</span>
            <span>{surface}</span>
          </div>
        ))}
      </div>
    </PaperCard>
  );
}

function ProjectStatusesCard({summary}: {summary: DashboardSummary}) {
  const statuses = summary.project_statuses ?? [];
  return (
    <PaperCard>
      <SectionHeader title="Project status" right={<span>{statuses.length} projects</span>} />
      <div className="soft-list">
        {statuses.map((status) => (
          <EmptyLine
            key={status.project_id}
            title={`${status.project_id} · ${status.status}`}
            detail={`${status.reason}${status.last_event_at ? ` · ${formatDate(status.last_event_at)}` : ''}`}
          />
        ))}
        {!statuses.length && <EmptyLine title="No project status records" detail="This dashboard payload does not include project status rows yet." />}
      </div>
    </PaperCard>
  );
}

function EmptyRepoView({repoName, onRunQuick, onChooseChecks}: {repoName: string; onRunQuick: () => void; onChooseChecks: () => void}) {
  return (
    <div className="empty-repo">
      <div className="workspace-mark large"><FolderGit2 size={34} /></div>
      <Eyebrow>No saved scan</Eyebrow>
      <h1>No scan yet for {repoName}</h1>
      <p>Run a quick safety sweep first. DëvSec will turn scanner output into local findings, reports, and next actions.</p>
      <div className="button-row">
        <Button icon={<Play size={15} />} onClick={onRunQuick}>Run quick sweep</Button>
        <Button variant="secondary" icon={<SlidersHorizontal size={15} />} onClick={onChooseChecks}>Choose checks</Button>
      </div>
    </div>
  );
}

function CaseDetailCard({item, onDecision}: {item: DisplayCase; onDecision: (caseId: string, repoName: string, status: CaseDecisionStatus | 'open', note: string) => Promise<void>}) {
  async function save(status: CaseDecisionStatus | 'open') {
    const note = status === 'open' ? '' : window.prompt('Optional note for this decision', item.decision?.note ?? '');
    if (note === null) return;
    await onDecision(item.id, item.repoName, status, note);
  }
  return (
    <PaperCard className="detail-card">
      <div className="detail-head">
        <SeverityPill tone={toneForCase(item)} label={severityLabelForCase(item)} />
        {item.suppressed && <span className="mini-label"><EyeOff size={12} /> Suppressed</span>}
      </div>
      <h2>{item.title}</h2>
      <p>{item.why}</p>
      <KV label="Case" value={item.id} />
      <KV label="Repository" value={item.repoName} />
      <KV label="Location" value={item.location} />
      <KV label="Category" value={item.category ? categoryLabel(item.category) : 'Uncategorized'} />
      <KV label="Scanner" value={item.sources.join(', ') || 'Not reported'} />
      <KV label="Confidence" value={item.confidence} />
      <KV label="Age" value={relativeAge(item.createdAt)} />
      {item.changeStatus && <KV label="Change state" value={item.changeStatus} />}
      {item.resolvedAt && <KV label="Resolved" value={formatDate(item.resolvedAt)} />}
      {item.decision && (
        <div className="evidence-panel">
          <Eyebrow>Case decision</Eyebrow>
          <KV label="Status" value={item.decision.status} />
          <KV label="Updated" value={formatDate(item.decision.updated_at)} />
          <KV label="Note" value={item.decision.note ?? 'No note'} />
          {item.decision.vex_status && <KV label="VEX" value={`${item.decision.vex_status}${item.decision.vex_reason ? ` · ${item.decision.vex_reason}` : ''}`} />}
          {item.decision.fixed_version && <KV label="Fixed version" value={item.decision.fixed_version} />}
        </div>
      )}
      {item.suppression && (
        <div className="evidence-panel">
          <Eyebrow>Suppression metadata</Eyebrow>
          <KV label="Reason" value={item.suppression.reason ?? item.suppression.vex_reason ?? 'Not recorded'} />
          <KV label="Decision" value={textOrFallback(item.suppression.decision_status ?? item.suppression.status)} />
          <KV label="VEX" value={textOrFallback(item.suppression.vex_status)} />
          <KV label="Matched by" value={textOrFallback(item.suppression.matched_by)} />
          {item.suppression.updated_at && <KV label="Updated" value={formatDate(item.suppression.updated_at)} />}
        </div>
      )}
      <div className="next-step">
        <Eyebrow>Next step</Eyebrow>
        <p>{item.nextStep}</p>
      </div>
      <div className="button-row wrap">
        {item.scanId && <a className="button primary" href={reportViewUrl(item.scanId, 'prompt')}><Sparkles size={14} /> AI prompt</a>}
        {item.scanId && <a className="button secondary" href={reportViewUrl(item.scanId, 'raw')}><FileText size={14} /> Raw report</a>}
      </div>
      <div className="decision-grid">
        {([
          ['verified', 'Verify', CheckCircle2],
          ['false_positive', 'False positive', X],
          ['accepted_risk', 'Accept risk', ShieldCheck],
          ['fixed', 'Mark fixed', Lock],
        ] as const).map(([status, label, Icon]) => (
          <button key={status} type="button" className={item.decision?.status === status ? 'active' : ''} onClick={() => void save(status)}>
            <Icon size={13} /> {label}
          </button>
        ))}
        {item.decision && <button type="button" onClick={() => void save('open')}><RotateCcw size={13} /> Reopen</button>}
      </div>
    </PaperCard>
  );
}

function FindingsTable({items, onPick}: {items: DisplayCase[]; onPick: (id: string) => void}) {
  return (
    <div className="findings-table">
      <div className="findings-head">
        <span>ID</span><span>Finding</span><span>Category</span><span>Scanner</span><span>Severity</span><span>Age</span><span />
      </div>
      {items.map((item, index) => (
        <button key={item.id} type="button" className="finding-row" onClick={() => onPick(item.id)}>
          <span>{displayId(item, index)}</span>
          <span><strong>{item.title}</strong><em>{item.location}</em></span>
          <span>{item.category ? categoryLabel(item.category) : 'Security'}</span>
          <span>{caseScanner(item)}</span>
          <span><SeverityPill tone={toneForCase(item)} label={severityLabelForCase(item)} /></span>
          <span>{relativeAge(item.createdAt)}</span>
          <ChevronRight size={16} />
        </button>
      ))}
      {!items.length && <div className="empty-table"><EmptyLine title="No findings match" detail="Try another filter or search term." /></div>}
    </div>
  );
}

function SuppressionReasonsCard({reasons}: {reasons: ReturnType<typeof suppressionReasons>}) {
  return (
    <PaperCard>
      <SectionHeader title="Suppression reasons" right={<span>{reasons.length} decision groups</span>} />
      <div className="data-table suppression-table">
        <div className="data-head">
          <span>Reason</span><span>Decision</span><span>VEX</span><span>Cases</span><span>Findings</span>
        </div>
        {reasons.map((reason) => (
          <div key={`${reason.reason}-${reason.decision_status}-${reason.vex_status}`} className="data-row">
            <strong>{reason.reason}</strong>
            <span>{reason.decision_status}</span>
            <span>{reason.vex_status}</span>
            <span>{reason.cases}</span>
            <span>{reason.findings}</span>
          </div>
        ))}
      </div>
    </PaperCard>
  );
}

function FindingLine({item, index, onClick, muted = false}: {item: DisplayCase; index: number; onClick?: () => void; muted?: boolean}) {
  const tone = toneForCase(item);
  return (
    <button type="button" className={`prose-line ${muted ? 'muted' : ''}`} onClick={onClick}>
      <span className="severity-rail" style={{background: severityMeta[tone].dot}} />
      <span>
        <strong>{item.title}</strong>
        <em>{severityLabelForCase(item)} · {caseScanner(item)} · {relativeAge(item.createdAt)}</em>
      </span>
      <ChevronRight size={16} />
      <i>{displayId(item, index)}</i>
    </button>
  );
}

function RiskLandscape({items, onPick}: {items: DisplayCase[]; onPick: (id: string) => void}) {
  const lanes: {tone: Tone; label: string; y: number}[] = [
    {tone: 'crit', label: 'Critical', y: 20},
    {tone: 'high', label: 'Elevated', y: 42},
    {tone: 'warn', label: 'Warning', y: 64},
    {tone: 'low', label: 'Low', y: 84},
  ];
  return (
    <div className="risk-landscape">
      {lanes.map((lane) => (
        <div key={lane.tone} className="risk-lane" style={{top: `${lane.y}%`}}>
          <span><i style={{background: severityMeta[lane.tone].dot}} />{lane.label}</span>
        </div>
      ))}
      {items.slice(0, 16).map((item, index) => {
        const tone = toneForCase(item);
        const lane = lanes.find((entry) => entry.tone === tone) ?? lanes[3];
        const x = 14 + ((index * 17) % 78);
        return (
          <button
            key={item.id}
            type="button"
            className="risk-dot"
            style={{left: `${x}%`, top: `${lane.y}%`, background: severityMeta[tone].dot, width: 10 + Math.min(14, item.title.length / 4), height: 10 + Math.min(14, item.title.length / 4)}}
            title={item.title}
            onClick={() => onPick(item.id)}
          />
        );
      })}
      <div className="risk-axis"><span>now</span><span>6h</span><span>24h · 1d</span><span>3d</span><span>1w</span><span>1m</span></div>
    </div>
  );
}

function HoneyKeyCard({honeyKey, selected, onClick, onArchive, isArchiving}: {honeyKey: HoneyKey; selected: boolean; onClick: () => void; onArchive: (id: string) => void; isArchiving: boolean}) {
  const tone: Tone = honeyKey.status === 'triggered' ? 'crit' : honeyKey.status === 'archived' ? 'neutral' : 'low';
  return (
    <div
      className={`honey-card ${selected ? 'selected' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') onClick();
      }}
    >
      <div className="workspace-mark"><ShieldCheck size={18} /></div>
      <div>
        <strong>{honeyKey.name}</strong>
        <span>{honeyKey.id} · {honeyKey.placement_path ?? 'unplaced'}</span>
        <code>{honeyKey.token_prefix}xxxxxxxxxxxxxxxx</code>
      </div>
      <div className="honey-meta">
        <SeverityPill tone={tone} label={honeyKey.status === 'active' ? 'ARMED' : honeyKey.status.toUpperCase()} />
        <em>{honeyKey.last_triggered_at ? `last hit ${formatDate(honeyKey.last_triggered_at)}` : 'never accessed'}</em>
        {honeyKey.status !== 'archived' && <button type="button" onClick={(event) => {event.stopPropagation(); onArchive(honeyKey.id);}} disabled={isArchiving}><Archive size={13} /> Retire</button>}
      </div>
    </div>
  );
}

function HoneyCreatePanel(props: {
  id: string;
  target: TargetSelection;
  name: string;
  setName: (value: string) => void;
  placementPath: string;
  setPlacementPath: (value: string) => void;
  note: string;
  setNote: (value: string) => void;
  isCreating: boolean;
  onCreate: () => void;
}) {
  return (
    <PaperCard id={props.id}>
      <SectionHeader title="Place new key" />
      <p className="muted-body">Honey Keys are powerless decoy secrets that alert when touched.</p>
      {props.target.type !== 'repo' ? (
        <Notice tone="warn" icon={<AlertTriangle size={16} />} title="Select a repo" body="Honey Keys require a repo target before creation." />
      ) : (
        <div className="form-stack">
          <label><span>Display name</span><input value={props.name} onChange={(event) => props.setName(event.target.value)} /></label>
          <label><span>Suggested placement</span><select value={props.placementPath} onChange={(event) => props.setPlacementPath(event.target.value)}>{placementTemplates.map((template) => <option key={template}>{template}</option>)}</select></label>
          <label><span>Note</span><textarea value={props.note} onChange={(event) => props.setNote(event.target.value)} rows={3} /></label>
          <Button icon={<KeyRound size={15} />} onClick={props.onCreate} disabled={props.isCreating}>{props.isCreating ? 'Creating...' : 'Create Honey Key'}</Button>
        </div>
      )}
    </PaperCard>
  );
}

function HoneyDetailPanel({honeyKey, events}: {honeyKey: HoneyKey; events: HoneyKeyEvent[]}) {
  return (
    <PaperCard>
      <SectionHeader title="Honey Key detail" />
      <KV label="ID" value={honeyKey.id} />
      <KV label="Name" value={honeyKey.name} />
      <KV label="Status" value={honeyKey.status} />
      <KV label="Placement" value={honeyKey.placement_path ?? 'Not recorded'} />
      <KV label="Created" value={formatDate(honeyKey.created_at)} />
      <KV label="Created by" value={honeyKey.created_by ?? 'Local user'} />
      <KV label="Triggers" value={String(honeyKey.trigger_count)} />
      <KV label="Last triggered" value={formatDate(honeyKey.last_triggered_at)} />
      <KV label="Archived" value={honeyKey.archived_at ? formatDate(honeyKey.archived_at) : 'No'} />
      <KV label="Note" value={honeyKey.note ?? 'No note'} />
      {!!events.length && (
        <div className="evidence-panel">
          <Eyebrow>Recent events</Eyebrow>
          <div className="soft-list">
            {events.slice(0, 4).map((event) => (
              <EmptyLine
                key={event.id}
                title={`${formatDate(event.triggered_at)} · ${event.method} ${event.path}`}
                detail={`${event.ip_address ?? 'unknown IP'} · confidence ${formatConfidenceValue(event.confidence)} · ${event.reason}`}
              />
            ))}
          </div>
        </div>
      )}
    </PaperCard>
  );
}

function HoneyEventEvidence({event}: {event: HoneyKeyEvent}) {
  const headerCount = Object.keys(event.headers ?? {}).length;
  return (
    <PaperCard>
      <SectionHeader title="Trip evidence" right={<SeverityPill tone={event.incident?.closed_at ? 'warn' : 'crit'} label={event.incident?.closed_at ? 'closed' : 'open'} />} />
      <KV label="Event" value={event.id} />
      <KV label="When" value={formatDate(event.triggered_at)} />
      <KV label="Source" value={event.source_type} />
      <KV label="Method / path" value={`${event.method} ${event.path}`} />
      <KV label="IP" value={event.ip_address ?? 'Unknown'} />
      <KV label="Geo" value={event.approximate_geo ?? 'Unknown'} />
      <KV label="User agent" value={event.user_agent ?? 'Unknown'} />
      <KV label="Confidence" value={formatConfidenceValue(event.confidence)} />
      <KV label="Headers" value={`${headerCount} captured`} />
      <KV label="Body" value={event.body_summary ?? 'No body summary'} />
      <KV label="Reason" value={event.reason} />
    </PaperCard>
  );
}

function IncidentChecklist({
  event,
  incident,
  savingIncident,
  onToggle,
  onClose,
}: {
  event: HoneyKeyEvent;
  incident?: HoneyIncident | null;
  savingIncident: string | null;
  onToggle: (eventId: string, step: IncidentStep, complete: boolean) => Promise<void>;
  onClose: (event: HoneyKeyEvent) => Promise<void>;
}) {
  const done = incidentSteps.filter((step) => incident?.[step.id]).length;
  return (
    <PaperCard>
      <SectionHeader title="Incident response" right={<span>{done}/{incidentSteps.length} complete</span>} />
      <div className="incident-grid">
        {incidentSteps.map((step) => {
          const checked = Boolean(incident?.[step.id]);
          const saving = savingIncident === `${event.id}:${step.id}`;
          return (
            <label key={step.id} className={checked ? 'checked' : ''}>
              <input type="checkbox" checked={checked} disabled={saving} onChange={(change) => void onToggle(event.id, step.id, change.target.checked)} />
              <span><strong>{step.label}</strong><em>{step.detail}</em></span>
            </label>
          );
        })}
      </div>
      <Button variant="secondary" onClick={() => void onClose(event)} disabled={savingIncident === `${event.id}:close`}>Close incident</Button>
    </PaperCard>
  );
}

function HoneyTenure({keys, onPick}: {keys: HoneyKey[]; onPick: (id: string) => void}) {
  return (
    <div className="honey-tenure">
      {keys.slice(0, 7).map((key) => {
        const days = quietDays(key);
        const pct = Math.max(4, Math.min(98, days * 2));
        const tone: Tone = key.status === 'triggered' ? 'crit' : key.status === 'archived' ? 'neutral' : 'low';
        return (
          <button type="button" key={key.id} onClick={() => onPick(key.id)} className="tenure-row">
            <span><i style={{background: severityMeta[tone].dot}} />{key.name}</span>
            <strong style={{width: `${pct}%`, background: severityMeta[tone].dot}} />
            <em>{key.status === 'archived' ? 'retired' : `${days}d`}</em>
          </button>
        );
      })}
      {!keys.length && <EmptyLine title="No tenure data" detail="Honey Keys will appear here after creation." />}
    </div>
  );
}

function quietDays(key: HoneyKey): number {
  const value = key.last_triggered_at ?? key.created_at;
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return 0;
  return Math.max(0, Math.round((Date.now() - time) / 86400000));
}

function ScannerCard({item, selected, onClick}: {item: ScannerDoctorItem; selected: boolean; onClick: () => void}) {
  const tone = scannerStatusTone(item.status);
  return (
    <button type="button" className={`scanner-card ${selected ? 'selected' : ''}`} onClick={onClick}>
      <div className="scanner-card-top">
        {iconForCategory(item.area.toLowerCase())}
        <SeverityPill tone={tone} label={item.status.replace('-', ' ')} />
      </div>
      <strong>{item.label}</strong>
      <p>{item.covers}</p>
      <div className="scanner-bars">
        {Array.from({length: 14}, (_, index) => <span key={index} style={{height: `${8 + ((index * (item.findings + 2)) % 28)}px`, opacity: item.status === 'ran' ? 0.75 : 0.22}} />)}
      </div>
    </button>
  );
}

function ScannerDetail({item, onChooseChecks}: {item: ScannerDoctorItem; onChooseChecks: () => void}) {
  return (
    <div className="scanner-detail">
      <Eyebrow>{item.area}</Eyebrow>
      <h2>{item.label}</h2>
      <p>{item.covers}</p>
      <KV label="Status" value={item.status} />
      <KV label="Profile" value={item.profile} />
      <KV label="Recommended packs" value={item.recommendedPacks.map((pack) => pack.label).join(', ') || 'No pack recommendation'} />
      <KV label="Findings" value={String(item.findings)} />
      <KV label="Repos" value={item.repoNames.join(', ') || 'Not run'} />
      <div className="next-step"><Eyebrow>Next action</Eyebrow><p>{item.action}</p></div>
      <div className="button-row wrap">
        <Button icon={<Play size={14} />} onClick={onChooseChecks}>Run now</Button>
        <Button variant="secondary" icon={<SlidersHorizontal size={14} />} onClick={onChooseChecks}>Choose profile</Button>
      </div>
    </div>
  );
}

function DoctorRow({item}: {item: ScannerDoctorItem}) {
  const tone = scannerStatusTone(item.status);
  return (
    <div className="doctor-row">
      <SeverityPill tone={tone} label={item.status.replace('-', ' ')} />
      <div>
        <strong>{item.label}</strong>
        <span>{item.action}</span>
        {!!item.recommendedPacks.length && <span>{item.recommendedPacks.map((pack) => `${pack.label}: ${pack.ready_count} ready`).join(' · ')}</span>}
      </div>
      <em>{item.findings} signals</em>
    </div>
  );
}

function CoverageCard({title, icon, items, empty}: {title: string; icon: ReactNode; items: string[]; empty: string}) {
  return (
    <PaperCard>
      <SectionHeader title={title} icon={icon} />
      <ul className="coverage-list">
        {items.length ? items.map((item) => <li key={item}>{item}</li>) : <li className="empty">{empty}</li>}
      </ul>
    </PaperCard>
  );
}

function Heatmap({history}: {history: DashboardSummary['history']}) {
  const values = Array.from({length: 7}, (_, day) => Array.from({length: 24}, (_, hour) => {
    return history.filter((scan) => {
      const date = new Date(scan.finished_at ?? scan.started_at);
      return !Number.isNaN(date.getTime()) && date.getDay() === day && date.getHours() === hour;
    }).length;
  }));
  const max = Math.max(1, ...values.flat());
  return (
    <div className="heatmap">
      {values.map((row, rowIndex) => (
        <div key={rowIndex}>
          <span>{['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][rowIndex]}</span>
          {row.map((value, colIndex) => <i key={colIndex} style={{opacity: 0.18 + (value / max) * 0.75}} />)}
        </div>
      ))}
    </div>
  );
}

function EventMix({summary}: {summary: DashboardSummary}) {
  const rows = [
    ['Scanner runs', summary.history.length, 'low'],
    ['Findings opened', totalFindings(summary), 'warn'],
    ['Findings suppressed', suppressedDisplayCases(summary).length, 'info'],
    ['Honey-key hits', (summary.honey_key_events ?? []).length, 'crit'],
    ['Verification gaps', topScannerItems(summary).filter((item) => item.status === 'missing' || item.status === 'error').length, 'high'],
  ] as const;
  const max = Math.max(1, ...rows.map((row) => row[1]));
  return (
    <div className="event-mix">
      {rows.map(([label, value, tone]) => (
        <div key={label}>
          <span><i style={{background: severityMeta[tone].dot}} />{label}</span><strong>{value}</strong>
          <em><b style={{width: `${(value / max) * 100}%`, background: severityMeta[tone].dot}} /></em>
        </div>
      ))}
    </div>
  );
}

function ActivityTimelineMini({items}: {items: ActivityItem[]}) {
  return (
    <div className="timeline-mini">
      {items.slice(0, 18).map((item, index) => {
        const hour = item.date ? item.date.getHours() + item.date.getMinutes() / 60 : index;
        return <span key={item.id} style={{left: `${(hour / 24) * 100}%`, background: severityMeta[item.tone].dot}} />;
      })}
      <div><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
    </div>
  );
}

function ActivityRow({item, showTone = false}: {item: ActivityItem; showTone?: boolean}) {
  return (
    <div className="activity-row">
      <time>{item.at}</time>
      <span className="activity-icon">{item.icon}</span>
      <div><strong>{item.label}</strong><em>{item.sub}</em></div>
      {showTone && <SeverityPill tone={item.tone} />}
    </div>
  );
}

function SeverityDistribution({counts}: {counts: ReturnType<typeof severityCounts>}) {
  const total = Math.max(1, counts.critical + counts.elevated + counts.warning + counts.low);
  const segments = [
    ['crit', counts.critical],
    ['high', counts.elevated],
    ['warn', counts.warning],
    ['low', counts.low],
  ] as const;
  return (
    <div className="severity-distribution">
      <div>{segments.map(([tone, value]) => <span key={tone} style={{width: `${(value / total) * 100}%`, background: severityMeta[tone].dot}} />)}</div>
      <p>{segments.map(([tone, value]) => <span key={tone}><i style={{background: severityMeta[tone].dot}} />{value} {severityMeta[tone].label.toLowerCase()}</span>)}</p>
    </div>
  );
}

function BarChart({data, onSurface = false}: {data: {label: string; value: number}[]; onSurface?: boolean}) {
  const max = Math.max(10, ...data.map((item) => item.value));
  return (
    <div className={`bar-chart ${onSurface ? 'on-surface' : ''}`}>
      {data.map((item, index) => {
        const height = Math.max(10, (item.value / max) * 70);
        const lit = index === data.length - 1;
        return (
          <span key={`${item.label}-${index}`}>
            <em>{item.value.toFixed(1)}</em>
            <i style={{height, opacity: lit ? 1 : undefined}} />
            <strong>{item.label}</strong>
          </span>
        );
      })}
    </div>
  );
}

function Donut({value}: {value: number}) {
  const size = 96;
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 10) * circumference;
  return (
    <svg className="donut" width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#fff" strokeWidth={stroke} strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} />
    </svg>
  );
}

function Button({children, variant = 'primary', size = 'md', icon, onClick, disabled}: {children: ReactNode; variant?: 'primary' | 'secondary' | 'ghost' | 'glass' | 'glassOnGlass'; size?: 'sm' | 'md'; icon?: ReactNode; onClick?: () => void; disabled?: boolean}) {
  return <button type="button" className={`button ${variant} ${size}`} onClick={onClick} disabled={disabled}>{icon}{children}</button>;
}

function IconButton({children, label, onClick}: {children: ReactNode; label: string; onClick: () => void}) {
  return <button type="button" className="icon-button" aria-label={label} title={label} onClick={onClick}>{children}</button>;
}

function PaperCard({children, className = '', padded = true, id}: {children: ReactNode; className?: string; padded?: boolean; id?: string}) {
  return <section id={id} className={`paper-card ${padded ? 'padded' : ''} ${className}`}>{children}</section>;
}

function SectionHeader({title, right, icon}: {title: string; right?: ReactNode; icon?: ReactNode}) {
  return <div className="section-header"><h3>{icon}{title}</h3>{right && <div>{right}</div>}</div>;
}

function Eyebrow({children, onSurface = false}: {children: ReactNode; onSurface?: boolean}) {
  return <div className={`eyebrow ${onSurface ? 'on-surface' : ''}`}>{children}</div>;
}

function Chip({children, active = false, dot, onClick}: {children: ReactNode; active?: boolean; dot?: string; onClick?: () => void}) {
  return <button type="button" className={`chip ${active ? 'active' : ''}`} onClick={onClick}>{dot && <i style={{background: dot}} />}{children}</button>;
}

function SeverityPill({tone = 'neutral', label}: {tone?: Tone; label?: string}) {
  const meta = severityMeta[tone];
  return <span className="severity-pill" style={{'--pill-bg': meta.bg, '--pill-fg': meta.fg, '--pill-dot': meta.dot} as CSSProperties}><i />{label ?? meta.label}</span>;
}

function KpiCard({title, value, detail, icon, onClick}: {title: string; value: string; detail: string; icon: ReactNode; onClick: () => void}) {
  return (
    <button type="button" className="kpi-card" onClick={onClick}>
      <div><Eyebrow>{title}</Eyebrow>{icon}</div>
      <strong>{value}</strong>
      <span>{detail}</span>
    </button>
  );
}

function MetricBlock({label, value, detail, tone = 'neutral', icon}: {label: string; value: string; detail?: string; tone?: Tone; icon?: ReactNode}) {
  return (
    <div className="metric-block">
      <div><Eyebrow>{label}</Eyebrow>{icon}</div>
      <strong style={{color: tone !== 'neutral' ? severityMeta[tone].fg : undefined}}>{value}</strong>
      {detail && <span>{detail}</span>}
    </div>
  );
}

function MetricCard({title, value, detail}: {title: string; value: string; detail: string}) {
  return <PaperCard><MetricBlock label={title} value={value} detail={detail} /></PaperCard>;
}

function MetricPill({label, value}: {label: string; value: number}) {
  return <span className="metric-pill"><em>{label}</em><strong>{value}</strong></span>;
}

function KV({label, value}: {label: string; value: string}) {
  return <div className="kv"><span>{label}</span><strong>{value}</strong></div>;
}

function Notice({tone, icon, title, body}: {tone: Tone; icon: ReactNode; title: string; body: string}) {
  return <div className={`notice ${tone}`}><span>{icon}</span><div><strong>{title}</strong><p>{body}</p></div></div>;
}

function EmptyLine({title, detail}: {title: string; detail: string}) {
  return <div className="empty-line"><strong>{title}</strong><span>{detail}</span></div>;
}

function SettingRow({label, sub, children}: {label: string; sub: string; children: ReactNode}) {
  return <div className="setting-row"><div><strong>{label}</strong><span>{sub}</span></div><div>{children}</div></div>;
}

function ScanIcon(props: {size?: number; className?: string}) {
  return <Search {...props} />;
}
