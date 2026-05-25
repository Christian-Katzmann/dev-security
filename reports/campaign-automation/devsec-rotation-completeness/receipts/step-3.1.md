# Implementation Receipt: Step 3.1 - Emergency rotation skill contract

## Target

- Plan: `campaigns/devsec-rotation-completeness.md`
- Batch: Step 3.1 - Skill `--no-grace` / `--emergency` flag with new Tier 5R variant
- Source report item(s): `campaigns/devsec-rotation-followup-notes.md` Emergency rotation section

## Before Health

The rotation skill supported the existing two-step `--force-revoke <id>` path after a Class B rotation had already entered grace, but it did not support a single incident-mode rotation. Operators under suspected compromise still had to run the normal rotate path first, then force-revoke later. The Tier 5R doctrine also only had the normal provider-side confirmation phrase.

## Changes Made

- Added `--emergency` as the single-shot incident mode for Class B provider secrets.
- Wired emergency mode to skip the pre-rotation health-check refusal gate, skip soak, and revoke the old provider key immediately after prod verification.
- Added Class A refusal logic so emergency mode cannot imply provider-side revocation where no provider old key exists.
- Added `emergency_mode` and `cached_caller_risk_acknowledged` to the rotation state record.
- Added the local JSONL emergency audit trail entry: `step: "REVOKE"`, `outcome: "emergency"`.
- Added the `EMERGENCY_ROTATION` receipt shape, with cached-caller risk acknowledgement and no-grace wording.
- Documented the emergency-mode contract in the secrets-rotation skill and the DëvSec Tier 5R doctrine.
- Extended backend/frontend confirmation helpers with the emergency phrase variant and locked it with the drift test.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `npm test` in `~/.claude/skills/secrets-rotation` | PASS | 6 files, 103 tests. New coverage exercises emergency Class B, Class A refusal, missing acknowledgement, and EMERGENCY_ROTATION receipt. |
| `uv run pytest tests/test_rotation_confirmation_phrase.py` | PASS | 2 phrase drift tests passed for normal and emergency Tier 5R variants. |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | PASS | Fast import smoke printed `ok`. |
| `cd dashboard-ui && npm run lint` | PASS | TypeScript typecheck passed. |
| `cd dashboard-ui && npm run build` | PASS | Vite rebuilt the served dashboard bundle. |
| `uv run pytest tests/test_dashboard_rotation_trigger.py tests/test_rotation_confirmation_phrase.py` | PASS | 20 focused dashboard rotation tests passed. |

## After Health

Green. The skill now has a single, auditable incident path for Class B rotations, refuses misleading Class A emergency semantics, emits a distinct emergency trust trail, and keeps the emergency confirmation phrase aligned across doctrine, backend, and frontend.

## Remaining Risk

The dashboard UI and trigger endpoint do not expose emergency mode yet; Step 3.2 owns that surface and should forward `--emergency` only after the cached-caller risk acknowledgement is captured.

## Next Batch

Step 3.2 - Dashboard surface for emergency rotation.
