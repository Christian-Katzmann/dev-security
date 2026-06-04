# DëvSec Design Lab

A **sealed design space** for rebuilding the DëvSec product dashboard in the
chosen direction — **Mistglass Grey** — screen by screen, from scratch, UX-first.

This is not a migration of the old UI. For each screen we re-derive it from
`(Mistglass Grey) + (what the screen must do)`. The live dashboard is only the
**feature map** of what to keep.

> Runs as its own Dock app — **"DëvSec Design"** (app-it) — so you can watch it
> evolve next to the live **Security Observatory** app, side by side.

## Direction: Mistglass Grey

Cool sage→teal grey surface, white-on-grey, frosted "mistglass" cards, soft
radii, calm restraint (see root `MISTGLASS-GREY.md`). Color is spent **only on
severity / attention** — the system is otherwise monochrome grey + white.

> A second direction — the dark gradient-mood kit from the original handoff —
> was explored and parked (its files still live under `foundation/` and
> `screens/foundation.jsx`, unloaded). Likely future home: the marketing site.

## The rules (what keeps it safe)

- **Sealed.** Never imports from the live app (`dashboard-ui/`, `src/`), and
  nothing imports from here. Isolation is by architecture, **committed, not
  `.gitignore`d** — so the work is reviewable and recoverable.
- **Fake data only.** No backend. These are visual prototypes; wiring to the
  real product is a separate, later phase.
- **One shell + one kit, built once.** Every screen composes from the shared
  `MistShell` + `mist-kit` so the system stays consistent and calm.

## The loop (per screen)

**Map → Brief → Build → Gate → Park** (brief template in `briefs/_template.md`).

## Structure

```
design-lab/
  index.html              # harness: Tailwind + React UMD + Babel standalone
  app.jsx                 # nav model + routing through MistShell
  foundation/
    mistglass.css         #   Mistglass Grey tokens (surface, glass, text, severity)
    mist-kit.jsx          #   shared components: MGlass, MSev, MState, MStat, MRow, MBtn, MPageHead, MFilters…
    mist-shell.jsx        #   the desktop chrome: canvas + quiet nav + CENTERED capped content column
    primitives.jsx        #   FocusLogo, Icon (Lucide), Trademark, QR
    assets/               #   logo, favicon
    (styles.css, colors_and_type.css, shell.jsx = parked dark kit)
  screens/
    m-overview.jsx  m-cases.jsx  m-activity.jsx  m-honey-keys.jsx
    m-verification.jsx  m-fixes.jsx  m-playbooks.jsx  m-catalog.jsx
    m-agent-lab.jsx  m-reports.jsx  m-settings.jsx
    (foundation.jsx, _stub.jsx = parked dark kit)
  briefs/_template.md
```

## Add a screen

1. Build `screens/m-<id>.jsx`; end with `Object.assign(window, { M<Name> });`.
2. Add its `<script type="text/babel" src=…>` to `index.html` (before `app.jsx`).
3. Register it in `app.jsx` → `MIST_SCREENS` and add a `MIST_NAV` item.

## Run

- **As an app:** open **"DëvSec Design"** from `~/Applications/App It/`. Cmd+Q to quit.
- **In a browser:** `bash scripts/run-design-lab.sh` → http://127.0.0.1:8788
- No build step — edit a file, refresh.

## Open items / decisions

- **Responsiveness.** Content is capped at 1180px and centered (fixes the 32"
  monitor proportions). A full responsive + mobile pass is still TODO.
- **Severity palette.** First-pass calm tones live in `mist-kit.jsx` (`SEV`);
  tunable. The "brighter brand color" Christian is choosing likely becomes the
  `critical` / attention hue.
- **Grey vs paper.** The dense Cases screen proves grey-forward holds for data,
  so paper may not be needed — revisit only if a screen feels low-contrast.
- **Graduation.** Approved screens get re-implemented + wired inside
  `dashboard-ui/` (the design/implementation split is the point, not rework).
