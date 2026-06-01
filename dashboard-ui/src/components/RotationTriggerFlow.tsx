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
import Dialog from './Dialog';

type PipelinePhase = {
  phase: RotationJobPhase;
  label: string;
  matches?: string[];
};

// Coarse phase order. The progress panel renders a class-aware track so Class A
// rotations do not look like they skipped Class B provider stages.
const CLASS_B_API_PHASES: PipelinePhase[] = [
  {phase: 'health_check', label: 'Pre-rotation health check'},
  {phase: 'preflight', label: 'Preflight checks'},
  {phase: 'acquire', label: 'Acquire new value'},
  {phase: 'stage_canary', label: 'Stage to canary'},
  {phase: 'verify_canary', label: 'Verify canary'},
  {phase: 'stage_prod', label: 'Stage to production'},
  {phase: 'verify_prod', label: 'Verify production'},
  {phase: 'soak', label: 'Soak — watch for auth errors'},
];

const CLASS_A_PHASES: PipelinePhase[] = [
  {phase: 'health_check', label: 'Pre-rotation health check'},
  {phase: 'preflight', label: 'Preflight checks'},
  {
    phase: 'acquire',
    label: 'Acquire and stage new value',
    matches: ['acquire', 'stage_canary', 'stage_prod'],
  },
  {
    phase: 'verify_prod',
    label: 'Deploy and verify',
    matches: ['verify_canary', 'verify_prod', 'soak', 'grace', 'revoke'],
  },
];

const CLASS_B_HUMAN_PHASES: PipelinePhase[] = [
  ...CLASS_B_API_PHASES.slice(0, 3),
  {
    phase: 'waiting_for_paste',
    label: 'Paste value from provider console',
  },
  ...CLASS_B_API_PHASES.slice(3),
];

function normalisedSecretClass(secret: RotationSecretRow): string {
  return (secret.class ?? '').trim().toUpperCase();
}

function pipelinePhasesForSecret(secret: RotationSecretRow): PipelinePhase[] {
  const secretClass = normalisedSecretClass(secret);
  if (secretClass === 'A') return CLASS_A_PHASES;
  if (secretClass === 'B-HUMAN') return CLASS_B_HUMAN_PHASES;
  return CLASS_B_API_PHASES;
}

function phaseMatches(entry: PipelinePhase, phase: string): boolean {
  return entry.phase === phase || Boolean(entry.matches?.includes(phase));
}

function phasePosition(job: RotationJob | null, phases: PipelinePhase[]): number {
  if (!job) return -1;
  if (job.phase === 'verified') return phases.length;
  if (job.phase === 'halted') return -1;
  const index = phases.findIndex((entry) => phaseMatches(entry, String(job.phase)));
  return Number.isInteger(index) ? index : -1;
}

function classWarning(secret: RotationSecretRow): string | null {
  const catalogWarning = secret.rotation_warning?.trim();
  if (catalogWarning) return catalogWarning;
  // Surface the secret-class consequence the operator needs to know BEFORE
  // confirming. Prefer the per-secret catalog copy above; fall back to the
  // class-level contract when a repo has no explicit warning.
  const secretClass = secret.class;
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

function normalisedSoakMinutes(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed)) return null;
  return Math.min(60, Math.max(10, parsed));
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
  const [testMode, setTestMode] = useState(false);
  const [noSoak, setNoSoak] = useState(false);
  const [soakAck, setSoakAck] = useState(false);
  const [skipHealthCheck, setSkipHealthCheck] = useState(false);
  const [healthCheckAck, setHealthCheckAck] = useState(false);
  const [soakMinutes, setSoakMinutes] = useState('');
  const [emergencyMode, setEmergencyMode] = useState(false);
  const [emergencyAck, setEmergencyAck] = useState(false);
  const [job, setJob] = useState<RotationJob | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [receiptText, setReceiptText] = useState<string | null>(null);
  const [receiptCopied, setReceiptCopied] = useState(false);

  const expectedPhrase = useMemo(
    () => rotationConfirmationPhrase(secret.secret, {emergencyMode}),
    [secret.secret, emergencyMode],
  );

  const phraseMatches = typedPhrase.trim() === expectedPhrase;
  const soakMinutesTrimmed = soakMinutes.trim();
  const soakMinutesNumber = Number(soakMinutesTrimmed);
  const soakMinutesValid =
    !soakMinutesTrimmed ||
    (Number.isInteger(soakMinutesNumber) && soakMinutesNumber >= 10 && soakMinutesNumber <= 60);
  const optionsValid =
    (!noSoak || soakAck) &&
    (!skipHealthCheck || healthCheckAck) &&
    (!emergencyMode || emergencyAck) &&
    (noSoak || soakMinutesValid);
  const canSubmit = phraseMatches && optionsValid && step === 'confirm';

  async function submitTrigger() {
    setSubmitError(null);
    const options: RotationTriggerOptions = {};
    if (testMode) {
      options.test_mode = true;
    }
    if (noSoak) {
      options.no_soak = true;
      options.acknowledged_skipping_soak = true;
    }
    if (skipHealthCheck) {
      options.skip_health_check = true;
      options.acknowledged_skipping_health_check = true;
    }
    if (emergencyMode) {
      options.emergency_mode = true;
      options.acknowledged_cached_caller_risk = true;
    }
    const parsedSoakMinutes = normalisedSoakMinutes(soakMinutes);
    if (parsedSoakMinutes !== null && !noSoak) {
      options.soak_minutes = parsedSoakMinutes;
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
              const jobResponse = await fetch(
                `/api/rotation/jobs/${encodeURIComponent(String(body.job_id))}`,
                {cache: 'no-store'},
              );
              if (jobResponse.ok) {
                const payload = (await jobResponse.json()) as {job: RotationJob};
                setJob(payload.job);
                setStep('running');
                return;
              }
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
    <Dialog
      ariaLabel={`Rotate ${secret.secret}`}
      onClose={close}
      closeOnBackdropClick={false}
      backdropClassName="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      className="bg-white border border-black/10 w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-[0_24px_80px_rgba(0,0,0,0.18)]"
    >
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
            testMode={testMode}
            onTestMode={setTestMode}
            noSoak={noSoak}
            onNoSoak={setNoSoak}
            soakAck={soakAck}
            onSoakAck={setSoakAck}
            skipHealthCheck={skipHealthCheck}
            onSkipHealthCheck={setSkipHealthCheck}
            healthCheckAck={healthCheckAck}
            onHealthCheckAck={setHealthCheckAck}
            soakMinutes={soakMinutes}
            onSoakMinutes={setSoakMinutes}
            emergencyMode={emergencyMode}
            onEmergencyMode={setEmergencyMode}
            emergencyAck={emergencyAck}
            onEmergencyAck={setEmergencyAck}
            submitError={submitError}
          />
        )}
        {step === 'running' && job && (
          <RunningStep secret={secret} job={job} pollError={pollError} />
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
              className={`px-4 py-2 font-mono text-[10px] uppercase tracking-widest border disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${
                emergencyMode
                  ? 'border-[#b91c1c] bg-[#b91c1c] text-white hover:bg-[#991b1b]'
                  : 'border-black bg-black text-white hover:bg-[#222]'
              }`}
            >
              {emergencyMode ? 'Emergency rotate' : 'Rotate now'}
            </button>
          </>
        )}
        {step === 'running' && (
          <span className="text-right text-[11px] leading-relaxed text-black/45">
            Cancellation isn't supported in v1. The pipeline is safe to abandon.
            <br />
            If you must abort:{' '}
            <span className="font-mono text-black/60">
              pkill -f 'npm run rotate -- {secret.secret}'
            </span>
            . Re-clicking Rotate resumes from disk.
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
    </Dialog>
  );
}

function ConfirmStep({
  secret,
  expectedPhrase,
  typedPhrase,
  onTypedPhrase,
  testMode,
  onTestMode,
  noSoak,
  onNoSoak,
  soakAck,
  onSoakAck,
  skipHealthCheck,
  onSkipHealthCheck,
  healthCheckAck,
  onHealthCheckAck,
  soakMinutes,
  onSoakMinutes,
  emergencyMode,
  onEmergencyMode,
  emergencyAck,
  onEmergencyAck,
  submitError,
}: {
  secret: RotationSecretRow;
  expectedPhrase: string;
  typedPhrase: string;
  onTypedPhrase: (value: string) => void;
  testMode: boolean;
  onTestMode: (value: boolean) => void;
  noSoak: boolean;
  onNoSoak: (value: boolean) => void;
  soakAck: boolean;
  onSoakAck: (value: boolean) => void;
  skipHealthCheck: boolean;
  onSkipHealthCheck: (value: boolean) => void;
  healthCheckAck: boolean;
  onHealthCheckAck: (value: boolean) => void;
  soakMinutes: string;
  onSoakMinutes: (value: string) => void;
  emergencyMode: boolean;
  onEmergencyMode: (value: boolean) => void;
  emergencyAck: boolean;
  onEmergencyAck: (value: boolean) => void;
  submitError: string | null;
}) {
  const warning = classWarning(secret);
  const defaultSoakMinutes = secret.soak_window_minutes ?? 15;
  const soakMinutesTrimmed = soakMinutes.trim();
  const soakMinutesNumber = Number(soakMinutesTrimmed);
  const soakMinutesInvalid =
    !noSoak &&
    soakMinutesTrimmed !== '' &&
    (!Number.isInteger(soakMinutesNumber) || soakMinutesNumber < 10 || soakMinutesNumber > 60);
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

      <div className="border border-black/10 bg-[#fbfbfb] p-3 text-xs text-black/60 leading-relaxed">
        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={testMode}
            onChange={(event) => onTestMode(event.target.checked)}
            className="mt-0.5"
          />
          <span>
            <span className="font-mono text-black">Test mode</span>: runs every
            pipeline step without changing the secret value. Recommended for a
            first rotation on a new secret.
          </span>
        </label>
      </div>

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

      <details className="border border-black/10 bg-[#fbfbfb] p-3 text-xs text-black/55">
        <summary className="cursor-pointer font-mono text-[10px] uppercase tracking-widest text-black/45">
          Advanced options
        </summary>
        <div className="mt-3 grid gap-3 leading-relaxed">
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={noSoak}
              onChange={(event) => onNoSoak(event.target.checked)}
              className="mt-0.5"
            />
            <span>
              <span className="font-mono text-black">--no-soak</span>: skip the
              post-rotation soak gate. Only safe when an independent verification
              path covers this secret.
            </span>
          </label>
          {noSoak && (
            <label className="flex items-start gap-2 cursor-pointer text-[#7f1d1d]">
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

          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={skipHealthCheck}
              onChange={(event) => onSkipHealthCheck(event.target.checked)}
              className="mt-0.5"
            />
            <span>
              <span className="font-mono text-black">--skip-health-check</span>:
              bypasses the pre-rotation baseline observation. Recorded loudly in
              the receipt.
            </span>
          </label>
          {skipHealthCheck && (
            <label className="flex items-start gap-2 cursor-pointer text-[#7f1d1d]">
              <input
                type="checkbox"
                checked={healthCheckAck}
                onChange={(event) => onHealthCheckAck(event.target.checked)}
                className="mt-0.5"
              />
              <span>
                I understand this bypasses the baseline observation; the receipt
                will record the override.
              </span>
            </label>
          )}

          <label className="grid gap-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-black/45">
              Soak minutes
            </span>
            <input
              type="number"
              min={10}
              max={60}
              step={1}
              value={soakMinutes}
              disabled={noSoak}
              onChange={(event) => onSoakMinutes(event.target.value)}
              onBlur={() => {
                const clamped = normalisedSoakMinutes(soakMinutes);
                if (clamped !== null) onSoakMinutes(String(clamped));
              }}
              placeholder={`Default: ${defaultSoakMinutes} min`}
              className={`w-36 border bg-white px-3 py-2 font-mono text-xs text-black focus:outline-none disabled:opacity-40 ${
                soakMinutesInvalid ? 'border-[#b91c1c]' : 'border-black/20 focus:border-black'
              }`}
            />
            <span className={soakMinutesInvalid ? 'text-[#7f1d1d]' : 'text-black/45'}>
              {noSoak
                ? 'Disabled while the soak gate is skipped.'
                : 'Override the soak window. Leave empty to use the catalog default; allowed range is 10 to 60 minutes.'}
            </span>
          </label>

          <div className="border-t border-black/10 pt-3 mt-1">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[#b91c1c]/70 mb-2">
              Incident response
            </div>
            <EmergencyModeSection
              secret={secret}
              emergencyMode={emergencyMode}
              onEmergencyMode={onEmergencyMode}
              emergencyAck={emergencyAck}
              onEmergencyAck={onEmergencyAck}
            />
          </div>
        </div>
      </details>

      {submitError && (
        <div className="border border-[#b91c1c]/40 bg-white p-3 text-xs text-[#7f1d1d]">
          {submitError}
        </div>
      )}
    </div>
  );
}

function EmergencyModeSection({
  secret,
  emergencyMode,
  onEmergencyMode,
  emergencyAck,
  onEmergencyAck,
}: {
  secret: RotationSecretRow;
  emergencyMode: boolean;
  onEmergencyMode: (value: boolean) => void;
  emergencyAck: boolean;
  onEmergencyAck: (value: boolean) => void;
}) {
  const isClassA = normalisedSecretClass(secret) === 'A';
  return (
    <div className="grid gap-3 leading-relaxed">
      <label
        className={`flex items-start gap-2 ${isClassA ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
        title={
          isClassA
            ? 'Class A secrets have no grace window. The old value dies the moment the new one deploys. Use the standard Rotate button.'
            : undefined
        }
      >
        <input
          type="checkbox"
          checked={emergencyMode}
          disabled={isClassA}
          onChange={(event) => {
            onEmergencyMode(event.target.checked);
            if (!event.target.checked) onEmergencyAck(false);
          }}
          className="mt-0.5"
        />
        <span>
          <span className="font-mono text-[#b91c1c]">Emergency mode</span>
          {' '}<span className="text-black/40">(Class B only)</span>
          {' '}&mdash; skip the 24h grace window. The old key dies immediately
          when this rotation completes.
        </span>
      </label>
      {emergencyMode && (
        <>
          <div className="border border-[#b91c1c]/30 bg-white p-3 text-xs leading-relaxed text-[#7f1d1d]">
            <AlertTriangle className="w-4 h-4 mb-1 inline-block mr-1.5 align-text-bottom" strokeWidth={1.5} />
            Use this when you have reason to believe the key is being actively
            used by an attacker. Cached callers (background workers, retry
            queues, webhook handlers) will fail until they pick up the new
            value &mdash; usually within minutes, but they fail loudly. That
            loud failure is itself a diagnostic signal: it tells you which
            surfaces were still using the old credential.
          </div>
          <label className="flex items-start gap-2 cursor-pointer text-[#7f1d1d]">
            <input
              type="checkbox"
              checked={emergencyAck}
              onChange={(event) => onEmergencyAck(event.target.checked)}
              className="mt-0.5"
            />
            <span>
              I understand the old key dies immediately and cached callers will
              fail loudly until they refresh.
            </span>
          </label>
        </>
      )}
    </div>
  );
}

function RunningStep({
  secret,
  job,
  pollError,
}: {
  secret: RotationSecretRow;
  job: RotationJob;
  pollError: string | null;
}) {
  const phases = pipelinePhasesForSecret(secret);
  const position = phasePosition(job, phases);
  return (
    <div className="grid gap-4">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-widest text-black/45 mb-2">
          Pipeline · {job.phase}
        </div>
        <ol className="grid gap-1.5">
          {phases.map((entry, index) => {
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
