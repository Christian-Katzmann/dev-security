# Acceptance: 03-backend-read-path-resilience

## Acceptance Criteria

**S-003 — SQLite history store is self-healing, and recovery is surfaced everywhere it is read**
- Pointing `ObservatoryDB` at a garbage / non-database file no longer raises out of `__init__`: the corrupt file is renamed to `observatory.db.corrupt-<ts>` (preserved, never deleted), a fresh schema is rebuilt, and `recovered_from_corruption` / `quarantined_path` are set. `tests/test_storage_corruption.py` asserts this graceful quarantine+rebuild and passes.
- A transient `sqlite3.OperationalError` (e.g. DB locked, disk I/O) is **re-raised untouched**, not mistaken for corruption — a test or assertion proves a healthy-but-busy DB is never quarantined.
- The **MCP read path** surfaces the recovery state: a corrupted-then-rebuilt store yields a calm "history was corrupted and quarantined; previous data preserved at `<quarantined path>`" signal through `_open_db`/`_with_db` (it reads `recovered_from_corruption`/`quarantined_path`), not a silently-empty result that looks like "no scans yet." The behavior is pinned by a test.
- `.adx/recovery.md` contains a "history DB corrupted" recovery note describing the quarantine-and-rebuild path and where the preserved corrupt file lands (`grep -i corrupt .adx/recovery.md` is non-empty).

**S-006 — every `do_GET` route returns a clean JSON 500 on an unexpected exception**
- `do_GET` wraps its routing/handler body in `try/except Exception` → `send_json_error(500, ...)`, mirroring the `do_POST`/`do_DELETE` convention, so a GET-route exception (corrupt DB per S-003, or a `dashboard_payload` bug) becomes a structured JSON 500 rather than an unhandled `BaseHTTPRequestHandler` error or a dropped connection.
- A **GET-route-raises test** forces a `do_GET` route to throw (e.g. monkeypatch the payload builder to raise) and asserts the response is a clean JSON 500 with a body, not a traceback/dropped socket. Removing the wrapper makes this test fail.

**S-023 — corrupt `cases_json` rows degrade to a warning, never a crash**
- All six previously-unguarded `cases_json` reads (`storage.py:1417`, `:1587`, `:2841`, `:2855`, `:2903`, `:2904`) decode through the same `except (TypeError, json.JSONDecodeError)` skip-and-warn pattern already used at `storage.py:2226-2227` (ideally via one shared decode-or-warn helper, not six copy-pasted blocks).
- A test injects a non-JSON / corrupt `cases_json` row and asserts `dashboard_payload()` **still returns** (degraded, the bad row skipped/warned) instead of raising `JSONDecodeError`. The same holds for the MCP read that shares `cases_json`. Reverting any one guard to a bare `json.loads` makes this test fail.

**Read-path integrity (all three S-IDs)**
- Full `uv run pytest` stays green with **0 skipped / 0 xfail** introduced; the new/extended tests are present and passing; no existing test was weakened or re-pinned to make the suite pass.

## Required Checks

| Check | Why |
| --- | --- |
| `uv run pytest tests/test_storage_corruption.py -v` | Proves the S-003 quarantine+rebuild, the transient-`OperationalError` re-raise, and the MCP recovery-surfacing are pinned (matrix validation path for S-003). |
| `python3 -c "import json; assert 'corrupt' in open('.adx/recovery.md').read().lower(); print('recovery note ok')"` | Proves the S-003 "history DB corrupted" recovery note exists in `.adx/recovery.md`. |
| `uv run pytest -k "get and (500 or error or corrupt)" -v` (the GET-route-raises test) | Proves the S-006 `do_GET` wrapper returns a clean JSON 500 on a route exception (matrix validation path for S-006: "GET-route-raises test; probe `/api/summary` on corrupt DB"). |
| `uv run pytest -k "cases_json or corrupt_row or dashboard_payload" -v` | Proves the S-023 corrupt-`cases_json` row degrades and `dashboard_payload()` still returns (matrix validation path for S-023). |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check from AGENTS.md — confirms the storage/dashboard/MCP edits did not break package importability. |
| `uv run pytest -q` (full suite) | Confirms 0 skipped / 0 xfail introduced, the whole read-path-resilience change keeps the suite green, and no existing test regressed. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
