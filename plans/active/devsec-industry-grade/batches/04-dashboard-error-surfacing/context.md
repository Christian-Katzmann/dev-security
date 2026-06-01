# Batch: 04-dashboard-error-surfacing

## Purpose
The dashboard's strong scanner/backend pipeline is undone by a leaky error-surfacing ring on its most trust-sensitive React surfaces. This batch fixes two of those: S-004, a failed "Mark fixed"/"Verify" decision on the Findings tab silently no-ops (the card doesn't change and no error shows — the user believes a case is resolved when it is not), and S-005, the dashboard has no React error boundary, so any render-time throw (e.g. an unexpected `/api/summary` shape) white-screens the whole app, and the offline/error overview state has no Retry. The shared fix surface is the React dashboard's mutation/error/fetch layer in `dashboard-ui/src/` — both items are about turning silent or catastrophic failures into crafted, recoverable states.

## Source Evidence
- **S-004** — Stop swallowing case-decision failures on the Findings tab: give `CaseCard` a per-card pending+disabled state during the awaited mutation and surface the rejection inline on the card. · evidence: `dashboard-ui/src/components/CaseCard.tsx:77-83` (`saveDecision` awaits `onDecision` with no in-flight/disabled/error state; decision buttons have no `disabled` attr); `dashboard-ui/src/App.tsx:1194-1205` (`saveCaseDecision` routes the rejection into `setRunError`) but `runError` renders only in `RunCheckSheet` (`App.tsx:1784`) and `OverviewView`, and `FindingsView.tsx` never reads `runError` (verified: zero matches) · synthesis row S-004, lens report 08-error-edge-state-health.initial.md (Rank 2)
- **S-005** — Add a top-level React `ErrorBoundary` with a crafted fallback, a "Retry" affordance on the offline/error overview state, and a thin runtime guard normalizing the trusted `/api/summary` arrays. · evidence: no `ErrorBoundary`/`componentDidCatch`/`getDerivedStateFromError`/`<Suspense` anywhere in `dashboard-ui/src` (verified: empty grep); `dashboard-ui/src/App.tsx:914-920` `loadSummary` does `setSummary(await response.json())` with no shape guard; `App.tsx:910,923` set the fetch `error` state and `OverviewView.tsx:53-58,166-171` show an honest offline note but no Retry button · synthesis rows S-005 (folds in lens Rank 3 + Rank 4), lens report 08-error-edge-state-health.initial.md (Rank 3, Rank 4)

## Target
Move S-004, S-005 from Yellow/Red (S-004's worst) to Green.

## Dependencies
None. The matrix shows "—" for both S-004 and S-005. No same-batch ordering is required (the CaseCard surfacing and the error-boundary/retry/shape-guard work are independent), though doing the smaller, well-bounded S-004 surfacing first is a natural warm-up.

## Non-Goals
- Do not attempt other batches' super-list items.
- Do not broaden this into a general cleanup.
- Do not make production, destructive, deploy, secret, or irreversible data changes without explicit approval.
- Do not touch the backend `do_GET` error wrapping or the self-healing SQLite path — those are S-006/S-003 in batch 03; this batch is the React-layer surfacing only.
- Do not change the idempotent server write contract (`storage.py` `on conflict(case_id) do update`); the defect is client-side invisibility, not the write.
- Keep the runtime `/api/summary` guard thin — normalize array shapes defensively, do not introduce a full schema-validation framework or rewrite the data contract (that is S-021/S-022's territory).

## Suggested Starting Steps
1. Re-read this context and acceptance.md.
2. Re-verify each S-ID's evidence against the exact files cited (`CaseCard.tsx:77-83`, `App.tsx:914-920` and `:1194-1205`, `OverviewView.tsx:53-58/166-171`; confirm `FindingsView.tsx` still has no `runError` and `dashboard-ui/src` still has no error boundary).
3. S-004: add a local pending state to `CaseCard` so the four decision buttons (`CaseCard.tsx:273-297`) disable while the awaited `onDecision` is in flight, and surface a per-card inline error when the decision rejects — so the Findings tab no longer routes its only failure signal into a `runError` channel it never renders.
4. S-005: add a top-level `ErrorBoundary` component wrapping the app tree (in `main.tsx`/`App`) that renders a crafted Mistglass "something went wrong — reload / report" fallback with the error detail collapsed; add a "Retry" button on the `OverviewView` offline/error state that calls `loadSummary()`; add a thin runtime guard normalizing the summary arrays from `response.json()` so an unexpected payload shape degrades to empty-state rather than throwing.
5. Implement the smallest root-cause fix that satisfies every acceptance criterion; add/adjust component tests where the surfacing risk justifies, and keep `npm run lint` and `npm run build` green.
