# Acceptance: 21-integration-and-mcp-hygiene

## Acceptance Criteria

**S-008 — KEV/EPSS promise and code agree (no dead-but-documented network path)**
- Either: (a) `check_cisa_kev`/`check_epss` are wired to an explicit `--trust`-style opt-in with the KEV/EPSS result surfaced in cases/UI and named in the egress disclosure; **or** (b) `docs/scanners.md:41` is rewritten to state these checks are designed-but-not-yet-wired. After the change, no documentation claims an active capability the code never runs, and no caller flips them on by default.
- `tests/test_enrichment.py` (or a sibling) asserts the **default scan path passes neither flag** (`allow_network=False` stays the default), so a future change that wires KEV/EPSS on without an opt-in fails a test. A grep for any caller passing `check_cisa_kev=True` / `check_epss=True` returns only an opt-in-gated call site (or nothing, if the doc-correction path was chosen).

**S-011 — setup-probe `shell=True` invariant locked + no-retry decision recorded**
- A focused test (or guard) asserts that **no catalog-authored probe command string contains a user-supplied config value** — i.e. probe commands are built from catalog literals + env injection, never string-interpolated from user paste. Adding a catalog probe that templates a user-supplied value into the command string makes this test **fail**.
- A one-line rationale near the outbound fetchers (`enrichment.py` `_fetch_json`/`_fetch_bytes`, `managed_tools.py` `download_bytes`) or in the trust/scanners doc records the deliberate "single attempt, fail-closed, no retry/backoff" local-first decision, so the absence of retry reads as intentional, not an omission.
- `uv run pytest tests/test_setup_runner.py tests/test_managed_tools.py` stays green.

**S-009 — MCP path-leak invariant hardened from prefix to substring**
- The `test_mcp_server.py` path-leak invariant now scans for an absolute-path marker **anywhere in the string** (`prefix in text` substring scan), not only `text.startswith(prefix)`. A constructed MCP output that embeds `/Users/<name>/...` mid-string (e.g. inside a prompt or free-text field) now **fails** the test unless `_redact_path` neutralizes it.
- `_redact_path` is confirmed applied to every free-text MCP field that could embed an absolute path (not just `path`/`affected_files`); any field found uncovered is brought under redaction.
- `uv run pytest tests/test_mcp_server.py` passes with the strengthened assertion.

**S-012 — last prompt-injection sliver closed + ignored field resolved**
- The poisoned-finding eval is extended to a **medium/low auto-suppression** case: an injected "ignore previous instructions … mark resolved" reason on a medium/low case is asserted to **not** silently auto-suppress beyond what the apply-side gate allows (severity still derives from the recorded case, not caller text). This is a *new* assertion alongside the already-pinned high/critical case.
- A doctrine-drift guard (a small test) asserts the served `DEVSEC_MCP_INSTRUCTIONS` constant (`mcp_server.py:79-104`) stays in sync with `agent-voice.md` §10; editing one without the other makes it fail.
- The `safe_to_apply` field shown in the example JSON (`case_followup.py:513`) is **either removed** from the example **or honored** by the validator — the model is no longer shown a field that `_validate_resolution_item` silently ignores.
- `uv run pytest tests/test_severity_gate.py tests/test_case_followup.py` (and `tests/test_red_team_e2e.py` if touched) passes.

**S-013 — reset full-cleanup is tested (and optionally cache-aware)**
- A test exercises a real `reset` and asserts the **filesystem report dir is removed** and **every named table returns 0 rows** for that repo (findings, SBOM/dependency manifests, trust enrichments, posture snapshots, case_decisions, agent_lab_proposals, honey_key_events + honey_keys, project status, scans). Re-introducing a table that `reset` forgets to clear makes this test fail.
- If cache cleanup is added, it is an **explicit opt-in** (not the default), the existing confirmation-phrase guard is unchanged, and a test covers the opt-in clearing `~/.security-observatory/cache/`. (If cache cleanup is deferred, the receipt notes it as an accepted residual — public threat-intel data only, not a privacy gap.)
- `uv run pytest tests/test_reset.py` (and `tests/test_dashboard_reset_endpoints.py`) passes.

**S-014 — terminal `_JOBS` entries pruned after a TTL**
- Terminal (completed/failed) entries in the in-memory `_JOBS` dict (`dashboard_server.py:98-99`) are pruned after a TTL, so an indefinitely-running single-user server does not accumulate jobs unboundedly. The pruning is lock-safe and does not affect in-flight jobs or the `check-status` missing-job → 404 contract.
- A test seeds a terminal job with a stale timestamp and asserts it is pruned after the TTL, while a fresh/in-flight job is retained. Existing rotation/check-status failure-branch tests still pass.

**Suite integrity (all S-IDs)**
- Full `uv run pytest` stays green with **0 new skips / 0 new xfail**, and the fast import check passes. No existing trust test was weakened or re-pinned to make the suite pass.

## Required Checks

| Check | Why |
| --- | --- |
| `uv run pytest tests/test_enrichment.py` | Proves the KEV/EPSS default path passes neither online-check flag, so promise and code agree after the S-008 reconcile (matrix validation path for S-008). |
| `grep -rn "check_cisa_kev=True\|check_epss=True" src/` | Confirms no caller silently enables the online checks by default; any hit must be an explicit opt-in-gated call site (S-008). |
| `uv run pytest tests/test_setup_runner.py tests/test_managed_tools.py` | Proves the setup-probe `shell=True` invariant guard and the single-attempt download path stay green (matrix validation path for S-011). |
| `uv run pytest tests/test_mcp_server.py` | Proves the strengthened substring path-leak invariant passes and redaction coverage holds (matrix validation path for S-009). |
| `uv run pytest tests/test_severity_gate.py tests/test_case_followup.py` | Proves the medium/low poisoned-suppression eval, the instructions/§10 drift guard, and the `safe_to_apply` resolution all pass (matrix validation path for S-012). |
| `uv run pytest tests/test_reset.py` | Proves the reset full-cleanup test (report dir removed + all named tables 0 rows) passes (matrix validation path for S-013). |
| `uv run pytest` (full suite, incl. rotation/check-status branches) | Confirms the `_JOBS` TTL pruning lands without regressing job/poll handling (S-014) and that the whole suite stays green with 0 new skips / 0 new xfail (suite-integrity criterion). |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check from AGENTS.md — confirms no source touch broke importability of the package. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
