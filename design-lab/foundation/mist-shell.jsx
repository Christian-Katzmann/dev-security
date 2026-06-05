/* MistShell — the shared desktop chrome for every product screen.
   Grey canvas + quiet left nav + a CENTERED, max-width content column so the
   layout stays proportioned from a laptop to a 32" monitor (the cap is the fix
   for content stretching edge-to-edge on huge displays). */

const SHELL_SANS = '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Geist", Inter, system-ui, sans-serif';

function MistNavItem({ item, active, onNavigate }) {
  const on = item.id === active;
  return (
    <button type="button" onClick={() => onNavigate(item.id)}
      aria-current={on ? "page" : undefined}
      className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-[13.5px] transition"
      style={{ color: on ? "var(--on-surface-strong)" : "var(--on-surface-faint)", background: on ? "var(--glass-light)" : "transparent" }}
      onMouseEnter={(e) => { if (!on) e.currentTarget.style.color = "var(--on-surface-muted)"; }}
      onMouseLeave={(e) => { if (!on) e.currentTarget.style.color = "var(--on-surface-faint)"; }}>
      <Icon name={item.icon} size={17} strokeWidth={1.7} style={{ opacity: on ? 0.95 : 0.65 }} />
      <span className="tracking-wide">{item.label}</span>
    </button>
  );
}

function MistShell({ groups, active, activeId, onNavigate, children, target = "all", onTarget, repos = [] }) {
  return (
    <div className="relative min-h-screen w-full" style={{ fontFamily: SHELL_SANS, color: "var(--on-surface)" }}>
      {/* grey canvas sized to the full content box */}
      <div className="mist-canvas" style={{ position: "absolute", inset: 0, zIndex: 0 }} />

      <div className="relative z-10 flex min-h-screen">
        {/* quiet nav */}
        <aside className="hidden w-60 shrink-0 flex-col px-4 py-7 lg:flex" style={{ borderRight: "1px solid var(--glass-border)" }}>
          <div className="flex items-center gap-3 px-3 pb-5">
            <FocusLogo size={20} color="#ffffff" />
            <span className="text-[15px] font-medium tracking-wide" style={{ color: "var(--on-surface-strong)" }}>DëvSec</span>
          </div>

          {/* workspace scope: all repositories ↔ a single repo */}
          <div className="mb-6 px-3">
            <div className="mb-1.5 font-mono text-[9px] uppercase tracking-[0.22em]" style={{ color: "var(--on-surface-ghost)", fontFamily: MONO }}>Workspace</div>
            <div className="relative">
              <select value={target} onChange={(e) => onTarget && onTarget(e.target.value)}
                className="w-full appearance-none rounded-md px-3 py-2 pr-8 text-[13px] outline-none transition"
                style={{ background: "rgba(255,255,255,0.10)", border: "1px solid var(--glass-border)", color: "var(--on-surface)" }}>
                <option value="all">All repositories</option>
                {repos.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <Icon name="chevron-right" size={14} className="pointer-events-none absolute right-2.5 top-1/2"
                style={{ transform: "translateY(-50%) rotate(90deg)", color: "var(--on-surface-faint)" }} />
            </div>
            <button type="button" onClick={() => onTarget && onTarget("__add__")}
              className="mt-2 flex w-full items-center gap-2 rounded-md px-3 py-2 text-[12.5px] transition"
              style={{ color: "var(--on-surface-muted)", border: "1px solid var(--glass-border)" }}>
              <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> Add repository
            </button>
          </div>

          <nav className="flex-1 space-y-6 overflow-y-auto">
            {groups.map((g) => (
              <div key={g.label} className="space-y-0.5">
                <div className="px-3 pb-1.5 font-mono text-[9.5px] uppercase tracking-[0.22em]" style={{ color: "var(--on-surface-ghost)", fontFamily: MONO }}>{g.label}</div>
                {g.items.map((it) => <MistNavItem key={it.id} item={it} active={activeId} onNavigate={onNavigate} />)}
              </div>
            ))}
          </nav>

          <div className="mt-6 flex items-center gap-2 px-3">
            <MDot color="#8fb59e" size={6} />
            <span className="font-mono text-[10px] uppercase tracking-[0.18em]" style={{ color: "var(--on-surface-faint)", fontFamily: MONO }}>local · offline</span>
          </div>
        </aside>

        {/* content — centered + capped so it stays proportioned on large displays */}
        <main className="flex-1 overflow-y-auto px-6 py-10 lg:px-12 lg:py-12">
          <div className="mx-auto w-full" style={{ maxWidth: 1180 }}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}

Object.assign(window, { MistShell });
