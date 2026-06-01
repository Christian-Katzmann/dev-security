# Implementation Receipt: 04-dashboard-error-surfacing

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 04-dashboard-error-surfacing
- Source report item(s): S-004, S-005 (lens `08-error-edge-state-health.initial.md`)

## Before Health

**Critical evidence correction — the cited files are dead code.** The synthesis/lens
evidence pointed at `dashboard-ui/src/components/CaseCard.tsx`,
`components/OverviewView.tsx`, and `components/FindingsView.tsx`. Re-verifying against
the current tree (`grep` for `CaseCard`, `OverviewView`, `FindingsView` across
`dashboard-ui/src`) shows that trio references **only each other** — nothing in the app
imports them. They are an orphaned, Tailwind-utility-styled cluster. The **live**
dashboard is rendered by App.tsx's own local, Mistglass-styled definitions:

- `OverviewView` — `App.tsx:1814`
- `FindingsView` — `App.tsx:2368` (master/detail; renders cases via `CaseDetailCard`)
- `CaseDetailCard` — `App.tsx:3375` (the real decision-button surface)

Re-verified defect on the live surfaces:

- **S-004** — `CaseDetailCard.save()` (`App.tsx:3393`) awaited `onDecision` with no
  in-flight/disabled/error state; the four decision buttons had no `disabled`.
  `saveCaseDecision` (`App.tsx:1218`) swallowed the rejection into `setRunError`, and
  the live `FindingsView` never reads/renders `runError` — so a failed decision was a
  silent no-op and the card looked unchanged. (The dead `views/FindingsView.tsx` having
  no `runError` was a true observation about a file that is never rendered.)
- **S-005** — no `ErrorBoundary`/`getDerivedStateFromError` anywhere in
  `dashboard-ui/src` (confirmed empty grep); `loadSummary` did
  `setSummary(await response.json())` with no shape guard (`App.tsx:944`); the offline
  overview state (`App.tsx:1981` `Notice`) was honest but had no Retry.

## Changes Made

All fixes landed on the **live** surfaces, not the dead `components/` trio.

**S-004 — surface case-decision failures inline on the Findings tab**
- `App.tsx` `saveCaseDecision` (~1218): stop swallowing the rejection into the
  never-rendered `runError` channel — it now **rethrows** so the calling card can react.
- `App.tsx` `CaseDetailCard` (~3375): added local `pendingDecision` + `decisionError`
  state (reset on `item.id` change). `save()` sets pending, awaits, catches, and clears
  pending in `finally`. All four decision buttons + Reopen are `disabled` while any
  decision is in flight (`aria-busy` on the active one, label flips to "Saving…"), so the
  card cannot be double-submitted. On rejection, an inline `.decision-error` block renders
  on the card ("This decision was not saved, so the case status is unchanged. …") and the
  status is not falsely changed (`loadSummary` is never reached on failure).

**S-005 — error boundary + shape guard + retry**
- New `dashboard-ui/src/components/ErrorBoundary.tsx`: class boundary
  (`getDerivedStateFromError` + `componentDidCatch`) with a crafted Mistglass fallback
  ("Something went wrong." — Reload + Copy-error-detail, full error collapsed in
  `<details>`). Local-first: logs to console only, copy via clipboard — no egress.
- `main.tsx`: wraps the rendered tree (`<App/>` / `SetupCardDemo`) in `<ErrorBoundary>`
  inside `<StrictMode>`.
- `App.tsx` `normalizeSummary` (new, module-scope ~920): thin guard that coerces the
  render-path arrays (`repos`, `history`, `findings`, `agent_lab_proposals`, plus the
  optional case/honey arrays when present-but-not-array) to arrays; non-object payloads
  fall back to `emptySummary`. Wired into `loadSummary` (`setSummary(normalizeSummary(
  await response.json()))`). Not schema validation — per the non-goal.
- `App.tsx` `Notice` gained an optional `action` slot; the overview offline `Notice`
  (~1981) now carries a **Retry** button that calls `onRefresh()` (= `loadSummary`),
  recovering in-product without a hard reload.
- `index.css`: `.decision-grid button:disabled`, `.decision-error`, `.notice-action`,
  and the `.app-error-boundary` fallback styles.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `cd dashboard-ui && npm run lint` (`tsc --noEmit`) | ✅ Pass | Clean; new props/guard/boundary type-check. |
| `cd dashboard-ui && npm run build` (`vite build`) | ✅ Pass | 1690 modules, built in ~1.3s, bundles emitted. |
| Manual: stop server → Verify from Findings tab | ⏸ Deferred to end-of-campaign human review | Verified by code trace (below); not booted live to avoid OS/firewall dialogs in the headless autopilot session. |
| Manual: throw in a child component | ⏸ Deferred (same) | Standard React boundary; build proves it compiles. |
| Manual: kill then restart server (Retry) | ⏸ Deferred (same) | Retry → `onRefresh`/`loadSummary` by code trace. |

**Code-trace evidence (manual criteria):**
- *S-004 disabled mid-flight*: `disabled={pendingDecision !== null}` on every decision
  button; `pendingDecision` is set before the `await` and cleared in `finally`.
- *S-004 inline failure*: server stopped → `fetch` rejects → `saveCaseDecision` rethrows
  → `CaseDetailCard.save` catch sets `decisionError` → `.decision-error` renders; the
  `await loadSummary()` after the POST is never reached, so the card status is unchanged.
- *S-005 boundary*: `getDerivedStateFromError` stores the error and `render` returns the
  fallback instead of children — a child throw can no longer white-screen the app.
- *S-005 shape guard*: a malformed/missing-array payload is coerced to arrays (or
  `emptySummary`), so `displayCases` / `actionBucketCounts` / `scanCompleteness` iterate
  arrays and degrade to the crafted empty state rather than throwing.
- *S-005 retry*: the offline `Notice` action button's `onClick` calls `onRefresh()`,
  which is `loadSummary` threaded down from `App`.

## After Health

S-004 and S-005 moved Yellow/Red → Green on the **live** surfaces. A failed case decision
now disables the buttons mid-flight and renders an honest inline error on the card instead
of a silent no-op; a render-time throw is caught by a crafted top-level fallback; an
unexpected `/api/summary` shape degrades to empty state; and the offline overview exposes a
working Retry. Lint + build (the matrix validation path for both items) are green.

## Remaining Risk

- The live browser/server walkthrough (3 manual checks) was **not executed** in this
  autonomous session to respect the no-GUI/no-firewall-prompt operating rules; it is left
  for the end-of-campaign human review. Logic is deterministic and covered by the code
  traces above; both static gates pass.
- The dead `components/{CaseCard,OverviewView,FindingsView}.tsx` trio was left untouched
  (removing it is an unrelated cleanup, out of this batch's scope). It still compiles but
  is never rendered. A future cleanup batch could delete it to stop misleading forensics.
- The shape guard is intentionally thin (array coercion only), per the non-goal; it is not
  a schema validator. Full contract validation remains S-021/S-022 territory.

## Next Batch

`05-trust-integrity-tests` (S-024, S-025) — Python test suite only; re-read confirmed it
references nothing in `dashboard-ui/`, so this batch required **no** downstream adjustment
to its context.md/acceptance.md. My changes add no egress, so the S-025 no-egress sentinel
scoping is unaffected.
