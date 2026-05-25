import {AlertTriangle, Copy, Pause, Play, RotateCcw, Square, X} from 'lucide-react';
import type {ReactNode} from 'react';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
  BatchFilterPreset,
  BatchJobSnapshot,
  ProjectRepo,
  RotationSecretRow,
  batchRotationConfirmationPhrase,
  formatDate,
  repoKeyFromPath,
} from '../dashboardData';
import {VerificationReportRenderer} from './RotationTriggerFlow';

type BatchStep = 'select' | 'confirm' | 'running' | 'done';

const FILTER_CHIPS: {preset: BatchFilterPreset; label: string; description: string}[] = [
  {preset: 'all_actionable', label: 'All actionable', description: 'Never rotated + needs attention'},
  {preset: 'never_rotated', label: 'Never rotated', description: 'Secrets that have never been rotated'},
  {preset: 'needs_attention', label: 'Needs attention', description: 'Overdue or in a failure state'},
];

const INFLIGHT_STATUSES = new Set([
  'HEALTH_CHECK', 'PREFLIGHT', 'ACQUIRED', 'WAITING_FOR_PASTE',
  'STAGED_CANARY', 'DEPLOYED_CANARY', 'IN_CANARY_VERIFY', 'VERIFIED_CANARY',
  'STAGED_PROD', 'DEPLOYED_PROD', 'VERIFIED', 'IN_SOAK', 'SOAKED',
]);

const CLASS_ORDER: Record<string, number> = {'A': 0, 'B-API': 1, 'B': 1, 'B-HUMAN': 2};

function classOrder(row: RotationSecretRow): number {
  return CLASS_ORDER[(row.class ?? '').toUpperCase()] ?? 3;
}

function isActionable(row: RotationSecretRow, preset: BatchFilterPreset): boolean {
  if (INFLIGHT_STATUSES.has(String(row.status))) return false;
  if (row.secret === '(corrupt)' || row.secret === '(unreadable)') return false;
  if (preset === 'never_rotated') return row.status === 'NEVER';
  if (preset === 'needs_attention') return row.needs_attention;
  return row.status === 'NEVER' || row.needs_attention;
}

function secretSubStatus(secret: string, batch: BatchJobSnapshot): 'queued' | 'running' | 'done' | 'halted' | 'skipped' {
  if (batch.completed.includes(secret)) return 'done';
  if (batch.halted.includes(secret)) return 'halted';
  if (batch.current_secret === secret) return 'running';
  const queueIndex = batch.queue.indexOf(secret);
  const position = batch.position ?? 0;
  if (queueIndex >= 0 && queueIndex < position && !batch.completed.includes(secret) && !batch.halted.includes(secret)) return 'skipped';
  return 'queued';
}

function subStatusLabel(status: ReturnType<typeof secretSubStatus>): string {
  return {queued: 'Queued', running: 'Now', done: 'Done', halted: 'Halted', skipped: 'Skipped'}[status];
}

function subStatusTone(status: ReturnType<typeof secretSubStatus>): string {
  return {
    queued: 'text-black/30',
    running: 'text-black',
    done: 'text-black/55',
    halted: 'text-[#7f1d1d]',
    skipped: 'text-black/40',
  }[status];
}

export type RotationBatchFlowProps = {
  repo: ProjectRepo;
  secrets: RotationSecretRow[];
  onClose: () => void;
  onDone: () => void;
};

export default function RotationBatchFlow({repo, secrets, onClose, onDone}: RotationBatchFlowProps) {
  const [step, setStep] = useState<BatchStep>('select');
  const [filter, setFilter] = useState<BatchFilterPreset>('all_actionable');
  const [customSelection, setCustomSelection] = useState<Set<string>>(new Set());
  const [useCustom, setUseCustom] = useState(false);
  const [typedPhrase, setTypedPhrase] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [batch, setBatch] = useState<BatchJobSnapshot | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [receiptText, setReceiptText] = useState<string | null>(null);
  const [receiptCopied, setReceiptCopied] = useState(false);
  const [stopRequested, setStopRequested] = useState(false);

  const candidates = useMemo(() => {
    if (useCustom) {
      return secrets
        .filter((row) => customSelection.has(row.secret) && !INFLIGHT_STATUSES.has(String(row.status)))
        .sort((a, b) => classOrder(a) - classOrder(b) || a.secret.localeCompare(b.secret));
    }
    return secrets
      .filter((row) => isActionable(row, filter))
      .sort((a, b) => classOrder(a) - classOrder(b) || a.secret.localeCompare(b.secret));
  }, [secrets, filter, useCustom, customSelection]);

  const hasClassB = useMemo(
    () => candidates.some((row) => (row.class ?? '').toUpperCase().startsWith('B')),
    [candidates],
  );

  const expectedPhrase = useMemo(
    () => batchRotationConfirmationPhrase(candidates.length, {hasClassB}),
    [candidates.length, hasClassB],
  );

  const phraseMatches = typedPhrase.trim() === expectedPhrase;
  const canSubmit = phraseMatches && candidates.length > 0 && step === 'confirm';

  const repoKey = repoKeyFromPath(repo.path);

  async function submitBatch() {
    setSubmitError(null);
    try {
      const response = await fetch(
        `/api/rotation/trigger-batch/${encodeURIComponent(repoKey)}`,
        {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            filter: useCustom ? 'all_actionable' : filter,
            confirmed: true,
            confirmation_phrase: expectedPhrase,
          }),
        },
      );
      if (!response.ok) {
        const text = await response.text();
        let detail = text;
        try {
          const parsed = JSON.parse(text);
          detail = parsed.error ?? parsed.message ?? text;
        } catch { /* use raw text */ }
        throw new Error(detail || 'Batch rotation request was refused.');
      }
      const payload = (await response.json()) as {batch: BatchJobSnapshot};
      setBatch(payload.batch);
      setStep('running');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Unable to trigger batch rotation.');
    }
  }

  const pollRef = useRef<number | null>(null);
  useEffect(() => {
    if (step !== 'running' || !batch) return;
    const batchId = batch.id;
    const tick = async () => {
      try {
        const response = await fetch(
          `/api/rotation/jobs/batch/${encodeURIComponent(batchId)}`,
          {cache: 'no-store'},
        );
        if (!response.ok) throw new Error(await response.text());
        const payload = (await response.json()) as {batch: BatchJobSnapshot};
        setBatch(payload.batch);
        const s = payload.batch.status;
        if (s === 'complete' || s === 'complete_with_errors' || s === 'stopped') {
          if (pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
          setStep('done');
        }
      } catch (err) {
        setPollError(err instanceof Error ? err.message : 'Lost track of the batch job.');
      }
    };
    void tick();
    pollRef.current = window.setInterval(tick, 2000);
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [batch?.id, step]);

  useEffect(() => {
    if (step !== 'done' || !batch?.batch_receipt) {
      setReceiptText(null);
      return;
    }
    const receiptPath = `/api/rotation/receipts/${encodeURIComponent(repoKey)}/${encodeURIComponent(batch.batch_receipt)}`;
    let cancelled = false;
    fetch(receiptPath, {cache: 'no-store'})
      .then((r) => (r.ok ? r.text() : Promise.reject(r)))
      .then((text) => { if (!cancelled) setReceiptText(text); })
      .catch(() => { if (!cancelled) setReceiptText(null); });
    return () => { cancelled = true; };
  }, [batch?.batch_receipt, step, repoKey]);

  const close = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (step === 'done') onDone();
    onClose();
  }, [onClose, onDone, step]);

  async function copyReceipt() {
    if (!receiptText) return;
    try {
      await navigator.clipboard.writeText(receiptText);
      setReceiptCopied(true);
      window.setTimeout(() => setReceiptCopied(false), 1800);
    } catch { /* clipboard denied; user can select text */ }
  }

  async function requestStop() {
    if (!batch) return;
    setStopRequested(true);
    try {
      await fetch(
        `/api/rotation/jobs/batch/${encodeURIComponent(batch.id)}/stop`,
        {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'},
      );
    } catch { /* best effort */ }
  }

  async function cancelStop() {
    setStopRequested(false);
  }

  async function requestContinue() {
    if (!batch) return;
    try {
      const response = await fetch(
        `/api/rotation/jobs/batch/${encodeURIComponent(batch.id)}/continue`,
        {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'},
      );
      if (response.ok) {
        const payload = (await response.json()) as {batch: BatchJobSnapshot};
        setBatch(payload.batch);
      }
    } catch { /* best effort */ }
  }

  async function requestBatchStop() {
    if (!batch) return;
    try {
      const response = await fetch(
        `/api/rotation/jobs/batch/${encodeURIComponent(batch.id)}/stop`,
        {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'},
      );
      if (response.ok) {
        const payload = (await response.json()) as {batch: BatchJobSnapshot};
        setBatch(payload.batch);
        setStep('done');
      }
    } catch { /* best effort */ }
  }

  const notableWarnings = useMemo(
    () => candidates.filter((row) => row.rotation_warning?.trim()),
    [candidates],
  );

  function toggleCustomSecret(secretName: string) {
    setCustomSelection((prev) => {
      const next = new Set(prev);
      if (next.has(secretName)) next.delete(secretName);
      else next.add(secretName);
      return next;
    });
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Rotate all — ${repo.name}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="bg-white border border-black/10 w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-[0_24px_80px_rgba(0,0,0,0.18)]">
        <header className="flex items-start justify-between gap-3 border-b border-black/10 px-5 py-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-black/40 flex items-center gap-2">
              <RotateCcw className="w-3.5 h-3.5" strokeWidth={1.5} />
              Batch rotation · Tier 5R
            </div>
            <h2 className="mt-1 text-lg font-medium text-black">
              Rotate {candidates.length} secret{candidates.length === 1 ? '' : 's'} —{' '}
              <span className="font-mono">{repo.name}</span>
            </h2>
            <p className="mt-1 text-xs text-black/45">
              Sequential execution. Each secret rotates one at a time.
            </p>
          </div>
          <button
            type="button"
            onClick={close}
            className="text-black/40 hover:text-black"
            aria-label="Close"
          >
            <X className="w-5 h-5" strokeWidth={1.5} />
          </button>
        </header>

        <div className="px-5 py-4">
          {step === 'select' && (
            <SelectStep
              secrets={secrets}
              filter={filter}
              onFilter={setFilter}
              useCustom={useCustom}
              onUseCustom={setUseCustom}
              customSelection={customSelection}
              onToggleSecret={toggleCustomSecret}
              candidates={candidates}
            />
          )}
          {step === 'confirm' && (
            <ConfirmStep
              candidates={candidates}
              hasClassB={hasClassB}
              expectedPhrase={expectedPhrase}
              typedPhrase={typedPhrase}
              onTypedPhrase={setTypedPhrase}
              notableWarnings={notableWarnings}
              submitError={submitError}
            />
          )}
          {step === 'running' && batch && (
            <RunningStep
              batch={batch}
              pollError={pollError}
              stopRequested={stopRequested}
              onRequestStop={requestStop}
              onCancelStop={cancelStop}
              onContinue={requestContinue}
              onStop={requestBatchStop}
            />
          )}
          {step === 'done' && batch && (
            <DoneStep
              batch={batch}
              receiptText={receiptText}
              receiptCopied={receiptCopied}
              onCopy={copyReceipt}
            />
          )}
        </div>

        <footer className="flex flex-col-reverse md:flex-row md:items-center md:justify-end gap-2 border-t border-black/10 px-5 py-4">
          {step === 'select' && (
            <>
              <button
                type="button"
                onClick={close}
                className="px-4 py-2 font-mono text-[10px] uppercase tracking-widest border border-black/10 hover:border-black/40"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={candidates.length === 0}
                onClick={() => setStep('confirm')}
                className="px-4 py-2 font-mono text-[10px] uppercase tracking-widest border border-black bg-black text-white hover:bg-[#222] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Continue with {candidates.length} secret{candidates.length === 1 ? '' : 's'}
              </button>
            </>
          )}
          {step === 'confirm' && (
            <>
              <button
                type="button"
                onClick={() => { setStep('select'); setTypedPhrase(''); setSubmitError(null); }}
                className="px-4 py-2 font-mono text-[10px] uppercase tracking-widest border border-black/10 hover:border-black/40"
              >
                Back
              </button>
              <button
                type="button"
                disabled={!canSubmit}
                onClick={() => { void submitBatch(); }}
                className="px-4 py-2 font-mono text-[10px] uppercase tracking-widest border border-black bg-black text-white hover:bg-[#222] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Rotate {candidates.length} secret{candidates.length === 1 ? '' : 's'}
              </button>
            </>
          )}
          {step === 'running' && (
            <span className="text-right text-[11px] leading-relaxed text-black/45">
              The batch runs each rotation sequentially. If one halts, the queue stops.
            </span>
          )}
          {step === 'done' && (
            <button
              type="button"
              onClick={close}
              className="px-4 py-2 font-mono text-[10px] uppercase tracking-widest border border-black bg-black text-white hover:bg-[#222] transition-colors"
            >
              Close
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}

function SelectStep({
  secrets,
  filter,
  onFilter,
  useCustom,
  onUseCustom,
  customSelection,
  onToggleSecret,
  candidates,
}: {
  secrets: RotationSecretRow[];
  filter: BatchFilterPreset;
  onFilter: (preset: BatchFilterPreset) => void;
  useCustom: boolean;
  onUseCustom: (value: boolean) => void;
  customSelection: Set<string>;
  onToggleSecret: (secret: string) => void;
  candidates: RotationSecretRow[];
}) {
  const selectableSecrets = secrets
    .filter((row) => !INFLIGHT_STATUSES.has(String(row.status)) && row.secret !== '(corrupt)' && row.secret !== '(unreadable)')
    .sort((a, b) => classOrder(a) - classOrder(b) || a.secret.localeCompare(b.secret));

  return (
    <div className="grid gap-4">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-2">
          Filter
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTER_CHIPS.map((chip) => (
            <button
              key={chip.preset}
              type="button"
              onClick={() => { onFilter(chip.preset); onUseCustom(false); }}
              className={`px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest border transition-colors ${
                !useCustom && filter === chip.preset
                  ? 'border-black bg-black text-white'
                  : 'border-black/10 bg-[#fbfbfb] text-black/60 hover:border-black/40'
              }`}
              title={chip.description}
            >
              {chip.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => onUseCustom(true)}
            className={`px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest border transition-colors ${
              useCustom
                ? 'border-black bg-black text-white'
                : 'border-black/10 bg-[#fbfbfb] text-black/60 hover:border-black/40'
            }`}
          >
            Custom selection
          </button>
        </div>
      </div>

      {useCustom ? (
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-2">
            Select secrets ({customSelection.size} selected)
          </div>
          <div className="border border-black/10 bg-[#fbfbfb] max-h-64 overflow-y-auto">
            {selectableSecrets.map((row) => (
              <label
                key={row.secret}
                className="flex items-center gap-3 px-3 py-2 border-b border-black/5 last:border-b-0 cursor-pointer hover:bg-black/[0.02]"
              >
                <input
                  type="checkbox"
                  checked={customSelection.has(row.secret)}
                  onChange={() => onToggleSecret(row.secret)}
                />
                <span className="font-mono text-xs text-black">{row.secret}</span>
                {row.class && (
                  <span className="font-mono text-[9px] uppercase tracking-widest text-black/35">
                    Class {row.class}
                  </span>
                )}
                <span className={`ml-auto font-mono text-[9px] uppercase tracking-widest ${
                  row.needs_attention ? 'text-[#b91c1c]' : 'text-black/35'
                }`}>
                  {row.status === 'NEVER' ? 'Never' : String(row.status).toLowerCase()}
                </span>
              </label>
            ))}
          </div>
        </div>
      ) : (
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-2">
            Candidates ({candidates.length})
          </div>
          {candidates.length === 0 ? (
            <div className="border border-black/10 bg-[#fbfbfb] p-4 text-sm text-black/55">
              No secrets match this filter.
            </div>
          ) : (
            <div className="border border-black/10 bg-[#fbfbfb] max-h-64 overflow-y-auto">
              {candidates.map((row) => (
                <div
                  key={row.secret}
                  className="flex items-center gap-3 px-3 py-2 border-b border-black/5 last:border-b-0"
                >
                  <span className="font-mono text-xs text-black">{row.secret}</span>
                  {row.class && (
                    <span className="font-mono text-[9px] uppercase tracking-widest text-black/35">
                      Class {row.class}
                    </span>
                  )}
                  <span className={`ml-auto font-mono text-[9px] uppercase tracking-widest ${
                    row.needs_attention ? 'text-[#b91c1c]' : 'text-black/35'
                  }`}>
                    {row.status === 'NEVER' ? 'Never' : String(row.status).toLowerCase()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ConfirmStep({
  candidates,
  hasClassB,
  expectedPhrase,
  typedPhrase,
  onTypedPhrase,
  notableWarnings,
  submitError,
}: {
  candidates: RotationSecretRow[];
  hasClassB: boolean;
  expectedPhrase: string;
  typedPhrase: string;
  onTypedPhrase: (value: string) => void;
  notableWarnings: RotationSecretRow[];
  submitError: string | null;
}) {
  return (
    <div className="grid gap-4">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-2">
          Rotation queue ({candidates.length} secret{candidates.length === 1 ? '' : 's'})
        </div>
        <div className="border border-black/10 bg-[#fbfbfb] max-h-48 overflow-y-auto">
          {candidates.map((row, index) => (
            <div
              key={row.secret}
              className="flex items-center gap-3 px-3 py-2 border-b border-black/5 last:border-b-0 text-xs"
            >
              <span className="font-mono text-[10px] text-black/30 w-5 text-right">{index + 1}</span>
              <span className="font-mono text-black">{row.secret}</span>
              {row.class && (
                <span className={`font-mono text-[9px] uppercase tracking-widest px-1.5 py-0.5 border ${
                  (row.class ?? '').toUpperCase().startsWith('B')
                    ? 'border-[#7d4d10]/30 text-[#7d4d10]'
                    : 'border-black/10 text-black/35'
                }`}>
                  {row.class}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {notableWarnings.length > 0 && (
        <div className="border border-[#7d4d10]/30 bg-[#fbfbfb] p-3 text-xs leading-relaxed text-[#7d4d10]">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-3.5 h-3.5 flex-none" strokeWidth={1.5} />
            <span className="font-mono text-[10px] uppercase tracking-widest">Notable consequences</span>
          </div>
          <ul className="grid gap-1.5 pl-1">
            {notableWarnings.map((row) => (
              <li key={row.secret}>
                <span className="font-mono text-[#7d4d10]">{row.secret}</span>:{' '}
                {row.rotation_warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {hasClassB && (
        <div className="border border-[#7d4d10]/30 bg-[#fbfbfb] p-3 text-xs leading-relaxed text-[#7d4d10] flex gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-none" strokeWidth={1.5} />
          <span>
            This batch includes Class B (provider-issued) secrets. Rotation triggers
            irreversible provider-side changes. The old key enters a 24h grace window
            before automatic revoke.
          </span>
        </div>
      )}

      <div>
        <label className="block text-sm text-black/70 mb-1">
          Type the batch confirmation phrase:
        </label>
        <pre className="mt-1 mb-2 font-mono text-xs text-black bg-[#fbfbfb] border border-black/10 p-3 whitespace-pre-wrap break-words">
          {expectedPhrase}
        </pre>
        <textarea
          value={typedPhrase}
          onChange={(event) => onTypedPhrase(event.target.value)}
          rows={2}
          spellCheck={false}
          className="block w-full font-mono text-xs border border-black/20 p-3 focus:outline-none focus:border-black"
          placeholder="Paste or retype the phrase exactly."
        />
      </div>

      {submitError && (
        <div className="border border-[#b91c1c]/40 bg-white p-3 text-xs text-[#7f1d1d]">
          {submitError}
        </div>
      )}
    </div>
  );
}

function RunningStep({
  batch,
  pollError,
  stopRequested,
  onRequestStop,
  onCancelStop,
  onContinue,
  onStop,
}: {
  batch: BatchJobSnapshot;
  pollError: string | null;
  stopRequested: boolean;
  onRequestStop: () => void;
  onCancelStop: () => void;
  onContinue: () => void;
  onStop: () => void;
}) {
  const isHaltedAwaiting = batch.halted_awaiting_decision;

  return (
    <div className="grid gap-4">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-1">
          Batch progress · {batch.completed.length + batch.halted.length} of {batch.total}
        </div>
        <div className="w-full h-1.5 bg-black/5 mt-1 mb-3">
          <div
            className={`h-full transition-all duration-500 ${
              batch.halted.length > 0 ? 'bg-[#b91c1c]' : 'bg-black'
            }`}
            style={{width: `${Math.round(((batch.completed.length + batch.halted.length) / Math.max(1, batch.total)) * 100)}%`}}
          />
        </div>
      </div>

      <div className="border border-black/10 bg-[#fbfbfb] max-h-64 overflow-y-auto">
        {batch.queue.map((secret) => {
          const status = secretSubStatus(secret, batch);
          return (
            <div
              key={secret}
              className={`flex items-center gap-3 px-3 py-2 border-b border-black/5 last:border-b-0 text-xs ${subStatusTone(status)}`}
            >
              <span className="font-mono text-[10px] uppercase tracking-widest w-14">
                {subStatusLabel(status)}
              </span>
              <span className={`font-mono ${status === 'running' ? 'text-black font-medium' : ''}`}>
                {secret}
              </span>
              {status === 'running' && batch.current_job_id && (
                <span className="ml-auto font-mono text-[9px] uppercase tracking-widest text-black/30">
                  In flight
                </span>
              )}
            </div>
          );
        })}
      </div>

      {isHaltedAwaiting && (
        <div className="border border-[#b91c1c]/40 bg-white p-4 text-xs leading-relaxed">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#b91c1c] mb-2">
            Rotation halted — decide how to continue
          </div>
          <p className="text-black/65 mb-3">
            {batch.current_secret
              ? `The rotation for ${batch.current_secret} halted.`
              : 'A rotation in the batch halted.'}{' '}
            {batch.queue.length - batch.position - 1} secret{batch.queue.length - batch.position - 1 === 1 ? '' : 's'} remain in the queue.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onContinue}
              className="inline-flex items-center gap-2 px-3 py-2 font-mono text-[10px] uppercase tracking-widest border border-black bg-black text-white hover:bg-[#222] transition-colors"
            >
              <Play className="w-3 h-3" strokeWidth={1.5} />
              Continue with remaining
            </button>
            <button
              type="button"
              onClick={onStop}
              className="inline-flex items-center gap-2 px-3 py-2 font-mono text-[10px] uppercase tracking-widest border border-[#b91c1c]/40 text-[#b91c1c] hover:border-[#b91c1c] transition-colors"
            >
              <Square className="w-3 h-3" strokeWidth={1.5} />
              Stop batch
            </button>
          </div>
        </div>
      )}

      {!isHaltedAwaiting && (
        <div className="flex justify-end">
          {stopRequested ? (
            <button
              type="button"
              onClick={() => { void onCancelStop(); }}
              className="inline-flex items-center gap-2 px-3 py-2 font-mono text-[10px] uppercase tracking-widest border border-[#7d4d10]/40 text-[#7d4d10] hover:border-[#7d4d10] transition-colors"
            >
              <Play className="w-3 h-3" strokeWidth={1.5} />
              Cancel stop — keep rotating
            </button>
          ) : (
            <button
              type="button"
              onClick={() => { void onRequestStop(); }}
              className="inline-flex items-center gap-2 px-3 py-2 font-mono text-[10px] uppercase tracking-widest border border-black/10 text-black/60 hover:border-black/40 transition-colors"
            >
              <Pause className="w-3 h-3" strokeWidth={1.5} />
              Stop after current
            </button>
          )}
        </div>
      )}

      {pollError && (
        <div className="border border-[#b91c1c]/40 bg-white p-3 text-xs text-[#7f1d1d]">
          {pollError}
        </div>
      )}
    </div>
  );
}

function DoneStep({
  batch,
  receiptText,
  receiptCopied,
  onCopy,
}: {
  batch: BatchJobSnapshot;
  receiptText: string | null;
  receiptCopied: boolean;
  onCopy: () => void;
}) {
  const hasHalts = batch.halted.length > 0;
  const statusLabel = batch.status === 'stopped'
    ? 'Batch stopped by operator'
    : hasHalts
      ? 'Batch completed with errors'
      : 'Batch completed';

  return (
    <div className="grid gap-4">
      <div
        className={`border p-3 text-xs leading-relaxed ${
          hasHalts || batch.status === 'stopped'
            ? 'border-[#b91c1c]/40 bg-white text-[#7f1d1d]'
            : 'border-black/10 bg-[#fbfbfb] text-black/65'
        }`}
      >
        <div className="font-mono text-[10px] uppercase tracking-widest mb-1">
          {statusLabel}
        </div>
        <div className="grid grid-cols-3 gap-2 mt-2">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-widest text-black/40">Completed</span>
            <div className="text-lg font-light text-black">{batch.completed.length}</div>
          </div>
          <div>
            <span className="font-mono text-[10px] uppercase tracking-widest text-black/40">Halted</span>
            <div className={`text-lg font-light ${hasHalts ? 'text-[#b91c1c]' : 'text-black'}`}>{batch.halted.length}</div>
          </div>
          <div>
            <span className="font-mono text-[10px] uppercase tracking-widest text-black/40">Skipped</span>
            <div className="text-lg font-light text-black">
              {batch.total - batch.completed.length - batch.halted.length}
            </div>
          </div>
        </div>
        {batch.finished_at && (
          <div className="mt-2 text-black/40 text-[11px]">
            Finished {formatDate(batch.finished_at)}
          </div>
        )}
      </div>

      <div className="border border-black/10 bg-[#fbfbfb] max-h-48 overflow-y-auto">
        {batch.queue.map((secret) => {
          const status = secretSubStatus(secret, batch);
          return (
            <div
              key={secret}
              className={`flex items-center gap-3 px-3 py-2 border-b border-black/5 last:border-b-0 text-xs ${subStatusTone(status)}`}
            >
              <span className="font-mono text-[10px] uppercase tracking-widest w-14">
                {subStatusLabel(status)}
              </span>
              <span className="font-mono">{secret}</span>
            </div>
          );
        })}
      </div>

      {receiptText ? (
        <VerificationReportRenderer markdown={receiptText} />
      ) : batch.batch_receipt ? (
        <div className="border border-black/10 bg-[#fbfbfb] p-3 text-xs text-black/55">
          Loading batch receipt…
        </div>
      ) : null}

      {receiptText && (
        <button
          type="button"
          onClick={onCopy}
          className="inline-flex items-center justify-center gap-2 self-start border border-black/10 bg-[#fbfbfb] px-3 py-2 font-mono text-[10px] uppercase tracking-widest hover:border-black/40"
        >
          <Copy className="w-3.5 h-3.5" strokeWidth={1.5} />
          {receiptCopied ? 'Copied' : 'Copy receipt'}
        </button>
      )}
    </div>
  );
}
