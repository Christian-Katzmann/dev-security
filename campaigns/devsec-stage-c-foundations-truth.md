# DëvSec Stage C — Foundations & Truth

> Autonomously pay down the structural debt (extract the scan orchestrator, split the two god modules, scanner-adapter registry, TypeScript strict + case-write contracts) and make the repo's self-description honest (the `.adx` agent layer, docs, changelog, remaining integration/MCP hygiene). Closes with a `feature-health-final` audit. Each batch is its own fresh session; a batch that can't pass its checks halts the chain.

## Context (locked decisions)

- **Branch:** all work lands on `main`.
- **Repo:** `/Users/christiankatzmann/Dev/Projects/dëv-security`.
- **Source of truth:** `reports/codebase-health/devsec-industry-grade/synthesis-2026-06-01.md` and `plans/active/devsec-industry-grade/`. Each step implements one batch's `context.md` + `acceptance.md`.
- **Mode:** fully unattended. Each step implements one batch, runs its Required Checks, writes a receipt, adaptively patches later steps if the code moved, then advances. A step that cannot make its checks pass calls `claude-automate fail` to halt rather than pass broken work forward.
- **Structural caution:** batches 15–17 are high-blast-radius refactors. Each must preserve behavior and the error-handling added in Stage A (batch 03); rely on the existing test suite as the safety net and run it before finishing.
- **Chain-after:** none — this is the final automated stage. After it completes, Christian launches the Stage D patch campaign manually using the two `.final` re-audits.

## Progress checklist

### Phase 1 — Foundations & Truth
- [ ] Step 1.1 — 14-scan-orchestrator-extract
- [ ] Step 1.2 — 15-split-dashboard-server
- [ ] Step 1.3 — 16-storage-payload-and-query-perf
- [ ] Step 1.4 — 17-scanner-adapter-registry
- [ ] Step 1.5 — 18-type-floor-and-contracts
- [ ] Step 1.6 — 19-adx-and-docs-truth
- [ ] Step 1.7 — 20-release-honesty
- [ ] Step 1.8 — 21-integration-and-mcp-hygiene
- [ ] Step 1.9 — feature-health-final audit
- [ ] Final review

## Step 1.1 — 14-scan-orchestrator-extract

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage C — Foundations & Truth" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 14-scan-orchestrator-extract (S-015) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: plans/active/devsec-industry-grade/batches/14-scan-orchestrator-extract/context.md + acceptance.md; health_matrix.md; synthesis row S-015; AGENTS.md; .adx/risks.json.
2. Re-verify S-015's evidence against the CURRENT files. Trust the code, not the cited line numbers. Use SocratiCode for blast-radius (this breaks the cli↔dashboard cycle).
3. Implement per acceptance.md: extract a scan_orchestrator/pipeline module from cli.py that cli, mcp_server, and dashboard_server all import; behavior-preserving. Senior quality. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (trigger-scan tests, fast import check, re-run the dependency-cycle scan → 0 cycles); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/14-scan-orchestrator-extract.md.
6. SUCCESS — commit on `main` and finish. BLOCKED — `claude-automate fail --slug devsec-stage-c-foundations-truth --step 1.1 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 15–21; the new orchestrator module changes imports that 15 (split dashboard_server), 16 (storage payload), 17 (scanner registry) reference — surgically update their context.md/acceptance.md. Never change a batch's target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.2 — 15-split-dashboard-server

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage C — Foundations & Truth" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 15-split-dashboard-server (S-016) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

High blast radius — behavior-preserving refactor of the ~4,200-line dashboard_server.py. Preserve the do_GET error handling and corrupt-store resilience added in Stage A (batch 03).

1. Read: plans/active/devsec-industry-grade/batches/15-split-dashboard-server/context.md + acceptance.md; health_matrix.md; synthesis row S-016; AGENTS.md; .adx/risks.json.
2. Re-verify S-016's evidence against the CURRENT files (Stage A and batch 14 will have changed this file). Trust the code. Use SocratiCode for structure.
3. Implement per acceptance.md: introduce a route table for do_GET/do_POST/do_DELETE, move the two inline server-rendered HTML pages into template modules or render from the React build, and lift per-repo enrichment out of do_GET. No behavior change. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (dashboard endpoint tests, fast import check, full uv run pytest); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/15-split-dashboard-server.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-c-foundations-truth --step 1.2 --reason "<blocker>"` and stop. Do not pass a half-split server forward.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 16–21; the new module/route structure changes file paths and line numbers many later batches (16, 19, 21) cite — surgically update their context.md/acceptance.md to point at the new locations. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.3 — 16-storage-payload-and-query-perf

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage C — Foundations & Truth" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 16-storage-payload-and-query-perf (S-017, S-027) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

Do-together: S-017 lifts payload assembly out of storage.py (removing the persistence→scanner import inversion); S-027 batches dashboard_payload into set-based queries (killing the per-repo fan-out and the nested case_resolution_items N+1). They share the same code, so land them together.

1. Read: plans/active/devsec-industry-grade/batches/16-storage-payload-and-query-perf/context.md + acceptance.md; health_matrix.md; synthesis rows S-017, S-027; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files (batches 14–15 changed imports/structure). Trust the code.
3. Implement per acceptance.md: a payload-assembly/service layer so storage owns schema + queries only; replace the per-repo loop's individual lookups with WHERE scan_id IN (...) / run_id IN (...) set queries assembled in memory; eliminate the nested N+1. Behavior-preserving. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (full uv run pytest, fast import check, the seeded query-count trace proving O(1) in repo count); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/16-storage-payload-and-query-perf.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-c-foundations-truth --step 1.3 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 17–21; surgically update their context.md/acceptance.md if your changes moved anything they reference. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.4 — 17-scanner-adapter-registry

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage C — Foundations & Truth" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 17-scanner-adapter-registry (S-018) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: plans/active/devsec-industry-grade/batches/17-scanner-adapter-registry/context.md + acceptance.md; health_matrix.md; synthesis row S-018; AGENTS.md; .adx/risks.json.
2. Re-verify S-018's evidence against the CURRENT files. Trust the code.
3. Implement per acceptance.md: collapse the parallel string-keyed branches (run_scanner, _command, _timeout, EXIT_CODES_WITH_FINDINGS, normalize dispatch) + catalog metadata into one dataclass/protocol entry per scanner; update docs/adding-scanners.md and docs/architecture.md. Behavior-preserving — every scanner still runs and normalizes identically. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (scanner + normalize tests); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/17-scanner-adapter-registry.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-c-foundations-truth --step 1.4 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 18–21; the registry changes how scanners are described — surgically update batch 19's (.adx/docs) and batch 21's (integration) context.md/acceptance.md if they reference the old dispatch sites. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.5 — 18-type-floor-and-contracts

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage C — Foundations & Truth" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 18-type-floor-and-contracts (S-021, S-022, S-026) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: plans/active/devsec-industry-grade/batches/18-type-floor-and-contracts/context.md + acceptance.md; health_matrix.md; synthesis rows S-021, S-022, S-026; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files. Trust the code.
3. Implement per acceptance.md: enable TypeScript strict (≥ strictNullChecks + noImplicitAny) and fix surfaced errors; trim the frontend SecurityCase type to the real wire shape and route case writes through SecurityCase so redaction/validation can't be bypassed; adopt PRAGMA user_version for versioned migrations. Do S-021 first (it makes S-022 safe). Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (tsc --noEmit under strict, npm run lint, cases tests, the migration round-trip test); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/18-type-floor-and-contracts.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-c-foundations-truth --step 1.5 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 19–21; surgically update their context.md/acceptance.md if your changes moved anything they reference. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.6 — 19-adx-and-docs-truth

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage C — Foundations & Truth" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 19-adx-and-docs-truth (S-030, S-031, S-048, S-049, S-050, S-010, S-051, S-052) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

This batch makes the repo's self-description true after the earlier structural work. Because batches 14–18 moved code, RE-DERIVE every doc/.adx fact from the CURRENT tree — do not copy stale line numbers from the synthesis.

1. Read: plans/active/devsec-industry-grade/batches/19-adx-and-docs-truth/context.md + acceptance.md; health_matrix.md; synthesis rows S-030, S-031, S-048, S-049, S-050, S-010, S-051, S-052; AGENTS.md; the .adx/ manifests; mcp/README.md; .adx/risks.json.
2. Re-verify each S-ID against the CURRENT files: refresh the .adx module map for the MCP write subsystem; make the .adx risk/recovery/verification notes tell the truth (pytest runs — confirm with a real run); fix the AGENTS.md MCP understatement; refresh the stale pytest-blocked caveat; add a canonical-vs-working-notes doc boundary; correct the mcp/README write-surface tool count; document the security-sensitive CLI verbs/flags; line-match the destructive-surface (Honey Key) doc claims to their guards.
3. Implement per acceptance.md. Bump .adx adx.json last_verified after the edits. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (json.load each edited .adx file, uv run pytest -q to confirm the suite count, cli --help, mcp/README vs mcp_server.py diff); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/19-adx-and-docs-truth.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-c-foundations-truth --step 1.6 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batches 20–21; surgically update their context.md/acceptance.md if your doc changes moved anything they reference. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.7 — 20-release-honesty

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage C — Foundations & Truth" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 20-release-honesty (S-046, S-053) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

1. Read: plans/active/devsec-industry-grade/batches/20-release-honesty/context.md + acceptance.md; health_matrix.md; synthesis rows S-046, S-053; AGENTS.md; CHANGELOG; pyproject.toml; README "real vs not yet" table; .adx/risks.json.
2. Re-verify each S-ID against the CURRENT files and git history.
3. Implement per acceptance.md: add/maintain a CHANGELOG [Unreleased] section reconciling the commits since the v0.1.0 tag and decide the version bump; re-read the README "real vs not yet" table against the now-shipped behavior (the code-fix dashboard surface, trends/diff, etc.) and correct any line that the campaign's work has made stale. Do NOT cut a git tag or push — leave the actual release action to Christian. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (git log v0.1.0..HEAD vs changelog; version triple agreement); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/20-release-honesty.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-c-foundations-truth --step 1.7 --reason "<blocker>"` and stop.
7. ADAPTIVE DOWNSTREAM ADJUSTMENT: re-read batch 21; surgically update its context.md/acceptance.md if your changes moved anything it references. Never change target S-IDs.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.8 — 21-integration-and-mcp-hygiene

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage C — Foundations & Truth" campaign (claude-automate, fresh session). Implement EXACTLY one batch — 21-integration-and-mcp-hygiene (S-008, S-011, S-009, S-012, S-013, S-014) — then stop. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

These are the smaller hardening items on an already-Green-ish surface. Several are test-strengthening or wire-or-document decisions; keep them tight.

1. Read: plans/active/devsec-industry-grade/batches/21-integration-and-mcp-hygiene/context.md + acceptance.md; health_matrix.md; synthesis rows S-008, S-011, S-009, S-012, S-013, S-014; AGENTS.md; .adx/risks.json.
2. Re-verify each S-ID's evidence against the CURRENT files (batches 14–19 changed integration/MCP code paths). Trust the code.
3. Implement per acceptance.md: resolve the KEV/EPSS wiring gap (wire behind an explicit opt-in OR document as not-yet-wired); lock the setup-probe shell=True invariant + record the no-retry decision; harden the MCP path-leak invariant (startswith→substring) + redaction coverage; close the prompt-injection sliver + drop the ignored safe_to_apply field; add reset-cache cleanup + a reset full-cleanup test; prune terminal _JOBS entries after a TTL. Do not weaken any guard. Honor .adx/risks.json.
4. Run Required Checks from acceptance.md (enrichment, setup-runner, mcp_server, severity-gate, reset tests); every criterion needs before/after evidence.
5. Write a receipt to plans/active/devsec-industry-grade/receipts/21-integration-and-mcp-hygiene.md.
6. SUCCESS — commit and finish. BLOCKED — `claude-automate fail --slug devsec-stage-c-foundations-truth --step 1.8 --reason "<blocker>"` and stop.
7. ADAPTIVE: last implementation step — no downstream implement steps. Run the full uv run pytest and confirm green before finishing.

COMMIT DISCIPLINE: stage ONLY the files you changed for this batch, using explicit paths (`git add <path> ...`). NEVER run `git add -A` or `git add .` — the working tree contains unrelated in-flight changes (e.g. AGENTS.md, CLAUDE.md, .ghost/) that must never appear in your commit. Skip per-step code review. Stop after this one batch.
```

## Step 1.9 — feature-health-final audit

Model: claude-opus-4-8
Parallel: no

```text
Autonomous step in the DëvSec "Stage C — Foundations & Truth" campaign (claude-automate, fresh session). READ-ONLY final audit — do NOT change repo code. Repo: /Users/christiankatzmann/Dev/Projects/dëv-security.

Run the campaign-closing feature-health-final pass. Read ~/Dev/skills/feature-health-forensic/SKILL.md, ~/Dev/skills/codebase-health-kit/references/health-suite-standard.md, and reports/codebase-health/devsec-industry-grade/excellence-brief.md first. Audit the whole product surface after all three stages, graded against the Brief's Definition of excellent and non-negotiable failure modes, and write the report to reports/codebase-health/devsec-industry-grade/feature-health-final.md following ~/Dev/skills/codebase-health-kit/templates/forensic-report.md.

Specifically confirm, with evidence: both non-negotiable breaches are eliminated (S-001 dashboard CSRF/suppression, S-002 Google Fonts egress); the local-first superpowers are now visible (S-039 history/diff, S-042 trends, S-043 code-fix surface, S-035 lifecycle); and re-check the README "real vs not yet" honesty (S-053) against shipped behavior. List every remaining residual, regression, or newly-introduced issue as an explicit punch-list — this, plus reports/codebase-health/devsec-industry-grade/11-behavioral-ux-health.final.md, is the input to the human-launched Stage D patch campaign. Write a short receipt to plans/active/devsec-industry-grade/receipts/feature-health-final.md. Do not run installers/scanners/dashboards/deploys. Then finish; the runner advances to Final review.
```

## Final review

```text
Human gate (Christian). All three automated stages are complete. Read the two campaign-closing audits — reports/codebase-health/devsec-industry-grade/feature-health-final.md and 11-behavioral-ux-health.final.md — and the receipts under plans/active/devsec-industry-grade/receipts/. Their punch-lists are the scope for the Stage D patch campaign you launch manually. Confirm `uv run pytest` and `cd dashboard-ui && npm run build` are green on a clean checkout before considering the campaign done.
```
