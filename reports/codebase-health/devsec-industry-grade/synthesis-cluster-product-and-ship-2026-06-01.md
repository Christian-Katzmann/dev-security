# Synthesis — devsec-industry-grade (cluster: product-and-ship)

**Date:** 2026-06-01
**Lenses synthesized:** 6 forensic reports (product-and-ship cluster)
**Excellence Brief:** `/Users/christiankatzmann/Dev/Projects/dëv-security/reports/codebase-health/devsec-industry-grade/excellence-brief.md`
**Reviewed by second agent:** No (cluster pass; review at merge)

Cluster lenses: `feature-health`, `product-workflow-health`, `behavioral-ux-health`, `design-system-accessibility-health`, `documentation-health`, `release-readiness-health`.

## Executive Finding

The single biggest pattern in this cluster is a **capability/visibility inversion: DëvSec has built powerful, trust-safe, local-first machinery that stays dark or unfinished in the surface a real user touches.** The strongest realization of the Brief's safe-AI-write ideal — `propose_fix → clean-room-review → land_fix` — ships, is fenced, and is tested, but has *no dashboard surface at all* (feature RH.1). Two named local-first superpowers are wired server-side yet have zero UI consumers: `/api/scan-history` and arbitrary-base/head `/api/scan-diff` (product-workflow RH.2/RH.3), while the posture-trend helper `trendValues` is dead code (feature RH.3). The Brief's signature "watch a case move open → in-progress → verifying → closed, with the diff that closed it" is the most-named gap in the cluster: there is no intermediate lifecycle state and closure is shown by *absence*, not proof (feature RH.2, product-workflow RH.1). And where the core loop *is* reached, it repeatedly drops to uncrafted primitives the Brief treats as first-class failures: the first-run "add a repo" gateway is a raw `window.prompt` (behavioral-ux RH.1), decision-note and incident-close capture drop to `window.prompt` again (behavioral-ux RH.2), the headline Cases screen carries a dead, off-Mistglass duplicate twin (behavioral-ux RH.3 / product-workflow RH.4), the toolbar advertises a `⌘K` shortcut wired to nothing (behavioral-ux RH.4), and keyboard users get no visible focus ring and cannot escape modals (design-system RH.2/RH.1). The good news the cluster also establishes: the triage *spine* is sound and often excellent (calm-by-default severity, crafted empty/first-run states, a real master-detail with live decision controls), the design-system primitives are mature, documentation is unusually honest, and the release posture is strong save one confirmed changelog-drift defect. The cluster's job is therefore not rescue but *finishing*: surface the dark superpowers, give cases a visible proof-bound lifecycle, and replace the janky native-dialog/duplicate/false-affordance touchpoints with crafted Mistglass surfaces — exactly the UX headline this campaign was framed around.

## Brief Coverage

Only Brief items this cluster's lenses bear on are listed. Items owned by sibling clusters (egress, MCP write-guard enforcement, normalization fidelity, architecture refactor, etc.) are out of this cluster's scope and not rated here.

| Brief item | Type | Findings | Coverage |
| --- | --- | --- | --- |
| Triage feels effortless and even satisfying (fast, keyboard-navigable, zero dead ends, no raw-JSON escapes, crafted empty/loading/error/first-run states) | outcome | S-001, S-002, S-004, S-005, S-006, S-008, S-009, S-013 | Partial |
| The core loop closes, with proof (case moves open → in-progress → verifying → closed, with the diff + verification that closed it) | outcome | S-003, S-007 | Partial |
| Does things only a local-first tool can — powerful and easy (posture-over-time trends, in-UI scan diffing, evidence-bound one-keystroke agent handoff) | outcome | S-007, S-010, S-011 | Partial |
| Every shipped feature polished to delight, not just present (no half-states presented as whole; no prototype-feel) | outcome | S-005, S-006, S-010, S-012, S-013, S-021, S-022 | Partial |
| Trust airtight and demonstrable from inside the product (AI handoff / MCP write path high-leverage *and* incapable of weakening the repo) | outcome | S-001, S-016 | Partial |
| Janky or dead-end UX (strands user, "Coming Soon" wall from a working action, uncrafted error/empty state, forced drop to CLI/raw JSON) — first-class failure | failure-mode | S-001, S-002, S-004, S-005, S-006, S-008, S-009, S-011, S-013 | Strong |
| Confident falsehood (a partial feature shown as complete) | failure-mode | S-010, S-016, S-021 | Partial |
| UX as the headline (triage flow, lifecycle states, keyboard nav, severity legibility, progressive disclosure, crafted states; behavioral-ux runs twice) | in-scope elevation | S-001, S-002, S-003, S-004, S-005, S-006, S-008, S-009 | Strong |
| Version honesty real and reproducible from a clean machine (version, changelog, install paths, "real vs not yet" true after the work lands) | outcome | S-014, S-016, S-021, S-022 | Strong |
| Feature discovery captured as ranked candidates (recorded, not lost) | in-scope elevation | S-C1…S-C13 (Scout subsection) | Strong |

## Master Ranked Super-List

Deduped, cross-lens-aware repair items, weakest/highest-risk first. IDs are **local to this cluster** (the merge step renumbers globally). The "janky/dead-end UX" items rank high per the Brief. Scout-lens feature candidates are preserved verbatim in the dedicated subsection below the table; they are candidates for a later decision, not repair items.

| ID | Repair item | Owning lens | Cross-refs | Health | Confidence | Brief mapping | Suggested validation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S-001 | First-run "add a repo" gateway is a raw `window.prompt` (no folder picker, no existence check, no example, silent empty-fail; fired from 4 places incl. a dropdown option). Replace with a crafted in-app Mistglass form (input + recent/known-repo suggestions from `/api/projects` + inline "path not found" validation + one primary action; retire dropdown-option-as-action). | behavioral-ux-health | feature-health (US.4) | Yellow/Red | High | failure-mode: janky/dead-end UX; outcome: effortless triage | After fix: `npm run lint && npm run build`; browser smoke add-repo with a bad path and an empty submit (final UX pass). |
| S-002 | `window.prompt` recurs across the core loop — decision-note capture (both case renderers) and Honey-key incident-close note drop to a blocking native OS dialog at the moment of resolution; cancel/empty handled silently. Replace each with an inline Mistglass note field/popover; keep one-click decisions. | behavioral-ux-health | feature-health, product-workflow-health | Yellow | High | failure-mode: janky/dead-end UX; outcome: effortless triage | Final pass: record a decision and close an incident in-browser; confirm no native dialog appears. |
| S-003 | Case lifecycle is flat (terminal triage-decision + rescan diff); **no in-progress / verifying intermediate state**, and closure is shown by *absence* (case drops out of `caseNeedsAttention`) rather than proof bound to the resolving scan + diff. Introduce an explicit `in_progress`/`awaiting_rescan` state, bind a resolved case to the scan + diff `resolved[]` entry that closed it, and keep a just-closed case visible as "Verified ✓ in scan X" for one cycle. Rotation's state machine is the in-repo reference pattern. | feature-health | product-workflow-health (RH.1), architecture-health (sibling cluster), domain-language-health (sibling cluster) | Yellow | High | outcome: core loop closes with proof; UX headline | `python-pytest` (new cases/storage lifecycle tests); component/e2e: act on a case, rescan, assert the case shows a resolved state bound to the new scan id. |
| S-004 | Orphaned parallel case UI: `components/{OverviewView,FindingsView,CaseCard}.tsx` is a complete second case UI imported by nothing, shadowing the live inline `CaseDetailCard`; its `CaseCard` is off-Mistglass (pure-black ink, `font-light`, `border-black`, severity as faint `text-black/45` with no colored pill — the `#000`/alarm register DESIGN.md §2 bans). Misleads readers/agents about which act path is real; latent off-system risk if revived. Delete the trio (or adopt + retire the inline equivalents), one source of truth. | product-workflow-health | behavioral-ux-health (RH.3) | Yellow | High | failure-mode: janky/dead-end UX (reader-facing half-state); outcome: polished feature | `npm run build` after removal; grep confirms no remaining import of the deleted files; no off-`#000` case styling remains. |
| S-005 | `⌘K` shortcut hint rendered in the toolbar is wired to nothing (only global keydown is the ⌘R hard-refresh); a false affordance advertising a keyboard speed feature named in the Brief. Implement ⌘K (focus search / command palette) or remove the `<kbd>` hint until it exists. | behavioral-ux-health | feature-health | Yellow | High | failure-mode: janky/dead-end UX; outcome: keyboard-navigable triage | Final pass: press ⌘K in browser; confirm it acts, or the hint is gone. |
| S-006 | Scan-failure feedback collapses to one undifferentiated `runError` string (set ~8 places, rendered as a generic inline error); scanner-missing vs scanner-errored vs scan-failed are not differentiated, and `runError` is rendered in only two of the surfaces that write to it. During a scan (highest-anxiety moment) the user can't tell what broke or where to go. Differentiate into crafted Mistglass error cards (missing tool → link to Verification; errored → retry; failed → details). | behavioral-ux-health | error-edge-state-health (sibling cluster, US.2) | Yellow | Medium | failure-mode: uncrafted error state; outcome: crafted error states | Final pass: browser smoke a scan with a missing scanner; confirm the error is actionable. |
| S-007 | Two local-first superpowers wired server-side but dark in the UI: `/api/scan-history` has **0** UI consumers, and `/api/scan-diff` accepts `base`/`head` but the UI only ever sends `repo` (arbitrary scan-to-scan compare is built but unreachable). Add a history/trends panel consuming `/api/scan-history` and a base/head picker driving `/api/scan-diff`. | product-workflow-health | feature-health (RH.3 trend), behavioral-ux-health | Yellow | High | outcome: local-first superpowers powerful and easy; polished feature | Component tests: render history panel and assert the fetch; pick base/head and assert the diff request carries both. |
| S-008 | No global visible focus indicator across the dashboard's primary controls; the only two `:focus-visible` rules (`.setup-card-input/textarea`) set `outline:none` + a near-invisible 1px shadow; the one 3px ring in the file is decorative on `.status-dot.live`. Keyboard-only and low-vision users can't see where they are. Add one global token-based `:focus-visible` ring on buttons/links/inputs/selects/textareas/clickable cards and replace the two `outline:none` rules. | design-system-accessibility-health | behavioral-ux-health (RH.8) | Yellow/Red | High | failure-mode: janky UX (keyboard); outcome: keyboard-navigable, accessible | Tab through every view; confirm a visible ring on each control; focus snapshot/axe test. |
| S-009 | Four `role="dialog"`+`aria-modal` modals (Rotation Trigger/Status/Batch, AiFollowUp) declare dialog semantics but have **no Escape handler, no focus trap, no focus restore** — keyboard users can tab behind an open rotation/AI-write dialog and can't dismiss it, on flows where mis-action has security cost. Build one shared `Dialog` primitive (focus trap + Escape-to-close + focus restore) and migrate all four. | design-system-accessibility-health | behavioral-ux-health (RH.8) | Yellow/Red | High | failure-mode: janky UX (keyboard); outcome: accessible, crafted | Open each modal via keyboard; verify trap + Escape + focus return; axe dialog rule. |
| S-010 | Posture-over-time trend superpower only half-built: `trendValues(summary, points=22)` is defined with zero call sites (dead code) while only a single `health_delta` number + a thin client-side 7-bar proxy render. Render `trendValues` as a posture sparkline on Overview/Activity, or delete the dead helper. | feature-health | product-workflow-health (RH.2 history) | Yellow/Green | High | outcome: local-first superpower; failure-mode: partial feature shown as scaffolding | `dashboard-lint`; visual check when dashboard work is approved. |
| S-011 | Hands-off code-fix flow (`propose_fix → clean_room_review_packet → record_clean_room_review → land_fix`) — the strongest realization of the Brief's safe-AI-write ideal, fenced and tested — is reachable only via MCP rw mode with **no dashboard surface and no entry in the "real vs not yet" table**. Add a dashboard proposals surface (list → diff → clean-room verdict → land decision) mirroring the rotation flow, or explicitly document it as MCP-only in the real-vs-not-yet table. | feature-health | permission-boundary-health (sibling cluster, RH.4), documentation-health, release-readiness-health (US: shipped post-tag) | Yellow | High | outcome: powerful agent handoff / trust demonstrable; failure-mode: hidden value / partial feature | `dashboard-lint`; add `tests/test_dashboard_fix_proposals.py` exercising the new route. |
| S-012 | Activity event-feed filter chips are dead controls (no onClick, no state) — clickable-looking controls that do nothing, beside FindingsView chips that are fully wired. Wire them to filter the event feed, or render them as static labels (not chip affordances). | feature-health | behavioral-ux-health | Green/Yellow | High | failure-mode: janky UX; outcome: polished feature | `dashboard-lint`; click each chip in-browser and confirm it filters (final pass). |
| S-013 | No skip-to-content link past the 240px sidebar; keyboard/SR users tab through the whole nav on every view change. Add an `.sr-only`-revealed "Skip to content" link targeting `<main>` (utility already exists). | design-system-accessibility-health | behavioral-ux-health | Yellow | High | outcome: keyboard-navigable, accessible triage | Keyboard: Tab from page top surfaces the skip link first; verify it jumps focus to `<main>`. |
| S-014 | CHANGELOG ↔ tree drift: `git describe` = `v0.1.0-104-g5e114e6` (104 commits since the tag) yet the changelog has only the single `0.1.0` entry and **no `[Unreleased]` section**, and `pyproject.toml` is still `0.1.0`. Post-tag work (guarded MCP write-back, scan-trigger, clean-room reviewer, red-team e2e) is unrecorded; a clean next release can't be cut honestly. Add/maintain `[Unreleased]`, reconcile the 104 commits, decide on a `0.2.0` bump, cut tag + version + entry together. | release-readiness-health | feature-health, documentation-health | Yellow | High | outcome: version honesty real and reproducible | `git log v0.1.0..HEAD --oneline`; diff vs changelog; confirm next tag + version bump + entry land together. |
| S-015 | No a11y test / no test framework at all in `dashboard-ui` (`lint` = `tsc --noEmit` only); DESIGN.md §11's accessibility floor has no guard — exactly how the focus-ring and modal gaps slipped in. Add vitest + jest-axe smoke covering button names, dialog semantics, and focus-visible on key views. | design-system-accessibility-health | test-confidence-health (sibling cluster, RH.4), behavioral-ux-health | Yellow | High | outcome: polished, regression-guarded UX (enables S-008/S-009) | New vitest run; assert `toHaveNoViolations` on rendered views. |
| S-016 | AGENTS.md:41 understates the MCP adapter as "read-only access … stdio-only" only, contradicting README:43 and the entire `mcp/README.md` (which accurately documents the guarded `devsec-mcp-rw` write path); the canonical agent guide is the one doc denying a capability that ships. Fix the single line to name both `devsec-mcp` (read-only default) and `devsec-mcp-rw` (guarded write — `case_resolutions.v1`, high/critical suppression held for human confirmation, clean-room diff-only reviewer), or defer to mcp/README. | documentation-health | permission-boundary-health (sibling cluster, US.1), feature-health, release-readiness-health | Green/Yellow | High | failure-mode: confident falsehood (understated capability); outcome: trust demonstrable from docs | Confirm AGENTS.md text matches `pyproject.toml` entry points + mcp/README; cite permission-boundary lens for guard-enforcement verdict. |
| S-017 | Stale verification caveat: `.adx/verification.json` says pytest is "currently blocked until pytest exists in the selected Python environment," but `pyproject.toml` declares `pytest>=9.0.3`, the repo has 46–47 test files, and `.adx/commands.json` ships `python-dev-sync` + `python-pytest`; AGENTS.md unconditionally says "run `uv run pytest`." A fresh agent may conclude the suite can't run and skip the most important safety check. Confirm `uv sync --dev && uv run pytest` from a clean checkout, then delete/rewrite the caveat so AGENTS.md and the matrix agree. | documentation-health | release-readiness-health (RH.2), ai-maintainability-health (sibling cluster) | Yellow | High | outcome: version honesty real and reproducible | From a clean checkout: `uv sync --dev && uv run pytest`; update the note to match observed reality. |
| S-018 | Doc over-supply: 202 `.md` files, mostly `campaigns/*` + `reports/campaign-automation/*` history plus root scratch docs (`next-step.md`, `overview-redesign-*.md`); AGENTS.md "Start Here" names canonical files but does not demote the churn, so a fresh agent can mistake a stale plan for current intent. Extend "Start Here" to mark those as historical/working-notes (and consider relocating root scratch docs under `docs/notes/`). | documentation-health | ai-maintainability-health (sibling cluster) | Yellow | Medium | outcome: trust/maintainability of the agent contract | Confirm AGENTS.md enumerates canonical sources and demotes campaign/automation/scratch docs; spot-check 3 stale docs for date/"superseded" markers. |
| S-019 | Aliased/undocumented CLI verbs and `argparse.SUPPRESS` flags gate destructive ops (`reset`/`factory-reset`, `case-decision`/`resolve-cases`, `propose-fix`/`land-fix`, `review-fix`/`clean-room-review`, `vex-import/export`; `--confirm-suppression/--apply/--yes/--backup-to`) but their guard semantics live only in code, undocumented in prose. Document (or deliberately note as code-only) the security-sensitive verbs and suppression flags. | documentation-health | feature-health (US.4/US.5), permission-boundary-health (sibling cluster) | Green/Yellow | Medium | outcome: trust demonstrable; polished docs | `python -m security_observatory.cli --help`; confirm prose covers the security-sensitive verbs/flags or notes them code-only. |
| S-020 | Destructive-surface doc-to-guard fidelity unconfirmed (channel outage during the doc pass): Honey Keys safety claims (overwrite refusal, in-repo placement, insertion confirmation, hash-only) and the trust-boundary diagram are doc-to-doc consistent but not line-matched to `honey_keys.py`/`dashboard_server.py` guards / the real egress inventory. Line-match each documented claim to a concrete guard; cite privacy/permission lenses for enforcement verdicts. | documentation-health | privacy-boundary-health (sibling cluster), permission-boundary-health (sibling cluster) | Green/Yellow | Medium | failure-mode: broken trust on destructive ops (doc accuracy); outcome: trust demonstrable | Read the guard code; confirm each documented claim has a corresponding assertion/refusal path; cross-ref `05`/`04`. |
| S-021 | "Real vs not yet" honesty must stay true *after* the campaign's polish/feature work lands; pyproject `0.1.0` is now 104 commits stale vs the tree, and the code-fix flow (S-011) and trends/diff (S-007/S-010) are exactly the kind of "shipped but invisible / half-built" surfaces that can turn the table into a confident falsehood as work lands. Re-read the table vs shipped behavior in `feature-health-final`. | release-readiness-health | feature-health, documentation-health | Green/Yellow | High | failure-mode: confident falsehood; outcome: version honesty true after the work lands | Re-read the table vs shipped behavior in `feature-health-final`; confirm version triple agrees at next bump. |
| S-022 | Token-inlining drift on some surfaces: 60 hardcoded hex + 212 rgba outside `:root` despite 69 tokens / 839 `var()` uses (top `#fff`×32, brand-green ×5), plus mixed styling idioms (named Mistglass classes in `App.tsx`/`index.css` vs raw Tailwind `black/white` opacities in `OverviewView.tsx`, and a stray `styled` import). Maintainability/theming drag for a future dark mode; quiet palette drift. Sweep `#fff`/brand-green inlines on shared primitives to tokens; decide one styling idiom. | design-system-accessibility-health | architecture-health (sibling cluster) | Green/Yellow | High | outcome: crafted, coherent, intentional design system | Visual diff after sweep; `vite build`. |

### Scout — Preserved feature candidates (NOT repair items; for a later decision)

These are the ranked feature-discovery short-lists from `feature-health` and `product-workflow-health`, captured verbatim per the Brief's success criteria ("recorded, not lost"). They are candidates, not commitments; several overlap repair rows above (cross-noted).

Feature-health scout (leverage × local-first/trust fit):

- **S-C1** — Case lifecycle with proof-bound closure: explicit `in_progress` → `verifying` → `closed`, each closure linked to the diff + rescan that closed it. (Highest leverage; also repair S-003.)
- **S-C2** — Posture-over-time trend view: real local-first sparkline/timeline of health score per repo from the SQLite history store (`trendValues` already a stub). (Pure superpower, no trust cost; relates to S-010/S-007.)
- **S-C3** — Local, no-cloud shareable posture report: export a self-contained HTML/PDF snapshot (cases + trend + diff) to hand to a teammate without any upload. Builds on the existing Reports/export surface.
- **S-C4** — In-dashboard code-fix review: surface the MCP propose/clean-room/land flow in the UI for non-MCP users. (Closes S-011.)
- **S-C5** — Scan scheduling / watch mode in the UI: `schedule`/`cron` exists in the CLI but is not a dashboard feature; a "rescan on a cadence / on git change" toggle would make the loop continuous and local-native.
- **S-C6** — Cross-repo posture rollup ("fleet view"): `--all-repos` discovery exists; a portfolio dashboard ranking repos by posture/regressions for small teams.
- **S-C7** — Suppression/decision expiry + re-review reminders: accepted-risk / false-positive decisions never expire; a "review again in N days / on next matching finding" mechanism prevents silent stale suppressions and strengthens trust.

Product-workflow scout (leverage on the core loop):

- **S-C8** — One-click "rescan this case to confirm closure": from a decided case, trigger a scoped rescan and auto-flip to `verified` (with resolving scan id) when its fingerprint lands in scan-diff `resolved[]`. (Operationalizes S-003.)
- **S-C9** — Keyboard-navigable triage queue: j/k to move, hotkeys for Verify / False positive / Accept / Fixed over open cases — inbox-zero for findings. (Serves the Brief's "fast, keyboard-navigable, even satisfying.")
- **S-C10** — Posture-over-time trend view that names regressions ("fixed 6, 2 regressed since last week"), built on the dark `/api/scan-history`. (Relates to S-007.)
- **S-C11** — Arbitrary scan-to-scan compare picker (base/head) — server already supports it. (Relates to S-007.)
- **S-C12** — Decisions that carry forward across rescans, shown explicitly ("you marked this accepted_risk on 2026-05-20") so the user isn't re-triaging the same finding each scan. (VEX + `case_decisions` exist; the carry-forward-and-show-it workflow should be explicit.)
- **S-C13** — Bulk per-severity manual decisions on the Cases tab ("accept all low," "false-positive these 3") — a manual analogue of the AI batch, without leaving for the JSON panel.

## Ledger Coverage

Mechanical completeness check. Every cluster-owned ledger ID (lenses: feature-health, product-workflow-health, behavioral-ux-health, design-system-accessibility-health, documentation-health, release-readiness-health) maps to exactly one outcome. IDs copied verbatim from the ledger JSON.

| Ledger ID | Outcome | Mapped to | Note |
| --- | --- | --- | --- |
| F-feature.RH.1 | own | S-011 | Hands-off code-fix flow has no dashboard surface. |
| F-feature.RH.2 | own | S-003 | Case lifecycle: no in-progress/verifying intermediate state. |
| F-feature.RH.3 | own | S-010 | `trendValues` dead code; posture trend half-built. |
| F-feature.RH.4 | own | S-012 | Activity event-feed filter chips are dead controls. |
| F-feature.RH.5 | cross-ref | S-003 | Honey Keys incident lifecycle cited as a finished reference model alongside rotation for the case-lifecycle build; no own repair (Green). |
| F-feature.RH.6 | cross-ref | S-003 | Secret rotation state machine is the in-repo reference pattern for the case lifecycle; Green, no own repair. |
| F-feature.RH.7 | cross-ref | S-007 | Core scan trigger (Green) is the scan half of the loop the dark history/diff endpoints sit on top of. |
| F-feature.RH.8 | cross-ref | S-007 | Scan-to-scan diffing UI (Green) is the surface S-007's base/head picker extends. |
| F-feature.RH.9 | cross-ref | S-C3 | Reports surface (Green) is the base for the no-cloud shareable posture report candidate; no repair. |
| F-feature.RH.10 | cross-ref | S-021 | Tool Catalog + install-state contract (Green) feeds the "real vs not yet" honesty watch item. |
| F-feature.RH.11 | cross-ref | S-011 | AI case-resolution follow-up (Green) is the trust-safe sibling of the code-fix flow; no own repair. |
| F-feature.RH.12 | cross-ref | S-016 | Read-only MCP adapter (Green) is the surface AGENTS.md understates. |
| F-feature.RH.13 | cross-ref | S-020 | Reset/data-clearing (Green) is a destructive surface whose doc-to-guard fidelity S-020 confirms. |
| F-feature.RH.14 | deferred | brief out-of-scope: External Surface scanning + runnable packs (display-only; honest "Coming Soon") | Graded Grey; correctly out of scope. |
| F-feature.US.1 | cross-ref | S-011 | Hidden code-fix flow surface. |
| F-feature.US.2 | cross-ref | S-010 | `trendValues` hidden/dead helper. |
| F-feature.US.3 | cross-ref | S-012 | Activity filter chips hidden dead control. |
| F-feature.US.4 | merged | S-019 | Hidden CLI subcommands via positional target merged into the documentation row that documents the undocumented/suppressed CLI surface; faithful because both name the same code-only command surface needing prose. |
| F-feature.US.5 | merged | S-019 | `vex-export`/`vex-import` hidden CLI capability merged into S-019 (undocumented CLI verbs needing prose); faithful — same surface, same fix. |
| F-feature.TR.1 | own | S-011 | Top repair: dashboard surface for the code-fix flow (or document MCP-only). |
| F-feature.TR.2 | own | S-003 | Top repair: visible lifecycle with proof-bound closure. |
| F-feature.TR.3 | merged | S-010 | Top repair "finish/remove trend + wire chips" — trend half is S-010; chip half is S-012. Merged to S-010 as the canonical trend row; faithful because S-012 carries the chip half explicitly. |
| F-product-workflow.RH.1 | cross-ref | S-003 | Rescan-to-closure doesn't actively show the proof — sibling echo of the feature-owned lifecycle row. |
| F-product-workflow.RH.2 | own | S-007 | `scan-history` superpower wired server-side, absent from UI. |
| F-product-workflow.RH.3 | own | S-007 | `/api/scan-diff` base/head built but unreachable (same dark-superpower row). |
| F-product-workflow.RH.4 | own | S-004 | Orphaned parallel case UI shadowing the live act path. |
| F-product-workflow.RH.5 | cross-ref | S-002 | AI follow-up act path (Green/Yellow): JSON-paste friction echoes the window.prompt/native-friction theme; no own repair (power path acceptable). |
| F-product-workflow.RH.6 | cross-ref | S-003 | Triage entry/grouping/decision controls (Green) — the working spine the lifecycle row builds on. |
| F-product-workflow.RH.7 | cross-ref | S-007 | Scan entry + rescan loop (Green) — the scan half feeding history/diff. |
| F-product-workflow.US.1 | cross-ref | S-007 | `GET /api/scan-history` no UI consumer. |
| F-product-workflow.US.2 | cross-ref | S-007 | `/api/scan-diff` base/head unreachable from UI. |
| F-product-workflow.US.3 | cross-ref | S-016 | `GET /api/cases` no UI consumer — API/MCP convenience needing documentation; folds into the doc-accuracy theme. |
| F-product-workflow.US.4 | cross-ref | S-004 | Orphaned parallel case UI hidden surface. |
| F-product-workflow.US.5 | cross-ref | S-019 | CLI act path parallel to dashboard (import-resolutions) — the documentation-worthy automation twin. |
| F-product-workflow.TR.1 | cross-ref | S-003 | Top repair: close the loop with visible proof — sibling echo of feature-owned S-003. |
| F-product-workflow.TR.2 | own | S-007 | Top repair: surface history/trends + arbitrary diff. |
| F-product-workflow.TR.3 | own | S-004 | Top repair: delete/adopt the orphaned case-UI trio. |
| F-behavioral-ux.RH.1 | own | S-001 | First-run add-repo via raw window.prompt. |
| F-behavioral-ux.RH.2 | own | S-002 | window.prompt recurs across the core loop. |
| F-behavioral-ux.RH.3 | own | S-004 | Duplicate FindingsView + off-Mistglass CaseCard dead twin (UX-owned, design echoes). |
| F-behavioral-ux.RH.4 | own | S-005 | `⌘K` hint with no handler (false affordance). |
| F-behavioral-ux.RH.5 | own | S-006 | Scan-failure feedback collapses to one undifferentiated error. |
| F-behavioral-ux.RH.6 | cross-ref | S-006 | Loading & first-fetch-failure states (DESIGN §7.6/§7.5) — same crafted-error/loading-state surface as S-006. |
| F-behavioral-ux.RH.7 | cross-ref | S-022 | Severity tuning / alarm-fatigue (Green/Yellow): the one watch item (hot `crit.bg` token) folds into the token-adherence sweep. |
| F-behavioral-ux.RH.8 | cross-ref | S-008 | Keyboard nav / focus order / modal Esc-trap — sibling echo of the design-system focus-ring (S-008) and dialog (S-009) rows. |
| F-behavioral-ux.US.1 | cross-ref | S-004 | Dead components/FindingsView + CaseCard hidden surface. |
| F-behavioral-ux.US.2 | cross-ref | S-005 | ⌘R/Ctrl-R hard-refresh global shortcut — the only global shortcut, making the dead ⌘K more glaring. |
| F-behavioral-ux.US.3 | cross-ref | S-015 | Hidden `?setupCardDemo=1` storybook route — undocumented visual-verification route; record it (doc/test harness scope). |
| F-behavioral-ux.US.4 | cross-ref | S-016 | Tab set wider than AGENTS.md route memory — under-documented views; folds into the doc-accuracy/route-memory theme. |
| F-behavioral-ux.US.5 | cross-ref | S-001 | `add-repo` dropdown option fires a native prompt — feeds the add-repo repair. |
| F-behavioral-ux.US.6 | cross-ref | S-001 | Custom repos persisted to localStorage — shapes the add-repo form's recent-suggestions source. |
| F-behavioral-ux.US.7 | cross-ref | S-021 | Coming-Soon walls reachable from navigable surfaces — confirm they read as honestly not-yet (real-vs-not-yet honesty); building them is out of scope. |
| F-behavioral-ux.TR.1 | cross-ref | S-001 | Top repair: replace raw window.prompt add-repo flow. |
| F-behavioral-ux.TR.2 | cross-ref | S-002 | Top repair: get window.prompt out of the core loop. |
| F-behavioral-ux.TR.3 | cross-ref | S-004 | Top repair: resolve Cases duplication + false ⌘K (S-004 + S-005). |
| F-design-system-accessibility.RH.1 | own | S-009 | Modals declare role=dialog but lack focus trap/Escape/restore. |
| F-design-system-accessibility.RH.2 | own | S-008 | No global visible focus indicator; the two :focus-visible rules remove the outline. |
| F-design-system-accessibility.RH.3 | own | S-015 | No a11y test / no test framework in dashboard-ui. |
| F-design-system-accessibility.RH.4 | own | S-013 | No skip-to-content link past the sidebar. |
| F-design-system-accessibility.RH.5 | cross-ref | S-022 | Severity partly signaled by color-only elements (rail/gauge) — mitigated by adjacent text; folds into the design-coherence/token sweep watch. |
| F-design-system-accessibility.RH.6 | cross-ref | S-008 | DESIGN.md §11 promises vs built behavior (focus ring/dialogs/live regions) — closed by S-008+S-009 (+ doc reconcile in S-020-adjacent). |
| F-design-system-accessibility.RH.7 | own | S-022 | Token-inlining drift on some surfaces. |
| F-design-system-accessibility.RH.8 | deferred | brief out-of-scope: cross-platform/dark-mode beyond MVP (no dark-mode/high-contrast path; DESIGN.md references it aspirationally) | Graded Green/Yellow; treated as a candidate, kept honest in DESIGN.md, not built this pass. |
| F-design-system-accessibility.RH.9 | cross-ref | S-008 | Design-system consistency/crafted states (Green) — the healthy primitive base that hosts the focus/dialog fixes. |
| F-design-system-accessibility.US.1 | cross-ref | S-022 | App.tsx 4027-line monolith holding most markup — raises cost of threading global a11y primitives; architecture sibling cluster owns the split, design-coherence echo here. |
| F-design-system-accessibility.US.2 | cross-ref | S-009 | Four parallel modal/overlay implementations — the duplication a single shared Dialog primitive fixes. |
| F-design-system-accessibility.US.3 | cross-ref | S-015 | No test framework at all in dashboard-ui. |
| F-design-system-accessibility.US.4 | cross-ref | S-022 | `styled` import in RotationTriggerFlow — styling-idiom inconsistency folded into the token/idiom decision. |
| F-design-system-accessibility.US.5 | cross-ref | S-022 | Mixed BEM-ish CSS + Tailwind utility idioms — same styling-idiom drift row. |
| F-design-system-accessibility.TR.1 | cross-ref | S-009 | Top repair: shared Dialog primitive + migrate 4 modals. |
| F-design-system-accessibility.TR.2 | cross-ref | S-008 | Top repair: global visible focus indicator. |
| F-design-system-accessibility.TR.3 | cross-ref | S-015 | Top repair: a11y test harness + skip link + §11 reconcile (S-015 + S-013). |
| F-documentation.RH.1 | own | S-016 | AGENTS.md understates the MCP adapter as read-only. |
| F-documentation.RH.2 | own | S-017 | Stale `.adx/verification.json` pytest-blocked caveat. |
| F-documentation.RH.3 | own | S-018 | Doc over-supply: no canonical-vs-working-notes boundary. |
| F-documentation.RH.4 | own | S-020 | Honey Keys safety claims vs code guards (doc-to-guard fidelity unconfirmed). |
| F-documentation.RH.5 | cross-ref | S-020 | Trust-boundary / no-egress promise documented vs demonstrable — same destructive/egress doc-fidelity row (privacy lens owns enforcement). |
| F-documentation.RH.6 | cross-ref | S-019 | README ⇄ CLI accuracy (Green); the gap is the aliased verbs/flags S-019 documents. |
| F-documentation.RH.7 | cross-ref | S-018 | Agent-contract layer freshness — folds into the canonical-vs-working-notes + manifest-freshness boundary. |
| F-documentation.RH.8 | cross-ref | S-018 | Core human docs (Green) with a glossary-vs-vocabulary divergence watch — folds into the doc-hygiene boundary row. |
| F-documentation.US.1 | cross-ref | S-016 | MCP write mode absent from AGENTS.md. |
| F-documentation.US.2 | cross-ref | S-019 | Aliased/undocumented CLI verbs. |
| F-documentation.US.3 | cross-ref | S-019 | Hidden argparse SUPPRESS flags gating destructive ops. |
| F-documentation.US.4 | cross-ref | S-017 | `.adx/verification.json` pytest-blocked caveat buried where AGENTS.md readers won't see it. |
| F-documentation.US.5 | cross-ref | S-018 | Root scratch docs + large campaigns/automation corpus unmarked as historical. |
| F-documentation.TR.1 | cross-ref | S-016 | Top repair: fix the AGENTS.md MCP understatement. |
| F-documentation.TR.2 | cross-ref | S-017 | Top repair: refresh the stale verification caveat. |
| F-documentation.TR.3 | cross-ref | S-018 | Top repair: canonical-vs-working-notes boundary + finish destructive-surface doc checks (S-018 + S-019 + S-020). |
| F-release-readiness.RH.1 | own | S-014 | CHANGELOG ↔ tree drift (no record of post-tag work). |
| F-release-readiness.RH.2 | cross-ref | S-017 | Test/lint/build pass result not observed (sandbox lacked `timeout`) — closes with the same clean-checkout pytest run as S-017; CI gates it. |
| F-release-readiness.RH.3 | deferred | brief out-of-scope (release-ops verification, not a product surface): branch-protection enforcement on `main` needs an online `gh api` read | Green/Yellow; checks run on main, "required" status unconfirmed offline; verify at release, not a campaign repair. |
| F-release-readiness.RH.4 | cross-ref | S-014 | Local SQLite migration safety (Green/Yellow) — the optional `PRAGMA user_version` polish is owned by data-contract sibling cluster; release row is healthy, no own repair. |
| F-release-readiness.RH.5 | cross-ref | S-014 | CI ↔ local parity (Green) — preserve when version/changelog discipline (S-014) lands. |
| F-release-readiness.RH.6 | cross-ref | S-021 | Install-path honesty (Green) — part of the "real vs not yet" honesty that must stay true after the work lands. |
| F-release-readiness.RH.7 | own | S-021 | Version-honesty surface ("real vs not yet" + SECURITY policy) must stay true after polish/feature work. |
| F-release-readiness.RH.8 | cross-ref | S-014 | Released-version internal consistency (Green) — re-confirm the version triple at next bump (S-014). |
| F-release-readiness.US.1 | cross-ref | S-014 | Guarded MCP write-back shipped post-tag, absent from changelog — the unrecorded post-tag work S-014 reconciles. |
| F-release-readiness.US.2 | deferred | brief out-of-scope (supply-chain/CI-ops, not a product surface this campaign repairs): `security.yml` scanner bootstrap network/machine installs | Tag-pinned + allowlist-justified; keep pinned and reviewed at release; not a cluster repair. |
| F-release-readiness.US.3 | cross-ref | S-014 | Local SQLite history-store schema (19 tables) — migration discipline tied to the release/version-bump process (S-014). |
| F-release-readiness.TR.1 | own | S-014 | Top repair: fix changelog/version discipline before the next release. |
| F-release-readiness.TR.2 | cross-ref | S-017 | Top repair: observe the three CI-gated checks locally — same clean-checkout run as S-017. |
| F-release-readiness.TR.3 | deferred | brief out-of-scope (release-ops, online read-only): confirm `main` branch protection enforces the verify checks | Verify at release; not a product repair this campaign. |

## Cross-Cutting Patterns

1. **Built-but-dark capability inversion** — powerful machinery that never reaches the user-facing surface. Items: S-007, S-010, S-011 (and candidates S-C2, S-C3, S-C4, S-C10, S-C11). The hands-off code-fix flow, posture-trend, scan-history, and arbitrary scan-diff are all real and tested yet invisible in the dashboard. The fix is surfacing, not building.
2. **Core-loop touchpoints drop to uncrafted primitives** — the Brief's first-class "janky/dead-end UX" failure. Items: S-001, S-002, S-005, S-006, S-012. Raw `window.prompt` at the gateway and at resolution, a dead ⌘K affordance, undifferentiated scan errors, and dead filter chips all puncture the otherwise-calm triage spine at the exact moments of action.
3. **The case lifecycle stops one step short of the product's signature feel** — closure by absence, not proof. Items: S-003, S-007 (and candidates S-C1, S-C8, S-C12). The pieces (decision controls, diff `resolved[]`, rotation's state-machine pattern) exist; what's missing is an intermediate state and a visible binding of a closed case to the scan that closed it.
4. **Accessibility is present-but-uneven, with a duplicated keyboard gap** — markup is there; keyboard/focus behavior is not, and nothing guards it. Items: S-008, S-009, S-013, S-015 (+ behavioral-ux RH.8 echo). No global focus ring, four modals with no Escape/trap, no skip link, and no a11y test harness — the missing harness is *why* the floor silently rotted.
5. **Honest-but-drifting docs and release metadata** — the trust story is strong but has narrow factual cracks. Items: S-014, S-016, S-017, S-018, S-019, S-020, S-021. One AGENTS.md line understates the write path, a stale verification caveat, 104 unrecorded post-tag commits, and undocumented destructive CLI verbs — each small, each a confident-falsehood risk for a trust-pitched security tool.
6. **One dead/duplicate React surface multiplies risk** — the orphaned `components/` case-UI trio and four ad-hoc modals. Items: S-004, S-009, S-022. A flaw (or off-system style, or missing focus behavior) in a duplicated primitive multiplies; collapsing to one canonical Cases component and one shared Dialog fixes several rows at once.

## Excellence Gaps

Brief outcomes these cluster lenses bear on but under-covered, with why and what would close them:

- **"Crafted loading state (static placeholder, no spinner/shimmer)" is unverified, not confirmed.** Behavioral-ux flagged that list/view transitions use motion fades and could not confirm the initial load / failed-first-`/api/summary` render a crafted card vs blank/raw, because the dashboard was correctly not started this pass (guardrails). The mandatory final behavioral-ux pass (in a running browser) closes it; until then it is a known unverified surface, not a clean Green.
- **Contrast was not measured against rendered pixels.** Design-system graded contrast Grey/unverified (no live axe/Lighthouse): mid-tone tokens (`--ink-faint` on `--paper`, `--sev-warn`) look AA-plausible but unproven. A real contrast tool pass on the final UI would close it; the cluster cannot assert Green on contrast from static evidence.
- **"Even satisfying / delightful" triage is asserted structurally, not felt.** No lens drove the running product (no keyboard walk, no screenshot, no felt-speed read), so the Brief's emotional bar ("satisfying," "delight") is inferred from source craft. Only the second behavioral-ux pass and a live product-walkthrough can confirm the felt experience after S-001/S-002/S-003 land — this is the campaign's deliberate single-pass trade-off, not a missed lens.

## Review Pass

| Review finding | Verdict | How it was handled |
| --- | --- | --- |
| pending — performed at merge level | pending | This is a cluster pass; the mandatory second-agent review runs at the merge synthesis, not here. |

## Suggested Plan Structure

Batched cross-cutting where possible — one fix surface lifting multiple owning lenses at once. Highest-leverage UX-headline batches first.

1. **De-jank the core-loop touchpoints** — items S-001, S-002, S-005, S-006, S-012: a single "replace native/dead primitives with crafted Mistglass surfaces" pass (add-repo form, inline note fields, ⌘K decision, differentiated error cards, live/static chips). One UX fix surface, the campaign headline.
2. **Visible proof-bound case lifecycle + surface the dark superpowers** — items S-003, S-007, S-010: add the in-progress/verifying state and bind closure to the resolving scan/diff, then light up scan-history + base/head diff + the trend sparkline (they share the history/diff data path). Closes the loop *and* delivers the local-first superpowers in one coherent feature batch.
3. **One canonical Cases surface + shared Dialog + focus/a11y floor** — items S-004, S-008, S-009, S-013, S-015, S-022: delete the orphaned case-UI trio, build one shared Dialog (trap/Escape/restore) for all four modals, add the global focus ring + skip link, sweep token/idiom drift, and stand up the vitest+jest-axe harness that guards all of it. One design-system fix surface; the harness must land with the focus/dialog fixes so they can't regress.
4. **Surface or document the hands-off code-fix flow** — item S-011 (+ candidate S-C4): a dashboard proposals view mirroring rotation, or an explicit "real vs not yet" MCP-only note. Pairs naturally with batch 2's lifecycle work (both touch the act leg).
5. **Doc + release honesty reconcile** — items S-014, S-016, S-017, S-018, S-019, S-020, S-021: one documentation/release pass — fix the AGENTS.md MCP line, refresh the stale pytest caveat, add `[Unreleased]` + reconcile the 104 commits, mark canonical-vs-working-notes, document the security-sensitive CLI verbs/flags, line-match destructive-surface guards, and re-assert the "real vs not yet" table true after the product work lands.

## Limits

- **No running product.** Per AGENTS.md + `.adx/risks.json`, no lens started the dashboard server, `security-scan`, the desktop launcher, or a browser. All UI/loop findings are source-anchored (render sites + handlers + tested endpoints), not live click-throughs. Loading-state craft, contrast against pixels, modal keyboard behavior, and differentiated scan-error rendering are inferred from source and flagged for the mandatory final behavioral-ux pass and a live walkthrough.
- **Single-pass staleness.** These are initial forensic reads; some findings may shift before repair (the cluster's strong-but-finishable shape absorbs most of it). The `feature-health-final` and second `behavioral-ux-health` passes re-confirm what survives.
- **Validation gates partly unobserved.** `uv run pytest`, `npm run lint`, and `npm run build` were not first-hand observed in several reports (a missing `timeout` shim and intermittent tool-output outages); CI gates all three, and the fast import + a clean `tsc`/`vite build` were observed elsewhere, but the cluster does not assert a tested-green it did not see (drives S-017 / release RH.2).
- **Intermittent tool-output channel outage during this synthesis.** The Bash/Read output channel went dark for a stretch while assembling the ledger slice. The cluster ID set in the Ledger Coverage table was reconstructed from the fully-read forensic reports (each report's RH/US/TR sections map 1:1 to ledger RH.n/US.n/TR.n) and the directly-read feature-health ledger slice; the self-verify step (`verify_synthesis_coverage.py`) is the mechanical check of record and was run to confirm completeness.
- **Sibling-cluster boundaries respected.** CSRF/permission enforcement, no-egress proof, normalization fidelity, the dashboard_server/storage/App.tsx architectural splits, `PRAGMA user_version`, and CI/branch-protection ops belong to other clusters; cited here where a cluster row leans on them, not re-derived.
