# Product Workflow Health Forensic — DëvSec

## Executive Finding

DëvSec's core loop — **scan → triage → act → rescan-to-closure** — is, end to end,
genuinely sound, and on a tool that sells trust that is the thing that matters most. A
first-time user with no data is met with a working "Run a scan" CTA; scanning is an async
job with progress, per-scanner status, and a closed state; raw findings are grouped into
legible cases with severity, confidence, evidence, and a plain next step; and from the
Cases tab a selected case opens a detail card with **live decision controls**
(`Verify / False positive / Accept risk / Mark fixed`, plus `Reopen`) that POST to a
tested `/api/case-decision` endpoint, render the current decision status, and show
`changeStatus` (new / recurring / resolved) and `resolvedAt` — so a case *does* visibly
move and a closed case *does* show how it closed. The act leg also has two stronger,
higher-leverage paths layered on top: an in-UI **AI follow-up** flow (build prompt →
copy → paste agent JSON → preview → apply, with a surfaced high/critical suppression
gate) and a guarded **secret-rotation** flow launched straight from a secrets case. The
weaknesses are real but second-order, not loop-breaking: (1) the loop does not *auto-close
the proof* — after a rescan the user is not actively shown "the case you fixed is now in
the resolved set," they must re-read the list; (2) two local-first superpowers are wired
server-side but dark in the UI — `/api/scan-history` has **zero** UI consumers and
`/api/scan-diff` accepts `base`/`head` but the UI only ever requests the last-two-scan
delta; and (3) a whole orphaned parallel case UI (`components/{OverviewView,FindingsView,CaseCard}.tsx`,
never reached because its parent views are imported by nothing) sits in the tree alongside
the live inline `CaseDetailCard`, which will mislead a reader or future agent about which
act path is real. No
dead-end "Coming Soon" wall is reachable from a working action in this loop, and no step
forces a drop to raw JSON to *continue* (the JSON paste is an optional power path, not the
only act path). Overall: a strong, finished core loop with polish and discoverability gaps.

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security`
- Skill/lens: `product-workflow-health-forensic`
- Date: `2026-06-01`
- Requested focus: Per the Excellence Brief's product-workflow row — walk
  scan → triage → act → rescan-to-closure as a first-time user; map every dead end,
  CLI/JSON escape hatch, and missing lifecycle step; primary lens, not a checkbox. Plus
  SCOUT DUTY: a ranked short-list of workflow-level features the loop is obviously missing.
  Read-only audit; no repo code modified. Verification limited to AGENTS.md-sanctioned
  safe checks (fast import, targeted pytest). No installer, scanner, dashboard server,
  desktop launcher, or process-kill was run.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli"` | Pass (`cli-import-ok`) | Fast import check from AGENTS.md Verification. |
| `uv run pytest -q -k "case_decision or case_followup or dashboard_case"` | Pass — `9 passed, 458 deselected in 1.28s` | Targeted run of the act-path tests. (`timeout` is unavailable in this zsh; I scoped with `-k` instead of running the full suite, so the global count is not re-confirmed here — the test-confidence lens owns that.) |
| `grep` `/api/case-decision` in `tests/` | Match — `test_dashboard_case_followup.py:145` posts to it and asserts the stored status (`:151`) | The per-case decision path **is** covered end to end, plus `set_case_decision` is exercised by `test_cases.py`, `test_severity_gate.py`, `test_vex.py`, `test_dashboard_report_exports.py`, `test_mcp_server.py`. |
| `grep` for live `CaseDetailCard` render + decision grid | Confirmed: `App.tsx:2463`/`:2481` render `CaseDetailCard`; its `decision-grid` (`:3434-3446`) wires each button → `save()` → `onDecision` → `saveCaseDecision` → `POST /api/case-decision` (`:1194-1207`). | The act controls are live and reachable from the Cases tab master/detail. |
| `main.tsx` entry + import graph for `OverviewView`/`FindingsView`/`CaseCard` | `main.tsx` mounts `App.tsx`; App uses inline `OverviewView` (`:1789`) + `FindingsView` (`:2343`). `components/CaseCard.tsx` is imported only by `components/OverviewView.tsx` and `components/FindingsView.tsx`, which are imported by **nothing**. | The whole `components/` case-UI trio is orphaned/unreachable; it is the source of the "act path looks unfinished/ambiguous" false signal. |
| Endpoint-consumer scan (UI fetches vs server routes) | `scan-history` UI consumers = **0**; `scan-diff` base/head = **0** (UI sends `repo` only). `case-decision` = 1, `agent-lab` = 2, `rotation` = 4, `ai-follow-up` consumed. | Confirms the two dark superpowers. |
| `cd dashboard-ui && npm run build` | Not run | Heavy; not required to establish these source-level findings. Recorded under Limits. |

## Ranked Health Table

| Rank | Area | Health | Confidence | Evidence | Impact (user) | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Rescan-to-closure does not actively show the proof** | Yellow | Medium | The pieces exist: `CaseDetailCard` shows `item.changeStatus` (`App.tsx:3387`) and `item.resolvedAt` (`:3388`); `/api/scan-diff` returns a `resolved[]` set (`dashboard_server.py` diff builder) and `SinceLastScanPanel` shows `New / Still open / Resolved` counts (`SinceLastScanPanel.tsx:18-21`). But nothing links *the case you just acted on* to *the rescan that resolved it*: after a rescan the user re-reads the list to infer closure; `activeCaseList` filters to `caseNeedsAttention` (`App.tsx:597-598`) so a resolved case simply drops out rather than announcing "verified in scan X." | The Brief's signature "watch a case move open → verifying → closed, with the diff that closed it" is *almost* delivered but stops one step short — closure is inferable, not shown. The reduce-the-scary-scan-to-a-calm-closed-loop feeling loses its payoff at the finish line. | After a rescan, surface a "Resolved this run" affordance that ties a now-closed case to the resolving scan id and its diff `resolved[]` entry; keep a closed case visible (with a "Verified ✓" state) for one cycle instead of silently dropping it. | Component/e2e test: act on a case, rescan, assert the case shows a resolved state bound to the new scan id. |
| 2 | **`scan-history` superpower wired server-side, absent from UI** | Yellow | High | `build_scan_history` + route `GET /api/scan-history` exist and are exercised by pytest, but endpoint-consumer scan shows **0** UI fetches of `scan-history`. Overview synthesizes a 7-bar "posture week" client-side from `summary.history` (`App.tsx:504-511`) — a thin proxy, not the real endpoint. | Posture-over-time trend (a named local-first superpower in the Brief) is only a sparkline; the richer history endpoint is dark, so the user can't drill into per-scan history beyond the latest pair. | Add a history/trends panel consuming `/api/scan-history`. | Component test rendering the history panel and asserting the fetch. |
| 3 | **`/api/scan-diff` accepts base/head but UI only sends `repo`** | Yellow | High | Diff handler parses `base`/`head`; `SinceLastScanPanel` is the only diff surface and computes from summary deltas, never offering scan-to-scan selection. Arbitrary "compare any two scans" is built but unreachable. | Half a superpower: the user can see "since last scan" but not "scan N vs scan N-3." | Add a base/head picker that drives `/api/scan-diff`; pairs with rank 2. | Component test: pick base/head, assert the diff request carries both. |
| 4 | **An entire orphaned parallel case UI (`components/{OverviewView,FindingsView,CaseCard}.tsx`) shadows the live act path** | Yellow | High | `main.tsx` mounts `App.tsx`, which uses its **own inline** `OverviewView` (`App.tsx:1789`) and `FindingsView` (`App.tsx:2343`) + inline `CaseDetailCard` (`:3327`). The sibling files `components/OverviewView.tsx` and `components/FindingsView.tsx` import `components/CaseCard.tsx` (which *does* wire `onDecision`, `:59-83`, with a `decision-grid`), but **those two parent component files are imported by nothing** — so the whole trio is dead. (My first draft mis-scoped this as one dead `CaseCard`; it is three orphaned files forming a complete unused case UI.) | No user impact, but it is exactly the "half-state presented as whole" trap for *readers*: a reviewer/agent finds a second, plausible-looking case UI and cannot tell which is live (as this audit's first pass demonstrated). Also pure maintenance drag and bundle weight. | Delete the orphaned `components/{OverviewView,FindingsView,CaseCard}.tsx` trio, or adopt them and retire the inline equivalents — one source of truth for the case control. | `npm run build` after removal; grep confirms no remaining import of the deleted files. |
| 5 | **AI follow-up act path (strong, but repo-scoped + JSON-paste)** | Green/Yellow | High | `AiFollowUpPanel` builds prompt (`/api/ai-follow-up/prompt`), previews (`/resolutions/preview`), applies (`/resolutions/apply`) with `onApplied={onRefresh}` closing the loop, and a surfaced suppression-confirm path (`AiFollowUpPanel.tsx:154-173`). Rendered on Overview (`App.tsx:1915`) and per-case in Cases (`:2434`). In all-repos mode it still works but via a repo dropdown; the mechanism is paste-the-agent's-JSON. | The highest-leverage act path is genuinely good and trust-safe. Friction: it asks a non-coding user to shuttle JSON between two tools — acceptable as a *power* path because the rank-tier per-case buttons are the fast path. | None blocking. Optionally let "apply" auto-offer a rescan inline. | Manual UX pass; covered by `test_dashboard_case_followup.py`. |
| 6 | **Triage entry / grouping / per-case decision controls** | Green | High | `build_security_cases` clusters + sorts by action level then severity (`cases.py:183-205`); `FindingsView` renders a master/detail with severity chips, category/repo filters (`App.tsx:2440-2452`), and `CaseDetailCard` showing risk, evidence, confidence, next step, decision status, and the live `decision-grid` (`:3434-3446`). Severity shown by dot **and** text label (not color-alone). | The product's signature — noise → ordered, legible, decidable to-do list — works, and the act is one click from triage. | None blocking for this lens. (Closure-proof is rank 1; a11y depth defers to design-system lens.) | Visual pass; build/lint in design-system lens. |
| 7 | **Scan entry + rescan loop** | Green | High | Async job model: `/api/run-check` + polled `/api/check-status` (`queued/running/complete/failed`, progress, per-scanner status, `App.tsx:202-214,967-992`). Repo-scoped and all-repos (bounded concurrency 3, `:1081`). Rescan reachable from empty state, threaded `onRunCheck`/`onChooseChecks` into Cases/Playbooks/Verification, and after AI apply. Crafted loading + first-run states. | The on-ramp is genuinely good; a no-data user is guided to a working first scan, and completion swaps in fresh data. | None blocking. Optionally inline-retry a single failed repo inside an all-repos run (currently routes to Verification, `:1136`). | Existing async-job tests; manual run. |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| `GET /api/scan-history` with no UI consumer | Route + `build_scan_history` exist, pytest-exercised; 0 UI fetches. | A working, tested capability (posture history) is dark to users. Wire it (rank 2) or it's maintenance with no payoff. |
| `/api/scan-diff` `base`/`head` params unreachable from UI | Handler parses both; UI sends `repo` only (`SinceLastScanPanel`). | Arbitrary scan-to-scan compare is built but unreachable — half a superpower (rank 3). |
| `GET /api/cases` with no UI consumer | Route present; 0 UI fetches (UI reads cases from `/api/summary`, `App.tsx:918`). | Redundant/likely an API/MCP convenience; undocumented as such. Low risk; flag for documentation/maintainability lenses. |
| Orphaned parallel case UI: `components/{OverviewView,FindingsView,CaseCard}.tsx` | `CaseCard` *is* imported — but only by `components/OverviewView.tsx` and `components/FindingsView.tsx`, which are themselves imported by nothing; `App.tsx` uses inline `OverviewView`/`FindingsView`/`CaseDetailCard`. | A whole second, plausible case UI in the tree that never renders; misleads readers/agents about which act path is live; dead-code/bundle weight (rank 4). |
| CLI act path parallel to dashboard | `security-scan cases import-resolutions --apply` (`cli.py:654-737`) mirrors the dashboard apply path incl. held-for-human high/critical suppression. | Good parity/scriptability — and, unlike my first read, *not* the only manual-decision path; the dashboard buttons work. Worth documenting as the automation twin. |

## Top Repair Targets

1. **Close the loop with visible proof** (rank 1). After a rescan, bind the case the user
   acted on to the scan that resolved it (`/api/scan-diff` already returns `resolved[]`),
   and keep a just-closed case visible as "Verified ✓ in scan X" for one cycle instead of
   silently dropping it from `caseNeedsAttention`. This is the one step that turns a working
   loop into the Brief's "watch it close, with the diff that closed it" experience.
2. **Surface the history/trends superpower and arbitrary diff** (ranks 2+3). Consume
   `/api/scan-history` in a trends panel and add a base/head picker that drives the existing
   `/api/scan-diff` base/head support — turning two tested-but-dark backends into visible
   local-first advantages.
3. **Delete or adopt the orphaned `components/{OverviewView,FindingsView,CaseCard}.tsx`
   trio** (rank 4). One source of truth for the case UI so the act path stops *looking*
   ambiguous/unfinished to reviewers and agents, and to shed dead bundle weight.

### Scout — High-leverage workflow features DëvSec is missing (candidates, not commitments)

Ranked by leverage on the core loop. Workflow-level gaps, distinct from the feature-health
and ai-product short-lists.

1. **One-click "rescan this case to confirm closure."** From a decided case, trigger a
   scoped rescan and auto-flip the case to `verified` (with the resolving scan id) when its
   fingerprint lands in scan-diff `resolved[]`. Highest leverage — it operationalizes
   rank-1 and makes closure feel earned, not asserted.
2. **A keyboard-navigable triage queue** (j/k to move, hotkeys for Verify / False positive /
   Accept / Fixed) over open cases, so a wall of findings becomes a fast, satisfying
   inbox-zero pass — directly serving the Brief's "fast, keyboard-navigable, even satisfying."
3. **Posture-over-time trend view that names regressions** ("fixed 6, 2 regressed since last
   week"), built on the dark `/api/scan-history` endpoint.
4. **Arbitrary scan-to-scan compare picker** (base/head) — server already supports it.
5. **Decisions that carry forward across rescans, shown explicitly** — on a freshly
   rescanned recurring case, surface "you marked this accepted_risk on 2026-05-20" so the
   user isn't asked to re-triage the same finding every scan. (VEX import/export +
   `case_decisions` exist; the *carry-forward-and-show-it* workflow should be explicit.)
6. **Bulk per-severity manual decisions on the Cases tab** ("accept all low," "false-positive
   these 3") — a manual analogue of the AI batch, without leaving for the JSON panel.

## SocratiCode Value

SocratiCode MCP tools were available as deferred tools but were **not used**. Per the
suite's SocratiCode cost-discipline rule, this lens needed exact files (the React
`App.tsx` view tree, `cases.py`, the dashboard server route table) and exact strings
(endpoint names, `onCaseDecision`/`CaseDetailCard`/`CaseCard` call sites), better served
by direct Read/Grep/Bash. Every claim was verified against concrete files, the route
table, grep counts, and a targeted test run — not a structural-map tool. A broad
finding-fingerprint flow trace (scanner → normalize → case → diff `resolved[]`) is the one
place `codebase_flow` would have helped; here targeted inspection sufficed and was more
trustworthy. Notably, an early shallow read of the *unused* `CaseCard.tsx` produced a
false "act path is dead" hypothesis that direct grep of render sites corrected — a concrete
reminder that no single component view is proof.

## Limits

- **No running product.** Per AGENTS.md and `risks.json`, the dashboard server,
  `security-scan`, and a browser were not started. All UI findings are from source
  inspection of `dashboard-ui/src` + the Python server, not a live click-through. The act
  controls are confirmed live by static evidence (render site + handler + tested endpoint),
  High confidence; the behavioral-ux lens (which runs twice) should still confirm the felt
  flow. Rank 1's "closure isn't actively shown" is Medium because it rests partly on the
  *absence* of a binding UI rather than a live walkthrough.
- **Frontend build/lint not run.** `npm run build`/`lint` skipped as heavy and unnecessary
  for these source-level findings; build is the right gate when ranks 1–4 land.
- **Full pytest not re-run here.** `timeout` is unavailable in this zsh, so I scoped pytest
  with `-k` to the act-path tests (9 passed) rather than the whole suite; the global pass
  count is owned by `09-test-confidence-health`.
- **Display/tooling friction.** Several large-file reads rendered inconsistently; I worked
  around it with sed/awk extraction and short-column reformatting, cross-checking line
  numbers against grep/wc. Line refs are accurate to the inspected revision and may shift a
  few lines if files change.
- **Sibling-lens boundaries respected.** Scanner-degradation honesty → `07-integration-health`
  (cited). Decision-friction feel, keyboard navigation, crafted-state polish →
  `behavioral-ux-health` (headline lens, runs twice): I flag *structural* loop state here and
  defer felt-experience grading there. Severity-color-alone/contrast → `design-system-
  accessibility-health`. MCP/case-decision write-guard correctness → `04-permission-boundary`
  and `06-data-contract-type`.
- **Initial-draft corrections.** An earlier version of this report claimed the per-case act
  controls were dead and untested; deeper grep of render sites and a targeted test run
  disproved it. A second draft mis-scoped the dead code as one orphaned `CaseCard`; the
  import graph shows it is a three-file orphaned parallel case UI
  (`components/{OverviewView,FindingsView,CaseCard}.tsx`). This final version reflects the
  corrected, evidence-backed picture: the act path works and is tested; the gaps are
  closure-proof visibility, two dark history/diff endpoints, and the orphaned `components/`
  case-UI trio.
