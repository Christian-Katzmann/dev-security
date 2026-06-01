# Implementation Receipt: 09-finish-dead-ui-surfaces

## Target

- Plan: `plans/active/devsec-industry-grade/`
- Batch: 09-finish-dead-ui-surfaces
- Source report item(s): S-036, S-037, S-038, S-044 (Yellow → Green)

## Before Health

Four dead/half-built dashboard surfaces, each presenting a half-state as whole:

- **S-036** — A complete orphaned parallel case UI (`components/{OverviewView,CasesView,CaseCard}.tsx`) imported by nothing, shadowing the live inline `OverviewView`/`CasesView`/`CaseDetailCard`; its `CaseCard` was off-Mistglass (`text-black/45`, `border-black`, `shadow-[inset_0_3px_0_#111111]`, banned by DESIGN.md §2). A fourth orphan, `components/HoneyKeysView.tsx`, sat in the same dead family.
- **S-037** — A `<kbd>⌘K</kbd>` hint in the toolbar with no handler anywhere (only `installHardRefreshShortcut` for ⌘R existed). A false affordance.
- **S-038** — Every scan-failure path set one undifferentiated `runError` string; scanner-missing vs scanner-errored vs scan-failed were indistinguishable, rendered as a generic red `inline-error`.
- **S-044** — Activity event-feed filter chips (`<Chip active>All</Chip>…`) rendered as clickable chips with **no `onClick` and no state** — dead controls, contrasting the fully-wired CasesView chips.

## Changes Made

**S-036 — deleted the orphaned parallel case UI (one source of truth).**
- Deleted `dashboard-ui/src/components/OverviewView.tsx`, `components/CasesView.tsx`, `components/CaseCard.tsx`, and the sanctioned fourth orphan `components/HoneyKeysView.tsx`.
- Confirmed (pre- and post-deletion) the only imports of these were `CaseCard` imported by the two deleted views — nothing else in `dashboard-ui/` referenced them. The live act path (inline `OverviewView`/`CasesView`/`CaseDetailCard`/`HoneyKeysView` in `App.tsx`) is unchanged and remains mounted.

**S-037 — made ⌘K real (focus search).**
- Added a `searchInputRef` in `App` and a capture-phase `keydown` effect that focuses + selects the toolbar search input on ⌘K / Ctrl-K (mirrors `installHardRefreshShortcut`'s pattern; never collides with ⌘R, which is untouched in `main.tsx`).
- Threaded the ref into `Toolbar` and attached it to the existing `input[name="dashboard-search"]`. The `<kbd>⌘K</kbd>` hint is now backed by a real handler.

**S-038 — differentiated scan-failure feedback into crafted Mistglass error states.**
- Introduced a discriminated `RunError = {kind: 'missing-tool' | 'errored' | 'failed' | 'validation'; message; detail?}` type; changed `runError` state from `string | null` to `RunError | null`.
- Mapped each write-site: all-repo setup failures → `missing-tool` (routes to Verification); fetch/poll catches → `errored` (offers retry, via new `erroredRunError` helper + `retryLastRun`); job-failed → `failed` (shows details); precondition messages → `validation`.
- Added a `RunErrorNotice` component rendering a crafted card with an eyebrow, headline, optional detail, and the right next-step action per kind (warn/amber register for setup+validation, crit/red register for errored+failed). Added matching `.run-error-notice` CSS in `index.css`.
- Replaced **all** `runError` render sites with `RunErrorNotice` (RunCheckSheet, CompactScanStatus, ScanControlPanel) and threaded `onRetry` from `App` → `ActiveView` → `OverviewView` → `CompactScanStatus`, so no failure is set-but-never-shown.

**S-044 — wired the Activity filter chips.**
- Added a `category` field (`'scan' | 'case' | 'honey' | 'project'`) to `ActivityItem`, populated in all four `buildActivity` pushes.
- Added `activityFilter` state to `ActivityView` and mapped the chips (`All` / `Scanner runs` / `Cases` / `Honey keys`) with `active`/`onClick`, filtering the feed (mirrors the wired CasesView chip pattern).

Files touched: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`; deleted `dashboard-ui/src/components/{OverviewView,CasesView,CaseCard,HoneyKeysView}.tsx`.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `cd dashboard-ui && npm run build` | ✅ clean | `vite build` — 1692 modules, built in ~1.3s |
| `cd dashboard-ui && npm run lint` (`tsc --noEmit`) | ✅ clean | no dangling imports/types after deletion + new error/chip types |
| `grep -rn "components/OverviewView\|components/CasesView\|components/CaseCard" dashboard-ui/src/` | ✅ none | no import of the deleted module paths remains |
| `grep -rn "text-black/45\|border-black\|shadow-[inset_0_3px_0_#111111]" dashboard-ui/src/` | ⚠ non-empty (no case surface) | **case-specific** banned styling is gone with the deleted trio; remaining matches are a pre-existing Tailwind-token family in **non-case** components (`RotationStatusCard`, `RotationTriggerFlow`, `RotationBatchFlow`, `DependenciesView`, `IacView`, `CodeView`, `McpView`, `ScanCompletenessPanel`, `SinceLastScanPanel`, `ReportDownloads`, `EmptyRepoState`) — out of S-036 scope (target = the case trio). Confirmed `grep -l border-black | grep -iE 'case\|finding'` → none. |
| `grep -rn "⌘K" dashboard-ui/src/` | ✅ present + handler | hint at `App.tsx` `<kbd>⌘K</kbd>` now backed by the `searchInputRef.current` keydown handler |
| In-browser UX pass (loopback `127.0.0.1:8876`, `--no-open`, chrome-devtools) | ✅ | **⌘K**: pressing Meta+k focused `input[name="dashboard-search"]` (verified via `document.activeElement`). **Chips**: All→36 rows, Scanner runs→16, Cases→20, Honey keys→0 (16+20=36, partitions correctly), active state toggles. **Error states**: injected each `RunError` kind into the live page — screenshot confirms 4 distinct crafted cards (Setup needed/amber+Open Verification, Run interrupted/red+Try again, Check failed/red+details, Before you run/amber), not a generic red line. |

## After Health

- **S-036 → Green:** one source of truth for the case control; the orphaned off-Mistglass parallel UI (+ HoneyKeysView orphan) deleted; no banned styling on any case surface; build/lint clean.
- **S-037 → Green:** ⌘K is a real affordance (focuses search, verified in-browser); ⌘R untouched.
- **S-038 → Green:** scan failures carry structure (missing-tool / errored / failed / validation), each a crafted Mistglass card with the right next step, rendered on every write surface.
- **S-044 → Green:** Activity chips filter the feed (verified in-browser); no clickable-looking dead control remains.

## Remaining Risk

- **Out-of-scope styling debt (documented, not a regression):** the repo-wide `border-black`/`text-black/45` grep is still non-empty because a broad pre-existing Tailwind-opacity token family lives in non-case components — several of them **live** (the `Rotation*` flow cards, `ScanCompletenessPanel`, `SinceLastScanPanel`, `ReportDownloads`). This is a larger off-Mistglass migration that S-036 explicitly does **not** cover (target = the case trio) and that batch 10's Non-Goals also exclude from S-054's "shared primitives" scope. No case surface is affected.
- **`SinceLastScanPanel.tsx` is now itself orphaned** (its only mounts were in the deleted `OverviewView`/`CasesView`). Left in place (out of scope); flagged to batch 12 (see downstream note below).
- **Live missing-scanner scan was intentionally not run.** Triggering a real scan touches the scanner subsystem (`risks.json` → `human_recommended` approval) and mutates the shared local SQLite in an unattended session. The S-038 error *rendering and differentiation* were verified deterministically by injecting each kind into the live page (screenshot); the retry/verification *actions* are statically wired and type-checked. The other two runtime claims (⌘K, chips) were verified live against the running UI.

### Downstream plan adjustments (ADAPTIVE step — target S-IDs unchanged)

- **Batch 10 (S-054):** evidence cited the now-deleted `components/OverviewView.tsx:45,49,65` (raw Tailwind opacities). Narrowed S-054 to the live `index.css` token sweep; fixed the acceptance Required-Check grep to drop the deleted file path; added a Note.
- **Batch 11 (S-035):** redirected the closure-by-absence UI work from the deleted `CaseCard.tsx:228-234` to the live inline `CaseDetailCard` in `App.tsx` (~`:3742`, rendered `:2837,:2855`); updated context Note + acceptance criterion.
- **Batch 12 (S-039):** noted the `SinceLastScanPanel` use sites (`OverviewView.tsx:87`/`CasesView.tsx:173`) were deleted, so that panel is now unmounted reference scaffolding; the S-039 gap (history/diff unreachable from the live UI) is unchanged.
- **Batch 13:** no references to the deleted orphans — no change.

## Next Batch

10-dashboard-frontend-perf (S-028 memoization, S-029 assets/code-split, S-054 token sweep) — note the S-054 narrowing above.
