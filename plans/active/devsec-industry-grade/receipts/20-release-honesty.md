# Implementation Receipt: 20-release-honesty

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 20-release-honesty
- Source report item(s): S-046 (reconcile CHANGELOG ↔ tree drift; add/populate `[Unreleased]`; decide bump; ready the version triple), S-053 (keep "real vs not yet" honest after the campaign work landed; re-confirm the version triple)

## Before Health

- **S-046 = Yellow.** Re-verified directly: `git rev-list v0.1.0..HEAD --count` = **130** (the context.md figure of 104 was the count when the batch was authored; 26 more commits — the Stage C structural/docs batches — landed since). `grep -m1 '^version' pyproject.toml` = `version = "0.1.0"`. `grep -n Unreleased CHANGELOG.md` = empty; the changelog had only `## [0.1.0] - 2026-05-23`. Trust-posture-changing post-tag work (guarded MCP write-back, scan-trigger, clean-room reviewer, red-team e2e, code-fix dashboard surface, trends/diff) was unrecorded.
- **S-053 = Green/Yellow.** README "What's real vs. what's not yet" table (`README.md:22`–`:36`) predated the code-fix flow (S-043) and scan-history/trends/diff (S-039/S-042) — both now genuinely shipped on the dashboard (confirmed against receipts `13-code-fix-dashboard-surface.md` and `12-surface-scan-history-trends.md`), yet absent from the maturity table. `pyproject.toml` was 130 commits stale vs the tree.

## Changes Made

**S-046 — CHANGELOG + version triple:**
- `CHANGELOG.md`: added a populated `## [Unreleased]` section at the top, in the existing Keep-a-Changelog style (Added / Changed / Fixed / Security). It walks the 130 post-tag commits and names the substantive work — guarded MCP write mode (`devsec-mcp-rw`), guarded `trigger_scan` with human gate, clean-room reviewer + bounded auto-merge, the propose→review→land code-fix flow and its dashboard surface, scan-history/trends/scan-diff, case lifecycle, secret rotation, Tool Catalog/setup flow, binary-trust verification, extended MCP read surface, accessibility, voice doctrine + safety tiers, plus the structural refactors and docs-truth fixes. Every entry traces to a real commit in `git log v0.1.0..HEAD`. A blockquote note stages it for release as **0.2.0** (tag `v0.2.0`) and documents the rename-on-cut step. The actual tag was **not** cut (per Non-Goals + `.adx/risks.json`).
- `pyproject.toml`: `version` `0.1.0` → `0.2.0`. Minor bump chosen because the body of work adds major backward-compatible subsystems (guarded write surface, rotation, catalog, code-fix surface).

**S-053 — README maturity table:**
- `README.md:7`: status line `0.1.x` → `0.2.x`.
- Added two honest rows to the "real vs not yet" table for surfaces this campaign shipped:
  - **Scan history & trends** — local per-scan history, posture sparkline, base/head scan-diff (`/api/scan-diff`) with resolved-case closure proofs.
  - **Guarded AI fix flow** — MCP write-mode propose→clean-room-review→land, the dashboard "Code fixes" view, narrow auto-merge-eligible classes; the "not yet" column keeps the human-gate honesty intact (broad/high-risk fixes and high/critical suppression held for explicit human confirmation; `land_fix` authorizes but never merges).
- Existing "Coming Soon" walls (External Surface, runnable IaC Pack page) left in place and not overstated.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `git rev-list v0.1.0..HEAD --count` vs `[Unreleased]` | PASS | 130 commits walked; all user-visible arcs reflected, none invented. |
| `grep -n "Unreleased" CHANGELOG.md` | PASS | No longer empty — section present at top. |
| `grep -m1 '^version' pyproject.toml` | PASS | `version = "0.2.0"` — no longer stale `0.1.0`. |
| Version triple agreement | PASS | pyproject `0.2.0` == `[Unreleased]`→intended `0.2.0` heading == intended tag `v0.2.0`. |
| `python3 -c "...import security_observatory.cli; print('ok')"` | PASS | `ok` — version bump did not break packaging/import metadata. |
| README `:22`–`:38` re-read vs shipped behavior | PASS | Code-fix flow + scan-history/trends now described; Coming-Soon walls preserved. |

## After Health

- **S-046 → Green.** `[Unreleased]` exists and is populated from the real 130-commit log; the version triple (pyproject == changelog target == intended tag) agrees on `0.2.0` and can be cut honestly. Tag left for human action per the approval gate.
- **S-053 → Green.** The maturity table describes the now-shipped code-fix and scan-history/trends surfaces accurately, keeps honest Coming-Soon walls, and the version triple is re-confirmed consistent — the "confident falsehood" failure mode is eliminated.

## Remaining Risk

- The git tag `v0.2.0` is deliberately **not** cut; Christian must `git tag v0.2.0` (and push) to complete the release. When cutting, rename the `## [Unreleased]` heading to `## [0.2.0] - <date>` and open a fresh `[Unreleased]`.
- Commit count is 130, not the 104 cited in context.md/synthesis (more commits landed after authoring); the reconciliation covers all 130.

## Next Batch

21-integration-and-mcp-hygiene (S-008–S-014). Its context.md cites only code files (`enrichment.py`, `setup_runner.py`, `mcp_server.py`, `case_followup.py`, `reset.py`, `dashboard_server.py`) — none touched here, no line references moved. No downstream adjustment needed; target S-IDs unchanged.
