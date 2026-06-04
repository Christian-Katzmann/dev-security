/* Code fixes — propose → clean-room review → land. The reviewer sees only the
   diff + invariants, never the finding text. */

const DIFF = [
  { t: "ctx", s: "  app.add_middleware(" },
  { t: "del", s: "      CORSMiddleware, allow_origins=[\"*\"]," },
  { t: "add", s: "      CORSMiddleware, allow_origins=settings.ALLOWED_ORIGINS," },
  { t: "ctx", s: "      allow_credentials=True," },
  { t: "ctx", s: "  )" },
];

function DiffLine({ t, s }) {
  const bg = t === "add" ? "rgba(143,181,158,0.14)" : t === "del" ? "rgba(217,138,122,0.12)" : "transparent";
  const mark = t === "add" ? "+" : t === "del" ? "−" : " ";
  const col = t === "ctx" ? "var(--on-surface-faint)" : "var(--on-surface)";
  return (
    <div className="flex gap-3 px-4 py-0.5" style={{ background: bg, fontFamily: MONO }}>
      <span className="select-none" style={{ color: "var(--on-surface-ghost)" }}>{mark}</span>
      <span className="whitespace-pre text-[12.5px]" style={{ color: col }}>{s}</span>
    </div>
  );
}

function MFixes() {
  return (
    <div>
      <MPageHead eyebrow="Act" title="Code fixes"
        sub="Proposed patches for open cases. Each goes through a clean-room review — the reviewer sees only the diff and the invariants it must preserve, never the finding — before you land it." />

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        {/* the proposed fix + diff */}
        <MGlass className="overflow-hidden">
          <div className="flex items-center justify-between gap-4 px-5 pt-5">
            <div>
              <MEyebrow className="mb-1.5">Proposal · C-203</MEyebrow>
              <div className="text-[15px]" style={{ color: "var(--on-surface-strong)" }}>Restrict CORS to configured origins</div>
            </div>
            <MSev level="medium" withLabel />
          </div>
          <div className="mt-4" style={{ borderTop: "1px solid var(--on-surface-ghost)" }}>
            <div className="flex items-center gap-2 px-4 py-2.5">
              <Icon name="file-text" size={13} style={{ color: "var(--on-surface-faint)" }} />
              <span className="font-mono text-[11px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>src/api/server.py</span>
            </div>
            <div className="pb-3">{DIFF.map((d, i) => <DiffLine key={i} {...d} />)}</div>
          </div>
          <div className="flex items-center gap-3 px-5 py-4" style={{ borderTop: "1px solid var(--on-surface-ghost)" }}>
            <MBtn variant="primary">Land fix</MBtn>
            <MBtn variant="glass">Open full diff</MBtn>
          </div>
        </MGlass>

        {/* review state */}
        <div className="space-y-5">
          <MGlass className="p-5">
            <MEyebrow className="mb-4">Clean-room review</MEyebrow>
            <div className="space-y-3 text-[13.5px]" style={{ color: "var(--on-surface)" }}>
              <div className="flex items-center gap-2.5"><MDot color="#8fb59e" size={7} /> Diff applies cleanly</div>
              <div className="flex items-center gap-2.5"><MDot color="#8fb59e" size={7} /> Invariants preserved (4/4)</div>
              <div className="flex items-center gap-2.5"><MDot color="#8fb59e" size={7} /> No new dependencies</div>
            </div>
            <p className="mt-4 text-[12px]" style={{ color: "var(--on-surface-faint)" }}>Reviewed against invariants only — the finding text was withheld.</p>
          </MGlass>

          <MGlass className="p-5">
            <MEyebrow className="mb-3">Queue</MEyebrow>
            <div className="space-y-2.5 text-[13px]" style={{ color: "var(--on-surface-muted)" }}>
              <div className="flex items-center justify-between"><span>C-204 · lodash bump</span><MState state="in_progress" /></div>
              <div className="flex items-center justify-between"><span>C-195 · drop root user</span><MState state="open" /></div>
            </div>
          </MGlass>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { MFixes });
