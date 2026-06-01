# Acceptance: 07-accessibility-foundation

## Acceptance Criteria

- **S-040 (global focus ring):** A single global `:focus-visible` rule, keyed on a Mistglass token, renders a visible focus ring (visible outline or box-shadow with offset) on every primary control — `button`, `a`, `input`, `select`, `textarea`, and clickable cards. Tabbing through every view shows a visible ring on each focused control.
- **S-040 (no opt-out):** The two `:focus-visible` rules that previously set `outline: none` (`index.css:5952` `.setup-card-input`, `index.css:5978` `.setup-card-textarea`) now show the visible ring instead of suppressing it; `grep -n "outline: *none" dashboard-ui/src/index.css` returns no `:focus-visible` rule that leaves a control with no visible focus indicator.
- **S-041 (shared Dialog primitive):** One shared `Dialog` component exists and is used by all four modals (`RotationTriggerFlow`, `RotationStatusCard`, `AiFollowUpPanel`, `RotationBatchFlow`); no modal retains its own ad-hoc focus/Escape handling that bypasses the primitive.
- **S-041 (keyboard behavior):** Opening any of the four modals via the keyboard traps focus inside the dialog (Tab/Shift+Tab cannot reach controls behind it), `Escape` closes it, and focus is restored to the control that opened it. The four modals' security semantics (high/critical suppression confirmation, AI-write gating) are unchanged.
- **S-045 (skip link):** An `.sr-only`-revealed "Skip to content" link is the first focusable element on the page; activating it moves focus to the `<main className="mist-main">` region (id + `tabIndex={-1}` added so focus lands), bypassing the sidebar nav.
- **S-047 (a11y harness):** `dashboard-ui` has vitest + jest-axe + @testing-library wired with a `test` script; the suite asserts `toHaveNoViolations` on key rendered views and includes specs covering dialog trap/Escape (S-041) and the presence of a focus-visible style (S-040), so the accessibility floor regresses loudly if any of these break.

## Required Checks

| Check | Why |
| --- | --- |
| `cd dashboard-ui && npm run lint` (`tsc --noEmit`) | Proves the new `Dialog` primitive, skip-link, and harness changes are type-sound. |
| `cd dashboard-ui && npm run build` (`vite build`) | Proves the production bundle still builds with the global focus ring and migrated modals (build was clean before — must stay clean). |
| `cd dashboard-ui && npm test` (new vitest + jest-axe run) | Proves S-047 exists and that `toHaveNoViolations`, dialog trap/Escape, and focus-visible specs pass on key views — the regression guard for S-040/S-041. |
| `grep -n "focus-visible" dashboard-ui/src/index.css` shows a global rule, and the two `.setup-card-*` rules no longer suppress the ring | Proves S-040: a global indicator exists and no control opts out. |
| `grep -rn 'role="dialog"' dashboard-ui/src/components/` cross-checked against the shared `Dialog` usage | Proves S-041: all four dialogs route through the shared primitive, not four ad-hoc overlays. |
| `grep -rn "Skip to content" dashboard-ui/src/` returns the new link; `<main className="mist-main">` (`App.tsx:1227`) carries an id/`tabIndex` target | Proves S-045: the skip link exists and has a real focus target. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
