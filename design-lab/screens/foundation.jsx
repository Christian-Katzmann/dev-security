/* Screen 00 — Foundation (lab-only).
   A living style guide: renders the new dark language so it can be seen, and
   serves as the drop-in test bed for the one bright --accent. Also names the
   gaps the website kit never had to solve (semantic/severity palette), so they
   read as open design decisions rather than silent omissions. */

function FCard({ title, note, children, span = "" }) {
  return (
    <section className={`rounded-sm border border-white/10 bg-white/[0.02] p-6 ${span}`}>
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="font-mono text-[10px] uppercase tracking-[0.24em] text-white/40">{title}</h2>
        {note && <span className="text-[11px] text-white/30">{note}</span>}
      </div>
      {children}
    </section>
  );
}

const MOODS = [
  { name: "Forest Moss", use: "Home / primary", grad: "radial-gradient(circle at center,#1a3a2a,#12251c 55%,#0b1611)", accent: "#10b981", accentName: "emerald" },
  { name: "Clay Terracotta", use: "Auth", grad: "radial-gradient(circle at center,#824e2d,#4f2d19 55%,#1f1008)", accent: "#d97706", accentName: "amber" },
  { name: "Plum Sangria", use: "Docs", grad: "radial-gradient(circle at 50% 18%,#3c162f,#240b1b 50%,#10030b)", accent: "#d946ef", accentName: "fuchsia" },
  { name: "Nordic Frost", use: "Cool alt", grad: "radial-gradient(circle at center,#132838,#0b1620 55%,#04070a)", accent: "#0ea5e9", accentName: "sky" },
  { name: "Obsidian Core", use: "Minimal", grad: "radial-gradient(circle at center,#171717,#0a0a0a 55%,#020202)", accent: "#f4f4f5", accentName: "zinc" },
];

const TEXT_LADDER = [
  { v: "#ffffff", cls: "text-white", label: "fg1 · primary / headings" },
  { v: "white/62", cls: "text-white/[0.62]", label: "fg2 · body" },
  { v: "white/50", cls: "text-white/50", label: "fg3 · secondary" },
  { v: "white/36", cls: "text-white/[0.36]", label: "fg4 · meta / mono labels" },
  { v: "#71717a", cls: "text-zinc-500", label: "zinc-500 · quietest" },
];

function FoundationScreen() {
  return (
    <div className="space-y-5">
      <p className="max-w-2xl text-[15px] leading-relaxed text-white/[0.62]">
        The new DëvSec language, rendered live. This screen is the design lab's reference and
        the test bed for the one bright accent. Everything else is built on these tokens —
        change <code className="font-mono text-[12px] text-white/80">--accent</code> and it
        moves everywhere at once.
      </p>

      {/* ACCENT — the decision in flight */}
      <FCard title="Brand accent — the one bright color" note="in flight">
        <div className="grid gap-6 md:grid-cols-[auto_1fr] md:items-center">
          <div className="flex items-center gap-4">
            <div className="h-20 w-20 rounded-sm border border-white/10" style={{ background: "var(--accent)" }} />
            <div>
              <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-white/40">current</div>
              <div className="mt-1 font-mono text-[13px] text-white/80">--accent · emerald (provisional)</div>
              <div className="mt-1 text-[12px] text-white/30">replace one token in colors_and_type.css</div>
            </div>
          </div>
          <div className="space-y-3 text-[13px] text-white/[0.62]">
            <p>Where the accent shows up — kept sparse, so it stays meaningful:</p>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <span className="flex items-center gap-2"><span className="h-4 w-0.5 rounded" style={{ background: "var(--accent)" }} /> active nav</span>
              <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: "var(--accent)" }} /> live status</span>
              <a href="#" onClick={(e) => e.preventDefault()} className="underline-offset-4 hover:underline" style={{ color: "var(--accent)" }}>link / focus</a>
              <span className="font-mono text-[22px]" style={{ color: "var(--accent)" }}>14</span>
              <span className="rounded-sm px-3 py-1 text-[12px]" style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>tinted chip</span>
            </div>
            <p className="text-[12px] text-white/30">
              Bring your brighter color → I swap the token → this card and the whole shell update.
            </p>
          </div>
        </div>
      </FCard>

      {/* SEMANTIC / SEVERITY — an open decision the website never needed */}
      <FCard title="Severity & semantic palette" note="open decision — not yet defined">
        <p className="mb-4 max-w-2xl text-[13px] text-white/[0.62]">
          The website kit only has per-mood <em>atmosphere</em> accents. A security dashboard also needs a
          functional palette — critical / high / medium / low, plus success & info — that reads calm on dark and
          stays color-blind friendly. Placeholder tones below; these are a real choice to make.
        </p>
        <div className="flex flex-wrap gap-2">
          {[
            { l: "critical", c: "#f87171" }, { l: "high", c: "#fb923c" }, { l: "medium", c: "#fbbf24" },
            { l: "low", c: "#a3a3a3" }, { l: "resolved", c: "#34d399" }, { l: "info", c: "#60a5fa" },
          ].map((s) => (
            <span key={s.l} className="flex items-center gap-2 rounded-sm border border-white/10 px-3 py-1.5 text-[12px] text-white/70">
              <span className="h-2 w-2 rounded-full" style={{ background: s.c }} />{s.l}
            </span>
          ))}
        </div>
      </FCard>

      {/* MOODS */}
      <FCard title="Gradient moods" note="atmosphere, per surface">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {MOODS.map((m) => (
            <div key={m.name} className="overflow-hidden rounded-sm border border-white/10">
              <div className="h-24" style={{ background: m.grad }}>
                <div className="flex h-full items-end p-3">
                  <span className="h-3 w-3 rounded-full ring-1 ring-white/20" style={{ background: m.accent }} />
                </div>
              </div>
              <div className="space-y-0.5 p-3">
                <div className="text-[12px] text-white/80">{m.name}</div>
                <div className="font-mono text-[9.5px] uppercase tracking-[0.16em] text-white/30">{m.use} · {m.accentName}</div>
              </div>
            </div>
          ))}
        </div>
      </FCard>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* TYPE */}
        <FCard title="Type scale" note="Plus Jakarta Sans · JetBrains Mono">
          <div className="space-y-4">
            <div className="display-hero" style={{ fontSize: 44 }}>Sëcure</div>
            <div className="h2">A calmer way to see what your repo needs</div>
            <div className="body-lg">Body large — descriptions and lead paragraphs sit at this comfortable, slightly-wide setting.</div>
            <div className="body">Body — the default reading size for dense dashboard copy and table content.</div>
            <div className="mono-label">DËVSEC // MONO LABEL · THE SIGNATURE MOVE</div>
            <div className="code">$ security-scan .  <span className="text-white/30"># honest, local-first</span></div>
          </div>
        </FCard>

        {/* TEXT LADDER */}
        <FCard title="Text — white-opacity ladder" note="never raw #fff/#000 in product">
          <div className="space-y-3">
            {TEXT_LADDER.map((t) => (
              <div key={t.label} className="flex items-baseline justify-between gap-4">
                <span className={`text-[15px] ${t.cls}`}>The quick brown fox</span>
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/30">{t.v}</span>
              </div>
            ))}
          </div>
        </FCard>

        {/* CONTROLS */}
        <FCard title="Buttons" note="press = active:scale-95">
          <div className="flex flex-wrap items-center gap-3">
            <button className="rounded-sm bg-white px-4 py-2.5 text-[13px] font-medium text-black shadow-xl transition hover:shadow-white/10 active:scale-95">Primary</button>
            <button className="rounded-sm border border-white/20 px-4 py-2.5 text-[13px] text-white/85 transition hover:border-white/40 hover:text-white active:scale-95">Secondary</button>
            <button className="rounded-sm px-4 py-2.5 text-[13px] text-white/55 transition hover:bg-white/[0.06] hover:text-white active:scale-95">Ghost</button>
            <button className="flex items-center gap-2 rounded-sm px-2 py-2 text-[13px] text-white/70 transition hover:text-white">
              Open repo <Icon name="arrow-right" size={15} />
            </button>
          </div>
        </FCard>

        {/* INPUT */}
        <FCard title="Input" note="mono label · sharp field">
          <label className="block">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">Workspace path</span>
            <input
              type="text" defaultValue="~/Dev/Projects/dev-security"
              className="mt-2 w-full rounded-sm border border-white/15 bg-black/30 px-3 py-2.5 font-mono text-[13px] text-white/85 outline-none transition focus:border-[color:var(--accent-line)]"
              style={{ caretColor: "var(--accent)" }}
            />
          </label>
        </FCard>
      </div>

      {/* TERMINAL */}
      <FCard title="Terminal" note="honest local commands · 16px grid">
        <div className="overflow-hidden rounded-sm border border-white/25 bg-black/40"
          style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.03) 1px,transparent 1px)", backgroundSize: "16px 16px" }}>
          <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2.5">
            <Icon name="terminal" size={14} className="text-white/50" />
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">SYS.TERMINAL // CORE_SCAN</span>
          </div>
          <pre className="overflow-x-auto p-4 font-mono text-[12.5px] leading-relaxed text-white/80">
{`$ git clone … && cd dev-security
$ security-scan .
  → 41 findings · 14 cases · 0 secrets leaked
  → report: ~/.security-observatory/reports/2026-06-04.html`}
          </pre>
        </div>
      </FCard>

      {/* SURFACES */}
      <div className="grid gap-5 lg:grid-cols-2">
        <FCard title="Borders — hairline ladder">
          <div className="space-y-2">
            {[["white/5", "border-white/5"], ["white/10", "border-white/10"], ["white/20", "border-white/20"], ["white/25", "border-white/25"]].map(([l, c]) => (
              <div key={l} className={`flex items-center justify-between rounded-sm border ${c} bg-white/[0.02] px-4 py-2.5`}>
                <span className="text-[13px] text-white/70">surface</span>
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/30">{l}</span>
              </div>
            ))}
          </div>
        </FCard>
        <FCard title="Radii — mostly sharp" note="4px on controls only">
          <div className="flex items-end gap-4">
            {[["none", "rounded-none", "panels / terminal"], ["4px", "rounded-sm", "controls"], ["full", "rounded-full", "dots only"]].map(([l, c, u]) => (
              <div key={l} className="text-center">
                <div className={`h-16 w-16 border border-white/20 bg-white/[0.04] ${c}`} />
                <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.14em] text-white/40">{l}</div>
                <div className="text-[10px] text-white/25">{u}</div>
              </div>
            ))}
          </div>
        </FCard>
      </div>
    </div>
  );
}

Object.assign(window, { FoundationScreen });
