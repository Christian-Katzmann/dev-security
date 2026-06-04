/* Verification — proof a case is actually closed, bound to a confirming scan. */

const CHECKS = [
  { id: "C-182", title: "Hardcoded test token removed", method: "Re-scan · secrets", status: "confirmed", proof: "scan #312" },
  { id: "C-179", title: "Debug endpoint disabled", method: "Re-scan · code", status: "confirmed", proof: "scan #317" },
  { id: "C-198", title: "Object storage policy tightened", method: "Re-scan · iac", status: "pending", proof: "needs a sweep" },
  { id: "C-201", title: "Error stack no longer exposed", method: "Manual + re-scan", status: "pending", proof: "needs a sweep" },
];

function VStatus({ status }) {
  const map = { confirmed: { c: "#8fb59e", label: "Confirmed" }, pending: { c: "#d7a86b", label: "Pending re-scan" } };
  const s = map[status] || map.pending;
  return <span className="inline-flex items-center gap-1.5 text-[12.5px]" style={{ color: "var(--on-surface-muted)" }}><MDot color={s.c} size={7} /> {s.label}</span>;
}

function MVerification() {
  const pending = CHECKS.filter((c) => c.status === "pending").length;
  return (
    <div>
      <MPageHead eyebrow="Findings" title="Verification"
        sub="A case isn't closed because someone said so — it's closed because a later scan proves the finding is gone. Closure is bound to the scan that confirmed it."
        actions={<MBtn variant="primary">Run a confirming sweep</MBtn>} />

      {pending > 0 && (
        <MGlass className="mb-6 p-5">
          <div className="flex items-center gap-3">
            <MDot color="#d7a86b" />
            <span className="text-[14px]" style={{ color: "var(--on-surface)" }}>
              {pending} resolved {pending === 1 ? "case is" : "cases are"} waiting on a confirming re-scan before they can close.
            </span>
          </div>
        </MGlass>
      )}

      <MGlass className="overflow-hidden">
        <div className="flex items-center gap-4 px-5 py-3 font-mono text-[10px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-ghost)" }}>
          <span className="w-16">Case</span><span className="flex-1">Finding</span><span className="hidden w-40 md:block">Method</span><span className="w-40">Status</span><span className="hidden w-24 text-right sm:block">Proof</span>
        </div>
        {CHECKS.map((c) => (
          <MRow key={c.id}>
            <span className="w-16 shrink-0 font-mono text-[12px]" style={{ fontFamily: MONO, color: "var(--on-surface-muted)" }}>{c.id}</span>
            <span className="min-w-0 flex-1 truncate text-[13.5px]" style={{ color: "var(--on-surface)" }}>{c.title}</span>
            <span className="hidden w-40 shrink-0 font-mono text-[11px] md:block" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{c.method}</span>
            <span className="w-40 shrink-0"><VStatus status={c.status} /></span>
            <span className="hidden w-24 shrink-0 text-right font-mono text-[11px] sm:block" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{c.proof}</span>
          </MRow>
        ))}
      </MGlass>
    </div>
  );
}

Object.assign(window, { MVerification });
