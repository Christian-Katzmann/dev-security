# 5 · DëvSec dashboard coherence — fix the lying numbers, lock the vocabulary, unify the control room

> Makes DëvSec's dashboard tell the truth about what you're looking at. Today different parts of the same page count things differently and use the same words for different stuff — this campaign fixes the numbers, the words, and the buttons so what you see matches what you actually mean.

## Scope

Structural redesign of the DëvSec dashboard to make it trustworthy and ergonomic. Six phases, sequenced from cheap visible wins to load-bearing structural decisions:

1. **Phase 0** — Salvage the in-session install-button work + bug-bash quick wins. Visible improvements ship in week one.
2. **Phase 1** — Lock the vocabulary system-wide. "Severity" words reserved for security severity; "findings" disambiguated into **Cases** (grouped, user-visible) and **Raw findings** (underlying scanner items).
3. **Phase 2** — Two-mode dashboard model (All Repos / Specific repo) as a first-class state machine, following Linear / Stripe / Vercel / GitHub conventions.
4. **Phase 3** — KPI scope discipline. Every KPI on a target-scoped view uses `scopedSummary`; cross-repo KPIs labeled explicitly. Resolves the "Overview lies with consistent-looking numbers" bug.
5. **Phase 4** — Findings master-detail composition. Row-click feedback works; detail card is visible without scrolling 800px.
6. **Phase 5** — Scan controls promoted to Overview. The "control room" pattern currently buried in Verification becomes the home page's daily-driver.

Done when: a user lands on the dashboard, sees clearly which scope they're in (All Repos vs. their selected repo), can read every KPI without parsing different vocabularies for the same word, can click a finding row and see what they clicked, can run a scan from the home page, and can install a missing Homebrew-method tool from inside the app. Daily-driver UX is trustworthy; structural foundation is in place for campaign #4 (rotation integration) to add new dashboard surface without inheriting old bugs.

## Context (locked decisions)

- **Campaign number `5 ·` in the sequence**, runs **after #2 (devsec-agent-doctrine) lands** and **before #3 (devsec-rotation-foundation)**. Hard reason: #4 (devsec-rotation-integration) will add new dashboard surface (Rotate buttons, status cards, secrets-case affordances). #4 must build against the fixed dashboard structure, not the broken one. Soft reason: #5's UI copy aligns to #2's locked voice doctrine first time, avoiding rewrite.
- **Branch: `devsec-dashboard-coherence`** off `main`. Each phase lands as a reviewable batch. Merge to `main` when Final review is APPROVED. Rationale: six phases of dashboard-wide work would dwarf any single review.
- **Out of scope (deferred to campaign #6 `devsec-catalog-setup-flow`)**: per-tool branding (logos + accent colors), Setup-in-tool with macOS Keychain credential storage, catalog schema additions (`setup_kind` / `setup_requirement` / `setup_probe`), typed `SetupCard` component, Connect-GitHub OAuth/PAT flow. These belong in their own campaign focused on Tool Catalog as a real surface.
- **In-session work to salvage**: a working Homebrew install endpoint (`POST /api/tools/install-via-pkg`) plus frontend wire-up was built in the planning session and tested live (legitify installed cleanly, state flipped from `missing` → `not-configured`, "Installed — needs setup" eyebrow renders). Code is uncommitted. Phase 0 verifies and commits this rather than rebuilding it.
- **Two-mode model is non-negotiable**. All Repos vs. Specific repo is the cleanest available pattern (Linear, Stripe, Vercel, GitHub) and retires both the "lying numbers" Step 7 and the "target-scope inconsistency" Step 9 issues in one decision.
- **Vocabulary lock is system-wide, not just UI**. Severity reservations and Cases-vs-Raw-findings disambiguation apply to UI copy, CLI output, JSON API field names where renaming is non-breaking, docs, and AI-handoff copy. One word, one meaning, everywhere.
- **README is part of the surface**. Tab-name drift (Findings vs. "What Needs Attention", missing tabs Code/Deps/Infra/MCP) lives in README.md and the actual `App.tsx:210` nav. Both are surfaces; both get fixed.
- **Findings master-detail keeps existing `CaseDetailCard` component**. Composition is broken, not the card itself. Implementation chooses between sticky right panel / sheet-modal / inline-expand based on what fits the existing layout best — decision deferred to Phase 4's owner.
- **Scan controls on Overview do not delete the Verification tab**. Verification stays as the deeper diagnostic view (which scanners failed, why); Overview gets the daily-driver Run / latest-scan-status / scanner-inventory surface.
- **Data-migration decision**: `besk-ftigelse.dk` and `obedai-learning-app` have raw findings from 2026-05-11 scans but 0 cases (case-building added later). Phase 3 keeps their raw evidence visible, labels them as pre-cases scans, and excludes them from case KPIs until a fresh scan can build cases. No automatic rescan on app open.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 0 — Salvage and bug bash

- [x] Step 0.1 — Verify, polish, and commit the in-session Homebrew install button
- [x] Step 0.2 — Bug-bash sweep (visual and information quick wins)

### Phase 1 — Vocabulary lock

- [x] Step 1.1 — Lock severity and findings/cases vocabulary across UI, CLI, docs, AI handoffs

### Phase 2 — Two-mode dashboard model

- [x] Step 2.1 — Per-view mode classification and repo-selector state machine
- [x] Step 2.2 — Wire the mode through Overview, Findings, Activity, Reports

### Phase 3 — KPI scope discipline

- [x] Step 3.1 — Every KPI uses `scopedSummary`; cross-repo KPIs labeled explicitly; decide handling of pre-cases scans

### Phase 4 — Findings master-detail composition

- [x] Step 4.1 — Make the row-click feedback visible (sticky panel / sheet / inline expand) — keep `CaseDetailCard` component

### Phase 5 — Scan controls promoted to Overview

- [x] Step 5.1 — Move the Verification-style scan-completion + Run controls to Overview; keep Verification as deeper diagnostic

### Close

- [x] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 0.1 — Verify, polish, and commit the in-session Homebrew install button

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 0.2

A working Homebrew install endpoint was built in the planning session and tested live (legitify installed cleanly, state flipped). The code is uncommitted in the working tree. This step verifies the diff is clean, the guardrails actually fire, the tests still pass, and commits with a clear message — then opens a PR against the `devsec-dashboard-coherence` branch.

```text
SCOPE: Verify the in-session Homebrew install button work, polish anything rough, and commit as the first PR on the devsec-dashboard-coherence branch.

REQUIRED READING:
1. campaigns/devsec-dashboard-coherence.md (this campaign's Context block)
2. src/security_observatory/dashboard_server.py — the new `install_via_homebrew` method (~lines 1510–1580) and the route registration (~line 1397)
3. dashboard-ui/src/components/catalog/useCatalogData.ts — new `installViaHomebrew()` function
4. dashboard-ui/src/components/catalog/catalogHelpers.tsx — new `canInstallViaHomebrew()` helper + updated `catalogCardAction()`
5. dashboard-ui/src/components/catalog/CatalogToolPage.tsx — updated `isAlreadyInstalled` (now includes `not-configured`), new "Installed — needs setup." eyebrow, button wires to `installViaHomebrew()` for missing+homebrew tools
6. dashboard-ui/src/components/catalog/CatalogBrowse.tsx — grid now sorts missing → top → coming-soon
7. /tmp/devsec-walkthrough-2026-05-24.md — Step 6e for full notes on what was built and tested

OUTPUT:
- New branch `devsec-dashboard-coherence` off main (if not already created)
- One clean commit (or split into 2: backend + frontend) on that branch
- Optionally: a brief CHANGELOG.md entry noting the new endpoint and the UI affordance
- Run pytest + the dashboard build before committing — both should pass

OPEN QUESTIONS:
- Does the existing tests/test_dashboard_server.py have coverage for the new endpoint? If not, add three tests (the same three guardrails I tested manually: missing confirm flag, non-homebrew tool, unknown tool) — pattern matches the existing managed-install tests.
- Is the binary-name regex `^[a-z0-9][a-z0-9._-]*$` strict enough, or should it also forbid leading hyphens / require a min length? Surface a recommendation, don't silently change it.
- Should we extend `install_via_homebrew` to also handle method=`uv tool` while we're here? Probably no (out of scope; defer to the Phase 0 / campaign #6 split), but flag if it's a 5-line addition.
- Anything else uncommitted in dashboard_server.py from earlier work that should ride along, or should the commit be strictly the install-button work?
```

## Step 0.2 — Bug-bash sweep (visual and information quick wins)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 0.1

Nine small bugs identified during the walkthrough, all in the dashboard or its docs. Bundle them as one bug-bash PR (or split into a visual batch + an information batch if that's cleaner). The win is ship-now: every one of these is friction Christian feels daily.

```text
SCOPE: Fix nine small bugs identified in the walkthrough. Bundle as one bug-bash PR on the devsec-dashboard-coherence branch (or split into visual vs information batches if cleaner). Land all of them in one sitting.

REQUIRED READING:
1. /tmp/devsec-walkthrough-2026-05-24.md — Steps 1, 3, 4, 5, 5b, 5c, 5d, 6b, 7, 8 (the bugs are scattered across these)
2. dashboard-ui/src/App.tsx — the central nav (line 210), severity color map (lines 267–268), KPI rendering (around the Overview "Open findings" card), `runFullCheck` (line 654)
3. dashboard-ui/src/components/CaseDetailCard.tsx — the "Case" row that shows raw UUID
4. README.md — §Dashboard with stale tab names
5. src/security_observatory/cli.py — `doctor` output (search for "missing" / install hints)

BUGS TO FIX:
1. Project selector chevron click target — only the project name is clickable in the Overview selector; the chevron icon isn't. Expand click target to cover the whole control.
2. Severity color collision — App.tsx:267–268 defines `crit: bg #e8c6c0` and `high: bg #ecc9b7`, both muted terracotta only ~5% lightness apart. Make Critical visually louder (deeper red or different saturation). Confirm with a side-by-side comparison after change.
3. "Open findings 500" KPI — 500 is a hard display cap presented as the real total, with "548 non-low" as small subtext. Either remove the cap or label clearly ("500+ of 548 non-low"). Whichever you pick, no surprises.
4. Recent Activity component on Overview — the graph + list don't cohere. Lighter pass: align the graph's tick density to the list rows, drop any unused legend artifacts. (Full redesign is out of scope; this is a polish pass.)
5. Doctor output — separate "missing-but-optional" (legitify, malcontent) from "missing-and-needed". Today both render identically; users with no context assume a broken install. Suggested approach: a "Missing (optional)" group with a one-line explanation.
6. README ↔ UI tab name parity — README §Dashboard lists tabs Code/Dependencies/Infrastructure/MCP that don't exist and uses "What Needs Attention" instead of "Findings". Rewrite the section against the actual nav (Overview, Findings, Honey keys, Tool Catalog, Agent Lab, Recovery playbooks, Verification, Activity, Reports, Settings — from App.tsx:210).
7. Per-case "AI prompt" button routes to whole-repo handoff — clicking it on one row currently opens the all-87-cases AI brief. Fix: per-row button → per-case markdown copied to clipboard (with a toast). Whole-repo prompt stays available as a global header/button (likely on the Findings page top bar). Don't conflate per-row and whole-repo intent.
8. Case detail "Case" row shows raw UUID — `case-8463ade7eb3b1b07` leaks internal id with no user value. Hide the row, or replace the value with the display id used in the table (e.g. `F-1B07`).
9. No top-level Quick scan button — toolbar only has "Run all" which immediately fires a full scan. Add a dropdown ("Run all / Run quick / Choose…") or a separate "Run scan" entry that opens the chooser without auto-firing. Quick scan should be a one-click option, not a chooser-buried setting.

OUTPUT:
- One PR (or 2) on the devsec-dashboard-coherence branch, all 9 bugs fixed
- Visual regression check: take screenshots of Overview, Findings, Tool Catalog, doctor output before and after — eyeball that nothing else broke
- All pytest tests pass; dashboard build succeeds

OPEN QUESTIONS:
- Bug 4 (Recent Activity) might want a fuller redesign — if it's bigger than a polish pass, flag and defer to Phase 4 or a separate ticket. Don't sink the sweep on this one.
- Bug 7 (per-case AI prompt) — what's the catalog of cases that already have per-case markdown generated, and is that something that already exists server-side or does it need a new endpoint? Surface the answer; don't ship a half-fix.
- Bug 9 — confirm whether `runFullCheck` (App.tsx:654) is the only entry point that fires a scan, or if there are others to update.
```

## Step 1.1 — Lock severity and findings/cases vocabulary across UI, CLI, docs, AI handoffs

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Two vocabulary collisions to lock system-wide. This step is cross-cutting on purpose — the whole point is one word, one meaning, everywhere. Touch UI copy, CLI output, JSON API field names (where renaming is non-breaking), docs, AI-handoff template copy.

```text
SCOPE: System-wide vocabulary lock. Two collisions to resolve, applied to every surface (UI, CLI, docs, AI handoff).

REQUIRED READING:
1. /tmp/devsec-walkthrough-2026-05-24.md — Steps 6b, 7, plus the "Principle (system-wide) — severity vocabulary is reserved" block
2. dashboard-ui/src/App.tsx — severity meta (lines 264–270), every place these words render
3. dashboard-ui/src/components/CaseDetailCard.tsx, FindingsView.tsx, OverviewView, catalog/* — all UI surfaces using "Critical / Elevated / Warning / Low" or "findings"
4. src/security_observatory/cli.py — CLI output uses these words too
5. src/security_observatory/cases.py — the normalized report's `severity` and `findings` fields (canonical model)
6. README.md, docs/*.md — text references
7. src/security_observatory/dashboard/ai-handoff/ (or wherever the AI handoff markdown template lives) — template copy

LOCKED VOCAB:
- **Severity words reserved**: `critical / elevated / warning / low` ONLY for security severity. Never for UI state (install state, sync state, validation, empty, pending). For UI state, use neutral additive verbs: "Not installed", "Add", "Pending", "Empty", "Connect", "+ Install". Same goes for the red/orange palette and ⚠️ icons — those belong to severity, full stop.
- **Findings vs cases**: pick **Cases** for the user-visible grouped concept (today: 87 cases for de-v-security) and **Raw findings** (or **Scanner evidence**) for the underlying deduped scanner items (today: 552 across all repos). One word, one meaning, everywhere.

OUTPUT:
- One PR on the devsec-dashboard-coherence branch
- A short docs/vocabulary.md (or section in an existing doc) capturing the locked terms so future contributors don't drift
- Audit table in the PR description: every surface checked, every word changed, every rename and its before/after
- Backwards-compatibility note for any API field renames (if the JSON `findings` field needs to become `cases` somewhere, that's a breaking change for any external consumers — flag explicitly and decide whether to keep an alias)

OPEN QUESTIONS:
- Are there external consumers of the JSON API today? If yes, what's our compatibility policy (keep aliases for one release, deprecate via warning, etc.)?
- Does the MCP server's tool names (`cases`, `findings`, `scan_history`) need to change too? Probably yes for consistency, but it's an MCP contract change — flag explicitly.
- The campaign-level handoff page already uses "cases" and "findings" both — confirm what the doctrine campaign (#2) has settled on for copy register; align to it first time.
```

## Step 2.1 — Per-view mode classification and repo-selector state machine

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The two-mode model needs two pieces of infrastructure before any view starts using it: a per-view classification (which mode does each tab support?) and a repo-selector that surfaces mode as a first-class state, not just "is a target picked or not."

```text
SCOPE: Stand up the two-mode dashboard model's infrastructure. Classify each existing view by which mode it supports. Refactor the repo-selector so mode is a first-class state, not an emergent property of "target is null."

REQUIRED READING:
1. /tmp/devsec-walkthrough-2026-05-24.md — Steps 7, 9, 10 (the diagnosis and decision)
2. dashboard-ui/src/App.tsx — current `target` state (search for `TargetSelection`, `selectTarget`, `targetLabel`), nav definition (line 210), `scopedSummary` derivation
3. dashboard-ui/src/components/Sidebar.tsx (or wherever the repo selector lives) — current UX
4. dashboard-ui/src/dashboardData.ts — how `scopedSummary` is computed from `summary` and `target`

LOCKED MODEL:
- Two explicit modes: **All Repos** (default on app open) and **Specific repo**.
- Per-view classification:
  - **Both modes**: Overview, Findings, Activity, Reports
  - **Per-repo only**: Honey Keys (decoys are repo-scoped), in-repo case detail
  - **All-repos / global only**: Tool Catalog, Settings, Agent Lab proposals (probably — confirm)
- Selecting a specific repo switches to Specific-repo mode. A new "All repos" entry in the selector switches back. No more "no target" gray state.

OUTPUT:
- Refactored target selector exposing `mode: 'all-repos' | 'repo'` + (when mode=='repo') the chosen repo id
- A `viewsByMode` registry naming which view supports which mode
- Sidebar shows / hides nav items based on the current mode (per-repo-only views grey out / hide / explain when in All Repos mode)
- Default app-open state = All Repos mode
- This step is structural; Step 2.2 wires the mode through the actual views

OPEN QUESTIONS:
- For per-repo-only views (Honey Keys), what's the UX in All Repos mode? Hide entirely, show with a "pick a repo to see Honey Keys" empty state, or show an aggregate ("12 Honey Keys across 3 repos, click a repo to see details")?
- For all-repos-only views (Tool Catalog), should the per-repo mode hide them or keep them visible (since the catalog IS global)? Recommend keep visible; surface it.
- Is "Agent Lab proposals" truly global or is it actually per-repo? Confirm against the existing data shape before classifying.
```

## Step 2.2 — Wire the mode through Overview, Findings, Activity, Reports

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Take the infrastructure from Step 2.1 and actually thread it through the four views that support both modes. Each view renders the right shape per mode: aggregated/comparison in All Repos mode, single-repo focused in Specific-repo mode.

```text
SCOPE: Make Overview, Findings, Activity, and Reports render correctly in both modes. Each view chooses its data shape (aggregated vs. single-repo) based on the current mode and labels the scope explicitly.

REQUIRED READING:
1. campaigns/devsec-dashboard-coherence.md — Phase 2 + 3 context
2. dashboard-ui/src/App.tsx — `OverviewView`, `FindingsView`, `ActivityView`, `ReportsView`, the refactored target selector from Step 2.1
3. dashboard-ui/src/dashboardData.ts — summary derivations
4. Step 2.1's PR (the infrastructure)

PER-VIEW SHAPE:
- **Overview** — All Repos mode: aggregated KPIs labeled "All repos", a per-repo comparison strip (which repo is worst / posture trend per repo). Specific-repo mode: that repo's KPIs only, labeled with the repo name.
- **Findings** — All Repos mode: cases across all repos, with a repo column in the table. Specific-repo mode: cases for that repo, no repo column.
- **Activity** — All Repos mode: combined activity timeline labeled by repo. Specific-repo mode: that repo's activity only.
- **Reports** — All Repos mode: list of all repos' latest reports. Specific-repo mode: that repo's report history.

OUTPUT:
- Each of the four views updated to read `mode` and render the correct shape
- Every KPI / metric / chart on these views carries an explicit scope label ("All repos" or the repo name)
- Pairs with Step 3.1, which deepens the scope discipline at the data layer

OPEN QUESTIONS:
- For the Findings page in All Repos mode, the repo column needs a sort/filter. Quick implementation: surface the existing per-repo filter chips. Worth it?
- Activity timeline aggregation might be expensive if there are many repos — is there a pagination / day-bucket strategy that makes sense, or is it always small enough?
```

## Step 3.1 — Every KPI uses `scopedSummary`; cross-repo KPIs labeled explicitly; decide handling of pre-cases scans

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Deepens the scope discipline. With the mode infrastructure (Step 2.1) and view wiring (Step 2.2) in place, every individual KPI now has to use the right summary source. Plus: decide what to do about old scans that have raw findings but no cases.

```text
SCOPE: Every KPI on a target-scoped view uses scopedSummary, not the full summary. Cross-repo KPIs are labeled explicitly. Also: decide handling of pre-cases scans (besk-ftigelse.dk / obedai-learning-app) that show raw findings but 0 cases.

REQUIRED READING:
1. /tmp/devsec-walkthrough-2026-05-24.md — Steps 7, 9 (the diagnosis with the specific lying-numbers table)
2. dashboard-ui/src/App.tsx — every KPI block (search for `KpiCard`, `MetricBlock`, severity bars, posture trend)
3. dashboard-ui/src/dashboardData.ts — `scopedSummary` derivation; check whether it actually filters everything it should
4. ~/.security-observatory/reports/besk-ftigelse.dk/ and obedai-learning-app/ — old scans with 0 cases

KPIs TO AUDIT (and likely fix):
- "Open findings" KPI on Overview — currently sums all repos
- Severity bar (16/166/366/4) — currently sums all repos
- "Honey keys armed" tile — confirm scoping
- "Tool Catalog 12/15" tile — actually global, should stay labeled "across all repos"
- Posture trend chart — currently aggregated across all repos
- Anything else that looks like a number

DECISION NEEDED — pre-cases scans:
- besk-ftigelse.dk has 371 raw findings / 0 cases (May 11 scan, predates case-building)
- obedai-learning-app has 53 / 0
- Today: their raw findings inflate the Overview KPI; their cases are silently 0
- Options: (a) auto-rescan on app open if a repo's scan predates case-building, (b) drop pre-cases scans from Overview KPIs entirely, (c) label them as "pre-cases scan, rescan to get cases"
- Recommend one and ship it.

OUTPUT:
- One PR with every KPI audited and fixed
- Audit table in the PR description: KPI name, current scope, new scope, scope label
- Pre-cases scan decision documented in the campaign Context block (update inline) and applied to the codebase

OPEN QUESTIONS:
- Is `scopedSummary` actually filtering everything it should? If certain fields slip through (e.g. `posture_30d` always pulls from the full summary), that's the root cause to fix instead of patching each KPI.
- Should "across all repos" labels live as a small badge / pill that's visually consistent, or just as text? Recommend a pill — easier to scan.
```

## Step 4.1 — Make the row-click feedback visible (sticky panel / sheet / inline expand) — keep `CaseDetailCard` component

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The Findings table's row-click already works — it updates a `<CaseDetailCard>` 800px below the fold. The component itself is clean. Composition is broken. Pick one of three patterns and ship.

```text
SCOPE: Fix Findings page composition so a row-click produces visible feedback. Keep the existing CaseDetailCard component; change how it's reached.

REQUIRED READING:
1. /tmp/devsec-walkthrough-2026-05-24.md — Steps 5, 5b, 5c (the full diagnosis with file:line refs)
2. dashboard-ui/src/App.tsx — `FindingsView` (lines 1194–1257), `FindingsTable` (lines 1976–1996), the CaseDetailCard render site (line 1244)
3. dashboard-ui/src/components/CaseDetailCard.tsx — the existing detail card (DON'T rewrite this; it's fine)

THREE PATTERNS TO PICK FROM:
- **(a) Sticky right-side panel** — table on the left, sticky CaseDetailCard on the right. Master-detail. Most "control room" feeling. Needs decent width; may break on narrow viewports.
- **(b) Click row → opens sheet / modal** — table fills the viewport; click opens a sheet/drawer overlay with the CaseDetailCard. Works on any width. Modal feel may be heavier than the rest of the app.
- **(c) Inline expand row under header** — clicked row expands inline with CaseDetailCard rendered between table rows. Most lightweight. Doesn't break the existing layout.
- Recommend (a) for desktop, (c) as a fallback for narrow viewports. Don't ship (b) unless (a) and (c) are both problematic — sheet/modal disrupts flow more than the other two.

OUTPUT:
- Findings page redesigned per the chosen pattern
- Row-click produces visible feedback: row highlights, detail card visible without scrolling
- CaseDetailCard component unchanged
- Visual regression check: walk through 5+ cases (different severities, different categories) and confirm the detail card renders right for each

OPEN QUESTIONS:
- For pattern (a), what's the minimum width threshold below which we fall back to (c)? Recommend something like ≥1280px for sticky panel, otherwise inline expand.
- Does the detail card on the Findings page have the same triage buttons (Verify / False positive / Accept risk / Mark fixed) as it does today? Confirm parity.
- For multiple-case selection (if it exists or should exist), how does the panel handle it? Recommend: single-select only for v1; multi-select is its own scope.
```

## Step 5.1 — Move the Verification-style scan-completion + Run controls to Overview; keep Verification as deeper diagnostic

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The Verification tab has the actual "control room" shape — Health / Saved Issues / Missing Checks / Duration KPIs, checks-that-ran list, Run checks button. That pattern belongs on Overview so a user never has to navigate sub-tabs to trigger or monitor a scan.

```text
SCOPE: Promote the scan-control surface from Verification to Overview. Keep Verification as the deeper diagnostic view.

REQUIRED READING:
1. /tmp/devsec-walkthrough-2026-05-24.md — Step 11 (the diagnosis)
2. dashboard-ui/src/App.tsx — `VerificationView` (around line 1563), the scan-completion panel it renders, `runFullCheck` + `runCheck` + `RunCheckSheet`, current `OverviewView`
3. Step 0.2's Bug 9 fix (toolbar Run controls) — coordinates with this work

OVERVIEW GETS (daily-driver scan control):
- Latest scan status (Health / Saved Issues / Missing Checks / Duration)
- Scanner inventory at a glance (which ran, which failed, which skipped)
- Run controls (Quick / Choose checks / Run all)
- "View full diagnostic" link to the Verification tab

VERIFICATION KEEPS (deeper diagnostic):
- Why a scanner failed (error logs, exit codes, missing-dep diagnosis)
- "Cannot prove" honest scope statements
- Detailed scanner inventory with per-scanner config and history

OUTPUT:
- Overview redesigned with the scan-control surface promoted
- Verification tab simplified to focus on diagnostic depth (drop the duplicate KPIs that now live on Overview)
- All Repos mode: Overview shows latest scan per-repo as a strip + a "Run scans on all repos" affordance
- Specific-repo mode: Overview shows that repo's scan controls + history

OPEN QUESTIONS:
- The Verification tab has a count badge in the sidebar (number of missing/erroring scanners). Does it stay, or move to a notification dot on Overview's scan section?
- Should Run-all-repos in All Repos mode actually fan out scans in parallel, or queue them one at a time? Recommend parallel by default with a fan-out limit (e.g. 3 concurrent) so a 20-repo developer doesn't get a 4-hour serial run.
- Coordinates with Step 0.2's Bug 9 (toolbar Run controls) — confirm there's no duplicate Run affordance after both land.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

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

Be honest. Lean. APPROVED if every step's acceptance criteria landed and there are no cross-step regressions. NEEDS WORK if any step cut corners or a primitive was bypassed.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.7 with Extra High thinking
(Your call — both are acceptable for this kind of cross-file review.)
```

**Verdict-to-action mapping:**

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign"). Merge the `devsec-dashboard-coherence` branch into `main`. Campaign is done.
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick the checkbox until APPROVED.
