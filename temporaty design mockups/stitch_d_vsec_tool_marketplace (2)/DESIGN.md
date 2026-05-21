---
name: Mistglass
colors:
  surface: '#f3fbf8'
  surface-dim: '#d3dcd8'
  surface-bright: '#f3fbf8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#edf6f2'
  surface-container: '#e7f0ec'
  surface-container-high: '#e1eae6'
  surface-container-highest: '#dce4e1'
  on-surface: '#151d1b'
  on-surface-variant: '#424846'
  inverse-surface: '#2a3230'
  inverse-on-surface: '#eaf3ef'
  outline: '#727876'
  outline-variant: '#c2c8c5'
  surface-tint: '#4c635e'
  primary: '#465c58'
  on-primary: '#ffffff'
  primary-container: '#5e7570'
  on-primary-container: '#e2fbf5'
  inverse-primary: '#b3ccc6'
  secondary: '#4f625b'
  on-secondary: '#ffffff'
  secondary-container: '#cfe4db'
  on-secondary-container: '#53675f'
  tertiary: '#4e5b55'
  on-tertiary: '#ffffff'
  tertiary-container: '#66736d'
  on-tertiary-container: '#eaf9f1'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#cfe8e2'
  primary-fixed-dim: '#b3ccc6'
  on-primary-fixed: '#081f1c'
  on-primary-fixed-variant: '#354b47'
  secondary-fixed: '#d2e7de'
  secondary-fixed-dim: '#b6cbc2'
  on-secondary-fixed: '#0d1f19'
  on-secondary-fixed-variant: '#384b44'
  tertiary-fixed: '#d8e6de'
  tertiary-fixed-dim: '#bccac3'
  on-tertiary-fixed: '#121e1a'
  on-tertiary-fixed-variant: '#3d4a44'
  background: '#f3fbf8'
  on-background: '#151d1b'
  surface-variant: '#dce4e1'
  mist-100: '#b6c4bd'
  mist-300: '#7d9189'
  mist-500: '#5e7570'
  mist-900: '#1c2422'
  paper: '#f3f1ec'
  paper-soft: '#ebe9e3'
  paper-deep: '#e2ded6'
  glass-border: rgba(255, 255, 255, 0.18)
  ink-strong: '#1c2422'
  ink-muted: '#5e6864'
  sev-low: '#8aa39a'
  sev-warn: '#c98a3f'
  sev-high: '#b56b4a'
  sev-crit: '#9c3b3b'
typography:
  display:
    fontFamily: Geist
    fontSize: 34px
    fontWeight: '600'
    lineHeight: '1.15'
    letterSpacing: -0.02em
  h1:
    fontFamily: Geist
    fontSize: 28px
    fontWeight: '600'
    lineHeight: '1.15'
    letterSpacing: -0.01em
  h2:
    fontFamily: Geist
    fontSize: 22px
    fontWeight: '600'
    lineHeight: '1.30'
    letterSpacing: -0.01em
  h3:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '500'
    lineHeight: '1.30'
  body:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.45'
  body-mono:
    fontFamily: Geist Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.30'
  label-caps:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '600'
    lineHeight: '1.0'
    letterSpacing: 0.08em
  caption:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.30'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  card-padding: 20px
  desktop-margin: 48px
  gutter: 24px
---

## Brand & Style

The design system is a high-fidelity interface for developer security, characterized by a "quiet," stoic, and technical personality. It rejects the alarmist tropes of traditional cybersecurity—neon glows and aggressive reds—in favor of a refined, sage-and-teal palette that evokes professional competence and calm.

The visual style is a hybrid of **Atmospheric Glassmorphism** and **Tactile Paper**. It uses a dual-surface logic:
- **Hero Surfaces:** Deep, atmospheric teal gradients with frosted glass overlays and subtle dot-grid textures for high-level summaries and "digests."
- **Paper Surfaces:** Warm, off-white, physical backgrounds for information-dense data analysis, tool catalogs, and settings.

The interface should feel "local-first," emphasizing precision, privacy, and earned severity.

## Colors

The palette is rooted in desaturated greens and warm neutrals. 

- **The Mist Ramp:** These teals form the core brand identity. The primary `#5e7570` is used for active states and hero depth, while lighter sages serve as accents.
- **The Paper Ramp:** These off-whites replace pure white to create a "warm industrial" feel. Use `--paper` for the main canvas in the Tool Catalog.
- **Typography (Ink vs. On-Surface):** Use "Ink" tokens on Paper surfaces (dark teal-greys) and "On-Surface" (white alphas) on Hero surfaces. 
- **Severity:** Use status colors sparingly. They should appear only in pills, indicators, or small icons—never as large background fills.

## Typography

This design system uses **Geist** for standard UI elements and **Geist Mono** for all technical data, telemetry, and versioning.

- **Numeric Data:** Always use `font-variant-numeric: tabular-nums` for monospaced levels to ensure data alignment in the Tool Catalog.
- **Hierarchy:** Display and H1 levels are reserved for the Hero section. For the Tool Catalog marketplace, rely on H2 and H3 for card titles and section headers.
- **Capitalization:** Use Sentence case for all headings and body text. Use Uppercase specifically for "Eyebrow" labels and Severity Pills, combined with the prescribed 0.08em letter spacing.
- **Weight Limit:** Avoid weights above 600 (Semibold) to maintain the "quiet" brand voice.

## Layout & Spacing

The system follows a strict **4pt grid** rhythm. 

- **Tool Catalog (Desktop):** Use a 12-column fixed grid with a max-width of 1280px. Gutters should be 24px (`--s-6`). 
- **Marketplace Cards:** In the tool marketplace, cards should span 3 or 4 columns depending on the information density required.
- **Rhythm:** Maintain significant "air" between sections. Use 48px or 72px for vertical section breaks to prevent the technical data from feeling overwhelming.
- **Safe Areas:** On desktop, ensure a minimum side margin of 48px.

## Elevation & Depth

Visual hierarchy is managed through two distinct layering models:

1.  **The Atmospheric Layer (Hero):** Uses `backdrop-filter: blur(20px)` and semi-transparent backgrounds (`rgba(255,255,255,0.14)`). Edges are defined by a 1px white border at 18% opacity.
2.  **The Physical Layer (Paper):** Uses extremely subtle, "uncolored" (graphite alpha) shadows. 
    - **Resting:** `0 1px 2px rgba(28,36,34,0.04)`
    - **Hovered/Active:** `0 4px 12px rgba(28,36,34,0.06)`

Avoid glows, neon borders, or heavy blurs outside of the Hero context. Use a 14px radial-gradient dot grid (`--dotgrid-dark`) on Hero backgrounds for a technical, blueprint-like texture.

## Shapes

The shape language is "Soft-Technical." It avoids sharp 0px corners but stops short of being "bubbly."

- **Standard Cards:** Use 20px (`rounded-lg`) for marketplace and tool cards.
- **Buttons/Input Fields:** Use 16px to create a distinct, tactile feel.
- **Pills/Badges:** Always use the `rounded-pill` (999px) setting.
- **Data Visuals:** Very small elements like heatmap cells or progress bars should use a 3px to 6px radius to maintain precision.

## Components

### GlassCard (Hero Context)
Used for high-level marketplace banners or featured tool highlights.
- **Background:** `rgba(255, 255, 255, 0.14)` with 20px backdrop blur.
- **Border:** 1px `var(--glass-border)`.
- **Inner Shadow:** `inset 0 1px 0 rgba(255,255,255,0.28)`.

### PaperCard (Catalog Context)
The primary container for tools in the marketplace.
- **Background:** `#ffffff`.
- **Border:** 1px `var(--border-hair)`.
- **Shadow:** `var(--shadow-1)` at rest, `var(--shadow-2)` on hover.

### SeverityPill
- **Style:** All-caps, semibold, 11px.
- **Format:** Background is a desaturated version of the status color; the "Dot" is the high-saturation indicator.
- **Interaction:** On Paper, text should be high-contrast (`--ink-strong`). On Hero, text should be `--mist-surface-700`.

### AppButton
- **Primary:** Background `--mist-surface-800` (Graphite), Text `#ffffff`.
- **Secondary:** Background `#ffffff`, Border `var(--border-strong)`, Text `var(--ink-strong)`.
- **Motion:** On `mousedown`, buttons scale to `0.98` with a 140ms `cubic-bezier(0.32, 0.72, 0.20, 1)` transition.

### Input Fields
- **Surface:** `--paper-soft` or white.
- **Border:** `var(--border-soft)` with a 1px stroke. 
- **Focus:** Border color shifts to `--mist-surface-500` with no outer glow.