# Behavioral UX Health Forensic — DëvSec (Security Observatory)

> Worst health: Yellow/Red · Lens: behavioral-ux-health-forensic (headline; initial of two passes) · Date: 2026-06-01

## Executive Finding

DëvSec's triage spine is genuinely well-conceived and, in the Mistglass-styled shell, often
excellent. The Overview hero collapses a wall of scanner output into one ranked verdict that
de-escalates correctly — critical case → open-case count → stale-scan nudge → calm "You're
in great shape." (`overviewHeroCopy`, `App.tsx:819-894`). Severity is driven by both color
*and* an explicit text label (`severityMeta`, `App.tsx:382-389`), honoring DESIGN.md §1
("loud only when earned") and the Brief's "no false calm." Empty and first-run states are
crafted (`EmptyRepoView` and `EmptyRepoState` both have an icon, plain copy, a local-first
reassurance, and two clear actions; the no-cases state says clean is "not a guarantee that
the repo is safe"). The "Pick a repo" gates embed an in-place repo selector rather than
dead-ending (`NeedsRepoTarget.tsx:18-44`, `role="note"`). Keyboard support is better than
typical: global `prefers-reduced-motion` (`index.css:102`), real `<button>` nav, and the
interactive `RiskLandscape` cells carry `role="button"` + `tabIndex={0}` + `onKeyDown`
(`App.tsx:3573-3575`). The actually-mounted Cases view is a proper master-detail
(`FindingsTable` + `CaseDetailCard`, `App.tsx:2343+`) with Mistglass `PaperCard`/`Chip`
filters whose severity chips show colored dots (`severityMeta[tone].dot`). This is the
product's signature feel working, and a lot of it is finished.

But the lens surfaces **one defect on the core loop the Brief treats as a first-class
failure, plus a cluster of off-system / unfinished surfaces.** (1) **The first-run "add a
repo" step — the gateway to almost the whole product — is a raw
`window.prompt('Paste the full path to the repo folder.')`** (`App.tsx:996`): no folder
picker, no validation that the path exists, no example, silent failure on empty input, and
it is fired from four places including a dropdown *option* ("+ Add repository…"). For
Christian's stated non-technical audience this is the worst possible first interaction. (2)
**`window.prompt` recurs across the core loop** — case-decision notes appear in *both*
case renderers (`CaseCard.tsx:81` and the inline `CaseDetailCard`, `App.tsx:3346`) and the
Honey-key incident-close (`App.tsx:2598` / `HoneyKeysView.tsx:157`). The decision *buttons*
are crafted; the note capture drops to a blocking OS dialog mid-resolution. (3) **There are
two `FindingsView` implementations.** The mounted one is the inline `App.tsx:2343` master-
detail; a separate, differently-organized `components/FindingsView.tsx` (289 lines, filter
buttons + suppressed-audit section) is reachable from nothing — dead code that guarantees
future Cases edits land on the wrong twin and the two experiences drift. (4) **The standalone
`CaseCard.tsx` is off-Mistglass** — pure-black ink, `font-light`, `border-black`,
`shadow-[inset_0_3px_0_#111111]`, and severity shown as a faint `text-black/45` gray label
with no colored pill (`CaseCard.tsx:27-32, 96-99`) — exactly the `#000`/alarm register
DESIGN.md §2 bans. Because it's only used by the dead twin today, this is latent rather than
live, but if that twin is ever revived it lands a louder, off-system surface on the most-used
triage screen. (5) **The toolbar shows a `⌘K` hint (`App.tsx:1612`) wired to nothing** —
the only global keydown handler is `installHardRefreshShortcut`, which handles **⌘R/Ctrl-R**
hard-refresh only (`main.tsx:7-28`); grep finds no ⌘K/command-palette handler anywhere. It
is a false affordance promising a speed feature that does not exist. (6) **Scan-failure
feedback collapses to one undifferentiated `runError` string** (set in ~8 places) rather
than the crafted, differentiated error states DESIGN.md §7.5 wants.

Net: the calm-triage intent is strong and much is finished, but the entry point is an
uncrafted native dialog, the core loop repeatedly drops to `window.prompt`, the headline
screen carries a dead off-system twin, and the UI advertises a shortcut it doesn't have.
**Worst row Yellow/Red; overall Yellow.** This is the headline lens and the Brief says it
needs work — the findings are concrete and source-verified; the post-repair final pass
should re-confirm them in a running browser.

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security` (Security Observatory — local-first security scanner: Python CLI + SQLite history + React/Mistglass dashboard + read-only/guarded-write MCP + Honey Keys + macOS desktop launcher)
- Skill/lens: `behavioral-ux-health-forensic` (headline lens; initial of two passes)
- Date: `2026-06-01`
- Requested focus: Triage flow noise-to-action, speed, keyboard-first navigation, scannable severity legibility, progressive disclosure, alarm-fatigue vs false-calm, and crafted empty/loading/error/first-run states across the dashboard surfaces (Overview, Activity, Cases, Honey keys, Tool catalog, Agent lab, Recovery playbooks, Verification, Reports, Settings).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| Read orientation set (excellence-brief, SKILL, health-suite-standard, forensic-report template) | PASS | All four read in full. |
| Read `DESIGN.md`, `README.md`, `AGENTS.md`, `.adx/{risks,verification,adx,commands}.json` | PASS | Mistglass spec, "real vs not yet" table, stable routes, severity tokens obtained. |
| Read `App.tsx` (4027 lines: state + full render incl. Sidebar, Toolbar, RunCheckSheet, OverviewView, inline FindingsView master-detail, CaseDetailCard, EmptyRepoView, HoneyKeysView, Playbooks/Verification/Activity/Reports/Settings, BarChart/Donut/Button/PaperCard/Chip/Notice/EmptyLine) | PASS | The actually-mounted triage shell + Cases view + sub-component library. |
| Read `CaseCard.tsx`, `FindingsView.tsx` (standalone), `EmptyRepoState.tsx`, `NeedsRepoTarget.tsx`, `SinceLastScanPanel.tsx`, `main.tsx` | PASS | Confirmed the dead twin, the off-Mistglass card, the three window.prompt sites, the gate picker, and the ⌘R-only global shortcut. |
| `index.css` for reduced-motion / focus / kbd | PASS | `prefers-reduced-motion` at 102; `kbd` styled at 124 + 543; per-control `outline:0` resets at several lines (focus-ring handling to verify with `design-system-accessibility-health`). |
| `npm run lint` / `npm run build` | NOT RUN | Dashboard validation commands mutate `node_modules`/build output and the tool channel was intermittently flaky; not safe-run this session. Not inferred to pass. |
| Browser smoke / screenshot / keyboard / lighthouse | NOT RUN | Dashboard server intentionally not started (AGENTS.md + `.adx/risks.json`; `security-scan dashboard`/launcher are flagged). No rendered pixels captured. |

No installer, scanner, dashboard server, desktop launcher, process-kill, or any
`dangerous_command_patterns` entry from `.adx/risks.json` was run. The only write is this report.

## Ranked Health Table

Weakest / highest-user-risk first. Impact lens = **user** (friction lands on the user's confidence, completion, and trust).

| Rank | Area | Health | Confidence | Evidence | Impact | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | First-run "add a repo" via raw `window.prompt` | Yellow/Red | High | `App.tsx:994-1004` — `selectTarget('add-repo')` → `window.prompt('Paste the full path to the repo folder.')`; empty input silently `return`s; only normalization is `.trim().replace(/\/+$/,'')`; no existence check/picker/example/inline error. Fired from the sidebar select (`1500`), toolbar select (`1591`), QuickActions "Add repository" tile (`1991`), and NeedsRepoTarget (`add-repo` option). It is the gateway: Operate views are `repo-required` (`342-363`). | The product's first interaction is its least-crafted surface — a blocking OS dialog with no validation. Non-technical users can't browse to a path and get no feedback on a typo. Named "janky/dead-end UX" failure in the Brief. | Replace with an in-app Mistglass PaperCard form: text input + known/recent-repo suggestions from `/api/projects` + inline "path not found" validation + one primary action; retire the dropdown-option-as-action. | After fix: `npm run lint && npm run build`; browser smoke add-repo with a bad path and an empty submit. |
| 2 | `window.prompt` recurs across the core loop (decision notes, incident close) | Yellow | High | Three sites beyond add-repo: `CaseCard.tsx:81` and inline `CaseDetailCard` `App.tsx:3346` (`'Optional note for this decision'`), and `App.tsx:2598`/`HoneyKeysView.tsx:157` (`'Add an accepted-risk note before closing this incident.'`). The one-click decision/close buttons are crafted in-card; the note capture is a native dialog; `null` (cancel) aborts silently. | The act-on-a-case and close-incident steps (core loop + a security-sensitive close) drop to an uncrafted OS prompt right at the moment of resolution, breaking the "effortless triage" feel and obscuring cancel/empty handling. | Replace each note prompt with an inline note field / small Mistglass popover on the card; keep one-click decisions. | Final pass: record a decision and close an incident in-browser; confirm no native dialog. |
| 3 | Duplicate `FindingsView` + off-Mistglass `CaseCard` (dead twin) | Yellow | High | Mounted Cases view is the inline `App.tsx:2343` master-detail (`1389`). A separate `components/FindingsView.tsx` (289 lines, distinct filters + suppressed-audit section) plus its `CaseCard.tsx` are imported by nothing reachable. That `CaseCard` is off-system: `text-black`, `border-black`, `font-light`, `shadow-[inset_0_3px_0_#111111]`, severity as faint `text-black/45` text with no colored pill (`CaseCard.tsx:27-32, 95-99`) — the `#000`/alarm register DESIGN.md §2 bans. | Latent, not live: a maintainer "fixing the Cases UI" could edit the dead twin (no effect) or revive it (lands a louder, off-Mistglass surface with near-invisible severity on the most-used screen). Either way the two experiences drift. | Decide one canonical Cases implementation; delete the unused `FindingsView.tsx`/`CaseCard.tsx` after merging any wanted parts, or re-skin them to Mistglass with real `SeverityPill`s before any reuse. | Final pass: grep confirms a single mounted Cases component; no off-`#000` case styling remains. |
| 4 | `⌘K` shortcut hint with no handler (false affordance) | Yellow | High | `App.tsx:1612` renders `<kbd>⌘K</kbd>` in the toolbar search. The only global keydown listener is `installHardRefreshShortcut` (`main.tsx:7-28`), which handles **⌘R/Ctrl-R** hard-refresh only; grep across `src/` finds no ⌘K / command-palette / search-focus handler. | Advertises a keyboard speed feature (named in the Brief's "definition of excellent") that does nothing — erodes trust and frustrates power users who press it. | Implement ⌘K (focus search / open a command palette) or remove the `<kbd>` hint until it exists. | Final pass: press ⌘K in browser; confirm it acts, or the hint is gone. |
| 5 | Scan-failure feedback collapses to one undifferentiated error | Yellow | Medium | Progress is good: 1200 ms poll updates `currentStep`/`progress` (`967-992`); `RunCheckSheet` shows a bar + step list (`1761-1772`); `LiveScanProgress` shows per-repo rows (`2206-2242`). But every failure path sets a single `runError` string (`983,987,1135-1137,1205`) rendered as a generic `inline-error` (`1784`); scanner-missing vs scanner-errored vs scan-failed are not differentiated, and DESIGN.md §7.5 wants a crafted error card with a clear retry/route. | During a scan (highest-anxiety moment for a security tool) a failure shows one red line; the user can't tell what broke or where to go. The run-check copy at `1136` already hints "Open Verification" — that routing should be in the error UI. | Differentiate error states (missing tool → link to Verification; errored → retry; failed → details) as Mistglass cards. | Final pass: browser smoke a scan with a missing scanner; confirm the error is actionable. |
| 6 | Loading & first-fetch-failure states (DESIGN §7.6 / §7.5) | Yellow | Medium | Crafted states exist for empty/no-scan/no-cases/gates and an Overview refresh `Notice` (`1956`). But list/view transitions use `motion` fade-ins, and DESIGN.md §7.6 mandates a *static placeholder, no spinner/shimmer*; whether the initial load and a failed first `/api/summary` (stored only as `error` string, `914-927`) render a crafted card vs a blank/raw state is not confirmable without the running app. | First-load and "API down on first open" are where trust is won; an uncrafted one is a Brief non-negotiable. Currently unverified, not disproven. | Confirm loading uses a static placeholder and a failed first fetch shows a crafted card, never blank/raw. | Final pass: browser smoke with the API down and an empty DB. |
| 7 | Severity tuning / alarm-fatigue vs false-calm | Green/Yellow | High | Strong: `severityMeta` is text+color, never color-alone (`382-389`); `toneForSeverity` reserves `crit` (`520-527`); hero only escalates to "Critical case needs attention." for a real `severity==='critical'` case, else de-escalates (`819-894`); clean scans say "not a guarantee that the repo is safe." The mounted Cases view's severity chips carry colored dots (`severityMeta[tone].dot`). Honors DESIGN.md §1 + the Brief. Minor: `crit` pill `bg:'#dcaaa5'` is hotter than DESIGN.md `--sev-crit-soft #e8c6c0`. | Largely a *strength* and the product's best UX trait — calm by default, honest about clean scans. Only watch item is the slightly hot critical fill (the faded severity issue is confined to the dead twin, row 3). | Align `crit.bg` to the DESIGN.md token. | Final pass: visual check of critical vs elevated pills. |
| 8 | Keyboard navigation, focus order, modal Esc/trap | Green/Yellow | Medium | Foundations present: `prefers-reduced-motion` (`index.css:102`), real `<button>` nav (`Sidebar` 1512) with `disabled` + `title` on gated items, native `<select>` switchers, `aria-label`ed search, `RiskLandscape` cells keyboard-operable (`3573-3575`), dialogs carry `role="dialog"`/`aria-modal` (AiFollowUp/Rotation modals). Risk: the dead ⌘K (row 4); per-control `outline:0` resets in `index.css` (focus-ring presence to confirm with the a11y lens); `RunCheckSheet` modal Esc/focus-trap not confirmed. | Keyboard basics are above-typical, so mostly polish — but the dead ⌘K and unconfirmed modal Esc/focus-trap are real friction for power users. | Confirm modal focus-trap + Esc; ensure a visible focus ring survives the `outline:0` resets. (Pure focus-ring/contrast specifics → `design-system-accessibility-health-forensic`.) | Final pass: tab Overview→Cases→a case→a decision keyboard-only; Esc the run sheet. |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| Dead `components/FindingsView.tsx` + `CaseCard.tsx` | Mounted Cases view is inline `App.tsx:2343` (`1389`); the standalone 289-line `FindingsView` and the off-Mistglass `CaseCard` it imports are reachable from nothing. | Hidden second implementation of the headline screen (ranked row 3). A maintainer could "fix the Cases UI" in the wrong file or revive an off-system surface. |
| `⌘R/Ctrl-R` hard-refresh global shortcut | `main.tsx:7-28` `installHardRefreshShortcut` intercepts ⌘R and reloads with a `_refresh` cache-buster query param. | Undocumented behavior override of the browser's native refresh; harmless but surprising, and it is the *only* global shortcut — making the `⌘K` hint's absence more glaring. |
| Hidden `?setupCardDemo=1` storybook route | `main.tsx:30-38` boots `SetupCardDemo` instead of the app when the query param is present; mock fetch handlers intercept `/api/*`. | A hidden visual-verification route — useful, but undocumented in AGENTS.md route memory; the final pass / `documentation-health` should record it. |
| Tab set wider than AGENTS.md route memory | `TabId` union + `navGroups`: overview, activity, **findings (Cases), honey-keys, scanners (Tool catalog), agent-lab, playbooks, verification**, reports, settings (`App.tsx:171, 298-335`). Memory lists only overview/activity/cases/catalog/reports/settings. | Honey keys, Agent lab, Recovery playbooks, Verification are first-class triage-adjacent views absent from canonical route memory; in-lens but under-documented. |
| `add-repo` dropdown option fires a native prompt | `selectTarget` switches on string sentinels (`994-1013`); the repo `<select>` overloads "+ Add repository…" to open `window.prompt`. | A select option that is secretly an action is an affordance smell; feeds row 1. |
| Custom repos persisted to `localStorage` | `customReposStorageKey='security-observatory-custom-repos'`, read on mount, written on add (`368,404-411,1000-1002`). | Hidden client-side store of typed repo paths; shapes the "why did my repo list change between machines" mental model. Note for privacy-boundary lens (paths are local identifiers). |
| Coming-Soon walls reachable from navigable surfaces | README "real vs not yet": External Surface + the IaC Pack *page* are Coming Soon; catalog uses `catalogRunReady`/`previewCanInstall` gating. | Brief non-negotiable: a Coming Soon wall reached from a working-looking action. Out of scope to *build* per Brief, but in scope to confirm these read as honestly not-yet and aren't reachable as fake working actions. |

## Top Repair Targets

1. **Replace the raw `window.prompt` add-repo flow** (`App.tsx:994-1004`) with a crafted in-app Mistglass form: existence validation against `/api/projects`, known/recent suggestions, an example, inline error. Highest leverage — first-run gateway and least-finished surface. Retire the dropdown-option-as-action smell.
2. **Get `window.prompt` out of the core loop**: replace the decision-note prompts (`CaseCard.tsx:81`, inline `CaseDetailCard` `App.tsx:3346`) and the incident-close note (`App.tsx:2598`) with inline Mistglass note fields, so resolving a case or closing an incident never drops to a native dialog.
3. **Resolve the Cases duplication and the false ⌘K**: pick one canonical Cases implementation and delete the dead off-Mistglass `FindingsView.tsx`/`CaseCard.tsx` twin (or re-skin to Mistglass + `SeverityPill` before any reuse), and either implement the `⌘K` shortcut or remove the `<kbd>` hint (`App.tsx:1612`).

## SocratiCode Value

SocratiCode was not used this session and was never reachable: `ToolSearch` for Glob/Grep
returned "no matching deferred tools" and the tool channel degraded intermittently before any
`socraticode` bootstrap could run; indexed-state is unknown. Per the suite's cost-discipline
rule this was acceptable — direct `Read`/`grep` of `App.tsx`, `CaseCard.tsx`,
`FindingsView.tsx`, and `main.tsx` plus the `DESIGN.md` contract gave exact, citable evidence
for the window.prompt sites, the dead twin, the off-Mistglass register, and the dead ⌘K
without a librarian pass (and let me *correct* an early mis-read: the `metaKey` grep hit was
the ⌘R hard-refresh, not ⌘K). For the mandated **final pass**, the highest-leverage
SocratiCode move (if indexed) is one scoped `codebase_flow` from Overview hero → case
decision (`saveCaseDecision`) → rescan, to confirm the visible lifecycle wiring; cache the
result so the final report need not re-query.

## Limits

- **Intermittent tool-output failure.** Several `sed`/`grep`/`Read` calls returned empty
  output mid-session (a bare `echo` once returned nothing), then recovered on retry. This is
  environment infrastructure, not the product, and not the `ë`-path (the same tree read fine
  repeatedly). It slowed but did not block the audit; all High-confidence rows rest on direct
  source reads that are verifiable without the running app.
- **Two mid-flight corrections.** An early draft over-stated the off-Mistglass problem as
  covering the live Cases screen (it is concentrated in the *dead* twin; the mounted view is
  more on-system, with colored severity chips) and briefly mis-attributed a ⌘R handler as a
  possible ⌘K wiring. Both are corrected above; the corrected versions are the findings of
  record.
- **No rendered behavior.** The dashboard server was correctly not started (guardrails), so
  no browser smoke, screenshot, lighthouse, keyboard walk, or `npm run lint/build` ran. None
  were inferred to pass. Medium rows (loading/first-fetch-failure styling, modal Esc/focus-
  trap, scan-error rendering) need the running UI.
- **No sibling-lens overlap.** Pure contrast/focus-ring/screen-reader/token findings are
  deferred to `design-system-accessibility-health-forensic` (the dead-twin pure-black and
  faded-severity are noted here only as a behavioral drift risk on the core surface).
  End-to-end completion plumbing (does rescan-to-closure actually close a case?) is deferred
  to `product-workflow-health-forensic`.
- **Mandatory re-confirmation in the final pass.** As the headline lens, the post-repair pass
  must verify in a running browser: the new add-repo form, no `window.prompt` left in the
  loop, a single canonical Mistglass Cases surface, the ⌘K decision, differentiated scan-
  error states, and the loading/first-fetch-failure states — before the campaign's advance
  gate clears on behavioral-UX.
