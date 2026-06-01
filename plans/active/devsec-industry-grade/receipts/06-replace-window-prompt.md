# Implementation Receipt: 06-replace-window-prompt

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 06-replace-window-prompt
- Source report item(s): S-033 (first-run add-repo gateway), S-034 (core-loop note/close dialogs) — lens report 11-behavioral-ux-health.initial.md rows 1–2

## Before Health

Four live `window.prompt` native OS dialogs remained in the mounted dashboard (line numbers as found this session, post-earlier-batches):

- `dashboard-ui/src/App.tsx:1050` — add-repo: `window.prompt('Paste the full path to the repo folder.')`, fired from a hidden `<option value="add-repo">` in the sidebar/toolbar/settings selects, the QuickActions tile, and `NeedsRepoTarget`. Empty input silently `return`ed; only normalization was `.trim().replace(/\/+$/,'')`.
- `dashboard-ui/src/App.tsx:2667` — Honey-key incident-close accepted-risk note prompt.
- `dashboard-ui/src/App.tsx:3445` — case decision optional-note prompt.
- `dashboard-ui/src/components/HoneyKeysView.tsx:157` — incident-close note prompt (in the **orphaned/dead** off-Mistglass twin, imported by nothing; acceptance still requires its prompt removed).

`dashboard-ui/src/components/CaseCard.tsx:81` is the dead twin left for batch 09 — **not touched** here (per Non-Goals).

## Changes Made

**S-033 — crafted in-app add-repo form (replaces the native prompt):**
- New `AddRepoDialog` component in `App.tsx`: a Mistglass paper modal (`role="dialog" aria-modal`) with one path input (mono, example placeholder `/Users/you/code/your-project`), inline validation, quick-pick suggestions from `/api/projects`, autofocus, Escape-to-close, backdrop-click-to-close, and one primary action.
- Inline validation eliminates the silent-empty `return`: empty submit → "Enter the full path to the repo folder."; non-absolute path → "Paste a full folder path, starting with “/” …". The form never closes or no-ops on a bad/empty submit (`aria-invalid` + `role="alert"` live region).
- `selectTarget('add-repo')` now opens the dialog instead of prompting; registration logic extracted to `addCustomRepo(path)` (same merge/persist/setTarget behavior as before).
- Retired the option-as-action smell: removed `<option value="add-repo">` from the sidebar, toolbar, and settings selects and from `NeedsRepoTarget`; replaced each with a visible "Add repository"/"Add repo" button that routes through `onTargetChange('add-repo')`. All four entry points now lead to the form; no select option secretly fires an action.

**S-034 — inline note capture (replaces the two live note prompts):**
- Case decision note (`CaseDetailCard`): added a persistent optional `.decision-note` textarea above the decision grid, seeded from the existing decision note. `save()` reads `noteDraft.trim()` instead of prompting. One-click decisions preserved — clicking a decision saves immediately with whatever (possibly empty) note is present; reopen still passes `''`. The case-resolution write path is unchanged.
- Honey-key incident-close (`IncidentChecklist` in `App.tsx`): `closeIncident` now takes the note as a parameter (no prompt). If the key was archived/reset, closes in one click; otherwise reveals an inline `.incident-close-note` field with explicit "Close incident" / "Cancel" — empty note stays valid, cancel is explicit (no silent abort). The incident-close write path is unchanged.
- Dead twin `components/HoneyKeysView.tsx`: same signature change + inline note (kept in its existing Tailwind aesthetic) so its `window.prompt` is gone and it still type-checks. File otherwise left dead (see Next Batch).

**CSS:** added `.sidebar-add-repo`, `.toolbar-add-repo`, `.setting-row-target`/`.setting-row-add-repo`, `.needs-repo-target-add`, the `.add-repo-*` dialog system, `.decision-note*`, and `.incident-close-note*` to `index.css` — all Mistglass tokens, fade-and-grow on the modal, reduced-motion already globally honored.

Files touched: `dashboard-ui/src/App.tsx`, `dashboard-ui/src/components/NeedsRepoTarget.tsx`, `dashboard-ui/src/components/HoneyKeysView.tsx`, `dashboard-ui/src/index.css`, and the rebuilt `src/security_observatory/dashboard/index.html` (served-asset refresh; `dashboard/assets/` is gitignored).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `cd dashboard-ui && npm run lint` | ✅ Pass | `tsc --noEmit` clean, no new type errors. |
| `cd dashboard-ui && npm run build` | ✅ Pass | `vite build` clean, 1690 modules; refreshed served static assets. |
| `grep -n "window.prompt" dashboard-ui/src/App.tsx dashboard-ui/src/components/HoneyKeysView.tsx` | ✅ Returns nothing | All live S-033/S-034 sites removed; explanatory comments avoid the literal string. (`CaseCard.tsx` twin excluded by design.) |
| Browser smoke — add a repo, bad path + empty submit | ✅ Pass | Served the built dashboard on `127.0.0.1:8899`, drove it via chrome-devtools. Empty submit → inline alert "Enter the full path…", dialog stays open, input `aria-invalid`. Bad path `not-a-real-path` → inline alert "Paste a full folder path, starting with “/”…". Valid path `/Users/.../example-repo` → dialog closes, repo added + selected as target, repo-scoped nav unlocks. No native dialog at any point. Screenshot: `receipts/evidence-06-add-repo-validation.png`. Only console error is the expected `/api` 404 (static server has no backend). |
| Browser smoke — case decision + Honey-key incident close | ⚠ Verified by type-check + build + code review, not data-backed live smoke | These views are data-driven; a full in-browser run needs the real dashboard server with a populated SQLite store, which was deliberately not spun up in the autonomous sandbox (OS firewall/permission-dialog risk per operating rules). The inline-note logic is deterministic and self-contained, and the resolution/incident-close write paths are byte-for-byte unchanged — only note capture moved from prompt to inline field. The shared modal/inline-field infra was exercised live via the S-033 smoke. Recommend re-confirming both in the mandated final UX pass (batch 07+ harness / data-backed dashboard). |

## After Health

- S-033 → **Green**: no `window.prompt` in the add-repo path; crafted Mistglass form with text input, example placeholder, `/api/projects` suggestions, inline validation that never silently fails, and one primary action; all four entry points route to the form; option-as-action retired. Verified live in-browser.
- S-034 → **Green (code/build verified)**: no `window.prompt` in the live decision-note or incident-close flows (or in the dead `HoneyKeysView.tsx`); inline Mistglass note capture on the case card and incident-close; one-click decisions preserved; cancel/empty explicit; write paths unchanged.

## Remaining Risk

- S-034's in-browser, data-backed smoke was not run autonomously (see Validation Run). Low risk: deterministic UI change, unchanged write paths, build + type-check clean.
- The add-repo "not valid" check is client-side format validation (absolute-path + non-empty), not a filesystem existence check — there is no server path-probe endpoint and the batch is frontend-scoped. Honest wording used ("Paste a full folder path…"); a known repo from `/api/projects` is the typo-free quick-pick.

## Next Batch

- **09-finish-dead-ui-surfaces** (S-036): added a clarifying note to its `context.md` — `components/HoneyKeysView.tsx` is a **fourth orphan** in the same dead-UI family (batch 06 only neutralized its dead prompt). Recommend deleting it alongside the `OverviewView`/`FindingsView`/`CaseCard` trio; until then the repo-wide `border-black` grep in 09's Required Checks will keep matching it. S-036's target S-ID was **not** changed.
- **11-case-lifecycle** (S-035): unaffected — its evidence cites `CaseCard.tsx` (the dead twin) and backend files, none touched here; my decision-note addition to the live `CaseDetailCard` is a separate concern from the resolved-state rendering S-035 changes.
