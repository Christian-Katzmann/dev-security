# Platform Posture Privacy Boundary

Platform posture is a connected, explicit opt-in mode. It is not part of default, quick, full-local, dependency, secret, AI, or IaC scans.

`security-scan --platform-posture` may call the configured SCM platform through legitify. The token is read from the environment (`SCM_TOKEN`, or the local fallback names documented in scanner docs) and is never placed in saved command arguments.

Observatory stores:

- sanitized policy name, title, namespace, severity, and pass/fail/skipped state
- remediation text
- a hashed platform-resource reference for drift comparison
- normalized `platform-posture` findings and change-aware drift alerts

Observatory does not store:

- raw token values
- raw legitify `aux` metadata
- raw SCM entity ids or names in posture snapshots
- full SCM resource URLs in posture snapshots

If legitify, credentials, scopes, or a repo target are absent, the platform posture step is saved as skipped or partial. The local scan still completes, and the UI must show that platform posture was not checked rather than implying a clean result.
