# Security policy

## Supported versions

DëvSec is pre-1.0. Only the latest `0.x` release receives security fixes.

## Reporting a vulnerability

Use the **Report a vulnerability** button on this repository's Security tab to open a private GitHub Security Advisory. Please do not open public issues for security bugs.

If GHSA is not available to you, email `christian@katzmann.dk` as a fallback.

I aim to acknowledge reports within 7 days. This is a solo project, and response times reflect that.

## Scope

In scope: the dashboard server, the `security-scan` CLI, the scanner orchestration and normalization layer in this repository.

Out of scope: vulnerabilities in third-party scanner binaries themselves (Trivy, Semgrep, Gitleaks, TruffleHog, OSV-Scanner, Grype, Syft, Checkov, Medusa, legitify). Report those to their upstream projects.
