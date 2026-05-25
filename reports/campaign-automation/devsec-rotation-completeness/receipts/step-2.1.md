# Implementation Receipt: Step 2.1 - Rotation modal options and warnings

## Target

- Plan: `campaigns/devsec-rotation-completeness.md`
- Batch: Step 2.1 - Test-mode toggle, advanced options exposure, per-secret rotation_warning plumbing
- Source report item(s): H4 test mode toggle, M5 advanced options, M6 class warning hard-coded

## Before Health

The dashboard trigger endpoint already accepted `test_mode`, `skip_health_check`, and `soak_minutes`, but the confirm modal only exposed `--no-soak`. Rotation status rows also did not carry catalog-specific `rotation_warning` copy, so the modal fell back to broad class warnings.

## Changes Made

- Added catalog enrichment to `read_rotation_status`, including per-repo `src/lib/rotation/catalog.local.json` precedence over the global secrets-rotation catalog.
- Added `rotation_warning` and `soak_window_minutes` fields to rotation status rows and frontend types.
- Updated the rotation confirm modal with a test-mode checkbox, collapsed advanced options, skip-health-check acknowledgement, soak-minute override, and per-secret warning preference.
- Added endpoint/unit coverage for catalog enrichment and trigger-option forwarding.
- Rebuilt the dashboard bundle so served assets include the modal changes.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | PASS | Fast import smoke check passed. |
| `uv run pytest tests/test_rotation.py tests/test_dashboard_rotation_endpoints.py tests/test_dashboard_rotation_trigger.py tests/test_mcp_server.py` | PASS | 95 focused rotation/dashboard/MCP tests passed. |
| `npm run lint` | PASS | TypeScript check passed. |
| `npm run build` | PASS | Vite rebuilt `src/security_observatory/dashboard/index.html` and assets. |
| `uv run pytest` | PASS | Full Python suite passed: 346 tests. |
| Dashboard load at `http://127.0.0.1:8876` | PASS | Built dashboard opened with no console errors; temporary server stopped. |

## After Health

Green. The dashboard now exposes the backend-supported operator options, status rows carry catalog warning/default-soak metadata, and tests cover both the catalog lookup and trigger forwarding behavior.

## Remaining Risk

No known implementation gap for this step. Browser validation was a load/console check, not a full manual rotation against a real scaffolded repo; campaign Step 5.1 covers the live end-to-end verification.

## Next Batch

Step 2.2 - Class-aware phase track, B-human paste-resume affordance, cancellation guidance.
