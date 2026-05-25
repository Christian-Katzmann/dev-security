import { motion } from 'motion/react';
import {
  DashboardSummary,
  DependencyChange,
  DependencyChangeType,
  Finding,
  behavioralDriftFindings,
  categoryTotal,
  dependencyChangeLabels,
  dependencyChanges,
  dependencyCveCounts,
  dependencyCveStatusLabels,
  dependencyDeltaCounts,
  dependencyDeltas,
  dependencyMatchLabels,
  dependencyTrustRecords,
  formatLocation,
  iocMatchFindings,
  sortedFindings,
} from '../dashboardData';

type DependenciesViewProps = {
  summary: DashboardSummary;
};

const changeTypeOrder: DependencyChangeType[] = ['added', 'upgraded', 'downgraded', 'version-changed', 'license-changed', 'removed'];

export default function DependenciesView({summary}: DependenciesViewProps) {
  const deltas = dependencyDeltas(summary);
  const allChanges = dependencyChanges(summary).sort(changeSort);
  const changes = allChanges.slice(0, 8);
  const changeCounts = dependencyDeltaCounts(summary);
  const cveCounts = dependencyCveCounts(summary);
  const totalChanges = allChanges.length;
  const packagesObserved = deltas.reduce((sum, delta) => sum + delta.current_count, 0);
  const previousPackages = deltas.reduce((sum, delta) => sum + delta.previous_count, 0);
  const vulnerableCount = categoryTotal(summary, 'dependencies');
  const dependencyFindings = sortedFindings(summary, 'dependencies');
  const packageRows = dependencyFindings.slice(0, 3);
  const trustRecords = dependencyTrustRecords(summary).sort(trustSort);
  const trustRows = trustRecords.slice(0, 6);
  const driftFindings = behavioralDriftFindings(summary).slice(0, 6);
  const iocFindings = iocMatchFindings(summary);
  const iocRows = iocFindings.slice(0, 6);
  const emptyState = dependencyDeltaEmptyState(summary, deltas, totalChanges);

  return (
    <motion.div
      initial={{opacity: 0, y: 10}}
      animate={{opacity: 1, y: 0}}
      exit={{opacity: 0, scale: 0.98}}
      className="relative flex flex-col w-full p-6 md:p-12 max-w-[1400px] mx-auto gap-8"
    >
      <div className="flex flex-col md:flex-row md:justify-between md:items-end border-b border-black/10 pb-6 shrink-0 relative z-10 gap-4">
        <div className="min-w-0">
          <h2 className="text-3xl font-light text-black tracking-tight break-words">Supply Chain & SBOM</h2>
          <p className="font-mono text-xs text-black/50 uppercase tracking-widest mt-2 inline-block px-2 py-1 bg-white/40">
            Dependency history
          </p>
        </div>
      </div>

      <section className="border border-black/10 bg-white/60 p-5 md:p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-5">
          <div className="min-w-0">
            <h3 className="text-xl font-light text-black tracking-tight">Changed since last scan</h3>
            <p className="text-sm text-black/55 mt-2 max-w-2xl">
              Component changes are compared per repo against that repo's previous scan.
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 shrink-0">
            {changeTypeOrder.map((type) => (
              <MetricPill key={type} label={dependencyChangeLabels[type]} value={changeCounts[type] ?? 0} />
            ))}
            <MetricPill label={dependencyCveStatusLabels['no-cve']} value={cveCounts['no-cve']} />
            <MetricPill label={dependencyCveStatusLabels['not-checked']} value={cveCounts['not-checked']} />
            <MetricPill label={dependencyCveStatusLabels.unknown} value={cveCounts.unknown} />
          </div>
        </div>

        {emptyState ? (
          <EmptyDeltaState title={emptyState.title} body={emptyState.body} eyebrow={emptyState.eyebrow} />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {changes.map((change) => (
              <DependencyChangeCard key={`${change.scan_id}-${change.package_key}-${change.change_types.join('-')}`} change={change} />
            ))}
          </div>
        )}
        {!emptyState && totalChanges > changes.length && (
          <p className="mt-4 font-mono text-[10px] uppercase tracking-widest text-black/35">
            Showing {changes.length} of {totalChanges} changed packages
          </p>
        )}
      </section>

      <section className="border border-black/10 bg-white/60 p-5 md:p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-5">
          <div className="min-w-0">
            <h3 className="text-xl font-light text-black tracking-tight">Named-campaign matches</h3>
            <p className="text-sm text-black/55 mt-2 max-w-2xl">
              IOC packs are matched against saved SBOM components, namespace watches, and local domain evidence.
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 shrink-0">
            <MetricPill label="Matches" value={iocFindings.length} />
            <MetricPill label="Exact" value={iocFindings.filter((finding) => finding.ioc_match_type === 'exact match').length} />
            <MetricPill label="Watch" value={iocFindings.filter((finding) => finding.ioc_match_type !== 'exact match').length} />
          </div>
        </div>

        {iocRows.length ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {iocRows.map((finding) => (
              <NamedCampaignMatchCard key={finding.fingerprint} finding={finding} />
            ))}
          </div>
        ) : (
          <EmptyDeltaState
            eyebrow="No IOC matches"
            title="No named-campaign indicators matched the latest scan"
            body="Starter and custom IOC packs can still be loaded; clean means no saved SBOM or local domain evidence matched them."
          />
        )}
        {iocFindings.length > iocRows.length && (
          <p className="mt-4 font-mono text-[10px] uppercase tracking-widest text-black/35">
            Showing {iocRows.length} of {iocFindings.length} named-campaign matches
          </p>
        )}
      </section>

      {driftFindings.length > 0 && (
        <section className="border border-black/10 bg-white/60 p-5 md:p-6 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-5">
            <div className="min-w-0">
              <h3 className="text-xl font-light text-black tracking-tight">Behavioral drift</h3>
              <p className="text-sm text-black/55 mt-2 max-w-2xl">
                Old and new package artifacts were compared for behavior changes. This is investigation evidence, not proof of compromise.
              </p>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 shrink-0">
              <MetricPill label="Drift signals" value={driftFindings.length} />
              <MetricPill label="High risk" value={driftFindings.filter((finding) => finding.severity === 'critical' || finding.severity === 'high').length} />
              <MetricPill label="Packages" value={new Set(driftFindings.map((finding) => driftPackageLabel(finding))).size} />
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {driftFindings.map((finding) => (
              <BehavioralDriftCard key={finding.fingerprint} finding={finding} />
            ))}
          </div>
        </section>
      )}

      <section className="border border-black/10 bg-white/60 p-5 md:p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-5">
          <div className="min-w-0">
            <h3 className="text-xl font-light text-black tracking-tight">Dependency trust signals</h3>
            <p className="text-sm text-black/55 mt-2 max-w-2xl">
              CVE risk, project hygiene, ecosystem importance, and data freshness are shown as separate signals.
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 shrink-0">
            <MetricPill label="Trust records" value={trustRecords.length} />
            <MetricPill label="Low hygiene" value={trustRecords.filter(isLowHygiene).length} />
            <MetricPill label="High importance" value={trustRecords.filter(isHighCriticality).length} />
            <MetricPill label="Stale or unknown" value={trustRecords.filter(hasStaleOrUnknownTrust).length} />
          </div>
        </div>

        {trustRows.length ? (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {trustRows.map((record) => (
              <DependencyTrustCard key={`${record.scan_id}-${record.component_package_key ?? record.component_fingerprint ?? trustPackageLabel(record)}`} record={record} summary={summary} />
            ))}
          </div>
        ) : (
          <EmptyDeltaState
            eyebrow="No trust data"
            title="No project trust enrichment has been saved"
            body="Run a trust check when you want package hygiene and ecosystem importance beside the CVE results."
          />
        )}
        {trustRecords.length > trustRows.length && (
          <p className="mt-4 font-mono text-[10px] uppercase tracking-widest text-black/35">
            Showing {trustRows.length} of {trustRecords.length} trust records
          </p>
        )}
      </section>

      <div className="w-full min-h-[500px] border border-black/10 bg-[#fbfbfb] relative overflow-hidden flex items-center justify-center p-6 md:p-8 group shadow-sm shrink-0">
        <div className="absolute top-5 left-5 md:top-8 md:left-8 z-20 grid grid-cols-1 sm:grid-cols-3 md:flex md:flex-col gap-3 md:gap-6 max-w-[calc(100%-2.5rem)]">
          <div className="bg-white/85 backdrop-blur border border-black/10 p-4 min-w-0 w-full sm:w-40 md:w-48 shadow-sm">
            <div className="font-mono text-[10px] text-black/40 uppercase mb-2">Total packages</div>
            <div className="text-4xl font-light">{packagesObserved}</div>
          </div>
          <div className="bg-white/85 backdrop-blur border border-black/10 p-4 min-w-0 w-full sm:w-40 md:w-48 shadow-sm">
            <div className="font-mono text-[10px] text-black/40 uppercase mb-2">Previous inventory</div>
            <div className="text-4xl font-light">{previousPackages}</div>
          </div>
          <div className="bg-white/90 backdrop-blur border border-graph-gold p-4 min-w-0 w-full sm:w-40 md:w-48 shadow-[inset_2px_0_0_#d4a62d]">
            <div className="font-mono text-[10px] text-graph-gold uppercase mb-2">Known CVEs</div>
            <div className="text-4xl font-light text-black">{vulnerableCount}</div>
          </div>
        </div>

        <svg
          viewBox="0 0 1000 600"
          className="absolute inset-0 w-full h-full pointer-events-none"
          preserveAspectRatio="xMidYMid slice"
        >
          <motion.g
            initial={{opacity: 0, scale: 0.9}}
            animate={{opacity: 1, scale: 1}}
            transition={{duration: 1}}
          >
            <g stroke="#111" strokeWidth="0.5" fill="none" opacity="0.3">
              <polygon points="100,500 250,450 180,300 50,380" />
              <polygon points="180,300 250,450 350,320 280,200" />
              <polygon points="280,200 350,320 480,280 400,120" />
              <polygon points="50,380 180,300 120,180" />
              <polygon points="120,180 280,200 220,80" />
              <polygon points="220,80 400,120 320,40" />
              <polygon points="350,320 450,450 550,350 480,280" />
              <line x1="250" y1="450" x2="450" y2="450" />
              <line x1="450" y1="450" x2="600" y2="520" />
              <line x1="550" y1="350" x2="700" y2="380" />
              <line x1="480" y1="280" x2="650" y2="250" />
              <line x1="400" y1="120" x2="600" y2="150" />
            </g>

            <g stroke="#111" strokeWidth="1" fill="rgba(0,0,0,0.1)">
              <polygon points="450,450 600,520 700,380 550,350" />
              <polygon points="550,350 700,380 820,290 650,250" />
              <polygon points="650,250 820,290 750,180 600,150" />
            </g>

            <g fill="#111">
              <polygon points="600,520 850,550 950,420 700,380" />
              <polygon points="700,380 950,420 890,260 820,290" />
              <polygon points="820,290 890,260 820,100 750,180" />
            </g>

            <g fill="#d4a62d">
              <circle cx="350" cy="320" r="8" className="animate-ping opacity-50" />
              <circle cx="350" cy="320" r="4" />
              <line x1="350" y1="320" x2="550" y2="350" stroke="#d4a62d" strokeWidth="1.5" />
              <circle cx="550" cy="350" r="6" />
              <line x1="550" y1="350" x2="700" y2="380" stroke="#d4a62d" strokeWidth="1.5" />
              <circle cx="700" cy="380" r="8" stroke="#111" strokeWidth="2" />
            </g>

            <line x1="100" y1="0" x2="100" y2="600" stroke="#d4a62d" strokeWidth="1" className="opacity-20">
              <animate attributeName="x1" values="100;900;100" dur="8s" repeatCount="indefinite" />
              <animate attributeName="x2" values="100;900;100" dur="8s" repeatCount="indefinite" />
            </line>
          </motion.g>
        </svg>

        <div className="absolute bottom-5 right-5 md:bottom-8 md:right-8 bg-white/90 backdrop-blur border border-black/10 shadow-sm p-5 flex flex-col gap-3 w-[min(18rem,calc(100%-2.5rem))] z-20">
          <h4 className="font-mono text-[10px] uppercase text-black/50 border-b border-black/10 pb-2">SBOM Snapshot</h4>
          <LegendRow tone="outline" label={`${packagesObserved} current package records`} />
          <LegendRow tone="solid" label={`${totalChanges} changed package records`} />
          <LegendRow tone="gold" label={`${vulnerableCount} known dependency CVE signals`} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-4 shrink-0 pb-12">
        <div className="md:col-span-2 flex flex-col gap-4 min-w-0">
          <h3 className="font-mono text-[10px] tracking-widest text-black/40 uppercase mb-2">Vulnerable Path Analysis</h3>
          {packageRows.length ? (
            packageRows.map((item) => (
              <div key={item.fingerprint} className="border border-black/10 bg-white/50 p-4 flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 hover:bg-white transition-colors group min-w-0">
                <div className="flex flex-col gap-1 min-w-0">
                  <div className="flex items-start gap-3 min-w-0">
                    <span className={"w-2 h-2 mt-1.5 shrink-0 " + (item.severity === 'critical' ? 'bg-graph-gold animate-pulse' : item.severity === 'high' ? 'bg-black' : 'bg-black/30')} />
                    <span className="font-mono text-xs font-semibold text-black break-words min-w-0">
                      {item.title} <span className="font-normal text-black/50 ml-2 break-all">{formatLocation(item)}</span>
                    </span>
                  </div>
                  <div className="text-xs text-black/60 mt-2 pl-5 break-words">
                    {item.remediation ?? 'Review the scanner report for the fixed version and advisory context.'}
                  </div>
                </div>
                <div className={"font-mono text-[10px] uppercase px-2 py-1 mt-1 border self-start shrink-0 " + (item.severity === 'critical' ? 'text-graph-gold border-graph-gold/30' : 'text-black/60 border-black/10')}>
                  {item.severity}
                </div>
              </div>
            ))
          ) : (
            <div className="border border-black/10 bg-white/50 p-5 text-sm text-black/55">
              No dependency vulnerability raw findings are recorded for the latest scan payload.
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4 min-w-0">
          <h3 className="font-mono text-[10px] tracking-widest text-black/40 uppercase mb-2">Change Types</h3>
          <div className="border border-black/10 p-6 bg-white/50 h-full min-w-0">
            <ul className="space-y-4">
              {changeTypeOrder.map((type) => (
                <li key={type} className="flex justify-between items-center gap-3 border-b border-black/5 pb-2 min-w-0">
                  <span className="font-mono text-[10px] text-black/70 break-words">{dependencyChangeLabels[type]}</span>
                  <span className="font-mono text-[10px] text-black/40 border border-black/10 px-1 shrink-0">{changeCounts[type] ?? 0}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function DependencyChangeCard({change}: {change: DependencyChange}) {
  return (
    <article className="border border-black/10 bg-[#fbfbfb] p-4 min-w-0">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 min-w-0">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-2 mb-3">
            {change.change_types.map((type) => (
              <span key={type} className={changeBadgeClass(type)}>
                {dependencyChangeLabels[type]}
              </span>
            ))}
          </div>
          <h4 className="text-base font-medium text-black break-words">{packageLabel(change)}</h4>
          <p className="mt-2 text-xs leading-relaxed text-black/55 break-words">{changeSummary(change)}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {change.silent_upgrade?.status === 'flagged' && (
              <StatusBadge tone="gold" label={change.silent_upgrade.label ?? 'Silent upgrade'} />
            )}
            <StatusBadge tone={cveTone(change.cve_status)} label={cveLabel(change)} />
            <StatusBadge tone={matchTone(change.match_confidence)} label={matchLabel(change)} />
            {(change.metadata_warnings ?? []).map((warning) => (
              <StatusBadge key={warning} tone="muted" label={warning} />
            ))}
          </div>
        </div>
        <span className="font-mono text-[9px] uppercase tracking-widest text-black/35 shrink-0">{change.repo_name}</span>
      </div>
      <dl className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
        <DeltaFact label="Version" value={versionText(change)} />
        <DeltaFact label="License" value={licenseText(change)} />
        <DeltaFact label="Ecosystem" value={change.ecosystem ?? change.component_type ?? 'Unknown'} />
        <DeltaFact label="CVE check" value={change.cve_reason ?? cveLabel(change)} />
        <DeltaFact label="Silent signal" value={silentUpgradeText(change)} />
        <DeltaFact label="Source" value={change.source_path ?? change.package_url ?? 'SBOM'} wide />
      </dl>
    </article>
  );
}

function DependencyTrustCard({record, summary}: {record: ReturnType<typeof dependencyTrustRecords>[number]; summary: DashboardSummary}) {
  const vulnerability = vulnerabilitySignal(summary, record);
  return (
    <article className="border border-black/10 bg-[#fbfbfb] p-4 min-w-0">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 min-w-0">
        <div className="min-w-0">
          <h4 className="text-base font-medium text-black break-words">{trustPackageLabel(record)}</h4>
          <p className="mt-1 text-xs text-black/45 break-all">{record.source_repo ?? record.source_repo_reason}</p>
        </div>
        <span className="font-mono text-[9px] uppercase tracking-widest text-black/35 shrink-0">{record.repo_name}</span>
      </div>

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5 gap-2">
        <TrustSignal label="Vulnerability risk" value={vulnerability.label} tone={vulnerability.tone} />
        <TrustSignal label="Project hygiene" value={scorecardLabel(record)} tone={scorecardTone(record)} />
        <TrustSignal label="Ecosystem importance" value={criticalityLabel(record)} tone={criticalityTone(record)} />
        <TrustSignal label="Freshness" value={freshnessLabel(record)} tone={freshnessTone(record)} />
        <TrustSignal label="Data state" value={trustStateLabel(record)} tone={trustStateTone(record)} />
      </div>

      <p className="mt-3 text-xs leading-relaxed text-black/55 break-words">{trustReason(record, vulnerability.label)}</p>
    </article>
  );
}

function NamedCampaignMatchCard({finding}: {finding: Finding}) {
  const advisory = finding.ioc_advisory_url;
  return (
    <article className="border border-black/10 bg-[#fbfbfb] p-4 min-w-0">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 min-w-0">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-2 mb-3">
            <StatusBadge tone={finding.ioc_match_type === 'exact match' ? 'gold' : 'dark'} label={finding.ioc_match_type ?? 'IOC match'} />
            <StatusBadge tone="outline" label={finding.ioc_confidence ?? 'unknown confidence'} />
          </div>
          <h4 className="text-base font-medium text-black break-words">{iocPackageLabel(finding)}</h4>
          <p className="mt-2 text-xs leading-relaxed text-black/55 break-words">
            {finding.ioc_source ?? finding.ioc_pack_id ?? 'IOC pack'} matched {finding.ioc_indicator ?? 'a named-campaign indicator'}.
          </p>
        </div>
        <span className="font-mono text-[9px] uppercase tracking-widest text-black/35 shrink-0">{finding.repo_name}</span>
      </div>

      <dl className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
        <DeltaFact label="Affected package" value={iocPackageLabel(finding)} />
        <DeltaFact label="Pack" value={finding.ioc_pack_id ?? finding.ioc_source ?? 'Unknown pack'} />
        <DeltaFact label="Evidence" value={finding.file ?? 'Repository evidence'} />
        <DeltaFact label="Advisory" value={advisory ?? 'No advisory link recorded'} />
      </dl>
      {advisory && (
        <a className="inline-block mt-3 font-mono text-[10px] uppercase tracking-widest text-black underline decoration-black/25" href={advisory}>
          Open advisory
        </a>
      )}
    </article>
  );
}

function BehavioralDriftCard({finding}: {finding: Finding}) {
  return (
    <article className="border border-black/10 bg-[#fbfbfb] p-4 min-w-0">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 min-w-0">
        <div className="min-w-0">
          <div className="flex flex-wrap gap-2 mb-3">
            <StatusBadge tone={finding.severity === 'critical' || finding.severity === 'high' ? 'gold' : 'outline'} label={finding.severity} />
            <StatusBadge tone="muted" label={finding.behavior_category ?? 'behavior change'} />
          </div>
          <h4 className="text-base font-medium text-black break-words">{driftPackageLabel(finding)}</h4>
          <p className="mt-2 text-xs leading-relaxed text-black/55 break-words">
            {finding.evidence_summary ?? 'malcontent reported a behavior difference between the old and new package artifacts.'}
          </p>
        </div>
        <span className="font-mono text-[9px] uppercase tracking-widest text-black/35 shrink-0">{finding.repo_name}</span>
      </div>

      <dl className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
        <DeltaFact label="Version" value={`${finding.old_version ?? 'Unknown'} -> ${finding.new_version ?? finding.package_version ?? 'Unknown'}`} />
        <DeltaFact label="Before" value={finding.before_behavior ?? 'No comparable behavior was reported'} />
        <DeltaFact label="After" value={finding.after_behavior ?? finding.title} />
        <DeltaFact label="Evidence" value={finding.file ?? 'Artifact diff'} />
      </dl>
    </article>
  );
}

function MetricPill({label, value}: {label: string; value: number}) {
  return (
    <div className="border border-black/10 bg-[#fbfbfb] px-3 py-2 min-w-0">
      <div className="font-mono text-[9px] uppercase tracking-widest text-black/35 leading-tight break-words">{label}</div>
      <div className="text-xl font-light text-black">{value}</div>
    </div>
  );
}

function EmptyDeltaState({title, body, eyebrow}: {title: string; body: string; eyebrow: string}) {
  return (
    <div className="border border-black/10 bg-[#fbfbfb] p-5">
      <div className="font-mono text-[10px] uppercase tracking-widest text-black/35 mb-2">{eyebrow}</div>
      <h4 className="text-lg font-medium text-black">{title}</h4>
      <p className="mt-2 text-sm leading-relaxed text-black/55 max-w-2xl">{body}</p>
    </div>
  );
}

function StatusBadge({tone, label}: {tone: 'gold' | 'dark' | 'muted' | 'outline'; label: string}) {
  const toneClass = {
    gold: 'border-graph-gold/40 text-graph-gold bg-white',
    dark: 'border-black text-black bg-white',
    muted: 'border-black/10 text-black/45 bg-white/60',
    outline: 'border-black/15 text-black/65 bg-white',
  }[tone];
  return (
    <span className={`font-mono text-[9px] uppercase tracking-widest border px-2 py-1 ${toneClass}`}>
      {label}
    </span>
  );
}

function TrustSignal({label, value, tone}: {label: string; value: string; tone: 'gold' | 'dark' | 'muted' | 'outline'}) {
  const toneClass = {
    gold: 'border-graph-gold/40 text-graph-gold bg-white',
    dark: 'border-black text-black bg-white',
    muted: 'border-black/10 text-black/45 bg-white/60',
    outline: 'border-black/15 text-black/65 bg-white',
  }[tone];
  return (
    <div className={`border p-3 min-w-0 ${toneClass}`}>
      <div className="font-mono text-[9px] uppercase tracking-widest opacity-70 leading-tight break-words">{label}</div>
      <div className="mt-2 text-xs font-medium text-black leading-snug break-words">{value}</div>
    </div>
  );
}

function DeltaFact({label, value, wide = false}: {label: string; value: string; wide?: boolean}) {
  return (
    <div className={`border border-black/10 bg-white/70 p-3 min-w-0 ${wide ? 'sm:col-span-2' : ''}`}>
      <dt className="font-mono text-[9px] uppercase tracking-widest text-black/35 mb-1">{label}</dt>
      <dd className="text-xs text-black/65 break-all">{value}</dd>
    </div>
  );
}

function LegendRow({tone, label}: {tone: 'outline' | 'solid' | 'gold'; label: string}) {
  const boxClass = tone === 'solid' ? 'bg-black' : tone === 'gold' ? 'bg-graph-gold' : 'border border-black/30';
  return (
    <div className="flex items-center gap-3 min-w-0">
      <div className={`w-3 h-3 shrink-0 ${boxClass}`} />
      <span className="text-xs text-black break-words">{label}</span>
    </div>
  );
}

function dependencyDeltaEmptyState(summary: DashboardSummary, deltas: ReturnType<typeof dependencyDeltas>, totalChanges: number) {
  if (!summary.repos.length) {
    return {
      eyebrow: 'No scans',
      title: 'No dependency scan has run yet',
      body: 'Run a dependency or full scan to build the first package inventory.',
    };
  }
  if (!deltas.length || deltas.every((delta) => delta.status === 'no-sbom')) {
    const explanation = deltas.find((delta) => delta.comparison_explanation)?.comparison_explanation;
    return {
      eyebrow: 'No SBOM',
      title: 'No package inventory was saved for the latest scan',
      body: explanation ?? 'Run a dependency/SBOM check so the observatory has package records to compare.',
    };
  }
  if (deltas.every((delta) => delta.status === 'first-scan')) {
    const explanation = deltas.find((delta) => delta.comparison_explanation)?.comparison_explanation;
    return {
      eyebrow: 'First scan',
      title: 'No previous scan exists for comparison',
      body: explanation ?? 'This scan saved an SBOM, but dependency changes need a second scan of the same repo.',
    };
  }
  if (totalChanges === 0) {
    const explanation = deltas.find((delta) => delta.comparison_explanation)?.comparison_explanation;
    return {
      eyebrow: 'No changes',
      title: 'No dependency changes since the previous scan',
      body: explanation ?? 'The latest SBOM matches the previous saved package inventory for this target.',
    };
  }
  return null;
}

function changeSort(a: DependencyChange, b: DependencyChange): number {
  const silentRank = Number(b.silent_upgrade?.status === 'flagged') - Number(a.silent_upgrade?.status === 'flagged');
  if (silentRank) return silentRank;
  const typeRank = changeTypeOrder.indexOf(a.change_type) - changeTypeOrder.indexOf(b.change_type);
  if (typeRank) return typeRank;
  return packageLabel(a).localeCompare(packageLabel(b), undefined, {sensitivity: 'base'});
}

function trustSort(a: ReturnType<typeof dependencyTrustRecords>[number], b: ReturnType<typeof dependencyTrustRecords>[number]): number {
  return trustRank(b) - trustRank(a) || trustPackageLabel(a).localeCompare(trustPackageLabel(b), undefined, {sensitivity: 'base'});
}

function trustRank(record: ReturnType<typeof dependencyTrustRecords>[number]): number {
  return (isLowHygiene(record) ? 4 : 0) + (isHighCriticality(record) ? 4 : 0) + (hasStaleOrUnknownTrust(record) ? 1 : 0);
}

function packageLabel(change: DependencyChange): string {
  const label = change.name ?? change.package_url ?? change.package_key.replace(/^[^|]+\|/, '');
  return label || 'Unknown package';
}

function trustPackageLabel(record: ReturnType<typeof dependencyTrustRecords>[number]): string {
  const version = record.package_version ? ` ${record.package_version}` : '';
  return `${record.package_name ?? record.package_url ?? record.component_package_key ?? 'Unknown package'}${version}`;
}

function driftPackageLabel(finding: Finding): string {
  const version = finding.new_version ?? finding.package_version;
  return `${finding.package_name ?? finding.package_url ?? finding.title}${version ? ` ${version}` : ''}`;
}

function iocPackageLabel(finding: Finding): string {
  const version = finding.package_version ? ` ${finding.package_version}` : '';
  return `${finding.package_name ?? finding.ioc_indicator ?? finding.title}${version}`;
}

function vulnerabilitySignal(summary: DashboardSummary, record: ReturnType<typeof dependencyTrustRecords>[number]): {label: string; tone: 'gold' | 'dark' | 'muted' | 'outline'} {
  const packageName = record.package_name?.toLowerCase();
  const packageKey = record.component_package_key?.toLowerCase();
  const fingerprint = record.component_fingerprint?.toLowerCase();
  const match = sortedFindings(summary, 'dependencies').find((finding) => {
    if (finding.repo_name !== record.repo_name) return false;
    if (packageKey && finding.component_package_key?.toLowerCase() === packageKey) return true;
    if (fingerprint && finding.component_fingerprint?.toLowerCase() === fingerprint) return true;
    if (packageName && finding.package_name?.toLowerCase() === packageName) return true;
    return Boolean(packageName && finding.title.toLowerCase().includes(packageName));
  });
  if (match) return {label: `${match.severity.toUpperCase()} CVE signal`, tone: match.severity === 'critical' || match.severity === 'high' ? 'gold' : 'dark'};
  return {label: 'No linked CVE', tone: 'outline'};
}

function scorecardLabel(record: ReturnType<typeof dependencyTrustRecords>[number]): string {
  if (typeof record.scorecard_score === 'number') return `${record.scorecard_score.toFixed(1)} / 10`;
  return record.scorecard_status === 'not_checked' ? 'Not checked' : 'Unavailable';
}

function scorecardTone(record: ReturnType<typeof dependencyTrustRecords>[number]): 'gold' | 'dark' | 'muted' | 'outline' {
  if (isLowHygiene(record)) return 'gold';
  if (typeof record.scorecard_score === 'number') return 'outline';
  return 'muted';
}

function criticalityLabel(record: ReturnType<typeof dependencyTrustRecords>[number]): string {
  if (typeof record.criticality_score === 'number') return record.criticality_score.toFixed(2);
  return record.criticality_status === 'not_checked' ? 'Not checked' : 'Unavailable';
}

function criticalityTone(record: ReturnType<typeof dependencyTrustRecords>[number]): 'gold' | 'dark' | 'muted' | 'outline' {
  if (isHighCriticality(record)) return 'dark';
  if (typeof record.criticality_score === 'number') return 'outline';
  return 'muted';
}

function freshnessLabel(record: ReturnType<typeof dependencyTrustRecords>[number]): string {
  if (record.freshness === 'fresh') return 'Fresh';
  if (record.freshness === 'stale') return 'Stale';
  if (record.status === 'unknown_source') return 'Unknown source';
  if (record.freshness === 'unavailable') return 'Unavailable';
  return 'Unknown';
}

function freshnessTone(record: ReturnType<typeof dependencyTrustRecords>[number]): 'gold' | 'dark' | 'muted' | 'outline' {
  if (record.freshness === 'fresh') return 'outline';
  if (record.freshness === 'stale') return 'gold';
  return 'muted';
}

function trustStateLabel(record: ReturnType<typeof dependencyTrustRecords>[number]): string {
  if (record.status === 'unknown_source') return 'Unknown source';
  if (record.freshness === 'stale') return 'Use as old context';
  if (record.freshness === 'unknown') return 'Freshness unknown';
  if (record.freshness === 'unavailable') return 'Trust lookup unavailable';
  if (record.error) return 'Lookup error';
  if (typeof record.scorecard_score !== 'number' || typeof record.criticality_score !== 'number') return 'Partly missing';
  return 'Ready to compare';
}

function trustStateTone(record: ReturnType<typeof dependencyTrustRecords>[number]): 'gold' | 'dark' | 'muted' | 'outline' {
  if (record.freshness === 'stale') return 'gold';
  if (record.status === 'unknown_source' || record.freshness === 'unknown' || record.freshness === 'unavailable' || record.error) return 'muted';
  return 'outline';
}

function trustReason(record: ReturnType<typeof dependencyTrustRecords>[number], vulnerabilityLabel: string): string {
  if (isLowHygiene(record) && isHighCriticality(record) && record.freshness !== 'stale') {
    return `${vulnerabilityLabel}. This package appears important in the ecosystem, but its project hygiene score is weak, so upgrades and fixes deserve a closer look.`;
  }
  if (record.freshness === 'stale') {
    return `${vulnerabilityLabel}. Hygiene or importance data is stale, so use it as context rather than proof.`;
  }
  if (record.status === 'unknown_source') {
    return `${vulnerabilityLabel}. No reliable source repository was found, so missing project hygiene is not treated as a failure.`;
  }
  if (typeof record.scorecard_score !== 'number' && typeof record.criticality_score !== 'number') {
    return `${vulnerabilityLabel}. Project hygiene and ecosystem importance were not available for this package.`;
  }
  return `${vulnerabilityLabel}. Trust facts add context, separate from known vulnerability raw findings.`;
}

function isLowHygiene(record: ReturnType<typeof dependencyTrustRecords>[number]): boolean {
  return typeof record.scorecard_score === 'number' && record.scorecard_score <= 4;
}

function isHighCriticality(record: ReturnType<typeof dependencyTrustRecords>[number]): boolean {
  return typeof record.criticality_score === 'number' && record.criticality_score >= 0.7;
}

function hasStaleOrUnknownTrust(record: ReturnType<typeof dependencyTrustRecords>[number]): boolean {
  return record.freshness === 'stale' || record.freshness === 'unknown' || record.freshness === 'unavailable' || record.status === 'unknown_source';
}

function changeSummary(change: DependencyChange): string {
  if (change.silent_upgrade?.status === 'flagged' && change.silent_upgrade.reason) return change.silent_upgrade.reason;
  if (change.change_type === 'added') return 'This package appears in the latest SBOM but not in the previous scan.';
  if (change.change_type === 'removed') return 'This package appeared in the previous SBOM but not in the latest scan.';
  if (change.version_changed && change.license_changed) return 'Version and license metadata both changed.';
  if (change.version_changed) return 'The saved package version changed between scans.';
  if (change.license_changed) return 'The saved license metadata changed while the package stayed present.';
  return 'The saved package metadata changed between scans.';
}

function versionText(change: DependencyChange): string {
  const previous = change.previous_version ?? 'Missing';
  const current = change.current_version ?? 'Missing';
  return `${previous} -> ${current}`;
}

function licenseText(change: DependencyChange): string {
  const previous = change.previous_license ?? 'Unknown';
  const current = change.current_license ?? 'Unknown';
  return `${previous} -> ${current}`;
}

function cveLabel(change: DependencyChange): string {
  if (change.cve_label) return change.cve_label;
  return dependencyCveStatusLabels[change.cve_status ?? 'unknown'];
}

function matchLabel(change: DependencyChange): string {
  if (change.match_label) return change.match_label;
  return dependencyMatchLabels[change.match_confidence ?? 'unknown'];
}

function cveTone(status: DependencyChange['cve_status']): 'gold' | 'dark' | 'muted' | 'outline' {
  if (status === 'has-cve') return 'gold';
  if (status === 'no-cve') return 'outline';
  if (status === 'not-checked') return 'muted';
  return 'dark';
}

function matchTone(confidence: DependencyChange['match_confidence']): 'gold' | 'dark' | 'muted' | 'outline' {
  if (confidence === 'strong') return 'outline';
  if (confidence === 'weak-match') return 'muted';
  return 'dark';
}

function silentUpgradeText(change: DependencyChange): string {
  const signal = change.silent_upgrade;
  if (!signal) return 'Not checked';
  if (signal.status === 'flagged') {
    const kind = signal.kind === 'direct' ? 'direct dependency' : 'transitive dependency';
    return `${signal.label ?? 'Silent upgrade'} (${kind})`;
  }
  if (signal.status === 'explained') return signal.reason ?? 'Manifest change explains this movement';
  if (signal.status === 'not-silent') return 'No silent-upgrade signal';
  return signal.reason ?? 'Unknown';
}

function changeBadgeClass(type: DependencyChangeType): string {
  const base = 'font-mono text-[9px] uppercase tracking-widest border px-2 py-1';
  if (type === 'added') return `${base} border-graph-gold/40 bg-white text-black`;
  if (type === 'removed') return `${base} border-black/10 bg-white/50 text-black/45`;
  if (type === 'downgraded') return `${base} border-black text-black bg-white`;
  if (type === 'license-changed') return `${base} border-black/15 bg-white text-black/60`;
  return `${base} border-black/10 bg-white text-black/70`;
}
