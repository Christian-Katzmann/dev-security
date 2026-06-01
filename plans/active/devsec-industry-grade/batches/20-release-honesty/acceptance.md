# Acceptance: 20-release-honesty

## Acceptance Criteria
- **S-046 (`[Unreleased]` exists and is populated):** `CHANGELOG.md` has an `[Unreleased]` section at the top, above `## [0.1.0] - 2026-05-23`, written in the existing Keep-a-Changelog style (Added / Changed / Fixed / Security buckets). It names the substantive post-tag work — at minimum the guarded MCP case-resolution write-back, the guarded scan-trigger with human gate, the clean-room reviewer with bounded auto-merge, and the red-team end-to-end — and every entry traces to a real commit in `git log v0.1.0..HEAD --oneline`. `grep -n "Unreleased" CHANGELOG.md` is no longer empty.
- **S-046 (the 104 commits are reconciled, not just stubbed):** The post-tag commit log (`git log v0.1.0..HEAD --oneline`, 104 commits) has been walked and every user-visible change is reflected in the `[Unreleased]` section — a reader of the changelog can learn that the MCP write-back (a trust-posture change) shipped. No invented entries: nothing in `[Unreleased]` lacks a backing commit.
- **S-046 (version triple can be cut honestly):** A version is chosen for the next release (the synthesis/lens guidance is to decide whether the body of work warrants `0.2.0`), `pyproject.toml` `version` is staged to that value, and `CHANGELOG.md` + `pyproject.toml` + the intended git tag are prepared so all three agree. The actual tag is *not* cut without explicit user approval, but the three sources are consistent and ready (`pyproject.toml` version == the `[Unreleased]`→numbered changelog heading == the intended tag name).
- **S-053 (README maturity table is true after the work lands):** The README "What's real vs. what's not yet" table (`README.md:22`–`:36`) has been re-read line-by-line against actual shipped behavior after this campaign's Stage A/B work landed. Anything now genuinely shipped (e.g. the hands-off code-fix flow surface from S-043, scan-history/trends/diff from S-039/S-042) is moved out of "not yet" or accurately described; nothing half-built or invisible is presented as complete. Honest "Coming Soon" walls that are still real (External Surface scanning, runnable packs) remain in place and are not overstated as active.
- **S-053 (version honesty re-confirmed at campaign end):** The version triple (`pyproject.toml` version, git tag intent, `CHANGELOG.md` top numbered entry) is confirmed to agree as part of the `feature-health-final` re-read; `pyproject.toml` is no longer the stale `0.1.0` that lags the tree by 104 commits. The "real vs not yet" claim is demonstrably consistent with shipped behavior — the confident-falsehood failure mode this row guards is eliminated.

## Required Checks
| Check | Why |
| --- | --- |
| `git log v0.1.0..HEAD --oneline` (and `git rev-list v0.1.0..HEAD --count` == 104) diffed against the new `[Unreleased]` section | Matrix + synthesis validation path for S-046; proves the 104 post-tag commits are accounted for in the changelog rather than silently dropped. |
| `grep -n "Unreleased" CHANGELOG.md` returns the new section; `grep -m1 '^version' pyproject.toml` shows the chosen next version | Proves `[Unreleased]` was added and the `pyproject.toml` version is no longer stuck at `0.1.0` — the concrete drift the lens flagged. |
| Confirm `pyproject.toml` version == intended changelog numbered heading == intended git tag name (the three sources agree) | Proves the version triple can be cut honestly at the next release (S-046 outcome); guards against a tag/version/changelog mismatch. |
| Re-read `README.md:22`–`:36` ("What's real vs. what's not yet") against shipped behavior in the campaign-end `feature-health-final` pass | Matrix + synthesis validation path for S-053; proves the maturity table is true *after* the polish/feature work landed, not a pre-campaign snapshot. |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` (fast import check) | Per AGENTS.md; confirms the `pyproject.toml` version bump did not break packaging/import metadata (the only code-adjacent file this batch touches). |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
