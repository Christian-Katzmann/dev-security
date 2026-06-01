# Data Contract & Type Health Forensic — DëvSec (Security Observatory)

## Executive Finding

DëvSec's data contracts are unusually disciplined for a tool of this size, and the
*trust-critical* contract — the AI/MCP `devsec.case_resolutions.v1` write path — is the
strongest part: it is hand-validated end to end (schema-version check, repo/scope match,
per-item disposition whitelist, severity read from the *recorded* case rather than
caller-supplied text, and a high/critical suppression gate that every write path crosses
at the single `set_case_decision` chokepoint). That path is **Green** and the brief's
"Unsafe AI write" non-negotiable is demonstrably eliminated, with passing tests. The
weaker areas are all about *type-level enforcement strength*, not active corruption: the
React frontend ships **without TypeScript `strict`/`strictNullChecks`**, so its
careful `?`-optional and `| null` annotations are decorative at compile time and the
"zero `any`" win is real but resting on a lower floor than it looks; the frontend
`SecurityCase` type is a permissive superset that has drifted from the backend wire shape
(it documents several fields the backend never emits); the `cases_json` blob is read in
the primary dashboard payload with **no `JSONDecodeError` guard** (a corrupt or
hand-edited DB row would crash the whole payload, where the same pattern is guarded
elsewhere); and `save_scan` accepts a typed-OR-raw-dict `cases` argument, leaving a latent
bypass of `SecurityCase`'s redaction/validation that is currently exercised only by tests.
None of these is a live data-corruption or silent-egress failure today; they are
enforcement gaps that make future drift cheap and a corrupt-DB edge state fragile.

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security`
- Skill/lens: `data-contract-type-health-forensic`
- Date: `2026-06-01`
- Requested focus: Excellence Brief row for this lens — "Are the normalized raw-finding
  shape, the case schema, lifecycle-state transitions, and the MCP `case_resolutions.v1`
  contract typed, validated, and versioned so malformed scanner output can't corrupt
  history?" Graded against the Brief's "Confident falsehood", "Dropped findings", and
  "Unsafe AI write" non-negotiable failure modes, not just the generic Green floor.
  External Surface and runnable packs treated as honest "Coming Soon" (out of scope).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli"` | Pass | Fast CLI import check per AGENTS.md. Exit 0. |
| `uv run pytest tests/test_case_followup.py test_severity_gate.py test_model.py test_normalize.py test_vex.py` | Pass | 21 passed in 0.58s. Covers the v1 validator, severity gate, dataclass normalization, scanner normalization, VEX. |
| `uv run pytest tests/test_cases.py test_cli_case_followup.py test_dashboard_case_followup.py test_priority.py test_red_team_e2e.py test_mcp_server.py` | Pass | 74 passed in 2.75s. Covers case-building, MCP server, dashboard apply boundary, and the red-team e2e. |
| `cd dashboard-ui && npm run lint` (`tsc --noEmit`) | Pass | Exit 0 — **but** `tsconfig.json` has no `strict`/`strictNullChecks`/`noImplicitAny`, so the clean typecheck is a weak signal (see Rank 1). |
| ESLint config present? | N/A | No `.eslintrc*` / `eslint.config.*`. The "lint" script is purely `tsc --noEmit`; there is no lint rule enforcing contract or null discipline. |
| `dashboard-ui && npm run build` (`vite build`) | Not run | Build was not required to verify the contract findings; `tsc --noEmit` already validates types. Recorded under Limits. |

## Ranked Health Table

| Rank | Area | Health | Confidence | Evidence | Impact (user/developer) | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Frontend TypeScript not in strict mode | Yellow/Red | High | `dashboard-ui/tsconfig.json` (single config, no `extends`) has no `strict`, `strictNullChecks`, `noImplicitAny`, or `noUncheckedIndexedAccess`. `npm run lint` = `tsc --noEmit` passes (exit 0) on this lax config. Zero `any`/cast/`@ts-ignore` in `src` (grep = 0 matches), which is real discipline — but without `strictNullChecks` the pervasive `?`/`| null` annotations on `SecurityCase`, `Finding`, etc. are not enforced. | Developer: a missing/null backend field can be accessed without a compile error; the type system gives false confidence. The runtime is saved today only by hand-written `??` fallbacks, not by the types. | Turn on `strict` (at minimum `strictNullChecks` + `noImplicitAny`) in `tsconfig.json`; fix the errors it surfaces; keep `tsc --noEmit` green. Optionally add a typed runtime guard at the 2-3 `await response.json()` boundaries. | `cd dashboard-ui && npm run lint` must stay green after enabling strict. |
| 2 | `cases_json` read with no JSON-decode guard in primary payload | Yellow | High | `storage.py:1357` `for item in json.loads(row["cases_json"])` (inside `dashboard_payload`), and again unguarded at `storage.py:1527`, `2781`, `2843`. Contrast `storage.py:2166-2167`, which wraps the *same* read in `except (TypeError, json.JSONDecodeError)`. A corrupt/hand-edited `cases_json` raises an unhandled `JSONDecodeError`, taking down the whole dashboard payload (and the MCP read that shares it). | User: corrupt-SQLite (brief's named edge state) shows a crash, not a degraded-but-safe read. Partly mitigated: `cases_json` is always written via `json.dumps` and is `NOT NULL default '[]'`, so the trigger is manual DB damage. | Wrap the `cases_json` reads in the same guard already used at line 2166 (skip-and-warn on decode failure), so one bad row degrades gracefully instead of crashing the payload. | Add a unit test that injects a non-JSON `cases_json` row and asserts `dashboard_payload()` still returns; `uv run pytest`. |
| 3 | Frontend `SecurityCase` type drifts from backend wire shape | Yellow | High | `dashboard-ui/src/dashboardData.ts:1115-1166` types `SecurityCase` with `plain_title`, `summary`, `why_matters`, `why_it_matters`, `bucket`, `action_bucket`, `next_step`, `affected_path`/`path`/`file`/`line` — none of which the backend `SecurityCase` dataclass emits (`model.py:141-178`, constructed in `cases.py:378-395`). The wire shape is exactly the dataclass fields. `inferred_secret_name` *is* injected, but only by `dashboard_server.py:2182`, not by the dataclass. | Developer: the canonical "what does a case look like" type is a permissive legacy superset; a reader can't tell which fields are live. It is defensive (over-typing never breaks the UI), so it is drift, not a runtime bug. | Trim `SecurityCase` to the actual wire fields plus the documented server-injected ones (`scan_id`, `repo`/`repo_name`, `change_status`, `decision`, `suppressed`, `suppression`, `inferred_secret_name`, honey/incident fields); delete dead aliases. Keep `DisplayCase` normalization. | `cd dashboard-ui && npm run lint` after trimming; spot-check `caseToDisplayCase`. |
| 4 | `save_scan` accepts raw-dict cases, bypassing `SecurityCase` validation | Yellow | High | `storage.py:885,891` — `cases: list[SecurityCase] \| list[dict[str, Any]]` and `case.to_dict() if isinstance(case, SecurityCase) else dict(case)`. A raw dict skips `SecurityCase.__post_init__` redaction (`model.py:160-175`), the `action_level`/`confidence` whitelist coercion, and severity normalization. Only caller in production is `cli.py:354` which passes typed cases from `cases.py:188 -> list[SecurityCase]`; the dict branch is exercised only by tests. | Developer/trust: a future caller could persist an un-redacted, un-normalized case (token leak into `cases_json`, invalid `action_level`) with no guard. Latent, not active. | Narrow the signature to `list[SecurityCase]`, or run dict inputs through `SecurityCase(**case)` before persisting so the redaction/whitelist always applies. | `uv run pytest tests/test_cases.py` (update any dict-passing tests to typed cases). |
| 5 | No `PRAGMA user_version` schema versioning; migrations are inference-based | Yellow | Medium | `storage.py:438-511` — schema applied via `executescript(SCHEMA)` (all `create table if not exists`) plus `_ensure_columns()` that diffs `pragma table_info` and `alter table ... add column`. The CHECK-constraint widening (`_migrate_resolution_status_constraints`, 513-581) detects need via a *string sentinel in `sqlite_master.sql`*, not a version number. There is no monotonic schema version, no down-migration, no generation-freshness marker. | Developer: migrations work and are idempotent, but ordering/rollback assumptions are implicit and untraceable; a partially-applied rebuild has no version to recover from. The brief asks contracts be "versioned." | Adopt `PRAGMA user_version` as the single migration counter; keep the column-diff helpers but gate destructive rebuilds on a version bump, not a string match. Document the migration order. | `uv run pytest` (storage tests); add a migration round-trip test from an old-shape fixture DB. |
| 6 | `case_resolutions.v1` contract — typed, validated, gated, versioned | Green | High | `case_followup.py:18` `SCHEMA_VERSION = "devsec.case_resolutions.v1"`; `validate_case_resolutions` (133) rejects wrong `schema_version` (145), non-dict payload (143), mismatched repo (153) / scope (159), non-list `resolutions` (169); `_validate_resolution_item` (326) whitelists `disposition` (348) and reads **severity from the recorded case, not caller text** (371, comment 369-370); `_is_gated_suppression` (610) + the `HumanConfirmationRequired` divert (282-294) hold high/critical suppressions for human confirmation. Same validator used by MCP (`mcp_server.py:702,728`), dashboard (`dashboard_server.py:2972`), CLI (`cli.py:694`). Documented in `mcp/README.md:22-23,157-160` with the exact disposition mapping (matches `DISPOSITION_TO_DECISION`). Tests: `test_case_followup.py`, `test_severity_gate.py`, `test_red_team_e2e.py` all pass. | User/trust: the brief's "Unsafe AI write" non-negotiable is eliminated with evidence — no AI/automated path can edit the repo, exfiltrate finding text, or auto-suppress high/critical. | None required. Keep the single-validator invariant if a `.v2` is ever added (version-negotiate, don't fork). | `uv run pytest tests/test_case_followup.py tests/test_severity_gate.py` (green). |
| 7 | `set_case_decision` severity gate — the write chokepoint | Green | High | `storage.py:2045-2152`. Every decision write crosses here. `human_authorized` defaults `False` (2061); suppressing a high/critical case raises `HumanConfirmationRequired` (2082-2087) with severity read from `_latest_case_for_decision` (2075, 2154) — the recorded case, never caller text. DB-level CHECK constraint on `case_decisions.status` (storage.py:231). The only `human_authorized=True` sites are a direct dashboard button click (`dashboard_server.py:2916`) and an operator-authored VEX import (`storage.py:1657`), each with a justifying comment; the AI/MCP apply path never sets it (`dashboard_server.py:2995`, no flag). | User/trust: irreversible-ish suppression is impossible without explicit, audited human confirmation, regardless of which surface calls in. | None required. | `uv run pytest tests/test_severity_gate.py` (green). |
| 8 | Scanner-output normalization boundary (untrusted -> `Finding`) | Green | High | `normalize.py:12-89` — every accessor (`_line`, `_dict_items`, `_dict_value`, `_text`, `_first_text`) tolerates wrong types and returns safe fallbacks; per-scanner parsers (semgrep/gitleaks/trivy/osv/grype/checkov/malcontent/legitify) all funnel through them. `normalize()` (91) dispatches by scanner name; unknown scanner returns `[]` (controlled, not a crash). `Finding.__post_init__` (model.py:87-135) redacts every text field via `redact_text`/`TOKEN_RE` and normalizes severity (`normalize_severity` coerces unknown -> "medium", 205-218). `read_json_safely` (model.py:250-266) survives malformed/NDJSON reports. Tests: `test_normalize.py`, `test_model.py` pass. | User/trust: malformed scanner output cannot corrupt history or leak a raw token into stored findings — exactly the brief's intent. | None required for contract integrity. (Unknown-scanner silent `[]` and severity->"medium" coercion are integration/edge-state lens concerns; cite those reports, do not duplicate here.) | `uv run pytest tests/test_normalize.py tests/test_model.py` (green). |
| 9 | Findings DB columns vs `Finding` dataclass — one source of truth | Green | High | `storage.py:60-100` (findings table) mirrors the `Finding` dataclass fields (`model.py:48-85`) 1:1; insert (`storage.py:936-984`) writes each typed attribute by name; `_ensure_columns` (457-487) adds any missing finding column. Findings are the *normalized* contract and are strictly typed end to end (no JSON-blob escape, unlike cases). DB CHECK constraints enforce lifecycle states on `case_decisions`, `case_resolution_runs/items`, `fix_proposals` (storage.py:231,257,274,356-357). | Developer: adding a finding field is a single coordinated change (dataclass + SCHEMA + `_ensure_columns` + insert tuple); low drift risk. | None required. | `uv run pytest tests/test_model.py` (green). |
| 10 | `decisions.py` VEX/dependency-identity normalization | Green | High | `decisions.py` — `VEX_STATUSES`, `DEFAULT_VEX_STATUS_BY_DECISION`, `normalize_vex_status` (33) fall back to a decision-derived default; `dependency_identity_from_case`/`_finding` (51,87) normalize vulnerability id (upper), package name/ecosystem (casefold), purl (version-stripped) into a stable comparable identity; suppression matching is exact-identity, not fuzzy text. Single source of `CASE_DECISION_STATUSES`/`SUPPRESSING_DECISION_STATUSES`/`GATED_SUPPRESSION_SEVERITIES`, imported by both `storage.py` and `case_followup.py`. Tests: `test_vex.py` passes. | Developer/trust: VEX and dependency-suppression contracts are centralized and consistently applied across CLI/dashboard/MCP. | None required. | `uv run pytest tests/test_vex.py` (green). |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| `cases_json` is a denormalized JSON blob, not a typed table | `storage.py:56` (`cases_json text not null default '[]'`), written at 931, read at 1357/1527/2781/2843. Findings get full normalized columns; cases do not. | The case schema has no DB-level column typing or CHECK constraints — its entire contract rests on the `SecurityCase` dataclass plus JSON round-tripping. Any drift in the dataclass silently changes the on-disk case shape with no schema gate, and a corrupt blob is only partly guarded (Rank 2). |
| Frontend trusts `await response.json()` with no runtime validation | `App.tsx:920` `setSummary(await response.json())`, `:938` `const payload: ProjectsPayload = await response.json()`, `:2401` `... as {secrets?: RotationSecretRow[]}`; no Zod/JSON-schema/`safeParse` anywhere in `dashboard-ui/src` (grep = 0). | The API->UI boundary has no runtime contract enforcement; TS types are compile-time only and (per Rank 1) not even strict. Practical risk is low because it is local-first and the same author owns both sides, but a backend shape change can produce silent `undefined` chains caught only by the hand-written `??` fallbacks. |
| `save_scan` raw-dict case branch | `storage.py:885,891` | A documented-by-signature escape hatch around `SecurityCase` validation/redaction, invisible to anyone reading only the dataclass. Currently test-only (Rank 4). |
| String-sentinel migration detection | `storage.py:567-573` rebuilds a table when a status literal is absent from `sqlite_master.sql`. | The migration "have I run this?" check is a substring match on stored DDL, not a version number — a non-obvious mechanism a future maintainer could break by reformatting the SCHEMA string (Rank 5). |

## Top Repair Targets

1. **Enable TypeScript `strict` (at minimum `strictNullChecks` + `noImplicitAny`) in
   `dashboard-ui/tsconfig.json`, fix the surfaced errors, keep `tsc --noEmit` green**
   (Rank 1). This is the highest-leverage single change: it converts the existing,
   already-good `?`/`| null` annotations and zero-`any` discipline from decorative into
   *enforced*, and is the foundation that makes the `SecurityCase` trim (Rank 3) safe.
2. **Guard the `cases_json` JSON reads** so one corrupt/hand-edited row degrades to a
   warning instead of crashing the dashboard payload and the shared MCP read — reuse the
   `except (TypeError, json.JSONDecodeError)` pattern already present at `storage.py:2166`
   (Rank 2). Directly hardens the brief's named "corrupt SQLite" edge state.
3. **Tighten the two case-write contracts**: trim the frontend `SecurityCase` type to the
   real wire shape and delete dead aliases (Rank 3), and narrow `save_scan`'s `cases`
   parameter to `list[SecurityCase]` (or route dicts through `SecurityCase(**case)`) so
   the redaction/whitelist can never be bypassed (Rank 4). Both remove latent drift around
   the case contract — the one shape with no DB-level enforcement.

(Adopting `PRAGMA user_version` for traceable, versioned migrations — Rank 5 — is the
natural follow-on once the higher-leverage items land.)

## SocratiCode Value

Not used. Per the suite's SocratiCode cost-discipline rule, this lens's surfaces were all
exact, known targets — the contract definitions live in a small, named set of files
(`model.py`, `normalize.py`, `cases.py`, `decisions.py`, `case_followup.py`,
`storage.py`, `mcp_server.py`, `dashboard-ui/src/dashboardData.ts`) reachable by direct
Read/Grep/Glob, and the validation was routine (`tsc --noEmit`, targeted `pytest`). A
structural map would not have changed any finding, and every claim here is grounded in
concrete file/line evidence plus passing local checks, not inference. SocratiCode
indexing state was therefore not exercised.

## Limits

- **Read-only, no repairs.** Per the lens contract and AGENTS.md, the only write was this
  report file. No installer, scanner (`security-scan`), dashboard server, desktop
  launcher, or anything in `.adx/risks.json` `dangerous_command_patterns` was run.
- **`vite build` not run.** `tsc --noEmit` validates the type contract directly and was
  sufficient; a full production build was out of scope for contract verification and not
  executed.
- **Strict-mode error count not measured.** Rank 1 asserts the *config* is non-strict
  (verified) but does not enumerate how many errors enabling `strict` would surface —
  that requires actually flipping the flag, which is a repair, not a diagnosis.
- **Corrupt-`cases_json` crash is inferred from code, not reproduced.** The unguarded
  `json.loads` at `storage.py:1357` will raise on invalid JSON by construction; I did not
  inject a bad row into a live DB to observe the crash (would touch
  `~/.security-observatory` runtime data).
- **Runtime API/UI shape mismatch not exercised live.** The "no runtime validation"
  surface is established from code (no Zod/`safeParse`); I did not drive the running
  dashboard against a deliberately malformed `/api/summary` response.
- **Migration round-trip from an old-shape DB not executed.** The `_ensure_columns` and
  status-constraint rebuild logic was read and reasoned about; I did not run it against a
  pre-existing narrow-schema database file.
- Tests run were the contract-relevant subset (95 tests across 11 files, all passing),
  not the full suite; areas outside this lens (e.g. rotation, honey keys) were not
  re-validated here.
