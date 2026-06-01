# Acceptance: 15-split-dashboard-server

## Acceptance Criteria
- **S-016 (route table):** `do_GET`, `do_POST`, and `do_DELETE` in `src/security_observatory/dashboard_server.py` dispatch through an explicit route table (a path/method → handler mapping) rather than long inline if/elif chains. Each verb still wraps its dispatch in the existing top-level error envelope (the S-006 `try/except → send_json_error(500)` backstop on GET, and the equivalent on POST/DELETE) — the calm-JSON-500 behavior on a corrupt/raising route is preserved, not regressed.
- **S-016 (inline HTML pages relocated):** The two server-rendered pages no longer live as f-strings inside the request-handler file — `report_page`/`prompt_report_page`/`raw_report_page` (the `/report/` export page, was near `:1146`–`:1243`) and `_docs_page_shell` (the `/docs/` shell, was near `:1511`–`:1515`) are moved into a dedicated template/page module imported by the handler (or rendered from the React build). `grep -n "<!doctype html>" src/security_observatory/dashboard_server.py` returns nothing (the inline HTML is gone from the handler module).
- **S-016 (enrichment lifted out of the handler):** The per-repo enrichment that ran inline in the GET request path is extracted into a named payload/assembly helper called by the route handler, so the handler routes and the assembly logic is separately readable. `dashboard_server.py` is materially smaller than its starting 4,263 lines.
- **S-016 (no behavior change / no cycle reintroduced):** Every endpoint keeps its exact path, request/response shape, status codes, and CSRF/Origin behavior — the split is purely structural and the full dashboard endpoint test suite passes unchanged. The `cli↔dashboard` cycle is not reintroduced: the scan import at the former `:1844` site points at the scan-orchestrator module (post batch 14), not back into `cli` in a way that recreates the cycle. The fast import check passes.

## Required Checks
| Check | Why |
| --- | --- |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check per AGENTS.md; proves the route-table + template-module split imports cleanly and didn't reintroduce an import error or the `cli↔dashboard` cycle. |
| `uv run python -c "import security_observatory.dashboard_server; print('ok')"` | Confirms `dashboard_server` itself imports under the uv-managed env after the handler/template/orchestrator-import restructure. |
| `uv run pytest` (dashboard endpoint tests included) | Proves no endpoint changed path, shape, status code, or error envelope — the structural split is behavior-preserving across the existing dashboard endpoint suite. |
| `grep -n "<!doctype html>" src/security_observatory/dashboard_server.py` returns nothing | Proves the two inline server-rendered HTML pages were relocated out of the request-handler module (template extraction landed). |
| `wc -l src/security_observatory/dashboard_server.py` is materially below 4,263 | Confirms the god module shrank — routing, templates, and enrichment moved to their own seams rather than staying inline. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
