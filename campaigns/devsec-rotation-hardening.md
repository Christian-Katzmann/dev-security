# 7 · DëvSec rotation hardening — lock concurrency, complete the audit trail, add reset

> Tightens three weak spots in how DëvSec rotates leaked passwords. Stops two clicks from racing against each other. Makes sure that when you manually mark a stuck rotation as "done," the system still writes it down. And adds a one-command way to wipe a project's saved data so setup can be tested from a clean slate.

## Scope

Three coherent fixes from today's rotation production-readiness audit (full punch list at `/tmp/devsec-walkthrough-2026-05-25.md`). Each closes a way the rotation system can quietly mislead the operator.

1. **Reset command** — `security-scan reset <repo>` with a Tier 5R-style confirmation phrase, transactional sqlite cleanup across the per-repo tables, removal of `~/.security-observatory/reports/<repo>/`, and an optional `--include-rotation-scaffold` for full clean-slate testing. Lands first because Phase 3's verification needs it.
2. **Concurrency lock at the trigger endpoint** — `POST /api/rotation/trigger/<repo>` refuses when the named secret is already in an inflight status (per `data/rotation-state.json`) or has a still-running entry in the in-memory `CHECK_JOBS`. Closes the C1 critical finding: today two clicks (or tab + slash command) spawn two `npm run rotate` subprocesses racing on the same state file.
3. **Operator-override audit completeness** — every state-mutating CLI flag in the rotation skill (`--rollback`, `--abort`, `--force-revoke`, `--finalize`, and `--mark-rotated` if v0.2 still carries it) appends to `data/rotation-log.jsonl` AND writes an `OPERATOR_OVERRIDE`-shaped receipt. `rotation_status` rows gain a `manually_marked` boolean so the dashboard can distinguish pipeline-verified from operator-asserted state. Failure-injection tests are extended to cover every override. Closes the H1 evidence: besk's AUTH_SECRET state says ROTATED but the JSONL trail still ends at HALTED and no receipt was ever written.

Done when: the trigger endpoint refuses concurrent rotations on the same secret with a clear 409; every documented override flag in `~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl` writes both a JSONL entry and a receipt (verifiable by a forced-halt-then-override test); `security-scan reset <repo>` cleanly wipes a repo's state from sqlite + reports + optional rotation scaffold under a Tier 5R-style confirmation; the dashboard's `RotationStatusCard` surfaces a "marked by operator" annotation for any rotation whose terminal status came from an override.

## Context (locked decisions)

- **Execution order: Phase 1 (reset) → Phase 2 (concurrency lock) → Phase 3 (override audit).** Phase 1 first because Phase 3's verification needs reproducible setup. Phase 2 is independent and the smallest backend change. Phase 3 is the biggest scope and depends on Phase 1's reset for clean test setup.
- **Anti-scope.** This campaign does NOT cover the other findings in the punch list: test-mode toggle in the dashboard modal, advanced options exposure (`--skip-health-check`, `--soak-minutes`), class-aware phase track, Class B-human paste resume UI, upgrade-path test, dual-source consistency badge. Those are a separate follow-up campaign — keeping scope tight here so the trust-contract holes get closed fast.
- **Reset is destructive but local-only.** It operates on `~/.security-observatory/` sqlite tables and report files, plus optionally the target repo's `data/rotation-*` files. No remote calls. No provider impact. Tier 5R-style confirmation phrase required for any non-`--dry-run` invocation. `--backup-to <path>` writes a sqldump + tarball before destruction.
- **Operator-override receipts are labeled `OPERATOR_OVERRIDE`.** They use the same Security Brief shape as pipeline receipts but explicitly carry an `override_kind` field naming the flag used (`--mark-rotated`, `--rollback`, etc.) and a `pre_override_status` field naming what the rotation's terminal status had been before the override.
- **`manually_marked` boolean added to `rotation_status` rows.** True for any rotation whose terminal status came from an operator override rather than the pipeline. Surfaces in MCP `rotation_status`, the `GET /api/rotation/status/<repo>` payload, and a small "marked by operator" annotation in the dashboard's `RotationStatusCard`. Defaults to false for older state files that don't carry the field (backwards-compatible read).
- **MCP boundary unchanged.** Reset is a CLI command, not an MCP tool. Override audit data flows through the existing read-only `rotation_status` and `rotation_history` tools. No new write tools.
- **The skill update precedes the repo update.** Step 3.1 changes `~/.claude/skills/secrets-rotation/` (affects every repo using the skill). Step 3.2 changes this repo (affects only DëvSec). The skill's audit-write contract must be settled before the repo-side reader can be hardened against it.
- **The reset command has a dry-run mode.** `--dry-run` prints exactly what would be deleted (table names, row counts, file paths) without changing anything. Safe rehearsal default.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Reset command (unblock end-to-end testing)

- [x] Step 1.1 — Add `security-scan reset <repo>` with Tier 5R confirmation, dry-run, transactional sqlite cleanup, and optional rotation-scaffold removal

### Phase 2 — Concurrency lock at the trigger endpoint

- [x] Step 2.1 — Refuse `POST /api/rotation/trigger/<repo>` when the secret is in-flight (per state file OR per `CHECK_JOBS`)

### Phase 3 — Operator-override audit completeness

- [x] Step 3.1 — Skill: every override CLI flag writes a JSONL entry AND an `OPERATOR_OVERRIDE` receipt
- [ ] Step 3.2 — Repo: surface `manually_marked` in normalization, MCP, dashboard payload, and `RotationStatusCard`
- [ ] Step 3.3 — End-to-end verification: reset besk, force a halt, override it, confirm both artifacts land and the UI shows the marker
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Reset command with Tier 5R confirmation

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Add `security-scan reset <repo>` to the CLI. The audit identified this as the missing tool — without it, every other change in this campaign is hard to test reproducibly, and v0.1 → v0.2 scaffolding upgrades on besk are blocked.

**Surface shape:**

```
security-scan reset <REPO> [--include-rotation-scaffold] [--backup-to <PATH>] [--yes] [--dry-run]
```

Behavior:

- `<REPO>` must be a known repo (resolved through `list_repos()` like the rotation tools do — same vocabulary).
- `--dry-run` prints a plan of what would be deleted: each sqlite table + row count, each filesystem path. Exits 0 without changing anything. Safe rehearsal default.
- Without `--yes`, refuses non-dry-run invocations unless an interactive Tier 5R-style confirmation phrase is supplied. Suggested phrase: `Yes, wipe \`<REPO>\` and accept that this is irreversible.` (mirror the rotation Tier 5R phrase's character-for-character structure).
- `--backup-to <PATH>` writes a `<PATH>/<REPO>-<TIMESTAMP>.sqldump` and a `<PATH>/<REPO>-<TIMESTAMP>-reports.tar.gz` before any destruction. Optional but recommended.
- `--include-rotation-scaffold` additionally removes `<repo_path>/data/rotation-state.json`, `rotation-log.jsonl`, `rotation-receipts/`, the `rotate` npm script, and the `src/lib/rotation/` directory in the target repo. Default is to leave the repo files alone — this flag is for full clean-slate testing.

**Scope of sqlite deletes (transactional, single BEGIN/COMMIT):**

Tables carrying per-repo rows (verify by inspecting the schema at audit time — `PRAGMA foreign_key_list(...)` for cascade rules; if cascades aren't declared at the schema level, delete child rows explicitly before parents):

- `scans` (and FK-cascade to `findings`, `case_decisions`, `dependency_manifest_entries`, `sbom_components`, `dependency_trust_enrichments`)
- `platform_posture_snapshots`
- `honey_key_events` (and the `honey_keys` rows scoped to this repo, if any)
- `security_project_status`
- `agent_lab_proposals`

The reset's transaction wraps every delete + every filesystem operation in one logical step. If anything fails partway, the sqlite transaction rolls back; filesystem ops are reversed via the backup tarball if `--backup-to` was set, otherwise abort with a clear "partial state — restore from backup before retrying" message.

**Files to add / modify:**

- `src/security_observatory/cli.py` — new `reset` subcommand
- `src/security_observatory/reset.py` (new module) — the reset logic, importable so tests can call it directly
- `tests/test_reset.py` (new) — covers dry-run, confirmation refusal, backup-and-restore, the `--include-rotation-scaffold` flag, and the transactional rollback path

**Acceptance criteria:**

- `security-scan reset foo --dry-run` lists exactly what would be removed without changing anything.
- `security-scan reset foo` without `--yes` interactively prompts for the confirmation phrase; refuses on mismatch.
- `security-scan reset foo --yes --backup-to /tmp` produces a sqldump + reports tarball, then wipes.
- `security-scan reset foo --include-rotation-scaffold --yes` additionally removes the repo's rotation files.
- A test simulates a mid-transaction failure (raise after one delete) and confirms the sqlite state is unchanged.

```text
/health-implement

SCOPE: Add `security-scan reset <repo>` to the CLI with Tier 5R-style confirmation, dry-run mode, transactional sqlite cleanup, optional filesystem backup, and optional rotation-scaffold removal.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cli.py — existing subcommand structure to extend
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py — sqlite access layer (transaction patterns, ObservatoryDB)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/model.py — table models for understanding cascade scope
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py:98-107 — `_rotation_confirmation_phrase` is the canonical Tier 5R phrase shape; mirror its structure for the reset confirmation
5. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/rotation.py:62-71 — `state_file_path`, `history_file_path`, `receipts_dir` helpers for finding repo-side rotation files when `--include-rotation-scaffold` is set
6. ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl — `--abort` and `--rollback` are the closest precedent for "destructive CLI subcommand with confirmation gate"
7. /tmp/devsec-walkthrough-2026-05-25.md — H3 finding section is the spec source for what "reset" means

OUTPUT:
- src/security_observatory/cli.py (extended)
- src/security_observatory/reset.py (new)
- tests/test_reset.py (new)
- One git commit; do not push

OPEN QUESTIONS:
- Should reset support `--all-repos` for wiping every tracked repo? Lean: NO for v1 — too easy to misuse. Add later if a real use case emerges.
- The `honey_keys` table is global, not per-repo. Should reset touch it at all? Lean: NO unless `--include-rotation-scaffold` is set AND the honey key was placed in the target repo. Most honey keys are project-level placements.
- Should reset clear the in-memory `CHECK_JOBS` for the named repo? Lean: YES — any running job for that repo's secret is meaningless after the reset. Add a CHECK_JOBS purge as part of the reset transaction (best-effort, doesn't block on lock contention).
```

## Step 2.1 — Concurrency lock at the rotation trigger endpoint

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Close the C1 critical finding. Today, `serve_rotation_trigger` at `dashboard_server.py:2860` validates secret name, confirmation phrase, repo existence, and secret-in-known-list — but doesn't check whether the same secret is currently mid-rotation. Two browser tabs (or tab + slash command) can spawn two `npm run rotate -- <SECRET>` subprocesses racing on `data/rotation-state.json`.

**The check (both gates, ordered cheap-first):**

After validating the request shape and resolving the repo + secret rows, but BEFORE creating the new job and spawning the subprocess:

1. **Per-status check** — if the secret's current row in `read_rotation_status(repo_path)` shows a `status` value in `ROTATION_INFLIGHT_STATUSES` (defined in `rotation.py:39`), refuse with 409 and a clear message naming the inflight status.
2. **Per-CHECK_JOBS check** — under `CHECK_JOBS_LOCK`, scan for any job where `kind == "rotation"`, `repo == clean_repo`, `secret == secret`, and `status in {"queued", "running"}`. If one exists, refuse with 409 and surface the existing `job_id` so the operator can poll it via `GET /api/rotation/jobs/<id>` instead of starting a second.

Both checks must run BEFORE the audit-trail line is written — refused-duplicate POSTs should not pollute `rotation-log.jsonl`.

**Acceptance criteria:**

- `serve_rotation_trigger` refuses with 409 when the per-status check matches.
- It refuses with 409 when the per-CHECK_JOBS check matches.
- The 409 response includes enough context for the operator: existing `job_id` (when from CHECK_JOBS) or current inflight status (when from state file).
- A test triggers a slow rotation, immediately re-triggers the same secret, and asserts the second POST gets 409 with the running `job_id`.
- A test seeds an inflight state in a fixture state file, POSTs trigger, asserts 409 with the inflight status name.
- The frontend's error rendering in `RotationTriggerFlow.tsx` recognises the 409 shape and surfaces "rotation already in flight; here's the existing job_id" instead of a generic error.

```text
/health-implement

SCOPE: Add an in-flight check to `serve_rotation_trigger` so a second trigger on the same secret is refused with 409 instead of spawning a second subprocess. Update the frontend to surface the 409 cleanly.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py:2860-3009 — `serve_rotation_trigger`, the function being extended
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/rotation.py:29-55 — `ROTATION_FAILURE_STATUSES` and `ROTATION_INFLIGHT_STATUSES` are the locked vocabularies the check uses
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py:2986-3008 — `CHECK_JOBS` + `CHECK_JOBS_LOCK` pattern; the per-jobs check holds the lock while scanning
4. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationTriggerFlow.tsx:101-132 — `submitTrigger` is where the 409 case must be recognized
5. Pattern reference for endpoint tests: locate the existing `serve_rotation_trigger` test file via `grep -rn "serve_rotation_trigger\|/api/rotation/trigger" tests/`
6. /tmp/devsec-walkthrough-2026-05-25.md — C1 finding section is the spec source

OUTPUT:
- src/security_observatory/dashboard_server.py (extended `serve_rotation_trigger`)
- dashboard-ui/src/components/RotationTriggerFlow.tsx (409 handling in submitTrigger)
- tests/ (two new tests added to the relevant endpoint test file)
- One git commit; do not push

OPEN QUESTIONS:
- For a stale CHECK_JOBS entry (status=running but the subprocess crashed silently with no terminal event): should the new POST sweep it before refusing? Lean: NO — surfacing the stale `job_id` and the operator's ability to inspect `GET /api/rotation/jobs/<id>` is more useful than silent recovery. A separate cleanup pass (out of scope here) can sweep stale jobs later.
- Should the per-status check also gate `WAITING_FOR_PASTE`? The frontend already disables the Rotate button for that status; the backend should refuse anyway for defense in depth. Lean: YES — `WAITING_FOR_PASTE` is in `ROTATION_INFLIGHT_STATUSES`, so the gate already covers it.
```

## Step 3.1 — Skill: every operator override writes a JSONL entry AND an OPERATOR_OVERRIDE receipt

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Close the H1 finding at its source. The skill's CLI today documents these state-mutating override flags (per `~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl` lines 30-50): `--rollback <id>`, `--abort <id>`, `--force-revoke <id>`, `--finalize <id>`. The audit also found evidence of a `--mark-rotated` flag (used by besk at `2026-05-17T21:16:33Z` to mark AUTH_SECRET as ROTATED after the pipeline halted) — but this flag isn't in the documented v0.2 surface. Either it's a v0.1 leftover, hidden, or hand-edited state. This step audits + closes the gap.

**For each override path, the skill must:**

1. **Append to `data/rotation-log.jsonl`** an event with: `step: "OPERATOR_OVERRIDE"`, `outcome: "applied"`, `override_kind: "<flag>"`, `pre_override_status: <whatever the rotation's terminal status had been>`, `note: <one plain-English line naming the override and the reason if surface allows>`.
2. **Write a receipt at `data/rotation-receipts/<secret>-<timestamp>.md`** using the same Security Brief shape as a pipeline receipt but with `override_kind` and `pre_override_status` fields, plus an "Operator override applied" banner at the top.
3. **Update `data/rotation-state.json`'s rotation record** to include `manually_marked: true` and `override_kind: "<flag>"`.

**Audit-tightening tasks within this step:**

- Search `rotate.ts.tmpl` + the built JS in `tests/_build/` + the test fixtures for `--mark-rotated`. If it exists in v0.2: document it; ensure it follows the same audit contract as the other overrides. If it doesn't: extend the skill's UPGRADE pass (per `PLAYBOOK.md:209-225`) to warn when a v0.1 state file shows `marked ROTATED by operator (--mark-rotated)` and recommend re-running the rotation pipeline or marking via the v0.2 path. Don't silently strip the v0.1 evidence; surface it for the operator.

**Failure-injection test extension:**

Extend `tests/failure-injection.test.ts`'s parametrization to cover each override flag. For each: force a halt at any pipeline step, apply the override, assert (a) JSONL has the `OPERATOR_OVERRIDE` entry with the correct `override_kind`, (b) the receipt file exists and matches the `OPERATOR_OVERRIDE` shape, (c) state.json's rotation record carries `manually_marked: true` and the correct `override_kind`.

**Verification-report template update:**

Extend `templates/lib/verification-report.ts.tmpl`'s `renderRotationReceipt` to accept a `RotationRecord` with `manually_marked: true` and render the `OPERATOR_OVERRIDE` shape — Security Brief structure preserved, but with the override banner, the two new fields surfaced clearly, and the last terminal pipeline-step event included verbatim from the JSONL trail (so the trust trail is readable in one place).

**Acceptance criteria:**

- Every documented override flag (`--rollback`, `--abort`, `--force-revoke`, `--finalize`, and `--mark-rotated` if present) writes both a JSONL entry and a receipt — verified by extending `tests/failure-injection.test.ts`.
- A test forces a HALT at DEPLOY (matching besk's evidence), applies an override, and asserts the on-disk audit trail mirrors the state file's claim of ROTATED.
- `RotationRecord` schema in `templates/lib/state.ts.tmpl` includes `manually_marked: boolean` and `override_kind: string | null`.
- Receipt rendering for `OPERATOR_OVERRIDE` is documented in SKILL.md (either inside the existing "Test mode contract" section or in a new "Operator override contract" section immediately after).

```text
/health-implement

SCOPE: Extend the secrets-rotation skill so every operator-override CLI flag appends a JSONL audit event AND writes an OPERATOR_OVERRIDE receipt. Extend the failure-injection tests to cover every override path. Update the state record schema to mark overridden rotations explicitly.

REQUIRED READING:
1. ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl (lines 1-100) — the documented CLI surface; locate the actual implementation of each override flag (--rollback, --abort, --force-revoke, --finalize, and search for --mark-rotated)
2. ~/.claude/skills/secrets-rotation/templates/lib/state.ts.tmpl — the state-record writer (where `manually_marked` and `override_kind` fields go)
3. ~/.claude/skills/secrets-rotation/templates/lib/verification-report.ts.tmpl — the receipt renderer (extend to handle the OPERATOR_OVERRIDE shape)
4. ~/.claude/skills/secrets-rotation/tests/failure-injection.test.ts — test pattern to extend for each override flag
5. ~/.claude/skills/secrets-rotation/tests/verification-report.test.ts — receipt-shape tests; extend to cover OPERATOR_OVERRIDE
6. ~/.claude/skills/secrets-rotation/SKILL.md (section "CLI commands the scaffolded `rotate` script supports") — documents the flags; extend to document the audit contract for overrides
7. /Users/christiankatzmann/Dev/Projects/beskæftigelse.dk/data/rotation-state.json — the concrete H1 evidence: a v0.1 scaffold using `--mark-rotated` with no JSONL entry and no receipt. This is the failure mode the change must close.
8. /tmp/devsec-walkthrough-2026-05-25.md — H1 finding section

OUTPUT:
- ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl (extended override handlers)
- ~/.claude/skills/secrets-rotation/templates/lib/state.ts.tmpl (RotationRecord schema additions)
- ~/.claude/skills/secrets-rotation/templates/lib/verification-report.ts.tmpl (OPERATOR_OVERRIDE rendering)
- ~/.claude/skills/secrets-rotation/tests/failure-injection.test.ts (parametrized override-path tests)
- ~/.claude/skills/secrets-rotation/tests/verification-report.test.ts (OPERATOR_OVERRIDE shape tests)
- ~/.claude/skills/secrets-rotation/SKILL.md (documented override contract)

OPEN QUESTIONS:
- Is `--mark-rotated` in the v0.2 CLI? If yes: document it and apply the audit contract. If no: surface besk-style v0.1 evidence in the UPGRADE pass; don't silently strip the v0.1 leftover. Don't introduce `--mark-rotated` if v0.2 deliberately removed it.
- Should the OPERATOR_OVERRIDE receipt include the pre-override JSONL trail's last entry verbatim (for traceability), or just summarize? Lean: include the last terminal step entry verbatim. The receipt's job is to make the trust trail readable in one place.
- For `--rollback`: is the rollback itself a state-mutation (worth a receipt) or a recovery action (worth only a JSONL entry)? Lean: both — rollback is a terminal state, deserves a receipt explaining what was reverted.
```

## Step 3.2 — Repo: surface `manually_marked` through normalization, MCP, dashboard payload, and `RotationStatusCard`

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Wire Step 3.1's new state fields through to the operator. Today, `_normalized_status_entry` in `rotation.py:112-149` produces a fixed-shape row that flows through MCP `rotation_status`, the dashboard's `serve_rotation_status` endpoint, and `RotationStatusCard.tsx`. Adding the override marker means touching all four layers — but the change is mechanical at each one because the flow is already wired.

**Normalization (`rotation.py`):**

- Extend `_normalized_status_entry` to accept `manually_marked: bool` and `override_kind: str | None`, returning them in the row dict.
- Update `read_rotation_status` to read these fields from the rotation record's `manually_marked` and `override_kind` (per Step 3.1's schema).
- Default to `manually_marked=False, override_kind=None` for any state file that doesn't have the fields (e.g., v0.1 scaffolds like besk — backwards-compatible read).

**MCP (`mcp_server.py`):**

- The MCP `rotation_status` tool flows through `read_rotation_status` automatically — the new fields appear in the JSON output without code changes. Add a docstring update naming the new fields.

**Dashboard payload (`dashboard_server.py:2704-2719`, `serve_rotation_status`):**

- The endpoint returns `read_rotation_status(repo_path)` rows directly, so the new fields flow through. Add a note in the endpoint docstring.

**Frontend (`RotationStatusCard.tsx` + `RotationTriggerFlow.tsx`):**

- Extend `RotationSecretRow` type in `dashboardData.ts` with `manually_marked: boolean` and `override_kind: string | null`.
- In `RotationSecretsList` row rendering (`RotationStatusCard.tsx:312-396`), when `manually_marked` is true: render a small "marked by operator" annotation next to the status chip, naming the `override_kind` flag. Match the existing typography (font-mono text-[9px] uppercase tracking-widest, IN-GRACE-ish amber tone).
- In `RotationHistoryPanel`, render `OPERATOR_OVERRIDE` events with a distinct outcome label (e.g., "override") so they're not mistaken for pipeline steps.
- In `ConfirmStep` (`RotationTriggerFlow.tsx`): when the secret's current row has `manually_marked: true`, surface a note in the confirm step: "Note: previous rotation was completed via operator override (`<override_kind>`). The new rotation will run the full pipeline."

**Acceptance criteria:**

- `read_rotation_status` returns `manually_marked` and `override_kind` for both pre- and post-Step-3.1 state files (forward-compatible read, backwards-compatible default).
- MCP `rotation_status` flows the new fields through (visible in the JSON output).
- Dashboard's `RotationStatusCard` renders the "marked by operator" annotation for any matching row.
- `RotationHistoryPanel` renders `OPERATOR_OVERRIDE` events distinctly.
- The trigger modal's confirm step mentions the previous override when applicable.
- A backend test seeds a state file with `manually_marked: true, override_kind: "--mark-rotated"`, calls `read_rotation_status`, asserts the fields are returned.

```text
/health-implement

SCOPE: Wire Step 3.1's new RotationRecord fields (`manually_marked`, `override_kind`) through `_normalized_status_entry`, the MCP tool, the dashboard payload, the frontend type, the RotationStatusCard render, the RotationHistoryPanel event render, and the trigger modal's confirm step.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/rotation.py:112-237 — `_normalized_status_entry` and `read_rotation_status` are the canonical normalization; extend in place
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/mcp_server.py — docstring update for `rotation_status` to mention the new fields
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py:2704-2719 — endpoint docstring update
4. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/dashboardData.ts — `RotationSecretRow` type extension
5. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationStatusCard.tsx:312-564 — `RotationSecretsList` and `RotationHistoryPanel`; add the annotation + override-event rendering
6. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationTriggerFlow.tsx:317-425 — `ConfirmStep`; add the previous-override note
7. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/ — locate the rotation.py test file via `grep -rn "_normalized_status_entry\|read_rotation_status" tests/`; extend with the new-fields test

OUTPUT:
- src/security_observatory/rotation.py (extended)
- src/security_observatory/mcp_server.py (docstring update)
- src/security_observatory/dashboard_server.py (docstring update)
- dashboard-ui/src/dashboardData.ts (type extension)
- dashboard-ui/src/components/RotationStatusCard.tsx (annotation + history-event render)
- dashboard-ui/src/components/RotationTriggerFlow.tsx (confirm-step note)
- tests/ (extended)
- One git commit; do not push

OPEN QUESTIONS:
- For a state file that has `manually_marked: true` but no `override_kind` (incomplete write, or an older format): how to render? Lean: show "marked by operator" without the flag name; render the flag name only when present.
- For the modal's previous-override note: should it surface only when the previous rotation was the most recent one, or for any historical override? Lean: only the most recent — older overrides are part of the rotation history, not load-bearing for the next rotation decision.
- The OPERATOR_OVERRIDE annotation tone: amber (IN-GRACE-ish, "needs awareness") or grey (informational)? Lean: amber. The point is to draw the operator's eye to a rotation whose trust trail involves a manual step.
```

## Step 3.3 — End-to-end verification: reset, force halt, override, confirm the audit trail lands

Model: Manual run-through; Sonnet 4.6 · High / GPT-5.5 · High for any iteration edits
Parallel: NO

Truth-from-the-running-product. Use Step 1.1's reset to start from a clean state, force a rotation halt with the failure-injection flag, apply each override, confirm Step 3.1's audit trail lands, confirm Step 3.2's UI annotation surfaces, smoke-test Step 2.1's concurrency lock.

**Procedure:**

1. **Back up besk's current state.** `cp -r ~/Dev/Projects/beskæftigelse.dk/data/rotation-* /tmp/besk-rotation-pre-hardening/`. The original H1 evidence is forensically interesting; keep it.
2. **Reset besk.** `security-scan reset besk-ftigelse.dk --include-rotation-scaffold --backup-to /tmp --yes`. Confirm clean state via MCP `rotation_status` returns empty list.
3. **Re-scaffold besk.** Open Claude Code in the besk repo, invoke `/secrets-rotation`. Confirm v0.2 scaffold lands with the updated `rotate.ts.tmpl` from Step 3.1. State file's `scaffolded_version` should now say `v0.2`.
4. **Successful Class A rotation, no override.** `rotate CRON_SECRET --test`. Confirm: full pipeline runs, state shows ROTATED, JSONL has step events, receipt is written to `data/rotation-receipts/`, MCP `rotation_status` returns the row with `manually_marked: false`.
5. **Forced halt + override.** `rotate MCP_API_KEY --test --fail-at DEPLOY`. Confirm halt at DEPLOY in both state + JSONL. Then apply an override — `--mark-rotated` if present in v0.2, otherwise `--rollback <id>` or `--force-revoke <id>` (whichever maps to the besk scenario). Confirm: JSONL gains an `OPERATOR_OVERRIDE` entry, receipt is written with the OPERATOR_OVERRIDE shape, state's record has `manually_marked: true, override_kind: <flag>`, MCP `rotation_status` returns the row with the new fields.
6. **Dashboard surface.** Open the dashboard, navigate to besk. Confirm the manually-marked secret renders with the "marked by operator" annotation per Step 3.2. Click Rotate on that secret; the modal's confirm step should mention the previous override.
7. **Concurrency lock smoke test.** Open the rotation modal for CRON_SECRET, confirm the trigger. Without waiting, open a second tab, navigate to the same dashboard, open the modal for CRON_SECRET, confirm. The second POST should get a 409 with the running `job_id` of the first. Confirm the frontend renders the 409 cleanly.
8. **Optional: restore besk.** If Christian wants besk back to its real (post-H1-evidence) state, restore from `/tmp/besk-rotation-pre-hardening/`. Otherwise leave it on the v0.2 scaffold.

**Acceptance criteria:**

- Each step above produces the expected on-disk + UI evidence.
- The concurrency lock returns 409 with useful context.
- The end-to-end story now has no audit gap: every state mutation, whether pipeline-driven or operator-driven, lands in both JSONL and a receipt.
- A short verification receipt is written to `campaigns/devsec-rotation-hardening/receipts/01-end-to-end.md` capturing each scenario's evidence and any drift noticed.

```text
/verify

SCOPE: End-to-end manual verification of the three campaign deliverables. Reset besk to a clean state, force halts at multiple pipeline steps, apply each operator override, confirm every audit artifact lands, confirm UI annotations surface, smoke-test the concurrency lock.

REQUIRED READING:
1. /tmp/devsec-walkthrough-2026-05-25.md — the original audit; cross-reference each finding against post-implementation evidence
2. ~/.claude/skills/secrets-rotation/SKILL.md — confirms what overrides are in v0.2 after Step 3.1
3. ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl — actual override CLI surface to exercise
4. ~/Dev/Projects/beskæftigelse.dk/data/rotation-state.json — original H1 evidence file (note its state for restoration after the test if Christian wants)

PROCEDURE:
1. Back up besk's current state to /tmp before reset (the original H1 evidence is forensically interesting).
2. Run the 8 verification steps above in order.
3. For each, capture: on-disk evidence (state file shape, JSONL contents, receipt file existence), MCP output, dashboard screenshot of the relevant surface.
4. Note any drift between the post-implementation behavior and the specs in Phase 1-3.

ACCEPTANCE:
- Every override flag writes both JSONL + receipt (no silent gaps).
- Dashboard surfaces the "marked by operator" annotation correctly.
- Concurrency lock returns 409 with the running job_id and the frontend renders it cleanly.
- Receipt at campaigns/devsec-rotation-hardening/receipts/01-end-to-end.md captures evidence.

OPEN QUESTIONS:
- If `--mark-rotated` was removed in v0.2 deliberately: confirm Step 3.1 surfaces v0.1 evidence cleanly in the UPGRADE pass rather than silently stripping it.
- If besk's original state needs to be restored at the end of testing for Christian's real use, the backup tarball from step 2's reset is the restore source. Confirm reset's backup format is restorable.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the devsec-rotation-hardening campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-hardening.md
Campaign: campaigns/devsec-rotation-hardening.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff (for repo-side changes) and the actual files in ~/.claude/skills/secrets-rotation/ (for skill-side work in Step 3.1) that the criteria actually landed. Don't trust step receipts — read the actual files.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas. Specifically watch for:

- Did Step 1.1's reset operate transactionally? Is there a test that simulates mid-transaction failure and asserts no partial state lands?
- Does Step 2.1's concurrency lock cover BOTH the per-status check AND the per-CHECK_JOBS check? Does the 409 response include the existing job_id?
- Did Step 3.1 actually update the skill's CLI to write both JSONL AND a receipt for every override flag? Or did it only update the failure-injection test parametrization without changing the runtime behaviour? Read the rotate.ts.tmpl handlers and confirm.
- Does Step 3.2's normalization default `manually_marked=False` for state files that don't carry the field (backwards compatibility for besk-style v0.1 state)?
- Did Step 3.3's verification cover the actual H1 reproduction (force halt at DEPLOY, override, confirm both artifacts land) or did it skip the forced-halt step?
- Was `--mark-rotated` properly handled? Either documented in v0.2 with the audit contract, OR surfaced in the UPGRADE pass as v0.1 evidence — not silently stripped.
- Are the OPERATOR_OVERRIDE receipt and the JSONL entry consistent with each other (same override_kind, same pre_override_status)?

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
