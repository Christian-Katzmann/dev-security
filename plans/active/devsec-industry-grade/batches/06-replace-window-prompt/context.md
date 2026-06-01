# Batch: 06-replace-window-prompt

## Purpose
The core triage loop repeatedly drops to raw `window.prompt` native OS dialogs — the worst kind of uncrafted, dead-end UX the Excellence Brief names as a first-class failure. This batch (S-033, S-034) replaces every `window.prompt` in the dashboard with crafted in-app Mistglass inputs, sharing one fix surface: the React dashboard's blocking-dialog flows in `dashboard-ui/src/App.tsx` (and `HoneyKeysView.tsx`). The headline is the first-run "add a repo" gateway — the product's very first interaction for Christian's non-technical audience is currently a bare path-paste prompt with no validation, picker, or feedback. Getting native dialogs out of the loop is the heart of the "effortless triage" outcome and gates the second behavioral-ux-health pass.

## Source Evidence
- **S-033** — Replace the first-run "add a repo" raw `window.prompt('Paste the full path to the repo folder.')` with a crafted in-app Mistglass form (text input + recent/known-repo suggestions from `/api/projects` + inline "path not found" validation + one primary action; retire the dropdown-option-as-action). · evidence: `dashboard-ui/src/App.tsx:996` (the prompt; empty input silently `return`s, only normalization is `.trim().replace(/\/+$/,'')`); fired from sidebar select `App.tsx:1500`, toolbar select `App.tsx:1591`, QuickActions tile `App.tsx:1991`, and `NeedsRepoTarget` add-repo option; `/api/projects` server route at `src/security_observatory/dashboard_server.py:2331`, client fetch at `App.tsx:936` · synthesis row S-033, lens report 11-behavioral-ux-health.initial.md (Ranked row 1)
- **S-034** — Replace the recurring core-loop `window.prompt` note dialogs with inline Mistglass note fields/popovers, keeping the one-click decisions: case-decision note capture and the Honey-key incident-close note. · evidence: decision note `dashboard-ui/src/App.tsx:3346` (`'Optional note for this decision'`); incident-close note `dashboard-ui/src/App.tsx:2598` and `dashboard-ui/src/components/HoneyKeysView.tsx:157` (`'Add an accepted-risk note before closing this incident.'`); cancel/empty `null` handled silently · synthesis row S-034, lens report 11-behavioral-ux-health.initial.md (Ranked row 2)

## Target
Move S-033, S-034 from Yellow/Red to Green.

## Dependencies
None. The matrix shows `—` in the Dependencies column for both S-033 and S-034. No same-batch ordering constraint; S-033 (the headline first-run gateway) is the higher-leverage of the two and is the natural first move.

## Non-Goals
- Do not attempt other batches' super-list items.
- Do not broaden this into a general cleanup.
- Do not make production, destructive, deploy, secret, or irreversible data changes without explicit approval.
- Do not touch the dead off-Mistglass twin `dashboard-ui/src/components/CaseCard.tsx` (its `window.prompt` at line 81 belongs to batch `09-finish-dead-ui-surfaces`, which deletes the orphaned trio). This batch only converts the **live, mounted** prompt sites in `App.tsx` and `HoneyKeysView.tsx`.
- Do not change what a decision/close *does* (the case-resolution and incident-close write paths stay identical) — only how the optional note is captured. Cancel/empty must remain a valid "no note" path, not a silent abort that misleads the user.
- Do not build a folder/native file picker (out of scope and reintroduces an OS dialog); suggestions come from `/api/projects`.

## Suggested Starting Steps
1. Re-read this context and acceptance.md.
2. Re-verify each S-ID's evidence against the exact files cited (`grep -rn "window.prompt" dashboard-ui/src/` should show the five sites; confirm `App.tsx:996`, `App.tsx:2598`, `App.tsx:3346`, `HoneyKeysView.tsx:157` are the four live targets and `CaseCard.tsx:81` is the dead twin left for batch 09).
3. S-033: build a Mistglass `PaperCard` add-repo form (text input, an example/placeholder, recent/known-repo suggestions pulled from the already-wired `/api/projects` fetch, inline "path not found" validation against that list, one primary action). Route all four entry points (sidebar/toolbar selects, QuickActions tile, `NeedsRepoTarget`) through the form and retire the `<select>` "+ Add repository…" option-as-action smell.
4. S-034: replace the two live note prompts with an inline Mistglass note field/popover on the card and on the incident-close flow; preserve one-click decisions and make cancel/empty an explicit "save without a note" rather than a silent no-op.
5. Implement the smallest root-cause fix that satisfies every acceptance criterion; keep changes within the Mistglass design system (read `DESIGN.md` first per AGENTS.md). Add a vitest/component test or browser-smoke evidence where risk justifies (note: the a11y test harness arrives in batch 07 — do not block on it here).
