import {AlertTriangle, CheckCircle2, CircleSlash, ShieldQuestion, Stethoscope} from 'lucide-react';
import {
  ScanCompleteness,
  ScannerDoctorItem,
  scannerCoverageSummary,
  scannerDoctorGroups,
  scannerStatusLabels,
  DashboardSummary,
} from '../dashboardData';

type ScanCompletenessPanelProps = {
  completeness: ScanCompleteness;
  summary: DashboardSummary;
  hasScan: boolean;
};

function ListBlock({
  icon: Icon,
  title,
  items,
  empty,
}: {
  icon: typeof CheckCircle2;
  title: string;
  items: string[];
  empty: string;
}) {
  return (
    <div className="border border-black/10 bg-white/55 p-4">
      <div className="mb-3 flex items-center gap-2 font-mono text-[9px] uppercase tracking-widest text-black/40">
        <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />
        {title}
      </div>
      {items.length ? (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item} className="text-sm leading-relaxed text-black/65 break-words">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm leading-relaxed text-black/45">{empty}</p>
      )}
    </div>
  );
}

export default function ScanCompletenessPanel({completeness, summary, hasScan}: ScanCompletenessPanelProps) {
  const doctorGroups = scannerDoctorGroups(summary);
  const coverageSummary = scannerCoverageSummary(summary);

  return (
    <section className="border border-black/10 bg-[#fbfbfb]/80">
      <div className="border-b border-black/10 bg-white/60 p-5 md:p-6 shadow-[inset_0_3px_0_#111111]">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div>
            <h3 className="text-lg font-medium text-black">What this scan covered</h3>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-black/55">
              These results only describe the checks that actually ran. A clean result is useful, but it is not a promise that everything is safe.
            </p>
          </div>
          <div className="border border-black/10 bg-[#fbfbfb] p-3 md:max-w-sm">
            <div className="mb-1 flex items-center gap-2 font-mono text-[9px] uppercase tracking-widest text-black/35">
              <Stethoscope className="h-3.5 w-3.5" strokeWidth={1.5} />
              Scanner health
            </div>
            <p className="text-xs leading-relaxed text-black/60">{coverageSummary}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 p-5 md:p-6 border-b border-black/10">
        <ListBlock
          icon={CheckCircle2}
          title="Checks that ran"
          items={hasScan ? completeness.checksRan : []}
          empty={hasScan ? 'The scan did not report completed checks.' : 'Run a check to see coverage here.'}
        />
        <ListBlock
          icon={CircleSlash}
          title="Skipped or not installed"
          items={hasScan ? completeness.checksMissing : []}
          empty="No skipped checks were reported."
        />
        <ListBlock
          icon={ShieldQuestion}
          title="Cannot prove"
          items={hasScan ? completeness.cannotProve : ['No scan has run for this target yet.']}
          empty="No limits were reported."
        />
      </div>

      <div className="p-5 md:p-6">
        <div className="mb-4 flex items-center gap-2 font-mono text-[9px] uppercase tracking-widest text-black/40">
          <AlertTriangle className="h-3.5 w-3.5" strokeWidth={1.5} />
          Fix scanner coverage
        </div>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-black/55">
          Not-installed tools are grouped by the kind of risk they would check. Install or rerun the right profile, then scan again.
        </p>

        <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-3">
          {doctorGroups.map((group) => (
            <div key={group.area} className="border border-black/10 bg-white/55 p-4">
              <h4 className="mb-3 font-mono text-[9px] uppercase tracking-widest text-black/40">{group.area}</h4>
              <div className="flex flex-col gap-2">
                {group.items.map((item) => (
                  <ScannerDoctorRow key={item.scanner} item={item} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ScannerDoctorRow({item}: {item: ScannerDoctorItem}) {
  const statusStyle = {
    ran: 'border-black/10 bg-[#fbfbfb] text-black/55',
    missing: 'border-black/10 bg-white text-black shadow-[inset_3px_0_0_var(--sev-info)]',
    error: 'border-black bg-white text-black',
    'not-run': 'border-black/10 bg-white/60 text-black/45',
  }[item.status];

  return (
    <div className={`border p-3 ${statusStyle}`}>
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-sm text-black">{item.label}</span>
            <span className="font-mono text-[9px] uppercase tracking-widest border border-black/10 bg-white/60 px-2 py-0.5 text-black/45">
              {scannerStatusLabels[item.status]}
            </span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-black/55">{item.covers}</p>
        </div>
        {item.status === 'ran' && (
          <span className="shrink-0 font-mono text-[9px] uppercase tracking-widest text-black/35">
            {item.findings} raw signals
          </span>
        )}
      </div>
      <div className="mt-3 border border-black/10 bg-white/60 p-2 font-mono text-[10px] leading-relaxed text-black/60 break-words">
        {item.action}
      </div>
      {!!item.recommendedPacks.length && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {item.recommendedPacks.slice(0, 3).map((pack) => (
            <span key={pack.id} className="border border-black/10 bg-[#fbfbfb] px-2 py-1 font-mono text-[9px] uppercase tracking-widest text-black/45">
              {pack.label} · {pack.ready_count} ready · {pack.missing_count} not installed
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
