import {useCallback, useEffect, useState} from 'react';
import {motion} from 'motion/react';
import {
  AlertTriangle,
  CheckCircle2,
  CircleSlash,
  GitPullRequest,
  Lock,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import {formatDate} from '../dashboardData';

// The hands-off code-fix flow (propose → clean-room review → land) is built,
// fenced, and test-pinned, but was previously reachable only through the
// devsec-mcp-rw adapter. This view surfaces it read-mostly: it lists proposals,
// shows each diff + clean-room verdict, and routes a land decision through the
// same `decide_landing` gate the MCP tool uses. It never proposes or reviews —
// that authoring half stays MCP-only by design.

type DiffStat = {added: number; removed: number};

type FixProposalSummary = {
  id: string;
  repo_name: string | null;
  title: string | null;
  case_id: string | null;
  base_branch: string | null;
  head_branch: string | null;
  fix_class: string | null;
  auto_merge_eligible: boolean;
  status: string | null;
  clean_room_status: string | null;
  landing_outcome: string | null;
  changed_files: string[];
  diff_stat: DiffStat;
  created_at: string | null;
  updated_at: string | null;
};

type FixProposalDetail = {
  proposal: FixProposalSummary;
  diff: string;
  diff_sha256: string | null;
  clean_room: {
    status: string | null;
    reviewer: string | null;
    reviewed_at: string | null;
    notes: string | null;
    checked_invariants: string[];
    invariants: string[];
  };
  landing: {
    outcome: string | null;
    reasons: string[];
    decided_at: string | null;
  };
};

type LandOutcome = {
  outcome: string;
  auto_merge: boolean;
  fix_class: string;
  clean_room_status: string;
  reasons: string[];
};

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
    const data = payload && typeof payload === 'object' ? (payload as {error?: string}) : {};
    throw new Error(data.error || `Request failed with ${response.status}`);
  }
  return payload as T;
}

function fixClassLabel(value: string | null): string {
  if (!value) return 'Unknown';
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

type CleanRoomTone = {label: string; classes: string};

function cleanRoomTone(status: string | null): CleanRoomTone {
  if (status === 'approved') return {label: 'Approved', classes: 'border-[#3c6b52] text-[#2e5742] bg-[#e6f1ea]'};
  if (status === 'rejected') return {label: 'Rejected', classes: 'border-[#842626] text-[#6e2020] bg-[#f3dcd9]'};
  return {label: 'Awaiting review', classes: 'border-black/15 text-black/55 bg-black/[0.03]'};
}

type LandingTone = {label: string; classes: string};

function landingTone(outcome: string | null): LandingTone {
  if (outcome === 'auto_merge') return {label: 'Auto-merge authorized', classes: 'border-[#3c6b52] text-[#2e5742] bg-[#e6f1ea]'};
  if (outcome === 'blocked') return {label: 'Blocked', classes: 'border-[#842626] text-[#6e2020] bg-[#f3dcd9]'};
  if (outcome === 'requires_human') return {label: 'Needs a human', classes: 'border-graph-gold text-[#7d4d10] bg-[#f5e6c8]'};
  return {label: 'No decision yet', classes: 'border-black/15 text-black/55 bg-black/[0.03]'};
}

export default function FixProposalsView() {
  const [proposals, setProposals] = useState<FixProposalSummary[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<FixProposalDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isLanding, setIsLanding] = useState(false);
  const [landMessage, setLandMessage] = useState<string | null>(null);

  const loadProposals = useCallback(async () => {
    setListError(null);
    try {
      const payload = await requestJson<{items: FixProposalSummary[]}>('/api/fix-proposals');
      setProposals(payload.items);
      setSelectedId((current) => current ?? payload.items[0]?.id ?? null);
    } catch (error) {
      setProposals([]);
      setListError(error instanceof Error ? error.message : 'Unable to load fix proposals.');
    }
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    setIsLoadingDetail(true);
    setDetailError(null);
    try {
      const payload = await requestJson<FixProposalDetail>(`/api/fix-proposals/${encodeURIComponent(id)}`);
      setDetail(payload);
    } catch (error) {
      setDetail(null);
      setDetailError(error instanceof Error ? error.message : 'Unable to load this proposal.');
    } finally {
      setIsLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    void loadProposals();
  }, [loadProposals]);

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  async function decideLanding() {
    if (!selectedId) return;
    setIsLanding(true);
    setLandMessage(null);
    try {
      const outcome = await requestJson<LandOutcome>(`/api/fix-proposals/${encodeURIComponent(selectedId)}/land`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: '{}',
      });
      setLandMessage(landingTone(outcome.outcome).label + (outcome.reasons[0] ? ` — ${outcome.reasons[0]}` : ''));
      await loadDetail(selectedId);
      await loadProposals();
    } catch (error) {
      setLandMessage(error instanceof Error ? error.message : 'Unable to record a land decision.');
    } finally {
      setIsLanding(false);
    }
  }

  return (
    <motion.div
      initial={{opacity: 0, y: 10}}
      animate={{opacity: 1, y: 0}}
      exit={{opacity: 0, scale: 0.98}}
      className="relative flex flex-col w-full p-6 md:p-12 max-w-[1400px] mx-auto gap-8"
    >
      <div className="flex justify-between items-end border-b border-black/10 pb-6 shrink-0">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-widest text-black/40 flex items-center gap-2 mb-2">
            <GitPullRequest className="w-3.5 h-3.5" /> Hands-off code fixes
          </div>
          <h2 className="text-3xl font-light text-black tracking-tight">Code fixes</h2>
          <p className="text-sm text-black/55 mt-2 max-w-2xl">
            An agent proposes a fix as a branch diff; a separate clean-room reviewer judges only the diff and its
            invariants — never the finding. Landing routes through the same gate the MCP tool uses: only an approved,
            allowlisted, hash-matching fix auto-merges.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadProposals()}
          className="font-mono text-[11px] uppercase tracking-widest text-black/50 hover:text-black flex items-center gap-2 border border-black/10 px-3 py-2 bg-white/50"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      <div className="flex flex-wrap gap-3 shrink-0">
        <BoundaryChip icon={<Lock className="w-3.5 h-3.5" />} label="Read + land only" detail="No propose or review here — those stay MCP-only." />
        <BoundaryChip icon={<ShieldCheck className="w-3.5 h-3.5" />} label="Clean-room fenced" detail="The reviewer sees the diff and invariants, never the finding." />
        <BoundaryChip icon={<GitPullRequest className="w-3.5 h-3.5" />} label="Gated auto-merge" detail="Only action-pin, dependency-bump, and lockfile-patch classes." />
      </div>

      <div className="grid grid-cols-12 gap-8 pb-12">
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-3">
          <h3 className="font-mono text-[10px] tracking-widest text-black/40 uppercase border-b border-black/5 pb-2">
            Proposals {proposals ? `· ${proposals.length}` : ''}
          </h3>
          {listError && <p className="text-xs text-[#6e2020] bg-[#f3dcd9] border border-[#842626]/30 p-3">{listError}</p>}
          {proposals === null && <p className="text-xs text-black/40 font-mono">Loading…</p>}
          {proposals && proposals.length === 0 && !listError && (
            <div className="border border-black/10 bg-white/50 p-6 text-sm text-black/55">
              <strong className="block text-black/70 mb-1">No proposals yet</strong>
              A code-fix proposal appears here once an agent records one through the <span className="font-mono">devsec-mcp-rw</span> adapter.
            </div>
          )}
          {proposals?.map((proposal) => {
            const tone = cleanRoomTone(proposal.clean_room_status);
            const isActive = proposal.id === selectedId;
            return (
              <button
                key={proposal.id}
                type="button"
                onClick={() => setSelectedId(proposal.id)}
                className={
                  'text-left border p-4 bg-white/60 transition-colors ' +
                  (isActive ? 'border-black shadow-sm' : 'border-black/10 hover:border-black/30')
                }
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm text-black/90 leading-snug">{proposal.title || proposal.id}</span>
                  <span className={'shrink-0 font-mono text-[9px] uppercase tracking-widest border px-1.5 py-0.5 ' + tone.classes}>
                    {tone.label}
                  </span>
                </div>
                <div className="font-mono text-[10px] text-black/45 mt-3 flex flex-wrap gap-x-3 gap-y-1">
                  <span>{proposal.repo_name}</span>
                  <span>{fixClassLabel(proposal.fix_class)}</span>
                  <span className="text-[#2e5742]">+{proposal.diff_stat.added}</span>
                  <span className="text-[#6e2020]">−{proposal.diff_stat.removed}</span>
                </div>
              </button>
            );
          })}
        </div>

        <div className="col-span-12 lg:col-span-8">
          {detailError && <p className="text-sm text-[#6e2020] bg-[#f3dcd9] border border-[#842626]/30 p-4">{detailError}</p>}
          {!detail && !detailError && (
            <div className="border border-black/10 bg-white/50 p-10 text-sm text-black/45 text-center">
              {isLoadingDetail ? 'Loading proposal…' : 'Select a proposal to see its diff and clean-room verdict.'}
            </div>
          )}
          {detail && <ProposalDetail detail={detail} isLanding={isLanding} landMessage={landMessage} onLand={decideLanding} />}
        </div>
      </div>
    </motion.div>
  );
}

function ProposalDetail({
  detail,
  isLanding,
  landMessage,
  onLand,
}: {
  detail: FixProposalDetail;
  isLanding: boolean;
  landMessage: string | null;
  onLand: () => void;
}) {
  const {proposal, diff, clean_room: cleanRoom, landing} = detail;
  const landTone = landingTone(landing.outcome);
  const crTone = cleanRoomTone(cleanRoom.status);

  return (
    <div className="flex flex-col gap-6">
      <div className="border border-black/10 bg-white/60 p-5">
        <h3 className="text-lg text-black/90 leading-snug">{proposal.title || proposal.id}</h3>
        <div className="font-mono text-[10px] text-black/45 mt-3 flex flex-wrap gap-x-4 gap-y-1">
          <span>{proposal.repo_name}</span>
          <span>{proposal.base_branch} ← {proposal.head_branch}</span>
          <span>{fixClassLabel(proposal.fix_class)}</span>
          {proposal.auto_merge_eligible
            ? <span className="text-[#2e5742]">Auto-merge eligible</span>
            : <span className="text-[#7d4d10]">Needs a human</span>}
          <span>{formatDate(proposal.created_at)}</span>
        </div>
      </div>

      <div className="border border-black/10 bg-[#1c1c1c] overflow-hidden">
        <div className="font-mono text-[10px] tracking-widest text-white/40 uppercase px-4 py-2 border-b border-white/10 flex justify-between">
          <span>Diff</span>
          <span>{proposal.changed_files.length} file{proposal.changed_files.length === 1 ? '' : 's'}</span>
        </div>
        <pre className="text-[11px] leading-relaxed text-white/80 font-mono p-4 overflow-auto max-h-[360px] whitespace-pre">
          {diff.split('\n').map((line, i) => (
            <div
              key={i}
              className={
                line.startsWith('+') && !line.startsWith('+++')
                  ? 'text-[#8fd0a8]'
                  : line.startsWith('-') && !line.startsWith('---')
                    ? 'text-[#e29a92]'
                    : line.startsWith('@@')
                      ? 'text-graph-gold'
                      : 'text-white/45'
              }
            >
              {line || ' '}
            </div>
          ))}
        </pre>
      </div>

      <div className="border border-black/10 bg-white/60 p-5">
        <div className="flex items-center justify-between border-b border-black/5 pb-3">
          <h4 className="font-mono text-[10px] tracking-widest text-black/40 uppercase">Clean-room verdict</h4>
          <span className={'font-mono text-[9px] uppercase tracking-widest border px-2 py-0.5 ' + crTone.classes}>{crTone.label}</span>
        </div>
        {cleanRoom.reviewer && (
          <p className="font-mono text-[10px] text-black/45 mt-3">Reviewed by {cleanRoom.reviewer} · {formatDate(cleanRoom.reviewed_at)}</p>
        )}
        <p className="text-xs text-black/50 mt-3">Invariants the reviewer verifies for this fix class — every one a statement about the diff:</p>
        <ul className="mt-2 space-y-1.5">
          {cleanRoom.invariants.map((invariant, i) => {
            const checked = cleanRoom.checked_invariants.includes(invariant);
            return (
              <li key={i} className="flex items-start gap-2 text-xs text-black/70">
                {checked
                  ? <CheckCircle2 className="w-3.5 h-3.5 text-[#3c6b52] mt-0.5 shrink-0" />
                  : <CircleSlash className="w-3.5 h-3.5 text-black/25 mt-0.5 shrink-0" />}
                <span>{invariant}</span>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="border border-black/10 bg-white/60 p-5">
        <div className="flex items-center justify-between border-b border-black/5 pb-3">
          <h4 className="font-mono text-[10px] tracking-widest text-black/40 uppercase">Land decision</h4>
          <span className={'font-mono text-[9px] uppercase tracking-widest border px-2 py-0.5 ' + landTone.classes}>{landTone.label}</span>
        </div>
        {landing.reasons.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {landing.reasons.map((reason, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-black/60">
                <span className="text-black/30 mt-0.5">·</span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="flex items-center gap-3 mt-4">
          <button
            type="button"
            onClick={onLand}
            disabled={isLanding}
            className="font-mono text-[11px] uppercase tracking-widest text-white bg-black px-4 py-2.5 hover:bg-black/80 disabled:opacity-40 flex items-center gap-2"
          >
            <GitPullRequest className="w-3.5 h-3.5" /> {isLanding ? 'Deciding…' : 'Evaluate land decision'}
          </button>
          <span className="flex items-center gap-1.5 font-mono text-[10px] text-black/40">
            <AlertTriangle className="w-3 h-3" /> Re-runs the proven gate; it never bypasses clean-room or branch rules.
          </span>
        </div>
        {landMessage && <p className="text-xs text-black/60 mt-3 bg-black/[0.03] border border-black/10 p-3">{landMessage}</p>}
      </div>
    </div>
  );
}

function BoundaryChip({icon, label, detail}: {icon: React.ReactNode; label: string; detail: string}) {
  return (
    <div className="flex items-start gap-2.5 border border-black/10 bg-white/50 px-3.5 py-2.5 max-w-xs">
      <span className="text-black/50 mt-0.5">{icon}</span>
      <span>
        <span className="block text-xs text-black/80 font-medium">{label}</span>
        <span className="block font-mono text-[10px] text-black/45 leading-tight mt-0.5">{detail}</span>
      </span>
    </div>
  );
}
