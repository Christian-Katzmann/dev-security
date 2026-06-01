# DëvSec Stage B — Experience & Power

> Autonomously deliver the UX headline (kill the raw `window.prompt` flows, lay the accessibility floor, unify severity language, finish the dead UI surfaces) and surface the dark local-first superpowers (case lifecycle, scan history/diff, code-fix dashboard). Closes with a post-repair behavioral-ux re-audit. Each batch is its own fresh session; a batch that can't pass its checks halts the chain.

## Context (locked decisions)

- **Branch:** all work lands on `main`.
- **Repo:** `/Users/christiankatzmann/Dev/Projects/dëv-security`.
- **Source of truth:** `reports/codebase-health/devsec-industry-grade/synthesis-2026-06-01.md` and `plans/active/devsec-industry-grade/`. Each step implements one batch's `context.md` + `acceptance.md`.
- **Mode:** fully unattended. Each step implements one batch, runs its Required Checks, writes a receipt, adaptively patches later steps if the code moved, then advances. A step that cannot make its checks pass calls `claude-automate fail` to halt rather than pass broken work forward.
- **Chain-after:** when Stage B's steps complete and finalize APPROVES, auto-launches `/Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-stage-c-foundations-truth.md` next.

## Progress checklist

### Phase 1 — Experience & Power
- [x] Step 1.1 — 06-replace-window-prompt
- [x] Step 1.2 — 07-accessibility-foundation
- [x] Step 1.3 — 08-severity-vocabulary
- [x] Step 1.4 — 09-finish-dead-ui-surfaces
- [x] Step 1.5 — 10-dashboard-frontend-perf
- [x] Step 1.6 — 11-case-lifecycle
- [x] Step 1.7 — 12-surface-scan-history-trends
- [x] Step 1.8 — 13-code-fix-dashboard-surface
- [x] Step 1.9 — post-repair behavioral-ux re-audit
- [x] Final review

## Step 1.1 — 06-replace-window-prompt

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage B — Experience & Power" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 06-replace-window-prompt (S-033, S-034) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: plans/active/devsec-industry-grade/batches/06-replace-window-prompt/context.md + acceptance.md; health_matrix.md; the synthesis rows S-033, S-034; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files before editing — earlier batches may have shifted line numbers. Trust the code.
3. Implement the smallest root-cause fix per acceptance.md (replace the raw window.prompt repo-add and note/incident-close dialogs with crafted inline Mistglass inputs per DESIGN.md). Senior quality; no broad unrelated refactors. Honor .adx/risks.json (no installers/scanners/dashboards/deploys/destructive/secret actions).
4. Run this batch's Required Checks from acceptance.md (npm run lint && build plus the named browser checks); every criterion needs before/after evidence.
5. Write a receipt (template: /Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md) to plans/active/devsec-industry-grade/receipts/06-replace-window-prompt.md.
6. SUCCESS — commit on `main` and finish. BLOCKED — `claude-automate fail --slug devsec-stage-b-experience-power --step 1.1 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read the later batches in this campaign (07–13); if your changes moved anything they reference (a shared component, a file path, a now-resolved residual), surgically update those batches' context.md/acceptance.md. Never change a batch's target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.2 — 07-accessibility-foundation

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage B — Experience & Power" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 07-accessibility-foundation (S-040, S-041, S-045, S-047) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: batches/07-accessibility-foundation/context.md + acceptance.md (under plans/active/devsec-industry-grade/); health_matrix.md; synthesis rows S-040, S-041, S-045, S-047; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files. Trust the code, not the cited line numbers.
3. Implement the smallest root-cause fix per acceptance.md: one global token-based :focus-visible ring on all controls, a shared Dialog primitive (focus-trap + Escape + focus restore) migrated across the 4 modals, a skip-to-content link, and a vitest + jest-axe smoke harness. Build S-047 (the a11y test harness) so it guards S-040/S-041. Senior quality. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (new vitest/axe run, lint, build); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/07-accessibility-foundation.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-b-experience-power --step 1.2 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 08–13; surgically update their context.md/acceptance.md if your new Dialog primitive / a11y harness changes how a later batch should implement (e.g. later modals should reuse the shared Dialog). Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.3 — 08-severity-vocabulary

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage B — Experience & Power" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 08-severity-vocabulary (S-019, S-032) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: batches/08-severity-vocabulary/context.md + acceptance.md (under plans/active/devsec-industry-grade/); health_matrix.md; synthesis rows S-019, S-032; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files. Trust the code.
3. Implement the smallest root-cause fix per acceptance.md: one shared severity→display map (high→Elevated, medium→Warning, …) consumed everywhere, plus the domain-language drift polish — and explicitly fix the unknown→medium confidence coercion so a case never reads more certain than its evidence (the confident-falsehood item). Senior quality. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md; every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/08-severity-vocabulary.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-b-experience-power --step 1.3 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 09–13; surgically update their context.md/acceptance.md if the new severity map changes how they render severity. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.4 — 09-finish-dead-ui-surfaces

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage B — Experience & Power" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 09-finish-dead-ui-surfaces (S-036, S-037, S-038, S-044) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: batches/09-finish-dead-ui-surfaces/context.md + acceptance.md (under plans/active/devsec-industry-grade/); health_matrix.md; synthesis rows S-036, S-037, S-038, S-044; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files. Confirm the orphaned components/{OverviewView,FindingsView,CaseCard}.tsx trio is still imported by nothing before deleting (S-036).
3. Implement per acceptance.md: delete the dead off-Mistglass case UI, make ⌘K real or remove the false hint, differentiate scan-failure feedback into crafted error states, and wire or retire the dead Activity filter chips. Senior quality. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (build + grep-no-orphan-import + the named browser checks); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/09-finish-dead-ui-surfaces.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-b-experience-power --step 1.4 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 10–13; if deleting the orphan trio or the error-state work moved anything they reference, surgically update their context.md/acceptance.md. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.5 — 10-dashboard-frontend-perf

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage B — Experience & Power" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 10-dashboard-frontend-perf (S-028, S-029, S-054) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: batches/10-dashboard-frontend-perf/context.md + acceptance.md (under plans/active/devsec-industry-grade/); health_matrix.md; synthesis rows S-028, S-029, S-054; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files. Trust the code, not the cited line numbers.
3. Implement per acceptance.md: memoize App.tsx derived state so search-box typing stops re-running all passes; trim the oversized static assets and decide code-splitting; sweep the hardcoded hex/rgba token-inlining drift back to tokens. Senior quality; behavior-preserving. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (build chunk report, lint, asset sizes); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/10-dashboard-frontend-perf.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-b-experience-power --step 1.5 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 11–13; surgically update their context.md/acceptance.md if your changes moved anything they reference. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.6 — 11-case-lifecycle

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage B — Experience & Power" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 11-case-lifecycle (S-020, S-035) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

This batch is a do-together pair: S-020 builds the canonical case-lifecycle module (reconciling the two divergent enums); S-035 adds the in-progress/verifying state + proof-bound closure on top of it. Build S-020 FIRST within this batch, then S-035.

1. Read: batches/11-case-lifecycle/context.md + acceptance.md (under plans/active/devsec-industry-grade/); health_matrix.md; synthesis rows S-020, S-035; AGENTS.md; .adx/risks.json. Use rotation's state machine as the in-repo reference pattern.
2. Re-verify each S-ID's evidence against the CURRENT files. Trust the code.
3. Implement per acceptance.md: one lifecycle module owning the state set + allowed transitions, consumed by cases/decisions/storage/dashboard; then bind a resolved case to the scan + diff entry that closed it and keep a just-closed case visible as "Verified in scan X" for one cycle. Senior quality. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (lifecycle/cases tests + the act→rescan flow check); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/11-case-lifecycle.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-b-experience-power --step 1.6 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 12–13; the new lifecycle module likely affects how 12 (scan history/diff) and 13 (code-fix surface) present case state — surgically update their context.md/acceptance.md to reference the new module. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.7 — 12-surface-scan-history-trends

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage B — Experience & Power" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 12-surface-scan-history-trends (S-039, S-042) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: batches/12-surface-scan-history-trends/context.md + acceptance.md (under plans/active/devsec-industry-grade/); health_matrix.md; synthesis rows S-039, S-042; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files. The /api/scan-history and /api/scan-diff (base/head) endpoints already exist server-side — this batch surfaces them; confirm their current shape before building UI.
3. Implement per acceptance.md: a history/trends panel consuming /api/scan-history, a base/head picker driving /api/scan-diff, and render the posture trend (use the existing trendValues helper or remove it if you render an equivalent). Senior quality; no new egress. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (component tests asserting the fetches, build); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/12-surface-scan-history-trends.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-b-experience-power --step 1.7 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batch 13; surgically update its context.md/acceptance.md if your changes moved anything it references. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.8 — 13-code-fix-dashboard-surface

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage B — Experience & Power" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 13-code-fix-dashboard-surface (S-043) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: batches/13-code-fix-dashboard-surface/context.md + acceptance.md (under plans/active/devsec-industry-grade/); health_matrix.md; synthesis row S-043; mcp/README.md for the propose_fix → clean_room_review_packet → record_clean_room_review → land_fix flow; AGENTS.md; .adx/risks.json.
2. Re-verify S-043's evidence against the CURRENT files. Trust the code.
3. Implement per acceptance.md: a dashboard proposals surface (list → diff → clean-room verdict → land decision) mirroring the rotation flow — OR, if acceptance.md chose the documentation route, document it as MCP-only in the real-vs-not-yet table. Do NOT weaken the clean-room fence or the land-gate; the dashboard only surfaces the existing guarded flow. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (the new dashboard route test, build); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/13-code-fix-dashboard-surface.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-b-experience-power --step 1.8 --reason "<blocker>"` and stop.
7. ADAPTIVE: last implementation step of Stage B — no downstream implement steps to adjust. Confirm full suite + build green before finishing.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.9 — post-repair behavioral-ux re-audit

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage B — Experience & Power" campaign (claude-automate, fresh session). This is a READ-ONLY re-audit — do NOT change repo code. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

Run the second, post-repair behavioral-ux-health forensic pass per the Excellence Brief. Read ~/Dev/skills/behavioral-ux-health-forensic/SKILL.md and ~/Dev/skills/codebase-health-kit/references/health-suite-standard.md and reports/codebase-health/devsec-industry-grade/excellence-brief.md first. Audit the dashboard UX after Stage B's repairs, graded against the Brief, and write the report to reports/codebase-health/devsec-industry-grade/11-behavioral-ux-health.final.md following ~/Dev/skills/codebase-health-kit/templates/forensic-report.md.

Compare against the initial pass (11-behavioral-ux-health.initial.md): confirm S-019, S-032, S-033, S-034, S-036, S-037, S-038, S-040, S-041, S-044, S-045, S-047, S-028, S-029, S-054 actually landed and the triage flow now feels crafted and effortless. List any residual or regression as an explicit punch-list — this feeds the human-launched Stage D patch campaign. Write a short receipt to plans/active/devsec-industry-grade/receipts/stage-b-ux-final.md. Do not run installers/scanners/dashboards/deploys. Then finish; the runner advances to Final review.
```

## Final review

```text
Human gate (Christian). Stage B is the UX headline. Skim the receipts under plans/active/devsec-industry-grade/receipts/ and the post-repair report reports/codebase-health/devsec-industry-grade/11-behavioral-ux-health.final.md for any residual or regression to fold into the Stage D patch campaign. Confirm `cd dashboard-ui && npm run build` clean. Stage C (devsec-stage-c-foundations-truth) chains automatically; `claude-automate stop --slug devsec-stage-b-experience-power` holds it if you want to review first.
```
