/* Overview — a full-width posture hero, then a bento board with real size
   variety: a 2×2 actionable anchor + a 2×2 stat cluster, then two tall columns
   (severity ladder, activity feed) flanking a chart stack, then two wides.
   Tile size mirrors information rank. Mode-aware (all repos ↔ single repo). */

function overviewData(target) {
  const isAll = target === "all";
  if (isAll) {
    return {
      isAll, scope: "all repositories",
      posture: { score: 8.1, tier: "Steady" }, delta: "+0.4 vs last week",
      week: [{ l: "M", v: 7.9 }, { l: "T", v: 8.0 }, { l: "W", v: 7.6 }, { l: "T", v: 8.2 }, { l: "F", v: 8.0 }, { l: "S", v: 8.1 }, { l: "S", v: 8.1 }],
      headline: "Your repos are in good shape.",
      sub: "27 cases across 2 of your 3 repos, closing faster than they open. One critical wants you first.",
      tiles: [
        { eyebrow: "Open cases", big: "27", sub: "1 critical · 3 high" },
        { eyebrow: "Repos affected", big: "2 / 3", sub: "2 need attention" },
        { eyebrow: "Honey keys", big: "4", sub: "armed · 0 tripped" },
        { eyebrow: "Last sweep", big: "2h", sub: "ago · 3 audits passed" },
      ],
      severity: [
        { label: "critical", value: 1 }, { label: "high", value: 3 },
        { label: "medium", value: 9 }, { label: "low", value: 14 },
      ],
      severityInsight: "Weight sits at the bottom.",
      line: { open: [18, 17, 19, 16, 15, 14, 13, 12, 11], resolved: [4, 7, 9, 11, 12, 14, 16, 18, 20] },
      activityInsight: "You scan most weekdays.",
      coverage: { overall: 74, insight: "Config has a gap.", items: [{ label: "secrets", pct: 96 }, { label: "deps", pct: 88 }, { label: "code", pct: 71 }, { label: "config", pct: 40 }] },
      attention: [["Hardcoded AWS key · payments-api", "critical"], ["Vulnerable lodash · advisories", "high"]],
      readiness: { pct: 65, label: "13 of 20 checks done" },
    };
  }
  return {
    isAll, scope: target,
    posture: { score: 8.0, tier: "Steady" }, delta: "+0.3 vs last week",
    week: [{ l: "M", v: 7.7 }, { l: "T", v: 7.8 }, { l: "W", v: 7.6 }, { l: "T", v: 7.9 }, { l: "F", v: 8.0 }, { l: "S", v: 8.0 }, { l: "S", v: 8.0 }],
    headline: `${target} is in good shape.`,
    sub: "8 cases, closing faster than they open. One high to look at first — no criticals. Last sweep 2 hours ago.",
    tiles: [
      { eyebrow: "Open cases", big: "8", sub: "0 critical · 1 high" },
      { eyebrow: "Secret rotation", big: "4", sub: "tracked · 0 due" },
      { eyebrow: "Honey keys", big: "3", sub: "armed · 0 tripped" },
      { eyebrow: "Last sweep", big: "2h", sub: "ago · 5 of 6 ran" },
    ],
    severity: [
      { label: "critical", value: 0 }, { label: "high", value: 1 },
      { label: "medium", value: 3 }, { label: "low", value: 4 },
    ],
    severityInsight: "Mostly low-severity.",
    line: { open: [14, 13, 12, 11, 10, 9, 9, 8, 8], resolved: [3, 5, 7, 9, 10, 12, 13, 14, 15] },
    activityInsight: "Scanned daily this week.",
    coverage: { overall: 83, insight: "One gap to close.", items: [{ label: "secrets", pct: 100 }, { label: "deps", pct: 88 }, { label: "code", pct: 80 }, { label: "config", pct: 60 }] },
    attention: [["Vulnerable lodash · advisories", "high"], ["Permissive CORS · internal route", "medium"]],
    readiness: { pct: 80, label: "16 of 20 checks done" },
  };
}

/* Repository health scoreboard — DëvSec's take on a per-entity "score" row
   (cf. an Outlier Score): each repo gets a tick-meter health score + N/10. */
const REPO_HEALTH = [
  { repo: "payments-api", cases: 27, score: 6 },
  { repo: "web-dashboard", cases: 8, score: 8 },
  { repo: "infra-terraform", cases: 4, score: 9 },
];

const OV_ACTIVITY = [
  { icon: "circle-check", text: "Quick sweep finished — 41 findings, 14 cases", repo: "payments-api", t: "2h" },
  { icon: "inbox", text: "2 new medium cases opened", repo: "payments-api", t: "2h" },
  { icon: "shield-check", text: "Full audit finished — no critical findings", repo: "web-dashboard", t: "6h" },
  { icon: "wrench", text: "Case resolved — debug endpoint disabled", repo: "web-dashboard", t: "1d" },
  { icon: "key-round", text: "Honey key rotated", repo: "infra-terraform", t: "1d" },
  { icon: "circle-check", text: "Quick sweep finished — 12 findings, 4 cases", repo: "infra-terraform", t: "2d" },
];

/* "How would you like to proceed?" — the 6-action grid restored from the live
   dashboard (App.tsx), mapped to the lab's icon set. */
const PROCEED_ACTIONS = [
  { icon: "circle-check", title: "Run a scan", detail: "Check your repos now" },
  { icon: "package", title: "View catalog", detail: "Explore tools" },
  { icon: "activity", title: "View activity", detail: "Recent scans" },
  { icon: "file-text", title: "View reports", detail: "Open saved reports" },
  { icon: "settings", title: "Setup integrations", detail: "Setup-capable tools" },
  { icon: "target", title: "Add repository", detail: "Register a target" },
];

/* AI follow-up options — mirrored from the live AiFollowUpPanel. */
const AI_REPOS = ["payments-api", "web-dashboard", "infra-terraform"];
const AI_ACTIONS = ["Verify findings", "Fix vulnerabilities", "Create remediation plan", "Explain risk", "Re-check after fixes"];
const AI_SCOPES = ["Critical", "Critical + High", "All open", "Selected cases", "New since last scan"];

const SEV_BADGE = {
  critical: { bg: "rgba(217,138,122,0.23)", fg: "#f2ad9d" },
  high: { bg: "rgba(215,168,107,0.23)", fg: "#f2c26f" },
  medium: { bg: "rgba(203,185,148,0.18)", fg: "#e1cfaa" },
};

function OverviewReplicaStyles() {
  return (
    <style>{`
      .overview-widget-card {
        border-radius: 28px !important;
        overflow: hidden;
      }
      .overview-priority-row {
        background: rgba(255,255,255,0.075);
        border: 1px solid rgba(255,255,255,0.07);
      }
      .overview-priority-row:hover {
        background: rgba(255,255,255,0.12);
      }
    `}</style>
  );
}

function MiniSparkline() {
  return (
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="absolute bottom-8 right-7 h-11 w-24 opacity-35">
      <path d="M3 25 C18 5 25 36 42 25 S56 0 70 18 S84 34 97 22" fill="none" stroke="rgba(255,255,255,0.62)" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function MiniBars() {
  const bars = [22, 34, 46, 30, 55, 38, 68];
  return (
    <div className="absolute bottom-8 right-7 flex h-20 items-end gap-2 opacity-65">
      {bars.map((h, i) => (
        <span key={i} className="w-2.5 rounded-full" style={{ height: h, background: "rgba(210,235,220,0.74)" }} />
      ))}
    </div>
  );
}

function HoneyGlyph() {
  return (
    <div className="absolute bottom-6 right-6 flex h-16 w-16 items-center justify-center opacity-45">
      <div className="absolute inset-1 rounded-full border border-dashed" style={{ borderColor: "rgba(255,255,255,0.58)" }} />
      <div className="absolute inset-4 rounded-full border border-dashed" style={{ borderColor: "rgba(255,255,255,0.44)" }} />
      <svg width="30" height="30" viewBox="0 0 24 24" style={{ color: "rgba(218,235,224,0.78)" }} aria-hidden="true">
        <path d="M12 3 19 6.2v5.4c0 4.4-2.9 7.7-7 9.4-4.1-1.7-7-5-7-9.4V6.2L12 3Z" fill="currentColor" opacity=".55" />
        <path d="M12 10.2a1.9 1.9 0 0 0-1 3.5v2.5h2v-2.5a1.9 1.9 0 0 0-1-3.5Z" fill="rgba(44,56,53,.8)" />
      </svg>
    </div>
  );
}

/* compact stat tile — mono label up top, figure anchored to the bottom with
   the reference-style side illustration where a matching widget has one. */
function StatTile({ gc, gr, eyebrow, big, sub, visual }) {
  return (
    <MWidget gc={gc} gr={gr} pad={18} className="overview-widget-card relative">
      {visual}
      <div className="relative z-10 flex h-full flex-col">
        <MEyebrow>{eyebrow}</MEyebrow>
        <div className="mt-auto">
          <div className="text-[34px] font-semibold leading-none tabular-nums" style={{ color: "var(--on-surface-strong)" }}>{big}</div>
          <div className="mt-2 text-[12px]" style={{ color: "var(--on-surface-muted)" }}>{sub}</div>
        </div>
      </div>
    </MWidget>
  );
}

function PriorityBadge({ level }) {
  const badge = SEV_BADGE[level] || SEV_BADGE.medium;
  return (
    <span className="rounded-full px-3 py-1 font-mono text-[10px] uppercase leading-none"
      style={{ background: badge.bg, color: badge.fg, fontFamily: MONO }}>
      {level}
    </span>
  );
}

function PriorityRows({ items }) {
  return (
    <div className="flex h-full flex-col justify-center gap-2.5">
      {items.map(([t, level]) => {
        const [title, meta] = t.split(" · ");
        return (
          <div key={t} className="overview-priority-row group flex items-center gap-3 rounded-[18px] px-4 py-3 transition">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: "rgba(199,230,213,0.86)" }} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[15.5px] font-medium" style={{ color: "var(--on-surface-strong)" }}>{title}</div>
              {meta && <div className="truncate font-mono text-[10px] uppercase tracking-[0.12em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{meta}</div>}
            </div>
            <PriorityBadge level={level} />
            <Icon name="chevron-right" size={16} style={{ color: "var(--on-surface-muted)" }} />
          </div>
        );
      })}
    </div>
  );
}

function SeverityReplica({ rows }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  const litFor = (row) => {
    if (row.label === "critical") return row.value > 0 ? 1 : 0;
    if (row.label === "high") return row.value > 0 ? Math.max(1, row.value) : 0;
    return Math.round((row.value / max) * 20);
  };

  return (
    <div className="flex h-full flex-col justify-between">
      {rows.map((row) => (
        <div key={row.label}>
          <div className="mb-2 flex items-baseline justify-between">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{row.label}</span>
            <span className="text-[22px] font-semibold leading-none tabular-nums" style={{ color: "var(--on-surface-strong)" }}>{row.value}</span>
          </div>
          <MTickMeter count={20} lit={litFor(row)} color="rgba(207,236,219,0.88)" track="rgba(255,255,255,0.075)" height={20} gap={4} />
        </div>
      ))}
    </div>
  );
}

function ReferenceTrend({ open, resolved }) {
  const W = 340;
  const H = 52;
  const pad = 5;
  const values = open.concat(resolved);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const x = (i, n) => (i / (n - 1)) * W;
  const y = (value) => H - pad - ((value - min) / (max - min || 1)) * (H - pad * 2);
  const points = (series) => series.map((value, index) => `${x(index, series.length).toFixed(1)},${y(value).toFixed(1)}`).join(" ");

  return (
    <div className="flex h-full flex-col justify-center gap-2">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-[52px] w-full">
        <line x1="0" x2={W} y1="35" y2="35" stroke="rgba(255,255,255,0.30)" strokeWidth="1.2" strokeDasharray="5 6" />
        <polyline points={points(resolved)} fill="none" stroke="rgba(255,255,255,0.48)" strokeWidth="2" strokeDasharray="6 7" />
        <polyline points={points(open)} fill="none" stroke="rgba(207,236,219,0.90)" strokeWidth="2.4" strokeLinecap="round" />
        <circle cx={x(open.length - 1, open.length)} cy={y(open[open.length - 1])} r="2.5" fill="rgba(207,236,219,0.95)" />
      </svg>
      <div className="flex items-center gap-7 font-mono text-[10px] uppercase tracking-[0.16em]" style={{ color: "var(--on-surface-faint)", fontFamily: MONO }}>
        <span className="flex items-center gap-2"><span className="h-[2px] w-6 rounded-full" style={{ background: "rgba(207,236,219,0.9)" }} /> open</span>
        <span className="flex items-center gap-2"><span className="h-px w-6 border-t" style={{ borderColor: "rgba(255,255,255,0.52)", borderTopStyle: "dashed" }} /> resolved</span>
      </div>
    </div>
  );
}

function MOverview({ target = "all" }) {
  const d = overviewData(target);
  const total = d.severity.reduce((s, r) => s + r.value, 0);
  const avg = (d.week.reduce((s, w) => s + w.v, 0) / d.week.length).toFixed(1);

  return (
    <div>
      <OverviewReplicaStyles />

      {/* top meta row */}
      <div className="mb-7 flex items-center justify-between">
        <MEyebrow>Overview · {d.scope}</MEyebrow>
        <span className="font-mono text-[10px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>Thu · 12:40 · local</span>
      </div>

      {/* HERO BAND — preserved from the original prototype. */}
      <section className="mb-9 grid items-center gap-9 lg:grid-cols-[1fr_auto]">
        <div>
          <MEyebrow>Security posture · {d.scope}</MEyebrow>
          <h1 className="mt-4 text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.05] tracking-tight" style={{ color: "var(--on-surface-strong)" }}>{d.headline}</h1>
          <p className="mt-4 max-w-xl text-[16px] leading-relaxed" style={{ color: "var(--on-surface)" }}>{d.sub}</p>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <MBtn variant="primary">{d.isAll ? "See what needs you" : "Review cases"} <Icon name="arrow-right" size={16} /></MBtn>
            <MBtn variant="ghost">View activity <Icon name="arrow-right" size={14} /></MBtn>
          </div>
        </div>

        <div className="mist-tile flex items-center gap-6" style={{ borderRadius: 18, padding: 24 }}>
          <div className="flex shrink-0 flex-col items-center">
            <MRing value={d.posture.score} max={10} unit="/10" tier={d.posture.tier} size={148} />
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-[10px] uppercase tracking-[0.14em]"
              style={{ background: "rgba(255,255,255,0.10)", border: "1px solid var(--glass-border)", color: "var(--on-surface-muted)", fontFamily: MONO }}>
              ↑ {d.delta}
            </div>
          </div>
          <div className="self-stretch" style={{ width: 1, background: "linear-gradient(180deg, transparent, rgba(255,255,255,0.20), transparent)" }} />
          <div style={{ width: 236 }}>
            <div className="mb-3 flex items-baseline justify-between">
              <MEyebrow>Last 7 days</MEyebrow>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>avg {avg}</span>
            </div>
            <MPostureBars data={d.week} />
          </div>
        </div>
      </section>

      <MBento>
        {/* ANCHOR — corresponding screenshot widget, restyled as Priorities. */}
        <MWidget gc="1 / 7" gr="1 / 3" lift className="overview-widget-card" eyebrow="Priorities"
          insight={d.attention.length ? "Start at the top." : "Nothing waiting."}
          footer={<MBtn variant="ghost" className="px-0 py-0">{`Review all ${d.isAll ? total + " " : ""}cases`} <Icon name="arrow-right" size={14} /></MBtn>}>
          <PriorityRows items={d.attention} />
        </MWidget>

        {/* STAT CLUSTER — corresponding screenshot widgets. */}
        <StatTile gc="7 / 10" gr="1" {...d.tiles[0]} visual={<MiniSparkline />} />
        <StatTile gc="10 / 13" gr="1" {...d.tiles[1]} visual={<MiniBars />} />
        <StatTile gc="7 / 10" gr="2" {...d.tiles[2]} visual={<HoneyGlyph />} />

        {/* READINESS — corresponding screenshot checklist-progress widget. */}
        <MWidget gc="10 / 13" gr="2" lift pad={18} className="overview-widget-card">
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between">
              <MEyebrow>Launch readiness</MEyebrow>
              <span className="rounded-full px-3 py-1 text-[12px] font-semibold tabular-nums" style={{ background: "rgba(255,255,255,0.16)", color: "var(--on-surface-strong)" }}>{d.readiness.pct}%</span>
            </div>
            <div className="mt-auto">
              <MTickMeter count={24} value={d.readiness.pct} max={100} color="rgba(207,236,219,0.88)" track="rgba(255,255,255,0.11)" height={14} gap={4} />
              <div className="mt-3 flex items-center justify-between">
                <span className="text-[10.5px]" style={{ color: "var(--on-surface-faint)" }}>{d.readiness.label}</span>
                <span className="inline-flex items-center gap-0.5 text-[11px]" style={{ color: "var(--on-surface-muted)" }}>Go to checklist <Icon name="chevron-right" size={12} /></span>
              </div>
            </div>
          </div>
        </MWidget>

        {/* TALL — severity ladder, corresponding screenshot widget. */}
        <MWidget gc="1 / 4" gr="3 / 6" eyebrow="By severity" className="overview-widget-card"
          headRight={<div className="text-right"><div className="text-[22px] font-semibold leading-none tabular-nums" style={{ color: "var(--on-surface-strong)" }}>{total}</div><div className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>open</div></div>}>
          <SeverityReplica rows={d.severity} />
        </MWidget>

        {/* WIDE — scan coverage, corresponding screenshot widget. */}
        <MWidget gc="4 / 9" gr="3 / 5" eyebrow="Scan coverage" insight={d.coverage.insight} className="overview-widget-card">
          <div className="flex h-full items-center gap-8">
            <MRing value={d.coverage.overall} max={100} unit="%" size={120} />
            <div className="flex h-full flex-1 flex-col justify-between py-1">
              {d.coverage.items.map((it) => (
                <div key={it.label}>
                  <div className="flex items-baseline justify-between">
                    <span className="font-mono text-[10px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{it.label}</span>
                    <span className="text-[13.5px] font-semibold tabular-nums" style={{ color: "var(--on-surface)" }}>{it.pct}%</span>
                  </div>
                  <div className="mt-1.5 h-[3px] w-full overflow-hidden rounded-full" style={{ background: "rgba(255,255,255,0.10)" }}>
                    <div className="h-full rounded-full" style={{ width: `${it.pct}%`, background: "rgba(207,236,219,0.82)" }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </MWidget>

        {/* SLIM — cases-over-time, corresponding screenshot widget. */}
        <MWidget gc="4 / 9" gr="5 / 6" pad={16} eyebrow="Cases over time" className="overview-widget-card"
          headRight={<span className="inline-flex items-center gap-1 text-[12px] font-semibold tabular-nums" style={{ color: "var(--on-surface)" }}>7D <Icon name="chevron-right" size={12} style={{ transform: "rotate(90deg)" }} /></span>}>
          <ReferenceTrend open={d.line.open} resolved={d.line.resolved} />
        </MWidget>

        {/* TALL — recent activity, corresponding screenshot widget. */}
        <MWidget gc="9 / 13" gr="3 / 6" eyebrow="Recent activity" className="overview-widget-card"
          headRight={<button type="button" className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.14em]" style={{ fontFamily: MONO, color: "var(--on-surface-muted)" }}>View all <Icon name="chevron-right" size={12} /></button>}>
          <div className="flex h-full flex-col justify-between">
            {OV_ACTIVITY.map((a, i) => (
              <div key={i} className="flex items-start gap-3">
                <Icon name={a.icon} size={16} strokeWidth={1.7} className="mt-px shrink-0" style={{ color: "var(--on-surface-faint)" }} />
                <div className="min-w-0 flex-1">
                  <div className="text-[12.5px] leading-snug" style={{ color: "var(--on-surface-strong)" }}>{a.text}</div>
                  {d.isAll && <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{a.repo}</div>}
                </div>
                <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{a.t}</span>
              </div>
            ))}
          </div>
        </MWidget>

        {/* WIDE — How would you like to proceed? (restored 6-action grid, 6 cols × 2 rows). */}
        <MWidget gc="1 / 7" gr="6 / 8" eyebrow="How would you like to proceed?">
          <div className="grid h-full grid-cols-3 grid-rows-2 gap-2.5">
            {PROCEED_ACTIONS.map((a) => (
              <button key={a.title} type="button" className="flex flex-col rounded-xl px-3.5 py-3 text-left transition"
                style={{ background: "rgba(255,255,255,0.07)", border: "1px solid var(--glass-border)" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.12)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.07)"; }}>
                <Icon name={a.icon} size={18} strokeWidth={1.7} style={{ color: "var(--on-surface-muted)" }} />
                <strong className="mt-auto pt-2.5 text-[12.5px] font-medium leading-tight" style={{ color: "var(--on-surface-strong)" }}>{a.title}</strong>
                <span className="mt-0.5 text-[10.5px] leading-tight" style={{ color: "var(--on-surface-faint)" }}>{a.detail}</span>
              </button>
            ))}
          </div>
        </MWidget>

        {/* FULL WIDTH — AI follow-up action bar (12 cols × 2 rows): description
            on the left, Repository · Action · Scope across the middle, actions right. */}
        <MWidget gc="1 / 13" gr="8 / 10" eyebrow="AI follow-up">
          <div className="flex h-full flex-col justify-center gap-5 lg:flex-row lg:items-center lg:gap-10">
            <p className="shrink-0 text-[13px] leading-relaxed lg:max-w-[230px]" style={{ color: "var(--on-surface-muted)" }}>
              Hand a finding to your coding agent — it returns a verified fix for you to review and land.
            </p>
            <div className="flex flex-1 flex-col gap-4 sm:flex-row sm:items-end">
              <div className={`grid flex-1 gap-4 ${d.isAll ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>
                {[...(d.isAll ? [["Repository", AI_REPOS]] : []), ["Action", AI_ACTIONS], ["Scope", AI_SCOPES]].map(([lbl, opts]) => (
                  <label key={lbl} className="block">
                    <span className="font-mono text-[9px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{lbl}</span>
                    <div className="relative mt-1.5">
                      <select className="w-full appearance-none rounded-md px-3 py-2.5 pr-8 text-[13px] outline-none" style={{ background: "rgba(28,36,34,0.20)", border: "1px solid var(--glass-border)", color: "var(--on-surface)" }}>
                        {opts.map((o) => <option key={o}>{o}</option>)}
                      </select>
                      <Icon name="chevron-right" size={13} className="pointer-events-none absolute right-2.5 top-1/2" style={{ transform: "translateY(-50%) rotate(90deg)", color: "var(--on-surface-faint)" }} />
                    </div>
                  </label>
                ))}
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <MBtn variant="primary">Give this to your AI</MBtn>
                <MBtn variant="glass">Import AI result</MBtn>
              </div>
            </div>
          </div>
        </MWidget>

        {/* SCORE — repository-health scoreboard (6 cols × 2 rows): each repo
            gets a tick-meter health score + N/10, in DëvSec's score idiom. */}
        <MWidget gc="7 / 13" gr="6 / 8" eyebrow="Repository health">
          <div className="flex h-full flex-col">
            <div className="grid items-center gap-3 pb-2" style={{ gridTemplateColumns: "1.5fr 0.6fr 1.7fr", borderBottom: "1px solid var(--glass-border)" }}>
              <span className="font-mono text-[9px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>Repository</span>
              <span className="text-right font-mono text-[9px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>Open</span>
              <span className="font-mono text-[9px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>Health</span>
            </div>
            <div className="flex flex-1 flex-col justify-around">
              {REPO_HEALTH.map((r) => (
                <div key={r.repo} className="grid items-center gap-3" style={{ gridTemplateColumns: "1.5fr 0.6fr 1.7fr" }}>
                  <div className="flex min-w-0 items-center gap-2">
                    <Icon name="package" size={14} strokeWidth={1.7} className="shrink-0" style={{ color: "var(--on-surface-faint)" }} />
                    <span className="truncate text-[12.5px]" style={{ color: "var(--on-surface-strong)" }}>{r.repo}</span>
                  </div>
                  <span className="text-right text-[13px] tabular-nums" style={{ color: "var(--on-surface)" }}>{r.cases}</span>
                  <div className="flex items-center gap-2.5">
                    <MTickMeter count={12} value={r.score} max={10} color="rgba(255,255,255,0.85)" height={16} />
                    <span className="shrink-0 rounded px-1.5 py-0.5 text-[11px] font-semibold tabular-nums" style={{ background: "rgba(255,255,255,0.14)", color: "var(--on-surface)" }}>{r.score}/10</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </MWidget>
      </MBento>
    </div>
  );
}

Object.assign(window, { MOverview });
