# Batch: 15-split-dashboard-server

## Purpose
`dashboard_server.py` is a 4,263-line god module: one `DashboardHandler` class whose `do_GET`/`do_POST`/`do_DELETE` are giant if/elif dispatchers that also run business logic inline, plus two full server-rendered HTML+CSS pages (`/report/` export and the `/docs/` shell) embedded as f-strings — a second, largely untested rendering surface that drifts from the React Mistglass design system. This batch fixes the single super-list item **S-016**: give the HTTP layer a real route table, move the inline HTML pages into their own template module(s) (or render from the React build), and lift the per-repo enrichment out of the request handler — so the most-edited backend file becomes legible and a new endpoint or report page is a one-seam change. The shared fix surface is the `dashboard_server.py` HTTP/routing seam (the god module flagged by the architecture, ai-maintainability, and performance lenses).

## Source Evidence
- **S-016** — Split `dashboard_server.py`: introduce a route table for `do_GET`/`do_POST`/`do_DELETE`, move the two inline server-rendered HTML pages into template module(s) or render from the React build, and lift per-repo enrichment out of the request handler · evidence: single `DashboardHandler` class at `src/security_observatory/dashboard_server.py:2028`; if/elif dispatchers at `do_GET`/`_handle_get` (`:2107`/`:2117`), `do_POST` (`:2419`), `do_DELETE` (`:2545`); two inline `<!doctype html>` + `<style>` pages — the `/report/` export page (`report_page`/`prompt_report_page`/`raw_report_page` at `:1146`/`:1152`/`:1211`, anchor f-string at `:1243`) and the docs shell (`_docs_page_shell` at `:1511`, anchor f-string at `:1515`); the `cli↔dashboard` cycle's lazy import was `from .cli import scan_repo` at `:1844` — **batch 14 (S-015) has since landed**, so this is now a clean top-level `from .scan_orchestrator import scan_repo` and the cycle is already gone (re-verify line numbers against the current file; they have shifted slightly) · synthesis row S-016, lens report 02-architecture-health.initial.md (Rank 1 + "Undocumented Or Hidden Surfaces": two server-rendered HTML pages parallel to the React UI).

## Target
Move S-016 from Yellow/Red to Green.

## Dependencies
S-003 and S-006 (both batch 03, `03-backend-read-path-resilience`) — already landed: `do_GET` now wraps everything in a `try/except → send_json_error(500)` and delegates to `_handle_get` (`:2107`–`:2117`), and `ObservatoryDB` self-heals corruption. Build the route-table extraction **on top of** that existing GET error backstop — preserve the calm-JSON-500 envelope and the self-heal guard; do not regress them while moving routing into a dispatch map. This batch (15) sequences after batch 14 (`14-scan-orchestrator-extract`, S-015), which has **landed**: `scan_repo` now lives in `src/security_observatory/scan_orchestrator.py`, the old `:1844` lazy `from .cli import scan_repo` is gone (replaced by a top-level `from .scan_orchestrator import scan_repo` in the dashboard_server import block), and the `cli↔dashboard` cycle is already broken. When you split the handler, import `scan_repo` from `scan_orchestrator`, never from `cli` — do not reintroduce the cycle.

## Non-Goals
- Do not attempt other batches' super-list items (storage payload lift S-017, scanner registry S-018, type floor S-021 are separate batches).
- Do not broaden this into a general cleanup.
- Do not make production, destructive, deploy, secret, or irreversible data changes without explicit approval.
- Do not change any endpoint's path, request/response shape, status codes, or auth/CSRF behavior — this is a pure structural split. The S-001 Origin/CSRF guards and the S-006 GET error envelope must behave identically after the refactor.
- Do not redesign the report/docs HTML or restyle it to Mistglass here; relocating the inline pages into template module(s) (or rendering from the React build) is the structural win — visual redesign of those pages is out of scope.
- Do not start the dashboard server, run scans, or fire any Honey-Key/process-kill path to "verify" (`.adx/risks.json`); prove behavior via the import check and `uv run pytest` dashboard endpoint tests.

## Suggested Starting Steps
1. Re-read this context and acceptance.md.
2. Re-verify S-016's evidence against the exact lines: confirm `DashboardHandler` at `:2028`, the three `do_*` dispatchers, the two inline HTML pages (`report_page` family near `:1146`–`:1243`, `_docs_page_shell` near `:1511`–`:1515`), and the `:1844` lazy `cli`/orchestrator import. Note that the S-006 GET error backstop (`do_GET` → `_handle_get`) is already in place and must be preserved.
3. Introduce an explicit route table (a method/path → handler mapping) so `do_GET`/`do_POST`/`do_DELETE` dispatch through one declarative map instead of long if/elif chains, keeping the existing top-level error envelope around each verb.
4. Move the two server-rendered HTML pages (`report_page`/`prompt_report_page`/`raw_report_page` and `_docs_page_shell`) into a dedicated template module (e.g. `dashboard_pages.py`/`templates.py`), imported by the handler; lift the inline per-repo enrichment currently inside the GET request path into a named payload/assembly helper.
5. Implement the smallest root-cause split that satisfies every acceptance criterion with no behavior change; run the fast import check and `uv run pytest` (dashboard endpoint tests) after each extraction to keep the suite green; add/adjust tests only where the move introduces real regression risk.
