# Final Rework — Managed Security Packs

## Gaps Addressed

- Wired scanner execution to prefer a verified DëvSec-managed Gitleaks binary for the approved managed install proof target.
- Kept normal user-owned `PATH` detection as the fallback when no verified managed Gitleaks evidence exists.
- Preserved uninstall protection boundaries: scanner resolution only reads ownership evidence and executable paths; uninstall still requires verified DëvSec ownership.
- Added version-check fields to managed-tool manifest records so manifest-only evidence can remain verifiable.
- Added a read-only active managed-tool DB loader so scanner resolution can verify existing SQLite-owned installs whose manifest was written before those manifest fields existed.
- Added a focused regression test proving Gitleaks scans use the verified managed binary when `PATH` has no `gitleaks`.

## Files Changed

- `src/security_observatory/scanners.py`
- `src/security_observatory/managed_tools.py`
- `tests/test_scanners.py`

## Verification Run

- `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; import security_observatory.managed_tools; print('ok')"` passed.
- `python3 -m compileall -q src/security_observatory/scanners.py src/security_observatory/managed_tools.py tests/test_scanners.py tests/test_managed_tools.py` passed.
- Focused direct harness passed: with `PATH` empty and `shutil.which` returning `None`, `run_scanner("gitleaks", ...)` used the verified managed binary path and returned `available=True`.
- `python3 -m pytest tests/test_scanners.py tests/test_managed_tools.py` could not run because this Python environment has no `pytest` module.
- `.venv/bin/python -m pytest tests/test_scanners.py tests/test_managed_tools.py` could not run because the repo virtualenv also has no `pytest` module.

## Remaining Gaps

- None known from the final-review repair item.

## Final Review Rerun

- Yes. The campaign should rerun the whole-campaign final review now.
