# Implementation Receipt: 19-adx-and-docs-truth

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 19-adx-and-docs-truth
- Source report item(s): S-030, S-031, S-048, S-049, S-050, S-010, S-051, S-052

## Before Health

The repo's self-description had drifted behind code that landed through 2026-05-31:

- `.adx/modules/index.json` listed 5 modules, none covering the MCP write subsystem; `grep -rl "mcp_server|fix_proposals|land_fix|propose_fix" .adx/` returned **0**.
- `.adx/risks.json` had 5 risk ids and a `dangerous_command_patterns` list with no `devsec-mcp-rw`/`land_fix`/`propose_fix`.
- `.adx/recovery.md` "Pytest Is Missing" and `.adx/verification.json:40` both asserted pytest **cannot run** ("currently blocked"). Live truth this run: `uv run pytest -q` = **524 passed, 0 skipped** (the predicted "409 passed, 4 skipped" was itself stale — the `mcp` extra is installed in this checkout, so nothing skips).
- `.adx/adx.json` `last_verified` was `2026-05-12T13:35:03Z` (stale vs code).
- `AGENTS.md` denied the shipped write path ("read-only access to scan results"), had no brand-identity line, and did not demote churn docs.
- `mcp/README.md` said the write adapter "adds three case-resolution tools only" / "plus three"; code registers **8** write tools.
- Security-sensitive CLI verbs/flags were code-only (note: batch 14 moved the parser, so the suppressed flags are now at `scan_orchestrator.py:73–84`, not `cli.py:85–96`).
- Honey Key safety claims were not line-matched to guards.

## Changes Made

**S-030 — module map.** Added a `mcp-write-surface` entry to `.adx/modules/index.json` (`key_files` = `mcp_server.py`, `fix_proposals.py`, `case_followup.py`, `decisions.py`, `mcp/README.md`; `tests` list; `boundary` pointer) and a new `.adx/modules/mcp-write-surface.md` intro.

**S-031a — risk register + danger patterns.** Added a `mcp-write-surface` risk to `.adx/risks.json` and added `devsec-mcp-rw`, `land_fix`, `propose_fix` (plus `security-scan reset`, `cases import-resolutions --apply`) to `dangerous_command_patterns`. Also corrected the stale `honey-keys` evidence line (`dashboard_server.py:995` → real guards `:2772` + `honey_keys.py:85`).

**S-031b / S-049 — pytest truth.** Rewrote `.adx/recovery.md` ("Pytest Is Missing" → "Pytest Won't Run", citing 524 passed/0 skipped + `uv run pytest`/`uv sync --dev`) and `.adx/verification.json` note (removed "currently blocked"). Also reworded the live `.adx/commands.json` recovery_hint ("If pytest is missing" → "If pytest fails to start") so no live contract trips the false-claim grep.

**S-031c — stamp.** Bumped `.adx/adx.json` `last_verified` to `2026-06-01T20:00:00Z` (newer than newest src mtime `2026-06-01T14:18:15`).

**S-031d — brand.** Added an AGENTS.md "Start Here" line equating Security Observatory (package/repo) ↔ DëvSec (product brand).

**S-048 — AGENTS.md MCP honesty.** Rewrote the MCP line to name both `devsec-mcp` (read-only, 11 tools) and `devsec-mcp-rw` (8 guarded write tools), matching `pyproject.toml` scripts.

**S-050 — doc boundary.** Added an AGENTS.md "Start Here" line demoting `campaigns/`, `reports/campaign-automation/`, and root scratch docs (`next-step.md`, `overview-redesign-*.md`) to historical working notes, not contract.

**S-010 — MCP README count.** Corrected intro, the "three tools only" line, the verify-block "plus three" line, and the "Write mode is case-only" Hard-limit framing to the real 8 tools; appended the `trigger_scan` and propose→review→land descriptions to the "Guarded write mode" section (existing accurate prose left intact per non-goal).

**S-051 — CLI surface.** New `docs/cli-security-surface.md` documenting the destructive/write verbs (`reset`, `cases import-resolutions`, `vex-import/export`) and the SUPPRESS-hidden flags (`--apply`, `--confirm-suppression`, `--yes`, `--backup-to`, …) with the code guard for each, plus an honest "verbs that are NOT on the CLI" note (factory-reset/case-decision/propose-fix/land-fix etc. are dashboard-API or MCP-only, not CLI). Added a "Security-sensitive commands" subsection + pointer in `README.md` Usage.

**S-052 — Honey Key fidelity.** Appended a "Guard Fidelity" table to `docs/honey-keys.md` binding each claim to its guard: overwrite refusal `dashboard_server.py:2772-2773`, in-repo containment `:2765`/`:2788`, duplicate refusal `:2675`, hash-only storage `honey_keys.py:85-86`. All cited lines verified present in current code.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `json.load` all edited `.adx/*.json` | PASS | index.json, risks.json, adx.json, verification.json, commands.json all parse |
| `grep -rl "mcp_server\|fix_proposals\|land_fix\|propose_fix" .adx/` | PASS | now hits index.json, risks.json, mcp-write-surface.md (was 0) |
| key_files exist | PASS | all 5 resolve |
| `grep -i "devsec-mcp-rw\|land_fix\|propose_fix" .adx/risks.json` | PASS | present in risk + danger patterns |
| `uv run pytest -q` | PASS | **524 passed, 0 skipped** (run twice, before + after edits) |
| `grep -ri "pytest is missing\|currently blocked\|pytest is not installed" .adx/` | PASS (live) | live contracts clean; only dated `audit/`+`implementation/` 2026-05-12 snapshots still contain the phrase (deliberately preserved — see Remaining Risk) |
| `last_verified` vs newest src mtime | PASS | 2026-06-01T20:00:00Z > 2026-06-01T14:18:15 |
| `grep -n "read-only access to scan results" AGENTS.md` | PASS | gone; `devsec-mcp-rw` now named |
| mcp/README write tools == 8; `grep "three...only\|plus three"` | PASS | 8 registered tools match; understatement gone |
| `grep -niE "historical\|working.notes\|not contract\|superseded" AGENTS.md` + brand | PASS | both lines present |
| `grep -riE "confirm-suppression\|factory-reset\|land-fix\|vex-export" docs/ README.md` | PASS | resolves to docs/cli-security-surface.md |
| Honey Key guards at cited lines | PASS | all 4 guards verified in code |
| import check + `git status --porcelain src tests reports` | PASS | "ok"; **no** src/tests/reports changes |

## After Health

S-030, S-031, S-048, S-049, S-050, S-010, S-051, S-052 → **Green**. The `.adx` contracts, AGENTS.md, mcp/README.md, and the CLI/Honey-Key docs now describe the shipped code truthfully. No `src/`, `tests/`, or `reports/` file was touched.

## Remaining Risk

- **Stale fact corrected vs synthesis:** the live suite is **524 passed, 0 skipped**, not the predicted "409 passed, 4 skipped" — used the observed count. Likewise the synthesis's `cli.py:85-96` flag location is now `scan_orchestrator.py:73-84` (batch 14 moved the parser); receipts/docs cite the current location.
- **Several "aliased verbs" in the S-051 spec do not exist as CLI verbs** (`factory-reset`, `case-decision`, `resolve-cases`, `propose-fix`, `land-fix`, `review-fix`, `clean-room-review`). They are dashboard-API (`/api/case-decision`) or MCP-only (`devsec-mcp-rw`) surfaces. Documented honestly rather than inventing CLI verbs.
- **Dated historical `.adx/audit/` + `.adx/implementation/` snapshots** (timestamped 2026-05-12) still contain "Pytest Is Missing" / "pytest is not installed". Left intact on purpose: they are an audit trail of what was true then; rewriting them would falsify history. A fresh ADX audit (out of scope here) would supersede them.

## Next Batch

20-release-honesty (S-053). Note: its `README.md:22–36` maturity-table reference is unaffected — this batch's README edit was inserted in the Usage section (~line 421), below the table. Batch 21 explicitly defers the MCP tool-count correction to this batch; nothing left for it there.
