# Step 3.1 — Full catalog sweep verification

Date: 2026-05-22
Dashboard: `http://127.0.0.1:8765/` served by `security-scan dashboard --port 8765 --no-open`.
Viewports walked: desktop 1440 × 900 and mobile 375 × 812.

## Lie-check matrix

| Criterion | Result | Evidence |
|---|---|---|
| (a) No Snooze button anywhere | Pass | `document.body.innerText.toLowerCase().includes('snooze') === false` on Home, Browse, Tool Detail, Pack Detail. |
| (b) Browse banner secondary reads "View tool" | Pass | Browse banner shows `Install` + `View tool` (icon: ArrowRight). Verified in snapshot and screenshot. |
| (c) "Read documentation" opens a real URL in a new tab | Pass | Verified click on Trivy (third-party) → opens `https://trivy.dev/` in a new tab, `target=_blank rel=noreferrer`, real page rendered (`<h1>The All-in-One Security Scanner</h1>`). Verified click on IOC Watch (built-in) → opens `http://127.0.0.1:8765/docs/iocs.md` in a new tab, body starts `# IOC Packs`. |
| (d) Pack hero has one calm note (no two disabled CTAs) | Pass | Starter Pack hero shows the single line "Pack-level install is on the roadmap. Each utility in the grid below installs on its own." A real action ("Open profile") sits below as the only recommended-scan-profile affordance. |
| (e) Install enabled for ≥ 3 tools | Pass | `/api/tool-catalog` reports `execution_available=true` for `gitleaks`, `trivy`, `syft`, `grype` (4 tools). |
| (f) §15 checklist still holds | Pass | Sentence-case headings ("Here's the catalog.", "Featured: Trivy", "Starter Pack."); one primary action per hero (Browse all tools / Install / Install plugin / Open profile); no looping motion; tap targets ≥ 44 px on mobile (button heights 44 px+); empty-state copy preserved on pack utilities ("View tool"); error path absent today but explicit "No documentation link published yet." fallback in `CatalogToolPage`. Mono is used only in places like the Honey-keys token display, which is telemetry — not in the catalog hero. |

## Per-route notes

- **Home (desktop & mobile):** Single primary CTA ("Browse all tools"), three pack cards, four popular plugins. No Snooze. Mobile collapses cleanly to single column; nav becomes horizontal scroll. Screenshot: `step-3.1-home-{desktop,mobile}.png`.
- **Browse (desktop & mobile):** Featured banner reads "Featured: Trivy" with `Install` + `View tool`. Category filter chips render at full width on desktop, wrap on mobile. Tool grid is calm and consistent. Screenshot: `step-3.1-browse-{desktop,mobile}.png`.
- **Tool Detail (Trivy, desktop & mobile):** One primary action ("Install plugin"). No Snooze. Aside contains "Read documentation" → `https://trivy.dev/` (real upstream, new tab). Specs and policy in two columns on desktop, stacked on mobile. Screenshot: `step-3.1-tool-{desktop,mobile}.png`.
- **Pack Detail (Starter Pack, desktop & mobile):** Hero shows the single calm note about roadmap. Below, a real "Open profile" button is the only primary action. The utility grid shows seven entries with "View tool" buttons. Screenshot: `step-3.1-pack-{desktop,mobile}.png`.

## Built-in vs third-party docs links

The catalog has 12 entries with `docs_path` set to a `/docs/<file>.md` path (4 built-in scanners + 1 tool-catalog reference + 1 External Surface placeholder). Step 1.2 shipped these as relative paths (`docs/iocs.md`), which the dashboard server does not serve — clicking them returned a 404. Step 3.1 fixed this in place by:

1. Adding a `/docs/<file>.md` route to `dashboard_server.py` that safely serves files from the repo's `docs/` directory.
2. Switching the catalog's `docs_path` values to absolute (`/docs/iocs.md`) so the link resolves correctly regardless of any client URL.
3. Making all `Read documentation` links open in a new tab (so clicking an in-repo doc doesn't blow away the SPA state).
4. Strengthening `test_every_catalog_entry_has_a_real_documentation_link` so any future `docs_path` must start with `/docs/` and resolve to a real file on disk.
5. Adding `tests/test_dashboard_docs_route.py` to assert the new route serves real markdown, 404s for missing files, and rejects path-traversal attempts.

## Cross-tab regression walk (desktop)

- Overview: KPI cards, posture chart, recent activity all render. Screenshot: `step-3.1-regression-overview-desktop.png`.
- Findings: 424-finding table, severity histogram, filter pills work. Screenshot: `step-3.1-regression-findings-desktop.png`.
- Honey keys: 1 armed key, deploy/retire affordances. Screenshot: `step-3.1-regression-honey-desktop.png`.
- Verification: Scanner doctor with "Checks that ran / Skipped or missing / Cannot prove" cards. Screenshot: `step-3.1-regression-verification-desktop.png`.

## Dropped-tool sanity

Per Step 2.1's choice (Trivy + Syft + Grype shipped; Semgrep + OSV-Scanner dropped from the managed-install path), the dropped tools still render an honest disabled install affordance:

- `osv-scanner` (state=`detected`): execution_available=false with explicit `execution_reason` "Detected tools are user-owned and are not managed by DëvSec." The Install button shows the user-owned next-step copy.
- `malcontent` (state=`missing`): execution_available=false with `execution_reason` "No managed installer is approved for this tool in the MVP." Install button visible but disabled, with shell instructions surfaced as next-step copy.

Neither is a "half-broken state where the button looks enabled but does nothing" — the disabled state and copy are clearly distinguished.

## Tooling state

- `npm run lint`: passes (tsc --noEmit, no errors).
- `make dashboard-build`: passes (vite build, 322 kB bundle).
- `uv run pytest`: 131 tests pass (added 3 docs-route tests, strengthened 1 catalog test).
- Dashboard server stopped at end of step (PID killed; port 8765 free).
