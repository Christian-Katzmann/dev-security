# Acceptance: 16-storage-payload-and-query-perf

## Acceptance Criteria
- **S-017 (payload assembly lifted out of `storage`):** The UI-payload assembly — scanner/tool/pack catalog embedding, per-repo scan deltas, suppression assembly, dependency-risk movements, recovery inputs — no longer lives inside the `ObservatoryDB` class in `src/security_observatory/storage.py`. It is moved into a dedicated payload-assembly/service module that consumes raw rows from `storage`. `storage` owns schema + queries only.
- **S-017 (persistence→scanner import inversion removed):** `storage.py` no longer imports scanner-orchestration catalogs for payload construction. `grep -n "from .scanners import" src/security_observatory/storage.py` no longer returns the `scan_profile_catalog, scanner_catalog, security_pack_catalog, tool_catalog` line (currently at `:39`); the catalog embedding (`scanner_catalog()` `:1566`, `scan_profile_catalog(...)` `:1569`) now happens in the lifted assembly layer, not in the DB module.
- **S-027 (per-repo fan-out batched):** The per-repo loop's ~12–18 individual lookups (previous-scan, the 5-query dependency delta, per-scan findings, trust, posture, resolution runs) are replaced by set-based pulls keyed on `scan_id IN (...)` (and `run_id IN (...)` where applicable), assembled in memory. A pytest using a `sqlite3` trace callback over a fixture seeded with N repos (e.g. N=5 vs N=50) asserts the query count does **not** grow linearly with repo count — it is O(1) in repo count (a fixed number of set-based queries, not per-repo).
- **S-027 (`case_resolution_items` N+1 eliminated):** The nested per-run `case_resolution_items where run_id = ?` query inside `list_case_resolution_runs` (called once per repo in the old loop) is collapsed into a single `... where run_id IN (...)` pull for all runs in the payload. The trace test confirms exactly one (not one-per-run) items query on the dashboard path.
- **S-017 + S-027 (no payload-shape change):** `/api/summary`'s payload — every field name, nesting, ordering, and value — is identical before and after on the same data. A pytest asserts the assembled payload dict is equal (deep-equal) to the pre-refactor output for a multi-repo, multi-scan fixture, so the React dashboard and the MCP read path see no change. The full `uv run pytest` suite passes unchanged and the fast import check is green.

## Required Checks
| Check | Why |
| --- | --- |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check per AGENTS.md; proves the storage lift + new assembly module import cleanly and didn't introduce an import error or reintroduce a cycle. |
| `uv run python -c "import security_observatory.storage; print('ok')"` | Confirms `storage` imports under the uv env after the catalog-import removal — proves the persistence→scanner inversion is actually gone, not just bypassed. |
| `grep -n "from .scanners import" src/security_observatory/storage.py` no longer returns the `scan_profile_catalog, scanner_catalog, security_pack_catalog, tool_catalog` line | Direct evidence the persistence→scanner-orchestration import inversion (S-017) is removed at the source. |
| `uv run pytest` (full suite, dashboard/storage tests included) | Proves the payload-shape contract holds — no endpoint or shared read changed shape, status, or values; the structural lift and query batching are behavior-preserving. |
| New pytest: sqlite3 trace over a fixture seeded with N=5 and N=50 repos asserting `dashboard_payload` query count is O(1) in repo count (and exactly one `case_resolution_items` query) | The synthesis "Suggested validation" for S-027; proves the N+1 fan-out is genuinely batched, not merely reorganized. |
| New pytest: assembled payload deep-equals the pre-refactor output on a multi-repo, multi-scan fixture | Proves S-017 + S-027 produce byte-for-byte the same `/api/summary` payload, protecting the React + MCP consumers. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
