# Implementation Receipt: 12-surface-scan-history-trends

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 12-surface-scan-history-trends
- Source report item(s): S-039 (surface scan-history + arbitrary scan-diff in the UI), S-042 (render posture-over-time trend / kill the dead `trendValues` helper)

## Before Health

- **S-039 — Yellow.** The rich per-scan history series and the "compare any two scans" capability were computed locally but unreachable. The live UI rendered only the 7-bar `postureWeek` proxy (`App.tsx` hero `BarChart`) and a "since last scan" delta. No literal `/api/scan-history` or `/api/scan-diff` route existed (re-verified: history flows through `/api/summary` `summary.history` + per-repo deltas). `grep` for a `scan-diff` UI consumer = 0.
- **S-042 — Yellow/Green.** `trendValues(summary)` was defined once (`dashboardData.ts:2108`) with **zero call sites** and a fabricated fallback array; the only "trend" shown was a single `health_delta` number labelled `trend` in the repo-comparison strip.

## Changes Made

**Backend — arbitrary scan-to-scan diff (S-039):**
- `src/security_observatory/storage.py`: new `ObservatoryDB.scan_diff(base_id, head_id)` reusing the existing `_scan_delta` engine — diffs *any* two saved scans (not just a scan and its predecessor). Returns directional `health_delta`, `same_repo`, new/recurring/resolved counts + case lists. Resolved cases keep the closure-proof binding (`resolved_by_scan_id`, `lifecycle_state: resolved`, "Verified — not found in scan X" `next_step`) from `_scan_delta`. Added `_scan_endpoint_meta` helper for base/head metadata.
- `src/security_observatory/dashboard_server.py`: new `GET /api/scan-diff?base=&head=` route in `_handle_get` — validates both ids (400), 404 on unknown scan, else returns the diff. Wrapped by the existing top-level GET error handler. No new egress (local SQLite only).

**Frontend (S-039 + S-042):**
- `dashboard-ui/src/dashboardData.ts`: rewrote `trendValues` to return the honest per-scan health series (0–100, oldest→newest, capped to `points`, `[]` when empty — no fabricated fallback). Added `ScanDiffEndpoint`/`ScanDiffResult` types and `fetchScanDiff(base, head)` (same-origin `/api/scan-diff`).
- `dashboard-ui/src/components/ScanHistoryTrendsPanel.tsx` (new): renders the full posture-over-time sparkline (real call site for `trendValues`) plus a base/head `<select>` picker that drives `/api/scan-diff` and renders the health Δ, new/recurring/resolved counts, and resolved-case closure proofs. Base options are scoped to the head's repo so every diff is a meaningful same-repo, two-points-in-time comparison; cross-repo diffs are guarded with an honest note.
- `dashboard-ui/src/App.tsx`: mounted `<ScanHistoryTrendsPanel summary={summary} />` on the Overview (primary surface); relabelled the one-number repo-comparison `trend` → `vs last` so a single delta no longer masquerades as a trend.
- `dashboard-ui/src/index.css`: Mistglass-consistent styles for the panel, sparkline, picker, and diff result.

**Tests:**
- `dashboard-ui/src/components/ScanHistoryTrendsPanel.test.tsx` (new, 5 specs): renders the full series (not the 7-bar proxy); default mount diff fetch carries `base=s2&head=s3`; selecting an arbitrary base flows `base=s1&head=s3` into the request; honest empty state < 2 scans; resolved-case closure proof surfaced.
- `tests/test_scan_diff.py` (new): pins directional health delta + new/recurring/resolved sets + closure-proof binding; None on unknown scan.
- `tests/test_dashboard_scan_diff_endpoint.py` (new): exercises the HTTP route (200 carries base/head, 400 missing id, 404 unknown scan) against a seeded temp DB on a loopback server.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `cd dashboard-ui && npm run lint` | PASS | `tsc --noEmit` clean. |
| `cd dashboard-ui && npm run build` | PASS | `vite build` clean (1693 modules). |
| `cd dashboard-ui && npm test -- --run` | PASS | 22/22 (incl. 5 new ScanHistoryTrendsPanel specs); no act() warnings. |
| `uv run pytest` | PASS | 509/509 (incl. 5 new scan-diff specs). |
| `python3 -c "...import security_observatory.cli..."` | PASS | `ok`. |
| `grep -rn "trendValues" dashboard-ui/src/` | PASS | Definition + real call site (`ScanHistoryTrendsPanel.tsx:120`) — no longer dead. |
| `grep -rn "scan-diff\|fetchScanDiff" dashboard-ui/src/` | PASS | `fetchScanDiff` consumes `/api/scan-diff` — real consumer (was 0). |

## After Health

- **S-039 → Green.** Full per-scan history series rendered on a primary surface; a base/head picker drives a real `/api/scan-diff` comparison of any two scans, both ids verified to flow into the request (component + route tests). Lens "scan-diff base/head = 0" finding closed.
- **S-042 → Green.** `trendValues` rendered as an honest posture sparkline from `summary.history`; the misleading one-number "trend" label removed. No half-built trend feature remains.

## Remaining Risk

- The posture sparkline plots on a fixed 0–100 scale (honest absolute posture); small scan-to-scan movements are intentionally subtle rather than auto-zoomed. The exact latest health value is shown alongside.
- The base/head picker scopes comparisons to the head's repo by default; cross-repo pairs remain computable via the route but are flagged in the UI as not like-for-like.

## Next Batch

13-code-fix-dashboard-surface (S-043). Its `context.md` line references into `storage.py` / `dashboard_server.py` were refreshed where this batch's insertions shifted them (`save_fix_proposal` :2039, `get_fix_proposal` :2116, rotation GET routes ~2432, do_POST rotation triggers ~2590; the new `/api/scan-diff` GET route sits just below the rotation GET routes). Target S-ID unchanged.
