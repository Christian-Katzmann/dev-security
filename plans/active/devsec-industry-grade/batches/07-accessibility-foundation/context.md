# Batch: 07-accessibility-foundation

## Purpose
The Mistglass design system is mature but keyboard and low-vision users hit hard walls: there is no visible focus indicator anywhere, the four security-sensitive modals (rotation + AI-write) cannot be dismissed or escaped with the keyboard, and there is no way to skip the 240px sidebar. This batch lays the accessibility floor the dashboard claims (DESIGN.md §11) but does not enforce — a global `:focus-visible` ring (S-040), a shared focus-trapping `Dialog` primitive for all four modals (S-041), a skip-to-content link (S-045) — and adds the a11y test harness (S-047) that guards them so the gap can never silently reopen. The shared fix surface is the dashboard UI's keyboard/focus layer: `dashboard-ui/src/index.css` plus a small set of shared React primitives.

## Source Evidence
- **S-040** — Add one global token-based `:focus-visible` ring on buttons/links/inputs/selects/textareas/clickable cards and replace the two `outline:none` rules · evidence: only two `:focus-visible` rules exist, `index.css:5952` (`.setup-card-input`) and `index.css:5978` (`.setup-card-textarea`), both `outline: none` + a near-invisible `box-shadow: 0 0 0 1px var(--ink-strong)`; the one 3px ring at `index.css:385` is decorative on `.status-dot.live`, not a focus state · synthesis row S-040, lens report 12-design-system-accessibility-health.initial.md (Ranked Health Table rank 2)
- **S-041** — Build one shared `Dialog` primitive (focus trap + Escape-to-close + focus restore) and migrate all four modals · evidence: four `role="dialog"`+`aria-modal` modals with zero Escape/`.focus()` handlers — `RotationTriggerFlow.tsx:321`, `RotationStatusCard.tsx:560`, `AiFollowUpPanel.tsx:232`, `RotationBatchFlow.tsx:272` · synthesis row S-041, lens report 12-design-system-accessibility-health.initial.md (Ranked Health Table rank 1)
- **S-045** — Add an `.sr-only`-revealed "Skip to content" link targeting `<main>` · evidence: no `skip-link`/"Skip to" anywhere in `dashboard-ui/src/`; the `.sr-only` utility already exists at `index.css:4717` and the target `<main className="mist-main">` exists at `App.tsx:1227` · synthesis row S-045, lens report 12-design-system-accessibility-health.initial.md (Ranked Health Table rank 4)
- **S-047** — Add a vitest + jest-axe smoke harness covering button names, dialog semantics, and focus-visible on key views · evidence: `dashboard-ui/package.json` `lint` script is `tsc --noEmit` only; no vitest/jest-axe/@testing-library/playwright present · synthesis row S-047, lens report 12-design-system-accessibility-health.initial.md (Ranked Health Table rank 3)

## Target
Move S-040, S-041, S-045, S-047 from Yellow/Red (the worst among these rows; S-040 and S-041 are Yellow/Red, S-045 and S-047 are Yellow) to Green.

## Dependencies
None of these rows depend on an earlier batch in the matrix. Same-batch ordering: build S-040 (global focus ring) and S-041 (shared Dialog primitive) first, then S-045 (skip link), and do S-047 (the a11y test harness) last — the matrix marks S-047 as depending on S-040 and S-041, since the harness asserts the focus ring and dialog semantics those two deliver.

## Non-Goals
- Do not attempt other batches' super-list items.
- Do not broaden this into a general cleanup (token-inlining drift S-054, dark-mode/high-contrast, severity-by-color S-019/contrast work, and the `App.tsx` monolith split all live in other batches — leave them).
- Do not make production, destructive, deploy, secret, or irreversible data changes without explicit approval.
- Do not start the dashboard server or run a live browser pass unless the task requires it and `.adx/risks.json` allows it; rely on the vitest/jest-axe harness plus `tsc`/`vite build` for evidence (no live axe/Lighthouse render is needed to pass).
- Do not change the four modals' security semantics — only add keyboard handling (trap/Escape/restore); the high/critical suppression and AI-write confirmation behavior must be untouched.
- Do not regress the existing crafted disabled/empty/error/loading states or the already-correct `honey-card` `role="button"`/`tabIndex`/`onKeyDown` keyboard wiring.

## Suggested Starting Steps
1. Re-read this context and acceptance.md.
2. Re-verify each S-ID's evidence against the exact files cited (`index.css:5952`/`:5978`/`:4717`/`:385`, the four modal files at the listed lines, `App.tsx:1227`, `package.json` scripts).
3. Add one global `:focus-visible` rule keyed on a Mistglass token (a visible outline or box-shadow ring with offset) covering `button`, `a`, `input`, `select`, `textarea`, and clickable cards; replace the two `outline:none` rules at `index.css:5952`/`:5978` with that visible ring so no control opts out.
4. Build a single shared `Dialog` React primitive (focus trap on the dialog subtree, `Escape`-to-close, focus restore to the previously-focused element on unmount) and migrate all four modals (`RotationTriggerFlow`, `RotationStatusCard`, `AiFollowUpPanel`, `RotationBatchFlow`) onto it, preserving each one's existing content, backdrop, and security behavior.
5. Add an `.sr-only`-revealed "Skip to content" anchor as the first focusable element on the page, targeting the `<main className="mist-main">` region at `App.tsx:1227` (add an `id`/`tabIndex={-1}` to `<main>` so focus actually lands there).
6. Add vitest + jest-axe + @testing-library to `dashboard-ui`, wire a `test` script, and write smoke specs that assert `toHaveNoViolations` on key rendered views, that each migrated dialog traps/escapes, and that controls expose a focus-visible style; implement the smallest root-cause fix that satisfies every acceptance criterion.
