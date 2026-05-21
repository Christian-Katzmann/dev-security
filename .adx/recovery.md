# ADX Recovery Notes

## Python Import Fails

First check:

```bash
python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"
```

Common causes:

- Command was not run from the repo root.
- `PYTHONPATH` was not set and the package is not installed.
- A recent edit introduced an import error.

Recovery:

- Run the import smoke command from the repo root.
- If CLI entrypoint installation is needed, use `python3 -m pip install -e .` in a Python environment with pip.

## Pytest Is Missing

Current observed state: `python3 -m pytest --version` and `.venv/bin/python -m pytest --version` both fail because pytest is not installed; `.venv` also lacks pip.

Recovery:

- Do not claim tests passed until a working test environment exists.
- Use the import smoke check as a minimum signal for Python-only edits.
- Recreate or repair the development environment before relying on `python3 -m pytest`.

## Dashboard Dependencies Are Missing

First check:

```bash
cd dashboard-ui && npm run lint
```

Recovery:

- Run `make dashboard-install` if dependencies are absent or stale.
- Run `make dashboard-build` after dashboard source changes that must update bundled static assets.

## Dashboard Has No Data

Evidence: `docs/troubleshooting.md` says a scan must run before the dashboard has data.

Recovery:

- Run `security-scan .` only when the task requires creating local scan data.
- Remember that scan output is written under `~/.security-observatory/`.

## Scanner Is Missing

First check:

```bash
security-scan doctor
```

Safer local alternative before the wrapper exists:

```bash
python3 -c "import sys; sys.path.insert(0, 'src'); from security_observatory.cli import main; raise SystemExit(main(['doctor']))"
```

Recovery:

- Review `docs/setup.md` before running the installer.
- Do not run `./install-security-observatory.sh` unless installing machine-level scanner tools is intended.

## Desktop Launcher Server Stays Warm

Evidence: `docs/desktop-launcher.md` says closing the window leaves the dashboard server warm.

Recovery:

```bash
make desktop-quit
```

Use this after desktop launcher work so no background server is left running.

## Repo Path Moved

Evidence: the desktop app bakes the project path into the bundle.

Recovery:

```bash
make desktop-build
make desktop-install
```

Run these only when the desktop app needs to be refreshed for the new path.
