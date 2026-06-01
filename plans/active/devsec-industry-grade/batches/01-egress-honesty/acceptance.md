# Acceptance: 01-egress-honesty

## Acceptance Criteria
- **S-002 (non-negotiable breach eliminated):** After `cd dashboard-ui && npm run build`, `grep -rEi 'googleapis|gstatic' src/security_observatory/dashboard/assets/` returns nothing — the served dashboard CSS no longer contains the remote `@import`, so the default render path makes zero third-party network calls. The breach is demonstrably eliminated: the trust-boundary diagram's "no third-party API call" claim is now literally true on the default path.
- **S-002 (fonts still render self-hosted):** Geist / Geist Mono are present as bundled `@font-face` assets in the build output (font files served from under `src/security_observatory/dashboard/assets/`), so removing the CDN import does not regress typography — the dashboard uses the same fonts loaded locally.
- **S-007 (disclosure exhaustive):** The trust-boundary diagram (`design/diagrams/trust-boundary.md`) and the dashboard's `--trust` opt-in copy each name all four real egress surfaces explicitly: (1) CVE IDs → EPSS (api.first.org), (2) source-repo IDs → OpenSSF Scorecard, (3) legitify repo slug → GitHub (on `--platform-posture`), (4) managed-tool binary downloads → GitHub releases. The stale "three opt-ins" / "no third-party API call exists by default" framing is corrected to match the now-egress-free default path.
- **S-007 (no new egress claimed):** The added copy discloses only egress that already ships behind an existing opt-in; it does not claim CISA KEV/EPSS auto-enrichment is wired, does not imply External Surface is active, and does not present packs as runnable.

## Required Checks
| Check | Why |
| --- | --- |
| `cd dashboard-ui && npm run build` | Rebuilds the dashboard so the self-hosted fonts land in the served bundle; must complete clean. |
| `grep -rEi 'googleapis|gstatic' src/security_observatory/dashboard/assets/` returns nothing | Proves the Google Fonts default-path egress (S-002 breach) is gone from the shipped CSS. |
| `grep -rEi '@font-face' src/security_observatory/dashboard/assets/` finds the Geist faces | Proves the fonts are now self-hosted, not dropped — typography is preserved (S-002). |
| `cd dashboard-ui && npm run lint` | Confirms the `index.css` / opt-in-copy edits don't break the frontend type/lint floor. |
| Read `design/diagrams/trust-boundary.md` + the trust opt-in copy and confirm all four egress surfaces are named and the default-path claim is corrected | Proves S-007's disclosure is exhaustive and visible, and that the diagram no longer over-claims. |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check per AGENTS.md, in case any Python copy/string surface was touched for the opt-in disclosure. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
