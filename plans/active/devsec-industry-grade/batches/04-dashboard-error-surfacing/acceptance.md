# Acceptance: 04-dashboard-error-surfacing

## Acceptance Criteria
- **S-004 (disabled mid-flight)** — While a case decision is awaiting the server, the four `CaseCard` decision buttons (`Verify`, `False positive`, `Accept risk`, `Mark fixed`) are visibly disabled / show a pending affordance, so the same card cannot be double-submitted. Observable: with the server stopped, clicking `Verify` on a case shows the buttons disabled during the in-flight await.
- **S-004 (failure surfaced on the Findings tab)** — When a case decision rejects, the failure is rendered inline on the Findings tab (on or beside the affected `CaseCard`), not routed into the `runError` channel that `FindingsView` never displays. Observable: with the server stopped, clicking a decision on the Findings tab produces a visible inline error on that card, and the card's status does not falsely appear changed.
- **S-005 (error boundary catches render throws)** — A top-level `ErrorBoundary` wraps the app tree; a render-time throw in a child renders a crafted Mistglass fallback ("something went wrong — reload / report", error detail collapsed) instead of white-screening the entire dashboard. Observable: temporarily throwing in a child component shows the fallback, not a blank page.
- **S-005 (`/api/summary` shape guard)** — The summary payload from `response.json()` is run through a thin runtime guard that normalizes the expected arrays, so an unexpected/older payload shape degrades to the crafted empty state rather than throwing through `displayCases`/`actionBucketCounts`/`scanCompleteness`. Observable: feeding a malformed summary (e.g. missing/non-array fields) does not crash the render.
- **S-005 (retry affordance)** — The offline/error overview state exposes a "Retry" control that calls `loadSummary()` and recovers in-product without a hard page reload. Observable: killing then restarting the server, the Retry button appears on the offline state and successfully refreshes on reconnect.

## Required Checks
| Check | Why |
| --- | --- |
| `cd dashboard-ui && npm run build` | TypeScript (`tsc -b`) compiles and `vite build` succeeds — proves the new `CaseCard` pending/error props, the `ErrorBoundary`, the summary guard, and the Retry control type-check and bundle (the matrix validation path for both S-004 and S-005). |
| `cd dashboard-ui && npm run lint` | eslint + oxlint stay clean across the edited React surfaces (`CaseCard.tsx`, `App.tsx`, `OverviewView.tsx`, the new `ErrorBoundary`), per AGENTS.md frontend verification. |
| Manual: stop the dashboard server, click `Verify` on a case from the Findings tab | Proves S-004 — the decision buttons disable mid-flight and an inline error surfaces on the card instead of a silent no-op (synthesis "Suggested validation" for S-004). |
| Manual: temporarily throw in a child component | Proves S-005's error boundary catches the throw and renders the crafted fallback instead of white-screening (synthesis "Suggested validation" for S-005). |
| Manual: kill the dashboard server, then restart it | Proves S-005's Retry affordance appears on the offline overview state and recovers via `loadSummary()` on reconnect (synthesis "Suggested validation" for S-005). |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
