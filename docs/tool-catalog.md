# Tool Catalog Contract

The Tool Catalog is DëvSec's product contract for security tools. It explains what each tool does, how it is allowed to behave, whether it is usable on this machine, and how it fits into scans and Security Packs.

The first version is intentionally read-only. It must not change scanner execution behavior, install tools automatically, or make external scanning feel available before the backend can enforce the safety rules.

Shortest product sentence: the Tool Catalog tells you what DëvSec can check, what is safe to run, and what is only future coverage.

## Human Context Contract

- User likely arrives feeling: curious, cautious, and unsure which security tools are safe to run.
- Prior context they may carry: scanner names are technical, installation status can be confusing, and a clean scan can feel more trustworthy than it really is.
- What they fear getting wrong: running a risky tool, sending code or targets outside the machine, or believing coverage exists when a scanner is not installed.
- What getting it wrong costs: false confidence, leaked source or credentials, unwanted network activity, or damage to a repo or account.
- Their likely bandwidth: low to medium; the catalog must be scannable without requiring scanner expertise.
- What they need to trust: clear install state, local-only boundaries, opt-in network behavior, and honest Coming Soon placeholders.
- Where they need agency: before any credential use, network access, file write, external target, install, uninstall, or destructive action.
- What the product must not do: hide risky behavior behind friendly labels or treat display-only tools as runnable actions.

## Plain-Language Vocabulary

The catalog is more than a list of binaries. A binary name only says "this command may exist." A catalog entry says what the tool is for, whether DëvSec owns it, what safety rules apply, whether this Mac can run it now, and which pack should explain it to the user.

Use these terms consistently:

| Term | Meaning |
| --- | --- |
| Tool Catalog | The complete read-only registry of supported, detected, built-in, unavailable, and coming-soon security tools. |
| Catalog entry | One tool, plugin, app, MCP connector, scanner, or workflow with stable metadata and enforceable policy fields. |
| Security Pack | A curated bundle of catalog entries for a job, such as Starter, Secrets, Dependencies, or AI Agent. |
| DëvSec-managed install | A tool DëvSec installed or can safely update/remove through a known managed path. This is future-facing until a managed-tool registry exists. |
| Detected install | A tool found locally, usually on `PATH`, but installed outside DëvSec. DëvSec may use it, but must not claim it can uninstall or upgrade it. |
| Built-in tool | Scanner logic implemented inside DëvSec. It does not depend on an external binary. |
| Optional Docker | Docker can be offered as an alternate way to run heavy or awkward tools, but the MVP must not depend on Docker as the foundation. |
| Policy-derived safety label | A user-facing label generated from policy fields, install state, and lifecycle state. It is not separate marketing copy. |
| Coming Soon placeholder | A display-only catalog entry that educates users about future coverage without offering run, install, target, uninstall, or Agent Lab actions. |

Security Packs should help users choose a job, not override the rules of the tools inside the pack. If one included tool needs credentials, network access, approval, or previous artifacts, the pack has to surface that before any action can run.

MVP invariant: External Surface is display-only. It has no domain input, no probing, no active recon, no install action, no run action, and no agent-triggered external scan until a later campaign adds enforceable target and approval controls.

## Catalog Entry Shape

Each catalog entry should have one stable `id`. For current scanners this should match the existing scanner key, such as `semgrep`, `gitleaks`, or `ai-static`.

```ts
type ToolCatalogEntry = {
  id: string;
  kind: 'scanner' | 'plugin' | 'app' | 'mcp-connector' | 'workflow';
  label: string;
  summary: string;
  description?: string;
  category: ToolCatalogCategory;
  scanner_key?: string;
  legacy_scanner?: ScannerCatalogCompat;
  lifecycle: ToolLifecycle;
  install_state: ToolInstallState;
  install: ToolInstallContract;
  policy: ToolPolicy;
  capabilities: ToolCapabilities;
  derived_labels: ToolDerivedLabels;
  packs: ToolPackMembership[];
  profiles: string[];
  docs_path?: string;
  homepage_url?: string;
};
```

Current scanner compatibility should be preserved through `legacy_scanner` or equivalent top-level compatibility fields until the dashboard has fully migrated.

```ts
type ScannerCatalogCompat = {
  scanner: string;
  label: string;
  area: string;
  covers: string;
  profile: string;
  install: string;
  next_step: string;
  built_in?: boolean;
};
```

Keep these current scanner fields stable for backward compatibility:

| Current field | Preserve as | Reason |
| --- | --- | --- |
| `scanner` | `id`, `scanner_key`, and compatibility field | Existing scan status joins by scanner key. |
| `label` | `label` | User-facing display name already exists in API and UI. |
| `area` | `category` plus compatibility field | Current dashboard groups by area. |
| `covers` | `summary` or `description` plus compatibility field | Existing cards explain what evidence the tool adds. |
| `profile` | `profiles` plus compatibility field | Scan profile membership is part of current guidance. |
| `install` | `install.instructions` plus compatibility field | Not-installed tool recovery depends on it. |
| `next_step` | `install.next_step` plus compatibility field | Not-run guidance depends on it. |
| `built_in` | `install.method = 'built-in'` plus compatibility field | Built-in tools never need external binaries. |

## Categories

Use stable categories for filtering and pack composition. Display copy can change, but category ids should not.

| Category id | Use for |
| --- | --- |
| `code-security` | Static analysis and code vulnerability tools. |
| `secrets` | Secret scanners and secret evidence. |
| `dependencies` | Vulnerability, SBOM, package inventory, and dependency trust tools. |
| `supply-chain` | Install hooks, workflow surfaces, provenance, and release behavior. |
| `infrastructure` | IaC and cloud configuration tools. |
| `ai-agent` | AI-agent, MCP, prompt, and editor risk tools. |
| `platform-posture` | Connected SCM or hosting posture tools. |
| `external-surface` | External attack-surface tools. MVP entries are display-only placeholders. |
| `defense-intel` | IOC and named-campaign defensive checks. |

## Lifecycle States

Lifecycle is product availability, not local install status.

| State | Meaning |
| --- | --- |
| `available` | Supported in the product and safe to present as usable when install state allows it. |
| `beta` | Supported but should be labelled as early or advanced. |
| `advanced` | Supported only for users who opt into advanced workflows. |
| `coming-soon` | Product placeholder only; no run, install, target input, or Agent Lab action. |
| `deprecated` | Still recognized for historical scan data but no longer promoted. |
| `hidden` | Internal or not shown to normal users. |

External Surface tools must use `coming-soon` for the MVP unless a later campaign adds enforceable target and approval controls.

## Install States

Install state is local truth about whether the tool can run here now.

| State | Meaning | Source of truth |
| --- | --- | --- |
| `built-in` | Implemented inside DëvSec. No external binary install is needed. | Static metadata plus scanner adapter. |
| `managed` | Installed or managed by DëvSec's installer. | Installer manifest or managed-tool registry. |
| `detected` | Found on `PATH` or through a supported local detection check, but not owned by DëvSec. | Runtime detection such as `shutil.which`. |
| `missing` | Supported but not currently available locally. Display as **Not installed** in UI/CLI copy. | Runtime detection. |
| `unavailable` | Cannot run in the current environment, profile, or configuration. | Runtime detection or explicit guardrail. |
| `not-configured` | Installed but requires credentials, local artifacts, cache data, or repo context. | Runtime preflight. |
| `coming-soon` | Display-only entry. It must not be runnable or installable. | Lifecycle state. |

### Built-In, Managed, Detected, Unavailable, Coming Soon

- `built-in` means DëvSec owns the scanner logic. Examples: AI static checks, install-hook classifier, workflow audit, IOC watch.
- `managed` means DëvSec installed or can update the external tool through a known installer path. This is future-facing until managed install state is recorded.
- `detected` means the tool exists locally but was installed outside DëvSec. The catalog may explain it, but uninstall or upgrade controls must not claim ownership.
- `missing` means the tool should work after installation. User-facing copy says **Not installed**, not "missing."
- `unavailable` means installation alone is not enough. The reason might be absent credentials, unsupported platform, absent artifacts, no previous SBOM, or no resolvable repository target.
- `coming-soon` means product education only. It is not a failed install and must not appear as degraded protection.

## Install Contract

```ts
type ToolInstallContract = {
  method: 'built-in' | 'homebrew' | 'uv-tool' | 'manual' | 'docker-optional' | 'managed-future' | 'none';
  owner: 'devsec' | 'external' | 'user' | 'not-applicable';
  detection: 'built-in' | 'path-binary' | 'config-preflight' | 'cache-preflight' | 'registry-future' | 'none';
  binary?: string;
  managed_package?: string;
  instructions?: string;
  next_step?: string;
  uninstall_posture: 'not-needed' | 'devsec-managed' | 'user-owned' | 'manual-only' | 'not-supported';
};
```

Docker may appear as an optional install method, but it should not be the foundation for the MVP because the product is local-first and should stay light on Christian's machine.

## Managed Install Ownership And Uninstall Rules

DëvSec must never confuse "I found this on your Mac" with "I installed this for you." Managed install state is an ownership claim, not just a binary detection result.

### Managed Copy Layout

- DëvSec-managed external tools live under `${SECURITY_OBSERVATORY_HOME:-~/.security-observatory}/tools/<tool-id>/<version>/`.
- The executable DëvSec runs must be inside that managed tool root, normally at `bin/<binary>`.
- A managed helper symlink or shim may live under `${SECURITY_OBSERVATORY_HOME:-~/.security-observatory}/tools/bin/`, but only when the ownership manifest records it.
- DëvSec must not install scanner binaries into `/usr/local/bin`, `/opt/homebrew`, Homebrew Cellar paths, `~/.local/bin`, `uv`'s global tool location, `pipx`, or system package-manager locations for the MVP managed proof. The existing `~/.local/bin/security-scan` wrapper is the app launcher, not scanner-tool ownership.
- Docker is optional only for future tools that benefit from isolation or are painful to install natively. Docker is not the default managed-install foundation.

### Ownership Evidence

A tool can be labelled `managed` only when all ownership evidence agrees:

1. A local SQLite ownership row exists for the tool id, version, binary path, install root, source, checksum when available, install time, installer version, and active status.
2. A manifest record under `${SECURITY_OBSERVATORY_HOME:-~/.security-observatory}/tools/managed-tools.json` has the same tool id, version, install root, binary path, and ownership id.
3. The binary path resolves inside the recorded managed install root.
4. The install root contains an ownership marker written by DëvSec, such as `.devsec-managed-tool.json`, with the same ownership id.
5. The binary exists and passes the tool's local version check within a short timeout.

If those records disagree, the UI must not call the tool managed. It should fall back to `detected`, `missing`, or `unavailable` based on runtime detection, and uninstall/update controls must be disabled until ownership is repaired.

SQLite is the queryable product source of truth for API and dashboard state. The JSON manifest and per-install marker are recovery evidence close to the files, so a future repair flow can tell a real DëvSec install from a user-owned path even if one store is stale.

### Detected System Tools

`detected` means DëvSec found a usable binary through `PATH` or another supported local detection check, but does not own it. A detected system tool can satisfy scanner availability, but DëvSec must not:

- uninstall it
- upgrade it
- relink it
- overwrite it with a managed copy
- assume Homebrew, `uv`, `pipx`, or another package manager may remove it

If a detected tool and a managed copy both exist, DëvSec should prefer the managed binary for managed actions and still show the detected copy as user-owned context. If the managed copy is absent or broken, DëvSec may fall back to detected execution only as a normal detected scanner, not as a managed install.

### Install Preview Requirement

Every managed install or uninstall needs a preview before execution. The preview must show:

- the exact tool, version, and install method
- the install root and binary path
- any shim or symlink DëvSec will create
- whether the action needs network access
- the files/directories DëvSec expects to own afterward
- the local version check DëvSec will run
- the uninstall boundary DëvSec will enforce later
- the fact that user-owned detected tools will be left alone

Pack pages may aggregate these previews, but broad pack install/uninstall remains deferred. MVP controls should preview individual tool actions and the one approved proof path only.

### Uninstall Boundary

Uninstall may remove only files that are all of these:

1. Under `${SECURITY_OBSERVATORY_HOME:-~/.security-observatory}/tools/`.
2. Inside the install root recorded in both SQLite and the manifest.
3. Marked with the matching DëvSec ownership id.
4. Not a symlink escape, parent directory, package-manager directory, or arbitrary path from user input.

Uninstall must refuse to run when ownership evidence is absent, mismatched, or points outside the managed root. It must never call `brew uninstall`, `uv tool uninstall`, `pipx uninstall`, `sudo`, or a broad package-manager removal for a detected system tool. It also must not delete scan reports, caches, the app database, or the `security-scan` wrapper.

### Version And Update Checks

Version checks are local readiness checks. They may run commands such as `<binary> version` or `<binary> --version` with a short timeout, captured output, and no shell interpolation. Version check failure can make a managed copy `unavailable` or `needs repair`, but it does not grant permission to delete user-owned binaries.

Update checks are not background package-manager actions. For the MVP proof, DëvSec should compare the managed version against pinned product metadata or a user-triggered network check that is labelled in the preview. A newer upstream release can produce an "update available" state, but updating still requires a managed install preview and the same ownership evidence.

### First Allowed Managed Install Proof

The first managed install/uninstall proof target is `gitleaks`, pinned to Gitleaks `v8.30.1` release artifacts for the managed proof path.

Why it is safe enough for the proof:

- It already exists as a supported scanner and participates in the Quick, Secrets, and default profiles.
- Its normal scan behavior is local, read-only, and does not require credentials.
- It has a bounded scanner timeout in DëvSec's adapter.
- It provides high-value coverage that a user can understand: exposed secrets.
- A DëvSec-managed copy can be isolated under the managed tools directory without taking over Homebrew, `uv`, `pipx`, or global `PATH`.

Only `gitleaks` is approved for the first managed install/uninstall implementation. Broad pack install, high-risk installers, Docker-backed installs, package-manager uninstall, and management of detected system tools remain out of scope until a later campaign explicitly expands the policy.

The backend exposes the proof through `POST /api/managed-tools/install` and `POST /api/managed-tools/uninstall`. Both endpoints require explicit confirmation fields, operate only on `gitleaks`, and refresh the Tool Catalog status after the action.

## Enforceable Policy Fields

Policy fields are rules. They are the source of truth for UI affordances, pack eligibility, Agent Lab permissions, and future install/run controls.

```ts
type ToolPolicy = {
  local_only: boolean;
  writes_files: boolean;
  network_access: 'none' | 'optional' | 'required';
  external_targets: 'none' | 'repo-derived' | 'user-provided';
  uses_credentials: 'none' | 'optional' | 'required';
  destructive_action: boolean;
  needs_approval: boolean;
  allowed_for_agent_lab: boolean;
  stores_results_locally: boolean;
  sends_source_off_machine: boolean;
  requires_human_setup: boolean;
  default_enabled: boolean;
};
```

### Policy Matrix

| Policy field | Enforcement rule | Product consequence |
| --- | --- | --- |
| `local_only` | If true, the tool must not require outbound service calls for normal operation. | Can receive a "Local" safety label. |
| `writes_files` | If true, any action that writes outside scan output or DëvSec runtime folders needs explicit UI treatment. | Show "Writes files"; require preview or confirmation for write actions. |
| `network_access` | `required` and `optional` tools must be blocked from silent background use unless the run path explicitly permits network access. | Show "Network" or "Optional network"; separate from local scanners. |
| `external_targets` | `user-provided` target entry must not exist for MVP External Surface placeholders. | Show "External target" only when target controls and approval exist. |
| `uses_credentials` | Required credentials must come from environment or explicit user setup, never saved command text. | Show "Needs credentials"; keep out of default scans. |
| `destructive_action` | Destructive tools are never normal scan actions and must require a hard approval gate. | Show "Destructive"; exclude from normal packs unless intentionally specialized. |
| `needs_approval` | Any run, install, uninstall, credential use, external target, or file write requiring approval must block agent-triggered execution. | Show "Needs approval" and disable one-click automation. |
| `allowed_for_agent_lab` | Agent Lab may only trigger tools when this is true and lifecycle/install state also allow it. | Controls agent-facing action availability. |
| `stores_results_locally` | If false, the catalog must explain where results go before the action runs. | Reinforces local-first trust. |
| `sends_source_off_machine` | If true, the tool is not local-first and must never be hidden inside a normal scan profile. | Show "Sends source off machine"; require explicit opt-in. |
| `requires_human_setup` | If true, DëvSec can guide setup but should not pretend the tool is ready. | Maps detected tools to `not-configured` when setup is incomplete. |
| `default_enabled` | Only safe, local, non-destructive tools should be default-enabled. | Prevents advanced checks from quietly joining quick/default scans. |

## Capabilities

Capabilities describe what evidence a tool can produce. They should not carry approval or safety semantics by themselves.

```ts
type ToolCapabilities = {
  finding_categories: string[];
  evidence_types: Array<
    | 'source-pattern'
    | 'secret-match'
    | 'dependency-advisory'
    | 'sbom'
    | 'iac-policy'
    | 'workflow-policy'
    | 'install-hook'
    | 'ai-config'
    | 'platform-posture'
    | 'behavior-diff'
    | 'ioc-match'
    | 'external-observation'
  >;
  scan_profiles: string[];
  requires_previous_scan: boolean;
  requires_artifacts: boolean;
  requires_repo_remote: boolean;
};
```

## Derived Safety Labels

Safety labels are product-facing summaries derived from policy and install state. They must not be handwritten independently on cards.

| Derived label | Derivation |
| --- | --- |
| `Local` | `policy.local_only = true` and `network_access = 'none'`. |
| `Optional network` | `network_access = 'optional'`. |
| `Network required` | `network_access = 'required'`. |
| `No credentials` | `uses_credentials = 'none'`. |
| `Needs credentials` | `uses_credentials = 'required'` or `'optional'` when the selected action needs them. |
| `Read-only` | `writes_files = false` and `destructive_action = false`. |
| `Writes files` | `writes_files = true`. |
| `Approval required` | `needs_approval = true`. |
| `Agent Lab allowed` | `allowed_for_agent_lab = true`, lifecycle is runnable, and install state is runnable. |
| `Agent Lab blocked` | `allowed_for_agent_lab = false` or lifecycle/install state is not runnable. |
| `Display only` | `lifecycle = 'coming-soon'` or `install_state = 'coming-soon'`. |
| `DëvSec managed` | `install.owner = 'devsec'`. |
| `Detected locally` | `install_state = 'detected'`. |

Do not solve trust by making copy warmer while leaving risky actions available. The done-well bar is that a cautious user can tell what will stay local, what needs opt-in, and what is only a placeholder before any button can run it.

## Security Packs

Security Packs are curated bundles of catalog entries. A pack does not weaken individual tool policy.

```ts
type ToolPackMembership = {
  pack_id: 'starter' | 'secrets' | 'dependencies' | 'ai-agent' | 'iac' | 'platform-posture' | 'advanced-dependency' | 'external-surface';
  role: 'included' | 'optional' | 'coming-soon';
  default_enabled: boolean;
};
```

Pack rules:

- Starter packs should prefer local, default-enabled, non-destructive tools.
- Advanced packs may include opt-in network, credential, previous-scan, or artifact requirements, but must surface those requirements before action.
- Coming Soon packs can educate and show future shape, but must not provide active install, run, target, or Agent Lab actions.
- External Surface is display-only in MVP: no domain input, probing, active recon, or agent-triggered external scan.

## Runnable State

A tool is runnable only when all of these are true:

1. `lifecycle` is `available`, `beta`, or an explicitly enabled `advanced` state.
2. `install_state` is `built-in`, `managed`, or `detected`.
3. Required setup is complete, so `install_state` is not `not-configured` or `unavailable`.
4. The selected action's policy permits the current context.
5. Any required approval has been granted by the user.
6. Agent Lab execution is requested only when `allowed_for_agent_lab` is true.

This prevents catalog optimism from becoming scanner optimism. Availability shown in the dashboard should still come from real system checks, not from static catalog metadata.

## MVP Answers To Open Questions

### Enforcement Rules vs Product Labels

The enforcement rules are `ToolPolicy`, `ToolInstallContract`, `lifecycle`, and runtime install/preflight detection. The product-facing labels are derived from those fields. Cards can choose which derived labels to display, but they should not own separate safety truth.

### Current Scanner Fields To Preserve

Preserve `scanner`, `label`, `area`, `covers`, `profile`, `install`, `next_step`, and `built_in` through the migration. The current dashboard and fallback catalog use those fields to group scanner doctor rows, join scan statuses, explain not-installed binaries, and tell the user what to do next.
