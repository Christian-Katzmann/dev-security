# Current Scanner Catalog Mapping

This note maps the scanner stack DëvSec already knows how to run into Tool Catalog entries. It is an implementation bridge from the legacy `scanner_catalog()` shape to the richer catalog contract in `docs/tool-catalog.md`.

The important rule is simple: static catalog metadata can explain a tool, but runtime scanner status still decides whether it is usable on this machine.

## Mapping Defaults

For all current scanners:

- Results are stored locally in DëvSec scan output and SQLite history.
- `destructive_action` is `false`.
- `writes_files` is `false` for catalog policy purposes because scanner output is DëvSec-owned runtime data, not repo mutation.
- `external_targets` is `none` unless explicitly called out.
- `uninstall_posture` is `not-needed` for built-ins, `user-owned` for Homebrew or user-installed binaries, and `manual-only` for tools that require separate artifact or credential setup.
- `needs_approval` is `true` when a tool leaves the local boundary, needs credentials, or belongs to an advanced opt-in flow.
- Safety labels must be derived from the policy fields below, not copied onto UI cards as independent text.

## Current Scanner Entries

| Scanner | Category | Policy fields | Derived safety labels | Install method | Uninstall posture | Pack placement |
| --- | --- | --- | --- | --- | --- | --- |
| `ioc-watch` | `defense-intel` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=true` | Local, No credentials, Read-only, Agent Lab allowed, Built in | Built in | not-needed | Starter optional; Dependencies optional |
| `install-hooks` | `supply-chain` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=true` | Local, No credentials, Read-only, Agent Lab allowed, Built in | Built in | not-needed | Starter included; Dependencies optional |
| `workflow-audit` | `supply-chain` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=true` | Local, No credentials, Read-only, Agent Lab allowed, Built in | Built in | not-needed | Starter included; IaC coming-soon support |
| `ai-static` | `ai-agent` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=true` | Local, No credentials, Read-only, Agent Lab allowed, Built in | Built in | not-needed | Starter included; AI Agent included |
| `semgrep` | `code-security` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=true` | Local, No credentials, Read-only, Agent Lab allowed, Detected locally when present | `./install-security-observatory.sh` or `brew install semgrep` | user-owned until managed installs exist | Starter included |
| `gitleaks` | `secrets` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=true` | Local, No credentials, Read-only, Agent Lab allowed, Detected locally when present | `./install-security-observatory.sh` or `brew install gitleaks` | user-owned until managed installs exist | Starter included; Secrets included |
| `trufflehog` | `secrets` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=false` | Local, No credentials, Read-only, Agent Lab allowed, Detected locally when present | `./install-security-observatory.sh` or `brew install trufflehog` | user-owned until managed installs exist | Secrets included |
| `trivy` | `dependencies` | `local_only=false`, `network_access=optional`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=true` | Optional network, No credentials, Read-only, Agent Lab allowed, Detected locally when present | `./install-security-observatory.sh` or `brew install trivy` | user-owned until managed installs exist | Dependencies included; Secrets optional; IaC coming-soon support |
| `osv-scanner` | `dependencies` | `local_only=false`, `network_access=required`, `external_targets=none`, `uses_credentials=none`, `needs_approval=true`, `allowed_for_agent_lab=false`, `requires_human_setup=false`, `default_enabled=true` | Network required, No credentials, Read-only, Approval required, Agent Lab blocked, Detected locally when present | `./install-security-observatory.sh` or `brew install osv-scanner` | user-owned until managed installs exist | Dependencies included; Starter optional with network disclosure |
| `syft` | `dependencies` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=true` | Local, No credentials, Read-only, Agent Lab allowed, Detected locally when present | `./install-security-observatory.sh` or `brew install syft` | user-owned until managed installs exist | Dependencies included |
| `grype` | `dependencies` | `local_only=false`, `network_access=optional`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=true` | Optional network, No credentials, Read-only, Agent Lab allowed, Detected locally when present | `./install-security-observatory.sh` or `brew install grype` | user-owned until managed installs exist | Dependencies included |
| `checkov` | `infrastructure` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=false`, `requires_human_setup=false`, `default_enabled=false` | Local, No credentials, Read-only, Agent Lab blocked, Detected locally when present | `./install-security-observatory.sh` or `uv tool install checkov` | user-owned until managed installs exist | IaC coming-soon pack |
| `medusa` | `ai-agent` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=false`, `allowed_for_agent_lab=true`, `requires_human_setup=false`, `default_enabled=false` | Local, No credentials, Read-only, Agent Lab allowed, Detected locally when present | `./install-security-observatory.sh` or `uv tool install medusa-security` | user-owned until managed installs exist | AI Agent included |
| `malcontent` | `dependencies` | `local_only=true`, `network_access=none`, `external_targets=none`, `uses_credentials=none`, `needs_approval=true`, `allowed_for_agent_lab=false`, `requires_human_setup=true`, `default_enabled=false` | Local, No credentials, Read-only, Approval required, Agent Lab blocked, Detected locally when present | Separate `malcontent` or `mal` binary plus local artifact cache | manual-only | Advanced Dependency coming-soon pack; advanced opt-in tool |
| `legitify` | `platform-posture` | `local_only=false`, `network_access=required`, `external_targets=repo-derived`, `uses_credentials=required`, `needs_approval=true`, `allowed_for_agent_lab=false`, `requires_human_setup=true`, `default_enabled=false` | Network required, Needs credentials, Read-only, Approval required, Agent Lab blocked, Detected locally when present | `brew install legitify`, then set `SCM_TOKEN` or equivalent | manual-only | Platform Posture coming-soon pack; advanced opt-in tool |

## Pack Interpretation

Starter should stay low-friction and mostly local: `ai-static`, `install-hooks`, `workflow-audit`, `semgrep`, and `gitleaks` are the core entries. `ioc-watch` and `osv-scanner` can appear as contextual helpers, but `osv-scanner` needs a network disclosure because it relies on OSV advisory lookup.

Secrets is a real MVP pack: `gitleaks`, `trufflehog`, and Trivy secret scanning belong here. Trivy should keep its optional-network label because vulnerability and misconfiguration databases may be refreshed outside the repo.

Dependencies is a real MVP pack: `syft`, `grype`, `trivy`, `osv-scanner`, and optional `ioc-watch` form the current dependency picture. `syft` provides the local SBOM base; the vulnerability tools add advisory evidence.

AI Agent is a real MVP pack: `ai-static` is the safe default, and `medusa` is the deeper local scanner when installed.

IaC is a Coming Soon pack in the catalog even though `checkov`, `workflow-audit`, and Trivy misconfiguration checks already exist. The pack should wait until the UI can explain IaC scope and avoid making cloud posture feel active by default.

Platform Posture is a Coming Soon pack. `legitify` should be visible only as an advanced opt-in tool because it needs SCM credentials and network access. It should not be pack-only, because the backend already supports `--platform-posture`, but non-advanced users should not see it as normal coverage.

Advanced Dependency is a Coming Soon pack. `malcontent` should be visible only as an advanced opt-in tool because it needs local old/new package artifacts and is capped by explicit safety bounds. It should not be pack-only, because the backend already supports `--behavioral-drift`, but normal users should not be asked to reason about artifact diffing during first-run setup.

External Surface is display-only in the MVP. There is no current scanner entry for domain probing, port scanning, subdomain discovery, HTTP fingerprinting, or active recon. If the dashboard needs an External Surface tile before those controls exist, it must use `lifecycle=coming-soon`, `install_state=coming-soon`, `external_targets=user-provided`, `network_access=required`, `needs_approval=true`, `allowed_for_agent_lab=false`, and no run, install, uninstall, or target-input action.

## Hidden or Advanced by Default

Hide `legitify` and `malcontent` from non-advanced catalog views at first. They are useful, but each requires setup that can confuse the trust story: credentials for `legitify`, local old/new artifacts for `malcontent`.

Keep `checkov` visible only when the user enters IaC or advanced catalog context. It is local and read-only, but the pack story is not MVP-ready.

Keep `osv-scanner`, `trivy`, and `grype` visible in Dependencies with clear network/cache labels. They should not be hidden, but the dashboard must not imply their advisory data is fresh when the binary is missing or its local database is stale.

## Runtime Truth

Install state for external binaries must come from detection such as `shutil.which(...)` or a future managed-tool registry, not from the catalog table. A catalog entry can say "Semgrep is supported"; only runtime status can say "Semgrep can run here now."

Built-in entries can use static `install_state=built-in`, but they still need normal scanner status for whether a scan actually ran, skipped, or errored.

