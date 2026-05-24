import {CheckCircle2, ChevronDown, CircleX, EyeOff, FileText, Gauge, KeyRound, RotateCcw, ShieldCheck, Sparkles, Wrench} from 'lucide-react';
import {
  AttentionBucket,
  CaseDecisionStatus,
  DisplayCase,
  attentionBucketLabels,
  caseChangeLabels,
  caseDecisionLabels,
  categoryLabel,
  reportViewUrl,
  severityLabel,
} from '../dashboardData';

type CaseCardProps = {
  item: DisplayCase;
  compact?: boolean;
  onDecision?: (item: DisplayCase, status: CaseDecisionStatus | 'open', note: string) => Promise<void> | void;
  /**
   * When the case's repo has rotation scaffolded AND the backend inferred a
   * tracked env-var name, the parent can wire `onRotate` to open the Tier 5R
   * rotation modal. The button only renders when both are true.
   */
  rotationScaffolded?: boolean;
  onRotate?: (item: DisplayCase) => void;
};

const bucketStyles: Record<AttentionBucket, string> = {
  'fix-now': 'border-black bg-white text-black shadow-[inset_3px_0_0_#cca43b]',
  verify: 'border-black/20 bg-white/75 text-black',
  watch: 'border-black/10 bg-white/60 text-black/70',
  info: 'border-black/10 bg-white/50 text-black/55',
};

function actionUrl(item: DisplayCase, kind: 'raw' | 'prompt'): string | undefined {
  if (kind === 'raw' && item.rawReportUrl) return item.rawReportUrl;
  if (kind === 'prompt' && item.aiPromptUrl) return item.aiPromptUrl;
  return item.scanId ? reportViewUrl(item.scanId, kind) : undefined;
}

const decisionActions: {status: CaseDecisionStatus; label: string; icon: typeof CheckCircle2}[] = [
  {status: 'verified', label: 'Verify', icon: CheckCircle2},
  {status: 'false_positive', label: 'False positive', icon: CircleX},
  {status: 'accepted_risk', label: 'Accept risk', icon: ShieldCheck},
  {status: 'fixed', label: 'Mark fixed', icon: Wrench},
];

function readableStatus(value?: string | null): string {
  if (!value) return 'Recorded';
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function suppressionDate(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

export default function CaseCard({
  item,
  compact = false,
  onDecision,
  rotationScaffolded = false,
  onRotate,
}: CaseCardProps) {
  const rawUrl = actionUrl(item, 'raw');
  const promptUrl = actionUrl(item, 'prompt');
  const suppressedAt = suppressionDate(item.suppression?.updated_at);
  const shouldRotate = item.installRecency?.confidence === 'strong' && Boolean(item.rotationSurfaces?.length);
  const canRotateSecret = Boolean(
    item.category === 'secrets' &&
    rotationScaffolded &&
    item.inferredSecretName &&
    onRotate,
  );

  async function saveDecision(status: CaseDecisionStatus | 'open') {
    if (!onDecision) return;
    const note = status === 'open'
      ? ''
      : window.prompt('Optional note for this decision', item.decision?.note ?? '');
    if (note === null) return;
    await onDecision(item, status, note);
  }

  return (
    <article className={`border transition-colors hover:bg-white ${bucketStyles[item.bucket]}`}>
      <div className={compact ? 'p-4 md:p-5' : 'p-5 md:p-6'}>
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-5">
          <div className="min-w-0 max-w-3xl">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <span className="font-mono text-[9px] uppercase tracking-widest border border-black/15 bg-[#fbfbfb] px-2 py-1 text-black">
                {attentionBucketLabels[item.bucket]}
              </span>
              {item.severity && (
                <span className="font-mono text-[9px] uppercase tracking-widest text-black/45">
                  {severityLabel(item.severity)}
                </span>
              )}
              {item.category && (
                <span className="font-mono text-[9px] uppercase tracking-widest text-black/35">
                  {categoryLabel(item.category)}
                </span>
              )}
              {item.decision && (
                <span className="font-mono text-[9px] uppercase tracking-widest border border-black/15 bg-white px-2 py-1 text-black">
                  {caseDecisionLabels[item.decision.status]}
                </span>
              )}
              {item.suppressed && (
                <span className="inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-widest border border-black/15 bg-white px-2 py-1 text-black/55">
                  <EyeOff className="w-3 h-3" strokeWidth={1.5} />
                  Suppressed
                </span>
              )}
              {item.suppression?.vex_status && (
                <span className="font-mono text-[9px] uppercase tracking-widest text-black/35">
                  VEX {readableStatus(String(item.suppression.vex_status))}
                </span>
              )}
              {item.changeStatus && (
                <span className={`font-mono text-[9px] uppercase tracking-widest border px-2 py-1 ${
                  item.changeStatus === 'new'
                    ? 'border-graph-gold text-black bg-white'
                    : item.changeStatus === 'resolved'
                      ? 'border-black/10 text-black/45 bg-white/60'
                      : 'border-black/10 text-black/35 bg-[#fbfbfb]'
                }`}>
                  {caseChangeLabels[item.changeStatus]}
                </span>
              )}
            </div>

            <h3 className={`${compact ? 'text-base' : 'text-lg md:text-xl'} font-medium leading-snug text-black break-words`}>
              {item.title}
            </h3>

            <p className="mt-3 text-sm leading-relaxed text-black/65 break-words">
              {item.why}
            </p>

            {shouldRotate && (
              <div className="mt-4 border border-graph-gold bg-[#fffaf0] p-3">
                <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-widest text-black mb-2">
                  <KeyRound className="w-3.5 h-3.5" strokeWidth={1.5} />
                  Rotate the following surfaces
                </div>
                <ul className="space-y-1">
                  {item.rotationSurfaces?.map((surface) => (
                    <li key={surface} className="text-xs leading-relaxed text-black/70 break-all">
                      {surface}
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs leading-relaxed text-black/55">
                  Rotate at the provider first, update local config last, and never commit rotated values.
                </p>
              </div>
            )}

            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="min-w-0 border border-black/10 bg-[#fbfbfb] p-3">
                <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-widest text-black/35 mb-1">
                  <FileText className="w-3 h-3" strokeWidth={1.5} />
                  Affected place
                </div>
                <p className="text-xs text-black/65 break-all">{item.location}</p>
              </div>
              <div className="border border-black/10 bg-[#fbfbfb] p-3">
                <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-widest text-black/35 mb-1">
                  <Gauge className="w-3 h-3" strokeWidth={1.5} />
                  Confidence
                </div>
                <p className="text-xs text-black/65 break-words">{item.confidence}</p>
              </div>
            </div>
          </div>

          <div className="lg:w-72 flex flex-col gap-3 shrink-0">
            <div className="border border-black/10 bg-[#fbfbfb] p-4">
              <div className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-2">Next step</div>
              <p className="text-sm leading-relaxed text-black/70 break-words">{item.nextStep}</p>
            </div>

            {item.decision && (
              <div className="border border-black/10 bg-white/60 p-4">
                <div className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-2">
                  Triage decision
                </div>
                <p className="text-sm font-medium text-black">{caseDecisionLabels[item.decision.status]}</p>
                {item.decision.status === 'fixed' && (
                  <p className="mt-2 text-xs leading-relaxed text-black/55">
                    This case is still present in the latest scan, so it needs another look.
                  </p>
                )}
                {item.decision.note && (
                  <p className="mt-2 text-xs leading-relaxed text-black/55 break-words">{item.decision.note}</p>
                )}
              </div>
            )}

            {item.suppression && (
              <div className="border border-black/10 bg-white/60 p-4">
                <div className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-2">
                  Suppression
                </div>
                <div className="flex flex-wrap gap-2 mb-2">
                  <span className="font-mono text-[9px] uppercase tracking-widest border border-black/10 bg-[#fbfbfb] px-2 py-1 text-black/55">
                    {readableStatus(item.suppression.decision_status ?? item.suppression.status)}
                  </span>
                  {item.suppression.vex_status && (
                    <span className="font-mono text-[9px] uppercase tracking-widest border border-black/10 bg-[#fbfbfb] px-2 py-1 text-black/55">
                      {readableStatus(String(item.suppression.vex_status))}
                    </span>
                  )}
                </div>
                <p className="text-xs leading-relaxed text-black/60 break-words">
                  {item.suppression.reason ?? item.suppression.vex_reason ?? item.suppression.vex_justification ?? 'Suppressed by a saved dependency decision.'}
                </p>
                {suppressedAt && (
                  <p className="mt-2 font-mono text-[9px] uppercase tracking-widest text-black/35">
                    Updated {suppressedAt}
                  </p>
                )}
              </div>
            )}

            {item.changeStatus === 'resolved' && (
              <div className="border border-black/10 bg-white/60 p-4">
                <div className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-2">
                  Latest scan
                </div>
                <p className="text-sm leading-relaxed text-black/60">
                  This case was not found in the latest scan{item.resolvedAt ? ` on ${new Date(item.resolvedAt).toLocaleDateString()}` : ''}.
                </p>
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              {promptUrl && (
                <a
                  href={promptUrl}
                  className="inline-flex min-h-9 items-center justify-center gap-2 border border-black bg-black px-3 py-2 text-[10px] font-mono uppercase tracking-widest text-white transition-colors hover:bg-[#222]"
                >
                  <Sparkles className="w-3.5 h-3.5" strokeWidth={1.5} />
                  AI prompt
                </a>
              )}
              {rawUrl && (
                <a
                  href={rawUrl}
                  className="inline-flex min-h-9 items-center justify-center border border-black/10 bg-white/60 px-3 py-2 text-[10px] font-mono uppercase tracking-widest text-black/55 transition-colors hover:border-black/30 hover:text-black"
                >
                  Raw report
                </a>
              )}
              {canRotateSecret && (
                <button
                  type="button"
                  onClick={() => onRotate?.(item)}
                  title={`Open Tier 5R rotation modal for ${item.inferredSecretName}`}
                  className="inline-flex min-h-9 items-center justify-center gap-2 border border-black/30 bg-[#fffaf0] px-3 py-2 text-[10px] font-mono uppercase tracking-widest text-black transition-colors hover:border-black hover:bg-white"
                >
                  <RotateCcw className="w-3.5 h-3.5" strokeWidth={1.5} />
                  Rotate {item.inferredSecretName}
                </button>
              )}
            </div>

            {onDecision && !compact && (
              <div className="flex flex-wrap gap-2 border-t border-black/10 pt-3">
                {decisionActions.map(({status, label, icon: Icon}) => (
                  <button
                    key={status}
                    type="button"
                    onClick={() => void saveDecision(status)}
                    className={`inline-flex min-h-8 items-center justify-center gap-1.5 border px-2.5 py-1.5 text-[9px] font-mono uppercase tracking-widest transition-colors ${
                      item.decision?.status === status
                        ? 'border-black bg-black text-white'
                        : 'border-black/10 bg-white/55 text-black/55 hover:border-black/30 hover:text-black'
                    }`}
                  >
                    <Icon className="w-3 h-3" strokeWidth={1.5} />
                    {label}
                  </button>
                ))}
                {item.decision && (
                  <button
                    type="button"
                    onClick={() => void saveDecision('open')}
                    className="inline-flex min-h-8 items-center justify-center gap-1.5 border border-black/10 bg-white/55 px-2.5 py-1.5 text-[9px] font-mono uppercase tracking-widest text-black/55 transition-colors hover:border-black/30 hover:text-black"
                  >
                    <RotateCcw className="w-3 h-3" strokeWidth={1.5} />
                    Reopen
                  </button>
                )}
              </div>
            )}

            <details className="group">
              <summary className="inline-flex cursor-pointer items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-black/45 transition-colors hover:text-black">
                Source scanners
                <ChevronDown className="w-3 h-3 transition-transform group-open:rotate-180" strokeWidth={1.5} />
              </summary>
              <div className="mt-2 border border-black/10 bg-white/60 p-3 text-xs text-black/55">
                {item.sources.length ? item.sources.join(', ') : 'Not included in this payload.'}
              </div>
            </details>
          </div>
        </div>
      </div>
    </article>
  );
}
