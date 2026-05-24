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
