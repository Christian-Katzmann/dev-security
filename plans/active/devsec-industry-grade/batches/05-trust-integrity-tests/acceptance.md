# Acceptance: 05-trust-integrity-tests

## Acceptance Criteria

**S-024 — dropped-findings invariant is tested**
- A new test feeds a multi-finding, multi-scanner fixture (≥2 scanners, ≥2 findings each) through `normalize`→case-build and asserts **total raw findings in == total accounted-for** (every input finding becomes a case or a tracked raw finding; none silently vanish). Deleting or short-circuiting one finding inside `normalize.py` makes this test **fail**.
- A second test feeds a malformed-but-**nonempty** scanner payload and asserts it surfaces as **degraded** (a tracked/warned/error outcome), **not** a silent `0 findings`. A regression that swallows the malformed payload into an empty-but-clean result makes this test fail.
- `tests/test_normalize.py` is no longer only the 3 single-input shape cases it has today; it (or a sibling test module) exercises count conservation across a realistic multi-finding dump.

**S-025 — repo-wide no-egress sentinel + redaction + non-skippable trust tests**
- A new `tests/test_no_egress.py` monkeypatches `socket.socket` (and `urllib.request.urlopen`) to raise on any outbound attempt, runs a **full default-path scan→normalize→case-build**, and asserts the pipeline completes with **zero outbound calls**. Adding a default-path network call anywhere in the Python scan pipeline makes this test fail. (Sentinel scope is the Python pipeline; if the served-CSS font path is deliberately excluded pending S-002, that residual is named in the receipt.)
- `tests/test_model.py` is expanded beyond its current 13-line stub to assert `redact_text` **removes the secret value while preserving the locator/key** for several real secret shapes (e.g. AWS key, GitHub token, generic API key). A redaction regression that lets a secret value survive into stored evidence makes this test fail.
- The MCP-guarded trust tests (`test_mcp_server.py`, `test_mcp_fix_proposals.py`, `test_mcp_trigger_scan.py`, `test_red_team_e2e.py`) are **non-skippable in the canonical dev environment**: `import mcp` succeeds via the dev dependency group (or an explicit importable-assertion), so `uv run pytest -q` reports **0 skipped** for these files. A dev checkout missing the `mcp` extra now fails loudly rather than reporting a weaker green.

**Suite integrity (both S-IDs)**
- Full `uv run pytest` stays green, with **0 skipped / 0 xfail** introduced, and the new tests are present and passing. No existing trust test was weakened or re-pinned to make the suite pass.

## Required Checks

| Check | Why |
| --- | --- |
| `uv run pytest tests/test_normalize.py tests/test_cases.py -v` | Proves the S-024 count-conservation and degraded-not-zero invariants pass (matrix validation path for S-024). |
| `uv run pytest tests/test_no_egress.py tests/test_model.py -v` | Proves the S-025 repo-wide no-egress sentinel and the hardened `redact_text` coverage pass (matrix validation path for S-025). |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check from AGENTS.md — confirms no test edit broke importability of the package. |
| `python3 -c "import mcp; print('mcp ok')"` | Proves the `mcp` extra is importable in the dev environment, so the four `importorskip("mcp")` trust tests actually run instead of silently skipping (S-025). |
| `uv run pytest -q` (full suite) | Confirms 0 skipped / 0 xfail introduced, the whole suite stays green, and no existing trust test regressed (suite-integrity criterion). |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
