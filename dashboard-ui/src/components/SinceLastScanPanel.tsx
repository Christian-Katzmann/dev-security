import {ArrowDownRight, ArrowUpRight, Clock3, Minus, RotateCcw, type LucideIcon} from 'lucide-react';
import {DashboardSummary, aggregateCaseDelta, staleRepoCount} from '../dashboardData';

type SinceLastScanPanelProps = {
  summary: DashboardSummary;
};

export default function SinceLastScanPanel({summary}: SinceLastScanPanelProps) {
  const delta = aggregateCaseDelta(summary);
  const staleCount = staleRepoCount(summary);
  const reposWithHistory = summary.repos.filter((repo) => repo.previous_scan_id).length;
  const healthDelta = summary.repos.reduce((sum, repo) => sum + (repo.health_delta ?? 0), 0);
  const healthLabel = reposWithHistory ? signedNumber(healthDelta) : 'New';
  const HealthIcon = healthDelta > 0 ? ArrowUpRight : healthDelta < 0 ? ArrowDownRight : Minus;

  return (
    <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <MetricTile label="New" value={delta.new} tone={delta.new > 0 ? 'warn' : 'quiet'} icon={ArrowUpRight} />
      <MetricTile label="Still open" value={delta.recurring} tone={delta.recurring > 0 ? 'plain' : 'quiet'} icon={RotateCcw} />
      <MetricTile label="Resolved" value={delta.resolved} tone={delta.resolved > 0 ? 'good' : 'quiet'} icon={ArrowDownRight} />
      <MetricTile label="Health change" value={healthLabel} detail={staleCount ? `${staleCount} stale` : 'Fresh scans'} tone={staleCount ? 'warn' : 'quiet'} icon={staleCount ? Clock3 : HealthIcon} />
    </section>
  );
}

type MetricTileProps = {
  label: string;
  value: number | string;
  detail?: string;
  tone: 'plain' | 'quiet' | 'warn' | 'good';
  icon: LucideIcon;
};

function MetricTile({label, value, detail, tone, icon: Icon}: MetricTileProps) {
  const style = {
    plain: 'border-black/15 bg-white text-black',
    quiet: 'border-black/10 bg-white/55 text-black',
    warn: 'border-graph-gold bg-white text-black shadow-[inset_3px_0_0_#cca43b]',
    good: 'border-black/15 bg-[#fbfbfb] text-black shadow-[inset_3px_0_0_#111111]',
  }[tone];

  return (
    <div className={`border p-4 min-w-0 ${style}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="font-mono text-[9px] uppercase tracking-widest text-black/35 truncate">{label}</div>
        <Icon className="w-3.5 h-3.5 text-black/35 shrink-0" strokeWidth={1.6} />
      </div>
      <div className="mt-2 text-2xl font-light text-black">{value}</div>
      {detail && <div className="mt-1 font-mono text-[9px] uppercase tracking-widest text-black/35">{detail}</div>}
    </div>
  );
}

function signedNumber(value: number): string {
  if (value > 0) return `+${value}`;
  return String(value);
}
