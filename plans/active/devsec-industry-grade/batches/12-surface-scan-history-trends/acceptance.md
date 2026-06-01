# Acceptance: 12-surface-scan-history-trends

## Acceptance Criteria

### S-039 — Surface scan-history + arbitrary scan-diff in the UI
- [ ] A history/trends panel exists in the dashboard that renders the **full local per-scan history series** (not just the 7-bar `postureWeek` proxy at `App.tsx:506-508`). The panel reads from the real history data already shipped to the client (`summary.history` from `/api/summary`, or a confirmed dedicated history endpoint) and is reachable from a primary surface (Overview and/or Activity). A user can read posture across more than the latest scan pair.
- [ ] The user can compare **two arbitrary scans**, not only "since last scan." A base/head scan picker drives a scan-to-scan diff, and the diff request/computation carries **both** the chosen base and head (not just `repo`/last-pair). If the comparison needs a server route the current tree lacks, the route is added with a Python test exercising it; if it can be computed from data already in the payload, a component test asserts the selected base/head both flow into the rendered diff.
- [ ] No dead-end or fake affordance: the picker and panel are wired (real fetch/computation + render), not clickable-looking controls that no-op. `grep -rn "scan-history\|scan-diff\|trendValues" dashboard-ui/src/` shows the history/diff surface is actually consumed, not just defined.
- [ ] `cd dashboard-ui && npm run build` and `cd dashboard-ui && npm run lint` are clean after the panel + picker land.

### S-042 — Render posture-over-time trend (or remove the dead helper)
- [ ] `trendValues` no longer dead: either (a) `trendValues(summary)` (`dashboardData.ts:2079`) is rendered as a posture sparkline on Overview and/or Activity — `grep -rn "trendValues" dashboard-ui/src/` returns at least one **call site** in addition to the definition, and the sparkline renders from the real `summary.history` series — **or** (b) the helper is deleted and the misleading "trend" scaffolding removed, with `grep -rn "trendValues" dashboard-ui/src/` returning nothing. No half-built trend feature remains presented as if whole.
- [ ] The shipped posture-trend (if rendered) reads honestly: it shows the actual per-scan health series, and the single `health_delta` "trend" number at `App.tsx:2317` is either superseded by or made consistent with the sparkline (the UI does not present a one-number delta as a "trend" while a richer series sits unused).
- [ ] `cd dashboard-ui && npm run build` is clean (matrix validation path for this row: trend sparkline renders; `npm run build`).

## Required Checks
| Check | Why |
| --- | --- |
| `cd dashboard-ui && npm run build` | Matrix validation path for both S-039 and S-042 — proves the history/trends panel, base/head picker, and the wired/removed `trendValues` compile and render. |
| `cd dashboard-ui && npm run lint` | `tsc --noEmit` confirms the new panel/picker, any new types for the history series, and the `trendValues` call-site (or its removal) type-check with no dangling references (S-039, S-042). |
| `grep -rn "trendValues" dashboard-ui/src/` | Confirms the S-042 outcome is unambiguous: a real call site exists (rendered) **or** zero matches (removed) — never the prior "defined once, zero call sites" dead-code state. |
| `grep -rn "scan-history\|scan-diff\|history" dashboard-ui/src/ \| grep -i fetch` (or equivalent consumer scan) | Confirms S-039's history/diff surface has a real UI consumer, closing the lens "scan-history UI consumers = 0 / scan-diff base/head = 0" finding. |
| Component test (vitest, if the batch-07 harness exists): render the history/trends panel and assert it reads the history series; select base/head and assert the diff carries both scans. | Synthesis "Suggested validation" for S-039 — proves the panel fetches/renders and the base/head selection actually drives the diff. |
| `uv run pytest` | Required only if S-039 adds a server route/handler for arbitrary scan diff; proves the new endpoint works and no Python regression (skip-justify in the receipt if no backend change was needed). |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check (AGENTS.md rule) if any Python (e.g. a new diff route) was touched. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
