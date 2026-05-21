# Tool Catalog Storefront

> Make the Tool Catalog feel like an app store for security capability. People should be able to browse tools, understand them, and know what is safe before they install or run anything.

## Scope

This campaign designs and builds the dashboard storefront for the DëvSec Tool Catalog. Done means the app has a clear catalog navigation area, searchable/filterable tool cards, polished tool detail pages, safety labels derived from backend policy, install-state language, and Coming Soon treatment for future packs such as External Surface.

## Context (locked decisions)

- Tool Catalog is the app-store layer for individual tools, plugins, apps, MCP connectors, and scanners.
- Security Packs are curated bundles, but individual tool pages are the heart of trust.
- Catalog UX must reduce cognitive load: users should not need to know what Semgrep, Trivy, or Nuclei are before DëvSec explains them.
- Docker is optional and should not dominate the UI.
- `docs/tool-catalog.md` is the source of truth for catalog vocabulary, categories, states, and policy labels. This campaign consumes that contract; it should not redefine it.
- `DESIGN.md` is the canonical Mistglass design system for dashboard UI work. Mockups under `temporaty design mockups/` are wireframe references only.
- The storefront is read-first in MVP: browsing, detail pages, install status, disabled or preview actions, and clear missing-tool states before broad install/uninstall.
- Storefront owns individual tool browsing and detail pages. Managed Security Packs owns real pack pages, pack status, pack preview flows, and install proof flows.
- Storefront may show pack membership badges and Coming Soon pack cards, but it should not build full pack pages or pack execution controls.
- External Surface Pack is a visible Coming Soon placeholder for now.
- External Surface is display-only in MVP: no target input, no domain probing, no active recon, and no agent-triggered external scans.
- The existing dashboard already has a Scanners view; this campaign may evolve it into Catalog without breaking current scan workflows.

## Prerequisites

- Tool Catalog Foundation has defined `docs/tool-catalog.md` as the canonical catalog contract.
- Catalog entries expose backend policy fields, derived safety labels, and detection-backed install states.
- Coming Soon and External Surface states exist in the catalog contract before UI work depends on them.
- Root `DESIGN.md` has been read before visual implementation begins.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Experience design

- [x] Step 1.1 — Design the catalog IA and detail model

### Phase 2 — Storefront implementation

- [x] Step 2.1 — Add catalog navigation and browse view
- [x] Step 2.2 — Add tool detail pages and safety panels
- [x] Step 2.3 — Add empty, missing, coming-soon, and detected-install states

### Phase 3 — Polish and verification

- [x] Step 3.1 — Tune responsive layout and copy
- [x] Step 3.2 — Validate dashboard build and screenshot review
- [x] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Design the catalog IA and detail model

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Decide how users move through the catalog and understand individual tools: browsing by category, searching by job, seeing pack membership, moving from a scan gap to the right tool page, and reading one trustworthy detail page.

```text
/human-centered-design

SCOPE: Design the information architecture and tool detail model for the DëvSec Tool Catalog storefront.
REQUIRED READING:
1. README.md
2. DESIGN.md
3. docs/tool-catalog.md
4. docs/tool-catalog-current-scanners.md
5. docs/scanners.md
6. dashboard-ui/src/App.tsx
7. dashboard-ui/src/dashboardData.ts
8. dashboard-ui/src/index.css
9. temporaty design mockups/stitch_d_vsec_tool_marketplace (4)/screen.png
10. temporaty design mockups/stitch_d_vsec_tool_marketplace (1)/screen.png
11. temporaty design mockups/stitch_d_vsec_tool_marketplace/screen.png
12. temporaty design mockups/stitch_d_vsec_tool_marketplace (3)/screen.png
OUTPUT: A concise UX plan in docs/tool-catalog-storefront.md covering navigation, filters, categories, search, card hierarchy, pack membership badges, Coming Soon pack cards, tool detail sections, plain-English copy rules, policy-derived safety label display, install-state display, and how the existing Scanners view should evolve. Consume docs/tool-catalog.md as the source of truth rather than redefining states. Use DESIGN.md as the visual source of truth and the mockup screenshots as wireframe references only. The dark mockup may inspire illustrated card treatments, but not the default page mood. Defer full pack pages and pack preview flows to the Managed Security Packs campaign.
OPEN QUESTIONS:
- Should the nav label become Tool Catalog immediately, or should Scanners remain until install/uninstall exists?
- Which categories should be first-class in the UI?
- How do we explain dangerous or advanced tools without making them attractive toys?
```

## Step 2.1 — Add catalog navigation and browse view

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Build the browse surface using existing dashboard patterns. Keep the first version useful even if install buttons are disabled, preview-only, or not yet wired.

```text
/frontend-design

SCOPE: Implement the Tool Catalog browse experience in the React dashboard.
REQUIRED READING:
1. docs/tool-catalog-storefront.md
2. DESIGN.md
3. dashboard-ui/src/App.tsx
4. dashboard-ui/src/dashboardData.ts
5. dashboard-ui/src/index.css
6. temporaty design mockups/stitch_d_vsec_tool_marketplace (4)/screen.png
7. temporaty design mockups/stitch_d_vsec_tool_marketplace/screen.png
8. temporaty design mockups/stitch_d_vsec_tool_marketplace (3)/screen.png
OUTPUT: Dashboard changes that add a catalog browse view with category filters, search, tool cards, policy-derived safety labels, install status, pack membership badges, and Coming Soon cards for future surfaces. Preserve existing scan-running behavior and avoid inventing UI-only states not backed by the catalog contract. Use the mockups for layout rhythm and card illustration ideas only; do not copy conflicting copy, install claims, or the dark mockup's full theme. Do not build full pack pages here.
OPEN QUESTIONS:
- Should this replace the Scanners tab or add a sibling Tool Catalog tab for the first pass?
```

## Step 2.2 — Add tool detail pages and safety panels

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Turn each card into a real page or panel. The user should leave with an intuitive understanding of what the tool does and what it costs or risks.

```text
/frontend-design

SCOPE: Implement tool detail pages or panels for the DëvSec Tool Catalog.
REQUIRED READING:
1. docs/tool-catalog-storefront.md
2. DESIGN.md
3. dashboard-ui/src/App.tsx
4. dashboard-ui/src/dashboardData.ts
5. dashboard-ui/src/index.css
6. temporaty design mockups/stitch_d_vsec_tool_marketplace (1)/screen.png
OUTPUT: UI changes for a tool detail experience with purpose, what it checks, policy-derived safety labels, permissions, install options, scan profiles, pack membership, docs links, last-run/availability state, and disabled or preview install/uninstall affordances when backend actions are not ready. Use the detail mockup for page anatomy, not its exact copy or tool assumptions. Keep pack detail navigation shallow until Managed Security Packs owns it.
OPEN QUESTIONS:
- Should detail pages be route-like internal state, modal panels, or side panels in the current single-page app?
```

## Step 2.3 — Add empty, missing, coming-soon, and detected-install states

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

A security app loses trust when states are vague. Make every state clear: built in, managed, detected, missing, unavailable, or coming soon.

```text
SCOPE: Add clear catalog UI states for every install and availability condition.
REQUIRED READING:
1. docs/tool-catalog.md
2. docs/tool-catalog-storefront.md
3. DESIGN.md
4. dashboard-ui/src/App.tsx
5. dashboard-ui/src/dashboardData.ts
OUTPUT: UI copy and components for built-in tools, DëvSec-managed installs, existing system installs, missing tools, disabled install actions, errors, and Coming Soon tools/packs. Include an External Surface Pack placeholder with no target input, no scan button, and no active scan execution.
OPEN QUESTIONS:
- Which states should use warning color, and which should stay neutral to avoid panic?
```

## Step 3.1 — Tune responsive layout and copy

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 3.2

Polish the catalog so it feels like a product, not an admin table. Keep it dense enough for operators but friendly enough for non-security users.

```text
/frontend-design

SCOPE: Polish the Tool Catalog storefront layout, responsiveness, and copy.
REQUIRED READING:
1. DESIGN.md
2. dashboard-ui/src/App.tsx
3. dashboard-ui/src/index.css
4. docs/tool-catalog.md
5. docs/tool-catalog-storefront.md
6. temporaty design mockups/stitch_d_vsec_tool_marketplace (4)/screen.png
7. temporaty design mockups/stitch_d_vsec_tool_marketplace (1)/screen.png
8. temporaty design mockups/stitch_d_vsec_tool_marketplace/screen.png
9. temporaty design mockups/stitch_d_vsec_tool_marketplace (3)/screen.png
OUTPUT: Styling and copy refinements so cards and detail panels scan well on desktop and mobile, safety labels fit without overlap, and Coming Soon states feel intentional rather than broken. Keep vocabulary aligned to docs/tool-catalog.md and visual decisions aligned to DESIGN.md. Consider restrained illustrated accents for cards where they clarify category or pack identity.
OPEN QUESTIONS:
- Does the page feel like an app store for security capability, or just a scanner list?
```

## Step 3.2 — Validate dashboard build and screenshot review

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 3.1

Run the dashboard checks and inspect the UI in a browser. This is the step that catches cramped cards, missing states, and bad responsive behavior.

```text
SCOPE: Validate the Tool Catalog storefront implementation.
REQUIRED READING:
1. .adx/commands.json
2. DESIGN.md
3. dashboard-ui/package.json
4. dashboard-ui/src/App.tsx
5. dashboard-ui/src/index.css
6. temporaty design mockups/stitch_d_vsec_tool_marketplace (4)/screen.png
7. temporaty design mockups/stitch_d_vsec_tool_marketplace (1)/screen.png
OUTPUT: Run dashboard lint/build commands from .adx/commands.json as appropriate. Start a local dashboard only if needed for visual review, then stop it when done. Capture screenshots or notes for desktop and mobile layout issues, comparing against DESIGN.md and the useful mockup patterns. Confirm the UI does not show External Surface inputs or imply unavailable tools already ran.
OPEN QUESTIONS:
- Are there any catalog states that cannot currently be reached with available test data?
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the Tool Catalog Storefront campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/catalog-storefront.md
Campaign: campaigns/catalog-storefront.md

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
