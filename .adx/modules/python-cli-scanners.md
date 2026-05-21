# Python CLI And Scanners

Primary source path: `src/security_observatory/`

This module owns the `security-scan` CLI, scan profiles, scanner adapters, normalized reports, scoring, case generation, SQLite persistence, and the built-in AI static checks.

Useful entry files:

- `cli.py` wires command-line behavior and dashboard startup.
- `scanners.py` owns external scanner commands, timeouts, and scanner catalog metadata.
- `normalize.py`, `model.py`, `cases.py`, and `priority.py` turn raw scanner output into findings and cases.
- `storage.py` owns the SQLite schema and dashboard payload.

Verification:

- Start with `python-import-cli`.
- Run `python-pytest` when a working pytest environment exists.
- Run `security-scan-quick` only when scanner behavior or report output must be verified.

Risks:

- Scanner runs write under `~/.security-observatory/`.
- Installer and scanner commands can touch external tools.
- Secret-related output should be treated as sensitive even when redacted.
