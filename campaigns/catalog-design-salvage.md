# Catalog UI Design Salvage

> The catalog page in DëvSec got too busy — it tries to do five things on one screen. This plan splits it into four cleaner pages, removes the clutter, and rebuilds each page to match the original mockups.

## Scope

The Catalog Storefront and Managed Security Packs campaigns shipped working code, but the UI collapsed five separate mockup screens into one overloaded `/catalog` route. This campaign fixes that. Done means the catalog lives across four routes — Catalog Home, Browse, Tool Detail, Pack Detail — each matching its mockup, each passing the DESIGN.md §15 build checklist, and each carrying a single primary action with 30–40% air. Backend stays untouched. This is structural IA, component decomposition, and CSS work.

## Context (locked decisions)

- **IA**: four routes — `/catalog` (home), `/catalog/browse`, `/catalog/tool/:id`, `/catalog/pack/:id`. No more pinned side panels and no more "every section at once."
- **Mockup mapping** (under `temporaty design mockups/`): `marketplace/` → home; `(4)/` → browse; `(1)/` → tool detail; `(2)/` → pack detail; `(3)/` → reference variant for a future hero treatment.
- **DESIGN.md is canon.** Smell test (`30–40% air, sentence case, one primary action, no pulsing decoration`) is the merge bar. The §15 build checklist is the verification surface.
- **Backend is untouched.** `/api/tool-catalog`, `/api/security-packs`, `/api/install-preview`, install/uninstall POSTs all stay as they are. No Python edits.
- **No backend tests change.** UI work only — `uv run pytest` should still pass at the end.
- **Component decomposition target**: extract catalog code from `App.tsx` into `dashboard-ui/src/components/catalog/*` files. App.tsx is over 3,500 lines and the catalog work is the cleanest chunk to split out.
- **Routing approach**: extend the existing `tab` state pattern in App.tsx with a `catalogRoute` substate first. Real router can come later if the pattern proves itself; don't bring in `react-router` just for this.
- **Branch**: `catalog-design-salvage`, off `main`. Merge to `main` when Final review is APPROVED. The page is intentionally broken between Phase 2 (demolition) and the end of Phase 3 (last route rebuilt); the branch keeps that ugliness out of `main`.
- **Skill**: use `/craft` for the four rebuild steps. Each route gets its own session — single screen, single skill, single mockup pinned.
- **External Surface stays display-only** across all routes. No regression of the safety rule.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — IA and scaffolding

- [x] Step 1.1 — Decide routing and split CatalogView into four route shells
- [x] Step 1.2 — Extract catalog data hooks and types

### Phase 2 — Demolition

- [x] Step 2.1 — Delete violating chrome and quiet the bold labels

### Phase 3 — Rebuild each route against its mockup

- [x] Step 3.1 — Build the Catalog Home route (sets the tone)
- [x] Step 3.2 — Build the Catalog Browse route
- [ ] Step 3.3 — Build the Tool Detail route
- [ ] Step 3.4 — Build the Pack Detail route

### Phase 4 — Tone sweep and validation

- [ ] Step 4.1 — Token, weight, and copy sweep across all four routes
- [ ] Step 4.2 — Mockup-vs-implementation screenshot review and §15 checklist
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Decide routing and split CatalogView into four route shells

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Pick the smallest routing primitive that supports four distinct catalog screens without dragging `react-router` into the project. Then create empty shells for the four routes so the demolition and rebuild steps have somewhere to land. The current `CatalogView` becomes the entry point for `CatalogHome`; the rest of `ToolCatalogBrowse` will be replaced.

```text
SCOPE: Add a four-route catalog IA to the dashboard and create empty shells for each route.
REQUIRED READING:
1. DESIGN.md
2. dashboard-ui/src/App.tsx
3. dashboard-ui/src/dashboardData.ts
4. dashboard-ui/src/index.css
5. campaigns/catalog-design-salvage.md
6. temporaty design mockups/stitch_d_vsec_tool_marketplace/screen.png
7. temporaty design mockups/stitch_d_vsec_tool_marketplace (4)/screen.png
8. temporaty design mockups/stitch_d_vsec_tool_marketplace (1)/screen.png
9. temporaty design mockups/stitch_d_vsec_tool_marketplace (2)/screen.png
OUTPUT:
- New files under dashboard-ui/src/components/catalog/: CatalogHome.tsx, CatalogBrowse.tsx, CatalogToolPage.tsx, CatalogPackPage.tsx — each a placeholder component that renders its name and a "Coming up" line.
- A catalogRoute substate added to App.tsx alongside the existing tab state. Default route is "home". The Tool Catalog tab routes to CatalogHome; navigation between catalog routes uses simple callbacks (onOpenTool, onOpenPack, onOpenBrowse, onBack).
- Keep the existing CatalogView export wired so nothing 404s during the transition, but route the Tool Catalog tab through the new CatalogHome shell.
- TypeScript types check; the dashboard renders without errors. No visual polish yet.
OPEN QUESTIONS:
- Should breadcrumb/back navigation use a single "Back to Catalog" link, or per-route labels (e.g. "Back to Browse")? Decide and document in a comment.
- Does any other view link into the catalog by deep URL today? Audit `dashboardData.ts` and any `openTab` callers — if there are deep entry points, they must still work after this split.
```

## Step 1.2 — Extract catalog data hooks and types

Model: Opus 4.7 · High / GPT-5.5 · High
Parallel: NO

Pull the catalog data plumbing out of `ToolCatalogBrowse` so all four route shells can share it. No design changes in this step — the goal is one place that owns catalog state, mutations, and runtime mapping, so the rebuild steps don't each re-derive it.

```text
SCOPE: Extract a useCatalogData hook (or equivalent module) that exposes catalog items, security packs, runtime map, install/uninstall mutations, and the mutation state machine.
REQUIRED READING:
1. dashboard-ui/src/App.tsx
2. dashboard-ui/src/dashboardData.ts
3. dashboard-ui/src/components/catalog/CatalogHome.tsx (from Step 1.1)
OUTPUT:
- A new dashboard-ui/src/components/catalog/useCatalogData.ts (or .tsx) exposing the catalog data and mutation handlers currently embedded in ToolCatalogBrowse.
- The four route shells from Step 1.1 import the hook but don't yet render the data — keep the placeholders visible.
- App.tsx no longer holds catalog-specific derivation helpers that are only used inside the catalog routes; those move under components/catalog/.
- npm run lint and npm run build both pass.
OPEN QUESTIONS:
- Which derived helpers (catalogStatusBucket, catalogRuntimeMap, securityPackTone, etc.) belong inside the hook vs. as pure functions next to it? Lean toward pure functions — they're easier to test and don't capture state.
- Does the install/uninstall mutation state need to survive route changes? If yes, lift it into the hook; if no, scope it to the route that owns it.
```

## Step 2.1 — Delete violating chrome and quiet the bold labels

Model: Opus 4.7 · High / GPT-5.5 · High
Parallel: NO

Subtractive step. The current `/catalog` page violates the DESIGN.md smell test (under 30% air, no clear primary action, posture buried under filter chrome). Delete the worst offenders before rebuilding — leaving the page intentionally bare so Step 3.1 starts from a clean canvas.

```text
SCOPE: Remove decorative chrome that violates DESIGN.md from the current ToolCatalogBrowse view and quiet bold-mono labels.
REQUIRED READING:
1. DESIGN.md (especially §0 smell test, §3.6 type weight cap, §15 build checklist)
2. dashboard-ui/src/App.tsx (ToolCatalogBrowse and adjacent functions)
3. dashboard-ui/src/index.css (lines 1455 onward — .catalog-* selectors)
OUTPUT:
- Remove the 4-metric .catalog-hero-metrics row from the catalog hero.
- Remove the 7-chip .catalog-state-strip below the hero.
- Collapse the double-row filter chrome (.catalog-controls + .catalog-filter-row + pack filter strip) — leave a single search input and a single category chip row, max 6 chips. Save the deletion as a clean diff so the rebuild can put filters back where they belong per mockup.
- Remove the permanent right-hand selected-tool / selected-pack side panel from ToolCatalogBrowse — detail becomes a route, not a sibling component.
- Remove the "Future coverage" / display-only grid from the home view; it will be reintroduced as part of the appropriate route in Phase 3.
- Quiet bold mono labels: any selector setting `font: 600 N var(--font-mono)` on non-telemetry text drops to `t-caption` or `t-h3`. Mono stays only on numbers, IDs, paths, and timestamps.
- Page renders without errors; lint and build pass; the catalog is allowed to look sparse — that's the point.
OPEN QUESTIONS:
- Is anything in the deleted chrome carrying information that doesn't exist elsewhere? If a count or label is only visible in the chrome being removed, surface it in the rebuild brief for the matching route in Phase 3 rather than reintroducing the chrome.
- Are any of the CSS selectors used outside the catalog? Grep before deleting; if yes, narrow the deletion to catalog-scoped variants.
```

## Step 3.1 — Build the Catalog Home route (sets the tone)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The smallest, most opinionated route. This one sets the visual rhythm the other three inherit. Match mockup `stitch_d_vsec_tool_marketplace/` (the base): hero banner with one CTA, Featured Security Packs row (3 cards), Popular Plugins row (4 cards). Nothing else.

```text
/craft

SCOPE: Build the /catalog home route matching the base marketplace mockup.
REQUIRED READING:
1. DESIGN.md (entire file — the smell test, principles, components, voice)
2. temporaty design mockups/stitch_d_vsec_tool_marketplace/screen.png
3. temporaty design mockups/stitch_d_vsec_tool_marketplace/code.html
4. temporaty design mockups/stitch_d_vsec_tool_marketplace/DESIGN.md
5. dashboard-ui/src/components/catalog/CatalogHome.tsx
6. dashboard-ui/src/components/catalog/useCatalogData.ts
7. dashboard-ui/src/index.css
OUTPUT:
- CatalogHome.tsx renders three sections: hero banner (one headline + one supporting sentence + one primary "Browse all tools" CTA + one illustrative panel), Featured Security Packs (exactly 3 pack cards — pick which 3 in code, default to the first three "real" MVP packs), Popular Plugins (exactly 4 tool cards — picked by some honest signal like "missing in the most packs" or "installed locally").
- Each pack card and plugin card matches its mockup card: name, one-paragraph summary, one CTA per card ("View Bundle" / "One-click install"), no severity chips on the home cards, no install-state chips on the home cards.
- Clicking a pack card routes to /catalog/pack/:id (the shell from Step 1.1). Clicking a plugin card routes to /catalog/tool/:id. Clicking "Browse all tools" routes to /catalog/browse.
- 30–40% air on the rendered page at desktop and mobile. Sentence case throughout. One primary action visible above the fold.
- CSS lives in a clearly-commented `/* --- CatalogHome --- */` section of index.css; reuse existing tokens, never paste hex.
- npm run lint and npm run build pass.
OPEN QUESTIONS:
- Which 3 packs are "featured"? Pick a rule in code, not a hand-curated list — e.g. first three MVP packs in catalog order, or top 3 by ready-tool count.
- Which 4 plugins are "popular"? Same — pick an honest rule (e.g. tools belonging to the most packs, or first 4 missing tools sorted by category) and document the rule in a code comment.
- Does the hero illustration need a real asset, or does a `--paper-deep` block with an icon read enough at this stage? Decide and ship the simpler one first; flag in the PR if a real asset is needed.
```

## Step 3.2 — Build the Catalog Browse route

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The list view. Match mockup `stitch_d_vsec_tool_marketplace (4)/`: featured tool banner, single filter chip row (5–6 chips max), 4-up tool grid. No side panel. Cards in the grid carry one severity hint (priority) and a one-paragraph summary, nothing more.

```text
/craft

SCOPE: Build the /catalog/browse route matching the featured-tool browse mockup.
REQUIRED READING:
1. DESIGN.md
2. temporaty design mockups/stitch_d_vsec_tool_marketplace (4)/screen.png
3. temporaty design mockups/stitch_d_vsec_tool_marketplace (4)/code.html
4. dashboard-ui/src/components/catalog/CatalogBrowse.tsx
5. dashboard-ui/src/components/catalog/useCatalogData.ts
6. dashboard-ui/src/index.css
OUTPUT:
- CatalogBrowse.tsx renders: a featured tool banner (matching mockup 4 — "Featured: <tool>" headline, one-paragraph summary, primary "Install" CTA, secondary "View Docs" link, illustrative panel), a single filter chip row beneath the banner ("All Tools" + 4–5 category chips, no second status row), and a 4-up grid of tool cards.
- Card anatomy: small category icon, one priority pill (sparingly — DESIGN.md severity rule), tool name (h3), one-paragraph summary, version on left and license on right in mono at the bottom.
- Clicking a card routes to /catalog/tool/:id.
- Search input lives in the top toolbar (existing pattern), not duplicated in the page body.
- Coming Soon tools are still visible but visibly quieter — muted card variant, no install button.
- Layout responsive: 4-up at desktop, 2-up at tablet, 1-up at mobile.
- 30–40% air; one primary action (the Install button on the featured banner).
- npm run lint and npm run build pass.
OPEN QUESTIONS:
- Which tool gets the "featured" slot, and how is it picked? Rule in code, not a hand-curated string.
- Should the priority pill ("Critical Path" / "High Priority" / "Standard" in mockup 4) be derived from policy fields or category? Mockup-style critical/high tags must come from real signal — pick one (e.g. derived from policy.needs_approval + category) and document.
- Does the filter row need a horizontal scroll on mobile, or do chips wrap? Pick the calmer option.
```

## Step 3.3 — Build the Tool Detail route

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The full tool page. Match mockup `stitch_d_vsec_tool_marketplace (1)/`: hero block with name + version pill + Install / Snooze actions, two-column body with Overview + Core Capabilities on the left and a Technical Specs sidebar on the right. Replace the current side-panel-only detail.

```text
/craft

SCOPE: Build the /catalog/tool/:id route matching the OpenSSL Scanner mockup.
REQUIRED READING:
1. DESIGN.md
2. temporaty design mockups/stitch_d_vsec_tool_marketplace (1)/screen.png
3. temporaty design mockups/stitch_d_vsec_tool_marketplace (1)/code.html
4. dashboard-ui/src/components/catalog/CatalogToolPage.tsx
5. dashboard-ui/src/components/catalog/useCatalogData.ts
6. dashboard-ui/src/index.css
7. src/security_observatory/catalog.py (for what fields actually exist — don't invent specs)
OUTPUT:
- CatalogToolPage.tsx renders: a hero block (back link, icon, tool label, "verified by DëvSec Core" eyebrow, Snooze + Install actions), an Overview card with the tool description, a Core Capabilities list (3–5 items derived from capabilities.finding_categories + evidence_types), and a Technical Specs sidebar (Version, Last Updated if known, License if known, Requirements). A "Read Documentation" link card sits under the sidebar.
- Install button is enabled only when the tool's install_preview supports execution (i.e. the Gitleaks managed proof path). Otherwise it shows the next-step copy and is visually quieter.
- Display-only tools (External Surface): no Install button, no Snooze, replace with a single "Display only" note matching the catalog rules.
- All policy / safety / permissions data the existing CatalogSelectedTool exposed gets surfaced — but laid out as a calm two-column page, not a stacked panel. Anything that doesn't belong on the first screen goes below the fold under clearly labelled sections.
- One primary action; 30–40% air; sentence case everywhere except severity pills and eyebrows.
- CSS in a `/* --- CatalogToolPage --- */` section. No new tokens; reuse DESIGN.md tokens.
- npm run lint and npm run build pass.
OPEN QUESTIONS:
- The mockup shows "v3.0.13", "4.2 MB", "Yesterday", "Apache 2.0" — only some of those are real data DëvSec has. Surface what's real (version from the install contract if present), show "—" for what isn't, and add a TODO comment explaining what backend field would be needed to fill the gap.
- Should the page be scrollable as one column on mobile, or keep the spec sidebar at the bottom? Calmer wins.
```

## Step 3.4 — Build the Pack Detail route

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The pack page. Match mockup `stitch_d_vsec_tool_marketplace (2)/`: large hero block with curated bundle eyebrow + headline + summary + Install Bundle / View Contents CTAs + illustrative panel, then an "Essential Utilities" grid of the included tools.

```text
/craft

SCOPE: Build the /catalog/pack/:id route matching the Zero-Trust Foundational Pack mockup.
REQUIRED READING:
1. DESIGN.md
2. temporaty design mockups/stitch_d_vsec_tool_marketplace (2)/screen.png
3. temporaty design mockups/stitch_d_vsec_tool_marketplace (2)/code.html
4. dashboard-ui/src/components/catalog/CatalogPackPage.tsx
5. dashboard-ui/src/components/catalog/useCatalogData.ts
6. dashboard-ui/src/index.css
7. src/security_observatory/catalog.py (for pack definitions)
8. docs/security-packs.md
OUTPUT:
- CatalogPackPage.tsx renders: a hero block (back link, "CURATED BUNDLE" eyebrow + week or version number, pack name as display headline, one-paragraph summary, primary "Install Bundle" CTA and secondary "View Contents" — both disabled for MVP since broad pack install is deferred; copy explains why), and an Essential Utilities grid of included tools (2-up at desktop, each card showing tool name, one-line summary, status chip, a single CTA, and the role chip from pack membership).
- Coming Soon packs: hero block shows the Coming Soon state clearly (no Install Bundle button, copy explains that broad pack install is deferred), the utilities grid still shows the tools that would be in the pack with their install state.
- A "Recommended scan profile" line lives under the hero (one short sentence + one CTA "Open profile" that hooks into the existing run-checks flow).
- One primary action; 30–40% air; reuse the visual rhythm of Step 3.1's home cards so the home → pack transition feels coherent.
- CSS in a `/* --- CatalogPackPage --- */` section. No new tokens.
- npm run lint and npm run build pass.
OPEN QUESTIONS:
- "Install Bundle" is shown but disabled in MVP. What's the exact copy that explains this without making the page feel broken? Draft 2 options and ship the calmer one.
- Should display-only packs (External Surface) get the same hero shape but with stronger Coming Soon framing, or a smaller hero? Calmer wins.
- The mockup's "ENTERPRISE", "FREE", "PRO" tier badges on tool cards don't map to DëvSec data. Drop them silently or replace with the pack-role chip ("Included" / "Optional" / "Coming Soon")? Pick replacement, not silent deletion.
```

## Step 4.1 — Token, weight, and copy sweep across all four routes

Model: Opus 4.7 · High / GPT-5.5 · High
Parallel: NO

Mechanical pass with taste. After the four rebuilds, walk every catalog file and confirm DESIGN.md tokens are used, no font-weight > 600 anywhere, mono is reserved for telemetry, no pasted hex values, and copy follows the §10 voice patterns. Fix in place.

```text
SCOPE: Sweep all four catalog routes for DESIGN.md token/weight/voice violations and fix in place.
REQUIRED READING:
1. DESIGN.md (especially §3 tokens, §3.6 type weight, §10 voice, §15 checklist)
2. dashboard-ui/src/components/catalog/CatalogHome.tsx
3. dashboard-ui/src/components/catalog/CatalogBrowse.tsx
4. dashboard-ui/src/components/catalog/CatalogToolPage.tsx
5. dashboard-ui/src/components/catalog/CatalogPackPage.tsx
6. dashboard-ui/src/index.css (catalog-scoped sections)
OUTPUT:
- No font-weight > 600 in any catalog selector. Anything bolder drops to 600.
- No `var(--font-mono)` on non-telemetry text. Mono stays for version numbers, IDs, paths, timestamps, single-number telemetry.
- No pasted hex values in catalog CSS. Every color goes through a DESIGN.md token.
- No #000 or #fff on paper or hero respectively; use --ink* / --on-surface*.
- All copy: sentence case headlines, UPPERCASE only for eyebrows and severity pills, mono-lowercase for technical strings.
- "Critical" severity is earned, not decorative — confirm no card is using critical color when the underlying signal is just "missing tool".
- No looping animations, no shimmer skeletons, no pulsing dots — confirm none were reintroduced.
- npm run lint and npm run build pass.
OPEN QUESTIONS:
- Are there any places where a stronger weight is genuinely needed for legibility (e.g. tiny eyebrow chips)? Document the one or two exceptions in a code comment if so — don't quietly violate.
- Is any catalog copy using "Click here" / "Tap to" / second-person imperatives that read as marketing? Rewrite per §10.4 voice patterns.
```

## Step 4.2 — Mockup-vs-implementation screenshot review and §15 checklist

Model: Opus 4.7 · High / GPT-5.5 · High
Parallel: NO

The verification surface. Run the dashboard, navigate every catalog route at desktop and mobile widths, screenshot each route, place it next to its mockup, walk the DESIGN.md §15 checklist for each. Record the result. Fix any gaps before declaring the campaign ready for Final review.

```text
SCOPE: Verify all four catalog routes against their mockups and the DESIGN.md §15 build checklist.
REQUIRED READING:
1. DESIGN.md (§15 build checklist)
2. .adx/commands.json
3. temporaty design mockups/stitch_d_vsec_tool_marketplace/screen.png
4. temporaty design mockups/stitch_d_vsec_tool_marketplace (4)/screen.png
5. temporaty design mockups/stitch_d_vsec_tool_marketplace (1)/screen.png
6. temporaty design mockups/stitch_d_vsec_tool_marketplace (2)/screen.png
OUTPUT:
- Run dashboard-lint and dashboard-build from .adx/commands.json; both pass.
- Start the local dashboard, take desktop (≥1280px) and mobile (375px) screenshots of each of the four catalog routes (8 screenshots total). Save under reports/campaign-automation/catalog-design-salvage/ as step-4.2-<route>-<viewport>.png.
- For each route, write a short paragraph confirming or denying alignment with its mockup, calling out the specific §15 items checked (surface, headline case + weight, tabular-nums, icon stroke, one primary action, severity scope, no #fff/#000, no looping motion, prefers-reduced-motion honored, tap targets ≥ 44 px, empty/loading/error states drawn, voice patterns).
- If anything fails the checklist, fix in place and re-screenshot. The validation isn't done until every box is checked.
- Stop the dashboard when finished.
OPEN QUESTIONS:
- Are there any catalog states (e.g. zero packs ready, zero tools installed) that can't be reached with current test data? Document the gap rather than faking it.
- Does anything regress in the rest of the dashboard (Findings, Honey keys, Overview)? Walk the other tabs at desktop and confirm no styling bled into them.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the Catalog UI Design Salvage campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/catalog-design-salvage.md
Campaign: campaigns/catalog-design-salvage.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff that the criteria actually landed. Don't trust step receipts — read the diff.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas.

Be honest. Lean. APPROVED if every step's acceptance criteria landed and there are no cross-step regressions. NEEDS WORK if any step cut corners or a primitive was bypassed.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.7 with Extra High thinking
(Your call — both are acceptable for this kind of cross-file review.)
```

**Verdict-to-action mapping:**

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign"). Campaign is done.
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick the checkbox until APPROVED.
