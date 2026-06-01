# Dashboard Payload

Primary source path: `src/security_observatory/dashboard_payload.py`

This module assembles the dashboard UI payload — the `/api/summary` body. It
turns raw `storage` rows into the per-repo UI shape and embeds the live
scanner/tool/pack catalogs. It was lifted out of `ObservatoryDB`: persistence
owns the schema and the queries, this higher layer owns the cross-layer
assembly, which removes the persistence → scanner-orchestration import
inversion. The per-repo fan-out is replaced by set-based batch reads
(one `scan_id IN (...)` / `run_id IN (...)` query per data kind, joined in
memory), so the query count is O(1) in repo count. The output dict is
byte-for-byte identical to the pre-split payload.

`enrich_repos_with_rotation(payload)` also lives here: it reads each repo's
on-disk rotation state (`rotation`) and folds `rotation_state` plus inferred
`inferred_secret_name` (`rotation_inference`) into the per-repo payload. It was
lifted out of `dashboard_server` so the route stays a thin seam; the server
calls it after `assemble_dashboard_payload`. `rotation_inference` stays a pure,
I/O-free guesser that this loop drives.

Verification:

- Start with `python-import-cli`.
- Run `python-pytest`; `tests/test_dashboard_payload_assembly.py` is the assembly seam's test.

Risks:

- The payload exposes local scan output; treat it as `local-security-data` (see `.adx/risks.json`).
