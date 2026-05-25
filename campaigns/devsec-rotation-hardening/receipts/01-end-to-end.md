# End-to-end verification receipt

**Date:** 2026-05-25
**Campaign:** devsec-rotation-hardening (step 3.3)
**Method:** Code review + automated test execution + MCP query + on-disk state inspection. No live rotation triggered (autonomous session; interactive CLI and browser tests deferred to manual follow-up).

---

## Phase 1 — Reset command (Step 1.1)

**Verdict: PASS**

| Criterion | Evidence |
|---|---|
| `security-scan reset foo --dry-run` lists what would be removed | `reset.py:36-113` plan_reset returns table row counts + filesystem paths; `test_dry_run_plan` passes |
| Without `--yes`, prompts for confirmation phrase | `cli.py:733-744` exact-phrase match; `test_confirmation_refusal_without_yes` passes |
| `--backup-to` produces sqldump + reports tarball | `reset.py:116-153` backup_repo_state writes both; `test_backup_creates_files` passes |
| `--include-rotation-scaffold` removes repo rotation files | `reset.py:234-268` removes state, log, receipts dir, src/lib/rotation/, rotate script; `test_execute_reset_removes_rotation_scaffold` passes |
| Mid-transaction failure leaves sqlite unchanged | `test_transactional_rollback_on_failure` uses ExplodingConnection; asserts row count unchanged after exception |

**Tests:** 13/13 passed (`tests/test_reset.py`, 0.41s)

---

## Phase 2 — Concurrency lock (Step 2.1)

**Verdict: PASS**

| Criterion | Evidence |
|---|---|
| Per-status check refuses with 409 | `dashboard_server.py:2954-2962` checks `ROTATION_INFLIGHT_STATUSES`; `test_trigger_409s_when_rotation_state_is_inflight` passes |
| Per-CHECK_JOBS check refuses with 409 + job_id | `dashboard_server.py:2963-2976` under `CHECK_JOBS_LOCK`; `test_trigger_409s_when_check_jobs_has_running_job` asserts 409 + `payload["job_id"]` |
| Both checks run before audit trail write | Lines 2954-2976 return before line 3020 (`_append_rotation_audit_event`) |
| Frontend recognizes 409 | `RotationTriggerFlow.tsx:122-134` explicit 409 branch extracts job_id; renders in ConfirmStep error display |

**Tests:** 12/12 passed (`tests/test_dashboard_rotation_trigger.py`, 7.60s)

---

## Phase 3.1 — Skill override audit completeness

**Verdict: PASS**

| Override flag | JSONL entry | Receipt file | State: manually_marked + override_kind |
|---|---|---|---|
| `--rollback` | `emitOverrideAuditAndReceipt` at line 490 | Same call | `manually_marked: true, override_kind: "rollback"` at line 481 |
| `--abort` | `emitOverrideAuditAndReceipt` at line 697 | Same call | `manually_marked: true, override_kind: "abort"` at line 689 |
| `--force-revoke` | `appendRotationLog` at line 741 + `emitOverrideAuditAndReceipt` at line 783 | Via finalize path | `manually_marked: true, override_kind: "force-revoke"` at line 737 |
| `--finalize` | `emitOverrideAuditAndReceipt` at line 783 | Same call | `manually_marked: true, override_kind: "finalize"` at line 772 |
| `--mark-rotated` | `emitOverrideAuditAndReceipt` at line 576 | Same call | `manually_marked: true, override_kind: "mark-rotated"` at line 559 |
| `--retry` | `appendRotationLog` at line 638 (old rotation ROLLED_BACK) | Via runRetry flow | `manually_marked: true, override_kind: "rollback"` at line 633 (superseded rotation) |

`--mark-rotated` IS present in v0.2 (lines 125, 500-584 of rotate.ts.tmpl). The open question is resolved: it was deliberately kept and now carries the full audit contract.

**RotationRecord schema:** `state.ts.tmpl` includes `manually_marked?: boolean` and `override_kind?: "mark-rotated" | "rollback" | "abort" | "force-revoke" | "finalize"`.

**Receipt shape:** `verification-report.ts.tmpl` has `renderOperatorOverrideShape` (lines 122-236) producing the OPERATOR_OVERRIDE receipt with override banner, pre-override status, and last JSONL entry verbatim.

**SKILL.md:** "Operator-override audit contract" section (lines 623-655) documents the three-part obligation.

**Failure-injection tests:** `tests/failure-injection.test.ts` lines 464-808 parametrize override-path tests covering state record, JSONL entry, and receipt shape for all flags.

---

## Phase 3.2 — Normalization + MCP + dashboard surface

**Verdict: PASS**

| Criterion | Evidence |
|---|---|
| `_normalized_status_entry` returns `manually_marked` + `override_kind` | `rotation.py:112-153` parameters + return dict (lines 151-152) |
| `read_rotation_status` reads fields with backwards-compatible default | `rotation.py:237-238` defaults to `False/None` for legacy state files |
| MCP `rotation_status` surfaces new fields | Confirmed via live MCP query: besk returns `manually_marked: false, override_kind: null` (correct v0.1 default) |
| MCP `rotation_history` surfaces `override_kind` | Confirmed via live query: besk entries show `override_kind: null` (no OPERATOR_OVERRIDE entries in v0.1 JSONL) |
| `RotationSecretRow` type extended | `dashboardData.ts:548-549` includes both fields |
| RotationStatusCard renders annotation | `RotationStatusCard.tsx:355-361` conditional amber badge "Operator override ({override_kind})" |
| RotationTriggerFlow ConfirmStep shows override note | `RotationTriggerFlow.tsx:374-385` AlertTriangle + previous override message |
| Frontend type-checks clean | `npx tsc --noEmit` exits 0, no errors |

**Tests:** 21/21 passed (`tests/test_rotation.py`, 0.04s). Includes:
- `test_read_rotation_status_surfaces_manually_marked_fields` — v0.2 state with fields set
- `test_read_rotation_status_defaults_manually_marked_for_legacy_state` — v0.1 state without fields
- `test_read_rotation_history_surfaces_override_kind`

---

## H1 evidence cross-reference (besk)

**On-disk state (v0.1, unchanged):**
- `rotation-state.json`: AUTH_SECRET shows ROTATED with log entry "marked ROTATED by operator (--mark-rotated)" at 2026-05-17T21:16:33Z
- `rotation-log.jsonl`: 6 entries, last is DEPLOY halted at 2026-05-17T19:46:31Z — no OPERATOR_OVERRIDE entry
- `rotation-receipts/`: directory does not exist

**MCP view:**
- `rotation_status`: AUTH_SECRET = ROTATED, `manually_marked: false` (correct v0.1 default — field didn't exist when this override happened)
- `rotation_history`: last event = DEPLOY halted. No override event in trail.

**Assessment:** The H1 gap is confirmed as real evidence. The v0.2 skill now closes this for future overrides. Besk's existing v0.1 state is read with backwards-compatible defaults (manually_marked=false), which is the specified behavior — the normalization does not retroactively infer override status from log entry text.

---

## Deferred to manual follow-up

These items require interactive CLI or browser testing:

1. **Reset besk + re-scaffold with v0.2** — requires interactive Tier 5R confirmation phrase + Claude Code `/secrets-rotation` invocation in besk repo
2. **Successful Class A rotation with `--test`** — requires `npm run rotate` in a scaffolded v0.2 repo
3. **Forced halt + override** — requires `rotate --fail-at DEPLOY` then `--mark-rotated`
4. **Dashboard visual rendering** — requires starting the dashboard server and navigating to besk's rotation view to confirm the amber annotation renders
5. **Concurrency lock browser smoke test** — requires two browser tabs triggering the same secret simultaneously
6. **Restore besk from backup** — depends on step 1's backup output

---

## Drift noticed

None. Post-implementation code matches campaign specs across all three phases.
