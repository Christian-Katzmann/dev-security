# Behavioral UX Health Forensic — DëvSec (Security Observatory) · FINAL (post-repair)

> Worst health: Green/Yellow · Lens: behavioral-ux-health-forensic (headline; **final** of two passes) · Date: 2026-06-01

## Executive Finding

Stage B landed the UX headline. Every defect the initial pass ranked as a first-class
failure is gone from the live surface, verified against current source plus a fresh
`lint` / `vitest` / `build` run. **`window.prompt` is fully eliminated** — `grep -rn
"window.prompt" dashboard-ui/src/` returns nothing. The first-run gateway is now a crafted
Mistglass `AddRepoDialog` (`App.tsx:1511`) with an autofocused mono input, an example
placeholder, `/api/projects` quick-picks, inline `aria-invalid` + `role="alert"` validation
that never silently no-ops, and a single primary action; the "+ Add repository…" select-option-as-action
smell is retired in favor of explicit buttons. The two core-loop note prompts became inline
fields — a persistent `.decision-note` textarea on the case card (`App.tsx:3921`) and an
inline `.incident-close-note` with explicit Close/Cancel on the Honey-key incident close
(`App.tsx:4238`) — so resolving a case or closing an incident never drops to an OS dialog.
The dead off-Mistglass twin is **deleted**: `components/{OverviewView,CasesView,CaseCard,HoneyKeysView}.tsx`
no longer exist, leaving one source of truth for the case surface. **⌘K is now real**
(`App.tsx:1033-1051`, capture-phase listener focuses + selects the toolbar search; verified
in-browser in the batch-09 receipt). Scan failures carry a discriminated `RunError`
(`missing-tool | errored | failed | validation`, `App.tsx:293`) rendered as distinct crafted
`RunErrorNotice` cards with the right next step, not one red line. The Activity filter chips
are wired (`activityFilter` state, `App.tsx:3275`) over a new `category` field. Severity now
flows from one `severityDisplay` map (`App.tsx:418`); confidence honesty is fixed at the
source — `model.py:166` preserves `"unknown"` rather than coercing it to `"medium"`, pinned
by unit tests. Accessibility got a real floor: a global `--focus-ring` token + `:focus-visible`
ring, a shared focus-trapping `Dialog` primitive behind all four Rotation/AiFollowUp modals, a
skip-to-content link landing on `<main id="main-content" tabIndex={-1}>`, and a vitest +
jest-axe harness (22 tests green this session) that regresses loudly if any of these break.
Derived state is memoized (15 `useMemo`, a perf regression test asserting zero re-runs of
`filterSummaryByTarget` across keystrokes). On top of the repairs, three local-first
superpowers shipped and mount live: a canonical `lifecycle.py` with a visible `in_progress`
beat and a "Closure proof — Verified in scan X" panel (`App.tsx:3864`), a `ScanHistoryTrendsPanel`
with a posture sparkline + base/head `/api/scan-diff` picker (`App.tsx:2339`), and a fenced
`FixProposalsView` code-fix surface (`App.tsx:1721`).

The triage spine now reads as crafted and effortless end to end: the entry point is a real
form, the act path stays in-card, severity is calm-by-default and honest about clean scans,
and the loop closes with visible proof. **No Red, no Yellow/Red.** Two genuine residuals
remain, both modest and both feeding the Stage D patch campaign: (1) the production JS bundle
grew to **627.76 kB** as the three new surfaces landed and now **re-trips Vite's 500 kB
chunk-size warning** that batch 10 explicitly recorded as absent — a real (if local-first,
non-user-facing) regression of the S-029 "no warning" claim; and (2) **`AddRepoDialog`, the
first-run gateway modal, bypasses the shared `Dialog` primitive** batch 07 built — it has
Escape, `aria-modal`, backdrop-close, a close button and autofocus, but **no focus-trap and no
focus-restore-to-opener**, the exact behaviors every other modal now inherits. Net: **worst
row Green/Yellow, overall Green.** The headline lens clears its advance gate; the punch-list
below is polish, not a blocker.

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security` (Security Observatory — local-first security scanner: Python CLI + SQLite history + React/Mistglass dashboard + read-only/guarded-write MCP + Honey Keys + macOS desktop launcher)
- Skill/lens: `behavioral-ux-health-forensic` (headline lens; **final** of two passes, post-Stage-B repairs)
- Date: `2026-06-01`
- Requested focus: Re-confirm that S-019, S-032, S-033, S-034, S-036, S-037, S-038, S-040, S-041, S-044, S-045, S-047, S-028, S-029, S-054 landed and that triage now feels crafted and effortless; produce an explicit residual/regression punch-list for the human-launched Stage D patch campaign.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| Read orientation set (excellence-brief, SKILL, health-suite-standard, forensic-report template, initial report) | PASS | All five read in full before auditing. |
| Read all 8 Stage-B batch receipts (06–13) | PASS | Cross-checked every claim against current source; receipts not taken on trust. |
| `grep -rn "window.prompt" dashboard-ui/src/` | PASS | **Returns nothing** — all four S-033/S-034 sites eliminated; no native dialog in the loop. |
| `cd dashboard-ui && npm run lint` (`tsc --noEmit`) | PASS | Clean, no type errors (run this session). |
| `cd dashboard-ui && npx vitest run` | PASS | **22/22** across 6 files (focus-ring guard, Dialog trap/Escape/restore + axe, SkipToContent, ScanHistoryTrendsPanel, RotationTriggerFlow a11y, App.perf memoization guard). |
| `cd dashboard-ui && npm run build` (`vite build`) | PASS **with warning** | Built clean in 1.46s, but JS chunk is **627.76 kB / 183.71 kB gzip** → Vite emits the **>500 kB chunk-size warning** (absent at batch 10's 485.57 kB). Reproducible; committed `index.html` unchanged. |
| `python3 -c "import security_observatory.cli"` | PASS | `import ok` — lifecycle/storage/dashboard backend loads. |
| Source verification of every confirmed S-ID against current `App.tsx` / `index.css` / `model.py` / components | PASS | Line-cited in the table below. |
| Browser smoke / screenshot / keyboard walk / lighthouse | NOT RUN | This step's operating rules forbid running dashboards/servers (loopback-listener firewall-prompt risk in the unattended session). Relied on source + the batch-06/09 receipts' own in-browser smokes (add-repo validation, ⌘K focus, chip filtering, the four error cards). Not inferred to pass beyond those. |

No installer, scanner, dashboard server, desktop launcher, process-kill, or any
`.adx/risks.json` dangerous pattern was run. `lint`/`vitest`/`build` bind no network port.
The only repo writes are this report and the receipt.

## Ranked Health Table

Weakest / highest-user-risk first. Impact lens = **user** (friction lands on the user's confidence, completion, and trust).

| Rank | Area | Health | Confidence | Evidence | Impact | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Bundle re-trips the 500 kB chunk-size warning (S-029 partial regression)** | Green/Yellow | High | `npm run build` this session: JS chunk **627.76 kB / 183.71 kB gzip** + Vite's "Some chunks are larger than 500 kB" warning. Batch-10 receipt recorded 485.57 kB / 137.53 kB gzip and "build emits no chunk-size warning." Growth is the three new surfaces (`FixProposalsView`, `ScanHistoryTrendsPanel`, lifecycle UI) landing in batches 11–13 *after* the single-bundle decision was finalized. | Local-first over loopback, so **not a user-facing latency regression** — but the explicit "no warning" health claim is now stale, and every future build prints a warning that masks real chunk problems. | Either lazy-load the heavy non-default views (`FixProposalsView`, `ScanHistoryTrendsPanel`, agent-lab, catalog, Rotation flows) behind `React.lazy`, or raise `build.chunkSizeWarningLimit` with a one-line rationale so the warning means something again. | `npm run build` shows no warning, or the limit is set with a recorded reason. |
| 2 | **`AddRepoDialog` (first-run gateway) bypasses the shared `Dialog` primitive (S-041 gap)** | Green/Yellow | High | `App.tsx:1511` `AddRepoDialog` declares `role="dialog" aria-modal="true"` + a window-level Escape listener (`1525-1531`) + backdrop-close + close button + autofocus (`1587`) + `aria-invalid`/`role="alert"` — but no Tab focus-trap and no focus-restore-to-opener. `App.tsx` does **not** import `components/Dialog`; `grep -c 'role="dialog"' App.tsx` = 1. The shared `Dialog.tsx` (batch 07) that owns trap/Escape/restore is used only by the four Rotation/AiFollowUp modals. Built in batch 06, never migrated when batch 07 landed. | Keyboard users in the most important new modal can Tab out of the dialog onto the page behind it, and focus is not restored to the opener on close — an a11y inconsistency on the first-run entry point. Has Escape + aria-modal, so the floor isn't broken, just below the bar the rest of the app now meets. | Migrate `AddRepoDialog` onto `<Dialog>` (drop the bespoke Escape effect; gain trap + restore). | `vitest` axe/trap spec for `AddRepoDialog`; browser Tab-walk stays inside the dialog and focus returns to the opener on close. |
| 3 | First-run add-repo via crafted form (S-033) | Green | High | `AddRepoDialog` (`App.tsx:1511`): mono input, example placeholder `/Users/you/code/your-project`, `/api/projects` quick-picks (`suggestions`, `1543`), empty submit → "Enter the full path…", non-absolute → "Paste a full folder path, starting with “/”…", never closes/no-ops on bad input. `selectTarget('add-repo')` opens the dialog; the select-option-as-action is retired for explicit buttons. No `window.prompt`. Live add-repo validation smoke in batch-06 receipt (screenshot). | The product's first interaction is now its most-crafted surface, not its least. Named "janky/dead-end UX" failure mode — eliminated. | None (residual: focus-trap, row 2). | Done; re-confirm in human browser walk. |
| 4 | `window.prompt` out of the core loop (S-034) | Green | High | Inline `.decision-note` textarea seeded from existing note (`App.tsx:3921`, `noteDraft` `3804`); one-click decisions still save immediately. Honey-key incident close reveals an inline `.incident-close-note` with explicit Close/Cancel (`App.tsx:4238`), empty note valid, cancel explicit. No `window.prompt` anywhere. | The act-on-a-case and close-incident steps stay in-card; the "effortless triage" feel holds at the moment of resolution. | None. | Human browser walk: record a decision + close an incident, confirm no native dialog. |
| 5 | Dead off-Mistglass case twin deleted (S-036) | Green | High | `components/{OverviewView,CasesView,CaseCard,HoneyKeysView}.tsx` no longer exist (dir listing + `grep -rn "components/CaseCard"` → none). One inline source of truth (`OverviewView`/`CasesView`/`CaseDetailCard` in `App.tsx`). | A maintainer can no longer edit the wrong twin or revive a louder off-system surface with near-invisible severity. | None. | Done. |
| 6 | ⌘K shortcut is real (S-037) | Green | High | `App.tsx:1033-1051` capture-phase keydown: ⌘K/Ctrl-K → `searchInputRef.current.focus()+select()`, never collides with ⌘R (owned by `main.tsx`). `<kbd>⌘K</kbd>` hint at `1948` now backed. Live-verified in batch-09 receipt (`document.activeElement`). | The advertised keyboard speed feature now works; no false affordance. | None. | Done; re-confirm in human browser walk. |
| 7 | Differentiated scan-failure feedback (S-038) | Green | Medium | Discriminated `RunError` (`missing-tool | errored | failed | validation`, `App.tsx:293-294`); `RunErrorNotice` renders a crafted card per kind with the right next step (missing-tool → Open Verification, errored → retry via `retryLastRun`, failed → details). All `runError` render sites use it. Batch-09 receipt screenshot shows 4 distinct cards. | At the highest-anxiety moment (a scan failing) the user sees what broke and where to go, not one red line. | None. | Medium until a live missing-scanner run renders each card in a real flow (deferred to human pass). |
| 8 | Activity filter chips wired (S-044) | Green | High | `activityFilter` state (`App.tsx:3275`), `category` field on every `ActivityItem` (`660-702`), chips carry `active` + `onClick` and filter the feed (`3281`, `3313`). Live-verified counts in batch-09 receipt (16 scan + 20 case = 36). | No clickable-looking dead control remains in the Activity feed. | None. | Done. |
| 9 | One severity→display map (S-019) | Green | High | `severityDisplay: Record<Tone,string>` (`App.tsx:418`) is the single source; `severityMeta` labels derive via `.toUpperCase()` (`428-433`); MetricBlock strip (`2834-2836`) + RiskLandscape legend read it. `docs/vocabulary.md` documents the one translation point. | Severity wording is consistent across dashboard, CLI, and MCP; no duplicate string-to-display logic to drift. | None. | Done. |
| 10 | Confidence honesty — `unknown` preserved (S-032) | Green | High | `model.py:166` — confidence stays `"unknown"` when unclassifiable instead of coercing to `"medium"`; 5 pinning tests. A case never reads more certain than its evidence. (Note: `normalize_severity`'s `"unknown"→"medium"` at `model.py:217` is a *severity*-bucket default, a separate, defensible axis — not the confidence path.) | Closes the Brief's "confident falsehood" non-negotiable on the confidence axis. | None. | `uv run pytest` (confidence-honesty tests). |
| 11 | Accessibility floor — focus ring / Dialog primitive / skip link / axe harness (S-040, S-041, S-045, S-047) | Green | High | `--focus-ring: #2f8f6e` token (`index.css:96`) + global `:focus-visible` ring; shared focus-trapping `Dialog.tsx` behind all four component modals (`grep 'role="dialog"' components/` → only `Dialog.tsx`); `SkipToContent` → `<main id="main-content" tabIndex={-1}>` (`App.tsx:1412`); vitest+jest-axe harness, 22 tests green this session. | Keyboard and screen-reader users get a visible ring, trapped/restoring modals, and a skip link — guarded by tests that fail if regressed. | Residual: `AddRepoDialog` not yet on the primitive (row 2). Pure contrast/SR specifics → `design-system-accessibility-health`. | `npx vitest run` (green). |
| 12 | Memoized derived state (S-028) | Green | High | 15 `useMemo` in `App.tsx`; root `scopedSummary`/`activeCases`/`posture` and per-view `cases`/`activities` memoized on real inputs; `App.perf.test.tsx` asserts **0** re-runs of `filterSummaryByTarget` across 12 keystrokes (green this session). | Typing in the search box no longer re-runs all derived passes across the 4.5k-line shell. | None (component-tree decomposition is Stage C / S-016, by design). | `npx vitest run` perf guard. |
| 13 | Token sweep on shared primitives (S-054) | Green | High | Batch-10 receipt: `index.css` inline `#fff`/`#2f6656` on shared primitives swept 48 → 3 `:root` token definitions; `--brand-green` added. Value-identical, no visual regression. | Shared primitives use the Mistglass token idiom; less drift risk. | Residual styling debt in non-case components is out-of-scope (design-system lens). | `grep -nE "#fff|#2f6656" index.css` → only `:root`. |
| 14 | Severity tuning / calm-by-default (carried strength) | Green | High | `severityDisplay`/`severityMeta` are text+color never color-alone; hero de-escalates and clean scans say clean is "not a guarantee that the repo is safe." Still the product's best UX trait. Minor: `crit` pill `bg:'#dcaaa5'` (`App.tsx:431`) remains hotter than DESIGN.md `--sev-crit-soft #e8c6c0`. | A strength — calm, honest about clean scans. | Align `crit.bg` to the token (design-system lens). | Visual check. |
| 15 | New local-first superpowers shipped and mounted (lifecycle / history-diff / fix-proposals) | Green | Medium | `lifecycle.py` (10 kB) + visible `in_progress` beat + "Closure proof — Verified in scan X" panel (`App.tsx:3864-3870`); `ScanHistoryTrendsPanel` posture sparkline + base/head `/api/scan-diff` picker mounted on Overview (`App.tsx:2339`); fenced `FixProposalsView` code-fix surface as its own tab (`App.tsx:1721`). | The core loop now closes with visible proof and the local-first superpowers are reachable in-UI — the Brief's "definition of excellent" outcomes. | These are *adjacent* to this lens (workflow/feature lenses own them); behaviorally they read finished. | Medium until a human browser walk exercises a real diff + closure. |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| `AddRepoDialog` is a hand-rolled modal parallel to the shared `Dialog` primitive | `App.tsx:1511` inline modal vs `components/Dialog.tsx`; App never imports Dialog. | Two modal idioms now coexist; the load-bearing first-run one is the weaker (no trap/restore). Punch-list row 2. |
| `RunCheckSheet` is a non-modal slide-in sheet, not a `role="dialog"` | `App.tsx:2031` function; no `role="dialog"`/`aria-modal`; no Escape handler found. | The initial pass flagged its Esc/focus-trap as unconfirmed; it is a sheet, so a trap may not be required, but Escape-to-close and focus management are still unverified — a human-pass item. |
| New `fix-proposals` tab + `/api/scan-diff` + lifecycle states | `App.tsx:1721`, `2339`; `lifecycle.py`; backend routes per batch 12/13 receipts. | First-class surfaces added this stage; AGENTS.md route memory still lists only the original tab set (also flagged in the initial pass) — `documentation-health` / `ai-maintainability` should refresh it. |
| Built dashboard assets regenerate on every `build` (gitignored) | `npm run build` rewrites `src/security_observatory/dashboard/assets/`; only `index.html` is committed. | Reproducible build confirmed the committed `index.html` is unchanged — but it means the chunk-size warning (row 1) prints on every developer build. |

## Top Repair Targets

1. **Kill the chunk-size-warning regression (S-029, row 1).** Lazy-load the heavy non-default views or set `chunkSizeWarningLimit` with a recorded rationale, so `npm run build` no longer prints a warning the team has decided to ignore. Highest leverage because it silently re-opened a closed health claim and masks future chunk problems.
2. **Migrate `AddRepoDialog` onto the shared `Dialog` primitive (S-041, row 2).** Drop the bespoke Escape effect, gain focus-trap + focus-restore on the first-run gateway modal so it matches the bar every other modal now meets; add an axe/trap vitest spec.
3. **Human browser confirmation pass** of the items this session could not render (operating rules forbade running the dashboard): Tab-walk Overview→Cases→a case→a decision keyboard-only, press ⌘K, trigger a missing-scanner failure to see each `RunErrorNotice`, exercise a real `/api/scan-diff` and a rescan-to-closure, and confirm `RunCheckSheet` Escape/focus. The component/axe/build evidence is strong; this closes the last rendered-behavior gaps before the Stage D campaign.

## SocratiCode Value

SocratiCode was not used this session. The confirm-set was a fixed list of S-IDs with exact
file/line evidence from the initial pass and the batch receipts, so direct `grep`/`Read`/`sed`
against `App.tsx`, `index.css`, `model.py`, the deleted-component dir listing, plus fresh
`lint`/`vitest`/`build` gave citable, verifiable evidence faster than a librarian pass — exactly
the case the suite's cost-discipline rule says to prefer direct inspection for. The MCP
`devsec` and `socraticode` servers were available but a structural map added nothing over the
targeted reads for a re-confirmation pass.

## Limits

- **No rendered behavior this session.** This step's operating rules forbid running
  dashboards/servers (a non-loopback listener trips the macOS firewall prompt that freezes an
  unattended run; even loopback was excluded by the explicit "do not run dashboards"
  instruction). So no browser smoke, screenshot, keyboard walk, or lighthouse ran here. Medium-
  confidence rows (scan-error rendering in a real flow, lifecycle/diff exercised live,
  RunCheckSheet Esc) rest on source + the batch-06/09 receipts' own in-browser smokes, not a
  fresh render. The human Final-review gate should run the row-3 browser pass.
- **Receipts cross-checked, not trusted.** Every "Green" claim above was re-verified against
  current source this session; the two residuals (bundle warning, AddRepoDialog focus-trap)
  were found *because* the receipts' claims were checked against a fresh build and the actual
  modal code rather than taken at face value.
- **No sibling-lens overlap.** Pure contrast/focus-ring-color/screen-reader/token specifics and
  the non-case Tailwind-opacity styling debt are deferred to
  `design-system-accessibility-health-forensic`; whether rescan-to-closure actually closes a
  case end-to-end is `product-workflow-health-forensic`; the AGENTS.md route-memory drift is
  `documentation-health` / `ai-maintainability`. The two residuals here are taken in this lens
  because both directly change user-facing behavior (build-noise health honesty; keyboard
  behavior on the first-run modal).
- **Punch-list is for Stage D.** Per the campaign, residuals feed the human-launched Stage D
  patch campaign; this pass does not fix them. Both are Green/Yellow polish — neither blocks the
  behavioral-UX advance gate, which clears: no Red, no Yellow/Red.
