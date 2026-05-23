# 3. Default dashboard target — aggregate "dashboard" view, not last-scanned repo

## Status

Accepted (2026-05-23). Resolves F-001, F-006, F-008 from the `walkthrough-audit-20260523-102224` punch list.

## Context

When the DëvSec dashboard opens, it must default to *some* target — either a specific scanned repo, or an aggregate view across all scanned repos. The audit found this default was driving three separate honesty bugs:

- **F-001** — The "Run all" button in the header toolbar was disabled with no tooltip when the default target was the aggregate, leaving users wondering why the button was inert.
- **F-006** — "Rerun checks" buttons on Recovery playbook cards silently no-op'd when the target was the aggregate.
- **F-008** — The "Open profile" button on Pack pages opened a sheet titled *"Choose a repo target"* with a disabled Start button and no repo picker.

All three symptoms shared one root cause: the default target was `dashboard` (the aggregate), and every "run a scan" affordance silently gated on `target.type === 'repo'` — visibly active, secretly inert.

Two paths were considered:

- **(A)** Change the default target to the most-recently-scanned repo, so every action just works without explanation.
- **(B)** Keep the aggregate `dashboard` view as the default and make every gated affordance visibly explain what it needs.

## Decision

**Path (B).** The dashboard's default target remains the `dashboard` aggregate view. Every affordance that requires a specific repo now visibly explains itself: tooltips on disabled buttons, inline picker affordances where appropriate, and a single shared *"needs a repo target"* helper component reused across all three surfaces.

The `useEffect` at `dashboard-ui/src/App.tsx:609` that silently hid the broken behavior was removed after pre-flight grep confirmed no other code path depended on it.

## Consequences

**Positive**

- First impression is *"see your whole world"* — open findings across every scanned repo, total honey keys armed, recent scan activity timeline. This matches the mental model a multi-repo developer arrives with.
- The aggregate view is the only place that surfaces cross-repo signals (which repo just got worse, which scan failed). Making it the default makes those signals discoverable.
- The fix for the three silent-gate bugs generalizes: any future affordance that needs a specific repo target gets the same shared helper.

**Negative**

- A user whose primary use case is scanning a single repo sees more chrome than necessary — they have to switch to that repo every time they open the dashboard. Mitigation: target selection persists across dashboard restarts (the `target` is in `localStorage`), so the only friction is on first open.
- The aggregate view has to remain meaningful even when zero repos are scanned (empty state). The empty state is calmer than path (A) would have required, but it's an additional surface to maintain.

## Alternatives considered

**Path (A) — default to last-scanned repo.** Would have made every action immediately runnable without explanation. Rejected because it changes the dashboard's mental model from *"see your whole world"* to *"see your last scan"* — a worse first impression for a multi-repo tool, and a worse landing experience for a public-repo debut where the aggregate view answers the *"what does this thing show me?"* question better than a single repo's findings list does.

**Path (C) — modal repo picker on dashboard open.** Force the user to pick a target before any view is rendered. Rejected because it's friction on every dashboard open, and the aggregate view IS a legitimate target — making it pickable but not default conflicts with the goal of surfacing cross-repo signals.

**Path (D) — silent fallback to last-scanned repo when an action requires it.** Have "Run all" silently scan the last repo when clicked from the aggregate. Rejected because silent fallback is the exact pattern the audit was punishing — visible-active-secretly-inert. Visible disabled-with-explanation beats visible enabled-with-surprise.
