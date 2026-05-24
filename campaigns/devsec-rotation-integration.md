# 4 · DëvSec rotation integration — one-click rotation from the dashboard

> Builds on the rotation foundation from campaign #3 — adds a button to the DëvSec dashboard and a slash command so the user can rotate a leaked secret with one click and read a "you are safe" report in DëvSec's calm voice. This is the visible feature that closes the detect → explain → rotate → verify loop.

## Scope

Three integration layers that turn the universal rotation skill (delivered by campaign #3) into a load-bearing DëvSec feature:

1. **MCP read tools** — add `rotation_status(repo)` and `rotation_history(repo)` to the existing `devsec` MCP server so agents can ask "what's the rotation state of X?" and get an answer pulled from the skill's state files. MCP stays read-only; no rotation-triggering tool is added.

2. **Dashboard surface** — add a rotation status card to the DëvSec dashboard showing per-secret status (matches the skill's status board UX), a "Rotate now" button that shells out to the skill via subprocess, and a "Set up rotation" CTA for repos where the skill hasn't been scaffolded yet. Renders the skill's verification report inline in the Security Brief format from campaign #2's calibration examples.

3. **Slash command + case integration** — write `/devsec-rotate <secret>` that shells out to the skill (same pattern as the planned `/devsec-watch`). Update `/devsec` menu to surface it. Update secrets-category case rendering so the case carries a "Rotate this" affordance when rotation is set up for the repo.

Done when: a user can find a leaked credential in a DëvSec scan, click "Rotate this case" in the dashboard, watch the rotation pipeline run through the verification report, and see the case transition to resolved — with full agent observability through the MCP read tools. The agent can also walk the same flow via `/devsec-cases` → `/devsec-rotate <case_id>`.

## Context (locked decisions)

- **Hard dependency: campaigns 1, 2, 3 must all be complete before this campaign runs.** Step 0.1 verifies this and refuses to proceed if any are missing.
- **MCP stays read-only.** No `rotate()` write tool. The two new tools (`rotation_status`, `rotation_history`) wrap the skill's state files. Mutation happens via the dashboard (human-clicked) or via the slash command (human-invoked) — both shell out to the skill, neither goes through MCP.
- **Dashboard owns the write surface.** The "Rotate now" button shells out to `npm run rotate <secret>` (or the appropriate adapter command) via subprocess. The dashboard has always been the human's write surface; this extends what it can trigger. The architectural contract: anything the agent can do via MCP is read-only; anything that writes goes through a human-clicked UI or human-typed command.
- **Slash command `/devsec-rotate <secret>` shells out via Bash.** Same pattern as the planned `/devsec-watch`. The MCP doesn't grow a write tool; the slash command coordinates the trigger via shell-out.
- **Verification report displayed in the dashboard matches the Security Brief format** from campaign #2's `calibration-examples.md` #10. The skill (after campaign #3) already writes this file to `data/rotation-receipts/<secret>-<timestamp>.md`; the dashboard reads and renders it. No second format invented.
- **Rotation is Tier 5 per the safety doctrine.** Confirmation gates apply per `docs/agent-safety.md`. Dashboard "Rotate" button has a confirmation modal; `/devsec-rotate` slash command body carries the Tier 5 language template. Both surfaces explain the cost in DëvSec's voice before acting.
- **Per-repo opt-in.** Rotation requires the skill to be scaffolded into that repo first. Dashboard shows a "Set up rotation" CTA for repos without it. The CTA launches the skill's scaffolding flow via subprocess.
- **Secrets-category cases get a "Rotate this" affordance.** In `/devsec-cases` table output (when the case category is `secrets` and rotation is available for the repo), in the dashboard case card, and in the case-resolution flows. Affordance points at the dashboard rotate button OR at `/devsec-rotate <case_id>` depending on surface.
- **No new MCP server.** All new tools added to the existing `devsec` MCP at `src/security_observatory/mcp_server.py`. The MCP grows from 8 tools (after campaign #1) to 10 tools.
- **The skill's verification receipt is the source of truth for "rotation succeeded".** Dashboard renders the receipt; doesn't generate its own. Two sources of truth = silent drift later.
- **Auto-detection of rotation state during scans.** Each DëvSec scan should detect whether each tracked repo has rotation set up (by checking for `data/rotation-state.json` in the repo) and surface that signal in the scan output. This makes "Set up rotation" CTAs auto-appear in the dashboard without manual configuration.
- **No queue / async approval flow.** The dashboard "Rotate" button → confirmation modal → confirmation triggers rotation via shell-out. Simpler than queue-then-approve; v0.1 doesn't need queueing.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

**Important note about prompts in this campaign:** because campaigns 1-3 may evolve between when this campaign was written and when it's executed, several fields in the steps below are marked `(populated by Step 0.1)`. Step 0.1 reads the actual current state of campaigns 1-3 outputs and surgically edits those fields in place. Do NOT skip Step 0.1.

## Progress checklist

### Phase 0 — Self-recalibrate before doing anything

- [ ] Step 0.1 — Verify campaigns 1-3 complete; audit their actual outputs; surgically edit Phase 1-3 prompts to reference real artifacts

### Phase 1 — Add rotation MCP read tools

- [ ] Step 1.1 — Add `rotation_status(repo)` and `rotation_history(repo)` to the existing devsec MCP server

### Phase 2 — Wire DëvSec dashboard to show + trigger rotations

- [ ] Step 2.1 — Add rotation status card to the dashboard (read-only display + "Set up rotation" CTA)
- [ ] Step 2.2 — Add "Rotate now" trigger UI (per-secret button, confirmation modal, verification report rendering)

### Phase 3 — Slash command + case integration

- [ ] Step 3.1 — Write `/devsec-rotate <secret>` slash command and update `/devsec` menu
- [ ] Step 3.2 — Update case rendering across surfaces so secrets-category cases offer "Rotate this"

### Phase 4 — End-to-end verification

- [ ] Step 4.1 — Manual run-through in a fresh Claude Code session; rotate a synthetic secret from each surface
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 0.1 — Verify dependencies; audit; recalibrate the rest

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

This campaign was written immediately after campaign #3 was drafted but before campaigns 1-3 shipped. The actual artifact shapes (MCP tool names, slash command formats, doctrine documents, rotation skill state-file shapes, verification receipt format) may have shifted between authoring and execution. Before doing any new work, audit current state and surgically edit the rest of this campaign's prompts in place.

**Authority bounds:**

- MAY update `REQUIRED READING`, acceptance criteria, `OPEN QUESTIONS`, model/parallel lines for Steps 1.1, 2.1, 2.2, 3.1, 3.2, 4.1.
- MAY merge or split steps within Phases 1-3 if the actual artifact shapes require it.
- MAY NOT silently add a phase, weaken intent, or change the locked decisions in this campaign's `## Context` block.
- MUST produce a short audit report at `campaigns/devsec-rotation-integration/notes/phase-0-audit.md` documenting what was found and what was changed in this campaign markdown.
- MUST refuse to proceed if any of campaigns 1, 2, 3 is incomplete. State which is missing, suggest the user complete it first, halt.

**Dependency verification checklist:**

1. **Campaign 1 (`devsec-power-commands.md`) shipped?**
   - Verify: `src/security_observatory/mcp_server.py` has 8 tools listed in `_tool_manager` (the original 6 + `honey_keys` + `scan_history`).
   - Verify: `~/.claude/commands/devsec-diff.md`, `devsec-pr.md`, `devsec-honey.md` exist.
   - If not shipped: HALT with "Campaign 1 (devsec-power-commands) is not complete. This campaign's MCP additions assume that work landed. Run campaign 1 first."

2. **Campaign 2 (`devsec-agent-doctrine.md`) shipped?**
   - Verify: `docs/agent-voice.md` and `docs/agent-safety.md` exist.
   - Verify: MCP `instructions` field in `mcp_server.py` carries the doctrine distillation.
   - Verify: All existing `/devsec-*` slash commands have a "Voice" section referencing the doctrine.
   - Verify: `~/.claude/commands/devsec-voice.md` exists.
   - If not shipped: HALT with "Campaign 2 (devsec-agent-doctrine) is not complete. This campaign's UX language depends on the doctrine being authoritative. Run campaign 2 first."

3. **Campaign 3 (`devsec-rotation-foundation.md`) shipped?**
   - Verify: `~/.claude/skills/secrets-rotation/templates/adapters/` exists with `vercel.ts.tmpl` and `python-cli.ts.tmpl`.
   - Verify: The skill's pipeline has the SOAK phase + verification report writer.
   - Verify: Sample receipts at `campaigns/devsec-rotation-foundation/notes/sample-receipts/` show the actual report format the dashboard will need to render.
   - If not shipped: HALT with "Campaign 3 (devsec-rotation-foundation) is not complete. This campaign's dashboard depends on the skill's v0.2 verification receipt format. Run campaign 3 first."

**Audit findings to capture in `phase-0-audit.md`:**

- **MCP tool inventory.** List all tools currently in `mcp_server.py`. Capture exact signatures. Updates to Phase 1's prompt may follow.
- **Doctrine artifact paths.** Confirm `docs/agent-voice.md` and `docs/agent-safety.md` are the actual paths (not e.g. `docs/agent/voice.md`). Tier 5 language template — quote the exact text from `agent-safety.md`. Updates to Phase 2's prompt may follow.
- **Verification receipt format.** Read a sample receipt from `campaigns/devsec-rotation-foundation/notes/sample-receipts/` (delivered by campaign 3). Confirm the markdown shape the dashboard needs to render. Capture the exact section headers + bullet structure.
- **Skill invocation entry point.** Confirm whether the skill is invoked as `npm run rotate <secret>` (Vercel projects) or some other command for Python CLI projects. If the v0.2 skill normalized this, capture the unified entry. Updates to Phase 2.2's shell-out invocation may follow.
- **Slash command conventions.** Re-read `~/.claude/commands/devsec.md`, `devsec-fix.md`, `devsec-pr.md` (closest siblings) to confirm format conventions for the new `/devsec-rotate` command.
- **Dashboard code surface.** Locate the dashboard server (`src/security_observatory/dashboard_server.py`) and the React UI (`dashboard-ui/`). Capture the existing patterns for case cards, status displays, and POST endpoints so the rotation card matches the existing design language.

**In-place edits to this campaign markdown:**

For each `(populated by Step 0.1)` placeholder in Steps 1.1, 2.1, 2.2, 3.1, 3.2: replace with the actual reference based on what was audited. Mark every edited step with "Updated by Step 0.1: <change reason>" at the top of its body, so a reviewer can see what shifted from the draft.

```text
/health-implement

SCOPE: Verify campaigns 1-3 are complete; audit their actual outputs; surgically edit the rest of this campaign's prompts in place. Refuse to proceed if any of campaigns 1-3 is incomplete.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-integration.md — this campaign (you will edit Phase 1-3 step prompts in place)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-power-commands.md — campaign 1 (verify complete)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-agent-doctrine.md — campaign 2 (verify complete)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-foundation.md — campaign 3 (verify complete)
5. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/mcp_server.py — current MCP tool surface
6. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/agent-voice.md (if exists) — doctrine
7. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/agent-safety.md (if exists) — safety tiers, especially Tier 5 template
8. ~/.claude/commands/devsec*.md — all existing slash commands; convention reference
9. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py — dashboard server
10. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/ — dashboard React UI
11. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-foundation/notes/sample-receipts/ (if exists) — actual verification report format the dashboard will render
12. ~/.claude/skills/secrets-rotation/SKILL.md — current state of the rotation skill (post-campaign-3)

OUTPUT:
- campaigns/devsec-rotation-integration/notes/phase-0-audit.md (audit report)
- In-place edits to Steps 1.1, 2.1, 2.2, 3.1, 3.2 in this campaign markdown (replace "(populated by Step 0.1)" placeholders with actual references; mark each edited step with "Updated by Step 0.1: <reason>")

OPEN QUESTIONS:
- Are all three dependency campaigns complete? If not, halt and report.
- Did any of campaigns 1-3 change a locked decision in a way that affects this campaign? Specifically: did the MCP boundary become writable in any way? Did the Tier 5 template change? Did the verification receipt format change? Flag any divergence.
- Is there work in the dashboard / MCP / skill that this campaign now duplicates (e.g., did campaign 3 add a partial dashboard already)? If so, recommend removing the duplication.

Do not start any new work. This step is exclusively about ensuring the rest of the campaign's prompts reference real, current artifacts.
```

## Step 1.1 — Add `rotation_status` and `rotation_history` MCP read tools

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

(populated by Step 0.1 — required reading and acceptance criteria below assume the post-campaign-1 MCP shape, which may have shifted)

Add two read-only tools to the existing devsec MCP server. They expose the rotation skill's state files to agents so the agent can answer "what's the rotation state of X repo?" without shelling out.

**Tool: `rotation_status(repo)`** — returns the current rotation state for every secret in the named repo. Reads from `<repo>/data/rotation-state.json` (the file the rotation skill writes). Returns:

```json
[
  {
    "secret": "AUTH_SECRET",
    "class": "A",
    "status": "ROTATED",
    "last_rotated_at": "2026-05-20T14:00:00Z",
    "days_since_rotation": 4,
    "cadence_days": 30,
    "next_rotation_due": "2026-06-19T14:00:00Z",
    "rotation_id": "abc123",
    "in_grace_until": null,
    "needs_attention": false
  },
  ...
]
```

Edge cases: repo not found → RepoNotFoundError. Repo found but rotation never set up → return empty list (no error). State file corrupt → return what's parseable, log the corruption, surface as "unknown" status entries.

**Tool: `rotation_history(repo, limit=20)`** — returns recent rotation events from `<repo>/data/rotation-log.jsonl`. Each event: timestamp, secret, phase (initiated/completed/halted/refused_unhealthy_baseline/soak_anomaly_detected), result. Most-recent first. Default limit 20, max 100.

Tests (extend `tests/test_mcp_server.py`):

- Update the tool-count assertion (was 8 after campaign 1; now 10).
- `test_rotation_status_no_rotation_setup_returns_empty_list` — repo has no `data/rotation-state.json`, returns `[]`.
- `test_rotation_status_returns_normalized_shape` — fixture state file with one ROTATED secret, one IN_GRACE secret; assert the shape.
- `test_rotation_status_corrupted_state_returns_partial` — corrupt JSON, returns what's parseable + unknowns.
- `test_rotation_history_returns_recent_first` — fixture log with 3 events; returns most-recent first.
- `test_rotation_history_limit_caps` — limit > 100 caps at 100.
- `test_rotation_tools_repo_not_found_raises_clear_error` — unknown repo, RepoNotFoundError.
- Verify the existing `test_no_absolute_paths_in_output` test still passes (rotation receipt paths returned should be repo-relative).

Docs:

- Update `mcp/README.md` tool table (add the two new rows, update tool count).
- Brief mention in the MCP `instructions` field that the server now surfaces rotation state.

Verify:

- `uv run pytest tests/test_mcp_server.py -v` all green.
- `uv run pytest` full suite, no regressions.
- Stdio JSON-RPC smoke test: pipe `tools/list` into `uv run devsec-mcp`, confirm 10 tools come back.

Commit: one clean commit, `Add rotation_status and rotation_history MCP tools`. Do not push.

```text
/health-implement

SCOPE: Add two MCP read tools to the existing devsec server — rotation_status(repo) and rotation_history(repo). Wrap the rotation skill's state files. Read-only; no rotation triggering through MCP.

REQUIRED READING:
1. campaigns/devsec-rotation-integration/notes/phase-0-audit.md (audit findings)
2. src/security_observatory/mcp_server.py (the existing 8-tool surface to extend)
3. tests/test_mcp_server.py (test pattern)
4. ~/.claude/skills/secrets-rotation/templates/lib/state.ts.tmpl — the state-file shape the tools read
5. campaigns/devsec-rotation-foundation/notes/sample-receipts/ — sample state files if available, for fixture inspiration
6. mcp/README.md — tool table to update
7. (populated by Step 0.1) — any tool-count or naming shifts from campaigns 1-2

OUTPUT:
- src/security_observatory/mcp_server.py — two new tools added
- tests/test_mcp_server.py — new tests + updated tool-count assertion
- mcp/README.md — updated table + tool count
- One git commit; do not push

OPEN QUESTIONS:
- For repos without rotation setup, return [] or raise a specific "RotationNotSetUpError"? Lean: return [] — it's a normal state, not an error. The dashboard can use the empty result to show the "Set up rotation" CTA.
- For corrupted state files: how loud should the error be? Lean: log warning, return what's parseable with unknown entries. Silent in MCP output (just unknowns), audible in stderr logs.
- The rotation skill writes state-file paths that may include absolute paths (the receipt file path). Test_no_absolute_paths_in_output must still pass — strip or relativize any paths in the MCP output.
```

## Step 2.1 — Rotation status card on the dashboard

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

(populated by Step 0.1 — references to existing dashboard components below assume the current React UI layout)

Add a read-only "Rotation Status" card to the DëvSec dashboard. Shows per-secret status (matching the skill's status board UX). For repos where rotation isn't set up, show a "Set up rotation" CTA instead.

**Backend (`src/security_observatory/dashboard_server.py`):**

Add new endpoints:

- `GET /api/rotation/status/<repo>` — calls the same logic as the `rotation_status` MCP tool; returns JSON of the per-secret status list.
- `GET /api/rotation/history/<repo>?limit=20` — same as `rotation_history` MCP tool.
- `GET /api/rotation/receipts/<repo>/<receipt-filename>` — serves a single verification receipt markdown file (path-traversal safe; only serves files matching `data/rotation-receipts/*.md` within the repo).

**Frontend (`dashboard-ui/`):**

Add a "Rotation Status" card to each repo's view. Card content:

If rotation IS set up (`status` endpoint returns non-empty):
- Per-secret rows matching the skill's status board format (status emoji, secret name, days-since-rotated, "needs attention" flag if overdue).
- Per the locked decision (no emoji): use words like ROTATED, IN GRACE, OVERDUE instead of symbols. Reserve the one `⚠` carve-out for IN_GRACE secrets approaching revoke time (consistency with the voice doctrine's Honey Key exception).
- Link "View history" → opens a panel with the last 20 rotation events.

If rotation IS NOT set up (empty result):
- "Rotation isn't set up for this repo."
- Plain-English explanation: "DëvSec can scaffold automated rotation for the secrets in this repo — leaked secrets become a single click to revoke and re-issue."
- "Set up rotation" CTA button. Clicking it opens a confirmation modal explaining what the scaffolding does (writes files into the repo, asks for catalog confirmation). On confirm, calls a backend endpoint that shells out to the rotation skill's scaffolding flow.
- For repos where the stack isn't supported (per the skill's v0.2 detection — Vercel + Python CLI only), show a different message: "This repo's stack isn't yet supported for automated rotation. Currently supported: Next.js + Vercel, Python CLI. More stacks coming."

**Scan integration:**

Each DëvSec scan should detect rotation state and persist it as scan metadata. Add a detection step to the scanner orchestration that checks for `data/rotation-state.json` in each tracked repo and stores the presence/absence in the scan output. This makes the dashboard card auto-appear or auto-show-CTA without manual configuration.

Acceptance criteria:

- Backend endpoints work and return valid JSON / markdown.
- Frontend card renders per the existing dashboard design language (match the visual hierarchy of other cards).
- "Set up rotation" CTA shells out correctly for repos where rotation isn't scaffolded.
- "Stack not supported" message renders for unsupported stacks.
- Path-traversal guard on the receipt-serving endpoint is tested with malicious input.
- Scan output now carries a rotation-state field per repo; tests added.
- DëvSec voice applies to all UI strings (calm, evidence-bound, no emoji except the named carve-out).

```text
/health-implement

SCOPE: Add a read-only "Rotation Status" card to the DëvSec dashboard with per-secret status display and a "Set up rotation" CTA for repos where it's not yet scaffolded. Add backend endpoints and scan-time detection.

REQUIRED READING:
1. src/security_observatory/dashboard_server.py — existing endpoints + pattern
2. dashboard-ui/ — existing card components (find the closest analog — a stable read-only card to mimic)
3. src/security_observatory/scanners.py — scan orchestration (where rotation-state detection slots in)
4. docs/agent-voice.md — voice for all UI strings
5. campaigns/devsec-rotation-integration/notes/phase-0-audit.md (audit findings)
6. (populated by Step 0.1) — exact dashboard React component conventions

OUTPUT:
- src/security_observatory/dashboard_server.py — three new endpoints with path-traversal safety
- dashboard-ui/ — new RotationStatusCard component + integration into repo view
- src/security_observatory/scanners.py — rotation-state detection added to scan output
- tests — endpoint tests, scan-output tests
- One git commit; do not push

OPEN QUESTIONS:
- Status display uses words (ROTATED, IN GRACE) not emoji per the voice doctrine. The one ⚠ carve-out: use only for IN_GRACE entries within 4h of revoke (operationally serious moment). Document this in the component.
- For multi-repo dashboards: should rotation card appear on every repo or only on repos with security findings? Lean: every repo. Rotation is preventative; it's part of repo posture, not finding-conditional.
- "Set up rotation" CTA: should clicking it shell out from the dashboard server (which is local) or instruct the user to run /secrets-rotation in their terminal? Lean: shell out — that's the whole point of the campaign (collapse rotation friction). But guard it heavily; this writes files into the user's repo.
- Backend rotation endpoints should reuse the MCP tools' implementation, not duplicate logic. Factor the rotation_status / rotation_history code into a shared module that both consume.
```

## Step 2.2 — "Rotate now" trigger UI with confirmation and verification report rendering

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

(populated by Step 0.1 — confirmation language pulled from docs/agent-safety.md Tier 5 template)

Add the rotation trigger UI to the dashboard. Per-secret "Rotate now" button. Confirmation modal in DëvSec's voice using the Tier 5 template. Shell-out execution. Verification report rendered inline once complete.

**Backend (`src/security_observatory/dashboard_server.py`):**

Add new endpoint:

- `POST /api/rotation/trigger/<repo>` — accepts JSON body `{ "secret": "AUTH_SECRET", "confirmed": true, "options": { "no_soak": false, "soak_minutes": 15 } }`. Shells out to the rotation skill via subprocess. Streams progress back to the client (server-sent events or WebSocket — match the existing dashboard pattern; if neither exists yet, use long-poll). On completion, returns the verification receipt path + status.

Safety:

- Require explicit `"confirmed": true` in the request body.
- Refuse the request if `--no-soak` is requested without an additional `"acknowledged_skipping_soak": true` field.
- Audit every trigger to scan history (which secret, when, who-via-dashboard, outcome).

**Frontend (`dashboard-ui/`):**

For each secret in the rotation card, add a "Rotate" action. Click flow:

1. Confirmation modal opens. Modal copy follows the Tier 5 template from `docs/agent-safety.md`. Format roughly:
   > **Rotating `AUTH_SECRET` now.**
   >
   > This will:
   > - Generate a new value at the provider (or for Class A, locally).
   > - Stage it to your `preview` deployment first.
   > - Verify against preview.
   > - Stage to production.
   > - Verify against production.
   > - Soak-test for 15 minutes by watching for auth-related errors.
   > - Keep the old key valid for 24h grace before revoking.
   >
   > Rotating `NEXTAUTH_SECRET` invalidates all active user sessions. (Conditional, only shown for secrets with `rotation_warning` in the catalog.)
   >
   > **[ Rotate now ]** **[ Cancel ]**
2. On confirm, the request is sent and a progress panel opens. Streams pipeline steps as they happen (`HEALTH_CHECK → ✓`, `PREFLIGHT → ✓`, etc.).
3. On completion, the verification receipt is fetched and rendered inline using the Security Brief format from campaign #2's `calibration-examples.md` #10.
4. The rotation status card auto-refreshes to show the new state (e.g., IN_GRACE).
5. If the rotation HALTS at any step, the HALT message and the recovery command from `errors.ts.tmpl` are shown plainly.

Verification report renderer:

- Markdown rendered with the dashboard's existing markdown renderer.
- "Copy" button to copy the receipt to clipboard (so the user can paste it into a Slack channel or attach to a PR).

Acceptance criteria:

- Trigger endpoint works end-to-end against a real (test-mode) rotation.
- Confirmation modal copy matches the Tier 5 template from `docs/agent-safety.md`.
- Progress UI streams pipeline steps in real time (or polls effectively if streaming is too much).
- Verification report renders inline in the Security Brief format.
- HALT cases render the plain-English message + recovery command.
- "Copy receipt" button works.
- Audit log captures every dashboard-triggered rotation.

```text
/health-implement

SCOPE: Add the rotation trigger UI (button + confirmation modal + progress panel + verification report rendering) to the DëvSec dashboard. Tier 5 confirmation language. Shell-out execution.

REQUIRED READING:
1. docs/agent-safety.md — Tier 5 confirmation language template (this is the exact copy for the modal)
2. docs/agent-voice.md — voice principles for the modal copy and progress messages
3. campaigns/devsec-agent-doctrine/notes/calibration-examples.md #10 — Security Brief format for the verification report rendering
4. src/security_observatory/dashboard_server.py — existing endpoint + streaming patterns
5. dashboard-ui/ — existing modal + progress UI components to reuse
6. ~/.claude/skills/secrets-rotation/templates/lib/errors.ts.tmpl — plain-English error messages for HALT cases
7. ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl — the entry point being shelled out to
8. campaigns/devsec-rotation-integration/notes/phase-0-audit.md (audit findings)

OUTPUT:
- src/security_observatory/dashboard_server.py — POST /api/rotation/trigger endpoint
- dashboard-ui/ — RotateButton, RotationConfirmationModal, RotationProgressPanel, VerificationReportRenderer components
- Audit log integration (rotation triggers captured in scan history)
- One git commit; do not push

OPEN QUESTIONS:
- Streaming pipeline progress: server-sent events vs WebSocket vs long-poll? Lean: SSE if no existing pattern, WebSocket if the dashboard already uses it. Avoid long-poll if avoidable (UX is worse).
- Should the user be able to cancel a rotation in flight? Lean: NO for v1. The pipeline is designed to be safe-to-abandon (resume from disk); cancellation introduces a tear-down complexity that's not worth it.
- For batch rotation ("rotate all overdue"): in scope for v1 or defer? Lean: defer. Per-secret rotation is the primary use case; batch comes after we've watched single rotations work in practice.
- The verification receipt rendering: should it always be shown inline post-rotation, or collapsed by default with a "View details" disclosure? Lean: shown inline, prominently. The receipt is the load-bearing trust signal — hiding it defeats the campaign's purpose.
```

## Step 3.1 — Write `/devsec-rotate <secret>` slash command and update `/devsec` menu

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

(populated by Step 0.1 — references to other slash commands and the doctrine voice section will be exact paths post-campaign-2)

Add a new slash command at `~/.claude/commands/devsec-rotate.md` that triggers rotation via shell-out to the skill, in the agent context. Same architectural pattern as the planned `/devsec-watch`.

Behavior:

- Arg: `<secret>` (required). If omitted, the command calls `rotation_status` for the current repo's name (or all repos via `list_repos`), lists rotatable secrets, asks which.
- Resolve which repo the user is asking about (from the slash command's project context, or by asking).
- Surface the Tier 5 confirmation language from `docs/agent-safety.md`. The agent must explicitly say:
  - What rotation will do for this specific secret class.
  - What's at risk (e.g., NEXTAUTH_SECRET invalidates sessions).
  - The grace window (default 24h for Class B).
  - What "verified" will mean here (provider ✓, application probe ✓, soak ✓).
- Wait for the user's explicit confirmation (in chat, as a typed "yes" or equivalent).
- On confirm, shell out to the rotation skill: `cd <repo> && npm run rotate <secret>` (or the appropriate Python CLI command per the v0.2 adapter unification — populated by Step 0.1).
- Tail the subprocess output. Render pipeline steps as they happen in the agent's voice.
- When the verification receipt is written, read it and surface the contents to the user (NOT a wall of subprocess output; the receipt is the curated version).

If rotation isn't set up for the repo:

- Tell the user. Surface the same "Set up rotation" CTA the dashboard does. Offer to invoke `/secrets-rotation` to scaffold.

Voice section:

- Apply the standard "Voice" block per `docs/agent-voice.md`.
- Apply the Tier 5 safety note from `docs/agent-safety.md`.
- Carve out: this command's confirmation language is more elaborate than `/devsec-fix` because rotation is irreversible at the provider — the agent should explain consequences before any action.

**Update `~/.claude/commands/devsec.md`:**

Add a new row to the commands menu table:

| `/devsec-rotate <secret>` | You want to rotate a secret end-to-end with verification — generates a new value, stages it via canary, soak-tests for 15 min, and gives you a "you are safe" receipt. Replaces the chore of manually clicking through provider consoles. |

Acceptance criteria:

- `~/.claude/commands/devsec-rotate.md` exists, follows the existing `/devsec-*` frontmatter convention.
- Confirmation language matches the Tier 5 template from `docs/agent-safety.md`.
- Shells out correctly to the rotation skill for both Vercel and Python CLI projects (the v0.2 adapter detection makes the entry point unified — confirm in Step 0.1's audit).
- Verification receipt content is surfaced to the user post-rotation in the Security Brief format.
- `~/.claude/commands/devsec.md` menu table updated with the new row.

```text
/skill-creator

SCOPE: Write ~/.claude/commands/devsec-rotate.md slash command that shells out to the rotation skill, with full Tier 5 confirmation per docs/agent-safety.md. Update /devsec menu to surface it.

REQUIRED READING:
1. ~/.claude/commands/devsec.md (home dashboard; menu update target)
2. ~/.claude/commands/devsec-fix.md (closest sibling — reference handoff command)
3. ~/.claude/commands/devsec-pr.md (similar pattern — write-action command with confirmation gates)
4. docs/agent-voice.md (voice for all command output)
5. docs/agent-safety.md (Tier 5 template — exact confirmation language)
6. campaigns/devsec-agent-doctrine/notes/calibration-examples.md #10 (Security Brief format for surfacing the receipt)
7. ~/.claude/skills/secrets-rotation/SKILL.md (the skill being shelled out to)
8. campaigns/devsec-rotation-integration/notes/phase-0-audit.md (audit findings — exact entry point command per adapter)

OUTPUT:
- ~/.claude/commands/devsec-rotate.md (new)
- ~/.claude/commands/devsec.md (one new menu row added)

OPEN QUESTIONS:
- How to handle the case where the secret name is ambiguous across multiple repos (e.g., AUTH_SECRET in two of Christian's repos)? Lean: list all matches, ask the user to pick by repo:secret.
- The agent's chat output during rotation should be live (each pipeline step surfaced as it happens) or summary (only the final receipt)? Lean: live, but pruned — surface step names and outcomes as one-liners, not raw subprocess output.
- Tier 5 confirmation: in slash commands the user types confirmation in chat ("yes, rotate"). What's the exact phrase per agent-safety.md? Pull it verbatim. Don't paraphrase.
```

## Step 3.2 — Case rendering: secrets-category cases get "Rotate this" affordance

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

(populated by Step 0.1 — case shape and rendering surfaces per the post-campaign-1 cases tool)

Update case rendering across surfaces so when a case is in the `secrets` category AND rotation is available for the repo, the case carries a "Rotate this" affordance. Three surfaces:

1. **`/devsec-cases` slash command output.** For secrets-category cases in repos with rotation set up, append a small annotation: `→ /devsec-rotate <inferred-secret-name>` to the case row.
2. **Dashboard case card.** Add a "Rotate this" button that maps the case's `affected_files` + finding details to a likely secret name, and triggers the dashboard rotation flow from Step 2.2.
3. **`/devsec-fix` slash command.** When the user asks for the playbook for the `secrets` category, the playbook output should include "If rotation is set up: `/devsec-rotate <secret>` collapses these manual steps into one click."

The inference from "exposed secret finding" → "rotatable secret name" needs care:
- If the finding includes `package_name` or `env_var_name` metadata, use that.
- If the finding only has a file path and a redacted evidence excerpt, ask the user which env var this maps to.
- Don't guess. Wrong-secret rotation is worse than no rotation.

Acceptance criteria:

- `/devsec-cases` output includes the rotate annotation where appropriate.
- Dashboard case card shows the "Rotate this" button conditionally.
- `/devsec-fix secrets` playbook output mentions the rotation path.
- The secret-name inference is conservative — never silently picks the wrong secret. When ambiguous, asks the user.
- All three surfaces follow the voice doctrine and Tier 5 confirmation language.

```text
/skill-creator

SCOPE: Update case rendering across /devsec-cases, dashboard case card, and /devsec-fix so secrets-category cases offer "Rotate this" when rotation is set up for the repo.

REQUIRED READING:
1. ~/.claude/commands/devsec-cases.md (slash command — update to add rotate annotation)
2. ~/.claude/commands/devsec-fix.md (slash command — playbook output update)
3. ~/.claude/commands/devsec-rotate.md (delivered by Step 3.1 — the target of the annotations)
4. src/security_observatory/cases.py (case shape — what fields are available for secret-name inference)
5. dashboard-ui/ (case card component to extend)
6. docs/agent-voice.md (voice for the annotations and button copy)
7. campaigns/devsec-rotation-integration/notes/phase-0-audit.md

OUTPUT:
- Updated ~/.claude/commands/devsec-cases.md
- Updated ~/.claude/commands/devsec-fix.md (specifically the secrets-playbook output)
- Updated dashboard case card component (in dashboard-ui/)
- Tests for the secret-name inference logic
- One git commit (only repo-side changes; slash command edits aren't in the repo)

OPEN QUESTIONS:
- For secret-name inference: the safest approach is to use the catalog (~/.claude/skills/secrets-rotation/catalog.json) to map common provider patterns (e.g., "GitHub PAT pattern detected" → suggest GITHUB_TOKEN, ANTHROPIC_API_KEY pattern → suggest ANTHROPIC_API_KEY). If no catalog match, ask the user.
- Annotation in /devsec-cases: should it appear on every row that COULD be rotated, or only ones currently flagged? Lean: every row in secrets category — even non-flagged secrets benefit from being rotation-aware.
- The dashboard case card's "Rotate this" button: should it open the same modal as the rotation status card's "Rotate" button, or have its own context-aware variant? Lean: reuse — same Tier 5 modal, just pre-fills the secret name.
```

## Step 4.1 — End-to-end manual verification

Model: Manual run-through; Sonnet 4.6 · High / GPT-5.5 · High for any iteration edits
Parallel: NO

Truth-from-the-running-product verification. Rotate a synthetic secret from each surface (dashboard button, slash command), confirm the verification report renders correctly, observe behavior under both success and forced-halt scenarios.

Procedure:

1. **Setup.** Ensure dëv-security's synthetic `DEVSEC_GITHUB_TOKEN` (from campaign #3's demo) is still in `.env.example`. Re-scaffold rotation if needed. Run `npm run rotate DEVSEC_GITHUB_TOKEN --test` once to confirm baseline works.

2. **MCP read tools.** In a fresh Claude Code session: ask "Use devsec to show me the rotation status of dëv-security." Confirm the agent calls `mcp__devsec__rotation_status` and renders the result.

3. **Dashboard surface.** Launch dashboard. Navigate to dëv-security repo view. Confirm rotation status card appears with DEVSEC_GITHUB_TOKEN listed. Click "Rotate" on it. Confirm modal copy matches Tier 5 template. Confirm. Watch progress panel stream. Confirm verification report renders inline in Security Brief format.

4. **Slash command surface.** In a fresh Claude Code session: type `/devsec-rotate DEVSEC_GITHUB_TOKEN`. Confirm Tier 5 confirmation flow appears in chat. Type confirmation. Watch pipeline output. Confirm receipt is surfaced in agent's voice (not raw subprocess output).

5. **Case integration.** Run `/devsec-cases secrets` (assuming dëv-security has any secrets cases). Confirm the rotate annotation appears for secrets cases in rotation-enabled repos. Click through one case in the dashboard; confirm "Rotate this" button is present.

6. **Forced halt.** Run `npm run rotate DEVSEC_GITHUB_TOKEN --fail-at SOAK --test` (using the failure injection mode from campaign #3). Confirm: dashboard shows HALT clearly; recovery command is plainly shown; verification report is the HALTED shape (not the success shape).

7. **Note any drift.** If observed output drifts from the voice doctrine (casual language, missing status-first framing, raw subprocess noise leaking through, modal copy not matching Tier 5 template) — capture the drift and the source, iterate.

Acceptance criteria:

- All surfaces work end-to-end against the synthetic secret.
- Verification report renders correctly in dashboard AND slash command.
- Forced halt scenario surfaces cleanly with recovery instructions.
- Observed drift documented and calibrated.
- Receipt written to `campaigns/devsec-rotation-integration/receipts/01-end-to-end.md`.

```text
/verify

SCOPE: Manual end-to-end verification of the rotation integration across MCP, dashboard, and slash command surfaces. Both success and forced-halt scenarios. Document drift; calibrate.

REQUIRED READING:
1. docs/agent-voice.md
2. docs/agent-safety.md (Tier 5 template)
3. campaigns/devsec-agent-doctrine/notes/calibration-examples.md #10 (Security Brief target shape)
4. ~/.claude/skills/secrets-rotation/SKILL.md (current state)
5. Sample receipts from campaigns/devsec-rotation-foundation/notes/sample-receipts/

PROCEDURE:
1. Fresh Claude Code session in dëv-security repo.
2. Run the six verification steps above in order.
3. Capture screenshots/transcripts of: dashboard rotation card, modal, progress panel, verification report, slash command transcript, halt scenario.
4. Note drift from voice doctrine and Tier 5 template.
5. Calibrate by editing the responsible surface (slash command body, dashboard component, doctrine itself).

ACCEPTANCE: All four surfaces (MCP read, dashboard read, dashboard trigger, slash command trigger) work end-to-end. Both success and forced-halt scenarios surface cleanly. Drift documented and addressed. Receipt written.

OPEN QUESTIONS:
- If the synthetic DEVSEC_GITHUB_TOKEN was removed after campaign #3's demo, re-add it for this verification (or use a different test secret).
- If dëv-security has no real secrets cases (likely — the repo's threat model doesn't require many secrets), skip the case-integration step and note in the receipt that this surface needs verification against a repo with real secrets cases.
- The forced-halt scenario depends on campaign #3's --fail-at flag landing correctly. If it didn't, this step's halt verification has to use a different mechanism (or be deferred until --fail-at works).
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the devsec-rotation-integration campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-integration.md
Campaign: campaigns/devsec-rotation-integration.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff (for repo-side changes) and the actual files in ~/.claude/commands/ (for slash command work) that the criteria actually landed. Don't trust step receipts — read the actual files.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas. Specifically watch for:

- Did the MCP stay read-only? No `rotate()` write tool snuck in?
- Are the new rotation_status and rotation_history tools actually wrapping the skill's state files, not duplicating logic?
- Does the dashboard's "Rotate" button shell out to the skill, not implement rotation logic directly?
- Does the confirmation modal copy match the Tier 5 template from docs/agent-safety.md exactly (not paraphrased)?
- Does the verification report rendering in both dashboard and /devsec-rotate match calibration-examples.md #10 in tone and structure?
- Did /devsec-rotate properly handle the "rotation not set up" case (with a path to /secrets-rotation scaffolding)?
- Does the secret-name inference in case rendering refuse to guess when ambiguous?
- Was Step 0.1 actually run? Are the (populated by Step 0.1) placeholders all filled in?
- Was end-to-end verification (Step 4.1) actually completed against a real running dashboard, not just a unit test pass?

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
