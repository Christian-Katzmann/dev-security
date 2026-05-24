# Phase 0 audit — `secrets-rotation` skill, as of 2026-05-24

Auditor's job: tell Phase 1 the truth about the current shape so the adapter extraction is honest. Skim time ~15 min if you've read SKILL.md once.

## TL;DR

- The pipeline is **Vercel-coupled through direct imports**, not threaded through a half-formed abstraction. That's a clean extraction surface — no false adapter pretending to abstract Vercel today. Most of the work is mechanical: replace `import { ... } from "./vercel-env"` calls with `adapter.<method>(...)`.
- The **per-secret plugin layer (`RotationPlugin`) is already pluggable** for provider-level verify/acquire/revoke and should NOT be reshaped by Phase 1. The missing axis is **per-stack** (env mgmt, deploy, app-level probe, log/output watching).
- `scripts/scan-repo.ts` and `scripts/classify.ts` **DO NOT EXIST**. The skill's `scripts/` folder is empty. "Stack detection" today lives in SKILL.md / `docs/PLAYBOOK.md` as instructions to the agent, not in executable code. Step 1.3 must create this code from scratch, not extend it.
- **No test infrastructure exists in the skill.** No `package.json`, no `tsconfig.json`, no `tests/` folder. Phase 1 must add the harness as well as the tests. Templates today are not type-checked; nothing runs.
- **No existing soak/log-tailing behavior.** Confirmed. `deployAndWait` polls `vercel inspect` for READY; that's the only post-deploy observation. SOAK is fully new.
- **The verify layer is naturally two-stage** (provider check vs application check). Current `plugin.verify` does provider check; the new adapter should add application probe. The original Step 1.1 prompt conflated them — Step 1.1 should keep `plugin.verify` and ADD `adapter.applicationProbe` rather than replace.
- **`rotate.ts.tmpl` is also Vercel-coupled** (calls `vercel env pull` for `readCurrentValueFromEnvOrPull`, imports `stageEnv` for rollback). The Step 1.1 surface area is bigger than the original prompt implied.

## (a) Current Vercel-specific assumptions

In `templates/lib/pipeline.ts.tmpl`:

- L36-47 — direct imports from `./vercel-env`: `ensureNoDrift`, `ensureProjectLinked`, `stageEnv`, `deployAndWait`, `whoami`.
- L245-247 — `runPreflight` calls `whoami(repoRoot)` + `ensureProjectLinked(repoRoot)` unconditionally.
- L273-277 — `runPreflight` calls `ensureNoDrift(repoRoot, ...)` unconditionally.
- L439-482 — `runStage` calls `stageEnv(repoRoot, ...)`. Hard-coded to stage to "Vercel (production + preview + development)".
- L484-518 — `runDeploy` calls `deployAndWait(repoRoot, "preview", ...)`. Hard-coded to Vercel preview deploy; production-deploy is gated behind a TODO.
- L520-580 — `runVerify` calls `plugin.verify(...)` — **already adapter-friendly, no change needed at the verify call site**. Plugin templates internally do `fetch(VERIFY_URL)`, which is Vercel-irrelevant.

In `templates/rotate.ts.tmpl`:

- L40 — `import { stageEnv } from "@/lib/rotation/vercel-env"` (used for rollback push).
- L167-202 — `readCurrentValueFromEnvOrPull` calls `vercel env pull`. Vercel-coupled.
- L302-335 — rollback's "can't find old value" fallback prints Vercel-specific recovery commands (`vercel env rm ...`).

In `templates/lib/vercel-env.ts.tmpl`:

- The whole file is Vercel-specific by design. Most of it lifts cleanly into `templates/adapters/vercel.ts.tmpl`.

**Translation work for Phase 1**: every direct `vercel-env` import call site in `pipeline.ts.tmpl` and `rotate.ts.tmpl` becomes an `adapter.<method>(...)` call. That's the bulk of the refactor.

## (b) Plugin-shape interface today

`templates/lib/plugin-shape.ts.tmpl` defines `RotationPlugin`:

```ts
interface RotationPlugin {
  readonly secretName: string;
  readonly secretClass: "A" | "B-API" | "B-human" | "C";
  readonly provider?: string;
  preflight(context): Promise<PreflightResult>;     // PROVIDER-side preconditions
  acquire(context): Promise<AcquireResult>;          // get the new value
  verify(newValue, context): Promise<VerifyResult>;  // PROVIDER-side probe
  revoke(oldKeyId, context): Promise<RevokeResult>;  // PROVIDER-side deactivate
}
```

This is per-SECRET, per-PROVIDER. It is NOT the per-stack abstraction the campaign is reaching for. Keep this shape; do not collapse adapter and plugin into one.

**HTTP-probe assumption — partially baked in, not in the type.** The interface allows `verify` to do anything. The `class-b-api` and `class-b-human` templates implement it as `fetch(VERIFY_URL)`. The `class-a` template returns an `(class-a stub probe — tune per-secret)` placeholder. So the type system is open; the conventional implementations are HTTP-shaped because providers expose HTTP APIs.

**The natural second verify layer (application-level) is missing**. Whether the deployed app / installed CLI actually picks up the new env var and works is not currently asserted by any code path — DEPLOY just waits for READY, the existing `plugin.verify` hits the PROVIDER not the application. Phase 2.1's canary-verify and Phase 2.2's soak both want an application-level signal. That belongs on the ADAPTER, not the plugin.

Recommendation: keep `plugin.verify` unchanged. Add `adapter.applicationProbe(...)` as a new, optional method. For Vercel: probe a configurable health URL on the deployment. For Python CLI: run the operator-specified smoke command.

## (c) State-machine assumptions

`templates/lib/state.ts.tmpl` is **mostly stack-agnostic**:

- Hard-codes `STATE_PATH = "data/rotation-state.json"`. Fine for Python CLI projects too — `data/` is a normal directory. No reason to make this adapter-pluggable in v0.2.
- Uses `proper-lockfile` for cross-process locking on the state file itself. Stack-agnostic.
- States: `NEVER | PREFLIGHT | ACQUIRED | WAITING_FOR_PASTE | STAGED | DEPLOYED | VERIFIED | IN_GRACE | ROTATED | HALTED | ROLLED_BACK`. The `DEPLOYED` state is Vercel-flavored in name but the concept (we wrote the env, waited for the app to pick it up) generalises. For Python CLI, `DEPLOYED` is essentially `INSTALLED` — same state-machine slot, no-op transition.

Phase 2.1 introduces new states (HEALTH_CHECK_FAILED, CANARY_VERIFY_FAILED, IN_CANARY_VERIFY). Phase 2.2 adds IN_SOAK / SOAK_FAILED. None of these break the existing shape.

**No adapter-driven state file path** is needed. Keep `data/rotation-state.json` for both stacks.

## (d) Existing verify / soak behavior

- **Verify:** `plugin.verify` is called by `runVerify` with `[10_000, 30_000, 90_000]` ms backoff (3 attempts). Test injection point is `verifyBackoffMs` in `RunRotationOptions`. Tight, well-shaped.
- **Soak:** none. There is no log-tailing, no post-VERIFY monitoring, no rate sampling. `runRevoke` re-probes once before deactivating the old key — but that's a single-point check, not a window. The campaign's assumption ("there's NONE") is correct.
- `deployAndWait` (vercel-env.ts.tmpl L242-304) polls `vercel inspect <url>` with 5/10/20/40/80s backoff for READY/ERROR. This is **deploy-readiness polling**, not soak.

SOAK is fully new code. Both adapters must implement `baseline(...)` (pre-rotation, captures error rate) and `soakWindow(...)` (post-rotation, compares against baseline). Plumbing the baseline through pipeline state is required because HEALTH_CHECK (Phase 2.1) captures it and SOAK (Phase 2.2) consumes it.

## (e) Stack detection logic

**There is no code today.** `scripts/scan-repo.ts` and `scripts/classify.ts` are referenced in SKILL.md and in this campaign's Step 1.3, but the `scripts/` folder is **empty**. Detection is described in `docs/PLAYBOOK.md` as agent operating procedure ("read `pwd`, look for `package.json` + `next.config.*` + `vercel.json` or `.vercel/`"). The agent (Claude/Codex) performs detection by reading instructions; nothing automates it.

**What Phase 1.3 actually has to create**: a new file (suggest `scripts/select-adapter.ts` or `templates/lib/adapter-registry.ts`) that holds the registered adapters, iterates `detect()`, returns the matching one. There is nothing to extend.

This isn't a problem, but the Step 1.3 prompt's "extend existing detection logic" framing is misleading. Updated language: "ADD `selectAdapter` logic; this is net-new code."

## (f) Recommended adapter interface signature

Minimal interface that fits Vercel and Python CLI without per-stack `if`-branches in the pipeline:

```ts
interface StackAdapter {
  readonly stackName: string; // "vercel" | "python-cli"

  detect(repoRoot: string): Promise<boolean>;
  preflight(repoRoot: string): Promise<PreflightResult>; // stack-level (Vercel: whoami + project link; CLI: .env writable + smoke cmd on PATH)

  readCurrentValue(repoRoot: string, name: string): Promise<string>; // replaces readCurrentValueFromEnvOrPull
  ensureNoDrift(repoRoot: string, name: string, expectedLastStagedAt?: string): Promise<void>; // Vercel: timestamp compare; CLI: no-op (or git-blame check)

  writeEnv(opts: {
    repoRoot: string;
    name: string;
    value: string;
    target: "canary" | "prod"; // "canary" = Vercel preview / CLI dry-run; "prod" = Vercel production+development / CLI commit-to-.env
  }): Promise<void>;

  deploy(opts: {
    repoRoot: string;
    target: "canary" | "prod";
    secretName: string;
    rotationId: string;
  }): Promise<DeploymentRef>; // Vercel: preview/prod deploy + READY poll; CLI: no-op returning { kind: "no-op" }

  applicationProbe(opts: {
    repoRoot: string;
    secretName: string;
    deployment: DeploymentRef;
    newValue: string;
  }): Promise<ProbeResult>; // Vercel: hit configured probe URL on deployment; CLI: run smoke command with new value in process env. Separate from plugin.verify (which is PROVIDER-side).

  baseline(opts: { // PRE-rotation (Phase 2.1 HEALTH_CHECK)
    repoRoot: string;
    durationMs: number;
    patterns: ReadonlyArray<RegExp>;
  }): Promise<BaselineResult>;

  soakWindow(opts: { // POST-rotation (Phase 2.2 SOAK)
    repoRoot: string;
    durationMs: number;
    patterns: ReadonlyArray<RegExp>;
    baseline: BaselineResult;
  }): Promise<SoakResult>;

  rollback(opts: { // restore prior env after a failure
    repoRoot: string;
    name: string;
    previousValue: string;
  }): Promise<void>;
}
```

**Decision rationale:**

- `target: "canary" | "prod"` is the right abstraction for canary-first staging. Vercel maps "canary" → preview, "prod" → production+development. Python CLI maps "canary" → in-memory dry-run, "prod" → commit to `.env`. Same vocabulary, different semantics, no branch leakage.
- `DeploymentRef` is opaque to the pipeline; Vercel stores `{ kind: "vercel"; url: string }`, Python CLI stores `{ kind: "no-op" }`. The pipeline persists it for diagnostics; only the adapter unpacks it.
- `applicationProbe` is the new application-level verify. Plumbed through `runVerify` AFTER `plugin.verify` succeeds. For CANARY: probes the canary deployment. For PROD: probes the prod deployment.
- `baseline` and `soakWindow` share the same `patterns` regex list. Vercel implementation tails `vercel logs`; Python CLI implementation runs N spaced invocations of the smoke command and watches stdout/stderr.
- `BaselineResult` carries error-rate-per-minute (or just count) plus the observation window. SOAK compares the new window's rate against `baseline + tolerance`.

**Things deliberately NOT on the adapter:**

- No state-file management (stays in `lib/state.ts.tmpl`, shared).
- No `acquire` / `revoke` (stays per-secret on the plugin).
- No CLI/argparsing concerns (stays in `rotate.ts.tmpl`, which now consumes the adapter).
- No `gitleaks-lite` scan (stays shared; both stacks benefit).

**Open question for Step 1.1 to decide:** does the adapter own `audit-emit` (Vercel Tier 1 vs CLI Tier 2)? Probably no — Tier detection can be pipeline-level (does `audit-events.ts` exist?), independent of the stack adapter. A Python CLI repo with audit infra is conceivable; a Vercel repo without it (Tier 2) exists today. Keep audit tiering as its own dimension.

## Open questions answered

> Is there code in the skill today that's already adapter-shaped (good signal: clean extraction) or is Vercel-coupling threaded through the pipeline (bad signal: harder refactor)?

**Mixed but tractable.** The plugin layer is genuinely abstracted (good). The stack layer is direct imports from `vercel-env` — coupled but lift-and-shiftable. There's no false-bottom abstraction to unwind. Refactor is mechanical, not exploratory.

> Does the plugin-shape interface make verify pluggable today, or is the HTTP-probe assumption baked in?

**Pluggable in the type, HTTP in the conventions.** The interface signature has no HTTP assumption. The three plugin templates all implement verify via `fetch`. Class A's stub is a no-op placeholder. The interface accepts any implementation — including a CLI-exec implementation for Python.

> Is there any existing test infrastructure (fixtures, mocks) that would help in Phase 1's reconciliation, or do we need to add it?

**Need to add it. From scratch.** No `package.json`, no `tsconfig.json`, no tests, no fixtures, no mocks. Phase 1.1's acceptance criterion "add a smoke test that scaffolds a fixture..." understates the work — it requires setting up the harness first. Suggest `vitest` (matches the broader project ecosystem), add a `tests/` folder, and accept that Step 1.1 carries one-time infra cost.

> Are there abstractions in the skill that look like adapters but aren't?

**No.** Per-secret plugins (`class-a`, `class-b-api`, `class-b-human`) and per-stack adapters are orthogonal concerns and the skill correctly treats them that way today (secrets are per-secret; stack is... assumed to be Vercel). No misplaced abstraction to refactor.

## What changed in the campaign markdown

Step 1.1, 1.2, and 1.3 each got a "Updated by Step 0.1" note. Changes are calibration, not redirection:

- **Step 1.1**: scope clarified to include `rotate.ts.tmpl` (also Vercel-coupled). Interface sketch updated to use `target: "canary" | "prod"` and add `applicationProbe` (separate from `plugin.verify`). Added test-infra scope warning.
- **Step 1.2**: `verifyProbe` references clarified as `adapter.applicationProbe` (NOT a replacement for `plugin.verify`). Acquire/revoke for the CLI clarified as per-secret plugin concerns, not adapter.
- **Step 1.3**: "extend existing detection logic" replaced with "create new adapter registry / selectAdapter logic — `scripts/scan-repo.ts` and `scripts/classify.ts` referenced in the original prompt do not exist." Required reading list pruned of non-existent files.
