# Implementation Receipt: 21-integration-and-mcp-hygiene

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 21-integration-and-mcp-hygiene (final batch of Stage C)
- Source report item(s): S-008, S-011, S-009, S-012, S-013, S-014

## Before Health

Closing hardening batch over already-Green/near-Green integration & MCP surfaces.
Re-verified each S-ID against current files (post batches 14–19):
- **S-008** Green/Yellow — `enrich_dependency_finding` defaults `check_cisa_kev`/`check_epss` to `False`; only internal caller `_fill_dependency_facts` (`enrichment.py:521`) passes neither; no CLI flag wires them; `docs/scanners.md:41` described KEV/EPSS as active "optional online checks". Doc/code drift confirmed.
- **S-011** Green/Yellow — `setup_runner._run_subprocess` uses `shell=True` with a catalog-literal command; the only catalog shell probe (legitify) injects its credential via `env_from_credential`, never interpolation. Fetchers (`enrichment._fetch_json/_fetch_bytes`, `managed_tools.download_bytes`) are single-attempt, no retry/backoff.
- **S-009** Green — `_redact_path` covered only typed `path`/`affected_files`; the invariant test used `startswith` only, so a mid-string path could slip through free-text fields.
- **S-012** Green — `safe_to_apply` shown in the example JSON (`case_followup.py:513`) but never read by `_validate_resolution_item`; `agent-voice.md` §10 boundary line was already stale vs the served `_READ_ONLY_BOUNDARY`.
- **S-013** Green — `execute_reset` clears all named tables + report dir, but no single test exercised the full table+filesystem cleanup.
- **S-014** Green/Yellow — `CHECK_JOBS` never pruned.

## Changes Made

**S-008 — KEV/EPSS promise/code agree (doc-correction path).**
- `docs/scanners.md`: rewrote the enrichment paragraph to state KEV/EPSS are **designed but not yet wired** (opt-in params default `False`, no scan/CLI path enables them; when wired they will follow the `--trust`-style opt-in + named egress disclosure). No code wires them on.
- `tests/test_enrichment.py`: `test_default_scan_path_never_enables_kev_or_epss` monkeypatches `cisa_kev_lookup`/`epss_lookup` to raise and drives `_fill_dependency_facts` (default scan path) — a future change that wires KEV/EPSS on without an opt-in fails. Also asserts the helper defaults both flags off.

**S-011 — shell=True invariant locked + no-retry decision recorded.**
- `enrichment.py` / `managed_tools.py`: one-line rationale comments at the fetchers recording the deliberate single-attempt, fail-closed, no-retry/backoff local-first decision.
- `tests/test_setup_runner.py`: `test_catalog_shell_probe_commands_carry_no_templating_placeholders` (every catalog shell-probe command is a literal — `{`, `}`, `%s`, `$(`, backticks fail the guard) and `test_shell_probe_injects_credential_via_env_not_command` (a credential with shell metacharacters reaches the child via env but is never interpolated into `result.command`).

**S-009 — path-leak invariant hardened prefix→substring + redaction coverage.**
- `mcp_server.py`: added `_redact_text` (scrubs absolute `/Users|/home|/root` path tokens embedded mid-string via per-token `_redact_path`; `_redact_path` itself untouched, output shape unchanged) and applied it to every free-text field that could carry a path: finding `title` + `evidence_excerpt`; case `title`, `plain_english_risk`, `suggested_steps`, `agent_handoff_prompt`.
- `tests/test_mcp_server.py`: invariant now substring-scans (`marker in text`) across **all** string fields of findings and the free-text case fields; added `test_free_text_fields_redact_mid_string_absolute_paths` constructing a finding+case with a mid-string `/Users/alice/...` path and asserting the JSON payloads carry no `/Users/`, `/home/`, `/root/`, or `alice`.

**S-012 — prompt-injection sliver closed + ignored field resolved.**
- `case_followup.py`: removed the `safe_to_apply` field from the example resolution JSON (validator never read it). Also dropped it from the `tests/test_case_followup.py` `_resolution` helper.
- `docs/agent-voice.md` §10: reconciled the stale read-only boundary line to match the served `_READ_ONLY_BOUNDARY` verbatim.
- `tests/test_case_followup.py`: `test_mcp_instructions_stay_in_sync_with_agent_voice_section_10` asserts `DEVSEC_MCP_INSTRUCTIONS == ` the §10 fenced block exactly (drift in either fails).
- `tests/test_severity_gate.py`: two new poisoned medium/low cases — `test_poisoned_medium_case_suppression_uses_recorded_severity` (injected `severity: critical` + "ignore instructions" on a medium case → preview severity stays `medium`, applies normally, never escalated) and `test_poisoned_severity_downgrade_cannot_bypass_gate` (injected `severity: low` on a critical case → still held for human confirmation; recorded critical governs the gate).

**S-013 — reset full-cleanup tested.**
- `tests/test_reset.py`: `test_execute_reset_full_cleanup_clears_every_named_table_and_report_dir` seeds every repo-scoped table (findings, sbom_components, dependency_manifest_entries, dependency_trust_enrichments, platform_posture_snapshots, case_decisions, agent_lab_proposals, honey_key_events, honey_keys, security_project_status, scans), runs `execute_reset`, and asserts report dir removed + 0 rows per named table (list-driven, so a forgotten table fails). Cache cleanup deferred (see Remaining Risk).

**S-014 — terminal `_JOBS` pruned after a TTL.**
- `dashboard_server.py`: added `CHECK_JOB_TTL_SECONDS = 3600`, `_job_is_expired_terminal`, and lock-safe `prune_terminal_check_jobs`; `job_snapshot` prunes on every poll. In-flight jobs and undatable terminal jobs are never pruned; the missing/expired-job → 404 contract is unchanged.
- `tests/test_dashboard_job_pruning.py`: stale terminal jobs pruned while fresh + in-flight retained; undatable terminal job kept; `job_snapshot` poll drops a stale terminal job (→ 404) while a live job stays readable.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/test_enrichment.py` | PASS | default path passes neither KEV/EPSS flag (S-008) |
| `grep -rn "check_cisa_kev=True\|check_epss=True" src/` | PASS | no hits — no caller enables online checks (S-008) |
| `uv run pytest tests/test_setup_runner.py tests/test_managed_tools.py` | PASS | shell=True invariant guard + single-attempt download green (S-011) |
| `uv run pytest tests/test_mcp_server.py` | PASS | strengthened substring path-leak invariant + redaction coverage (S-009) |
| `uv run pytest tests/test_severity_gate.py tests/test_case_followup.py` | PASS | medium/low poisoned eval, §10 drift guard, safe_to_apply removed (S-012) |
| `uv run pytest tests/test_reset.py` | PASS | full-cleanup test: report dir removed + all named tables 0 rows (S-013) |
| `uv run pytest tests/test_dashboard_reset_endpoints.py` | PASS | reset endpoints unaffected |
| `uv run pytest` (full suite) | PASS | **535 passed, 0 new skips, 0 xfail** (incl. rotation/check-status branches for S-014) |
| `python3 -c "...import security_observatory.cli..."` | PASS | fast import check green |

## After Health

All six rows → Green. Promise/code agree (S-008); shell=True invariant + no-retry decision suite-enforced (S-011); path-leak invariant catches mid-string leaks across free-text MCP fields (S-009); no shown-but-ignored field, doctrine drift guarded, poisoned medium/low suppression pinned to recorded severity (S-012); reset full-cleanup test in place (S-013); `_JOBS` bounded by TTL pruning (S-014). No trust guard weakened, re-pinned, skipped, or xfailed.

## Remaining Risk

- **S-013 cache cleanup deferred (accepted residual):** `reset` still does not clear `~/.security-observatory/cache/` threat-intel caches. This is **public threat-intel data only (CISA KEV / EPSS / OpenSSF), not a privacy gap** — no findings, file paths, or operator-identifying data live there. Left as an explicit opt-in for a future pass per the batch non-goals.
- **`docs/ai-case-follow-up-workflow-plan.md`** (historical working-notes doc, not canonical contract per AGENTS.md) still shows `safe_to_apply: true` in an example; left as-is since it is a stale plan doc, not the served prompt.
- S-014 pruning triggers on the poll path (`job_snapshot`); a server that creates jobs but is never polled would still grow, but any server actually in use is polled while jobs run. Bounded and lock-safe as specified.

## Next Batch

None — this is the final batch of Stage C and of the devsec-industry-grade campaign. Stage C complete.
