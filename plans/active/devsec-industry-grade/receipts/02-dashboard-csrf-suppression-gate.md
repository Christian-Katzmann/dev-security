# Implementation Receipt: 02-dashboard-csrf-suppression-gate

## Target

- Plan: `plans/active/devsec-industry-grade/health_matrix.md`
- Batch: 02-dashboard-csrf-suppression-gate
- Source report item(s): S-001 (CSRF/Origin-harden the dashboard's mutating loopback HTTP surface + re-arm the high/critical suppression gate)

## Before Health

S-001 = Yellow/Red. The dashboard's mutating loopback HTTP surface had **zero** CSRF/Origin/Sec-Fetch defense, and `read_json_body` accepted any `Content-Type`:

- `do_POST`/`do_DELETE` dispatched straight to handlers with no provenance check — a malicious page in a same-machine browser (classic CSRF or DNS rebinding) could forge POSTs to `/api/case-decision`, honey-insert, package install, scan reset, rotation trigger with no operator click.
- `save_case_decision` passed `human_authorized=True` **unconditionally** (rationale comment: "a direct dashboard click … is the human confirmation"), so a forged cross-origin POST could suppress a high/critical case — defeating the otherwise-correct server-side gate at `storage.set_case_decision` (`storage.py:2142-2147`). This is the Brief's non-negotiable "applies a high/critical suppression without explicit, audited human confirmation."
- Evidence re-verified against current files before editing: `grep -nE "Origin|Sec-Fetch"` on `dashboard_server.py` returned **only** the lens-cited zero matches (no guard); `human_authorized=True` confirmed hardcoded in `save_case_decision`. (Cited line numbers had drifted from earlier batches; trusted the code.)

## Changes Made

Root-cause fix on the one fix surface (the mutating loopback HTTP layer), in two layers:

**1. CSRF/Origin + Content-Type guard (`src/security_observatory/dashboard_server.py`)**
- Added `_origin_is_same_site()`: rejects a request whose `Sec-Fetch-Site` is not `same-origin`/`none`, or whose `Origin` is not the dashboard's own loopback origin (scheme `http`, host in `{127.0.0.1, localhost, ::1}`, port == server port). A foreign `Origin` is a browser tell the script cannot forge — this also defeats DNS rebinding (the rebound host is not loopback). Missing `Origin`/`Sec-Fetch-Site` (CLI/curl/tests) is allowed: a browser cannot omit `Origin` on a cross-origin request, so non-browser clients were never the CSRF threat.
- Added `_guard_mutation()` called at the top of **both** `do_POST` and `do_DELETE` before dispatch: cross-origin → clean JSON **403**; body-bearing POST that is not `application/json` → clean JSON **415**. `/api/honey/trigger` is **deliberately exempt** (`_CSRF_EXEMPT_PATHS`) so the honeytoken still beacons cross-origin.
- `read_json_body` now also requires `Content-Type: application/json` (defense-in-depth behind the dispatch guard).

**2. Re-armed suppression gate (decoupled `human_authorized` from "a POST arrived")**
- Added a per-process confirmation token `_DASHBOARD_CSRF_TOKEN`, handed out only on a same-origin read `GET /api/csrf-token` (a cross-site page cannot read that response under SOP).
- Added `_human_confirmation_present()` (constant-time compare of the `X-DevSec-Confirm` header against the token).
- `save_case_decision` now passes `human_authorized=self._human_confirmation_present()` instead of hardcoded `True`, and returns clean JSON errors (`send_json_error`) instead of HTML `send_error`. `storage.set_case_decision` is the **unchanged** sole server-side chokepoint.

**3. Frontend (`dashboard-ui/src/App.tsx`)** — fetches the token once (cached `getConfirmToken()`) and echoes `X-DevSec-Confirm` on the case-decision POST, so the real same-origin triage flow still suppresses high/critical cases. Rebuilt the bundle (`npm run build`) → tracked `src/security_observatory/dashboard/index.html` updated.

**4. Threat model (`docs/threat-model.md`)** — documented the loopback-browser cross-site / DNS-rebinding vector (new risk row 3a + boundary-2 note), which previously covered only LAN/reverse-proxy exposure.

**5. Tests** — new `tests/test_dashboard_csrf.py` (forged-cross-origin-403-cannot-suppress-critical, same-origin-with-token-succeeds, same-origin-without-token-cannot-suppress, missing-`application/json`-415, honey-trigger-exempt). Updated `tests/test_dashboard_case_followup.py` to carry the confirmation token on its critical suppression (it pinned the now-deliberately-changed old gate semantics).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/test_dashboard_csrf.py -v` | PASS | 5 passed — forged 403 + no suppression, same-origin+token suppresses, no-token blocked, 415, honey exempt |
| `uv run pytest tests/test_dashboard_case_followup.py tests/test_dashboard_reset_endpoints.py tests/test_dashboard_credentials_endpoints.py tests/test_dashboard_tool_install.py tests/test_honey_keys.py -q` | PASS | (run together with chokepoint suite below) no regression to legitimate same-origin flows |
| `uv run pytest tests/test_red_team_e2e.py tests/test_case_followup.py -q` | PASS | 29 passed, 1 skipped across this + dashboard suite — server-side gate + MCP write boundary intact and untouched |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.dashboard_server; print('ok')"` | PASS | prints `ok` |
| `uv run pytest` | PASS | 414 passed, 4 skipped — no collateral breakage |
| `grep -nE "Origin\|Sec-Fetch\|Content-Type" src/security_observatory/dashboard_server.py` | PASS | guard now present (`_origin_is_same_site`, `Sec-Fetch-Site`, `_guard_mutation` 415) where the lens found zero |
| `cd dashboard-ui && npm run lint` | PASS | `tsc --noEmit` clean |
| `cd dashboard-ui && npm run build` | PASS | vite build clean; bundle emitted to `src/security_observatory/dashboard/` |

## After Health

S-001 → **Green**. The non-negotiable breach is eliminated on the dashboard surface:
- A forged cross-origin `POST /api/case-decision` with `status=false_positive` against a critical case returns **403** and the case stays unsuppressed in storage (test-pinned).
- `human_authorized=True` is no longer inferred from POST arrival — it requires the same-origin-only confirmation token; a same-origin POST without the token cannot suppress a critical case (gate raises, test-pinned).
- A legitimate same-origin decision carrying the token still records (no triage regression; frontend wired + test-pinned).
- `/api/honey/trigger` stays exempt and still beacons cross-origin (test-pinned).
- `docs/threat-model.md` now documents the loopback-browser vector.

## Remaining Risk

- The confirmation token is per-server-process (rotates on restart) and assumes the single-operator, no-RBAC model — consistent with the documented threat model; not a residual to fix here.
- Only `/api/case-decision` requires the positive confirmation token today (it is the only gated-suppression write on the dashboard path). Other mutating endpoints rely on the Origin/Content-Type guard, which is the correct CSRF posture for them.
- The tracked `dashboard/index.html` points at the gitignored built `assets/` (pre-existing repo convention); a fresh clone must `npm run build` to materialize assets — unchanged by this batch.

## Next Batch

`03-backend-read-path-resilience` (S-003, S-006, S-023). NOTE: this batch shifted `dashboard_server.py` handler line numbers (~+80) and `App.tsx` (~+23); batches 03 and 04 context.md citations were surgically updated and carry a re-grep note. `storage.py` was not touched.
