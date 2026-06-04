/* Agent lab — the MCP surface coding agents use, read vs guarded-write. */

const READ_TOOLS = ["list_cases", "get_case", "scan_history", "scan_diff", "tool_catalog", "honey_key_status"];
const WRITE_TOOLS = [
  { n: "follow_up / preview / apply", d: "case resolution trio" },
  { n: "trigger_scan", d: "rate-limited, local-offline rescan" },
  { n: "propose_fix", d: "draft a patch for a case" },
  { n: "clean_room_review_packet", d: "diff + invariants only" },
  { n: "record_clean_room_review", d: "log the verdict" },
  { n: "land_fix", d: "apply an approved patch" },
];

function MAgentLab() {
  return (
    <div>
      <MPageHead eyebrow="Catalog" title="Agent lab"
        sub="The MCP tools a coding agent can use against your scan history. Read is the default; write is a separate, guarded adapter." />

      <div className="grid gap-5 lg:grid-cols-2">
        <MGlass className="p-6">
          <div className="mb-4 flex items-center justify-between">
            <MEyebrow>Read tools</MEyebrow>
            <span className="font-mono text-[11px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>11 · default</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {READ_TOOLS.map((t) => (
              <span key={t} className="rounded-lg px-2.5 py-1.5 font-mono text-[11.5px]" style={{ fontFamily: MONO, background: "var(--glass-light)", border: "1px solid var(--glass-border)", color: "var(--on-surface-muted)" }}>{t}</span>
            ))}
            <span className="px-1.5 py-1.5 text-[11.5px]" style={{ color: "var(--on-surface-faint)" }}>+5 more</span>
          </div>
          <p className="mt-4 text-[12.5px]" style={{ color: "var(--on-surface-faint)" }}>Stdio-only · no network port · cannot change anything.</p>
        </MGlass>

        <MGlass className="p-6">
          <div className="mb-4 flex items-center justify-between">
            <MEyebrow>Write tools</MEyebrow>
            <span className="inline-flex items-center gap-1.5 font-mono text-[11px]" style={{ fontFamily: MONO, color: "var(--on-surface-muted)" }}>
              <MDot color="#d7a86b" size={6} /> 8 · guarded
            </span>
          </div>
          <div className="space-y-2.5">
            {WRITE_TOOLS.map((t) => (
              <div key={t.n} className="flex items-baseline justify-between gap-4">
                <span className="font-mono text-[12px]" style={{ fontFamily: MONO, color: "var(--on-surface)" }}>{t.n}</span>
                <span className="shrink-0 text-[11.5px]" style={{ color: "var(--on-surface-faint)" }}>{t.d}</span>
              </div>
            ))}
          </div>
        </MGlass>
      </div>

      <MGlass className="mt-5 p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 shrink-0" style={{ color: "var(--on-surface-muted)" }}><Icon name="shield-check" size={18} strokeWidth={1.7} /></span>
          <p className="text-[13.5px] leading-relaxed" style={{ color: "var(--on-surface)" }}>
            Suppressing a high or critical case never auto-applies — it's held for explicit human confirmation. And the clean-room reviewer only ever sees the diff and the invariants, never the finding text.
          </p>
        </div>
      </MGlass>
    </div>
  );
}

Object.assign(window, { MAgentLab });
