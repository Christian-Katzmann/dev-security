# Demo 1 — Next.js + Vercel rotation (mock adapter stand-in)

**Date:** 2026-05-24
**Demo driver:** `campaigns/devsec-rotation-foundation/notes/demo-runs/vercel/run-demo.ts`
**Artifacts:** `campaigns/devsec-rotation-foundation/notes/demo-runs/vercel/artifacts/`

## What ran

A Class B-API rotation (`ANTHROPIC_ADMIN_KEY`, the harder-shape secret in
the catalog — has provider lifecycle, 24h grace, REVOKE step) driven through
the v0.2 pipeline against a Vercel-shaped mock adapter. The mock returns
`{ kind: "vercel", url: "https://moneyapp..." }` from `deploy()` so the
pipeline renders Vercel-flavored log lines and the verification receipt
picks up the Vercel scope statement.

## Why mock and not a real Vercel project

Two independent constraints:

1. **Skill safety rails** explicitly forbid `vercel --prod` without
   per-invocation operator approval (see SKILL.md "Safety rails"). This
   step runs autonomously in `claude --print` — there is no operator in
   the loop to approve a real production deploy.
2. **Real soak windows are 10–60 minutes** (default 15 min, clamped by
   `pipeline.ts` at `SOAK_MIN_MS = 10 * 60_000`). A single-session
   autonomous demo cannot sit on a 10-minute wall-clock sleep AND finish
   in the session's budget.

The campaign anticipated this: *"if no Christian Next.js project is
conveniently scaffold-ready, fall back to a minimal test fixture.
Document the choice."*

## What the demo proves

End-to-end pipeline state machine on Vercel shape, with all v0.2 safety
primitives:

```
HEALTH_CHECK → PREFLIGHT → ACQUIRE
  → STAGE_CANARY → DEPLOY_CANARY → VERIFY_CANARY
  → STAGE_PROD   → DEPLOY_PROD   → VERIFY_PROD
  → SOAK
  → IN_GRACE  ← terminal for Class B-API (REVOKE deferred to cron/next run)
```

Recorded adapter call sequence (11 calls, in order):

```
baseline → preflight → readCurrentValue → ensureNoDrift
→ writeEnv:canary → deploy:canary → applicationProbe:canary
→ writeEnv:prod   → deploy:prod   → applicationProbe:prod
→ soakWindow:900000
```

Two dual-axis verifies (`applicationProbe` for canary AND prod, both
preceded by `plugin.verify`), no per-stack branching in the pipeline —
the abstraction held cleanly.

Verification receipt (verbatim, from `artifacts/ANTHROPIC_ADMIN_KEY-2026-05-24T190748Z.md`):

```markdown
# Rotation verified — `ANTHROPIC_ADMIN_KEY`

- **Status:** IN_GRACE
- **Action: completed · Severity: medium**
- **Provider check:** ✓ provider API returned ok at https://api.anthropic.com/v1/admin/me
- **Application probe:** ✓ vercel probe at https://moneyapp.vercel.app/api/health/auth-secret returned ok
- **Soak test:** ✓ 15 min window, 0 new auth-related errors above baseline (0 matches in 5 min baseline)
- **Old key status:** valid until 2026-05-25T19:07:48.214Z (24h grace; revoke runs automatically)
- **Audit trail:** rotation_id `8760e0ce-aecc-48bd-9809-07118773e78a`, events emitted to `rotation-log.jsonl`
- **New key fingerprint:** `sha256:fp-mock-sk-ant-f…` (cross-reference at the provider console)

Scope of this verification: Vercel preview + production env writes, provider verify, application probe against the production deployment, and a soak window tailing `vercel logs` for auth-error patterns above the pre-rotation baseline. Outside scope: long-running processes that cache credentials in memory may still hold the old value until they next restart; runtime configuration on external services is not observed.
```

Matches `notes/sample-receipts/02-in-grace-class-b-api-vercel.md` shape
exactly. Severity correctly inherited from Class B-API → medium. The
scope statement renders the Vercel-flavored language.

## What the demo does NOT prove

The real Vercel CLI calls inside `templates/adapters/vercel.ts.tmpl`
(`vercel env add`, `vercel`, `vercel --prod`, `vercel logs`, `vercel inspect`)
are *not* exercised by this demo. They are exercised by:

- `tests/adapter-registry.smoke.test.ts` — `detect()` against real
  `vercel.json` / `.vercel/` fixtures.
- The original v0.1 manual operator-supervised rotations (git history of
  earlier campaigns).
- The next operator-supervised real rotation on Christian's money app —
  out of scope for this autonomous session, captured as a follow-up.

## Surprises / honest notes

- The `fatal: not a git repository` line during PREFLIGHT comes from
  `gitleaks-lite` running on the temp-dir fixture (no `.git`). Harmless —
  the scan reports zero blocking findings and the pipeline continues. In
  a real repo this is silent. Worth flagging if the noise turns out to
  bother operators in production rotations.
- Class B-API correctly terminates at `IN_GRACE`, not `ROTATED`. The 24h
  grace window is honored; REVOKE is deferred to the cron schedule (or
  next `npm run rotate` invocation in Tier 2 repos).

## Verdict

Vercel-shape pipeline runs end-to-end with all v0.2 safety primitives
(HEALTH_CHECK gate, canary-first staging, soak with baseline compare,
verification receipt). The fixture stand-in is honest about what it
covers and what it doesn't.
