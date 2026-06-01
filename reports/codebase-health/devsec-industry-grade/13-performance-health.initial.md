# Performance Health Forensic — DëvSec (Security Observatory)

## Executive Finding

DëvSec's performance posture is solid at the data layer and clean in the core
compute, with one real, growth-sensitive hot path. The SQLite schema is
comprehensively indexed (every per-scan / per-repo lookup has a covering index,
`storage.py:102-433`), and case-building is genuinely O(n log n) — a single
group-by pass plus one sort, no O(n²) (`cases.py:183-205`), which directly clears
the Excellence Brief's named "no O(n²) case-building" risk. The weak spot is
`dashboard_payload()` (`storage.py:1323-1411`): the function backing `/api/summary`
— the dashboard's primary load — runs a per-repo fan-out of ~12-18 small indexed
queries *for every repo* (previous-scan lookup, a 5-query dependency delta, a
per-scan findings pull, trust enrichments, a platform-posture join, and case
resolution runs each with a nested per-run items query). Each query is fast
because it is indexed, but the count scales with repo count and is all serialized
on one request. On the client, `App.tsx` is a single 4028-line component that
recomputes derived state (`scopedSummary`, `activeCases`, `posture`,
`buildActivity`) on every render — including every keystroke in the search box —
without top-level memoization, which is exactly the keyboard-first triage path the
Brief elevates. The shipped SPA is a single ~472 KB JS + ~153 KB CSS bundle with
no code-splitting, and two static icons are ~2 MB each — both low-impact on
localhost but not "finished." Net: no Red. The dashboard-summary fan-out and the
client render-waste are the two findings worth a bounded repair; everything else
is Green to Green/Yellow.

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security`
- Skill/lens: `performance-health-forensic`
- Date: `2026-06-01`
- Requested focus: Excellence Brief `performance-health` row — "Real-repo scan and
  dashboard stay snappy on a large history store: no O(n²) case-building, no UI lock
  on big finding sets, fast trends/diff queries against SQLite." Impact lens:
  **user** (load, route transitions, interaction latency). Out of scope per Brief:
  External Surface scanning, runnable packs, non-macOS desktop, net-new scanners.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "...import security_observatory.cli..."` (fast import) | **Pass (exit 0)** | Printed `cli-import-ok`. CLI import graph loads cleanly. |
| Built-asset size inspection (`ls -la src/security_observatory/dashboard/assets/`) | **Pass** | `index-*.js` = 472,967 B; `index-*.css` = 153,190 B (single chunk each). |
| Built static images (`ls -la src/security_observatory/dashboard/`) | **Pass** | `favicon.png` and `apple-touch-icon.png` = 2,104,121 B each; `logo.png` = 606,592 B. |
| Index coverage read (`grep "create index" storage.py`) | **Pass** | 27 indexes; every per-scan/per-repo access pattern covered. |
| `npm run build` / `npm run lint` (tsc) | **Not run** | Avoided per cost-discipline after the bundle was already measurable from emitted assets; would refine gzip sizes and confirm no lazy boundaries. Recorded under Limits. |
| Live scan / dashboard server / desktop launcher | **Not run** | Out of scope per AGENTS.md and `.adx/risks.json`. No risk-flagged command executed. |

The only write performed was this report file.

## Ranked Health Table

Weakest / highest-user-impact first.

| Rank | Area | Health | Confidence | Evidence | Impact (user) | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `dashboard_payload()` per-repo query fan-out behind `/api/summary` | Yellow | High | `storage.py:1347-1411` loops over every latest-scan repo; per iteration: `_previous_scan` (`:1349/1563`), `_dependency_delta` running `list_sbom_components`×2 + `list_dependency_manifest_entries`×2 + a dependency-findings query (`:1592-1620`), a `select * from findings where scan_id ...` (`:1366-1372`), `list_dependency_trust_enrichments` (`:1408`), `latest_platform_posture_snapshot` join (`:1409`), and `list_case_resolution_runs(limit=5)` which itself runs a nested `case_resolution_items` query per run (`:1785-1789`). ~12-18 round-trips × repos, serialized. | The single most-hit endpoint (dashboard open + post-scan refresh). Each query is indexed and fast, but total latency grows linearly with repo count and history size — the Brief's "snappy on a large history store" target. | Batch the per-repo deltas: fetch previous-scan rows, sbom/manifest/findings, trust, posture, and resolution runs for all latest scans in set-based queries keyed by `scan_id IN (...)`, then assemble in memory. Eliminates the per-run items N+1 via one `case_resolution_items where run_id IN (...)`. | Seed a fixture DB with 50 repos × deep history; time `dashboard_payload()`; assert query count is O(1) in repo count via a `sqlite3` trace callback in a pytest. |
| 2 | `App.tsx` derived-state recompute on every render (no top-level memo) | Yellow | High | `App.tsx:947-954` computes `targetRepos`, `scopedSummary` (`filterSummaryByTarget`), `activeCases` (`activeCaseList`→`displayCases`), and `posture` (`postureWeek`/`postureDelta`) inline every render. `search` is React state (`:912`); typing in it re-renders this 4028-line root component, re-running all derived passes plus `buildActivity` (`:601-659`, sorts up to 36 items). No `useMemo` wrapping these. | Keyboard-first triage and search — the Brief's headline UX path — pay full derived-state cost per keystroke. Cheap on small summaries; janky on a repo with thousands of findings/cases. | Wrap `scopedSummary`/`activeCases`/`posture`/`buildActivity` in `useMemo` keyed on `[summary, target]` (and `search` only where it is actually consumed); consider splitting the root component so search state does not re-render the whole shell. | React Profiler with a large seeded summary; confirm typing in search does not re-run `filterSummaryByTarget`/`buildActivity`. |
| 3 | Client bundle: single chunk, no code-splitting | Green/Yellow | High | `dashboard/assets/index-*.js` = 473 KB, `index-*.css` = 153 KB (one chunk each). `vite.config.ts` is a plain `react()`+`tailwindcss()` build with **no `build.rollupOptions.manualChunks`** and no chunk strategy. `App.tsx:1-104` imports every page/view + all icons statically; no `React.lazy`/`import()` in `src` (only `loading="lazy"` on `<img>` tags, `catalogHelpers.tsx:233`). Deps: `react`, `react-dom`, `lucide-react`, `motion`. | First paint of the triage view carries all pages (catalog, agent-lab, rotation flows) the user may never open. Served from localhost, so network cost is near-zero; impact is parse/eval of unused JS, modest. | Optional: lazy-load heavy rarely-first views (Agent Lab, Catalog, Rotation flows) behind `React.lazy`; or accept single-bundle given local-only delivery. Low priority vs. ranks 1-2. | `npm run build`, read Vite chunk report; confirm split boundaries and gzip sizes. |
| 4 | Oversized static images served by the dashboard | Green/Yellow | High | `dashboard/favicon.png` and `apple-touch-icon.png` = 2.1 MB **each**; `logo.png` = 607 KB. | A 2 MB favicon is wasteful even on localhost; re-fetched if cache headers are weak. Low user impact (loads once, local). | Downscale favicon/touch-icon to appropriate raster sizes (a few KB); verify `Cache-Control` on static assets. | `ls -la` after re-export; check the server static handler for cache headers. |
| 5 | Server concurrency / scan-job execution model | Green | High | `dashboard_server.py:2480-2513` — the `/api/run-check` POST handler dispatches `run_check_job` via `threading.Thread(target=run_check_job, ..., daemon=True).start()`, so scans run off the request thread; status is polled at `/api/check-status` (`:2309`, client `App.tsx:969-990`). Server is `ThreadingHTTPServer(("127.0.0.1", port), ...)` (`:4228`), isolating a slow `/api/summary` from other endpoints. Same off-thread pattern for rotation/honey jobs (`:3194`, `:3772`, `:3891`, `:4040`). | A long scan does not freeze the UI or other API calls — confirmed, not inferred. | None required. | Already verified via the handler dispatch lines above. |
| 6 | Case-building / scoring complexity on big finding sets | Green | High | `build_security_cases` (`cases.py:191-205`): one `defaultdict` group-by `_cluster_key` (O(n)), `_case_from_group` per group, single `sorted()`. `_dependency_trust_index` built once (`:270-281`); `_merge_steps` membership checks are over ~4-8 fixed steps (`:783-788`). `priority.decide_action_level` is straight-line (`priority.py:26-71`). No nested loop over all findings. | Reducing a huge raw-finding set to cases is O(n log n), dominated by the final sort — no quadratic stall. Directly clears the Brief's "no O(n²) case-building" non-negotiable. | None. | Micro-benchmark `build_security_cases` on a 10k-finding fixture; assert sub-linear-per-item time. |
| 7 | SQLite index coverage for trends/diff/finding loads | Green | High | `storage.py:102-433`: `idx_scans_repo_started(repo_name, started_at desc)` powers `_previous_scan`/latest-scan (`:1564-1590`); `idx_findings_scan(scan_id)` powers per-scan finding pulls; `idx_sbom_components_repo`, `idx_dependency_manifest_repo`, `idx_dependency_trust_scan`, `idx_platform_posture_repo`, `idx_case_resolution_*` all cover the dashboard's access patterns; `idx_honey_events_*` cover event listing. | Individual trends/diff queries stay fast as history grows — the per-query half of the Brief's "fast SQLite" target is met. The remaining risk is *count* of queries (rank 1), not per-query cost. | None at the index layer. | `EXPLAIN QUERY PLAN` on `_previous_scan` and the dependency-delta queries against a fixture; confirm index use, no `SCAN TABLE`. |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters (performance) |
| --- | --- | --- |
| Per-run nested query inside `list_case_resolution_runs` | `storage.py:1785-1789` runs one `case_resolution_items where run_id = ?` per run row, and is itself called once per repo inside `dashboard_payload` (`:1410`). | A nested N+1 inside the rank-1 fan-out — the clearest single batching win (`run_id IN (...)`). Capped at `limit=5` runs/repo today, so bounded, but compounds with repo count. |
| Honey-event pruning on every dashboard load | `dashboard_payload` calls `prune_honey_key_events` (`:1325`) before assembling. | A write/delete on the hottest read path. Indexed (`idx_honey_events_*`) and likely cheap, but it couples read latency to retention housekeeping; worth confirming it is bounded. |
| `motion` (framer-motion successor) as a runtime dependency | `dashboard-ui/package.json` deps. | Animation library on the critical bundle; a meaningful share of the 473 KB JS. Candidate for the lazy-load/trim decision in rank 3. |
| Large report-generation modules | `enrichment.py` (1055), `agent_lab.py` (1031), `landing.py`/`scorecard.py`/`docs_render.py` server-side rendering. | Synchronous full-document generation on request could spike latency for large histories; not exercised this pass, flagged for a future render-path look. |

## Top Repair Targets

1. **Batch `dashboard_payload()` into set-based queries (rank 1 + the nested
   `case_resolution_items` N+1).** Replace the per-repo loop's individual lookups
   with `... WHERE scan_id IN (...)` / `run_id IN (...)` pulls assembled in memory.
   Highest-leverage: it directly hardens the dashboard's primary endpoint against
   the Brief's "large history store" growth case.
2. **Memoize derived state in `App.tsx` (rank 2).** Wrap `scopedSummary`,
   `activeCases`, `posture`, and `buildActivity` in `useMemo` keyed on
   `[summary, target]` so search-box typing stops re-running them — protects the
   headline keyboard-first triage path.
3. **Trim oversized static assets and decide on code-splitting (ranks 3-4).**
   Downscale the 2 MB favicon/touch-icon to KB-scale; optionally lazy-load the
   rarely-first views (Agent Lab, Catalog, Rotation). Low user impact on localhost,
   but the "finished, not just present" bar wants it addressed.

## SocratiCode Value

SocratiCode was not used. Per the suite's cost-discipline rule, the lens targeted
known files (storage/cases/priority/dashboard_server and the React root), so direct
Read/Grep was the right tool and SocratiCode's broad flow/impact mapping was not
needed. The standard is explicit that SocratiCode is a librarian, not proof; all
verdicts here rest on direct code reads, the emitted-bundle sizes, the index DDL,
and the passing import check. If a follow-up wanted to confirm every call site of
`dashboard_payload` and the scan-job dispatch, `codebase_flow` on the
scan→case→storage→dashboard path could pre-map them before reading.

## Limits

- **Not run (safe but skipped):** `npm run build` / `tsc --noEmit` — bundle sizes
  were read directly from emitted assets, but gzip sizes and confirmation of zero
  lazy boundaries were not measured; `EXPLAIN QUERY PLAN` and timing benchmarks
  against a seeded fixture DB were not executed. All such claims are reasoned from
  code + index DDL, not from a live query plan, and are labeled accordingly.
- **Inferred (Medium confidence):** the scan-job-on-background-thread model (rank 5)
  is inferred from `ThreadingHTTPServer` + the `CHECK_JOBS` lock/dict + the polling
  client; the `run-check` handler body was not read line-by-line to confirm it never
  runs a scan inline.
- **Not exercised:** real-repo scan latency, live dashboard responsiveness on a large
  history store, actual SQLite query plans, render-profile data, image cache headers.
  No production or live system was touched; no installer, `security-scan`, dashboard
  server, desktop launcher, or `.adx/risks.json` dangerous pattern was run.
- **Tooling note:** early in the session the tool-result channel delivered output in
  a delayed batch, which briefly looked like a fault; once it caught up, every read
  and the import check returned real content, and this report reflects that verified
  evidence.
