# Implementation Receipt: 01-egress-honesty

## Target

- Plan: `plans/active/devsec-industry-grade/`
- Batch: 01-egress-honesty
- Source report item(s): S-002 (eliminate Google Fonts default-path egress), S-007 (make `--trust` opt-in egress disclosure exhaustive and visible)

## Before Health

- **S-002 (Yellow/Red — non-negotiable breach):** `dashboard-ui/src/index.css:1` carried
  `@import url('https://fonts.googleapis.com/css2?family=Geist...')`, which survived into the
  shipped bundle `src/security_observatory/dashboard/assets/index-DXDjm9a7.css`. Verified before
  edit: `grep -rEi 'googleapis|gstatic' src/security_observatory/dashboard/assets/` matched the
  CDN `@import` in the served CSS — so the default browser render path made a silent third-party
  call, contradicting `design/diagrams/trust-boundary.md` ("no third-party API call") and
  `README.md` ("never leave the machine").
- **S-007 (Green/Yellow — disclosure incomplete):** the trust-boundary diagram framed only "three
  opt-ins" and named neither EPSS's host nor the managed-tool download egress; the dashboard had no
  surface naming what crosses under opt-in. The four real third-party egress surfaces were
  confirmed still present in current code:
  - EPSS → `https://api.first.org/data/v1/epss` (`enrichment.py:19`)
  - OpenSSF Scorecard → `https://api.scorecard.dev/projects/{repo}` (`enrichment.py:20`)
  - legitify repo slug → GitHub on `--platform-posture` (`scanners.py:_legitify_target`/`_repo_target_from_remote`)
  - managed-tool binary downloads → `github.com/<vendor>/releases/download/...` (`managed_tools.py:65,105,147,194`)

## Changes Made

**S-002 — self-host Geist / Geist Mono (zero default-path egress):**
- Vendored the official Vercel `geist` package v1.7.1 variable woff2 faces into the repo so the
  build is fully offline/reproducible and carries no unused npm dependency:
  - `dashboard-ui/src/fonts/Geist-Variable.woff2`
  - `dashboard-ui/src/fonts/GeistMono-Variable.woff2`
  - `dashboard-ui/src/fonts/Geist-LICENSE.txt` (SIL Open Font License — required when redistributing the fonts)
  - (The `geist` npm package was installed only to source these files, then uninstalled;
    `package.json`/`package-lock.json` are unchanged from before the batch. The package's
    `exports` map is Next.js-oriented and does not expose the raw woff2 for Vite `url()` bundling,
    so vendoring is the correct path.)
- `dashboard-ui/src/index.css`: removed the remote `@import url('https://fonts.googleapis.com/...')`
  and added two local `@font-face` rules (variable faces, `font-weight: 100 900`, `font-display: swap`)
  referencing the vendored woff2 via relative `./fonts/...` URLs. Vite hashes and bundles them.

**S-007 — exhaustive, visible opt-in egress disclosure:**
- `design/diagrams/trust-boundary.md`: corrected the default-path note (now adds that the dashboard
  self-hosts its bundled fonts, so even loading the UI contacts no external host), and rewrote the
  "Explicit opt-ins" section from "three opt-ins" into **four named third-party egress surfaces** —
  each naming the exact host and exactly what is sent: EPSS (`api.first.org`, CVE IDs), OpenSSF
  Scorecard (`api.scorecard.dev`, source-repo slugs), legitify→GitHub (repo slug on
  `--platform-posture`), managed-tool downloads (`github.com/<vendor>/releases`) — plus the Honey
  Key callback kept as a distinct "crosses only to infrastructure you own" box.
- `dashboard-ui/src/App.tsx`: added a `Globe` icon import and a new **"Network egress"** card in the
  Settings view (after "Privacy and storage"). It states the default scan makes no third-party
  network calls (fonts bundled), then names all four opt-in surfaces with their host and the data
  sent. Copy claims only egress that already ships behind an existing opt-in — it does **not** imply
  CISA KEV/EPSS auto-enrichment is wired, that External Surface is active, or that packs are runnable.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `cd dashboard-ui && npm run build` | PASS | Clean. Emits `Geist-Variable-jflMhO5d.woff2` + `GeistMono-Variable-yiMTwG4J.woff2` and `index-DxSZHKAN.css` into `src/security_observatory/dashboard/assets/`. |
| `grep -rEi 'googleapis\|gstatic' src/security_observatory/dashboard/assets/` | PASS (empty) | Exit 1, no match — the CDN `@import` is gone from the shipped CSS. |
| `grep -rEi '@font-face' src/security_observatory/dashboard/assets/` | PASS | Bundled CSS has both faces: `font-family:Geist` → `/assets/Geist-Variable-*.woff2`, `font-family:Geist Mono` → `/assets/GeistMono-Variable-*.woff2`. |
| `cd dashboard-ui && npm run lint` (`tsc --noEmit`) | PASS | Exit 0 — the `index.css` + Settings-view edits keep the type floor green. |
| Read diagram + dashboard copy; confirm 4 surfaces named + default-path corrected | PASS | All four (`api.first.org`, `api.scorecard.dev`, legitify→GitHub, `github.com releases`) named in both; "three opt-ins" framing replaced; default path stated egress-free. |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli; print('ok')"` | PASS | `ok` — no Python surface was changed, fast import still clean. |

## After Health

- **S-002 → Green:** the served dashboard CSS contains no external host; the default render path
  makes zero third-party network calls, so the trust-boundary "no third-party API call" claim is now
  literally true. Typography preserved — Geist/Geist Mono load from bundled `@font-face` woff2.
- **S-007 → Green:** both the trust-boundary diagram and the in-product Settings "Network egress"
  card now name all four opt-in egress surfaces (host + data sent) and correct the stale
  "three opt-ins" / default-path framing. Disclosure is exhaustive and visible; no new egress claimed.

## Remaining Risk

- Low. The font binaries are vendored (committed) rather than pulled at build time — intentional, so
  the build stays offline and reproducible; provenance + OFL license are recorded in `src/fonts/`.
  If Geist is ever updated, re-vendor from the `geist` package and rebuild.
- The disclosure is descriptive copy/diagram, not an enforcement mechanism. The repo-wide no-egress
  *test* backstop for the Python pipeline is batch 05 (S-025); this batch only eliminates the live
  font egress and discloses the intentional opt-in egress. Batch 05's `context.md` was updated to
  note S-002 has landed (served CSS already egress-free), so its sentinel can stay scoped to the
  Python pipeline without a stale front-end caveat.

## Next Batch

02-dashboard-csrf-suppression-gate (S-001) — the second non-negotiable trust red-line.
