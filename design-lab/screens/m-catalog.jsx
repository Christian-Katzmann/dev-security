/* Tool catalog — the open-source scanners DëvSec orchestrates, with trust. */

const TOOLS = [
  { name: "gitleaks", cat: "secrets", state: "installed", score: "8.6", fresh: "updated 3d ago" },
  { name: "Semgrep", cat: "code", state: "installed", score: "9.1", fresh: "updated 1w ago" },
  { name: "Trivy", cat: "dependencies · iac", state: "installed", score: "9.0", fresh: "updated 2d ago" },
  { name: "pip-audit", cat: "dependencies", state: "installed", score: "8.2", fresh: "updated 5d ago" },
  { name: "Checkov", cat: "infrastructure", state: "available", score: "8.4", fresh: "not installed" },
  { name: "TruffleHog", cat: "secrets", state: "available", score: "8.0", fresh: "not installed" },
];

function ToolState({ state }) {
  const installed = state === "installed";
  return (
    <span className="inline-flex items-center gap-1.5 text-[11.5px]" style={{ color: "var(--on-surface-muted)" }}>
      <MDot color={installed ? "#8fb59e" : "rgba(255,255,255,0.35)"} size={6} /> {installed ? "Installed" : "Available"}
    </span>
  );
}

function MCatalog() {
  return (
    <div>
      <MPageHead eyebrow="Catalog" title="Tool catalog"
        sub="The established open-source scanners DëvSec runs for you — with a trust score and freshness, so you know what's reading your code." />

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {TOOLS.map((t) => (
          <MGlass key={t.name} hover className="p-5">
            <div className="flex items-start justify-between">
              <span style={{ color: "var(--on-surface-muted)" }}><Icon name="package" size={20} strokeWidth={1.7} /></span>
              <ToolState state={t.state} />
            </div>
            <div className="mt-4 text-[15px]" style={{ color: "var(--on-surface-strong)" }}>{t.name}</div>
            <div className="mt-1 font-mono text-[10.5px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{t.cat}</div>
            <div className="mt-4 flex items-center justify-between text-[12px]" style={{ color: "var(--on-surface-muted)" }}>
              <span>OpenSSF {t.score}</span>
              <span style={{ color: "var(--on-surface-faint)" }}>{t.fresh}</span>
            </div>
          </MGlass>
        ))}
      </div>

      <p className="mt-6 text-[12.5px]" style={{ color: "var(--on-surface-faint)" }}>
        Curated packs are browse-only for now — one-click install of full packs isn't enabled yet.
      </p>
    </div>
  );
}

Object.assign(window, { MCatalog });
