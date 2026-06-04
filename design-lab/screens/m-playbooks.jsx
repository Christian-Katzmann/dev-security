/* Recovery playbooks — per-category steps with an agent-ready handoff. */

const PLAYBOOKS = [
  { id: "secrets", icon: "key-round", title: "Leaked secret", steps: 5, blurb: "Rotate, revoke, purge history, verify." },
  { id: "deps", icon: "package", title: "Vulnerable dependency", steps: 4, blurb: "Pin, upgrade, re-lock, re-scan." },
  { id: "code", icon: "wrench", title: "Code vulnerability", steps: 4, blurb: "Patch, test, review, land." },
  { id: "iac", icon: "package", title: "Infrastructure exposure", steps: 5, blurb: "Tighten policy, re-plan, apply, confirm." },
];

const STEPS = [
  "Revoke the exposed credential at the provider.",
  "Rotate to a fresh secret and update the local store.",
  "Purge the value from git history (filter-repo).",
  "Plant a honey key in its place to catch reuse.",
  "Re-scan to confirm the secret is gone.",
];

function MPlaybooks() {
  const [active, setActive] = React.useState("secrets");
  return (
    <div>
      <MPageHead eyebrow="Act" title="Recovery playbooks"
        sub="When something is wrong, the calm, ordered steps to make it right — each ready to hand to an agent." />

      <div className="grid gap-5 lg:grid-cols-[1fr_1.3fr]">
        {/* category list */}
        <div className="space-y-3">
          {PLAYBOOKS.map((p) => {
            const on = p.id === active;
            return (
              <button key={p.id} type="button" onClick={() => setActive(p.id)} className="block w-full text-left">
                <MGlass hover className="p-4" style={on ? { background: "rgba(255,255,255,0.20)" } : {}}>
                  <div className="flex items-center gap-3">
                    <span style={{ color: "var(--on-surface-muted)" }}><Icon name={p.icon} size={18} strokeWidth={1.7} /></span>
                    <div className="flex-1">
                      <div className="text-[14px]" style={{ color: "var(--on-surface)" }}>{p.title}</div>
                      <div className="text-[12px]" style={{ color: "var(--on-surface-faint)" }}>{p.blurb}</div>
                    </div>
                    <span className="font-mono text-[11px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{p.steps} steps</span>
                  </div>
                </MGlass>
              </button>
            );
          })}
        </div>

        {/* steps */}
        <MGlass className="p-6">
          <MEyebrow className="mb-5">Leaked secret · recovery</MEyebrow>
          <ol className="space-y-4">
            {STEPS.map((s, i) => (
              <li key={i} className="flex gap-4">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-[11px]"
                  style={{ background: "var(--glass-light)", border: "1px solid var(--glass-border)", color: "var(--on-surface-muted)", fontFamily: MONO }}>{i + 1}</span>
                <span className="pt-0.5 text-[14px] leading-relaxed" style={{ color: "var(--on-surface)" }}>{s}</span>
              </li>
            ))}
          </ol>
          <div className="mt-6 flex items-center gap-3" style={{ borderTop: "1px solid var(--on-surface-ghost)", paddingTop: 20 }}>
            <MBtn variant="primary">Copy agent handoff</MBtn>
            <MBtn variant="ghost">View as markdown</MBtn>
          </div>
        </MGlass>
      </div>
    </div>
  );
}

Object.assign(window, { MPlaybooks });
