# Batch: 02-dashboard-csrf-suppression-gate

## Purpose
The dashboard runs an unauthenticated, state-mutating HTTP server on `127.0.0.1` with no Origin / Sec-Fetch / CSRF defense, and `read_json_body` accepts any `Content-Type`. A malicious web page the operator visits in a same-machine browser can forge POSTs that drive `/api/case-decision`, honey-key insertion, package installs, scan resets, and rotation triggers — no human ever clicks. Worse, the dashboard suppression path passes `human_authorized=True` unconditionally on the premise that "a POST means a real human clicked," so a forged cross-origin request can suppress a high/critical case, defeating the otherwise-proven server-side suppression gate. This batch owns **S-001** and fixes both halves on one surface: the dashboard's mutating loopback HTTP layer.

## Source Evidence
- **S-001** — CSRF/Origin-harden the dashboard's mutating loopback HTTP surface, then re-arm the suppression gate by decoupling `human_authorized=True` from "a POST arrived" · evidence: `dashboard_server.py:4228` binds `127.0.0.1`; `do_POST`/`do_DELETE` mutating handlers at `dashboard_server.py:2392-2531` have zero Origin/Referer/Sec-Fetch/CSRF check; `read_json_body` at `dashboard_server.py:4089` accepts any Content-Type; `save_case_decision` at `dashboard_server.py:2916` calls `db.set_case_decision(..., human_authorized=True)` unconditionally (rationale comment lines 2914-2915); server-side gate chokepoint is correct at `storage.py:2082-2087`; honey-key trigger reachable via GET (`dashboard_server.py:2302`) and POST (`dashboard_server.py:2428`); MCP-side gate reference `_is_gated_suppression` at `case_followup.py:610` · synthesis row S-001, lens report `04-permission-boundary-health.initial.md` (Ranks 1-2, Top Repair Targets 1-2, Undocumented Surfaces #2-#3)

## Target
Move S-001 from Yellow/Red to Green.

## Dependencies
None — the matrix Dependencies column shows `—` for S-001. This is the only S-ID in the batch, so there is no same-batch ordering. Do the CSRF/Origin hardening first, then re-arm the suppression gate on top of it (the gate fix relies on the same request-validation surface).

## Non-Goals
- Do not attempt other batches' super-list items (this batch is S-001 only).
- Do not broaden this into a general cleanup of `dashboard_server.py` (the god-module split is S-016, batch 15).
- Do not make production, destructive, deploy, secret, or irreversible data changes without explicit approval.
- Do not add CSRF/Origin enforcement to the honey-key trigger callback (`/api/honey/trigger`): a honeytoken embedded in a URL must beacon on a cross-origin GET by design — hardening it breaks the decoy. Exempt it deliberately and explicitly.
- Do not change the existing server-side suppression chokepoint in `storage.set_case_decision` (`storage.py:2082-2087`); it is correct and test-pinned — only change what `human_authorized=True` attests to on the dashboard path.
- Do not touch the MCP/AI write boundary; it is already proven safe (Ranks 3-5) and is not the breach.

## Suggested Starting Steps
1. Re-read this context and acceptance.md.
2. Re-verify each S-ID's evidence against the exact files cited: confirm `do_POST`/`do_DELETE` mutating handlers (`dashboard_server.py:2392-2531`) and `read_json_body` (`:4089`) still lack Origin/Content-Type checks, and that `save_case_decision` (`:2916`) still passes `human_authorized=True` unconditionally.
3. Add a shared request-guard for mutating handlers: reject any `do_POST`/`do_DELETE` whose `Origin`/`Sec-Fetch-Site` is not same-origin (allow `null`/missing only for the operator's own browser-app context as appropriate) with a clean JSON 403, and require `Content-Type: application/json` in `read_json_body` for mutating handlers. Route every mutating endpoint through this guard; deliberately exempt `/api/honey/trigger`.
4. Re-arm the suppression gate: stop inferring human confirmation from request arrival. For high/critical suppressions, require a positive intent signal that survives CSRF hardening (e.g. a short-lived confirmation token minted into the served dashboard HTML and echoed by the action) so `human_authorized=True` is positively attested, not assumed; keep `storage.set_case_decision` as the sole server-side chokepoint.
5. Document the loopback-browser (CSRF / DNS-rebinding) vector in `docs/threat-model.md`, which today covers only LAN/reverse-proxy exposure.
6. Implement the smallest root-cause fix that satisfies every acceptance criterion; add `tests/test_dashboard_csrf.py` covering forged-cross-origin-rejected, same-origin-succeeds, missing-Content-Type-rejected, honey-trigger-exempt, and cannot-suppress-critical-via-forged-POST.
