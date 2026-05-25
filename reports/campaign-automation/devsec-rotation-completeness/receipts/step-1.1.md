# Implementation Receipt: Step 1.1 — Fix Tier 1 audit emit on Next.js stacks

## Target

- Plan: `/Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rotation-completeness.md`
- Batch: Step 1.1 — Fix Tier 1 audit-emit broken on Next.js stacks (RSC import boundary)
- Source report item(s): `campaigns/devsec-rotation-followup-notes.md` Tier 1 audit-emit evidence
- Run time: 2026-05-25T15:45:15Z

## Before Health

Red / High confidence. The scaffolded Tier 1 rotation shim imported the target app's `emitAuditEvent` directly from the rotation process. On Next.js stacks where `emitAuditEvent` reaches `server-only`, rotations logged `[rotation:audit-emit-failed]` and produced zero `audit.secret_rotation` rows.

## Changes Made

- Replaced the secrets-rotation `templates/lib/audit-emit.ts.tmpl` Tier 1 path with a server-condition bridge that runs `src/scripts/rotation-audit-emit.ts` under `NODE_OPTIONS=--conditions=react-server`.
- Added `templates/scripts/rotation-audit-emit.ts.tmpl`, which reads one audit payload from stdin and calls the target repo's canonical `emitAuditEvent`.
- Added explicit local degradation logging to `data/rotation-log.jsonl` for `AUDIT_BRIDGE_MISSING`, `AUDIT_BRIDGE_FAILED`, and `RSC_IMPORT_FAILED` instead of silently dropping Tier 1 audit events.
- Updated secrets-rotation doctrine and PLAYBOOK upgrade notes so Tier 1 installs and upgrades include the new bridge file.
- Applied the upgraded scaffold to `/Users/christiankatzmann/Dev/Projects/beskæftigelse.dk/src/lib/rotation/audit-emit.ts` and added `/Users/christiankatzmann/Dev/Projects/beskæftigelse.dk/src/scripts/rotation-audit-emit.ts`.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `npm test` in `/Users/christiankatzmann/Dev/skills/secrets-rotation` | Pass | 6 test files, 97 tests. New tests cover bridge success, RSC failure logging, missing bridge logging, and Tier 2 no-op. |
| `npm run typecheck` in `/Users/christiankatzmann/Dev/Projects/beskæftigelse.dk` | Pass | Confirms the upgraded scaffold and new bridge typecheck in the target Next.js app. |

## After Health

Green/Yellow / High confidence. Tier 1 scaffolded rotations no longer import the Next.js audit module directly from the rotation process, and failure paths are explicit in the local rotation log. Live audit_log insertion was not exercised because a real besk rotation can touch production-like secrets/provider state; campaign Phase 5 owns that live verification.

## Remaining Risk

The bridge depends on the target repo having `tsx` available, matching the existing `npm run rotate` contract. If a future Tier 1 repo uses a different runner, the install plan must mirror that repo's script convention.

## Next Batch

Step 1.2 — status-vs-history consistency check, job state persistence, and confirmation phrase drift test.
