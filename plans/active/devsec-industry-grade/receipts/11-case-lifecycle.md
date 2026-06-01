# Implementation Receipt: 11-case-lifecycle

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 11-case-lifecycle
- Source report item(s): S-020 (canonical case-lifecycle module + reconciled vocabulary), S-035 (visible in-progress/verifying state + proof-bound closure)

## Before Health

- No `lifecycle.py` existed. Two divergent four-value enums named the same case:
  storage/decision view `CASE_DECISION_STATUSES = {verified, false_positive, accepted_risk, fixed}` (`decisions.py:10`) and MCP presentation view `SUPPORTED_CASE_STATUSES = (open, verified, accepted_risk, resolved)` (`mcp_server.py:51`), with an ad-hoc `fixed`/`false_positive`→`resolved` fold inline in `_case_status_label` (`mcp_server.py:233`).
- No intermediate `in_progress`/`verifying` state anywhere; the lifecycle was flat. Closure was by absence — `_scan_delta` set `change_status="resolved"` + `resolved_by_scan_id` with a "not found in the latest scan" message (`storage.py:2894-2898`), and the case dropped out of attention rather than showing proof.
- The word `resolved` ambiguously named both a case-presentation state and the scan-diff axis (`change_status ∈ new/recurring/resolved`).

## Changes Made

**S-020 (landed first, conceptually — single commit for the batch):**
- New `src/security_observatory/lifecycle.py` — the single source of truth for the case state set, allowed transitions, and the documented presentation mapping. Three layers in one place: stored decision statuses, lifecycle/presentation states, and the namespaced `DIFF_*` scan-diff axis. Module docstring carries the canonical mapping table.
- `decisions.py` now re-exports `CASE_DECISION_STATUSES = DECISION_STATUSES` and `SUPPRESSING_DECISION_STATUSES = SUPPRESSING_STATUSES` from `lifecycle` (no second independent definition). Added `in_progress → under_investigation` to `DEFAULT_VEX_STATUS_BY_DECISION`.
- `mcp_server.py`: `SUPPORTED_CASE_STATUSES = MCP_PRESENTATION_STATES`; `_case_status_label` now delegates to `lifecycle.mcp_status_label` (documented fold, not inline).
- `storage.py`: widened the `case_decisions.status` CHECK constraint to include `in_progress` (SCHEMA literal) + new non-destructive migration `_migrate_case_decision_status_constraint` (widen, preserve rows, explicit-column copy — no destructive rebuild of data).
- `docs/glossary.md`: new "Case lifecycle" section with the same mapping table and an explicit note that `change_status` is a distinct axis from the lifecycle state.

**S-035 (built on top of the same machine):**
- `in_progress` is a real state in the canonical machine (decision status + lifecycle state + MCP presentation), with defined transitions (`ALLOWED_TRANSITIONS`).
- `storage.py`: `_attach_lifecycle_state` stamps `case["lifecycle_state"]` from decision + diff on every case; resolved cases in `_scan_delta` now carry `lifecycle_state="resolved"` and an affirmative "Verified — not found in scan X, the rescan that closed it" `next_step`, bound to `resolved_by_scan_id` (closure proof, not absence).
- Dashboard (`dashboardData.ts`): added `CaseLifecycleState`, `CaseDiffStatus` alias (+ docs), `lifecycle_state`/`lifecycleState`/`resolvedByScanId` fields, `caseLifecycleLabels`, `in_progress` in `CaseDecisionStatus`/labels/ranks/counts.
- `App.tsx` `CaseDetailCard`: shows a "Lifecycle" KV, an affirmative "Closure proof — Verified in scan X" panel for rescan-closed cases, friendly decision labels, and a new "Fix in progress" decision button (the transition into `in_progress`).
- `index.css`: `.closure-proof` style.
- Tests: `tests/test_cases.py` gained 5 tests (module vocabulary/mapping, transitions, `set_case_decision` accepts non-suppressing `in_progress`, legacy CHECK-constraint widen round-trip, rescan closure-proof binding, fixed-but-present → `in_progress`).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/test_cases.py tests/test_severity_gate.py` | PASS | 26 passed; new lifecycle/closure tests + unchanged suppression gate. |
| `uv run pytest` | PASS | 504 passed. No regression across storage/MCP/normalize/decisions. |
| `python3 -c "...import security_observatory.cli..."` | PASS | `ok` — new `lifecycle.py` + rewired modules load. |
| `grep -rn "CASE_DECISION_STATUSES\|SUPPORTED_CASE_STATUSES\|in_progress\|awaiting_rescan" src/` | PASS | `CASE_DECISION_STATUSES`/`SUPPORTED_CASE_STATUSES` each resolve to the `lifecycle.py` canonical source (alias only); `in_progress` lives in the canonical module. |
| `cd dashboard-ui && npm run build` | PASS | Clean build; regenerated `dashboard/index.html` committed (assets gitignored, per repo convention). |
| `cd dashboard-ui && npm run lint` | PASS | `tsc --noEmit` clean. |

## After Health

- One canonical `lifecycle.py` owns the state set + transitions; storage/decisions/MCP/dashboard all derive from it. The `fixed`/`false_positive`→`resolved` fold is the documented `DECISION_PRESENTATION` mapping, mirrored in the glossary table.
- `in_progress`/verifying is a real, transition-defined state; a fixed-but-still-present case reads `in_progress` on the dashboard.
- A rescan-closed case is bound to the closing scan and shows "Verified ✓ in scan X" for one cycle (proof, not absence) — covered by a test that acts→rescans→asserts the binding.
- Suppression semantics unchanged: `SUPPRESSING_DECISION_STATUSES == {false_positive, accepted_risk}`; high/critical human-confirmation hold intact (`test_severity_gate.py` green).
- S-020 and S-035 → Green.

## Remaining Risk

- The MCP presentation label is intentionally coarse (no per-scan diff context), so `fixed` still folds to `resolved` at MCP while the dashboard shows the richer `in_progress` beat — documented in the mapping table; an MCP-only consumer won't see the verifying beat. This is by design (backward compatibility) and noted in `lifecycle.py`.

## Next Batch

12-surface-scan-history-trends (S-039, S-042). Downstream context notes added to batches 12 and 13 pointing at `lifecycle.py` (diff axis vs lifecycle state; `in_progress` as the post-land/pre-rescan beat). Target S-IDs unchanged.
