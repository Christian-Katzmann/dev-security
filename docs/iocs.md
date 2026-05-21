# IOC Packs

IOC Watch matches named supply-chain campaign indicators against local evidence that Security Observatory already stores. It does not call package registries, advisory APIs, or network services during default use.

## Pack Format

An IOC pack is a small YAML file:

```yaml
id: 2026-05-12-supply-chain-worm
source: Security Observatory incident log
published_at: 2026-05-12
advisory_url: docs/incidents/2026-05-12-npm-pypi-supply-chain-worm-ioc-scan.md
confidence: high
indicators:
  - ecosystem: npm
    name: "@opensearch-project/opensearch"
    versions: ["3.5.3", "3.6.2", "3.7.0", "3.8.0"]
  - ecosystem: pypi
    name: mistralai
    versions: ["2.4.6"]
  - ecosystem: npm
    namespace_prefix: "@tanstack/"
    confidence: low
  - ecosystem: other
    domain: git-tanstack.com
    confidence: medium
```

Top-level fields:

- `id`: stable pack id used for idempotent imports.
- `source`: human-readable source name.
- `published_at`: advisory or pack publication date.
- `advisory_url`: local or web link for review context.
- `confidence`: default confidence for indicators in the pack.
- `indicators`: package pins, namespace watches, and domain watches.

Indicator fields:

- `ecosystem`: `npm`, `pypi`, or `other`.
- `name`: exact package name.
- `versions`: exact versions to match for named packages.
- `namespace_prefix`: namespace watch such as `@tanstack/`.
- `domain`: domain watch such as `git-tanstack.com`.
- `confidence`: optional override for this indicator.

## Matching Rules

Exact package matches are critical findings when the saved SBOM has the same ecosystem, package name, and exact version.

Namespace-prefix watches are high-severity findings. They are intentionally softer because a namespace match is a signal to inspect, not proof that a named bad version is installed.

Domain watches check local strings from package scripts, lockfile registry references, and GitHub Actions `run:` blocks. They do not run scanners or call the network.

## Usage

Use the starter pack against the current repo:

```bash
security-scan ioc .
```

Use a custom pack or directory of packs:

```bash
security-scan ioc . --feed ./iocs/current-campaign.yaml
security-scan ioc --all-repos --dev-root ~/Dev/Projects --feed ./iocs/
```

`--json` prints the same match shape used by the Dependencies dashboard panel. `--fail-on` controls the exit threshold; the IOC verb defaults to failing on critical matches.
