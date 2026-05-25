# 5b · DëvSec dashboard coherence — close NEEDS WORK findings, then merge to main

**Branch: `devsec-dashboard-coherence`** (operates on the existing #5 branch; auto-finalize merges to `main` on APPROVED).

> Bridge campaign that resolves the four NEEDS WORK findings from campaign #5's final review and lets the #5 branch merge cleanly to `main`. Auto-finalize runs #5's full review at the end; on APPROVED it auto-merges and auto-chains to campaign #6 (`devsec-catalog-setup-flow`).

## Scope

Campaign #5's final review came back NEEDS WORK with four findings (one structural — Phase 2-5 work not committed — and three specific code issues). This bridge has a single coding step that closes all of them, after which `claude-automate finalize` runs #5's original review prompt against the cumulative branch diff, iterates fixes if the review still flags issues, and on APPROVED auto-merges to `main` and chains to campaign #6.

Done when:

1. The four NEEDS WORK findings are closed on the `devsec-dashboard-coherence` branch.
2. `npm run lint && npm run build` in `dashboard-ui/` pass.
3. The Python import check and the project's test suite still pass.
4. Auto-finalize's review of `main...devsec-dashboard-coherence` returns APPROVED.
5. `devsec-dashboard-coherence` is merged into `main`.
6. Campaign #6 (`devsec-catalog-setup-flow`) is auto-launched from a fresh branch off the new `main`.

## Context (locked decisions)

- **Branch: `devsec-dashboard-coherence`** (already exists; this campaign closes it out for merge to `main`).
- **No new scope.** Only the four review findings get closed. No drive-by refactors, no unrelated cleanups.
- **No history rewrites.** Phase 2-5 commits are added on top of the existing `devsec-dashboard-coherence` branch. No squashing, no `--amend`, no force-pushes.
- **No skipping hooks.** Pre-commit hooks must pass. If a hook fails, fix the underlying issue.
- **Iterate up to 5 review rounds.** `--max-fix-retries 5` is set at init time. Auto-finalize handles the review → fix-agent → re-review loop. Step 1.1 only does the initial pass.
- **Auto-merge + auto-chain are configured at init time.** No manual `git merge` or `claude-automate launch` in this campaign's steps — the runner does it.

## Review findings to close

These are the exact NEEDS WORK findings from #5's final review:

1. **Phase 2-5 work is not on the branch.** `main...HEAD` only contains commits through Step 1.1. Phase 2-5 work sits unstaged in the working tree.
2. **Step 5.1's "View full diagnostic" link is broken in All Repos mode.** Overview always renders it, but Verification is repo-only and the app redirects unavailable tabs back to Overview. See `dashboard-ui/src/App.tsx:1711`, `dashboard-ui/src/App.tsx:304`, `dashboard-ui/src/App.tsx:724`.
3. **All Repos "Choose checks" is a dead affordance.** Overview enables it, but the run sheet disables Start unless a repo is selected. See `dashboard-ui/src/App.tsx:1732` and `dashboard-ui/src/App.tsx:1411`.
4. **Vocabulary lock is incomplete.** Rotation still exposes `aria-label="warning"` plus a warning icon for rotation state, and the Honey Key create API still returns a UI-state field named `warning`. See `dashboard-ui/src/components/RotationStatusCard.tsx:344`, `src/security_observatory/dashboard/dashboard_server.py:2211`, `dashboard-ui/src/components/HoneyKeysView.tsx:25`.

Positive checks from the review (must not regress):

- Install endpoint guardrail tests pass
- `python -c "import security_observatory"` passes
- `npm run lint` passes in `dashboard-ui/`
- `npm run build` passes in `dashboard-ui/`
- `CaseDetailCard` was not rewritten by the uncommitted Step 4.1 composition work

## Progress checklist

- [x] Step 1.1 — Close the four NEEDS WORK findings and verify build + tests

## Step 1.1 — Close the four NEEDS WORK findings and verify build + tests

Model: Opus 4.7 1M · Extra High
Parallel: NO

Address all four findings on the `devsec-dashboard-coherence` branch. After this step completes, `claude-automate finalize` runs automatically: it executes the "## Final review" prompt below against `main...HEAD`, iterates a fix-agent if needed, and on APPROVED merges to `main` and chains to campaign #6.

```text
SCOPE: Close the four NEEDS WORK findings from campaign #5's final review. No new scope.

REQUIRED READING (in order):
1. campaigns/devsec-dashboard-coherence-fix-and-merge.md (this file — read the "Review findings to close" section and the "## Final review" prompt below)
2. campaigns/devsec-dashboard-coherence.md (the campaign being closed out — re-read its Step 1.1 prompt to understand the vocabulary lock that must hold; re-read its "## Final review" section because that's the prompt auto-finalize will run against your work)
3. dashboard-ui/src/App.tsx — read around lines 304, 724, 1411, 1711, 1732
4. dashboard-ui/src/components/RotationStatusCard.tsx — read around line 344
5. src/security_observatory/dashboard/dashboard_server.py — read around line 2211
6. dashboard-ui/src/components/HoneyKeysView.tsx — read around line 25
7. `git log --oneline -10` to learn the established commit-message style (e.g. "step 2.1: ..."); match it.

CURRENT STATE TO EXPECT:
- Branch: devsec-dashboard-coherence — confirm with `git branch --show-current`. If you're on a different branch, abort with a fail and a precise reason.
- Working tree has uncommitted modifications across the dashboard for Phase 2-5 of campaign #5.
- main...HEAD currently only contains commits through Phase 1's Step 1.1 — the Phase 2-5 work needs to land.

WORK PLAN (in order):

1) Inventory the uncommitted work
   - Run `git status` and `git diff --stat`.
   - Group files by which Phase/Step they belong to (cross-reference against campaign #5's progress checklist: Step 2.1 + 2.2 = two-mode model, Step 3.1 = KPI scope, Step 4.1 = findings master-detail, Step 5.1 = scan controls on Overview).
   - If a file doesn't map cleanly to a step, note it in the receipt and include it with the closest-matching step's commit.

2) Apply the three surgical code fixes BEFORE committing
   These belong INSIDE the corresponding Phase 4 / Phase 5 / Phase 1 commits — not as a separate "fix review findings" commit. The branch should read as if these had landed correctly the first time.

   FIX A — "View full diagnostic" link broken in All Repos mode
   - In All Repos mode the case detail's "View full diagnostic" link currently routes to Verification, but Verification is repo-only and the app redirects unavailable tabs back to Overview.
   - Recommended fix: in All Repos mode, if the case has a single underlying repo, auto-select that repo and link to its Verification tab. If the case spans multiple repos (or it isn't possible to derive one), hide the link entirely with a tooltip ("Available in repo mode") so the affordance isn't dead.
   - Touch points: `dashboard-ui/src/App.tsx` around lines 1711, 304 (tab availability), 724 (redirect logic).

   FIX B — "Choose checks" affordance dead in All Repos mode
   - In All Repos, the run sheet's Start button is disabled until a repo is selected — but All Repos is exactly the case where the user wants to run across all repos.
   - Recommended fix: enable Start in All Repos mode so it runs the selected checks across all repos in scope. The run-sheet confirmation copy should read "Running across N repos" when no specific repo is chosen.
   - Touch points: `dashboard-ui/src/App.tsx` around lines 1732, 1411. Read the run-sheet's `isStartDisabled` (or equivalent) and the Choose-checks click handler. Update both.

   FIX C — Vocabulary lock holes
   - `RotationStatusCard.tsx:344`: replace `aria-label="warning"` with the locked vocabulary. Read Step 1.1 of campaign #5 for the canonical replacements (likely `aria-label="attention"` or similar depending on what the icon represents). Replace the underlying icon component if it's still semantically `Warning*`.
   - `dashboard_server.py:2211`: the Honey Key create API returns a UI-state field named `warning`. Rename to the locked vocabulary. Update any response schema / TypedDict alongside.
   - `HoneyKeysView.tsx:25`: update the frontend consumer that reads `warning` to use the new name.
   - Verification: run `git grep -nE '"warning"|warning:|aria-label="warning"' dashboard-ui/src/ src/security_observatory/dashboard/`. Each remaining hit must have a defensible justification noted in the receipt (legitimate Python `import warnings`, third-party API field name, test fixture explicitly testing "warning behaviour", etc.).

3) Commit the work
   - Group commits by Step (e.g. `step 2.1: ...`, `step 2.2: ...`, `step 3.1: ...`, `step 4.1: ...`, `step 5.1: ...`) following the established style.
   - Fold the three surgical fixes into the related step commits, NOT a separate "fix review findings" commit.
   - Campaign md updates currently in the working tree:
     - `campaigns/devsec-dashboard-coherence.md` (checkbox ticks for Steps 2.1, 2.2, 3.1, 4.1, 5.1) — fold into the corresponding step commits, or include in a single `chore: campaign #5 checklist ticks` commit if cleaner.
     - `campaigns/devsec-rotation-integration.md` (Final review checkbox tick from campaign #4, which already merged) — commit separately as `chore: tick #4 final review checkbox`.
     - `campaigns/devsec-dashboard-coherence-fix-and-merge.md` (NEW, untracked, the campaign you're running) — commit as `chore: add #5 cleanup bridge campaign`.
   - Leave `reports/campaign-automation/devsec-dashboard-coherence/` untracked — it's automation log noise.
   - Each commit must pass pre-commit hooks. Don't `--no-verify`.

4) Verify before marking done
   - `cd dashboard-ui && npm run lint` passes
   - `cd dashboard-ui && npm run build` passes
   - `cd /Users/christiankatzmann/Dev/Projects/dëv-security && python -c "import security_observatory"` passes
   - The project's pytest command passes for the touched modules (check `pyproject.toml` / `Makefile` / `package.json` for the actual command if you're unsure)
   - `git status` clean (or only `reports/` and ignored artifacts remain)
   - `git log --oneline main..HEAD` shows the new commits in step order

5) Receipt
   Write to ~/.claude-automate/campaigns/devsec-dashboard-coherence-fix-and-merge/receipts/step-1.1.md. Include:
   - Commit hashes + messages
   - The three surgical fixes (file:line + 1-line description each)
   - Verification results
   - Any open caveats

DO NOT:
- Add new features outside the four findings
- Refactor unrelated code
- Force-push, rebase shared history, or skip hooks
- Run the secrets-rotation skill or any other side-effect skill
- Manually trigger `claude-automate finalize` or `git merge` — auto-finalize is wired and will run after `advance`

When the work is done and verified, call:
  claude-automate advance --slug devsec-dashboard-coherence-fix-and-merge --completed-step 1.1
```

## Final review

This is the prompt that `claude-automate finalize` will run after Step 1.1 completes. It is a verbatim restatement of campaign #5's original final-review prompt — auto-finalize runs it against the cumulative `main...devsec-dashboard-coherence` diff (which after Step 1.1 includes all of Phase 0-5 plus the four close-outs).

```text
Run a final review on the devsec-dashboard-coherence campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-dashboard-coherence.md
Campaign: campaigns/devsec-dashboard-coherence.md (read inline against the cumulative diff on the devsec-dashboard-coherence branch)

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff that the criteria actually landed. Don't trust step receipts — read the diff.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another (e.g., the vocabulary lock in Step 1.1 not actually applied in a later step's new copy), intent claimed in early steps but undermined by later ones (e.g., a KPI added in Step 5.1 that doesn't use scopedSummary), dead code left behind, regressions in unrelated areas.

Specific things to verify:
- Vocabulary lock from Step 1.1 holds in every later step's new copy (no "warning" used for UI state, no ambiguous "findings")
- Two-mode model (Step 2.1) is honored by every view modified in Step 2.2, 3.1, 4.1, 5.1
- Every KPI on a target-scoped view actually uses scopedSummary (Step 3.1), including ones added later in Step 5.1
- CaseDetailCard component is unchanged (Step 4.1 didn't rewrite it)
- Verification tab still works as a deeper diagnostic; nothing essential moved to Overview was lost (Step 5.1)
- The in-session install button (Step 0.1) is committed and the endpoint guardrails still fire

Specific findings from the previous review that MUST be closed:
- "View full diagnostic" link is no longer broken in All Repos mode (either hidden with a tooltip, or it auto-selects a repo and routes to Verification)
- "Choose checks" / Start button is no longer dead in All Repos mode (Start enabled, runs across all repos in scope)
- aria-label="warning" and the UI-state field named `warning` in the Honey Key create API are gone — replaced with the locked vocabulary
- Phase 2-5 commits are on the branch (`main...HEAD` shows commits for Steps 2.1, 2.2, 3.1, 4.1, 5.1)

Be honest. Lean. APPROVED if every step's acceptance criteria landed and there are no cross-step regressions. NEEDS WORK if any step cut corners or a primitive was bypassed.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.7 with Extra High thinking
(Your call — both are acceptable for this kind of cross-file review.)
```
