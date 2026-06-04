/* Placeholder for a section that's on the board but not yet designed.
   Deliberately calm and intentional (not a broken/empty state): it shows the
   FEATURE MAP for this screen — what the live dashboard does today, the only
   thing we carry over — plus the per-screen loop. "Current app = the map." */

const LOOP = [
  ["Map", "List what today's screen does — features only."],
  ["Brief", "Who's here · the one thing · keep/cut/merge · what's missing."],
  ["Build", "Design it fresh in the new language, fake data."],
  ["Gate", "Brand ✓ · UX ✓ · coverage ✓."],
  ["Park", "Lock it, move on."],
];

function StubScreen({ section }) {
  const map = section.map || [];
  return (
    <div className="space-y-6">
      <div className="inline-flex items-center gap-2 rounded-sm border border-white/10 bg-white/[0.02] px-3 py-1.5">
        <span className="h-1.5 w-1.5 rounded-full border border-white/25" />
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40">not designed yet</span>
      </div>

      <p className="max-w-2xl text-[15px] leading-relaxed text-white/[0.62]">
        {section.blurb || `“${section.label}” is on the board. We'll design it from scratch in the new
        language when its turn comes — using the live dashboard only as the feature map below.`}
      </p>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* feature map */}
        <section className="rounded-sm border border-white/10 bg-white/[0.02] p-6">
          <h2 className="mb-4 font-mono text-[10px] uppercase tracking-[0.24em] text-white/40">
            Feature map · what it does today
          </h2>
          {map.length ? (
            <ul className="space-y-2.5">
              {map.map((f) => (
                <li key={f} className="flex gap-3 text-[13.5px] text-white/75">
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-white/30" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-white/40">Map this from the live screen before designing.</p>
          )}
        </section>

        {/* the loop */}
        <section className="rounded-sm border border-white/10 bg-white/[0.02] p-6">
          <h2 className="mb-4 font-mono text-[10px] uppercase tracking-[0.24em] text-white/40">
            The loop · per screen
          </h2>
          <ol className="space-y-3">
            {LOOP.map(([step, gloss], i) => (
              <li key={step} className="flex gap-3">
                <span className="font-mono text-[12px] text-white/30">{String(i + 1).padStart(2, "0")}</span>
                <span className="text-[13.5px] text-white/75"><span className="text-white">{step}</span> — {gloss}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}

Object.assign(window, { StubScreen });
