/* Mistglass data-viz — refined, thin, monochrome, airy. Modelled on the mobile
   insight screens: each visual is quiet evidence under a plain-language insight.
   Thin strokes, white-on-grey, end-dots, mono labels. Color stays reserved. */

/* MTickMeter — a row of thin vertical ticks (an equalizer / segment meter).
   The first `lit` ticks are coloured — a solid `color`, or a `from`→`to`
   gradient interpolated across the lit run — and the rest use the faint
   `track`. The shared motif behind the severity ladder, launch-readiness, and
   the repo-health score. */
function MTickMeter({ count = 22, lit, value = 0, max = 10, color = "rgba(255,255,255,0.82)", from, to, track = "rgba(255,255,255,0.15)", height = 22, gap = 3 }) {
  const litCount = Math.max(0, Math.min(count, lit != null ? lit : Math.round((value / max) * count)));
  const toRgb = (h) => { const s = h.replace("#", ""); return [0, 2, 4].map((i) => parseInt(s.slice(i, i + 2), 16)); };
  const ramp = from && to ? [toRgb(from), toRgb(to)] : null;
  return (
    <div className="flex w-full items-stretch" style={{ gap, height }}>
      {Array.from({ length: count }).map((_, i) => {
        let bg = track;
        if (i < litCount) {
          if (ramp) {
            const t = litCount <= 1 ? 1 : i / (litCount - 1);
            const c = ramp[0].map((a, k) => Math.round(a + (ramp[1][k] - a) * t));
            bg = `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
          } else bg = color;
        }
        return <div key={i} className="flex-1 rounded-full" style={{ background: bg, minWidth: 2 }} />;
      })}
    </div>
  );
}

/* thin posture/exposure ring with an end-dot */
function MRing({ value = 8.1, max = 10, unit = "/10", tier, size = 156 }) {
  const sw = 4, pad = 9;
  const r = (size - sw - pad * 2) / 2;
  const cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, value / max));
  const tip = (-90 + frac * 360) * Math.PI / 180;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth={sw} />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.9)" strokeWidth={sw} strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={circ * (1 - frac)} transform={`rotate(-90 ${cx} ${cy})`} />
        <circle cx={cx + r * Math.cos(tip)} cy={cy + r * Math.sin(tip)} r={sw / 1.3} fill="#fff" />
      </svg>
      <div className="absolute text-center">
        <div className="flex items-baseline justify-center gap-0.5">
          <span className="font-semibold leading-none" style={{ fontSize: 36, color: "var(--on-surface-strong)" }}>{value}</span>
          <span style={{ fontSize: 13, color: "var(--on-surface-faint)" }}>{unit}</span>
        </div>
        {tier && <div className="mt-1.5 font-mono text-[9px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-muted)" }}>{tier}</div>}
      </div>
    </div>
  );
}

/* hairline severity bars — big right-aligned numbers, the label carries meaning.
   `fill` distributes the rows over the tile's full height (for a tall tile). */
function MSeverityBars({ rows, fill = false }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  const renderItem = (r) => (
    <div key={r.label}>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>
          {r.color && <span className="h-1.5 w-1.5 rounded-full" style={{ background: r.color }} />}{r.label}
        </span>
        <span className="font-semibold tabular-nums" style={{ fontSize: fill ? 21 : 17, color: "var(--on-surface-strong)" }}>{r.value}</span>
      </div>
      <MTickMeter count={20} value={r.value} max={max} color={r.color || "rgba(255,255,255,0.7)"} height={fill ? 22 : 14} />
    </div>
  );
  if (fill) return <div className="flex h-full flex-col justify-between">{rows.map(renderItem)}</div>;
  return <div className="space-y-5">{rows.map(renderItem)}</div>;
}

/* minimal open-vs-resolved line trend. `compact` is a slim sparkline variant
   for a short tile — it fills its height and keeps a one-line legend. */
function MLineTrend({ open, resolved, compact = false }) {
  const W = 320, H = compact ? 40 : 96, n = open.length;
  const all = open.concat(resolved);
  const max = Math.max(...all), min = Math.min(...all);
  const pad = compact ? 4 : 6;
  const x = (i) => (i / (n - 1)) * W;
  const y = (v) => H - pad - ((v - min) / (max - min || 1)) * (H - pad * 2 - 3);
  const pts = (arr) => arr.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const legend = (
    <div className={`flex items-center gap-5 font-mono text-[10px] uppercase tracking-[0.16em] ${compact ? "" : "mt-3"}`} style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>
      <span className="flex items-center gap-2"><span className="h-px w-4" style={{ background: "rgba(255,255,255,0.92)" }} /> open · {open[open.length - 1]}</span>
      <span className="flex items-center gap-2"><span className="h-px w-4" style={{ background: "rgba(255,255,255,0.4)", borderTop: "1px dashed" }} /> resolved · {resolved[resolved.length - 1]}</span>
    </div>
  );
  const chart = (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: H }}>
      <polygon points={`0,${H} ${pts(open)} ${W},${H}`} fill="rgba(255,255,255,0.08)" stroke="none" />
      <polyline points={pts(resolved)} fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeDasharray="3 4" />
      <polyline points={pts(open)} fill="none" stroke="rgba(255,255,255,0.92)" strokeWidth="2" />
      <circle cx={x(n - 1)} cy={y(open[n - 1])} r="3" fill="#fff" />
    </svg>
  );
  if (compact) {
    return <div className="flex h-full flex-col justify-center gap-2">{chart}{legend}</div>;
  }
  return <div>{chart}{legend}</div>;
}

/* scan-activity contribution heatmap (weekdays brighter) — fills its widget:
   columns spread to the full width, block centered vertically. */
function MHeatmap({ weeks = 20 }) {
  const days = 7;
  const cell = (d, w) => {
    const weekday = d >= 1 && d <= 5;
    const base = weekday ? 2 + ((w * 3 + d * 2) % 5) : (w + d) % 2;
    return Math.max(0, Math.min(6, base));
  };
  const alpha = [0.05, 0.12, 0.22, 0.34, 0.5, 0.68, 0.9];
  return (
    <div className="flex h-full flex-col justify-center">
      <div className="flex w-full justify-between">
        {Array.from({ length: weeks }).map((_, w) => (
          <div key={w} className="flex flex-col gap-[4px]">
            {Array.from({ length: days }).map((_, d) => (
              <div key={d} className="rounded-[2px]" style={{ width: 14, height: 14, background: `rgba(255,255,255,${alpha[cell(d, w)]})` }} />
            ))}
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>
        less {alpha.slice(1, 6).map((a, i) => <span key={i} className="rounded-[2px]" style={{ width: 11, height: 11, background: `rgba(255,255,255,${a})` }} />)} more
      </div>
    </div>
  );
}

/* concentric coverage arcs — one ring per category, center = overall */
function MCoverageArcs({ overall = 74, items = [], size = 168 }) {
  const cx = size / 2, cy = size / 2, sw = 4;
  const radii = [0.42, 0.34, 0.26, 0.18].map((f) => Math.round(f * size)).slice(0, items.length);
  return (
    <div className="flex items-center gap-7">
      <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size}>
          {items.map((it, i) => {
            const r = radii[i], circ = 2 * Math.PI * r, frac = it.pct / 100;
            return (
              <g key={it.label}>
                <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.10)" strokeWidth={sw} />
                <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth={sw} strokeLinecap="round"
                  strokeDasharray={circ} strokeDashoffset={circ * (1 - frac)} transform={`rotate(-90 ${cx} ${cy})`} />
              </g>
            );
          })}
        </svg>
        <div className="absolute text-center">
          <div className="font-semibold leading-none" style={{ fontSize: 26, color: "var(--on-surface-strong)" }}>{overall}<span style={{ fontSize: 14, color: "var(--on-surface-faint)" }}>%</span></div>
          <div className="mt-1 font-mono text-[8.5px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-muted)" }}>covered</div>
        </div>
      </div>
      <div className="grid flex-1 grid-cols-2 gap-x-5 gap-y-3">
        {items.map((it) => (
          <div key={it.label} className="flex items-baseline justify-between gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.16em]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{it.label}</span>
            <span className="font-semibold" style={{ fontSize: 15, color: it.pct < 50 ? "#d7a86b" : "var(--on-surface)" }}>{it.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { MTickMeter, MRing, MSeverityBars, MLineTrend, MHeatmap, MCoverageArcs });
