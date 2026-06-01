# Implementation Receipt: 18-type-floor-and-contracts

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 18-type-floor-and-contracts
- Source report item(s): S-021 (TS strict floor), S-022 (case-write contracts), S-026 (versioned migrations)

## Before Health

- `dashboard-ui/tsconfig.json` had no strict family (`skipLibCheck`/`noEmit` only); the careful `?`/`| null` annotations were decorative — `tsc --noEmit` passed on a lax floor. Zero `any`/`@ts-ignore` baseline (real discipline, low floor).
- Frontend `SecurityCase` type (`dashboardData.ts`) declared ~17 drifted aliases the backend never emits (`plain_title`, `summary`, `why_matters`/`why_it_matters`, `affected_path`/`path`/`file`/`line`, `next_step`, `bucket`/`action_bucket`, `source_scanners`/`scanner`, `remediation`, `raw_report_url`/`ai_prompt_url`, `id`).
- `save_scan` (`storage.py`) accepted `list[SecurityCase] | list[dict]` and persisted raw dicts via `dict(case)`, bypassing `SecurityCase.__post_init__` redaction + action_level/confidence whitelist.
- No `user_version`; the destructive `_migrate_resolution_status_constraints` rebuild was gated by a fragile `select sql from sqlite_master` substring sentinel.

## Changes Made

**S-021 — TS strict (do first):**
- `dashboard-ui/tsconfig.json`: added `"strict": true`.
- Fixed the 2 surfaced errors at the root (no casts/ignores): `formatDuration` now accepts `string | null` (wire shape's `finished_at` is nullable; the existing falsy guard already handled it); `Toolbar.searchInputRef` prop typed `RefObject<HTMLInputElement | null>` to match React 19's `useRef<T>(null)`.

**S-022 — case-write contracts:**
- Trimmed frontend `SecurityCase` to the real wire shape (dataclass fields + documented server-injected fields). Removed all dead aliases and pruned their now-unreachable fallbacks in `caseToDisplayCase`, `caseLocation`, `caseSources`; removed dead `rawReportUrl`/`aiPromptUrl` from `DisplayCase`. Strict TS confirmed nothing live was dropped (it also caught + fixed dead-alias use in `components/ScanHistoryTrendsPanel.tsx`).
- `save_scan` (`storage.py`): every dict input is now rebuilt through `SecurityCase(**case)` before persistence, so redaction/whitelist can never be bypassed regardless of typed-vs-dict input.

**S-026 — versioned migrations:**
- Added `SCHEMA_USER_VERSION = 1` + a documented migration ledger.
- `_connect_and_initialize` detects a fresh DB (no tables) and stamps it straight to current; otherwise `_run_schema_migrations(fresh=...)` reads `PRAGMA user_version` and runs each numbered step only when below it, then bumps the version.
- The two destructive rebuilds are now gated on the version bump (string-sentinel skip removed); additive `_ensure_columns` column-diffs kept as version-independent.

**Tests:**
- `tests/test_cases.py`: new `test_save_scan_redacts_token_for_typed_and_dict_cases` (token redacted in persisted `cases_json` for both typed + dict; invalid dict action_level normalized).
- `tests/test_storage_migrations.py` (new): old-shape fixture migrates to current `user_version` with rows intact; reopen is idempotent (patched rebuild proves the version gate, not a sentinel, prevents re-rebuild); fresh DB stamped to current.
- Converted dict-passing `save_scan` callers to typed cases: `test_scan_diff.py`, `test_dashboard_scan_diff_endpoint.py`, `test_dashboard_payload_assembly.py` (`_case`/`_dependency_case`/`_secrets_case`).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `cd dashboard-ui && npm run lint` (tsc --noEmit, strict on) | PASS | 0 errors under strict |
| `cd dashboard-ui && npm run build` | PASS | vite build ok (pre-existing chunk-size warning only) |
| `cd dashboard-ui && npm test` | PASS | 22 passed |
| `grep -E '"strict"' dashboard-ui/tsconfig.json` | PASS | `"strict": true` |
| `grep plain_title\|why_matters\|action_bucket\|affected_path dashboard-ui/src/dashboardData.ts` | PASS | none (aliases removed) |
| `uv run pytest tests/test_cases.py` | PASS | incl. new redaction test |
| `uv run pytest tests/test_severity_gate.py tests/test_red_team_e2e.py` | PASS | trust paths / "Unsafe AI write" preserved |
| `python3 -c "import security_observatory.cli"` | PASS | import ok |
| `uv run pytest` (full) | PASS | 524 passed incl. new migration round-trip |
| `grep user_version src/security_observatory/storage.py` | PASS | pragma read + written |

## After Health

S-021, S-022, S-026 → Green. Strict mode enforces the existing null-safety discipline (still zero `any`/`@ts-ignore`); the frontend type matches the real wire contract; `save_scan` redaction is unbypassable; schema migrations are versioned by `PRAGMA user_version` and idempotent.

## Remaining Risk

- The optional typed runtime guard at the 3 `await response.json()` boundaries was not added (acceptance marked it optional; strict static typing now covers the in-code paths). Low risk; could be a future hardening.
- `save_scan` still accepts dicts at runtime (defensively coerced); production callers already pass typed cases.

## Next Batch

19-adx-and-docs-truth (no dependency on this batch; batches 19–21 reviewed — none reference the type floor, case contract, or migration changes, so no downstream context/acceptance edits were needed).
