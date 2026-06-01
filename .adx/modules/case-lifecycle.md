# Case Lifecycle

Primary source path: `src/security_observatory/lifecycle.py`

This module is the single source of truth for the states a security case can
hold and the transitions between them. Before it existed, two divergent
four-value enums described the same case across surfaces — the storage/decision
view (`verified` / `false_positive` / `accepted_risk` / `fixed`, what a human
records) and the MCP presentation view (`open` / `verified` / `accepted_risk` /
`resolved`, what an agent sees). They are now one canonical lifecycle plus an
explicit, documented presentation mapping. `decisions.py`, `cases.py`,
`storage.py` (the CHECK constraint), and `mcp_server.py` all derive their state
vocabulary from here.

Three layers, one place:

1. **Decision statuses (stored)** — what a human records; persisted in `case_decisions.status` and validated by `set_case_decision`.
2. **Lifecycle / presentation states (shown)** — what a case *is* at a glance, in the dashboard and the MCP `cases(status=...)` filter.
3. The presentation mapping that translates stored decisions into shown states.

Verification:

- Start with `python-import-cli`.
- Run `python-pytest`; `tests/test_cases.py` and `tests/test_storage_migrations.py` exercise the state vocabulary and the CHECK constraint.

Risks:

- A wrong state mapping can mislabel an unresolved security case as closed — treat changes here as `local-security-data` sensitive (`.adx/risks.json`).
