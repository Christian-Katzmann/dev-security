# Batch: 05-trust-integrity-tests

## Purpose
This batch closes the two trust-critical invariants that DëvSec *claims* but does not yet *prove at the test level* — "no finding is silently dropped" and "nothing leaves on a default path." Both are non-negotiable failure modes in the Excellence Brief, and today the suite catches regressions only in known call sites or single-input fixtures. **S-024** adds normalization count-conservation / dropped-findings tests; **S-025** adds a repo-wide no-egress sentinel, hardens `redact_text`/`model.py` coverage, and makes the MCP-guarded trust tests non-skippable. The shared fix surface is the Python test suite under `tests/` (no production code changes required for the core work) — turning two proven-per-function guarantees into suite-enforced invariants that fail if the guarantee breaks.

## Source Evidence
- **S-024** — Add a multi-finding, multi-scanner count-conservation test (total-in == total-accounted-for through normalize→case) plus a malformed-but-nonempty payload test asserting it surfaces as *degraded*, not silently zero · evidence: `tests/test_normalize.py` is 45 lines / 3 single-input cases, each asserting `len(findings) == 1` with no count-conservation across a multi-finding input (lens report Rank 1; file confirmed 1311 bytes) · synthesis row S-024, lens report `09-test-confidence-health.initial.md`
- **S-025** — Add a repo-wide no-egress sentinel (monkeypatch `socket`/`urlopen` to raise, run a full default-path scan→case-build, assert zero outbound attempts), expand `test_model.py` to assert `redact_text` removes secret values while keeping locators, and pin the `mcp` extra so write-guard/injection/clean-room/red-team tests can't silently skip · evidence: no repo-wide socket-deny sentinel exists (lens report Rank 2; `tests/test_no_egress.py` confirmed absent); `tests/test_model.py` is a 13-line stub for the privacy-load-bearing `redact_text` (lens report Rank 3; file confirmed 702 bytes); `tests/test_mcp_server.py:20`, `test_mcp_fix_proposals.py:15`, `test_mcp_trigger_scan.py:17`, `test_red_team_e2e.py:30` all `pytest.importorskip("mcp")`, and `pyproject.toml:9` declares `mcp` only as an optional extra (`mcp = ["mcp>=1.0"]`), not in the dev group (lens report "Undocumented Or Hidden Surfaces" + Top Repair Target 2) · synthesis row S-025, lens report `09-test-confidence-health.initial.md`

## Target
Move S-024, S-025 from Yellow to Green.

## Dependencies
- S-024: None (matrix Dependencies column is —).
- S-025: S-002 (soft). S-002 is owned by batch `01-egress-honesty` (eliminate the Google Fonts default-path egress). The dependency is *soft* — the no-egress sentinel can be authored and run independently, but if the sentinel is written to cover the **served dashboard CSS / build output**, it will only stay green after S-002 lands. Scope the sentinel to the **Python default-path scan→case pipeline** (which is the lens report's evidence and is already egress-free), so this batch does not block on 01. Note the residual in the receipt if the sentinel deliberately excludes the front-end font path.
- No same-batch ordering constraint between S-024 and S-025; they touch disjoint test files.

## Non-Goals
- Do not attempt other batches' super-list items.
- Do not broaden this into a general cleanup.
- Do not make production, destructive, deploy, secret, or irreversible data changes without explicit approval.
- Do not fix the live Google Fonts egress here — that is S-002 / batch `01-egress-honesty`. This batch only adds the *test backstop* that would catch a *future* default-path egress in the Python pipeline.
- Do not add front-end (JS/TS) component tests — frontend test posture is deferred to the behavioral-ux / design-system lenses per the lens report's own scoping.
- Do not weaken or re-pin any existing trust test to make it pass; the `mcp` change must make the guarded tests *run*, never skip.

## Suggested Starting Steps
1. Re-read this context and acceptance.md.
2. Re-verify each S-ID's evidence: open `tests/test_normalize.py` (confirm 3 single-input cases), `tests/test_model.py` (confirm 13-line stub), grep `pytest.importorskip("mcp")` across `tests/`, and confirm `pyproject.toml` lists `mcp` only as an optional extra. Read `normalize.py`, `cases.py`, `model.py` (`redact_text`), and the default-path scan entry to learn the real shapes before writing fixtures.
3. **S-024:** in `tests/test_normalize.py` (or a sibling), add a multi-finding/multi-scanner fixture and assert total raw findings in == total accounted-for through normalize→case (none vanish); add a malformed-but-nonempty payload case asserting it surfaces as *degraded* (a tracked/warned outcome), not a silent zero. Use real scanner output shapes, not hand-waved dicts.
4. **S-025:** add `tests/test_no_egress.py` that monkeypatches `socket.socket` and `urllib.request.urlopen` to raise, runs a full default-path scan→case-build, and asserts it completes with zero outbound attempts; expand `tests/test_model.py` to assert `redact_text` strips secret *values* while preserving locators across several real secret shapes; and make the `mcp`-guarded tests non-skippable in the canonical dev environment (pin `mcp` into the dev dependency group, or add a guard/assertion that `import mcp` succeeds so the `importorskip` paths execute) — chosen so a contributor without the extra gets a true-red, not a false-green.
5. Implement the smallest root-cause fix that satisfies every acceptance criterion; prefer real fixtures over mocks, and add tests where risk justifies. Run `uv run pytest tests/test_normalize.py tests/test_cases.py tests/test_no_egress.py tests/test_model.py -v` plus the full `uv run pytest` to confirm nothing else broke and that no trust test now skips.
