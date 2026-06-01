# Implementation Receipt: 15-split-dashboard-server

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 15-split-dashboard-server
- Source report item(s): S-016 (split `dashboard_server.py`: route table for `do_GET`/`do_POST`/`do_DELETE`, relocate the two inline server-rendered HTML pages, lift per-repo enrichment out of the GET handler). Lens report 02-architecture-health.initial.md (Rank 1 + "Undocumented Or Hidden Surfaces").

## Before Health

- `src/security_observatory/dashboard_server.py` was a 4,510-line god module (synthesis baseline 4,263; batch 14 had since grown it). One `DashboardHandler` class whose `do_GET`/`_handle_get` (`:2263`), `do_POST` (`:2612`), `do_DELETE` (`:2744`) were long inline `if/elif` dispatchers that also ran business logic inline.
- Two full `<!doctype html>` + `<style>` server-rendered pages lived as f-strings inside the handler module: the `/report/` export page (`report_page`/`prompt_report_page`/`raw_report_page` + `_page_shell`, `:1146`–`:1420`) and the `/docs/` shell (`_docs_page_shell`, `:1514`). `grep -n "<!doctype html>" dashboard_server.py` → 2 hits.
- Per-repo rotation/secret-name enrichment for `/api/summary` ran inline in the GET request path (`:2311`–`:2360`).
- S-006 GET error envelope (`do_GET` → `try/except` → `send_json_error(500)`) and the corrupt-store self-heal were already in place (batch 03) and had to be preserved.
- Batch 14 already moved `scan_repo` to `scan_orchestrator`; the `cli↔dashboard` cycle was already gone (`from .scan_orchestrator import scan_repo` at `:86`).

## Changes Made

**New module `src/security_observatory/dashboard_pages.py` (840 lines).** Moved the entire report/docs content-and-rendering cluster out of the handler module: `report_page`, `prompt_report_page`, `raw_report_page`, `_page_shell`, `_scan_cases`, `_case_sort_key`, `_case_card`, `_summary_table`, `_url_text`, `_docs_title`, `_docs_page_shell`, plus the content helpers they depend on (`build_ai_prompt`, `raw_report_export`, `raw_report_fallback`, `_suppression_view`, `_case_decisions_for_report`, `summarize_counts`, `category_label`, `CATEGORY_LABELS`, `SEVERITY_ORDER`). Pure functions; imports only `.cases` and `.decisions`, so there is no import cycle back into the handler.

**Route table in `dashboard_server.py`.** `do_GET`/`do_POST`/`do_DELETE` now dispatch through ordered class-attribute route tables (`_GET_ROUTES`, `_POST_ROUTES`, `_DELETE_ROUTES`) via a single `_dispatch(routes)` helper, instead of inline `if/elif` chains. Each route pairs a module-level matcher (`_match_exact`, `_match_exact_parsed`, `_match_rstrip_parsed`, `_match_prefix`, `_match_prefix_strip`, `_match_prefix_parsed`, `_match_docs`, `_match_regex_groups`) with the handler method name; the matcher returns the positional args to hand the handler. Existing worker methods (`serve_rotation_status`, `serve_credential_keys`, `save_case_decision`, `create_honey_key`, …) are registered directly with no wrappers. Inline GET branches were extracted into named `_get_*` methods; the run-check body into `_post_run_check`; two kwarg cases into `_get_honey_trigger`/`_post_honey_trigger`. Route ordering preserved exactly (e.g. `/api/rotation/jobs/batch/` before `/api/rotation/jobs/`).

**Error envelopes preserved.** `do_GET` still wraps `_handle_get` in the S-006 `try/except → send_json_error(500)`; `_post_run_check` keeps its own `try/except → 500`; the `_guard_mutation` Origin/CSRF gate still runs before any POST/DELETE dispatch. Unmatched GET → static-file fallback; unmatched POST/DELETE → `send_error(404)`. No path, request/response shape, status code, or CSRF behavior changed.

**Enrichment lifted.** The inline `/api/summary` per-repo enrichment is now the module-level `assemble_summary_payload(db)` (`:1340`); `_get_summary` is a thin route that calls it.

**Cleanup.** Removed now-dead imports (`html`, `assemble_suppression`, `build_security_cases`, `scanner_evidence_gaps`) from `dashboard_server.py`. The three page-only functions (`prompt_report_page`, `raw_report_page`, `raw_report_fallback`) are now imported from `dashboard_pages` in `tests/test_dashboard_report_exports.py` and `tests/test_cases.py` (their new home); `build_ai_prompt`, `raw_report_export`, `report_page`, `_docs_page_shell`, `_docs_title` are re-exported from `dashboard_server` because the handler/cli still use them internally.

**Downstream adjustments (no S-IDs changed):** updated line/anchor citations that this refactor moved — batch 16 (note that `assemble_summary_payload` is the dashboard-side seam for S-017), batch 18 (`inferred_secret_name` injection `:2182`→`:1416`), batch 19 (honey guards `:3282/3372/3379-3380/3394`→`:2675/2765/2772-2773/2787`), batch 21 (`CHECK_JOBS` `:98-99`→`:104-105`; writers/check-status `:284-374,1870-1923,2305-2313`→`:280-378,1086-1110,1809-1815`).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli; print('ok')"` | PASS | Fast import check; no cycle / import error. |
| `uv run python -c "import security_observatory.dashboard_server; print('ok')"` | PASS | Imports cleanly under uv env after split. |
| `uv run pytest` | PASS | 516 passed in ~62s. |
| `grep -n "<!doctype html>" src/security_observatory/dashboard_server.py` | PASS (no output) | Both inline HTML pages relocated to `dashboard_pages.py` (2 hits there). |
| `wc -l src/security_observatory/dashboard_server.py` | PASS | 3,700 lines — down from 4,510 (and below the 4,263 synthesis baseline). |
| `uv run ruff check dashboard_server.py dashboard_pages.py` | PASS | All checks passed (dead imports removed, re-exports honest). |

## After Health

- S-016 → **Green.** Three verbs dispatch through declarative route tables; the two `<!doctype html>` pages live in `dashboard_pages.py`; `/api/summary` enrichment is the named `assemble_summary_payload` helper. Handler module shrank 4,510 → 3,700 lines. S-006 GET 500 envelope and S-001 CSRF guard behave identically (full suite green, incl. `test_dashboard_get_resilience`, `test_dashboard_csrf`). No `cli↔dashboard` cycle reintroduced — `scan_repo` still imported from `scan_orchestrator`; `dashboard_pages` imports only `.cases`/`.decisions`.

## Remaining Risk

- None blocking. The route tables encode exact original ordering; the test suite (incl. every dashboard endpoint test) exercises the dispatch paths. `format_location` remains in `dashboard_server.py` (unused but untouched — out of scope). The `dashboard_pages.py` rendering surface is still server-rendered HTML parallel to React (relocating it was the structural win; a Mistglass visual redesign of those pages remains future work, explicitly out of scope for S-016).

## Next Batch

`16-storage-payload-and-query-perf` (S-017 + S-027). `assemble_summary_payload(db)` (`dashboard_server.py:1340`) is the dashboard-side seam to call the new storage assembly layer once `storage.py`'s catalog embedding is lifted.
