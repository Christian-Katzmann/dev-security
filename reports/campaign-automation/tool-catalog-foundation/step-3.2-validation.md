# Step 3.2 Validation Receipt

Automation: `d-vsec-tool-catalog-foundation-step-3-2-20260521-160402`

## Result

APPROVED for this bounded validation step.

## Checks Run

- `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` passed.
- `npm run lint` in `dashboard-ui/` passed.
- `python3 -m compileall -q src tests` passed.
- Plain-Python catalog contract assertions passed for detected, missing, not-configured, managed, unavailable, and coming-soon install-state behavior.
- `python3 -m pytest tests/test_scanners.py tests/test_dashboard_report_exports.py -q` could not start because `pytest` is not installed.
- `.venv/bin/python -m pytest tests/test_scanners.py tests/test_dashboard_report_exports.py -q` could not start because `pytest` is not installed in the repo venv.

## Contract Coverage Added

- `tests/test_scanners.py` now checks that path-backed tools use runtime detection for `detected`, `missing`, and setup-blocked `not-configured` states.
- `tests/test_scanners.py` now checks the label and Agent Lab gating contract for `detected`, `managed`, `missing`, `unavailable`, and `coming-soon` install states.
- `tests/test_scanners.py` now checks that `run_scanner()` still uses real binary availability at execution time instead of trusting catalog metadata.

## Stale Metadata Risk

The catalog can safely describe what a tool is and what policy applies, but runtime availability still needs to come from `shutil.which(...)`, config preflights, or a future managed-tool registry. The current dashboard summary and `/api/tool-catalog` path both request detection-backed catalog data, so stale static metadata should not make a missing scanner look runnable.

Remaining risk is environmental, not contract-level: the normal pytest suite cannot run until `pytest` is installed in an active Python environment.
