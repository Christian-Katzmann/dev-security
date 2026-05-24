import {ReactNode, useCallback, useEffect, useMemo, useState} from 'react';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  CircleSlash,
  ClipboardList,
  Clock3,
  Copy,
  FileText,
  Lock,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  X,
} from 'lucide-react';
import NeedsRepoTarget from '../NeedsRepoTarget';
import {
  AgentLabAdapterId,
  AgentLabContextPayload,
  AgentLabExecutionPreview,
  AgentLabProposal,
  AgentLabRequestedExecution,
  DashboardSummary,
  ProjectRepo,
  TargetSelection,
  formatDate,
} from '../../dashboardData';

type Props = {
  summary: DashboardSummary;
  target: TargetSelection;
  targetRepos: ProjectRepo[];
  onRefresh: () => Promise<void>;
  onTargetChange: (value: string) => void;
};

type AdapterOption = {
  id: AgentLabAdapterId;
  label: string;
  detail: string;
  icon: ReactNode;
  future: string;
};

type ProposalResponse = {
  proposal: AgentLabProposal;
};

type ProposalListResponse = {
  items: AgentLabProposal[];
};

type PreviewResponse = {
  preview: AgentLabExecutionPreview;
  proposal: AgentLabProposal;
};

type RunResponse = {
  job?: {
    id?: string;
    status?: string;
    message?: string;
  };
  preview?: AgentLabExecutionPreview;
};

class AgentLabApiError extends Error {
  details: string[];

  constructor(message: string, details: string[] = []) {
    super(message);
    this.details = details;
  }
}

const adapterOptions: AdapterOption[] = [
  {
    id: 'codex',
    label: 'Codex',
    detail: 'Paste context into Codex and import strict JSON.',
    future: 'Live OpenAI adapter deferred',
    icon: <Sparkles size={16} />,
  },
  {
    id: 'claude-code',
    label: 'Claude Code',
    detail: 'Use the same portable prompt with Claude Code.',
    future: 'Provider OAuth deferred',
    icon: <TerminalSquare size={16} />,
  },
  {
    id: 'local-agent',
    label: 'Local agent',
    detail: 'Copy the contract into a local assistant.',
    future: 'Local socket handoff deferred',
    icon: <Bot size={16} />,
  },
  {
    id: 'manual-json',
    label: 'Manual JSON',
    detail: 'Paste hand-written proposal JSON for validation.',
    future: 'Free-form import blocked',
    icon: <FileText size={16} />,
  },
];

export default function AgentLabView({summary, target, targetRepos, onRefresh, onTargetChange}: Props) {
  const [adapterId, setAdapterId] = useState<AgentLabAdapterId>('codex');
  const [contextPayload, setContextPayload] = useState<AgentLabContextPayload | null>(null);
  const [contextError, setContextError] = useState<string | null>(null);
  const [isLoadingContext, setIsLoadingContext] = useState(false);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [proposalText, setProposalText] = useState('');
  const [importError, setImportError] = useState<{message: string; details: string[]} | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [fetchedProposals, setFetchedProposals] = useState<AgentLabProposal[] | null>(null);
  const [proposalError, setProposalError] = useState<string | null>(null);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null);
  const [decisionNote, setDecisionNote] = useState('');
  const [decisionMessage, setDecisionMessage] = useState<string | null>(null);
  const [isSavingDecision, setIsSavingDecision] = useState(false);
  const [preview, setPreview] = useState<AgentLabExecutionPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [isQueuingRun, setIsQueuingRun] = useState(false);

  const selectedAdapter = adapterOptions.find((option) => option.id === adapterId) ?? adapterOptions[0];
  const repo = target.type === 'repo' ? target.repo : null;

  const summaryProposals = useMemo(() => {
    if (!repo) return [];
    return (summary.agent_lab_proposals ?? []).filter((proposal) => proposalBelongsToRepo(proposal, repo));
  }, [repo, summary.agent_lab_proposals]);

  const proposals = fetchedProposals ?? summaryProposals;
  const selectedProposal = proposals.find((proposal) => proposal.id === selectedProposalId) ?? proposals[0] ?? null;
  const storedPreview = selectedProposal?.final_execution_plan?.last_preview ?? null;
  const activePreview = selectedProposal?.id && preview?.proposal_id === selectedProposal.id ? preview : storedPreview;

  const contextPrompt = useMemo(() => {
    if (!contextPayload) return '';
    return buildAgentPrompt(selectedAdapter, contextPayload);
  }, [contextPayload, selectedAdapter]);

  const contextStats = useMemo(() => {
    const toolCount = contextPayload?.tool_catalog?.length ?? summary.tool_catalog?.length ?? 0;
    const packCount = contextPayload?.security_packs?.length ?? summary.security_packs?.length ?? 0;
    const profileCount = contextPayload?.allowed_scan_profile_ids?.length ?? summary.scan_profiles?.length ?? 0;
    const allowedCount = contextPayload?.allowed_tool_ids?.length ?? (summary.tool_catalog ?? []).filter((item) => item.policy.allowed_for_agent_lab).length;
    return {toolCount, packCount, profileCount, allowedCount};
  }, [contextPayload, summary.scan_profiles, summary.security_packs, summary.tool_catalog]);

  const loadContext = useCallback(async () => {
    if (!repo) return;
    setIsLoadingContext(true);
    setContextError(null);
    try {
      const params = new URLSearchParams({repoPath: repo.path, repoName: repo.name});
      const payload = await requestJson<AgentLabContextPayload>(`/api/agent-lab/context?${params.toString()}`);
      setContextPayload(payload);
    } catch (error) {
      setContextError(error instanceof Error ? error.message : 'Unable to build Agent Lab context.');
    } finally {
      setIsLoadingContext(false);
    }
  }, [repo]);

  const loadProposals = useCallback(async () => {
    if (!repo) return;
    setProposalError(null);
    try {
      const params = new URLSearchParams({repoName: repo.name});
      const payload = await requestJson<ProposalListResponse>(`/api/agent-lab/proposals?${params.toString()}`);
      setFetchedProposals(payload.items);
    } catch (error) {
      setProposalError(error instanceof Error ? error.message : 'Unable to load Agent Lab proposals.');
    }
  }, [repo]);

  useEffect(() => {
    setContextPayload(null);
    setFetchedProposals(null);
    setSelectedProposalId(null);
    setPreview(null);
    setDecisionMessage(null);
    setRunMessage(null);
    setProposalText('');
    if (repo) {
      void loadContext();
      void loadProposals();
    }
  }, [loadContext, loadProposals, repo]);

  useEffect(() => {
    if (!proposals.length) {
      setSelectedProposalId(null);
      return;
    }
    if (!selectedProposalId || !proposals.some((proposal) => proposal.id === selectedProposalId)) {
      setSelectedProposalId(proposals[0].id);
    }
  }, [proposals, selectedProposalId]);

  useEffect(() => {
    setPreview(null);
    setPreviewError(null);
    setDecisionMessage(null);
    setRunMessage(null);
    setDecisionNote(selectedProposal?.approval_note ?? '');
  }, [selectedProposal?.id]);

  if (!repo) {
    return (
      <div className="agent-lab">
        <div className="agent-lab-empty">
          <div className="agent-lab-empty-mark"><Bot size={30} /></div>
          <h1>Pick a repo for Agent Lab</h1>
          <p>Agent Lab exports repo-scoped planning context, so it needs an explicit local repository target before a proposal can be imported or approved.</p>
          <NeedsRepoTarget targetRepos={targetRepos} onTargetChange={onTargetChange} message="Choose a repo before exporting Agent Lab context." />
        </div>
      </div>
    );
  }

  async function copyPrompt() {
    if (!contextPrompt) return;
    try {
      await navigator.clipboard.writeText(contextPrompt);
      setCopyState('copied');
      window.setTimeout(() => setCopyState('idle'), 1800);
    } catch {
      setCopyState('failed');
    }
  }

  async function importProposal() {
    setIsImporting(true);
    setImportError(null);
    setDecisionMessage(null);
    setRunMessage(null);
    try {
      const payload = await requestJson<ProposalResponse>('/api/agent-lab/proposals', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({proposal_json: proposalText}),
      });
      setProposalText('');
      setSelectedProposalId(payload.proposal.id);
      await loadProposals();
      await onRefresh();
    } catch (error) {
      if (error instanceof AgentLabApiError) {
        setImportError({message: error.message, details: error.details});
      } else {
        setImportError({message: error instanceof Error ? error.message : 'Unable to import proposal.', details: []});
      }
    } finally {
      setIsImporting(false);
    }
  }

  async function saveDecision(approvalState: 'approved' | 'denied' | 'pending') {
    if (!selectedProposal) return;
    setIsSavingDecision(true);
    setDecisionMessage(null);
    setRunMessage(null);
    try {
      const payload = await requestJson<ProposalResponse>('/api/agent-lab/proposals/decision', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          proposalId: selectedProposal.id,
          approvalState,
          note: decisionNote,
          decidedBy: 'local-user',
        }),
      });
      setDecisionMessage(`${approvalLabel(payload.proposal.approval_state)} saved.`);
      setSelectedProposalId(payload.proposal.id);
      await loadProposals();
      await onRefresh();
    } catch (error) {
      setDecisionMessage(error instanceof Error ? error.message : 'Unable to save approval decision.');
    } finally {
      setIsSavingDecision(false);
    }
  }

  async function previewExecution() {
    if (!selectedProposal) return;
    setIsPreviewing(true);
    setPreviewError(null);
    setRunMessage(null);
    try {
      const params = new URLSearchParams({proposalId: selectedProposal.id, mode: 'dry_run_preview'});
      const payload = await requestJson<PreviewResponse>(`/api/agent-lab/proposals/execution-preview?${params.toString()}`);
      setPreview(payload.preview);
      await loadProposals();
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : 'Unable to preview Agent Lab route.');
    } finally {
      setIsPreviewing(false);
    }
  }

  async function queueApprovedRun() {
    if (!selectedProposal) return;
    setIsQueuingRun(true);
    setRunMessage(null);
    try {
      const payload = await requestJson<RunResponse>('/api/agent-lab/proposals/run', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({proposalId: selectedProposal.id, mode: 'approved_run', execute: true}),
      });
      setPreview(payload.preview ?? null);
      setRunMessage(payload.job?.id ? `Queued DëvSec scan job ${payload.job.id}.` : 'Queued approved Agent Lab scan.');
      await loadProposals();
      await onRefresh();
    } catch (error) {
      setRunMessage(error instanceof Error ? error.message : 'Unable to queue approved Agent Lab scan.');
    } finally {
      setIsQueuingRun(false);
    }
  }

  return (
    <div className="agent-lab view-stack">
      <section className="agent-lab-console">
        <div className="agent-lab-console-main">
          <div className="agent-lab-eyebrow"><Bot size={14} /> User-mediated planner</div>
          <h1>Agent Lab</h1>
          <p>Export bounded DëvSec context, use the AI you already trust, then import one strict proposal for local approval and DëvSec-controlled execution.</p>
        </div>
        <div className="agent-lab-policy-strip">
          <BoundaryItem icon={<Lock size={15} />} label="No provider tokens" detail="OAuth and live adapters stay disabled in MVP." />
          <BoundaryItem icon={<FileText size={15} />} label="JSON proposals only" detail="Markdown, prose, and unknown actions are rejected." />
          <BoundaryItem icon={<ShieldCheck size={15} />} label="DëvSec runs scans" detail="Approved work routes through existing profiles." />
        </div>
      </section>

      <section className="agent-lab-grid">
        <div className="agent-lab-panel">
          <PanelHeader
            eyebrow="1 · Export context"
            title="Choose the agent and copy the planning prompt"
            right={<button type="button" className="agent-lab-icon-button" onClick={() => void loadContext()} disabled={isLoadingContext} aria-label="Refresh Agent Lab context"><RefreshCw size={15} /></button>}
          />
          <div className="agent-lab-adapter-grid">
            {adapterOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                className={`agent-lab-adapter ${option.id === adapterId ? 'active' : ''}`}
                onClick={() => setAdapterId(option.id)}
              >
                <span>{option.icon}</span>
                <strong>{option.label}</strong>
                <em>{option.detail}</em>
                <small><Lock size={11} /> {option.future}</small>
              </button>
            ))}
          </div>
          <div className="agent-lab-stat-row">
            <MiniStat label="Tools in context" value={contextStats.toolCount} />
            <MiniStat label="Agent-allowed" value={contextStats.allowedCount} />
            <MiniStat label="Packs" value={contextStats.packCount} />
            <MiniStat label="Scan profiles" value={contextStats.profileCount} />
          </div>
          <div className="agent-lab-prompt-shell">
            <div className="agent-lab-prompt-head">
              <div>
                <strong>{contextPayload?.context_id ?? 'Context not exported yet'}</strong>
                <span>{contextPayload?.context_hash ?? 'DëvSec will add a hash after export.'}</span>
              </div>
              <button type="button" className="agent-lab-action secondary" onClick={() => void copyPrompt()} disabled={!contextPrompt}>
                <Copy size={14} /> {copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy failed' : 'Copy prompt'}
              </button>
            </div>
            {contextError ? (
              <InlineNotice tone="warn" icon={<AlertTriangle size={15} />} title="Context export failed" body={contextError} />
            ) : (
              <textarea
                readOnly
                value={isLoadingContext ? 'Building Agent Lab context...' : contextPrompt}
                aria-label="Agent Lab context prompt"
                className="agent-lab-code-area"
                rows={14}
              />
            )}
          </div>
        </div>

        <div className="agent-lab-panel">
          <PanelHeader eyebrow="2 · Import proposal" title="Paste the agent's JSON response" />
          <InlineNotice
            tone="warn"
            icon={<AlertTriangle size={15} />}
            title="Treat imports as hostile"
            body="DëvSec validates size, schema, known IDs, pack rules, external-surface blocks, and arbitrary-command blocks before a proposal can be approved."
          />
          <textarea
            value={proposalText}
            onChange={(event) => setProposalText(event.target.value)}
            className="agent-lab-import-area"
            aria-label="Agent Lab proposal JSON"
            placeholder={proposalPlaceholder(contextPayload, adapterId, repo.path)}
            spellCheck={false}
          />
          {importError && (
            <div className="agent-lab-error">
              <strong>{importError.message}</strong>
              {!!importError.details.length && (
                <ul>
                  {importError.details.map((detail) => <li key={detail}>{detail}</li>)}
                </ul>
              )}
            </div>
          )}
          <div className="agent-lab-button-row">
            <button type="button" className="agent-lab-action primary" onClick={() => void importProposal()} disabled={isImporting || !proposalText.trim()}>
              <ClipboardList size={14} /> {isImporting ? 'Importing...' : 'Import and validate'}
            </button>
            <button type="button" className="agent-lab-action secondary" onClick={() => setProposalText('')} disabled={!proposalText.trim() || isImporting}>
              <X size={14} /> Clear
            </button>
          </div>
        </div>
      </section>

      <section className="agent-lab-review-layout">
        <div className="agent-lab-panel">
          <PanelHeader eyebrow="3 · Proposal records" title="Audit trail" right={<span className="agent-lab-count">{proposals.length}</span>} />
          {proposalError && <InlineNotice tone="warn" icon={<AlertTriangle size={15} />} title="Proposal list unavailable" body={proposalError} />}
          <div className="agent-lab-proposal-list">
            {proposals.map((proposal) => (
              <button
                key={proposal.id}
                type="button"
                className={`agent-lab-proposal-row ${selectedProposal?.id === proposal.id ? 'active' : ''}`}
                onClick={() => setSelectedProposalId(proposal.id)}
              >
                <span className={`agent-lab-state-dot ${approvalTone(proposal.approval_state)}`} />
                <span>
                  <strong>{proposal.summary || 'Untitled proposal'}</strong>
                  <em>{proposal.source?.agent_label ?? 'Agent'} · imported {formatDate(proposal.imported_at)}</em>
                </span>
                <small>{approvalLabel(proposal.approval_state)}</small>
              </button>
            ))}
            {!proposals.length && (
              <EmptyState
                icon={<ClipboardList size={22} />}
                title="No proposals imported"
                body="Copy the prompt to Codex, Claude Code, or a local agent, then paste the returned JSON here."
              />
            )}
          </div>
        </div>

        <div className="agent-lab-panel agent-lab-review-panel">
          {selectedProposal ? (
            <ProposalReview
              proposal={selectedProposal}
              preview={activePreview}
              decisionNote={decisionNote}
              setDecisionNote={setDecisionNote}
              decisionMessage={decisionMessage}
              isSavingDecision={isSavingDecision}
              isPreviewing={isPreviewing}
              previewError={previewError}
              isQueuingRun={isQueuingRun}
              runMessage={runMessage}
              onDecision={saveDecision}
              onPreview={previewExecution}
              onRun={queueApprovedRun}
            />
          ) : (
            <EmptyState
              icon={<ShieldCheck size={22} />}
              title="Import a proposal to review"
              body="The review surface will show requested tools, packs, safety labels, approval state, preview routes, blockers, and evidence gaps."
            />
          )}
        </div>
      </section>
    </div>
  );
}

function ProposalReview({
  proposal,
  preview,
  decisionNote,
  setDecisionNote,
  decisionMessage,
  isSavingDecision,
  isPreviewing,
  previewError,
  isQueuingRun,
  runMessage,
  onDecision,
  onPreview,
  onRun,
}: {
  proposal: AgentLabProposal;
  preview: AgentLabExecutionPreview | null;
  decisionNote: string;
  setDecisionNote: (value: string) => void;
  decisionMessage: string | null;
  isSavingDecision: boolean;
  isPreviewing: boolean;
  previewError: string | null;
  isQueuingRun: boolean;
  runMessage: string | null;
  onDecision: (approvalState: 'approved' | 'denied' | 'pending') => Promise<void>;
  onPreview: () => Promise<void>;
  onRun: () => Promise<void>;
}) {
  const executionItems = proposal.final_execution_plan?.items?.length ? proposal.final_execution_plan.items : proposal.requested_execution ?? [];
  const lastExecution = proposal.final_execution_plan?.last_execution;
  const canQueue = proposal.approval_state === 'approved' && Boolean(preview?.can_execute);

  return (
    <>
      <PanelHeader
        eyebrow="4 · Review and approve"
        title={proposal.source?.agent_label ? `${proposal.source.agent_label} proposal` : 'Agent proposal'}
        right={<span className={`agent-lab-status-pill ${approvalTone(proposal.approval_state)}`}>{approvalLabel(proposal.approval_state)}</span>}
      />
      <div className="agent-lab-proposal-summary">
        <h2>{proposal.summary}</h2>
        <p>{proposal.notes || 'No additional agent notes were imported.'}</p>
        <div className="agent-lab-meta-grid">
          <MetaItem label="Proposal" value={proposal.external_proposal_id || proposal.id} />
          <MetaItem label="Context" value={proposal.context_id || 'Not recorded'} />
          <MetaItem label="Imported" value={formatDate(proposal.imported_at)} />
          <MetaItem label="Updated" value={formatDate(proposal.updated_at)} />
        </div>
      </div>

      <div className="agent-lab-review-grid">
        <ReviewBlock title="Recommended tools" icon={<Sparkles size={15} />}>
          {proposal.recommended_tools?.map((tool) => (
            <StackItem
              key={tool.tool_id}
              title={tool.label ?? tool.tool_id}
              detail={tool.reason || tool.expected_benefit || 'No reason imported.'}
              meta={tool.install_state ? humanize(tool.install_state) : undefined}
            >
              <SafetyLabels labels={tool.safety_labels ?? []} />
            </StackItem>
          ))}
          {!proposal.recommended_tools?.length && <MutedLine>No tools recommended.</MutedLine>}
        </ReviewBlock>

        <ReviewBlock title="Recommended packs" icon={<ClipboardList size={15} />}>
          {proposal.recommended_packs?.map((pack) => (
            <StackItem
              key={String(pack.pack_id)}
              title={pack.label ?? String(pack.pack_id)}
              detail={pack.reason || 'Recommendation only.'}
              meta={pack.runnable === false ? 'Not runnable in MVP' : 'Rejected if runnable'}
            />
          ))}
          {!proposal.recommended_packs?.length && <MutedLine>No packs recommended.</MutedLine>}
        </ReviewBlock>
      </div>

      <ReviewBlock title="Requested DëvSec execution" icon={<Play size={15} />}>
        {executionItems.map((item, index) => <ExecutionItem key={`${item.scan_profile_id}-${index}`} item={item} />)}
        {!executionItems.length && <MutedLine>No executable route was imported.</MutedLine>}
      </ReviewBlock>

      <div className="agent-lab-review-grid">
        <ReviewBlock title="Evidence gaps" icon={<AlertTriangle size={15} />}>
          {(proposal.expected_evidence_gaps ?? []).map((gap, index) => (
            <StackItem key={`${gap.tool_id}-${index}`} title={gap.tool_label ?? gap.tool_id ?? 'Expected gap'} detail={gap.user_message || gap.reason || 'Gap recorded by agent.'} />
          ))}
          {!proposal.expected_evidence_gaps?.length && <MutedLine>No expected evidence gaps.</MutedLine>}
        </ReviewBlock>
        <ReviewBlock title="Blocked requests" icon={<CircleSlash size={15} />}>
          {(proposal.blocked_requests ?? []).map((blocked, index) => (
            <StackItem key={`${blocked.reason}-${index}`} title={humanize(blocked.reason ?? 'Blocked')} detail={blocked.detail || 'Policy gate recorded.'} />
          ))}
          {!proposal.blocked_requests?.length && <MutedLine>No blocked requests imported.</MutedLine>}
        </ReviewBlock>
      </div>

      <div className="agent-lab-decision-box">
        <label>
          <span>Approval note</span>
          <textarea value={decisionNote} onChange={(event) => setDecisionNote(event.target.value)} rows={3} placeholder="Optional local audit note" />
        </label>
        <div className="agent-lab-button-row">
          <button type="button" className="agent-lab-action primary" onClick={() => void onDecision('approved')} disabled={isSavingDecision}>
            <CheckCircle2 size={14} /> Approve
          </button>
          <button type="button" className="agent-lab-action secondary" onClick={() => void onDecision('denied')} disabled={isSavingDecision}>
            <CircleSlash size={14} /> Deny
          </button>
          <button type="button" className="agent-lab-action ghost" onClick={() => void onDecision('pending')} disabled={isSavingDecision}>
            <Clock3 size={14} /> Pending
          </button>
        </div>
        {decisionMessage && <p className="agent-lab-message">{decisionMessage}</p>}
      </div>

      <div className="agent-lab-preview-box">
        <div className="agent-lab-preview-head">
          <div>
            <strong>Dry-run route preview</strong>
            <span>{preview ? `${preview.scanner_names?.length ?? 0} scanners · ${preview.scan_profile_ids?.join(', ') || 'no profile route'}` : 'Preview before queueing any scan.'}</span>
          </div>
          <div className="agent-lab-button-row">
            <button type="button" className="agent-lab-action secondary" onClick={() => void onPreview()} disabled={isPreviewing}>
              <RefreshCw size={14} /> {isPreviewing ? 'Previewing...' : 'Preview route'}
            </button>
            <button type="button" className="agent-lab-action primary" onClick={() => void onRun()} disabled={isQueuingRun || !canQueue} title={!canQueue ? 'Approve the proposal and confirm a routable preview first.' : undefined}>
              <Play size={14} /> {isQueuingRun ? 'Queueing...' : 'Queue approved scan'}
            </button>
          </div>
        </div>
        {previewError && <InlineNotice tone="warn" icon={<AlertTriangle size={15} />} title="Preview blocked" body={previewError} />}
        {runMessage && <p className="agent-lab-message">{runMessage}</p>}
        {preview && <PreviewDetail preview={preview} />}
        {lastExecution && (
          <div className="agent-lab-audit-trail">
            <div><span>Last execution</span><strong>{humanize(lastExecution.status ?? 'unknown')}</strong></div>
            <div><span>Job</span><strong>{lastExecution.job_id ?? 'Not recorded'}</strong></div>
            <div><span>Started</span><strong>{formatDate(lastExecution.started_at)}</strong></div>
          </div>
        )}
      </div>
    </>
  );
}

function PreviewDetail({preview}: {preview: AgentLabExecutionPreview}) {
  return (
    <div className="agent-lab-preview-detail">
      <div className="agent-lab-route-strip">
        <MetaItem label="Surface" value={humanize(preview.execution_surface ?? 'existing_devsec_scan_pipeline')} />
        <MetaItem label="Mode" value={humanize(preview.requested_mode ?? 'dry_run_preview')} />
        <MetaItem label="Can execute" value={preview.can_execute ? 'Yes, after approval' : 'No'} />
      </div>
      {(preview.items ?? []).map((item, index) => (
        <div key={`${item.scan_profile_id}-${index}`} className="agent-lab-preview-item">
          <div>
            <strong>{item.profile_label ?? item.scan_profile_id ?? 'Scan profile'}</strong>
            <span>{humanize(item.status ?? 'previewed')}</span>
          </div>
          <div className="agent-lab-tool-chips">
            {(item.tools ?? []).map((tool) => (
              <span key={`${tool.tool_id}-${tool.status}`} className={`agent-lab-tool-chip ${tool.status === 'blocked' ? 'blocked' : ''}`}>
                {tool.tool_label ?? tool.tool_id} · {humanize(tool.status ?? tool.install_state ?? 'unknown')}
              </span>
            ))}
          </div>
        </div>
      ))}
      {!!preview.blocked_items?.length && (
        <InlineNotice tone="warn" icon={<CircleSlash size={15} />} title="Policy blockers" body={preview.blocked_items.map((item) => humanize(item.reason ?? 'blocked')).join(', ')} />
      )}
      {!!preview.evidence_gaps?.length && (
        <InlineNotice tone="info" icon={<AlertTriangle size={15} />} title="Evidence gaps will be recorded" body={preview.evidence_gaps.map((item) => item.tool_label ?? item.tool_id ?? item.reason ?? 'gap').join(', ')} />
      )}
    </div>
  );
}

function BoundaryItem({icon, label, detail}: {icon: ReactNode; label: string; detail: string}) {
  return (
    <div className="agent-lab-boundary-item">
      <span>{icon}</span>
      <div><strong>{label}</strong><em>{detail}</em></div>
    </div>
  );
}

function PanelHeader({eyebrow, title, right}: {eyebrow: string; title: string; right?: ReactNode}) {
  return (
    <div className="agent-lab-panel-head">
      <div>
        <span>{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      {right}
    </div>
  );
}

function MiniStat({label, value}: {label: string; value: number}) {
  return (
    <div className="agent-lab-mini-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function InlineNotice({tone, icon, title, body}: {tone: 'warn' | 'info'; icon: ReactNode; title: string; body: string}) {
  return (
    <div className={`agent-lab-notice ${tone}`}>
      <span>{icon}</span>
      <div><strong>{title}</strong><p>{body}</p></div>
    </div>
  );
}

function ReviewBlock({title, icon, children}: {title: string; icon: ReactNode; children: ReactNode}) {
  return (
    <div className="agent-lab-review-block">
      <h3>{icon}{title}</h3>
      <div>{children}</div>
    </div>
  );
}

function StackItem({title, detail, meta, children}: {title: string; detail: string; meta?: string; children?: ReactNode}) {
  return (
    <div className="agent-lab-stack-item">
      <div>
        <strong>{title}</strong>
        <span>{detail}</span>
        {children}
      </div>
      {meta && <em>{meta}</em>}
    </div>
  );
}

function ExecutionItem({item}: {item: AgentLabRequestedExecution}) {
  return (
    <div className="agent-lab-execution-item">
      <div>
        <strong>{item.profile_label ?? item.scan_profile_id ?? 'Scan profile'}</strong>
        <span>{item.reason || 'No route reason imported.'}</span>
      </div>
      <div className="agent-lab-tool-chips">
        <span>{humanize(item.action)}</span>
        <span>{humanize(item.mode ?? 'dry_run_preview')}</span>
        {(item.tool_ids ?? []).map((toolId) => <span key={toolId}>{toolId}</span>)}
      </div>
    </div>
  );
}

function SafetyLabels({labels}: {labels: string[]}) {
  if (!labels.length) return null;
  return (
    <div className="agent-lab-safety-labels">
      {labels.slice(0, 5).map((label) => <span key={label}>{label}</span>)}
    </div>
  );
}

function MetaItem({label, value}: {label: string; value: string}) {
  return (
    <div className="agent-lab-meta-item">
      <span>{label}</span>
      <strong>{value || 'Not recorded'}</strong>
    </div>
  );
}

function MutedLine({children}: {children: ReactNode}) {
  return <p className="agent-lab-muted-line">{children}</p>;
}

function EmptyState({icon, title, body}: {icon: ReactNode; title: string; body: string}) {
  return (
    <div className="agent-lab-empty-state">
      <span>{icon}</span>
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {...init, cache: init?.method ? undefined : 'no-store'});
  const text = await response.text();
  let payload: unknown = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = {error: text};
    }
  }
  if (!response.ok) {
    const data = payload && typeof payload === 'object' ? payload as {error?: string; errors?: unknown} : {};
    const details = Array.isArray(data.errors) ? data.errors.map((item) => String(item)) : [];
    throw new AgentLabApiError(data.error || `Request failed with ${response.status}`, details);
  }
  return payload as T;
}

function buildAgentPrompt(adapter: AdapterOption, context: AgentLabContextPayload): string {
  return [
    `You are helping plan a DëvSec Agent Lab proposal for ${adapter.label}.`,
    '',
    'Read the DëvSec context bundle below. Recommend only known tool IDs, pack IDs, and scan profile IDs from the bundle.',
    'Packs are recommendations only, not runnable actions. External Surface is display-only.',
    'Do not suggest arbitrary commands, provider OAuth, installs, uninstalls, direct scanner execution, or policy overrides.',
    '',
    'Return exactly one JSON object matching schema_version "agent-lab.proposal.v1".',
    'Do not wrap it in Markdown. Do not include prose outside the JSON.',
    '',
    'BEGIN_DEVSEC_AGENT_CONTEXT_V1',
    JSON.stringify(context, null, 2),
    'END_DEVSEC_AGENT_CONTEXT_V1',
  ].join('\n');
}

function proposalPlaceholder(context: AgentLabContextPayload | null, adapterId: AgentLabAdapterId, repoPath: string): string {
  const contextId = context?.context_id ?? 'ctx_from_export';
  const contextHash = context?.context_hash ?? 'sha256:from-export';
  const profileId = context?.allowed_scan_profile_ids?.[0] ?? 'quick';
  const toolId = context?.allowed_tool_ids?.[0] ?? 'ai-static';
  return JSON.stringify({
    schema_version: 'agent-lab.proposal.v1',
    proposal_id: 'agent-generated-id',
    source: {adapter_id: adapterId, agent_label: adapterLabel(adapterId)},
    context: {context_id: contextId, context_hash: contextHash, repo_path: repoPath},
    summary: 'Run an existing DëvSec scan profile because the catalog says it is allowed for Agent Lab.',
    recommended_tools: [{tool_id: toolId, reason: 'Known Agent Lab tool.', expected_benefit: 'Adds local evidence.', safety_labels: []}],
    recommended_packs: [],
    requested_execution: [{action: 'run_scan_profile', scan_profile_id: profileId, tool_ids: [toolId], mode: 'dry_run_preview', requires_approval: true, reason: 'Use DëvSec scan routing only.'}],
    requested_permissions: ['local_repo_read', 'write_devsec_reports'],
  }, null, 2);
}

function proposalBelongsToRepo(proposal: AgentLabProposal, repo: ProjectRepo): boolean {
  return proposal.repo_path === repo.path || proposal.repo_name === repo.name || basename(String(proposal.repo_path ?? '')) === repo.name;
}

function basename(path: string): string {
  return path.replace(/\/+$/, '').split('/').pop() || path;
}

function adapterLabel(id: AgentLabAdapterId): string {
  return adapterOptions.find((option) => option.id === id)?.label ?? id;
}

function approvalTone(value?: string): 'pending' | 'approved' | 'denied' {
  if (value === 'approved') return 'approved';
  if (value === 'denied') return 'denied';
  return 'pending';
}

function approvalLabel(value?: string): string {
  if (value === 'approved') return 'Approved';
  if (value === 'denied') return 'Denied';
  return 'Pending';
}

function humanize(value?: string | null): string {
  if (!value) return 'Not recorded';
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
