# Overview Redesign - Model Split

Source of truth: `overview-redesign-diff-grounded.md`

This splits the Overview redesign into work suitable for a fast, less sophisticated visual model (`Codex-5.3-spark`) versus work that needs a stronger engineering model (`GPT-5.5`). The split is intentionally conservative: Spark should only touch things that cannot accidentally change security meaning, routing, or data binding.

---

## Routing Rule

Use **Codex-5.3-spark** for isolated visual polish where:

- The data source stays exactly the same.
- Existing click handlers and routes stay exactly the same.
- It mostly edits `dashboard-ui/src/index.css`.
- Any `dashboard-ui/src/App.tsx` edit is limited to static icon/label/class markup with no new state, no new helpers, and no changed data meaning.

Use **GPT-5.5** for anything involving:

- Counts, severity, posture, repo health, or scanner/tool coverage.
- Routing, nav membership, tabs, selectors, or click behavior.
- Removing/re-homing Scan Control.
- Empty/loading/error states.
- Shared components whose changes affect multiple pages.
- Missing product concepts like `Goals`, user profile, team members, or invite flows.

---

## Codex-5.3-spark Track

These are small visual passes. Keep them separate; Spark should not do all of them in one giant patch.

### Spark Pass 1 - Sidebar Visual Polish

Scope:

- Style the existing sidebar toward the target: softer selected state, green-tinted active row, slightly warmer spacing/radius.
- Restyle the existing workspace mark visually.
- Optionally replace the shield icon with a static `A` monogram only if treated as a static brand mark.

Files:

- `dashboard-ui/src/index.css`
- `dashboard-ui/src/App.tsx` only if swapping the static workspace icon/letter

Do not:

- Change `navGroups`, `viewsByMode`, `TabId`, `navScopeLabel()`, or routing.
- Add `Goals`.
- Remove `Cases` or `Honey keys`.
- Add the user profile block.

### Spark Pass 2 - Search and Top-Bar Visual Polish

Scope:

- Make the existing search field more prominent, rounder, and closer to the target.
- Improve the `⌘K` chip styling.
- Make the posture status dot visually clearer.
- Lightly adjust toolbar spacing and title size if it does not break other tabs.

Files:

- `dashboard-ui/src/index.css`

Allowed small copy-only edit:

- In `Toolbar`, change the default placeholder from `Search cases, manifests` to `Search cases, tools, repos...`.

Do not:

- Turn the scope label into a dropdown.
- Change posture pill data or remove `posture.delta`.
- Add new toolbar state.

### Spark Pass 3 - Hero Visual Repaint

Scope:

- Richer forest/emerald hero background.
- Better hero contrast.
- Improve 7-day bar readability and rounded bar tops.
- Keep the current hero layout and data binding.

Files:

- `dashboard-ui/src/index.css`

Do not:

- Change hero headline logic.
- Add the healthy subtitle.
- Change "Open cases" to "Run a scan."
- Change `postureWeek()`.
- Rewrite `Donut()`.

### Spark Pass 4 - KPI Card Chrome

Scope:

- Add soft circular icon treatment to the existing KPI cards.
- Add a visual chevron affordance.
- Improve card radius/shadow/spacing.
- Keep current labels, values, details, and click handlers.

Files:

- `dashboard-ui/src/index.css`
- `dashboard-ui/src/App.tsx` only for adding a static chevron/icon wrapper inside `KpiCard`

Do not:

- Rename `Honey keys armed` to `Repos with issues`.
- Change card values/details.
- Change card routes.
- Change `KpiCard` in a way that assumes new data.

### Spark Pass 5 - Safe Copy Nits

Scope:

- `Recovery playbooks` -> `Recovery Playbooks`.
- Search placeholder jargon removal as listed above.
- Very local label polish where no data meaning changes.

Files:

- `dashboard-ui/src/App.tsx`

Do not:

- Replace `raw findings` globally.
- Replace `non-low` globally.
- Change `Honey keys armed`.
- Change severity labels.

### Spark Verification

After each pass:

- Run `cd dashboard-ui && npm run lint`.
- Run `cd dashboard-ui && npm run build` only if lint passes.
- Visually inspect Overview at desktop and mobile widths.

---

## GPT-5.5 Track

These tasks need stronger reasoning because they touch data semantics, state, routing, or product contracts.

### GPT-5.5 Task 1 - Overview Data Semantics

Implement the real data bindings behind the target summary:

- Open cases card should show open cases and `critical/high` counts from active cases.
- Card 2 becomes `Repos with issues`, sourced from repo issue state, not Honey Keys.
- Tool coverage denominator/source must be made consistent.
- Add helper(s) for Overview-only repo health buckets.

Files:

- `dashboard-ui/src/App.tsx`
- `dashboard-ui/src/dashboardData.ts`
- Possibly `dashboard-ui/src/uiTypes.ts`

Key guardrail:

- Do not collapse backend severity taxonomy. Keep `critical/high/medium/low/info`; derive simpler Overview presentation buckets.

### GPT-5.5 Task 2 - Honest Posture Hero

Implement the target hero behavior:

- Healthy/attention/empty-state headline and subtitle logic.
- `Run a scan` primary action wired to existing scan flow.
- Filled posture gauge with centered score, `/10`, tier label, and badge.
- Fix no-history behavior so the 7-day chart does not fabricate a meaningful trend.

Files:

- `dashboard-ui/src/App.tsx`
- `dashboard-ui/src/index.css`

Key guardrail:

- No hardcoded `10.0`, `Excellent`, or healthy copy for all states.

### GPT-5.5 Task 3 - Scan Control Re-home

Remove the dense `ScanControlPanel` from Overview without losing behavior:

- Preserve `RunCheckSheet`.
- Preserve quick scan, choose checks, all-repo fan-out, live progress, errors, and completion path.
- Keep scanner inventory/setup gaps reachable in `VerificationView` and/or Tool Catalog.
- Consider a compact active-run banner if a scan is currently running.

Files:

- `dashboard-ui/src/App.tsx`
- `dashboard-ui/src/index.css`
- `src/security_observatory/dashboard_server.py` only if API behavior truly needs adjustment

Key guardrail:

- Deleting the Overview panel must not delete the scan machinery.

### GPT-5.5 Task 4 - Quick Actions

Add the real "What would you like to do?" launcher:

- Run a scan -> existing scan flow.
- View catalog -> Tool Catalog tab/catalog route.
- View activity -> Activity tab.
- View reports -> Reports tab.
- Setup integrations -> real Tool Catalog/setup destination, not fake copy.
- Invite members -> decide/defer because no user/team model exists.

Files:

- `dashboard-ui/src/App.tsx`
- `dashboard-ui/src/index.css`

Key guardrail:

- Do not hardcode unsupported team/member behavior.

### GPT-5.5 Task 5 - Repository Health Overview

Replace bottom Overview areas with a real data-driven health row:

- Total repositories.
- Healthy.
- Needs attention.
- Critical.
- No recent scan.
- Include discovered but never-scanned repos in `No recent scan`.

Files:

- `dashboard-ui/src/App.tsx`
- `dashboard-ui/src/dashboardData.ts`
- `dashboard-ui/src/index.css`

Key guardrail:

- Counts must bind to `targetRepos`, `summary.repos`, active cases, scan recency, and target mode. No mock numbers.

### GPT-5.5 Task 6 - Recent Activity Redesign

Replace the mini timeline with a list-first activity panel:

- Remove `ActivityTimelineMini` from Overview.
- Use real `buildActivity()` output.
- Add top "View all" link and bottom "View all activity" button.
- If changing `ActivityRow`, account for its use in `ActivityView`.

Files:

- `dashboard-ui/src/App.tsx`
- `dashboard-ui/src/index.css`

Key guardrail:

- Do not hardcode the target rows. Current data does not support `Member invited`.

### GPT-5.5 Task 7 - Nav, Profile, and Product Contracts

Handle structural/product pieces:

- Decide what `Goals` is and implement/defer accordingly.
- Move `Activity` up while preserving access to Cases and Honey Keys through cards/deep links if removed from nav.
- Remove `REPO`/`GLOBAL` tags by changing `navScopeLabel()` rendering.
- Add profile block only after deciding a real local profile/user source.
- Solve mobile behavior because `.sidebar-footer` is hidden under 720px.

Files:

- `dashboard-ui/src/App.tsx`
- `dashboard-ui/src/index.css`
- Possibly backend/profile config files if a profile source is introduced

Key guardrail:

- Do not hardcode `Alexandra / Admin` as live product data.

### GPT-5.5 Verification

Run:

- `cd dashboard-ui && npm run lint`
- `cd dashboard-ui && npm run build`

Also manually verify:

- Empty no-scan state.
- Populated all-repos state.
- Single repo state.
- Running scan state.
- `/api/summary` failure state.
- Desktop and mobile layouts.

---

## Recommended Order

1. Spark Passes 1-4 for low-risk visual movement.
2. GPT-5.5 Task 1 to settle data meanings before changing copy.
3. GPT-5.5 Task 2 for the hero and posture honesty.
4. GPT-5.5 Task 3 to remove/re-home Scan Control.
5. GPT-5.5 Tasks 4-6 for quick actions, health overview, and activity.
6. GPT-5.5 Task 7 last, because `Goals`, profile, and teams are product decisions hiding inside pixels.

This order avoids the most dangerous failure mode: making the page look like the target while quietly lying about counts, scan state, or repository health.
