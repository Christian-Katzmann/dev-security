/* Mistglass kit — the shared component vocabulary for the desktop product.
   Every screen composes from these so the system stays consistent and calm.
   Mistglass rules: white-on-grey alpha ladder, frosted glass cards with a lit
   top edge, soft radii, color spent ONLY on severity/attention. */

const MONO = '"SF Mono", "Geist Mono", ui-monospace, Menlo, monospace';

/* severity / attention hues — calm earthy tones (no SOC neon), always paired
   with a text label so color is never the only signal. Open to tuning; the
   "brighter color" likely becomes `critical`. */
const SEV = {
  critical: { c: "#d98a7a", label: "critical" },
  high:     { c: "#d7a86b", label: "high" },
  medium:   { c: "#cbb994", label: "medium" },
  low:      { c: "rgba(255,255,255,0.45)", label: "low" },
  info:     { c: "#9bb3c2", label: "info" },
  resolved: { c: "#8fb59e", label: "resolved" },
};

/* lifecycle states (neutral chips) */
const STATE = {
  open:          { c: "rgba(255,255,255,0.70)", label: "Open" },
  verified:      { c: "#9bb3c2", label: "Verified" },
  in_progress:   { c: "#d7a86b", label: "In progress" },
  accepted_risk: { c: "rgba(255,255,255,0.45)", label: "Accepted risk" },
  resolved:      { c: "#8fb59e", label: "Resolved" },
};

function MEyebrow({ children, className = "" }) {
  return (
    <div className={`font-mono text-[10px] uppercase tracking-[0.2em] ${className}`}
      style={{ color: "var(--on-surface-faint)", fontFamily: MONO }}>
      {children}
    </div>
  );
}

function MGlass({ hover = false, className = "", style = {}, children }) {
  return (
    <div className={`mist-glass ${hover ? "mist-glass-hover" : ""} rounded-2xl ${className}`} style={style}>
      {children}
    </div>
  );
}

function MDot({ color, size = 8 }) {
  return <span className="inline-block shrink-0 rounded-full" style={{ width: size, height: size, background: color }} />;
}

function MSev({ level, withLabel = false }) {
  const s = SEV[level] || SEV.low;
  if (!withLabel) return <MDot color={s.c} />;
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px]" style={{ color: "var(--on-surface-muted)" }}>
      <MDot color={s.c} /> {s.label}
    </span>
  );
}

function MState({ state }) {
  const s = STATE[state] || STATE.open;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px]"
      style={{ background: "var(--glass-light)", border: "1px solid var(--glass-border)", color: "var(--on-surface-muted)" }}>
      <MDot color={s.c} size={6} /> {s.label}
    </span>
  );
}

function MBtn({ variant = "glass", children, onClick, className = "" }) {
  const base = "inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-[13.5px] transition";
  if (variant === "primary")
    return <button type="button" onClick={onClick} className={`mist-btn-primary font-medium ${base} ${className}`}>{children}</button>;
  if (variant === "ghost")
    return <button type="button" onClick={onClick} className={`${base} ${className}`} style={{ color: "var(--on-surface-muted)" }}>{children}</button>;
  return <button type="button" onClick={onClick} className={`mist-btn-glass ${base} ${className}`}>{children}</button>;
}

function MStat({ value, unit, label }) {
  return (
    <div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-[32px] font-semibold leading-none" style={{ color: "var(--on-surface-strong)" }}>{value}</span>
        {unit && <span className="text-[15px]" style={{ color: "var(--on-surface-faint)" }}>{unit}</span>}
      </div>
      {label && <div className="mt-2 text-[12.5px]" style={{ color: "var(--on-surface-muted)" }}>{label}</div>}
    </div>
  );
}

/* filter / segmented chips */
function MFilters({ items, active, onChange }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {items.map((it) => {
        const id = typeof it === "string" ? it : it.id;
        const label = typeof it === "string" ? it : it.label;
        const on = id === active;
        return (
          <button key={id} type="button" onClick={() => onChange && onChange(id)}
            className="rounded-full px-3 py-1.5 text-[12.5px] transition"
            style={on
              ? { background: "var(--glass-lightest)", color: "var(--mist-700)" }
              : { color: "var(--on-surface-muted)", border: "1px solid var(--glass-border)" }}>
            {label}
          </button>
        );
      })}
    </div>
  );
}

/* page header inside the content column */
function MPageHead({ eyebrow, title, sub, actions }) {
  return (
    <div className="mb-8 flex items-start justify-between gap-6">
      <div className="min-w-0">
        {eyebrow && <MEyebrow className="mb-2.5">{eyebrow}</MEyebrow>}
        <h1 className="text-[26px] font-semibold leading-tight tracking-tight" style={{ color: "var(--on-surface-strong)" }}>{title}</h1>
        {sub && <p className="mt-2 max-w-2xl text-[14px] leading-relaxed" style={{ color: "var(--on-surface-muted)" }}>{sub}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2.5">{actions}</div>}
    </div>
  );
}

/* MBento — the tiling widget grid (4 columns; widgets span 1–4). */
function MBento({ children, className = "" }) {
  return (
    <div className={`grid gap-4 ${className}`} style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gridAutoFlow: "row dense" }}>
      {children}
    </div>
  );
}

/* MWidget — a self-contained bento tile. Apple-widget craft: generous radius +
   padding, frosted glass, an optional eyebrow/insight header and a footer slot.
   `span` = grid columns (1 = square, 2 = wide, 4 = full). Content fills the
   middle; design each widget to fit its size. */
function MWidget({ span = 2, minH = 168, eyebrow, insight, footer, pad = 22, center = false, className = "", children }) {
  return (
    <div className={`mist-glass flex flex-col rounded-[22px] ${className}`}
      style={{ gridColumn: `span ${span} / span ${span}`, minHeight: minH, padding: pad }}>
      {(eyebrow || insight) && (
        <div className="shrink-0" style={{ marginBottom: insight ? 18 : 14 }}>
          {eyebrow && <MEyebrow className={insight ? "mb-2" : ""}>{eyebrow}</MEyebrow>}
          {insight && <div className="text-[17px] font-medium leading-snug tracking-tight" style={{ color: "var(--on-surface-strong)" }}>{insight}</div>}
        </div>
      )}
      <div className={`min-h-0 flex-1 ${center ? "flex flex-col items-center justify-center" : ""}`}>{children}</div>
      {footer && <div className="mt-4 shrink-0">{footer}</div>}
    </div>
  );
}

/* posture indicator — calm + honest. A single-tone ring (NOT green-good /
   red-bad), the number /10, and the tier word that carries the judgment.
   Replaces the live app's donut without the speedometer kitsch. */
function MPosture({ score = 8.1, tier = "Steady", size = 132 }) {
  const r = (size - 14) / 2;
  const circ = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, score / 10));
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.13)" strokeWidth="6" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.90)" strokeWidth="6"
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - frac)} />
      </svg>
      <div className="absolute text-center">
        <div className="flex items-baseline justify-center gap-0.5">
          <span className="font-semibold leading-none" style={{ fontSize: 30, color: "var(--on-surface-strong)" }}>{score.toFixed(1)}</span>
          <span style={{ fontSize: 13, color: "var(--on-surface-faint)" }}>/10</span>
        </div>
        <div className="mt-1.5 font-mono text-[9px] uppercase tracking-[0.18em]" style={{ fontFamily: MONO, color: "var(--on-surface-muted)" }}>{tier}</div>
      </div>
    </div>
  );
}

/* 7-point posture bars (values 0–10) */
function MPostureBars({ data }) {
  return (
    <div className="flex items-end gap-2" style={{ height: 84 }}>
      {data.map((d, i) => {
        const lit = i === data.length - 1;
        return (
          <div key={i} className="flex flex-1 flex-col items-center justify-end gap-1.5" style={{ height: "100%" }}>
            <span className="font-mono text-[9px]" style={{ fontFamily: MONO, color: lit ? "var(--on-surface)" : "var(--on-surface-faint)" }}>{d.v.toFixed(1)}</span>
            <div className="w-full rounded-t-md" style={{ height: `${Math.max(4, (d.v / 10) * 100)}%`, background: lit ? "#ffffff" : "rgba(255,255,255,0.26)" }} />
            <span className="font-mono text-[9px]" style={{ fontFamily: MONO, color: "var(--on-surface-faint)" }}>{d.l}</span>
          </div>
        );
      })}
    </div>
  );
}

/* a clean list row used by Cases / Activity / etc. */
function MRow({ children, onClick, className = "" }) {
  return (
    <div onClick={onClick}
      className={`flex items-center gap-4 px-5 py-4 transition ${onClick ? "cursor-pointer" : ""} ${className}`}
      style={{ borderTop: "1px solid var(--on-surface-ghost)" }}
      onMouseEnter={(e) => { if (onClick) e.currentTarget.style.background = "rgba(255,255,255,0.05)"; }}
      onMouseLeave={(e) => { if (onClick) e.currentTarget.style.background = "transparent"; }}>
      {children}
    </div>
  );
}

Object.assign(window, { MEyebrow, MGlass, MDot, MSev, MState, MBtn, MStat, MFilters, MPageHead, MRow, MPosture, MPostureBars, MBento, MWidget, SEV, STATE, MONO });
