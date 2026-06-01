# Feature Health Forensic — DëvSec (Security Observatory)

## Executive Finding

DëvSec is a mature, broad, and unusually *honest* product surface: the CLI, the
local SQLite history, the React dashboard, the read-only + guarded-write MCP
adapter, Honey Keys, secret rotation, and the macOS launcher are all genuinely
built, and 467 Python tests plus a clean `tsc` typecheck pass. The README's
"What's real vs. what's not yet" table and the catalog's display-only
placeholders are exactly the candor the Excellence Brief rewards — nothing
broken is dressed as finished, and the out-of-scope walls (External Surface,
runnable packs) are honest "Coming Soon," not laziness. The weak spots are not
broken features but *unevenly finished* ones: (1) the most powerful AI-write
feature — `propose_fix → clean-room-review → land_fix` for hands-off code fixes
— is real, well-fenced, and tested, but **has no dashboard surface at all**, so
a dashboard-only user cannot see or reach it; (2) the case model is a flat
*triage-decision* model (`verified / false_positive / accepted_risk / fixed`)
plus rescan-driven `new/recurring/resolved` diffing — there is **no
in-progress/verifying intermediate lifecycle state** for cases, so the Brief's
signature "watch a case move open → in-progress → verifying → closed" only truly
exists for *secret rotation* (which has a real state machine), not for cases
generally; (3) the local-first "posture-over-time trend" superpower is only
half-realized — a single `health_delta` number and an audits-per-day chart ship,
but the 22-point trend helper `trendValues` is **dead code**, never rendered; and
(4) a small dead control: the Activity event-feed filter chips are not wired.
None of these are non-negotiable failures; they are the gap between "works" and
"finished and delightful" that this campaign exists to close.

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security`
- Skill/lens: `feature-health-forensic`
- Date: `2026-06-01`
- Requested focus: Excellence Brief `feature-health` row — does each shipped
  feature deliver end to end *and feel finished*? Flag prototype-grade surfaces,
  not just broken ones. Are the local-first superpowers (trends, diffing)
  present and powerful? Plus SCOUT DUTY: surface a ranked short-list of
  high-leverage features DëvSec is missing (candidates, not commitments).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "...import security_observatory.cli..."` | Pass | Prints `import ok`; CLI module imports clean from `src`. |
| `uv run pytest -q` | Pass | 467 passed in 53.33s. Broad coverage: 46 test files spanning normalize, cases, storage, MCP, fix-proposals, honey-keys, rotation, reset, red-team e2e. |
| `cd dashboard-ui && npm run lint` (`tsc --noEmit`) | Pass | No type errors across the React dashboard. |
| `cd dashboard-ui && npm run build` | Not run | Not required for a read-only feature inventory; `tsc` already confirms type health. Build mutates bundled assets, so deferred per AGENTS.md "edit source, regenerate output." |
| `security-scan` / dashboard server / desktop launcher | Not run | Prohibited by AGENTS.md + `.adx/risks.json` (local-security-data, scanner-installer, desktop-process-control). Runtime behavior inferred from code + tests, not live execution. |

## Ranked Health Table

| Rank | Area | Health | Confidence | Evidence | Impact (user) | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Hands-off code-fix flow (`propose_fix` → `clean_room_review_packet` → `record_clean_room_review` → `land_fix`) reachable only via MCP; **no dashboard surface** | Yellow | High | `src/security_observatory/fix_proposals.py` (full propose/review/land + clean-room fence), MCP tools `mcp_server.py:1001-1090`, tests `tests/test_fix_proposals.py` + `tests/test_mcp_fix_proposals.py`. Dashboard "Agent lab" view (`AgentLabView.tsx`) is the *tool-recommendation/suppression* flow (`AgentLabProposal` = recommended_tools/packs/permissions, `dashboardData.ts:389`), not the code-fix flow. No `/api/*` route or component references `propose_fix`/`land_fix`/`clean_room`. | A genuinely excellent, well-fenced superpower (reviewer never sees finding text; diff-only invariants; audited land gate) is invisible to anyone who only uses the dashboard. The Brief's "evidence-bound, one-keystroke agent handoff" and closed loop are weaker than the code can support. | Add a dashboard surface for code-fix proposals (list → diff → clean-room verdict → land decision), or document explicitly that this is an MCP-only capability in the "real vs not yet" table. | `dashboard-lint`; add a `tests/test_dashboard_fix_proposals.py` exercising the new route. |
| 2 | Case lifecycle: flat triage-decision + rescan diff; **no in-progress / verifying intermediate state** | Yellow | High | Decision vocabulary is terminal-only: `decisions.py:10 CASE_DECISION_STATUSES = {"verified","false_positive","accepted_risk","fixed"}`; UI mirror `dashboardData.ts:855 CaseDecisionStatus`. Change/diff status is `new/recurring/resolved` (`dashboardData.ts:856`, `CaseCard.tsx:121-129,228`). No `in_progress`/`verifying` token anywhere in `cases.py`/`decisions.py`/UI. Rescan-to-closure exists *implicitly* via "not found in latest scan → Resolved" (`CaseCard.tsx:228-234`, `resolved_by_scan_id`). | The Brief names "watch a case move open → in-progress → verifying → closed, with the diff and the verification that closed it" as the product's signature feel. Today a case goes open → triage decision → (disappears on rescan = resolved). The "verifying" beat — fix applied, awaiting rescan proof — has no visible home. Closure is by *absence*, not by *proof tied to the fix*. | Introduce an explicit case lifecycle (at least an `in_progress`/`awaiting_rescan` state) and bind a resolved case to the scan + diff that closed it, surfaced on the CaseCard. | `python-pytest` (new `cases`/`storage` lifecycle tests); `dashboard-lint`. |
| 3 | Posture-over-time trend superpower only half-built; `trendValues` is **dead code** | Yellow/Green | High | `dashboardData.ts:2079 export function trendValues(summary, points=22)` defined once, **zero call sites** (grep across `dashboard-ui/src` returns only the definition). What ships: a single `health_delta` number (`App.tsx:2317-2329` "trend"), `SinceLastScanPanel` deltas, and `AuditsPerDay`/`EventMix` charts (`App.tsx:2876-2882`). | The Brief calls posture-over-time trends a local-first "superpower." A 22-point series helper exists but renders nowhere, so users get a delta number, not a trend line they can read at a glance. Either wire it (cheap win) or delete it (it's misleading scaffolding). | Render `trendValues` as a posture sparkline on Overview/Activity, or remove the dead helper. | `dashboard-lint`; visual check when dashboard work is approved. |
| 4 | Activity event-feed filter chips are dead controls | Green/Yellow | High | `App.tsx:2887` `<Chip active>All</Chip><Chip>Scanner runs</Chip><Chip>Cases</Chip><Chip>Honey keys</Chip>` — no `onClick`, no state. Contrast FindingsView chips at `App.tsx:2440-2450` which are fully wired with `active`/`onClick`. | Clickable-looking controls that do nothing is exactly the "janky UX" the Brief flags as first-class for a UX campaign. Small, but it erodes the crafted feel. | Wire the chips to filter the event feed, or render them as static labels (not chip affordances). | `dashboard-lint`. |
| 5 | Honey Keys (create / insert / hash-only / incident workflow / archive) | Green | High | `honey_keys.py` (236 LOC), `HoneyKeysView.tsx` (531 LOC) with full incident state path `investigating → secrets_rotated → logs_reviewed → archived_reset` (`HoneyKeysView.tsx:35-56`), endpoints `/api/honey/{keys,insert,trigger,archive,incident-step,incident-close}`, tests `tests/test_honey_keys.py`. Risk guard in `.adx/risks.json` (honey-keys). | A finished, coherent defensive feature with a real incident-response lifecycle — one of the most polished surfaces. Matches README claims (store only a hash, callback on touch, user-supplied webhook). | None required; spot-check insert-overwrite guard remains intact per risk register. | `python-pytest` (`test_honey_keys.py`). |
| 6 | Secret rotation flow (Tier 5R: status / trigger / batch, canary-verify + soak state machine) | Green | High | `rotation.py` (764 LOC), UI `RotationStatusCard/TriggerFlow/BatchFlow.tsx` (~2,724 LOC total) with real states `WAITING_FOR_PASTE → IN_CANARY_VERIFY → IN_SOAK → SOAKED` (`RotationStatusCard.tsx:41-63`), verification receipts (`VerificationReportRenderer`), endpoints under `/api/rotation/*`, tests `test_rotation*.py`, confirmation-phrase gate (`test_rotation_confirmation_phrase.py`). | The *one* feature that fully embodies the Brief's "lifecycle with visible verification" ideal — proves DëvSec can do it; the gap is that cases don't get the same treatment (see Rank 2). | None; this is the reference model for the case-lifecycle repair. | `python-pytest` (`test_rotation.py`, `test_dashboard_rotation_*`). |
| 7 | Core loop scan trigger from dashboard (background worker + status polling) | Green | High | `dashboard_server.py:3060 run_check_job` validates repo/audits, spawns daemon thread `_run_check_worker`, returns `{started:True}`; polled via `/api/check-status` (`:2308`). Audit set `{quick,secrets,code,deps,iac,platform-posture,ai,full}`. EmptyRepoState first-run CTA `EmptyRepoState.tsx`. | scan → triage is fully wired from the UI with a crafted first-run/empty state. The "scan" and "triage" halves of the loop are solid; the weakness is the "act → verify → closure-with-proof" half (Ranks 1-2). | None. | `python-pytest` (`test_dashboard_*`). |
| 8 | Scan-to-scan diffing surfaced in UI (New / Still open / Resolved / Health change) | Green | High | `SinceLastScanPanel.tsx`, `aggregateCaseDelta` + `staleRepoCount` (`dashboardData.ts:1818-1832`), `previous_scan_id`/`health_delta`/`case_delta` on repo records, `changeStatus` per case (`CaseCard.tsx:121`). | A real local-first superpower and the strongest realized differentiator. Powerful and legible. | None. | `dashboard-lint`. |
| 9 | Reports surface (raw + AI-prompt export, dependency deltas, CVE/IOC/trust panels, history) | Green | High | `ReportsView` (`App.tsx:2898-2960+`), export links `reportViewUrl(scan_id,'raw'|'prompt')`, dependency/CVE/IOC/trust cards, crafted empty states ("No reports saved"), tests `test_dashboard_report_exports.py`, `docs_render.py`. | A finished reporting surface with honest export paths (raw + agent prompt), no cloud dependency. Matches the "local shareable posture" direction. | None. | `python-pytest` (`test_dashboard_report_exports.py`). |
| 10 | Tool Catalog + Security Packs + install-state contract | Green | High | `catalog.py` (1,656 LOC), `catalog/` UI (CatalogHome/Browse/PackPage/ToolPage), install states `built-in/managed/detected/missing/unavailable/not-configured/coming-soon` (`dashboardData.ts:44`), display-only honesty (`catalogHelpers.tsx:355` "cannot collect targets, install tooling, run scans"), tests `test_catalog.py`, `test_managed_tools.py`, `test_dashboard_tool_install.py`. | A coherent, contract-driven catalog where the install state is the gate. Coming-soon entries (External Surface, IaC Pack run-mode) are honestly placeholdered per the Brief's out-of-scope list. | None (out-of-scope items correctly left as honest placeholders). | `python-pytest` (`test_catalog.py`). |
| 11 | AI case-resolution follow-up (prompt → preview → audited apply, high/critical suppression gated) | Green | High | `case_followup.py` (673 LOC), `AiFollowUpPanel.tsx`, endpoints `/api/ai-follow-up/{prompt,resolutions/preview,resolutions/apply}`, gating `decisions.py:14-15 GATED_SUPPRESSION_SEVERITIES = {"high","critical"}` (never auto-applies), MCP `case_resolutions.v1` contract, tests `test_case_followup.py`, `test_dashboard_case_followup.py`, `test_severity_gate.py`. | Directly satisfies the Brief's "unsafe AI write" non-negotiable: a high/critical suppression is held for explicit human confirmation. Well-built and tested. | None; (deep boundary verification belongs to permission-boundary lens). | `python-pytest` (`test_severity_gate.py`). |
| 12 | Read-only MCP adapter (11 read tools, stdio-only) | Green | High | `mcp_server.py` tools `list_repos, honey_keys, latest_scan, scan_history, raw_findings, findings, cases, recovery_playbook, dependency_trust, rotation_status, rotation_history` (`:766-893`); rw mode adds case-resolution + fix-proposal tools (`:910-1090`); tests `test_mcp_server.py`, `mcp/README.md`. | A real, documented agent-access surface that matches the AGENTS.md/README "read-only, stdio-only, no network port" claim. | None (permission-boundary lens owns the deep boundary trace). | `python-pytest` (`test_mcp_server.py`). |
| 13 | Reset / data-clearing surface (preview + confirm-phrase gated) | Green | High | `reset.py` (501 LOC), endpoints `/api/reset/scan-results{,/preview}`, confirmation phrase (`reset_confirmation_phrase`), tests `test_reset.py`, `test_dashboard_reset_endpoints.py`, risk guard `local-security-data`. | A safe, guarded destructive-op surface — matches the Brief's "broken trust on destructive ops" guard. | None. | `python-pytest` (`test_reset.py`). |
| 14 | External Surface + runnable packs (display-only) | Grey | High | `catalog.py:1045-1049` "Display-only MVP entry... does not collect targets, probe domains, or run external reconnaissance yet"; `AgentLabView.tsx:809` "Packs are recommendations only, not runnable actions. External Surface is display-only." | Correctly **out of scope** per the Brief. Graded Grey (planned/placeholder), not Red — the honesty is itself excellent. Do not penalize. | None this campaign (dedicated future campaign if pursued). | n/a. |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| Hands-off code-fix flow (propose → clean-room review → land) | `fix_proposals.py`, MCP tools `propose_fix/clean_room_review_packet/record_clean_room_review/land_fix` (`mcp_server.py:1001-1090`). No dashboard route, no nav item, not in README "real vs not yet" table. | A high-leverage, well-fenced feature that ships and is tested but is effectively invisible — reachable only by an MCP client in rw mode. Either surface it or document it; right now it is hidden product value. |
| `trendValues(summary, points=22)` posture-trend helper | `dashboardData.ts:2079`, zero call sites. | Implies a posture-trend feature that does not render anywhere — dead scaffolding that could mislead a future agent into thinking trends are wired. |
| Activity event-feed filter chips | `App.tsx:2887` — chips with no handlers. | Looks interactive, does nothing; a hidden dead control inside an otherwise finished view. |
| Hidden CLI subcommands via positional `target`/`ioc_target` | `cli.py:59-60` (`target`, suppressed `ioc_target`); dispatch at `cli.py:108-137` routes `dashboard/doctor/check/handoff/template/schedule/vex-export/vex-import/cases/credentials/reset/ioc`. Several flags are `argparse.SUPPRESS` (`--action/--scope/--case-id/--preview/--apply/--confirm-suppression`). | The CLI has a substantial command surface that is not discoverable from `--help` (suppressed) and not all enumerated in user docs — power-user/agent surface worth an explicit command map. |
| `vex-export` / `vex-import` (VEX decision interchange) | `cli.py:120-122`, `vex.py` (461 LOC), `decisions.py` VEX mapping, `test_vex.py`. | A real import/export capability (security decision interchange) that is barely surfaced in the dashboard — an integration-grade feature hiding in the CLI. |

## Top Repair Targets

1. **Give the code-fix flow a dashboard surface (or document it as MCP-only).**
   `propose_fix → clean-room-review → land_fix` is the strongest realization of
   the Brief's safe-AI-write ideal but is invisible to dashboard users (Rank 1).
   The cheapest honest fix is a "real vs not yet" / Agent-lab note; the
   excellent fix is a proposals view (list → diff → clean-room verdict → land
   decision) mirroring the rotation flow's polish.

2. **Promote cases to a visible lifecycle with proof-bound closure.** Add at
   least an `in_progress`/`awaiting_rescan` state and bind a resolved case to
   the scan + diff that closed it, surfaced on the CaseCard (Rank 2). The
   rotation state machine (Rank 6) is the in-repo reference pattern. This is the
   single change that most directly delivers the Brief's "signature feel."

3. **Finish or remove the posture-trend superpower, and wire the dead Activity
   chips.** Render `trendValues` as a sparkline (Overview/Activity) or delete it
   (Rank 3); wire the event-feed filter chips or downgrade them to static labels
   (Rank 4). Small, high-polish wins that move shipped surfaces from "works" to
   "finished."

### SCOUT — High-leverage missing features (candidates, not commitments)

Ranked by leverage × fit with the local-first/trust model. Each is a candidate
for a post-campaign decision, recorded per the Brief's success criteria.

1. **Case lifecycle with proof-bound closure** — explicit `in_progress` →
   `verifying` → `closed`, each closure linked to the diff + rescan that closed
   it. (Also the #2 repair target; listed here because it is *the* missing
   feature, not just a polish gap.) Highest leverage: it is the product's stated
   signature loop.
2. **Posture-over-time trend view** — a real local-first sparkline/timeline of
   health score per repo from the SQLite history store (the `trendValues` helper
   is already a stub). Pure local-first superpower; no trust cost.
3. **Local, no-cloud shareable posture report** — export a self-contained HTML/PDF
   posture snapshot (cases + trend + diff) the user can hand to a teammate
   without any upload. Builds on the existing Reports/export surface.
4. **In-dashboard code-fix review** — surface the MCP propose/clean-room/land flow
   in the UI so a non-MCP user can drive hands-off fixes (closes Rank 1).
5. **Scan scheduling / watch mode in the UI** — `schedule`/`cron` exists in the
   CLI (`cli.py:118`) but is not a dashboard feature; a "rescan on a cadence /
   on git change" toggle would make the loop continuous and local-native.
6. **Cross-repo posture rollup ("fleet view")** — `--all-repos` discovery exists
   (`discovery.py`, `cli.py:150`); a portfolio dashboard ranking repos by
   posture/regressions would be a strong local-first differentiator for small
   teams.
7. **Suppression/decision expiry + re-review reminders** — accepted-risk and
   false-positive decisions never expire; a "review again in N days / on next
   matching finding" mechanism would prevent silent stale suppressions and
   strengthen the trust story.

## SocratiCode Value

SocratiCode was **not used** for this lens. Per the suite standard's cost-discipline
rule, the repo's own scaffolding made it unnecessary: the `.adx` manifests
(`modules/index.json`, `commands.json`, `risks.json`, `verification.json`) gave a
precise structural map, and the feature surface was enumerable directly via
Grep/Glob/Read against known files (CLI argparse, dashboard `/api/*` route table,
React `TabId`/nav groups, MCP `@server.tool()` decorators). Direct inspection plus
the passing 467-test suite and clean `tsc` gave higher-confidence, file-anchored
evidence than a structural librarian would have. No SocratiCode index was
consulted, so no claims here depend on it.

## Limits

- **No runtime/live verification.** The dashboard server, `security-scan`, the
  desktop launcher, and the MCP adapter were not started (prohibited by
  AGENTS.md + `.adx/risks.json`). All "reachable / wired" claims are inferred
  from code paths + tests, not from clicking the live UI. Behavioral-UX and
  product-workflow lenses (which may drive the running product) should confirm
  the dead-control and lifecycle findings against the live dashboard.
- **`npm run build` not run** — only `tsc --noEmit` (lint). Type health is
  confirmed; bundle-time/asset issues are not.
- **Boundary depth deferred to sibling lenses.** The MCP write-guard, no-egress,
  and suppression-gate findings are reported here at feature granularity only;
  permission-boundary and privacy-boundary lenses own the deep traces. The
  managed-tools/setup-runner `urllib` egress (`managed_tools.py:527`,
  `setup_runner.py:383`) was confirmed to live on install/setup paths, not the
  default scan path, but a full egress trace is the privacy lens's job.
- **Single-pass staleness.** This is a read-only initial pass; some findings may
  shift before repair. The `feature-health-final` pass re-confirms what survived.
