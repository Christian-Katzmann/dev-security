# Adding New Scanners

Add one scanner at a time.

Every per-scanner fact lives in one place: the `SCANNER_REGISTRY` table at the
bottom of `src/security_observatory/scanners.py`. Each scanner is a single
`ScannerAdapter` entry that co-locates its command line, timeout,
exit-codes-that-mean-findings, normalizer, and (for built-in or bespoke
scanners) its run strategy. Adding a scanner is therefore one co-located edit —
you cannot wire it into the runner but forget its timeout or exit codes, because
they are fields on the same object.

1. Write a `_<name>_command(repo, scan_dir, rules_dir)` builder in
   `scanners.py` (skip this for a built-in scanner that has no external binary).
2. Write the normalizer in `src/security_observatory/normalize.py` that converts
   the scanner's raw JSON into `Finding` rows.
3. Add one `ScannerAdapter(...)` entry to `SCANNER_REGISTRY` in `scanners.py`,
   wiring `command`, `timeout`, `exit_codes_with_findings`, and `normalizer`
   (import the normalizer at the top of `scanners.py`). External binaries leave
   `run=None` to use the generic subprocess path; built-in or bespoke scanners
   pass a `run` callable instead.
4. Add the binary to `install-security-observatory.sh` (external scanners only).
5. Add docs explaining what it covers and when to run it.
6. Run `security-scan --quick` and one targeted scan mode that includes the new
   scanner.

The dispatch helpers — `run_scanner`, `_command`, `_timeout`,
`EXIT_CODES_WITH_FINDINGS`, and `normalize` — all read from `SCANNER_REGISTRY`,
so they pick the new scanner up automatically once its entry exists.

Keep adapters boring. A scanner adapter should not become a second framework.

Built-in local scanners can skip the installer step when they have no external
binary. They carry a `run` callable on their registry entry, should still write
a raw JSON report, normalize raw findings through `normalize.py`, and use the
same case lifecycle as external scanners.

Advanced scanners that need previous scan state, credentials, or local artifacts should stay opt-in. They should report skipped or unavailable evidence as `not_checked`, and they should never turn missing external context into a scan failure.
