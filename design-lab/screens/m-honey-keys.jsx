/* Honey keys — tripwire secrets planted in the repo. Calm status, not alarm. */

const KEYS = [
  { id: "HK-1", label: "AWS-style access key", path: "config/.env.sample", state: "armed", checked: "5h ago" },
  { id: "HK-2", label: "Database URL with password", path: "docs/setup.md", state: "armed", checked: "5h ago" },
  { id: "HK-3", label: "API token (fixture)", path: "tests/fixtures/auth.json", state: "armed", checked: "5h ago" },
  { id: "HK-4", label: "Private SSH key fragment", path: "deploy/keys.example", state: "armed", checked: "1d ago" },
];

function MHoneyKeys() {
  return (
    <div>
      <MPageHead eyebrow="Findings" title="Honey keys"
        sub="Fake credentials planted in the repo. If one is ever read or exfiltrated, you'll know something is wrong — before real damage."
        actions={<MBtn variant="glass">Rotate all</MBtn>} />

      {/* status summary */}
      <div className="mb-6 grid gap-5 sm:grid-cols-3">
        <MGlass className="p-5"><MEyebrow className="mb-3">Armed</MEyebrow><MStat value="4" label="planted and watching" /></MGlass>
        <MGlass className="p-5"><MEyebrow className="mb-3">Tripped</MEyebrow><MStat value="0" label="nothing has touched them" /></MGlass>
        <MGlass className="p-5"><MEyebrow className="mb-3">Last checked</MEyebrow><MStat value="5h" unit="ago" label="next check on the daily sweep" /></MGlass>
      </div>

      <MEyebrow className="mb-3">Placements</MEyebrow>
      <MGlass className="overflow-hidden">
        {KEYS.map((k, i) => (
          <MRow key={k.id} onClick={() => {}} className={i === 0 ? "border-t-0" : ""}>
            <span className="shrink-0" style={{ color: "var(--on-surface-muted)" }}><Icon name="key-round" size={17} strokeWidth={1.7} /></span>
            <div className="min-w-0 flex-1">
              <div className="text-[14px]" style={{ color: "var(--on-surface)" }}>{k.label}</div>
              <div className="mt-1 font-mono text-[11px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{k.path}</div>
            </div>
            <span className="hidden shrink-0 items-center gap-1.5 text-[12px] sm:inline-flex" style={{ color: "var(--on-surface-muted)" }}>
              <MDot color="#8fb59e" size={6} /> armed
            </span>
            <span className="w-20 shrink-0 text-right font-mono text-[11px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{k.checked}</span>
          </MRow>
        ))}
      </MGlass>
    </div>
  );
}

Object.assign(window, { MHoneyKeys });
