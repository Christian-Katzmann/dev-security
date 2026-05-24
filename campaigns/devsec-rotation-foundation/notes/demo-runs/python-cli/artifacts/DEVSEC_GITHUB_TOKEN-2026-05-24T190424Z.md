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
