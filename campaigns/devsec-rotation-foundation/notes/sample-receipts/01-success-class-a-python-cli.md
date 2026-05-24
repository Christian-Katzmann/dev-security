# Rotation verified — `DEVSEC_GITHUB_TOKEN`

- **Status:** ROTATED
- **Action: completed · Severity: info**
- **Provider check:** ✓ Class A self-generated (no provider) (no remote provider to verify — value is self-generated)
- **Application probe:** ✓ python-cli probe at security-scan --version (PATH: /Users/c/Dev/Projects/dëv-security/.venv/bin/sec… returned ok
- **Soak test:** ✓ 15 min window, 0 new auth-related errors above baseline (0 matches in 5 min baseline)
- **Old key status:** replaced (Class A — no grace window; new value live in env, old value not separately tracked at any provider)
- **Audit trail:** rotation_id `01HXAB2C-7E1F-4D9A-8B33-9E4C2F11D5A0`, events emitted to `rotation-log.jsonl`
- **New key fingerprint:** `sha256:3c5b7d9e0f2a4c6e…` (cross-reference at the provider console)

Scope of this verification: atomic `.env` replace, three spaced smoke-command invocations spanning the soak window, stdout/stderr scanned for auth-error patterns against the pre-rotation baseline. Outside scope: any subprocess that read the old `.env` value into its own environment before rotation still holds the old value; long-running services started before rotation must be restarted to pick up the new value.
