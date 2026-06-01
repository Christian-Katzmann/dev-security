# Receipt: Stage B — post-repair behavioral-ux final pass

- Step: 1.9 (devsec-stage-b-experience-power) — READ-ONLY re-audit
- Date: 2026-06-01
- Report: `reports/codebase-health/devsec-industry-grade/11-behavioral-ux-health.final.md`

## Verdict

Worst row **Green/Yellow**, overall **Green**. No Red, no Yellow/Red. The behavioral-UX
advance gate clears. All 15 confirmed S-IDs landed and verify against current source + a
fresh `lint` / `vitest` (22/22) / `build` run this session.

## S-ID confirmation (all Green unless noted)

| S-ID | Outcome | Evidence |
| --- | --- | --- |
| S-033 add-repo prompt | Green | `AddRepoDialog` `App.tsx:1511`; no `window.prompt` |
| S-034 note/incident prompts | Green | inline `.decision-note` `:3921`, `.incident-close-note` `:4238` |
| S-036 dead case twin | Green | `components/{OverviewView,CasesView,CaseCard,HoneyKeysView}.tsx` deleted |
| S-037 ⌘K | Green | real handler `App.tsx:1033-1051` |
| S-038 scan-error states | Green | discriminated `RunError` `:293` + `RunErrorNotice` |
| S-044 Activity chips | Green | `activityFilter` `:3275`, `category` field wired |
| S-019 severity vocab | Green | one `severityDisplay` map `:418` |
| S-032 confidence honesty | Green | `model.py:166` preserves `unknown` |
| S-040 focus ring | Green | `--focus-ring` `index.css:96` + global `:focus-visible` |
| S-041 Dialog primitive | Green* | shared `Dialog.tsx` behind 4 modals; *AddRepoDialog not migrated (residual) |
| S-045 skip link | Green | `SkipToContent` → `<main id="main-content">` `:1412` |
| S-047 a11y harness | Green | vitest+jest-axe, 22 tests green |
| S-028 memoization | Green | 15 `useMemo`; `App.perf.test.tsx` green |
| S-029 assets/code-split | Green/Yellow | **bundle 627.76 kB re-trips Vite >500 kB warning** (regression) |
| S-054 token sweep | Green | `index.css` swept to `:root` tokens |

Bonus surfaces shipped & mounted: lifecycle (`in_progress` + closure proof), ScanHistoryTrendsPanel (`/api/scan-diff`), FixProposalsView.

## Punch-list for Stage D (residuals/regressions)

1. **S-029 bundle warning regression (Green/Yellow).** JS chunk grew 485→627.76 kB after batches 11–13; `npm run build` now prints Vite's >500 kB chunk-size warning that batch 10 recorded as absent. Local-first/loopback → not user-facing latency, but the "no warning" claim is stale and it masks future chunk issues. Fix: `React.lazy` the heavy non-default views, or set `chunkSizeWarningLimit` with a recorded reason.
2. **AddRepoDialog bypasses the shared Dialog primitive (Green/Yellow, S-041 gap).** First-run gateway modal has Escape + aria-modal + backdrop-close + autofocus but **no focus-trap / focus-restore**; App.tsx never imports `Dialog`. Migrate it onto `<Dialog>`; add an axe/trap spec.
3. **Human browser confirmation pass** (this step's rules forbade running the dashboard): keyboard-only Tab walk, ⌘K, a missing-scanner failure to render each `RunErrorNotice`, a real `/api/scan-diff` + rescan-to-closure, and `RunCheckSheet` Escape/focus.
4. Minor (design-system lens): `crit` pill `bg:#dcaaa5` (`App.tsx:431`) hotter than DESIGN token `--sev-crit-soft #e8c6c0`; broad Tailwind black/white-opacity debt in non-case components; AGENTS.md route memory missing the new tabs.

## Notes for next step (Final review)

- No repo code changed (read-only audit). Only writes: the final report + this receipt.
- `npm run build` is reproducible — committed `dashboard/index.html` unchanged.
- The two pre-existing working-tree changes (`campaigns/devsec-stage-{a,b}*.md`) pre-date this session and were not touched.
