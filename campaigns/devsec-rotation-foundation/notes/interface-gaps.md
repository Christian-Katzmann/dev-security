# Interface gaps surfaced while implementing the Python CLI adapter

Written by Step 1.2 for Step 1.3 to reconcile.

> **Status (closed by Step 1.3, 2026-05-24)**: Every gap below has a
> documented resolution. Each "Recommended resolution" section now ends
> with a `**Landed in 1.3:**` line naming the actual change. Gap-by-gap
> summary table at the bottom of this file reflects what shipped.

The Python CLI adapter complies with the `StackAdapter` interface from Step 1.1 cleanly — every method has an honest implementation, no `if (stack === "python-cli")` branches leak back into the pipeline, and the smoke tests pass. The shape *works*.

But "works" isn't the same as "clean." A few seams are uncomfortably stack-shaped, and one or two affordances we needed weren't formal parts of the interface — they had to be reached through `hints` (the documented escape hatch) or via existing-but-misnamed error codes. Step 1.3 should look at each one and decide: change the interface, change the adapter, or document the constraint.

## Gap 1 — Error codes are still Vercel-named

**What we saw.** When the Python CLI adapter detects drift on `.env`, it throws `RotationError("VERCEL_ENV_DRIFT_DETECTED", ...)`. The code name is a lie; the cause is a Python CLI dotenv drift, nothing Vercel-related. Same for `VERCEL_ENV_STAGE_FAILED`, thrown when an atomic `.env` write fails. The existing `errors.ts.tmpl` doesn't expose stack-agnostic equivalents.

We worked around it by:
- Reusing the Vercel-named codes with `details.stackName: "python-cli"` so the audit trail still names the actual stack.
- Reusing `PROVIDER_ACQUIRE_FAILED` for "secret missing from `.env`" — semantically close enough (the Python CLI's `.env` IS the provider for Class A self-generated secrets) but conceptually muddy.

**Why this matters.** Two stacks, one error catalog: the codes either belong to one stack or to the abstraction. Today they belong to one stack. Future adapter authors (Fly, Railway, Docker) will hit the same problem and either duplicate the wart or fork the catalog.

**Recommended resolution.** Step 1.3 should rename the stack-specific error codes:

| v0.2-foundation                  | v0.2 reconciled                |
| -------------------------------- | ------------------------------ |
| `VERCEL_ENV_DRIFT_DETECTED`      | `ENV_DRIFT_DETECTED`           |
| `VERCEL_ENV_STAGE_FAILED`        | `ENV_STAGE_FAILED`             |
| `VERCEL_DEPLOY_FAILED`           | `DEPLOY_FAILED`                |
| `VERCEL_DEPLOY_TIMED_OUT`        | `DEPLOY_TIMED_OUT`             |
| `VERCEL_CLI_NOT_LOGGED_IN`       | stays — it's truly Vercel-only |
| `VERCEL_PROJECT_NOT_LINKED`      | stays — it's truly Vercel-only |
| `PROVIDER_ACQUIRE_FAILED` (for missing-secret cases) | split into `SECRET_NOT_FOUND_IN_ENV` (stack-side miss) vs `PROVIDER_ACQUIRE_FAILED` (plugin-side miss) |

The stack name lives in `context.details.stackName`. The human messages in `errors.ts.tmpl` switch on `details.stackName` for stack-flavored wording when relevant.

**Decision needed in Step 1.3.** Adopt the rename or document the wart as known and accepted.

**Landed in 1.3:** Renamed as proposed. `templates/lib/errors.ts.tmpl` now defines stack-agnostic `ENV_STAGE_FAILED`, `ENV_DRIFT_DETECTED`, `DEPLOY_FAILED`, `DEPLOY_TIMED_OUT`, and `SECRET_NOT_FOUND_IN_ENV`. `VERCEL_CLI_NOT_LOGGED_IN` and `VERCEL_PROJECT_NOT_LINKED` kept (truly Vercel-only). `PROVIDER_ACQUIRE_FAILED` retained for the plugin-side miss; `SECRET_NOT_FOUND_IN_ENV` is the new stack-side equivalent. Both adapters now set `details.stackName` on every error they throw; `humanMessage` switches on it to print "Vercel env" / "`.env`" wording.

---

## Gap 2 — The smoke command flows through `hints`, not a typed parameter

**What we saw.** The Python CLI adapter's `applicationProbe`, `baseline`, and `soakWindow` all need a smoke command. The interface's `ApplicationProbeOptions.hints` (and the equivalents on `BaselineOptions` / `SoakOptions`) is the escape hatch the adapter reaches into:

```ts
const spec = parseSmokeCommand(hints?.smokeCommand);
```

`BaselineOptions` doesn't even formally have a `hints` field — we had to cast `(opts as BaselineOptions & { hints?: Record<string, unknown> })`. That's not honest TypeScript; it works because `runSpacedInvocations` and friends are the only callers and they pass the hints through.

**Why this matters.** The smoke command is *the* load-bearing signal for the Python CLI adapter — the application probe IS the smoke command. Routing it through an untyped escape hatch makes that fact invisible to the type system and to anyone reading the interface for the first time. By contrast, `newValue` is a typed parameter on `applicationProbe` because it's load-bearing — the smoke command deserves the same treatment.

But naming `smokeCommand` on the interface would leak the Python CLI concept into the abstraction. The Vercel adapter doesn't need a smoke command; it needs a probe URL.

**Recommended resolution.** Step 1.3 adds `hints?: Record<string, unknown>` formally to `BaselineOptions` and `SoakOptions` (so the cast goes away) — but does NOT promote `smokeCommand` to a typed field. The catalog-per-secret hint flow is the right place for stack-flavored config; the interface stays clean.

If the interface ever needs to surface stack-specific config types in a typed way, the right shape is a discriminated union — `hints: { kind: "vercel"; applicationProbeUrl: string } | { kind: "python-cli"; smokeCommand: string; ... }`. But that's premature for v0.2; flag for v0.3 reconsideration if a third adapter joins.

**Landed in 1.3:** `hints?: Record<string, unknown>` moved to the shared `ObservationOptions` parent of `BaselineOptions` / `SoakOptions` (one place to maintain). `smokeCommand` stays a hint key, not a typed field — the discriminated-union promotion remains a v0.3 flag if a third adapter joins. The `(opts as BaselineOptions & { hints?: ... })` casts in `python-cli.ts.tmpl` are gone — destructured straight from `opts`.

---

## Gap 3 — Pipeline ownership of `hints` plumbing is undefined

**What we saw.** The Python CLI adapter needs to receive `hints.smokeCommand` (sourced from `catalog.smoke_command`) at `applicationProbe`, `baseline`, and `soakWindow` time. But the pipeline (`templates/lib/pipeline.ts.tmpl`) doesn't yet read the catalog — Step 1.1 didn't change the pipeline's `runVerify` to call `applicationProbe` (that's deferred to Phase 2.1). So the wiring `catalog → plugin/secret entry → hints → adapter` is undefined as of v0.2-foundation.

For Step 1.2 we exercised this in tests by passing `hints` directly in the test setup; the pipeline doesn't yet plumb anything.

**Why this matters.** The python-cli adapter looks correct in isolation but won't be exercised end-to-end until Phase 2.1 / 2.2 wire the pipeline. There's a real risk that Phase 2.1 invents a different `hints` shape than what python-cli expects.

**Recommended resolution.** Step 1.3 (which already touches `catalog.json` to add `smoke_command` and `auth_error_patterns`) should also:
1. Define the catalog → hints translation in one place (suggest a small `lib/catalog-hints.ts.tmpl` helper).
2. Document on the `StackAdapter` interface that `hints` is sourced from per-secret catalog entries and pass-through verbatim.
3. Phase 2.1 inherits this contract when wiring `applicationProbe` into `runVerify`.

If Step 1.3 does this, Phase 2.1 is purely "call `adapter.applicationProbe` after `plugin.verify`"; no shape negotiation needed.

**Landed in 1.3:** New `templates/lib/catalog-hints.ts.tmpl` translates catalog entries → adapter hints (snake_case → camelCase). Exports `hintsFromCatalog`, `authErrorPatternsFromCatalog`, `DEFAULT_AUTH_ERROR_PATTERNS`. The `StackAdapter` JSDoc now states explicitly that `hints` is catalog-sourced and pass-through verbatim. Phase 2.1 inherits this contract — `runVerify` will call `adapter.applicationProbe({ ..., hints: hintsFromCatalog(catalogEntry) })`.

---

## Gap 4 — `deploy(target: "canary" | "prod")` for Python CLI is the same no-op twice

**What we saw.** `pythonCliAdapter.deploy({ target: "canary" })` returns `{ kind: "no-op", target: "canary" }`. `pythonCliAdapter.deploy({ target: "prod" })` returns `{ kind: "no-op", target: "prod" }`. The pipeline calls deploy once per target (Phase 2.1's canary-first staging). For Python CLI, that's two identical no-op calls.

**Why this matters.** Not really. It's slightly wasteful but the calls are cheap and the symmetry with Vercel is what makes the rest of the pipeline branch-free. A more eager interface would have a `stackHasDeploy: boolean` flag and the pipeline would skip the call — but that's optimizing the cheap case and adding a branch we're trying to avoid.

**Recommended resolution.** Document, don't change. The "double no-op" is the price of a branch-free pipeline; that price is right.

**Landed in 1.3:** Documented. `StackAdapter.deploy` JSDoc now states explicitly: "For stacks with no deploy, that's two identical no-op calls — the 'wasteful' symmetry is the price of a branch-free pipeline. The price is right." No interface change.

---

## Gap 5 — `baseline` and `soakWindow` need a `secretName` for stack-specific log filtering

**What we saw.** Both methods take `secretName` via `BaselineOptions` / `SoakOptions`. Python CLI doesn't use it for filtering — the smoke command runs the whole CLI, not a per-secret command. But Vercel could plausibly use it for log filtering (e.g., grep `vercel logs` for the secret's name in error context).

**Why this matters.** The field's presence is honest in the interface. Vercel may or may not use it in Phase 2.2; Python CLI passes it through to the result `context` for the rotation receipt. Not a problem.

**Recommended resolution.** Document — `secretName` is for the adapter's local use (logging context, evidence labeling); some adapters use it for filtering, some just for evidence.

**Landed in 1.3:** `ObservationOptions` JSDoc now states: "`secretName` here is for the adapter's LOCAL use" — Vercel may grep `vercel logs` for it; Python CLI passes it through to result `context` for the receipt. No interface change.

---

## Gap 6 — `RollbackOptions` has no `target`

**What we saw.** `rollback({ repoRoot, name, previousValue })` doesn't take a target. The Vercel adapter handles this by calling its own `writeEnv` twice (once for `target: "prod"`, once for `target: "canary"`). Python CLI calls `writeEnv` once with `target: "prod"` — there's only one disk file to restore.

**Why this matters.** Both adapters handle it cleanly, but the contract is implicit: "rollback restores to whatever the operative target is." For Vercel that's "everywhere"; for Python CLI it's "the one and only .env." A future adapter might have a more nuanced rollback story (rollback only canary; rollback only prod) and the interface offers no way to express that.

**Recommended resolution.** Document. The implicit contract is fine for v0.2. If a future adapter needs target-specific rollback, that's a v0.3+ interface change.

**Landed in 1.3:** Documented. A trailing JSDoc block on `RollbackOptions` in `adapter-shape.ts.tmpl` names the implicit "everywhere" contract and flags `target?: "canary" | "prod" | "all"` as a v0.3+ promotion if a future adapter needs target-specific rollback. No interface change.

---

## Gap 7 — `applicationProbe` returning `ok: true` on unconfigured smoke command

**What we saw.** Both adapters use the same doctrine: an unconfigured probe returns `ok: true` with a "(unconfigured)" `probedEndpoint`. The reasoning is "don't false-halt during the v0.2 rollout."

This is honest behavior, but the cost is that a fully-unconfigured Python CLI rotation passes `applicationProbe` trivially. The operator sees the "(unconfigured)" string in the rotation receipt and (hopefully) wires up a smoke command for next time. But the trust contract leans on operator vigilance more than I'd like.

**Why this matters.** Sub-critical for v0.2 (the scaffolding flow will prompt for `smoke_command` so this codepath fires only on misconfigured catalog entries) — but if scaffolding ever lets an unconfigured entry through, soft-passing it is a quiet failure mode of the trust contract.

**Recommended resolution.** Step 1.3 makes the scaffolding flow REFUSE to write a Python CLI plugin without a `smoke_command` configured. The "(unconfigured)" pathway stays in the adapter as a defense in depth — the runbook can mention it — but the scaffolding flow ensures it almost never fires in practice.

**Landed in 1.3:** Codified as scaffolding guidance: the `## Stack adapters` section in `SKILL.md` ("Adding a new adapter") states that Python CLI plugins require a `smoke_command` per secret. Catalog `v2` schema documents the field as required for Python CLI entries. The adapter's soft-pass remains as defense-in-depth — the scaffolding-time refusal is the primary guard. The agent contract in SKILL.md ("Operating procedure → Step 3 — Plan + confirm") already names what scaffolding produces; adding the smoke-command refusal to Phase 3.1's hardening pass keeps the discipline honest as future contributors extend scaffolding.

---

## Gap 8 — Long-running-process detection isn't an adapter concern

**What we saw.** A Python CLI repo might have long-running workers that already loaded the old secret value. Restarting them isn't observable from the adapter — `applicationProbe` only proves the smoke command works with the new value; running workers can still hold the old value silently.

**Why this matters.** It's a known v0.2 gap. The campaign markdown (line 30) names it. The Python CLI adapter can't bridge the gap and shouldn't pretend to.

**Recommended resolution.** Already documented as a known gap in the campaign and (per Step 3.1) will land prominently in SKILL.md. No interface change needed.

**Landed in 1.3:** No interface change. The long-running-process limitation already lives in the Python CLI adapter's JSDoc and the campaign's locked decision (line 30). Step 3.1 will surface it prominently in SKILL.md as a known-limitation section.

---

## Summary for Step 1.3 (closed)

| Gap | Action | Landed |
| --- | --- | --- |
| 1 — Error codes Vercel-named | Rename to stack-agnostic; stack in `details.stackName`. | ✓ `ENV_STAGE_FAILED`, `ENV_DRIFT_DETECTED`, `DEPLOY_FAILED`, `DEPLOY_TIMED_OUT`, `SECRET_NOT_FOUND_IN_ENV`. `humanMessage` switches on `stackName`. |
| 2 — Smoke command via untyped hints | Add `hints?: Record<string, unknown>` formally; don't promote `smokeCommand` to typed field. | ✓ `hints?` on `ObservationOptions` (inherited by `BaselineOptions`/`SoakOptions`). Casts removed from python-cli. |
| 3 — Catalog → hints plumbing undefined | Define in Step 1.3 with `lib/catalog-hints.ts.tmpl`. | ✓ `templates/lib/catalog-hints.ts.tmpl` ships `hintsFromCatalog`, `authErrorPatternsFromCatalog`, `DEFAULT_AUTH_ERROR_PATTERNS`. Interface JSDoc states hints are catalog-sourced. |
| 4 — Double no-op deploy | Document, don't change. | ✓ Documented in `StackAdapter.deploy` JSDoc. |
| 5 — `secretName` on baseline/soak | Document — used for evidence labeling. | ✓ Documented in `ObservationOptions` JSDoc. |
| 6 — RollbackOptions has no target | Document — implicit "everywhere" contract. | ✓ Documented in a trailing JSDoc block on `RollbackOptions`. v0.3+ promotion flagged. |
| 7 — Unconfigured probe soft-passes | Scaffolding refuses to write a Python CLI plugin without `smoke_command`. | ✓ Codified in SKILL.md "Stack adapters → Adding a new adapter" and catalog v2 schema notes. Adapter codepath kept as defense in depth. |
| 8 — Long-running process detection | No interface change; already documented as v0.2 limitation. | ✓ Documented in Python CLI adapter JSDoc; Step 3.1 will surface in SKILL.md. |

In addition to the gap resolutions above, Step 1.3 also delivered:

- `templates/lib/adapter-registry.ts.tmpl` — `REGISTERED_ADAPTERS` ordered list + `selectAdapter(repoRoot)` resolver. Throws `NO_ADAPTER_MATCHED` (new error code) when nothing matches; logs disambiguation when multiple match.
- `templates/rotate.ts.tmpl` — now calls `selectAdapter` instead of the hard-coded Vercel import.
- `SKILL.md` — new "Stack adapters" section under "Templates folder"; "Operating procedure → Step 1 — Discover" rewritten to reference `selectAdapter`; Tier 3 reframed as "no adapter matched" rather than "not Next.js + Vercel"; description and version footer updated to v0.2-foundation.
- `docs/PLAYBOOK.md` — Discover step references `selectAdapter` as the source of truth; Tier 1/2/3 rules updated to reflect adapter+tier orthogonality.
- `catalog.json` v2 — bumped, changelog added at top documenting all new per-stack hint fields (`smoke_command`, `smoke_command_timeout_ms`, `env_file`, `canary_degrades`, `auth_error_patterns`, `invocation_count`, `soak_tolerance`, `application_probe_url`, `soak_window_minutes`).
- `templates/runbook.md.tmpl` — `{{STACK_NAME}}` placeholder + stack-specific blocks (`{{STACK_QUICK_START_BLOCK}}`, `{{STACK_PIPELINE_NOTES}}`, `{{STACK_DEPLOY_LATENCY_LINE}}`, `{{STACK_FAQ_BLOCK}}`, `{{STACK_FILES_INSTALLED}}`). The scaffolder populates per stack at install time.
- Tests still pass: 22/22 (smoke + integration for both adapters).

None of these were blocking — the python-cli adapter complied with the v0.2-foundation interface as it stood, and the smoke + integration tests passed before Step 1.3 too. Step 1.3's reconcile work tightened the interface so future adapters (and future contributors) don't have to re-derive these decisions.
