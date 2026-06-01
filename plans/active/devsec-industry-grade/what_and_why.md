# DëvSec — Industry-Grade Hardening

## What And Why

Turn DëvSec from fine to industry-grade across all 17 health domains, per the devsec-industry-grade Excellence Brief and synthesis-2026-06-01 master super-list.

The synthesis' one-line finding: DëvSec is a **strong, security-critical core wrapped in a thin, leaky ring.** The hard part — the MCP/AI write boundary, offline-by-default scanning, secret redaction — is genuinely excellent and test-proven. Almost every repair target is in the ring around it (the dashboard HTTP layer, the React UI, the type floor, the `.adx`/docs). Both non-negotiable breaches fit this shape (a proven suppression gate walked around via an unhardened dashboard; a proven offline promise broken by a font CDN), and the biggest product upside is the same shape inverted — powerful local-first capability already built but **dark** in the UI. This campaign *finishes the ring around a strong core.*

## Campaign Shape

Batches are **fix surfaces**, not health domains — one change usually lifts several lenses at once, which is the leverage the synthesis exists to surface. The 54 super-list items are 21 ordered batches across three review stages (full detail in `health_matrix.md`):

- **Stage A — Trust & Resilience** (batches 01–05): eliminate the two non-negotiable red-lines (dashboard CSRF/suppression gate, Google Fonts egress) and harden the finding/error-integrity paths. Ship first; security-critical.
- **Stage B — Experience & Power** (batches 06–13): the UX headline (kill `window.prompt` flows, accessibility floor, severity unification, finish dead surfaces) plus surfacing the dark superpowers (case lifecycle, scan history/diff, code-fix dashboard). Re-run `behavioral-ux-health` (the second, post-repair pass) after this stage.
- **Stage C — Foundations & Truth** (batches 14–21): structural seams (split the god modules, scanner registry, TS strict) and honest docs/release.

Anchored to the Excellence Brief: every batch maps to a Brief outcome or non-negotiable failure mode. The Brief's "Out of scope" items and the scout-lens feature candidates are parked in `health_matrix.md`, not built this pass. Close the campaign with a `feature-health-final` pass that re-confirms the Brief outcomes and the "real vs not yet" honesty (S-053).

## Source Reports

- Synthesis (source of truth): `reports/codebase-health/devsec-industry-grade/synthesis-2026-06-01.md`
  - Plan batches MUST come from the Master Ranked Super-List in this synthesis.
  - Do not re-batch from individual lens reports — the synthesis already deduped them.

## Campaign Goal

Turn the selected health findings green without creating new codebase health issues.

## Operating Rules

- Use one bounded batch at a time.
- Preserve user work.
- Verify evidence before editing.
- Prefer root-cause fixes.
- Keep changes reviewable.
- Add or adjust tests where risk justifies it.
- Do not weaken types, permissions, validation, audit behavior, or error handling.
- Stop for explicit approval before destructive, production, secret, deploy, force-sync, or irreversible data actions.

## Definition Of Done

- The selected health findings have concrete before/after evidence.
- Relevant checks pass or failures are explained with next action.
- Each completed batch has an implementation receipt.
- The next batch is clear.
