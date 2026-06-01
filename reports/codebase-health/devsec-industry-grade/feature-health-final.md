# Feature Health Forensic — DëvSec (Security Observatory) · FINAL (campaign-closing)

> Worst health: Green/Yellow · Lens: feature-health-forensic (**final** pass — re-confirms what survived all three stages) · Date: 2026-06-01

## Executive Finding

DëvSec ends the industry-grade campaign with an honest, broad, and now **finished**
product surface. The two non-negotiable trust breaches the campaign opened against are
**both eliminated and verified against current code, not receipts**: the dashboard's
mutating loopback HTTP surface is CSRF/Origin-guarded and the high/critical suppression
gate is re-armed to a same-origin-only confirmation token (`human_authorized` is no
longer inferred from "a POST arrived"); and the Google Fonts default-path egress is
gone — the served bundle self-hosts Geist via local `@font-face` and contains no
`googleapis`/`gstatic` host, so loading the UI makes zero third-party calls. All four
weak spots the **initial** feature-health pass ranked (code-fix flow invisible, flat
case lifecycle, dead `trendValues` trend helper, dead Activity chips) are closed: a
canonical `lifecycle.py` gives cases a real `in_progress` beat and proof-bound closure
("Verified — not found in scan X" bound to `resolved_by_scan_id`); a
`ScanHistoryTrendsPanel` renders the honest posture sparkline and drives a base/head
`/api/scan-diff` picker; a fenced `FixProposalsView` surfaces the propose → clean-room →
land flow in the dashboard without adding any bypass; and the README "real vs. not yet"
table now describes exactly that shipped behavior. The full Python suite is green
(**535 passed**) and `tsc`/`vite build` are clean.

The product is not perfect, but its imperfections are **polish, not breakage** — no Red,
no Yellow/Red on the feature surface. Two genuine residuals carry into the
human-launched Stage D patch campaign, both inherited from and re-confirmed by the
sibling [`11-behavioral-ux-health.final.md`](11-behavioral-ux-health.final.md): (1) the
production JS bundle has grown to **627.44 kB** as the three new surfaces landed and now
**re-trips Vite's 500 kB chunk-size warning** that batch 10 had recorded as absent — a
real (local-first, non-user-facing) regression of the S-029 "no warning" claim,
reproduced fresh this session; and (2) **`AddRepoDialog`, the first-run gateway modal,
still bypasses the shared focus-trapping `Dialog` primitive** (it has Escape +
`aria-modal` but no focus-trap and no focus-restore). Both are Green/Yellow. Net:
**worst row Green/Yellow, overall Green.** The campaign clears its excellence gate; the
punch-list below — plus the UX-final's — is the Stage D scope.

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security` (Security Observatory — local-first security scanner: Python CLI + SQLite history + React/Mistglass dashboard + read-only/guarded-write MCP + Honey Keys + secret rotation + macOS desktop launcher)
- Skill/lens: `feature-health-forensic` (campaign-closing **final** pass, post Stages A/B/C)
- Date: `2026-06-01`
- Requested focus: Confirm with evidence that both non-negotiable breaches are eliminated (S-001 dashboard CSRF/suppression, S-002 Google Fonts egress); that the local-first superpowers are now visible (S-039 history/diff, S-042 trends, S-043 code-fix surface, S-035 lifecycle); and re-check README "real vs not yet" honesty (S-053) against shipped behavior. Produce an explicit residual/regression/new-issue punch-list as Stage D input.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| Read orientation set (SKILL, health-suite-standard, excellence-brief, forensic-report template) | PASS | All four read in full before auditing. |
| Read the relevant Stage A/B/C receipts (01, 02, 11, 12, 13) + initial feature-health + UX-final | PASS | Cross-checked every claim against current source; receipts not taken on trust. |
| `grep -rEi 'googleapis\|gstatic' src/security_observatory/dashboard/assets/` | PASS (empty) | Exit 1, no match — the CDN `@import` is gone from the **served** CSS (S-002). |
| `grep -Eoi '@font-face\|font-family:Geist' .../dashboard/assets/*.css` | PASS | Served `index-K2-g72Zd.css` carries both self-hosted faces. |
| `grep -nE '_origin_is_same_site\|_guard_mutation\|_human_confirmation_present\|_DASHBOARD_CSRF_TOKEN' dashboard_server.py` | PASS | Guard + token present; `_guard_mutation` called at top of `do_POST`/`do_DELETE`; `human_authorized=self._human_confirmation_present()` (S-001). |
| `ls lifecycle.py` + `grep lifecycle_state\|Closure proof storage.py` | PASS | `lifecycle.py` (10 kB) exists; storage stamps `lifecycle_state` + binds closure proof to `resolved_by_scan_id` (S-035). |
| `grep -nE '/api/scan-diff\|scan_diff' dashboard_server.py` + `fetchScanDiff`/`ScanHistoryTrendsPanel` in `src/` | PASS | Route `_get_scan_diff` + `db.scan_diff`; panel mounted at `App.tsx:2339`, consumes `fetchScanDiff` (S-039). |
| `grep -rn 'trendValues' dashboard-ui/src/` | PASS | Real call site `ScanHistoryTrendsPanel.tsx:120` (`useMemo(() => trendValues(summary))`) — no longer dead (S-042). |
| `grep -nE '/api/fix-proposals\|decide_fix_landing' dashboard_server.py` + `FixProposalsView` in `App.tsx` | PASS | List/detail/land routes; `FixProposalsView` is its own `fix-proposals` tab (`App.tsx:1721`) (S-043). |
| Read README "What's real vs. what's not yet" table (lines 26–38) | PASS | Scan-history/trends + guarded-AI-fix rows describe the now-shipped behavior; External Surface / IaC Pack run-mode correctly "Coming Soon" (S-053). |
| `uv run pytest -q` | PASS | **535 passed in 62.04s.** No regression from the Stage C god-module splits / orchestrator extract / registry / type-floor work. |
| `cd dashboard-ui && npm run build` | PASS **with warning** | `tsc`+`vite` clean, built in 1.76s — but JS chunk **627.44 kB / 183.58 kB gzip** → Vite emits the **>500 kB chunk-size warning** (absent at batch 10's 485.57 kB). Reproducible. |
| Reverted the build-regenerated `dashboard/index.html` | DONE | The build is a read-only check; the one-line hash diff was restored so this audit changes no repo code. |
| Browser smoke / screenshot / keyboard walk / live scan-diff / rescan-to-closure | NOT RUN | Step operating rules forbid running dashboards/servers/scanners (loopback-listener firewall-prompt risk in the unattended session). Rendered-behavior confidence rests on source + component/route tests + the batch-06/09 receipts' own in-browser smokes. The human Final-review gate should run this. |

No installer, scanner, dashboard server, desktop launcher, process-kill, or any
`.adx/risks.json` dangerous pattern was run. `pytest`/`build` bind no network port. The
only repo writes are this report and the receipt.

## Ranked Health Table

Weakest / highest-user-risk first. Impact lens = **user** (the feature surface is what users encounter; weak areas are how broken value reaches them).

| Rank | Area | Health | Confidence | Evidence | Impact (user) | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Bundle re-trips the 500 kB chunk-size warning (S-029 partial regression)** | Green/Yellow | High | `npm run build` this session: JS chunk **627.44 kB / 183.58 kB gzip** + Vite "Some chunks are larger than 500 kB" warning. Batch-10 receipt recorded 485.57 kB and "no chunk-size warning." Growth is the three new surfaces (`FixProposalsView`, `ScanHistoryTrendsPanel`, lifecycle UI) landing in batches 11–13 after the single-bundle decision was finalized. | Local-first over loopback, so **not a user-facing latency regression** — but the explicit "no warning" health claim is now stale, and every future build prints a warning that masks real chunk problems. | Lazy-load the heavy non-default views (`FixProposalsView`, `ScanHistoryTrendsPanel`, agent-lab, catalog, Rotation flows) via `React.lazy`, or raise `build.chunkSizeWarningLimit` with a one-line rationale. | `npm run build` shows no warning, or the limit is set with a recorded reason. |
| 2 | **`AddRepoDialog` (first-run gateway) bypasses the shared `Dialog` primitive (S-041 gap)** | Green/Yellow | High | `App.tsx:1511` `AddRepoDialog` declares `role="dialog" aria-modal="true"` + window-level Escape + backdrop-close + autofocus + `aria-invalid`/`role="alert"` — but no Tab focus-trap and no focus-restore-to-opener. `App.tsx` does not import `components/Dialog`; the shared trap/restore primitive is used only by the four Rotation/AiFollowUp modals. | Keyboard users in the most important new modal can Tab out onto the page behind it, and focus isn't restored to the opener on close — an a11y inconsistency on the first-run entry point. Escape + aria-modal hold, so the floor isn't broken, just below the bar the rest of the app meets. | Migrate `AddRepoDialog` onto `<Dialog>` (drop the bespoke Escape effect; gain trap + restore); add an axe/trap vitest spec. | `vitest` axe/trap spec; browser Tab-walk stays inside the dialog and focus returns to opener. |
| 3 | **S-001 — dashboard CSRF/Origin guard + re-armed high/critical suppression gate** | Green | High | `dashboard_server.py`: `_DASHBOARD_CSRF_TOKEN` (`:1341`), `_origin_is_same_site` (`:1550`), `_guard_mutation` called at top of `do_POST` (`:1952`) and `do_DELETE` (`:1997`), `_human_confirmation_present` (`:1593`) constant-time compares `X-DevSec-Confirm`, `save_case_decision` passes `human_authorized=self._human_confirmation_present()` (`:2387`) — not hardcoded `True`. `tests/test_dashboard_csrf.py` pins forged-cross-origin-403-cannot-suppress-critical + honey-trigger-exempt. **Non-negotiable breach eliminated.** | A forged cross-origin POST can no longer suppress a high/critical case; the otherwise-correct server-side gate at `storage.set_case_decision` is no longer defeated by inferred authorization. Closes the Brief's "unsafe AI write / unaudited suppression" non-negotiable on the dashboard path. | None. | `uv run pytest tests/test_dashboard_csrf.py tests/test_severity_gate.py` (green in full run). |
| 4 | **S-002 — Google Fonts default-path egress eliminated** | Green | High | Source `dashboard-ui/src/index.css` has two local `@font-face` rules (no `@import url(googleapis)`); served `dashboard/assets/index-K2-g72Zd.css` carries `@font-face`/`font-family:Geist` and **no** `googleapis`/`gstatic` host; build emits `Geist-Variable-*.woff2` + `GeistMono-Variable-*.woff2` into served assets. **Non-negotiable breach eliminated.** | The default browser render path makes zero third-party network calls; the trust-boundary "no third-party API call" claim is now literally true. Typography preserved (self-hosted Geist). | None. | `grep -rEi 'googleapis\|gstatic' served assets` → empty; `npm run build` emits bundled woff2. |
| 5 | **S-035 — case lifecycle with visible `in_progress` + proof-bound closure** | Green | High | Canonical `lifecycle.py` (state set + `ALLOWED_TRANSITIONS` + presentation mapping); `storage._attach_lifecycle_state` stamps `case["lifecycle_state"]`; resolved cases bound to `resolved_by_scan_id` with affirmative "Verified — not found in scan X" `next_step` (`storage.py:3113-3119`); `App.tsx` CaseDetailCard shows a "Closure proof — Verified in scan X" panel + "Fix in progress" decision. `tests/test_cases.py` pins the closure binding + transitions. | The Brief's signature "watch a case move open → in-progress → verifying → closed, with the diff/verification that closed it" now exists for cases, not just rotation. Closure is by **proof**, not absence. | None (medium-confidence on *live* rescan-to-closure → human browser pass). | `uv run pytest tests/test_cases.py`. |
| 6 | **S-039 — scan history + arbitrary scan-to-scan diff surfaced in UI** | Green | High | `db.scan_diff(base,head)` + `GET /api/scan-diff?base=&head=` (`dashboard_server.py:1655,1912`, validates ids 400 / unknown 404); `ScanHistoryTrendsPanel` mounted on Overview (`App.tsx:2339`) with a base/head `<select>` driving `fetchScanDiff`, rendering health Δ + new/recurring/resolved + closure proofs. `tests/test_scan_diff.py`, `tests/test_dashboard_scan_diff_endpoint.py`, `ScanHistoryTrendsPanel.test.tsx` (5 specs). | The "compare any two scans" superpower is reachable in-UI (was computed locally but unrendered). Local-first differentiator, no egress. | None (medium-confidence on a *live* diff → human browser pass). | `uv run pytest tests/test_scan_diff.py`; `vitest`. |
| 7 | **S-042 — posture-over-time trend rendered (dead helper revived)** | Green | High | `trendValues` (`dashboardData.ts:2109`) now returns the honest per-scan health series and has a real call site `ScanHistoryTrendsPanel.tsx:120` (`useMemo(() => trendValues(summary))`); the misleading one-number "trend" label was relabelled `vs last`. Empty/short-history honest state. | A readable posture sparkline replaces the single delta number masquerading as a trend; no fabricated fallback array. | None. | `vitest` (sparkline spec); `grep trendValues` → definition + call site. |
| 8 | **S-043 — hands-off code-fix flow surfaced in the dashboard (fenced)** | Green | High | `GET /api/fix-proposals` (summary, no diff/finding text), `GET /api/fix-proposals/<id>` (diff + clean-room verdict + invariants), `POST /api/fix-proposals/<id>/land` delegating to `fix_proposals.decide_landing` (`dashboard_server.py:1656-1684,2941-2959`); `FixProposalsView` tab (`App.tsx:1721`). Dashboard adds **no** authoring half and **no** bypass — the auto-merge gate (clean-room `approved` + matching `diff_sha256` + allowlisted class + protected-branch refusal) is unchanged. `tests/test_dashboard_fix_proposals.py` (7 cases); red-team guard test passes unmodified. | The campaign's most powerful AI-write feature is no longer MCP-invisible; a dashboard-only operator can list → read diff/verdict → land an already-reviewed fix, authorized only where the proven boundary already allowed it. | None. | `uv run pytest tests/test_dashboard_fix_proposals.py tests/test_fix_proposals.py tests/test_mcp_fix_proposals.py`. |
| 9 | **S-053 — README "real vs. not yet" honesty matches shipped behavior** | Green | High | `README.md:32` (scan history/trends row) describes the shipped sparkline + base/head `/api/scan-diff` + closure proofs; `:33` (guarded AI fix row) describes the "Code fixes" view + the narrow auto-merge classes + the human-confirmation hold; `:36-37` keep External Surface and IaC Pack run-mode as honest "Coming Soon." No line overstates the now-shipped surface; no shipped surface is undersold. | Closes the Brief's "confident falsehood / partial-shown-as-complete" non-negotiable on the doc axis: the inventory the user reads is true after the campaign's feature work landed. | None (deeper drift across PROVOCATION/AGENTS/mcp-README is `documentation-health`/`ai-maintainability` territory — see punch-list #3). | Read table vs shipped routes/components. |
| 10 | No Stage-C feature regression from the structural refactors | Green | High | Stages C split the ~4.2k-line `dashboard_server.py`, extracted the scan orchestrator, added the scanner-adapter registry, and enabled TS strict — all behavior-preserving. **535 Python tests pass** and `tsc`/`build` are clean this session; the route table, lifecycle, scan-diff, and fix-proposal surfaces all still resolve. | The hardening work did not silently drop or break a user-facing feature; the surface that was Green before the refactors is Green after. | None. | `uv run pytest` (535 green); `npm run build`. |
| 11 | Carried strengths — Honey Keys, secret rotation, catalog, reports, MCP read/write, reset, AI follow-up | Green | High | Unchanged from the initial pass and re-confirmed by the green suite: rotation state machine, Honey Key incident lifecycle, contract-driven catalog with honest install states, raw+prompt report export, 11 read / 8 write MCP tools, confirm-phrase-gated reset, high/critical-gated AI case resolutions. | The broad surface remains finished and coherent; the out-of-scope walls (External Surface, runnable packs) stay honest Grey placeholders, not penalized. | None. | `uv run pytest` (full suite). |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| New `fix-proposals` tab + `/api/scan-diff` + lifecycle states now first-class | `App.tsx:1721`, `2339`; `lifecycle.py`; `dashboard_server.py` routes. | These shipped this campaign; the AGENTS.md "Ghost Invasion Memory" `stable_routes` line still lists only `/`, `/api/summary`, `/api/tool-catalog`, and route/tab memory predates the new surfaces — a `documentation-health`/`ai-maintainability` refresh item (punch-list #3). |
| `AddRepoDialog` is a hand-rolled modal parallel to the shared `Dialog` primitive | `App.tsx:1511` inline modal vs `components/Dialog.tsx`; App never imports Dialog. | Two modal idioms coexist; the load-bearing first-run one is the weaker (no trap/restore). Punch-list #2. |
| `RunCheckSheet` is a non-modal slide-in sheet, not a `role="dialog"` | `App.tsx` `RunCheckSheet`; no `role="dialog"`/`aria-modal`/Escape handler found (per UX-final). | A sheet may not need a trap, but Escape-to-close + focus management are unverified — a human-pass item, deferred to `design-system-accessibility-health`/Stage D. |
| Built dashboard assets regenerate on every `build` (gitignored) | `npm run build` rewrites `dashboard/assets/`; only `index.html` is committed (and was reverted here). | Means the chunk-size warning (row 1) prints on every developer build until punch-list #1 lands. |

## Top Repair Targets

1. **Kill the chunk-size-warning regression (S-029, row 1).** Lazy-load the heavy non-default views or set `chunkSizeWarningLimit` with a recorded rationale, so `npm run build` stops printing a warning the team has decided to ignore and the "no warning" health claim is true again. Highest leverage: it silently re-opened a closed claim and masks future chunk problems.
2. **Migrate `AddRepoDialog` onto the shared `Dialog` primitive (S-041, row 2).** Gain focus-trap + focus-restore on the first-run gateway modal so it matches the bar every other modal meets; add an axe/trap vitest spec.
3. **Refresh route/tab memory (documentation drift).** Update AGENTS.md's Ghost Invasion `stable_routes` + any route/tab registry to include `fix-proposals`, `/api/scan-diff`, `/api/fix-proposals*`, and the lifecycle states — a `documentation-health`/`ai-maintainability` follow-up so a fresh agent's repo memory matches the shipped surface.
4. **Human browser confirmation pass** (operating rules forbade running the dashboard here): Tab-walk Overview→Cases→a decision keyboard-only, press ⌘K, trigger a missing-scanner failure to render each `RunErrorNotice`, exercise a real `/api/scan-diff` and a rescan-to-closure end-to-end, and confirm `RunCheckSheet` Escape/focus. Closes the last Medium-confidence rendered-behavior gaps before Stage D.

## SCOUT — High-leverage missing features carried forward (candidates, not commitments)

The initial pass surfaced seven. **Three shipped this campaign** — case lifecycle with
proof-bound closure (#1), posture-over-time trend view (#2), in-dashboard code-fix review
(#4). Four remain recorded for a post-campaign decision per the Brief's success criteria:

1. **Local, no-cloud shareable posture report** — export a self-contained HTML/PDF posture snapshot (cases + trend + diff) a user can hand to a teammate with no upload. Builds on the existing Reports/export surface. Pure local-first; no trust cost.
2. **Scan scheduling / watch mode in the UI** — `schedule`/`cron` exists in the CLI but is not a dashboard feature; a "rescan on a cadence / on git change" toggle would make the loop continuous and local-native.
3. **Cross-repo posture rollup ("fleet view")** — `--all-repos` discovery exists; a portfolio dashboard ranking repos by posture/regressions would be a strong local-first differentiator for small teams.
4. **Suppression/decision expiry + re-review reminders** — accepted-risk/false-positive decisions never expire; a "review again in N days / on next matching finding" mechanism would prevent silent stale suppressions and strengthen the trust story.

## Punch-list for Stage D (consolidated)

This report plus [`11-behavioral-ux-health.final.md`](11-behavioral-ux-health.final.md)
are the input scope for the human-launched Stage D patch campaign. Feature-lens items:

- **[Green/Yellow] Bundle chunk-size warning regression** (627.44 kB > 500 kB) — S-029. Lazy-split or raise the limit with a rationale. *(Shared with UX-final row 1.)*
- **[Green/Yellow] `AddRepoDialog` focus-trap/restore gap** — S-041. Migrate onto the shared `Dialog`. *(Shared with UX-final row 2.)*
- **[doc] Route/tab memory drift** — AGENTS.md `stable_routes` + tab registry omit the new `fix-proposals`/`scan-diff`/lifecycle surfaces. → `documentation-health`/`ai-maintainability`.
- **[verify] Rendered-behavior confirmation pass** — live keyboard walk, ⌘K, each `RunErrorNotice`, a real scan-diff, a rescan-to-closure, `RunCheckSheet` Escape/focus. → human Final-review gate.
- **No Red, no Yellow/Red on the feature surface.** Both non-negotiable breaches eliminated and verified; the campaign's excellence gate clears.

## SocratiCode Value

SocratiCode was **not used** this pass. The confirm-set was a fixed list of S-IDs with
exact file/line evidence from the initial pass and the batch receipts, so direct
`grep`/`Read` against `dashboard_server.py`, `App.tsx`, `index.css`, `storage.py`,
`lifecycle.py`, plus a fresh `uv run pytest` + `npm run build` gave citable,
file-anchored evidence faster than a librarian pass — exactly the case the suite's
cost-discipline rule says to prefer direct inspection for. The MCP `devsec`/`socraticode`
servers were available but added nothing over targeted reads for a re-confirmation pass.

## Limits

- **No rendered behavior this session.** Operating rules forbid running
  dashboards/servers/scanners (a non-loopback listener trips the macOS firewall prompt
  that freezes an unattended run). So no browser smoke, screenshot, keyboard walk, live
  scan-diff, or rescan-to-closure ran here. Medium-confidence rows (live lifecycle/diff,
  scan-error rendering) rest on source + component/route tests + the batch-06/09
  receipts' own in-browser smokes, not a fresh render. The human Final-review gate should
  run the punch-list #4 browser pass.
- **Receipts cross-checked, not trusted.** Every "Green" claim was re-verified against
  current source this session; the two residuals were re-confirmed (the bundle warning by
  a fresh build, the modal gap by reading the actual `AddRepoDialog` code), not copied.
- **Sibling-lens boundaries respected.** Deep CSRF/suppression-boundary tracing is
  `permission-boundary-health`; the full no-egress trace is `privacy-boundary-health`;
  contrast/focus-color/SR specifics and the non-case styling debt are
  `design-system-accessibility-health`; whether rescan-to-closure closes a case live is
  `product-workflow-health`. This lens reports those at feature granularity and points at
  the owning lens.
- **Punch-list is for Stage D.** Per the campaign, residuals feed the human-launched
  Stage D patch campaign; this pass does not fix them. Both feature-lens residuals are
  Green/Yellow polish — neither blocks the excellence advance gate.
</content>
</invoke>
