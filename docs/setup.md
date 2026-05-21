# Setup Guide

## Requirements

- macOS preferred
- Homebrew
- Python 3.11+
- `uv` for Python CLI tools
- Node.js/npm if rebuilding the dashboard design

## Install

```bash
./install-security-observatory.sh
```

The script validates these binaries:

```text
semgrep
gitleaks
trufflehog
trivy
osv-scanner
syft
grype
checkov
medusa
```

## PATH

The installer writes the CLI wrapper to:

```text
~/.local/bin/security-scan
```

If your shell cannot find it, add this to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## First Scan

```bash
security-scan .
security-scan dashboard
```

The dashboard runs on `127.0.0.1:8765` by default.
