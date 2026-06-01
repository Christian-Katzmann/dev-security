# DëvSec Stage D — Six Lenses to Green

> After a big cleanup, six parts of the DëvSec security app are "almost great" but not quite. This plan finishes the job: tidy the messy big files, make the app actually tell you when it rescued your data, polish the warning and loading screens, finish a half-done style cleanup, and make the written notes match the real code — so every part reaches top marks.

## Scope

The `devsec-industry-grade` campaign's post-run re-sweep graded all 17 health lenses; 11 reached Green but **6 stalled at Green/Yellow**: architecture, error-edge-state, behavioral-ux (the headline lens), design-system-accessibility, documentation, and ai-maintainability. Each carries a small, specific, evidence-backed residual — not a missing feature, but an unfinished edge. This campaign closes exactly those residuals and nothing more. **Done = a re-sweep of these six lenses returns Green with code evidence, both non-negotiables (no default-path egress; no forced high/critical suppression) remain intact, and `uv run pytest` / `npm run build` / `npm run lint` / `vitest` stay green.** It does not add features, decompose `App.tsx`, or reopen anything already Green.

## Context (locked decisions)

- **Repo:** `/Users/christiankatzmann/Dev/Projects/dëv-security` (Security Observatory / DëvSec). Local git checkout; commit per step to `main`, matching the prior three stages (no separate branch).
- **Source of truth for the residuals:** the post-campaign re-sweep completed in the session that authored this plan. The concrete file:line pointers are embedded in each step prompt, so a fresh session needs no chat history.
- **`App.tsx` decomposition (4,594 lines) is explicitly OUT of scope** — parked. Forcing a large React refactor here risks regressions and balloons the campaign; architecture Green is scoped to the Python residuals only.
- **No live rendered-browser pass in any step** — operating rules forbid launching the dashboard/server unattended. Crafted states are built and unit/axe-tested in code; the live keyboard/visual confirmation is the human Final-review gate.
- **Do not weaken the two non-negotiables** (`test_no_egress.py`, `test_dashboard_csrf.py`) or anything already Green. Use existing Mistglass tokens (`DESIGN.md`); severity is never signaled by color alone.
- **Verification is code-only:** `uv run pytest -q`, `cd dashboard-ui && npm run lint && npm run build && npx vitest run`. No servers, no scanners, no non-loopback listeners.

## Unattended execution contract

This campaign runs fully unattended via `/claude-automate` — a chain of headless `claude --print` sessions, guarded by a watchdog, with no human at the keyboard. Every step MUST honor this contract or the run can stall for hours:

- **No interactive input, ever.** No step may pause for a prompt, confirmation, login, or `[y/N]` — there is no TTY to answer it.
- **Servers bind `127.0.0.1` only — never `0.0.0.0`/LAN.** A non-loopback listener triggers the macOS firewall "accept incoming connections?" dialog, which no flag can suppress and which blocks the whole run until someone clicks it. Use `--host 127.0.0.1` / `HOST=127.0.0.1`.
- **No blocking GUI/OS dialog.** Don't trip first-run macOS permission panels (screen recording, accessibility, Automation, Full Disk Access) or Gatekeeper. Strip quarantine from any downloaded binary (`xattr -dr com.apple.quarantine`); prefer brew/npm/uv over ad-hoc downloads.
- **No interactive auth.** No `gh auth login`, `ghost login`, MitID, or MCP `authenticate` mid-run — any credential a step needs must already be in place before launch.
- **Keep writes under the repo / `~/Dev`.** Avoid `~/Desktop`, `~/Documents`, `~/Downloads` (they trip macOS privacy prompts) unless Full Disk Access is pre-granted to the launcher.
- **A blocker means `fail` loudly, never `wait`.** If a prerequisite is missing, call `claude-automate fail` with a one-line reason so the watchdog escalates — never hang waiting for a human.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Land the audited gains & sync the record

- [x] Step 1.1 — Commit the Stage D working tree (the clean base)
- [x] Step 1.2 — Sync the written record to the code (docs S-052 + .adx)

### Phase 2 — Shrink the architecture & lock the lifecycle seam

- [x] Step 2.1 — Lift rotation enrichment out of dashboard_server + break the catalog↔setup_runner cycle
- [x] Step 2.2 — Derive the case-decision CHECK from lifecycle + add test_lifecycle.py

### Phase 3 — Craft the missing states & finish the token sweep

- [x] Step 3.1 — Render the recovery notice + craft the failure/loading states
- [x] Step 3.2 — Finish the design-token sweep (S-054)
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Commit the Stage D working tree (the clean base)

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

The re-sweep graded the working tree as Green-capable, but the two fixes that earn that grade — the `React.lazy` code-split (S-029) and the `AddRepoDialog` focus-trap migration (S-041) — are uncommitted. `HEAD` does not yet contain them. This step makes `HEAD` equal the audited tree so every later step builds on solid ground. No source changes — commit as-is, then verify the suite is still green.

```text
SCOPE: Commit the already-audited, uncommitted Stage D edits so HEAD matches the graded working tree. No behavior change.
REQUIRED READING:
1. The working tree itself — `git status` and `git diff`
2. plans/active/devsec-industry-grade/receipts/stage-d-patch-campaign.md (what these edits are: S-029 code-split, S-041 AddRepoDialog focus-trap, AGENTS.md route/tab memory)
WORK: Stage and commit, in one commit, the Stage D edits — dashboard-ui/src/App.tsx, dashboard-ui/src/components/Dialog.tsx, dashboard-ui/src/index.css, src/security_observatory/dashboard/index.html, AGENTS.md, and the new dashboard-ui/src/AddRepoDialog.a11y.test.tsx — plus the stage-d-patch-campaign.md receipt. Do NOT modify any source; commit exactly what is on disk.
OUTPUT: one commit on main; working tree clean for those paths.
ACCEPTANCE: `cd dashboard-ui && npm run lint && npm run build && npx vitest run` all green (build ~438 kB, no >500 kB chunk warning, 28 tests pass); `uv run pytest -q` → 535 passed.
OPEN QUESTIONS: campaigns/devsec-stage-c-foundations-truth.md is also modified — is it a real edit to keep or transient campaign-automation bookkeeping? Surface it; do not silently sweep it into this commit unless it is clearly intended.
FORWARD SWEEP: before checking this step off, skim the remaining step prompts. If committing surfaced anything that moves a path or assumption a later step leans on, make a surgical edit there. A quick sweep, not a rewrite.
```

## Step 1.2 — Sync the written record to the code (docs S-052 + .adx)

Model: Opus 4.8 · High / GPT-5.5 · Extra High
Parallel: NO

Two lenses are held at Green/Yellow purely by stale written records, not by code defects. Documentation: the honey-key Guard Map binds each safety claim to a real guard, but its `dashboard_server.py` line numbers drifted ~50 lines — an auditor following the doc lands on the wrong code. ai-maintainability: the `.adx` module map never learned about the campaign's new split modules, and it cites a stale test count. Close both and these two lenses go Green.

```text
SCOPE: Make the written record match the code. (a) docs/honey-keys.md Guard Map line citations drifted; (b) .adx omits the new split modules and cites a stale pytest count.
REQUIRED READING:
1. docs/honey-keys.md — the Guard Map table (~lines 43-46)
2. src/security_observatory/dashboard_server.py — the honey-key insert guards: relative_to-escape, exists()→409, different-repo→400, IntegrityError→409 (currently near lines 2725, 2816, 2824, 2839; the doc wrongly cites 2675/2765/2772/2788)
3. .adx/modules/index.json and .adx/modules/dashboard-server.md
4. .adx/recovery.md (~line 26) and .adx/verification.json (~line 40) — the "524 passed" claim
5. README.md Usage section and docs/cli-security-surface.md
WORK:
- Repoint the honey-keys.md Guard Map citations to the real guard lines, and make them drift-resistant: cite each guard by its quoted message or symbol rather than a bare line number, OR add a tiny test that fails if a cited line stops containing the named guard. The artifact's whole purpose is auditable line-matching — it must not carry the drift it was built to eliminate.
- Register the campaign's new modules in .adx/modules/index.json: scan_orchestrator.py, dashboard_payload.py, dashboard_pages.py, lifecycle.py — each with key_file paths that exist on disk; update the dashboard-server module entry so a cold-reading agent learns the split exists. Match the existing module-entry convention (incl. any modules/*.md intro files).
- Update the cited pytest count from 524 to the current count in .adx/recovery.md and .adx/verification.json; re-stamp last_verified.
- Surface docs/cli-security-surface.md prominently in the README Usage section (a real cross-link, not one buried line).
OUTPUT: corrected docs + .adx; committed.
ACCEPTANCE: every dashboard_server.py line cited in honey-keys.md resolves to its named guard (or the new drift-guard test passes); each .adx JSON parses (`python3 -c "import json; json.load(open(p))"`); grep finds scan_orchestrator/dashboard_payload/dashboard_pages/lifecycle in .adx; the cited test count equals `uv run pytest -q` (currently 535).
OPEN QUESTIONS: per-module modules/*.md intro vs index.json-only — follow whatever the existing entries do. Remember: a locked decision says don't touch anything already Green — keep edits to the named docs/.adx surfaces.
FORWARD SWEEP: skim the remaining steps; if Step 2.x will move any module path you just registered, leave a note or pre-true the .adx entry so it stays accurate after the refactor.
```

## Step 2.1 — Lift rotation enrichment out of dashboard_server + break the catalog↔setup_runner cycle

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 2.2

Architecture is Green/Yellow because `dashboard_server.py` is still a ~3,750-line file and one import cycle survives. Both are structural, not behavioral. Lift the per-repo rotation-enrichment loop into the payload-assembly module so the server keeps only thin routes, and turn the lazy function-local `catalog → setup_runner` import into a clean top-level dependency. Surgical moves only — preserve behavior.

```text
SCOPE: Close the Python-side architecture residuals: shrink dashboard_server.py by moving the rotation-enrichment loop into the payload module, and break the catalog↔setup_runner import cycle. App.tsx is parked — do not touch it.
REQUIRED READING:
1. src/security_observatory/dashboard_server.py — the per-repo rotation-enrichment + secret-name inference loop (~lines 1394-1468, _build_summary_payload / assemble_summary_payload)
2. src/security_observatory/dashboard_payload.py — assemble_dashboard_payload (the cohesive home for that loop) and rotation_inference.py (already extracted secret inference)
3. src/security_observatory/catalog.py (~lines 688/695) — the lazy function-local `read_tool_config` import that forms the cycle
4. src/security_observatory/setup_runner.py — the other side of the cycle
WORK: Move the rotation-enrichment loop into dashboard_payload.py (or rotation_inference.py — pick the seam that keeps the payload module cohesive) so dashboard_server keeps only routing + dispatch. Restructure the catalog/setup_runner dependency so the import is clean and top-level (extract the shared piece if that's the cleanest break). Surgical, behavior-preserving moves — do not redesign the payload pipeline or rename public functions without need.
OUTPUT: smaller dashboard_server.py, no catalog↔setup_runner cycle; committed.
ACCEPTANCE: an import-cycle scan over src/security_observatory shows zero top-level cycles (catalog↔setup_runner gone); dashboard_server.py line count meaningfully lower; fast import check (`python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli; import security_observatory.dashboard_server; print('ok')"`) passes; `uv run pytest -q` → 535+ passed.
OPEN QUESTIONS: does the rotation enrichment belong in dashboard_payload.py or rotation_inference.py? Choose the seam that keeps the payload module cohesive and say why. LOCKED: do not expand scope to App.tsx or to files already Green — this scope-creep tag (locked-decision-deviation) has bitten a past campaign.
FORWARD SWEEP: if you moved a function a later step or the .adx map references, true up the reference (Step 1.2 registered these module paths — keep them accurate).
```

## Step 2.2 — Derive the case-decision CHECK from lifecycle + add test_lifecycle.py

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 2.1

The second architecture residual: the case state machine has a canonical home (`lifecycle.py`), but the `case_decisions` SQL `CHECK` constraint hand-copies the status list as a literal that can silently drift, and the new `can_transition` / `ALLOWED_TRANSITIONS` machine has no direct test. Make the SQL and the constant un-driftable, and pin the state machine with a test.

```text
SCOPE: Lock the lifecycle seam — one source of truth for case-decision statuses, plus a direct state-machine test.
REQUIRED READING:
1. src/security_observatory/lifecycle.py — DECISION_STATUSES, LIFECYCLE_STATES, ALLOWED_TRANSITIONS, can_transition, the lifecycle_state() verifying-beat fold
2. src/security_observatory/storage.py — the case_decisions CHECK literal (~line 280) and its migrated-table mirror (~line 758)
3. tests/test_storage_migrations.py — the existing migration-test style to match
WORK: Make the CHECK constraint's status set derive from lifecycle.DECISION_STATUSES so the SQL and the canonical set cannot diverge — generate the DDL fragment from the constant if SQLite takes it cleanly; if that is too invasive, instead add a test that fails the moment the SQL literal and lifecycle.DECISION_STATUSES disagree. Add tests/test_lifecycle.py covering can_transition / ALLOWED_TRANSITIONS (allowed transitions, rejected transitions, and the fixed-but-present → in_progress verifying-beat fold). This is schema-adjacent: do not alter existing rows or change migration behavior.
OUTPUT: drift-proof CHECK + tests/test_lifecycle.py; committed.
ACCEPTANCE: no hardcoded status list can silently diverge from lifecycle.DECISION_STATUSES (derived, or guarded by a drift-detecting test); tests/test_lifecycle.py exists; `uv run pytest tests/test_lifecycle.py tests/test_storage_migrations.py -v` green; full `uv run pytest -q` → 535+ passed.
OPEN QUESTIONS: can SQLite accept a generated CHECK string cleanly here, or is the drift-guard test the lower-risk move? Pick the safer one and note why.
FORWARD SWEEP: if you renamed or moved a lifecycle symbol, check Step 3.1 (which reads the RunError/lifecycle rendering) and the .adx lifecycle entry from Step 1.2 still hold.
```

## Step 3.1 — Render the recovery notice + craft the failure/loading states

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Two lenses share one frontend surface. error-edge-state: the backend emits a `history_recovery` notice when it self-heals a corrupt store, but the dashboard renders it nowhere — the rescue is silent on the product's main surface. behavioral-ux (headline): scan-failure feedback collapses to one undifferentiated string, and loading / first-fetch-failure states aren't crafted. Build all three in code with test coverage; the live visual confirmation is the human Final-review gate.

```text
SCOPE: Build the crafted states two lenses still miss. (a) Surface the backend history_recovery/quarantine notice on the dashboard. (b) Differentiate scan-failure feedback into crafted Mistglass cards and craft the loading / first-fetch states.
REQUIRED READING:
1. src/security_observatory/dashboard_server.py (~lines 1401-1415) — the payload.history_recovery shape (status, message, quarantined_path)
2. dashboard-ui/src/App.tsx — the OverviewView render, the RunError union (~line 299), and RunErrorNotice (~line 2004) routing missing-tool → "Open Verification"
3. dashboard-ui/src/dashboardData.ts — the summary payload type (needs a history_recovery field)
4. DESIGN.md — Mistglass empty/loading/error/first-run states and the §7.5 scan-failure treatment
WORK:
- When payload.history_recovery is present, render a calm, crafted Overview banner ("Your scan history could not be read and was quarantined; the previous database is preserved and a fresh history was started"), including the quarantined path. Type history_recovery in dashboardData.ts.
- Extend scan-failure feedback into crafted cards per failure kind per DESIGN.md §7.5 (scanner-missing → install/Open-Verification CTA, errored → retry, validation/failed → distinct copy), building on the existing RunError union rather than replacing it.
- Craft the loading and first-fetch-failure states so they read as designed, not bare text.
- Add vitest + jest-axe coverage for the recovery banner and the differentiated failure states.
OUTPUT: crafted states in App.tsx (+ a small component if warranted), typed payload, new vitest specs; committed.
ACCEPTANCE: grep finds history_recovery consumed in dashboard-ui/src; new vitest specs pass; `cd dashboard-ui && npm run lint && npm run build && npx vitest run` green; no severity/state signaled by color alone.
OPEN QUESTIONS: is there an existing Mistglass banner/notice component to reuse, or does this warrant one small new one? Prefer reuse. LOCKED: do not launch a server to "see" it — the live walk is the human gate; your job is the code + tests.
FORWARD SWEEP: if you added a payload field or component the final review will check, make sure the dashboardData.ts type and the server payload agree.
```

## Step 3.2 — Finish the design-token sweep (S-054)

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

The last design-system residual: the earlier token sweep was sampled, not finished. ~327 raw color literals remain in `index.css`, including raw `#6c1f1f` where the `--sev-crit-ink` token already exists, plus format-duplicate `rgba()` spellings of the same color. Finish it — no drift, no duplicate spellings — without changing a single rendered pixel.

```text
SCOPE: Complete the S-054 token sweep so design-system-accessibility reaches Green. Goal: no token has a raw twin, and no color has two spellings — not "zero literals for its own sake."
REQUIRED READING:
1. dashboard-ui/src/index.css — the :root token block (~lines 60-100) and the raw literals (raw #6c1f1f at ~3095/4950/7931; format-dupes like rgba(28,36,34,0.04) vs rgba(28, 36, 34, 0.04))
2. DESIGN.md — the Mistglass token palette (which literal maps to which token)
WORK: Replace raw literals with their existing token — start with #6c1f1f → var(--sev-crit-ink). Collapse format-duplicate rgba() values to one canonical spelling. For an alpha/shade that repeats 3+ times and has no token, add a clearly-named token and use it. Leave genuinely one-off values alone. The rendered output must not change.
OUTPUT: token-clean index.css; committed.
ACCEPTANCE: `grep -c '#6c1f1f' dashboard-ui/src/index.css` shows it only in the token definition; format-duplicate rgba spellings collapsed; raw-literal count meaningfully down from ~327; `cd dashboard-ui && npm run build` clean; computed colors unchanged on a spot-check of several rules.
OPEN QUESTIONS: any literal that repeats but has no obvious semantic name — park it in a short list in the commit message rather than inventing a misleading token name.
FORWARD SWEEP: if Step 3.1 added new state styles using raw colors, fold those into this sweep so the campaign doesn't reintroduce the drift it just removed.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the DëvSec Stage D — Six Lenses to Green campaign.

Plan: campaigns/devsec-stage-d-to-green.md
Campaign: /Users/christiankatzmann/Dev/Projects/dëv-security

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff that the criteria actually landed. Don't trust step receipts — read the diff.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas. Specifically confirm: the two non-negotiables still hold (test_no_egress.py and test_dashboard_csrf.py pass, no new default-path egress, no forced high/critical suppression); App.tsx was NOT decomposed (out of scope); and the six target lenses (architecture, error-edge-state, behavioral-ux, design-system-accessibility, documentation, ai-maintainability) each have their residual closed in code. If feasible, re-run the relevant *-health-forensic lenses (or the /devsec-resweep workflow) over current code and confirm each returns Green.

Be honest. Lean. APPROVED if every step's acceptance criteria landed, the suites are green (uv run pytest, npm run lint, npm run build, vitest), and there are no cross-step regressions. NEEDS WORK if any step cut corners or a primitive was bypassed.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.8 with Extra High thinking
(Your call — both are acceptable for this kind of cross-file review.)
```

**Verdict-to-action mapping:**

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign"). Campaign is done.
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick the checkbox until APPROVED.
