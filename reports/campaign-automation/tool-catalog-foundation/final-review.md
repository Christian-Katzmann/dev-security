APPROVED

The campaign delivered its stated foundation. The docs define the Tool Catalog and Security Packs vocabulary, the current scanner mapping, and the MVP rule that External Surface is display-only. The backend now has typed catalog metadata, enforceable policy fields, derived labels, legacy `scanner_catalog()` compatibility, detection-backed install state, `/api/tool-catalog`, and dashboard summary exposure. The TypeScript data contract includes the catalog shape and falls back cleanly for older summary payloads.

The previous final-review gap is closed. `src/security_observatory/catalog.py` now includes a non-scanner `external-surface` workflow entry with `lifecycle='coming-soon'`, `install_state='coming-soon'`, no install/run/uninstall posture, required-network and user-provided-target policy metadata, approval required, Agent Lab blocked, and External Surface pack membership. It has no `scanner_key` or `legacy_scanner`, so it stays out of scanner compatibility while still appearing in the detection-backed tool catalog payload.

Verification during this rerun:

- `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` passed.
- `python3 -m compileall -q src tests` passed.
- `cd dashboard-ui && npm run lint` passed.
- Direct Python contract checks for `tool_catalog(detect_install_state=True)`, `scanner_catalog()`, and `ObservatoryDB.dashboard_payload()` passed.
- `python3 -m pytest tests/test_scanners.py tests/test_dashboard_report_exports.py -q` still cannot start because the active Python has no `pytest` module installed.

Residual risk is environmental, not campaign-level: the focused pytest tests exist but cannot be executed in the current Python until `pytest` is installed.
