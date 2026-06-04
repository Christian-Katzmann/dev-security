/* Reports — local report history. Everything stays on your machine. */

const REPORTS = [
  { id: "318", date: "Jun 4 · 14:02", profile: "Quick sweep", findings: 41, cases: 14 },
  { id: "317", date: "Jun 3 · 11:48", profile: "Full audit", findings: 39, cases: 13 },
  { id: "312", date: "Jun 1 · 16:00", profile: "Secrets", findings: 6, cases: 3 },
  { id: "309", date: "May 30 · 09:14", profile: "Full audit", findings: 44, cases: 16 },
];

function DownloadChip({ label }) {
  return (
    <span className="rounded-lg px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-[0.12em] transition hover:opacity-80"
      style={{ fontFamily: MONO, border: "1px solid var(--glass-border)", color: "var(--on-surface-muted)" }}>{label}</span>
  );
}

function MReports() {
  return (
    <div>
      <MPageHead eyebrow="System" title="Reports"
        sub="Every sweep leaves a report on your machine — HTML to read, JSON to parse, SBOM to share. Nothing is uploaded."
        actions={<MBtn variant="glass">Compare two scans</MBtn>} />

      <MGlass className="overflow-hidden">
        <div className="flex items-center gap-4 px-5 py-3 font-mono text-[10px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-ghost)" }}>
          <span className="w-24">Scan</span><span className="flex-1">Profile</span><span className="hidden w-40 sm:block">Result</span><span className="w-44 text-right">Download</span>
        </div>
        {REPORTS.map((r) => (
          <MRow key={r.id}>
            <div className="w-24 shrink-0">
              <div className="font-mono text-[12px]" style={{ fontFamily: MONO, color: "var(--on-surface)" }}>#{r.id}</div>
              <div className="font-mono text-[10.5px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{r.date}</div>
            </div>
            <span className="min-w-0 flex-1 truncate text-[13.5px]" style={{ color: "var(--on-surface)" }}>{r.profile}</span>
            <span className="hidden w-40 shrink-0 text-[12.5px] sm:block" style={{ color: "var(--on-surface-muted)" }}>{r.findings} findings · {r.cases} cases</span>
            <div className="flex w-44 shrink-0 justify-end gap-1.5">
              <DownloadChip label="HTML" /><DownloadChip label="JSON" /><DownloadChip label="SBOM" />
            </div>
          </MRow>
        ))}
      </MGlass>
    </div>
  );
}

Object.assign(window, { MReports });
