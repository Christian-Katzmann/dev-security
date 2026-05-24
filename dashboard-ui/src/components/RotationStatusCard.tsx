import {Copy, FileText, RefreshCw, RotateCcw, Settings2} from 'lucide-react';
import {useCallback, useEffect, useState} from 'react';
import {
  ProjectRepo,
  RotationHistoryPayload,
  RotationScaffoldHandoff,
  RotationSecretRow,
  RotationStateSignal,
  RotationStatusPayload,
  formatDate,
  repoKeyFromPath,
} from '../dashboardData';
import RotationTriggerFlow from './RotationTriggerFlow';

type RotationStatusCardProps = {
  repo: ProjectRepo;
  /** Optional pre-fetched signal from /api/summary. Lets the card render the
   *  empty / unsupported branches without an immediate round-trip. */
  precomputed?: RotationStateSignal | null;
};

// Words, not symbols, per docs/agent-voice.md. The lone ⚠ carve-out only
// applies to IN_GRACE entries within 4h of revoke — see needsImminentRevoke.
const STATUS_LABELS: Record<string, string> = {
  ROTATED: 'ROTATED',
  IN_GRACE: 'IN GRACE',
  HALTED: 'HALTED',
  HEALTH_CHECK_FAILED: 'HEALTH CHECK FAILED',
  CANARY_VERIFY_FAILED: 'CANARY VERIFY FAILED',
  SOAK_FAILED: 'SOAK FAILED',
  ROLLED_BACK: 'ROLLED BACK',
  NEVER: 'NEVER ROTATED',
  MANUAL: 'MANUAL',
  unknown: 'UNKNOWN',
};

const INFLIGHT_LABEL = 'IN PROGRESS';
const INFLIGHT_STATUSES = new Set([
  'HEALTH_CHECK',
  'PREFLIGHT',
  'ACQUIRED',
  'WAITING_FOR_PASTE',
  'STAGED_CANARY',
  'DEPLOYED_CANARY',
  'IN_CANARY_VERIFY',
  'VERIFIED_CANARY',
  'STAGED_PROD',
  'DEPLOYED_PROD',
  'VERIFIED',
  'IN_SOAK',
  'SOAKED',
]);

function statusLabel(status: string): string {
  if (INFLIGHT_STATUSES.has(status)) return INFLIGHT_LABEL;
  return STATUS_LABELS[status] ?? status.toUpperCase();
}

function statusTone(status: string, needsAttention: boolean): string {
  if (needsAttention) return 'border-[#b91c1c] text-[#b91c1c]';
  if (status === 'ROTATED') return 'border-black/30 text-black';
  if (status === 'IN_GRACE') return 'border-[#7d4d10] text-[#7d4d10]';
  if (INFLIGHT_STATUSES.has(status)) return 'border-black/20 text-black/60';
  return 'border-black/10 text-black/45';
}

/**
 * The one ⚠ carve-out from the no-emoji rule (per the voice doctrine): an
 * IN_GRACE secret whose grace window expires within 4 hours is an
 * operationally serious moment — the old key is about to be revoked and the
 * operator needs to verify nothing depends on it. Anywhere else, words.
 */
function needsImminentRevoke(row: RotationSecretRow): boolean {
  if (row.status !== 'IN_GRACE' || !row.in_grace_until) return false;
  const expiry = new Date(row.in_grace_until).getTime();
  if (Number.isNaN(expiry)) return false;
  const hoursLeft = (expiry - Date.now()) / 3_600_000;
  return hoursLeft >= 0 && hoursLeft <= 4;
}

function stackCopy(stack: string | null | undefined): string {
  if (stack === 'vercel') return 'Next.js + Vercel';
  if (stack === 'python-cli') return 'Python CLI';
  return 'Stack not detected';
}

function formatCadence(row: RotationSecretRow): string {
  if (row.cadence_days == null) return 'No cadence set';
  if (row.days_since_rotation == null) return `Cadence ${row.cadence_days}d`;
  return `${row.days_since_rotation}d ago · cadence ${row.cadence_days}d`;
}

async function safeJson<T>(response: Response): Promise<T | null> {
  try {
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export default function RotationStatusCard({repo, precomputed}: RotationStatusCardProps) {
  const [status, setStatus] = useState<RotationStatusPayload | null>(null);
  const [history, setHistory] = useState<RotationHistoryPayload | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [isSettingUp, setIsSettingUp] = useState(false);
  const [handoff, setHandoff] = useState<RotationScaffoldHandoff | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [rotateTarget, setRotateTarget] = useState<RotationSecretRow | null>(null);

  // The dashboard's rotation endpoints are keyed by the slugified scan-history
  // repo name (e.g. ``besk-ftigelse.dk``), not by the un-slugified display name
  // from ``ProjectRepo.name`` (e.g. ``beskæftigelse.dk``). Derive the slug from
  // the on-disk path the same way the summary builder does.
  const repoKey = repoKeyFromPath(repo.path);

  const loadStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/rotation/status/${encodeURIComponent(repoKey)}`,
        {cache: 'no-store'},
      );
      if (response.status === 404) {
        setStatus(null);
        return;
      }
      if (!response.ok) throw new Error(await response.text());
      const payload = await safeJson<RotationStatusPayload>(response);
      setStatus(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to read rotation state.');
    } finally {
      setIsLoading(false);
    }
  }, [repoKey]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  async function loadHistory() {
    if (history) {
      setShowHistory((value) => !value);
      return;
    }
    setIsHistoryLoading(true);
    try {
      const response = await fetch(
        `/api/rotation/history/${encodeURIComponent(repoKey)}?limit=20`,
        {cache: 'no-store'},
      );
      if (!response.ok) throw new Error(await response.text());
      const payload = await safeJson<RotationHistoryPayload>(response);
      setHistory(payload);
      setShowHistory(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to read rotation history.');
    } finally {
      setIsHistoryLoading(false);
    }
  }

  async function requestScaffoldHandoff() {
    setIsSettingUp(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/rotation/scaffold/${encodeURIComponent(repoKey)}`,
        {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({confirmed: true}),
        },
      );
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || 'Unable to prepare scaffold handoff.');
      }
      const payload = await safeJson<RotationScaffoldHandoff>(response);
      setHandoff(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to prepare scaffold handoff.');
    } finally {
      setIsSettingUp(false);
    }
  }

  async function copyText(label: string, value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(label);
      window.setTimeout(() => setCopied(null), 1800);
    } catch {
      setError('Clipboard access was denied. Copy the text manually.');
    }
  }

  const signal: RotationStateSignal | null =
    status?.rotation_state ?? precomputed ?? null;
  const secrets = status?.secrets ?? [];
  const receipts = status?.receipts ?? [];

  return (
    <section className="border border-black/10 bg-white/70 p-5 md:p-6 shadow-[0_18px_60px_rgba(0,0,0,0.04)]">
      <header className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-5">
        <div>
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-black/40 mb-2">
            <RotateCcw className="w-4 h-4" strokeWidth={1.5} />
            Rotation Status
          </div>
          <h3 className="text-xl md:text-2xl font-light tracking-tight text-black">
            {repo.name}
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-black/55">
            Read-only view of the secrets-rotation skill's state for this repo.
            Status uses words, not symbols. The one carve-out is{' '}
            <span className="font-mono text-black">⚠</span>, reserved for an
            IN GRACE secret within four hours of revoke.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void loadStatus();
          }}
          disabled={isLoading}
          className="inline-flex items-center justify-center gap-2 border border-black/10 bg-[#fbfbfb] px-3 py-2 font-mono text-[10px] uppercase tracking-widest hover:border-black/40 disabled:opacity-50"
        >
          <RefreshCw className="w-3.5 h-3.5" strokeWidth={1.5} />
          {isLoading ? 'Reading' : 'Refresh'}
        </button>
      </header>

      {error && (
        <div className="mb-4 border border-[#b91c1c]/40 bg-white p-3 text-xs text-[#7f1d1d]">
          {error}
        </div>
      )}

      {!signal?.scaffolded ? (
        <ScaffoldEmptyState
          signal={signal}
          isSettingUp={isSettingUp}
          onRequest={requestScaffoldHandoff}
          handoff={handoff}
          copied={copied}
          onCopy={copyText}
        />
      ) : secrets.length === 0 && !isLoading ? (
        <p className="text-sm text-black/55">
          The rotation skill is scaffolded but no secrets are tracked yet.
          Run <span className="font-mono text-black">/secrets-rotation</span>{' '}
          in this repo to register secrets.
        </p>
      ) : (
        <RotationSecretsList secrets={secrets} onRotate={setRotateTarget} />
      )}

      {rotateTarget && (
        <RotationTriggerFlow
          repo={repo}
          secret={rotateTarget}
          onClose={() => setRotateTarget(null)}
          onDone={() => {
            void loadStatus();
            setHistory(null);
          }}
        />
      )}

      {signal?.scaffolded && (
        <div className="mt-5 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <button
            type="button"
            onClick={() => {
              void loadHistory();
            }}
            disabled={isHistoryLoading}
            className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-black hover:text-black/60"
          >
            <FileText className="w-3.5 h-3.5" strokeWidth={1.5} />
            {isHistoryLoading
              ? 'Reading history'
              : showHistory
                ? 'Hide history'
                : 'View history'}
          </button>
          {receipts.length > 0 && (
            <span className="font-mono text-[10px] uppercase tracking-widest text-black/40">
              {receipts.length} verification receipt
              {receipts.length === 1 ? '' : 's'}
            </span>
          )}
        </div>
      )}

      {showHistory && history && (
        <RotationHistoryPanel history={history} />
      )}

      {signal?.scaffolded && receipts.length > 0 && (
        <RotationReceiptsList repo={repo} receipts={receipts} />
      )}
    </section>
  );
}

function RotationSecretsList({
  secrets,
  onRotate,
}: {
  secrets: RotationSecretRow[];
  onRotate: (row: RotationSecretRow) => void;
}) {
  return (
    <div className="grid gap-2">
      {secrets.map((row) => {
        const imminent = needsImminentRevoke(row);
        const rotatable =
          row.status !== 'WAITING_FOR_PASTE' && row.status !== 'unknown';
        return (
          <article
            key={row.secret}
            className={`border bg-[#fbfbfb] p-4 ${
              row.needs_attention
                ? 'border-[#b91c1c]/40'
                : 'border-black/10'
            }`}
          >
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span
                    className={`font-mono text-[9px] uppercase tracking-widest border px-2 py-1 ${statusTone(
                      String(row.status),
                      row.needs_attention,
                    )}`}
                  >
                    {imminent && (
                      <span aria-label="warning" className="mr-1">
                        ⚠
                      </span>
                    )}
                    {statusLabel(String(row.status))}
                  </span>
                  {row.class && (
                    <span className="font-mono text-[9px] uppercase tracking-widest text-black/35">
                      Class {row.class}
                    </span>
                  )}
                </div>
                <h4 className="text-base font-medium text-black break-words font-mono">
                  {row.secret}
                </h4>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-black/55">
                  <span>{formatCadence(row)}</span>
                  {row.last_rotated_at && (
                    <span>Last: {formatDate(row.last_rotated_at)}</span>
                  )}
                  {row.in_grace_until && (
                    <span>
                      Revoke at: {formatDate(row.in_grace_until)}
                    </span>
                  )}
                  {row.next_rotation_due && row.status === 'ROTATED' && (
                    <span>Due: {formatDate(row.next_rotation_due)}</span>
                  )}
                </div>
              </div>
              <div className="flex md:flex-col items-start md:items-end gap-2">
                <button
                  type="button"
                  disabled={!rotatable}
                  onClick={() => onRotate(row)}
                  className="inline-flex items-center justify-center gap-2 border border-black bg-black text-white px-3 py-2 font-mono text-[10px] uppercase tracking-widest hover:bg-[#222] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  title={
                    rotatable
                      ? `Rotate ${row.secret}`
                      : 'This secret is mid-flight or in an unknown state.'
                  }
                >
                  <RotateCcw className="w-3.5 h-3.5" strokeWidth={1.5} />
                  Rotate
                </button>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function ScaffoldEmptyState({
  signal,
  isSettingUp,
  onRequest,
  handoff,
  copied,
  onCopy,
}: {
  signal: RotationStateSignal | null;
  isSettingUp: boolean;
  onRequest: () => void;
  handoff: RotationScaffoldHandoff | null;
  copied: string | null;
  onCopy: (label: string, value: string) => Promise<void>;
}) {
  const stack = signal?.stack ?? null;
  const supported = signal?.stack_supported ?? false;

  if (handoff && handoff.supported === false) {
    return (
      <div className="border border-black/10 bg-[#fbfbfb] p-5">
        <p className="text-sm leading-relaxed text-black/65">
          {handoff.message}
        </p>
      </div>
    );
  }

  if (handoff && handoff.supported === true) {
    return (
      <div className="border border-black bg-white p-5">
        <h4 className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-3">
          Set up rotation · handoff
        </h4>
        <p className="text-sm leading-relaxed text-black/60 mb-3">
          {handoff.why_not_shelled_out}
        </p>
        <div className="border border-black/10 bg-[#fbfbfb] p-4 mb-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-black/45">
              Working directory
            </span>
            <button
              type="button"
              onClick={() => onCopy('cwd', handoff.working_directory)}
              className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-black hover:text-black/60"
            >
              <Copy className="w-3 h-3" strokeWidth={1.5} />
              {copied === 'cwd' ? 'Copied' : 'Copy'}
            </button>
          </div>
          <pre className="text-xs text-black/75 whitespace-pre-wrap break-all font-mono">
            {handoff.working_directory}
          </pre>
        </div>
        <div className="border border-black/10 bg-[#fbfbfb] p-4 mb-4">
          <div className="flex items-center justify-between gap-3 mb-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-black/45">
              Command
            </span>
            <button
              type="button"
              onClick={() => onCopy('cmd', handoff.command)}
              className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-black hover:text-black/60"
            >
              <Copy className="w-3 h-3" strokeWidth={1.5} />
              {copied === 'cmd' ? 'Copied' : 'Copy'}
            </button>
          </div>
          <pre className="text-xs text-black/75 whitespace-pre-wrap break-all font-mono">
            {handoff.command}
          </pre>
        </div>
        <ol className="text-sm text-black/65 list-decimal pl-5 space-y-1">
          {handoff.next_steps.map((step, index) => (
            <li key={index}>{step}</li>
          ))}
        </ol>
      </div>
    );
  }

  if (!supported) {
    return (
      <div className="border border-black/10 bg-[#fbfbfb] p-5">
        <h4 className="text-sm font-medium text-black mb-2">
          Rotation isn't set up for this repo.
        </h4>
        <p className="text-sm leading-relaxed text-black/55 mb-3">
          This repo's stack isn't yet supported for automated rotation.
          Currently supported: Next.js + Vercel, Python CLI. Detected:{' '}
          <span className="font-mono text-black">{stackCopy(stack)}</span>.
        </p>
        <p className="text-xs text-black/45">
          When the repo gains a supported stack — or when the rotation skill
          adds an adapter for the current one — this card switches to the
          "Set up rotation" CTA.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-black/10 bg-[#fbfbfb] p-5">
      <h4 className="text-sm font-medium text-black mb-2">
        Rotation isn't set up for this repo.
      </h4>
      <p className="text-sm leading-relaxed text-black/55 mb-4">
        DëvSec can scaffold automated rotation for the secrets in this repo —
        leaked secrets become a single click to revoke and re-issue. Detected
        stack: <span className="font-mono text-black">{stackCopy(stack)}</span>.
      </p>
      <button
        type="button"
        onClick={onRequest}
        disabled={isSettingUp}
        className="inline-flex items-center justify-center gap-2 border border-black bg-black text-white px-4 py-3 font-mono text-[10px] uppercase tracking-widest hover:bg-[#222] transition-colors disabled:opacity-50"
      >
        <Settings2 className="w-4 h-4" strokeWidth={1.5} />
        {isSettingUp ? 'Preparing…' : 'Set up rotation'}
      </button>
      <p className="mt-3 text-xs text-black/40">
        The actual scaffolding happens inside a Claude Code session so the
        skill can confirm tier and secret classifications. This button
        returns the exact command and working directory.
      </p>
    </div>
  );
}

function RotationHistoryPanel({history}: {history: RotationHistoryPayload}) {
  if (!history.events.length) {
    return (
      <div className="mt-4 border border-black/10 bg-[#fbfbfb] p-4 text-sm text-black/55">
        No rotation events recorded yet.
      </div>
    );
  }
  return (
    <div className="mt-4 border border-black/10 bg-[#fbfbfb] p-4">
      <h4 className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-3">
        Last {history.events.length} events
      </h4>
      <ul className="grid gap-2">
        {history.events.map((event, index) => (
          <li
            key={`${event.timestamp}-${index}`}
            className="grid grid-cols-[120px_1fr_auto] gap-3 text-xs text-black/60 items-baseline"
          >
            <span className="font-mono text-black/45">
              {event.timestamp ? formatDate(event.timestamp) : 'unknown time'}
            </span>
            <span>
              <span className="font-mono text-black">{event.secret}</span>{' '}
              <span className="text-black/45">·</span>{' '}
              {event.step ?? 'unknown step'}
              {event.note ? ` — ${event.note}` : ''}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-black/45">
              {event.outcome ?? 'unknown'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RotationReceiptsList({
  repo,
  receipts,
}: {
  repo: ProjectRepo;
  receipts: {filename: string; modified_at: string}[];
}) {
  return (
    <div className="mt-4 border border-black/10 bg-[#fbfbfb] p-4">
      <h4 className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-3">
        Verification receipts
      </h4>
      <ul className="grid gap-1.5 text-xs">
        {receipts.slice(0, 6).map((receipt) => (
          <li
            key={receipt.filename}
            className="flex items-center justify-between gap-3"
          >
            <a
              href={`/api/rotation/receipts/${encodeURIComponent(repoKeyFromPath(repo.path))}/${encodeURIComponent(receipt.filename)}`}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-black hover:text-black/60 truncate"
            >
              {receipt.filename}
            </a>
            <span className="text-black/45 font-mono text-[10px] uppercase tracking-widest">
              {formatDate(receipt.modified_at)}
            </span>
          </li>
        ))}
        {receipts.length > 6 && (
          <li className="text-black/45">
            …and {receipts.length - 6} older.
          </li>
        )}
      </ul>
    </div>
  );
}

