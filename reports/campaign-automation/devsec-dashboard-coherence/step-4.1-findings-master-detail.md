# Step 4.1 receipt — Findings master-detail composition

## Decision

- Chose pattern (a) for desktop: a sticky right-side selected-case panel.
- Chose pattern (c) below 1280px: the selected case expands inline under the clicked row.
- Kept `CaseDetailCard` unchanged; only changed how `FindingsView` and `FindingsTable` place it.
- Kept single-select behavior for v1. There is no multi-select interaction in this surface today.

## Implementation

- `dashboard-ui/src/App.tsx`
  - Replaced the old table-then-detail vertical stack with `.findings-master-detail`.
  - Added the desktop `<aside className="findings-detail-pane">` for the selected case.
  - Passed a narrow-layout inline detail render into `FindingsTable`.
  - Added `aria-expanded` to selectable case rows.
- `dashboard-ui/src/index.css`
  - Added the responsive master-detail grid.
  - Set the sticky desktop threshold to `min-width: 1280px`.
  - Added inline-detail display rules for `max-width: 1279px`.
  - Strengthened selected-row feedback by coloring the chevron with the selected accent.

## Verification

- `cd dashboard-ui && npm run lint` passed.
- `cd dashboard-ui && npm run build` passed and regenerated served dashboard assets.
- Started the local dashboard on `http://127.0.0.1:8767` with `--no-open`, then checked the Cases view through Playwright.
- Desktop check at `1440x900`:
  - Detail pane displayed as `block`.
  - Inline detail stayed hidden.
  - Selected row reported `aria-expanded="true"`.
  - Master and detail pane did not overlap.
- Narrow check at `1100x900`:
  - Detail pane displayed as `none`.
  - Inline detail displayed as `block` directly under the selected row.
- Walked these cases:
  - `F-1F33` — warning, AI agent risks.
  - `F-A47D` — critical, workflow surfaces.
  - `F-8DB5` — critical, dependency risks.
  - `F-6E2D` — warning, repository / AI agent risks.
  - `F-DBD4` — elevated, dependency risks.

