# Health Matrix — DëvSec Industry-Grade Hardening

Source of truth: `reports/codebase-health/devsec-industry-grade/synthesis-2026-06-01.md` (Master Ranked Super-List S-001…S-054). IDs below mirror the synthesis S-IDs. Evidence for each lives in the synthesis row plus its owning lens report under `reports/codebase-health/devsec-industry-grade/`.

Batches are **fix surfaces**, not health domains — one batch is one coherent change that often lifts several lenses at once. Three review stages group the six synthesis phases:

- **Stage A — Trust & Resilience** (batches 01–05): the two non-negotiable red-lines + finding/error integrity. Ship first.
- **Stage B — Experience & Power** (batches 06–13): the UX headline + surfacing the dark local-first superpowers. Gates the second `behavioral-ux-health` pass.
- **Stage C — Foundations & Truth** (batches 14–21): structural seams + honest docs/release.

Target health for every row is **Green** (Green/Yellow where a residual is explicitly accepted). All "current health" values are carried from the synthesis.

## Ordered Repair Targets

| ID | Area | Current | Target | Stage | Dependencies | Batch | Validation path |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S-002 | Eliminate Google Fonts default-path egress (self-host Geist) | Yellow/Red | Green | A·P1 | — | 01-egress-honesty | `grep -r googleapis dashboard/assets` empty; `npm run build` |
| S-007 | Make `--trust` egress disclosure exhaustive & visible (UI + diagram) | Green/Yellow | Green | A·P1 | — | 01-egress-honesty | Diagram lists all 4 egress surfaces; opt-in copy names them |
| S-001 | Dashboard CSRF/Origin harden + re-arm suppression gate (`human_authorized` not hardcoded) | Yellow/Red | Green | A·P1 | — | 02-dashboard-csrf-suppression-gate | `tests/test_dashboard_csrf.py`: forged cross-origin POST 403, cannot suppress critical |
| S-003 | Self-healing SQLite (quarantine + rebuild on corrupt store) | Yellow/Red | Green | A·P2 | — | 03-backend-read-path-resilience | `tests/test_storage_corruption.py`; `uv run pytest` |
| S-006 | Wrap `do_GET` routes in top-level error handling | Yellow | Green | A·P2 | S-003 | 03-backend-read-path-resilience | GET-route-raises test; probe `/api/summary` on corrupt DB |
| S-023 | Guard `cases_json` JSON reads against corrupt rows | Yellow | Green | A·P2 | — | 03-backend-read-path-resilience | inject non-JSON row, assert `dashboard_payload()` survives |
| S-004 | Surface case-decision failures on the Findings tab | Yellow/Red | Green | A·P2 | — | 04-dashboard-error-surfacing | `npm run build`; manual: stop server, Verify shows inline error |
| S-005 | React error boundary + fetch-retry + `/api/summary` shape guard | Yellow | Green | A·P2 | — | 04-dashboard-error-surfacing | `npm run build`; throw in child → boundary catches; Retry on reconnect |
| S-024 | Normalization count-conservation / dropped-findings test | Yellow | Green | A·P2 | — | 05-trust-integrity-tests | `uv run pytest tests/test_normalize.py tests/test_cases.py -v` |
| S-025 | Repo-wide no-egress sentinel + `redact_text` tests + non-skippable `mcp` | Yellow | Green | A·P2 | S-002 (soft) | 05-trust-integrity-tests | `uv run pytest tests/test_no_egress.py tests/test_model.py -v` |
| S-033 | Replace first-run `window.prompt` repo-add with crafted Mistglass form | Yellow/Red | Green | B·P3 | — | 06-replace-window-prompt | `npm run lint && build`; browser add-repo bad-path + empty submit |
| S-034 | Replace `window.prompt` note/close dialogs with inline inputs | Yellow | Green | B·P3 | — | 06-replace-window-prompt | record a decision + close incident in-browser; no native dialog |
| S-040 | Global visible `:focus-visible` indicator on all controls | Yellow/Red | Green | B·P3 | — | 07-accessibility-foundation | tab through every view; axe/focus snapshot |
| S-041 | Shared Dialog primitive: focus-trap + Escape + focus restore (4 modals) | Yellow/Red | Green | B·P3 | — | 07-accessibility-foundation | keyboard open each modal: trap + Escape + focus return; axe dialog |
| S-045 | Skip-to-content link past the sidebar | Yellow | Green | B·P3 | — | 07-accessibility-foundation | Tab from top surfaces skip link; jumps to `<main>` |
| S-047 | a11y test harness (vitest + jest-axe smoke) | Yellow | Green | B·P3 | S-040, S-041 | 07-accessibility-foundation | new vitest run; `toHaveNoViolations` on key views |
| S-019 | Unify severity vocabulary across surfaces (one severity→display map) | Yellow | Green | B·P3 | — | 08-severity-vocabulary | `npm run build`; grep Elevated/Warning resolves to one map |
| S-032 | Domain-language drift polish (incl. `unknown`→`medium` confident-falsehood) | Yellow | Green | B·P3 | — | 08-severity-vocabulary | grep glossary vs catalog; `npm run build && lint` |
| S-036 | Delete orphaned off-Mistglass parallel case UI | Yellow | Green | B·P3 | — | 09-finish-dead-ui-surfaces | `npm run build`; grep no import of deleted files |
| S-037 | Make ⌘K real (focus search/palette) or remove the false hint | Yellow | Green | B·P3 | — | 09-finish-dead-ui-surfaces | press ⌘K in browser: acts, or hint gone |
| S-038 | Differentiate scan-failure feedback into crafted error states | Yellow | Green | B·P3 | — | 09-finish-dead-ui-surfaces | browser scan with missing scanner → actionable error |
| S-044 | Wire or retire dead Activity filter chips | Green/Yellow | Green | B·P3 | — | 09-finish-dead-ui-surfaces | click each chip → filters, or rendered as static labels |
| S-028 | Memoize `App.tsx` derived state | Yellow | Green | B·P3 | — | 10-dashboard-frontend-perf | React Profiler: typing doesn't re-run derived passes |
| S-029 | Trim oversized assets + decide code-splitting | Green/Yellow | Green | B·P3 | — | 10-dashboard-frontend-perf | re-export assets `ls -la`; `npm run build` chunk report |
| S-054 | Sweep token-inlining drift (hardcoded hex/rgba → tokens) | Green/Yellow | Green | B·P3 | — | 10-dashboard-frontend-perf | visual diff; `vite build` |
| S-020 | Canonical case-lifecycle module + reconcile divergent enums | Yellow | Green | B·P4 | — | 11-case-lifecycle | `uv run pytest tests/test_cases.py`; one documented mapping table |
| S-035 | In-progress/verifying lifecycle state + proof-bound closure | Yellow | Green | B·P4 | S-020 (same batch) | 11-case-lifecycle | act→rescan→case shows resolved bound to scan id |
| S-039 | Surface scan-history + arbitrary scan-diff in the UI | Yellow | Green | B·P4 | — | 12-surface-scan-history-trends | history panel fetches; base/head diff request carries both |
| S-042 | Render posture-over-time trend (or remove dead helper) | Yellow/Green | Green | B·P4 | — | 12-surface-scan-history-trends | trend sparkline renders; `npm run build` |
| S-043 | Dashboard surface for the hands-off code-fix flow | Yellow | Green | B·P4 | — | 13-code-fix-dashboard-surface | `tests/test_dashboard_fix_proposals.py`; `npm run build` |
| S-015 | Extract `scan_orchestrator` from `cli.py` (break cli↔dashboard cycle) | Yellow | Green | C·P5 | — | 14-scan-orchestrator-extract | `uv run pytest tests/test_mcp_trigger_scan.py`; cycle scan → 0 |
| S-016 | Split `dashboard_server.py` (route table + extract inline HTML pages) | Yellow/Red | Green | C·P5 | S-003, S-006 | 15-split-dashboard-server | `uv run pytest` (dashboard endpoints); fast import check |
| S-017 | Lift payload assembly out of `storage.py` (remove persistence→scanner inversion) | Yellow/Red | Green | C·P5 | — | 16-storage-payload-and-query-perf | `uv run pytest`; fast import check |
| S-027 | Batch `dashboard_payload` into set-based queries (kill N+1) | Yellow | Green | C·P5 | S-017 (same batch) | 16-storage-payload-and-query-perf | seed 50 repos; sqlite trace query count O(1) in repo count |
| S-018 | Scanner adapter registry (one entry per scanner) | Yellow | Green | C·P5 | S-015 | 17-scanner-adapter-registry | `uv run pytest tests/test_scanners.py tests/test_normalize.py` |
| S-021 | Enable TypeScript strict mode | Yellow/Red | Green | C·P5 | — | 18-type-floor-and-contracts | `cd dashboard-ui && tsc --noEmit` green under strict |
| S-022 | Tighten case-write contracts (trim FE type; typed `save_scan`) | Yellow | Green | C·P5 | S-021 | 18-type-floor-and-contracts | `npm run lint`; `uv run pytest tests/test_cases.py` |
| S-026 | Versioned migrations via `PRAGMA user_version` | Yellow | Green | C·P5 | — | 18-type-floor-and-contracts | migration round-trip test from old-shape fixture DB |
| S-030 | Refresh `.adx` module map for the MCP write subsystem | Yellow | Green | C·P6 | — | 19-adx-and-docs-truth | `json.load(.adx/modules/index.json)`; `ls` each key_file |
| S-031 | Make `.adx` safety/recovery/verification tell the truth (pytest runs) | Yellow | Green | C·P6 | — | 19-adx-and-docs-truth | `uv run pytest -q`; `json.load(.adx/risks.json)`; bump last_verified |
| S-048 | Fix AGENTS.md MCP write-mode understatement | Green/Yellow | Green | C·P6 | — | 19-adx-and-docs-truth | AGENTS.md text matches pyproject entry points + mcp/README |
| S-049 | Refresh stale `.adx` pytest-blocked verification caveat | Yellow | Green | C·P6 | — | 19-adx-and-docs-truth | clean checkout `uv sync --dev && uv run pytest`; rewrite note |
| S-050 | Canonical-vs-working-notes doc boundary in AGENTS.md | Yellow | Green | C·P6 | — | 19-adx-and-docs-truth | AGENTS.md demotes campaign/automation/scratch docs |
| S-010 | Correct mcp/README write-surface tool count (3 → 7–8) | Green/Yellow | Green | C·P6 | — | 19-adx-and-docs-truth | diff mcp/README tool list vs `mcp_server.py` registrations |
| S-051 | Document security-sensitive CLI verbs/flags | Green/Yellow | Green | C·P6 | — | 19-adx-and-docs-truth | `cli --help`; prose covers verbs/flags or notes code-only |
| S-052 | Line-match destructive-surface doc claims to guards | Green/Yellow | Green | C·P6 | — | 19-adx-and-docs-truth | each documented Honey Key claim has a guard assertion |
| S-046 | CHANGELOG/version discipline (`[Unreleased]` + reconcile 104 commits) | Yellow | Green | C·P6 | — | 20-release-honesty | `git log v0.1.0..HEAD`; changelog + version + tag agree |
| S-053 | Keep "real vs not yet" honest after the work lands | Green/Yellow | Green | C·P6 | Stages A,B | 20-release-honesty | re-read table vs shipped behavior in feature-health-final |
| S-008 | Resolve CISA KEV/EPSS wiring gap (wire-or-document) | Green/Yellow | Green | C·P6 | — | 21-integration-and-mcp-hygiene | `uv run pytest tests/test_enrichment.py`; grep callers |
| S-011 | Lock setup-probe `shell=True` invariant + record no-retry decision | Green/Yellow | Green | C·P6 | — | 21-integration-and-mcp-hygiene | `uv run pytest tests/test_setup_runner.py tests/test_managed_tools.py` |
| S-009 | Harden MCP path-leak invariant (startswith→substring) + redaction coverage | Green | Green | C·P6 | — | 21-integration-and-mcp-hygiene | `uv run pytest tests/test_mcp_server.py` |
| S-012 | Close prompt-injection sliver + drop ignored `safe_to_apply` field | Green | Green | C·P6 | — | 21-integration-and-mcp-hygiene | `uv run pytest tests/test_severity_gate.py tests/test_case_followup.py` |
| S-013 | Reset-cache cleanup + reset full-cleanup test | Green | Green | C·P6 | — | 21-integration-and-mcp-hygiene | reset test: report dir removed, tables 0 rows |
| S-014 | Prune terminal `_JOBS` entries after a TTL | Green/Yellow | Green | C·P6 | — | 21-integration-and-mcp-hygiene | `uv run pytest` (rotation/check-status branches) |

## Batch Order

**Stage A — Trust & Resilience**
1. `01-egress-honesty` — S-002, S-007
2. `02-dashboard-csrf-suppression-gate` — S-001
3. `03-backend-read-path-resilience` — S-003, S-006, S-023
4. `04-dashboard-error-surfacing` — S-004, S-005
5. `05-trust-integrity-tests` — S-024, S-025

**Stage B — Experience & Power**
6. `06-replace-window-prompt` — S-033, S-034
7. `07-accessibility-foundation` — S-040, S-041, S-045, S-047
8. `08-severity-vocabulary` — S-019, S-032
9. `09-finish-dead-ui-surfaces` — S-036, S-037, S-038, S-044
10. `10-dashboard-frontend-perf` — S-028, S-029, S-054
11. `11-case-lifecycle` — S-020, S-035
12. `12-surface-scan-history-trends` — S-039, S-042
13. `13-code-fix-dashboard-surface` — S-043

**Stage C — Foundations & Truth**
14. `14-scan-orchestrator-extract` — S-015
15. `15-split-dashboard-server` — S-016
16. `16-storage-payload-and-query-perf` — S-017, S-027
17. `17-scanner-adapter-registry` — S-018
18. `18-type-floor-and-contracts` — S-021, S-022, S-026
19. `19-adx-and-docs-truth` — S-030, S-031, S-048, S-049, S-050, S-010, S-051, S-052
20. `20-release-honesty` — S-046, S-053
21. `21-integration-and-mcp-hygiene` — S-008, S-011, S-009, S-012, S-013, S-014

After Stage B lands, re-run `behavioral-ux-health` (the second, post-repair pass per the Brief) before closing Stage C. At campaign end, run `feature-health-final` to confirm the Brief outcomes and re-check "real vs not yet" honesty (S-053).

## Parking Lot

Real items deliberately **not** in this campaign (per the Excellence Brief "Out of scope"), plus the scout-lens feature candidates held for a post-campaign decision.

**Out of scope (Brief):**
- External Surface scanning (active recon/probing) — stays an honest "Coming Soon"; if ever pursued, its own dedicated campaign.
- Runnable packs (IaC Pack run-mode, broad one-click install/uninstall) — honest placeholders this pass.
- Cross-platform desktop launcher beyond macOS.
- Net-new scanners beyond the current roster.
- Release-ops verification needing online access (branch-protection enforcement, `security.yml` supply-chain bootstrap) — confirm at release, not a campaign repair.

**Feature candidates (scout lenses S-C1…S-C13 in the synthesis) — decide which to pull into a future campaign:**
- Keyboard triage queue (j/k + decision hotkeys); bulk per-severity decisions
- Decision/suppression expiry + re-review reminders; carry-forward triage decisions on recurring cases
- Local-LLM triage backend (Ollama/llama.cpp) — close the loop fully on-machine
- Prompt-injection red-team eval promoted to a shippable artifact
- Local AI scan-diff narration; plain-language "explain this case" rewrite
- Cross-repo fleet rollup; scan scheduling / watch mode
- Local no-cloud shareable posture report (one of the 4 Brief-named features — promote here if desired)
