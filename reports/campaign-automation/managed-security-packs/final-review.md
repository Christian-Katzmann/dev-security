# APPROVED

The Managed Security Packs campaign delivered its stated MVP intent.

Verified against the actual worktree evidence, not just step receipts:

- `docs/security-packs.md` defines the real MVP packs, Coming Soon packs, recommended scan profiles, External Surface display-only rule, and the locked Gitleaks managed-install proof target.
- `docs/tool-catalog.md`, `src/security_observatory/catalog.py`, `src/security_observatory/managed_tools.py`, `src/security_observatory/storage.py`, and `src/security_observatory/dashboard_server.py` establish install ownership, previews, SQLite plus manifest tracking, one bounded Gitleaks managed install/uninstall path, and uninstall protection for detected/user-owned tools.
- `src/security_observatory/scanners.py` now prefers a verified DëvSec-managed Gitleaks binary for scanner execution, while falling back to normal `PATH` detection when no verified managed copy exists.
- `src/security_observatory/cases.py`, `dashboard-ui/src/components/ScanCompletenessPanel.tsx`, and the dashboard data shape connect scan evidence gaps to relevant pack/tool pages without creating a pack-run mode.
- `dashboard-ui/src/App.tsx`, `dashboard-ui/src/dashboardData.ts`, and `dashboard-ui/src/index.css` add pack pages, Coming Soon/display-only treatment, install preview panels, and bounded managed install/uninstall controls only for the approved proof path.

The earlier final-review gap is closed. A focused harness with `PATH` empty and a verified managed Gitleaks record confirmed `run_scanner("gitleaks", ...)` used the managed binary path and returned `available=True`.

Verification run:

- `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; import security_observatory.managed_tools; print('ok')"` passed.
- `python3 -m compileall -q src/security_observatory/scanners.py src/security_observatory/managed_tools.py src/security_observatory/catalog.py src/security_observatory/dashboard_server.py src/security_observatory/storage.py tests/test_scanners.py tests/test_managed_tools.py` passed.
- Focused direct managed-Gitleaks scanner harness passed.
- `npm run lint` in `dashboard-ui` passed.
- `npm run build` in `dashboard-ui` passed.
- `git diff --check` passed.
- `python3 -m pytest tests/test_scanners.py tests/test_managed_tools.py` could not run because system Python has no `pytest` module.
- `.venv/bin/python -m pytest tests/test_scanners.py tests/test_managed_tools.py` could not run because the repo virtualenv has no `pytest` module.

No material cross-step shortcuts or regressions remain from this campaign.
