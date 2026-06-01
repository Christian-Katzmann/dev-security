# Implementation Receipt: 07-accessibility-foundation

## Target

- Plan: `plans/active/devsec-industry-grade/`
- Batch: 07-accessibility-foundation
- Source report item(s): S-040, S-041, S-045, S-047 (lens 12-design-system-accessibility-health)

## Before Health

Re-verified against the current tree (line numbers had drifted from the cited evidence; trusted the code):

- **S-040** (Yellow/Red): only two `:focus-visible` rules existed — `.setup-card-input` (`index.css:6070`) and `.setup-card-textarea` (`index.css:6096`), both `outline: none` + a near-invisible `box-shadow: 0 0 0 1px var(--ink-strong)`. No global focus ring. Nine base rules also set `outline: 0`.
- **S-041** (Yellow/Red): four `role="dialog"` + `aria-modal` modals with zero Escape / `.focus()` handling — `RotationTriggerFlow.tsx:321`, `RotationStatusCard.tsx:560` (`PasteResumeDialog`), `AiFollowUpPanel.tsx:232`, `RotationBatchFlow.tsx:272`.
- **S-045** (Yellow): no skip link anywhere; `.sr-only` existed (`index.css:4763`); `<main className="mist-main">` at `App.tsx:1292` had no id/focus target.
- **S-047** (Yellow): `package.json` had only `lint: tsc --noEmit`; no vitest / jest-axe / testing-library.

## Changes Made

**S-040 — global focus ring.** Added a `--focus-ring: #2f8f6e` token (brightened brand green, ≥3:1 on both light paper and the dark sidebar). Appended one global `:focus-visible` rule at the end of `index.css` covering `a, button, input, select, textarea, summary, [role=button], [role=link], [role=tab], [tabindex]` → `outline: 2px solid var(--focus-ring); outline-offset: 2px`. Placed last so it wins source-order ties against the seamless inputs that set `outline: 0` on their base rule. Rewrote the two `.setup-card-*:focus-visible` rules to paint the same visible ring instead of suppressing it. `.mist-main:focus-visible` is explicitly `outline: none` (it is the skip-link landing region, not a control).

**S-041 — shared Dialog primitive.** New `components/Dialog.tsx`: presentation-agnostic primitive owning focus-trap (Tab/Shift+Tab wrap inside the panel), Escape-to-close, and focus-restore-to-opener on unmount. Renders `role="dialog" aria-modal="true" aria-label tabIndex={-1}`. Callers pass `backdropClassName` + `className` so each modal keeps its existing chrome (Tailwind overlays or Mistglass `*-modal` classes). Migrated all four modals onto it; `closeOnBackdropClick={false}` preserves each modal's prior no-backdrop-dismiss behavior — only keyboard handling was added, security semantics untouched. `grep 'role="dialog"' src/components/` now matches **only** `Dialog.tsx`.

**S-045 — skip link.** New `components/SkipToContent.tsx` (`<a class="skip-link" href="#main-content">`), rendered as the first child of `mist-viewport` in `App.tsx`. `<main>` gained `id="main-content" tabIndex={-1}`. `.skip-link` styles (hidden via `translateY(-150%)`, revealed on focus) added to `index.css`.

**S-047 — a11y harness.** Added vitest@3.2.4 + @testing-library/react + user-event + jest-dom + jest-axe (jsdom). Config lives in `vite.config.ts` `test` block (single-vite, deduped) + `src/test/setup.ts`; `npm test` → `vitest run`. Type augmentation `src/test/vitest.d.ts` keeps `toHaveNoViolations` lint-clean. 16 specs across 4 files: Dialog semantics/trap/Escape/restore/axe (S-041), a real migrated modal (`RotationTriggerFlow`) dialog + Escape + axe, skip-link (S-045), and a CSS guard that asserts the global ring exists and no control `:focus-visible` rule sets `outline: none` (S-040).

Files touched: `dashboard-ui/src/components/Dialog.tsx` (new), `SkipToContent.tsx` (new), `RotationTriggerFlow.tsx`, `RotationStatusCard.tsx`, `AiFollowUpPanel.tsx`, `RotationBatchFlow.tsx`, `App.tsx`, `index.css`, `vite.config.ts`, `package.json`, `package-lock.json`, `src/test/setup.ts` (new), `src/test/vitest.d.ts` (new), `src/test/focusRing.test.ts` (new), `src/components/Dialog.test.tsx` (new), `src/components/SkipToContent.test.tsx` (new), `src/components/RotationTriggerFlow.a11y.test.tsx` (new).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `npm test` (vitest + jest-axe) | PASS | 16 tests / 4 files green; `toHaveNoViolations`, dialog trap/Escape/restore, focus-ring CSS guard |
| `npm run lint` (`tsc --noEmit`) | PASS | clean, no errors |
| `npm run build` (`vite build`) | PASS | 1692 modules, built clean (was clean before) |
| `grep -n "focus-visible" src/index.css` | PASS | global rule at the file tail; two `.setup-card-*` rules now paint the ring |
| `grep -rn 'role="dialog"' src/components/` | PASS | matches only `Dialog.tsx` — all four modals route through the primitive |
| `grep -rn "Skip to content\|main-content" src/` | PASS | skip link + `<main id="main-content" tabIndex={-1}>` |

## After Health

S-040, S-041, S-045, S-047 → **Green**. Global keyboard focus ring on every primary control; one shared focus-trapping/Escape/restore Dialog behind all four modals; skip-to-content link with a real `<main>` focus target; and a vitest+jest-axe harness that regresses loudly if any of these break.

## Remaining Risk

- No live browser / Lighthouse pass was run (not required by acceptance; the vitest+axe harness + build/lint are the evidence). The `--focus-ring` contrast on the dark sidebar was reasoned, not measured in-browser.
- Focus ring color is a single token; a future dark-mode/high-contrast pass (out of scope, other batches) may want a paired light/dark ring.
- jsdom cannot evaluate `:focus-visible` heuristics; the trap/Escape/restore specs assert focus *movement*, and the ring itself is guarded via a CSS-source assertion rather than a rendered-style check.

## Next Batch

08-severity-vocabulary. Downstream notes added this batch: batch 09 (S-037) — build the command-palette path, if chosen, on the shared `Dialog`; batch 12 (S-039) — the vitest harness now exists, write a real component spec.
