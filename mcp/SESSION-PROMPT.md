# MCP adapter session — DëvSec

## Mission

Build the read-only MCP (Model Context Protocol) adapter for DëvSec so local
agents can call this project's security findings instead of treating it as an
island. Ship a pro-grade, smoke-tested MVP in one focused pass.

This work was scoped during a `/repo-craft` re-run and pre-approved. The path
is decided; this session executes it. Do not redesign the tool surface, the
file layout, or the transport — those are settled.

## Project context

- **Repo**: `/Users/christiankatzmann/Dev/Projects/dëv-security`
- **Language**: Python 3.11+
- **Package**: `security-observatory` (CLI entry: `security-scan`)
- **Source layout**: `src/security_observatory/`
- **Dep manager**: `uv` (uv.lock + pyproject.toml — do not use pip/poetry/pdm)
- **Test framework**: `pytest`
- **Local data**: SQLite at `~/.security-observatory/` (read-only for the adapter)

**Read these first** to internalize the project's stance before writing a line:

- `PROVOCATION.md` — why local-first matters for this project
- `docs/threat-model.md` — what's protected and what isn't (this adapter is a new surface; honor the existing posture)
- `AGENTS.md` — operating rules for agents working in this repo
- `.adx/risks.json` — risk register
- `.adx/commands.json` — canonical command registry (you will add an entry to this)

## Existing query layer — wrap it, don't reinvent it

The adapter is a thin wrapper over methods that already exist. **Do not build
new query methods.** Use what's in:

- `src/security_observatory/storage.py` — `ObservatoryDB` class (~1600 lines).
  The substantial read API. Methods cover scan history, findings, cases,
  dependency trust, platform posture. Read the public method signatures
  before designing tool implementations.
- `src/security_observatory/cases.py` — `build_security_cases()` and case
  helpers.
- `src/security_observatory/recency.py` — staleness tagging.
- `src/security_observatory/priority.py` — case priority logic.

If a tool you want to expose has no backing method in `ObservatoryDB`, that
tool is out of scope for this pass. Either drop it from the surface, or stop
and ask the user — never silently add new query methods to the storage layer
inside this session.

## Scope — six read-only tools

Build these as a FastMCP server (the official `mcp` SDK includes FastMCP).
All read-only. All return JSON-serializable shapes. All handle "repo not
found" / "empty DB" gracefully (return empty list or clear error, never raw
Python exception bubbling to MCP).

1. **`list_repos()`** — repositories with scan history.
   Returns: `[{name, last_scan_at, scan_count}]`

2. **`latest_scan(repo: str)`** — most recent scan summary for a repo.
   Returns: `{scan_id, started_at, finished_at, scanner_count, finding_count, health_score, status}`

3. **`findings(repo: str, severity: str | None = None, limit: int = 50)`** — findings for a repo.
   `severity` filter: `critical|high|medium|low|info` (None = all).
   Returns: `[{id, title, severity, category, scanner, path, line, evidence_excerpt}]`

4. **`cases(repo: str, status: str | None = None)`** — action-level cases. This is the
   load-bearing tool — cases are the project's primary unit of value, not raw
   findings. `status` filter: `open|resolved|verified|accepted_risk` (None = open by default).
   Returns: `[{id, title, plain_english_risk, severity, category, action_level, confidence, affected_files, suggested_steps, agent_handoff_prompt, status}]`

5. **`recovery_playbook(category: str)`** — playbook content for a finding category.
   Categories come from the existing case-builder vocabulary in `cases.py` —
   do not invent new ones.
   Returns: `{category, title, steps, estimated_minutes, agent_prompt}`

6. **`dependency_trust(repo: str)`** — dependency trust records.
   Returns: `[{package, version, trust_score, sources, last_updated}]`

## Hard rejections — do not ship any of these

- **No write tools.** No `mark_resolved`, `add_note`, `delete_*`, `update_*`,
  anything that mutates state. Writes in a security tool need explicit
  thinking about agent safety; that's a separate session. If you find
  yourself wanting to add one, stop.
- **No HTTP transport.** Stdio only. The dashboard uses HTTP because a
  browser needs it; the MCP server's consumer is a parent process
  (Claude Desktop, Cursor) — stdio opens zero ports and matches the local-only
  posture. Do not add `--http`, `--sse`, or any network listener.
- **No new query methods in `ObservatoryDB`.** Wrap existing methods only.
- **No new dependencies beyond the official `mcp` SDK.** Add `mcp>=1.0` as
  an optional dep. No FastAPI, no pydantic-extra, no httpx, no async
  frameworks, no helpers. The MCP SDK is sufficient.
- **No absolute paths in tool output.** Path values returned to the agent
  must be repo-relative where possible. Never include `/Users/<name>/`
  prefixes — that leaks the user's name and home location.
- **No background tasks, no daemons, no file watchers.** Request/response only.
- **No logging to stdout.** Stdio MCP servers use stdout for JSON-RPC; log
  to stderr only. Use `logging.basicConfig(stream=sys.stderr)` or equivalent.
- **No telemetry, no analytics, no "phone home."** This is a local-first
  project. The MCP adapter is local-only too.

## Layout — exactly this

```
src/security_observatory/mcp_server.py   # the server (~200-300 lines)
mcp/
  README.md                              # connection instructions (this directory exists, has SESSION-PROMPT.md)
tests/test_mcp_server.py                 # smoke + per-tool tests
pyproject.toml                           # add optional dep + script entry
.adx/commands.json                       # add `devsec-mcp` to the registry
AGENTS.md                                # add one-line entry about the MCP server
README.md                                # one-line mention in "What It Is" pointing to mcp/README.md
```

**Why this layout:**
- Python lives in `src/security_observatory/mcp_server.py` (single module) to
  avoid shadowing the `mcp` SDK package name when you `import mcp`.
- The repo-root `mcp/` directory is a v3 repo-craft visibility convention —
  someone scanning the top-level immediately sees `mcp/` and knows there's
  an adapter. `mcp/SESSION-PROMPT.md` (this file) and `mcp/README.md` live
  there; no Python code in `mcp/`.

**pyproject.toml additions:**
```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0"]

[project.scripts]
# add to existing scripts section
devsec-mcp = "security_observatory.mcp_server:main"
```

## Tests — minimum required

`tests/test_mcp_server.py` must include:

- `test_server_lists_expected_tools` — server advertises all 6 tools with correct names and schemas
- `test_list_repos_empty_db` — graceful empty list when DB is empty/missing, never an exception
- `test_list_repos_with_seeded_data` — returns expected shape from a fixture DB
- `test_findings_returns_normalized_shape` — JSON-serializable, no leaked Python types (sqlite3.Row, datetime, Path)
- `test_findings_severity_filter_works` — filter narrows results
- `test_cases_returns_action_level_shape` — includes `action_level`, `agent_handoff_prompt`, etc.
- `test_cases_status_filter_defaults_to_open` — passing `None` returns open cases, not all
- `test_repo_not_found_returns_clear_error` — explicit MCP error response, not Python traceback
- `test_no_absolute_paths_in_output` — scan a fixture, confirm no `/Users/` or `/home/` prefixes in any returned `path` field

Use existing test patterns from the project's other tests. Seed test data by
constructing temporary `~/.security-observatory/`-shaped directories — the
project's test suite already has fixtures for this; find them
(`grep -r "ObservatoryDB" tests/`) and reuse rather than build new ones.

## `mcp/README.md` — what to write

Short (under 100 lines). Cover:

1. One-paragraph summary of what the adapter exposes and what it doesn't.
2. Installation: `uv sync --extra mcp`.
3. Claude Desktop config snippet (lives at
   `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):
   ```json
   {
     "mcpServers": {
       "devsec": {
         "command": "uv",
         "args": ["--directory", "/path/to/dev-security", "run", "devsec-mcp"]
       }
     }
   }
   ```
4. Cursor / Codex / generic-MCP-client config (similar shape).
5. List of the 6 tools with one-sentence descriptions each.
6. Hard limits stated plainly: read-only, local-only, stdio-only, no writes.
   Link to `../docs/threat-model.md`.
7. A *"Why no write tools yet"* section — one short paragraph explaining
   that write paths in a security tool need explicit agent-safety thinking
   and are deferred to a future pass. Do not promise dates.

## Main README touch

Add a single line to `README.md`'s `## What It Is` section, after the existing
dashboard or SQLite bullet (use the one that flows best):

```
- An MCP server for local agent access (optional install: `uv sync --extra mcp`). See [mcp/README.md](mcp/README.md).
```

One line. No paragraph. No "powerful new way" framing. The README's calm
tone is already correct; don't break it.

## `.adx/commands.json` touch

Add an entry for the new `devsec-mcp` command in the appropriate section
of `.adx/commands.json` (read the file first, follow the existing schema).
Mark it as a long-running stdio server, not a one-shot command.

## `AGENTS.md` touch

Add one line under `## Operating Rules` near the bottom:

```
- The MCP adapter (`devsec-mcp`) exposes read-only access to scan results. It is stdio-only and does not open a network port. See [mcp/README.md](mcp/README.md).
```

## Acceptance criteria — you are done when all of these pass

1. `uv sync --extra mcp` completes successfully (the `mcp` SDK installs).
2. `uv run pytest tests/test_mcp_server.py -v` is fully green (all 9+ tests pass).
3. `uv run devsec-mcp` starts the server without error. Verify with a single
   JSON-RPC `tools/list` request via stdin — the response should list exactly 6 tools.
   (One way: `echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | uv run devsec-mcp` —
   adjust to whatever the SDK expects for stdio one-shot calls.)
4. The full test suite `uv run pytest` does not regress beyond the existing
   `tests/test_ai_static.py` failures (those are pre-existing, known debt —
   leave them alone, do not fix them in this session).
5. Two commits, both clean:
   - **Commit 1**: `src/security_observatory/mcp_server.py` + `tests/test_mcp_server.py` + `pyproject.toml` changes — the adapter + tests.
   - **Commit 2**: `mcp/README.md` + `README.md` one-line touch + `.adx/commands.json` entry + `AGENTS.md` entry — the docs and integration.
6. **Do NOT push.** Christian reviews locally before pushing. Leave commits
   in place; he will `git push origin main` after review.

## Sizing reality check

This is 2-4 hours of focused work. **If it's taking longer than 4 hours,
scope creep has happened.** Stop, surface the issue, do not silently expand
the surface. The six tools above are the entire scope; do not add a seventh.

## Report back when done

Final output should include, in order:

- Files created (list with line counts)
- Files modified (list)
- Test results: `X passed, Y failed in Z.Zs`
- Confirmation that `devsec-mcp` starts and responds to `tools/list` with 6 tools (paste the actual response)
- Confirmation that full suite has the same pre-existing failures (no new regressions)
- Two commit SHAs with one-line subjects
- Any decisions deferred or scope tensions encountered, in one paragraph
- The exact command Christian should run to launch the server for the first time, end-to-end

## What success looks like

A visitor who runs `uv sync --extra mcp`, edits their Claude Desktop config
per `mcp/README.md`, restarts Claude Desktop, and asks
*"What are the open critical cases in the dëv-security repo?"* — gets a
real answer pulled from their own local scan history, via the agent,
without any cloud round-trip or HTTP listener. That's the bar.
