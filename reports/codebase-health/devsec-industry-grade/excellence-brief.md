# Excellence Brief — DëvSec (Security Observatory)

**Date:** 2026-06-01
**Campaign:** devsec-industry-grade
**Author:** Christian Katzmann

This brief defines what *excellent* means for DëvSec, beyond the Codebase Health
Suite's generic "Green = healthy enough" floor. Every forensic in this campaign reads
it before running. The synthesis pass measures findings against it. The bar is not
"no obvious problems" — it is a tool a skeptical security engineer would *prefer*.

## Product context

DëvSec is a local-first security tool for developers and small teams who work in repos
they own and want a real security read without shipping source to a SaaS. Scanners run
on the user's machine; history lives in SQLite under `~/.security-observatory`; a React
dashboard (Mistglass design system) turns scanner noise into a small set of
plain-English remediation *cases*, each with severity, evidence, and an agent-ready
handoff prompt. It also exposes a read-only MCP server (plus a guarded write mode for
AI case resolutions), a honeytoken system (Honey Keys), scan history/diffing, and an
optional macOS desktop launcher. Two things raise the floor above ordinary software:
it is a *security* tool (confidently wrong is worse than absent), and its entire pitch
is *trust* (local-first, candid). Excellence must honor both while still feeling
powerful and delightful — not safe-but-dull.

## Definition of excellent

- **Triage feels effortless and even satisfying.** From a wall of raw scanner output, a
  first-time user reaches confident next actions in seconds — fast, keyboard-navigable,
  zero dead ends, no raw-JSON escapes, crafted empty/loading/error/first-run states.
  Reducing a scary scan to a calm, ordered to-do list is the product's signature feel.
- **The core loop closes, with proof.** scan → triage → act (fix / rotate / verify) →
  rescan-to-closure works end to end, and the user can *see* a case move
  open → in-progress → verifying → closed, with the diff and the verification that
  closed it. Nothing is a one-way trip into a "Coming Soon" wall.
- **It does things only a local-first tool can — and they're powerful and easy.**
  Posture-over-time trends from the local history store; scan-to-scan diffing ("what's
  new, what regressed, what you fixed") surfaced in the UI; evidence-bound, one-keystroke
  agent handoff. These feel like superpowers, not settings.
- **Every shipped feature is polished to delight, not just present.** Cases, recovery
  playbooks, Honey Keys, MCP, history, desktop launcher — each is coherent, legible,
  fast, and finished. No half-states presented as whole; no feature that technically
  works but feels like a prototype.
- **Trust is airtight and demonstrable from inside the product.** No source, findings,
  or telemetry leave the machine on any default path; every egress is opt-in, named, and
  visible. Every case binds to concrete evidence and never overstates certainty. The AI
  handoff and MCP write path are high-leverage *and* incapable of weakening the repo,
  leaking evidence, or auto-applying a high/critical suppression without explicit,
  audited human confirmation.

## Non-negotiable failure modes

- **Silent egress.** Any default-path upload of source, findings, repo identifiers, or
  telemetry — or any network call not explicitly opted into and surfaced.
- **Confident falsehood.** A clean scan shown as "secure," a partial feature shown as
  complete, or a case asserting High confidence on inferred evidence.
- **Dropped findings.** A real scanner result that never becomes a case or raw finding
  and vanishes without trace.
- **Unsafe AI write.** Any path where an AI/MCP action edits the repo, exfiltrates finding
  text, or applies a high/critical suppression without explicit, audited human confirmation.
- **Janky or dead-end UX.** A flow that strands the user, a "Coming Soon" wall reached
  from what looked like a working action, an uncrafted error/empty state, or a triage
  path that forces a drop to the CLI or raw JSON to continue. For a UX-headline campaign,
  these are first-class failures, not polish backlog.
- **Broken trust on destructive ops.** Honey Key handling, secret rotation, process-kill,
  install, or report-storage actions that lose data, leak a secret, or fire irreversibly
  without a guard.

## Domain risk cues per lens

| Lens | Domain risk cue |
| --- | --- |
| feature-health | Does each shipped feature deliver end to end *and feel finished*? Flag prototype-grade surfaces, not just broken ones. Are the local-first superpowers (trends, diffing) present and powerful? **Also surface a ranked short-list of high-leverage features DëvSec is missing — candidates, not commitments.** |
| architecture-health | Is the scanner→normalize→case→storage→dashboard pipeline separated cleanly enough to add a new scanner, finding category, or case-lifecycle state without cross-layer surgery? |
| domain-language-health | Are raw-finding vs case, severity vs confidence, "clear within scan scope" vs "secure", and case lifecycle states used consistently across CLI, dashboard, MCP, and docs? |
| permission-boundary-health | Does the MCP write mode enforce its boundary (stdio-only, no auto-suppress of high/critical, audited path)? Does the dashboard expose nothing it shouldn't? |
| privacy-boundary-health | Trace every network-capable call. Prove no source/findings/telemetry leave on a default path; confirm legitify/Scorecard/Honey Key callbacks are opt-in *and visibly so in the UI*. |
| data-contract-type-health | Are the normalized raw-finding shape, the case schema, lifecycle-state transitions, and the MCP `case_resolutions.v1` contract typed, validated, and versioned so malformed scanner output can't corrupt history? |
| integration-health | Each scanner adapter: does it degrade *honestly and legibly* when the tool is missing or errors, rather than silently producing zero findings — and does the UI say so? |
| error-edge-state-health | Partial scans, crashed scanner, empty/huge repo, corrupt SQLite, first-ever run, zero-findings clean repo — is every state crafted and safe, never a raw stack trace or a degraded scan shown as complete? |
| test-confidence-health | Are the trust-critical paths (normalization fidelity, no-egress, case-building, MCP write guards, Honey Key hashing, lifecycle transitions) covered by tests that fail if the guarantee breaks? |
| product-workflow-health | Walk scan→triage→act→rescan-to-closure as a first-time user. Map every dead end, every CLI/JSON escape hatch, every missing lifecycle step. **Also surface workflow-level features the loop is obviously missing.** This is a primary lens, not a checkbox. |
| behavioral-ux-health | **Headline lens — runs twice (initial + final).** Does triage reduce noise to confident action without alarm-fatigue or false calm? Speed, keyboard-first, scannable severity, progressive disclosure, delight. The final pass re-audits after UX repairs land. |
| design-system-accessibility-health | Is Mistglass applied consistently and accessibly (contrast, focus order, keyboard, screen-reader, severity never signaled by color alone)? Does the product look and feel crafted, coherent, intentional? |
| performance-health | Real-repo scan and dashboard stay snappy on a large history store: no O(n²) case-building, no UI lock on big finding sets, fast trends/diff queries against SQLite. |
| ai-product-health | Are agent handoff prompts and MCP outputs accurate, evidence-bound, resistant to prompt-injection from finding text, never overconfident, and genuinely time-saving? **Also propose AI-native capabilities that would make the loop more powerful — candidates, not commitments.** |
| documentation-health | Do README, PROVOCATION, AGENTS.md, mcp/README, and the trust-boundary diagram match built behavior with zero drift between promise and code? |
| ai-maintainability-health | Can a fresh agent extend DëvSec safely via the .adx manifests, command registry, risk register, recovery notes — and are those still accurate after this campaign's changes? |
| release-readiness-health | Is the version honesty real and reproducible from a clean machine: version, changelog, install paths (managed vs Homebrew vs uv), and a "real vs not yet" table that's true *after* the polish/feature work lands? |

## In scope — beyond fixing what's broken

This campaign explicitly elevates, not just repairs:

- **UX as the headline.** Triage flow, lifecycle states, keyboard navigation, severity
  legibility, progressive disclosure, and crafted empty/loading/error/first-run states.
  `behavioral-ux-health` runs twice (initial + post-repair final).
- **Polish every shipped feature** from "works" to "finished and delightful."
- **New high-leverage, local-first-native capabilities** where they make the core loop
  more powerful without breaking the trust model — e.g. posture-over-time trends, in-UI
  scan diffing, a stronger case lifecycle with visible verification, a local
  (no-cloud) shareable posture report. Four are named; they are a starting set, not a cap.
- **Feature discovery is part of the audit.** `feature-health`, `product-workflow-health`,
  and `ai-product-health` each surface a short, ranked list of domain-obvious,
  high-leverage features DëvSec is missing — flagged as candidates for a later decision,
  not commitments for this campaign. The point is to end the campaign knowing what would
  obviously make the product better, not just that the current surface is healthy.

## Out of scope for this campaign

- **External Surface scanning (active recon/probing).** Stays an honest "Coming Soon" —
  this is a deliberate product/safety boundary, not laziness. Excellence = it's clearly
  not-yet and inviting, not that it's built. If recon is ever pursued, it is its own
  dedicated campaign, never folded into this one.
- **Runnable packs (IaC Pack run-mode, broad one-click install/uninstall)** — honest,
  well-designed placeholders, not implementation, this pass.
- **Cross-platform desktop launcher beyond macOS.**
- **Net-new scanners beyond the current roster.**

## Excellence verdict criteria

The campaign succeeds when:

- Every non-negotiable failure mode is demonstrably eliminated, with evidence.
- Every excellent outcome has concrete evidence in the final `feature-health-final` pass,
  and the UX outcomes are re-confirmed by the second `behavioral-ux-health` pass.
- The synthesis super-list has no Red, no Yellow/Red, and the documented advance gate has
  cleared on every contributing lens.
- The feature-discovery short-lists from `feature-health`, `product-workflow-health`, and
  `ai-product-health` are captured for a post-campaign decision (recorded, not lost).
