# Batch: 01-egress-honesty

## Purpose
DëvSec's headline promise is that running it sends nothing off the machine on the default path, yet the shipped dashboard CSS fetches Geist from Google Fonts on every load — a silent, un-opted-in third-party call the trust-boundary diagram explicitly denies exists. This batch makes the egress story honest end to end: **S-002** removes the one real default-path egress (self-host the fonts), and **S-007** makes the *intentional* opt-in egress disclosure exhaustive and visible so every network surface that can cross is named in the UI and the diagram. Both items share one fix surface — the egress-honesty seam spanning the dashboard build/CSS and the `--trust` opt-in copy plus `design/diagrams/trust-boundary.md`.

## Source Evidence
- **S-002** — Eliminate the Google Fonts default-path egress: self-host Geist / Geist Mono as bundled `@font-face` assets and remove the remote `@import` so the served CSS contacts no external host · evidence: `dashboard-ui/src/index.css:1` (`@import url('https://fonts.googleapis.com/css2?family=Geist...')`), which survives into the shipped bundle `src/security_observatory/dashboard/assets/index-DXDjm9a7.css` (verified present, exactly 1 `@import`); the claim it breaks is `design/diagrams/trust-boundary.md:40-49` ("no third-party API call") and `README.md:69` ("never leave the machine") · synthesis row S-002, lens report 05-privacy-boundary-health.initial.md (Rank 1).
- **S-007** — Make the `--trust` opt-in egress disclosure exhaustive and visible: name, in the dashboard trust opt-in copy and the trust-boundary diagram, exactly what crosses under opt-in · evidence: the four real egress surfaces are CVE IDs → EPSS/api.first.org (`enrichment.py:643`), source-repo IDs → Scorecard (`enrichment.py:286`), legitify repo slug → GitHub on `--platform-posture` (`scanners.py:562-600`), and managed-tool binary downloads → GitHub releases (`managed_tools.py:65,105,147,194,526-542`); the diagram today frames only "three opt-ins" (`design/diagrams/trust-boundary.md:51-95`) · synthesis row S-007, lens reports 05-privacy-boundary-health.initial.md (Rank 8 + Undocumented Surfaces) and 07-integration-health.initial.md ("Six outbound endpoints" / legitify-target rows).

## Target
Move S-002, S-007 from Yellow/Red to Green.

## Dependencies
None — the matrix shows `—` for both S-002 and S-007. Within this batch there is no hard ordering, but do **S-002 first** (the live breach) so the trust-boundary diagram you touch for S-007 can be edited to state the default path is now genuinely egress-free.

## Non-Goals
- Do not attempt other batches' super-list items.
- Do not broaden this into a general cleanup.
- Do not make production, destructive, deploy, secret, or irreversible data changes without explicit approval.
- Do not actually wire or fire any opt-in egress to verify it (no live calls to Google, EPSS, Scorecard, GitHub) — `.adx/risks.json` and the lens "no live calls" guardrail forbid it; prove behavior from code, build output, and a `grep` of the served bundle.
- Do not wire CISA KEV / EPSS into a *new* caller here — that promise-vs-code reconcile is S-008 (batch 21). This batch only **discloses** the egress that already ships.
- Do not imply External Surface is active or that packs are runnable in any copy you add.

## Suggested Starting Steps
1. Re-read this context and acceptance.md.
2. Re-verify each S-ID's evidence against the exact files cited: confirm the live `@import` is still in `dashboard-ui/src/index.css:1` and in the shipped `src/security_observatory/dashboard/assets/*.css`; confirm the four egress surfaces still match the `enrichment.py`/`scanners.py`/`managed_tools.py` lines above; read `design/diagrams/trust-boundary.md:40-95` for the current "no third-party API call" + "three opt-ins" framing.
3. S-002: add the Geist / Geist Mono font files into the dashboard build (Vite — e.g. under `dashboard-ui/src/` assets), replace the remote `@import` in `dashboard-ui/src/index.css` with local `@font-face` rules, rebuild with `cd dashboard-ui && npm run build`, and confirm the rebuilt CSS under `src/security_observatory/dashboard/assets/` contains the self-hosted faces and no `googleapis`/`gstatic` reference.
4. S-007: update the dashboard `--trust` opt-in copy and `design/diagrams/trust-boundary.md` so all four egress surfaces (EPSS CVE IDs, Scorecard source-repo IDs, legitify GitHub repo slug, managed-tool GitHub binary downloads) are explicitly named, and correct the "three opt-ins" / "no third-party API call" framing to match reality now that fonts are self-hosted.
5. Implement the smallest root-cause fix that satisfies every acceptance criterion; add/adjust tests where risk justifies (e.g. a guard that the served bundle stays free of external hosts).
