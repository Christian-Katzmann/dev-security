import {useEffect, useMemo, useState} from 'react';
import {History} from 'lucide-react';
import {
  DashboardSummary,
  ScanDiffResult,
  ScanHistoryItem,
  SecurityCase,
  fetchScanDiff,
  formatDate,
  repoDisplayName,
  trendValues,
} from '../dashboardData';

type ScanHistoryTrendsPanelProps = {
  summary: DashboardSummary;
};

function scanTime(scan: ScanHistoryItem): number {
  const time = new Date(scan.finished_at ?? scan.started_at ?? 0).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function scanOptionLabel(summary: DashboardSummary, scan: ScanHistoryItem): string {
  return `${scan.profile} · ${repoDisplayName(summary, scan.repo_name)} · ${formatDate(scan.finished_at ?? scan.started_at)}`;
}

function caseTitle(item: SecurityCase): string {
  return item.title ?? 'Security case';
}

function caseKey(item: SecurityCase, index: number): string {
  return String(item.case_id ?? index);
}

/**
 * Honest posture-over-time line on a fixed 0–100 health scale. Renders nothing
 * useful below two points — the caller gates on history length first, this is
 * the belt-and-braces guard.
 */
function PostureSparkline({values}: {values: number[]}) {
  if (values.length < 2) {
    return <p className="scan-trend-empty">Run at least two scans to chart posture over time.</p>;
  }
  const width = 240;
  const height = 56;
  const pad = 5;
  const points = values.map((value, index) => {
    const x = pad + (index / (values.length - 1)) * (width - pad * 2);
    const y = pad + (1 - Math.max(0, Math.min(100, value)) / 100) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const [lastX, lastY] = points[points.length - 1].split(',').map(Number);
  const latest = values[values.length - 1];
  return (
    <svg
      className="scan-trend-sparkline"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Posture trend across ${values.length} scans; latest health ${latest} of 100`}
      preserveAspectRatio="none"
    >
      <polyline className="scan-trend-line" points={points.join(' ')} fill="none" vectorEffect="non-scaling-stroke" />
      <circle className="scan-trend-dot" cx={lastX} cy={lastY} r={3} />
    </svg>
  );
}

function ScanDiffResultView({diff, summary}: {diff: ScanDiffResult; summary: DashboardSummary}) {
  const delta = diff.health_delta;
  const deltaLabel = delta === null ? '—' : `${delta >= 0 ? '+' : ''}${delta}`;
  const deltaTone = delta === null || delta === 0 ? 'flat' : delta > 0 ? 'up' : 'down';
  const resolved = diff.resolved_cases.slice(0, 5);
  return (
    <div className="scan-diff-result">
      <div className="scan-diff-headline">
        <span className={`scan-diff-delta tone-${deltaTone}`}>
          <b>{deltaLabel}</b>
          <em>health Δ</em>
        </span>
        <span className="scan-diff-scope">
          {diff.base.health_score} → {diff.head.health_score} · {repoDisplayName(summary, diff.head.repo_name)}
        </span>
      </div>
      {!diff.same_repo && (
        <p className="scan-diff-note">
          These scans are from different repositories, so case changes reflect raw appearance rather than a like-for-like comparison.
        </p>
      )}
      <div className="scan-diff-counts">
        <span className="scan-diff-count new"><b>{diff.counts.new}</b><em>new</em></span>
        <span className="scan-diff-count recurring"><b>{diff.counts.recurring}</b><em>recurring</em></span>
        <span className="scan-diff-count resolved"><b>{diff.counts.resolved}</b><em>resolved</em></span>
      </div>
      {resolved.length > 0 && (
        <ul className="scan-diff-cases">
          {resolved.map((item, index) => (
            <li key={caseKey(item, index)}>
              <strong>{caseTitle(item)}</strong>
              <span>{`Verified — not found in scan ${diff.head.scan_id}.`}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Scan history & trends (S-039, S-042): renders the full per-scan posture series
 * (more than the 7-bar week proxy) and lets the user diff any two saved scans —
 * not just "since last scan" — by driving the local `/api/scan-diff` route with
 * a base/head picker. All data is local; no new egress.
 */
export default function ScanHistoryTrendsPanel({summary}: ScanHistoryTrendsPanelProps) {
  // Newest first for the pickers and the date axis.
  const history = useMemo(
    () => [...summary.history].sort((a, b) => scanTime(b) - scanTime(a)),
    [summary.history],
  );
  const series = useMemo(() => trendValues(summary), [summary]);

  const defaults = useMemo(() => {
    if (history.length < 2) return null;
    const head = history[0];
    const base = history.find((scan, index) => index > 0 && scan.repo_name === head.repo_name) ?? history[1];
    return {headId: head.id, baseId: base.id};
  }, [history]);

  const [headId, setHeadId] = useState<string>(defaults?.headId ?? '');
  const [baseId, setBaseId] = useState<string>(defaults?.baseId ?? '');
  const [diff, setDiff] = useState<ScanDiffResult | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle');

  // Re-seed the selection whenever the underlying history changes (e.g. the
  // user switches the scoped target or a fresh scan lands).
  useEffect(() => {
    setHeadId(defaults?.headId ?? '');
    setBaseId(defaults?.baseId ?? '');
  }, [defaults]);

  const head = useMemo(() => history.find((scan) => scan.id === headId) ?? null, [history, headId]);
  // Base options are constrained to the head's repo so every comparison is a
  // meaningful same-repo, two-points-in-time diff.
  const baseOptions = useMemo(
    () => (head ? history.filter((scan) => scan.id !== head.id && scan.repo_name === head.repo_name) : []),
    [history, head],
  );

  // Keep the base valid for the chosen head.
  useEffect(() => {
    if (!baseOptions.length) {
      if (baseId) setBaseId('');
      return;
    }
    if (!baseOptions.some((scan) => scan.id === baseId)) {
      setBaseId(baseOptions[0].id);
    }
  }, [baseOptions, baseId]);

  useEffect(() => {
    if (!baseId || !headId || baseId === headId) {
      setDiff(null);
      setStatus('idle');
      return;
    }
    let cancelled = false;
    setStatus('loading');
    fetchScanDiff(baseId, headId)
      .then((result) => {
        if (cancelled) return;
        setDiff(result);
        setStatus('idle');
      })
      .catch(() => {
        if (cancelled) return;
        setDiff(null);
        setStatus('error');
      });
    return () => {
      cancelled = true;
    };
  }, [baseId, headId]);

  const newest = history[0];
  const oldest = history[history.length - 1];

  return (
    <section className="paper-card padded scan-trend-panel">
      <div className="section-header">
        <h3><History size={16} /> Scan history &amp; trends</h3>
        <div><span>{history.length} scan{history.length === 1 ? '' : 's'}</span></div>
      </div>

      {history.length < 2 ? (
        <p className="scan-trend-empty">Run at least two scans to chart posture over time and compare them.</p>
      ) : (
        <>
          <div className="scan-trend-chart">
            <PostureSparkline values={series} />
            <div className="scan-trend-axis">
              <span>{formatDate(oldest.finished_at ?? oldest.started_at)}</span>
              <span>Health {series[series.length - 1]}/100</span>
              <span>{formatDate(newest.finished_at ?? newest.started_at)}</span>
            </div>
          </div>

          <div className="scan-trend-compare">
            <label>
              <span>Base scan</span>
              <select aria-label="Base scan" value={baseId} onChange={(event) => setBaseId(event.target.value)}>
                {baseOptions.map((scan) => (
                  <option key={scan.id} value={scan.id}>{scanOptionLabel(summary, scan)}</option>
                ))}
              </select>
            </label>
            <span className="scan-trend-arrow" aria-hidden="true">→</span>
            <label>
              <span>Head scan</span>
              <select aria-label="Head scan" value={headId} onChange={(event) => setHeadId(event.target.value)}>
                {history.map((scan) => (
                  <option key={scan.id} value={scan.id}>{scanOptionLabel(summary, scan)}</option>
                ))}
              </select>
            </label>
          </div>

          {status === 'loading' && <p className="scan-trend-status">Comparing scans…</p>}
          {status === 'error' && <p className="scan-trend-status error">Comparison failed. Try another pair of scans.</p>}
          {status === 'idle' && diff && <ScanDiffResultView diff={diff} summary={summary} />}
        </>
      )}
    </section>
  );
}
