/* DëvSec Design Lab — the dashboard shell.
   This is NET-NEW design: the website's centered pill-nav can't hold a
   10-section product, so the dashboard gets a left nav rail + top bar, dressed
   in the new dark language (Forest-Moss mood, hairline borders, mono labels,
   the one bright --accent on the active item). Every screen renders inside it. */

/* Persistent shell mood. Forest Moss is the primary brand gradient; the lab
   keeps it constant so the frame reads as "home base" while screens evolve. */
const SHELL_BG = "radial-gradient(circle at 22% 0%, #1a3a2a 0%, #12251c 46%, #0b1611 100%)";

function StatusDot({ status }) {
  if (status === "ready") return <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--accent)" }} />;
  if (status === "lab") return <span className="h-1.5 w-1.5 rounded-full bg-white/40" />;
  return <span className="h-1.5 w-1.5 rounded-full border border-white/20" />;
}

function NavItem({ item, active, onNavigate }) {
  const isActive = active === item.id;
  return (
    <button
      type="button"
      onClick={() => onNavigate(item.id)}
      aria-current={isActive ? "page" : undefined}
      className={`group relative flex w-full items-center gap-3 rounded-sm px-3 py-2 text-left text-[13px] transition
        ${isActive ? "bg-white/[0.06] text-white" : "text-white/55 hover:bg-white/[0.03] hover:text-white/90"}`}
    >
      {/* active accent bar — the one bright color, used sparingly */}
      <span
        className="absolute left-0 top-1/2 h-5 -translate-y-1/2 rounded-full transition-all"
        style={{ width: isActive ? 2 : 0, background: "var(--accent)" }}
      />
      <Icon name={item.icon} size={17} strokeWidth={1.7}
        className={isActive ? "opacity-90" : "opacity-60 group-hover:opacity-80"} />
      <span className="flex-1 truncate tracking-wide">{item.label}</span>
      {item.status === "todo"
        ? <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-white/25">soon</span>
        : <StatusDot status={item.status} />}
    </button>
  );
}

function NavRail({ groups, active, onNavigate }) {
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-white/5 md:flex">
      {/* brand */}
      <div className="flex items-center gap-3 px-5 pb-6 pt-6">
        <FocusLogo size={20} color="#ffffff" />
        <span className="font-display text-[15px] font-medium tracking-wide text-white">DëvSec</span>
        <span className="ml-auto font-mono text-[9px] uppercase tracking-[0.22em] text-white/30"
          style={{ color: "var(--accent)" }}>lab</span>
      </div>

      {/* groups */}
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 pb-6">
        {groups.map((group) => (
          <div key={group.label} className="space-y-1">
            <div className="px-3 pb-1 font-mono text-[9.5px] uppercase tracking-[0.24em] text-white/30">
              {group.label}
            </div>
            {group.items.map((item) => (
              <NavItem key={item.id} item={item} active={active} onNavigate={onNavigate} />
            ))}
          </div>
        ))}
      </nav>

      {/* rail footer — sample shell chrome (target repo + scan freshness) */}
      <div className="border-t border-white/5 px-5 py-4">
        <div className="flex items-center gap-2 text-white/55">
          <Icon name="target" size={14} strokeWidth={1.7} className="opacity-60" />
          <span className="font-mono text-[11px] tracking-wide text-white/70">dev-security</span>
        </div>
        <div className="mt-1 font-mono text-[9.5px] uppercase tracking-[0.18em] text-white/30">
          last sweep · 2h ago · sample
        </div>
      </div>
    </aside>
  );
}

function TopBar({ active }) {
  const isLab = active.kind === "lab";
  return (
    <header className="flex items-start justify-between gap-6 border-b border-white/5 px-6 py-6 lg:px-10">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-white/36">
          DËVSEC // {active.label}
        </div>
        <h1 className="mt-2 font-display text-[26px] font-medium leading-tight tracking-tight text-white">
          {active.title || active.label}
        </h1>
      </div>
      <div className="hidden shrink-0 items-center gap-3 sm:flex">
        {!isLab && (
          <span className="flex items-center gap-2 rounded-sm border border-white/10 px-3 py-2 text-white/55">
            <Icon name="target" size={14} strokeWidth={1.7} className="opacity-60" />
            <span className="font-mono text-[11px] tracking-wide">dev-security</span>
          </span>
        )}
        {isLab ? (
          <span className="rounded-sm border px-3 py-2 font-mono text-[10px] uppercase tracking-[0.2em]"
            style={{ borderColor: "var(--accent-line)", color: "var(--accent)" }}>
            design lab
          </span>
        ) : (
          <button type="button"
            className="rounded-sm bg-white px-4 py-2.5 text-[13px] font-medium text-black shadow-xl transition hover:shadow-white/10 active:scale-95">
            Run safety sweep
          </button>
        )}
      </div>
    </header>
  );
}

function Shell({ groups, active, activeId, onNavigate, children }) {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[#07070a] font-sans text-zinc-100 antialiased selection:bg-white/20 selection:text-white">
      {/* mood layers — gradient, top sheen, bottom shade, film grain */}
      <div className="fixed inset-0 z-0" style={{ background: SHELL_BG }} />
      <div className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(ellipse_at_top,rgba(255,255,255,0.06),transparent_50%)]" />
      <div className="pointer-events-none fixed inset-0 z-0 bg-gradient-to-b from-transparent via-black/10 to-black/30" />
      <div className="bg-grain pointer-events-none fixed inset-0 z-0 mix-blend-overlay" />

      <div className="relative z-10 flex min-h-screen">
        <NavRail groups={groups} active={activeId} onNavigate={onNavigate} />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar active={active} />
          <main className="animate-fade-in flex-1 overflow-y-auto px-6 py-8 lg:px-10 lg:py-10">
            <div className="mx-auto w-full max-w-6xl">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Shell });
