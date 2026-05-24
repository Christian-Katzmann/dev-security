# Step 2.1 summary — canary-first staging + pre-rotation health refusal

Companion skill changes for Phase 2.1 land at `~/.claude/skills/secrets-rotation/`. This note tracks what the campaign produced and what downstream steps need to know.

## Two new safety gates in the pipeline

1. **`HEALTH_CHECK`** runs first. The adapter captures a baseline auth-error rate (default 5 min). Any auth-error pattern match in the baseline refuses the rotation with a clear plain-English message and emits a dedicated audit phase (`refused_unhealthy_baseline`). `--skip-health-check` bypasses for incident-response cases; the bypass is recorded in state and surfaces in the receipt.

2. **Canary-first staging** splits the old single STAGE step into `STAGE_CANARY → DEPLOY_CANARY → VERIFY_CANARY → STAGE_PROD → DEPLOY_PROD → VERIFY_PROD`. Verify gates run BOTH `plugin.verify` (provider) and `adapter.applicationProbe` (application). A canary failure rolls back the canary write and halts at `CANARY_VERIFY_FAILED` — prod env is never touched.

## New states

`RotationStatus`: `HEALTH_CHECK`, `STAGED_CANARY`, `DEPLOYED_CANARY`, `IN_CANARY_VERIFY`, `VERIFIED_CANARY`, `STAGED_PROD`, `DEPLOYED_PROD`, `HEALTH_CHECK_FAILED`, `CANARY_VERIFY_FAILED`.

`ErrorCode`: `HALTED_AT_HEALTH_CHECK`, `HALTED_AT_CANARY_VERIFY`.

Audit phase: `refused_unhealthy_baseline` (with `baseline_error_count` + `baseline_window_ms` fields).

## What downstream steps inherit

- **Step 2.2 (SOAK)**: the pipeline already plumbs `baseline_result` through state via `runHealthCheck`. SOAK reads it from `rotation.baseline_result` instead of re-capturing. The `IN_SOAK` / `SOAK_FAILED` states + `--no-soak` flag are the remaining work.
- **Step 2.3 (Verification report)**: needs to handle the two new terminal statuses (`HEALTH_CHECK_FAILED`, `CANARY_VERIFY_FAILED`) with the HALTED-shape receipt — but distinct enough that the operator sees WHICH gate caught it.
- **Adapter hints**: the pipeline accepts `RunRotationOptions.adapterHints` and forwards verbatim into every adapter call site. Step 1.3 already wired up `catalog-hints.ts.tmpl`; the CLI scaffolding to plumb per-secret hints from `catalog.json` into `runRotation` is a v0.2 wiring task carried by Step 3.1's docs pass.

## Tests

`npm test` in the skill workspace: 30/30 pass across `adapter-registry.smoke`, `pipeline.smoke`, and `python-cli.smoke` test files. New pipeline tests cover: full happy path through canary + prod verify, HEALTH_CHECK refusal, `--skip-health-check` bypass, and CANARY_VERIFY_FAILED with prod left untouched.
