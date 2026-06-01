import {CheckCircle2, Search} from 'lucide-react';
import {motion} from 'motion/react';
import {useMemo, useState} from 'react';
import {
  AttentionBucket,
  CaseChangeStatus,
  CaseDecisionStatus,
  DashboardSummary,
  actionBucketCounts,
  attentionBucketLabels,
  attentionBuckets,
  caseChangeCounts,
  caseChangeLabels,
  caseDecisionCounts,
  caseDecisionLabels,
  displayCases,
  formatDate,
  latestRepoScan,
  latestScanTime,
  scanCompleteness,
  suppressedDisplayCases,
} from '../dashboardData';
import CaseCard from './CaseCard';
import ReportDownloads from './ReportDownloads';
import ScanCompletenessPanel from './ScanCompletenessPanel';
import SinceLastScanPanel from './SinceLastScanPanel';

type CasesViewProps = {
  summary: DashboardSummary;
  targetLabel: string;
  onChooseChecks?: () => void;
  onCaseDecision?: (caseId: string, repoName: string, status: CaseDecisionStatus | 'open', note: string) => Promise<void> | void;
};

type BucketFilter = 'all' | AttentionBucket;
type DecisionFilter = 'all' | 'open' | CaseDecisionStatus;
type ChangeFilter = 'all' | CaseChangeStatus;

export default function CasesView({summary, targetLabel, onChooseChecks, onCaseDecision}: CasesViewProps) {
  const [bucketFilter, setBucketFilter] = useState<BucketFilter>('all');
  const [decisionFilter, setDecisionFilter] = useState<DecisionFilter>('all');
  const [changeFilter, setChangeFilter] = useState<ChangeFilter>('all');
  const [query, setQuery] = useState('');
  const [visibleLimit, setVisibleLimit] = useState(24);

  const cases = useMemo(() => displayCases(summary), [summary]);
  const suppressedCases = useMemo(() => suppressedDisplayCases(summary), [summary]);
  const counts = useMemo(() => actionBucketCounts(summary), [summary]);
  const decisionCounts = useMemo(() => caseDecisionCounts(summary), [summary]);
  const changeCounts = useMemo(() => caseChangeCounts(summary), [summary]);
  const completeness = useMemo(() => scanCompleteness(summary), [summary]);
  const suppressionReasons = summary.suppression_reasons ?? summary.suppressed_counts?.reasons ?? [];
  const suppressedFindingCount = summary.suppressed_counts?.findings ?? summary.suppressed_findings?.length ?? 0;
  const hasSuppressed = suppressedCases.length > 0 || suppressedFindingCount > 0;

  const visibleCases = useMemo(() => {
    const cleanQuery = query.toLowerCase().trim();
    return cases.filter((item) => {
      if (bucketFilter !== 'all' && item.bucket !== bucketFilter) return false;
      if (decisionFilter === 'open' && item.decision) return false;
      if (decisionFilter !== 'all' && decisionFilter !== 'open' && item.decision?.status !== decisionFilter) return false;
      if (changeFilter !== 'all' && item.changeStatus !== changeFilter) return false;
      if (!cleanQuery) return true;
      const haystack = `${item.title} ${item.why} ${item.location} ${item.nextStep} ${item.category ?? ''}`.toLowerCase();
      return haystack.includes(cleanQuery);
    });
  }, [bucketFilter, cases, changeFilter, decisionFilter, query]);

  const shownCases = visibleCases.slice(0, visibleLimit);

  const lastScan = latestScanTime(summary);
  const hasScan = summary.repos.length > 0;
  const latestScan = latestRepoScan(summary);

  return (
    <motion.div
      initial={{opacity: 0, y: 10}}
      animate={{opacity: 1, y: 0}}
      exit={{opacity: 0, scale: 0.98}}
      className="p-6 md:p-12 flex flex-col gap-8 max-w-[1400px] w-full"
    >
      <div className="flex flex-col xl:flex-row xl:items-end justify-between gap-6 border-b border-black/10 pb-6">
        <div className="min-w-0">
          <h2 className="text-3xl font-light text-black tracking-tight">Cases</h2>
          <p className="text-sm text-black/55 mt-2 max-w-2xl">
            Active cases for {targetLabel}, grouped by what to do next. Suppressed raw findings are kept separate for audit.
          </p>
          <p className="font-mono text-[10px] tracking-widest uppercase text-black/35 mt-3">
            Latest scan: {formatDate(lastScan)}
          </p>
          {latestScan && summary.repos.length === 1 && (
            <div className="mt-4">
              <ReportDownloads scanId={latestScan.scan_id} />
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3 w-full xl:w-auto">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            <button
              type="button"
              onClick={() => setBucketFilter('all')}
              className={`border px-3 py-2 text-left transition-colors ${bucketFilter === 'all' ? 'border-black bg-white text-black shadow-[inset_0_3px_0_#111111]' : 'border-black/10 bg-white/45 text-black hover:border-black/30'}`}
            >
              <span className="block font-mono text-[9px] uppercase tracking-widest text-black/40">Cases</span>
              <span className="block text-lg font-light text-black">{cases.length}</span>
            </button>
            {attentionBuckets.map((bucket) => (
              <button
                type="button"
                key={bucket}
                onClick={() => setBucketFilter(bucket)}
                className={`border px-3 py-2 text-left transition-colors ${bucketFilter === bucket ? 'border-black bg-white text-black shadow-[inset_0_3px_0_#111111]' : 'border-black/10 bg-white/45 text-black hover:border-black/30'}`}
              >
                <span className="block font-mono text-[9px] uppercase tracking-widest text-black/40">{attentionBucketLabels[bucket]}</span>
                <span className="block text-lg font-light text-black">{counts[bucket]}</span>
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {([
              ['open', 'Open', decisionCounts.open],
              ['verified', caseDecisionLabels.verified, decisionCounts.verified],
              ['false_positive', caseDecisionLabels.false_positive, decisionCounts.false_positive],
              ['accepted_risk', caseDecisionLabels.accepted_risk, decisionCounts.accepted_risk],
              ['fixed', caseDecisionLabels.fixed, decisionCounts.fixed],
            ] as const).map(([status, label, count]) => (
              <button
                type="button"
                key={status}
                onClick={() => setDecisionFilter(decisionFilter === status ? 'all' : status)}
                className={`border px-3 py-2 text-left transition-colors ${decisionFilter === status ? 'border-black bg-white text-black shadow-[inset_0_3px_0_#111111]' : 'border-black/10 bg-white/45 text-black hover:border-black/30'}`}
              >
                <span className="block font-mono text-[9px] uppercase tracking-widest text-black/40">{label}</span>
                <span className="block text-lg font-light text-black">{count}</span>
              </button>
            ))}
          </div>

          <div className="grid grid-cols-3 gap-2">
            {(['new', 'recurring', 'resolved'] as const).map((status) => (
              <button
                type="button"
                key={status}
                onClick={() => setChangeFilter(changeFilter === status ? 'all' : status)}
                className={`border px-3 py-2 text-left transition-colors ${changeFilter === status ? 'border-black bg-white text-black shadow-[inset_0_3px_0_#111111]' : 'border-black/10 bg-white/45 text-black hover:border-black/30'}`}
              >
                <span className="block font-mono text-[9px] uppercase tracking-widest text-black/40">{caseChangeLabels[status]}</span>
                <span className="block text-lg font-light text-black">{changeCounts[status]}</span>
              </button>
            ))}
          </div>

          <label className="flex flex-col gap-1">
            <span className="font-mono text-[9px] uppercase tracking-widest text-black/35">Search</span>
            <span className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-black/35" />
              <input
                type="search"
                name="findings-search"
                aria-label="Search cases"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Title, path, or next step"
                className="w-full bg-white/60 border border-black/10 pl-9 pr-3 py-2 text-xs text-black outline-none focus:border-black/40 placeholder:text-black/30"
              />
            </span>
          </label>
        </div>
      </div>

      {hasScan && <SinceLastScanPanel summary={summary} />}

      {!hasScan && (
        <div className="border border-black/10 bg-white/55 p-8 text-black/60">
          This repo has no saved scan yet. Run a quick safety sweep first, then cases will appear here.
        </div>
      )}

      {hasScan && cases.length === 0 && (
        <div className="border border-black/10 bg-white/60 p-8 flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div className="flex gap-4">
            <CheckCircle2 className="w-6 h-6 text-graph-gold shrink-0" strokeWidth={1.5} />
            <div>
              <h3 className="text-xl font-light text-black">The checks that ran did not find saved issues.</h3>
              <p className="text-sm text-black/55 mt-2">
                That is a useful result, but it is not a guarantee that the repo is safe. Review the coverage below before trusting it.
              </p>
            </div>
          </div>
          {onChooseChecks && (
            <button
              type="button"
              onClick={onChooseChecks}
              className="border border-black/10 bg-white/50 px-4 py-2 font-mono text-[10px] uppercase tracking-widest hover:border-black/30 transition-colors"
            >
              Choose checks
            </button>
          )}
        </div>
      )}

      {hasScan && cases.length > 0 && visibleCases.length === 0 && (
        <div className="border border-black/10 bg-white/55 p-8 text-black/60">
          No active cases match the current view.
        </div>
      )}

      {visibleCases.length > 0 && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-4">
            <h3 className="font-mono text-[10px] uppercase tracking-widest text-black/40">Active cases</h3>
            {hasSuppressed && (
              <span className="font-mono text-[10px] uppercase tracking-widest text-black/35">
                {suppressedFindingCount} suppressed
              </span>
            )}
          </div>
          {shownCases.map((item) => (
            <CaseCard
              key={item.id}
              item={item}
              onDecision={onCaseDecision ? (caseItem, status, note) => onCaseDecision(caseItem.id, caseItem.repoName, status, note) : undefined}
            />
          ))}
          {shownCases.length < visibleCases.length && (
            <button
              type="button"
              onClick={() => setVisibleLimit((current) => current + 24)}
              className="border border-black/10 bg-white/55 px-4 py-3 font-mono text-[10px] uppercase tracking-widest text-black/55 transition-colors hover:border-black/30 hover:text-black"
            >
              Show more cases ({visibleCases.length - shownCases.length} left)
            </button>
          )}
        </div>
      )}

      {hasSuppressed && (
        <section className="border border-black/10 bg-white/45 p-5 md:p-6">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-5">
            <div>
              <h3 className="text-xl font-light text-black">Suppressed cases</h3>
              <p className="text-sm text-black/55 mt-2 max-w-2xl">
                These are hidden from active counts because a dependency decision matched them. Keep the reason visible so the choice can be reviewed later.
              </p>
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-black/40">
              {summary.suppressed_counts?.cases ?? suppressedCases.length} cases / {suppressedFindingCount} raw findings
            </div>
          </div>

          {suppressionReasons.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-5">
              {suppressionReasons.slice(0, 4).map((reason, index) => (
                <div key={`${reason.reason}-${index}`} className="border border-black/10 bg-[#fbfbfb] p-3">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <span className="font-mono text-[9px] uppercase tracking-widest border border-black/10 bg-white px-2 py-1 text-black/50">
                      {String(reason.vex_status).replace(/_/g, ' ')}
                    </span>
                    <span className="font-mono text-[9px] uppercase tracking-widest text-black/35">
                      {reason.cases} cases / {reason.findings} raw findings
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed text-black/60 break-words">{reason.reason}</p>
                </div>
              ))}
            </div>
          )}

          {suppressedCases.length > 0 && (
            <div className="flex flex-col gap-3">
              {suppressedCases.slice(0, 8).map((item) => (
                <CaseCard key={`suppressed-${item.id}`} item={item} compact />
              ))}
              {suppressedCases.length > 8 && (
                <div className="border border-black/10 bg-[#fbfbfb] p-3 font-mono text-[10px] uppercase tracking-widest text-black/40">
                  {suppressedCases.length - 8} more suppressed cases are included in the raw report export.
                </div>
              )}
            </div>
          )}
        </section>
      )}

      <ScanCompletenessPanel completeness={completeness} summary={summary} hasScan={hasScan} />
    </motion.div>
  );
}
