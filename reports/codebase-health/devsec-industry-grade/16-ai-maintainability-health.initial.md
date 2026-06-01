# AI Maintainability Health — Forensic (Initial)

## Executive Finding

The DëvSec **code** is, in most respects, pleasant and safe for a future agent to extend:
intent-revealing module names across 35 source files, very low misleading-comment debt (the
verified TODO/FIXME count in the Python source returned 0), per-module tests, and a full
Python suite that **passes** (`uv run pytest`: 317 passed, 2 xfailed, 8 deselected) including
a 1,234-line dedicated suite for the newest high-stakes module
(`tests/test_mcp_server.py`). The dominant maintainability risk is **drift in the `.adx`
agent-guidance layer**, which is exactly what this campaign's domain-risk cue asks ("Can a
fresh agent extend DëvSec safely via the `.adx` manifests, command registry, risk register,
recovery notes — and are those still accurate after this campaign's changes?"). Between
2026-05-21 and 2026-05-31 the repo grew a guarded AI case-resolution / fix-proposal write
surface: `mcp_server.py` (added 2026-05-24, exposes write tools `apply_case_resolutions`,
`propose_fix`, `land_fix`, `trigger_scan`), `fix_proposals.py` (2026-05-31, the
propose→clean-room-review→land decision/audit machinery), `case_followup.py` (2026-05-31),
and `decisions.py` (2026-05-21). The command registry (`commands.json`, updated 2026-05-30)
correctly added the `devsec-mcp` / `devsec-mcp-rw` commands, **and** `mcp/README.md` documents
the write boundary clearly and accurately ("Guarded write mode... Write mode is case-only...
[the adapter] never... write[s] repository files"). The write boundary itself is therefore
honestly described and enforced in code — `fix_proposals.py`'s own docstring (lines 32-36)
states the physical git work stays with the orchestrating command and "this adapter never
writes repository files," and `mcp_server.py` reports `suppress: 0` occurrences. So this is
**not** a silent-egress or unsafe-AI-write failure for the lens. The maintainability gap is
narrower but real: the **module map, risk register, recovery notes, and `adx.json` are frozen
at 2026-05-12**, before this subsystem existed. Verified by scanning every `.adx` file — the
new write subsystem's symbols (`fix_proposals`, `mcp_server`, `propose_fix`, `land_fix`)
appear in **zero** `.adx` files; `devsec-mcp-rw` appears **only** in `commands.json`. For a
cold-reading agent that orients from the manifests (not the code), the consequences are: (1)
the module map omits the entire MCP / fix-proposal subsystem, so an agent doesn't know it
exists or where its boundaries live; (2) the risk register has no entry for the AI write
surface, even as an "audited, guarded, but security-sensitive" note; (3) `recovery.md` and
`verification.json` both assert pytest **cannot run**, which is provably false (317 pass),
suppressing the repo's strongest safety net. Worst health: **Yellow** (stale agent-guidance
contracts around a new, otherwise well-documented subsystem). Everything is Yellow or better,
and every repair is bounded and low-blast-radius. (Note: an earlier draft of this report
overstated this as Yellow/Red by wrongly claiming `fix_proposals.py` executes
`git checkout/add/commit` — it does not; that claim has been removed.)

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security`
- Skill/lens: `ai-maintainability-health-forensic`
- Date: `2026-06-01`
- Requested focus: Excellence Brief domain-risk cue for this lens — "Can a fresh agent extend
  DëvSec safely via the `.adx` manifests, command registry, risk register, recovery notes —
  and are those still accurate after this campaign's changes?" The lens grades agent
  repairability: stable named landmarks, accurate AGENTS.md / module map / command manifests
  matching current behavior, one source of truth, stale/generated code separated from live
  code, labeled safe-vs-unsafe scripts with runnable validation, blast-radius coverage, and
  misleading TODOs/old names. Out of scope per Brief: penalising External Surface for being an
  honest "Coming Soon"; runnable packs; non-macOS desktop; net-new scanners. Per the
  no-sibling-overlap rule, deep doc-prose drift defers to documentation-health and brand/term
  consistency to domain-language-health; this report keeps only their agent-repairability
  slices.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli; print('ok')"` | Pass (printed `ok`, exit 0) | AGENTS.md fast import smoke check; the cold-start landmark a fresh agent runs first. |
| `uv run pytest -q` | Pass — 317 passed, 2 xfailed, 8 deselected (~47s) | Full Python suite. Directly contradicts `.adx/recovery.md` "Pytest Is Missing" and `verification.json`'s "currently blocked until pytest exists" notes. |
| `python3 -c "import json; json.load(open('.adx/modules/index.json'))"` | Pass (`VALID JSON`) | Module map parses; its *content* (omitted subsystems) is the issue, not its syntax. |
| `python`/`grep` scan of all `.adx` files for `fix_proposals`/`mcp_server`/`land_fix`/`propose_fix`/`devsec-mcp-rw` | Confirmed gap | Those module/symbol names appear in 0 `.adx` files; `devsec-mcp-rw` only in `commands.json` (2x); `case_followup` only in `commands.json` (1x). |
| `git log --diff-filter=A` per new module | Drift confirmed | `mcp_server.py` added 2026-05-24, `decisions.py` 2026-05-21, `fix_proposals.py` + `case_followup.py` 2026-05-31; `adx.json`/`risks.json`/`recovery.md`/`modules/index.json` last committed 2026-05-12; only `commands.json` updated 2026-05-30. |
| `git ls-files src/security_observatory/dashboard/assets/` + `.gitignore` | 0 tracked; `.gitignore` line 14 = `src/security_observatory/dashboard/assets/` | Generated Vite output is correctly gitignored and untracked — properly separated from source (no finding). |
| `fix_proposals.py` / `mcp_server.py` git-execution check | No `git checkout/add/commit` execution found | `fix_proposals.py` docstring lines 32-36: physical git "stays with the orchestrating command... this adapter never writes repository files." `mcp_server.py`: `suppress` 0x; docstring "never... write repository files." Write tools record decisions/audit, they do not mutate the repo. |
| `dashboard_server.py` structure | 4,236 lines; 1 class `DashboardHandler(SimpleHTTPRequestHandler)`; 3 verb handlers (`do_GET` L2107, `do_POST` L2392, `do_DELETE` L2518) | A large single-file handler; exact intra-handler dispatch style not fully characterized (see Limits). |

No installer, scanner (`security-scan`), dashboard server, desktop launcher, process-kill, or
any `.adx/risks.json`-flagged command was run. All checks are within the AGENTS.md
"Verification" allow-list and read-only except `uv run pytest` (verification-matrix
`local_mutation`), which produced no tracked changes.

## Ranked Health Table

| Rank | Area | Health | Confidence | Evidence | Impact | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Module map (`.adx/modules/index.json`) omits the MCP / fix-proposal write subsystem | Yellow | High | Map lists 5 modules; no entry and no `key_files` names `mcp_server.py` (1,118 LOC), `fix_proposals.py` (775), `case_followup.py` (673), or `decisions.py` (425). The whole `mcp/` dir (`mcp/README.md`, `SESSION-PROMPT.md`) is absent. `python-cli-scanners` nominally covers all of `src/`, but its `purpose`/`common_changes` describe only scan→normalize→case→storage, never the AI write path. Modules added 2026-05-21..05-31; map frozen 2026-05-12. | developer/agent — the canonical landmark AGENTS.md points to for "where things live" never names the write subsystem, so an agent orienting from the map edits the MCP/fix-proposal code blind to its existence and to the (well-documented, in-code) write boundary it must preserve. | Add a module entry (e.g. `mcp-write-surface`) for `mcp_server.py` + `mcp/` + `fix_proposals.py` + `case_followup.py` + `decisions.py`, with `key_files`, the existing matching tests, the new risk id from row 2, and a one-line summary pointing at `mcp/README.md` for the boundary. | `python3 -c "import json;json.load(open('.adx/modules/index.json'))"`; `ls` each new `key_files` path. |
| 2 | Risk register has no entry for the AI write surface | Yellow | High | `.adx/risks.json` has 5 entries (installer, local-data, honey-keys, desktop, generated-assets); a full scan of all `.adx` files finds zero occurrences of `fix_proposals`/`mcp_server`/`land_fix`/`propose_fix`. `dangerous_command_patterns` has no `devsec-mcp-rw`/`land_fix`/`propose_fix`. The boundary IS documented in `mcp/README.md` (L126-142 "Guarded write mode") and enforced in code — so this is a missing *cross-reference*, not an undocumented danger. | developer/agent — an agent told to "check `.adx/risks.json` before running... process-kill, or report-storage commands" finds no pointer to the guarded write surface or the case-resolution/fix-proposal audit path. The safety register a careful agent trusts is silent on a real (if guarded) security-sensitive subsystem. | Add a `mcp-write-surface` risk entry (paths: `mcp_server.py`, `fix_proposals.py`, `case_followup.py`, `decisions.py`) summarizing the guarded write boundary, pointing to `mcp/README.md` and the clean-room/audit invariants; add `devsec-mcp-rw`/`land_fix`/`propose_fix` to `dangerous_command_patterns`. | `python3 -c "import json;json.load(open('.adx/risks.json'))"`; grep the new entry's paths to confirm they reference real files. |
| 3 | `recovery.md` + `verification.json` falsely say pytest cannot run | Yellow | High | `.adx/recovery.md` "Pytest Is Missing": "Current observed state: `python3 -m pytest --version` and `.venv/bin/python -m pytest --version` both fail because pytest is not installed; `.venv` also lacks pip." `verification.json` change-matrix notes: pytest "currently blocked until pytest exists in the selected Python environment." Verified false: `uv run pytest` ran 317 tests green this session. | developer/agent — an agent reading recovery notes believes it cannot verify Python changes and will either skip the suite ("do not claim tests passed") or burn a turn on `uv sync --dev`. The repo's strongest safety net (317 passing tests) is described as unavailable. | Rewrite the "Pytest Is Missing" section to state `uv run pytest` works (cite the pass count); keep `uv sync --dev` only as a stale-env contingency. Update the matrix's "currently blocked" notes. | Re-run `uv run pytest -q`; paste the pass line into the note. |
| 4 | `adx.json` advertises a verified state older than the current code | Yellow | High | `adx.json` `last_verified: 2026-05-12T13:35:03Z` and `contracts.modules/safety/recovery: true`, while those contracts are stale relative to code added through 2026-05-31 (rows 1-3). The audit pointer itself is healthy: `last_audit: .adx/audit/latest.json` resolves (`os.path.exists` → `True`; file is 9,300 bytes, dated 2026-05-12), and an implementation receipt `.adx/implementation/2026-05-12T133503Z.json` exists. So the issue is purely the stale timestamp, not a dangling reference. | developer/agent — the manifest index an agent reads first to judge "is this guidance current?" carries a stamp two-to-three weeks older than the code it describes, granting false confidence in the stale contracts above. | After fixing rows 1-3, regenerate `.adx/audit/latest.json` and bump `last_verified` so the verification stamp matches the current code. | `python3 -c "import json,os;d=json.load(open('.adx/adx.json'));print(os.path.exists(d['last_audit']))"` already prints `True`; confirm `last_verified` post-repair is newer than the newest source mtime. |
| 5 | `dashboard_server.py` is a 4,236-line single-handler file | Yellow | Medium | `wc -l` = 4,236; one class `DashboardHandler(SimpleHTTPRequestHandler)` with `do_GET`/`do_POST`/`do_DELETE`; 114 module defs. The module map already points the dashboard module here, so it is at least findable. | developer/agent — any one-endpoint fix forces loading a 4k-line file and reading the verb handler to find the right branch; high context cost. Medium confidence on the *dispatch style* (the intra-handler routing pattern was not fully characterized this session). | Out-of-scope to refactor here; flag for architecture-health (it owns module splits). For this lens: add a module-map note / header comment naming where GET/POST/DELETE routing lives so an agent knows the entry points. | N/A (diagnostic); a split would be validated by `uv run pytest` + the dashboard endpoint tests. |
| 6 | Dual identity "Security Observatory" vs "DëvSec" not mapped in the agent guide | Green/Yellow | Medium | Package/repo = `security_observatory` / "Security Observatory" (AGENTS.md line 5); product brand = "DëvSec"; MCP commands = `devsec-mcp`/`devsec-mcp-rw`; `docs/branding.md` exists. AGENTS.md uses "DëvSec" only in the MCP line and Ghost memory, never stating the two names are the same thing. | developer/agent — mild cold-read orientation cost; the package name is unambiguous in code so no edit danger, but an agent reading the Excellence Brief ("DëvSec") then AGENTS.md ("Security Observatory") must infer the equivalence. | One sentence in AGENTS.md "Start Here": "Security Observatory is the package/repo name; DëvSec is the product brand." Deeper term consistency defers to domain-language-health. | N/A (docs); no validation needed. |
| 7 | Generated dashboard assets are correctly separated from source | Green | High | `.gitignore` line 14 = `src/security_observatory/dashboard/assets/`; `git ls-files` of that path returns 0 tracked files; AGENTS.md and the `risks.json` `generated-assets` entry both name the folder as generated/do-not-hand-edit. | developer/agent — generated build output is ignored, untracked, and flagged in two manifests; an agent will not mistake it for hand-editable source. (Corrects an earlier draft that wrongly graded this Green/Yellow.) | None; maintain. | N/A. |
| 8 | Live Python source modules are clean, well-named, low-debt | Green | High | 35 source modules with intent-revealing names; the verified TODO/FIXME/XXX/HACK count in the `*.py` source returned 0; tests exist per module including `test_mcp_server.py` (1,234 LOC), `test_fix_proposals.py` (420), `test_case_followup.py` (177); full suite passes. `cli.py` (987 LOC) is a clear entry point. | developer/agent — for the in-code edit surface (excluding the dashboard single-file handler), the repo is pleasant and safe to extend: clear landmarks, named tests, low misleading-comment debt. | None; maintain. Register new modules in the module map (rows 1-2) as they land so this stays Green. | `uv run pytest -q`. |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| MCP write-mode adapter + fix-proposal subsystem absent from the `.adx` map/register | `commands.json` lists `devsec-mcp-rw`; `mcp_server.py` implements `apply_case_resolutions`/`preview_case_resolutions`/`propose_fix`/`land_fix`/`trigger_scan`; `fix_proposals.py` owns the propose→clean-room→land decision/audit flow. None of these appear in `modules/index.json` or `risks.json`. | A real, security-sensitive (though guarded and well-documented-in-code) subsystem is invisible to the two `.adx` contracts agents are told to consult for orientation and risk. The boundary is sound; the cross-reference is missing. |
| `decisions.py` (added 2026-05-21) and `case_followup.py` (2026-05-31) | `git log --diff-filter=A`; 425 and 673 LOC; both participate in the case-resolution write/follow-up path. Neither is in the module map. | New write-adjacent modules landed after the last `.adx` refresh with no map/risk entry orienting agents to them. |
| `docs/conftest.py` location | A pytest `conftest.py` lives under `docs/` (alongside `docs/decisions/`, `docs/incidents/`, `docs/tools/`). | Minor cold-read surprise: an agent scanning `docs/` for prose finds a test-config file. Harmless; not graded as a finding. |
| Stale-stamped `adx.json` over newer code | `last_verified: 2026-05-12`; newest code 2026-05-31. The audit/implementation receipt files themselves exist and the pointer resolves — only the stamp is stale. | An agent or re-audit tool trusting the verification stamp may assume the contracts are current when several are stale (rows 1-4). |

## Top Repair Targets

1. **Refresh the module map to include the MCP / fix-proposal / case-followup / decisions
   subsystem**, with `key_files`, the existing matching tests, the new risk id, and a one-line
   summary pointing at `mcp/README.md` for the write boundary — so the canonical landmark
   AGENTS.md points to actually covers the current architecture, including `mcp/`. (Row 1.)
2. **Add a `mcp-write-surface` risk-register entry and command-danger entries.** Summarize the
   guarded write boundary (case-only, clean-room-reviewed, audited, never writes repo files),
   point to `mcp/README.md` and the clean-room/audit invariants, and add `devsec-mcp-rw` /
   `land_fix` / `propose_fix` to `dangerous_command_patterns` — so the safety register an agent
   consults before risky ops cross-references the write subsystem. (Row 2.)
3. **Make the recovery/verification notes and `adx.json` tell the truth about current state:**
   correct `recovery.md`'s "pytest is missing" section and `verification.json`'s "currently
   blocked" notes (pytest runs: 317 pass), and bump `last_verified` (regenerating or
   de-referencing the audit pointer as needed) after the above. (Rows 3-4.) Lower-priority
   follow-ups: a header/module-map note on `dashboard_server.py`'s verb-handler entry points
   (row 5) and one line in AGENTS.md mapping "Security Observatory" ↔ "DëvSec" (row 6).

## SocratiCode Value

Not used. Per the SocratiCode cost-discipline rule, this lens's questions were exact-target
(known `.adx` file paths, named modules, specific symbols, git add-dates, JSON validation, and
a test run) — precisely the case where Read / Grep / Bash / direct git inspection are the right
first tools and SocratiCode would add no signal. All findings rest on direct evidence: file
reads, `git log --diff-filter=A` add-dates, exhaustive `.adx` string scans, source docstrings,
`.gitignore` inspection, and a clean `uv run pytest`. No SocratiCode index was consulted and
none was needed — a deliberate choice, not an availability gap.

## Limits

- **`uv run pytest` is the only non-read-only command run** (verification-matrix
  `local_mutation`); it produced no tracked changes. All other inspection was read-only. No
  installer, scanner, dashboard server, desktop launcher, process-kill, or
  `risks.json`-flagged command was executed, per AGENTS.md and the run brief.
- **The MCP write boundary was read, not exercised.** I confirmed `fix_proposals.py`'s
  docstring guarantees (clean-room reviewer never sees finding text; class recomputed from diff
  bytes; no auto-merge without a recorded approval matching the diff hash) and `mcp_server.py`'s
  write-tool inventory by reading source, and confirmed neither executes `git checkout/add/commit`
  (the docstrings state physical git stays with the orchestrating command). I did not run the
  adapter; the *runtime* correctness of those guards is permission-boundary / ai-product
  territory. This lens grades only whether agents are oriented to and warned about the surface —
  they are not in the `.adx` contracts (rows 1-2), though `mcp/README.md` covers it well.
- **`dashboard_server.py` dispatch style (row 5) confirmed:** `do_GET` routes via a flat
  series of `if parsed.path == "..."` / `parsed.path.startswith("...")` guards with early
  `return` (verified by reading lines 2107-2181) — a long linear chain, not a route table. The
  size/cold-read cost stands; row 5 is kept Yellow/Medium because the *full* branch count across
  all three verb handlers was not exhaustively enumerated, but the dispatch pattern is now
  confirmed.
- **Tool-channel flakiness this session was worked around, not relied upon.** Several
  `grep`/`sed`/`Read` calls intermittently returned empty stdout for files that `wc`/`git`
  confirmed had content; every load-bearing number, date, line reference, and string-scan result
  in this report rendered in a successful tool result (re-run via a `python3` one-liner or temp
  file where needed) and is grounded there. In particular, `.adx/audit/latest.json` was
  confirmed to exist and resolve (row 4 upgraded to High).
- **Sibling-lens boundaries respected:** the `dashboard_server.py` size/split is flagged for
  architecture-health; brand/term consistency for domain-language-health; doc-prose drift for
  documentation-health. This report keeps only their agent-repairability slices.
- **Correction note for the synthesis pass.** An earlier draft of this exact file contained two
  material errors, now removed: (1) it claimed `fix_proposals.py` executes `git checkout -b` /
  `add` / `commit` and graded that Yellow/Red — false; the module never writes the repo. (2) It
  claimed generated dashboard assets were committed without a `.gitignore` marker — false; they
  are gitignored (line 14) and untracked. The final verdict above (worst = Yellow) reflects the
  corrected evidence. It also referenced non-existent symbols (`fix_pipeline.py`,
  `case_store.py`, `_handle_summary`, `_GET_ROUTES`) which do not exist in this repo and have
  been purged.
