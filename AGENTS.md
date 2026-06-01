# Agent Guide

## Start Here

- This repo is Security Observatory: a local-first security scanner, SQLite history store, local dashboard, and macOS desktop launcher. **Security Observatory** is the package/repo name (`src/security_observatory/`, the `security-scan` CLI); **DëvSec** is the product brand. They are the same project — code uses `security_observatory`, user-facing surfaces say DëvSec.
- Canonical ADX manifest: `.adx/adx.json`
- Command registry: `.adx/commands.json`
- Verification matrix: `.adx/verification.json`
- Risk register: `.adx/risks.json`
- Recovery notes: `.adx/recovery.md`
- Module map: `.adx/modules/index.json`
- Canonical contract = the `.adx/*` files above plus this `AGENTS.md`, `README.md`, `mcp/README.md`, and `docs/`. Treat `campaigns/`, `reports/campaign-automation/`, and the root scratch docs (`next-step.md`, `overview-redesign-*.md`) as historical working notes — a record of how the repo got here, not current contract. They may be stale or superseded; do not trust them over the canonical files or the code itself.

## Repo Shape

- Python CLI and scanner orchestration live in `src/security_observatory/`.
- Scanner adapters live in `src/security_observatory/scanners.py`; normalized findings are produced through `normalize.py`, `model.py`, `cases.py`, `priority.py`, and `storage.py`.
- The dashboard server is `src/security_observatory/dashboard_server.py`.
- React dashboard source is in `dashboard-ui/`; its built static assets are served from `src/security_observatory/dashboard/`.
- macOS desktop launcher scripts live in `scripts/`, with generated app bundles under `desktop/`.

## Design System

- For dashboard/frontend UI work, read `DESIGN.md` before editing. It is the canonical Mistglass design system for DëvSec.
- Prefer root `DESIGN.md` over mockup-local design notes. Mockup `DESIGN.md` files are references, not source of truth.
- Treat `temporaty design mockups/` as temporary wireframe evidence, not production source code. Useful references:
  - `temporaty design mockups/stitch_d_vsec_tool_marketplace (4)/screen.png` for catalog browse, filters, compact tool cards, and status pills.
  - `temporaty design mockups/stitch_d_vsec_tool_marketplace (1)/screen.png` for tool detail anatomy, specs, capabilities, and install-state panels.
  - `temporaty design mockups/stitch_d_vsec_tool_marketplace (2)/screen.png` for pack-page rhythm, included tools, and curated pack storytelling.
  - `temporaty design mockups/stitch_d_vsec_tool_marketplace/screen.png` for catalog section rhythm, featured packs, and popular tools.
  - `temporaty design mockups/stitch_d_vsec_tool_marketplace (3)/screen.png` is useful for illustrated card treatments and future dark-mode exploration; do not use its overall dark/atmospheric mood as the default light theme.
- Do not copy mockup wording that conflicts with MVP safety decisions. In particular, avoid implying External Surface is active, packs are runnable, or broad one-click install/uninstall is already available.

## Operating Rules

- Use `.adx/commands.json` instead of guessing setup, scan, dashboard, test, or desktop commands.
- Check `.adx/risks.json` before running installer, scanner, Honey Key, desktop install/quit, process-kill, or report-storage commands.
- Treat `~/.security-observatory` as local runtime data, not source.
- Do not run `./install-security-observatory.sh`, `security-scan`, dashboard servers, or desktop launcher commands unless the task requires them.
- Do not wire blocking hooks or CI gates without explicit user approval.
- Generated/noisy folders include `.venv/`, `.pytest_cache/`, `.playwright-mcp/`, `dashboard-ui/node_modules/`, `src/security_observatory/dashboard/assets/`, `desktop/`, `assets/icons/build/`, and Python `__pycache__/` folders.
- Two MCP adapters ship (`pyproject.toml` `[project.scripts]`): `devsec-mcp` is the read-only default (stdio-only, no network port, no write tools — 11 read tools over scan history), and `devsec-mcp-rw` is a guarded write adapter (also stdio-only, no network port) that adds eight write-mode tools on top: the `devsec.case_resolutions.v1` follow-up/preview/apply trio, a rate-limited local-offline rescan (`trigger_scan`), and the propose → clean-room-review → land fix flow (`propose_fix`, `clean_room_review_packet`, `record_clean_room_review`, `land_fix`). Suppressing a high/critical case never auto-applies — it is held for explicit human confirmation — and the clean-room reviewer sees only the diff and invariants, never the finding text. See [mcp/README.md](mcp/README.md) for the full write surface.

## Verification

- For Python changes, prefer `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` as a very fast import check, then run `uv run pytest` for the Python test suite.
- For dashboard UI changes, use `cd dashboard-ui && npm run lint` and `cd dashboard-ui && npm run build`.
- For desktop launcher changes, use the Makefile targets only when the task specifically concerns the app bundle, and stop any warm server with `make desktop-quit` when finished.

## Known Gaps

- This directory is a local git checkout. It may not have a remote; check before assuming push/PR workflows exist.
- The local `.venv` is managed by `uv`; use `uv sync --dev` if test dependencies are stale, then `uv run pytest`.
- There is no repo-local ADX command runner installed; use the JSON contracts directly or the shared ADX kit when available.

## Ghost Invasion Memory

Durable, non-secret facts the next Ghost Invasion run can reuse.
<!-- ghost-invasion-memory:start -->
- safe_base_url: http://127.0.0.1:8876
- reset_strategy: none / unknown
- auth_roles: anonymous:none
- default_pack: launch-readiness
- stable_routes: /, /api/summary, /api/tool-catalog
- success_criteria: dashboard-overview-renders: expectVisible; dashboard-summary-api-responds: wait; dashboard-tool-catalog-api-responds: wait; dashboard-activity-renders: expectVisible; dashboard-cases-renders: expectVisible; dashboard-catalog-renders: expectVisible; dashboard-reports-renders: expectVisible; dashboard-settings-renders: expectVisible
- latest_trusted_report: .ghost/runs/2026-05-31T21-33-20-619Z/report.json
<!-- ghost-invasion-memory:end -->
