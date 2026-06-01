# Implementation Receipt: 10-dashboard-frontend-perf

## Target

- Plan: `plans/active/devsec-industry-grade/`
- Batch: 10-dashboard-frontend-perf (Stage B step 1.5)
- Source report item(s): S-028 (memoize derived state), S-029 (trim assets + code-splitting decision), S-054 (token-inlining sweep)

## Before Health

- **S-028** — Yellow. `scopedSummary`/`activeCases`/`posture` were computed inline in the `App.tsx` root on every render (current lines `App.tsx:1074-1081`), and `buildActivity`/`activeCaseList`/`displayCases` ran fresh inside `OverviewView`/`ActivityView`/`CasesView` on each render. `search` is local root state, so every keystroke re-ran all derived passes across the 4,500-line shell.
- **S-029** — Green/Yellow. `favicon.png` 2,104,121 B, `apple-touch-icon.png` 2,104,121 B (both 1254×1254), `logo.png` 606,592 B (4000×796). `vite.config.ts` was a plain single-bundle build; no `manualChunks`/`React.lazy`. Code-splitting decision was implicit.
- **S-054** — Green/Yellow. `dashboard-ui/src/index.css` carried 43 `#fff`/`#ffffff` + 5 `#2f6656` inline values outside `:root` (top offenders) despite a mature token palette. (`components/OverviewView.tsx` half of S-054 was already resolved — batch 09 deleted that orphan.)

## Changes Made

**S-028 — memoized derived state (`dashboard-ui/src/App.tsx`):**
- Root: wrapped `targetRepos`, `scopedSummary` (`filterSummaryByTarget`), `activeCases` (`activeCaseList`), and `posture` (`postureScore`/`postureDelta`/`postureWeek`) in `useMemo` keyed on their real inputs (`[summary, target]` / repo inputs). Component tree unchanged — no decomposition (that is Stage C / S-016).
- `OverviewView`: `cases` (`activeCaseList`) memoized on `[summary]`; `activities` (`buildActivity`) on `[summary, target.mode]`.
- `ActivityView`: base `buildActivity` memoized on `[summary, target.mode]`; the cheap search + chip `.filter()` (which legitimately reads `search`) runs each render.
- `CasesView` (the headline triage path where search lives): `cases`/`suppressed`/`reasons`/`counts`/`categories`/`repoNames` memoized on `[summary]`/`[cases]`; the search `filtered` pass stays per-render.

**S-029 — assets + code-splitting (`dashboard-ui/public/*.png`, rebuilt into `src/security_observatory/dashboard/`):**
- Re-exported the three source PNGs via `sips`, visually identical (raster downscale only): favicon 256×256, apple-touch-icon 180×180 (Apple standard), logo 1200×239 (wordmark; not referenced in live `src` but kept as a served brand asset).
- **Code-splitting decision: single bundle deliberately accepted.** The dashboard is local-first, served over loopback (127.0.0.1) by a Python `SimpleHTTPRequestHandler`; there is no CDN/network latency. The production JS chunk is 485.57 kB / 137.53 kB gzip — under Vite's 500 kB warning threshold (build emits no chunk-size warning). Adding `React.lazy`/Suspense boundaries for Agent Lab/Catalog/Rotation would introduce extra fallback UI states to craft and test for zero perceptible gain on localhost. Decision recorded here per acceptance.
- **Cache-header spot-check:** static assets (Vite content-hashed JS/CSS + the PNGs) are served by `SimpleHTTPRequestHandler`, which sends `Last-Modified` and honors conditional `If-Modified-Since` (304) but no explicit `Cache-Control`. Adequate for loopback delivery — content-hashed filenames give automatic cache-busting on rebuild. No server change made (out of this batch's frontend scope; touching `dashboard_server.py` risks unrelated honey-key/server logic).

**S-054 — token sweep (`dashboard-ui/src/index.css`):**
- Added one genuinely-needed token `--brand-green: #2f6656;` to `:root` and replaced all 5 outside-`:root` `#2f6656` usages with `var(--brand-green)`.
- Replaced `background: #fff;` → `var(--surface-card)` and `color: #fff;` → `var(--on-surface-strong)` (both tokens are exactly `#ffffff`, so value-identical) across all shared-primitive occurrences; the one gradient `#ffffff` → `var(--surface-card)`.
- **One-idiom decision:** named Mistglass `:root` tokens are the idiom for shared primitives in `index.css`. Genuine one-off raster tints (`#f8faf8`, gradient stops `#4f8a72`) left inline.

**Test (`dashboard-ui/src/App.perf.test.tsx`, new):** deterministic stand-in for the manual React Profiler pass — renders `<App/>` with a 60-case seeded summary, types into the search box, and asserts `filterSummaryByTarget` is invoked **zero** additional times across the keystrokes (pre-memoization it fired once per keystroke render). Regression guard for S-028.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `cd dashboard-ui && npm run lint` (`tsc --noEmit`) | ✅ pass | clean |
| `cd dashboard-ui && npm run build` (`vite build`) | ✅ pass | built in 1.35s; single JS chunk 485.57 kB / 137.53 kB gzip; CSS 159.30 kB / 26.40 kB gzip; no chunk-size warning |
| `ls -la src/security_observatory/dashboard/*.png` | ✅ pass | favicon 2,104,121→77,709 B; apple-touch-icon 2,104,121→37,259 B; logo 606,592→91,697 B (all KB-scale) |
| React Profiler (deterministic equivalent: `App.perf.test.tsx`) | ✅ pass | 12 keystrokes → 0 re-runs of `filterSummaryByTarget` |
| `grep -nE "#fff\|#2f6656" dashboard-ui/src/index.css` before vs after | ✅ pass | before: 48 (43 `#fff`/`#ffffff` + 5 `#2f6656`), 2 inside `:root`. after: 3, all `:root` token definitions (`--brand-green`, `--on-surface-strong`, `--surface-card`); 0 outside `:root` |
| `cd dashboard-ui && npx vitest run` (full suite) | ✅ pass | 17/17 tests across 5 files (a11y harness + new perf guard) |

## After Health

- **S-028 → Green.** Derived passes memoized at the root and in the three search-touched views; typing no longer re-runs `filterSummaryByTarget`/`activeCaseList`/`buildActivity`/`displayCases`. Proven by `App.perf.test.tsx`. Component tree intact.
- **S-029 → Green.** Assets KB-scale and visually identical; code-splitting decision now explicit (single bundle accepted for local-only delivery, rationale above); cache headers spot-checked.
- **S-054 → Green.** Inline hex on shared primitives swept to tokens (48 → 3 `:root` definitions); one styling idiom (Mistglass tokens) documented for the touched primitives. Value-identical, no visual regression.

## Remaining Risk

- Single-bundle acceptance is a deliberate local-first call; if DëvSec ever ships a remotely-hosted dashboard, revisit `React.lazy` boundaries.
- `logo.png` is a served brand asset with no live `src` consumer (only `index.html` references favicon/apple-touch-icon). Downscaled rather than deleted to preserve `/logo.png` for external/desktop/brand use.
- A broader Tailwind `black/white`-opacity family still lives in non-case components (`RotationStatusCard.tsx`, `DependenciesView.tsx`) — explicitly out of S-054's "shared primitives" scope per acceptance; not chased here.

## Next Batch

11-case-lifecycle (Stage B step 1.6). Downstream adjustment applied: corrected `App.tsx` line refs that drifted (batch 11 `CaseDetailCard` def ~3768 / renders 2860,2878; batch 12 `postureWeek` proxy 538-544 and `health_delta` "trend" number 2704). Batch 13 references nothing this batch touched.
