import {useEffect, useMemo, useState} from 'react';
import {AlertTriangle, ClipboardCheck, Copy, Upload, X} from 'lucide-react';
import {
  AiFollowUpActionId,
  AiFollowUpPromptResponse,
  AiFollowUpScopeId,
  CaseResolutionApplyResponse,
  CaseResolutionPreviewResponse,
  DashboardSummary,
  RepositorySummary,
  TargetSelection,
  repoDisplayName,
  repoKeyFromPath,
  repositoryDisplayName,
} from '../dashboardData';
import Dialog from './Dialog';

type AiFollowUpPanelProps = {
  summary: DashboardSummary;
  target: TargetSelection;
  selectedCaseIds?: string[];
  compact?: boolean;
  onApplied?: () => Promise<void>;
};

const EMPTY_SELECTED_CASE_IDS: string[] = [];
const CASE_ID_SEPARATOR = '\u001f';

const actionOptions: {id: AiFollowUpActionId; label: string}[] = [
  {id: 'verify_findings', label: 'Verify findings'},
  {id: 'fix_vulnerabilities', label: 'Fix vulnerabilities'},
  {id: 'create_remediation_plan', label: 'Create remediation plan'},
  {id: 'explain_risk', label: 'Explain risk'},
  {id: 'recheck_after_fixes', label: 'Re-check after fixes'},
];

const scopeOptions: {id: AiFollowUpScopeId; label: string}[] = [
  {id: 'critical', label: 'Critical'},
  {id: 'critical_high', label: 'Critical + High'},
  {id: 'all_open', label: 'All open'},
  {id: 'selected_cases', label: 'Selected cases'},
  {id: 'new_since_last_scan', label: 'New since last scan'},
];

export default function AiFollowUpPanel({summary, target, selectedCaseIds = EMPTY_SELECTED_CASE_IDS, compact = false, onApplied}: AiFollowUpPanelProps) {
  const repos = useMemo(() => summary.repos.filter((repo) => repo.scan_id), [summary.repos]);
  const selectedCaseIdsKey = selectedCaseIds.join(CASE_ID_SEPARATOR);
  const stableSelectedCaseIds = useMemo(
    () => selectedCaseIdsKey ? selectedCaseIdsKey.split(CASE_ID_SEPARATOR) : [],
    [selectedCaseIdsKey],
  );
  const [repoName, setRepoName] = useState('');
  const [action, setAction] = useState<AiFollowUpActionId>('verify_findings');
  const [scope, setScope] = useState<AiFollowUpScopeId>('critical');
  const [prompt, setPrompt] = useState<AiFollowUpPromptResponse | null>(null);
  const [isPromptLoading, setIsPromptLoading] = useState(false);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [modalOpen, setModalOpen] = useState(false);
  const [importText, setImportText] = useState('');
  const [preview, setPreview] = useState<CaseResolutionPreviewResponse | null>(null);
  const [applyResult, setApplyResult] = useState<CaseResolutionApplyResponse | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);

  const selectedRepo = repos.find((repo) => repo.repo === repoName) ?? repos[0] ?? null;
  const selectedCount = stableSelectedCaseIds.length;
  const canUseSelectedScope = selectedCount > 0;

  useEffect(() => {
    const nextRepo = defaultRepoName(repos, target);
    setRepoName((current) => current && repos.some((repo) => repo.repo === current) ? current : nextRepo);
  }, [repos, target]);

  useEffect(() => {
    if (!selectedRepo) return;
    setScope((current) => {
      if (current === 'selected_cases' && !canUseSelectedScope) return recommendedScope(selectedRepo);
      if (current !== 'critical') return current;
      return recommendedScope(selectedRepo);
    });
  }, [selectedRepo, canUseSelectedScope]);

  useEffect(() => {
    setCopyState('idle');
  }, [prompt?.prompt]);

  useEffect(() => {
    if (!repoName) {
      setPrompt(null);
      return;
    }
    const controller = new AbortController();
    async function loadPrompt() {
      setIsPromptLoading(true);
      try {
        const params = new URLSearchParams({repo: repoName, action, scope});
        if (scope === 'selected_cases') stableSelectedCaseIds.forEach((id) => params.append('caseId', id));
        const response = await fetch(`/api/ai-follow-up/prompt?${params.toString()}`, {cache: 'no-store', signal: controller.signal});
        if (!response.ok) throw new Error(await responseErrorMessage(response, 'Unable to build AI follow-up prompt'));
        setPrompt(await response.json());
      } catch (err) {
        if (!controller.signal.aborted) {
          setPrompt({
            repo: repoName,
            action,
            scope,
            case_count: 0,
            preview: err instanceof Error ? err.message : 'Unable to build AI follow-up prompt',
            prompt: '',
          });
        }
      } finally {
        if (!controller.signal.aborted) setIsPromptLoading(false);
      }
    }
    void loadPrompt();
    return () => controller.abort();
  }, [repoName, action, scope, stableSelectedCaseIds]);

  async function copyPrompt() {
    if (!prompt?.prompt || !prompt.case_count) return;
    try {
      await navigator.clipboard.writeText(prompt.prompt);
      setCopyState('copied');
    } catch {
      setCopyState('failed');
    }
  }

  async function previewImport() {
    setModalError(null);
    setApplyResult(null);
    setIsImporting(true);
    try {
      const response = await fetch('/api/ai-follow-up/resolutions/preview', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          text: importText,
          expectedRepo: repoName,
          expectedScope: scope,
          expectedCaseIds: scope === 'selected_cases' ? stableSelectedCaseIds : undefined,
        }),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Unable to preview AI result'));
      setPreview(await response.json());
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Unable to preview AI result');
      setPreview(null);
    } finally {
      setIsImporting(false);
    }
  }

  async function applyImport() {
    if (!preview?.run_id) return;
    setModalError(null);
    setIsImporting(true);
    try {
      const response = await fetch('/api/ai-follow-up/resolutions/apply', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({runId: preview.run_id}),
      });
      if (!response.ok) throw new Error(await responseErrorMessage(response, 'Unable to apply AI result'));
      const result = await response.json();
      setApplyResult(result);
      await onApplied?.();
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Unable to apply AI result');
    } finally {
      setIsImporting(false);
    }
  }

  const empty = !repos.length;
  const disabled = empty || !prompt?.case_count || isPromptLoading;
  const repoLabel = selectedRepo ? repositoryDisplayName(selectedRepo) : 'No scanned repo';
  const history = summary.case_resolution_runs?.filter((run) => run.repo === repoName || run.repo_name === repoName).slice(0, 1) ?? [];

  return (
    <>
      <section className={`paper-card padded ai-follow-panel ${compact ? 'compact' : ''}`}>
        <div className="ai-follow-head">
          <div>
            <div className="eyebrow">AI follow-up</div>
            <strong>{repoLabel}</strong>
          </div>
          {!!history.length && <span>{history[0].status.replace(/_/g, ' ')}</span>}
        </div>
        <div className="ai-follow-controls">
          {target.mode === 'all-repos' && (
            <label>
              <span>Repository</span>
              <select value={repoName} onChange={(event) => setRepoName(event.target.value)} disabled={empty}>
                {repos.map((repo) => (
                  <option key={repo.repo} value={repo.repo}>{repositoryDisplayName(repo)}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            <span>Action</span>
            <select value={action} onChange={(event) => setAction(event.target.value as AiFollowUpActionId)} disabled={empty}>
              {actionOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
            </select>
          </label>
          <label>
            <span>Scope</span>
            <select value={scope} onChange={(event) => setScope(event.target.value as AiFollowUpScopeId)} disabled={empty}>
              {scopeOptions.map((option) => (
                <option key={option.id} value={option.id} disabled={option.id === 'selected_cases' && !canUseSelectedScope}>
                  {option.label}{option.id === 'selected_cases' && selectedCount ? ` (${selectedCount})` : ''}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="ai-follow-preview-row">
          <input value={isPromptLoading ? 'Building prompt...' : prompt?.preview ?? 'Run a scan before handing cases to an AI.'} readOnly />
          <button type="button" className="button primary sm" onClick={() => void copyPrompt()} disabled={disabled}>
            {copyState === 'copied' ? <ClipboardCheck size={14} /> : <Copy size={14} />}
            {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy failed' : 'Give this to your AI of choice'}
          </button>
          <button type="button" className="button secondary sm" onClick={() => { setModalOpen(true); setPreview(null); setApplyResult(null); setModalError(null); }} disabled={empty}>
            <Upload size={14} /> Import AI result
          </button>
        </div>
      </section>

      {modalOpen && (
        <Dialog
          ariaLabel="Import AI result"
          onClose={() => setModalOpen(false)}
          closeOnBackdropClick={false}
          backdropClassName="ai-follow-modal-backdrop"
          className="ai-follow-modal"
        >
          <div className="ai-follow-modal-head">
            <div>
              <div className="eyebrow">Paste AI result JSON</div>
              <strong>{repoDisplayName(summary, repoName)}</strong>
            </div>
            <button type="button" className="icon-button" onClick={() => setModalOpen(false)} aria-label="Close import modal"><X size={16} /></button>
          </div>
          <textarea
            value={importText}
            onChange={(event) => {
              setImportText(event.target.value);
              setPreview(null);
              setApplyResult(null);
            }}
            rows={10}
            placeholder='{"schema_version":"devsec.case_resolutions.v1",...}'
          />
          {modalError && <div className="inline-error compact">{modalError}</div>}
          {preview && <ResolutionPreview preview={preview} />}
          {applyResult && (
            <div className="ai-follow-result">
              <ClipboardCheck size={15} />
              Applied {applyResult.applied}; left open {applyResult.left_open}; rejected {applyResult.rejected}.
            </div>
          )}
          <div className="ai-follow-modal-actions">
            <button type="button" className="button ghost sm" onClick={() => setModalOpen(false)}>Cancel</button>
            <button type="button" className="button secondary sm" onClick={() => void previewImport()} disabled={isImporting || !importText.trim()}>
              Preview result
            </button>
            <button type="button" className="button primary sm" onClick={() => void applyImport()} disabled={isImporting || !preview || !preview.summary.will_apply}>
              Apply resolutions
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}

function ResolutionPreview({preview}: {preview: CaseResolutionPreviewResponse}) {
  const dispositions = preview.summary.dispositions ?? {};
  const warnings = preview.summary.warnings ?? [];
  return (
    <div className="ai-follow-preview-card">
      <div className="ai-follow-preview-counts">
        <span><strong>{preview.summary.total ?? preview.items.length}</strong> reviewed</span>
        <span><strong>{preview.summary.will_apply ?? 0}</strong> will apply</span>
        <span><strong>{preview.summary.will_leave_open ?? 0}</strong> left open</span>
        <span><strong>{preview.summary.rejected ?? 0}</strong> rejected</span>
      </div>
      {!!Object.keys(dispositions).length && (
        <div className="ai-follow-dispositions">
          {Object.entries(dispositions).map(([key, value]) => <span key={key}>{key.replace(/_/g, ' ')} · {value}</span>)}
        </div>
      )}
      {!!warnings.length && (
        <div className="ai-follow-warnings">
          <AlertTriangle size={15} />
          <div>{warnings.slice(0, 4).map((warning) => <p key={warning}>{warning}</p>)}</div>
        </div>
      )}
      <div className="ai-follow-items">
        {preview.items.slice(0, 6).map((item) => (
          <div key={item.id}>
            <strong>{item.display_id ?? item.case_id}</strong>
            <span>{item.disposition.replace(/_/g, ' ')} · {item.status.replace(/_/g, ' ')}</span>
            {item.warning && <em>{item.warning}</em>}
          </div>
        ))}
      </div>
    </div>
  );
}

function defaultRepoName(repos: RepositorySummary[], target: TargetSelection): string {
  if (!repos.length) return '';
  if (target.mode === 'repo') {
    const key = repoKeyFromPath(target.repo.path);
    const match = repos.find((repo) => repo.path === target.repo.path || repo.repo === key);
    return match?.repo ?? repos[0].repo;
  }
  const withCritical = repos.find((repo) => (repo.active_cases ?? repo.cases ?? []).some((item) => item.severity === 'critical'));
  return (withCritical ?? repos[0]).repo;
}

function recommendedScope(repo: RepositorySummary): AiFollowUpScopeId {
  const cases = (repo.active_cases ?? repo.cases ?? []).filter((item) => !item.suppressed);
  if (cases.some((item) => item.severity === 'critical')) return 'critical';
  if (cases.some((item) => item.severity === 'high')) return 'critical_high';
  return 'all_open';
}

async function responseErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json();
    return typeof payload.error === 'string' ? payload.error : fallback;
  } catch {
    return fallback;
  }
}
