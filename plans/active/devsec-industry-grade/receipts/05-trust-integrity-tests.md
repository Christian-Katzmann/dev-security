# Implementation Receipt: 05-trust-integrity-tests

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 05-trust-integrity-tests
- Source report item(s): S-024 (dropped-findings / count-conservation), S-025 (no-egress sentinel + redaction + non-skippable MCP trust tests)

## Before Health

- `tests/test_normalize.py`: 3 single-input shape cases, each asserting `len(findings) == 1`; no count conservation across a multi-finding/multi-scanner dump, no degraded-not-zero coverage.
- `tests/test_model.py`: 13-line stub covering only `score_findings`; no coverage of `redact_text`, the privacy-load-bearing redaction.
- `tests/test_no_egress.py`: absent — no repo-wide socket-deny sentinel anywhere.
- `pyproject.toml`: `mcp` declared only as an optional extra (`[project.optional-dependencies] mcp`), not in the dev group, so a fresh `uv sync --dev` would leave the five `pytest.importorskip("mcp")` trust tests skipping (false green).
- Baseline run: `uv run pytest -q` → **480 passed** (0 skipped only because this particular venv happened to have the extra installed; the guarantee was incidental, not structural).

## Changes Made

- **S-024 · `tests/test_normalize.py`**
  - `test_multi_scanner_findings_are_conserved_through_normalize_and_cases`: real semgrep/trivy/gitleaks payloads (3 scanners × 2 findings = 6 raw). Asserts `len(normalized) == raw_count` (normalize drops nothing) and that the union of `case.source_fingerprints` **equals** the set of input fingerprints (case-build conserves — none vanish, none invented).
  - `test_malformed_scanner_payload_surfaces_as_degraded_not_silent_zero`: a stand-in `checkov` binary emits non-empty, unparseable output and exits 2; drives the real `run_scanner` and asserts the scanner is available, yields **0 findings**, records a tracked `error`, and surfaces as an evidence gap via `scanner_evidence_gaps`. Proves a malformed payload becomes a degraded outcome, not an empty-but-clean pass.
- **S-025 · `tests/test_no_egress.py`** (new): arms a hard block on `AF_INET`/`AF_INET6` sockets, `socket.create_connection`, and `urllib.request.urlopen`; a `test_sentinel_actually_blocks_egress` guard proves the block trips (non-vacuous); then runs a full default-path `scan_repo` (built-in scanners → normalize → cases → local IOC packs → scoring → SQLite) and asserts **zero outbound attempts**. External scanner binaries are forced to skip (patched `shutil.which`) so the in-process Python pipeline is exercised deterministically regardless of which tools are installed locally.
- **S-025 · `tests/test_model.py`**: parametrized `redact_text` coverage over five real secret shapes (AWS key id, GitHub PAT, OpenAI key, Slack token, generic 32+ char key) asserting the secret **value** is stripped while the **locator/key survives**; plus a no-false-positive test (plain prose passes through verbatim) and a mid-sentence redaction test.
- **S-025 · `pyproject.toml`**: pinned `mcp>=1.0` into `[dependency-groups] dev` so `uv sync --dev` always installs it and the `importorskip("mcp")` trust tests run instead of silently skipping. `uv.lock` regenerated via `uv sync --dev`. No existing trust test was weakened or re-pinned.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/test_normalize.py tests/test_cases.py -v` | PASS | S-024 conservation + degraded-not-zero invariants pass. |
| `uv run pytest tests/test_no_egress.py tests/test_model.py -v` | PASS | S-025 no-egress sentinel + hardened `redact_text` coverage pass. |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli; print('ok')"` | PASS | Package still importable. |
| `python3 -c "import mcp; print('mcp ok')"` | PASS | `mcp` importable (system + `uv run python` both confirmed). |
| `uv run pytest -q` (full) | PASS | **491 passed, 0 skipped, 0 xfail** (was 480; +11 new tests). |
| Mutation check (drop one finding in `normalize._gitleaks`) | FAILS as required | Conservation test is non-vacuous — it fails when a finding is silently dropped. |

## After Health

- S-024 → Green: count conservation across a realistic multi-finding/multi-scanner dump is suite-enforced; a degraded scanner payload is provably tracked, not swallowed.
- S-025 → Green: a repo-wide no-egress sentinel fails on any new default-path Python egress; `redact_text` value-stripping is enforced across real secret shapes; the MCP-guarded trust tests are structurally non-skippable in the canonical dev env (`mcp` in the dev group → 0 skipped).

## Remaining Risk

- **Sentinel scope (named per acceptance):** the no-egress sentinel covers the **in-process Python scan pipeline** only. External scanner binaries run out-of-process and are forced to skip in the test — an in-process socket guard cannot observe a child process's sockets anyway; that is a separate trust boundary. The served-dashboard font path is no longer a residual: S-002 (batch 01) landed, fonts are self-hosted, and the served CSS under `src/security_observatory/dashboard/assets/` contains no `googleapis`/`gstatic` reference (verified).
- The degraded test creates and executes a small local Python shim named `checkov` inside `tmp_path` (no network, no installer, honors `.adx/risks.json`). It is portable via `sys.executable`; environments without an executable interpreter path would need adjustment, but that matches every other test here.

## Next Batch

Last implementation step of Stage A — no downstream batch. Full suite confirmed green (491 passed, 0 skipped / 0 xfail) before finishing.
