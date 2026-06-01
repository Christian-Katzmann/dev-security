# Acceptance: 02-dashboard-csrf-suppression-gate

## Acceptance Criteria
- **S-001 (CSRF/Origin defense):** Every mutating dashboard handler (`do_POST`/`do_DELETE` at `dashboard_server.py:2392-2531` — at minimum `/api/case-decision`, `/api/honey/insert`, `/api/tools/install-via-pkg`, `/api/managed-tools/(un)install`, `/api/reset/scan-results`, `/api/rotation/trigger/*`, `/api/run-check`) rejects a request whose `Origin`/`Sec-Fetch-Site` is not same-origin with a clean JSON `403`; a same-origin request with the correct signal still succeeds.
- **S-001 (Content-Type requirement):** `read_json_body` (`dashboard_server.py:4089`) rejects a mutating request that does not carry `Content-Type: application/json` (returns a clean JSON error, not a parse crash); a request with the correct Content-Type is accepted.
- **S-001 (honey-trigger exemption):** `/api/honey/trigger` (GET `dashboard_server.py:2302` / POST `:2428`) is deliberately exempt from the cross-origin/CSRF guard and still beacons cross-origin, so the decoy is not broken; this exemption is asserted by a test.
- **S-001 (suppression-gate breach eliminated — non-negotiable):** A forged cross-origin `POST /api/case-decision` with `status=false_positive` against a high/critical case returns `403` and does **not** suppress the case (the case remains unsuppressed in storage). `human_authorized=True` is no longer set merely because a POST arrived — the dashboard path now requires a positive, CSRF-surviving intent signal for high/critical suppression, while `storage.set_case_decision` (`storage.py:2082-2087`) stays the unchanged server-side chokepoint. The Brief's non-negotiable "applies a high/critical suppression without explicit, audited human confirmation" is demonstrably eliminated on the dashboard surface.
- **S-001 (same-origin still works end-to-end):** A legitimate same-origin case decision carrying the valid intent signal still records the decision (no regression to the real triage flow).
- **S-001 (threat-model honesty):** `docs/threat-model.md` documents the loopback-browser cross-site / DNS-rebinding vector against the `127.0.0.1` listener, where today it covers only LAN/reverse-proxy exposure.

## Required Checks
| Check | Why |
| --- | --- |
| `uv run pytest tests/test_dashboard_csrf.py -v` | New suite: proves forged cross-origin `/api/case-decision` returns 403 and cannot suppress a critical case, same-origin succeeds, missing Content-Type rejected, and the honey-trigger callback stays exempt. Directly evidences the non-negotiable breach is eliminated. |
| `uv run pytest tests/test_dashboard_case_followup.py tests/test_dashboard_reset_endpoints.py tests/test_dashboard_credentials_endpoints.py tests/test_dashboard_tool_install.py tests/test_honey_keys.py -q` | Re-runs the existing dashboard endpoint suite to prove the new guard did not regress legitimate same-origin mutating flows (case decisions, reset, credentials, tool install, honey keys). |
| `uv run pytest tests/test_red_team_e2e.py tests/test_case_followup.py -q` | Confirms the server-side suppression chokepoint and MCP write boundary remain intact and untouched (the gate that must stay the sole chokepoint). |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.dashboard_server; print('ok')"` | Fast import check per AGENTS.md that the edited `dashboard_server.py` still imports cleanly. |
| `uv run pytest` | Full Python suite green per AGENTS.md verification rules — no collateral breakage. |
| `grep -nE "Origin|Sec-Fetch|Content-Type" src/security_observatory/dashboard_server.py` | Evidence the cross-origin/Content-Type guard now exists where the lens report found zero matches. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
