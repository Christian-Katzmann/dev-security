# Final Rework Receipt

Run: d-vsec-tool-catalog-foundation-final-rework-20260521-181800
Time: 2026-05-21T16:30:00Z

## Gaps addressed

- Added a non-scanner `external-surface` Tool Catalog placeholder as a display-only Coming Soon workflow.
- Kept the placeholder out of `scanner_catalog()` compatibility by leaving `scanner_key` and `legacy_scanner` unset.
- Exposed safe policy-derived metadata for the placeholder through the normal catalog and dashboard summary payloads:
  - `lifecycle=coming-soon`
  - `install_state=coming-soon`
  - `install.method=none`
  - `install.owner=not-applicable`
  - `install.detection=none`
  - `install.uninstall_posture=not-supported`
  - `policy.network_access=required`
  - `policy.external_targets=user-provided`
  - `policy.needs_approval=true`
  - `policy.allowed_for_agent_lab=false`
  - External Surface pack membership as `coming-soon`
- Added focused contract coverage for the derived labels `Display only`, `Coming soon`, and `Agent Lab blocked`.

## Files changed

- `/Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/catalog.py`
- `/Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_scanners.py`
- `/Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_dashboard_report_exports.py`

## Verification run

- `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` passed.
- `python3 -m compileall -q src tests` passed.
- Direct Python contract check for `tool_catalog(detect_install_state=True)`, `scanner_catalog()`, and `ObservatoryDB.dashboard_payload()` passed.
- `python3 -m pytest tests/test_scanners.py tests/test_dashboard_report_exports.py -q` could not run because the active Python has no `pytest` module installed.

## Remaining gaps

- None known from the final review's NEEDS WORK item.

## Next action

- Rerun the whole-campaign final review now.
