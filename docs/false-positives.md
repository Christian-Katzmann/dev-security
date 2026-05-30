# False-Positive Handling

The goal is low noise, not zero raw findings.

Use this order:

1. Fix the issue if it is real.
2. Narrow the scanner rule or ignore entry to the exact file/rule.
3. Add a short reason near the suppression.
4. Avoid broad folder-level exclusions unless the folder is generated output.

Never suppress a secret raw finding until the credential has been rotated or proven fake.

## AI-Assisted Case Resolution

The dashboard's AI follow-up panel can generate a bounded prompt for open cases.
Paste the prompt into the local AI agent you already trust, then import the
agent's structured JSON result back into DëvSec.

The import contract is `devsec.case_resolutions.v1`. Imported decisions are
stored in an audit trail before they are applied, so unclear cases and rejected
items are still inspectable later.

AI disposition mapping:

| AI disposition | Stored decision | Open count behavior |
| --- | --- | --- |
| `confirmed_real` | `verified` | Stays open. |
| `false_positive` | `false_positive` | Suppresses the exact case. |
| `docs_example` | `false_positive` | Suppresses the exact case because the risky pattern is intentionally shown as documentation/example evidence, not live project behavior. |
| `accepted_risk` | `accepted_risk` | Suppresses the exact case. |
| `already_fixed` | `fixed` | Reappears if the latest scan still finds the same case. |
| `fixed_by_agent` | `fixed` | Requires verification evidence; reappears if the latest scan still finds the same case. |
| `needs_review` | none | Stays open. |

Secret cases have a stricter rule: an AI result cannot close a secret as a false
positive unless the reason explains why the value is synthetic, test-only,
revoked, or otherwise non-sensitive.

Dependency decisions may also carry a VEX-style status:

- `affected` for confirmed or accepted dependency risk.
- `not_affected` for a dependency false positive.
- `fixed` when the vulnerable dependency state has been removed.
- `under_investigation` while a dependency raw finding is still being checked.

Dependency suppressions must include a human-readable reason. Matching is limited to the same repository, advisory ID, and package name, with ecosystem/package URL checks when available, so a decision for one package does not hide another package that happens to mention the same CVE.

## Local VEX Import and Export

Security Observatory supports a small VEX-compatible subset for dependency decisions.

Export:

```sh
security-scan vex-export --repo my-repo --output my-repo.vex.json
```

Import:

```sh
security-scan vex-import --repo my-repo --input my-repo.vex.json
```

The export is an OpenVEX-like JSON document with `statements`. Each statement contains:

- `vulnerability.name`
- one dependency product, preferably a package URL such as `pkg:npm/lodash@1.0.0`
- `status` as `affected` or `not_affected`
- `impact_statement` as the human-readable reason
- local metadata for repository, case ID, package name, ecosystem, package URL, and update date

Import accepts that OpenVEX-like shape, and also a CycloneDX-like `vulnerabilities` list when it has `id`, `analysis.state`, `analysis.detail`, and `affects.ref`.

Imported status mapping:

- `not_affected` or CycloneDX `false_positive` becomes a false-positive dependency decision.
- `affected` or CycloneDX `exploitable` becomes an accepted-risk dependency decision.
- `fixed` or CycloneDX `resolved` becomes a fixed decision.
- `under_investigation` or CycloneDX `in_triage` becomes a verified, non-suppressing decision.

The importer only uses the repository, advisory ID, package identity, status, and reason. Other VEX fields are ignored and reported as notes instead of crashing the import. Suppressing imports must include a reason, either as `impact_statement`, `analysis.detail`, or a supported local reason property.
