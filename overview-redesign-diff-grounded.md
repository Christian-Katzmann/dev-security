# Overview Redesign - V1 -> V2: Code-Grounded Implementation Map

Source diff: `/Users/christiankatzmann/Downloads/overview-redesign-diff.md`
Repo root: `/Users/christiankatzmann/Dev/Projects/dëv-security`

This pass grounds the pixel-only diff against the actual code. Paths below are repo-relative unless explicitly absolute. No application code was changed.

---

## Phase 1 - Orientation

### Framework, language, styling system, component library

- Framework/runtime: React 19 + TypeScript + Vite in `dashboard-ui/`.
- Styling: mostly hand-authored CSS in `dashboard-ui/src/index.css`, with Tailwind 4 imported and used in some older/component-local files.
- Component/icon libraries: `lucide-react` for icons, `motion` for some older component files.
- App entry: `dashboard-ui/src/main.tsx` renders `dashboard-ui/src/App.tsx` except the hidden `?setupCardDemo=1` route.

### Design tokens / theme / colors

- Real active token source: `dashboard-ui/src/index.css`, especially `:root` variables at the top.
- Canonical design doc says tokens live in `colors_and_type.css`, but that file is not present in this repo. Treat this as a code/doc mismatch before doing a large palette pass.
- The palette shift should start in `dashboard-ui/src/index.css` (`--mist-surface-*`, `--paper*`, `--sev-*`, radii, shadows), then patch component-specific hardcoded colors where needed.

### Sidebar nav and routing

- Nav config: `navGroups`, `tabTitles`, `viewsByMode`, and `navScopeLabel()` in `dashboard-ui/src/App.tsx`.
- Routing is in-memory tab state (`TabId`, `activeTab`, `setActiveTab`), not URL routes.
- Catalog has its own in-memory subroute (`CatalogRoute`) inside `App.tsx`.
- Sidebar target selection is a hidden `<select>` in `Sidebar`; the top toolbar currently displays the scope as passive text.

### Data layer feeding Overview

- Frontend loads `/api/summary` and `/api/projects` in `dashboard-ui/src/App.tsx`.
- `/api/summary` is served by `src/security_observatory/dashboard_server.py`, using `ObservatoryDB.dashboard_payload()` in `src/security_observatory/storage.py`.
- `/api/projects` is served by `src/security_observatory/dashboard_server.py` using `discover_repos()`.
- Overview data is filtered by `filterSummaryByTarget()` from `dashboard-ui/src/dashboardData.ts`.
- Posture score: `postureScore()` in `App.tsx`, based on `averageHealth(summary)` from `dashboardData.ts`.
- Repo counts: `targetRepos = mergeProjectRepos(projectRepos, customRepos, summary.repos)`.
- Open cases: `activeCaseList(summary)` -> `displayCases(summary).filter(caseNeedsAttention)`.
- Recent activity: `buildActivity(summary, includeRepo)` in `App.tsx`, composed from honey events, active cases, scan history, and project statuses.
- Tool coverage: `topScannerItems(globalSummary)` from `uiHelpers.ts`, ultimately `scannerDoctorGroups(summary)` in `dashboardData.ts`, plus `toolCatalogItems(globalSummary)`.
- Honey key counts: `honeyKeyCounts(summary)` in `dashboardData.ts`.

### Overview entry file and composed components

- Live Overview implementation: `OverviewView()` defined inside `dashboard-ui/src/App.tsx`.
- It composes `hero-digest`, `KpiCard`, `ScanControlPanel`, optional `PreCaseScanNote`, optional `RepositoryComparisonStrip`, `Notice`, bottom `Open cases` and `Recent activity` `PaperCard`s, and repo-only `RotationStatusCard`.
- Important: `dashboard-ui/src/components/OverviewView.tsx` exists but is not imported by `App.tsx`; it is not the live Overview shown in the screenshot.

---

## How items are tagged

- **[VISUAL]** - pure styling. Safe to hand to the fast visual AI only when the code notes below do not re-tag it.
- **[CODE]** - needs logic, data, routing, or structural change. Hand to engineering.
- **[SPLIT]** - has a visual part and a code part.
- **[DATA-STATE]** - likely empty-vs-populated data state, unless code notes below flag a real fallback/hardcode problem.

**The big thesis of the redesign, in one line:** V1 is an expert, dense, raw-data control panel. V2 is a friendly, status-first, guided dashboard. Almost every choice below serves that shift.

---

## A. Brand / workspace switcher (top-left)

- **[VISUAL]** Logo: replace the sage shield *outline* with a **solid green rounded square containing an "A" monogram**.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `Sidebar`; CSS `.workspace-card`, `.workspace-mark`. Shared only as the global app shell.
  - -> Data: current mark is hardcoded as `<ShieldCheck size={17} />`; no workspace avatar/initial source found.
  - -> Note: visual for MVP if the "A" is a static brand/workspace mark. If it should be a real workspace initial, this becomes CODE because no workspace identity model exists.

- **[SPLIT]** Workspace label: "All repos / All repositories" -> "All repos / **18 repositories**".
  - Visual: same two-line layout, friendlier weight.
  - Code: the count ("18") is real data, not a static string.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/dashboardData.ts`, `src/security_observatory/dashboard_server.py`.
  - -> Component: `Sidebar`; uses `targetLabel(target)` and a hardcoded subtitle expression.
  - -> Data: bind count to `targetRepos.length` for selectable repositories. `targetRepos` is `mergeProjectRepos(projectRepos, customRepos, summary.repos)`, fed by `/api/projects`, local custom repos, and scanned repos.
  - -> Note: current subtitle hardcodes "All repositories" / "Specific repo"; it does not render a count. Use `summary.repos.length` only if the label is meant to mean scanned repos, but the target copy reads like selectable total repositories.

- **[VISUAL]** Overall: warmer, more saturated, more rounded than V1's muted/flat treatment.
  - -> Files: `dashboard-ui/src/index.css`.
  - -> Component: shell CSS for `.mist-sidebar`, `.workspace-card`, `.workspace-mark`.
  - -> Note: mostly token/radius/shadow work. Coordinate with global token pass in section M.

## B. Left sidebar - structure & content

- **[CODE]** First nav group changes membership:
  - V1: **Overview, Cases, Honey keys**
  - V2: **Overview, Goals, Activity**
  - So: `Cases` and `Honey keys` are **removed** from nav, `Goals` is **added**, and `Activity` **moves up** from the bottom group. (Decide intent: is "Goals" a rename of something, or genuinely new?)
  - -> Files: `dashboard-ui/src/App.tsx`.
  - -> Component: `navGroups`, `TabId`, `tabTitles`, `viewsByMode`, `ActiveView`, `Sidebar`.
  - -> Data: nav count badges currently use `navCounts` for `findings`, `honey-keys`, `agent-lab`, and `verification`.
  - -> Note: `Goals` is not found in code. This is a new tab/view unless product decides it maps to an existing view. Hiding `Cases` and `Honey keys` from sidebar should not delete their routes; Overview cards and deep flows still need to open `findings` and `honey-keys`.

- **[CODE]** Section headers change:
  - V1: `WORKSPACE`, `OPERATE`, `RECORDS`
  - V2: *(no header on first group)*, `OPERATE`, `REPORTS`
  - So: the `WORKSPACE` header is dropped, and `RECORDS` is renamed `REPORTS` (now containing only Reports).
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `navGroups`, `Sidebar`, CSS `.sidebar-group-title`.
  - -> Note: the first group currently always renders `group.title`; support `title: null` or conditional header rendering.

- **[VISUAL]** Capitalization: "Recovery playbooks" -> "Recovery **P**laybooks".
  - -> Files: `dashboard-ui/src/App.tsx`.
  - -> Component: `navGroups`, `tabTitles`.
  - -> Note: string-only, but keep `tabTitles.playbooks` consistent with the nav label.

- **[VISUAL]** Remove all the inline `REPO` / `GLOBAL` tags next to nav items.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `navScopeLabel()`, `Sidebar`; CSS `.nav-scope`.
  - -> Note: re-tag VISUAL -> CODE. The pills come from logic, not CSS alone. Keep `viewsByMode` for disabled/availability behavior, but stop rendering `navScopeLabel()`.

## C. Left sidebar - styling

- **[VISUAL]** Icons: thin monochrome outline -> **filled / duotone green** icons.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `Sidebar`, nav icon entries in `navGroups`; Lucide icons are outline SVGs.
  - -> Note: visual, but coordinated. Lucide does not provide filled variants for most icons, so implement with soft icon containers / stroke colors or switch selected icons deliberately.

- **[VISUAL]** Selected-item state: V1's flat gray fill -> V2's softer **green-tinted highlight**.
  - -> Files: `dashboard-ui/src/index.css`.
  - -> Component: CSS `.nav-row.active`.
  - -> Note: safe visual CSS change.

- **[VISUAL]** General spacing/rounding feels a touch softer and warmer.
  - -> Files: `dashboard-ui/src/index.css`.
  - -> Component: `.mist-sidebar`, `.workspace-card`, `.nav-row`, `.sidebar-footer`.
  - -> Note: safe visual CSS, but check mobile because sidebar becomes a horizontal top nav at `max-width: 720px`.

## D. User profile (bottom-left) - NEW

- **[SPLIT]** Add a profile block above Settings: **circular avatar + green online dot + "Alexandra / Admin" + dropdown chevron.**
  - Visual: the avatar card, dot, layout, chevron.
  - Code: real user name, role, photo, and what the dropdown opens.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `Sidebar`, `.sidebar-footer`.
  - -> Data: not found. No current user, account, team, member, role, avatar, auth, or profile endpoint found. `Alexandra`, `Admin`, and "Invite members" are not in the codebase.
  - -> Note: do not hardcode target mock data. Recommendation: either defer profile data until account/team exists, or introduce a small local profile config contract explicitly. Dropdown behavior is also not defined.

- **[VISUAL]** Settings row keeps its gear icon; restyle to match the new icon language.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `Sidebar`, settings footer button.
  - -> Note: visual CSS/icon treatment, but mobile currently hides `.sidebar-footer`, so the new profile/settings area needs a mobile placement decision.

## E. Top bar (heading, posture pill, search)

- **[VISUAL]** Page heading "Overview": larger / bolder in V2.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `Toolbar`; CSS `.toolbar-title strong`.
  - -> Note: re-tag VISUAL -> SPLIT if changing only Overview, because `Toolbar` is shared by all tabs. Current CSS uses weight 700, while `DESIGN.md` says product display should cap at 600.

- **[SPLIT]** Subtitle next to heading: "All repos" -> "**All repositories**" rendered as a clear dropdown.
  - Visual: dropdown styling. Code: it's a real repo-scope selector.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/dashboardData.ts`.
  - -> Component: `Toolbar`; target state comes from `target`, `targetLabel()`, `selectTarget()`.
  - -> Data: existing real selector lives in `Sidebar` as `.workspace-select`; `Toolbar` only receives a string `targetLabel`.
  - -> Note: code change. Pass `target`, `targetRepos`, and `onTargetChange` into `Toolbar`, or extract a shared `TargetSelector`.

- **[VISUAL]** Posture pill format: `POSTURE 10.0 +0.0` -> `POSTURE: 10.0 / 10`.
  - Adds a colon, adds the `/10` denominator, **drops the `+0.0`** delta.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `Toolbar`, `.posture-pill`.
  - -> Data: `posture.score` and `posture.delta` are real values from `postureScore()` / `postureDelta()`.
  - -> Note: re-tag VISUAL -> SPLIT. Dropping delta is a content/behavior decision in shared toolbar markup.

- **[VISUAL]** Pill status dot reads clearly green in V2.
  - -> Files: `dashboard-ui/src/index.css`.
  - -> Component: `.status-dot`, `.status-dot.live`.
  - -> Data: state classes are driven by `error` and `isLoading` in `Toolbar`.
  - -> Note: visual token adjustment; keep paused/syncing states distinct.

- **[VISUAL]** Search placeholder: "Search cases, **manifests**" -> "Search cases, **tools, repos**..." (jargon removed, ellipsis added).
  - -> Files: `dashboard-ui/src/App.tsx`.
  - -> Component: `Toolbar`.
  - -> Data: placeholder is hardcoded by tab title expression. Existing alternatives: Tool Catalog -> "Search tools, packs"; Agent Lab -> "Search proposals, tools"; otherwise "Search cases, manifests".
  - -> Note: string/code edit. Keep per-tab placeholders intentional.

- **[VISUAL]** Search field: more prominent, rounded, leading magnifier icon, clear `⌘K` chip.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `Toolbar`; CSS `.toolbar-search`.
  - -> Note: visual CSS. Search field is shared across pages.

## F. Hero banner - content & tone

- **[VISUAL]** Background: muted desaturated sage-green -> **richer forest/emerald gradient**, more depth and contrast.
  - -> Files: `dashboard-ui/src/index.css`.
  - -> Component: `.hero-digest`, token variables `--mist-surface-*`.
  - -> Note: safe visual if done through tokens/classes; ripples to `verification-hero`, `report-hero`, and catalog surfaces that reuse the same tokens.

- **[SPLIT]** Date label: `TODAY . SATURDAY, MAY 30 . ALL REPOS` (all-caps, middots) -> `Saturday, May 20` (sentence case, clean).
  - Visual: casing + style. Data-state: the actual date differs only because the mocks were captured on different days.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `OverviewView`, `Eyebrow`.
  - -> Data: current date is dynamic: `new Intl.DateTimeFormat(...).format(new Date())`; scope is `targetLabel(target)`.
  - -> Note: no hardcoded date. Make scope treatment deliberate if the target drops `All repos` from the hero eyebrow.

- **[VISUAL]** Headline shifts from an **instruction** to a **status**:
  - V1: "Choose a repo and run a quick safety sweep."
  - V2: "**You're in great shape.**"
  - -> Files: `dashboard-ui/src/App.tsx`.
  - -> Component: `OverviewView`, `headline` local variable.
  - -> Data: current headline is already conditional on active cases, pre-case scans, and whether scans exist.
  - -> Note: re-tag VISUAL -> CODE. Replace the current conditional copy ladder with posture/case-aware friendly copy; do not hardcode the healthy line for all states.

- **[SPLIT]** Add an encouraging subtitle under the headline: "**Everything looks healthy. Keep it up!**"
  - Visual: the line + styling. Code: this string should be **conditional on posture** (healthy vs. needs-attention copy), not hardcoded.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `OverviewView`, `.hero-copy`.
  - -> Data: should bind to `cases`, `preCaseRepos`, `summary.repos.length`, and `posture.score`.
  - -> Note: no hero subtitle currently exists in the live `OverviewView`.

- **[SPLIT]** Primary/secondary buttons: "Open cases / See activity" -> "**Run a scan** / **View activity**".
  - Visual: button styles, green-tinted play icon.
  - Code: the **primary action changes** to "Run a scan" and must trigger a scan; "View activity" routes to Activity.
  - -> Files: `dashboard-ui/src/App.tsx`.
  - -> Component: `OverviewView`, `Button`, callbacks `onRunQuick`, `onOpenTab('activity')`.
  - -> Data: scan action uses existing `runQuickCheck()`; all-repos mode fans out through `runAllRepoChecks(['quick'])`.
  - -> Note: code change. Current primary opens `findings`; target primary must invoke scan flow.

## G. Hero banner - posture gauge

- **[SPLIT]** The gauge is the single biggest hero upgrade:
  - V1: an **empty outline circle** (even though the score is 10.0 - arguably a bug).
  - V2: a **filled green progress ring** with `10.0 /10` + `Excellent` + a small shield-check badge inside, and an "Overall posture" label above.
  - Visual: the filled ring, inner labels, badge, color.
  - Code: the fill % and the `Excellent`/tier word must **bind to the actual score**.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `Donut`, `OverviewView`, `.hero-metrics`, `.donut`.
  - -> Data: fill is already bound to `posture.score`. Tier label ("Excellent") is not found.
  - -> Note: correction: the live `Donut` does bind stroke progress to score, but it has no filled interior, no centered value, and no tier. Add a score-to-tier helper rather than hardcoding "Excellent".

## H. Hero banner - 7-day chart

- **[VISUAL]** Bars: V1's bars are barely visible (low contrast on the background) -> V2's bars are **clearly readable light-green, rounded tops**, with legible value labels.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `BarChart`, `.bar-chart.on-surface`.
  - -> Data: bar heights/labels come from `posture.week`.
  - -> Note: visual CSS, but see data note below about synthetic fallback values.

- **[VISUAL]** "Posture over the last 7 days" label reads as a clear chart title.
  - -> Files: `dashboard-ui/src/App.tsx`.
  - -> Component: `OverviewView`, `Eyebrow` currently renders `Posture . 7 d . {scopeLabel}`.
  - -> Note: string/markup change only.

- **[VISUAL]** Last bar stays highlighted (white) in both - keep that, just cleaner.
  - -> Files: `dashboard-ui/src/index.css`.
  - -> Component: `.bar-chart.on-surface span:last-child`.
  - -> Note: safe visual CSS.

- **[DATA-STATE]** The bar *values* differ (8.6/8.8/9.0... vs 8.6/8.7/8.4...) - sample data only, ignore.
  - -> Files: `dashboard-ui/src/App.tsx`.
  - -> Component: `postureWeek()`.
  - -> Data: when `summary.history` is empty, current code fabricates a 7-day series from the current score. That is why an empty state can still show a full-looking trend.
  - -> Note: re-tag DATA-STATE -> CODE. Do not chase mock values, but do fix the synthetic fallback so no-history renders honestly.

## I. The three summary cards

General, all three:

- **[VISUAL]** Add a **leading icon inside a soft light-green circle** to each card.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `KpiCard`, `.kpi-card`.
  - -> Note: mostly visual. `KpiCard` is currently only used by the Overview KPI row.

- **[SPLIT]** Add a **chevron (>)** on the right of each card.
  - Visual: the chevron. Code: cards become **clickable** and route somewhere.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `KpiCard`.
  - -> Data: not data-bound.
  - -> Note: correction: cards are already clickable `<button>`s with `onClick`. Chevron is visual affordance; only destination changes where the card meaning changes.

- **[VISUAL]** Labels move from ALL-CAPS to sentence case.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `KpiCard`, `Eyebrow`.
  - -> Note: re-tag VISUAL -> SPLIT if `Eyebrow` is changed globally, because it is used across many pages. Safer: give KPI labels their own sentence-case class.

- **[VISUAL]** Sublabels get **semantic color** (green for good, amber for attention).
  - -> Files: `dashboard-ui/src/index.css`, `dashboard-ui/src/App.tsx`.
  - -> Component: `KpiCard`.
  - -> Data: color should depend on computed card state, especially card 2.
  - -> Note: likely SPLIT because amber/green depends on data state.

Card by card:

- **[VISUAL]** Card 1: `OPEN CASES` (0) -> `Open cases` (0). Sublabel "0 raw findings . 0 non-low" -> "**0 critical . 0 high**" (green). Folder icon.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/dashboardData.ts`.
  - -> Component: `OverviewView`, `KpiCard`, helper `caseSeverityCounts()`, `activeCaseList()`.
  - -> Data: current value is `cases.length`; current detail uses raw/pre-case findings and `nonLowFindings`.
  - -> Note: re-tag VISUAL -> CODE for sublabel. Use active case severity counts (`critical` and `high`) rather than raw finding counts if the label says "Open cases".

- **[CODE]** Card 2: `HONEY KEYS ARMED` (1) -> `Repos with issues` (1). **The number "1" now means something completely different** (1 honey key armed -> 1 repo with issues). Sublabel "all quiet" -> "**1 needs attention**" (amber). Shield icon. -> This is a content/data change, not cosmetic - see Flags.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/dashboardData.ts`.
  - -> Component: `OverviewView`, `KpiCard`.
  - -> Data: current source is `honeyKeyCounts(summary).active`; target should count repositories with active cases/issues from `summary.repos` + `displayCases(summary).filter(caseNeedsAttention)`.
  - -> Note: route should likely open `findings` or a filtered repo-health view, not `honey-keys`. Honey Keys remain real product functionality but should not power this card.

- **[VISUAL]** Card 3: `TOOL CATALOG` (0/15) -> `Tool coverage` (0/15). Sublabel "16 catalog entries" -> "**15 tools available**" (also fixes V1's 15-vs-16 inconsistency). Clipboard icon.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/dashboardData.ts`, `dashboard-ui/src/uiHelpers.ts`.
  - -> Component: `OverviewView`, `KpiCard`.
  - -> Data: current value is `scannerHealthy / Math.max(scanners.length, 1)` from `topScannerItems(globalSummary)`; current detail uses `toolCatalogItems(globalSummary).length || scanners.length`.
  - -> Note: re-tag VISUAL -> CODE for the 15-vs-16 fix. Decide whether coverage denominator is scanner-capable tools, all catalog tools, or runnable tools. Do not paper over the mismatch with copy.

## J. Main content - Scan Control -> "What would you like to do?"

This is the largest structural change on the page.

- **[CODE]** **Remove the entire V1 "SCAN CONTROL" block** from the Overview, including:
  - The "Daily driver / No saved scan yet" panel.
  - The stacked action buttons "Run quick / Choose checks / Run all repos" + the "3-repo fan-out limit" caption.
  - The four metric tiles (Health / Saved cases / Setup gaps / Duration).
  - The "Scanner inventory" mini-stats (Ran / Setup gaps / Not run).
  - The 8 scanner cards (IOC Watch, Install hook classifier, Workflow surface audit, Built-in AI static checks, Medusa, Semgrep, Gitleaks, TruffleHog, each "Not run / 0 raw signals").
  - The "Latest scan by repo" empty state.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `ScanControlPanel`, `ScanMetric`, `ScanStatusCount`, `LiveScanProgress`, `ScannerInventoryMini`, `RepoScanStrip`; CSS `.scan-control-*`, `.scan-inventory-*`, `.scanner-inventory-*`, `.repo-scan-*`.
  - -> Data: uses `latestRepoScan(summary)`, `topScannerItems(summary)`, `setupGapCount(summary)`, `displayCases(summary)`, `activeJob`, `allRepoRun`, `isRunningCheck`, `runError`.
  - -> Note: remove from Overview only after confirming the same live-progress/run affordances remain reachable elsewhere.

- **[SPLIT]** **Add the "What would you like to do?" quick-action card** - a 6-tile launcher, each tile = icon-in-circle + title + subtitle:
  1. Run a scan - "Check your repos now"
  2. View catalog - "Explore available tools"
  3. View activity - "See recent scans and runs"
  4. View reports - "Open dashboards"
  5. Setup integrations - "Connect your tools"
  6. Invite members - "Add your team"
  - Visual: the grid, icons, circles, typography (a fast AI can build a static version).
  - Code: each tile **routes/triggers** its action; "Run a scan" and "Setup integrations" especially need wiring.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: new Overview-only component recommended, e.g. `QuickActionsPanel`; callbacks already available in `OverviewView`: `onRunQuick`, `onOpenTab`, `onChooseChecks`.
  - -> Data: no dynamic values in labels, but actions must call real handlers.
  - -> Note: "Setup integrations" as a destination is not found. It likely maps to Tool Catalog setup flows (`CatalogRouter`, `CatalogToolPage`, `SetupCard`) or `onChooseChecks`. "Invite members" is not supported by current local-first/userless data model.

- **[CODE]** Decide where the removed scan machinery now lives (choose-checks, run-all-repos, per-scanner status, fan-out). The Overview no longer shows it - it needs a home (a dedicated Scan/Tools page). See Flags.
  - -> Files: `dashboard-ui/src/App.tsx`, `src/security_observatory/dashboard_server.py`.
  - -> Component: `RunCheckSheet`, `VerificationView`, `CatalogRouter`, `runQuickCheck()`, `runFullCheck()`, `chooseChecks()`, `runAllRepoChecks()`, `startRepoCheck()`, `pollRepoCheck()`.
  - -> Data/API: `/api/run-check`, `/api/check-status`, `CheckJob`, `AllRepoRun`, `auditOptions`, `scanner_names_for_profile()` server-side.
  - -> Note: recommendation in appendix: keep run/choose/fan-out in `RunCheckSheet`; keep detailed scanner inventory in `VerificationView`; use Tool Catalog for setup/integration details.

## K. Recent activity panel

- **[CODE]** Replace V1's **24-hour timeline axis** (00:00-20:00, "No activity yet") with V2's **reverse-chronological list**.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `ActivityTimelineMini`, `ActivityRow`, Overview bottom `PaperCard`.
  - -> Data: `buildActivity(summary, includeRepo)` already returns reverse-sorted activity items.
  - -> Note: correction: the list already exists below the mini timeline when activities exist. Work is to remove `ActivityTimelineMini` from Overview and restyle/limit the existing list.

- **[VISUAL]** List item style: leading status icon + title + subtitle + right-aligned timestamp.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `ActivityRow`; shared by Overview and `ActivityView`.
  - -> Data: item fields are `icon`, `label`, `sub`, `at`, `tone`.
  - -> Note: re-tag VISUAL -> SPLIT if changing `ActivityRow` globally. V2 wants timestamp right; current `ActivityRow` puts time in the first column.

- **[VISUAL]** Add a "View all" link (top-right) and a "**View all activity ->**" button at the bottom.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `SectionHeader` right slot, Overview recent activity card, `Button`.
  - -> Data: routes to existing `activity` tab via `onOpenTab('activity')`.
  - -> Note: top-right link exists as `All >`; bottom button is new markup/code.

- **[DATA-STATE]** The four populated rows (Security scan completed, TruffleHog added, Workflow audit completed, Member invited) are real data - don't hardcode them; they appear once activity exists.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/dashboardData.ts`.
  - -> Component: `buildActivity()`, `ActivityRow`.
  - -> Data: current sources include honey key events, active cases, scan history, and project statuses. "Tool added" and "Member invited" event types are not present in the current summary schema.
  - -> Note: DATA-STATE is true for generic rows, but target-specific "Member invited" cannot appear without a team/user event source.

## L. Repository health overview - NEW (bottom)

- **[CODE]** Replace V1's bottom area (the "Open cases" segmented bar + legend, and "Repo comparison / No snapshots") with a **"Repository health overview"** row.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`, `dashboard-ui/src/dashboardData.ts`.
  - -> Component: current bottom pieces are `SeverityDistribution`, `FindingLine`, `RepositoryComparisonStrip`; new component recommended, e.g. `RepositoryHealthOverview`.
  - -> Data: use `targetRepos`, `summary.repos`, `activeCaseList(summary)`, `staleRepoCount(summary)` as a starting point.
  - -> Note: V1 bottom is not one single component. `RepositoryComparisonStrip` is only rendered in all-repos mode; the `Open cases` card is inside the bottom split grid for both modes.

- **[VISUAL]** Header gets a small **green underline accent**; "View all repositories >" link on the right.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: new `RepositoryHealthOverview`, probably uses/extends `SectionHeader`.
  - -> Data: no repository-list tab exists today. Link target needs a decision: Reports snapshot, Settings target list, or a new repositories view.

- **[SPLIT]** A horizontal row of status stats, each with a colored icon:
  - Total repositories: 18
  - Healthy: 17 (green check)
  - Needs attention: 1 (amber triangle)
  - Critical: 0 (red X)
  - No recent scan: 1 (gray clock)
  - Visual: the icons, colors, layout. Code: every count is real, computed from repo states.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/dashboardData.ts`.
  - -> Component: new helper/component recommended.
  - -> Data: total should likely be `targetRepos.length`; scanned health comes from `summary.repos`; issue counts come from `activeCaseList(summary)` grouped by repo; no-recent-scan should include both stale scanned repos and known target repos absent from `summary.repos`.
  - -> Note: do not hardcode counts. Existing `staleRepoCount(summary, maxAgeDays = 7)` only covers scanned repos with old/missing `last_scan`; it does not count discovered-but-never-scanned `targetRepos`.

- **[CODE]** Note: this introduces a **status taxonomy** - healthy / needs-attention / critical / no-recent-scan. See Flags.
  - -> Files: `dashboard-ui/src/dashboardData.ts`, `dashboard-ui/src/App.tsx`.
  - -> Component: new presentation helper recommended, not backend severity replacement.
  - -> Note: keep backend severity taxonomy intact; derive repo health buckets for Overview display.

## M. Global visual language (applies everywhere)

- **[VISUAL]** Primary color: muted sage -> **richer forest/emerald green**.
  - -> Files: `dashboard-ui/src/index.css`.
  - -> Component: root tokens `--mist-surface-*`, hero/workspace/catalog token consumers.
  - -> Note: the real token source is `index.css`; `colors_and_type.css` named in `DESIGN.md` is missing.

- **[VISUAL]** Accent strategy: V1 is near-monochrome; V2 uses **green accents + semantic amber/red/gray** for status.
  - -> Files: `dashboard-ui/src/index.css`, `dashboard-ui/src/App.tsx`, `dashboard-ui/src/uiTypes.ts`.
  - -> Component: `severityMeta`, `Tone`, severity/status classes.
  - -> Data: status colors map from `Tone` and data-derived status helpers.
  - -> Note: visual tokens plus some code mapping if new repo health statuses are introduced.

- **[VISUAL]** Icons everywhere: thin outline -> **filled/duotone**, frequently inside **soft circular containers**.
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`, catalog component CSS.
  - -> Component: `Sidebar`, `KpiCard`, `ActivityRow`, new quick actions, new health overview.
  - -> Note: visual but broad. Use containers/colors rather than pretending Lucide has filled versions everywhere.

- **[VISUAL]** Corner radius: tighter/sharper -> **softer, rounder** (cards, buttons, chips, avatar).
  - -> Files: `dashboard-ui/src/index.css`.
  - -> Component: root radii `--r-*`, `.button`, `.paper-card`, `.kpi-card`, `.toolbar-search`, nav rows.
  - -> Note: broad token pass. Existing `DESIGN.md` radii are much larger than current `index.css` tokens.

- **[VISUAL]** Elevation: V2 cards feel slightly more **lifted / soft-shadowed**.
  - -> Files: `dashboard-ui/src/index.css`.
  - -> Component: `--shadow-*`, `.paper-card`, `.kpi-card`, catalog cards.
  - -> Note: safe visual token pass if shadows stay subtle.

- **[VISUAL]** Typography: headings **bolder and a bit larger**; section labels move from **ALL-CAPS-with-middots -> sentence case**.
  - -> Files: `dashboard-ui/src/index.css`, `dashboard-ui/src/App.tsx`.
  - -> Component: `Eyebrow`, `SectionHeader`, `Toolbar`, hero copy.
  - -> Note: re-tag VISUAL -> SPLIT. `Eyebrow` and `SectionHeader` are app-wide; do not globally sentence-case every label without checking dense diagnostic pages.

- **[VISUAL]** Remove the black "Run quick" button treatment from V1 entirely (it belonged to the deleted Scan Control).
  - -> Files: `dashboard-ui/src/index.css`, `dashboard-ui/src/App.tsx`.
  - -> Component: `Button`, `.button.primary`, `ScanControlPanel`.
  - -> Note: only safe if `ScanControlPanel` is removed from Overview and primary scan action gets a new treatment in hero/quick actions.

## N. Voice / wording cluster (cross-cutting)

A deliberate jargon -> plain-language pass. Mostly **[VISUAL]** as string swaps, but worth doing as one coordinated edit:

- "manifests" -> "tools, repos"
  - -> Files: `dashboard-ui/src/App.tsx`.
  - -> Component: `Toolbar`.
  - -> Note: string edit in shared toolbar placeholder.

- "raw findings", "non-low" -> "critical", "high"
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/dashboardData.ts`, many non-Overview pages.
  - -> Component: Overview KPI detail, `SeverityDistribution`, Findings/Reports/Activity surfaces.
  - -> Note: re-tag VISUAL -> CODE/SPLIT. "Raw findings" is a real domain concept used across reports/MCP; only simplify where the Overview needs user-facing summary copy.

- "Honey keys armed" -> "Repos with issues"
  - -> Files: `dashboard-ui/src/App.tsx`.
  - -> Component: Overview KPI card 2.
  - -> Note: CODE, not wording. Data source changes.

- "raw signals", "Setup gaps", "Scanner inventory", "Daily driver", "fan-out limit" -> removed
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `ScanControlPanel`, `ScannerInventoryMini`, `RepoScanStrip`.
  - -> Note: remove from Overview, not necessarily from diagnostic/verification surfaces.

- Instruction headline -> status + encouragement ("You're in great shape." / "Everything looks healthy. Keep it up!")
  - -> Files: `dashboard-ui/src/App.tsx`.
  - -> Component: `OverviewView` headline/subtitle logic.
  - -> Note: CODE because copy is data-state-dependent.

- ALL-CAPS middot labels -> friendly sentence-case
  - -> Files: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`.
  - -> Component: `Eyebrow`, `SectionHeader`, individual strings.
  - -> Note: broad visual/content pass; scope carefully.

---

## Data-state caveat (read before building visual prompts)

These look like differences but are **just V1-empty vs V2-populated** unless noted:

- Recent activity rows: content should come from `buildActivity()`. Do not hardcode target rows.
- Repository health counts: numbers are data; component and computation are real work.
- 7-day chart bar values: do not copy mock values. Also fix current synthetic no-history fallback in `postureWeek()`.
- Hero date: already dynamic via `Intl.DateTimeFormat`; only style/format changes.

---

## Corrections to the original diff

- The live Overview is `OverviewView()` inside `dashboard-ui/src/App.tsx`; `dashboard-ui/src/components/OverviewView.tsx` is not imported by the app entry.
- The posture ring is not purely "empty despite 10.0"; `Donut` already binds stroke progress to `posture.score`. The real gap is no filled interior, no centered value/tier, and misleading synthetic chart values when history is empty.
- The three KPI cards are already clickable. The chevron is visual; only the second card's meaning/route clearly changes.
- Recent activity is not only a 24-hour axis today. The Overview already renders `ActivityRow`s when `buildActivity()` returns items; V2 removes the mini timeline and changes row layout.
- `Tool Catalog` showing `0 / 15` while the detail says `16 catalog entries` is a real binding mismatch between scanner inventory count and catalog item count.
- `colors_and_type.css` is referenced by `DESIGN.md` but not present. The active token definitions live in `dashboard-ui/src/index.css`.
- "Remove REPO/GLOBAL tags" is not a pure visual change; those tags are emitted by `navScopeLabel()`.
- `Goals`, `Alexandra`, `Admin`, profile/avatar data, team members, and invite-member events were not found in the codebase.

## Code-only differences the pixel diff missed

- `postureWeek()` fabricates a 7-day history when `summary.history` is empty. This can make an empty dashboard look healthier and more historically informed than it is.
- Several older component files duplicate surfaces now implemented inline in `App.tsx` (`dashboard-ui/src/components/OverviewView.tsx`, plus older Findings/ScanCompleteness paths). Use care when editing so the live screen changes.
- The top-level `Toolbar` is shared by every tab. Heading size, search styling, posture pill format, and scope selector changes ripple beyond Overview.
- `Eyebrow`, `SectionHeader`, `Button`, `PaperCard`, `ActivityRow`, `MetricBlock`, and token CSS are shared. Treat global typography/casing/radius changes as coordinated design-system work.
- Empty/loading/error states need explicit design: `/api/summary` load failure currently shows `Notice`; no-history and no-repos states must not show fake trend data or hardcoded healthy copy.
- Mobile breakpoint at `max-width: 720px` turns the sidebar into a horizontal top nav and hides `.sidebar-footer`. The new profile block and Settings placement need a mobile answer.
- User/team/profile concepts are absent. Adding "Invite members" and "Alexandra / Admin" requires a new product/data contract, not just a card.
- The removed Scan Control is not only markup. It is the visible home for live job progress, all-repo fan-out status, setup gaps, scanner inventory, and latest scan by repo.

## Open decisions, resolved against the code

### 1. Severity taxonomy

Current backend/domain severity is five-tier: `critical`, `high`, `medium`, `low`, `info` in `src/security_observatory/model.py` and `dashboard-ui/src/dashboardData.ts`.

The current Overview presentation collapses that visually into four buckets: `critical`, `elevated` (high), `warning` (medium), and `low` (low + info) through `severityCounts()`, `caseSeverityCounts()`, and `severityMeta` in `App.tsx`.

Recommendation: do not collapse the backend severity model. Keep five-tier domain severity for storage, cases, reports, MCP, and scanner normalization. Add Overview-specific presentation helpers:

- `critical/high` for the Open cases card.
- `healthy/needs-attention/critical/no-recent-scan` for repository health buckets.
- Keep `medium/low/info` available elsewhere for diagnostics and reports.

Touches: `src/security_observatory/model.py`, `src/security_observatory/normalize.py`, `src/security_observatory/cases.py`, `dashboard-ui/src/dashboardData.ts`, `dashboard-ui/src/App.tsx`, `dashboard-ui/src/uiTypes.ts`, and `dashboard-ui/src/index.css`.

### 2. Card #2's changed meaning

Current card 2 source:

- `honeyKeyCounts(summary).active` in `OverviewView()`.
- Detail from `honeyCounts.triggered ? "... tripped" : "all quiet"`.
- Click route: `onOpenTab('honey-keys')`.

Target card 2 source:

- Count repositories with active issues/cases, not honey keys.
- Recommended binding: group `activeCaseList(summary)` by repo, or derive from `summary.repos` where the repo has active cases / non-healthy status.
- Detail "1 needs attention" should be the same repo issue bucket count.
- Click route should likely open `findings` filtered/grouped by repo, or the new repository-health view if created.

Honey Keys should stay in `HoneyKeysView` and data structures, but they should not power "Repos with issues."

### 3. Scan Control's new home

The scan/run machinery already has a better underlying home than the visible Overview block:

- `RunCheckSheet` handles choosing audits/profiles, repo target, progress, completion, and "View cases."
- `runQuickCheck()`, `runFullCheck()`, `chooseChecks()`, `runAllRepoChecks()`, `startRepoCheck()`, and `pollRepoCheck()` own the client behavior.
- `/api/run-check` and `/api/check-status` in `dashboard_server.py` own execution/progress.
- `VerificationView` already shows detailed scanner inventory and setup gaps.
- Tool setup/integration flows live under Tool Catalog and setup-card endpoints/components.

Recommendation: remove `ScanControlPanel` from Overview, but keep:

- Hero "Run a scan" -> `onRunQuick()`.
- Quick action "Run a scan" -> `onRunQuick()` or `chooseChecks()` depending on product preference.
- Quick action "Setup integrations" -> Tool Catalog browse/setup path, not a fake page.
- Verification remains the detailed scanner inventory/diagnostic home.
- Preserve all-repo fan-out progress in `RunCheckSheet` or a compact running-job banner if a run is active.

## Sharpened split

### Safe for a fast visual-only AI

- Sidebar visual treatment: icon containers, selected green highlight, spacing, radius, softer workspace mark styling.
- Workspace/logo visual if the "A" is accepted as a static mark.
- Hero background richness, bar contrast, rounded bars, card shadows/radii, and soft icon circles when scoped to existing markup.
- KPI card visual shell: leading circular icons, chevron affordance, spacing, shadows.
- Search field visual treatment.
- Quick-action card static shell only, with placeholder buttons left for engineering wiring.
- Repository health overview static shell only, with no hardcoded counts.
- Token-level color/radius/shadow pass in `dashboard-ui/src/index.css`, with engineering review because tokens ripple app-wide.

### Must go to engineering

- Nav restructure: `Goals` tab/view, moving Activity, hiding Cases/Honey Keys while preserving routes, section header changes.
- Removing REPO/GLOBAL pills because they are emitted by `navScopeLabel()`.
- Toolbar scope dropdown and target selector wiring.
- User profile block because no user/profile/team data model exists.
- Hero headline/subtitle because copy must follow real posture/cases/scan state.
- Hero "Run a scan" behavior and quick-action behavior.
- Gauge tier label, shield badge, and no-history chart behavior.
- Card 1 severity sublabel, Card 2 "Repos with issues", Card 3 coverage denominator.
- Removing/re-homing Scan Control without losing run progress, choose-checks, all-repo fan-out, scanner inventory, and setup gaps.
- Recent activity layout if changing shared `ActivityRow`.
- Repository health status computation, including no-recent-scan for discovered but unscanned repos.
- Severity/repo-health taxonomy helpers.
- Any global wording changes involving "raw findings" because that is a real internal/reporting concept, not just UI jargon.
