# Fresh Session Handoff Prompt

```text
Use /health-implement on plans/active/devsec-industry-grade. Use SocratiCode only if the batch needs broad structure, flow, ownership, or blast-radius discovery.

Do not attempt to build everything in one go. Start with batch 01-egress-honesty (Stage A — Trust & Resilience). The batch order and dependencies are in health_matrix.md; work batches in order unless a dependency says otherwise.

Read first:
- plans/active/devsec-industry-grade/what_and_why.md          (campaign shape + the 3 stages)
- plans/active/devsec-industry-grade/health_matrix.md          (all 54 items → 21 batches, ordered, with deps)
- plans/active/devsec-industry-grade/batches/01-egress-honesty/context.md
- plans/active/devsec-industry-grade/batches/01-egress-honesty/acceptance.md

The synthesis is the source of truth for every finding:
- reports/codebase-health/devsec-industry-grade/synthesis-2026-06-01.md (Master Ranked Super-List S-001..S-054)

Before editing, re-verify each S-ID's evidence against the EXACT current files — the working tree has some in-flight changes, so a few lens-cited line numbers may have drifted (batch 03 in particular already has partial work landed). Use SocratiCode as the structural map, not as proof.

Make only the changes needed for this batch. Preserve existing user work. Keep the implementation senior-quality: root-cause fix, no weakened types, no bypassed permissions/validation/audit, no broad unrelated refactors, no new hidden debt. Honor .adx/risks.json and AGENTS.md verification rules; stop for approval before destructive, production, secret, deploy, or irreversible data actions.

Stop after this one batch, write a receipt under plans/active/devsec-industry-grade/receipts/, and report:
- what changed (with before/after evidence)
- what checks passed (and any that failed, with next action)
- what risk remains
- which batch should come next

After Stage B lands, re-run behavioral-ux-health (the second, post-repair pass). Close the campaign with a feature-health-final pass.
```
