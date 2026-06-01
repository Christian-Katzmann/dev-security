# Scan Orchestrator

Primary source path: `src/security_observatory/scan_orchestrator.py`

This module owns `scan_repo` — the single, append-only scan path that the CLI,
the MCP server, and the dashboard all drive — plus the parser/profile
resolution it needs to stand alone. It used to live in `cli.py`, which forced
`mcp_server` and `dashboard_server` to import the command-line entry point just
to run a scan (a `cli ↔ dashboard_server` import cycle and an `mcp → cli`
reach). It now imports only domain/pipeline layers (`model`, `scanners`,
`storage`, …) and none of the entry-point modules, so all three can share it
without re-introducing the cycle.

Verification:

- Start with `python-import-cli`.
- Run `python-pytest`; `tests/test_sbom.py` and `tests/test_scan_rotation_detection.py` exercise this path.
- Run a live scan only when the task requires real scanner behavior.

Risks:

- This drives external scanner binaries and writes local scan history under `~/.security-observatory` — see `.adx/risks.json` `scanner-installer` and `local-security-data`.
