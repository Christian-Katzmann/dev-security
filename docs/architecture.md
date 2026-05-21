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

Each adapter owns:

- command construction
- timeout
- raw output location
- exit-code interpretation
- sanitizer handoff

The normalizer owns schema conversion into findings.

## Future Support

The architecture has room for these tools without changing the storage model:

- OWASP ZAP
- Nuclei
- Dependency-Track
- Cosign
- Falco

They should be added as scanner adapters with normalized output, not as a new platform layer.
