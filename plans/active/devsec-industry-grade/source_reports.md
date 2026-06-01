# Source Reports

## Inputs

- Synthesis (source of truth): `reports/codebase-health/devsec-industry-grade/synthesis-2026-06-01.md`
  - Plan batches MUST come from the Master Ranked Super-List in this synthesis.
  - Do not re-batch from individual lens reports — the synthesis already deduped them.

## Report Summary

All 17 lens reports live under `reports/codebase-health/devsec-industry-grade/`. They are cross-reference evidence pointers — the synthesis Master Super-List is what the batches come from. Worst health per lens (from the forensics):

| Report | Lens | Worst health | Headline weakest area |
| --- | --- | --- | --- |
| 05-privacy-boundary-health.initial.md | privacy-boundary | Yellow/Red | Google Fonts default-path egress contradicts the trust-boundary diagram (→ S-002) |
| 04-permission-boundary-health.initial.md | permission-boundary | Yellow/Red | Dashboard CSRF lets a local page forge a high/critical suppression as `human_authorized` (→ S-001) |
| 02-architecture-health.initial.md | architecture | Yellow/Red | Four oversized god modules straddling layers; scanner logic across ~5 sites (→ S-015/S-016/S-017/S-018) |
| 08-error-edge-state-health.initial.md | error-edge-state | Yellow/Red | Corrupt SQLite has no recovery; silent case-decision failures; no React error boundary (→ S-003/S-004/S-005/S-006) |
| 11-behavioral-ux-health.initial.md | behavioral-ux | Yellow/Red | Core loop drops to raw `window.prompt`; dead duplicate Cases screen; fake ⌘K (→ S-033/S-034/S-036/S-037) |
| 12-design-system-accessibility-health.initial.md | design-system-accessibility | Yellow/Red | No focus indicator; modals lack focus-trap/Escape; no a11y tests (→ S-040/S-041/S-047) |
| 06-data-contract-type-health.initial.md | data-contract-type | Yellow/Red | Frontend TS not strict; unguarded JSON decode; FE/BE type drift (→ S-021/S-022/S-023) |
| 01-feature-health.initial.md | feature | Yellow | Code-fix flow MCP-only; flat case lifecycle; posture-trend dead code (→ S-035/S-042/S-043) + scout candidates |
| 03-domain-language-health.initial.md | domain-language | Yellow | Severity Elevated/Warning vs high/medium; two lifecycle enums; glossary vs spec (→ S-019/S-020/S-032) |
| 09-test-confidence-health.initial.md | test-confidence | Yellow | No count-conservation invariant; no repo-wide egress sentinel; `test_model.py` stub (→ S-024/S-025) |
| 10-product-workflow-health.initial.md | product-workflow | Yellow | Rescan-to-closure not bound; scan-history/diff dark in UI; orphaned case UI (→ S-035/S-039/S-036) + scout candidates |
| 13-performance-health.initial.md | performance | Yellow | `/api/summary` per-repo fan-out + nested N+1; App.tsx recompute on every keystroke (→ S-027/S-028) |
| 15-documentation-health.initial.md | documentation | Yellow | AGENTS.md understates MCP write mode; stale pytest-blocked caveat; doc over-supply (→ S-048/S-049/S-050) |
| 16-ai-maintainability-health.initial.md | ai-maintainability | Yellow | `.adx` module map/risk register frozen before the MCP write subsystem; false "pytest can't run" (→ S-030/S-031) |
| 17-release-readiness-health.initial.md | release-readiness | Yellow | 104 commits since v0.1.0 with no `[Unreleased]` changelog entry (→ S-046/S-053) |
| 07-integration-health.initial.md | integration | Green/Yellow | Unreachable KEV/EPSS wiring; no retry/backoff by design (→ S-008/S-011) |
| 14-ai-product-health.initial.md | ai-product | Green/Yellow | Strongest surface, test-pinned; only doc polish + a doctrine-drift guard left (→ S-009/S-010/S-012) |

The findings ledger (`reports/codebase-health/devsec-industry-grade/findings-ledger.json`, 272 entries) and the synthesis Ledger Coverage table give per-finding traceability from each S-ID back to the exact report row.

## Evidence Rules

Every plan item points back to its synthesis row (S-ID) and the owning lens report above, and carries its own validation path (see `health_matrix.md`). If evidence is weak for a batch, its first implementation step is investigation, not editing.
