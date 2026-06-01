# Acceptance: 11-case-lifecycle

## Acceptance Criteria

### S-020 — Canonical case-lifecycle module + reconciled vocabulary
- [ ] One module — `src/security_observatory/lifecycle.py` — owns the canonical case-state set and the allowed transitions between states. It is the single source of truth: `decisions.py` (the status set previously hardcoded at `decisions.py:10`), `cases.py`, `storage.py`, and `mcp_server.py` (`SUPPORTED_CASE_STATUSES` at `:51`) all derive their state vocabulary from it rather than re-declaring it. `grep -rn "CASE_DECISION_STATUSES\|SUPPORTED_CASE_STATUSES" src/` shows no second independent definition of the state set (each reference resolves to the `lifecycle.py` canonical source).
- [ ] The two divergent four-value enums are reconciled: the storage/decision view (`verified/false_positive/accepted_risk/fixed`) and the MCP presentation view (`open/verified/accepted_risk/resolved`) are expressed as one canonical set plus an explicit, documented presentation mapping. The `fixed`/`false_positive`→`resolved` collapse at `mcp_server.py:224-231` (`_case_status_label`) is driven by that documented mapping table, not an ad-hoc inline fold.
- [ ] A single documented mapping table exists (in the lifecycle module's docstring and/or `docs/`/`glossary.md`) showing each canonical state, its stored decision-status form, and its MCP-presentation form — so an agent querying MCP `status=resolved` can find, in one place, that `resolved` is a display fold of `fixed` + `false_positive`. The unrelated scan-diff axis (`change_status ∈ new/recurring/resolved`, `storage.py:1422`, `dashboardData.ts:856`) is qualified off the bare word `resolved` (e.g. renamed/labelled `diff_status`) or explicitly documented as a distinct axis so the same word no longer names two unrelated state machines.
- [ ] Any change to the storage status CHECK constraint (`storage.py:574-578`) is a non-destructive widen: existing case rows survive, no destructive table rebuild is required, and a round-trip test loads an old-shape fixture/row and reads it back intact.
- [ ] The suppression semantics are unchanged: `SUPPRESSING_DECISION_STATUSES` (`decisions.py:11`) still names exactly `false_positive` + `accepted_risk`, and the high/critical human-confirmation hold is untouched. `uv run pytest tests/test_severity_gate.py` passes.

### S-035 — Visible in-progress/verifying state + proof-bound closure
- [ ] An explicit intermediate lifecycle state (`in_progress`/`awaiting_rescan`, i.e. "fix applied, awaiting rescan proof") exists in the canonical `lifecycle.py` state machine from S-020 — not a second parallel one — with a defined transition into and out of it. `grep -rn "in_progress\|awaiting_rescan\|verifying" src/security_observatory/` shows the new state lives in the canonical module.
- [ ] A resolved case is provably bound to the scan + diff entry that closed it: instead of closing by absence, a rescan that no longer finds a case records the resolving `scan_id` and the corresponding `resolved[]` diff entry on the case (extending the existing `resolved_by_scan_id` binding at `storage.py:2870-2872`). A test acts on a case, runs/simulates a rescan, and asserts the case shows a resolved state carrying the new scan id (closure proof, not closure-by-disappearance). *(This closure-proof binding sub-claim is Medium-confidence per the synthesis until implemented and tested.)*
- [ ] A just-closed case stays visible for one cycle as an affirmative "Verified ✓ in scan X" state rather than silently dropping out of the attention list (apply to the live inline **`CaseDetailCard`** in `App.tsx` ~`:3742`; the orphan `CaseCard.tsx:228-234` named in the original evidence was deleted by batch 09 (S-036), so target the live card — it should name the scan that closed it rather than relying solely on "not found in the latest scan" framing). `cd dashboard-ui && npm run build` is clean and `npm run lint` passes after the UI change.
- [ ] The full case lifecycle is demonstrable end to end: a case can move open → in-progress/verifying → resolved, with the resolved state bound to the diff + scan that closed it. `uv run pytest tests/test_cases.py` passes, including the new lifecycle-transition and closure-binding tests.

## Required Checks
| Check | Why |
| --- | --- |
| `uv run pytest tests/test_cases.py tests/test_severity_gate.py` | Matrix validation path for S-020/S-035: exercises the new lifecycle transitions and closure binding, and proves the suppression gate semantics are unchanged. |
| `uv run pytest` | Confirms no regression across storage, MCP, normalize, and decision paths from the enum reconciliation and the (non-destructive) CHECK-constraint widen. |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check (AGENTS.md rule) that the new `lifecycle.py` and the rewired `decisions`/`cases`/`storage`/`mcp_server` modules load cleanly. |
| `grep -rn "CASE_DECISION_STATUSES\|SUPPORTED_CASE_STATUSES\|in_progress\|awaiting_rescan" src/` | Confirms one canonical state set (no second independent definition) and that the new intermediate state lives in the canonical module — the "one documented mapping" outcome from the matrix/synthesis. |
| `cd dashboard-ui && npm run build` | Proves the proof-bound "Verified ✓ in scan X" closure UI (S-035) compiles and renders; matrix validation path includes the dashboard surface. |
| `cd dashboard-ui && npm run lint` | `tsc --noEmit` confirms the case-state / diff-axis type changes (`dashboardData.ts:855-856`) type-check with no dangling references. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
