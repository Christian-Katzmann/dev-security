# Post-launch polish for DëvSec

> The DëvSec repo just went public. Four small things didn't make it into the launch — drawing one flow picture for the front page, officially marking the first version, deciding which other project should sit next to it on the profile, and fixing two old bugs the new automated checks just caught. None of this blocks anything; it's the cleanup pass.

## Scope

The `/repo-craft` pass took DëvSec from a private folder to a live public artifact (https://github.com/Christian-Katzmann/dev-security) on 2026-05-23. Four named items didn't make it into the launch and don't block anything — but they tighten the surface a serious visitor sees. Done means: a memorable diagram is in the README (v3 §10), the v0.1.0 release tag is pushed and visible on the Releases page (v3 Phase 7), the pinned-set strategy is decided (v3 §16), and both CI workflows are green (the new Verify workflow currently runs red on pre-existing TypeScript + pytest debt that wasn't surfaced locally before CI was added). Final review APPROVED closes the campaign.

## Context (locked decisions)

- **`/repo-craft` completed for dev-security on 2026-05-23.** Commits `c8afcf5` through current `HEAD` are the launch work. Repo is public, social preview is live, trailer is embedded, repo is pinned (1 of 6 slots).
- **MCP adapter is already shipped — do not duplicate.** The `devsec` MCP server is live with read-only tools (`cases`, `findings`, `latest_scan`, `list_repos`, `dependency_trust`, `recovery_playbook`) plus 5 companion skills (`devsec`, `devsec-brief`, `devsec-cases`, `devsec-deps`, `devsec-fix`). The retrospective named this as a deferred item; it's now closed.
- **Pinned-set thesis is locked**: *"local-first, source-grounded, calm-by-default tools for serious domains — built so AI agents can work in them safely."* Next pin must fit this through-line.
- **Scope is polish-after-launch, not blocking.** The repo is already usable, discoverable, and pinned. These items improve the surface, not the substance.
- **Phase order is cheap-first, debt-second.** Phase 1 lands the visible wins (diagram, tag, pin decision) in one batch. Phase 2 pays down the Verify CI debt, which is real product work and a separate context window's worth.
- **Branch: work on `main` directly.** This is small polish, not a feature branch's worth. Commit per logical change.
- **`/repo-craft`'s own SKILL.md update from today's retrospective is OUT OF SCOPE.** Those edits live in `~/.claude/skills/repo-craft/`, not this repo.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Launch leftovers (cheap wins)

- [x] Step 1.1 — Add a logic/reasoning diagram to README (v3 §10)
- [x] Step 1.2 — Verify and push v0.1.0 release tag
- [x] Step 1.3 — Decide pinned-set strategy and act on it

### Phase 2 — Pay down Verify CI debt

- [ ] Step 2.1 — Fix the React 19 / `@types/react` mismatch in dashboard-ui
- [ ] Step 2.2 — Reconcile the AI-static scanner with its two failing tests
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Add a logic/reasoning diagram to README (v3 §10)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.2 and Step 1.3

The README has strong screenshots and prose but zero diagrams. v3 §10 says *"one memorable diagram beats five forgettable ones"* — pick the diagram type that does the most explanatory work for DëvSec, draft it in ASCII (consistent with no-other-diagrams-in-repo, grep-able, AI-readable), and place it where it earns its space. The strongest candidate is a logic/reasoning map of the project's core flow: scanner invocation → normalized findings → grouped cases → action levels → playbook + agent-ready handoff.

```text
SCOPE: Add one memorable ASCII diagram to README per v3 §10. Show DëvSec's core flow from scanner invocation to agent-ready next step. The diagram should use the project's own vocabulary (finding, case, action level, playbook, agent-ready follow-up) and explain the thesis at a glance, not just describe the architecture.

REQUIRED READING:
1. README.md — full read, to choose the insertion point (candidates: a new ## section between ## Screens and ## Current Features, or as the opener of ## Current Features itself)
2. ~/Downloads/public-repo-craft-v3.md §10 — "Diagrams that get remembered"
3. docs/glossary.md — terminology to use in the diagram
4. src/security_observatory/cases.py and src/security_observatory/normalize.py — confirm the actual flow matches what the diagram claims
5. PROVOCATION.md — the local-first stance the diagram should reinforce (data flow stays on the user's machine throughout)

OUTPUT:
- One fenced ASCII diagram block in README.md
- Placed in a section the diagram earns (don't squeeze it into an existing section if a new ## fits the rhythm better)
- Uses the project's own terms — not generic data / record / action
- One sentence introducing the diagram, italicized, says what's *proven* not what's depicted (v3 §6 captions rule applies)
- Committed with a tight message: `Add core-flow diagram to README` or similar

OPEN QUESTIONS:
- Should the diagram include the local-first trust boundary (showing that nothing crosses the machine boundary) as an explicit element, or is that load carried by the surrounding prose?
- Best insertion point: between Screens and Current Features (visual rhythm: screens → diagram → features), or before Why this exists (visual rhythm: hero → diagram → narrative)? Pick the one that reads better when scrolling, not what the structure suggests.
```

## Step 1.2 — Verify and push v0.1.0 release tag

Model: Manual — no agent
Parallel: YES — with Step 1.1 and Step 1.3

Per Step 5.1 of `campaigns/public-repo-ready.md`, a `v0.1.0` tag was created locally during the public-repo-ready campaign with the deliberate note "Do NOT push the tag yet — that's part of the flip Christian does himself." The flip happened; the tag wasn't pushed alongside it. After this step, the Releases section on the public repo gets its first entry.

```text
SCOPE: Confirm the v0.1.0 tag exists locally and push it to origin.

COMMANDS:
1. Verify the tag exists: `git tag -l | grep v0.1.0`
2. If yes, push it: `git push origin v0.1.0`
3. If no, surface that — the tag was supposed to be created during the public-repo-ready campaign; if it isn't there, something to investigate before re-creating

VERIFY:
- After push, visit https://github.com/Christian-Katzmann/dev-security/releases — should show v0.1.0
- The tag's commit should be the campaign's final commit (probably eb7c1de or its successor), not a /repo-craft polish commit, because v0.1.0 marks the launchable state, not the post-launch polish

OPEN QUESTIONS:
- If the tag points at the wrong commit, what's the right pointer? Probably eb7c1de (the campaign's auto-merge tail commit before /repo-craft started). Confirm via `git tag --points-at <sha>` and `git log v0.1.0 -1` before pushing.
```

## Step 1.3 — Decide pinned-set strategy and act on it

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.1 and Step 1.2

v3 §16 wants a coherent multi-repo pinned set communicating a through-line. Currently 1 of 6 pins is used. Decide whether to pin a second repo NOW (and which), or document the criteria the next pin must meet so a future `/repo-craft` pass can apply it. Either way, the deliverable is a decision plus the action that follows from it.

```text
/innovate

SCOPE: Decide DëvSec's pinned-set strategy and act on the decision. v3 §16 assumes a coherent multi-repo pinned set anchored by a thesis; currently only dev-security is pinned. Two paths: (a) pin a second repo now if a candidate genuinely fits the thesis at its current public-readiness state, or (b) document the criteria a repo must meet to earn the next pin so future /repo-craft passes have a target.

REQUIRED READING:
1. ~/Downloads/public-repo-craft-v3.md §16 — Pinned-set coherence (the standard for what a coherent set looks like)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/PROVOCATION.md — the thesis dev-security anchors
3. ~/Dev/Projects/ — list other repos that might fit ("local-first, source-grounded, calm-by-default tools for serious domains — built so AI agents can work in them safely")
4. For each candidate (ModelArena at /Users/christiankatzmann/Dev/ïdea.com/modelarena/, monëy.com at /Users/christiankatzmann/Dev/Projects/monëy.com/, reuse-kit at /Users/christiankatzmann/Dev/reuse-kit/): the README opener — does the opening sentence fit the thesis at its CURRENT state, not its potential state?
5. The candidate's public-ness — only public repos can be pinned (private repos don't appear in the Pinned set on a profile)

OUTPUT:
- A short written decision: either (a) "pin X now because Y", or (b) "no candidate is ready; here are the criteria the next pin must meet"
- If (a): drive the pin via chrome MCP (Profile → Customize your pins → check the box → Save), same flow used during /repo-craft. The /repo-craft SKILL.md documents this in its "GitHub platform recipes" section.
- If (b): write the criteria as a short section in ~/Dev/Projects/dëv-security/docs/pinned-set-criteria.md (committed to dev-security since it anchors the set) or in a notes file Christian can re-read later. Don't pin a half-fit repo just to fill a slot — empty slots are honest.

OPEN QUESTIONS:
- Are any of Christian's other repos currently public? If all candidates are private, the answer is (b) by default — pinning has to wait for one of them to earn its own /repo-craft pass.
- If a candidate IS public and fits the thesis, is its current public surface (README first-fold, hero shot or its absence, status statement) good enough to share a pinned shelf with dev-security? A weak-surface pin drags dev-security's perceived quality down with it.
```

## Step 2.1 — Fix the React 19 / `@types/react` mismatch in dashboard-ui

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 2.2

Verify CI's Dashboard job fails on first run with 15+ TypeScript errors of shape *"Property 'key' does not exist on type '{...}'"*. Affects `src/App.tsx` (lines 1171, 1179, 1225, 1227, 1244, 1417, 1447, 1588, 1624, 1876, 2140) and `src/components/DependenciesView.tsx` (lines 73, 86, 115, 150). Locally `npm run lint` was passing because `npm install` (local) installed a different `@types/react` than `npm ci` (CI) does from the lockfile. Find the root cause, apply the smallest fix that doesn't widen prop types beyond what React 19 actually expects.

```text
SCOPE: Resolve the 15+ "Property 'key' does not exist" TypeScript errors in dashboard-ui surfaced by Verify CI. Most likely root cause: @types/react version drift relative to React 19. Smallest fix may be a single lockfile update; if individual components need adjustment, do it without widening prop interfaces beyond what React 19's BaseProps actually requires.

REQUIRED READING:
1. dashboard-ui/package.json — confirm React version and check whether @types/react is in deps or transitively
2. dashboard-ui/package-lock.json — find the actual installed @types/react version (grep for "@types/react")
3. dashboard-ui/src/App.tsx — read the flagged components at the lines above
4. dashboard-ui/src/components/DependenciesView.tsx — read the flagged components at lines 73, 86, 115, 150
5. https://github.com/Christian-Katzmann/dev-security/actions — latest failed Verify run for the full error list and any errors I missed in the campaign brief

PRE-FLIGHT:
- Reproduce locally: `cd dashboard-ui && rm -rf node_modules && npm ci && npm run lint`. Errors will appear with `npm ci` even if `npm install` was passing.
- Check `npm view @types/react versions` for the version that matches React 19.

OUTPUT:
- Smallest-possible fix:
  · If types-only: update @types/react to the version matching React 19, regenerate lockfile, commit lockfile + package.json
  · If component-level: add or import explicit React.Key handling on the flagged components. Don't add `key` to component prop interfaces — that's wrong; React's key is special and handled by the parent's iteration, not the child's props. The errors suggest TypeScript is misreading where key flows; fixing the types should make the errors vanish without source-level changes.
- After fix, both `npm run lint` and `npm run build` must pass locally with `npm ci`
- Push and confirm Verify CI's Dashboard job goes green

OPEN QUESTIONS:
- Is the root cause a missing @types/react dep, a stale lockfile, or genuine component-level type errors? The first hypothesis is most likely given the symptom (every error is the same shape — Property 'key' does not exist), but confirm before assuming.
- If a types update cascades into other type errors elsewhere in the bundle, surface those and decide whether to address inline or queue separately.
```

## Step 2.2 — Reconcile the AI-static scanner with its two failing tests

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 2.1

Two failing pytest tests: `tests/test_ai_static.py::test_ai_static_detects_risky_mcp_json_settings` and `::test_ai_static_detects_risky_agent_text`. Both write fixtures with `approval_mode: never` and `"autoApprove": ["*"]` patterns, then assert the AI-static scanner returns a finding titled *"Agent/editor config appears to enable broad auto-approval"*. The scanner currently returns nothing. Decide whether the scanner regressed (and needs the pattern restored) or the tests are stale (and the scanner's current behavior is correct for an updated security model).

```text
SCOPE: Two pytest failures in tests/test_ai_static.py. Both expect a specific finding title from scan_ai_static() that the scanner doesn't produce. Decide which is right (scanner or tests) and fix.

REQUIRED READING:
1. tests/test_ai_static.py — full file, both failing tests in context (test_ai_static_detects_risky_mcp_json_settings, test_ai_static_detects_risky_agent_text)
2. src/security_observatory/ai_static.py (or wherever scan_ai_static is defined — `grep -r "def scan_ai_static" src/`) — the scanner function
3. .adx/risks.json — confirm AI-agent risk surface is in scope for this scanner
4. docs/agent-lab.md — the AI-agent risk surface DëvSec is meant to catch
5. `git log --oneline src/security_observatory/ai_static.py` — recent commits to the scanner that might explain a regression
6. `git log --oneline tests/test_ai_static.py` — recent commits to the tests that might explain stale expectations

OUTPUT:
- Determine the right fix:
  · If the scanner SHOULD catch these patterns but doesn't (regression): update scan_ai_static to detect "approval_mode: never" and "autoApprove": ["*"] patterns. Produce the finding title the tests expect.
  · If the scanner's current behavior is correct (the project's stance on what counts as risky shifted): update the tests to match — but only if the scanner has a real replacement signal that catches the underlying risk via a different title or pattern. Don't delete the tests' intent just because the scanner moved on.
- Run `uv run pytest tests/test_ai_static.py -v` locally; both tests must pass
- Run full `uv run pytest` to confirm no regressions in other tests
- Push and confirm Verify CI's Python job goes green

OPEN QUESTIONS:
- The tests' intent is clear: DëvSec should flag agent configs that enable broad auto-approval. Is the scanner's current silence a real bug, or did the security model shift? Read the recent commits for the actual reason before deciding.
- If the scanner needs new pattern matching, what's the right severity? The tests probably reveal the expected severity via assertion on the finding object; honor it.
- Are there OTHER AI-agent risk patterns the scanner should catch but currently doesn't? Don't expand scope here, but surface them as a separate observation if you spot them.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the Post-launch polish for DëvSec campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/post-launch-polish.md
Campaign: campaigns/post-launch-polish.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff that the criteria actually landed. Don't trust step receipts — read the diff.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas.

Be honest. Lean. APPROVED if every step's acceptance criteria landed and there are no cross-step regressions. NEEDS WORK if any step cut corners or a primitive was bypassed.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.7 with Extra High thinking
(Your call — both are acceptable for this kind of cross-file review.)
```

**Verdict-to-action mapping:**

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign"). Campaign is done.
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick the checkbox until APPROVED.
