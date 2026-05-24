# Demo 2 — dëv-security Python CLI rotation (real adapter, real binary)

**Date:** 2026-05-24
**Demo driver:** `campaigns/devsec-rotation-foundation/notes/demo-runs/python-cli/run-demo.ts`
**Artifacts:** `campaigns/devsec-rotation-foundation/notes/demo-runs/python-cli/artifacts/`

## What ran

A Class A rotation (`DEVSEC_GITHUB_TOKEN`, synthetic self-generated
token) driven through the v0.2 pipeline against the **real**
`pythonCliAdapter` (not a mock) using the **real** `security-scan
--version` binary at `.venv/bin/security-scan` as the application
probe and soak smoke command.

This is the canonical "eating our own dog food" demo the campaign asked
for: dëv-security as a Python CLI repo rotates its own synthetic token.

The demo runs in TWO parts because the pipeline clamps the soak window
to a minimum of 10 minutes (`SOAK_MIN_MS`). That floor is correct for
production — the campaign locked it as the SRE-cadence baseline. But an
autonomous session can't sit on a 10-minute wall-clock sleep AND finish
in the session's budget, so the demo splits:

### Part A — Full pipeline, --no-soak

Runs the complete pipeline with `skipSoak: true`. Demonstrates every
state transition except SOAK's wall-clock observation:

```
HEALTH_CHECK → PREFLIGHT → ACQUIRE
  → STAGE_CANARY → DEPLOY_CANARY → VERIFY_CANARY
  → STAGE_PROD   → DEPLOY_PROD   → VERIFY_PROD
  → SOAK skipped (--no-soak)
  → ROTATED
```

The HEALTH_CHECK baseline ran for ~60 seconds (the python-cli adapter
clamps `durationMs` to a 60s floor — its documented minimum spacing
constraint). Two real invocations of `security-scan --version` exited
cleanly; baseline reported `errorCount: 0` and the pipeline advanced.

The skip surfaces correctly in three places:

1. **Log line during run:** `▶ SOAK skipped (--no-soak) — rotation will reach ROTATED without verifying the new credential works under real conditions. This defeats the trust contract...`
2. **State file:** `soak_skipped: true` (in `artifacts/rotation-state.json`).
3. **Verification receipt:** `**Soak test:** SKIPPED via --no-soak` and `**Operator overrides:** --no-soak (recorded for audit)`.

### Part B — Direct adapter baseline + soakWindow, compressed

Calls `pythonCliAdapter.baseline()` and `pythonCliAdapter.soakWindow()`
directly with `durationMs: 2_000` and `invocationCount: 2`. The
adapter clamps to its 60s floor (documented behavior) but runs the
SAME code path: real `security-scan` invocations, real stderr/stdout
collection, real pattern matching against the configured regexes.

Result (verbatim from `artifacts/soak-direct-result.json`):

```json
{
  "baseline": { "errorCount": 0, "observedDurationMs": 60148, "samples": [] },
  "soak": {
    "errorCount": 0,
    "anomalyDetected": false,
    "verdict": "Soak clean: 0 matches over 2 invocations vs baseline 0 (tolerance 0)."
  }
}
```

Both invocation pairs (baseline + soak) ran the real `security-scan
--version` binary, exit 0, no auth-pattern hits. The same baseline +
soak code path that runs in production was exercised.

## Verification receipt (Part A)

Verbatim from `artifacts/DEVSEC_GITHUB_TOKEN-2026-05-24T190424Z.md`:

```markdown
# Rotation verified — `DEVSEC_GITHUB_TOKEN`

- **Status:** ROTATED
- **Action: completed · Severity: info**
- **Provider check:** ✓ Class A self-generated (no provider) returned ok at (class-a no-provider stub)
- **Application probe:** ✓ python-cli probe at /Users/christiankatzmann/Dev/Projects/dëv-security/.venv/bin/security-scan --ve… returned ok
- **Soak test:** SKIPPED via --no-soak (rotation reached ROTATED without verifying the new credential under real conditions)
- **Old key status:** replaced (Class A — no grace window; new value live in env, old value not separately tracked at any provider)
- **Audit trail:** rotation_id `8084afdf-a07d-4f68-8547-a6b8d7e0f25b`, events emitted to `rotation-log.jsonl`
- **New key fingerprint:** `sha256:fp-demo-syntheti…` (cross-reference at the provider console)
- **Operator overrides:** --no-soak (recorded for audit)

Scope of this verification: atomic `.env` replace, three spaced smoke-command invocations spanning the soak window, stdout/stderr scanned for auth-error patterns against the pre-rotation baseline. Outside scope: any subprocess that read the old `.env` value into its own environment before rotation still holds the old value; long-running services started before rotation must be restarted to pick up the new value.
```

Status line, severity (Class A → info), provider check, application
probe, audit trail, fingerprint, scope, operator-overrides — all
render correctly.

## .env atomic-replace + backup

`artifacts/.env` (post-rotation) carries the new value:

```
DEVSEC_GITHUB_TOKEN="synthetic-post-rotation-token-0002-XYZ"
DEVSEC_LOG_LEVEL=info
```

`artifacts/.env.backup-2026-05-24T19-04-24-304Z` carries the pre-rotation
value. The non-rotation key `DEVSEC_LOG_LEVEL` was preserved across the
atomic-replace — the python-cli adapter's `writeEnv("prod")` is
surgical, not a full-file overwrite.

## Surprises / honest notes

1. **Receipt scope statement is stale when `--no-soak` is set.** The
   `Scope of this verification:` paragraph at the bottom of the receipt
   still reads *"three spaced smoke-command invocations spanning the soak
   window, stdout/stderr scanned for auth-error patterns against the
   pre-rotation baseline."* But those invocations did NOT happen — soak
   was skipped. The `**Soak test:**` line correctly says "SKIPPED via
   --no-soak", but the scope paragraph contradicts that. **Receipt-template
   gap.** Worth fixing in a follow-up: the scope paragraph should pivot
   on `soak_skipped` and render an honest version when soak didn't run.

2. **The HEALTH_CHECK baseline wall-clock is ~60s even with
   `healthCheckDurationMs: 1500`.** The python-cli adapter clamps to a
   60s floor regardless of the pipeline's requested duration. This is
   *documented* (see `templates/adapters/python-cli.ts.tmpl:53-56` and
   `clampDurationMs()` at line 413-416) but worth surfacing: a real
   "rotate AUTH_SECRET --test" against a Python CLI repo will spend at
   least 60s in HEALTH_CHECK before doing anything else. Not a bug —
   just a thing operators should know.

3. **`gitleaks-lite` warning during PREFLIGHT** about the current value
   appearing in `.env:3` (current-value, untracked). Correct behavior:
   `.env` is untracked, the warning is informational, and the pipeline
   continues. Worth noting that the PREFLIGHT log lines a non-fluent
   operator might find scary — *"⚠️  pattern-match in .../.env:3
   (current-value, untracked)"* — but it's the expected scan output.

4. **No drift in fingerprint format.** `fp-demo-syntheti…` is the
   plugin-supplied fingerprint (truncated to 16 chars in display). The
   receipt-format uses `sha256:` as the prefix; the real Class A plugin
   uses a real SHA-256. The fixture uses a string for reproducibility.
   This drift is intentional — the demo's `fp-demo-` prefix makes it
   obvious that the value is synthetic.

5. **The pipeline ran in 60.5 seconds** wall-clock, dominated by the
   HEALTH_CHECK 60s clamp. Everything else (ACQUIRE through ROTATED)
   completed in <300ms. The real cost of a Python CLI rotation is the
   baseline + soak windows; the pipeline orchestration is fast.

## Verdict

The dëv-security Python CLI rotation works end-to-end against the
**real** binary. Three real subprocess invocations of `security-scan
--version` happened across the run (one during VERIFY_CANARY, one
during VERIFY_PROD, plus the two-pair baseline + soak in Part B). The
verification receipt is generated correctly. The `.env` is atomically
replaced. The backup is created. One receipt-template gap surfaced
(scope statement on `--no-soak`); everything else lands.

The DEVSEC_GITHUB_TOKEN entry has been added to `.env.example` as a
documented demo artifact, per campaign decision.
