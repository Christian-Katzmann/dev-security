# Dashboard Server

Primary source path: `src/security_observatory/dashboard_server.py`

This module serves the local dashboard, exposes API endpoints, starts background scan jobs, exports raw reports and AI handoff prompts, and handles Honey Key creation, insertion, archiving, and trigger recording.

Verification:

- Start with `python-import-cli`.
- Run `python-pytest` when a working pytest environment exists.
- Only run a live dashboard server when the task requires browser or API behavior validation.

Risks:

- Honey Key endpoints must preserve path containment, no-overwrite behavior, and explicit placement confirmation.
- Report endpoints expose local scan output; do not paste or upload full reports casually.
- Background scan jobs can invoke external scanner binaries.
