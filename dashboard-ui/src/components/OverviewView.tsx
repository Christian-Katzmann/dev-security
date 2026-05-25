import {AlertCircle, CheckCircle2, ClipboardList, FolderGit2, ShieldAlert} from 'lucide-react';
import { motion } from 'motion/react';
import {
  DashboardSummary,
  actionBucketCounts,
  attentionBucketLabels,
  attentionBuckets,
  caseNeedsAttention,
  displayCases,
  formatDate,
  honeyKeyById,
  latestOpenHoneyKeyEvent,
  latestScanTime,
  scanCompleteness,
} from '../dashboardData';
import CaseCard from './CaseCard';
import ScanCompletenessPanel from './ScanCompletenessPanel';
import SinceLastScanPanel from './SinceLastScanPanel';

type OverviewViewProps = {
  summary: DashboardSummary;
  error: string | null;
  targetLabel: string;
};

export default function OverviewView({summary, error, targetLabel}: OverviewViewProps) {
  const cases = displayCases(summary);
  const activeCases = cases.filter(caseNeedsAttention);
  const counts = actionBucketCounts(summary);
  const completeness = scanCompleteness(summary);
  const hasScan = summary.repos.length > 0;
  const lastScan = latestScanTime(summary);
  const firstCase = activeCases[0];
  const topCases = activeCases.slice(0, 3);
  const honeyEvent = latestOpenHoneyKeyEvent(summary);
  const honeyKey = honeyEvent ? honeyKeyById(summary, honeyEvent.honey_key_id) : undefined;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className="p-6 md:p-12 flex flex-col gap-8 max-w-[1400px] w-full"
    >
      <section className="border border-black/10 bg-white/70 p-6 md:p-8 shadow-[0_18px_60px_rgba(0,0,0,0.06)] relative overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-1 bg-[#111111]" />
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-8">
          <div className="min-w-0">
            <div className="mb-4 flex flex-wrap items-center gap-3 font-mono text-[10px] uppercase tracking-widest text-black/40">
              <span>{targetLabel}</span>
              <span className="text-black/20">/</span>
              <span>Latest scan: {formatDate(lastScan)}</span>
              {error && (
                <>
                  <span className="text-black/20">/</span>
                  <span>Dashboard offline</span>
                </>
              )}
            </div>

            <h2 className="text-3xl md:text-5xl font-light tracking-tight text-black leading-tight break-words">
              {firstCase ? `${attentionBucketLabels[firstCase.bucket]}: ${firstCase.title}` : hasScan ? 'No saved issues from the checks that ran.' : 'Run a check to see cases.'}
            </h2>

            <p className="mt-4 max-w-3xl text-sm md:text-base leading-relaxed text-black/60">
              {firstCase
                ? firstCase.why
                : hasScan
                  ? 'This is a good sign, but it does not prove the repo is safe. Start by reviewing what the scan covered.'
                  : 'Choose a repo and run a quick safety sweep. The dashboard will turn raw scanner output into cases and plain next actions.'}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 content-start">
            {attentionBuckets.map((bucket) => (
              <div key={bucket} className="border border-black/10 bg-[#fbfbfb] p-4 shadow-[inset_0_2px_0_rgba(17,17,17,0.88)]">
                <div className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-2">
                  {attentionBucketLabels[bucket]}
                </div>
                <div className="text-3xl font-light text-black">{counts[bucket]}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {hasScan && <SinceLastScanPanel summary={summary} />}

      {honeyEvent && (
        <section className="border border-[#b91c1c] bg-white p-6 md:p-7 shadow-[inset_4px_0_0_#b91c1c]">
          <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-6">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-[#b91c1c] mb-3">
                <ShieldAlert className="w-4 h-4" strokeWidth={1.7} />
                Severity: Critical
              </div>
              <h3 className="text-2xl font-medium text-black">Honey Key triggered</h3>
              <p className="mt-3 text-sm leading-relaxed text-black/60">
                A decoy secret was touched. Treat this as possible unauthorized access to a sensitive location in the codebase.
              </p>
            </div>
            <dl className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 text-sm min-w-0 xl:max-w-[760px]">
              <div className="border border-black/10 bg-[#fbfbfb] p-3">
                <dt className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-1">Key</dt>
                <dd className="break-words">{honeyKey?.name ?? honeyEvent.honey_key_id}</dd>
              </div>
              <div className="border border-black/10 bg-[#fbfbfb] p-3">
                <dt className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-1">Last triggered</dt>
                <dd>{formatDate(honeyEvent.triggered_at)}</dd>
              </div>
              <div className="border border-black/10 bg-[#fbfbfb] p-3">
                <dt className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-1">Trigger count</dt>
                <dd>{honeyKey?.trigger_count ?? 1}</dd>
              </div>
              <div className="border border-black/10 bg-[#fbfbfb] p-3">
                <dt className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-1">Source IP</dt>
                <dd className="break-words">{honeyEvent.ip_address ?? 'Unknown'}</dd>
              </div>
              <div className="border border-black/10 bg-[#fbfbfb] p-3 sm:col-span-2">
                <dt className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-1">User-agent</dt>
                <dd className="break-words">{honeyEvent.user_agent ?? 'Unknown'}</dd>
              </div>
            </dl>
          </div>
        </section>
      )}

      <section className="grid grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)] gap-6">
        <div className="border border-black/10 bg-[#fbfbfb]/85 p-5 md:p-6 h-fit shadow-[inset_3px_0_0_#111111]">
          <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-widest text-black/40 mb-4">
            <ClipboardList className="w-3.5 h-3.5" strokeWidth={1.5} />
            Best next action
          </div>
          {firstCase ? (
            <>
              <h3 className="text-xl font-medium text-black break-words">{firstCase.nextStep}</h3>
              <p className="mt-4 text-sm leading-relaxed text-black/55">
                Give this to an AI agent with the prompt link on the case card, then run the check again.
              </p>
            </>
          ) : hasScan ? (
            <>
              <div className="flex gap-3">
                <CheckCircle2 className="w-5 h-5 text-graph-gold shrink-0" strokeWidth={1.5} />
                <div>
                  <h3 className="text-xl font-medium text-black">Review scan coverage.</h3>
                  <p className="mt-3 text-sm leading-relaxed text-black/55">
                    The checks that ran did not find saved issues. Make sure the skipped checks are acceptable.
                  </p>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="flex gap-3">
                <FolderGit2 className="w-5 h-5 text-black/55 shrink-0" strokeWidth={1.5} />
                <div>
                  <h3 className="text-xl font-medium text-black">Run a repo check.</h3>
                  <p className="mt-3 text-sm leading-relaxed text-black/55">
                    Start with the quick sweep unless you are preparing to trust or ship the repo.
                  </p>
                </div>
              </div>
            </>
          )}
          {error && (
            <div className="mt-5 flex gap-3 border border-black/10 bg-white/70 p-3 text-sm text-black/60">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" strokeWidth={1.5} />
              <span>The dashboard could not refresh. Saved data may be older than shown.</span>
            </div>
          )}
        </div>

        <div className="min-w-0">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xl font-medium text-black">Top cases</h3>
            <span className="font-mono text-[10px] uppercase tracking-widest text-black/35">
              {activeCases.length} active
            </span>
          </div>

          {topCases.length ? (
            <div className="flex flex-col gap-3">
              {topCases.map((item) => (
                <CaseCard key={item.id} item={item} compact />
              ))}
            </div>
          ) : (
            <div className="border border-black/10 bg-white/55 p-6 text-sm leading-relaxed text-black/60">
              {hasScan
                ? 'The checks that ran did not find saved issues. This is not a guarantee of safety.'
                : 'No scan has run for this target yet.'}
            </div>
          )}
        </div>
      </section>

      <ScanCompletenessPanel completeness={completeness} summary={summary} hasScan={hasScan} />
    </motion.div>
  );
}
