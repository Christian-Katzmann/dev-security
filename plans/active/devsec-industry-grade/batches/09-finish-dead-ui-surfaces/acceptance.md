# Acceptance: 09-finish-dead-ui-surfaces

## Acceptance Criteria

### S-036 — Delete the orphaned parallel case UI
- [ ] The orphaned trio `dashboard-ui/src/components/OverviewView.tsx`, `components/FindingsView.tsx`, and `components/CaseCard.tsx` is removed (or any genuinely wanted part adopted into the live inline equivalents and re-skinned to Mistglass, with the orphaned files then deleted). The live act path remains the inline `OverviewView` (`App.tsx:1789`), inline `FindingsView` (`App.tsx:2343`), and inline `CaseDetailCard` — one source of truth for the case control.
- [ ] No remaining import of the deleted files anywhere: `grep -rn "components/OverviewView\|components/FindingsView\|components/CaseCard" dashboard-ui/src/` returns nothing (or only references to the live inline components, never the deleted module paths).
- [ ] No off-Mistglass case styling survives from the deleted card: `grep -rn "text-black/45\|border-black\|shadow-\[inset_0_3px_0_#111111\]" dashboard-ui/src/` shows none of the banned `#000`/alarm-register styling on a case surface.
- [ ] `cd dashboard-ui && npm run build` is clean after removal.

### S-037 — Make ⌘K real or remove the false hint
- [ ] The `<kbd>⌘K</kbd>` hint is no longer a false affordance: **either** pressing ⌘K (Cmd/Ctrl+K) acts — focuses the toolbar search input or opens a command palette via a real global keydown handler — **or** the `<kbd>⌘K</kbd>` at `App.tsx:1612` is removed. If implemented, a handler exists in `dashboard-ui/src/` (mirroring `installHardRefreshShortcut` in `main.tsx`); if removed, `grep -rn "⌘K" dashboard-ui/src/` returns nothing. No half-working palette ships.
- [ ] The existing ⌘R/Ctrl-R hard-refresh shortcut (`main.tsx:7-28`) is untouched.
- [ ] Final UX pass: in-browser, press ⌘K — confirm it acts (focus/palette), or confirm the hint is gone.

### S-038 — Differentiate scan-failure feedback into crafted error states
- [ ] Scan-failure feedback is no longer one undifferentiated `runError` string: the failure paths (`App.tsx:983,987,1135-1137,1205`) carry enough structure to distinguish at least scanner-missing vs scanner-errored vs scan-failed, each rendered as a crafted Mistglass error card with the right next step (missing tool → link to Verification, reusing the existing `App.tsx:1136` "Open Verification" routing; errored → retry; failed → details).
- [ ] The error is surfaced on every surface that writes it, not only the one `inline-error` at `App.tsx:1784` — the two previously-silent write sites now render their error to the user (no scan failure is set-but-never-shown).
- [ ] `cd dashboard-ui && npm run build && npm run lint` is clean.
- [ ] Final UX pass: in-browser, smoke a scan with a missing scanner — confirm the error is actionable (names what broke and routes the user), not a single generic red line.

### S-044 — Wire or retire dead Activity filter chips
- [ ] The Activity event-feed filter chips at `App.tsx:2887` are no longer dead controls: **either** each chip carries `active`/`onClick` state and clicking it filters the event feed (mirroring the wired FindingsView chips at `App.tsx:2440-2450`), **or** they are rendered as plain static labels with no chip affordance (no clickable-looking control that does nothing).
- [ ] `cd dashboard-ui && npm run build` is clean.
- [ ] Final UX pass: in-browser, click each Activity chip — confirm it filters the feed, or confirm the chips no longer present as interactive.

## Required Checks
| Check | Why |
| --- | --- |
| `cd dashboard-ui && npm run build` | Proves the orphaned-trio deletion (S-036), the ⌘K change (S-037), the differentiated error cards (S-038), and the chip change (S-044) all compile and render; matrix validation path for all four rows. |
| `cd dashboard-ui && npm run lint` | `tsc --noEmit` confirms the deleted module paths leave no dangling imports/types and the new error-state and chip-state code type-check (S-036, S-038, S-044). |
| `grep -rn "components/OverviewView\|components/FindingsView\|components/CaseCard" dashboard-ui/src/` | Confirms no import of the deleted orphaned files remains (S-036 — matrix + synthesis "Suggested validation"). |
| `grep -rn "text-black/45\|border-black\|shadow-\[inset_0_3px_0_#111111\]" dashboard-ui/src/` | Confirms the banned `#000`/alarm-register case styling from the deleted `CaseCard` is gone (S-036 — DESIGN.md §2). |
| `grep -rn "⌘K" dashboard-ui/src/` | If ⌘K was retired, confirms the false hint is gone; if implemented, the accompanying handler grep + browser press proves it acts (S-037 — synthesis "Suggested validation"). |
| In-browser final UX pass (per AGENTS.md, only for this final-pass step): press ⌘K, smoke a scan with a missing scanner, click each Activity chip | The three runtime claims (⌘K acts/absent, scan error is actionable, chips filter/are static) are behavioral and can only be confirmed against the running UI (S-037, S-038, S-044 — synthesis "Suggested validation"). |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
