# Step 3.2 validation

Run time: 2026-05-21T18:23:20Z

## Commands

- `cd dashboard-ui && npm run lint` passed.
- `make dashboard-build` passed and rebuilt `src/security_observatory/dashboard/`.

## Browser review

Local dashboard reviewed at `http://127.0.0.1:8766`, then stopped.

Screenshots:

- `step-3.2-desktop.png` - 1440 x 1000 catalog browse.
- `step-3.2-mobile.png` - 390 x 844 first mobile fold.
- `step-3.2-mobile-cards.png` - mobile install-state/filter area.
- `step-3.2-mobile-detail.png` - mobile pack/card area.
- `step-3.2-external-surface.png` - External Surface display-only detail.

Checks:

- Desktop body width matched viewport and no visible horizontal overflow was detected.
- Mobile body width matched viewport; offscreen nav items are contained by the intended horizontal mobile nav geometry.
- External Surface detail had no inputs, no runnable buttons, and no install/uninstall affordances.
- External Surface copy states that DëvSec does not collect targets, probe domains, or run external reconnaissance yet.

## Reachable catalog states

Current dashboard API data exposes 16 catalog entries: 4 built-in, 9 detected locally, 2 missing, and 1 coming soon. There are no current entries for DëvSec-managed, needs-setup, or unavailable states, so those states are visible in the state strip but not reachable as selected tool cards with available test data.
