/* Cases — the dense list. The real test of whether grey-forward holds for data.
   Calm even when dense: severity is a small dot, hierarchy is the alpha ladder,
   one row per case, generous row height, hairline dividers. */

const CASES = [
  { id: "C-204", sev: "medium", title: "Outdated dependency with a known CVE", cat: "dependencies", path: "lodash@4.17.11", state: "open", age: "2h" },
  { id: "C-203", sev: "medium", title: "Permissive CORS allows any origin", cat: "code", path: "src/api/server.py:42", state: "open", age: "2h" },
  { id: "C-201", sev: "low", title: "Verbose error stack exposed in 500 response", cat: "code", path: "src/api/handlers.py:88", state: "verified", age: "1d" },
  { id: "C-198", sev: "medium", title: "Object storage policy is world-readable (sample)", cat: "infrastructure", path: "infra/s3.tf:7", state: "in_progress", age: "1d" },
  { id: "C-195", sev: "low", title: "Container image runs as root", cat: "infrastructure", path: "Dockerfile:12", state: "open", age: "1d" },
  { id: "C-190", sev: "low", title: "Missing rate limit on the login route", cat: "code", path: "src/api/auth.py:15", state: "accepted_risk", age: "5d" },
  { id: "C-188", sev: "low", title: "Dependency is two majors behind", cat: "dependencies", path: "requests", age: "2h", state: "open" },
  { id: "C-182", sev: "resolved", title: "Hardcoded test token in a fixture", cat: "secrets", path: "tests/fixtures/auth.json", state: "resolved", age: "3d" },
  { id: "C-179", sev: "resolved", title: "Debug endpoint left enabled", cat: "code", path: "src/api/debug.py:3", state: "resolved", age: "6d" },
];

const CASE_FILTERS = [
  { id: "all", label: "All" }, { id: "open", label: "Open" }, { id: "verified", label: "Verified" },
  { id: "in_progress", label: "In progress" }, { id: "accepted_risk", label: "Accepted" }, { id: "resolved", label: "Resolved" },
];

function MCases() {
  const [filter, setFilter] = React.useState("all");
  const rows = CASES.filter((c) => filter === "all" || c.state === filter);
  const openCount = CASES.filter((c) => c.state === "open").length;

  return (
    <div>
      <MPageHead
        eyebrow="Findings"
        title="Cases"
        sub="Scanner noise, triaged into a short list of next actions. Each case carries its evidence, a fix direction, and an agent-ready handoff."
        actions={<MBtn variant="primary">Run a sweep</MBtn>}
      />

      {/* quiet summary strip */}
      <div className="mb-5 flex flex-wrap items-center gap-x-7 gap-y-2 text-[13px]" style={{ color: "var(--on-surface-muted)" }}>
        <span><span className="text-[15px] font-semibold" style={{ color: "var(--on-surface-strong)" }}>{openCount}</span> open</span>
        <span className="inline-flex items-center gap-1.5"><MSev level="critical" /> 0 critical</span>
        <span className="inline-flex items-center gap-1.5"><MSev level="high" /> 0 high</span>
        <span className="inline-flex items-center gap-1.5"><MSev level="medium" /> 2 medium</span>
        <span className="ml-auto font-mono text-[11px] tracking-wide" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>last sweep · 2h ago</span>
      </div>

      <div className="mb-4"><MFilters items={CASE_FILTERS} active={filter} onChange={setFilter} /></div>

      {/* the list */}
      <MGlass className="overflow-hidden">
        {rows.map((c, i) => (
          <MRow key={c.id} onClick={() => {}} className={i === 0 ? "border-t-0" : ""}>
            <span className="w-2 shrink-0"><MSev level={c.sev} /></span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[14px]" style={{ color: "var(--on-surface)" }}>{c.title}</div>
              <div className="mt-1 flex items-center gap-2 font-mono text-[11px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>
                <span>{c.id}</span><span>·</span><span>{c.cat}</span><span>·</span><span className="truncate">{c.path}</span>
              </div>
            </div>
            <div className="hidden shrink-0 sm:block"><MState state={c.state} /></div>
            <span className="w-10 shrink-0 text-right font-mono text-[11px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{c.age}</span>
            <Icon name="chevron-right" size={16} className="shrink-0" style={{ color: "var(--on-surface-ghost)" }} />
          </MRow>
        ))}
        {rows.length === 0 && (
          <div className="px-5 py-12 text-center text-[13px]" style={{ color: "var(--on-surface-faint)" }}>No cases in this state.</div>
        )}
      </MGlass>
    </div>
  );
}

Object.assign(window, { MCases });
