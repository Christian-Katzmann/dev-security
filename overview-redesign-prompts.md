# Overview Redesign - Prompt Pack

Use these prompts in order. The GPT-5.5 prompts are larger because they need data/routing judgment.

Reference docs:

- `overview-redesign-diff-grounded.md`
- `overview-redesign-model-split.md`
- `DESIGN.md`

Repo:

- `/Users/christiankatzmann/Dev/Projects/dëv-security`

Verification for implementation prompts:

- `cd dashboard-ui && npm run lint`
- If lint passes: `cd dashboard-ui && npm run build`

---

## GPT-5.5 Prompt 1 - Data Semantics + Honest Hero

```text
You are working in /Users/christiankatzmann/Dev/Projects/dëv-security.

You are a senior frontend engineer. Implement the data-correct parts of the Overview redesign. This is not a mockup-copy task: all values must bind to real state.

Read first:
- AGENTS.md / project instructions already loaded in the repo context
- DESIGN.md
- overview-redesign-diff-grounded.md
- overview-redesign-model-split.md

Primary files:
- dashboard-ui/src/App.tsx
- dashboard-ui/src/dashboardData.ts
- dashboard-ui/src/index.css
- dashboard-ui/src/uiTypes.ts only if needed

Tasks:
1. Fix the three Overview KPI cards semantically:
   - Open cases value remains active open cases.
   - Open cases detail should use active case severity counts: critical and high.
   - KPI card labels should land on the target sentence-case wording: "Open cases", "Repos with issues", and "Tool coverage".
   - KPI sublabels should use semantic color based on real state, scoped to KPI cards rather than changing every Eyebrow globally.
   - KPI icons should match the target meaning as closely as possible: folder/open cases, shield/repos with issues, clipboard/tool coverage.
   - Card 2 becomes "Repos with issues", sourced from repo issue state, not Honey Keys.
   - Card 2 detail should reflect repos needing attention.
   - Card 2 should route to a relevant real destination, likely Cases/findings unless you create a better existing-target path.
   - Tool coverage should use a consistent denominator/source. Do not hide the current scanner-count vs catalog-count mismatch with copy.

2. Add Overview-only repo health/status helper logic:
   - Keep backend/domain severity taxonomy as critical/high/medium/low/info.
   - Do not collapse or rename stored severities.
   - Derive simpler Overview presentation buckets only where needed.

3. Implement the honest target-style hero:
   - Headline/subtitle should be conditional on real state: healthy, issues, no scans, stale/pre-case, etc.
   - Do not hardcode "You're in great shape." for every state.
   - Date label should be clean sentence case and still dynamic. Do not hardcode the screenshot date.
   - Primary hero action becomes "Run a scan" and uses the existing scan flow.
   - Secondary action routes to Activity.
   - Add a filled posture gauge with centered score, /10, a data-derived tier label, and a small badge.
   - Rename the 7-day chart label toward "Posture over the last 7 days" while keeping values real.
   - Fix no-history behavior so the 7-day chart does not fabricate a meaningful trend when summary.history is empty.

4. Update the shared top posture pill carefully:
   - Format should move from "POSTURE 10.0 +0.0" toward "POSTURE: 10.0 / 10".
   - Score must remain posture.score.
   - Do not hardcode 10.0.
   - Remove/hide the delta only as a deliberate UI choice, and verify this shared toolbar still works on other tabs.

Guardrails:
- Do not remove ScanControlPanel in this prompt.
- Do not add user profile, Goals, or Invite members.
- Do not hardcode target screenshot numbers like 10.0, 18, 17, 1, or 15.
- Preserve existing scan APIs and behavior.
- Work with the current dirty tree; do not revert unrelated changes.

Verification:
- Run cd dashboard-ui && npm run lint
- If lint passes, run cd dashboard-ui && npm run build
- Report changed files, what data each card binds to, and any verification failures.
```

---

## GPT-5.5 Prompt 2 - Remove Scan Control + Add Quick Actions + Recent Activity

```text
You are working in /Users/christiankatzmann/Dev/Projects/dëv-security.

You are a senior frontend engineer. Continue the Overview redesign by replacing the dense Scan Control area with guided actions, while preserving all scan functionality.

Read first:
- DESIGN.md
- overview-redesign-diff-grounded.md sections J and K
- overview-redesign-model-split.md

Primary files:
- dashboard-ui/src/App.tsx
- dashboard-ui/src/index.css
- src/security_observatory/dashboard_server.py only if truly necessary

Tasks:
1. Remove ScanControlPanel from the Overview page only.
   - Do not delete scan machinery just because the panel disappears.
   - Preserve RunCheckSheet.
   - Preserve run quick, choose checks, run all repos, all-repo fan-out, active job progress, run errors, and completion flow.
   - Keep scanner inventory/setup gaps reachable through VerificationView and/or Tool Catalog.
   - If a scan is actively running, provide a compact Overview-safe status surface or keep the existing sheet/progress path visible enough.

2. Add a real "What would you like to do?" quick-action panel:
   - Run a scan -> existing scan flow.
   - View catalog -> Tool Catalog tab / catalog route.
   - View activity -> Activity tab.
   - View reports -> Reports tab.
   - Setup integrations -> real Tool Catalog/setup destination or the closest existing setup-capable path.
   - Invite members -> do not fake unsupported team behavior. Either omit, disable with honest copy, or mark as unavailable in a way consistent with the product.

3. Redesign the Overview recent activity panel:
   - Remove the 24-hour mini timeline from Overview.
   - Use real buildActivity() rows.
   - Add top "View all" link and bottom "View all activity" button.
   - Do not hardcode target rows like "Member invited".
   - If changing ActivityRow, account for its use in ActivityView.

Guardrails:
- Do not hardcode any target numbers or activity rows.
- Do not change backend scan behavior unless absolutely necessary.
- Do not remove VerificationView scanner diagnostics.
- Work with the current dirty tree; do not revert unrelated changes.

Verification:
- Run cd dashboard-ui && npm run lint
- If lint passes, run cd dashboard-ui && npm run build
- Report changed files, where scan controls now live, and any verification failures.
```

---

## GPT-5.5 Prompt 3 - Repository Health Overview + Bottom Layout

```text
You are working in /Users/christiankatzmann/Dev/Projects/dëv-security.

You are a senior frontend engineer. Implement the target "Repository health overview" as a real data-driven component and clean up the old bottom Overview layout.

Read first:
- DESIGN.md
- overview-redesign-diff-grounded.md section L
- overview-redesign-model-split.md

Primary files:
- dashboard-ui/src/App.tsx
- dashboard-ui/src/dashboardData.ts
- dashboard-ui/src/index.css

Tasks:
1. Replace the old bottom Overview areas with a Repository health overview:
   - Remove/replace the old Open cases segmented bar/card from the Overview bottom.
   - Replace the all-repos Repo comparison strip with the new health row.
   - Keep cases accessible elsewhere through the Cases/findings route/card.

2. Compute real counts:
   - Total repositories.
   - Healthy.
   - Needs attention.
   - Critical.
   - No recent scan.
   - Include discovered but never-scanned repos in "No recent scan".

3. Make status logic explicit and local to Overview presentation:
   - Do not change backend severity taxonomy.
   - Do not store the new buckets as backend severity.
   - Use targetRepos, summary.repos, active cases, scan recency, and target mode.

4. Add the visual treatment:
   - Header "Repository health overview".
   - Small green underline accent.
   - Colored icons for each bucket.
   - "View all repositories" link only if it points to a real existing destination; otherwise use honest disabled/omitted behavior.

Guardrails:
- No mock counts.
- No hardcoded "18", "17", "1", or "0".
- Do not break single-repo mode.
- Work with the current dirty tree; do not revert unrelated changes.

Verification:
- Run cd dashboard-ui && npm run lint
- If lint passes, run cd dashboard-ui && npm run build
- Report changed files, count formulas, and any verification failures.
```

---

## GPT-5.5 Prompt 4 - Navigation, Profile, and Product Contracts

```text
You are working in /Users/christiankatzmann/Dev/Projects/dëv-security.

You are a senior frontend/product engineer. Handle the structural parts of the Overview redesign that touch nav, unavailable concepts, and responsive shell behavior.

Read first:
- DESIGN.md
- overview-redesign-diff-grounded.md sections B, D, and E
- overview-redesign-model-split.md

Primary files:
- dashboard-ui/src/App.tsx
- dashboard-ui/src/index.css
- dashboard-ui/src/dashboardData.ts only if needed
- Backend/profile config files only if you intentionally introduce a real local profile source

Tasks:
1. Sidebar nav:
   - Move Activity into the first group if appropriate.
   - Remove or hide REPO/GLOBAL nav tags by changing rendering, not CSS-only.
   - Rename Records to Reports, with Reports as the only item in that section.
   - Decide how Cases and Honey Keys remain reachable if removed from sidebar. Do not delete their views.
   - Decide whether Goals is a real new view. If not supported, do not fake it as a working feature.

2. Workspace switcher:
   - Update the sidebar workspace subtitle so all-repos mode can show a real repository count, e.g. "18 repositories", sourced from existing repo data.
   - Do not hardcode the target screenshot count.
   - Decide whether this count means selectable repositories (targetRepos.length) or scanned repositories (summary.repos.length), and document the choice.
   - Keep the existing target selector behavior working.

3. Toolbar scope selector:
   - Turn the passive target label into a real scope selector only if it can reuse existing target selection behavior safely.
   - Avoid duplicating target-selection logic if a shared component is cleaner.

4. Profile block:
   - Do not hardcode "Alexandra / Admin".
   - If no real user/profile/team model exists, either defer the profile block or introduce a small explicit local profile contract.
   - Define dropdown behavior honestly; no fake account/team actions.

5. Responsive behavior:
   - Check mobile under 720px, where sidebar becomes horizontal and sidebar footer is hidden.
   - Ensure Settings/profile/nav still have a coherent mobile placement.

Guardrails:
- Do not remove routes/views just because nav changes.
- Do not fake team/member/invite behavior.
- Do not change scan/data semantics in this prompt.
- Work with the current dirty tree; do not revert unrelated changes.

Verification:
- Run cd dashboard-ui && npm run lint
- If lint passes, run cd dashboard-ui && npm run build
- Inspect desktop and mobile layout.
- Report changed files, product decisions made/deferred, and any verification failures.
```

---

## Optional GPT-5.5 Final Integration Prompt

Use this only after the Spark and GPT implementation prompts above have run.

```text
You are working in /Users/christiankatzmann/Dev/Projects/dëv-security.

You are a senior frontend reviewer doing a final integration pass on the Overview redesign.

Read first:
- DESIGN.md
- overview-redesign-diff-grounded.md
- overview-redesign-model-split.md

Review the current implementation against the target redesign and the grounded diff.

Do:
- Fix inconsistencies introduced by earlier passes.
- Verify every visible Overview number binds to real data.
- Verify empty, populated, single-repo, all-repos, loading/error, and running-scan states.
- Verify mobile and desktop layout.
- Remove dead Overview-only CSS/markup left behind by removed ScanControlPanel if safe.
- Keep shared component changes intentional and documented.

Do not:
- Do not invent user/team/profile data.
- Do not hardcode screenshot values.
- Do not collapse backend severity taxonomy.
- Do not delete scan functionality.
- Do not revert unrelated dirty worktree changes.

Verification:
- Run cd dashboard-ui && npm run lint
- Run cd dashboard-ui && npm run build
- Provide a concise final report: what changed, what remains deferred, and any risks.
```
