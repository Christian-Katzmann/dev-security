# Synthesis — devsec-industry-grade (cluster: structure-and-quality)

**Date:** 2026-06-01
**Lenses synthesized:** 6 forensic reports (structure-and-quality cluster)
**Excellence Brief:** `/Users/christiankatzmann/Dev/Projects/dëv-security/reports/codebase-health/devsec-industry-grade/excellence-brief.md`
**Reviewed by second agent:** No (cluster pass; review at merge)

Cluster lenses: `architecture-health`, `domain-language-health`, `data-contract-type-health`, `ai-maintainability-health`, `test-confidence-health`, `performance-health`. This sub-synthesis owns the 95 ledger entries whose `lens` field is one of those six. The merge step renumbers S-IDs globally; numbering here is local to this cluster.

## Executive Finding

DëvSec has a genuinely clean domain *core* — `model.py` is a pure, zero-import leaf that bakes redaction, severity normalization, and action-level whitelisting into its dataclasses; `catalog.py` is richly typed; the trust-critical write path (`case_resolutions.v1` → `set_case_decision` severity gate) is hand-validated end to end and proven by fail-on-break tests; case-building is O(n log n); and SQLite is comprehensively indexed. The single biggest pattern across this cluster is that almost all of the structural weight and almost all of the *enforcement* weakness sits in a thin outer ring around that good core: four oversized god modules (`dashboard_server.py` ~4,236 lines, `storage.py` ~3,515, `App.tsx` ~4,027, `dashboardData.ts` ~2,314) concentrate routing + business logic + inline HTML + UI-payload assembly + per-repo query fan-out in single files; scanner knowledge is scattered across ~5 string-keyed dispatch sites instead of one adapter registry; the case lifecycle has no central state machine and is named by two divergent four-value enums plus a third diff-axis; the type floor is soft (TS not in `strict`/`strictNullChecks`, so the careful `?`/`| null` annotations are decorative); and the `.adx` agent-guidance layer is frozen at 2026-05-12, blind to the entire MCP/fix-proposal write subsystem added through 2026-05-31. None of this is broken today — 467 tests pass, no Red in the cluster — but every one of these is the same failure shape: *a sound invariant living in a place that does not enforce or advertise it.* The highest-leverage repairs are therefore structural seams (extract the scan orchestrator, split the god modules, build one scanner registry, one case-lifecycle module, turn on TS strict, refresh `.adx`) because each lifts several lenses' findings at once.

## Brief Coverage

Only Brief items this cluster's lenses bear on are listed. UX, privacy, permission, integration, and edge-state items are owned by sibling clusters and omitted here.

| Brief item | Type | Findings | Coverage |
| --- | --- | --- | --- |
| Pipeline separated enough to add a scanner / finding category / lifecycle state without cross-layer surgery (architecture cue) | outcome | F-architecture.RH.1, RH.2, RH.3, RH.4, RH.5, RH.6, US.1, US.2, US.3, US.4 (S-001, S-002, S-003, S-004) | Strong |
| `raw finding` vs `case`, `severity` vs `confidence`, "clear within scan scope" vs "secure", lifecycle states consistent across CLI/dashboard/MCP/docs (domain-language cue) | outcome | F-domain-language.RH.1, RH.2, RH.9, RH.10 (S-005, S-006, kept-strong rows) | Strong |
| Normalized finding shape, case schema, lifecycle transitions, `case_resolutions.v1` typed/validated/versioned so malformed scanner output can't corrupt history (data-contract cue) | outcome | F-data-contract-type.RH.1, RH.2, RH.4, RH.5, RH.6, RH.8, RH.9 (S-007, S-008, S-009, S-012) | Strong |
| Trust-critical paths covered by tests that fail if the guarantee breaks (test-confidence cue) | outcome | F-test-confidence.RH.1, RH.2, RH.5, RH.6, RH.7, RH.8 (S-010, S-011) | Strong |
| Real-repo scan + dashboard stay snappy on a large history store; no O(n²) case-building; no UI lock on big finding sets; fast SQLite (performance cue) | outcome | F-performance.RH.1, RH.2, RH.3, RH.4, RH.6, RH.7 (S-013, S-014, S-015) | Strong |
| Fresh agent can extend DëvSec safely via `.adx` manifests/registry/risks/recovery, still accurate after the campaign (ai-maintainability cue) | outcome | F-ai-maintainability.RH.1, RH.2, RH.3, RH.4, RH.6 (S-016, S-017) | Strong |
| Unsafe AI write eliminated (no repo edit / evidence exfil / auto-suppress without audited human confirmation) | failure-mode | F-data-contract-type.RH.6, RH.7; F-test-confidence.RH.6, RH.7 | Strong (verified clean — no repair owed by this cluster) |
| Dropped findings (a real scanner result that never becomes a case/raw finding) | failure-mode | F-test-confidence.RH.1; F-data-contract-type.RH.8 (S-010) | Partial (invariant untested at the count-conservation level; no live drop found) |
| Silent egress on any default path | failure-mode | F-test-confidence.RH.2, RH.9 (S-011) | Partial (proven per-function; no repo-wide sentinel — sibling privacy cluster owns the Google-Fonts egress itself) |
| Confident falsehood (a partial feature shown as complete; a case overstating certainty) | failure-mode | F-domain-language.RH.8; F-data-contract-type.RH.3; F-ai-maintainability.RH.3, RH.4 (S-006/S-009/S-017) | Partial (`unknown`→`medium` confidence coercion and stale "pytest can't run" notes are the in-cluster slivers) |

## Master Ranked Super-List

Deduped, cross-lens-aware. Ranked weakest / highest-structural-risk first. S-IDs local to this cluster. "Cross-refs" names sibling lenses that observed the same item. Several rows are explicitly *one structural fix that lifts multiple lenses* — noted in the mapping/validation columns.

| ID | Repair item | Owning lens | Cross-refs | Health | Confidence | Brief mapping | Suggested validation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S-001 | Extract a `scan_orchestrator`/pipeline module from `cli.py`: move `scan_repo` (+ parser/profile resolution) into an application-layer module that `cli`, `mcp_server`, `dashboard_server` all import. Breaks the `cli ↔ dashboard_server` cycle and the `mcp → cli` reach in one move. | architecture-health | ai-maintainability (module map), performance | Yellow | High | architecture cue (add-scanner/lifecycle without cross-layer surgery) | `uv run pytest tests/test_mcp_trigger_scan.py`; fast import check; re-run cycle scan → 0 cycles |
| S-002 | Split `dashboard_server.py` (~4,236 lines): introduce a route table for `do_GET`/`do_POST`/`do_DELETE`, move the two inline server-rendered HTML pages (`/report/` :1243, docs :1515) into template modules or render from the React build, and lift per-repo enrichment out of `do_GET`. Same god-module flagged by 3 lenses. | architecture-health | ai-maintainability (RH.5/US), performance, error-edge-state (sibling cluster) | Yellow/Red | High | architecture cue; "finished, not prototype" | `uv run pytest` (dashboard endpoint tests); fast import check |
| S-003 | Lift catalog/UI-payload assembly out of `storage.py` (~3,515 lines) into a payload-assembly/service layer so `storage` owns schema + queries only; remove the persistence→scanner-orchestration import inversion (`storage` importing `scan_profile_catalog`/`scanner_catalog`/etc.). | architecture-health | performance (dashboard_payload fan-out), data-contract, ai-maintainability | Yellow/Red | High | architecture cue | `uv run pytest`; fast import check |
| S-004 | Collapse scanner knowledge into one adapter registry: replace the parallel string-keyed branches (`run_scanner`, `_command`, `_timeout`, `EXIT_CODES_WITH_FINDINGS`, `normalize` dispatch) + `catalog` metadata with one dataclass/protocol entry per scanner; update `docs/adding-scanners.md` + `docs/architecture.md`. Directly answers the Brief's add-a-scanner cue. | architecture-health | ai-maintainability, data-contract (normalize boundary) | Yellow | High | architecture cue (single-seam scanner add) | `uv run pytest tests/test_scanners.py tests/test_normalize.py` |
| S-005 | Unify severity vocabulary across surfaces: one shared severity→display map (`high→Elevated`, `medium→Warning`, …) consumed by the dashboard, and an explicit decision on whether the MCP/CLI agent persona speaks display words or internal severities — so a user never reads "Elevated" in the UI and "high" via the handoff for one case. | domain-language-health | behavioral-ux (sibling), data-contract | Yellow | High | domain-language cue (never translate the same word twice) | `cd dashboard-ui && npm run build`; grep `Elevated`/`Warning` resolves to one map |
| S-006 | Build one canonical case-lifecycle module + reconcile its vocabulary: a `lifecycle.py` owning the state set + allowed transitions (consumed by `cases`/`decisions`/`storage`/dashboard), and reconcile the two divergent four-value enums (MCP `open/verified/accepted_risk/resolved` vs storage `verified/false_positive/accepted_risk/fixed`) plus the `new/recurring/resolved` diff-axis; document the `fixed`/`false_positive`→`resolved` presentation collapse. Merges the architectural gap and the naming drift — they are the same missing seam. | architecture-health | domain-language (RH.2), data-contract, feature (sibling) | Yellow | High | architecture + domain-language cues; "case moves open→verifying→closed" outcome | `uv run pytest tests/test_cases.py tests/test_severity_gate.py`; one documented mapping table |
| S-007 | Enable TypeScript `strict` (≥ `strictNullChecks` + `noImplicitAny`) in `dashboard-ui/tsconfig.json`, fix surfaced errors, keep `tsc --noEmit` green; optionally add a typed runtime guard at the 2–3 `await response.json()` boundaries. Highest-leverage type fix: converts the existing zero-`any` + `?`/`| null` discipline from decorative into enforced, and is the safety net that makes S-008 safe. | data-contract-type-health | test-confidence (frontend coverage), error-edge-state (no shape guard), behavioral-ux | Yellow/Red | High | data-contract cue; confident-falsehood (false type confidence) | `cd dashboard-ui && npm run lint` stays green after enabling strict |
| S-008 | Tighten the two case-write contracts: trim the frontend `SecurityCase` type to the real wire shape and delete the ~10 dead aliases the backend never emits (`plain_title`, `why_matters`, `bucket`, `action_bucket`, …); narrow `save_scan`'s `cases` param to `list[SecurityCase]` (or route dicts through `SecurityCase(**case)`) so redaction/validation can never be bypassed. Merges the data-contract drift rows and the domain-language implicit-API-shape row — same root cause. | data-contract-type-health | domain-language (RH.7, US.4) | Yellow | High | data-contract cue; confident-falsehood | `cd dashboard-ui && npm run lint`; `uv run pytest tests/test_cases.py` |
| S-009 | Guard the `cases_json` JSON reads (storage.py :1357/:1527/:2781/:2843) with the `except (TypeError, json.JSONDecodeError)` pattern already present at :2166, so one corrupt/hand-edited row degrades to a warning instead of crashing the dashboard payload + the shared MCP read. Hardens the Brief's named corrupt-SQLite edge state. | data-contract-type-health | error-edge-state (sibling cluster), performance (shared payload) | Yellow | High | data-contract cue; corrupt-SQLite edge state | inject a non-JSON `cases_json` row, assert `dashboard_payload()` still returns; `uv run pytest` |
| S-010 | Add a normalization count-conservation / dropped-findings test: a multi-finding, multi-scanner fixture asserting total-in == total-accounted-for through normalize→case, plus a malformed-but-nonempty payload test asserting it surfaces as degraded (not silently zero). `test_normalize.py` is only 3 single-input cases today. Closes the "dropped findings" non-negotiable at the test level. | test-confidence-health | data-contract (normalize boundary), integration (sibling) | Yellow | High | dropped-findings failure-mode | `uv run pytest tests/test_normalize.py tests/test_cases.py -v` |
| S-011 | Add a repo-wide no-egress sentinel test + harden `redact_text`/`model.py` coverage + make the MCP-guarded trust tests non-skippable. One sentinel monkeypatches `socket`/`urlopen` to raise, runs a full default-path scan→case-build, asserts zero outbound attempts (closes silent-egress against *future* code); expand the 13-line `test_model.py` to assert redaction removes secret values while keeping locators; pin the `mcp` extra so the write-guard/injection/clean-room/red-team tests can't silently skip. | test-confidence-health | privacy (sibling cluster owns the live egress), data-contract | Yellow | High | silent-egress + confident-falsehood failure-modes | `uv run pytest tests/test_no_egress.py tests/test_model.py -v`; assert `mcp` importable |
| S-012 | Adopt `PRAGMA user_version` as the single migration counter; gate destructive table rebuilds on a version bump instead of the current string-sentinel substring match in `sqlite_master.sql`; document migration order. Makes the schema contract "versioned" per the Brief and traceable for recovery. | data-contract-type-health | architecture (storage seams), error-edge-state | Yellow | Medium | data-contract cue (versioned contracts) | `uv run pytest` (storage tests); add a migration round-trip test from an old-shape fixture DB |
| S-013 | Batch `dashboard_payload()` into set-based queries: replace the per-repo loop's ~12–18 individual lookups (previous-scan, 5-query dependency delta, per-scan findings, trust, posture, resolution runs) with `... WHERE scan_id IN (...)` / `run_id IN (...)` pulls assembled in memory; eliminate the per-run `case_resolution_items` N+1. The single most-hit endpoint; latency grows linearly with repo count today. Naturally co-lands with S-003. | performance-health | architecture (storage cross-layer hub) | Yellow | High | performance cue (snappy on large history store) | seed 50 repos × deep history; trace query count is O(1) in repo count via sqlite3 trace in pytest |
| S-014 | Memoize derived state in `App.tsx`: wrap `scopedSummary`, `activeCases`, `posture`, `buildActivity` in `useMemo` keyed on `[summary, target]` so search-box typing stops re-running all derived passes on a 4,028-line root; consider splitting so search state doesn't re-render the whole shell. Protects the headline keyboard-first triage path. Co-lands with the `App.tsx` decomposition. | performance-health | architecture (App.tsx monolith RH.7), behavioral-ux, design-system | Yellow | High | performance cue (no UI lock on big finding sets) | React Profiler on a large seeded summary; confirm typing doesn't re-run `filterSummaryByTarget`/`buildActivity` |
| S-015 | Trim oversized static assets and decide code-splitting: downscale the 2 MB favicon/apple-touch-icon and 607 KB logo to KB-scale; optionally lazy-load rarely-first views (Agent Lab, Catalog, Rotation) behind `React.lazy`; confirm static-asset cache headers. Low user impact on localhost but the "finished, not just present" bar wants it. | performance-health | architecture (App.tsx imports), design-system | Green/Yellow | High | performance cue; "finished" outcome | re-export assets, `ls -la`; `npm run build` chunk report; check server cache headers |
| S-016 | Refresh the `.adx` module map to include the MCP / fix-proposal / case-followup / decisions write subsystem: add a `mcp-write-surface` module entry (`mcp_server.py`, `mcp/`, `fix_proposals.py`, `case_followup.py`, `decisions.py`) with `key_files`, matching tests, the new risk id, and a one-line pointer to `mcp/README.md` for the boundary. The canonical landmark AGENTS.md points to is blind to this subsystem. | ai-maintainability-health | architecture, permission (sibling) | Yellow | High | ai-maintainability cue (fresh agent can extend safely) | `python3 -c "import json;json.load(open('.adx/modules/index.json'))"`; `ls` each new key_file |
| S-017 | Make `.adx` safety/recovery contracts tell the truth: add a `mcp-write-surface` risk-register entry (+ `devsec-mcp-rw`/`land_fix`/`propose_fix` to `dangerous_command_patterns`); rewrite `recovery.md`'s "Pytest Is Missing" + `verification.json`'s "currently blocked" notes (pytest runs: 467 pass); bump `adx.json` `last_verified` after the above; add one AGENTS.md line mapping "Security Observatory" ↔ "DëvSec". The repo's strongest safety net is currently described as unavailable. | ai-maintainability-health | architecture, domain-language (brand dual-identity) | Yellow | High | ai-maintainability cue; confident-falsehood (docs assert false state) | re-run `uv run pytest -q`; `python3 -c "import json;json.load(open('.adx/risks.json'))"`; confirm `last_verified` newer than newest source mtime |
| S-018 | Polish residual domain-language drift: collapse `action_level`/`attention bucket` to one name + one encoding (drop the `fix_now`/`fix-now` shim); rename the internal `findings` route/`TabId`/`FindingsView` to `cases`; fix `glossary.md` Tool Catalog to mirror `tool-catalog.md`'s two axes (`lifecycle` vs `install_state`) with real value names; qualify the `watch` PostureTier band so it doesn't collide with action-level `watch`; document or honestly render the `unknown`→`medium` case-confidence coercion. Low-cost naming hygiene that removes documented-but-fictional vocabulary. | domain-language-health | data-contract, ai-maintainability, documentation (sibling) | Yellow | High | domain-language cue; confident-falsehood (`unknown`→`medium`) | `grep` glossary values vs `catalog.py`/`tool-catalog.md`; `cd dashboard-ui && npm run build && npm run lint` |

## Ledger Coverage

One row per cluster ledger ID. 95 IDs total. RH rows that are Green/strong with "None required" repairs are marked `cross-ref` to the strongest row that carries them or kept as their own confirmation row; TR rows map to the S-ID that absorbed that lens's repair; US rows map to the S-ID whose fix removes/addresses that surface.

| Ledger ID | Outcome | Mapped to | Note |
| --- | --- | --- | --- |
| F-architecture.RH.1 | own | S-002 | `dashboard_server.py` god module |
| F-architecture.RH.2 | own | S-003 | `storage.py` cross-layer reach |
| F-architecture.RH.3 | own | S-004 | scattered scanner dispatch → registry |
| F-architecture.RH.4 | own | S-001 | `scan_repo` in CLI → orchestrator |
| F-architecture.RH.5 | merged | S-001 | both cycles broken by the orchestrator extraction (`cli↔dashboard`) + config-module split for `catalog↔setup_runner`; faithful because S-001 names the cycle-break as its primary effect |
| F-architecture.RH.6 | own | S-006 | no central case-lifecycle state machine |
| F-architecture.RH.7 | cross-ref | S-014 | `App.tsx` 4,027-line root — structural shape; decomposition co-lands with the memoization fix |
| F-architecture.RH.8 | cross-ref | S-003 | clean `model.py`/`catalog.py` core (Green) — the foundation S-003 preserves; no repair owed |
| F-architecture.RH.9 | cross-ref | S-001 | pipeline isolation + entry points sound (Green); keep `architecture.md` in sync as S-001 lands |
| F-architecture.US.1 | cross-ref | S-002 | two inline server-rendered HTML pages — removed/relocated by S-002 |
| F-architecture.US.2 | cross-ref | S-003 | `dashboard_payload()` cross-layer hub — lifted by S-003 |
| F-architecture.US.3 | cross-ref | S-001 | `scan_repo` shared service hiding in CLI — relocated by S-001 |
| F-architecture.US.4 | cross-ref | S-001 | `catalog↔setup_runner` lazy-import cycle — broken alongside S-001 (config-module split) |
| F-architecture.TR.1 | own | S-001 | top repair = extract orchestrator |
| F-architecture.TR.2 | merged | S-002 | TR.2 pairs the dashboard split + storage lift; S-002 owns the split, S-003 the storage lift; faithful because both are named in this row's repair and tracked as sibling S-IDs |
| F-architecture.TR.3 | own | S-004 | top repair = scanner adapter registry |
| F-domain-language.RH.1 | own | S-005 | severity vocabulary splits per surface |
| F-domain-language.RH.2 | cross-ref | S-006 | two divergent case-state enums — reconciled by the lifecycle module |
| F-domain-language.RH.3 | cross-ref | S-018 | glossary catalog vocabulary contradicts canonical spec |
| F-domain-language.RH.4 | cross-ref | S-018 | `action_level`/`attention bucket`, `fix_now`/`fix-now` |
| F-domain-language.RH.5 | cross-ref | S-018 | Cases surface still routed/filed as `findings` |
| F-domain-language.RH.6 | cross-ref | S-018 | `watch` overloaded across three meanings |
| F-domain-language.RH.7 | cross-ref | S-008 | implicit `SecurityCase` API shape + dead aliases — same root as the data-contract trim |
| F-domain-language.RH.8 | cross-ref | S-018 | `unknown` confidence coerced to `medium` — honest-render decision folded into the naming-hygiene row |
| F-domain-language.RH.9 | cross-ref | S-005 | "clear within scan scope" vs "secure" (Green) — kept-strong; protect with a copy test when severity map lands |
| F-domain-language.RH.10 | cross-ref | S-005 | `raw finding` vs `case` core distinction (Green) — kept-strong; only residual is the route name in S-018 |
| F-domain-language.US.1 | cross-ref | S-018 | "Attention bucket" undocumented UI name |
| F-domain-language.US.2 | cross-ref | S-006 | MCP `SUPPORTED_CASE_STATUSES` presentation enum — documented by the lifecycle reconciliation |
| F-domain-language.US.3 | cross-ref | S-018 | glossary install-state list code doesn't implement |
| F-domain-language.US.4 | cross-ref | S-008 | dead case-field aliases on the API boundary |
| F-domain-language.TR.1 | own | S-005 | top repair = unify severity vocabulary |
| F-domain-language.TR.2 | cross-ref | S-006 | top repair = reconcile case-state vocabulary |
| F-domain-language.TR.3 | cross-ref | S-018 | top repair = glossary catalog + naming hygiene |
| F-data-contract-type.RH.1 | own | S-007 | TS not in strict mode |
| F-data-contract-type.RH.2 | own | S-009 | `cases_json` read with no JSON-decode guard |
| F-data-contract-type.RH.3 | own | S-008 | frontend `SecurityCase` drifts from wire shape |
| F-data-contract-type.RH.4 | merged | S-008 | `save_scan` raw-dict bypass; merged into the case-write-contract row because both tighten the same un-enforced case shape — faithful, S-008 names both fixes |
| F-data-contract-type.RH.5 | own | S-012 | no `PRAGMA user_version` schema versioning |
| F-data-contract-type.RH.6 | cross-ref | S-008 | `case_resolutions.v1` typed/gated/versioned (Green) — verified clean; keep single-validator invariant when S-008 edits the case contract |
| F-data-contract-type.RH.7 | cross-ref | S-008 | `set_case_decision` severity gate (Green) — verified clean; preserve through S-008 |
| F-data-contract-type.RH.8 | cross-ref | S-010 | normalization boundary (Green) — the count-conservation test backstops it |
| F-data-contract-type.RH.9 | cross-ref | S-012 | findings columns vs dataclass one-source-of-truth (Green) — preserved by versioned migrations |
| F-data-contract-type.RH.10 | cross-ref | S-008 | `decisions.py` VEX/identity normalization (Green) — adjacent to the case contract; no repair owed |
| F-data-contract-type.US.1 | cross-ref | S-009 | `cases_json` denormalized blob — its fragility is the JSON-guard target |
| F-data-contract-type.US.2 | cross-ref | S-007 | frontend trusts `response.json()` with no runtime validation — strict mode + optional runtime guard |
| F-data-contract-type.US.3 | cross-ref | S-008 | `save_scan` raw-dict branch surface |
| F-data-contract-type.US.4 | cross-ref | S-012 | string-sentinel migration detection |
| F-data-contract-type.TR.1 | own | S-007 | top repair = enable TS strict |
| F-data-contract-type.TR.2 | cross-ref | S-009 | top repair = guard `cases_json` reads |
| F-data-contract-type.TR.3 | cross-ref | S-008 | top repair = tighten case-write contracts |
| F-test-confidence.RH.1 | own | S-010 | normalization fidelity / dropped-findings invariant |
| F-test-confidence.RH.2 | own | S-011 | no repo-wide no-egress sentinel |
| F-test-confidence.RH.3 | cross-ref | S-011 | `test_model.py` 13-line stub — redaction coverage folded into S-011 |
| F-test-confidence.RH.4 | deferred | brief out-of-scope: sibling-lens boundary — frontend component tests deferred to behavioral-ux / design-system-accessibility per the report's own no-sibling-overlap note | frontend `dashboard-ui` unit/component tests |
| F-test-confidence.RH.5 | cross-ref | S-011 | Honey Key hashing/placement guards (Green) — fail-on-break anchor; the non-skippable-`mcp` fix in S-011 protects it |
| F-test-confidence.RH.6 | cross-ref | S-011 | MCP suppression gate + prompt-injection (Green) — verified clean; S-011 keeps it from silently skipping |
| F-test-confidence.RH.7 | cross-ref | S-011 | AI fix-proposal clean-room fence (Green) — verified clean; same non-skippable protection |
| F-test-confidence.RH.8 | cross-ref | S-011 | destructive-rotation confirmation + lifecycle (Green) — kept-strong regression anchor |
| F-test-confidence.RH.9 | cross-ref | S-011 | per-function no-egress coverage (Green/Yellow) — completed by the repo-wide sentinel |
| F-test-confidence.RH.10 | cross-ref | S-011 | no hidden-failure debt (Green) — the `importorskip("mcp")` risk is what S-011's pin closes |
| F-test-confidence.US.1 | cross-ref | S-011 | MCP tests conditionally skippable — directly the pin-`mcp` fix |
| F-test-confidence.US.2 | cross-ref | S-010 | normalization tested on single-finding inputs only |
| F-test-confidence.US.3 | cross-ref | S-011 | `redact_text` thinly tested |
| F-test-confidence.TR.1 | own | S-010 | top repair (a) count-conservation; (b) no-egress sentinel split across S-010/S-011 |
| F-test-confidence.TR.2 | cross-ref | S-011 | top repair = make MCP-guarded trust tests non-skippable |
| F-test-confidence.TR.3 | cross-ref | S-011 | top repair = harden `redact_text`/`model.py` coverage |
| F-performance.RH.1 | own | S-013 | `dashboard_payload()` per-repo query fan-out |
| F-performance.RH.2 | own | S-014 | `App.tsx` derived-state recompute per render |
| F-performance.RH.3 | cross-ref | S-015 | single-chunk bundle, no code-splitting |
| F-performance.RH.4 | own | S-015 | oversized static images |
| F-performance.RH.5 | cross-ref | S-013 | server concurrency / scan-job model (Green) — off-thread already; preserved through the batching refactor |
| F-performance.RH.6 | cross-ref | S-013 | case-building O(n log n) (Green) — clears the no-O(n²) cue; no repair owed |
| F-performance.RH.7 | cross-ref | S-013 | SQLite index coverage (Green) — per-query cost fine; S-013 fixes query *count* |
| F-performance.US.1 | cross-ref | S-013 | per-run nested `case_resolution_items` N+1 — the clearest batching win in S-013 |
| F-performance.US.2 | deferred | brief out-of-scope: privacy/integration egress surface — six outbound endpoints owned by the privacy-and-integration cluster | outbound network dependencies |
| F-performance.US.3 | cross-ref | S-013 | honey-event pruning on every dashboard load — bounded-cost confirmation co-checked with the payload batching |
| F-performance.US.4 | cross-ref | S-002 | large report-generation modules (server-side render) — render-path latency lives in the `dashboard_server` split |
| F-performance.TR.1 | own | S-013 | top repair = batch `dashboard_payload()` |
| F-performance.TR.2 | cross-ref | S-014 | top repair = memoize `App.tsx` derived state |
| F-performance.TR.3 | own | S-015 | top repair = trim assets + decide code-splitting |
| F-ai-maintainability.RH.1 | own | S-016 | module map omits MCP/fix-proposal subsystem |
| F-ai-maintainability.RH.2 | own | S-017 | risk register has no AI-write-surface entry |
| F-ai-maintainability.RH.3 | own | S-017 | recovery/verification falsely say pytest can't run |
| F-ai-maintainability.RH.4 | cross-ref | S-017 | stale `adx.json` `last_verified` — bumped after the above |
| F-ai-maintainability.RH.5 | cross-ref | S-002 | `dashboard_server.py` 4,236-line file — split owned by architecture |
| F-ai-maintainability.RH.6 | cross-ref | S-017 | "Security Observatory" ↔ "DëvSec" dual identity unmapped — one AGENTS.md line in S-017 |
| F-ai-maintainability.RH.7 | cross-ref | S-016 | generated dashboard assets correctly separated (Green) — keep accurate in the refreshed map |
| F-ai-maintainability.RH.8 | cross-ref | S-016 | live Python modules clean/low-debt (Green) — register new modules in the map (S-016) so it stays Green |
| F-ai-maintainability.US.1 | cross-ref | S-016 | MCP write-mode + fix-proposal subsystem absent from `.adx` |
| F-ai-maintainability.US.2 | cross-ref | S-016 | `decisions.py`/`case_followup.py` not in module map |
| F-ai-maintainability.US.3 | cross-ref | S-016 | `docs/conftest.py` cold-read surprise — addressed by the refreshed map note (harmless) |
| F-ai-maintainability.US.4 | cross-ref | S-017 | stale-stamped `adx.json` over newer code |
| F-ai-maintainability.TR.1 | own | S-016 | top repair = refresh module map |
| F-ai-maintainability.TR.2 | cross-ref | S-017 | top repair = add risk-register + command-danger entries |
| F-ai-maintainability.TR.3 | cross-ref | S-017 | top repair = correct recovery/verification + bump stamp |

## Cross-Cutting Patterns

1. **Four god modules carry the cluster's structural risk and span four lenses each.** `dashboard_server.py`, `storage.py`, `App.tsx`, `dashboardData.ts` show up independently in architecture, ai-maintainability, performance, and (for the UI pair) domain-language/data-contract. Splitting them is where the leverage is — ties S-002, S-003, S-013, S-014, S-015, and the structural shape of S-001.

2. **One missing seam, named three ways: the case lifecycle.** Architecture sees "no state machine," domain-language sees "two divergent enums + a diff-axis," feature (sibling) sees "no in-progress/verifying state." A single `lifecycle.py` + documented mapping resolves all three — ties S-006 (and cross-clusters to feature/product-workflow).

3. **Sound invariants resting on a soft enforcement floor.** Zero-`any` TS but no `strict`; redaction baked into `model.py` but bypassable via `save_scan` raw dicts; no-egress proven per-function but no repo-wide sentinel; `case_resolutions.v1` rock-solid but `cases_json` unguarded on read. The fix pattern is "make the floor enforce what the code already intends" — ties S-007, S-008, S-009, S-010, S-011, S-012.

4. **The pipeline orchestrator's location is the root of the coupling.** `scan_repo` living in `cli.py` causes the `cli↔dashboard` cycle, the `mcp→cli` reach, and a misleading module map. Moving it is a single high-leverage move — ties S-001, and feeds S-016/S-017's accuracy.

5. **The `.adx` agent-guidance layer drifted behind a real new subsystem.** The MCP/fix-proposal write surface (added 2026-05-21..05-31) is invisible to the module map, risk register, and recovery notes (frozen 2026-05-12), and the strongest safety net (467 passing tests) is documented as unavailable. Refreshing it is pure documentation-of-truth, low blast radius — ties S-016, S-017.

## Excellence Gaps

- **No lens in this cluster owns whether the *severity→display* mapping is the same value a screen-reader/keyboard user perceives.** Domain-language stops at the vocabulary split (S-005); the UX rendering of severity-as-trust-signal is explicitly handed to behavioral-ux/design-system (sibling cluster). The gap: the synthesis can't confirm from these six reports that fixing the vocab also fixes perception. Closes when S-005 lands jointly with the sibling cluster's severity-legibility row.
- **Cross-language contract test (Python wire shape ↔ React `SecurityCase`) is proposed but not owned by a single lens.** Data-contract flags the drift (S-008), test-confidence flags the absence of frontend tests (deferred F-test-confidence.RH.4), but neither owns a contract test that would *fail* when the backend changes the case shape. The lenses each saw half. Closes by adding a shape-contract assertion when S-007/S-008 land.
- **No lens measured the *actual* cost of enabling TS strict.** S-007 is High-confidence that the config is lax, but the error count from flipping the flag is unmeasured (it's a repair, not a diagnosis). The plan must budget for an unknown error volume in the first batch.
- **Performance was reasoned from code + emitted-asset sizes, never from a live query plan or render profile.** No EXPLAIN QUERY PLAN, no React Profiler run, no seeded large-history DB. S-013/S-014 are well-grounded structurally but their *magnitude* on a real large store is inferred. The validation columns specify the missing measurements.

## Review Pass

| Review finding | Verdict | How it was handled |
| --- | --- | --- |
| pending — performed at merge level | pending | This cluster pass is unreviewed by design; the second-agent review runs at the cross-cluster merge synthesis. |

## Suggested Plan Structure

Batches favor cross-cutting fixes — one fix surface that lifts multiple lenses.

1. **Pipeline/structure seam** — S-001, S-005' cycle-break dependency: extract `scan_orchestrator`, break both cycles, split the `catalog↔setup_runner` config. One refactor that fixes architecture RH.4/RH.5 and unblocks accurate `.adx`. Rationale: lowest-risk highest-leverage; everything else reads cleaner after.
2. **God-module decomposition** — S-002, S-003, S-013, S-014, S-015: split `dashboard_server.py` + lift `storage.py` payload assembly (co-land the `dashboard_payload` batching), then decompose `App.tsx` + memoize (co-land asset trim). Rationale: the storage/dashboard split and the query-batching touch the same code; the `App.tsx` split and memoization touch the same component — pairing them avoids double-editing the largest files.
3. **Scanner registry + case lifecycle** — S-004, S-006: one adapter registry and one `lifecycle.py`, each a new single-seam module that also resolves domain-language enum drift. Rationale: both are "create the missing seam" moves that several lenses depend on.
4. **Type floor + contract enforcement** — S-007, S-008, S-009, S-012: enable TS strict (budget for unknown error count), trim/narrow the case contracts, guard `cases_json`, version migrations. Rationale: S-007 is the safety net that makes S-008 safe; all four harden the same soft enforcement floor.
5. **Trust-test hardening** — S-010, S-011: count-conservation + repo-wide no-egress sentinel + redaction coverage + non-skippable MCP tests. Rationale: cheap, high-leverage, closes two non-negotiable failure classes against future code.
6. **Naming hygiene + `.adx` truth** — S-016, S-017, S-018: refresh module map/risk register/recovery, collapse the residual vocabulary drift. Rationale: pure documentation-of-truth and low-cost renames; safe to run last, and S-017 needs the earlier batches landed so its stamp reflects reality.

## Limits

- **No repo code or forensic report was edited.** The only write is this cluster synthesis file. No installer, scanner, dashboard server, desktop launcher, or `.adx/risks.json`-flagged command was run.
- **Health/confidence labels are copied from the forensic reports, not independently re-derived.** Where a report bolded labels (test-confidence), the synthesis uses the plain label form per the shared standard.
- **Cross-cluster cross-refs are asserted, not verified against the sibling reports.** Mentions of behavioral-ux, design-system, error-edge-state, feature, privacy, integration, permission, documentation, and product-workflow point at sibling clusters; their exact S-IDs are assigned at the merge step.
- **Two ledger IDs are deferred to explicit Brief out-of-scope / sibling-boundary items** (F-test-confidence.RH.4 → sibling-lens frontend testing; F-performance.US.2 → privacy/integration egress surface). All other 93 IDs are own / cross-ref / merged within this cluster.
- **Magnitude of the performance and TS-strict findings is inferred from static evidence**; no live query plan, render profile, seeded large-history DB, or strict-mode flip was executed (per the underlying reports' own Limits and the read-only contract).
- **The `.adx` drift claims are time-stamped against git add-dates in the ai-maintainability report (frozen 2026-05-12 vs code through 2026-05-31)**; this synthesis did not re-run that git inspection.
