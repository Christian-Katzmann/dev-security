# Architecture

Security Observatory is a local-first pipeline:

```text
CLI -> scanner adapters -> sanitized raw reports -> normalizer -> SQLite -> dashboard API -> browser UI
```

## Design Choices

- Python orchestration keeps install and debugging simple on macOS.
- SQLite is enough for local scan history and trend data.
- The dashboard source is React/Vite in `dashboard-ui/`; its static build is served by the Python CLI.
- Scanner failures are isolated. A missing or failing scanner marks that scan as partial but does not destroy the whole run.
- Normalization is deliberately small: repo, scanner, severity, category, title, file, line, remediation, timestamp.

## Scanner Adapter Contract

Every scanner is one `ScannerAdapter` entry in the `SCANNER_REGISTRY` table in
`scanners.py` — the single source of truth for per-scanner behavior. Each entry
co-locates:

- command construction (`command`)
- timeout (`timeout`)
- exit-code interpretation (`exit_codes_with_findings`)
- normalizer reference (`normalizer`)
- run strategy (`run`) — `None` for the generic external-binary path; built-in
  and bespoke scanners (e.g. `ai-static`, `install-hooks`, `legitify`) carry
  their own run callable

The dispatch sites — `run_scanner`, `_command`, `_timeout`,
`EXIT_CODES_WITH_FINDINGS`, and `normalize` — all read from this one registry
rather than parallel per-scanner branches. Adding a scanner is one co-located
edit, and a scanner cannot be wired into one facet but missing from another.

The normalizer owns schema conversion into raw findings; the registry entry just
points each scanner at its normalizer so normalization shares the same source.

## Future Support

The architecture has room for these tools without changing the storage model:

- OWASP ZAP
- Nuclei
- Dependency-Track
- Cosign
- Falco

They should be added as scanner adapters with normalized output, not as a new platform layer.
