# Acceptance: 06-replace-window-prompt

## Acceptance Criteria

**S-033 — first-run add-repo gateway (Yellow/Red → Green)**
- No `window.prompt` remains in the add-repo flow: `grep -n "window.prompt" dashboard-ui/src/App.tsx` shows no match for the add-repo path (line ~996 site is gone).
- Adding a repo opens a crafted in-app Mistglass form (a `PaperCard`-style surface with a text input, a visible example/placeholder, and one primary action) — not a native OS dialog.
- The form surfaces recent/known-repo suggestions sourced from `/api/projects` (the already-wired fetch at `App.tsx:936`).
- Submitting a path that is not found / not valid shows an **inline** "path not found"-style validation message in the form; the form does not silently close or no-op on a bad or empty submission (the old silent-empty-`return` behavior is eliminated).
- All four entry points (sidebar select, toolbar select, QuickActions "Add repository" tile, and `NeedsRepoTarget`) lead to the form; the `<select>` "+ Add repository…" option-as-action smell is retired (a select option no longer secretly fires an action).

**S-034 — note/close dialogs across the core loop (Yellow → Green)**
- No `window.prompt` remains in the live decision-note flow or the live incident-close flow: `grep -n "window.prompt" dashboard-ui/src/App.tsx dashboard-ui/src/components/HoneyKeysView.tsx` returns nothing (the `App.tsx:3346`, `App.tsx:2598`, and `HoneyKeysView.tsx:157` sites are gone).
- Recording a case decision captures the optional note via an inline Mistglass note field/popover on the card; one-click decisions are preserved (deciding without a note still works in one action).
- Closing a Honey-key incident captures the accepted-risk note via an inline Mistglass field, not a blocking native dialog.
- Cancel/empty is explicit, not silent: the user can clearly choose "save without a note," and the underlying decision/close write path (case resolution / incident close) is unchanged by this batch.
- The dead-twin `dashboard-ui/src/components/CaseCard.tsx:81` `window.prompt` is intentionally **not** touched here (owned by batch 09); its presence does not count against this batch.

## Required Checks

| Check | Why |
| --- | --- |
| `cd dashboard-ui && npm run lint` | Type-check (`tsc --noEmit`) passes after the React changes; no new type errors introduced by the new form/inline-note components. |
| `cd dashboard-ui && npm run build` | The dashboard builds cleanly with the replaced flows and refreshes the served static assets. |
| `grep -n "window.prompt" dashboard-ui/src/App.tsx dashboard-ui/src/components/HoneyKeysView.tsx` returns nothing | Proves all live `window.prompt` sites for S-033 and S-034 are removed (the dead `CaseCard.tsx` twin is excluded by design). |
| Browser smoke: add a repo with a bad path and with an empty submit | Proves the S-033 form validates inline and never silently fails — the final behavioral-UX pass evidence (lens report row 1 validation path). |
| Browser smoke: record a case decision and close a Honey-key incident in-browser | Proves no native dialog appears in the core loop and the inline note capture works end-to-end (lens report row 2 validation path; final behavioral-ux-health pass re-confirmation). |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
