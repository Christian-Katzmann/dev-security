# DëvSec Stage A — Trust & Resilience

> Autonomously close DëvSec's two trust red-lines — the dashboard CSRF/suppression-gate gap and the Google Fonts egress — and harden the finding- and error-integrity paths. Five batches, each its own fresh session, with a hard stop if any batch's checks can't pass.

## Context (locked decisions)

- **Branch:** all work lands on `main`.
- **Repo:** `/Users/christiankatzmann/Dev/Projects/dëv-security`.
- **Source of truth:** `reports/codebase-health/devsec-industry-grade/synthesis-2026-06-01.md` and the health plan `plans/active/devsec-industry-grade/`. Each step implements one batch's `context.md` + `acceptance.md`.
- **Mode:** fully unattended. Every step is a fresh session that implements one batch, runs that batch's Required Checks, writes a receipt, adaptively patches later steps if the code moved, then advances. A step that cannot make its checks pass calls `claude-automate fail` to halt the chain rather than pass broken work forward.
- **Chain-after:** `devsec-stage-b-experience-power` — Stage B launches automatically when Stage A's steps complete.

## Progress checklist

### Phase 1 — Trust & Resilience
- [ ] Step 1.1 — 01-egress-honesty
- [ ] Step 1.2 — 02-dashboard-csrf-suppression-gate
- [ ] Step 1.3 — 03-backend-read-path-resilience
- [ ] Step 1.4 — 04-dashboard-error-surfacing
- [ ] Step 1.5 — 05-trust-integrity-tests
- [ ] Final review

## Step 1.1 — 01-egress-honesty

Model: claude-opus-4-8
Parallel: no

```text
You are an autonomous step in the DëvSec "Stage A — Trust & Resilience" health campaign (claude-automate, fresh session). Implement EXACTLY one batch — 01-egress-honesty (super-list items S-002, S-007) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read, in order: plans/active/devsec-industry-grade/batches/01-egress-honesty/context.md and acceptance.md; plans/active/devsec-industry-grade/health_matrix.md (this batch's rows + dependencies); the synthesis rows S-002, S-007 in reports/codebase-health/devsec-industry-grade/synthesis-2026-06-01.md; AGENTS.md; .adx/risks.json; .adx/verification.json.
2. Re-verify each S-ID's evidence against the CURRENT files before editing — earlier batches in this campaign may have shifted line numbers or already landed part of the work. Trust the code, not the cited line numbers. Use SocratiCode only for genuine structure/blast-radius discovery.
3. Implement the smallest root-cause fix that satisfies every acceptance criterion. Senior quality: no weakened types/permissions/validation/audit/error-handling, no broad unrelated refactors, no new hidden debt, no new codebase-health issues. Honor .adx/risks.json — do NOT run installers, scanners, dashboards, desktop launchers, deploys, or any destructive/secret/irreversible action, and do NOT fire any live network call to "verify" egress.
4. Run this batch's Required Checks (listed in acceptance.md). Every acceptance criterion must have concrete before/after evidence.
5. Write an implementation receipt from /Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md to plans/active/devsec-industry-grade/receipts/01-egress-honesty.md (changes made, checks passed, before/after evidence, residual risk).
6. SUCCESS — if all Required Checks pass and every acceptance criterion is met, commit on `main` and finish; the runner advances to the next step. BLOCKED — if after a genuine effort a check still fails, or the batch needs a forbidden action above, do NOT advance: run `claude-automate fail --slug devsec-stage-a-trust-resilience --step 1.1 --reason "<precise one-line blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT (before finishing on success): re-read the later batches in this campaign (02–05). If your implementation materially changed what a later batch will face — a residual you resolved, a file you split/renamed/moved, line numbers or structure that shifted, a sub-task now obsolete — update that later batch's plans/active/devsec-industry-grade/batches/<batch>/context.md (and acceptance.md if a check changed) so the next fresh session inherits an accurate map. Keep edits surgical; never change which S-IDs a batch targets.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review (final review is at campaign end). Stop after this one batch.
```

## Step 1.2 — 02-dashboard-csrf-suppression-gate

Model: claude-opus-4-8
Parallel: no

```text
You are an autonomous step in the DëvSec "Stage A — Trust & Resilience" health campaign (claude-automate, fresh session). Implement EXACTLY one batch — 02-dashboard-csrf-suppression-gate (super-list item S-001) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

This is the highest-stakes security batch: it CSRF/Origin-hardens the dashboard's mutating loopback HTTP surface and re-arms the high/critical suppression gate so `human_authorized` can no longer be inferred from a POST arriving. Get this exactly right.

1. Read, in order: plans/active/devsec-industry-grade/batches/02-dashboard-csrf-suppression-gate/context.md and acceptance.md; plans/active/devsec-industry-grade/health_matrix.md; the synthesis row S-001 in reports/codebase-health/devsec-industry-grade/synthesis-2026-06-01.md; AGENTS.md; .adx/risks.json; .adx/verification.json.
2. Re-verify S-001's evidence against the CURRENT files before editing — earlier batches may have shifted line numbers. Trust the code, not the cited line numbers.
3. Implement the smallest root-cause fix that satisfies every acceptance criterion. Senior quality; deliberately keep the honey-key trigger callback exempt from the CSRF guard; do not touch the storage.py suppression chokepoint logic except to require explicit confirmation; do not alter the MCP write boundary. Honor .adx/risks.json — no installers/scanners/dashboards/deploys/destructive/secret actions.
4. Run this batch's Required Checks (from acceptance.md), including the new tests/test_dashboard_csrf.py asserting a forged cross-origin POST returns 403 and cannot suppress a critical case while a same-origin request still works. Every criterion needs before/after evidence.
5. Write a receipt (template: /Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md) to plans/active/devsec-industry-grade/receipts/02-dashboard-csrf-suppression-gate.md.
6. SUCCESS — commit on `main` and finish. BLOCKED — `claude-automate fail --slug devsec-stage-a-trust-resilience --step 1.2 --reason "<blocker>"` and stop. Do not pass a half-hardened auth boundary forward.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 03–05; if your changes moved anything they reference, surgically update those batches' context.md/acceptance.md. Never change a batch's target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.3 — 03-backend-read-path-resilience

Model: claude-opus-4-8
Parallel: no

```text
You are an autonomous step in the DëvSec "Stage A — Trust & Resilience" health campaign (claude-automate, fresh session). Implement EXACTLY one batch — 03-backend-read-path-resilience (super-list items S-003, S-006, S-023) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

Note: this batch's context.md flags that some of this work may already be partially landed in the working tree. Re-verify current state first and implement only the genuine residuals.

1. Read, in order: plans/active/devsec-industry-grade/batches/03-backend-read-path-resilience/context.md and acceptance.md; health_matrix.md; the synthesis rows S-003, S-006, S-023; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files (the context.md warns the cited line numbers have drifted and quarantine/do_GET work may already exist). Trust the code. Preserve any quarantined DB file; re-raise on OperationalError; do not silently swallow real errors.
3. Implement the smallest root-cause fix per acceptance.md. Senior quality; no module split here (that is batch 15). Honor .adx/risks.json.
4. Run this batch's Required Checks (from acceptance.md), including the corrupt-store and unguarded-JSON tests; every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/03-backend-read-path-resilience.md.
6. SUCCESS — commit on `main` and finish. BLOCKED — `claude-automate fail --slug devsec-stage-a-trust-resilience --step 1.3 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 04–05; surgically update their context.md/acceptance.md if your changes moved anything they reference. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.4 — 04-dashboard-error-surfacing

Model: claude-opus-4-8
Parallel: no

```text
You are an autonomous step in the DëvSec "Stage A — Trust & Resilience" health campaign (claude-automate, fresh session). Implement EXACTLY one batch — 04-dashboard-error-surfacing (super-list items S-004, S-005) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read, in order: plans/active/devsec-industry-grade/batches/04-dashboard-error-surfacing/context.md and acceptance.md; health_matrix.md; the synthesis rows S-004, S-005; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files before editing. Trust the code, not the cited line numbers.
3. Implement the smallest root-cause fix per acceptance.md (surface case-decision failures inline on the Findings tab; add a top-level React error boundary + fetch-retry + a runtime shape guard on /api/summary). Senior quality; no broad unrelated refactors. Honor .adx/risks.json.
4. Run this batch's Required Checks (from acceptance.md) — frontend lint + build plus the named manual checks; every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/04-dashboard-error-surfacing.md.
6. SUCCESS — commit on `main` and finish. BLOCKED — `claude-automate fail --slug devsec-stage-a-trust-resilience --step 1.4 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batch 05; surgically update its context.md/acceptance.md if your changes moved anything it references.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.5 — 05-trust-integrity-tests

Model: claude-opus-4-8
Parallel: no

```text
You are an autonomous step in the DëvSec "Stage A — Trust & Resilience" health campaign (claude-automate, fresh session). Implement EXACTLY one batch — 05-trust-integrity-tests (super-list items S-024, S-025) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

This batch locks the trust guarantees the rest of Stage A established: a repo-wide no-egress sentinel, normalization count-conservation / dropped-findings tests, redact_text coverage, and making the MCP-guarded trust tests non-skippable.

1. Read, in order: plans/active/devsec-industry-grade/batches/05-trust-integrity-tests/context.md and acceptance.md; health_matrix.md; the synthesis rows S-024, S-025; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files. The no-egress sentinel must monkeypatch socket/urlopen to raise and run a full default-path scan→case-build asserting zero outbound attempts — without making any real network call.
3. Implement the smallest root-cause fix per acceptance.md. Senior quality; tests must genuinely fail if the guarantee breaks (no vacuous assertions). Honor .adx/risks.json.
4. Run this batch's Required Checks (from acceptance.md); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/05-trust-integrity-tests.md.
6. SUCCESS — commit on `main` and finish. BLOCKED — `claude-automate fail --slug devsec-stage-a-trust-resilience --step 1.5 --reason "<blocker>"` and stop.
7. ADAPTIVE: this is the last implementation step of Stage A — no downstream steps to adjust. Confirm the full suite is green before finishing.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Final review

```text
Human gate (Christian). Stage A is the security-critical stage — review before Stage B is trusted. Confirm: `uv run pytest` green, the fast import check passes, `cd dashboard-ui && npm run build` clean. Read the five receipts under plans/active/devsec-industry-grade/receipts/ — especially 01 (egress) and 02 (CSRF/suppression) — and skim the actual diffs for the two red-lines. Stage B (devsec-stage-b-experience-power) chains automatically; run `claude-automate stop --slug devsec-stage-a-trust-resilience` if you want to hold before it proceeds.
```
