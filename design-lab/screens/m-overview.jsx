/* Overview — a full-width posture hero, then a bento board of right-sized
   widgets (content fills each tile; tiles are paired by height). Mode-aware. */

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
        { eyebrow: "Open cases", big: "27", sub: "1 critical · 3 high", tone: "#d98a7a" },
        { eyebrow: "Repos affected", big: "2 / 3", sub: "2 need attention" },
        { eyebrow: "Honey keys", big: "4", sub: "armed · 0 tripped" },
        { eyebrow: "Last sweep", big: "2h", sub: "ago · 3 audits passed" },
      ],
      severity: [
        { label: "critical", value: 1, color: "#d98a7a" }, { label: "high", value: 3, color: "#d7a86b" },
        { label: "medium", value: 9, color: "#cbb994" }, { label: "low", value: 14 },
      ],
      severityInsight: "Weight sits at the bottom.",
      line: { open: [18, 17, 19, 16, 15, 14, 13, 12, 11], resolved: [4, 7, 9, 11, 12, 14, 16, 18, 20] },
      activityInsight: "You scan most weekdays.",
      coverage: { overall: 74, insight: "Config has a gap.", items: [{ label: "secrets", pct: 96 }, { label: "deps", pct: 88 }, { label: "code", pct: 71 }, { label: "config", pct: 40 }] },
      attention: [["Hardcoded AWS key · payments-api", "critical"], ["Vulnerable lodash · 2 advisories", "high"]],
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
      { label: "critical", value: 0, color: "#d98a7a" }, { label: "high", value: 1, color: "#d7a86b" },
      { label: "medium", value: 3, color: "#cbb994" }, { label: "low", value: 4 },
    ],
    severityInsight: "Mostly low-severity.",
    line: { open: [14, 13, 12, 11, 10, 9, 9, 8, 8], resolved: [3, 5, 7, 9, 10, 12, 13, 14, 15] },
    activityInsight: "Scanned daily this week.",
    coverage: { overall: 83, insight: "One gap to close.", items: [{ label: "secrets", pct: 100 }, { label: "deps", pct: 88 }, { label: "code", pct: 80 }, { label: "config", pct: 60 }] },
    attention: [["Vulnerable lodash · 2 advisories", "high"], ["Permissive CORS · internal route", "medium"]],
  };
}

const OV_ACTIVITY = [
  { icon: "circle-check", text: "Quick sweep finished — 14 cases", repo: "payments-api", t: "2h" },
  { icon: "inbox", text: "1 critical case opened", repo: "payments-api", t: "2h" },
  { icon: "wrench", text: "Case resolved — debug endpoint off", repo: "web-dashboard", t: "1d" },
  { icon: "key-round", text: "Honey key rotated", repo: "infra-terraform", t: "1d" },
];

const QUICK_ACTIONS = [
  { icon: "circle-check", t: "Run a scan" }, { icon: "package", t: "Tool catalog" },
  { icon: "file-text", t: "Reports" }, { icon: "target", t: "Add repo" },
];

function StatTile({ eyebrow, big, sub, tone }) {
  return (
    <MWidget span={1} minH={140} eyebrow={eyebrow}>
      <div className="flex h-full flex-col justify-end">
        <div className="text-[34px] font-semibold leading-none" style={{ color: "var(--on-surface-strong)" }}>{big}</div>
        <div className="mt-2 text-[12px]" style={{ color: tone || "var(--on-surface-muted)" }}>{sub}</div>
      </div>
    </MWidget>
  );
}

function MOverview({ target = "all" }) {
  const d = overviewData(target);
  return (
    <div>
      {/* HERO BAND — full width, distinct from the bento */}
      <div className="mb-7 flex items-center justify-between">
        <MEyebrow>Overview · {d.scope}</MEyebrow>
        <span className="font-mono text-[10px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>Thu · 12:40 · local</span>
      </div>

      <section className="mb-4 grid items-center gap-8 lg:grid-cols-[1fr_auto]">
        <div>
          <MEyebrow>Security posture · {d.scope}</MEyebrow>
          <h1 className="mt-4 text-[clamp(30px,3.4vw,44px)] font-semibold leading-[1.06] tracking-tight" style={{ color: "var(--on-surface-strong)" }}>{d.headline}</h1>
          <p className="mt-4 max-w-xl text-[16px] leading-relaxed" style={{ color: "var(--on-surface)" }}>{d.sub}</p>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <MBtn variant="primary">{d.isAll ? "See what needs you" : "Review cases"} <Icon name="arrow-right" size={16} /></MBtn>
            <MBtn variant="glass">View activity</MBtn>
          </div>
        </div>
        <div className="mist-glass flex items-center gap-7 rounded-[22px] px-7 py-6">
          <div className="flex shrink-0 flex-col items-center">
            <MRing value={d.posture.score} max={10} unit="/10" tier={d.posture.tier} size={132} />
            <div className="mt-2.5 font-mono text-[10px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-muted)" }}>↑ {d.delta}</div>
          </div>
          <div style={{ width: 224 }}>
            <MEyebrow className="mb-3">Last 7 days</MEyebrow>
            <MPostureBars data={d.week} />
          </div>
        </div>
      </section>

      <MBento>
        {/* stat squares — content sits to the bottom, fills the tile */}
        {d.tiles.map((t) => <StatTile key={t.eyebrow} {...t} />)}

        {/* severity + coverage (paired height) */}
        <MWidget span={2} minH={236} eyebrow="Open cases by severity" insight={d.severityInsight}>
          <div className="flex h-full items-center"><div className="w-full"><MSeverityBars rows={d.severity} /></div></div>
        </MWidget>
        <MWidget span={2} minH={236} eyebrow="Scanner coverage" insight={d.coverage.insight}>
          <div className="flex h-full items-center gap-6">
            <MRing value={d.coverage.overall} max={100} unit="%" size={104} />
            <div className="grid flex-1 grid-cols-2 gap-x-7 gap-y-4">
              {d.coverage.items.map((it) => (
                <div key={it.label}>
                  <div className="flex items-baseline justify-between">
                    <span className="font-mono text-[10px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{it.label}</span>
                    <span className="text-[13px] font-semibold" style={{ color: it.pct < 50 ? "#d7a86b" : "var(--on-surface)" }}>{it.pct}%</span>
                  </div>
                  <div className="mt-1.5 h-[3px] w-full overflow-hidden rounded-full" style={{ background: "rgba(255,255,255,0.10)" }}>
                    <div className="h-full rounded-full" style={{ width: `${it.pct}%`, background: it.pct < 50 ? "#d7a86b" : "rgba(255,255,255,0.7)" }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </MWidget>

        {/* charts (paired height) */}
        <MWidget span={2} minH={210} eyebrow="Cases over time" insight="Closing faster than they open.">
          <div className="flex h-full items-end"><div className="w-full"><MLineTrend open={d.line.open} resolved={d.line.resolved} /></div></div>
        </MWidget>
        <MWidget span={2} minH={210} eyebrow="Scan activity" insight={d.activityInsight}>
          <MHeatmap weeks={20} />
        </MWidget>

        {/* lists (paired height) */}
        <MWidget span={2} minH={220} eyebrow="Needs you first" insight={d.attention.length ? "Start at the top." : "Nothing waiting."}
          footer={<MBtn variant="ghost" className="px-0 py-0">Review all cases <Icon name="arrow-right" size={14} /></MBtn>}>
          <div className="flex h-full flex-col justify-center gap-4">
            {d.attention.map(([t, lvl]) => (
              <div key={t} className="flex items-center gap-3">
                <MSev level={lvl} />
                <span className="flex-1 truncate text-[14px]" style={{ color: "var(--on-surface)" }}>{t}</span>
                <Icon name="chevron-right" size={15} style={{ color: "var(--on-surface-ghost)" }} />
              </div>
            ))}
          </div>
        </MWidget>
        <MWidget span={2} minH={220} eyebrow="Recent activity"
          footer={<MBtn variant="ghost" className="px-0 py-0">View all</MBtn>}>
          <div className="flex h-full flex-col justify-center gap-3.5">
            {OV_ACTIVITY.map((a, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className="shrink-0" style={{ color: "var(--on-surface-muted)" }}><Icon name={a.icon} size={15} strokeWidth={1.7} /></span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13px]" style={{ color: "var(--on-surface)" }}>{a.text}</div>
                  {d.isAll && <div className="font-mono text-[10px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{a.repo}</div>}
                </div>
                <span className="shrink-0 font-mono text-[10px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{a.t}</span>
              </div>
            ))}
          </div>
        </MWidget>

        {/* hand-off + quick actions (paired height) */}
        <MWidget span={2} minH={186} eyebrow="Hand a case to your AI">
          <div className="grid h-full content-center gap-3 sm:grid-cols-2">
            {[["Action", ["Verify findings", "Fix vulnerabilities", "Create plan"]], ["Scope", ["Critical", "All open", "New since scan"]]].map(([lbl, opts]) => (
              <label key={lbl} className="block">
                <span className="font-mono text-[9px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{lbl}</span>
                <div className="relative mt-1.5">
                  <select className="w-full appearance-none rounded-lg px-3 py-2 pr-8 text-[12.5px] outline-none" style={{ background: "rgba(28,36,34,0.18)", border: "1px solid var(--glass-border)", color: "var(--on-surface)" }}>
                    {opts.map((o) => <option key={o}>{o}</option>)}
                  </select>
                  <Icon name="chevron-right" size={13} className="pointer-events-none absolute right-2.5 top-1/2" style={{ transform: "translateY(-50%) rotate(90deg)", color: "var(--on-surface-faint)" }} />
                </div>
              </label>
            ))}
            <div className="flex items-center gap-3 sm:col-span-2">
              <MBtn variant="primary">Copy prompt</MBtn>
              <MBtn variant="glass">Import result</MBtn>
            </div>
          </div>
        </MWidget>
        <MWidget span={2} minH={186} eyebrow="Quick actions">
          <div className="grid h-full grid-cols-2 content-center gap-2.5">
            {QUICK_ACTIONS.map((a) => (
              <button key={a.t} type="button" className="flex items-center gap-2.5 rounded-xl px-3 py-3 text-left text-[12.5px] transition"
                style={{ background: "var(--glass-light)", border: "1px solid var(--glass-border)", color: "var(--on-surface)" }}>
                <Icon name={a.icon} size={15} strokeWidth={1.7} style={{ color: "var(--on-surface-muted)" }} />{a.t}
              </button>
            ))}
          </div>
        </MWidget>
      </MBento>
    </div>
  );
}

Object.assign(window, { MOverview });
