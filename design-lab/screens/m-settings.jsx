/* Settings — workspace, scan profiles, preferences. The form archetype. */

const PROFILES = [
  { id: "quick", label: "Quick safety sweep", d: "Fast pass across all categories", on: true },
  { id: "secrets", label: "Leaked secrets", d: "gitleaks · TruffleHog" },
  { id: "code", label: "Code vulnerabilities", d: "Semgrep" },
  { id: "deps", label: "Dependency risks", d: "Trivy · pip-audit" },
  { id: "iac", label: "Infrastructure exposure", d: "Trivy · Checkov" },
  { id: "full", label: "Full repo audit", d: "Everything, deepest pass" },
];

function MToggle({ on }) {
  return (
    <span className="relative inline-block h-5 w-9 rounded-full transition"
      style={{ background: on ? "var(--glass-lightest)" : "var(--glass-light)", border: "1px solid var(--glass-border)" }}>
      <span className="absolute top-0.5 h-3.5 w-3.5 rounded-full transition-all"
        style={{ left: on ? 18 : 3, background: on ? "var(--mist-700)" : "rgba(255,255,255,0.75)" }} />
    </span>
  );
}

function SettingSection({ label, children }) {
  return (
    <div>
      <MEyebrow className="mb-3">{label}</MEyebrow>
      <MGlass className="overflow-hidden">{children}</MGlass>
    </div>
  );
}

function MSettings() {
  return (
    <div>
      <MPageHead eyebrow="System" title="Settings"
        sub="Where DëvSec looks, what it runs, and how it tells you. All local." />

      <div className="space-y-8">
        <SettingSection label="Workspace">
          <div className="p-5">
            <label className="block">
              <span className="font-mono text-[10px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>Target repository</span>
              <input type="text" defaultValue="~/Dev/Projects/dev-security"
                className="mt-2 w-full rounded-xl px-3.5 py-3 font-mono text-[13px] outline-none transition"
                style={{ background: "rgba(28,36,34,0.18)", border: "1px solid var(--glass-border)", color: "var(--on-surface)", fontFamily: MONO }} />
            </label>
          </div>
        </SettingSection>

        <SettingSection label="Scan profiles">
          {PROFILES.map((p, i) => (
            <div key={p.id} className="flex items-center gap-4 px-5 py-3.5" style={i ? { borderTop: "1px solid var(--on-surface-ghost)" } : {}}>
              <div className="flex-1">
                <div className="flex items-center gap-2.5">
                  <span className="text-[14px]" style={{ color: "var(--on-surface)" }}>{p.label}</span>
                  {p.on && <span className="rounded-full px-2 py-0.5 text-[10px]" style={{ background: "var(--glass-lightest)", color: "var(--mist-700)" }}>default</span>}
                </div>
                <div className="mt-0.5 text-[12px]" style={{ color: "var(--on-surface-faint)" }}>{p.d}</div>
              </div>
              <MToggle on={p.on} />
            </div>
          ))}
        </SettingSection>

        <SettingSection label="Preferences">
          {[
            ["Keep local report history", "Stored in SQLite — never uploaded", true],
            ["Notify on a new high or critical case", "Quietly, only when it matters", true],
            ["Plant honey keys on each scan", "Refresh tripwires automatically", false],
          ].map(([t, d, on], i) => (
            <div key={t} className="flex items-center gap-4 px-5 py-4" style={i ? { borderTop: "1px solid var(--on-surface-ghost)" } : {}}>
              <div className="flex-1">
                <div className="text-[14px]" style={{ color: "var(--on-surface)" }}>{t}</div>
                <div className="mt-0.5 text-[12px]" style={{ color: "var(--on-surface-faint)" }}>{d}</div>
              </div>
              <MToggle on={on} />
            </div>
          ))}
        </SettingSection>
      </div>
    </div>
  );
}

Object.assign(window, { MSettings });
