# Step 1.1 vocabulary audit

Status: implemented and verified on 2026-05-24T22:02:33Z.

## Summary

This step locks DëvSec vocabulary across the dashboard, CLI, docs, reports, and MCP surface:

- **Cases** are the user-visible grouped work items.
- **Raw findings** are scanner-level records and evidence rows.
- **Critical / Elevated / Warning / Low** are reserved for security severity, not install, setup, runtime, or catalog priority state.

## Audit table

| Surface | Before | After | Compatibility note |
| --- | --- | --- | --- |
| Dashboard navigation and case surfaces | `Findings`, `Open findings`, suppressed `findings` | `Cases`, `Open cases`, suppressed `raw findings` where scanner rows are counted | Internal tab id remains `findings` to avoid routing churn. |
| Overview KPIs and activity | User-visible grouped work and raw scanner totals both used `findings` | Open work uses `cases`; saved scanner records use `raw findings` | Raw JSON fields still feed the counts. |
| Tool Catalog and packs | Missing/setup/runtime states borrowed warning-like tone and `Missing` labels | UI copy uses `Not installed`, `Needs setup`, `Approval required`, `Default check`, and info/neutral tone | Internal install enum remains `missing`; display label maps to `Not installed`. |
| Scanner doctor and CLI output | `missing`, `not found`, and skipped scanner copy read like broken protection | CLI groups not-installed common vs optional tools and keeps skipped/unavailable as evidence gaps | Existing scanner status fields stay unchanged. |
| Report and AI handoff pages | Mixed `cases` and `findings` without explaining the layer | Report summaries show `Cases`, `Raw findings`, and `Suppressed raw findings` | Static report shell and server-generated pages now match. |
| MCP adapter | Tool list exposed `findings` as the scanner-record query | Added preferred `raw_findings(...)`; kept `findings(...)` as a compatibility alias | MCP tool count is now eleven. Existing clients do not break. |
| Docs and doctrine | Current docs used `findings` for raw records, user tasks, and agent copy | `docs/vocabulary.md` defines the lock; docs use `cases` or `raw findings` based on layer | Historical field names are documented as compatibility names. |
| Severity vocabulary | Catalog priority and non-security states used severity-like labels or tones | Severity words stay on security risk only; non-security state uses neutral words | Code tone ids may remain internal when not user-facing. |

## API and contract decision

No breaking JSON field rename was made. The normalized JSON, dashboard API, and SQLite schema keep `findings`, `active_findings`, and `suppressed_findings`; these are documented as raw-finding compatibility fields. New user-facing copy and MCP clients should prefer `raw findings` / `raw_findings(...)`.

External JSON consumers are not known from this repo. The safe policy is to keep aliases until there is a versioned API plan and a deprecation window.

## Verification

- `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"`
- `uv run pytest` — 273 passed.
- `cd dashboard-ui && npm run lint`
- `cd dashboard-ui && npm run build`
