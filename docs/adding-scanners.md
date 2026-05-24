# Adding New Scanners

Add one scanner at a time.

1. Add the command in `src/security_observatory/scanners.py`.
2. Add schema conversion in `src/security_observatory/normalize.py`.
3. Add the binary to `install-security-observatory.sh`.
4. Add docs explaining what it covers and when to run it.
5. Run `security-scan --quick` and one targeted scan mode that includes the new scanner.

Keep adapters boring. A scanner adapter should not become a second framework.

Built-in local scanners can skip the installer step when they have no external
binary. They should still write a raw JSON report, normalize raw findings through
`normalize.py`, and use the same case lifecycle as external scanners.

Advanced scanners that need previous scan state, credentials, or local artifacts should stay opt-in. They should report skipped or unavailable evidence as `not_checked`, and they should never turn missing external context into a scan failure.
