---
name: mistglass-devsec
version: 1.0
status: v1 — derived from reference image + brief; revisit when DëvSec source is attached
audience: engineers and design-aware agents building DëvSec product surfaces
read-first: yes
sources:
  - README.md                     # brand voice, rationale, examples
  - colors_and_type.css           # CSS variables — single source of truth for tokens
  - ui_kits/devsec_mobile/        # canonical mobile UI kit (React, visual reference)
  - assets/                       # logo, mark, icon notes
  - preview/                      # one-purpose visual cards for each token / component
---

# DESIGN.md — Mistglass for DëvSec

> A single, build-ready specification for **DëvSec**, the local-first developer security platform.
> Read this end-to-end before producing UI. Every value is concrete; every component has anatomy, states, props, and a "when to / when not to" pair.

This document is the **build spec**. Brand voice and rationale live in [`README.md`](./README.md); the agent-invocation manifest is [`SKILL.md`](./SKILL.md); CSS tokens live in [`colors_and_type.css`](./colors_and_type.css). Everything here either restates those for buildability, or adds the precision they don't carry.

---

## 0 · Quick start

```html
<link rel="stylesheet" href="colors_and_type.css">
<script src="https://unpkg.com/react@18.3.1/umd/react.development.js"
        integrity="sha384-hD6/rw4ppMLGNu3tX5cjIb+uRZ7UkRJ6BPkLpg4hAu/6onKUg4lLsHAs9EBPT82L"
        crossorigin="anonymous"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js"
        integrity="sha384-u6aeetuaXnQ38mYT8rp6sbXaQe3NL9t+IBXmnYxwkUI2Hw4bsp2Wvmx4yRQF1uAm"
        crossorigin="anonymous"></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js"
        integrity="sha384-m08KidiNqLdpJqLq95G/LEi8Qvjl/xUYll3QILypMoQ65QorJ9Lvtp2RXYGBFj1y"
        crossorigin="anonymous"></script>
<script type="text/babel" src="ui_kits/devsec_mobile/Components.jsx"></script>
```

Then either compose with the kit, or — for production — match the visual contract in your host stack using the values in §3.

**Smell test for any new screen**: 30–40% air, sentence case, one primary action, no pulsing decoration. If a screen fails any of these, stop and rework before continuing.

---

## 1 · Principles

These are the rules in priority order. When they conflict with a designer's instinct, the principle wins.

1. **Quiet by default, loud only when earned.** The default screen is sage and still. Critical red appears only when something is genuinely on fire — most days, nothing is.
2. **State the posture, then the detail.** Lead with the one-line summary; let the breakdown be discoverable. Never bury the verdict.
3. **Numbers earn their place.** A telemetry value must change something the user does. No vanity counters, no green-good-red-bad gauges, no scoreboard chrome.
4. **System speech, not advertising speech.** Mistglass is the voice of an experienced ops lead — calm, specific, present-tense. Never marketing, never alarmist.
5. **Material restraint.** Soft radii, hairline borders, very subtle shadows. If an effect doesn't add legibility or hierarchy, it's not adding anything.
6. **Fades over moves.** Calm easing, short durations, no bounces. Telemetry updates on real events, not on a pulse.
7. **Generous negative space.** Roughly 30–40% air on any Mistglass screen. Resist filling.

---

## 2 · Anti-patterns (banned outright)

| ❌ Banned | Why | Use instead |
|---|---|---|
| Matrix green, neon, glowing terminals | SOC trope; performative, not informative | Sage `--mist-surface-300`, deep teal `--mist-surface-500` |
| Skull / hazard / lock icons as decoration | Theatrics | Lucide `shield-check` / `shield-alert`, sparingly |
| Pure white background (`#fff` body) | Cold, clinical | `--paper #f3f1ec` (warm fog) |
| Pure black text (`#000`) | Reads as printer toner, not ink | `--ink #2c3835` on paper, `--on-surface` on hero |
| Pulsing dots / breathing buttons / animated alarms | "Always-on" alarm fatigue | Static elements; animate only on real state change |
| Red/green diverging heatmap | Color-blind hostile + carries SOC associations | `--mist-surface-200..700` ramp |
| Emoji in product UI | Casual where calm is needed | Lucide icon @ 14–18 px, or no icon |
| Gauges, speedometers, dial widgets | Dashboard kitsch | Single tabular-mono number + 12 px delta caption |
| Bold (700+) display type | Reads as alarm | `--w-semibold 600` ceiling for display |
| `backdrop-filter` for decoration | Blur is for separating layers, not for vibes | Use only when there is content beneath to blur |
| Slide-from-edge transitions | Cinematic; out of scale | Fade-and-grow, 220 ms standard ease |
| "Daily Security Digest Overview" title case | Marketing register | Sentence case: *"Here's your digest."* |

---

## 3 · Tokens

All tokens live in [`colors_and_type.css`](./colors_and_type.css). **Reference variables by name** in your CSS/JSX — never paste hex values inline. The table below restates them so an engineer can grep and a designer can read; the file is canonical if they ever disagree.

### 3.1 Color — surface (sage/teal)

The signature surface ramp. Hero gradient is `--mist-surface-300 → --mist-surface-500`, top to bottom.

| Token | Hex | Use |
|---|---|---|
| `--mist-surface-100` | `#b6c4bd` | Highest fog — accent on light backgrounds |
| `--mist-surface-200` | `#94a89e` | Light sage |
| `--mist-surface-300` | `#7d9189` | **Sage — top of hero gradient** |
| `--mist-surface-400` | `#69807a` | Mid teal — single-tone hero |
| `--mist-surface-500` | `#5e7570` | **Deep teal — bottom of hero gradient** |
| `--mist-surface-600` | `#4d605c` | Graphite teal |
| `--mist-surface-700` | `#3c4b48` | Near-black teal — text on light glass pills |
| `--mist-surface-800` | `#2c3835` | Graphite — body ink on paper |
| `--mist-surface-900` | `#1c2422` | Deepest — never pure black |

```css
background: var(--hero-gradient);
/* equivalent to: linear-gradient(180deg, #7d9189 0%, #5e7570 100%) */
```

### 3.2 Color — paper & fog

| Token | Hex | Use |
|---|---|---|
| `--paper` | `#f3f1ec` | **App background outside the hero** |
| `--paper-soft` | `#ebe9e3` | Sunken sections, table-row stripes |
| `--paper-deep` | `#e2ded6` | Modal scrim base, sheet edge |
| `--fog-50…900` | see CSS | Neutral cool grays for chrome (icons, separators, disabled states) |

### 3.3 Color — foreground

Always use foreground tokens, **never `#000` or `#fff` directly**.

| Token | Value | Use |
|---|---|---|
| `--on-surface-strong` | `#ffffff` | Display headline on hero only |
| `--on-surface` | `rgba(255,255,255,0.92)` | Body on hero |
| `--on-surface-muted` | `rgba(255,255,255,0.70)` | Captions, supporting copy on hero |
| `--on-surface-faint` | `rgba(255,255,255,0.48)` | Inactive ticks, ghost labels on hero |
| `--ink-strong` | `#1c2422` | Display & H1 on paper |
| `--ink` | `#2c3835` | Body on paper |
| `--ink-muted` | `#5e6864` | Captions on paper |
| `--ink-faint` | `#8d938f` | Inactive, separator labels |

### 3.4 Color — severity

Severity is a **small surface** (8–12 px pill, 6 px dot, 18 px icon). Never a panel background, never a full-bleed banner.

| Kind | Pill bg | Pill fg | Dot | Use |
|---|---|---|---|---|
| `healthy` | `#dfe7e3` | `#3c4b48` | `--sev-low #8aa39a` | All clear, default green-tinted state |
| `info` | `--sev-info-soft #cfdbe9` | `#36506e` | `--sev-info #6b8db5` | System activity, neutral notes |
| `low` | `#dfe7e3` | `#3c4b48` | `#8aa39a` | Minor finding, FYI |
| `warning` | `--sev-warn-soft #f1dcbe` | `#7d4d10` | `--sev-warn #c98a3f` | Action soon, not now |
| `elevated` | `#ecc9b7` | `#6e3a1c` | `--sev-high #b56b4a` | Should review today |
| `critical` | `--sev-crit-soft #e8c6c0` | `#6c1f1f` | `--sev-crit #9c3b3b` | **Reserved** — live threat |

**Earning critical.** Use `critical` only when there is a real, time-sensitive event the user must act on. If you cannot complete the sentence *"Action needed. A [thing] [is happening] [right now]"* truthfully, downgrade to `elevated`.

### 3.5 Color — glass & borders

```css
--glass-light:    rgba(255,255,255,0.12);   /* card on hero, default */
--glass-lighter:  rgba(255,255,255,0.22);   /* hovered/elevated */
--glass-lightest: rgba(255,255,255,0.40);   /* prominent pills, badges */
--glass-border:   rgba(255,255,255,0.18);   /* on hero */
--glass-border-d: rgba(28,36,34,0.08);      /* on paper */

--border-hair:    rgba(28,36,34,0.08);      /* default hairline on paper */
--border-soft:    rgba(28,36,34,0.12);      /* slightly heavier separator */
--border-strong:  rgba(28,36,34,0.20);      /* ghost button outline */

--focus-ring:     rgba(111,166,166,0.55);   /* muted cyan, keyboard focus */
```

### 3.6 Type

Family stack — `--font-sans` (Geist) and `--font-mono` (Geist Mono). Geist is a substitute for SF Pro; see §13.

| Token | Size | Weight | Line | Tracking | Used on |
|---|---|---|---|---|---|
| `.t-display` | 34 px | 600 | 1.15 | -0.02em | *"Here's your digest."* |
| `.t-h1` | 28 px | 600 | 1.15 | -0.01em | Screen titles |
| `.t-h2` | 22 px | 600 | 1.30 | -0.01em | Section headers |
| `.t-h3` | 18 px | 500 | 1.30 | 0 | Card titles |
| `.t-body` | 16 px | 400 | 1.45 | 0 | Default body |
| `.t-body-strong` | 16 px | 500 | 1.45 | 0 | In-line emphasis |
| `.t-small` | 14 px | 400 | 1.45 | 0 | Secondary copy, rows |
| `.t-caption` | 12 px | 500 | 1.30 | 0.01em | Sub-labels |
| `.t-caps` | 12 px | 600 | 1.0 | 0.08em | **Eyebrows & severity pills** — `UPPERCASE` |
| `.t-mono` | 14 px | 500 | 1.30 | 0 | Code, token IDs, timestamps, ratios |
| `.t-numeric` | inherit | — | — | — | Add to any number that updates in place — applies `tabular-nums` |

**Hard rules**
- Maximum weight in product: `600 (semibold)`. `700` reads as alarm.
- Telemetry numbers (`9.1`, `12`, `04:12`) always use `--font-mono` with `font-variant-numeric: tabular-nums`.
- Never set type smaller than `--t-micro` (11 px), and only use 11 px for the inside of severity pills and chart axis ticks.

### 3.7 Radii

```
--r-xs 6  · --r-sm 10 · --r-md 14 · --r-lg 20 · --r-xl 28 · --r-2xl 36 · --r-pill 999
```

| Element | Radius |
|---|---|
| Severity pill, category pill | `--r-pill` |
| Button | 16 px (matches `--r-lg` minus 4 — hand-tuned) |
| Telemetry pill icon container | `--r-md 14` (36 px square) |
| Card (glass or paper) | `--r-lg 20` |
| Hero sheet, modal | `--r-xl 28` |
| Phone frame, large surface | `--r-2xl 36` |
| Bar chart bar | 8 px top corners only (`8px 8px 0 0`) |
| Heatmap cell | 3 px |

### 3.8 Shadows

```
--shadow-1     buttons, paper cards at rest
--shadow-2     hovered card, picked-up row
--shadow-3     floating sheet, popover
--shadow-glass card on hero — outer soft + inner top highlight
--shadow-inset switch tracks, depressed surfaces
```

All shadows are **uncolored** (graphite alpha only) and **soft**. No tinted shadows, no `0 0 20px` glows. If you find yourself reaching for a glow, you want a border or an inset highlight, not a shadow.

### 3.9 Spacing

4 px scale. Most paddings come from a narrow set.

```
--s-1 4 · --s-2 8 · --s-3 12 · --s-4 16 · --s-5 20 · --s-6 24 · --s-7 32 · --s-8 40 · --s-9 56 · --s-10 72
```

| Context | Default |
|---|---|
| Card internal padding | `--s-5 20px` (or 18 px when dense) |
| Stack between cards | `--s-3 12px` |
| Section break (header → content) | `--s-6 24px` |
| Eyebrow → first item | `--s-3 12px` |
| Page horizontal gutter (mobile) | `--s-5 20px` |
| Status bar safe area | 54 px top |
| Home indicator safe area | 34 px bottom |
| Floating CTA → home indicator | 16 px |
| Mobile reading width (375 px frame) | 343 px content, 320 px hero text |

### 3.10 Motion

```
--ease-standard  cubic-bezier(0.32, 0.72, 0.20, 1.00)   90% of use
--ease-emphasis  cubic-bezier(0.20, 0.80, 0.20, 1.00)   used only on first paint
--ease-exit      cubic-bezier(0.40, 0.00, 0.80, 0.40)   dismissal

--dur-fast  140ms   hover, press, focus, toggle thumb
--dur-base  220ms   transitions, list reorder, count-up
--dur-slow  360ms   screen swap, sheet present
```

**Choreography rules**
- Telemetry numbers fade-and-count, never spin or roll.
- Charts fade in and grow vertically from baseline — never sweep horizontally.
- Cards do not slide in from off-screen. They fade and lift (`translateY(8px) → 0`).
- Nothing loops. No pulsing dots, no breathing buttons, no shimmer skeletons (use a static placeholder block instead).

---

## 4 · Layout & rhythm

### 4.1 The Mistglass screen

A Mistglass screen has three vertical regions:

```
┌───────────────────────────────┐  ← 54 px safe area
│  ← back   Screen title        │  ScreenHeader (36 px)
│                               │
│  [eyebrow]                    │  s-6 gap from header
│  [hero card / display title]  │
│                               │
│  [secondary cards…]           │  s-3 between cards
│                               │
│  [list…]                      │
│                               │
│                               │
│  ┌─────────────────────────┐  │  ← CTA floats here on hero
│  │  Primary action          │  │     16 px above bottom
│  └─────────────────────────┘  │
│  ← 34 px home indicator       │
└───────────────────────────────┘
```

### 4.2 Vertical rhythm

All vertical gaps are multiples of 4. Most are 8 / 12 / 16 / 20 / 24. **No 13 px, no 17 px.** When in doubt, snap to 12 or 16.

### 4.3 Negative space rule

Measure your screen. Roughly **30–40% of pixels should be background** (sage on hero, paper on paper). If you're below 30%, remove a card or shrink the type. If you're above 50%, the screen lacks a hero element — add a display headline or a chart.

### 4.4 One primary action

Every screen has exactly one primary action. Variants:
- On hero: **white** `AppButton` (`variant="primary"`), full-width, floats above home indicator.
- On paper: **graphite** `AppButton` (`variant="graphite"`).
- Destructive flow only: `critical` (deep red) — and only when irreversible.

A second action (Snooze, Cancel) is `ghost` and sits directly under the primary.

---

## 5 · Surfaces

DëvSec has exactly two product surfaces. Pick one per screen; do not mix.

### 5.1 Hero surface

The signature sage→teal gradient with a 14 px dot grid overlay. Used for:
- Daily digest (entry)
- Splash / lock
- Post-action summary ("All set. Token rotated.")
- Onboarding moments

```jsx
<HeroSurface>
  {/* white text, glass cards, white CTA */}
</HeroSurface>
```

Anatomy:
- `background: linear-gradient(180deg, #7d9189 0%, #5e7570 100%)`
- Dot grid: `radial-gradient(rgba(255,255,255,0.10) 1px, transparent 1px)` at `14px 14px`
- All text on this surface is white, weighted by alpha (`--on-surface*`).

### 5.2 Paper surface

Warm off-white `#f3f1ec`. Used for everything else — dashboards, lists, details, settings.

```jsx
<PaperSurface>
  {/* ink text, paper cards, graphite CTA */}
</PaperSurface>
```

Anatomy:
- `background: var(--paper)`
- No gradient, no dot grid. Let the cards do the work.
- All text is graphite (`--ink*`).

### 5.3 Choosing a surface

| Screen type | Surface |
|---|---|
| Entry point / one-line verdict | Hero |
| List of things | Paper |
| Detail of one thing | Paper |
| Settings / configuration | Paper |
| Empty / "all clear" celebration | Hero |
| Critical alert sheet | Paper (graphite header), severity pill at top |

---

## 6 · Components

Each component below has: **anatomy → props → variants → states → when to use / when not to**. Source: [`ui_kits/devsec_mobile/Components.jsx`](./ui_kits/devsec_mobile/Components.jsx). Live preview cards are in [`preview/`](./preview/).

### 6.1 `SeverityPill`

A small uppercase pill with a 6 px dot. The most-used signal in the system.

**Anatomy** — `dot · LABEL` inside a 999-radius capsule, 6×12 px padding, 11 px semibold, 0.08em tracking.

**Props**
| Prop | Type | Default | Notes |
|---|---|---|---|
| `kind` | `healthy \| info \| low \| warning \| elevated \| critical` | `low` | Picks bg / fg / dot color |
| `label` | string | `kind.toUpperCase()` | Override the auto-label |
| `onSurface` | bool | `false` | If `true`, uses white-translucent bg for hero surface |

**States** — single visual state; never animated, never hover-changed.

**Use when** — labeling a finding, a row, a card with its severity. One pill per row maximum.
**Don't use when** — labeling something that isn't actually a severity (use `CategoryPill`).

> Preview: [`preview/31-pill-severity.html`](./preview/31-pill-severity.html)

### 6.2 `CategoryPill`

Eyebrow-style pill with optional leading icon. Use for non-severity tagging — *Posture*, *Activity*, *Tokens*.

**Props** — `icon?`, `label`, `onSurface?`.

**Use when** — a section needs a one-word topic tag.
**Don't use when** — the topic is severity (use `SeverityPill`) or the label is more than 2 words (use a heading).

### 6.3 `GlassCard`

The frosted card that sits on the hero surface. The only place `backdrop-filter` is allowed in Mistglass.

**Anatomy**
- `background: rgba(255,255,255,0.14)`
- `backdrop-filter: blur(20px) saturate(140%)`
- `border: 1px solid rgba(255,255,255,0.20)`
- `border-radius: 20px`
- `box-shadow: var(--shadow-glass)` — outer soft + inner top highlight
- Internal padding: 18 px (compact) or 20 px (default)

**Props** — `style?`, `onClick?`, children.

**Press state** (mobile) — `transform: scale(0.98); opacity: 0.92`, 140 ms.

**Use when** — a card sits on the hero gradient.
**Don't use when** — the surface beneath is paper (use `PaperCard`) — there is nothing to blur, and the effect becomes muddy.

### 6.4 `PaperCard`

The default card on the paper surface.

**Anatomy** — white fill, 1 px hairline border `--border-hair`, 20 px radius, `--shadow-1`. 18–20 px padding.

**Use when** — grouping anything on paper.
**Don't use when** — you want to nest cards. Mistglass does not nest cards; use a hairline divider inside one card instead.

### 6.5 `AppButton`

The single button primitive. 56 px tall, full-width by default, 16 px radius, 16 px semibold copy.

**Variants**
| Variant | Background | Foreground | Used on | Use case |
|---|---|---|---|---|
| `primary` (default) | `#ffffff` | `--ink-strong` | Hero surface | Main CTA on hero |
| `graphite` | `#2c3835` | `#fff` | Paper | Main CTA on paper |
| `ghost` | transparent | `--ink-strong` + 1 px border | Paper | Secondary action (Snooze, Cancel) |
| `glass` | `rgba(255,255,255,0.18)` + blur | `#fff` | Hero | Secondary action on hero |
| `critical` | `--sev-crit #9c3b3b` | `#fff` | Either | **Irreversible** destructive flow only |

**States**
- Hover: `opacity: 0.92`
- Press: `transform: scale(0.98); opacity: 0.92` (140 ms standard ease)
- Focus: 3 px `--focus-ring` outline, 2 px offset
- Disabled: `opacity: 0.5`, no transform

**Use when** — exactly one primary action per screen.
**Don't use when** — the action is one of many list rows (use `TelemetryRow` with a `chevron`).

### 6.6 `BarChart`

The signature chart. Rounded-top bars, one bar highlighted (today / latest).

**Props**
| Prop | Type | Default | Notes |
|---|---|---|---|
| `data` | `[{label, value}]` | required | 5–10 bars; more becomes a heatmap instead |
| `highlight` | number | `-1` | Index of the lit bar; `-1` = last |
| `max` | number | `10` | Top of the scale |
| `height` | number | `160` | Including value labels above and weekday labels below |
| `onSurface` | bool | `true` | White fills on hero, graphite fills on paper |

**Anatomy** — each bar: numeric value on top (mono), bar with `8px 8px 0 0` radius, weekday letter below. Bar fill is `rgba(255,255,255,0.32)` on hero, `rgba(44,56,53,0.18)` on paper. The highlighted bar is solid `#fff` or `#2c3835`.

**Use when** — comparing 5–10 discrete time buckets (days of week, last N audits).
**Don't use when** — showing a continuous trend (use `TrendLine`) or >10 buckets (use a heatmap).

### 6.7 `TrendLine`

2 px stroke, rounded caps, soft fill below, single end-cap circle.

**Props** — `points: number[]`, `width`, `height`, `stroke`, `fillStop`.

**Anatomy** — `<path>` over `<path fill>` over a vertical linear gradient that fades to transparent at the bottom. End-cap is a 4 px white circle stroked with the line color — anchors the "current value" reading.

**Use when** — showing a continuous metric over ≥10 ticks (posture · 30 d, audit count · 7 d).
**Don't use when** — bucketed data with discrete labels.

### 6.8 `TelemetryRow`

The list row primitive. Icon container + label + sub + value, with a hairline bottom border.

**Props** — `icon?`, `label`, `sub?`, `value?`, `onClick?`, `onSurface?`.

**Anatomy** — 36 px icon container (paper: `--paper` fill, hero: `rgba(255,255,255,0.12)`), 14 px medium label, 12 px mono sub, mono value on the right.

**Use when** — a vertical list of homogeneous items (findings, events, settings).
**Don't use when** — items vary structurally (use distinct `PaperCard`s).

### 6.9 `TabBar`

Floating pill at the bottom of the viewport. Off-white-translucent fill, 999 radius, ~52 px tall.

**Props** — `tabs: [{id, label, icon}]`, `active`, `onChange`.

**Use when** — top-level navigation on mobile.
**Don't use when** — there are fewer than 3 destinations (use a back button) or more than 5 (split / promote).

### 6.10 `HeroSurface` / `PaperSurface`

Surface wrappers. They apply the background and (for hero) the dot grid. Always use one of these at the screen root — never apply the gradient or paper color inline on an arbitrary `<div>`.

### 6.11 `Icon`

Lucide-style inline SVG, stroke 1.75, `currentColor`. The component in the kit hand-inlines a subset; in production you load Lucide from CDN and override `stroke-width`.

**Sizes** — 14 (inline), 18 (default), 20 (in pills), 24 (nav), 28 (hero status).

**Use when** — any iconographic need. Color via `color="…"` or by setting `color` on the parent.
**Don't use when** — the glyph isn't in the curated subset ([`assets/ICONS.md`](./assets/ICONS.md)). Ask before adding new icons.

### 6.12 `SettingRow` (defined in `Screens.jsx`)

A label + sub + iOS-style toggle row. 46×28 px track, 24 px thumb, `--mist-surface-500` when on, `--fog-300` when off. 220 ms standard ease on the thumb.

---

## 7 · Patterns

The composition rules that turn components into screens.

### 7.1 Daily digest (hero)

**Order, top → bottom**
1. Display headline (`.t-display`) — *"Here's your digest."*
2. Body sentence (`.t-body`, 78% white) — one calm sentence summarizing the night.
3. **Spacer 64 px.**
4. Category pill (e.g. `Posture`).
5. One-line measurement (e.g. *"9.1 of 10 — better than yesterday by 0.4."*).
6. `BarChart` (180 px).
7. Closing sentence (`.t-h2`, white) — *"Well done. You're in better shape today…"*
8. `AppButton` primary — *"Open digest"*.
9. Ghost link button — *"See 2 findings →"*.

> Reference: [`ui_kits/devsec_mobile/Screens.jsx`](./ui_kits/devsec_mobile/Screens.jsx) `DigestScreen`.

### 7.2 Dashboard (paper)

1. `ScreenHeader` with back chevron.
2. **Hero card** — eyebrow + tabular-mono number + `+delta` + `TrendLine`.
3. **Severity strip** — two `PaperCard`s side-by-side, each with a pill + count + caption.
4. **Eyebrow** — `OPEN FINDINGS`.
5. List inside a `PaperCard` — `TelemetryRow`s with chevron `value`.

### 7.3 Detail (paper)

1. `ScreenHeader`.
2. `SeverityPill` + title (`.t-h1`) + subject in mono.
3. `PaperCard` — `SUMMARY` eyebrow + 1–2 sentence body.
4. `PaperCard` — `CHANGE` row (`from → to`) + `WHEN` row (mono timestamp).
5. Floating actions — graphite primary + ghost secondary, fixed 100 px above bottom.

### 7.4 Empty state

A short calm sentence, lowercase if possible. No illustration, no icon. Example:

> *"Nothing on the wire. We'll let you know."*

No CTA. The system is the actor; the user does not need to do anything.

### 7.5 Error / failed action

A `PaperCard` with `SeverityPill kind="elevated"`, a one-sentence description in `.t-body`, and a `graphite` retry button. Never a red flash, never a shaking animation.

### 7.6 Loading

A static `--paper-deep` block at the size of the eventual content. No shimmer, no spinner. Replace with the real content via 220 ms fade-in when ready. If loading exceeds 800 ms, show one line of mono caption — *"Scanning · 4 of 32 dependencies"* — that updates from real progress, not animation.

---

## 8 · Data visualization

Specific rules that override anything implicit in §6.

### 8.1 Bars

- Top corners `8 px`, bottom flush.
- 5–10 bars only.
- One bar lit (solid white on hero / graphite on paper); the rest at 32% / 18% alpha.
- Value label always shown above; weekday letter or short label always shown below.

### 8.2 Lines

- 2 px stroke, rounded caps + joins.
- Soft fill below (≤18% alpha of a sage/cyan), fading to transparent at the bottom.
- End-cap dot — 4 px white core, stroked with the line color.
- No grid lines. Let the card border carry the frame.

### 8.3 Heatmaps

- 7×24 grid for activity (days × hours). Cell `aspect-ratio: 1`, `3 px` radius, `3 px` gap.
- Ramp from `--mist-surface-100` (low) to `--mist-surface-700` (high) — seven steps.
- Legend in the bottom-right: `low ▢ ▢ ▢ ▢ ▢ high` with the seven swatches, mono caption.
- **Never** use red/green. Color-blind hostile and SOC-coded.

### 8.4 Single numbers

- `--font-mono`, semibold, tabular-nums.
- Optional `+0.4` delta caption beneath in 12 px mono, sage if positive, `--sev-warn` if negative *and* the metric is one where down is bad. Don't auto-decide direction.

---

## 9 · Iconography

Lucide @ stroke-width `1.75`, color `currentColor`. Curated subset in [`assets/ICONS.md`](./assets/ICONS.md).

**Sizing**
| px | Use |
|---|---|
| 14 | Inside `CategoryPill`, inline in body |
| 18 | Default UI, `TelemetryRow` icon |
| 20 | In status pills, secondary CTAs |
| 24 | Tab bar, screen header back chevron (16 actually — see kit) |
| 28 | Hero status cards |

**Rules**
- One icon per row maximum.
- No multi-color icons. Never fill an icon — they are stroke-only.
- Never use an icon as decoration. Every icon must label a thing the user might tap or read.
- Lucide is a substitute; flag this in any production handoff (see §13).

---

## 10 · Voice & copy

Pulled forward from the README because copy is part of the design contract.

### 10.1 Voice principles

1. **Posture first, detail second.** *"Posture is healthy. Two low-severity findings — both in dependencies."*
2. **Quantify when it helps, abstain when it doesn't.** *"Token rotation last ran 9 hours ago."* — not *"Token rotation: GREAT ✓"*.
3. **Sound like a human, not a script.** Sentence case, short clauses, plain words.
4. **Severity is earned.** "Critical" is reserved for genuinely critical events.

### 10.2 Pronouns

- **You** — the operator. *"You're in better shape than yesterday."*
- **We** — DëvSec. *"We rotated 12 tokens overnight."*
- **I** — never. DëvSec is a system, not a personality.

### 10.3 Casing

| Context | Casing |
|---|---|
| Display headlines, screen titles, buttons, menu items | Sentence case |
| Severity pills, eyebrows | `UPPERCASE` + 0.08em tracking |
| Code, token IDs, paths, timestamps | `lowercase mono` |

### 10.4 Copy patterns to imitate

| Where | Copy |
|---|---|
| Daily digest headline | *Here's your digest.* |
| Healthy summary | *Quiet overnight. Three audits ran, all passed.* |
| Single warning | *One thing to look at: an expiring credential in `aws-prod`.* |
| Critical | *Action needed. A live secret was committed 4 minutes ago.* |
| Primary CTAs | *Open digest* · *Review finding* · *Acknowledge* · *Snooze 24 h* |
| Empty state | *Nothing on the wire. We'll let you know.* |
| Section eyebrow | *POSTURE* · *AUDIT HISTORY* · *RECENT ACTIVITY* |
| Numbers in body | *"9.1 of 10"*, *"4 of 32 dependencies"* — never *"4/32 deps"* |
| Time | *"9 h ago"*, *"yesterday at 09:41"* — never *"2.5h"* or *"now()"* |

### 10.5 No emoji

In product surfaces. The only exception is the inline marks `·` (middle dot) and `→` (arrow), used as punctuation in text — never as buttons.

---

## 11 · Accessibility floor

| Check | Threshold |
|---|---|
| Body text contrast on paper | ≥ 7:1 (`--ink #2c3835` on `--paper #f3f1ec` ≈ 11:1 ✓) |
| Body text contrast on hero | ≥ 4.5:1 (`--on-surface` on `--mist-surface-400` ≈ 5.4:1 ✓) |
| Tap target | ≥ 44 × 44 px (button 56 ✓, tab bar item 44 ✓, severity pill is **not** a tap target) |
| Focus visible | 3 px `--focus-ring` outline, 2 px offset, always on keyboard |
| Color information | Never the sole channel. Severity always pairs a color with a `LABEL`. Heatmap pairs color with a tooltip-on-tap. |
| Motion preference | Respect `prefers-reduced-motion: reduce` — drop the count-up animation, snap charts in without the grow. |
| Font scaling | Type tokens are px today (matching the iOS feel). When porting to a stack that honors Dynamic Type, swap to rem and pin `1rem = 16px`. |

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 12 · Do / Don't gallery

### Color
| ✅ Do | ❌ Don't |
|---|---|
| Sage `#7d9189` background with white text at 92% | Bright green `#22c55e` "status OK" everywhere |
| Severity colors on a 10 px pill | Severity colors as a full panel background |
| `--ink #2c3835` for body on paper | `#000000` for body on paper |

### Type
| ✅ Do | ❌ Don't |
|---|---|
| `font-variant-numeric: tabular-nums` on `9.1` | Default proportional figures on a live number |
| Sentence case headlines | `TITLE CASE OVERVIEW HEADLINE` |
| Geist Mono for `aws-prod-2024` | Geist sans-serif for an ID |

### Motion
| ✅ Do | ❌ Don't |
|---|---|
| 220 ms fade-and-grow on a new card | Slide-from-right card entrance |
| Toggle thumb glides 220 ms | Toggle thumb bounces past and settles |
| Update a number once it's actually changed | Pulse the number every 2 s |

### Iconography
| ✅ Do | ❌ Don't |
|---|---|
| Lucide `shield-check` at stroke 1.75 | A red exclamation triangle with a glow |
| One 18 px icon per row | Three multi-color icons per card |

> Each preview card in [`preview/`](./preview/) is a "do" example. There is no "don't" gallery in the file system — the anti-patterns in §2 and the table above are the authoritative list.

---

## 13 · Substitutions & open flags

This is **v1**. Where Mistglass had to make a guess because source wasn't attached, it's flagged here. A real product handoff should resolve each row.

| # | Flag | Currently | Resolve by |
|---|---|---|---|
| 1 | No DëvSec codebase, Figma, or design tokens were attached | System derived from reference image + brief | Attach repo or Figma; re-run the design system creation against it |
| 2 | SF Pro is the intended typographic family | Geist (Google Fonts) used as substitute | Drop licensed SF Pro `.woff2` into `fonts/` and swap `--font-sans` |
| 3 | No proprietary icon set | Lucide chosen for tonal fit | Provide real icon set or confirm Lucide |
| 4 | Reference image was the only visual source | All visual values backed out from that one frame | Provide 5–10 additional reference screens to validate |
| 5 | No tablet or desktop targets defined | Mobile-only kit | Confirm tablet/desktop scope; type and spacing scales will need extension |
| 6 | No dark mode | Hero surface is the "dark" side; paper is the "light" side — but there is no true dark mode | Decide whether to add one, or whether the hero/paper duality is the answer |
| 7 | No localization rules | English-only copy | Provide locales; recheck line lengths at 1.4× expansion (German) and 0.7× (Japanese) |
| 8 | No data viz beyond bar / line / heatmap | Three primitives in the kit | Add donut / sparkline / stack-area only when a real screen requires it |

---

## 14 · File map

```
.
├── DESIGN.md                       ← this file
├── README.md                       ← brand rationale + content fundamentals
├── SKILL.md                        ← agent-invocation manifest
├── colors_and_type.css             ← single source of truth for all tokens
├── assets/
│   ├── devsec-logo.svg             ← wordmark (monochrome, currentColor)
│   ├── devsec-mark.svg             ← shield + dot glyph
│   ├── ICONS.md                    ← curated Lucide subset for SecOps
│   └── lucide.min.js               ← offline copy of Lucide (CDN preferred)
├── fonts/
│   └── README.md                   ← Geist vs SF Pro substitution note
├── ui_kits/devsec_mobile/
│   ├── index.html                  ← runnable click-through prototype
│   ├── Components.jsx              ← all primitives (canonical for visual contract)
│   ├── Screens.jsx                 ← composed screens — patterns reference
│   ├── ios-frame.jsx               ← phone bezel for prototyping
│   └── README.md                   ← screen + component index
└── preview/
    ├── 01..08-color-*.html         ← color tokens
    ├── 10..13-type-*.html          ← type styles
    ├── 20-radii.html               ← radius scale
    ├── 21-shadows.html             ← shadow scale
    ├── 22-spacing-scale.html       ← spacing
    ├── 23-motion.html              ← easing & durations
    ├── 30..38-*.html               ← components (button, pill, card, chart…)
    ├── 40-logo.html, 41-mark.html  ← brand
    ├── 42-dotgrid.html             ← surface texture
    └── 43-hero-screen-mini.html    ← composed example
```

---

## 15 · Build checklist (paste into PR template)

Before merging a Mistglass screen:

- [ ] Surface is `HeroSurface` or `PaperSurface` (not an arbitrary `<div>` with a background)
- [ ] Headline is sentence case, weight ≤ 600
- [ ] Every number that updates uses `--font-mono` + `tabular-nums`
- [ ] Every icon is Lucide @ stroke 1.75 — `currentColor`, no fills
- [ ] There is exactly one primary action on the screen
- [ ] Severity colors appear only on pills / dots / 18 px icons — never as panel bg
- [ ] No pure white (`#fff`) text on hero — use `--on-surface*`
- [ ] No pure black (`#000`) text on paper — use `--ink*`
- [ ] No looping animations, no shimmer skeletons, no pulsing dots
- [ ] `prefers-reduced-motion` honored
- [ ] Tap targets ≥ 44 px
- [ ] Empty / loading / error states drawn
- [ ] Copy matches the voice patterns in §10.4

---

## 16 · Working with this system (for agents)

If you are an agent (Claude Code, Claude.ai, another LLM) generating DëvSec UI:

1. **Read this file end-to-end before producing anything.** Then skim `README.md` for tone and `Components.jsx` for the visual contract.
2. **Link `colors_and_type.css`** in any HTML you produce. Never re-declare tokens; never paste hex values inline.
3. **Reuse components from `ui_kits/devsec_mobile/Components.jsx`** in throwaway prototypes. For production code, re-implement in the host stack but match the visual contract exactly (radii, shadows, type, motion).
4. **Default to static HTML** for visual artifacts. Use React only when there is real interactive behaviour (toggles, navigation, live data).
5. **Ask before adding** new icons, new colors, new components, or anything that isn't already in the curated set.
6. **Flag substitutions explicitly** when you make them (e.g. "I used Lucide `network` here because no other glyph fits — confirm").
7. **The hero gradient is the only place `backdrop-filter` is allowed.** If you reach for it elsewhere, you want a hairline border or a `--shadow-1`, not a blur.

When in doubt: be quieter, be smaller, leave more space. Mistglass earns trust by under-acting.
