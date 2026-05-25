# 8 · DëvSec rotation completeness — close the trust, UX, incident-response, and batch-operation gaps

> Closes the remaining holes in how DëvSec rotates secret passwords. Makes sure the system can't lie to itself about what happened, fills in the missing dashboard buttons so non-coders can actually use it, and adds an emergency mode for when a key is being attacked right now. Also adds a "rotate all" button so you don't have to click 18 times.

## Scope

Builds on campaign #7 (devsec-rotation-hardening, 2026-05-25) which closed the trigger-concurrency lock, operator-override audit trail, and reset command. This campaign closes the v0.2 rotation feature out by addressing four remaining gap categories surfaced by today's audit + live verification.

1. **Trust contract integrity** — fix the Tier 1 audit-emit RSC import boundary so Next.js stacks actually deliver the "two audit events per rotation" the trust contract claims. Add a status-vs-history consistency check helper + dashboard badge. Persist job state to disk so a dashboard restart mid-rotation doesn't drop tracking. Add a lock test asserting the Tier 5R confirmation phrase produces identical strings across backend, frontend, and doctrine.

2. **Modal UX completeness** — surface the test-mode toggle, advanced options (skip-health-check, soak-minutes), and per-secret rotation_warning copy that exist in the backend + catalog but aren't reachable from the dashboard. Render a class-aware phase track (Class A is 3 effective phases; today the modal shows 8 regardless). Add a B-human paste-resume button so WAITING_FOR_PASTE rotations don't force the operator back to the terminal. Document the safe-abort path in the modal footer.

3. **Incident response surface** — single-shot emergency rotation flag (`--no-grace` / `--emergency`) that skips the 24h grace window for Class B secrets under active attack. New Tier 5R variant phrase. New audit-trail flag (`emergency: true`). Dashboard exposure under an "Advanced" disclosure with deliberate incident-response copy.

4. **Batch operations** — Rotate-all backend that sequentially rotates secrets matching a filter (default: NEVER or needs_attention). Single batch confirmation phrase. HALT-and-resume semantics. Per-secret sub-receipts inside one batch-level Security Brief. Dashboard UI with filter chips and a live progress panel.

Done when: Tier 1 audit emission lands real `emitAuditEvent` calls on besk (no more `audit-emit-failed` lines); the dashboard's RotationStatusCard surfaces every option the slash command supports; emergency-mode rotation works end-to-end with its own receipt shape; Rotate-all runs a sequential queue with safe halt-resume; the trust trail consistency check warns when state and log disagree.

## Context (locked decisions)

- **Source substance.** Today's audit punch list + Christian's live-verification additions are collected in `campaigns/devsec-rotation-followup-notes.md` (committed in `b470ee3`). Every step's REQUIRED READING points there for the full finding context.
- **Anti-scope.** This campaign does NOT cover: BYOA one-button setup with token-cost disclosure (its own future campaign — credential management, billing telemetry, in-dashboard agent runtime is substantially larger surface); stack expansion beyond Vercel + Python CLI; CLI top-level subparser refactor (treat `security-scan` subcommands properly); receipt-export beyond clipboard copy; the Vercel STAGE_CANARY failure on besk (configuration issue, not a rotation skill bug).
- **Build-pipeline discipline (campaign-wide).** Any step that touches `dashboard-ui/src/` includes `npm run build` (from `dashboard-ui/`) in its acceptance criteria. Vite writes directly into `src/security_observatory/dashboard/`; the assets directory is gitignored, so only `index.html` lands in commits — the build itself must run for the dashboard to actually show the change. Campaign #7 missed this; this campaign won't.
- **Phase ordering: trust first.** Phase 1 (trust contract integrity) lands before Phases 2-4. A broken audit emission undermines every other UX surface — fix it before adding more buttons.
- **Emergency rotation is Class B only.** Class A secrets are already incident-safe (self-generated, no external provider holds the value); `--no-grace` is a no-op there. The skill refuses with a clear message: "Class A secrets don't have a grace window. Use the standard rotate command."
- **Rotate-all is sequential, not parallel.** The concurrency lock from campaign #7 handles same-secret races, but parallel rotations of different secrets could overwhelm provider rate limits. Sequential default; future opt-in for `--parallel <N>` if a real use case emerges.
- **Voice doctrine preserved.** Words not symbols. The single `⚠` carve-out (IN_GRACE within 4h of revoke) remains. New surfaces (emergency badge, override badge, consistency badge) use amber tones matched to existing typography — no new symbol vocabulary.
- **MCP boundary unchanged.** Reset (from campaign #7) and Rotate-all (this campaign) are dashboard + CLI surfaces, not MCP tools. MCP rotation tools stay read-only.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Trust contract integrity (no more silent lies)

- [x] Step 1.1 — Fix Tier 1 audit-emit broken on Next.js stacks (RSC import boundary)
- [x] Step 1.2 — Status-vs-history consistency check + job state persistence + confirmation phrase drift test

### Phase 2 — Modal UX completeness

- [x] Step 2.1 — Test-mode toggle, advanced options exposure, per-secret rotation_warning plumbing
- [x] Step 2.2 — Class-aware phase track, B-human paste-resume affordance, cancellation guidance

### Phase 3 — Incident response surface

- [x] Step 3.1 — Skill: `--no-grace` / `--emergency` flag with new Tier 5R variant
- [x] Step 3.2 — Dashboard surface for emergency rotation

### Phase 4 — Batch operations

- [x] Step 4.1 — Skill + dashboard backend for Rotate-all (sequential, halt-resume, batch receipt)
- [ ] Step 4.2 — Dashboard UI for Rotate-all (filter chips, live progress panel)

### Phase 5 — End-to-end verification

- [ ] Step 5.1 — Live verification of all four phases against a freshly-reset besk
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Fix Tier 1 audit-emit broken on Next.js stacks

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The SKILL.md trust contract claims "two audit events per rotation" (`initiated` at PREFLIGHT pass, `completed | halted | rolled_back` at terminal). On besk's Next.js stack, both events fail today:

```
[rotation:audit-emit-failed] b0b29644-… initiated: Error: This module cannot be imported from a Client Component module. It should only be used from a Server Component.
[rotation:audit-emit-failed] b0b29644-… halted: Error: This module cannot be imported from a Client Component module. It should only be used from a Server Component.
```

The rotation skill's scaffolded `audit-emit.ts` imports the repo's `emitAuditEvent` which transitively pulls in a module marked `"use server"` (React Server Component boundary). The `tsx --env-file=.env` CLI context can't load it. The trust contract silently downgrades from "two events per rotation" to "zero events" on every Next.js Tier 1 install.

**Fix approach — pick one (the agent should evaluate the besk repo's actual surface and decide):**

A. **Scaffold a server-action wrapper.** Add a small `src/scripts/audit-emit-action.ts` that re-exports `emitAuditEvent` behind a thin Node-runtime shim — accessible from both RSC contexts AND the tsx CLI. The scaffolded `audit-emit.ts` calls the wrapper instead of the original.

B. **Graceful degradation with surfaced gap.** If RSC import fails, the scaffolded `audit-emit.ts` catches the error, logs a `RSC_IMPORT_FAILED` event to `data/rotation-log.jsonl` (so the audit trail captures the failure rather than swallowing it), and continues. The dashboard's RotationStatusCard surfaces a "audit_log integration degraded" badge.

C. **Both.** Wrapper as the primary fix, graceful degradation as the fallback if the wrapper can't be generated cleanly.

**Acceptance criteria:**

- A test rotation on besk produces at least one `audit.secret_rotation` event in `audit_log` (verifiable via the audit_log query surface).
- If the fix uses graceful degradation, the dashboard surfaces the degradation clearly — no silent fallback to zero events.
- The scaffolder's detection logic at scaffold time distinguishes Tier 1 stacks that can vs. can't emit audit events cleanly, and the install plan shows the operator what they'll get.
- besk's existing scaffold gets upgraded by the next `/secrets-rotation` UPGRADE pass — diff-applied via the documented upgrade flow (PLAYBOOK.md:209-225).

```text
/health-implement

SCOPE: Fix the Tier 1 audit-emit RSC import boundary so rotations on Next.js stacks actually deliver the "two audit events per rotation" the trust contract promises.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-followup-notes.md — section "Tier 1 audit-emit broken on besk" for the failure-mode evidence and suggested fixes
2. ~/.claude/skills/secrets-rotation/templates/audit-emit-tier1.ts.tmpl (or whatever the Tier 1 audit-emit template is named — locate via grep for "emitAuditEvent" in templates/)
3. ~/.claude/skills/secrets-rotation/SKILL.md (search for "Two audit events per rotation" and "Audit-integration" — the doctrine the fix must satisfy)
4. ~/.claude/skills/secrets-rotation/docs/PLAYBOOK.md sections "Tier detection rules" and "Upgrade pass" — how the scaffolder detects Tier 1 today and how the upgrade lands on existing repos like besk
5. /Users/christiankatzmann/Dev/Projects/beskæftigelse.dk/src/lib/security/audit-events.ts — the actual emitAuditEvent surface the rotation skill is trying to import
6. /Users/christiankatzmann/Dev/Projects/beskæftigelse.dk/data/rotation-log.jsonl (after a test rotation) — confirm RSC_IMPORT_FAILED events are written if graceful degradation is the chosen path

OUTPUT:
- ~/.claude/skills/secrets-rotation/templates/ (the audit-emit template, possibly a new server-action wrapper template, scaffolder logic changes)
- Possibly besk-specific repo changes if a wrapper file needs to be written into the target repo by the scaffolder
- Tests for both the "wrapper path works" and "graceful degradation path works" scenarios

OPEN QUESTIONS:
- Does the wrapper approach require Next.js-specific runtime tagging (`"use server"`, `next/dynamic`), or is a plain Node re-export enough? Test against besk's actual setup.
- For repos where the wrapper can't be generated (audit-events.ts has structural quirks), graceful degradation is the fallback — should the scaffolder refuse to install Tier 1 in those cases, or install with a degradation warning? Lean: install with warning, surface in the install receipt and the dashboard. Refusing makes the repo unusable; warning is honest.
- Should the existing besk audit-emit be re-scaffolded by this campaign's UPGRADE pass automatically, or does the operator need to run `/secrets-rotation` themselves? Lean: automatic via UPGRADE — the existing audit-events.ts schema already accepts the v0.2 fields, just the import path needs the wrapper.
```

## Step 1.2 — Status-vs-history consistency check, job state persistence, confirmation phrase drift test

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Three observability/trust concerns small enough to bundle. All three surface gaps that hide silent contradictions in the trust trail.

**(a) Status-vs-history consistency check.** `rotation_status` reads `data/rotation-state.json` (terminal status). `rotation_history` reads `data/rotation-log.jsonl` (event trail). They can disagree — campaign #7 closed the operator-override case, but other paths (corrupt state file, partial write, manual edit, race) can still produce divergence. Add `rotation_consistency_check(repo_path)` in `src/security_observatory/rotation.py` that returns a structured warning when (a) the latest rotation record's status doesn't match the last terminal jsonl event for that secret, or (b) the jsonl trail has events with no matching state record, or (c) the state record has rotations with no matching jsonl events at all. Surface the result in the dashboard payload (`GET /api/rotation/status/<repo>` adds a `consistency: { ok: bool, warnings: string[] }` field). Frontend renders an amber "Trust trail inconsistent" badge at the top of `RotationStatusCard` when warnings exist.

**(b) Job state persistence.** `CHECK_JOBS` in `dashboard_server.py` is a Python dict guarded by a lock. Dashboard restart mid-rotation loses the tracking dict; the rotation pipeline survives (resume-from-disk is the skill's invariant) but the dashboard's view goes blank. Either persist `CHECK_JOBS` to disk under `~/.security-observatory/jobs/<job_id>.json` (write on every update), or — simpler — on dashboard startup scan recent `rotation-log.jsonl` files for rotations whose latest event is non-terminal AND less than the per-step cap ago, then re-register them as `discovered` jobs. Pick whichever is cleaner; lean toward the rediscovery approach because it has fewer write-amplification concerns.

**(c) Confirmation phrase drift test.** The Tier 5R rotation confirmation phrase lives in three places: backend `dashboard_server.py:_rotation_confirmation_phrase`, frontend `dashboardData.ts:rotationConfirmationPhrase`, doctrine `docs/agent-safety.md` (Tier 5R section). If any drifts (punctuation change, escaping shift), the trigger endpoint refuses confirmations from the UI/slash command. Add a Python test that loads all three sources and asserts they produce identical strings for a fixture secret name. ~30-line test, no implementation changes.

**Acceptance criteria:**

- `rotation_consistency_check` returns `{ok: True, warnings: []}` for a clean state and a non-empty warnings list for the divergence cases above. Tests for each case.
- Dashboard renders the amber consistency badge when warnings exist; doesn't render it when ok.
- After a dashboard restart mid-rotation, the modal can re-attach to the running job (via rediscovery OR persisted state).
- Lock test for the Tier 5R phrase: runs on every `pytest` run, fails noisily if any of the three sources drift.

```text
/health-implement

SCOPE: Bundle three trust-observability fixes — status-vs-history consistency check + dashboard badge, job state persistence (rediscovery via jsonl preferred over write-amplified persistence), and a Tier 5R confirmation phrase drift test that covers Python backend + TS frontend + doctrine markdown.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-followup-notes.md — sections H2 (consistency check), H5 (job state in-memory only), H6 (confirmation phrase drift)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/rotation.py — where `rotation_consistency_check` lands; reuses the existing `read_rotation_status` + `read_rotation_history` helpers
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py — `CHECK_JOBS`/`CHECK_JOBS_LOCK` pattern at lines ~2986-3008; `_rotation_confirmation_phrase` at lines 98-107; `serve_rotation_status` at lines 2704-2719 for the consistency payload addition
4. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/dashboardData.ts — `rotationConfirmationPhrase` (frontend source of truth #2)
5. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/agent-safety.md — Tier 5R section (doctrine source of truth #3)
6. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationStatusCard.tsx — where the consistency badge renders
7. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/ — locate the rotation-related test files via `grep -rn "rotation_status\|_rotation_confirmation_phrase" tests/`

OUTPUT:
- src/security_observatory/rotation.py — new `rotation_consistency_check` helper
- src/security_observatory/dashboard_server.py — startup job rediscovery (or persistence), consistency payload in `serve_rotation_status`
- dashboard-ui/src/dashboardData.ts — type extension for `consistency` field on the status payload
- dashboard-ui/src/components/RotationStatusCard.tsx — amber "Trust trail inconsistent" badge rendering
- npm run build in dashboard-ui/ (bundle rebuild — required since TSX changed)
- tests/ — three new test cases for consistency check; one new test for confirmation phrase drift

OPEN QUESTIONS:
- Job rediscovery cutoff: how recent is "recent enough" for a non-terminal jsonl event to count as still-running? Lean: 2× the dashboard's per-step cap (`_ROTATION_SUBPROCESS_TIMEOUT_SECONDS`, default 60min). Anything older is stale and discoverable as such.
- For the consistency check warnings list: structured (each warning has a kind + secret + detail fields) or just strings? Lean: structured — easier to render distinct badges later; strings are harder to evolve.
- Should the consistency check run inline on every `serve_rotation_status` call (cheap, but adds latency to every dashboard refresh) or lazily on a "verify trust trail" button click? Lean: inline — it's reading files that are already on disk for the existing rotation_status logic, marginal cost.
```

## Step 2.1 — Test-mode toggle, advanced options exposure, per-secret rotation_warning plumbing

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Three modal-completeness changes that share the `RotationTriggerFlow.tsx` ConfirmStep surface area. Today the modal exposes `--no-soak`; the backend accepts `test_mode`, `skip_health_check`, `soak_minutes` too, and the catalog has per-secret `rotation_warning` strings — none of which reach the operator.

**(a) Test-mode toggle.** Add a checkbox above the confirmation phrase: "Test mode — runs every pipeline step but doesn't change the secret's value. Recommended for first-time rotation on a new secret." Wires to `options.test_mode: true` in the trigger POST. The receipt for a test-mode rotation should already carry `test_mode: true` per the audit-events schema; verify it renders distinctly.

**(b) Advanced options disclosure.** Below the confirmation phrase, add a collapsed `<details>` titled "Advanced options" containing:
- `skip_health_check` checkbox + acknowledgement checkbox (matches the existing `--no-soak` pattern). Warning copy: "Bypasses the pre-rotation baseline observation. Recorded loudly in the receipt."
- `soak_minutes` integer input (clamp 10..60, default empty = use the catalog's per-secret value). Help copy: "Override the soak window. Default uses the catalog's per-secret value (15min for most Class A secrets)."

**(c) Per-secret rotation_warning plumbing.** Catalog has rich per-secret consequences (e.g. `NEXTAUTH_SECRET`'s "rotating invalidates every active user session"). Today `RotationTriggerFlow.tsx:classWarning()` ignores them and renders a hard-coded class-level warning. Plumb the catalog entry through:
- `read_rotation_status` (rotation.py) optionally enriches each row with the catalog's `rotation_warning` string. Lazy-load the catalog once on first call.
- `serve_rotation_status` (dashboard_server.py) carries the field through.
- `RotationSecretRow` type (dashboardData.ts) gains `rotation_warning: string | null`.
- `classWarning()` in RotationTriggerFlow.tsx prefers `secret.rotation_warning` when present; falls back to the class-default copy when absent.

**Acceptance criteria:**

- Test-mode toggle visible in the confirm step; checking it sends `options.test_mode: true`.
- Advanced disclosure visible (collapsed by default); contents work end-to-end against the existing backend.
- For NEXTAUTH_SECRET (or another secret with `rotation_warning` in the catalog), the modal shows the per-secret warning instead of the class-default.
- Dashboard bundle rebuilt and committed (the index.html will land in git; assets/ stays gitignored).

```text
/health-implement

SCOPE: Surface the operator-facing options the backend already supports — test mode, skip-health-check, soak-minutes, per-secret rotation_warning — in the dashboard's RotationTriggerFlow ConfirmStep. Catch up the modal to the catalog and backend.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-followup-notes.md — sections H4 (test mode toggle), M5 (advanced options), M6 (class warning hard-coded)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py:2860-3009 — `serve_rotation_trigger` accepts `test_mode`/`skip_health_check`/`soak_minutes`; the modal already sends some
3. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationTriggerFlow.tsx:317-425 — ConfirmStep, where the new toggles + disclosure go; classWarning() at lines 41-65 to replace
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/rotation.py — `_normalized_status_entry` and `read_rotation_status` for the rotation_warning enrichment
5. ~/.claude/skills/secrets-rotation/catalog.json — per-secret `rotation_warning` strings, lazy-loaded
6. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/dashboardData.ts — `RotationSecretRow` type extension

OUTPUT:
- src/security_observatory/rotation.py — catalog enrichment
- src/security_observatory/dashboard_server.py — payload extension (docstring update)
- dashboard-ui/src/dashboardData.ts — type extension
- dashboard-ui/src/components/RotationTriggerFlow.tsx — three UI additions
- npm run build in dashboard-ui/
- Tests for the catalog-lookup enrichment

OPEN QUESTIONS:
- Catalog file location resolution: ~/.claude/skills/secrets-rotation/catalog.json is the canonical source, but per-repo overrides can live at `<repo>/src/lib/rotation/catalog.local.json`. Merge order: repo-local takes precedence. Implement the merge or just read the canonical? Lean: implement the merge — the override pattern is documented in PLAYBOOK.md.
- For `soak_minutes`: should the input show the catalog default as a placeholder ("Default: 15 min")? Lean: YES — surfaces the per-secret catalog value without forcing the operator to specify it.
- Test-mode position: above or below the confirmation phrase? Lean: above. It's a meaningful decision the operator should make before reading the confirmation; advanced options stay below as "fine-tuning."
```

## Step 2.2 — Class-aware phase track, B-human paste-resume, cancellation guidance

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Three modal-completeness changes that share `RotationTriggerFlow.tsx` interaction surface and `RotationStatusCard.tsx` row-rendering. Independent of Step 2.1's options/warning work; could conflict on the same file so still sequential.

**(a) Class-aware phase track.** Today `PIPELINE_PHASES` at `RotationTriggerFlow.tsx:18-39` is a fixed 8-phase list. Class A's actual pipeline is 3 effective phases (PREFLIGHT → ACQUIRE+STAGE → DEPLOY+VERIFY); Class B-API is the full 8. Operators rotating a Class A secret see `stage_canary` / `verify_canary` / `stage_prod` / `verify_prod` show as pending then transition to done without explanation — implying a more complex pipeline than ran. Render the list per-class:
- Class A: `health_check → preflight → acquire → verify`
- Class B-API: full 8 phases as today
- Class B-human: full 8 phases + `waiting_for_paste` slot between `acquire` and `stage_canary`
The rotation_status row already carries `class`; use it to select the right list.

**(b) B-human WAITING_FOR_PASTE resume.** `WAITING_FOR_PASTE` is currently in `ROTATION_INFLIGHT_STATUSES`; the frontend disables the Rotate button for it. But Class B-human rotations PAUSE mid-pipeline waiting for the operator to paste a new value from the provider console (e.g., creating an Anthropic admin key in their dashboard). No dashboard surface exists for this; operators have to drop to terminal `npm run rotate -- <SECRET>` to resume. Add a "Resume + paste" button to the WAITING_FOR_PASTE row in `RotationStatusCard`. Clicking opens a small modal with:
- A reminder of what to paste (linked to the catalog's `console_url`)
- A password-style input (no echo)
- A "Submit" button that POSTs to a new endpoint `POST /api/rotation/paste/<job_id>` (or `<rotation_id>`)
The endpoint stdin-feeds the running subprocess. Path-traversal-safe; only accepts pastes for jobs in WAITING_FOR_PASTE state.

**(c) Cancellation guidance.** Today the modal footer says "Cancellation isn't supported in v1. The pipeline is safe to abandon." Operators reasonably ask "OK but what if I really need to abort?" Add a one-liner below: "If you must abort: `pkill -f 'npm run rotate -- <SECRET>'`. The pipeline is safe to abandon — re-clicking Rotate resumes from disk." That's already accurate (resume-from-disk is the skill's documented invariant); just needs to surface in the UX.

**Acceptance criteria:**

- For a Class A rotation in test mode, the phase track shows 4 phases (not 8); no mysterious skipped phases.
- For a Class B-human rotation that hits WAITING_FOR_PASTE, the dashboard shows a Resume button that opens a paste modal; pasting a value resumes the pipeline.
- The cancellation copy is present in the modal footer during the `running` step.
- Dashboard bundle rebuilt.

```text
/health-implement

SCOPE: Three modal-interaction completeness fixes — class-aware phase track, B-human WAITING_FOR_PASTE resume surface, cancellation guidance copy.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-followup-notes.md — sections H7 (phase track), M3 (B-human paste), M4 (cancellation)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationTriggerFlow.tsx:18-39 — PIPELINE_PHASES (the fixed-8-phase list to make class-aware); footer at lines 297-300 (cancellation copy)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationStatusCard.tsx — where the Resume+paste button slots into the WAITING_FOR_PASTE row
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py — pattern for the new POST /api/rotation/paste/<id> endpoint (path-traversal safety, stdin-feed mechanics; reference _run_rotation_job)
5. ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl — confirm WAITING_FOR_PASTE behavior (where the subprocess pauses on stdin); paste protocol the new endpoint feeds into
6. ~/.claude/skills/secrets-rotation/catalog.json — `console_url` per-secret (for the paste modal copy)

OUTPUT:
- dashboard-ui/src/components/RotationTriggerFlow.tsx — class-aware PIPELINE_PHASES, cancellation copy
- dashboard-ui/src/components/RotationStatusCard.tsx — Resume button + paste modal
- src/security_observatory/dashboard_server.py — POST /api/rotation/paste/<id> endpoint
- npm run build in dashboard-ui/
- Tests for the paste endpoint (auth-style: only feeds jobs in WAITING_FOR_PASTE state)

OPEN QUESTIONS:
- Paste endpoint key: `<job_id>` or `<rotation_id>`? `job_id` is the dashboard's UUID; `rotation_id` is the skill's. The skill's stdin-feed is keyed to its own rotation. Lean: `<job_id>` because it's the dashboard's identifier and the dashboard validates against CHECK_JOBS, then maps to the rotation's stdin pipe via the subprocess handle.
- Should the paste modal show the provider console URL as a clickable link? Yes — but go through claude-in-chrome MCP since external URLs from emails/messages get suspicion-checked. Actually catalog URLs are known-safe; render as a direct link with a small "opens in browser" note.
- Should the WAITING_FOR_PASTE row disable the existing Rotate button (it already does) AND add the Resume button? Yes — Rotate is for starting a new rotation, Resume is for continuing the existing one. Two distinct affordances.
```

## Step 3.1 — Skill: `--no-grace` / `--emergency` flag with new Tier 5R variant

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Single-shot incident-rotation flag in the rotation skill. Closes the gap Christian identified during live verification: today an active attack against a Class B secret requires two terminal commands (`rotate <SECRET>` → enters IN_GRACE → `rotate <SECRET> --force-revoke <id>`) plus the 24h grace window's worth of risk before the old key dies.

**Two flag variants — pick the cleaner shape during implementation:**

- `--no-grace` (skip just the grace window; soak and health-check still run)
- `--emergency` (composite: `--no-soak` + `--no-grace` + `--skip-health-check`; the full "I know what I'm doing, the key is compromised, rotate now" mode)

Both add a new entry to the documented CLI surface in `rotate.ts.tmpl` (the section starting around line 30). Both refuse for Class A secrets with a clear message: "Class A secrets don't have a grace window. Use the standard rotate command." Class A is already incident-safe — the old value dies the moment the new value deploys.

**Tier 5R confirmation phrase variant.** The standard rotation phrase doesn't capture the irreversibility difference (24h grace vs. immediate death). Add a new variant:

> `Yes, rotate <SECRET> emergency-mode and accept that the old key dies immediately with no grace.`

Mirrored character-for-character across `_rotation_confirmation_phrase` (Python), `rotationConfirmationPhrase` (TS — needs to accept an emergency flag), and `docs/agent-safety.md` (a new "Emergency rotation" subsection of the Tier 5R doctrine).

**Audit contract for emergency rotations.** The JSONL trail and the receipt must explicitly mark emergency rotations:
- JSONL entry: `outcome: "emergency"` on the `REVOKE` step (no grace = revoke is immediate)
- Receipt: new shape `EMERGENCY_ROTATION` with the Security Brief structure preserved + new fields `emergency: true`, `grace_skipped: true`, `cached_caller_risk_acknowledged: true`.
- State record: new field `emergency_mode: boolean` on the rotation record.

**Acceptance criteria:**

- `rotate ANTHROPIC_API_KEY --emergency` (or `--no-grace`) on a B-API secret completes the full pipeline in one shot with immediate revoke.
- The Tier 5R phrase variant is enforced — bare `--emergency` without the phrase is refused.
- Class A secret + `--emergency` is refused with the clear message.
- Receipt for an emergency rotation carries the EMERGENCY_ROTATION shape; auditor can distinguish from a normal Class B rotation.
- failure-injection tests parametrize over `--emergency`; the audit chain (state + jsonl + receipt) stays consistent.

```text
/health-implement

SCOPE: Add a single-shot incident-rotation flag (--no-grace or --emergency, decide during implementation which shape is cleaner) to the rotation skill, with a new Tier 5R confirmation phrase variant, EMERGENCY_ROTATION receipt shape, and Class A refusal logic.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-followup-notes.md — "Emergency rotation: --no-grace / single-shot incident flag" section (full spec)
2. ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl (lines 1-50 for the CLI surface; --force-revoke at line ~750 for the existing two-step path) — extension point
3. ~/.claude/skills/secrets-rotation/templates/lib/state.ts.tmpl — RotationRecord schema additions (emergency_mode field)
4. ~/.claude/skills/secrets-rotation/templates/lib/verification-report.ts.tmpl — receipt renderer (extend for EMERGENCY_ROTATION shape; reuse OPERATOR_OVERRIDE structure as inspiration)
5. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/agent-safety.md — current Tier 5R section; extend with "Emergency rotation" subsection
6. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py:98-107 — `_rotation_confirmation_phrase`; extend to accept an emergency flag
7. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/dashboardData.ts — `rotationConfirmationPhrase` extension
8. ~/.claude/skills/secrets-rotation/tests/failure-injection.test.ts — extend parametrization for the --emergency path

OUTPUT:
- ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl — new flag + Class A refusal logic
- ~/.claude/skills/secrets-rotation/templates/lib/state.ts.tmpl — emergency_mode field
- ~/.claude/skills/secrets-rotation/templates/lib/verification-report.ts.tmpl — EMERGENCY_ROTATION receipt
- ~/.claude/skills/secrets-rotation/SKILL.md — document the emergency-mode contract
- docs/agent-safety.md — new Emergency rotation subsection of Tier 5R
- src/security_observatory/dashboard_server.py — `_rotation_confirmation_phrase` accepts emergency flag
- dashboard-ui/src/dashboardData.ts — `rotationConfirmationPhrase` extension
- failure-injection.test.ts + verification-report.test.ts — parametrized over the new path

OPEN QUESTIONS:
- `--no-grace` vs `--emergency`: which name is cleaner and what semantics? Lean: ship --emergency as the composite (no-soak + no-grace + skip-health-check) because the operator under attack rarely wants to skip ONLY grace; they usually want the whole "act now" mode. --no-grace as a finer-grained flag for power users who want soak + skip grace.
- Phase 3.2 (dashboard surface) lands the UI for emergency rotation. This step settles the contract; 3.2 reads it. Coordinate the field names.
- The receipt's "cached_caller_risk_acknowledged" field — should it be required (raises if not present) or optional? Lean: required when emergency=true. The audit trail must capture that the operator was aware of cached-caller risk.
```

## Step 3.2 — Dashboard surface for emergency rotation

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Wire Step 3.1's emergency-mode flag through to the operator. Touches `RotationTriggerFlow.tsx` (the modal), `RotationStatusCard.tsx` (post-rotation badge), and `dashboard_server.py` (trigger endpoint options forwarding).

**Modal surface.** Inside the existing Advanced disclosure from Step 2.1, add an "Incident response" subsection with a deliberately loud header. Copy:

> **Emergency mode** — skip the 24h grace window. The old key dies immediately when this rotation completes. Use this when you have reason to believe the key is being actively used by an attacker. Cached callers (background workers, retry queues, webhook handlers) will fail until they pick up the new value — usually within minutes, but they fail loudly. That loud failure is itself a diagnostic signal: it tells you which surfaces were still using the old credential.

Checkbox: "Enable emergency mode (Class B only)." When checked, the confirmation phrase swaps to the emergency variant from Step 3.1. The Rotate button copy changes to "Emergency rotate" with a red-amber border. For Class A secrets, the checkbox is disabled with a tooltip explaining why.

**Post-rotation badge.** RotationStatusCard's row rendering already has the amber "Operator override (mark-rotated)" pill from Step 3.2 of campaign #7. Add a sibling pill rendered when `emergency_mode === true`: red-amber border, copy "Emergency rotated" or "Emergency (no grace)". The two pills can coexist (an emergency rotation that later required an operator override would show both).

**Trigger endpoint forwarding.** `serve_rotation_trigger` already accepts `options.no_soak` and the matching acknowledgement. Add `options.emergency_mode` + `options.acknowledged_cached_caller_risk` (both required when emergency_mode=true). Forward the `--emergency` flag to the subprocess command construction.

**Acceptance criteria:**

- Modal shows the emergency disclosure inside Advanced; checkbox is disabled for Class A secrets.
- Confirmation phrase changes when the checkbox is checked; the Rotate button copy changes.
- An emergency-rotated secret shows the "Emergency rotated" pill in the rotation card next to the existing ROTATED chip.
- Backend rejects emergency=true without the acknowledgement flag.
- Dashboard bundle rebuilt.

```text
/health-implement

SCOPE: Dashboard surface for emergency-mode rotation — Advanced-disclosure subsection in the modal, confirmation phrase swap, post-rotation badge, and trigger endpoint options forwarding.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-followup-notes.md — "Emergency rotation" section (full spec)
2. Step 3.1's output — settled the skill side (--emergency flag, EMERGENCY_ROTATION receipt, Tier 5R variant phrase, emergency_mode field). Coordinate field names.
3. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationTriggerFlow.tsx:317-425 — ConfirmStep; the emergency subsection slots into the Advanced disclosure added by Step 2.1
4. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationStatusCard.tsx:355-361 — existing "Operator override" pill rendering; mirror for emergency
5. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py:2860-3009 — `serve_rotation_trigger` options forwarding; the --no-soak/acknowledged_skipping_soak pattern at lines 2884-2894 is the precedent

OUTPUT:
- dashboard-ui/src/components/RotationTriggerFlow.tsx — emergency disclosure, phrase swap, button copy
- dashboard-ui/src/components/RotationStatusCard.tsx — "Emergency rotated" pill
- dashboard-ui/src/dashboardData.ts — type extensions (emergency_mode on row, options.emergency_mode in trigger payload)
- src/security_observatory/dashboard_server.py — `serve_rotation_trigger` accepts emergency_mode + acknowledged_cached_caller_risk
- npm run build in dashboard-ui/
- Test: trigger endpoint rejects emergency=true without acknowledgement

OPEN QUESTIONS:
- Visual tone: red-amber for emergency vs. just-amber for operator-override — distinct enough? Lean: yes, but verify with screenshot review. Red feels appropriate for "the old key is dead RIGHT NOW."
- The class-A-disabled tooltip copy: should it offer to fall through to the standard rotate? Lean: NO — the standard Rotate button is already right there. Tooltip just explains why emergency is greyed out.
- For the post-rotation badge: should we also surface the "loud cached-caller failure" risk in the rotation history panel? Lean: yes, but in Phase 5 verification — add a note that emergency rotations should be paired with operator vigilance on application logs in the hour after.
```

## Step 4.1 — Skill + dashboard backend for Rotate-all

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Sequential batch rotation. Today an operator looking at besk's 18 secrets in NEVER state has to click each one through Tier 5R confirmation individually. Christian flagged this immediately: "we kinda need a 'rotate all' — right?" Campaign #4 deferred this with the criterion "after we've watched single rotations work in practice." That criterion is now met.

**Filter semantics.** Rotate-all takes an explicit filter. Defaults to `{status: 'NEVER'} ∪ {needs_attention: true}` — "everything that's never been rotated, plus anything overdue or in a failure terminal state." Operator can narrow:
- "Rotate all never-rotated" (just NEVER)
- "Rotate all overdue" (just needs_attention=true with cadence exceeded)
- "Custom selection" (explicit checkbox list from the rotation card)

**Confirmation phrase.** Tier 5R-style but names the COUNT, not each secret (operators don't paste 18 secret names):

> `Yes, rotate <N> secrets and accept the irreversible provider-side changes.`

For batches that include any Class B secret, the confirmation also requires `acknowledged_provider_irreversibility` checkbox.

**Sequencing + HALT semantics.** Sequential execution; campaign #7's concurrency lock handles same-secret races but parallel different-secret rotations could overwhelm provider rate limits. If rotation N halts, the queue STOPS by default. The operator sees a "continue with remaining N-1 secrets / stop / rollback completed" choice. Don't blind-march through 18 rotations if 3 went wrong.

**Batch receipt.** Single Security-Brief-shaped receipt at `data/rotation-receipts/batch-<timestamp>.md` listing each secret with its sub-status (ROTATED / IN_GRACE / HALTED / SKIPPED). Each sub-entry links to the per-secret receipt for full detail.

**Backend endpoint.** `POST /api/rotation/trigger-batch/<repo>` body `{filter: {...}, confirmed: true, confirmation_phrase: "...", options: {...}}`. Returns `{batch_job_id: "..."}`. Polled like single rotations via `GET /api/rotation/jobs/batch/<batch_job_id>` which returns the batch state + per-secret sub-job snapshots.

**Skill CLI surface.** Add `npm run rotate --all [--filter <preset>] [--continue-on-halt]` for terminal-bound operators. Mirrors the dashboard flow shape.

**Acceptance criteria:**

- Backend endpoint accepts a filter, queues per-secret rotations, runs them sequentially, returns a batch_job_id.
- HALT semantics work: triggering halt-on-second-secret leaves first-secret rotated and stops; status endpoint shows the partial-batch state clearly.
- Batch receipt at the documented path with per-secret sub-status.
- CLI `npm run rotate --all` works end-to-end against a Class A fixture.
- Concurrency: a batch run while a single rotation is in-flight for the same secret refuses the batch (or skips that secret with a "rotation already in flight" note in the batch receipt).

```text
/health-implement

SCOPE: Skill + dashboard backend for sequential batch rotation. Filter-based queue, single batch confirmation phrase, halt-on-error semantics with operator continue/stop choice, batch-level receipt.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-followup-notes.md — "Rotate all" section (full spec)
2. ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl — extend with --all flag; sequential queue around the existing runRotation
3. ~/.claude/skills/secrets-rotation/templates/lib/verification-report.ts.tmpl — extend with batch-receipt rendering
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py:2860-3019 — `serve_rotation_trigger` + `_run_rotation_job` patterns to extend for batch
5. Campaign #7's concurrency lock implementation (dashboard_server.py:2954-2976) — batch rotations must respect this per-secret
6. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/rotation.py — `read_rotation_status` for the default filter logic

OUTPUT:
- ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl — --all flag, queue runner
- ~/.claude/skills/secrets-rotation/templates/lib/verification-report.ts.tmpl — batch receipt rendering
- ~/.claude/skills/secrets-rotation/SKILL.md — document the batch contract
- src/security_observatory/dashboard_server.py — POST /api/rotation/trigger-batch/<repo>, GET /api/rotation/jobs/batch/<id>
- Tests for the filter logic, halt-and-resume, and batch receipt shape

OPEN QUESTIONS:
- HALT default behavior: stop (operator decides next) vs. continue with the rest? Lean: stop. A halt during a batch is a meaningful signal — don't auto-march. The operator's choice keeps them in the loop.
- Should batch rotations be cancellable mid-stream? Today single rotations can't be cancelled (safe-to-abandon doctrine). Batch should follow the same — between sub-rotations, the queue can be aborted (the in-flight rotation isn't cancelled but the next one doesn't start).
- For the filter: do we expose the filter language in the API (operators can construct custom filters from the dashboard) or just the three presets? Lean: presets only for v1; custom filters in a future iteration. Simpler API, fewer footguns.
- Mix-of-classes batches: when a batch includes both Class A and Class B secrets, does the confirmation phrase change wording? Lean: only the "provider-side changes" portion is relevant; if there's a Class B in the batch, mention it explicitly in the modal description.
```

## Step 4.2 — Dashboard UI for Rotate-all

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Frontend surface for Step 4.1's batch backend. Adds the "Rotate all" button + filter chips + batch progress panel to `RotationStatusCard.tsx`.

**Button + filter chips.** At the top of the rotation card (next to the existing Refresh button), add "Rotate all". Clicking opens a modal showing the candidate secrets matching the default filter (NEVER ∪ needs_attention). Filter chips above the list let the operator narrow to "All overdue" / "All never-rotated" / "Custom selection" (the latter exposes checkboxes per secret).

**Batch confirmation modal.** Same shape as the existing single-rotation Tier 5R modal but:
- Header: "Rotate <N> secrets — <repo>"
- A scrollable list of the queued secrets with their class chips
- The batch confirmation phrase to type
- Per-secret rotation_warning strings rolled up into a "Notable consequences" section (e.g., "Rotating NEXTAUTH_SECRET (in this batch) invalidates every active user session")
- The acknowledged_provider_irreversibility checkbox (visible only if any Class B secret is in the batch)

**Batch progress panel.** During execution, a new modal step replaces the single-rotation progress panel. Shows:
- A list of all secrets in the batch with per-secret status icons (queued / running / done / halted / skipped)
- The currently-running secret's phase track (from Step 2.2's class-aware track)
- A "Stop after current" button (lets the operator halt the queue between rotations)
- On halt: the "continue / stop / rollback completed" choice

**Batch receipt rendering.** When the batch terminates, surface the batch-level Security Brief receipt rendered inline (reuse the existing `VerificationReportRenderer` component or extend it for the batch shape).

**Acceptance criteria:**

- "Rotate all" button appears on the rotation card; clicking opens the candidate-selection modal.
- Filter chips narrow the candidate list correctly.
- Confirmation phrase enforcement works (typed phrase must match the count).
- Live progress panel updates as each sub-rotation completes; halt produces the choice surface.
- Batch receipt renders inline post-completion.
- Dashboard bundle rebuilt.

```text
/health-implement

SCOPE: Frontend "Rotate all" surface — button, filter chips, candidate-selection modal, batch confirmation, live progress panel, batch receipt rendering.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-followup-notes.md — "Rotate all" section
2. Step 4.1's output — settled the backend endpoints and the batch confirmation phrase shape
3. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationStatusCard.tsx — where the Rotate-all button + filter chips slot in
4. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationTriggerFlow.tsx — the single-rotation modal flow; mirror its structure for the batch variant
5. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/RotationTriggerFlow.tsx:565-678 — VerificationReportRenderer; extend for batch shape

OUTPUT:
- dashboard-ui/src/components/RotationStatusCard.tsx — Rotate-all button + filter chips
- dashboard-ui/src/components/RotationBatchFlow.tsx (new) — the batch modal (candidate selection → confirmation → progress → receipt)
- dashboard-ui/src/dashboardData.ts — types for batch payload + batch job snapshots
- npm run build in dashboard-ui/

OPEN QUESTIONS:
- Should RotationBatchFlow be a separate component or extend RotationTriggerFlow? Lean: separate. The batch flow has enough different state (filter, candidate list, per-secret sub-progress) to warrant its own component; sharing the confirmation-input subcomponent is fine.
- For the "Stop after current" button: should the button text change to "Stopping after this rotation completes" once clicked, with a way to cancel the stop? Lean: yes — the operator might change their mind. Toggle-style.
- For the candidate list in the confirmation step: order by class (A first, then B-API, then B-human) or by name? Lean: by class — surfaces the higher-risk Class B rotations visibly.
```

## Step 5.1 — End-to-end verification of all four phases

Model: Manual run-through; Sonnet 4.6 · High / GPT-5.5 · High for any iteration edits
Parallel: NO

Truth-from-the-running-product verification of every phase. Same shape as campaign #7's Step 3.3 — reset besk, re-scaffold to v0.2 + this campaign's additions, exercise each verifiable surface.

**Procedure:**

1. **Reset besk** (preserving the post-campaign-7 state to `/tmp/besk-post-c7/` first). `security-scan reset besk-ftigelse.dk --include-rotation-scaffold --backup-to /tmp --yes`.
2. **Re-scaffold besk** via fresh Claude Code session + `/secrets-rotation`. Confirm: the new scaffold uses the post-campaign-8 templates (Phase 1's audit-emit fix, Phase 2's modal additions, Phase 3's emergency flag, Phase 4's batch surface).
3. **Verify Phase 1 (trust contract integrity):**
   - Run a successful Class A test rotation (`rotate CRON_SECRET --test`). Confirm: `audit_log` table has the two events (`initiated` + `completed`). The Tier 1 RSC boundary fix landed.
   - Manually corrupt `data/rotation-state.json` (change a status field). Confirm: the dashboard surfaces the "Trust trail inconsistent" badge.
   - Trigger a long-running rotation, restart the dashboard subprocess mid-flight, refresh the browser. Confirm: the in-flight job is rediscovered and the modal can re-attach.
   - Run `pytest tests/test_rotation_phrase_drift.py` (or wherever the drift test landed). Confirm: green.
4. **Verify Phase 2 (modal UX):**
   - Open the rotation modal for AUTH_SECRET (Class A). Confirm: phase track shows 4 phases (not 8). Test-mode checkbox is visible. Advanced disclosure has skip-health-check and soak-minutes.
   - Open the modal for ANTHROPIC_API_KEY (Class B-human). Confirm: phase track shows the WAITING_FOR_PASTE slot. Per-secret rotation_warning copy is visible.
   - Trigger a B-human rotation in test mode; confirm a Resume+paste affordance appears when it pauses (skip the actual paste — verify the modal renders).
5. **Verify Phase 3 (emergency rotation):**
   - Open the modal for a Class B secret. Confirm: Advanced disclosure has the "Incident response" / "Emergency mode" subsection. Class A check: emergency checkbox is disabled with tooltip.
   - In test mode, trigger an emergency rotation. Confirm: confirmation phrase changes to the emergency variant; receipt carries `emergency: true, emergency_mode: true`; "Emergency rotated" pill appears in the rotation card post-completion.
6. **Verify Phase 4 (Rotate-all):**
   - Click "Rotate all" on besk. Confirm: candidate list shows all NEVER-rotated secrets. Filter chips narrow correctly. Tier 5R batch confirmation phrase mentions the count.
   - In test mode, run a batch of 3 Class A secrets. Confirm: sequential execution; per-secret progress visible; batch receipt at `data/rotation-receipts/batch-<timestamp>.md` lists all three with their sub-status.
   - Force a halt mid-batch (use `--fail-at` on the second secret). Confirm: queue STOPS; "continue / stop / rollback completed" choice appears.
7. **Optional restore.** If you want besk back to its post-campaign-7 state, restore from `/tmp/besk-post-c7/`.

**Acceptance criteria:**

- All four phase verifications pass with on-disk evidence + UI screenshots.
- Receipt at `campaigns/devsec-rotation-completeness/receipts/01-end-to-end.md` captures the evidence (state file diffs, JSONL excerpts, screenshots, MCP query outputs).
- Any drift between implementation and spec gets a note in the receipt; if substantial, gets reopened in the affected step before moving to Final review.

```text
/verify

SCOPE: End-to-end manual verification of all four campaign phases against a freshly-reset besk with the post-campaign-8 scaffold.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-completeness.md — this campaign (verify each step's acceptance criteria against the running product)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-followup-notes.md — original audit substance
3. ~/.claude/skills/secrets-rotation/SKILL.md — post-campaign-8 doctrine; confirm new contracts are documented

PROCEDURE:
- Back up besk's current (post-campaign-7) state to /tmp before reset.
- Run the 7 verification steps above in order.
- For each, capture: on-disk evidence (state file shape, JSONL contents, receipt file existence + content), MCP/API output, dashboard screenshot.
- Note any drift from the spec; surface in the receipt; reopen the affected step if substantive.

ACCEPTANCE:
- Each phase's verifications produce the expected evidence.
- Receipt at campaigns/devsec-rotation-completeness/receipts/01-end-to-end.md captures every step's outcome.
- If any drift requires reopening a step, note which step and why; don't close the campaign with known gaps.

OPEN QUESTIONS:
- The Tier 1 audit-emit verification: it requires reading from besk's actual audit_log surface — confirm the query path exists in besk (likely `src/scripts/audit-dump.ts` or similar). If it doesn't, note the verification path can only confirm the rotation-skill side wrote the event (no `audit-emit-failed` in jsonl) but can't confirm receipt-side persistence.
- For the dashboard restart test: graceful restart (HUP signal) or hard kill + relaunch? Lean: hard kill — that's the worst case the persistence/rediscovery fix has to handle.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the devsec-rotation-completeness campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-completeness.md
Campaign: campaigns/devsec-rotation-completeness.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff (for repo-side changes) and the actual files in ~/.claude/skills/secrets-rotation/ (for skill-side work in Steps 1.1, 3.1, 4.1) that the criteria actually landed. Don't trust step receipts — read the actual files.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas. Specifically watch for:

- Step 1.1: did the Tier 1 audit-emit fix actually produce real `emitAuditEvent` calls on the besk fixture, or did it just suppress the error without delivering the event? Read the audit_log query result, not just the jsonl absence of audit-emit-failed.
- Step 1.2: are all three bundled fixes shipped, or did one get quietly dropped? Consistency check helper + dashboard badge + job rediscovery (or persistence) + confirmation phrase drift test — verify each.
- Step 2.1 + 2.2: the dashboard bundle was rebuilt (index.html in git references the new hashed JS, not a stale bundle). Both steps touched dashboard-ui/src/; both needed npm run build.
- Step 3.1: emergency rotation refuses for Class A. The Tier 5R phrase variant is enforced character-for-character. Receipt carries the EMERGENCY_ROTATION shape with all required fields.
- Step 4.1: HALT semantics work — a forced halt mid-batch produces the operator-choice surface, not a silent continue.
- Step 4.2: the Rotate-all UI was rebuilt into the served bundle (same build-pipeline discipline as Steps 2.1/2.2/3.2).
- Step 5.1: end-to-end verification actually exercised the running product, not just code review. Receipts capture concrete evidence per phase, not assertions.
- Campaign-wide: every step that touched dashboard-ui/src/ has the rebuilt bundle in git (index.html change in the commit). Build-pipeline discipline didn't slip again.

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
