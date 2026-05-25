# Tool branding discipline

Each tool in the Tool Catalog ships two pieces of brand evidence — and only
two:

1. **A logo**, stored under `dashboard-ui/public/tool-logos/<id>.svg`.
2. **One accent color**, stored as a hex on the catalog entry under
   `branding.accent_color`.

The logo replaces the generic category icon on cards and the hero. The
accent color renders as a 4px stripe on the left edge of the card and a 1px
underline beneath the tool name on the detail page. That's the whole
contract.

Reference patterns: VS Code Marketplace, Raycast Store, Linear integrations.
Each tool gets recognition — never a takeover.

## What we don't brand

If you find yourself reaching for any of these, stop:

- Background color of cards, sections, hero, or page.
- Font, font weight, letter-spacing, or text color of the tool name.
- Card shape, border-radius, padding, or shadow.
- Per-tool gradients, illustrations, or decorative chrome.
- Hover states tied to brand color.

DëvSec's chrome stays uniform. The 4px stripe and the 1px underline are the
only places where tool-side brand color appears. If a future request reads
"can we tint X for tool Y?" the answer is no.

## Why subtraction

The catalog browse grid renders 16+ tools side by side. If every card had
its own background, font, or shadow the grid would feel chaotic — closer to
sponsored ads than to a curated catalog. The VS Code Marketplace pattern
proves restraint scales: identical card shape, identical typography, one
splash of brand color per row, and the eye reads each tool individually
without losing the grid as a whole.

The accent stripe is enough signal because DëvSec's chrome is already low-
chroma sage/paper. A single 4px column of brand color carries the
recognition load without competing with content.

## Adding a new tool

1. Source the logo. Prefer SVG from the tool's official repo (`brand/`,
   `assets/`, or the README header). PNG fallback if no SVG ships. Trademark
   policies vary — most OSS projects allow logo use under brand guidelines,
   but record any explicit-permission requirements in `step-3.1.md`'s
   license audit table.
2. Sample one accent color from the wordmark. Use a color picker; don't
   guess. Store as a 6- or 7-char hex.
3. Drop the SVG into `dashboard-ui/public/tool-logos/<id>.svg`.
4. Populate `branding=ToolBranding(accent_color="#XXXXXX", logo="<id>.svg")`
   on the entry in `src/security_observatory/catalog.py`.
5. That's it. No CSS, no component changes, no per-tool React.

Tools without a published wordmark or with a generic icon fall back to the
category icon + DëvSec's own accent (`#3c4b48`). That's the default and it
is *fine*. A naked accent stripe still reads as "this card belongs to a
tool" — the empty state isn't a bug.

## Built-in DëvSec tools

The 4 DëvSec-internal built-ins (`ioc-watch`, `install-hooks`,
`workflow-audit`, `ai-static`) inherit the DëvSec accent — same visual
language as external tools, just sourced from DëvSec instead of an upstream
project. They don't need or get external logos.

## Where this lives in code

- Schema: `ToolBranding` dataclass in `src/security_observatory/catalog.py`.
- Defaults: `DEVSEC_ACCENT = "#3c4b48"` in the same file.
- TypeScript mirror: `ToolBranding` type in `dashboard-ui/src/dashboardData.ts`.
- Render helpers: `toolLogo()` and `toolAccent()` in
  `dashboard-ui/src/components/catalog/catalogHelpers.tsx`.
- Card CSS: `.catalog-browse-card::before` (the stripe) and
  `.catalog-browse-card-icon` (the logo tile) in
  `dashboard-ui/src/index.css`.
- Hero CSS: `.catalog-tool-hero-title` (the underline) and
  `.catalog-tool-hero-icon` (the logo tile) in the same file.

Every brand surface routes through these. There is no per-tool component
and no per-tool stylesheet. If a future change wants more brand surface,
push back; if it's worth it, change the discipline here first, then ship.
