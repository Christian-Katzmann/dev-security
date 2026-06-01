# Architecture Health Forensic — DëvSec (Security Observatory)

## Executive Finding

DëvSec rests on a genuinely strong domain core and a coherent, honestly-documented
pipeline (`CLI → scanner adapters → normalizer → SQLite → dashboard API → browser UI`),
but its structure concentrates almost all of its weight in four oversized "god modules"
that straddle layer boundaries: `storage.py` (3,515 lines), `dashboard_server.py`
(4,236 lines), `cli.py` (the 199-line `scan_repo` orchestrator that three entry points
reuse), and the React `App.tsx` (4,027 lines). The base layers are clean — `model.py`
has zero intra-package imports and bakes redaction/validation into its dataclasses, and
`catalog.py` is a richly-typed metadata layer — so the dependency direction is mostly
sound. The two real structural risks are: (1) two managed circular dependencies
(`cli ↔ dashboard_server`, `catalog ↔ setup_runner`), both resolved only by deferred
function-local imports, and (2) scanner knowledge scattered across ~5 string-keyed
dispatch sites rather than co-located per adapter as the architecture doc promises, plus
a persistence layer (`storage.dashboard_payload`) that reaches up into scanner-catalog
construction and application-level UI assembly. None of this is broken — 467 tests pass
and the fast import check is clean — but against the Excellence Brief's bar ("add a new
scanner, finding category, or case-lifecycle state without cross-layer surgery"), adding
a scanner today is a documented 5-touchpoint edit, and the case lifecycle has no central
transition module at all. Overall health: **Yellow** — solid and shippable, with concrete
seam-level repairs that would materially de-risk future work.

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security`
- Skill/lens: `architecture-health-forensic`
- Date: `2026-06-01`
- Requested focus: Per the Excellence Brief, the architecture lens audits whether the
  `scanner → normalize → case → storage → dashboard` pipeline is separated cleanly enough
  to add a new scanner, finding category, or case-lifecycle state without cross-layer
  surgery. Read-only diagnostic; single write is this report.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli; print('ok')"` | Pass | Fast import check; `cli` (fan-out 19) imports cleanly. |
| `python3 ... import security_observatory.dashboard_server` | Pass | Imports cleanly despite the `cli ↔ dashboard_server` cycle (resolved by deferred import at `dashboard_server.py:1844`). |
| `python3 ... import security_observatory.mcp_server` (base python3) | Fail (env) | `ModuleNotFoundError: No module named 'mcp.server'` — base interpreter lacks the `mcp` dep; not a code defect. |
| `uv run python -c "... import security_observatory.mcp_server"` | Pass | Imports cleanly under the `uv`-managed env. Confirms env-only failure above. |
| `uv run pytest -q` | Pass | 467 passed in 53.4s. Includes `test_red_team_e2e.py`, `test_mcp_server.py`, `test_normalize.py`, `test_cases.py`, `test_storage`-adjacent coverage. |
| Custom dependency-graph + cycle scan (AST/regex over `src/security_observatory/*.py`) | 2 cycles | `catalog → setup_runner → catalog`; `cli → dashboard_server → cli`. Both real, both broken at runtime by lazy imports. |

## Ranked Health Table

| Rank | Area | Health | Confidence | Evidence | Impact (developer/agent) | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `dashboard_server.py` as a 4,236-line god module mixing routing, business orchestration, and inline HTML/CSS templates | Yellow/Red | High | Single `DashboardHandler` class (`:2028`); `do_GET` (`:2107`) and `do_POST` (`:2392`) are giant if/elif dispatchers that also run business logic inline (per-repo rotation enrichment + secret-name inference inside `do_GET`, `:2126`–`:2200`); two full server-rendered pages embed HTML+CSS as f-strings (`/report/` page at `:1243`, docs page at `:1515`, each with hundreds of lines of `<style>`); 16 intra-package deps. | A new endpoint, report page, or background-job change forces edits deep in a 4k-line file with no route table; the inline HTML is a second, untested rendering path parallel to (and at design-drift risk from) the React Mistglass system. Agents must hold the whole file in context to edit safely. | Extract a route table/dispatch map; move the two server-rendered HTML pages into separate template modules (or render them from the React build); lift the per-repo enrichment in `do_GET` into a payload-assembly function. | `uv run pytest` (dashboard endpoint tests exist); `python-import-cli`. |
| 2 | `storage.py` (3,515 lines) — persistence layer reaches up into scanner-catalog construction and application-level UI assembly | Yellow/Red | High | `from .scanners import scan_profile_catalog, scanner_catalog, security_pack_catalog, tool_catalog` (`:39`); `dashboard_payload()` (`:1323`) assembles the entire UI payload — scan deltas, suppression assembly via `assemble_suppression`, dependency-risk movements, recovery inputs — and embeds live scanner/tool/pack catalogs with install-state detection (`:1505`–`:1509`). Storage has fan-out 9 (`decisions, honey_keys, managed_tools, model, platform_posture, sbom, scanners, silent_upgrades, vex`). | The data store transitively pulls scanner orchestration (`scanners → normalize, ai_static, surface_scanners, managed_tools`), so a "persistence" import drags in half the pipeline. Changing the UI payload shape means editing the SQLite module; changing storage risks the dashboard. Hardest single file for an agent to reason about by layer. | Introduce a thin payload-assembly/service layer between `storage` (raw rows) and `dashboard_server` (HTTP), so `storage` owns schema/queries only and the catalog embedding moves out of the DB class. | `uv run pytest`; `python-import-cli`. |
| 3 | Scanner knowledge scattered across ~5 string-keyed dispatch sites — no central scanner registry/protocol | Yellow | High | Adding a scanner touches: `EXIT_CODES_WITH_FINDINGS` dict (`scanners.py:27`), `run_scanner` branches (`:127`–`:153`), `_command` branches (`:362`–`:438`), `_timeout` branches (`:727`), `normalize()` dispatch (`normalize.py:91`–`:114`), plus `catalog.py` metadata. `docs/adding-scanners.md` honestly lists this as a 5-step edit; `docs/architecture.md:17` claims "Each adapter owns command/timeout/exit-code/sanitizer" but those facets live in *separate* per-scanner branches, not one adapter object. | Directly answers the Brief's risk cue: a new scanner is a multi-file, multi-branch edit with no single seam — easy to add a scanner to `run_scanner` but forget `_timeout` or `EXIT_CODES_WITH_FINDINGS`. Intent ("keep adapters boring", `adding-scanners.md:11`) is good; the structure doesn't enforce co-location. | Collapse the per-scanner branches into one adapter registry (a dataclass/protocol per scanner carrying command, timeout, exit-codes, normalizer) keyed once; `normalize` dispatch then reads from the same registry. | `uv run pytest tests/test_scanners.py tests/test_normalize.py`. |
| 4 | `scan_repo` pipeline orchestrator lives inside `cli.py` (the entry-point/presentation module) yet is the canonical scan path for CLI, MCP, and dashboard | Yellow | High | `scan_repo` is ~199 lines (`cli.py:178`–`:376`) and is the single append-only scan path; MCP imports it directly (`mcp_server.py:29` `from .cli import build_parser, scan_repo`, used at `:578`/`:644`), dashboard lazy-imports it (`dashboard_server.py:1844`). The reuse is deliberate and well-commented (`mcp_server.py:572`–`:620`: "Reuses the CLI parser so every flag scan_repo reads exists"). | The most load-bearing pipeline function sits in the CLI module, so two non-CLI consumers must import the CLI to scan. This is the root of the `cli ↔ dashboard_server` cycle and the `mcp → cli` reach. Reuse is the right call; its *location* forces the coupling. | Move `scan_repo` (+ `build_parser`/profile resolution it needs) into a dedicated `scan_orchestrator`/`pipeline` module that `cli`, `mcp_server`, and `dashboard_server` all import — breaking the cycle and clarifying the application layer. | `uv run pytest tests/test_mcp_trigger_scan.py`; `python-import-cli`. |
| 5 | Two circular dependencies, both masked by deferred function-local imports | Yellow | High | `cli → dashboard_server` (top-level `cli.py:22`) and `dashboard_server → cli` (lazy `dashboard_server.py:1844`); `setup_runner → catalog` (top-level `setup_runner.py:40`) and `catalog → setup_runner` (lazy `catalog.py:685`, with an explicit comment: "Lazy import: setup_runner imports catalog at module top, so the…"). Cycle scan over all modules found exactly these two. | Lazy imports work but hide the coupling from static tools and new readers; they are a fragility signal (re-ordering a top-level import or moving a function can resurface an `ImportError`). The `catalog ↔ setup_runner` cycle suggests tool-config reading is split across the catalog and its consumer. | Break `cli ↔ dashboard` via the orchestrator extraction (Rank 4); break `catalog ↔ setup_runner` by moving `read_tool_config` into a small config module both depend on. | `python-import-cli`; re-run the cycle scan to confirm zero cycles. |
| 6 | Case lifecycle has no central state-machine / transition module | Yellow | Medium | Lifecycle is expressed as decision statuses, not states: `CASE_DECISION_STATUSES = {"verified","false_positive","accepted_risk","fixed"}` and `SUPPRESSING_DECISION_STATUSES` (`decisions.py:10`–`:11`); `SecurityCase.status` is a free `str | None` (`model.py:187`) and `action_level` is validated against `{fix_now,verify,watch,info}` in `__post_init__` (`model.py:163`). No module owns "open → in-progress → verifying → closed" transitions. | The Brief's excellence target (a visible case moving through lifecycle states with the verification that closed it) has no architectural home; adding a new lifecycle state today means touching `decisions`, `model` validation, suppression assembly, and the UI without a single seam. (Domain-language and data-contract lenses own the vocabulary side; flagged here as the structural gap.) | When the lifecycle work lands, introduce one `lifecycle.py` owning the state set + allowed transitions, consumed by `cases`, `decisions`, `storage`, and the dashboard. | `uv run pytest tests/test_cases.py tests/test_severity_gate.py`. |
| 7 | React `App.tsx` is a 4,027-line root component | Yellow | High | `App.tsx` 4,027 lines and `dashboardData.ts` 2,314 lines dominate a 31-file UI tree; next-largest components are 700–1,000 lines (`RotationTriggerFlow.tsx` 1,008, `RotationStatusCard.tsx` 870). Components *are* extracted, but the root carries an outsized share of view/state logic. | Mirrors the backend god-module pattern: most UI changes route through one enormous file, raising merge/regression risk and making it hard for an agent to edit one view safely. (Detailed UI-craft findings belong to behavioral-ux / design-system lenses; flagged here as the structural shape.) | Decompose `App.tsx` into view-level route components + a small app shell; split `dashboardData.ts` by domain (cases, rotation, catalog, history). | `cd dashboard-ui && npm run lint && npm run build`. |
| 8 | Domain core: `model.py` and `catalog.py` are clean, typed, well-bounded base layers | Green | High | `model.py` has zero intra-package imports (true leaf; fan-in 18 — the shared kernel) and enforces invariants in dataclass `__post_init__` (redaction, severity/confidence/action-level normalization, `model.py:160`–`:175`). `catalog.py` uses `StrEnum` types + frozen dataclasses for tool kind/category/lifecycle/install-state/policy/capabilities (`:11`–`:301`). Generated assets cleanly separated (`.gitignore:14` `dashboard/assets/`, `:16` `dashboard-ui/dist/`). | Dependency direction at the base is correct: everything depends on `model`, `model` depends on nothing. This is the foundation that makes the seam-level repairs above tractable rather than a rewrite. | None required; preserve `model` as a pure leaf and keep new domain types in `catalog`'s typed style. | `python-import-cli`; `uv run pytest tests/test_model.py`. |
| 9 | Pipeline isolation + entry-point ownership are sound and documented | Green | High | `docs/architecture.md` accurately states the pipeline and "Scanner failures are isolated… marks scan partial but does not destroy the run" — borne out by `run_scanner` returning empty `ScannerResult` on unavailable/timeout/tampered binaries (`scanners.py:158`–`:186`, `:207`–`:218`). Entry points are clear: `cli.main` (`:100`), `mcp_server` (FastMCP), `dashboard_server.serve_dashboard`. MCP→CLI reuse is intentional and documented, not an accident. | A fresh agent can find the entry points and trust the doc. Failure isolation means a missing scanner degrades honestly rather than corrupting history — aligns with the Brief's trust bar. | None; keep `architecture.md` in sync as the orchestrator/registry repairs land. | `uv run pytest tests/test_scanners.py`. |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| Two server-rendered HTML pages inside the Python server, parallel to the React UI | `dashboard_server.py:1243` (`/report/` export page) and `:1515` (`_docs_page_shell` docs page), each a full `<!doctype html>` + inline `<style>` block | This is a second rendering surface with its own CSS, disconnected from the Mistglass design system in `dashboard-ui/` / `DESIGN.md`. Design changes can silently skip it; it is largely untested vs the React tree. Not surfaced in the module map (which describes `dashboard_server` only as "API endpoints… report exports"). |
| `dashboard_payload()` is the real cross-layer hub | `storage.py:1323`, embedding scanner/tool/pack catalogs (`:1505`–`:1509`) and calling `assemble_suppression` from `decisions` | The module map lists `storage.py` as "owns the SQLite schema and dashboard payload" but understates that this one method couples persistence to scanner orchestration and suppression logic — the densest cross-layer point in the repo. |
| `scan_repo` is a shared service hiding in the CLI | `cli.py:178`; imported by `mcp_server.py:29` and lazily by `dashboard_server.py:1844` | The module map frames `cli.py` as "wires command-line behavior and dashboard startup," not as the home of the canonical scan pipeline that two other subsystems depend on. An agent told to edit "just the CLI" could break MCP/dashboard scans. |
| `catalog ↔ setup_runner` cycle with a load-bearing lazy import | `catalog.py:685` (comment-documented lazy `read_tool_config` import); `setup_runner.py:40` top-level catalog import | Hidden coupling: tool-config reading is split between the catalog and its consumer. Static analysis won't see it; a refactor that moves `read_tool_config` to module scope reintroduces an `ImportError`. |

## Top Repair Targets

1. **Extract a `scan_orchestrator` / pipeline module from `cli.py`.** Move `scan_repo`
   (and the parser/profile resolution it requires) into a dedicated application-layer
   module that `cli`, `mcp_server`, and `dashboard_server` all import. This single move
   breaks the `cli ↔ dashboard_server` cycle, removes the `mcp → cli` reach, and gives
   the pipeline a true home distinct from any entry point. Highest leverage: it fixes
   Ranks 4 and 5 at once and makes the scan path agent-legible.

2. **Split `dashboard_server.py` and lift the catalog/payload assembly out of `storage.py`.**
   Introduce a route table for `do_GET`/`do_POST`, move the two inline HTML pages into
   their own template modules (or render from the React build), and pull the
   per-repo enrichment and catalog-embedding into a payload-assembly/service layer so
   `storage.py` owns schema + queries only. This addresses Ranks 1 and 2, the two
   highest-risk god modules, and removes the persistence→scanner layer inversion.

3. **Collapse scanner knowledge into a single adapter registry.** Replace the parallel
   string-keyed branches (`run_scanner`, `_command`, `_timeout`, `EXIT_CODES_WITH_FINDINGS`,
   `normalize` dispatch) with one registry entry per scanner (command, timeout, exit-codes,
   normalizer), so adding a scanner is one co-located edit. Update `docs/adding-scanners.md`
   and `docs/architecture.md` to match. This directly satisfies the Excellence Brief's
   architecture risk cue (Rank 3) and is a prerequisite for any future scanner additions.

## SocratiCode Value

Not used. The architecture lens here was well-served by direct inspection: a custom
AST/regex dependency-graph + cycle scan over `src/security_observatory/*.py` produced the
fan-in/fan-out tables and pinpointed both circular dependencies precisely, and exact file
reads confirmed every claim against real line numbers. Per the suite's SocratiCode
cost-discipline rule, reflexive structural-map queries were unnecessary once the module set
(34 Python files) was small enough to graph directly, and SocratiCode is not treated as
proof in any case. If a broader cross-language blast-radius view (Python ↔ React payload
contract) were needed later, SocratiCode `codebase_flow`/`codebase_impact` would be the
right tool; it was not required to reach these findings.

## Limits

- **MCP import under base python3 could not be verified directly** (`No module named
  'mcp.server'`); confirmed clean only via `uv run`. The `uv`-managed environment is
  authoritative per AGENTS.md, so this is recorded as an environment limit, not a defect.
- **No runtime/behavioral architecture probing.** Per AGENTS.md and `.adx/risks.json`, I
  did not start the dashboard server, run `security-scan`, the installer, desktop
  launchers, or any process-kill/Honey-Key path. Layer behavior is inferred from static
  reads + the passing test suite, not from a live request trace.
- **Cycle detection covered only intra-package imports** within `src/security_observatory/`
  (top-level + `from . import` forms). Dynamic imports beyond the two function-local ones
  I located, or imports via `importlib`/string names, would not be caught by the scan.
- **God-module line counts are structural signals, not severity verdicts.** Large files can
  be cohesive; the Yellow/Red labels rest on the *cross-layer mixing* evidence (routing +
  business logic + inline HTML in one class; persistence importing scanner orchestration),
  not size alone.
- **Sibling-lens boundaries respected.** Case-lifecycle *vocabulary* (Rank 6) and React
  *UI craft* (Rank 7) are flagged here only as structural seams; their full treatment
  belongs to the domain-language / data-contract and behavioral-ux / design-system lenses.
