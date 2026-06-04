/* Activity — a calm chronological feed of what the system did. */

const ACTIVITY = [
  { day: "Today", items: [
    { t: "14:02", icon: "circle-check", kind: "scan", text: "Quick sweep finished — 41 findings, 14 cases", meta: "scan #318" },
    { t: "14:02", icon: "inbox", kind: "case", text: "2 new medium cases opened", meta: "C-203, C-204" },
    { t: "09:30", icon: "key-round", kind: "honey", text: "Honey key checked — still armed", meta: "config/.env.sample" },
  ]},
  { day: "Yesterday", items: [
    { t: "18:11", icon: "wrench", kind: "case", text: "Case resolved — debug endpoint disabled", meta: "C-179" },
    { t: "11:48", icon: "circle-check", kind: "scan", text: "Full audit finished — no critical findings", meta: "scan #317" },
    { t: "11:20", icon: "inbox", kind: "case", text: "Case moved to in progress", meta: "C-198" },
  ]},
  { day: "Mon, Jun 1", items: [
    { t: "16:05", icon: "key-round", kind: "honey", text: "Honey key rotated", meta: "tests/fixtures/auth.json" },
    { t: "15:52", icon: "wrench", kind: "case", text: "Case resolved — hardcoded token removed", meta: "C-182" },
  ]},
];

const ACT_FILTERS = [{ id: "all", label: "All" }, { id: "scan", label: "Scanner runs" }, { id: "case", label: "Cases" }, { id: "honey", label: "Honey keys" }];

function MActivity() {
  const [filter, setFilter] = React.useState("all");
  return (
    <div>
      <MPageHead eyebrow="Posture" title="Activity"
        sub="Everything the scanner, cases, and tripwires have done — newest first." />
      <div className="mb-6"><MFilters items={ACT_FILTERS} active={filter} onChange={setFilter} /></div>

      <div className="space-y-8">
        {ACTIVITY.map((group) => {
          const items = group.items.filter((it) => filter === "all" || it.kind === filter);
          if (!items.length) return null;
          return (
            <div key={group.day}>
              <MEyebrow className="mb-3">{group.day}</MEyebrow>
              <MGlass className="overflow-hidden">
                {items.map((it, i) => (
                  <MRow key={i} className={i === 0 ? "border-t-0" : ""}>
                    <span className="w-12 shrink-0 font-mono text-[11px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{it.t}</span>
                    <span className="shrink-0" style={{ color: "var(--on-surface-muted)" }}><Icon name={it.icon} size={16} strokeWidth={1.7} /></span>
                    <span className="min-w-0 flex-1 truncate text-[13.5px]" style={{ color: "var(--on-surface)" }}>{it.text}</span>
                    <span className="hidden shrink-0 font-mono text-[11px] sm:block" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{it.meta}</span>
                  </MRow>
                ))}
              </MGlass>
            </div>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { MActivity });
