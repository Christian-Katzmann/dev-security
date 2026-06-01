# Receipt: Stage D — human-launched patch campaign

- Plan: `plans/active/devsec-industry-grade`
- Stage: D (manual patch campaign, post Stages A/B/C)
- Date: 2026-06-01
- Scope source: the two campaign-closing `.final` audits' consolidated punch-lists
  - `reports/codebase-health/devsec-industry-grade/feature-health-final.md`
  - `reports/codebase-health/devsec-industry-grade/11-behavioral-ux-health.final.md`

## Baseline confirmed (clean checkout, before any change)

| Check | Result |
| --- | --- |
| `uv run pytest -q` | 535 passed |
| `cd dashboard-ui && npm run build` | 627.44 kB JS, **re-trips Vite >500 kB chunk-size warning** |

Both matched the audits exactly — the two Green/Yellow residuals reproduced, not taken on trust.

## Punch-list items closed

### 1. [Green/Yellow → Green] Bundle chunk-size warning regression (S-029)

Real fix, not a raised limit: code-split the heavy non-default tab surfaces with
`React.lazy` behind a single `<Suspense>` boundary around `<ActiveView>`.

- Lazy: `CatalogHome`, `CatalogBrowse`, `CatalogToolPage`, `CatalogPackPage`,
  `AgentLabView`, `FixProposalsView` (`App.tsx`). `ScanHistoryTrendsPanel` stays
  eager — it renders on the default Overview surface.
- Suspense fallback styled via `.view-loading` (`index.css`) so a tab switch never
  flashes raw text.
- **Result: main JS chunk 627.44 kB → 438.06 kB (gzip 126.79 kB); the >500 kB
  warning is gone.** FixProposalsView (134.6 kB), AgentLabView (23 kB), and the four
  catalog routes are now separate on-demand chunks.

### 2. [Green/Yellow → Green] `AddRepoDialog` focus-trap/restore gap (S-041)

Migrated the first-run gateway modal onto the shared focus-trapping `Dialog`
primitive — it now inherits Tab-trap + focus-restore-to-opener, matching the bar
every other modal meets.

- Dropped the bespoke window-level Escape effect and the hand-rolled
  backdrop/`<section role="dialog">` chrome; rendered children inside `<Dialog>`
  with `backdropClassName="add-repo-backdrop"` / `className="add-repo-modal"` so the
  Mistglass chrome is preserved.
- Added `initialFocusRef` to `Dialog` so the crafted autofocus on the path input is
  preserved without an `autoFocus` attribute (which would steal focus before Dialog
  records the opener for restore). This is a clean, reusable enhancement; the
  existing `Dialog.test.tsx` (7 specs) stays green.
- New spec `src/AddRepoDialog.a11y.test.tsx` (6 cases): dialog semantics, initial
  focus on the input, Tab-trap never reaching the page behind, Escape-to-close,
  focus-restore-to-opener, zero axe violations. `AddRepoDialog` is now exported for
  testability.

### 3. [doc] Route/tab memory drift

Updated AGENTS.md Ghost Invasion Memory to match the shipped surface (verified
against `dashboard_server.py` and `App.tsx`, not invented):

- `stable_routes` now includes `/api/scan-diff`, `/api/fix-proposals`,
  `/api/fix-proposals/<id>`, `/api/fix-proposals/<id>/land`.
- Added `dashboard_tabs` (11 tabs incl. `fix-proposals`, `agent-lab`).
- Added `case_lifecycle_states: open, verified, in_progress, accepted_risk,
  resolved` (canonical `LIFECYCLE_STATES`, closure bound to `resolved_by_scan_id`).

## Item carried to the human gate (not code-fixable here)

### 4. [verify] Rendered-behavior confirmation pass

Operating rules forbid running dashboards/servers/scanners in an unattended session,
so the live keyboard walk (Overview→Cases→decision keyboard-only), ⌘K, each
`RunErrorNotice`, a real `/api/scan-diff`, a rescan-to-closure, and `RunCheckSheet`
Escape/focus remain for the human Final-review gate. The component/axe/route test
evidence is strong; this closes the last Medium-confidence rendered-behavior gaps.

## Final verification (Stage D changes applied)

| Check | Result |
| --- | --- |
| `cd dashboard-ui && npm run lint` (`tsc --noEmit`) | clean |
| `cd dashboard-ui && npx vitest run` | **28 passed** (22 prior + 6 new AddRepoDialog) |
| `cd dashboard-ui && npm run build` | clean, **438.06 kB, no chunk-size warning** |
| `uv run pytest -q` | **535 passed** |

## Notes

- Files changed: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/components/Dialog.tsx`,
  `dashboard-ui/src/index.css`, `dashboard-ui/src/AddRepoDialog.a11y.test.tsx` (new),
  `AGENTS.md`, and the committed `src/security_observatory/dashboard/index.html`
  (regenerated to point at the split bundle; `dashboard/assets/` is gitignored).
- Both feature-lens and UX-lens Green/Yellow residuals are now Green. The only open
  item is the human browser pass (#4), which is the gate's own step.
