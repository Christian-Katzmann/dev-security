# Scanner Explanations

## Semgrep

General static analysis for code security patterns. This project uses local rules by default to avoid relying on a remote registry.

## Install Hook Classifier

Built-in local scanner for install-time supply-chain surfaces. It reads
`package.json` install scripts, Python build hooks, and `setup.py` install
commands. High and critical records become cases; medium and info records stay
in the raw report so every install hook is still visible.

See `docs/install-hooks.md`.

## Workflow Surface Audit

Built-in local scanner for GitHub Actions workflow risk. It flags unpinned
actions, fetch-and-exec shell blocks, unsafe secret handling, risky
`pull_request_target` checkout patterns, untrusted event text in shell, and
broad workflow token permissions.

See `docs/workflow-audit.md`.

## Gitleaks

Fast secret detection for git repositories and working trees. Reports are generated with redaction.

## TruffleHog

Second-opinion secret scanning with deeper detectors.

## Trivy

Filesystem, dependency, container, IaC, and secret scanning.

## OSV-Scanner

Open-source dependency vulnerability detection using OSV advisories.

Dependency raw findings can be enriched after normalization. The helper layer extracts CVE, GHSA, and OSV-style advisory IDs, package names, and fixed-version text from scanner output — all from local scanner data, with no network calls.

CISA KEV and EPSS lookups are designed but **not yet wired**. The helper carries opt-in `check_cisa_kev` / `check_epss` parameters (both default `False`), but no scan path or CLI flag enables them today, so the default scan never reaches out for KEV/EPSS data. When they are wired, they will follow the same explicit `--trust`-style opt-in and named egress disclosure as OpenSSF trust enrichment, fail closed as "not checked" when unavailable, and never block a scan or be treated as proof that a vulnerability is not exploited.

## Optional OpenSSF Trust Enrichment

Dependency trust enrichment is opt-in. Default scans stay offline-capable and do not call OpenSSF services.

Use:

```bash
security-scan --deps --trust
```

This runs SBOM generation, then attaches cache-backed trust records to SBOM components when a GitHub source repository can be resolved with strong confidence. Observatory currently treats these as separate facts, not raw findings:

- source repository
- source-repo resolution confidence and reason
- OpenSSF Scorecard score
- OpenSSF Criticality score
- checked-at timestamp
- freshness label
- status

Cache files live under:

```text
~/.security-observatory/cache/dependency-trust/
  scorecard/
  criticality/
```

Use cached trust data without network access:

```bash
security-scan --deps --trust-cache-only
```

Freshness is explicit:

- `fresh` means the cache is inside the local TTL.
- `stale` means Observatory reused older cached data because a refresh was not requested or failed.
- `unavailable` means the source was known, but no usable Scorecard or Criticality data was available.
- `unknown` means the package metadata did not identify a reliable GitHub source repository.

Source repository resolution is intentionally conservative. Direct GitHub package URLs such as `pkg:github/owner/repo@version`, Go module package URLs under `github.com/owner/repo`, and explicit GitHub repository metadata are strong matches. Registry package names such as npm or PyPI names are not guessed. Unknown source repositories are recorded as `unknown_source`; this is not treated as bad hygiene.

## Syft

SBOM generation.

Security Observatory saves Syft package inventory into local SQLite as scan history. Each saved component is tied to the scan id and repo name, so later dashboard views can compare one repo's latest SBOM only against that same repo's previous scan.

The dashboard dependency history reports:

- added packages
- removed packages
- upgrades
- downgrades
- other version changes where direction cannot be safely inferred
- license metadata changes, including license-only changes where the package version stayed the same

If a scan has no saved SBOM, the dashboard treats that as missing inventory instead of assuming every previous package was removed. If a repo only has one SBOM-backed scan, the dashboard explains that there is no previous scan to compare yet.

## Grype

Vulnerability scanning from an SBOM or repository filesystem.

## Checkov

Terraform, Kubernetes, and cloud/IaC policy scanning.

## Optional Platform Posture With legitify

Platform posture is opt-in because it leaves the purely local boundary. Default, quick, IaC, dependency, AI, secret, and full local scans do not require legitify or an SCM token.

Use:

```bash
SCM_TOKEN=<github-or-gitlab-token> security-scan --platform-posture
```

Observatory runs legitify with JSON output and limits the check to one repository target. The target is resolved from `SECURITY_OBSERVATORY_PLATFORM_REPO` when set, otherwise from the repo's `origin` remote. To use GitLab, set:

```bash
SECURITY_OBSERVATORY_PLATFORM_SCM=gitlab
```

By default Observatory asks legitify for `repository,actions` namespaces. Override this only when you intentionally want a broader connected scan:

```bash
SECURITY_OBSERVATORY_PLATFORM_NAMESPACES=repository,actions,organization
```

Token expectations follow legitify's own model:

- GitHub full analysis: `admin:org`, `read:enterprise`, `admin:org_hook`, `read:org`, `repo`, and `read:repo_hook`.
- GitHub repository-only analysis can be narrower, but insufficient scopes may cause skipped or partial policies.
- GitLab full analysis: `read_api`, `read_user`, `read_repository`, and `read_registry`.

Privacy boundary:

- Tokens are passed through the environment, never through saved command arguments.
- Raw token values are not stored in legitify scanner reports or posture snapshots.
- Posture snapshots keep policy name, title, namespace, severity, pass/fail/skipped status, remediation text, and a hashed platform-resource reference.
- Observatory does not store raw legitify `aux` metadata such as entity ids, entity names, secret lists, or full SCM resource URLs in the posture snapshot.
- Missing legitify, missing credentials, or missing repo target records a skipped platform scan and keeps the rest of the local scan usable.

Platform posture raw findings use the `platform-posture` category. When a previous platform snapshot exists, Observatory compares the sanitized policy states and raises change-aware alerts for important regressions such as default branch protection becoming disabled or workflow token permissions widening.

## Medusa

Local AI-agent security scanning for MCP, prompt injection, AI editor configs, and repo poisoning patterns. The observatory also includes a small built-in deterministic scanner for AI-facing config files.

## Optional Behavioral Drift With malcontent

Behavioral drift is opt-in. Default scans do not run malcontent and do not fetch package artifacts.

Use:

```bash
security-scan --behavioral-drift
```

This mode uses the saved SBOM history to select changed dependency versions only. Added packages, removed packages, unchanged packages, and license-only changes are not sent to malcontent. The check is bounded:

- at most 5 changed package versions per scan
- each old or new artifact must be 50 MB or smaller
- local artifact traversal is capped at 20,000 files
- missing old versions or missing local artifacts are recorded as `not_checked`

Artifact fetching is intentionally not automatic. Put artifacts in the local cache when you want this advanced check to run:

```text
~/.security-observatory/cache/behavioral-artifacts/
  npm/
    package-name/
      1.0.0/artifact
      1.1.0/artifact
```

When both old and new artifacts are available, Observatory runs malcontent diff and stores behavioral-drift raw findings with:

- old version
- new version
- behavior category
- before behavior
- after behavior
- evidence summary

Behavioral drift can show that a package artifact gained behavior such as network access, process execution, file writes, persistence, obfuscation, or credential access. It cannot prove compromise by itself. Some legitimate releases add new behavior, and scanner rules can be noisy. Treat these raw findings as a reason to inspect the upgrade, source provenance, maintainer history, and release notes before trusting the new version.
