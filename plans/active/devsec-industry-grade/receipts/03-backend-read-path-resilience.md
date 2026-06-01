# Implementation Receipt: 03-backend-read-path-resilience

## Target

- Plan: `plans/active/devsec-industry-grade/health_matrix.md`
- Batch: 03-backend-read-path-resilience
- Source report item(s): S-003 (self-healing SQLite store + surface recovery everywhere it is read), S-006 (`do_GET` returns a clean JSON 500 on any route exception), S-023 (guard the remaining `cases_json` JSON reads)

## Before Health

Re-verified each S-ID against the current files first (context.md warned line numbers had drifted and core work had partially landed — trusted the code):

- **S-003 (Yellow/Red)** — The store-open + quarantine + rebuild core was already landed and tested: `ObservatoryDB.__init__` catches `sqlite3.DatabaseError`, **re-raises** transient `OperationalError` untouched, and quarantines the corrupt file (`observatory.sqlite.corrupt-<ts>`, preserved, never deleted) via `_quarantine_corrupt_db`; `tests/test_storage_corruption.py` (5 tests) passed. The **dashboard** read path already surfaced recovery (`/api/summary` adds a `history_recovery` block). **Residuals confirmed:** the MCP read path (`_with_db`/`_open_db`) opened `ObservatoryDB` but never read `recovered_from_corruption`/`quarantined_path`, so a corrupted-then-rebuilt store returned a silently-empty "no scans yet" result; `.adx/recovery.md` had **no** corrupt-store note (`grep -ic corrupt` = 0).
- **S-006 (Yellow)** — The `do_GET` wrapper was already landed (`do_GET` wraps `_handle_get()` in `try/except Exception` → `send_json_error(500, ...)`, mirroring `do_POST`/`do_DELETE`). **Residual confirmed:** no GET-route-raises test pinned the behavior, so the asymmetry could silently return.
- **S-023 (Yellow)** — Fresh grep confirmed six unguarded `json.loads(... cases_json ...)` sites (storage.py 1417, 1587, 2841, 2855, 2903, 2904) against one guarded read (2226–2227). A hand-edited / truncated row would raise `JSONDecodeError` out of `dashboard_payload()` and the shared MCP read.

## Changes Made

Smallest root-cause fix on the one read-path surface (`storage.py` / `dashboard_server.py` / `mcp_server.py`); no module split (that is batch 15). Honored `.adx/risks.json` `local-security-data` — the corrupt file is preserved, never deleted; transient `OperationalError` is never treated as corruption.

**1. S-023 — single decode-or-warn helper (`src/security_observatory/storage.py`)**
- Added a module logger (`logging.getLogger("security_observatory.storage")`, mirroring `rotation.py`) and `_decode_cases(cases_json)`: decodes the column, and on `(TypeError, json.JSONDecodeError)` — or a value that decodes to a non-list — logs a warning and returns `[]`. Single source of truth.
- Applied `_decode_cases` at all six previously-unguarded sites **and** consolidated the one pre-existing guarded read (old 2226–2227 try/except) onto the same helper. No `json.loads(... cases_json ...)` site remains except inside the helper.

**2. S-003 residual — MCP read path surfaces recovery (`src/security_observatory/mcp_server.py`)**
- Added `HistoryRecoveredError(RuntimeError)`.
- `_with_db` now, after opening, checks `db.recovered_from_corruption` and raises `HistoryRecoveredError` with a calm message — "Your scan history could not be read and was quarantined; the previous database is preserved on this machine at `<redacted path>`. A fresh history was started — re-run a scan to repopulate it." — instead of running the action against an empty store. The quarantined path is run through `_redact_path` so it never leaks the operator's home prefix. FastMCP delivers this to the client as a `ToolError`, not a traceback or a silently-empty result.

**3. S-003 residual — recovery note (`.adx/recovery.md`)**
- Added a "History DB Corrupted" section describing the quarantine-and-rebuild path, where the preserved corrupt file lands, the sidecar-clear, the transient-`OperationalError` re-raise, and how it surfaces (dashboard `history_recovery` + MCP `HistoryRecoveredError`). `grep -i corrupt .adx/recovery.md` is now non-empty.

**4. Tests**
- `tests/test_storage_corruption.py`: added `test_corrupt_cases_json_row_degrades_dashboard_payload` (S-023 — injects a non-JSON `cases_json` row, asserts `dashboard_payload()` still returns and the repo is still present) and `test_mcp_read_path_surfaces_recovery` (S-003 — garbage DB → `create_server` → `call_tool("list_repos")` raises `ToolError` whose message contains "quarantined"/"preserved", corrupt file preserved on disk).
- New `tests/test_dashboard_get_resilience.py`: S-006 GET-route-raises test — monkeypatches `dashboard_payload` to raise, `GET /api/summary` returns a clean JSON **500** with an `error` body (loopback-bound server, `127.0.0.1`). Removing the `do_GET` wrapper makes it fail.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/test_storage_corruption.py -v` | PASS | 7 passed — quarantine+rebuild, transient-`OperationalError` re-raise, cases_json degrade, **MCP recovery-surfacing** all pinned |
| `python3 -c "...assert 'corrupt' in open('.adx/recovery.md').read().lower()..."` | PASS | prints `recovery note ok` |
| `uv run pytest -k "get and (500 or error or corrupt)" -v` | PASS | 1 passed — `do_GET` route exception → clean JSON 500 |
| `uv run pytest -k "cases_json or corrupt_row or dashboard_payload" -v` | PASS | 3 passed — corrupt `cases_json` degrades, `dashboard_payload()` still returns |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli; print('ok')"` | PASS | prints `ok` |
| `uv run pytest -q` (full suite) | PASS | **480 passed, 0 skipped** (after `uv sync --extra mcp`; see note) |

## After Health

- **S-003 → Green.** Corrupt store quarantines + rebuilds (preserved, never deleted); transient `OperationalError` re-raised untouched; recovery now surfaces in **both** read paths — dashboard `history_recovery` block (pre-existing) and MCP `HistoryRecoveredError` (new), so a rebuilt store never reads as "no scans yet"; `.adx/recovery.md` documents the path. All test-pinned.
- **S-006 → Green.** `do_GET` clean-JSON-500 wrapper confirmed present and now pinned by a GET-route-raises test; the symmetry with `do_POST`/`do_DELETE` cannot silently regress.
- **S-023 → Green.** All six `cases_json` reads (plus the previously-lone guarded one) route through `_decode_cases`; a corrupt row degrades to a warning and an empty case list; `dashboard_payload()` and the shared MCP read still return. Test-pinned; reverting any guard to a bare `json.loads` fails the test.

## Remaining Risk

- **Environment note (not a code residual):** this runner had only a partial top-level `mcp` package (no `mcp.server`), so the MCP-dependent suite — including the new `test_mcp_read_path_surfaces_recovery` — skipped under `pytest.importorskip("mcp")`, the repo's established convention for the optional `mcp` extra. I ran `uv sync --extra mcp` (installed the SDK into the gitignored `.venv` only — **no** tracked `pyproject.toml`/`uv.lock` changes) and re-ran: the MCP recovery test and the whole suite pass with **0 skipped (480 passed)**. Permanently un-skipping these by pinning `mcp` into the dev group is S-025's job (batch 05) — its context.md was surgically updated to add this new `importorskip` site to its enumeration.
- `HistoryRecoveredError` is raised for every MCP tool call while a freshly-recovered store is open, which is the intended calm signal (consistent with the existing `RepoNotFoundError` pattern), not silent emptiness.

## Next Batch

`04-dashboard-error-surfacing` (React-layer surfacing of backend errors). It explicitly defers the `do_GET` wrapper and self-healing SQLite path to this batch (03) — no line-number citations to update there. `05-trust-integrity-tests` (S-025) context.md was updated to note `test_storage_corruption.py` now also carries a `pytest.importorskip("mcp")` site. `storage.py` line numbers shifted ~+30 (logger + `_decode_cases` helper near the top); no other batch cites absolute `storage.py` line numbers in a way that broke.
