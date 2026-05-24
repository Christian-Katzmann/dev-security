# Three differentiator commands for the DëvSec MCP

> Adds three smart shortcuts to the local security tool — see what changed since last time, turn a security finding into a ready-to-review fix in one move, and check on the honeypot traps you've planted to catch attackers.

## Scope

Ship three new slash commands (`/devsec-diff`, `/devsec-pr`, `/devsec-honey`) that lean into DëvSec's structurally unique surface: local-first scan history, cases-as-primary-unit, and built-in Honey Keys active defense. Two of the three commands need new read-only MCP tools first (`scan_history`, `cases` extended with `scan_id`, and `honey_keys`) because the current 6-tool surface only exposes the *latest* scan and has no Honey Key visibility at all. After the MCP layer is extended, write the three slash commands as user-scoped markdown files, update the `/devsec` dashboard menu to surface them, and verify end-to-end by starting a fresh Claude Code session.

Done when: the MCP server lists ≥9 tools (the 6 existing + honey_keys + scan_history + the extended cases signature counts as one), the three new commands render in `/devsec`'s menu and execute against real scan history, the full pytest suite passes with no regressions, and the MCP-layer commit is in place on `main` locally (not pushed — Christian reviews before pushing).

## Context (locked decisions)

- **Three commands, no more.** `/devsec-diff`, `/devsec-pr`, `/devsec-honey`. We deliberately rejected `/devsec-ask`, `/devsec-explain`, `/devsec-quiz` as ceremonial or duplicative.
- **MCP stays read-only.** `/devsec-pr` writes git state via `gh pr create` from the slash-command layer; it does NOT add a write tool to the MCP. The security store is never mutated by the agent.
- **Repo work vs operator-config work split.** Phase 1 (MCP tools) lives in the dëv-security repo, gets committed. Phase 2 + 3 (slash commands, dashboard update) live in `~/.claude/commands/` — operator config, not version-controlled in this repo.
- **No push.** Christian reviews each commit locally before pushing to `origin/main`.
- **Honey Keys MCP tool is the architectural gap from the original session.** The original 6-tool scope deliberately excluded write tools and out-of-scope surfaces; Honey Keys data was missing from the read surface and is the load-bearing addition this campaign makes.
- **Slash commands stay at user scope** (`~/.claude/commands/`), matching the existing `/devsec` set so they're available in any project.
- **Existing 6-tool MCP surface is the contract baseline.** New tools added, existing tool signatures only extended (backwards-compatible defaults). No breaking changes.
- **Tests are non-optional.** Every new MCP tool gets at least: empty-DB shape test, seeded-data shape test, error-shape test. Pattern lives in `tests/test_mcp_server.py`.
- **No absolute paths in tool output** is an invariant — covered by an existing test that must continue to pass.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Extend the MCP read surface

- [ ] Step 1.1 — Add `honey_keys`, `scan_history`, and `scan_id`-aware `cases` to mcp_server.py (tool + tests + docs + commit)

### Phase 2 — Build the three slash commands

- [ ] Step 2.1 — Write `/devsec-diff` (temporal delta)
- [ ] Step 2.2 — Write `/devsec-pr` (case → PR via `gh pr create`)
- [ ] Step 2.3 — Write `/devsec-honey` (Honey Key visibility)

### Phase 3 — Wire-up and end-to-end verification

- [ ] Step 3.1 — Update `/devsec` dashboard menu to surface the three new commands; manual verification in a fresh Claude Code session
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Extend the MCP read surface

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Extend `src/security_observatory/mcp_server.py` with the read-only tools the three new slash commands need. This is one coherent change: three small additions to the same module, sharing the same test fixture, committed together.

What to add:

1. **`honey_keys()`** — list every Honey Key with status (active/triggered/archived), placement project, age, and most recent trigger event (if any). Wraps `ObservatoryDB.list_honey_keys()`, `list_honey_key_events()`, and `project_statuses()`. Return shape: `[{id, project_id, status, placed_at, placement_repo, trigger_count, last_triggered_at, severity_if_triggered}]`. Cap at 100 keys; sort triggered-first then by recency.

2. **`scan_history(repo, limit=10)`** — list previous scans for a repo, most-recent-first. Direct SQL against the `scans` table. Return shape: `[{scan_id, started_at, finished_at, health_score, finding_count, status}]`. Bounded `limit` (max 50). Raises `RepoNotFoundError` for unknown repos.

3. **Extend `cases(repo, status=None, scan_id=None)`** — accept an optional `scan_id` that overrides "latest scan." Default behavior is unchanged. When `scan_id` is provided, use `db.scan_export(scan_id)` directly instead of resolving the latest scan first. Validate the `scan_id` belongs to `repo`; if not, raise `ValueError` with a clear message.

Tests (extend `tests/test_mcp_server.py`):

- Update `test_server_lists_expected_tools` to expect 8 tools (6 + `honey_keys` + `scan_history`).
- Add `test_honey_keys_empty_returns_list`, `test_honey_keys_returns_normalized_shape` with one fixture key, `test_honey_keys_includes_trigger_event` with a fixture trigger.
- Add `test_scan_history_empty_raises`, `test_scan_history_returns_recent_first`, `test_scan_history_limit_caps`.
- Add `test_cases_accepts_explicit_scan_id` and `test_cases_rejects_scan_id_from_other_repo`.
- All existing tests must still pass — especially `test_no_absolute_paths_in_output`.

Docs:

- Update `mcp/README.md`'s tool table to include the two new tools and the extended `cases` signature.
- Update `mcp/README.md`'s one-paragraph summary if needed (still six? now eight? state it plainly).
- Update `.adx/commands.json` entry for `devsec-mcp` if the long-running stdio description references "6 tools" anywhere (likely not, but check).

Verify:

- `uv run pytest tests/test_mcp_server.py -v` — all green.
- `uv run pytest` — full suite, no regressions.
- Stdio JSON-RPC smoke test: pipe `tools/list` into `uv run devsec-mcp`, confirm 8 tools come back.

Commit:

- One clean commit: `Extend MCP read surface with honey_keys, scan_history, and scan_id-aware cases`.
- Co-author line as per repo convention.
- DO NOT push.

```text
/health-implement

SCOPE: Extend src/security_observatory/mcp_server.py with three additions — honey_keys() tool, scan_history(repo, limit) tool, and an optional scan_id parameter on the existing cases() tool. All read-only, all wrapping existing ObservatoryDB methods.

REQUIRED READING:
1. mcp/SESSION-PROMPT.md (original 6-tool scope + hard rejections — these still apply to the additions)
2. src/security_observatory/mcp_server.py (existing 6-tool surface; copy the conventions)
3. tests/test_mcp_server.py (test fixture pattern with _seed_scan helper)
4. src/security_observatory/storage.py — methods list_honey_keys, list_honey_key_events, project_statuses, latest_scan_for_repo, scan_export, the scans table schema
5. mcp/README.md (tool table to update)

OUTPUT: 
- src/security_observatory/mcp_server.py — three additions, no breaking changes
- tests/test_mcp_server.py — new tests for the three additions + update of the expected-tool-count assertion
- mcp/README.md — table updated, tool count corrected
- One git commit; do not push

OPEN QUESTIONS:
- For honey_keys: should we expose trigger event details (timestamp, summary) or just a trigger_count + last_triggered_at? Lean toward minimal — the dashboard surfaces details; the agent just needs to know IF and HOW RECENTLY.
- For scan_history: how should "status" be derived? Look at the scans table — there's a status column. Pass it through verbatim.
- For cases(scan_id=): what error shape is most agent-friendly when the scan_id is unknown or belongs to a different repo? Match the pattern of test_repo_not_found_returns_clear_error.
- Are there any rough edges in storage.py public API surface that argue for a small wrapper helper before exposing? Read the methods first; if they need wrappers, add minimal ones in mcp_server.py — DO NOT add new methods to storage.py.

Read carefully before changing anything — the original session enforced strict scope discipline (no write tools, no new query methods in ObservatoryDB, no absolute paths in output). Those rules carry over.
```

## Step 2.1 — Write `/devsec-diff`

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 2.2 and 2.3

Write the `/devsec-diff [since]` slash command to `~/.claude/commands/devsec-diff.md`. The command answers the most-asked daily security question — "what changed since last time?" — with scan-history-aware deltas.

Behavior:

- Argument `since` (optional) parses to one of: empty (default to previous scan), `last`, `Nd` (N days ago), `since YYYY-MM-DD`, or `since <commit>`. If commit form is used and there's no scan after that commit, fall back to "previous scan" with a one-line note.
- Resolves the comparison scan via the new `scan_history` MCP tool.
- For each repo (or just one if `$ARGUMENTS` is a repo name): fetch `cases(repo, scan_id=<current>)` and `cases(repo, scan_id=<since>)`, diff by `case_id`.
- Categorize the diff into: new (in current, not in since), resolved (in since, not in current), severity-shifted (same id, different severity), recurring (same id, same severity).
- Print a compact table. Cap output at 25 rows.

Format (target — adjust as the prompt drafts):

```
DëvSec — changes since <since-description>

| Repo | Δ | Sev | Category | Title |
| --- | --- | --- | --- | --- |
| ... | new | critical | secrets | ... |
| ... | resolved | high | dependencies | ... |
| ... | ↑ med→high | medium | code-security | ... |
```

Below the table: one line summarizing counts ("3 new, 1 resolved, 1 severity shift across 2 repos. 0 recurring shown.").

Follow the conventions in the existing `~/.claude/commands/devsec.md` and `~/.claude/commands/devsec-cases.md` (calm tone, no emoji, capped length, table format).

```text
/skill-creator

SCOPE: Write a single slash command markdown file — `~/.claude/commands/devsec-diff.md` — that uses the devsec MCP server to answer "what changed since last time" with a scan-to-scan delta.

REQUIRED READING:
1. ~/.claude/commands/devsec.md (the home dashboard — conventions, tone, format)
2. ~/.claude/commands/devsec-cases.md (closest sibling — table format, filtering, length cap)
3. The 8-tool MCP surface (delivered by Step 1.1) — specifically scan_history and the cases(scan_id=) signature
4. /Users/christiankatzmann/Dev/Projects/dëv-security/mcp/README.md (tool descriptions)

OUTPUT: A single file at ~/.claude/commands/devsec-diff.md following the existing /devsec-* convention (frontmatter name + description + argument-hint, then the prompt body with tool-call instructions and an exact format spec).

OPEN QUESTIONS:
- How should "since <commit>" be resolved when there's no scan after that commit? Fall back gracefully — show the note, use the previous scan.
- For the severity-shift indicator: which direction is "↑" — increasing risk (critical is up) or decreasing? Decide one and stick to it. Increasing risk = ↑, document it in the command body so the agent prints a small legend if needed.
- Should the command default to all repos or to the repo with the most-recent scan if no repo is specified? Lean: all repos, but cap to top 25 rows so it doesn't sprawl.
- What's the right default for `since` when omitted? Previous scan for the most-recently-scanned repo. State this explicitly in the command.

Tone: calm, no emoji, factual. Cap at 30 lines of output. Follow the same prompt-engineering style as the existing devsec slash commands — specify exact tools to call, exact output format, exact length cap, and the rules section at the bottom.
```

## Step 2.2 — Write `/devsec-pr`

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 2.1 and 2.3

Write `/devsec-pr <case_id>` to `~/.claude/commands/devsec-pr.md`. This command closes the loop from a case to a real PR, with the case's `agent_handoff_prompt` and `plain_english_risk` baked into the PR description.

Behavior:

- Arg: `<case_id>` (required). If missing, list open cases via `cases()` across repos and ask which one.
- Resolve the case across repos by calling `list_repos` then `cases(repo)` until found. Cap the search to avoid sprawl.
- Read the case's `affected_files`, `agent_handoff_prompt`, `plain_english_risk`, `suggested_steps`.
- The agent applies the fix using its normal coding tools — NOT through MCP. Constrain scope: one case, one fix, one PR. No bundling.
- Create a new branch (`fix/devsec-<case_id>` or similar) before editing.
- Run `gh pr create` with title `Security fix: <case title>` and body containing: plain English risk, suggested steps, the `case_id` for traceability, and a "This was guided by `/devsec-pr <case_id>`" footer.
- Print the PR URL.

Critical constraints (state these explicitly in the command body):

- **One case per PR.** Resist bundling fixes for sibling cases.
- **The MCP is read-only.** The case status in DëvSec does NOT get updated by this command. Marking the case fixed (`fixed`, `verified`) is a separate human action via the dashboard/CLI.
- **Surface what was changed before opening the PR.** Print the diff summary so the user can abort if scope drifted.
- **Don't push if `gh` is not authenticated** — surface the auth state, suggest `gh auth login`, stop.

```text
/skill-creator

SCOPE: Write a single slash command markdown file — `~/.claude/commands/devsec-pr.md` — that turns a DëvSec case into a real GitHub PR via `gh pr create`, with the case context baked into the PR body.

REQUIRED READING:
1. ~/.claude/commands/devsec.md (conventions, calm tone)
2. ~/.claude/commands/devsec-fix.md (closest sibling — case resolution pattern; this command is the active-fix counterpart)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/mcp/README.md (the cases tool shape — affected_files, agent_handoff_prompt, plain_english_risk)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/PROVOCATION.md (why local-first matters — informs the PR description tone)
5. (For reference, not editing) /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py — the SecurityCase shape

OUTPUT: A single file at ~/.claude/commands/devsec-pr.md following the existing /devsec-* convention.

OPEN QUESTIONS:
- Should the command stop and ask the user to review before pushing the branch and opening the PR? Yes — the PR is irreversible from the agent's side once opened (well, closeable, but conspicuous). One confirmation step before `gh pr create` is warranted. State explicitly in the command body.
- What if the case spans multiple repos? It shouldn't — cases are per-repo. If somehow the case_id is ambiguous across repos, surface that and ask which.
- How should the agent handle a case whose affected_files list is empty? Refuse to proceed — there's nothing to fix without a target file. Tell the user the case is too abstract for /devsec-pr; suggest /devsec-fix instead.
- Should the PR body include the agent_handoff_prompt verbatim? Yes — that's the architectural differentiator. The reviewer sees what guided the fix.

This is the most architecturally risky of the three commands (it writes git state). Lean conservative: confirmation gates, one-case-one-PR discipline, clear "the MCP is still read-only — the case status in DëvSec does not auto-update" disclaimer at the bottom of the printed output.
```

## Step 2.3 — Write `/devsec-honey`

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 2.1 and 2.2

Write `/devsec-honey` to `~/.claude/commands/devsec-honey.md`. Surfaces the Honey Key state — what decoys are placed where, which (if any) have triggered, and the response posture for each project. Uses the new `honey_keys` MCP tool from Step 1.1.

Behavior:

- No required args. Optional `<project>` filters to one project.
- Call `mcp__devsec__honey_keys()` (the tool added in Step 1.1).
- Group by project. Per project: count of active keys, count of triggered keys (with red-flag visibility), oldest placement age, most recent trigger.
- For triggered keys: surface in a dedicated alert block at the top, BEFORE the overall table. This is the load-bearing case — a triggered honey key is potentially an active exfiltration event.

Format:

```
Honey Keys — <project filter description if any>

⚠ Triggered:
  · <project> — <key_id> placed <when>, triggered <when>. Severity: <high|critical>.
  · (only if triggers exist; otherwise omit this block entirely — no "no triggers" line)

Placements:

| Project | Active | Triggered | Oldest | Last trigger |
| --- | --- | --- | --- | --- |
| ... | 3 | 0 | 14d ago | — |
| ... | 1 | 1 | 22d ago | 2h ago ⚠ |
```

Below the table: if any project has zero Honey Keys, suggest placing some via the dashboard. If all projects have ≥1 Honey Key with no triggers, say "no triggers, all decoys in place" — calmly, no celebration.

The use of one `⚠` is justified here because triggered Honey Keys are genuinely critical events; this is the one place the no-emoji rule is relaxed. Document the exception in the command body so the agent doesn't over-generalize.

```text
/skill-creator

SCOPE: Write a single slash command markdown file — `~/.claude/commands/devsec-honey.md` — that surfaces local Honey Key state via the new mcp__devsec__honey_keys tool (delivered by Step 1.1), with explicit alert handling for any triggered keys.

REQUIRED READING:
1. ~/.claude/commands/devsec.md (conventions; this is a sibling)
2. ~/.claude/commands/devsec-deps.md (closest format sibling — table sorted by risk, callouts under the table)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/mcp/README.md (the honey_keys tool description — read what shape it returns)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/honey-keys.md (if it exists — the project's honey-keys design rationale)
5. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/threat-model.md (Honey Key risk #4 — false-alarm vs real exfiltration trade-off)

OUTPUT: A single file at ~/.claude/commands/devsec-honey.md following the existing /devsec-* convention.

OPEN QUESTIONS:
- Should the triggered-keys block include the per-trigger evidence (path, timestamp) or just the count? Lean: name the project and key_id and trigger time. Path-level detail is dashboard work; the slash command's job is to alert and orient.
- How should we handle archived keys (the `archived` status)? Suppress from the table by default; mention in a footer if the count is non-zero.
- Should we suggest follow-up actions when a key has triggered? Yes — one line: "Open the dashboard for incident response. See docs/honey-keys.md for the playbook." Don't try to walk the playbook inline — that's `/devsec-fix` territory.
- The ⚠ emoji exception: document it explicitly in the command's "Rules" section so future maintainers don't whitescrub it.

This command's job is twofold: ambient visibility (which keys exist) AND alert escalation (which fired). The two are connected — visibility makes alerts intelligible. State both jobs at the top of the command body so the format reflects them.
```

## Step 3.1 — Update `/devsec` menu and verify end-to-end

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

Two small artifacts and one manual verification:

1. **Update `~/.claude/commands/devsec.md`** — the home-dashboard command. Add three rows to the commands menu table so users discover the new commands:

| Command | Use it when |
| --- | --- |
| `/devsec-diff [since]` | You want to see what changed since last time — new cases, resolved cases, severity shifts. |
| `/devsec-pr <case_id>` | You want to turn a case into a real GitHub PR, with the case context baked in. |
| `/devsec-honey` | You want to see your Honey Key placements and whether any have triggered. |

Keep the existing rows. Order: brief, cases, fix, deps, diff, pr, honey.

2. **Manual verification.** Start a fresh Claude Code session (or `claude /restart` in this one) and run:
- `/devsec` — confirm the dashboard renders, all 7 commands (existing + 3 new) appear in the menu.
- `/devsec-honey` — should return Honey Key state (likely empty if none placed; that's a valid state).
- `/devsec-diff` — should diff against the previous scan if there is one; gracefully say "only one scan on record" if not.
- `/devsec-pr <some-real-case-id>` — only run this if you have a real low-stakes case and feel like exercising it end-to-end; otherwise skip and rely on a dry-run prompt-read.

3. **No commit at this step.** Phase 1's commit landed in the dëv-security repo. The slash commands live in `~/.claude/commands/` and are not part of any repo. There is nothing to commit here.

```text
/skill-creator

SCOPE: Update ~/.claude/commands/devsec.md to add three new rows to the commands menu table (devsec-diff, devsec-pr, devsec-honey), preserving the existing rows and conventions.

REQUIRED READING:
1. ~/.claude/commands/devsec.md (the file being edited)
2. ~/.claude/commands/devsec-diff.md (the new sibling — read for one-line description accuracy)
3. ~/.claude/commands/devsec-pr.md (the new sibling)
4. ~/.claude/commands/devsec-honey.md (the new sibling)

OUTPUT: An updated ~/.claude/commands/devsec.md with the three new menu rows in place. Nothing else changes.

OPEN QUESTIONS:
- Order of rows in the menu — keep the original five at the top and add the new three below? Or interleave by use-frequency? Lean: keep originals first, new three below — preserves muscle memory for existing users.
- Does the dashboard need to suggest /devsec-diff prominently (e.g., when the same case appears across multiple scans)? Not in this step — surfacing recommendations is a future polish.

After the edit, the user will manually verify by starting a fresh Claude Code session and running each command. Surface any rendering issues immediately.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the devsec-power-commands campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-power-commands.md
Campaign: campaigns/devsec-power-commands.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff (for Phase 1) and the actual files in ~/.claude/commands/ (for Phase 2 and 3) that the criteria actually landed. Don't trust step receipts — read the diff and read the markdown files.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas. Specifically watch for:

- Did the MCP layer stay strictly read-only? (No write tools in mcp_server.py.)
- Does /devsec-pr actually shell out to `gh pr create` — or did it accidentally land an MCP write tool?
- Does the no-absolute-paths-in-output test (test_no_absolute_paths_in_output) still pass after the new tools landed?
- Does the /devsec dashboard menu list all three new commands, in addition to the originals?
- Are the three slash commands consistent in tone and format with the existing /devsec-* set?

Be honest. Lean. APPROVED if every step's acceptance criteria landed and there are no cross-step regressions. NEEDS WORK if any step cut corners or a primitive was bypassed.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.7 with Extra High thinking
(Your call — both are acceptable for this kind of cross-file review.)
```

**Verdict-to-action mapping:**

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign"). Campaign is done.
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick the checkbox until APPROVED.
