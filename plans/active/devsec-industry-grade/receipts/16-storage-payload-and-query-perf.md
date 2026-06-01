# Implementation Receipt: 16-storage-payload-and-query-perf

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 16-storage-payload-and-query-perf
- Source report item(s): S-017 (architecture — payload assembly lifted out of `storage`, persistence→scanner import inversion removed), S-027 (performance — per-repo fan-out batched, `case_resolution_items` N+1 eliminated)

## Before Health

- `storage.py` imported scanner-orchestration catalogs for UI payload construction: `from .scanners import scan_profile_catalog, scanner_catalog, security_pack_catalog, tool_catalog` (was `storage.py:41`) — the persistence→scanner import inversion.
- `ObservatoryDB.dashboard_payload()` (was `storage.py:1467`) owned the entire `/api/summary` assembly: catalog embedding with install-state detection, per-repo scan deltas, suppression assembly, dependency-risk movements, recovery inputs.
- The per-repo loop ran ~12–18 individual queries **per repo**: `_previous_scan`, a 5-query `_dependency_delta` (sbom×2, manifest×2, dependency-findings), a per-scan `findings` select, `list_dependency_trust_enrichments`, `latest_platform_posture_snapshot`, and `list_case_resolution_runs(limit=5)` — the last running a nested `case_resolution_items where run_id = ?` query **per run** (N+1). Total round-trips grew linearly with repo count.

## Changes Made

**S-017 — assembly lifted out, import inversion removed**
- New module `src/security_observatory/dashboard_payload.py` with `assemble_dashboard_payload(db)`. It owns the catalog embedding (`scanner_catalog`/`tool_catalog`/`security_pack_catalog`/`scan_profile_catalog`, imported from `.scanners` — the correct layering direction) and all per-repo UI enrichment. The pure assembly helpers (`_scan_delta`, `_dependency_delta`, risk-movement, suppression, counts, honey-event helpers) are imported from `storage` (they are module functions, never class methods, and carry no scanner dependency).
- `storage.py`: removed the `from .scanners import …` catalog line and the now-unused `suppression_counts` import. `ObservatoryDB.dashboard_payload()` is now a thin delegate to `assemble_dashboard_payload(self)` (lazy import, no import cycle). `storage` owns schema + queries only; `grep -n "from .scanners import" src/security_observatory/storage.py` returns nothing.
- The dashboard server seam is unchanged — `assemble_summary_payload` still calls `db.dashboard_payload()`, which now routes through the lifted layer. All other callers (`case_followup.py`, tests, MCP read path) keep the same public API.

**S-027 — set-based batching, N+1 collapsed**
- Added set-based query methods to `storage` (persistence owns the queries): `latest_scans()`, `recent_scan_history()`, `previous_scans_for_latest()` (one window query, resolved in memory), `findings_for_scans()`, `sbom_components_for_scans()`, `dependency_manifest_entries_for_scans()`, `dependency_trust_for_scans()` (all via `_rows_by_scan` — one `where scan_id in (...)` query each), `platform_posture_for_scans()`, and `case_resolution_runs_for_dashboard()`.
- `case_resolution_runs_for_dashboard()` pulls the global top-50 and the per-repo top-5 (window function) and fetches **all** their items in a single `where run_id in (...)` query — collapsing both the per-repo run lookups and the per-run `case_resolution_items` N+1.
- The assembly layer pulls each data kind once, keyed on the scan-id / repo-name set, and joins in memory. Current dependency findings are derived from the already-batched findings list (consumers build sets, so order-independent), avoiding an extra query.
- Output is byte-for-byte identical: no `/api/summary` field, nesting, ordering, or value changed.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "...import security_observatory.cli; print('ok')"` | ✅ ok | Fast import check — new module + storage lift import cleanly, no cycle. |
| `uv run python -c "import security_observatory.storage; print('ok')"` | ✅ ok | Storage imports under uv after catalog-import removal — inversion is gone, not bypassed. |
| `grep -n "from .scanners import" src/security_observatory/storage.py` | ✅ NONE | Persistence→scanner import inversion removed at the source. |
| `uv run pytest` (full suite) | ✅ 518 passed | 516 pre-existing (deep-check payload across sbom/cases/honey/vex/posture/trust/drift) + 2 new. Payload-shape contract holds. |
| New: query-count trace, N=5 vs N=50 vs N=200 | ✅ pass | **25 statements at every N** (O(1) in repo count); exactly **1** `case_resolution_items` query, **1** `findings` query. |
| New: batched payload deep-equals un-batched assembly | ✅ pass | Same DB assembled twice — real (batched) vs reference proxy using the untouched per-repo `list_*`/`_previous_scan` helpers — deep-equal on a 3-repo, multi-scan, content-rich fixture (trust, posture, cases+decision, resolution runs). |

## After Health

- S-017: catalog embedding and per-repo UI assembly live in `dashboard_payload.py`; `storage` owns schema + queries only and carries no scanner-orchestration import. Green.
- S-027: dashboard query count is fixed at 25 regardless of repo count; the per-run `case_resolution_items` N+1 is a single batched pull. Green.
- Honey-event pruning (`prune_honey_key_events`) stays on the dashboard path with unchanged retention behavior (per Non-Goals — its relocation is a separate perf call, not in scope here).

## Remaining Risk

- The set-based reads use a single `IN (...)` per data kind without parameter-chunking. SQLite's bound-variable limit is 32766 (3.47.1 here), comfortably above realistic repo/scan counts; only a deployment with tens of thousands of repos in one payload would need chunking, which would keep the count effectively O(1) anyway.
- `previous_scans_for_latest` resolves the previous scan from the two newest per repo; a repo whose two newest scans share an identical `started_at` is the same tie `_previous_scan` already resolved arbitrarily (real scans use distinct timestamps). Behavior matches the pre-refactor code for all well-formed data.

## Next Batch

17-scanner-adapter-registry (S-018). No downstream context edits were required: batch 17 targets scanner **adapters** in `scanners.py` (not the catalog functions relocated here), and batch 18 targets `save_scan`'s cases handling and schema/migrations — none of which this batch touched. Batches 17–21 re-verify live line numbers per their own steps; the only drift introduced here is ~2 lines (two removed imports) plus the added batch-query methods after `save_scan`.
