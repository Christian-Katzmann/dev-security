# Security Packs

Security Packs are curated capability bundles. They explain which Tool Catalog entries belong together for a security job, what each tool adds, and which scan profile to run after the needed tools are available.

MVP rule: packs are not runnable execution modes. DëvSec still runs scan profiles such as `--quick`, `--secrets`, `--deps`, and `--ai`; packs only recommend, explain, and prepare capability.

External Surface is display-only in the MVP. It has no domain input, no probing, no active recon, no install action, no run action, and no agent-triggered external scan.

## Human Context Contract

- User likely arrives feeling: curious but cautious about installing or running security tools.
- Prior context they may carry: scanner names are technical, missing tools can look like failed protection, and "pack" can sound like a one-click action.
- What they fear getting wrong: installing too much, sending code or targets outside the machine, or trusting coverage that is only planned.
- What getting it wrong costs: false confidence, unwanted network activity, local machine churn, or accidental disclosure of repo or credential context.
- Their likely bandwidth: low to medium; the pack has to explain the job before the tool list.
- What they need to trust: local-first defaults, clear network and credential labels, honest missing-tool states, and no hidden execution.
- Where they need agency: before installs, network-backed checks, credential-backed checks, target entry, or uninstall.
- What the product must not do: imply that a pack can run by itself, imply External Surface is active, or claim ownership of tools DëvSec only detected.

## Pack Availability

| Pack | MVP state | Visibility | Why |
| --- | --- | --- | --- |
| Starter Pack | Real MVP pack | Default | Low-friction baseline for first scans. |
| Secrets Pack | Real MVP pack | Default | Clear, high-value job with local secret scanners. |
| Dependencies Pack | Real MVP pack | Default | Core SBOM and dependency advisory workflow. |
| AI Agent Pack | Real MVP pack | Default | Matches DëvSec's agent/MCP focus and has a safe built-in baseline. |
| IaC Pack | Coming Soon | Default Coming Soon | Useful roadmap item, but pack UX needs clearer scope before promotion. |
| External Surface Pack | Coming Soon | Default Coming Soon, display-only | Users expect this category, but MVP must prevent target entry or probing. |
| Platform Posture Pack | Coming Soon | Advanced | Requires SCM credentials and network access. |
| Advanced Dependency Pack | Coming Soon | Advanced | Requires previous SBOMs and local package artifacts. |

## Recommended Scan Profiles

| Pack | Primary profile | Secondary profiles | Notes |
| --- | --- | --- | --- |
| Starter Pack | `security-scan --quick` | `security-scan .`, `security-scan --code`, `security-scan --secrets` | Use for a fast first read. OSV may need network access; missing scanners become evidence gaps, not pack failures. |
| Secrets Pack | `security-scan --secrets` | `security-scan --quick`, `security-scan --secrets --deps` | Secret checks stay local by default; Trivy may also contribute secret evidence when installed. |
| Dependencies Pack | `security-scan --deps` | `security-scan --deps --trust-cache-only`, `security-scan --deps --trust` | SBOM is local; vulnerability and trust enrichment can require network or cache disclosures. |
| AI Agent Pack | `security-scan --ai` | `security-scan --quick`, `security-scan --full` | Built-in AI static checks are the safe baseline; Medusa deepens local AI/MCP coverage when installed. |

## Managed Install Proof Target

The first managed install proof is `gitleaks`, pinned to Gitleaks `v8.30.1` release artifacts for the bounded managed copy.

This locks the Phase 2 implementation target before install/uninstall code begins. Gitleaks is in the Starter and Secrets packs, already has scanner normalization and bounded runtime behavior, runs locally without credentials, and gives a clear user benefit without needing Docker or a global package-manager install.

Pack install controls must still stay narrow:

- Show managed install preview for `gitleaks` only.
- Leave broad pack install and uninstall disabled.
- Leave Docker-backed installs disabled.
- Treat Homebrew, `uv`, `pipx`, and other PATH-discovered copies as detected user-owned tools.
- Offer uninstall only for the DëvSec-owned `gitleaks` copy recorded under the managed tools directory.
- Never remove or relink a detected system `gitleaks`.

## MVP Packs

### Starter Pack

Purpose: give a cautious user the fastest honest baseline across code, secrets, workflow, install-hook, and AI-agent risk without making them understand every scanner first.

Plain-English benefit: "Start here to see obvious security problems and setup gaps before choosing a deeper pack."

Expected runtime: usually seconds to a few minutes on small repos. External scanner timeouts bound the worst case: Semgrep and OSV-Scanner cap at 10 minutes each, Gitleaks at 5 minutes.

Recommended first action: run `security-scan --quick`.

Included tools:

| Tool | Role | Policy-derived safety labels | Install posture |
| --- | --- | --- | --- |
| Built-in AI static checks | Included | Local, No credentials, Read-only, Agent Lab allowed | Built in |
| Install hook classifier | Included | Local, No credentials, Read-only, Agent Lab allowed | Built in |
| Workflow surface audit | Included | Local, No credentials, Read-only, Agent Lab allowed | Built in |
| Semgrep | Included | Local, No credentials, Read-only, Agent Lab allowed | Missing or detected locally |
| Gitleaks | Included | Local, No credentials, Read-only, Agent Lab allowed | Missing or detected locally |
| IOC Watch | Optional | Local, No credentials, Read-only, Agent Lab allowed | Built in; needs prior local evidence |
| OSV-Scanner | Optional | Network required, No credentials, Read-only, Approval required, Agent Lab blocked | Missing or detected locally |

Design consequence: the pack should lead with "fast baseline" and show OSV as a disclosed network-backed helper, not as a silent default promise.

### Secrets Pack

Purpose: focus on exposed API keys, tokens, passwords, private keys, and secret-like evidence with multiple scanners where available.

Plain-English benefit: "Find secrets that should be rotated before they become an incident."

Expected runtime: usually a few minutes. Gitleaks caps at 5 minutes, TruffleHog caps at 10 minutes, and Trivy caps at 15 minutes when present.

Recommended first action: run `security-scan --secrets`.

Included tools:

| Tool | Role | Policy-derived safety labels | Install posture |
| --- | --- | --- | --- |
| Gitleaks | Included | Local, No credentials, Read-only, Agent Lab allowed | Missing or detected locally |
| TruffleHog | Included | Local, No credentials, Read-only, Agent Lab allowed | Missing or detected locally |
| Trivy | Optional helper | Optional network, No credentials, Read-only, Agent Lab allowed | Missing or detected locally |

Design consequence: missing secret tools should read as "install needed for deeper evidence," not as "your repo is safe."

### Dependencies Pack

Purpose: combine SBOM inventory, dependency vulnerability checks, advisory evidence, and named-campaign IOC context.

Plain-English benefit: "Understand what packages are present, which ones are vulnerable, and whether a known supply-chain campaign touches this repo."

Expected runtime: commonly a few minutes after tools are installed. Syft caps at 5 minutes, Grype and OSV-Scanner cap at 10 minutes, and Trivy caps at 15 minutes.

Recommended first action: run `security-scan --deps`.

Included tools:

| Tool | Role | Policy-derived safety labels | Install posture |
| --- | --- | --- | --- |
| Syft | Included | Local, No credentials, Read-only, Agent Lab allowed | Missing or detected locally |
| Grype | Included | Optional network, No credentials, Read-only, Agent Lab allowed | Missing or detected locally |
| Trivy | Included | Optional network, No credentials, Read-only, Agent Lab allowed | Missing or detected locally |
| OSV-Scanner | Included | Network required, No credentials, Read-only, Approval required, Agent Lab blocked | Missing or detected locally |
| IOC Watch | Optional | Local, No credentials, Read-only, Agent Lab allowed | Built in; needs prior local evidence |
| Install hook classifier | Optional | Local, No credentials, Read-only, Agent Lab allowed | Built in |

Design consequence: the pack page should separate local inventory from network-backed advisory lookups so users can choose cache-only or online trust enrichment deliberately.

### AI Agent Pack

Purpose: check agent-readable files, MCP configuration, prompt-injection surfaces, AI editor setup, and repo-poisoning patterns.

Plain-English benefit: "See whether this repo gives AI tools risky instructions or unsafe local capabilities."

Expected runtime: built-in checks usually finish in seconds. Medusa is bounded to 3 minutes in quick mode when installed.

Recommended first action: run `security-scan --ai`.

Included tools:

| Tool | Role | Policy-derived safety labels | Install posture |
| --- | --- | --- | --- |
| Built-in AI static checks | Included | Local, No credentials, Read-only, Agent Lab allowed | Built in |
| Medusa | Included deep check | Local, No credentials, Read-only, Agent Lab allowed | Missing or detected locally |

Design consequence: the pack should present the built-in scanner as real baseline coverage and Medusa as deeper local coverage, not as a required prerequisite.

## Coming Soon Packs

Coming Soon packs educate and set expectations. They must not show run, install, uninstall, target-input, or Agent Lab actions until later campaigns add enforceable backend controls.

### IaC Pack

Purpose: future bundle for Terraform, Kubernetes, GitHub Actions, and configuration-policy checks.

Likely tools: Checkov, Trivy misconfiguration checks, and Workflow surface audit.

Policy-derived safety labels: Local, No credentials, Read-only for Checkov and workflow audit; Trivy keeps Optional network when database refresh is involved. Agent Lab remains blocked for Checkov in current catalog policy.

Expected runtime: to be proven later; current individual scanners cap at 10 minutes for Checkov and 15 minutes for Trivy.

Visibility: default Coming Soon. This belongs in normal catalog browsing, but with clear "not a runnable pack yet" treatment.

### Platform Posture Pack

Purpose: future connected checks for repository branch protection, Actions permissions, webhooks, and SCM settings.

Likely tool: legitify.

Policy-derived safety labels: Network required, Needs credentials, Read-only, Approval required, Agent Lab blocked.

Expected runtime: to be proven later; legitify currently caps at 10 minutes.

Visibility: Advanced. It needs SCM credentials and repo-derived network access, so it should not appear as ordinary first-run coverage.

### Advanced Dependency Pack

Purpose: future package-behavior investigation for suspicious dependency version changes.

Likely tool: malcontent.

Policy-derived safety labels: Local, No credentials, Read-only, Approval required, Agent Lab blocked.

Expected runtime: to be proven later; malcontent currently caps at 15 minutes and also requires bounded local artifacts.

Visibility: Advanced. It depends on previous SBOM-backed scans and local old/new package artifacts, so it is a specialist workflow.

### External Surface Pack

Purpose: future approval-gated checks for user-provided domains and internet-facing assets.

Likely tools: not defined in MVP.

Policy-derived safety labels: Network required, Display only, Approval required, Agent Lab blocked.

Expected runtime: not applicable in MVP because there is no scanner, target input, install action, or run action.

Visibility: default Coming Soon, display-only. It may explain the future category, but it must not create a form field, probe a domain, call an external service, or give an agent an external scan action.

## Implementation Preservation Notes

- Do not turn packs into a second scanner execution path. Scan profiles remain the execution surface.
- Do not make a missing tool look like missing protection certainty. It is an evidence gap.
- Do not hide network, credential, artifact, previous-scan, or approval requirements inside a tooltip.
- Do not show install or uninstall ownership until DëvSec can prove the tool is managed by DëvSec.
- Do not copy Coming Soon tools into runnable pack actions.
- Do not solve trust with friendly copy while leaving risky actions available.

## User-State Acceptance Scenarios

Given the user is cautious and unsure what leaves their Mac, when they open a pack page, they can see local, network, credential, and approval labels before any action is offered.

Given the user sees a missing scanner in a pack, when they read the pack status, they understand the pack has an evidence gap and the repo has not been declared safe.

Given the user opens External Surface, when they inspect the page, they cannot enter a target, run a scan, install a tool, or trigger Agent Lab.

Given the user wants to use a real MVP pack, when they choose what to do next, the page recommends an existing `security-scan` profile rather than inventing a pack-run mode.
