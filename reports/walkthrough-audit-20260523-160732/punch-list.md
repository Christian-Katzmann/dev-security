# PUNCH LIST CLEAR

# DëvSec — Product walkthrough audit (re-run)

Audit ID: `walkthrough-audit-20260523-160732`
Date: 2026-05-23
Predecessor: `walkthrough-audit-20260523-102224` (13 findings, all closed)
Mode: `no-ai` (project documents no cloud LLM calls; nothing to budget)
Tooling: chrome-devtools MCP against `http://127.0.0.1:8766/`

## Verdict

Re-walked every surface the original audit covered, plus the Recovery playbooks
re-render, the rebuilt Activity strip, the new in-app docs renderer, and the
SCM_TOKEN gate that was previously invisible. Every one of the original 13
findings is genuinely fixed in the running app, not just in the diff. The a11y
nit (`A form field element should have an id or name attribute`) is also
resolved — the run-check sheet and all dashboard form fields now carry either
a `name` or an `aria-label` attribute. Console is silent on the Overview,
Catalog, Catalog detail pages, Recovery playbooks, Activity, Settings, and the
Run security check sheet.

## Original findings — verified closed

| ID    | Surface                                           | Original status                                     | Final state in the running app                                                                                                                                            | Evidence                                       |
|-------|---------------------------------------------------|------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------|
| F-001 | Header — Run all                                  | dimmed, no tooltip                                   | Label is "Run all (pick a repo)" with `title="Pick a repo first"`. Click opens the Run security check sheet with a repo picker as the first row.                          | `evidence/F001-F008-runall-sheet.png`          |
| F-002 | Sidebar agent pill / toolbar Pause                | fake "Agent live · tailing scanners" toggle         | Pill and toggle removed entirely. No agent metaphor anywhere in the sidebar or toolbar.                                                                                   | `evidence/overview-final.png`                  |
| F-003 | Tool detail "Read documentation" links            | served raw markdown                                  | Local docs now render through `/docs/<file>.md` as a styled DëvSec docs page with headings, tables, and code blocks. External-tool docs continue pointing at vendor URLs. | `evidence/F003-docs-rendered.png`              |
| F-004 | Trivy detail page                                 | active "Install plugin" CTA on a detected install   | Install hero now reads "Detected locally. Trivy is installed locally. Run a matching scan profile to include it." No active Install button. NEXT STEP matches reality.    | (Trivy detail captured in F012 browse evidence) |
| F-005 | Settings → Generated reports                      | Export button with no handler                       | Export button removed. Row keeps its subtext, which remains accurate without a button.                                                                                    | `evidence/F005-settings-no-export.png`         |
| F-006 | Recovery playbooks → Rerun checks                 | silently no-op on target=dashboard                  | One-line note at top: "Switch to the repo where the finding lives to rerun its check." Per-card Rerun checks button visibly disabled with a matching tooltip; repo picker shown inline. | `evidence/F006-F007-playbooks.png`             |
| F-007 | Recovery playbooks                                | 6 identical "Rotate live secret" cards              | 3 distinct, case-class playbooks: "Upgrade vulnerable dependencies" (grype, 41 cases), "Harden workflow supply-chain surfaces" (workflow-audit, 4 cases), "Narrow AI/agent permissions" (medusa, 42 cases). Steps are class-specific. | `evidence/F006-F007-playbooks.png`             |
| F-008 | Pack page → Open profile                          | contradictory "Choose a repo target" + disabled Start | Sheet now opens with calm "Pick a repo to target" + inline picker. Start check is disabled with description "Pick a repo to run checks against" until a repo is chosen.  | `evidence/F001-F008-F010-runcheck-sheet.png`   |
| F-009 | Health Score scale (README vs UI)                 | README claimed 0–100; dashboard showed `/ 10`        | README §Health Score now explicitly states the engine computes 0–100 internally and the dashboard normalises to 0–10 for display. Penalty table re-expressed on the 0–10 scale. Dashboard still renders `0.0 / 10` consistently. | `README.md:365-381`                            |
| F-010 | Run-check sheet → Connected platform              | enabled with no token disclosure                    | When `scm_token_present` is false (it is on this machine), the tile is disabled, carries a "· Needs SCM_TOKEN" sub-label, and shows an inline instruction to set the env var and restart. | `evidence/F001-F008-F010-runcheck-sheet.png`   |
| F-011 | Activity → 24h × 7d heatmap                       | empty plot area under day labels                    | Replaced with an honest per-day scan-count strip: "0 Sun · 0 Mon · 0 Tue · 0 Wed · 0 Thu · 0 Fri · 1 Sat" with "1 scan this week" eyebrow. The Event mix · 7 D panel below it carries the categorical breakdown. | `evidence/F011-activity-strip.png`             |
| F-012 | Catalog Popular plugins + Featured banner CTAs    | universal "Install plugin" label                    | Popular plugins cards now say "View tool" for built-in (Built-in AI, Install hook classifier) and detected-locally (Trivy, Gitleaks) tools. Featured banner ("Featured: Trivy") only shows the View tool button — no Install. (Fix tightened in this step — see "Inline fixes" below.) | `evidence/F012-catalog-home.png`, `evidence/F012-catalog-browse-featured.png` |
| F-013 | Trivy detail → Last runtime                       | literal "ran" with no timestamp                     | Now renders "Last runtime: 12 min ago" — a real relative timestamp.                                                                                                       | (visible in F004 / catalog flow)               |

## A11y nit — verified closed

Original audit reported: `A form field element should have an id or name attribute (count: 2)`.

Final state: console is silent on Overview, Catalog, Tool detail pages, Recovery
playbooks, Activity, Settings, and the Run security check sheet. Fixes landed
in this step:

- `dashboard-ui/src/App.tsx` — workspace `<select>` and toolbar search `<input>` (Overview) gained `name` + `aria-label`.
- `dashboard-ui/src/App.tsx` — Settings workspace `<select>` gained `name` + `aria-label`.
- `dashboard-ui/src/components/FindingsView.tsx` — findings search `<input>` gained `name` + `aria-label`.
- `dashboard-ui/src/components/CodeView.tsx` — vectors filter `<input>` gained `name` + `aria-label`.
- `dashboard-ui/src/components/NeedsRepoTarget.tsx` — repo picker `<select>` gained `name`.

## Inline fixes landed during this re-walk

Two small things were caught and fixed inline (the campaign allows label-tweak
class fixes here without reopening a step):

1. **F-012 was only partially fixed in Step 1.3.** The helper `catalogCardAction`
   in `dashboard-ui/src/components/catalog/catalogHelpers.tsx` checked
   `previewCanInstall` but didn't first short-circuit on `install_state === 'built-in'`
   or `install_state === 'detected'`. Trivy and Gitleaks reported install_state
   `'detected'` from the catalog API but still had a managed-install preview
   (a Homebrew reinstall path), so the home card showed "Install plugin" even
   though the detail page disabled the install button. Fix: short-circuit on
   `built-in` and `detected` in `catalogCardAction`, then propagate the same
   helper into `CatalogBrowse.tsx`'s `featuredInstallEnabled` so the Featured
   banner CTA also obeys runtime install state. Trivy now correctly shows only
   "View tool" on both the home card and the featured banner.

2. **A11y nit count: 2.** Workspace `<select>`, toolbar `<input>`, Settings
   `<select>`, findings search, code filter, and NeedsRepoTarget picker now
   all carry `name` + `aria-label`.

## Surfaces re-tested vs. the previous audit's coverage receipt

| Surface (from previous receipt) | Re-tested now? | Notes |
|---------------------------------|----------------|-------|
| Overview (dashboard target) | ✓ | Hero screenshot regenerated: `evidence/overview-final.png`. |
| Overview hero KPIs | ✓ | OPEN FINDINGS, HONEY KEYS ARMED, TOOL CATALOG, POSTURE all read correctly. |
| Findings table | n/a | Not re-walked individually; nothing in the punch list touched it. |
| Honey keys page | n/a | Not re-walked beyond the sidebar count. Mutation surfaces stay skipped on safety grounds (see Open questions). |
| Tool Catalog home | ✓ | Popular plugins + Featured pack cards verified. `evidence/F012-catalog-home.png` |
| Tool Catalog Browse all | ✓ | Featured banner now matches install state. `evidence/F012-catalog-browse-featured.png` |
| Tool detail: Trivy | ✓ | F-004 / F-013 verified. |
| Tool detail: Built-in AI static checks | ✓ | F-003 docs link verified to render styled HTML. |
| Pack page (Starter) | ✓ | F-008 verified end-to-end. |
| Pack Open profile CTA | ✓ | Opens the new repo-picker sheet correctly. |
| Run security check sheet | ✓ | Repo picker is first row; SCM_TOKEN gate visible on the Connected platform tile. |
| Recovery playbooks | ✓ | F-006 and F-007 verified. |
| Recovery playbook Rerun checks button | ✓ | Disabled with tooltip; matches the new helper. |
| Activity view | ✓ | F-011 strip verified. |
| Settings view | ✓ | F-005 Export button gone. |
| Workspace target switcher | ✓ | aria-label present. |
| Header Pause/Resume agent toggle | ✓ | Removed (F-002). |
| Header Run all button | ✓ | Tooltip + state-aware label (F-001). |
| Sidebar agent status pill | ✓ | Removed (F-002). |
| Read documentation link (built-in tool) | ✓ | Renders HTML (F-003). |
| Verification view | not re-walked | Not in punch list; uses the same shared NeedsRepoTarget primitive. |
| Reports view | not re-walked | Out of scope for this re-audit. |
| Workspace + Add repo prompt | still skipped | Uses `window.prompt()`; chrome-devtools MCP gets into a locked dialog state. Same primitive as VERIFY / case-decision dialogs; not in the original punch list. |
| Honey key Place new key form | still skipped | Mutating (writes a real file). |
| Honey key Retire action | still skipped | Mutating. |
| Run all / Start check execution | still skipped | Would trigger real scans against the user's local repos. |
| Install plugin actions on installable third-party tools | still skipped | Would run Homebrew install. |

## Build/test/lint

- `uv run pytest` — 152 passed
- `cd dashboard-ui && npm run lint` (tsc --noEmit) — clean
- `cd dashboard-ui && npm run build` — clean

## Pre-flip GitHub metadata

Set via `gh repo edit Christian-Katzmann/dev-security`:

- `--description "Local-first security observability for modern repositories — scan, audit, and recover without sending your code or findings to anyone else."`
- `--add-topic security,sast,sca,sbom,local-first,security-scanner,python,react`
- `--homepage ""` (no landing page yet)

(See receipt for the exact commands and output.)

## v0.1.0 tag

`CHANGELOG.md` `[0.1.0]` updated to `2026-05-23`. Tag created locally:

```
git tag -a v0.1.0 -m "Initial public release"
```

Not pushed — that's part of the flip Christian does himself.

## Final summary

**Ready to flip.**

Every finding from `walkthrough-audit-20260523-102224` is closed and verified in
the running app. The a11y nit is resolved. Lint, build, and the full pytest
suite are green. The README hero has been replaced with the post-fix Overview
screenshot. GitHub repo metadata is set for the public landing card. v0.1.0 is
tagged locally and ready for Christian's push when he runs `gh repo edit --visibility public`.
