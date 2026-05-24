# 3 · DëvSec rotation foundation — stack-agnostic skill with proven verification

> When our security tool finds a leaked password, the user usually has to manually click through provider websites to change it — a chore that often gets skipped. This work lets the tool change passwords automatically and then proves the new one actually works by watching real traffic for 15 minutes — across any kind of project, not just Vercel apps.

## Scope

Two structural shifts to the existing `~/.claude/skills/secrets-rotation/` skill so it becomes the universal rotation foundation rather than a Vercel feature. The DëvSec integration (dashboard buttons, MCP tools, slash commands) is a separate, sequential campaign that consumes what this one ships.

**Shift 1 — Stack abstraction.** Extract the existing Vercel-specific code paths (deploy, env-write, verify probe, log-based soak) into per-stack adapters. Ship Vercel adapter (refactor of existing code) and Python CLI adapter (a maximally different stack with no deploy step, no cloud env vars, no HTTP traffic). The two adapters at opposite ends of the design space prove the abstraction works; future stacks (Fly, Railway, Docker, Render) become additive PRs that conform to the interface this campaign establishes.

**Shift 2 — Closed verification loop.** Add canary-first staging (preview → verify → prod) so a bad credential never touches production. Add a default-on soak-test phase that measures auth-related error rate post-rotation against a pre-rotation baseline. Refuse to rotate if the pre-rotation baseline is already unhealthy (don't rotate into a fire). Generate a unified verification report written to file in the DëvSec Security Brief format — explicit positive signals ("Provider ✓ Application probe ✓ Soak ✓ — rotation verified") so the operator never wonders whether the rotation actually worked.

Done when: the skill can rotate a secret end-to-end on both a Next.js + Vercel project AND a pure Python CLI project, with a soak-tested verification report that gives the operator the "you are safe" signal Christian explicitly named as the missing piece. Demo target for the Python CLI side is dëv-security itself with a synthetic `DEVSEC_GITHUB_TOKEN` for OpenSSF Scorecard checks — eating our own dog food, end-to-end.

## Context (locked decisions)

- **Two adapters in v0.2, not five.** Vercel (refactor of existing code) + Python CLI (new, maximally different). Together they prove the abstraction across the design space. Fly, Railway, Docker, Render, etc., become additive PRs after this lands.
- **Maximally-different test pick: Python CLI.** Picked specifically because it has no deploy step, no cloud env vars, no HTTP traffic — i.e., NONE of the assumptions the Vercel adapter makes. If the abstraction handles both extremes cleanly, it handles everything in between. Picking another edge-serverless platform (Fly) would test a narrow region of the design space and discover gaps too late.
- **Plugin-style adapter architecture.** Each adapter lives in `templates/adapters/<stack>.ts.tmpl`. The skill detects stack at scaffold time and writes only the matching adapter into the target repo. No "all adapters in every repo" bloat.
- **Skill stays at user scope** (`~/.claude/skills/secrets-rotation/`). Bundling via DëvSec install is a Campaign 2 concern. This work is invisible to DëvSec users until Campaign 2 ships; visible to anyone running `/secrets-rotation` immediately.
- **Soak window: 10 min minimum, 15 min default, 60 min maximum.** Industry SLO target from current SRE practitioner writing is "99.9% of rotations succeeding within 10 minutes of scheduled time." Use 10 as floor, 15 as default, 60 as ceiling. Document the rationale so future maintainers don't shorten without reason.
- **Soak test is DEFAULT, not opt-in.** The whole point of v0.2 is "rotation that proves itself." If the proof is optional, people skip it under deadline pressure — exactly when verification matters most. `--no-soak` requires an explicit flag and prints a "you are flying without verification" warning.
- **Pre-rotation health check refuses rotation if app is already unhealthy.** Capture 5-min baseline auth-error rate BEFORE rotation. If above threshold (configurable, default: any auth errors in baseline = halt), refuse to rotate with "your app is showing auth errors before rotation; investigate before rotating into a fire." Catches the "operator panics and tries to rotate as a fix" failure mode.
- **Canary-first staging.** STAGE preview → VERIFY against preview → THEN STAGE prod. For Vercel: native preview deployments. For Python CLI: dry-run-with-new-value mode that uses the new secret without committing it to `.env`. Catches bad credentials before they touch anywhere real.
- **CLI soak mechanic: 3 invocations of operator-specified smoke command, spaced across the soak window (start, middle, end), plus stderr/stdout monitoring for auth-error patterns during each invocation.** Three is enough to catch flaky behavior and cold-cache issues; stderr monitoring catches the "binary returns 0 but logs auth warning" case the operator would miss.
- **Unified verification report writes to a FILE, not just stdout.** `data/rotation-receipts/<secret>-<timestamp>.md`. Format matches the DëvSec Security Brief pattern from `campaigns/devsec-agent-doctrine/notes/calibration-examples.md` example #10. Shareable into Slack, attachable to PRs, referenceable in audit. ~10 lines of additional code; meaningful product surface.
- **Auto-first-rotation as part of scaffolding, with operator picking which secret.** Scaffolding ends with a prompt: "Which Class A secret would you like to rotate first as a confidence test?" lists options with safety annotations (e.g. "AUTH_SECRET rotating invalidates all active sessions ⚠"), operator picks one, rotation runs. Converts the felt experience from "set up rotation" to "your first secret just got rotated and verified." Auto-rotating the first-alphabetical secret is a footgun; auto-rotating an operator-picked secret is a guided demo.
- **Failure injection mode (`--fail-at <step>`) added to internal test suite.** Deliberately injects failures at a named pipeline step and confirms the HALT message is clear and the rollback works. Lives in the skill's tests, not exposed to end users. ~50 lines; the discipline that keeps the trust contract honest as the code evolves.
- **No skill rename.** It stays `secrets-rotation`. The skill IS the universal rotation layer; DëvSec uses it, doesn't own it. Renaming would imply ownership we don't claim.
- **Long-running-process refresh awareness deferred to v0.3.** Documented as a known gap in SKILL.md with a manual mitigation ("if you have long-running workers, restart them after rotation completes"). The detection mechanic is per-stack and complex; out of scope for this campaign.
- **Demo target for Python CLI: dëv-security itself with synthetic `DEVSEC_GITHUB_TOKEN`.** Eating our own dog food. The synthetic secret is real enough (env var in `.env`, used by a Python module, verified by re-running the CLI), and the positioning is strong ("DëvSec rotates DëvSec's own secrets"). Keep or delete the synthetic artifact after the demo at the operator's discretion.
- **Campaign is independently shippable but benefits from `/devsec-agent-doctrine` landing first.** The verification report references the Security Brief format from the doctrine campaign. The format is already locked via calibration-examples.md #10, so this campaign doesn't strictly depend on the doctrine campaign — but the doctrine doc gives broader context that helps future contributors understand the format choice.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 0 — Audit and recalibrate

- [x] Step 0.1 — Read the skill end-to-end, identify exact extraction points, adjust Phase 1's step prompts in place if reality differs

### Phase 1 — Extract the adapter abstraction

- [x] Step 1.1 — Sketch adapter interface and extract Vercel adapter
- [x] Step 1.2 — Implement Python CLI adapter (stress-tests the abstraction)
- [x] Step 1.3 — Reconcile interface based on Phase 1.2 findings; document; add stack-detection

### Phase 2 — Close the verification gap

- [x] Step 2.1 — Implement canary-first staging + pre-rotation health refusal
- [x] Step 2.2 — Implement soak-test pipeline phase (default-on, per-adapter)
- [x] Step 2.3 — Implement unified verification report (file-written, Security Brief format)

### Phase 3 — Hardening, demo, receipts

- [x] Step 3.1 — Update SKILL.md / catalog.json / runbook template; add `--fail-at` failure injection mode to test suite
- [x] Step 3.2 — End-to-end demo on both stacks (real Next.js + Vercel project AND dëv-security with synthetic token), capture receipts
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 0.1 — Audit existing skill, recalibrate Phase 1 prompts

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

The skill was written months ago and this campaign is being authored without re-reading every template file. Before locking in the adapter abstraction shape, audit current code to find the exact extraction points and adjust Phase 1's step prompts in place if reality differs from the plan.

Authority bounds:

- MAY update `REQUIRED READING`, acceptance criteria, `OPEN QUESTIONS`, model/parallel lines for Steps 1.1, 1.2, 1.3.
- MAY merge or split steps within Phase 1 if the actual extraction shape requires it.
- MAY NOT silently add a phase, weaken intent, or change locked decisions.
- MUST produce a short audit report at `campaigns/devsec-rotation-foundation/notes/phase-0-audit.md` documenting what was found and what was changed in the campaign markdown.

What to audit:

1. **The current pipeline shape.** Read `~/.claude/skills/secrets-rotation/templates/lib/pipeline.ts.tmpl`. Identify every Vercel-specific assumption (Vercel CLI calls, vercel.json references, preview-vs-prod targeting, `vercel env add`, `vercel inspect`).
2. **The current verify-probe shape.** Read `~/.claude/skills/secrets-rotation/templates/lib/plugin-shape.ts.tmpl` and the Class A/B-API/B-human plugin templates. What method signature does VERIFY use today? How tightly is it coupled to HTTP probes?
3. **The current state-file shape.** Read `~/.claude/skills/secrets-rotation/templates/lib/state.ts.tmpl`. What does the state machine assume about file paths, lock mechanisms, and platform-specific behavior?
4. **The existing soak/verify behavior.** Look for any existing log-tailing or post-deploy monitoring. The campaign assumes there's NONE — confirm or contradict.
5. **Stack detection logic.** Read scripts/scan-repo.ts and scripts/classify.ts. How does the skill currently decide it's a Next.js + Vercel repo? Where would Python CLI detection slot in?

Output:

- `campaigns/devsec-rotation-foundation/notes/phase-0-audit.md` — 1-2 page audit report.
- Edits to Steps 1.1, 1.2, 1.3 in this campaign markdown if needed, with a one-line note at the top of each edited step's body saying "Updated by Step 0.1: <what changed and why>."

```text
/socraticode

SCOPE: Audit ~/.claude/skills/secrets-rotation/ end-to-end. Identify exact extraction points for the Vercel adapter, exact assumptions baked into the pipeline interface, and exact places Python CLI support would slot in. Update Phase 1 step prompts in this campaign in place if reality differs.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-foundation.md — this campaign (you may edit Phase 1's step prompts in place)
2. ~/.claude/skills/secrets-rotation/SKILL.md
3. ~/.claude/skills/secrets-rotation/catalog.json
4. ~/.claude/skills/secrets-rotation/docs/PLAYBOOK.md
5. ~/.claude/skills/secrets-rotation/templates/lib/pipeline.ts.tmpl
6. ~/.claude/skills/secrets-rotation/templates/lib/state.ts.tmpl
7. ~/.claude/skills/secrets-rotation/templates/lib/plugin-shape.ts.tmpl
8. ~/.claude/skills/secrets-rotation/templates/lib/vercel-env.ts.tmpl
9. ~/.claude/skills/secrets-rotation/templates/plugins/class-a.ts.tmpl
10. ~/.claude/skills/secrets-rotation/templates/plugins/class-b-api.ts.tmpl
11. ~/.claude/skills/secrets-rotation/templates/plugins/class-b-human.ts.tmpl
12. ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl

OUTPUT:
- campaigns/devsec-rotation-foundation/notes/phase-0-audit.md — short audit report covering: (a) current Vercel-specific assumptions, (b) plugin-shape interface today, (c) state-machine assumptions, (d) existing verify/soak behavior, (e) stack-detection logic, (f) recommended adapter interface signature based on what you found.
- In-place edits to Steps 1.1, 1.2, 1.3 of this campaign markdown if your findings require adjustments. Mark every edited step with "Updated by Step 0.1: <change reason>" at the top of its body.

OPEN QUESTIONS:
- Is there code in the skill today that's already adapter-shaped (good signal: clean extraction) or is Vercel-coupling threaded through the pipeline (bad signal: harder refactor)?
- Does the plugin-shape interface make verify pluggable today, or is the HTTP-probe assumption baked in?
- Is there any existing test infrastructure (fixtures, mocks) that would help in Phase 1's reconciliation, or do we need to add it?
- Are there abstractions in the skill that look like adapters but aren't — e.g., separate Class A vs Class B paths that COULD have been adapters but are currently if/else branches?

Do not over-architect the recommendations. The goal is to make Phase 1 cheaper and more honest, not to design the adapter interface in advance.
```

## Step 1.1 — Sketch adapter interface and extract Vercel adapter

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

**Updated by Step 0.1**: (1) Refactor scope widened — `rotate.ts.tmpl` is also Vercel-coupled (`readCurrentValueFromEnvOrPull` calls `vercel env pull`; rollback imports `stageEnv`). It must route through the adapter too. (2) Interface refined: `verifyProbe` reconceptualised as `applicationProbe`, sitting alongside `plugin.verify` (provider-side) rather than replacing it. `writeEnv` / `deploy` take `target: "canary" | "prod"` instead of raw Vercel targets, so canary-first staging (Step 2.1) drops in cleanly. `readCurrentValue` and `ensureNoDrift` added because both are Vercel-coupled today. (3) Test-infra warning: the skill has **no** `package.json`, `tsconfig.json`, or `tests/` folder. Step 1.1 carries the one-time cost of standing up the harness (suggest vitest) before any test can be written.

Define the `StackAdapter` TypeScript interface in `~/.claude/skills/secrets-rotation/templates/lib/adapter-shape.ts.tmpl` and extract the existing Vercel-specific code into `~/.claude/skills/secrets-rotation/templates/adapters/vercel.ts.tmpl`. This is mostly a refactor of existing code — the goal is to leave behavior unchanged for Vercel rotations while separating "what the pipeline does" from "what Vercel does."

Interface methods (refined from phase-0-audit.md §f):

- `detect(repoRoot): Promise<boolean>` — does this stack apply to the repo?
- `preflight(repoRoot): Promise<PreflightResult>` — stack-specific preconditions (Vercel: `whoami` + project link; CLI: `.env` writable + smoke cmd on PATH).
- `readCurrentValue(repoRoot, name): Promise<string>` — replaces `readCurrentValueFromEnvOrPull` in `rotate.ts.tmpl`.
- `ensureNoDrift(repoRoot, name, expectedLastStagedAt?): Promise<void>` — Vercel: timestamp compare; CLI: no-op or git-blame check.
- `writeEnv({ repoRoot, name, value, target: "canary" | "prod" }): Promise<void>` — stage the new value. Canary/prod is stack-agnostic vocabulary.
- `deploy({ repoRoot, target, secretName, rotationId }): Promise<DeploymentRef>` — trigger a deploy. Returns opaque ref. Python CLI returns `{ kind: "no-op" }`.
- `applicationProbe({ repoRoot, secretName, deployment, newValue }): Promise<ProbeResult>` — **application-level** verify, distinct from `plugin.verify` (provider-level). For Vercel: hit configured probe URL on the deployment. For Python CLI: run smoke command with new value in process env.
- `baseline({ repoRoot, durationMs, patterns }): Promise<BaselineResult>` — pre-rotation error-rate capture (consumed by Phase 2.1 HEALTH_CHECK).
- `soakWindow({ repoRoot, durationMs, patterns, baseline }): Promise<SoakResult>` — post-rotation error-rate vs baseline (Phase 2.2 SOAK).
- `rollback({ repoRoot, name, previousValue }): Promise<void>` — restore previous value.

`plugin.verify` stays unchanged on the per-secret plugin layer. Do NOT collapse it into the adapter — provider check and application check are independent signals.

Vercel adapter implements all of these by lift-and-shifting existing code from `lib/vercel-env.ts.tmpl` and the direct call sites in `lib/pipeline.ts.tmpl` / `rotate.ts.tmpl`. `applicationProbe`, `baseline`, `soakWindow` are net-new for Vercel (deploy-readiness polling exists, soak doesn't).

Acceptance criteria:

- `templates/lib/adapter-shape.ts.tmpl` exists, defining the `StackAdapter` interface with JSDoc per method (including `DeploymentRef`, `ProbeResult`, `BaselineResult`, `SoakResult` shapes).
- `templates/adapters/vercel.ts.tmpl` exists, implementing every interface method.
- `lib/pipeline.ts.tmpl` is refactored: no direct imports from `./vercel-env`; all stack-touching calls route through the adapter.
- `rotate.ts.tmpl` is refactored: `readCurrentValueFromEnvOrPull` is gone; rollback uses `adapter.rollback` not `stageEnv`.
- Test infrastructure is stood up: `package.json` with vitest (or matching ecosystem choice), `tsconfig.json`, `tests/` folder. Add one smoke test that runs a fixture Class A rotation against a mock adapter (in-memory stand-in for Vercel) and confirms the pipeline reaches ROTATED.
- The interface is documented in `templates/lib/adapter-shape.ts.tmpl` with JSDoc comments explaining the contract for each method.

```text
/health-implement

SCOPE: Define the StackAdapter interface and extract the existing Vercel-specific code into a Vercel adapter. Refactor pipeline.ts.tmpl AND rotate.ts.tmpl to call adapter methods instead of Vercel-specific code directly. Stand up test infrastructure (the skill has none today). Preserve existing behavior for Vercel rotations.

REQUIRED READING:
1. campaigns/devsec-rotation-foundation/notes/phase-0-audit.md (delivered by Step 0.1 — read this FIRST. §a lists every Vercel call site; §f has the recommended interface signature)
2. ~/.claude/skills/secrets-rotation/SKILL.md (the design principles and trust contract)
3. ~/.claude/skills/secrets-rotation/templates/lib/pipeline.ts.tmpl (the code being refactored — direct vercel-env imports at L36-47)
4. ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl (also Vercel-coupled — see audit §a for call sites)
5. ~/.claude/skills/secrets-rotation/templates/lib/vercel-env.ts.tmpl (Vercel-specific code being lifted into the adapter)
6. ~/.claude/skills/secrets-rotation/templates/lib/plugin-shape.ts.tmpl (existing per-secret plugin interface — UNCHANGED; do not collapse into the adapter)
7. ~/.claude/skills/secrets-rotation/templates/plugins/class-a.ts.tmpl (consumes the pipeline; verify-probe path may need a context tweak so applicationProbe can co-exist)

OUTPUT:
- ~/.claude/skills/secrets-rotation/templates/lib/adapter-shape.ts.tmpl (new — interface + DeploymentRef / ProbeResult / BaselineResult / SoakResult types with JSDoc)
- ~/.claude/skills/secrets-rotation/templates/adapters/vercel.ts.tmpl (new — Vercel implementation; lift-and-shift from vercel-env.ts.tmpl, add stubs for applicationProbe/baseline/soakWindow even if Phase 2 fleshes them out further)
- ~/.claude/skills/secrets-rotation/templates/lib/pipeline.ts.tmpl (modified — calls adapter methods; no direct ./vercel-env imports)
- ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl (modified — readCurrentValue + rollback routed through adapter)
- ~/.claude/skills/secrets-rotation/package.json, tsconfig.json, tests/ (new — vitest harness)
- tests/pipeline.smoke.test.ts (new — Class A fixture rotation against a mock adapter, asserts terminal status ROTATED)

OPEN QUESTIONS:
- State-file path: stays in lib/state.ts.tmpl as data/rotation-state.json — works for both stacks per audit §c. Do NOT make adapter-pluggable in v0.2.
- The soakWindow / baseline options shape should live in adapter-shape.ts.tmpl as named types (SoakOptions, BaselineOptions) so both adapters get the same shape and Phase 2.2 doesn't reinvent it.
- applicationProbe vs plugin.verify: keep both. Provider-level (plugin.verify) and application-level (adapter.applicationProbe) are independent signals. The pipeline's runVerify should call BOTH — provider first (cheap, definitive), application after (expensive, integrative). Document the ordering.
- DeploymentRef shape: lean toward a tagged union — `{ kind: "vercel"; url: string } | { kind: "no-op" }`. Pipeline persists it in state for diagnostics; only adapters unpack.
- Class A's verify-probe stub: today it returns a no-op. Now that applicationProbe exists on the adapter, the per-secret class-a template can be tightened (or kept as-is and let applicationProbe carry the load). Lean: keep class-a's verify as the placeholder it is; add a "for application-level checks, use adapter.applicationProbe with a probe URL configured per secret" note.

This is a refactor, not a redesign. Behavior for existing Vercel rotations should be unchanged. If the refactor reveals something that NEEDS to change (e.g., the soakWindow interface needs a method the current code doesn't have), add it — but flag it clearly in the implementation report so we can update the doctrine if the change is load-bearing.
```

## Step 1.2 — Implement Python CLI adapter

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

**Updated by Step 0.1**: (1) Clarification: the adapter itself is TypeScript (`.ts.tmpl`) — the skill's orchestrator stays Node/TS even for Python CLI targets. The "Python" part is the project being rotated (the adapter knows how to read/write its `.env`, run its smoke command). Don't try to rewrite the rotation tool in Python. (2) `verifyProbe` is now `adapter.applicationProbe` (the application-level check), distinct from `plugin.verify` (provider-level). Class A self-generated secrets in Python CLI projects have no provider — so `plugin.verify` stays a no-op stub there and `adapter.applicationProbe` carries the load. (3) `writeEnv` takes `target: "canary" | "prod"` — for Python CLI, "canary" means dry-run (don't commit), "prod" means atomic-replace the `.env`. This makes Phase 2.1's canary-first staging a one-line dispatch, not a special case.

Implement `~/.claude/skills/secrets-rotation/templates/adapters/python-cli.ts.tmpl` against the interface from Step 1.1. This adapter is the abstraction's stress test — it has none of Vercel's assumptions (no deploy, no cloud env vars, no HTTP traffic, no preview environments).

Per-method behavior for Python CLI:

- `detect`: returns true if `pyproject.toml` exists AND no Vercel signals (no `vercel.json`, no `.vercel/`).
- `preflight`: confirms `.env` (or equivalent env-source file) is writable; runs the existing gitleaks-lite scan; verifies the configured smoke command is on PATH.
- `readCurrentValue`: read from `.env` (parse it; tolerate quoted values per dotenv conventions).
- `ensureNoDrift`: stat `.env` mtime against `expectedLastStagedAt` — if `.env` was modified after the last rotation's stage, halt as DRIFT_DETECTED. (Stronger check than git-blame; cheaper too.)
- `writeEnv` with `target: "canary"`: returns silently after validating the new value can parse; nothing touches `.env`. The new value is held by the pipeline in memory and passed to `applicationProbe` via process env.
- `writeEnv` with `target: "prod"`: atomic-replace — write to `.env.tmp`, fsync, rename. Backs up the previous file as `.env.backup-<timestamp>` for `rollback` to use.
- `deploy`: returns `{ kind: "no-op" }` for both targets. CLIs don't deploy; the new value takes effect on next invocation.
- `applicationProbe`: runs the operator-specified smoke command (e.g., `security-scan --version`) with the new env value injected via the process environment. Expects exit code 0. Captures stdout/stderr for the soak's pattern matching.
- `baseline` (Phase 2.1 pre-rotation): 3 invocations of the smoke command spaced across the duration window, monitoring stdout/stderr against the auth-error regex list. Returns count of pattern hits; if any → baseline is unhealthy.
- `soakWindow` (Phase 2.2 post-rotation): same shape as baseline but compares hit-count against the captured baseline + tolerance.
- `rollback`: restores `.env` from the most recent `.env.backup-<timestamp>`.

Canary-first staging for Python CLI maps cleanly via `target: "canary" | "prod"`: canary writeEnv is a no-op (value lives in memory only), applicationProbe runs against it, then prod writeEnv commits to disk. No special-case branching needed.

`plugin.verify` for a self-generated secret with no provider: stays as the no-op stub it is today. Provider-level verify is genuinely "nothing to verify" for Class A in a stack with no external dependency. The trust signal comes from `adapter.applicationProbe` and the soak.

Acceptance criteria:

- `templates/adapters/python-cli.ts.tmpl` exists, implementing every StackAdapter interface method.
- Detection logic distinguishes Python CLI from Python web (Django/FastAPI deployed to Vercel/Fly/etc.) — only Pure-CLI matches.
- Canary mode (verify-before-commit) is implemented via the `target: "canary"` dispatch on `writeEnv` — no separate "dry-run mode" flag.
- A smoke test scaffolds a fixture rotation against a mock Python CLI project (a minimal `pyproject.toml` + `.env` + dummy smoke script that reads an env var and exits 0/1) and confirms the pipeline reaches ROTATED.
- Any interface gaps discovered (methods the Vercel adapter has that Python CLI can't fulfill, or vice versa) are documented in `campaigns/devsec-rotation-foundation/notes/interface-gaps.md` for Step 1.3 to reconcile.

```text
/health-implement

SCOPE: Implement the Python CLI adapter (TypeScript template, drives Python projects) against the StackAdapter interface defined in Step 1.1. This adapter has no deploy, no cloud env vars, no HTTP traffic — it stress-tests the interface. Document any interface gaps for Step 1.3 to reconcile.

REQUIRED READING:
1. ~/.claude/skills/secrets-rotation/templates/lib/adapter-shape.ts.tmpl (interface to implement, delivered by Step 1.1)
2. ~/.claude/skills/secrets-rotation/templates/adapters/vercel.ts.tmpl (the reference implementation, delivered by Step 1.1)
3. ~/.claude/skills/secrets-rotation/SKILL.md (trust contract and design principles still apply)
4. campaigns/devsec-rotation-foundation/notes/phase-0-audit.md (Step 0.1 audit findings — particularly §b on the two verify layers)
5. /Users/christiankatzmann/Dev/Projects/dëv-security/pyproject.toml — example of a real Python CLI pyproject for the detection logic to recognize
6. ~/.claude/skills/secrets-rotation/templates/plugins/class-a.ts.tmpl (Class A self-generated secret — note its verify stub; for Python CLI Class A, this stays a stub and adapter.applicationProbe carries the load)

OUTPUT:
- ~/.claude/skills/secrets-rotation/templates/adapters/python-cli.ts.tmpl (new)
- campaigns/devsec-rotation-foundation/notes/interface-gaps.md (new — document any methods that don't fit cleanly so Step 1.3 can reconcile)
- tests/python-cli.smoke.test.ts (new — uses the vitest harness stood up in Step 1.1)

OPEN QUESTIONS:
- The smoke command for applicationProbe needs to be operator-specified at scaffold time. What's the catalog entry shape for this? Suggest: a `smoke_command` field per Python CLI secret entry; the scaffold flow prompts the operator to provide one. The default for the dëv-security demo: `security-scan --version`.
- Canary-mode constraint: the in-memory-new-value pattern requires the smoke command to accept the secret via environment variable (not via a config file the CLI reads from disk). Some CLIs read config from files only. For those: canary mode degrades to "writeEnv prod, applicationProbe, rollback on failure" — slightly less safe but the best we can do. Document this honestly in the adapter's JSDoc.
- soakWindow spacing: 3 invocations spaced across the window. If the window is 10 min, that's t=0/5/10. If 15 min, that's t=0/7.5/15. If 60 min, that's t=0/30/60. Document the spacing formula in the adapter and warn that smoke commands taking >1 min compress the spacing meaningfully.
- Stderr/stdout monitoring during invocations: default regex list `auth.*fail|unauthorized|invalid.*token|jwt.*expired|permission.*denied` — keep configurable per secret in the catalog as `auth_error_patterns`.
- Plugin.verify for Class A in a Python CLI project: the stub returns `{ ok: true, probedEndpoint: "(class-a stub)" }`. That's honest — there's no provider to probe. Document explicitly so future contributors don't try to "fix" it.

Resist the temptation to invent abstractions for stacks beyond Vercel and Python CLI. If the interface needs reshaping based on findings here, that's Step 1.3's job — focus on making Python CLI work cleanly first, document gaps separately.
```

## Step 1.3 — Reconcile interface, add stack detection, document the abstraction

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

**Updated by Step 0.1**: (1) `scripts/scan-repo.ts` and `scripts/classify.ts` referenced in the original prompt **do not exist** — the skill's `scripts/` folder is empty. Stack detection today is described in SKILL.md / `docs/PLAYBOOK.md` as agent operating procedure, executed by the human/agent reading instructions. Step 1.3 must CREATE the detection code from scratch (suggest `templates/lib/adapter-registry.ts.tmpl` for the registered-adapters list, plus a `selectAdapter` function the scaffolding flow calls). There is nothing to extend. (2) Required reading list pruned accordingly.

Refactor the StackAdapter interface based on Step 1.2's findings so both Vercel and Python CLI adapters comply cleanly without per-stack hacks. Add stack-detection logic to the scaffolding flow. Update SKILL.md to document the abstraction.

What to reconcile:

1. **Interface refactor.** Read `campaigns/devsec-rotation-foundation/notes/interface-gaps.md` (from Step 1.2). For each gap, decide: change the interface, change the adapter, or document the constraint. NO `if (stack === "vercel")` branches in the pipeline — that's the failure mode this campaign is preventing.
2. **Stack detection — NEW code.** Create `templates/lib/adapter-registry.ts.tmpl` exporting a registered-adapters array and a `selectAdapter(repoRoot): Promise<StackAdapter>` function. Iterates over registered adapters, calls each `detect()`, returns the matching one. If multiple match or none match, halt with a clear message asking the operator to choose or to add a stack-detection hint. The scaffolding flow (currently described in SKILL.md "Step 1 — Discover" as agent procedure) gets a code path that calls `selectAdapter`.
3. **SKILL.md updates.** Document the adapter architecture in a new "Stack adapters" section. List the v0.2 adapters (Vercel, Python CLI), document the interface, document how future adapters get added. ALSO update the "Operating procedure" section to reference `selectAdapter` instead of describing manual detection.
4. **catalog.json schema update.** Add per-stack hints where catalog entries need them (e.g., Python CLI entries can carry `smoke_command` and `auth_error_patterns` fields).
5. **runbook template update.** The scaffolded runbook should print the right shape per stack — for Python CLI, no "Vercel deploy" section, etc.

Acceptance criteria:

- Interface is consistent — both adapters comply without per-stack hacks in the pipeline.
- Stack detection works on at least three fixture repos: a Next.js + Vercel project, a Python CLI project, and a Python + Vercel project (should detect as Vercel, not Python CLI).
- SKILL.md has a "Stack adapters" section under the "Templates folder" section; the "Operating procedure" section's Step 1 references `selectAdapter` instead of describing manual detection.
- catalog.json schema is updated; existing entries still validate.
- runbook template renders correctly for both stacks.
- `campaigns/devsec-rotation-foundation/notes/interface-gaps.md` is closed out — every gap has a documented resolution.

```text
/health-implement

SCOPE: Reconcile the StackAdapter interface so both Vercel and Python CLI adapters comply cleanly. Create NEW adapter-registry / selectAdapter code (the skill's scripts/ folder is empty — see audit §e). Update SKILL.md, catalog.json schema, and runbook template to reflect the multi-stack reality.

REQUIRED READING:
1. campaigns/devsec-rotation-foundation/notes/interface-gaps.md (Step 1.2's findings)
2. campaigns/devsec-rotation-foundation/notes/phase-0-audit.md (§e on the empty scripts/ folder)
3. ~/.claude/skills/secrets-rotation/templates/lib/adapter-shape.ts.tmpl (Step 1.1)
4. ~/.claude/skills/secrets-rotation/templates/adapters/vercel.ts.tmpl (Step 1.1)
5. ~/.claude/skills/secrets-rotation/templates/adapters/python-cli.ts.tmpl (Step 1.2)
6. ~/.claude/skills/secrets-rotation/SKILL.md (target of doc updates; "Operating procedure" Step 1 currently describes manual detection)
7. ~/.claude/skills/secrets-rotation/docs/PLAYBOOK.md (also describes manual detection; update in lockstep)
8. ~/.claude/skills/secrets-rotation/catalog.json (target of schema updates)
9. ~/.claude/skills/secrets-rotation/templates/runbook.md.tmpl (target of template updates)

OUTPUT:
- Reconciled adapter-shape.ts.tmpl (interface possibly refactored)
- Updated vercel.ts.tmpl and python-cli.ts.tmpl (compliance with reconciled interface)
- New templates/lib/adapter-registry.ts.tmpl (registered adapters + selectAdapter function)
- Updated SKILL.md (new "Stack adapters" section; "Operating procedure" Step 1 references selectAdapter)
- Updated docs/PLAYBOOK.md (manual detection references replaced with selectAdapter call)
- Updated catalog.json (schema extensions for per-stack hints — smoke_command, auth_error_patterns)
- Updated runbook.md.tmpl (renders correctly for both stacks)
- Closed-out interface-gaps.md with documented resolutions

OPEN QUESTIONS:
- If the interface NEEDS a method that's a no-op for one of the adapters, is that a sign of bad abstraction? Lean: no — adapters CAN have no-op implementations (Python CLI's deploy() is a no-op returning `{ kind: "no-op" }`, that's honest). But if multiple methods are no-ops, the abstraction is leaking the stack-specific shape into the interface — that IS a sign to redesign.
- Stack detection precedence: Python + Vercel should detect as Vercel (Vercel signal is stronger — `vercel.json` or `.vercel/` directory). Document the precedence rules in SKILL.md so future adapters know where they slot in. Suggest: detect order = [vercel, python-cli], first match wins.
- Should the StackAdapter interface be exposed in the SCAFFOLDED repo as an extension point (so power users can write their own adapter), or kept private to the skill? Lean: keep private for v0.2. Adding user-extension points is a v0.3+ decision.
- selectAdapter ambiguity: if `detect()` returns true for zero adapters, halt with "no adapter matched this repo. Supported in v0.2: Vercel (Next.js + .vercel/), Python CLI (pyproject.toml, no Vercel signals)." If multiple match, the precedence rule resolves automatically — but log which adapters matched so the operator sees the disambiguation.
```

## Step 2.1 — Implement canary-first staging and pre-rotation health refusal

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Add two safety primitives to the pipeline: canary-first staging (preview → verify → prod) and pre-rotation health refusal (refuse to rotate if app is already unhealthy).

**Canary-first staging.** Currently the STAGE step writes the new value atomically to `preview + production + development`. New behavior:

1. STAGE preview only.
2. Deploy preview (if adapter supports it).
3. VERIFY against preview deployment.
4. ONLY THEN: STAGE prod + development.
5. Deploy prod.
6. VERIFY against prod.

For Python CLI: "canary" means the verifyProbe runs against the in-memory new value (already implemented in Step 1.2). The two-phase staging maps to "dry-run verify → commit to `.env`".

**Pre-rotation health refusal.** Before PREFLIGHT, add HEALTH_CHECK step:

1. Run adapter's `soakWindow({duration: 5_min, mode: "baseline"})` to capture 5-min baseline error rate.
2. If baseline error rate > threshold (default: any auth-error pattern matches in baseline = halt), refuse to rotate.
3. Halt message: "Your app is showing auth errors before rotation. Rotation will not help and may make diagnosis harder. Investigate first."
4. `--skip-health-check` flag bypasses (for cases where the operator knows the baseline is unhealthy and is rotating anyway as part of incident response).

Acceptance criteria:

- Canary-first staging works on Vercel (verified against preview before staging prod).
- Pre-rotation health refusal works on both adapters (Vercel via log baseline, Python CLI via 3 baseline invocations of the smoke command — if any fail, refuse).
- `--skip-health-check` flag exists and is documented in `rotate.ts.tmpl` and the runbook.
- All existing terminal states still work: ROTATED (success), HALTED_AT_<step> (failure), now including HALTED_AT_HEALTH_CHECK and HALTED_AT_CANARY_VERIFY.
- Pre-rotation health refusal emits an audit event in Tier 1 repos (phase: "refused_unhealthy_baseline").

```text
/health-implement

SCOPE: Add canary-first staging (preview → verify → prod) and pre-rotation health refusal (don't rotate into a fire) to the rotation pipeline. Both adapters must support both primitives.

REQUIRED READING:
1. ~/.claude/skills/secrets-rotation/templates/lib/pipeline.ts.tmpl (the pipeline being extended)
2. ~/.claude/skills/secrets-rotation/templates/adapters/vercel.ts.tmpl (Step 1's Vercel adapter)
3. ~/.claude/skills/secrets-rotation/templates/adapters/python-cli.ts.tmpl (Step 1's Python CLI adapter)
4. ~/.claude/skills/secrets-rotation/templates/lib/errors.ts.tmpl (where new HALTED_AT_HEALTH_CHECK and HALTED_AT_CANARY_VERIFY error codes go)
5. ~/.claude/skills/secrets-rotation/templates/lib/audit-emit.ts.tmpl (Tier 1 audit event for refused_unhealthy_baseline)

OUTPUT:
- Updated pipeline.ts.tmpl with HEALTH_CHECK step before PREFLIGHT and split STAGE → STAGE_CANARY → VERIFY_CANARY → STAGE_PROD → VERIFY_PROD
- Updated errors.ts.tmpl with new error codes + human messages
- Updated audit-emit.ts.tmpl with "refused_unhealthy_baseline" phase
- Updated rotate.ts.tmpl with --skip-health-check flag
- Updated state.ts.tmpl with new states (HEALTH_CHECK_FAILED, CANARY_VERIFY_FAILED, IN_CANARY_VERIFY)
- Updated runbook.md.tmpl to document the new safety primitives

OPEN QUESTIONS:
- Should canary-first staging be opt-out via a --no-canary flag? Lean: no for v0.2. The whole point is safer-by-default. Adding the flag is one line if it turns out users need it.
- For Python CLI, "STAGE_CANARY" maps to in-memory verify before writing .env. Is that visibly a "canary" step or hidden inside writeEnv? Lean: make it visible (separate state) for diagnostic clarity. Operator can see "we verified before writing" in the state file.
- Pre-rotation health refusal threshold: any auth errors = refuse, or N errors per minute? Lean: any errors in baseline window = refuse, with --skip-health-check as the escape hatch. Simpler to explain.

This step doesn't add a new pipeline phase — it adds gates within existing phases. The pipeline becomes: HEALTH_CHECK → PREFLIGHT → ACQUIRE → STAGE_CANARY → VERIFY_CANARY → STAGE_PROD → VERIFY_PROD → [SOAK in Step 2.2] → GRACE → REVOKE.
```

## Step 2.2 — Implement soak-test pipeline phase

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Add the SOAK phase to the pipeline, default-on. Lives between VERIFY_PROD and GRACE. Per-adapter implementation.

**Pipeline placement.** After VERIFY_PROD passes, run SOAK:

1. Adapter's `soakWindow({duration: <configured>, mode: "verify", baseline: <captured pre-rotation>})`.
2. Soak runs for 10/15/60 min (configurable per secret in catalog, default 15).
3. Vercel: tail `vercel logs` filtering for auth-error patterns; compare to baseline rate.
4. Python CLI: 3 invocations of smoke command spaced across the window; stderr/stdout monitored for auth patterns.
5. If anomalies detected (rate above baseline + tolerance), HALT and surface the spike.
6. If clean, transition to GRACE.

**Default-on with explicit override.** `--no-soak` exists but prints a warning: "⚠ Soak skipped. Rotation will reach ROTATED without verifying the new credential works under real conditions. This defeats the trust contract — only use this when you have an independent verification path."

**Soak window configuration.** Per-secret in catalog: `soak_window_minutes` (default 15, min 10, max 60). Per-stack defaults if the catalog doesn't specify.

Acceptance criteria:

- SOAK phase added to pipeline between VERIFY_PROD and GRACE.
- Default-on. `--no-soak` requires explicit flag and prints a warning.
- Configurable soak window (10/15/60 min); catalog can specify per secret.
- Vercel adapter's `soakWindow` tails `vercel logs` and detects auth-error spikes vs baseline.
- Python CLI adapter's `soakWindow` runs 3 spaced invocations with stderr/stdout monitoring.
- New error code `HALTED_AT_SOAK` with plain-English message.
- New audit event phase `"soak_anomaly_detected"` (Tier 1).
- A failure-injection test (foreshadowing Step 3.1) proves the soak detects a deliberately-introduced auth error.

```text
/health-implement

SCOPE: Add the SOAK phase to the rotation pipeline. Default-on (--no-soak requires explicit flag + warning). Per-adapter implementation: Vercel tails vercel logs; Python CLI runs 3 spaced smoke-command invocations.

REQUIRED READING:
1. ~/.claude/skills/secrets-rotation/templates/lib/pipeline.ts.tmpl (where SOAK slots in)
2. ~/.claude/skills/secrets-rotation/templates/adapters/vercel.ts.tmpl (soakWindow implementation)
3. ~/.claude/skills/secrets-rotation/templates/adapters/python-cli.ts.tmpl (soakWindow implementation)
4. ~/.claude/skills/secrets-rotation/templates/lib/state.ts.tmpl (new states for IN_SOAK, SOAK_FAILED)
5. ~/.claude/skills/secrets-rotation/catalog.json (where soak_window_minutes goes per secret)

OUTPUT:
- Updated pipeline.ts.tmpl with SOAK phase between VERIFY_PROD and GRACE
- Updated vercel.ts.tmpl and python-cli.ts.tmpl with full soakWindow implementations
- Updated rotate.ts.tmpl with --no-soak flag (with warning) and --soak-minutes override
- Updated state.ts.tmpl with new states
- Updated errors.ts.tmpl with HALTED_AT_SOAK
- Updated catalog.json with soak_window_minutes field on relevant entries (e.g., add to AUTH_SECRET, CRON_SECRET defaults)
- Updated audit-emit.ts.tmpl with soak_anomaly_detected phase

OPEN QUESTIONS:
- For Vercel soak: how do we know the baseline error rate to compare against? The pre-rotation HEALTH_CHECK from Step 2.1 captured a 5-min baseline. SOAK compares against THAT. Plumb the baseline through the pipeline state.
- For Python CLI soak: 3 invocations spaced across e.g. 15 min = invocations at 0, 7.5, 15 min. If the smoke command takes 30 seconds, that's fine. If it takes 5 minutes (long test suite), the spacing collapses. Document the assumption: smoke commands should complete in < 1 min for the spacing to be meaningful.
- Soak tolerance: how much above baseline counts as anomaly? Lean: any new auth errors in the soak window above zero (assuming baseline was zero — which it must be, since HEALTH_CHECK refused otherwise). Tightest possible tolerance.
- What if SOAK halts? Pipeline state is IN_SOAK_FAILED. The new key is live, the old key is still valid (GRACE hasn't happened). Operator decides: roll forward (mark resolved, accept the anomaly was unrelated) or roll back (restore old value, investigate the anomaly). The runbook should explain both paths.
```

## Step 2.3 — Implement unified verification report (file-written, Security Brief format)

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

At the end of a successful rotation (state = ROTATED or IN_GRACE), write a verification report to `data/rotation-receipts/<secret>-<timestamp>.md` matching the DëvSec Security Brief format. Also print the report to stdout for immediate visibility.

Report format (matches calibration-examples.md #10 from the doctrine campaign):

```markdown
# Rotation verified — `<SECRET_NAME>`

- **Status:** <ROTATED | IN_GRACE>
- **Action: completed · Severity: <inherited from secret's class — A=info, B=medium>**
- **Provider check:** ✓ <provider name> returned <expected status>
- **Application probe:** ✓ <probe description> returned <result>
- **Soak test:** ✓ <window-minutes> min window, 0 new auth-related errors above baseline (<baseline-window> baseline)
- **Old key status:** <revoked | valid until <timestamp> (24h grace)>
- **Audit trail:** rotation_id `<id>`, events emitted to <audit-events.ts | rotation-log.jsonl>

Scope of this verification: <one line — what was tested>. Outside scope: <one line — what wasn't, e.g., "long-running processes that cache credentials in memory may still hold the old value until they next restart">.
```

For HALTED rotations, write a different shape:

```markdown
# Rotation HALTED — `<SECRET_NAME>` at <STEP>

- **Status:** HALTED_AT_<STEP>
- **Why:** <one plain-English line from errors.ts.tmpl humanMessage>
- **What was preserved:** <state of provider key, env vars, deploy>
- **Recovery:** <one line + command>

The rotation did NOT complete. The old credential is still in use.
```

Acceptance criteria:

- Successful rotations write a `data/rotation-receipts/<secret>-<timestamp>.md` file in the report format above.
- Failed rotations write a HALTED-shape receipt.
- The report is also printed to stdout (so the operator sees it at the end of the rotation without opening the file).
- The receipt path is added to .gitignore (it's local-only).
- The Security Brief format matches calibration-examples.md #10 — verify by side-by-side comparison.

```text
/health-implement

SCOPE: At the end of every rotation, write a verification report file matching the DëvSec Security Brief format. Print it to stdout for immediate visibility. Cover both successful (ROTATED/IN_GRACE) and failed (HALTED) shapes.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-agent-doctrine/notes/calibration-examples.md (#10 is the format target)
2. ~/.claude/skills/secrets-rotation/templates/lib/pipeline.ts.tmpl (where the report-writer hook goes — at terminal state)
3. ~/.claude/skills/secrets-rotation/templates/lib/state.ts.tmpl (state shape the report reads from)
4. ~/.claude/skills/secrets-rotation/templates/lib/errors.ts.tmpl (human messages for HALTED shape)

OUTPUT:
- ~/.claude/skills/secrets-rotation/templates/lib/verification-report.ts.tmpl (new — the report writer)
- Updated pipeline.ts.tmpl to call the report writer at terminal state
- Updated .gitignore patterns (data/rotation-receipts/ added to existing gitignore management)
- Sample receipts in campaigns/devsec-rotation-foundation/notes/sample-receipts/ (one successful, one halted) for review

OPEN QUESTIONS:
- File naming: <secret>-<timestamp>.md or <timestamp>-<secret>.md? Lean: <secret>-<timestamp>.md so files for the same secret sort together when listed alphabetically.
- Receipt retention: how long do we keep these files? Lean: indefinitely for v0.2. Cleanup is a v0.3 concern. Document this in SKILL.md.
- Should the receipt include the new key's fingerprint (SHA-256) for the operator to cross-reference at the provider? Lean: yes — small addition, useful for audit.

This is a write-the-file-and-format-it step, not architecturally interesting. The hard part is making the report format match the Security Brief exactly. Use calibration-examples.md #10 as ground truth; if your output drifts from the example's tone or structure, it's wrong.
```

## Step 3.1 — Hardening: docs, catalog, runbook, failure injection

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 3.2

Update the skill's documentation surfaces to reflect everything Phases 1-2 shipped. Add `--fail-at` failure injection mode to the internal test suite.

**Documentation updates:**

- SKILL.md — add sections covering: multi-stack architecture (adapters, detection precedence), HEALTH_CHECK and CANARY phases, SOAK phase (default-on, override semantics), verification report format, the long-running-process limitation and manual mitigation.
- catalog.json — schema updates already in Step 1.3 / Step 2.2; ensure changelog at top of file documents what changed.
- runbook.md.tmpl — operator-facing runbook should show the new pipeline shape, the new state names, the new commands.
- A new doc `docs/STACK_ADAPTERS.md` covering how to add a future adapter. ~1 page. Captures the lessons learned in Phases 1-2 so future contributors don't re-derive them.

**Failure injection mode:**

- Add `--fail-at <step>` flag to `rotate.ts.tmpl`. Accepts pipeline step names (PREFLIGHT, HEALTH_CHECK, ACQUIRE, STAGE_CANARY, VERIFY_CANARY, STAGE_PROD, VERIFY_PROD, SOAK, GRACE, REVOKE).
- When set, the named step throws a deliberate `RotationError("INJECTED_FAILURE_<STEP>")` after running its real logic to wherever the failure could occur.
- Surfaces in the HALTED message as "HALTED at <STEP>: Injected failure for testing".
- Internal test suite uses this to confirm: (a) every HALT state has a clear plain-English message, (b) rollback works from every HALT state, (c) state-file is consistent after every HALT.

Acceptance criteria:

- SKILL.md is updated with all new pipeline phases, adapter architecture, soak semantics, verification report shape, and the long-running-process gap with documented manual mitigation.
- catalog.json has a top-of-file changelog entry documenting v0.2 schema changes.
- runbook.md.tmpl renders correctly with all new states.
- docs/STACK_ADAPTERS.md exists, ~1 page, covers the contract for future adapter contributions.
- `--fail-at <step>` works for every pipeline step.
- A test suite (`tests/failure-injection.test.ts` or equivalent) runs `--fail-at` for every step and asserts the HALT message + rollback behavior.

```text
/health-implement

SCOPE: Documentation hardening + add --fail-at failure injection mode for the internal test suite. Update SKILL.md, runbook.md.tmpl, catalog.json changelog, and write a new STACK_ADAPTERS.md doc.

REQUIRED READING:
1. ~/.claude/skills/secrets-rotation/SKILL.md (substantial updates)
2. ~/.claude/skills/secrets-rotation/templates/runbook.md.tmpl (state-name updates)
3. ~/.claude/skills/secrets-rotation/catalog.json (changelog entry)
4. ~/.claude/skills/secrets-rotation/templates/lib/pipeline.ts.tmpl (failure injection hook)
5. ~/.claude/skills/secrets-rotation/templates/rotate.ts.tmpl (--fail-at flag)
6. All adapter and lib files modified in Phases 1-2 (you're documenting their behavior)

OUTPUT:
- Updated SKILL.md (sections: Stack adapters, HEALTH_CHECK + CANARY phases, SOAK phase, verification report, long-running-process gap)
- Updated runbook.md.tmpl
- Updated catalog.json (changelog entry at top)
- New ~/.claude/skills/secrets-rotation/docs/STACK_ADAPTERS.md (contract for future adapters)
- --fail-at flag in rotate.ts.tmpl + injection hook in pipeline.ts.tmpl
- tests/failure-injection.test.ts (or equivalent) covering every pipeline step

OPEN QUESTIONS:
- SKILL.md is at v0.1; this work brings it to v0.2. Update the version footer. Should we keep v0.1 around as a historical snapshot? Lean: no — git history is the snapshot. Single source of truth, currently maintained.
- The long-running-process limitation in SKILL.md: should it be a prominent "Known limitations" section, or buried in the SOAK phase docs? Lean: prominent. It's the load-bearing thing operators need to know about post-rotation manual checks.
- failure-injection test coverage: every pipeline step is ~10 steps. Is one test per step too much? Lean: no — each step has its own failure modes. The test is one parametrized test with 10 cases, not 10 separate tests.

This step is mostly mechanical (docs + test additions) but high-leverage — the docs are how future contributors understand the architecture. Don't rush.
```

## Step 3.2 — End-to-end demo on both stacks + receipts

Model: Sonnet 4.6 · High / GPT-5.5 · High (mostly observation, lighter prompt edits)
Parallel: YES — with Step 3.1

Execute the rotation pipeline end-to-end on two real targets. Capture receipts showing the full flow.

**Demo 1 — Next.js + Vercel target.**

- Pick a real Christian project that has rotation set up (or set it up if not). Money app or another Next.js project.
- Run `rotate AUTH_SECRET --test` (or operator-picked Class A secret).
- Observe: HEALTH_CHECK passes, PREFLIGHT passes, ACQUIRE generates new value, STAGE_CANARY writes to preview, VERIFY_CANARY passes against preview deployment, STAGE_PROD writes to prod, VERIFY_PROD passes, SOAK runs for 15 min, verification report written.
- Capture: the verification report markdown, screenshot of status board.

**Demo 2 — dëv-security with synthetic token.**

- Scaffold rotation into dëv-security if not already done (the skill's first invocation against a Python CLI project).
- Add a synthetic `DEVSEC_GITHUB_TOKEN` entry to `.env.example` for the demo. Catalog entry: Class A self-generated, smoke command `security-scan --version`.
- Use the operator-picked-first-rotation flow: scaffolding completes, operator picks DEVSEC_GITHUB_TOKEN, rotation runs.
- Observe: full pipeline runs on Python CLI adapter (no preview, dry-run-with-new-value canary, smoke-command verify, 3-invocation soak), report written.
- Capture: the verification report markdown, transcript of the operator-picked-first-rotation prompt.
- Decide: keep the synthetic DEVSEC_GITHUB_TOKEN as a worked example for future contributors, or delete after demo. Lean: keep, document as "demo artifact for the v0.2 campaign — safe to remove if not needed."

**Receipts:**

- `campaigns/devsec-rotation-foundation/receipts/01-demo-vercel.md` — what shipped, what worked, what surprised us.
- `campaigns/devsec-rotation-foundation/receipts/02-demo-python-cli.md` — same shape for the Python CLI demo.
- `campaigns/devsec-rotation-foundation/receipts/03-final-state.md` — overall summary: what the v0.2 skill does, what's known-limited, what's deferred to v0.3, what Campaign 2 will build on top.

Acceptance criteria:

- Both demos run end-to-end with verification reports.
- All three receipts written.
- Any unexpected behavior captured honestly (good and bad).
- If either demo fails to complete, that's a Phase regression — go back and fix before claiming v0.2 done.

```text
/verify

SCOPE: Execute end-to-end demos on Next.js + Vercel and on dëv-security with synthetic Python CLI secret. Capture verification reports and receipts. Honest documentation of what shipped — including any surprises.

REQUIRED READING:
1. ~/.claude/skills/secrets-rotation/SKILL.md (updated by Step 3.1)
2. campaigns/devsec-rotation-foundation/notes/sample-receipts/ (Step 2.3's sample receipts — actual demo receipts should match this shape)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/pyproject.toml (target for the Python CLI demo)

PROCEDURE:
Demo 1 (Next.js + Vercel):
1. Pick a real Next.js + Vercel project (Christian's money app or similar).
2. If rotation isn't set up: invoke /secrets-rotation, scaffold v0.2, use operator-picked-first-rotation.
3. If already set up: run `rotate <CLASS_A_SECRET> --test` against the simplest available.
4. Observe and capture: HEALTH_CHECK, canary stages, SOAK, verification report file.

Demo 2 (dëv-security):
1. cd /Users/christiankatzmann/Dev/Projects/dëv-security
2. Add synthetic DEVSEC_GITHUB_TOKEN to .env.example
3. Invoke /secrets-rotation. Confirm Python CLI adapter is selected.
4. Configure smoke command: `security-scan --version` (or whatever proves the binary loads with the new env).
5. Run the operator-picked-first-rotation flow; pick DEVSEC_GITHUB_TOKEN.
6. Observe and capture: full pipeline, 3-invocation soak with stderr monitoring, verification report.

OUTPUT:
- campaigns/devsec-rotation-foundation/receipts/01-demo-vercel.md
- campaigns/devsec-rotation-foundation/receipts/02-demo-python-cli.md
- campaigns/devsec-rotation-foundation/receipts/03-final-state.md

OPEN QUESTIONS:
- Demo 1: if no Christian Next.js project is conveniently scaffold-ready, fall back to a minimal test fixture. Document the choice.
- Demo 2: should the synthetic DEVSEC_GITHUB_TOKEN be a Class A (self-generated, no provider) or Class B (with a synthetic provider stub)? Lean: Class A — simpler, proves the same things, no fake provider infrastructure.
- If anything in either demo breaks: STOP, do not paper over. The whole point of Phase 3 is honest end-to-end verification. A broken demo means the skill isn't ready, regardless of how green the individual step tests are.

This is the truth-from-the-running-product step. The skill's docs are only as good as the demo proves them. If the demo reveals a gap, that's a gift — fix it, then redemo.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the devsec-rotation-foundation campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-foundation.md
Campaign: campaigns/devsec-rotation-foundation.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the actual state of ~/.claude/skills/secrets-rotation/ (the skill being modified) and campaigns/devsec-rotation-foundation/ (audit notes, sample receipts, demo receipts). Don't trust step receipts — read the actual files.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas. Specifically watch for:

- Did the StackAdapter interface stay clean, or did per-stack hacks creep into the pipeline?
- Does the pipeline actually run HEALTH_CHECK → PREFLIGHT → ACQUIRE → STAGE_CANARY → VERIFY_CANARY → STAGE_PROD → VERIFY_PROD → SOAK → GRACE → REVOKE in that order?
- Is SOAK actually default-on? Does --no-soak require an explicit flag and print a warning?
- Does the verification report match calibration-examples.md #10 in tone and structure? Or did it drift into a different format?
- Does --fail-at work for every pipeline step and produce clear HALT messages?
- Do both demos in Step 3.2 actually pass end-to-end, with receipts in campaigns/devsec-rotation-foundation/receipts/?
- Is the long-running-process limitation documented prominently in SKILL.md with a manual mitigation, or buried?
- Did dëv-security's synthetic DEVSEC_GITHUB_TOKEN get cleaned up or documented as a kept demo artifact?

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
