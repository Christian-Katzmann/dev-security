import {CSSProperties, ReactNode, useCallback, useEffect, useMemo, useState} from 'react';
import CatalogHome from './components/catalog/CatalogHome';
import CatalogBrowse from './components/catalog/CatalogBrowse';
import CatalogToolPage from './components/catalog/CatalogToolPage';
import CatalogPackPage from './components/catalog/CatalogPackPage';
import AgentLabView from './components/agent-lab/AgentLabView';
import NeedsRepoTarget from './components/NeedsRepoTarget';
import RotationStatusCard from './components/RotationStatusCard';
import RotationTriggerFlow from './components/RotationTriggerFlow';
import {
  CatalogMutationState,
  CatalogStatusFilter,
  catalogCapabilityLabels,
  catalogCategoryLabels,
  catalogCategoryOrder,
  catalogCredentialLabels,
  catalogDisplayLabels,
  catalogEvidenceLabels,
  catalogIcon,
  catalogInstallDetectionLabels,
  catalogInstallLabels,
  catalogInstallMethodLabels,
  catalogInstallOwnerLabels,
  catalogLifecycleLabels,
  catalogNetworkLabels,
  catalogPackIconCategory,
  catalogPackLabels,
  catalogPackOrder,
  catalogPolicySummary,
  catalogProfileRole,
  catalogProfileTone,
  catalogRunReady,
  catalogRuntimeCopy,
  catalogRuntimeLabel,
  catalogRuntimeTone,
  catalogSearchText,
  catalogStateCopy,
  catalogStatusBucket,
  catalogStatusFilters,
  catalogStatusLabel,
  catalogStatusTone,
  catalogTargetLabels,
  catalogUninstallLabels,
  previewActionLabel,
  previewCanInstall,
  previewCanUninstall,
  previewOwnedPaths,
  previewTone,
  securityPackSearchText,
  securityPackStateLabel,
  securityPackTone,
  shouldShowAdvancedCatalogItem,
} from './components/catalog/catalogHelpers';
import {useCatalogData} from './components/catalog/useCatalogData';
import {humanizeKey, responseErrorMessage, safetyLabelTone, scannerStatusTone, topScannerItems} from './uiHelpers';
import {Tone} from './uiTypes';
import {
  Activity,
  AlertTriangle,
  Archive,
  BarChart3,
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleSlash,
  ClipboardList,
  Clock3,
  Copy,
  Database,
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
  DashboardMode,
  DashboardSummary,
  DisplayCase,
  HoneyIncident,
  HoneyKey,
  HoneyKeyEvent,
  HoneyKeyStatus,
  ProjectRepo,
  ProjectsPayload,
  RecoveryPlaybook,
  RecoveryPlaybookItem,
  RepositorySummary,
  RotationSecretRow,
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
  activeRawFindingCount,
  averageHealth,
  caseBackedRawFindingCount,
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
  preCaseRawFindingCount,
  preCaseScanRepos,
  repoKeyFromPath,
  repoHasPreCaseScan,
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

type TabId = 'overview' | 'findings' | 'honey-keys' | 'scanners' | 'agent-lab' | 'playbooks' | 'verification' | 'activity' | 'reports' | 'settings';
type ViewModeAvailability = 'normal' | 'repo-required' | 'global';
type ViewModeRegistryEntry = {
  supportedModes: DashboardMode[];
  availability: ViewModeAvailability;
  unavailableReason?: string;
};
type NavItem = {id: TabId; label: string; icon: typeof Home};
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

type AllRepoRunItem = {
  repoName: string;
  repoPath: string;
  jobId?: string;
  status: 'waiting' | 'queued' | 'running' | 'complete' | 'failed';
  progress: number;
  message: string;
  error?: string | null;
  scan?: CompletedScan;
};

type AllRepoRun = {
  id: string;
  status: 'running' | 'complete' | 'failed';
  audits: AuditId[];
  concurrency: number;
  startedAt: string;
  finishedAt?: string;
  items: AllRepoRunItem[];
};

type CreatedHoneyKey = {
  key: HoneyKey;
  raw_token: string;
  snippets: Record<string, string>;
  notice: string;
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

type RecoveryPlaybookView = RecoveryPlaybook & {tone: Tone};

const navGroups: {title: string; items: NavItem[]}[] = [
  {
    title: 'Workspace',
    items: [
      {id: 'overview', label: 'Overview', icon: Home},
      {id: 'findings', label: 'Cases', icon: ShieldAlert},
      {id: 'honey-keys', label: 'Honey keys', icon: ShieldCheck},
    ],
  },
  {
    title: 'Operate',
    items: [
      {id: 'scanners', label: 'Tool Catalog', icon: Search},
      {id: 'agent-lab', label: 'Agent Lab', icon: Bot},
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
  findings: 'Cases',
  'honey-keys': 'Honey keys',
  scanners: 'Tool Catalog',
  'agent-lab': 'Agent Lab',
  playbooks: 'Recovery playbooks',
  verification: 'Verification',
  activity: 'Activity',
  reports: 'Reports',
  settings: 'Settings',
};

const viewsByMode: Record<TabId, ViewModeRegistryEntry> = {
  overview: {supportedModes: ['all-repos', 'repo'], availability: 'normal'},
  findings: {supportedModes: ['all-repos', 'repo'], availability: 'normal'},
  activity: {supportedModes: ['all-repos', 'repo'], availability: 'normal'},
  reports: {supportedModes: ['all-repos', 'repo'], availability: 'normal'},
  'honey-keys': {
    supportedModes: ['repo'],
    availability: 'repo-required',
    unavailableReason: 'Pick a repo to inspect Honey keys.',
  },
  playbooks: {
    supportedModes: ['repo'],
    availability: 'repo-required',
    unavailableReason: 'Pick a repo to rerun recovery playbooks.',
  },
  verification: {
    supportedModes: ['repo'],
    availability: 'repo-required',
    unavailableReason: 'Pick a repo to run or inspect checks.',
  },
  // Current Agent Lab context export and proposal review are repo-scoped:
  // /api/agent-lab/context requires repoPath/repoName, and proposals filter by repo.
  'agent-lab': {
    supportedModes: ['repo'],
    availability: 'repo-required',
    unavailableReason: 'Pick a repo to open Agent Lab.',
  },
  scanners: {supportedModes: ['all-repos'], availability: 'global'},
  settings: {supportedModes: ['all-repos'], availability: 'global'},
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

const severityMeta: Record<Tone, {label: string; dot: string; bg: string; fg: string}> = {
  low: {label: 'LOW', dot: 'var(--sev-low)', bg: 'rgba(138,163,154,0.20)', fg: '#3c4b48'},
  warn: {label: 'WARNING', dot: 'var(--sev-warn)', bg: '#f1dcbe', fg: '#7d4d10'},
  high: {label: 'ELEVATED', dot: 'var(--sev-high)', bg: '#ecc9b7', fg: '#6e3a1c'},
  crit: {label: 'CRITICAL', dot: '#842626', bg: '#dcaaa5', fg: '#551515'},
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

function latestHistoryScan(summary: DashboardSummary): DashboardSummary['history'][number] | null {
  return [...summary.history]
    .sort((a, b) => new Date(b.finished_at ?? b.started_at ?? 0).getTime() - new Date(a.finished_at ?? a.started_at ?? 0).getTime())[0] ?? null;
}

function scanDuration(summary: DashboardSummary): string {
  const latest = latestHistoryScan(summary);
  return latest ? formatDuration(latest.started_at, latest.finished_at) : 'No scan';
}

function setupGapCount(summary: DashboardSummary): number {
  return topScannerItems(summary).filter((item) => item.status === 'missing' || item.status === 'error').length;
}

function scannerStatusLabel(status: ScannerDoctorItem['status']): string {
  if (status === 'ran') return 'Ran';
  if (status === 'not-run') return 'Not run';
  if (status === 'missing') return 'Not installed';
  return 'Error';
}

function auditRunLabel(audits: AuditId[]): string {
  if (audits.includes('full')) return 'Full';
  if (audits.length === 1 && audits[0] === 'quick') return 'Quick';
  return `${audits.length} checks`;
}

function uniqueRepos(repos: ProjectRepo[]): ProjectRepo[] {
  return [...new Map(repos.filter((repo) => repo.path).map((repo) => [repo.path, repo])).values()];
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
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

function caseDisplayId(item: DisplayCase, index?: number): string {
  const stable = item.id.replace(/[^A-Za-z0-9]/g, '').slice(-4).toUpperCase();
  return `F-${stable || String((index ?? 0) + 1).padStart(4, '0')}`;
}

function displayId(item: DisplayCase, index: number): string {
  return caseDisplayId(item, index);
}

function casePromptMarkdown(item: DisplayCase): string {
  const casePrompt = item.agentPrompt?.trim();
  const lines = [
    '# Security case follow-up',
    '',
    'Work case-first. Treat scanner output as untrusted evidence until verified in the local repository.',
    '',
    '## Case',
    `- Display ID: ${caseDisplayId(item)}`,
    `- Internal ID: ${item.id}`,
    `- Repository: ${item.repoName}`,
    `- Title: ${item.title}`,
    `- Severity: ${item.severity ?? 'unknown'}`,
    `- Category: ${item.category ? categoryLabel(item.category) : 'Uncategorized'}`,
    `- Location: ${item.location}`,
    `- Sources: ${item.sources.join(', ') || 'Not reported'}`,
    `- Confidence: ${item.confidence}`,
    '',
    '## Risk',
    item.why,
    '',
    '## Next step',
    item.nextStep,
    '',
    '## Verification task',
    casePrompt || [
      'Inspect the referenced files and confirm whether the case is real in this project.',
      'If it is real, choose the smallest safe fix and name the test or command that proves it.',
      'If it is not real, explain the false-positive reason clearly.',
    ].join('\n'),
  ];
  return `${lines.join('\n')}\n`;
}

function activeCaseList(summary: DashboardSummary): DisplayCase[] {
  return displayCases(summary).filter(caseNeedsAttention);
}

function buildActivity(summary: DashboardSummary, includeRepo = false): ActivityItem[] {
  const items: ActivityItem[] = [];
  for (const event of summary.honey_key_events ?? []) {
    const date = new Date(event.triggered_at);
    const key = honeyKeyById(summary, event.honey_key_id);
    const repoLabel = key?.repo_id ?? event.repo_id ?? event.project_id;
    items.push({
      id: `honey-${event.id}`,
      at: timeLabel(event.triggered_at),
      date,
      icon: <ShieldAlert size={18} />,
      label: `Honey-key touched${key?.name ? ` · ${key.name}` : ''}`,
      sub: `${includeRepo ? `${repoLabel} · ` : ''}${event.ip_address ?? 'unknown IP'} · ${event.reason}`,
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
      sub: `${includeRepo ? `${item.repoName} · ` : ''}${item.location}`,
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
      sub: `${includeRepo ? `${scan.repo_name} · ` : ''}${scan.health_score}/100 health · ${scan.status}`,
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

function recoveryPlaybooksFor(summary: DashboardSummary): RecoveryPlaybookView[] {
  const playbooks = summary.recovery_playbooks ?? [];
  return playbooks.map((playbook) => ({...playbook, tone: toneForSeverity(playbook.severity)}));
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
  const grouped = new Map<string, {reason: string; decision_status: string; vex_status: string; cases: number; rawFindings: number}>();
  const source = fromRepos.length ? fromRepos : direct;
  for (const item of source) {
    const key = `${item.reason}:${item.decision_status}:${item.vex_status}`;
    const current = grouped.get(key) ?? {
      reason: item.reason,
      decision_status: item.decision_status,
      vex_status: item.vex_status,
      cases: 0,
      rawFindings: 0,
    };
    current.cases += item.cases;
    current.rawFindings += item.findings;
    grouped.set(key, current);
  }
  return [...grouped.values()].sort((a, b) => b.rawFindings - a.rawFindings || b.cases - a.cases);
}

function activeFindingCount(summary: DashboardSummary): number {
  return summary.active_findings?.length ?? summary.findings.filter((finding) => !finding.suppressed).length;
}

function suppressedFindingCount(summary: DashboardSummary): number {
  return summary.suppressed_findings?.length ?? summary.findings.filter((finding) => finding.suppressed).length;
}

function caseSeverityCounts(cases: DisplayCase[]) {
  return cases.reduce(
    (counts, item) => {
      const tone = toneForCase(item);
      if (tone === 'crit') counts.critical += 1;
      else if (tone === 'high') counts.elevated += 1;
      else if (tone === 'warn') counts.warning += 1;
      else counts.low += 1;
      return counts;
    },
    {critical: 0, elevated: 0, warning: 0, low: 0},
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [catalogRoute, setCatalogRoute] = useState<CatalogRoute>({kind: 'home'});
  const [summary, setSummary] = useState<DashboardSummary>(emptySummary);
  const [projectRepos, setProjectRepos] = useState<ProjectRepo[]>([]);
  const [customRepos, setCustomRepos] = useState<ProjectRepo[]>(() => loadCustomRepos());
  const [target, setTarget] = useState<TargetSelection>({mode: 'all-repos'});
  const [isCheckOpen, setIsCheckOpen] = useState(false);
  const [selectedAudits, setSelectedAudits] = useState<AuditId[]>(defaultAudits);
  const [isRunningCheck, setIsRunningCheck] = useState(false);
  const [activeJob, setActiveJob] = useState<CheckJob | null>(null);
  const [allRepoRun, setAllRepoRun] = useState<AllRepoRun | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
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
  }, [target]);

  useEffect(() => {
    if (viewIsUnavailableInMode(activeTab, target.mode)) {
      setActiveTab('overview');
    }
  }, [activeTab, target.mode]);

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
      setTarget({mode: 'repo', repo});
      return;
    }
    if (value === 'all-repos' || value === 'dashboard') {
      setTarget({mode: 'all-repos'});
      return;
    }
    const path = value.replace(/^repo:/, '');
    const repo = targetRepos.find((item) => item.path === path);
    if (repo) setTarget({mode: 'repo', repo});
  }

  function toggleAudit(auditId: AuditId) {
    setRunError(null);
    if (activeJob?.status === 'complete') setActiveJob(null);
    if (auditId === 'platform-posture' && !(summary.environment?.scm_token_present ?? true)) {
      return;
    }
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

  function updateAllRepoRunItem(runId: string, repoPath: string, updates: Partial<AllRepoRunItem>) {
    setAllRepoRun((current) => {
      if (!current || current.id !== runId) return current;
      return {
        ...current,
        items: current.items.map((item) => item.repoPath === repoPath ? {...item, ...updates} : item),
      };
    });
  }

  async function startRepoCheck(repo: ProjectRepo, audits: AuditId[]): Promise<CheckJob> {
    const response = await fetch('/api/run-check', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({repoPath: repo.path, audits}),
    });
    if (!response.ok) throw new Error(await responseErrorMessage(response, `Unable to start checks for ${repo.name}`));
    const payload: {job: CheckJob} = await response.json();
    return payload.job;
  }

  async function pollRepoCheck(runId: string, repoPath: string, jobId: string): Promise<CheckJob> {
    for (;;) {
      await wait(1200);
      const response = await fetch(`/api/check-status?jobId=${encodeURIComponent(jobId)}`, {cache: 'no-store'});
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Unable to read check progress'));
      const payload: {job: CheckJob} = await response.json();
      updateAllRepoRunItem(runId, repoPath, {
        status: payload.job.status,
        progress: payload.job.progress,
        message: payload.job.currentStep ?? payload.job.message,
        error: payload.job.error,
        scan: payload.job.scan,
      });
      if (payload.job.status === 'complete' || payload.job.status === 'failed') return payload.job;
    }
  }

  async function runAllRepoChecks(auditsOverride: AuditId[]) {
    const repos = uniqueRepos(targetRepos);
    if (!repos.length) {
      setRunError('Add or select at least one repo before running all-repo checks.');
      setIsCheckOpen(true);
      return;
    }
    const tokenPresent = summary.environment?.scm_token_present ?? true;
    const audits = tokenPresent ? auditsOverride : auditsOverride.filter((id) => id !== 'platform-posture');
    const effectiveAudits = audits.length ? audits : defaultAudits;
    const runId = `all-repos-${Date.now()}`;
    const concurrency = Math.min(3, repos.length);
    setSelectedAudits(effectiveAudits);
    setIsCheckOpen(false);
    setIsRunningCheck(true);
    setActiveJob(null);
    setRunError(null);
    setAllRepoRun({
      id: runId,
      status: 'running',
      audits: effectiveAudits,
      concurrency,
      startedAt: new Date().toISOString(),
      items: repos.map((repo) => ({
        repoName: repo.name,
        repoPath: repo.path,
        status: 'waiting',
        progress: 0,
        message: 'Waiting for a runner',
      })),
    });

    const queue = [...repos];
    const failures: string[] = [];
    async function worker() {
      for (;;) {
        const repo = queue.shift();
        if (!repo) return;
        updateAllRepoRunItem(runId, repo.path, {status: 'queued', progress: 0, message: 'Queued'});
        try {
          const job = await startRepoCheck(repo, effectiveAudits);
          updateAllRepoRunItem(runId, repo.path, {
            jobId: job.id,
            status: job.status,
            progress: job.progress,
            message: job.message,
          });
          const terminal = await pollRepoCheck(runId, repo.path, job.id);
          if (terminal.status === 'failed') failures.push(`${repo.name}: ${terminal.error ?? 'check failed'}`);
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Unable to run checks';
          failures.push(`${repo.name}: ${message}`);
          updateAllRepoRunItem(runId, repo.path, {status: 'failed', progress: 100, message: 'Check failed', error: message});
        }
      }
    }

    await Promise.all(Array.from({length: concurrency}, () => worker()));
    await loadSummary();
    setAllRepoRun((current) => current && current.id === runId ? {
      ...current,
      status: failures.length ? 'failed' : 'complete',
      finishedAt: new Date().toISOString(),
    } : current);
    setIsRunningCheck(false);
    if (failures.length) {
      setRunError(`${failures.length} repo check${failures.length === 1 ? '' : 's'} failed. Open Verification for the setup details.`);
    }
  }

  async function runCheck(auditsOverride = selectedAudits) {
    if (target.mode !== 'repo') {
      setRunError('Select a repo target before running checks.');
      setIsCheckOpen(true);
      return;
    }
    const tokenPresent = summary.environment?.scm_token_present ?? true;
    const audits = tokenPresent ? auditsOverride : auditsOverride.filter((id) => id !== 'platform-posture');
    setIsRunningCheck(true);
    setActiveJob(null);
    setAllRepoRun(null);
    setRunError(null);
    try {
      const response = await fetch('/api/run-check', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({repoPath: target.repo.path, audits}),
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
    if (target.mode === 'repo') {
      setIsCheckOpen(true);
      void runCheck(['full']);
    } else {
      void runAllRepoChecks(['full']);
    }
  }

  function runQuickCheck() {
    setSelectedAudits(['quick']);
    if (target.mode === 'repo') {
      setIsCheckOpen(true);
      void runCheck(['quick']);
    } else {
      void runAllRepoChecks(['quick']);
    }
  }

  function chooseChecks(profile?: string) {
    if (profile && auditOptions.some((option) => option.id === profile)) {
      setSelectedAudits([profile as AuditId]);
    }
    setIsCheckOpen(true);
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
    'agent-lab': (scopedSummary.agent_lab_proposals ?? []).filter((proposal) => proposal.approval_state === 'pending').length,
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
            onRunAll={runFullCheck}
            onRunQuick={runQuickCheck}
            onChooseChecks={() => chooseChecks()}
            showRunControls={activeTab !== 'overview'}
            canRun={target.mode === 'repo' || targetRepos.length > 0}
            runAllHint={target.mode === 'repo' ? 'Run all configured checks for the selected repo' : 'Run full checks for every known repo, up to 3 at once'}
          />
          {isCheckOpen && (
            <RunCheckSheet
              target={target}
              targetRepos={targetRepos}
              selectedAudits={selectedAudits}
              activeJob={activeJob}
              isRunningCheck={isRunningCheck}
              runError={runError}
              scmTokenPresent={summary.environment?.scm_token_present ?? true}
              onToggleAudit={toggleAudit}
              onRun={() => {
                if (target.mode === 'all-repos') {
                  void runAllRepoChecks(selectedAudits);
                } else {
                  void runCheck();
                }
              }}
              onTargetChange={selectTarget}
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
              globalSummary={summary}
              search={search}
              target={target}
              targetRepos={targetRepos}
              updatedAt={updatedAt}
              error={error}
              posture={posture}
              catalogRoute={catalogRoute}
              onCatalogRouteChange={setCatalogRoute}
              onOpenTab={setActiveTab}
              onChooseChecks={chooseChecks}
              onRunQuick={runQuickCheck}
              onRunAll={runFullCheck}
              activeJob={activeJob}
              allRepoRun={allRepoRun}
              isRunningCheck={isRunningCheck}
              runError={runError}
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
  globalSummary,
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
  onRunAll,
  activeJob,
  allRepoRun,
  isRunningCheck,
  runError,
  onCaseDecision,
  onRefresh,
  onTargetChange,
}: {
  tab: TabId;
  summary: DashboardSummary;
  globalSummary: DashboardSummary;
  search: string;
  target: TargetSelection;
  targetRepos: ProjectRepo[];
  updatedAt: Date | null;
  error: string | null;
  posture: {score: number; delta: number; week: {label: string; value: number}[]};
  catalogRoute: CatalogRoute;
  onCatalogRouteChange: (route: CatalogRoute) => void;
  onOpenTab: (tab: TabId) => void;
  onChooseChecks: (profile?: string) => void;
  onRunQuick: () => void;
  onRunAll: () => void;
  activeJob: CheckJob | null;
  allRepoRun: AllRepoRun | null;
  isRunningCheck: boolean;
  runError: string | null;
  onCaseDecision: (caseId: string, repoName: string, status: CaseDecisionStatus | 'open', note: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  onTargetChange: (value: string) => void;
}) {
  if (target.mode === 'repo' && summary.repos.length === 0 && tab !== 'honey-keys' && tab !== 'agent-lab' && tab !== 'settings') {
    return <EmptyRepoView repoName={target.repo.name} onRunQuick={onRunQuick} onChooseChecks={onChooseChecks} />;
  }
  if (tab === 'overview') {
    return (
      <OverviewView
        summary={summary}
        globalSummary={globalSummary}
        target={target}
        targetRepos={targetRepos}
        posture={posture}
        error={error}
        activeJob={activeJob}
        allRepoRun={allRepoRun}
        isRunningCheck={isRunningCheck}
        runError={runError}
        onOpenTab={onOpenTab}
        onRunQuick={onRunQuick}
        onRunAll={onRunAll}
        onChooseChecks={onChooseChecks}
        onTargetChange={onTargetChange}
      />
    );
  }
  if (tab === 'findings') return <FindingsView summary={summary} search={search} target={target} onCaseDecision={onCaseDecision} />;
  if (tab === 'honey-keys') return <HoneyKeysView summary={summary} target={target} onRefresh={onRefresh} />;
  if (tab === 'scanners') return <CatalogRouter route={catalogRoute} summary={summary} onRouteChange={onCatalogRouteChange} onRefresh={onRefresh} onChooseChecks={onChooseChecks} />;
  if (tab === 'agent-lab') return <AgentLabView summary={summary} target={target} targetRepos={targetRepos} onRefresh={onRefresh} onTargetChange={onTargetChange} />;
  if (tab === 'playbooks') return <PlaybooksView summary={summary} target={target} targetRepos={targetRepos} onChooseChecks={onChooseChecks} onTargetChange={onTargetChange} />;
  if (tab === 'verification') return <VerificationView summary={summary} target={target} targetRepos={targetRepos} onChooseChecks={onChooseChecks} onTargetChange={onTargetChange} />;
  if (tab === 'activity') return <ActivityView summary={summary} search={search} target={target} />;
  if (tab === 'reports') return <ReportsView summary={summary} target={target} />;
  return <SettingsView summary={summary} target={target} targetRepos={targetRepos} updatedAt={updatedAt} onTargetChange={onTargetChange} />;
}

// CatalogRouter — dispatches the Tool Catalog substate to the four route
// shells. Navigation between catalog routes uses callbacks (onOpenTool /
// onOpenPack / onOpenBrowse / onBack); no URL routing yet. summary +
// onRefresh flow through to every shell so each one can call useCatalogData
// without re-deriving the same plumbing.
function CatalogRouter({
  route,
  summary,
  onRouteChange,
  onRefresh,
  onChooseChecks,
}: {
  route: CatalogRoute;
  summary: DashboardSummary;
  onRouteChange: (route: CatalogRoute) => void;
  onRefresh: () => Promise<void>;
  onChooseChecks: (profile?: string) => void;
}) {
  const originOf = (kind: CatalogRoute['kind']): 'home' | 'browse' => (kind === 'browse' ? 'browse' : 'home');
  if (route.kind === 'browse') {
    return (
      <CatalogBrowse
        summary={summary}
        onRefresh={onRefresh}
        onOpenTool={(id) => onRouteChange({kind: 'tool', id, from: 'browse'})}
        onBack={() => onRouteChange({kind: 'home'})}
      />
    );
  }
  if (route.kind === 'tool') {
    return (
      <CatalogToolPage
        summary={summary}
        onRefresh={onRefresh}
        toolId={route.id}
        onBack={() => onRouteChange(route.from === 'browse' ? {kind: 'browse'} : {kind: 'home'})}
      />
    );
  }
  if (route.kind === 'pack') {
    return (
      <CatalogPackPage
        summary={summary}
        onRefresh={onRefresh}
        packId={route.id}
        onBack={() => onRouteChange(route.from === 'browse' ? {kind: 'browse'} : {kind: 'home'})}
        onOpenTool={(id) => onRouteChange({kind: 'tool', id, from: originOf(route.kind)})}
        onOpenProfile={(profile) => onChooseChecks(profile)}
      />
    );
  }
  return (
    <CatalogHome
      summary={summary}
      onRefresh={onRefresh}
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
}: {
  active: TabId;
  counts: Partial<Record<TabId, number>>;
  target: TargetSelection;
  targetRepos: ProjectRepo[];
  onTargetChange: (value: string) => void;
  onNav: (tab: TabId) => void;
}) {
  return (
    <aside className="mist-sidebar">
      <div className="dotgrid-dark mist-sidebar-texture" />
      <div className="workspace-card">
        <div className="workspace-mark"><ShieldCheck size={17} /></div>
        <div className="workspace-copy">
          <div className="workspace-title">{targetLabel(target)}</div>
          <div className="workspace-subtitle">{target.mode === 'repo' ? 'Specific repo' : 'All repositories'}</div>
          <select
            className="workspace-select"
            name="workspace-target"
            aria-label="Workspace target"
            value={targetValue(target)}
            onChange={(event) => onTargetChange(event.target.value)}
          >
            <option value="all-repos">All repos</option>
            {targetRepos.map((repo) => (
              <option key={repo.path} value={`repo:${repo.path}`}>Specific repo · {repo.name}</option>
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
            {group.items.map((item) => {
              const unavailable = viewIsUnavailableInMode(item.id, target.mode);
              const scope = navScopeLabel(item.id);
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`nav-row ${active === item.id ? 'active' : ''}`}
                  onClick={() => onNav(item.id)}
                  disabled={unavailable}
                  title={unavailable ? viewsByMode[item.id].unavailableReason : undefined}
                >
                  <item.icon size={17} />
                  <span>{item.label}</span>
                  {!!counts[item.id] && <strong>{counts[item.id]}</strong>}
                  {scope && <em className="nav-scope">{scope}</em>}
                </button>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <button type="button" className={`nav-row ${active === 'settings' ? 'active' : ''}`} onClick={() => onNav('settings')}>
          <Settings size={17} />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}

function viewIsUnavailableInMode(tab: TabId, mode: DashboardMode): boolean {
  const entry = viewsByMode[tab];
  return entry.availability === 'repo-required' && mode !== 'repo';
}

function navScopeLabel(tab: TabId): string | null {
  const entry = viewsByMode[tab];
  if (entry.availability === 'repo-required') return 'Repo';
  if (entry.availability === 'global') return 'Global';
  return null;
}

function Toolbar({
  title,
  targetLabel,
  posture,
  search,
  setSearch,
  isLoading,
  error,
  onRunAll,
  onRunQuick,
  onChooseChecks,
  showRunControls,
  canRun,
  runAllHint,
}: {
  title: string;
  targetLabel: string;
  posture: {score: number; delta: number};
  search: string;
  setSearch: (value: string) => void;
  isLoading: boolean;
  error: string | null;
  onRunAll: () => void;
  onRunQuick: () => void;
  onChooseChecks: () => void;
  showRunControls: boolean;
  canRun: boolean;
  runAllHint: string;
}) {
  const searchPlaceholder = title === 'Tool Catalog' ? 'Search tools, packs' : title === 'Agent Lab' ? 'Search proposals, tools' : 'Search cases, manifests';
  const runAllLabel = canRun ? 'Run all' : 'Run all (pick a repo)';
  const runQuickLabel = canRun ? 'Run quick' : 'Run quick (pick a repo)';
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
        <input
          type="search"
          name="dashboard-search"
          aria-label="Search the dashboard"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={searchPlaceholder}
        />
        <kbd>⌘K</kbd>
      </label>
      {showRunControls && (
        <>
          <Button
            variant="secondary"
            size="sm"
            icon={<SlidersHorizontal size={14} />}
            onClick={onChooseChecks}
            title={canRun ? 'Choose checks to run' : 'Add a repo first'}
            ariaLabel="Choose checks"
          >
            Choose...
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={<Play size={14} />}
            onClick={onRunQuick}
            title={canRun ? 'Run the quick safety sweep' : 'Add a repo first'}
            ariaLabel={runQuickLabel}
          >
            Run quick
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw size={14} />}
            onClick={onRunAll}
            title={runAllHint}
            ariaLabel={runAllLabel}
          >
            Run all
          </Button>
        </>
      )}
    </header>
  );
}

function RunCheckSheet({
  target,
  targetRepos,
  selectedAudits,
  activeJob,
  isRunningCheck,
  runError,
  scmTokenPresent,
  onToggleAudit,
  onRun,
  onTargetChange,
  onClose,
  onNewCheck,
  onViewResults,
}: {
  target: TargetSelection;
  targetRepos: ProjectRepo[];
  selectedAudits: AuditId[];
  activeJob: CheckJob | null;
  isRunningCheck: boolean;
  runError: string | null;
  scmTokenPresent: boolean;
  onToggleAudit: (audit: AuditId) => void;
  onRun: () => void;
  onTargetChange: (value: string) => void;
  onClose: () => void;
  onNewCheck: () => void;
  onViewResults: () => void;
}) {
  const isAllRepos = target.mode === 'all-repos';
  const allReposCount = isAllRepos ? targetRepos.length : 0;
  const noReposAvailable = isAllRepos && allReposCount === 0;
  const startDisabled = noReposAvailable || isRunningCheck;
  const startTitle = noReposAvailable
    ? 'Add a repo before running checks'
    : isAllRepos
      ? `Run the selected checks across ${allReposCount} repo${allReposCount === 1 ? '' : 's'}`
      : undefined;
  const headlineSubtitle = activeJob?.status === 'complete'
    ? 'Latest local scan data has been saved.'
    : isAllRepos
      ? `Running across ${allReposCount} repo${allReposCount === 1 ? '' : 's'}. Existing backend behavior stays unchanged.`
      : 'Choose the scanners to run. Existing backend behavior stays unchanged.';
  return (
    <section className="run-sheet">
      <div className="run-sheet-head">
        <div>
          <Eyebrow>{activeJob?.status === 'complete' ? 'Security check complete' : 'Run security check'}</Eyebrow>
          <h2>{target.mode === 'repo' ? target.repo.name : isAllRepos ? `All repos · ${allReposCount}` : 'Run security check'}</h2>
          <p>{headlineSubtitle}</p>
        </div>
        <div className="run-actions">
          {activeJob?.status === 'complete' ? (
            <>
              <Button variant="secondary" onClick={onNewCheck}>New check</Button>
              <Button onClick={onViewResults}>View cases</Button>
            </>
          ) : (
            <>
              <Button variant="ghost" onClick={onClose} disabled={isRunningCheck}>Cancel</Button>
              <Button onClick={onRun} disabled={startDisabled} title={startTitle}>{isRunningCheck ? 'Checking...' : 'Start check'}</Button>
            </>
          )}
        </div>
      </div>
      {noReposAvailable && activeJob?.status !== 'complete' && (
        <NeedsRepoTarget
          targetRepos={targetRepos}
          onTargetChange={onTargetChange}
          message="Add a repo to run checks against."
        />
      )}
      {activeJob?.status !== 'complete' && (
        <div className="audit-grid">
          {auditOptions.map((option) => {
            const tokenGate = option.id === 'platform-posture' && !scmTokenPresent;
            const tileClass = [
              'audit-tile',
              selectedAudits.includes(option.id) ? 'selected' : '',
              tokenGate ? 'gated' : '',
            ].filter(Boolean).join(' ');
            return (
              <label
                key={option.id}
                className={tileClass}
                title={tokenGate ? 'Set SCM_TOKEN in the environment that launches the dashboard, then reload.' : undefined}
              >
                <input
                  type="checkbox"
                  checked={selectedAudits.includes(option.id) && !tokenGate}
                  onChange={() => onToggleAudit(option.id)}
                  disabled={isRunningCheck || tokenGate}
                />
                <span>
                  {option.label}
                  {tokenGate && <small className="audit-tile-gate"> · Needs SCM_TOKEN</small>}
                </span>
                <em>{option.estimate}</em>
                <p>{option.description}</p>
                {tokenGate && (
                  <p className="audit-tile-gate-note">
                    Stop the dashboard, export <code>SCM_TOKEN=&lt;github-or-gitlab-token&gt;</code> in the same shell, then run <code>security-scan dashboard</code> again to enable this check.
                  </p>
                )}
              </label>
            );
          })}
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
          <MetricBlock label="Raw findings saved" value={String(activeJob.scan?.findings.length ?? 0)} />
          <MetricBlock label="Setup gaps" value={String(incompleteToolCount(activeJob.scan))} />
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

function OverviewView({
  summary,
  globalSummary,
  target,
  targetRepos,
  posture,
  error,
  activeJob,
  allRepoRun,
  isRunningCheck,
  runError,
  onOpenTab,
  onRunQuick,
  onRunAll,
  onChooseChecks,
  onTargetChange,
}: {
  summary: DashboardSummary;
  globalSummary: DashboardSummary;
  target: TargetSelection;
  targetRepos: ProjectRepo[];
  posture: {score: number; delta: number; week: {label: string; value: number}[]};
  error: string | null;
  activeJob: CheckJob | null;
  allRepoRun: AllRepoRun | null;
  isRunningCheck: boolean;
  runError: string | null;
  onOpenTab: (tab: TabId) => void;
  onRunQuick: () => void;
  onRunAll: () => void;
  onChooseChecks: (profile?: string) => void;
  onTargetChange: (value: string) => void;
}) {
  const scopeLabel = targetLabel(target);
  const cases = activeCaseList(summary);
  const rawCounts = severityCounts(summary);
  const caseCounts = caseSeverityCounts(cases);
  const rawFindingTotal = activeRawFindingCount(summary) || rawCounts.critical + rawCounts.elevated + rawCounts.warning + rawCounts.low;
  const loadedFindingRows = totalFindings(summary);
  const nonLowFindings = rawCounts.critical + rawCounts.elevated + rawCounts.warning;
  const preCaseRepos = preCaseScanRepos(summary);
  const preCaseRawTotal = preCaseRawFindingCount(summary);
  const caseBackedRawTotal = caseBackedRawFindingCount(summary);
  const openCaseValue = String(cases.length);
  const rawFindingDetail = preCaseRawTotal
    ? target.mode === 'repo'
      ? `${preCaseRawTotal} pre-cases raw findings · rescan to build cases`
      : `${caseBackedRawTotal} case-backed raw · ${preCaseRawTotal} pre-cases raw need rescan`
    : rawFindingTotal > loadedFindingRows
    ? `${rawFindingTotal} raw findings · ${loadedFindingRows} rows loaded`
    : `${rawFindingTotal || loadedFindingRows} raw findings · ${nonLowFindings} non-low`;
  const honeyCounts = honeyKeyCounts(summary);
  const scanners = topScannerItems(globalSummary);
  const catalogCount = toolCatalogItems(globalSummary).length || scanners.length;
  const scannerHealthy = scanners.filter((item) => item.status === 'ran').length;
  const activities = buildActivity(summary, target.mode === 'all-repos');
  const recentActivities = activities.slice(0, 6);
  const lastScan = latestScanTime(summary);
  // summary.repos[].repo is the slugified scan-history key (e.g.
  // ``besk-ftigelse.dk``); ProjectRepo.name is the un-slugified display name
  // (``beskæftigelse.dk``). Match against the slug so per-repo rotation state
  // resolves for repos whose name contains non-ASCII characters.
  const rotationSignal =
    target.mode === 'repo'
      ? summary.repos.find((entry) => entry.repo === repoKeyFromPath(target.repo.path))?.rotation_state ?? null
      : null;
  // "View full diagnostic" routes to Verification, which is repo-required.
  // In All Repos mode with a single underlying repo we auto-select it; with
  // multiple repos we hide the link so the affordance is never dead.
  const diagnosticAutoRepoValue: string | null =
    target.mode === 'all-repos' && targetRepos.length === 1
      ? `repo:${targetRepos[0].path}`
      : null;
  const canOpenDiagnostic = target.mode === 'repo' || diagnosticAutoRepoValue !== null;
  const headline = cases[0]
    ? `${severityLabelForCase(cases[0])}: ${cases[0].title}`
    : preCaseRepos.length
      ? target.mode === 'repo'
        ? 'This older scan needs a fresh run before cases can be grouped.'
        : `${preCaseRepos.length} older scan${preCaseRepos.length === 1 ? '' : 's'} need a fresh run before cases are complete.`
    : summary.repos.length
      ? 'Quiet overnight. No active cases from the checks that ran.'
      : 'Choose a repo and run a quick safety sweep.';
  return (
    <div className="view-stack">
      <section className="hero-digest">
        <div className="dotgrid-light hero-dots" />
        <div className="hero-copy">
          <Eyebrow onSurface>Today · {new Intl.DateTimeFormat(undefined, {weekday: 'long', month: 'long', day: 'numeric'}).format(new Date())} · {scopeLabel}</Eyebrow>
          <h1>{headline}</h1>
          <div className="hero-actions">
            <Button variant="glassOnGlass" onClick={() => onOpenTab('findings')}>Open cases</Button>
            <Button variant="glass" icon={<Activity size={15} />} onClick={() => onOpenTab('activity')}>See activity</Button>
          </div>
        </div>
        <div className="hero-metrics">
          <Donut value={posture.score} />
          <div className="posture-big">
            <Eyebrow onSurface>Posture · 30 d · {scopeLabel}</Eyebrow>
            <strong>{posture.score.toFixed(1)}</strong><span>/ 10</span>
            <em>{posture.delta >= 0 ? `+${posture.delta.toFixed(1)}` : posture.delta.toFixed(1)} vs previous</em>
          </div>
          <div className="hero-bars">
            <Eyebrow onSurface>Posture · 7 d · {scopeLabel}</Eyebrow>
            <BarChart data={posture.week} onSurface />
          </div>
        </div>
      </section>

      <section className="kpi-grid">
        <KpiCard title="Open cases" value={openCaseValue} detail={`${scopeLabel} · ${rawFindingDetail}`} icon={<ShieldAlert size={18} />} onClick={() => onOpenTab('findings')} />
        <KpiCard title="Honey keys armed" value={String(honeyCounts.active)} detail={`${scopeLabel} · ${honeyCounts.triggered ? `${honeyCounts.triggered} tripped` : 'all quiet'}`} icon={<ShieldCheck size={18} />} onClick={() => onOpenTab('honey-keys')} />
        <KpiCard title="Tool Catalog" value={`${scannerHealthy} / ${Math.max(scanners.length, 1)}`} detail={`Across all repos · ${catalogCount} catalog entries`} icon={<ScanIcon size={18} />} onClick={() => onOpenTab('scanners')} />
      </section>

      <ScanControlPanel
        summary={summary}
        target={target}
        targetRepos={targetRepos}
        activeJob={activeJob}
        allRepoRun={allRepoRun}
        isRunningCheck={isRunningCheck}
        runError={runError}
        onRunQuick={onRunQuick}
        onRunAll={onRunAll}
        onChooseChecks={onChooseChecks}
        onOpenDiagnostic={canOpenDiagnostic ? () => {
          if (diagnosticAutoRepoValue) onTargetChange(diagnosticAutoRepoValue);
          onOpenTab('verification');
        } : undefined}
      />

      {!!preCaseRepos.length && <PreCaseScanNote repos={preCaseRepos} rawFindingTotal={preCaseRawTotal} />}

      {target.mode === 'all-repos' && <RepositoryComparisonStrip summary={summary} cases={cases} />}

      {error && <Notice tone="warn" icon={<AlertTriangle size={17} />} title="Dashboard data could not refresh" body="Saved data may be older than shown." />}

      <section className="split-grid wide-left">
        <PaperCard>
          <SectionHeader
            title="Open cases"
            right={<div className="section-actions"><ScopePill label={scopeLabel} /><button onClick={() => onOpenTab('findings')}>All {cases.length} <ChevronRight size={14} /></button></div>}
          />
          <SeverityDistribution counts={caseCounts} />
          <div className="soft-list">
            {cases.slice(0, 5).map((item, index) => <FindingLine key={item.id} item={item} index={index} onClick={() => onOpenTab('findings')} />)}
            {!cases.length && <EmptyLine title="No active cases" detail={lastScan ? `Latest scan ${formatDate(lastScan)}` : 'No scan has run yet'} />}
          </div>
        </PaperCard>
        <PaperCard>
          <SectionHeader
            title="Recent activity"
            right={<div className="section-actions"><ScopePill label={scopeLabel} /><button onClick={() => onOpenTab('activity')}>All <ChevronRight size={14} /></button></div>}
          />
          <ActivityTimelineMini items={recentActivities} />
          <div className="activity-list compact">
            {recentActivities.map((item) => <ActivityRow key={item.id} item={item} />)}
            {!activities.length && <EmptyLine title="No activity yet" detail="Run a scan to build the local record." />}
          </div>
        </PaperCard>
      </section>

      {target.mode === 'repo' && (
        <RotationStatusCard repo={target.repo} precomputed={rotationSignal} />
      )}
    </div>
  );
}

function ScanControlPanel({
  summary,
  target,
  targetRepos,
  activeJob,
  allRepoRun,
  isRunningCheck,
  runError,
  onRunQuick,
  onRunAll,
  onChooseChecks,
  onOpenDiagnostic,
}: {
  summary: DashboardSummary;
  target: TargetSelection;
  targetRepos: ProjectRepo[];
  activeJob: CheckJob | null;
  allRepoRun: AllRepoRun | null;
  isRunningCheck: boolean;
  runError: string | null;
  onRunQuick: () => void;
  onRunAll: () => void;
  onChooseChecks: (profile?: string) => void;
  onOpenDiagnostic?: () => void;
}) {
  const scopeLabel = targetLabel(target);
  const latest = latestRepoScan(summary);
  const scanners = topScannerItems(summary);
  const ran = scanners.filter((item) => item.status === 'ran').length;
  const notRun = scanners.filter((item) => item.status === 'not-run').length;
  const gaps = setupGapCount(summary);
  const cases = displayCases(summary).length;
  const activeRun = target.mode === 'all-repos' ? allRepoRun : null;
  const runLabel = activeRun?.status === 'running'
    ? `${auditRunLabel(activeRun.audits)} checks running`
    : latest
    ? `${latest.profile || 'Scan'} completed`
    : 'No saved scan yet';
  const runDetail = latest
    ? `${scopeLabel} · ${formatDate(latest.last_scan)} · ${latest.status}`
    : `${scopeLabel} · run a quick sweep to create the first local record`;
  const canRunAllRepos = target.mode === 'repo' || targetRepos.length > 0;

  return (
    <PaperCard className="scan-control-card">
      <SectionHeader
        title="Scan control"
        right={onOpenDiagnostic
          ? <button className="text-link" type="button" onClick={onOpenDiagnostic}>View full diagnostic <ChevronRight size={14} /></button>
          : <span className="text-link disabled" title="Available in repo mode">View full diagnostic</span>}
      />
      <div className="scan-control-layout">
        <div className="scan-control-main">
          <div className="scan-control-headline">
            <div>
              <Eyebrow>{target.mode === 'all-repos' ? 'Daily driver · all repos' : 'Daily driver · selected repo'}</Eyebrow>
              <h2>{runLabel}</h2>
              <p>{runDetail}</p>
            </div>
            <ScopePill label={scopeLabel} />
          </div>
          <div className="scan-metric-grid">
            <ScanMetric label="Health" value={latest ? `${latest.health}/100` : 'None'} detail={latest ? 'latest saved scan' : 'no local record'} />
            <ScanMetric label="Saved cases" value={String(cases)} detail="grouped user-visible cases" />
            <ScanMetric label="Setup gaps" value={String(gaps)} detail={`${ran}/${Math.max(scanners.length, 1)} checks ran`} />
            <ScanMetric label="Duration" value={scanDuration(summary)} detail={latest ? latest.profile || 'scan profile' : 'waiting for first run'} />
          </div>
        </div>
        <div className="scan-control-actions-panel">
          <Button icon={<Play size={14} />} onClick={onRunQuick} disabled={isRunningCheck || !canRunAllRepos} title={canRunAllRepos ? 'Run the quick safety sweep' : 'Add a repo first'}>Run quick</Button>
          <Button variant="secondary" icon={<SlidersHorizontal size={14} />} onClick={() => onChooseChecks()} disabled={isRunningCheck || !canRunAllRepos} title={target.mode === 'repo' ? 'Choose checks for this repo' : canRunAllRepos ? `Choose checks across ${targetRepos.length} repo${targetRepos.length === 1 ? '' : 's'}` : 'Add a repo first'}>Choose checks</Button>
          <Button variant="secondary" icon={<RefreshCw size={14} />} onClick={onRunAll} disabled={isRunningCheck || !canRunAllRepos} title={target.mode === 'all-repos' ? 'Run full checks for every known repo, up to 3 at once' : 'Run full checks for the selected repo'}>{target.mode === 'all-repos' ? 'Run all repos' : 'Run all'}</Button>
          <p>{target.mode === 'all-repos' ? 'All-repo runs queue with a 3-repo fan-out limit.' : 'Runs stay local and write into the SQLite history store.'}</p>
        </div>
      </div>

      <LiveScanProgress activeJob={activeJob} allRepoRun={allRepoRun} target={target} />
      {runError && <div className="inline-error compact">{runError}</div>}

      <div className="scan-inventory-panel">
        <div>
          <Eyebrow>Scanner inventory</Eyebrow>
          <p>{scannerCoverageSummary(summary)}</p>
        </div>
        <div className="scan-inventory-counts">
          <ScanStatusCount label="Ran" value={ran} tone="good" />
          <ScanStatusCount label="Setup gaps" value={gaps} tone={gaps ? 'gap' : 'quiet'} />
          <ScanStatusCount label="Not run" value={notRun} tone="neutral" />
        </div>
      </div>
      <ScannerInventoryMini scanners={scanners} />
      {target.mode === 'all-repos' && <RepoScanStrip summary={summary} />}
    </PaperCard>
  );
}

function ScanMetric({label, value, detail}: {label: string; value: string; detail: string}) {
  return (
    <div className="scan-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{detail}</em>
    </div>
  );
}

function ScanStatusCount({label, value, tone}: {label: string; value: number; tone: 'good' | 'gap' | 'quiet' | 'neutral'}) {
  return (
    <span className={`scan-status-count ${tone}`}>
      <strong>{value}</strong>
      <em>{label}</em>
    </span>
  );
}

function LiveScanProgress({activeJob, allRepoRun, target}: {activeJob: CheckJob | null; allRepoRun: AllRepoRun | null; target: TargetSelection}) {
  if (target.mode === 'all-repos' && allRepoRun) {
    const complete = allRepoRun.items.filter((item) => item.status === 'complete').length;
    const failed = allRepoRun.items.filter((item) => item.status === 'failed').length;
    return (
      <div className="scan-progress-card">
        <div className="scan-progress-head">
          <strong>{auditRunLabel(allRepoRun.audits)} all-repo run</strong>
          <span>{complete}/{allRepoRun.items.length} complete{failed ? ` · ${failed} failed` : ''}</span>
        </div>
        <div className="scan-run-list">
          {allRepoRun.items.map((item) => (
            <div key={item.repoPath} className={`scan-run-row ${item.status}`}>
              <div>
                <strong>{item.repoName}</strong>
                <span>{item.message}</span>
              </div>
              <em>{item.status}</em>
              <i><b style={{width: `${item.progress}%`}} /></i>
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (!activeJob || activeJob.status === 'complete') return null;
  return (
    <div className="scan-progress-card">
      <div className="scan-progress-head">
        <strong>{activeJob.repoName}</strong>
        <span>{Math.round(activeJob.progress)}%</span>
      </div>
      <div className="progress-track"><span style={{width: `${activeJob.progress}%`}} /></div>
      <p>{activeJob.currentStep ?? activeJob.message}</p>
    </div>
  );
}

function ScannerInventoryMini({scanners}: {scanners: ScannerDoctorItem[]}) {
  const visible = scanners.slice(0, 8);
  return (
    <div className="scanner-inventory-mini">
      {visible.map((item) => (
        <div key={item.scanner} className={`scanner-inventory-row ${item.status}`}>
          <div>
            <strong>{item.label}</strong>
            <span>{item.area} · {item.findings} raw signals</span>
          </div>
          <em>{scannerStatusLabel(item.status)}</em>
        </div>
      ))}
      {!visible.length && <EmptyLine title="No scanner inventory yet" detail="Run doctor or a scan to populate local scanner coverage." />}
    </div>
  );
}

function RepoScanStrip({summary}: {summary: DashboardSummary}) {
  const repos = [...summary.repos].sort((a, b) => new Date(b.last_scan ?? 0).getTime() - new Date(a.last_scan ?? 0).getTime()).slice(0, 6);
  return (
    <div className="repo-scan-strip">
      <div className="repo-scan-strip-head">
        <Eyebrow>Latest scan by repo</Eyebrow>
        <span>{repos.length} repo{repos.length === 1 ? '' : 's'}</span>
      </div>
      <div className="repo-scan-grid">
        {repos.map((repo) => {
          const gaps = repo.scanners.filter((scanner) => !scanner.available || scanner.error).length;
          return (
            <div key={`${repo.repo}-${repo.scan_id ?? repo.path}`} className="repo-scan-tile">
              <strong>{repo.repo}</strong>
              <span>{repo.last_scan ? formatDate(repo.last_scan) : 'No scan'} · {repo.profile || 'profile'}</span>
              <div>
                <em>{repo.health}/100 health</em>
                <em>{gaps ? `${gaps} setup gaps` : 'checks accounted for'}</em>
              </div>
            </div>
          );
        })}
        {!repos.length && <EmptyLine title="No repository scans" detail="Run checks on a repo to build the all-repos strip." />}
      </div>
    </div>
  );
}

function PreCaseScanNote({repos, rawFindingTotal}: {repos: RepositorySummary[]; rawFindingTotal: number}) {
  const names = repos.map((repo) => repo.repo).join(', ');
  const repoLabel = repos.length === 1 ? names : `${repos.length} repos`;
  return (
    <PaperCard className="precase-note">
      <div>
        <Clock3 size={18} />
        <strong>Older scans need cases</strong>
      </div>
      <p>
        {repoLabel} saved {rawFindingTotal} raw finding{rawFindingTotal === 1 ? '' : 's'} before case-building was added. Raw evidence stays visible, but case KPIs wait for a fresh scan.
      </p>
      {repos.length > 1 && <span>{names}</span>}
    </PaperCard>
  );
}

function RepositoryComparisonStrip({summary, cases}: {summary: DashboardSummary; cases: DisplayCase[]}) {
  const repos = [...summary.repos].sort((a, b) => a.health - b.health).slice(0, 4);
  return (
    <PaperCard className="repo-comparison-card">
      <SectionHeader title="Repo comparison" right={<ScopePill label="All repos" />} />
      {repos.length ? (
        <div className="repo-comparison-grid">
          {repos.map((repo, index) => {
            const openCases = cases.filter((item) => item.repoName === repo.repo || repoKeyFromPath(item.repoName) === repo.repo).length;
            const trend = typeof repo.health_delta === 'number' ? `${repo.health_delta >= 0 ? '+' : ''}${repo.health_delta}` : 'flat';
            const preCase = repoHasPreCaseScan(repo);
            return (
              <div key={`${repo.repo}-${repo.scan_id ?? repo.path}`} className={`repo-comparison-tile ${index === 0 ? 'lowest' : ''}`}>
                <div>
                  <strong>{repo.repo}</strong>
                  <span>{preCase ? 'Needs rescan' : index === 0 ? 'Lowest posture' : 'Repository posture'}</span>
                </div>
                <div className="repo-comparison-metrics">
                  <span><b>{repo.health}</b><em>health</em></span>
                  <span><b>{openCases}</b><em>open cases</em></span>
                  <span><b>{trend}</b><em>trend</em></span>
                </div>
                <p>{formatDate(repo.last_scan)} · {preCase ? 'pre-cases scan, rescan for cases' : repo.profile || 'scan'}</p>
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyLine title="No repository snapshots" detail="Run a scan to build the all-repos comparison." />
      )}
    </PaperCard>
  );
}

function FindingsView({summary, search, target, onCaseDecision}: {summary: DashboardSummary; search: string; target: TargetSelection; onCaseDecision: (caseId: string, repoName: string, status: CaseDecisionStatus | 'open', note: string) => Promise<void>}) {
  const [severityFilter, setSeverityFilter] = useState<Tone | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [repoFilter, setRepoFilter] = useState<string>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [rotateTarget, setRotateTarget] = useState<{repo: ProjectRepo; secret: RotationSecretRow} | null>(null);
  const [rotateError, setRotateError] = useState<string | null>(null);
  const scopeLabel = targetLabel(target);
  const showRepoColumn = target.mode === 'all-repos';
  const cases = displayCases(summary);
  const suppressed = suppressedDisplayCases(summary);
  const reasons = suppressionReasons(summary);
  const counts = caseSeverityCounts(cases);
  const categories = [...new Set(cases.map((item) => item.category).filter(Boolean) as string[])];
  const repoNames = [...new Set(cases.map((item) => item.repoName))].sort((a, b) => a.localeCompare(b, undefined, {sensitivity: 'base'}));
  useEffect(() => {
    if (target.mode === 'repo') setRepoFilter('all');
  }, [target.mode]);
  // Map case.repoName → rotation context. The "Rotate this" affordance only
  // appears when the case's repo has rotation scaffolded; the path comes
  // straight from the summary so we can construct the ProjectRepo the
  // RotationTriggerFlow modal expects.
  const rotationByRepo = useMemo(() => {
    const map = new Map<string, {scaffolded: boolean; repo: ProjectRepo}>();
    for (const repo of summary.repos) {
      const scaffolded = Boolean(repo.rotation_state?.scaffolded);
      map.set(repo.repo, {
        scaffolded,
        repo: {name: repo.repo, path: repo.path},
      });
    }
    return map;
  }, [summary.repos]);
  const filtered = cases.filter((item) => {
    if (severityFilter !== 'all' && toneForCase(item) !== severityFilter) return false;
    if (categoryFilter !== 'all' && item.category !== categoryFilter) return false;
    if (showRepoColumn && repoFilter !== 'all' && item.repoName !== repoFilter) return false;
    if (search.trim()) {
      const haystack = `${item.title} ${item.why} ${item.location} ${item.nextStep} ${item.repoName} ${item.category ?? ''}`.toLowerCase();
      if (!haystack.includes(search.toLowerCase())) return false;
    }
    return true;
  });
  const shown = filtered.slice(0, 32);
  const selected = cases.find((item) => item.id === selectedId) ?? filtered[0] ?? null;
  const latest = latestRepoScan(summary);

  async function openRotation(item: DisplayCase) {
    setRotateError(null);
    const context = rotationByRepo.get(item.repoName);
    if (!context?.scaffolded || !item.inferredSecretName) return;
    try {
      const response = await fetch(
        `/api/rotation/status/${encodeURIComponent(item.repoName)}`,
        {cache: 'no-store'},
      );
      if (!response.ok) throw new Error(await response.text());
      const payload = (await response.json()) as {secrets?: RotationSecretRow[]};
      const row = (payload.secrets ?? []).find(
        (entry) => entry.secret === item.inferredSecretName,
      );
      if (!row) {
        setRotateError(
          `Secret ${item.inferredSecretName} is not tracked in rotation state — open the rotation card to pick from the available secrets.`,
        );
        return;
      }
      setRotateTarget({repo: context.repo, secret: row});
    } catch (err) {
      setRotateError(
        err instanceof Error ? err.message : 'Unable to read rotation state for this repo.',
      );
    }
  }

  return (
    <div className="view-stack">
      <section className="summary-strip">
        <MetricBlock label="Cases" value={String(cases.length)} detail={`${scopeLabel} · open grouped cases`} />
        <MetricBlock label="Critical" value={String(counts.critical)} detail={scopeLabel} tone="crit" />
        <MetricBlock label="Elevated" value={String(counts.elevated)} detail={scopeLabel} tone="high" />
        <MetricBlock label="Warning" value={String(counts.warning)} detail={scopeLabel} tone="warn" />
        <MetricBlock label="Low / info" value={String(counts.low)} detail={scopeLabel} tone="low" />
      </section>
      {latest?.scan_id && (
        <div className="findings-actions">
          <ScopePill label={scopeLabel} />
          <a className="button secondary sm" href={reportViewUrl(latest.scan_id, 'prompt')}><Sparkles size={14} /> Whole-repo prompt</a>
        </div>
      )}
      <PaperCard className="landscape-card">
        <SectionHeader title="Risk landscape · severity × age" right={<span>{scopeLabel} · {cases.filter((item) => toneForCase(item) !== 'low' && relativeAge(item.createdAt).includes('d')).length} non-low cases aged past 24 h</span>} />
        <RiskLandscape items={cases} onPick={setSelectedId} />
      </PaperCard>
      <div className="chip-row">
        <Chip active={severityFilter === 'all'} onClick={() => setSeverityFilter('all')}>All severities</Chip>
        {(['crit', 'high', 'warn', 'low'] as const).map((tone) => (
          <Chip key={tone} active={severityFilter === tone} dot={severityMeta[tone].dot} onClick={() => setSeverityFilter(severityFilter === tone ? 'all' : tone)}>{severityMeta[tone].label}</Chip>
        ))}
        {categories.map((category) => <Chip key={category} active={categoryFilter === category} onClick={() => setCategoryFilter(categoryFilter === category ? 'all' : category)}>{categoryLabel(category)}</Chip>)}
      </div>
      {showRepoColumn && repoNames.length > 1 && (
        <div className="chip-row">
          <Chip active={repoFilter === 'all'} onClick={() => setRepoFilter('all')}>All repos</Chip>
          {repoNames.map((repoName) => (
            <Chip key={repoName} active={repoFilter === repoName} onClick={() => setRepoFilter(repoFilter === repoName ? 'all' : repoName)}>{repoName}</Chip>
          ))}
        </div>
      )}
      <section className="findings-master-detail">
        <div className="findings-master">
          <FindingsTable
            items={shown}
            selectedId={selected?.id ?? null}
            showRepoColumn={showRepoColumn}
            onPick={setSelectedId}
            selectedDetail={selected ? (
              <CaseDetailCard
                item={selected}
                onDecision={onCaseDecision}
                rotationScaffolded={rotationByRepo.get(selected.repoName)?.scaffolded ?? false}
                onRotate={openRotation}
                rotateError={rotateError}
              />
            ) : null}
          />
          {filtered.length > shown.length && (
            <div className="table-note">
              Showing {shown.length} of {filtered.length}. Search or filter to narrow the full local result set.
            </div>
          )}
        </div>
        <aside className="findings-detail-pane" aria-label="Selected case details">
          {selected ? (
            <CaseDetailCard
              item={selected}
              onDecision={onCaseDecision}
              rotationScaffolded={rotationByRepo.get(selected.repoName)?.scaffolded ?? false}
              onRotate={openRotation}
              rotateError={rotateError}
            />
          ) : <PaperCard><EmptyLine title="No active cases" detail="This scope has no case matching the current filters." /></PaperCard>}
        </aside>
      </section>
      {!!suppressed.length && (
        <PaperCard>
          <SectionHeader title="Suppressed cases" right={<span>{scopeLabel} · {suppressed.length} cases</span>} />
          <div className="soft-list">
            {suppressed.slice(0, 5).map((item, index) => <FindingLine key={item.id} item={item} index={index} muted />)}
          </div>
        </PaperCard>
      )}
      {!!reasons.length && <SuppressionReasonsCard reasons={reasons} />}
      {rotateTarget && (
        <RotationTriggerFlow
          repo={rotateTarget.repo}
          secret={rotateTarget.secret}
          onClose={() => setRotateTarget(null)}
          onDone={() => setRotateTarget(null)}
        />
      )}
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
    if (target.mode !== 'repo') return;
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
    if (target.mode !== 'repo' || !created) return;
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
          {target.mode === 'repo' && (
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

function PlaybooksView({summary, target, targetRepos, onChooseChecks, onTargetChange}: {summary: DashboardSummary; target: TargetSelection; targetRepos: ProjectRepo[]; onChooseChecks: () => void; onTargetChange: (value: string) => void}) {
  const playbooks = recoveryPlaybooksFor(summary);
  const [activeId, setActiveId] = useState(playbooks[0]?.id ?? '');
  const active = playbooks.find((item) => item.id === activeId) ?? playbooks[0];
  const needsRepo = target.mode !== 'repo';
  const rerunHint = needsRepo ? 'Switch to the repo where the case lives to rerun its check' : undefined;

  if (!playbooks.length || !active) {
    return (
      <div className="view-stack">
        <PaperCard>
          <div className="empty-state">
            <Eyebrow>Recovery playbooks</Eyebrow>
            <h2>No open cases need a recovery playbook right now.</h2>
            <p>Playbooks appear when active cases match a recovery class — leaked secrets, vulnerable dependencies, risky AI/agent config, IaC misconfig, platform-posture drift, workflow surfaces, install hooks, package drift, or named-campaign indicators.</p>
          </div>
        </PaperCard>
      </div>
    );
  }

  const scanSource = active.items.find((item) => item.scan_id) ?? null;

  return (
    <div className="view-stack">
      {needsRepo && (
        <NeedsRepoTarget
          targetRepos={targetRepos}
          onTargetChange={onTargetChange}
          message="Switch to the repo where the case lives to rerun its check."
        />
      )}
      <div className="playbook-grid">
        {playbooks.map((item) => (
          <button key={item.id} type="button" className={`playbook-tile ${active.id === item.id ? 'selected' : ''}`} onClick={() => setActiveId(item.id)}>
            <BookOpen size={22} />
            <span>{item.case_count} case{item.case_count === 1 ? '' : 's'} · {item.estimate_label}</span>
            <strong>{item.title}</strong>
            <p>{item.summary}</p>
            <em>{severityMeta[item.tone].label} · {item.scanners.slice(0, 2).join(' + ') || 'no scanner attached'}</em>
          </button>
        ))}
      </div>
      <PaperCard>
        <div className="playbook-detail">
          <div>
            <Eyebrow>Recovery playbook</Eyebrow>
            <h2>{active.title}</h2>
            <code>{severityMeta[active.tone].label} · {active.case_count} case{active.case_count === 1 ? '' : 's'}{active.scanners.length ? ` · ${active.scanners.join(', ')}` : ''}</code>
            <p>{active.summary}</p>
            <div className="button-row">
              {scanSource?.scan_id && <a className="button primary" href={reportViewUrl(scanSource.scan_id, 'prompt')}><Sparkles size={14} /> AI prompt</a>}
              {scanSource?.scan_id && <a className="button secondary" href={reportViewUrl(scanSource.scan_id, 'raw')}><FileText size={14} /> Raw report</a>}
              <Button variant="ghost" onClick={onChooseChecks} disabled={needsRepo} title={rerunHint}>Rerun checks</Button>
            </div>
            <ol className="step-list">
              {active.steps.map((step, index) => <li key={`${active.id}-step-${index}`}><span>{index + 1}</span><strong>{step}</strong></li>)}
            </ol>
            <PlaybookItemList items={active.items} />
          </div>
          <div className="playbook-meta">
            <MetricBlock label="Cases" value={String(active.case_count)} />
            <MetricBlock label="Wall est." value={active.estimate_label} />
            <MetricBlock label="Sources" value={active.scanners.length ? active.scanners.join(' + ') : 'verification'} />
          </div>
        </div>
      </PaperCard>
    </div>
  );
}

function PlaybookItemList({items}: {items: RecoveryPlaybookItem[]}) {
  if (!items.length) return null;
  return (
    <div className="playbook-items">
      <Eyebrow>Cases in this playbook</Eyebrow>
      <ul className="playbook-item-list">
        {items.map((item) => (
          <li key={item.case_id || `${item.repo}-${item.title}`}>
            <strong>{item.title}</strong>
            <em>{severityMeta[toneForSeverity(item.severity)].label} · {item.location} · {item.scanners.join(', ') || 'no scanner attached'}</em>
          </li>
        ))}
      </ul>
    </div>
  );
}

function VerificationView({summary, target, targetRepos, onChooseChecks, onTargetChange}: {summary: DashboardSummary; target: TargetSelection; targetRepos: ProjectRepo[]; onChooseChecks: () => void; onTargetChange: (value: string) => void}) {
  const completeness = scanCompleteness(summary);
  const scanners = topScannerItems(summary);
  const coverage = scannerCoverageSummary(summary);
  const failed = scanners.filter((item) => item.status === 'missing' || item.status === 'error');
  const needsRepo = target.mode !== 'repo';
  return (
    <div className="view-stack">
      {needsRepo && (
        <NeedsRepoTarget
          targetRepos={targetRepos}
          onTargetChange={onTargetChange}
          message="Pick a repo to run its checks."
        />
      )}
      <section className={`verification-hero ${failed.length ? 'attention' : ''}`}>
        <div>
          <Eyebrow onSurface>Diagnostic verification</Eyebrow>
          <h1>{failed.length ? `${failed.length} scanner diagnostics need setup.` : 'Scanner diagnostics are ready when you need depth.'}</h1>
          <p>{coverage} Daily scan controls now live on Overview; this page keeps the evidence and limits.</p>
        </div>
        <Button variant="glassOnGlass" onClick={onChooseChecks}>Choose checks</Button>
      </section>
      <section className="triple-grid">
        <CoverageCard title="Checks that ran" icon={<CheckCircle2 size={18} />} items={completeness.checksRan} empty="No completed checks reported." />
        <CoverageCard title="Setup gaps" icon={<CircleSlash size={18} />} items={completeness.checksMissing} empty="No setup gaps reported." />
        <CoverageCard title="Cannot prove" icon={<Stethoscope size={18} />} items={completeness.cannotProve} empty="No limits reported." />
      </section>
      <PaperCard>
        <SectionHeader title="Detailed scanner inventory" right={<span>{scanners.length} checks · {failed.length} setup gaps</span>} />
        <div className="doctor-grid">
          {scanners.map((item) => <DoctorRow key={item.scanner} item={item} />)}
        </div>
      </PaperCard>
    </div>
  );
}

function ActivityView({summary, search, target}: {summary: DashboardSummary; search: string; target: TargetSelection}) {
  const scopeLabel = targetLabel(target);
  const activities = buildActivity(summary, target.mode === 'all-repos').filter((item) => {
    if (!search.trim()) return true;
    return `${item.label} ${item.sub}`.toLowerCase().includes(search.toLowerCase());
  });
  const honeyHits = (summary.honey_key_events ?? []).length;
  const rawFindings = activeRawFindingCount(summary);
  const preCaseRawTotal = preCaseRawFindingCount(summary);
  const rawFindingDetail = preCaseRawTotal
    ? `${scopeLabel} · ${preCaseRawTotal} pre-cases raw need rescan`
    : `${scopeLabel} · ${suppressedDisplayCases(summary).length} suppressed cases`;
  return (
    <div className="view-stack">
      <section className="summary-strip">
        <MetricBlock label="Audit history" value={String(summary.history.length)} detail={`${scopeLabel} · runs saved locally`} />
        <MetricBlock label="Storage" value={`${Math.max(0.1, summary.history.length * 0.04).toFixed(1)} MB`} detail={`${scopeLabel} · local sqlite`} />
        <MetricBlock label="Raw findings · 7 d" value={String(rawFindings)} detail={rawFindingDetail} />
        <MetricBlock label="Honey hits" value={String(honeyHits)} detail={scopeLabel} tone={honeyHits ? 'crit' : 'neutral'} />
      </section>
      <section className="split-grid align-start">
        <PaperCard>
          <AuditsPerDay history={summary.history} scopeLabel={scopeLabel} />
        </PaperCard>
        <PaperCard>
          <SectionHeader title="Event mix · 7 d" right={<ScopePill label={scopeLabel} />} />
          <EventMix summary={summary} />
        </PaperCard>
      </section>
      <PaperCard padded={false}>
        <div className="event-feed-head">
          <Eyebrow>Event feed · Today · {scopeLabel}</Eyebrow>
          <div className="chip-row compact"><Chip active>All</Chip><Chip>Scanner runs</Chip><Chip>Cases</Chip><Chip>Honey keys</Chip></div>
        </div>
        <div className="activity-list feed">
          {activities.map((item) => <ActivityRow key={item.id} item={item} showTone />)}
          {!activities.length && <div className="empty-feed"><EmptyLine title="No matching events" detail="The local event feed is quiet." /></div>}
        </div>
      </PaperCard>
    </div>
  );
}

function ReportsView({summary, target}: {summary: DashboardSummary; target: TargetSelection}) {
  const scopeLabel = targetLabel(target);
  const allReposMode = target.mode === 'all-repos';
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
          <Eyebrow onSurface>{allReposMode ? 'Latest report across all repos' : 'Current repo report'} · {scopeLabel}</Eyebrow>
          <h1>{latest ? `${allReposMode ? latest.repo : scopeLabel} · ${latest.profile}` : 'No scan reports yet'}</h1>
          <p>{latest ? `Finished ${formatDate(latest.last_scan)} · ${allReposMode ? `${latest.repo} · ` : ''}${latest.health}/100 health` : 'Run a repo check to create the first local report.'}</p>
        </div>
        {latest?.scan_id && (
          <div className="hero-actions">
            <a className="button glass-on" href={reportViewUrl(latest.scan_id, 'raw')}><FileText size={14} /> Raw report</a>
            <a className="button glass" href={reportViewUrl(latest.scan_id, 'prompt')}><Sparkles size={14} /> AI prompt</a>
          </div>
        )}
      </section>
      <section className="triple-grid">
        <MetricCard title="Dependency deltas" value={String(depChanges.length)} detail={`${scopeLabel} · ${deps.length} repo comparisons`} />
        <MetricCard title="Known CVE state" value={String(cveCounts['has-cve'])} detail={`${scopeLabel} · ${cveCounts['not-checked']} not checked`} />
        <MetricCard title="Named-campaign matches" value={String(iocMatches.length)} detail={`${scopeLabel} · ${iocMatches.filter((finding) => finding.ioc_match_type === 'exact match').length} exact`} />
        <MetricCard title="Trust records" value={String(trust.length)} detail={`${scopeLabel} · dependency enrichment`} />
      </section>
      <RepositorySnapshotCard summary={summary} target={target} />
      <PaperCard>
        <SectionHeader title={allReposMode ? 'Saved scan reports' : 'Report history'} right={<span>{scopeLabel} · {summary.history.length} total</span>} />
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
          {!summary.history.length && <EmptyLine title="No reports saved" detail={`Completed checks for ${scopeLabel} will appear here.`} />}
        </div>
      </PaperCard>
      <section className="split-grid align-start">
        <PaperCard>
          <SectionHeader title="Supply chain changes" right={<span>{scopeLabel} · {depChanges.length} records</span>} />
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
          <SectionHeader title="Trust records" right={<span>{scopeLabel} · {trust.length} packages</span>} />
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
        <SectionHeader title="Named-campaign matches" right={<span>{scopeLabel} · {iocMatches.length} IOC signals</span>} />
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
      <PlatformPostureCard snapshots={platformSnapshots} findings={platform} scopeLabel={scopeLabel} />
    </div>
  );
}

function RepositorySnapshotCard({summary, target}: {summary: DashboardSummary; target: TargetSelection}) {
  const scopeLabel = targetLabel(target);
  const allReposMode = target.mode === 'all-repos';
  return (
    <PaperCard>
      <SectionHeader
        title={allReposMode ? 'Latest reports by repo' : 'Latest report'}
        right={<span>{scopeLabel} · {summary.repos.length} current {summary.repos.length === 1 ? 'target' : 'targets'}</span>}
      />
      <div className="data-table repo-table">
        <div className="data-head">
          <span>Repo</span><span>Health</span><span>Previous</span><span>Active raw</span><span>Total raw</span><span>Suppressed</span><span>Reports</span>
        </div>
        {summary.repos.map((repo) => (
          <div key={`${repo.repo}-${repo.scan_id ?? repo.path}`} className="data-row">
            <strong>{repo.repo}<em>{repo.path}</em></strong>
            <span>{repo.health}/100</span>
            <span>{repo.previous_health ?? 'none'}{typeof repo.health_delta === 'number' ? ` (${repo.health_delta >= 0 ? '+' : ''}${repo.health_delta})` : ''}</span>
            <span>{countRecord(repo.counts)} {repoHasPreCaseScan(repo) ? 'pre-cases raw' : 'active raw'}</span>
            <span>{countRecord(repo.raw_counts)} raw total</span>
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
  scopeLabel,
}: {
  snapshots: ReturnType<typeof platformPostureSnapshots>;
  findings: ReturnType<typeof platformPostureFindings>;
  scopeLabel: string;
}) {
  return (
    <PaperCard>
        <SectionHeader title="Platform posture" right={<span>{scopeLabel} · {snapshots.length} snapshots · {findings.length} raw findings</span>} />
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
            <select
              name="settings-workspace-target"
              aria-label="Workspace target"
              value={targetValue(target)}
              onChange={(event) => onTargetChange(event.target.value)}
            >
              <option value="all-repos">All repos</option>
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
          <SettingRow label="Generated reports" sub="Reports remain local unless you export or share them." />
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
    ['Active raw findings', activeFindingCount(summary), 'scanner evidence behind cases'],
    ['Suppressed raw findings', suppressedFindingCount(summary), 'shown with reasons'],
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
      <p>Run a quick safety sweep first. DëvSec will turn scanner output into cases, reports, and next actions.</p>
      <div className="button-row">
        <Button icon={<Play size={15} />} onClick={onRunQuick}>Run quick sweep</Button>
        <Button variant="secondary" icon={<SlidersHorizontal size={15} />} onClick={onChooseChecks}>Choose checks</Button>
      </div>
    </div>
  );
}

function CaseDetailCard({
  item,
  onDecision,
  rotationScaffolded = false,
  onRotate,
  rotateError = null,
}: {
  item: DisplayCase;
  onDecision: (caseId: string, repoName: string, status: CaseDecisionStatus | 'open', note: string) => Promise<void>;
  rotationScaffolded?: boolean;
  onRotate?: (item: DisplayCase) => void;
  rotateError?: string | null;
}) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  useEffect(() => setCopyState('idle'), [item.id]);

  async function save(status: CaseDecisionStatus | 'open') {
    const note = status === 'open' ? '' : window.prompt('Optional note for this decision', item.decision?.note ?? '');
    if (note === null) return;
    await onDecision(item.id, item.repoName, status, note);
  }
  // "Rotate this" affordance: only on secrets-category cases when the repo
  // has rotation scaffolded AND the backend inferred a tracked secret name.
  // The button opens the same Tier 5R modal the rotation status card uses —
  // single confirmation phrase across both surfaces (see docs/agent-safety.md).
  const canRotate = Boolean(
    item.category === 'secrets' &&
    rotationScaffolded &&
    item.inferredSecretName &&
    onRotate,
  );

  async function copyCasePrompt() {
    try {
      await navigator.clipboard.writeText(casePromptMarkdown(item));
      setCopyState('copied');
      window.setTimeout(() => setCopyState('idle'), 1800);
    } catch {
      setCopyState('failed');
      window.setTimeout(() => setCopyState('idle'), 2200);
    }
  }

  return (
    <PaperCard className="detail-card">
      <div className="detail-head">
        <SeverityPill tone={toneForCase(item)} label={severityLabelForCase(item)} />
        {item.suppressed && <span className="mini-label"><EyeOff size={12} /> Suppressed</span>}
      </div>
      <h2>{item.title}</h2>
      <p>{item.why}</p>
      <KV label="Case" value={caseDisplayId(item)} />
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
        <button type="button" className="button primary" onClick={() => void copyCasePrompt()}>
          <Sparkles size={14} /> {copyState === 'copied' ? 'Copied case prompt' : copyState === 'failed' ? 'Copy failed' : 'Copy case prompt'}
        </button>
        {item.scanId && <a className="button secondary" href={reportViewUrl(item.scanId, 'raw')}><FileText size={14} /> Raw report</a>}
        {canRotate && (
          <button
            type="button"
            className="button secondary"
            onClick={() => onRotate?.(item)}
            title={`Open Tier 5R rotation modal for ${item.inferredSecretName}`}
          >
            <RotateCcw size={14} /> Rotate {item.inferredSecretName}
          </button>
        )}
      </div>
      {rotateError && (
        <div className="evidence-panel" style={{borderColor: '#b91c1c40', color: '#7f1d1d'}}>
          {rotateError}
        </div>
      )}
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

function FindingsTable({
  items,
  selectedId,
  showRepoColumn,
  onPick,
  selectedDetail,
}: {
  items: DisplayCase[];
  selectedId: string | null;
  showRepoColumn: boolean;
  onPick: (id: string) => void;
  selectedDetail?: ReactNode;
}) {
  const modeClass = showRepoColumn ? 'with-repo' : '';
  return (
    <div className="findings-table">
      <div className={`findings-head ${modeClass}`}>
        <span>ID</span>{showRepoColumn && <span>Repo</span>}<span>Case</span><span>Category</span><span>Scanner</span><span>Severity</span><span>Age</span><span />
      </div>
      {items.map((item, index) => (
        <div key={item.id} className="finding-row-group">
          <button type="button" className={`finding-row ${modeClass} ${selectedId === item.id ? 'selected' : ''}`} onClick={() => onPick(item.id)} aria-expanded={selectedId === item.id}>
            <span className="mono-cell">{displayId(item, index)}</span>
            {showRepoColumn && <span className="mono-cell">{item.repoName}</span>}
            <span><strong>{item.title}</strong><em>{item.location}</em></span>
            <span>{item.category ? categoryLabel(item.category) : 'Security'}</span>
            <span className="mono-cell">{caseScanner(item)}</span>
            <span><SeverityPill tone={toneForCase(item)} label={severityLabelForCase(item)} /></span>
            <span className="mono-cell">{relativeAge(item.createdAt)}</span>
            <ChevronRight size={16} />
          </button>
          {selectedId === item.id && selectedDetail && (
            <div className="finding-inline-detail">
              {selectedDetail}
            </div>
          )}
        </div>
      ))}
      {!items.length && <div className="empty-table"><EmptyLine title="No cases match" detail="Try another filter or search term." /></div>}
    </div>
  );
}

function SuppressionReasonsCard({reasons}: {reasons: ReturnType<typeof suppressionReasons>}) {
  return (
    <PaperCard>
      <SectionHeader title="Suppression reasons" right={<span>{reasons.length} decision groups</span>} />
      <div className="data-table suppression-table">
        <div className="data-head">
          <span>Reason</span><span>Decision</span><span>VEX</span><span>Cases</span><span>Raw findings</span>
        </div>
        {reasons.map((reason) => (
          <div key={`${reason.reason}-${reason.decision_status}-${reason.vex_status}`} className="data-row">
            <strong>{reason.reason}</strong>
            <span>{reason.decision_status}</span>
            <span>{reason.vex_status}</span>
            <span>{reason.cases}</span>
            <span>{reason.rawFindings}</span>
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
      {props.target.mode !== 'repo' ? (
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
      <KV label="Raw findings" value={String(item.findings)} />
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
      <em>{item.findings} raw signals</em>
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

function AuditsPerDay({history, scopeLabel}: {history: DashboardSummary['history']; scopeLabel: string}) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const dayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const days = Array.from({length: 7}, (_, i) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (6 - i));
    return date;
  });
  const counts = days.map((day) => {
    const next = new Date(day);
    next.setDate(day.getDate() + 1);
    return history.filter((scan) => {
      const value = scan.finished_at ?? scan.started_at;
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return false;
      return date >= day && date < next;
    }).length;
  });
  const max = Math.max(1, ...counts);
  const total = counts.reduce((sum, value) => sum + value, 0);
  const totalLabel = total === 1 ? '1 scan this week' : `${total} scans this week`;
  return (
    <>
      <SectionHeader title="Scans · 7 d" right={<span>{scopeLabel} · {totalLabel}</span>} />
      <div className="audits-strip">
        {counts.map((count, idx) => {
          const isToday = days[idx].getTime() === today.getTime();
          const height = count === 0 ? 0 : Math.max(6, (count / max) * 88);
          return (
            <span key={idx} className={isToday ? 'is-today' : undefined}>
              <em>{count}</em>
              <i style={{height: `${height}px`}} />
              <strong>{dayLabels[days[idx].getDay()]}</strong>
            </span>
          );
        })}
      </div>
    </>
  );
}

function EventMix({summary}: {summary: DashboardSummary}) {
  const caseBackedRaw = caseBackedRawFindingCount(summary);
  const preCaseRaw = preCaseRawFindingCount(summary);
  const rows: [string, number, Tone][] = [
    ['Scanner runs', summary.history.length, 'neutral'],
    ['Case-backed raw', caseBackedRaw, 'info'],
    ...(preCaseRaw ? [['Pre-cases raw', preCaseRaw, 'info'] as [string, number, Tone]] : []),
    ['Cases suppressed', suppressedDisplayCases(summary).length, 'info'],
    ['Honey-key hits', (summary.honey_key_events ?? []).length, 'crit'],
    ['Verification gaps', topScannerItems(summary).filter((item) => item.status === 'missing' || item.status === 'error').length, 'info'],
  ];
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
  const tickLabels = ['00', '04', '08', '12', '16', '20'];
  return (
    <div className="timeline-mini">
      {items.map((item, index) => {
        const hour = item.date ? item.date.getHours() + item.date.getMinutes() / 60 : index;
        return <span key={item.id} style={{left: `${(hour / 24) * 100}%`, background: severityMeta[item.tone].dot}} />;
      })}
      <div>{tickLabels.map((label) => <span key={label}>{label}:00</span>)}</div>
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

function Button({children, variant = 'primary', size = 'md', icon, onClick, disabled, title, ariaLabel}: {children: ReactNode; variant?: 'primary' | 'secondary' | 'ghost' | 'glass' | 'glassOnGlass'; size?: 'sm' | 'md'; icon?: ReactNode; onClick?: () => void; disabled?: boolean; title?: string; ariaLabel?: string}) {
  return <button type="button" className={`button ${variant} ${size}`} onClick={onClick} disabled={disabled} title={title} aria-label={ariaLabel}>{icon}{children}</button>;
}

function PaperCard({children, className = '', padded = true, id}: {children: ReactNode; className?: string; padded?: boolean; id?: string}) {
  return <section id={id} className={`paper-card ${padded ? 'padded' : ''} ${className}`}>{children}</section>;
}

function SectionHeader({title, right, icon}: {title: string; right?: ReactNode; icon?: ReactNode}) {
  return <div className="section-header"><h3>{icon}{title}</h3>{right && <div>{right}</div>}</div>;
}

function ScopePill({label}: {label: string}) {
  return <span className="scope-pill">{label}</span>;
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

function SettingRow({label, sub, children}: {label: string; sub: string; children?: ReactNode}) {
  return <div className="setting-row"><div><strong>{label}</strong><span>{sub}</span></div>{children !== undefined && <div>{children}</div>}</div>;
}

function ScanIcon(props: {size?: number; className?: string}) {
  return <Search {...props} />;
}
