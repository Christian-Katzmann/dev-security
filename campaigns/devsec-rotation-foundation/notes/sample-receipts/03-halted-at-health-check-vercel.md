# Rotation HALTED — `ANTHROPIC_ADMIN_KEY` at HEALTH_CHECK

- **Status:** HEALTH_CHECK_FAILED
- **Why:** Your app is showing 3-error pattern matches in the pre-rotation baseline window (300s observed). Rotating ANTHROPIC_ADMIN_KEY now will not help and may make diagnosis harder. Investigate the auth errors first. If you've already decided to rotate anyway (e.g. incident response), re-run with `--skip-health-check`.
- **What was preserved:** nothing changed — env still on the OLD value at vercel; no provider call was made
- **Recovery:** Investigate the pre-rotation auth errors first; if you must rotate anyway, re-run with `npm run rotate ANTHROPIC_ADMIN_KEY --skip-health-check`
- **Audit trail:** rotation_id `01HXCD6E-A1F2-3B4C-5D66-8E7F4A33F7C2`, events emitted to `audit-events.ts`

The rotation did NOT complete. The old credential is still in use.
