# Implementation Receipt: Step 1.2 - Rotation trust observability

## Target

- Plan: `campaigns/devsec-rotation-completeness.md`
- Batch: Step 1.2 - Status-vs-history consistency check, job state persistence, confirmation phrase drift test
- Source report item(s): `campaigns/devsec-rotation-followup-notes.md` H2, H5, H6

## Before Health

Rotation status and rotation history could disagree without an explicit dashboard signal. Dashboard rotation jobs lived only in `CHECK_JOBS`, so a dashboard restart could lose the live job handle while the rotation continued on disk. The Tier 5R confirmation phrase existed in backend Python, frontend TypeScript, and doctrine markdown without a drift lock.

## Changes Made

- Added `rotation_consistency_check(repo_path)` with structured warnings for state/history status mismatch, history events without state records, and state records without history events.
- Added the `consistency` payload to `GET /api/rotation/status/<repo>`.
- Added dashboard startup rediscovery for recent in-flight rotation jobs from `rotation-state.json` plus `rotation-log.jsonl`, using a 2x rotation timeout cutoff.
- Returned rediscovered `job_id` values through the trigger conflict path and let the modal reattach to that running job.
- Added the amber "Trust trail inconsistent" badge in `RotationStatusCard`.
- Added a Tier 5R confirmation phrase drift test across Python backend, TypeScript frontend, and `docs/agent-safety.md`.
- Rebuilt the dashboard bundle.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -m py_compile src/security_observatory/rotation.py src/security_observatory/dashboard_server.py tests/test_rotation_confirmation_phrase.py` | PASS | Syntax check for changed Python paths. |
| `uv run pytest tests/test_rotation.py tests/test_dashboard_rotation_endpoints.py tests/test_dashboard_rotation_trigger.py tests/test_rotation_confirmation_phrase.py` | PASS | 54 focused rotation/dashboard tests passed. |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | PASS | CLI import smoke printed `ok`. |
| `uv run pytest` | PASS | 342 tests passed. |
| `cd dashboard-ui && npm run lint` | PASS | TypeScript typecheck passed. |
| `cd dashboard-ui && npm run build` | PASS | Vite build regenerated bundled dashboard assets. |
| Local dashboard browser check | PASS | `http://127.0.0.1:8767` loaded; no console warnings/errors; document, JS, CSS, and API requests returned 200. |

## After Health

Green. The rotation status API now names trust-trail contradictions instead of silently presenting a status row as authoritative, restart rediscovery restores recent running jobs into the dashboard's polled-job model, and phrase drift fails the Python suite.

## Remaining Risk

The rediscovered job is a lightweight handle: it can reattach the modal and prevent duplicate rotation, but it cannot reconstruct prior stdout tail from before the dashboard restart.

## Next Batch

Step 2.1 - Test-mode toggle, advanced options exposure, per-secret rotation_warning plumbing.
