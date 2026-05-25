import {AlertTriangle, Copy, RotateCcw, X} from 'lucide-react';
import type {ReactNode} from 'react';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
  ProjectRepo,
  RotationJob,
  RotationJobPhase,
  RotationSecretRow,
  RotationTriggerOptions,
  formatDate,
  repoKeyFromPath,
  rotationConfirmationPhrase,
} from '../dashboardData';

// Coarse phase order. The progress panel renders this as a vertical track so
// the operator can see where the pipeline is. Mirrors the skill's pipeline
// shape; the panel updates "current" as the server emits phase changes.
const PIPELINE_PHASES: {phase: RotationJobPhase; label: string}[] = [
  {phase: 'health_check', label: 'Pre-rotation health check'},
  {phase: 'preflight', label: 'Preflight checks'},
  {phase: 'acquire', label: 'Acquire new value'},
  {phase: 'stage_canary', label: 'Stage to canary'},
  {phase: 'verify_canary', label: 'Verify canary'},
  {phase: 'stage_prod', label: 'Stage to production'},
  {phase: 'verify_prod', label: 'Verify production'},
  {phase: 'soak', label: 'Soak — watch for auth errors'},
];

const PHASE_INDEX: Record<string, number> = Object.fromEntries(
  PIPELINE_PHASES.map((entry, index) => [entry.phase, index]),
);

function phasePosition(job: RotationJob | null): number {
  if (!job) return -1;
  if (job.phase === 'verified') return PIPELINE_PHASES.length;
  if (job.phase === 'halted') return -1;
  const index = PHASE_INDEX[job.phase];
  return Number.isInteger(index) ? index : -1;
}

function classWarning(secretClass: string | null): string | null {
  // Surface the secret-class consequence the operator needs to know BEFORE
  // confirming. The skill catalog encodes these as `rotation_warning` strings;
  // until we ferry that field across, hard-code the two we know about.
  if (!secretClass) return null;
  if (secretClass.toUpperCase() === 'A') {
    return (
      'Class A: self-generated. Rotating NEXTAUTH_SECRET or AUTH_SECRET invalidates' +
      ' all active user sessions. No provider revoke; the new value goes live.'
    );
  }
  if (secretClass.toUpperCase() === 'B-API' || secretClass.toUpperCase() === 'B') {
    return (
      'Class B-api: provider-issued. The old key stays valid through the 24h grace' +
      ' window so dependents can pick up the new value. Revoke runs automatically.'
    );
  }
  if (secretClass.toUpperCase() === 'B-HUMAN') {
    return (
      'Class B-human: provider-issued, requires you to paste the new value mid-flight.' +
      ' Keep the provider console open before you confirm.'
    );
  }
  return `Class ${secretClass} — review the catalog before confirming.`;
}

export type RotationTriggerFlowProps = {
  repo: ProjectRepo;
  secret: RotationSecretRow;
  onClose: () => void;
  onDone: () => void;
};

type Step = 'confirm' | 'running' | 'done';

export default function RotationTriggerFlow({
  repo,
  secret,
  onClose,
  onDone,
}: RotationTriggerFlowProps) {
  const [step, setStep] = useState<Step>('confirm');
  const [typedPhrase, setTypedPhrase] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [noSoak, setNoSoak] = useState(false);
  const [soakAck, setSoakAck] = useState(false);
  const [job, setJob] = useState<RotationJob | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [receiptText, setReceiptText] = useState<string | null>(null);
  const [receiptCopied, setReceiptCopied] = useState(false);

  const expectedPhrase = useMemo(
    () => rotationConfirmationPhrase(secret.secret),
    [secret.secret],
  );

  const phraseMatches = typedPhrase.trim() === expectedPhrase;
  const optionsValid = !noSoak || soakAck;
  const canSubmit = phraseMatches && optionsValid && step === 'confirm';

  async function submitTrigger() {
    setSubmitError(null);
    const options: RotationTriggerOptions = {};
    if (noSoak) {
      options.no_soak = true;
      options.acknowledged_skipping_soak = true;
    }
    try {
      const response = await fetch(
        `/api/rotation/trigger/${encodeURIComponent(repoKeyFromPath(repo.path))}`,
        {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            secret: secret.secret,
            confirmed: true,
            confirmation_phrase: expectedPhrase,
            options,
          }),
        },
      );
      if (!response.ok) {
        if (response.status === 409) {
          let detail = 'A rotation for this secret is already in progress.';
          try {
            const body = await response.json();
            if (body.job_id) {
              detail += ` (job: ${body.job_id})`;
            } else if (body.error) {
              detail = body.error;
            }
          } catch { /* use default detail */ }
          throw new Error(detail);
        }
        const text = await response.text();
        throw new Error(text || 'Rotation request was refused.');
      }
      const payload = (await response.json()) as {job: RotationJob};
      setJob(payload.job);
      setStep('running');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Unable to trigger rotation.');
    }
  }

  // Poll for job snapshots. Terminal states (complete/halted/failed) stop the
  // poll and trigger the receipt fetch.
  const pollRef = useRef<number | null>(null);
  useEffect(() => {
    if (step !== 'running' || !job) return;
    const id = job.id;
    const tick = async () => {
      try {
        const response = await fetch(`/api/rotation/jobs/${encodeURIComponent(id)}`, {
          cache: 'no-store',
        });
        if (!response.ok) throw new Error(await response.text());
        const payload = (await response.json()) as {job: RotationJob};
        setJob(payload.job);
        if (
          payload.job.status === 'complete' ||
          payload.job.status === 'halted' ||
          payload.job.status === 'failed'
        ) {
          if (pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
          setStep('done');
        }
      } catch (err) {
        setPollError(
          err instanceof Error ? err.message : 'Lost track of the rotation job.',
        );
      }
    };
    void tick();
    pollRef.current = window.setInterval(tick, 1500);
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [job?.id, step]);

  // Fetch the receipt once the job has one.
  useEffect(() => {
    if (step !== 'done' || !job?.receipt_url) {
      setReceiptText(null);
      return;
    }
    let cancelled = false;
    fetch(job.receipt_url, {cache: 'no-store'})
      .then((response) => (response.ok ? response.text() : Promise.reject(response)))
      .then((text) => {
        if (!cancelled) setReceiptText(text);
      })
      .catch(() => {
        if (!cancelled) setReceiptText(null);
      });
    return () => {
      cancelled = true;
    };
  }, [job?.receipt_url, step]);

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
    } catch {
      // Clipboard access can be denied silently in some embeds; the user can
      // still select the text. Don't fail the modal over a copy gesture.
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Rotate ${secret.secret}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="bg-white border border-black/10 w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-[0_24px_80px_rgba(0,0,0,0.18)]">
        <header className="flex items-start justify-between gap-3 border-b border-black/10 px-5 py-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-black/40 flex items-center gap-2">
              <RotateCcw className="w-3.5 h-3.5" strokeWidth={1.5} />
              Rotation · Tier 5R
            </div>
            <h2 className="mt-1 text-lg font-medium text-black">
              Rotate{' '}
              <span className="font-mono">{secret.secret}</span>
            </h2>
            <p className="mt-1 text-xs text-black/45">
              {repo.name} · {repo.path}
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
          {step === 'confirm' && (
            <ConfirmStep
              secret={secret}
              expectedPhrase={expectedPhrase}
              typedPhrase={typedPhrase}
              onTypedPhrase={setTypedPhrase}
              noSoak={noSoak}
              onNoSoak={setNoSoak}
              soakAck={soakAck}
              onSoakAck={setSoakAck}
              submitError={submitError}
            />
          )}
          {step === 'running' && job && (
            <RunningStep job={job} pollError={pollError} />
          )}
          {step === 'done' && job && (
            <DoneStep
              job={job}
              receiptText={receiptText}
              receiptCopied={receiptCopied}
              onCopy={copyReceipt}
            />
          )}
        </div>

        <footer className="flex flex-col-reverse md:flex-row md:items-center md:justify-end gap-2 border-t border-black/10 px-5 py-4">
          {step === 'confirm' && (
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
                disabled={!canSubmit}
                onClick={() => {
                  void submitTrigger();
                }}
                className="px-4 py-2 font-mono text-[10px] uppercase tracking-widest border border-black bg-black text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#222] transition-colors"
              >
                Rotate now
              </button>
            </>
          )}
          {step === 'running' && (
            <span className="font-mono text-[10px] uppercase tracking-widest text-black/40">
              Cancellation isn't supported in v1. The pipeline is safe to abandon.
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

function ConfirmStep({
  secret,
  expectedPhrase,
  typedPhrase,
  onTypedPhrase,
  noSoak,
  onNoSoak,
  soakAck,
  onSoakAck,
  submitError,
}: {
  secret: RotationSecretRow;
  expectedPhrase: string;
  typedPhrase: string;
  onTypedPhrase: (value: string) => void;
  noSoak: boolean;
  onNoSoak: (value: boolean) => void;
  soakAck: boolean;
  onSoakAck: (value: boolean) => void;
  submitError: string | null;
}) {
  const warning = classWarning(secret.class);
  return (
    <div className="grid gap-4">
      <div>
        <h3 className="text-sm font-medium text-black mb-2">
          What rotation will do
        </h3>
        <ol className="list-decimal pl-5 text-sm text-black/65 leading-relaxed grid gap-1.5">
          <li>Run a pre-rotation health check to refuse rotating into a dirty baseline.</li>
          <li>Acquire a new value (provider call for Class B-api; local generation for Class A).</li>
          <li>Stage to preview, verify with provider and application probes.</li>
          <li>Stage to production, verify again.</li>
          <li>Soak for 15 minutes, watching auth-related errors above baseline.</li>
          <li>Hold the old value through the 24h grace window before revoking automatically.</li>
        </ol>
      </div>

      {warning && (
        <div className="border border-[#7d4d10]/30 bg-[#fbfbfb] p-3 text-xs leading-relaxed text-[#7d4d10] flex gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-none" strokeWidth={1.5} />
          <span>{warning}</span>
        </div>
      )}

      {secret.manually_marked && (
        <div className="border border-[#7d4d10]/30 bg-[#fbfbfb] p-3 text-xs leading-relaxed text-[#7d4d10] flex gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-none" strokeWidth={1.5} />
          <span>
            Previous rotation was completed via operator override
            {secret.override_kind ? (
              <> (<span className="font-mono">{secret.override_kind}</span>)</>
            ) : null}.
            The new rotation will run the full pipeline.
          </span>
        </div>
      )}

      <div className="border border-black/10 bg-[#fbfbfb] p-3 text-xs text-black/55 leading-relaxed">
        <div className="font-mono text-[9px] uppercase tracking-widest text-black/40 mb-1">
          Verification will mean
        </div>
        Provider check returns ok · application probe returns ok · soak window
        shows no new auth-related errors above baseline.
      </div>

      <div>
        <label className="block text-sm text-black/70 mb-1">
          Type the confirmation phrase to enable rotation:
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

      <div className="border border-black/10 bg-[#fbfbfb] p-3 text-xs text-black/55">
        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={noSoak}
            onChange={(event) => onNoSoak(event.target.checked)}
            className="mt-0.5"
          />
          <span>
            <span className="font-mono text-black">--no-soak</span> — skip the
            post-rotation soak gate. Reaches ROTATED without verifying under real
            traffic. Only safe when an independent verification path covers the
            secret.
          </span>
        </label>
        {noSoak && (
          <label className="mt-2 flex items-start gap-2 cursor-pointer text-[#7f1d1d]">
            <input
              type="checkbox"
              checked={soakAck}
              onChange={(event) => onSoakAck(event.target.checked)}
              className="mt-0.5"
            />
            <span>
              I understand skipping soak removes the verification gate; the
              receipt will surface this loud override.
            </span>
          </label>
        )}
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
  job,
  pollError,
}: {
  job: RotationJob;
  pollError: string | null;
}) {
  const position = phasePosition(job);
  return (
    <div className="grid gap-4">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-2">
          Pipeline · {job.phase}
        </div>
        <ol className="grid gap-1.5">
          {PIPELINE_PHASES.map((entry, index) => {
            const state =
              job.phase === 'halted'
                ? index < position
                  ? 'done'
                  : 'halted'
                : index < position
                  ? 'done'
                  : index === position
                    ? 'current'
                    : 'pending';
            return (
              <li
                key={entry.phase}
                className={`grid grid-cols-[120px_1fr] gap-3 text-xs items-baseline ${
                  state === 'current'
                    ? 'text-black'
                    : state === 'done'
                      ? 'text-black/55'
                      : state === 'halted'
                        ? 'text-[#7f1d1d]'
                        : 'text-black/30'
                }`}
              >
                <span className="font-mono uppercase tracking-widest text-[10px]">
                  {state === 'done'
                    ? 'Done'
                    : state === 'current'
                      ? 'Now'
                      : state === 'halted'
                        ? 'Halted'
                        : 'Pending'}
                </span>
                <span>{entry.label}</span>
              </li>
            );
          })}
        </ol>
      </div>

      <div className="border border-black/10 bg-[#fbfbfb] p-3 text-xs text-black/65 leading-relaxed">
        {job.message}
      </div>

      {pollError && (
        <div className="border border-[#b91c1c]/40 bg-white p-3 text-xs text-[#7f1d1d]">
          {pollError}
        </div>
      )}

      <details>
        <summary className="font-mono text-[10px] uppercase tracking-widest text-black/40 cursor-pointer">
          stdout tail ({job.stdout_tail.length} lines)
        </summary>
        <pre className="mt-2 text-[11px] bg-black text-white p-3 overflow-x-auto font-mono whitespace-pre-wrap leading-relaxed">
          {job.stdout_tail.slice(-30).join('\n') || '(no output yet)'}
        </pre>
      </details>
    </div>
  );
}

function DoneStep({
  job,
  receiptText,
  receiptCopied,
  onCopy,
}: {
  job: RotationJob;
  receiptText: string | null;
  receiptCopied: boolean;
  onCopy: () => void;
}) {
  const halted = job.phase === 'halted' || job.status === 'halted' || job.status === 'failed';
  return (
    <div className="grid gap-4">
      <div
        className={`border p-3 text-xs leading-relaxed ${
          halted
            ? 'border-[#b91c1c]/40 bg-white text-[#7f1d1d]'
            : 'border-black/10 bg-[#fbfbfb] text-black/65'
        }`}
      >
        <div className="font-mono text-[10px] uppercase tracking-widest mb-1">
          {halted ? 'Rotation halted' : 'Rotation verified'} · phase {job.phase}
        </div>
        {job.message}
        {job.finished_at && (
          <div className="mt-1 text-black/40">
            Finished {formatDate(job.finished_at)}
          </div>
        )}
      </div>

      {receiptText ? (
        <VerificationReportRenderer markdown={receiptText} />
      ) : job.receipt_url ? (
        <div className="border border-black/10 bg-[#fbfbfb] p-3 text-xs text-black/55">
          Loading verification receipt…
        </div>
      ) : (
        <div className="border border-[#7d4d10]/30 bg-white p-3 text-xs text-[#7d4d10] leading-relaxed">
          No verification receipt was written. The rotation may have halted
          before the receipt step. Re-read state with `npm run rotate --status`
          and inspect{' '}
          <span className="font-mono">data/rotation-log.jsonl</span>.
        </div>
      )}

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

/**
 * Renders a Security-Brief-shaped rotation receipt as styled HTML.
 *
 * The receipt is markdown the skill writes to
 * data/rotation-receipts/<secret>-<timestamp>.md. We don't pull in a markdown
 * dependency for this; the receipt has a tight, well-known shape — H1, a list
 * of bold-labelled bullets, and one or two scope paragraphs at the end. The
 * lightweight renderer respects that shape and leaves anything unrecognised as
 * plain text so receipts always render legibly.
 */
export function VerificationReportRenderer({markdown}: {markdown: string}) {
  const blocks = useMemo(() => renderMarkdownBlocks(markdown), [markdown]);
  return (
    <article className="border border-black/10 bg-white p-4 text-sm text-black/75 leading-relaxed grid gap-2.5">
      {blocks}
    </article>
  );
}

function renderInlineMarkdown(text: string): ReactNode[] {
  // Handles **bold** and `code` spans. Anything else passes through as text.
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let key = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > lastIndex) {
      nodes.push(<span key={key++}>{text.slice(lastIndex, start)}</span>);
    }
    const token = match[0];
    if (token.startsWith('**')) {
      nodes.push(
        <strong key={key++} className="text-black font-medium">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith('`')) {
      nodes.push(
        <code key={key++} className="font-mono text-black">
          {token.slice(1, -1)}
        </code>,
      );
    }
    lastIndex = start + token.length;
  }
  if (lastIndex < text.length) {
    nodes.push(<span key={key++}>{text.slice(lastIndex)}</span>);
  }
  return nodes;
}

function renderMarkdownBlocks(markdown: string): ReactNode[] {
  const lines = markdown.split('\n');
  const blocks: ReactNode[] = [];
  let listBuffer: string[] = [];
  let paragraphBuffer: string[] = [];
  let key = 0;

  const flushList = () => {
    if (!listBuffer.length) return;
    blocks.push(
      <ul key={`ul-${key++}`} className="grid gap-1.5 list-disc pl-5">
        {listBuffer.map((item, index) => (
          <li key={index}>{renderInlineMarkdown(item)}</li>
        ))}
      </ul>,
    );
    listBuffer = [];
  };

  const flushParagraph = () => {
    if (!paragraphBuffer.length) return;
    blocks.push(
      <p key={`p-${key++}`} className="text-black/70">
        {renderInlineMarkdown(paragraphBuffer.join(' '))}
      </p>,
    );
    paragraphBuffer = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (line.startsWith('# ')) {
      flushList();
      flushParagraph();
      blocks.push(
        <h3
          key={`h-${key++}`}
          className="text-base font-medium text-black border-b border-black/10 pb-2"
        >
          {renderInlineMarkdown(line.slice(2))}
        </h3>,
      );
      continue;
    }
    if (line.startsWith('- ')) {
      flushParagraph();
      listBuffer.push(line.slice(2));
      continue;
    }
    if (line.trim() === '') {
      flushList();
      flushParagraph();
      continue;
    }
    flushList();
    paragraphBuffer.push(line);
  }
  flushList();
  flushParagraph();
  return blocks;
}
