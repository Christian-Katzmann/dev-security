NEEDS WORK

The Agent Lab campaign delivered the main product shape: docs define the user-mediated trust model and OAuth deferral, backend context export exists, proposal records are persisted in SQLite, API routes import/approve/preview/run proposals, the UI exposes Codex/Claude/local/manual flows without provider tokens, and focused tests cover the happy path plus major safety rails. Verification passed:

- `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"`
- `uv run pytest` -> 185 passed
- `cd dashboard-ui && npm run lint`
- `make dashboard-build`

However, the hostile-import contract is not strict enough yet. `src/security_observatory/agent_lab.py` silently accepts non-list values for some nested array fields via `_list_of_text`, notably `requested_permissions`, `requested_execution[].tool_ids`, and `recommended_tools[].safety_labels`. I confirmed a proposal with `requested_permissions = "local_repo_read"` and `tool_ids = "gitleaks"` is accepted. That conflicts with the campaign requirements for strict structured proposal import, schema validation, and no flexible natural-language/action coercion. It also means malformed `tool_ids` can be treated as omitted and expanded to all allowed tools for the profile, which is too forgiving for hostile input.

Smallest responsible repair:

1. In `src/security_observatory/agent_lab.py`, make list-typed proposal fields fail validation when present but not arrays. At minimum cover `requested_permissions`, `requested_execution[].tool_ids`, `recommended_tools[].safety_labels`, and any similar list helper call used for proposal import.
2. Keep the existing safe default only for omitted optional lists where the schema explicitly allows omission.
3. Add focused tests in `tests/test_agent_lab.py` proving malformed list fields are rejected and that omitted `tool_ids` still behaves intentionally.
4. Re-run the fast import check and `uv run pytest`; dashboard lint/build are only needed if the rework touches UI.
