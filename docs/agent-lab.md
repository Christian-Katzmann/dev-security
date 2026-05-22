# Agent Lab

Agent Lab lets a user bring the AI assistant they already trust, such as Codex,
Claude Code, or a future local agent, without handing DëvSec provider tokens on
day one. The first version is user-mediated: DëvSec exports safe planning
context, the user gives that context to an agent, and DëvSec imports a strict
structured proposal that the user can approve or deny.

The product promise is simple: the agent may investigate and recommend, but
DëvSec governs tool access, policy, execution, audit history, and normalized
evidence.

## Trust Boundary

Agent Lab is not an unbounded shell for an AI assistant. It is a controlled
planning loop around existing DëvSec scan profiles, Tool Catalog policy, and
Security Pack state.

- The agent is advice, not authority.
- The imported proposal is hostile input until validated.
- DëvSec executes only known, approved, policy-allowed local actions.
- Scanner output and normalized findings are evidence; agent reasoning is
  context for choosing what to run next.
- External Surface remains display-only in the MVP. No domain input, probing,
  active recon, install action, run action, or agent-triggered external scan is
  available.
- Packs are planning and education surfaces. They are not runnable execution
  modes.
- OAuth and live provider connections are later work. The MVP must prove the
  bring-your-own-AI loop without storing provider tokens.

## Roles And Responsibilities

| Role | Responsibility | Must not do |
| --- | --- | --- |
| User | Chooses what context to export, which agent to use, and whether to approve a proposal. | Accidentally grant hidden network, credential, install, write, or destructive permissions. |
| Agent | Reads exported context and returns a structured recommendation. | Run tools directly through DëvSec, invent tool IDs, request arbitrary commands, or treat pack names as executable actions. |
| DëvSec | Validates proposals, enforces catalog policy, executes approved existing scans, records decisions, and stores evidence locally. | Trust free-form text, bypass approval gates, or execute actions outside the catalog/profile allowlist. |
| Scanner adapters | Run bounded tool commands and produce raw output for normalization. | Become a second agent runner or accept agent-supplied shell fragments. |
| Normalizer and storage | Turn scanner output into findings, evidence gaps, history, and audit records. | Treat agent claims as scanner findings. |

## Prerequisites

Agent Lab depends on these product contracts already being visible and
enforceable:

- Tool Catalog entries with stable IDs, lifecycle state, install state, policy
  fields, capabilities, safety labels, and `allowed_for_agent_lab`.
- Security Packs that recommend scan profiles without becoming runnable pack
  modes.
- Existing scan profile IDs and scanner availability states.
- Evidence gaps for missing, skipped, unavailable, or policy-blocked tools.
- Local SQLite storage for scan history and audit records.
- Clear UI language for local-only, optional network, network required, needs
  credentials, needs approval, and Agent Lab blocked.

## User-Mediated MVP Flow

1. DëvSec builds an exportable context bundle for the selected repository.
2. The user copies that context into Codex, Claude Code, or another trusted
   agent.
3. The agent returns a structured proposal, not a natural-language instruction
   list.
4. The user pastes the proposal back into DëvSec.
5. DëvSec validates the proposal before storing it as a proposal record.
6. DëvSec shows a review screen with requested tools, packs, scan profiles,
   safety labels, blocked items, missing tools, and evidence gaps.
7. The user approves, denies, or leaves the proposal pending.
8. Approved work runs only through existing DëvSec-controlled scan profiles or
   explicit allowlisted scanner actions.
9. Results become normal raw reports, normalized findings, scanner status, and
   audit history.

This loop keeps provider trust with the user. DëvSec does not need provider
OAuth tokens, API keys, background callbacks, or live assistant sessions for the
first version.

## Agent Adapters

Agent adapters are a thin contract between DëvSec and the user's chosen AI. They
do not make Codex, Claude Code, or any future assistant a privileged execution
backend. In the MVP, every adapter has the same user-mediated shape:

```text
DëvSec context export -> user copies into agent -> agent returns proposal JSON -> user imports JSON -> DëvSec validates, approves, and executes
```

Provider-specific behavior belongs outside DëvSec until a later OAuth and live
connection design exists. The MVP should prove that the adapter contract works
with Codex and Claude Code because the exported context and imported proposal are
portable, not because DëvSec can call either provider directly.

### Exportable Context

The export is a planning bundle assembled from the same product contracts the
dashboard already uses: `/api/summary`, `/api/tool-catalog`,
`/api/security-packs`, and `/api/scan-profiles`. It should be small enough to
paste into an agent session and explicit enough that the agent does not need raw
reports or source files to recommend a safe next scan.

```json
{
  "schema_version": "agent-lab.context.v1",
  "context_id": "ctx_2026_05_21_repo_slug",
  "created_at": "2026-05-21T22:00:00Z",
  "repo": {
    "name": "repo-slug",
    "path": "/path/to/repo"
  },
  "tool_catalog": [],
  "security_packs": [],
  "scan_profiles": [],
  "scan_history_summary": {
    "latest_scan_id": "repo-20260521",
    "latest_profile": "quick",
    "latest_status": "complete",
    "severity_counts": {},
    "category_counts": {},
    "evidence_gap_counts": {}
  },
  "allowed_scan_profile_ids": ["quick", "code", "ai", "deps", "secrets", "iac"],
  "allowed_tool_ids": ["ai-static", "semgrep", "gitleaks"],
  "blocked_actions": [
    "arbitrary_command",
    "pack_execution",
    "external_surface_scan",
    "provider_oauth",
    "install_tool",
    "uninstall_tool"
  ],
  "policy_boundaries": {
    "packs_are_runnable": false,
    "external_surface_is_display_only": true,
    "proposal_actions_must_use_known_ids": true
  }
}
```

Tool and pack entries may be trimmed for paste size, but they must preserve IDs,
labels, policy fields, derived safety labels, lifecycle, install state,
capabilities, profile membership, pack membership, and Agent Lab availability.
Raw scanner output, secrets, private keys, environment variables, full finding
evidence, and unrelated filesystem state stay out of the export.

### Copy/Paste Prompt Format

DëvSec should generate one prompt that the user can copy into Codex, Claude
Code, or a local agent. The prompt should make the return format boring and
machine-checkable:

```text
You are helping plan a DëvSec Agent Lab proposal.

Read the DëvSec context bundle below. Recommend only known tool IDs, pack IDs,
and scan profile IDs from the bundle. Packs are recommendations only, not
runnable actions. External Surface is display-only. Do not suggest arbitrary
commands, provider OAuth, installs, uninstalls, or direct scanner execution.

Return exactly one JSON object matching schema_version
"agent-lab.proposal.v1". Do not wrap it in Markdown. Do not include prose
outside the JSON.

BEGIN_DËVSEC_AGENT_CONTEXT_V1
{...context json...}
END_DËVSEC_AGENT_CONTEXT_V1
```

If an agent cannot follow the format, the user can still read its advice, but
DëvSec must not import prose or turn prose into actions.

### Proposal Import Schema

Imported proposals use one strict JSON shape. Unknown executable intent is a
validation error, not a prompt for DëvSec to improvise.

```json
{
  "schema_version": "agent-lab.proposal.v1",
  "proposal_id": "agent_generated_unique_id",
  "source": {
    "adapter_id": "codex",
    "agent_label": "Codex",
    "created_at": "2026-05-21T22:05:00Z"
  },
  "context": {
    "context_id": "ctx_2026_05_21_repo_slug",
    "context_hash": "sha256:example",
    "repo_path": "/path/to/repo"
  },
  "summary": "Run the quick and secrets profiles first because local secret and code scanners are ready.",
  "recommended_tools": [
    {
      "tool_id": "gitleaks",
      "reason": "High-value local secret coverage is available.",
      "expected_benefit": "Find committed secrets before deeper dependency work.",
      "safety_labels": ["Local", "No credentials", "Read-only"]
    }
  ],
  "recommended_packs": [
    {
      "pack_id": "secrets",
      "reason": "The pack explains the secret-scanning job.",
      "runnable": false
    }
  ],
  "requested_execution": [
    {
      "action": "run_scan_profile",
      "scan_profile_id": "secrets",
      "tool_ids": ["gitleaks", "trufflehog"],
      "mode": "dry_run_preview",
      "requires_approval": true,
      "reason": "Use existing DëvSec scan profile execution, not agent commands."
    }
  ],
  "requested_permissions": ["local_repo_read", "write_devsec_reports"],
  "expected_evidence_gaps": [
    {
      "tool_id": "trufflehog",
      "reason": "missing_tool",
      "user_message": "TruffleHog may be unavailable locally, so DëvSec should record a gap if it cannot run."
    }
  ],
  "blocked_requests": [
    {
      "reason": "pack_not_runnable",
      "detail": "The Secrets pack can be recommended, but execution must target scan profile IDs."
    }
  ],
  "notes": "Optional explanation for the user. DëvSec does not parse this field into actions."
}
```

Validation rules:

- `schema_version` must match exactly.
- The payload must fit the import size limit before parsing.
- Top-level fields and executable nested fields must be allowlisted.
- `adapter_id` must be one of `codex`, `claude-code`, `local-agent`, or
  `manual-json` until a later adapter registry exists.
- Tool IDs, pack IDs, and scan profile IDs must exist in the exported context
  and current DëvSec catalogs.
- `requested_execution[].action` must be a fixed enum. MVP starts with
  `run_scan_profile` and may add explicit scanner-adapter actions only when
  they map to existing DëvSec execution paths.
- `requested_execution[].mode` must be `dry_run_preview` or `approved_run`.
  Import may request a mode, but DëvSec chooses what is actually available.
- `tool_ids` must be a subset of the selected scan profile or an explicit
  allowlist for that action.
- Pack recommendations must carry `"runnable": false`; any runnable-pack
  request is rejected.
- External Surface actions, arbitrary commands, markdown instructions, local
  file paths as commands, URLs as commands, provider OAuth, install, uninstall,
  policy overrides, and safety-label overrides are rejected.

### Adapter Capabilities

| Adapter | MVP capability | Not in MVP |
| --- | --- | --- |
| `codex` | Copy context into Codex, import strict proposal JSON, show source as Codex. | DëvSec calling Codex, storing OpenAI tokens, streaming Codex output, or giving Codex a DëvSec tool channel. |
| `claude-code` | Copy context into Claude Code, import strict proposal JSON, show source as Claude Code. | DëvSec calling Anthropic, storing Anthropic tokens, live tool invocation, or shell delegation. |
| `local-agent` | Copy context into a local or internal assistant and import the same proposal schema. | Assuming the local agent is safe, bypassing validation, or granting filesystem access through DëvSec. |
| `manual-json` | Let an expert paste a hand-written proposal that passes the same schema. | Treating free-form notes as executable instructions. |

The adapter contract is intentionally agent-agnostic. Provider names affect UI
labels, prompt copy, and future connection status; they do not affect validation
or execution rights.

### Future Connection State

The UI can reserve connection states without making them active promises:

| State | Meaning |
| --- | --- |
| `user-mediated` | MVP state. Export/import works without provider credentials. |
| `not-configured` | Live provider connection is not set up. |
| `oauth-available` | Later work has shipped a provider-specific OAuth flow. |
| `connected` | Later work has a valid local connection and scoped token. |
| `expired` | Later token exists but cannot be used until the user reconnects. |
| `revoked` | User disconnected the provider; no live calls are allowed. |
| `unavailable` | Provider adapter is hidden or disabled in this environment. |

Only `user-mediated` should be active in the first version. OAuth, local
callbacks, scopes, token storage, revocation, refresh behavior, and live provider
invocation are later security work.

### Future OAuth Decision Note

OAuth is explicitly deferred for the MVP. The user-mediated export/import loop
must prove that people want Agent Lab before DëvSec accepts provider-token risk.
The easy part is UI status, a local callback route, and provider-specific
labels. The security-sensitive part is everything that can turn a pasted
proposal workflow into a live privileged session: scopes, token persistence,
refresh, revocation, audit, prompt contents, and local callback abuse.

OAuth becomes worth adding only after the strict proposal loop is useful without
it: users repeatedly copy the same context into Codex or Claude Code, imported
proposals pass validation reliably, approval gates are understood, and live
handoff would remove real friction without expanding execution rights.

A later provider connection should use a native-app OAuth flow with PKCE, a
short-lived `127.0.0.1` loopback callback listener, an unpredictable `state`
value, an exact callback path, and provider-specific allowlists. The callback
must exchange only the authorization code, close itself after success or
timeout, and never expose a general dashboard API for provider redirects.

Provider scopes should be narrow and adapter-specific. The first live scopes
should allow reading or continuing the user's chosen assistant session only if
the provider supports that safely. They must not grant repo write access, shell
execution, scanner execution, organization administration, file upload beyond
the approved context bundle, or permission to bypass DëvSec proposal validation.

Token storage should use the macOS Keychain for access and refresh tokens. Local
SQLite may store connection metadata such as provider, account label, connection
state, granted scope names, token expiry, a non-secret token fingerprint, and
audit timestamps. SQLite must not store provider access tokens, refresh tokens,
API keys, OAuth client secrets, authorization codes, raw provider responses, or
conversation transcripts unless the user explicitly exports or imports them as
Agent Lab records.

Refresh should be conservative: refresh only when the user starts a live Agent
Lab action, mark expired tokens as `expired`, and fall back to the user-mediated
loop instead of silently running background refresh. Disconnect should delete
Keychain items, clear local connection metadata that implies live access, mark
the adapter `revoked`, call the provider revocation endpoint when available, and
block new live calls until the user reconnects.

Audit records for OAuth should contain enough to explain what happened without
leaking credentials: connect, callback success or failure, scopes granted,
token-refresh success or failure, live prompt/export sent, proposal imported,
approval decision, disconnect, revocation result, provider error class, and the
DëvSec scan IDs created after approval. Audit records must never include token
values, authorization codes, refresh responses, environment variables, honey-key
raw values, private keys, raw reports, or unredacted scanner evidence.

### Execution Handoff

After import, DëvSec should turn the proposal into a reviewable plan, not an
immediate scan:

1. Validate schema, size, known IDs, action enum, profile allowlist, policy
   fields, and blocked actions.
2. Store the proposal as pending with validation results and source metadata.
3. Show the user the requested scan profiles, tools, packs, permissions, safety
   labels, missing tools, blocked requests, and expected evidence gaps.
4. Require approval for the exact plan.
5. Convert approved `run_scan_profile` items into the same scan profile
   execution used by the CLI and dashboard `run-check` flow.
6. Record skipped, missing, unavailable, blocked, or policy-disallowed tools as
   evidence gaps.

The handoff must never accept shell fragments from the proposal. The only
execution surface is existing DëvSec scan/profile/tool routing.

### Evidence Return

Agent Lab returns DëvSec evidence, not agent claims:

- proposal validation result and reasons
- approval state and decision time
- scan job or scan ID created from approved execution
- scanner statuses, raw report paths, normalized findings, cases, and severity
  summaries already produced by DëvSec
- evidence gaps for missing, unavailable, skipped, or blocked tools
- a link back to the original proposal record and context export metadata

Agent notes can remain attached to the proposal, but they must not become
findings unless a DëvSec-controlled scanner produced matching evidence.

### Fallback Behavior

If the chosen agent is unavailable, the workflow should degrade without losing
the product:

- keep DëvSec scanning, Tool Catalog browsing, and Security Pack pages usable
- let the user copy the same context into another adapter
- offer the strict JSON schema and an example proposal for manual drafting
- reject invalid imports with precise validation errors
- keep pending proposals editable only through structured fields, not prose
  parsing
- preserve audit records for exports, imports, denials, and validation failures

The lowest-risk MVP is therefore a complete export/import loop with strict JSON
validation and explicit approval, ending at dry-run preview or existing scan
profile execution. Live provider auth can wait until this loop proves users want
Agent Lab enough to justify the token-handling risk.

## What The Agent Can See

The exported context should be useful but intentionally narrow:

- repository name/path summary and DëvSec product version where available
- Tool Catalog entries with IDs, categories, lifecycle, install state, policy
  fields, safety labels, capabilities, profile membership, and Agent Lab
  availability
- Security Pack summaries, included tools, Coming Soon state, and recommended
  scan profiles
- scan history summary such as latest run time, profile, overall status,
  severity counts, category counts, and evidence-gap counts
- allowed scan profile IDs and tool IDs
- blocked actions and policy boundaries
- explicit reminder that packs are not runnable and External Surface is
  display-only

The exported context should not include raw report dumps, secrets, full finding
evidence, local credential values, scanner raw output, unrelated filesystem
state, or hidden implementation details unless a later approval flow makes that
specific disclosure clear.

## What The Agent Can Propose

A proposal may recommend:

- known Tool Catalog tool IDs
- known Security Pack IDs as recommendations only
- known scan profile IDs such as quick, code, AI, dependencies, secrets, or
  other profiles DëvSec explicitly exports as allowed
- expected benefit and plain-language reason
- requested permissions chosen from a fixed set
- expected evidence gaps, including missing tools or blocked tools
- a final execution plan that maps back to explicit scan profiles or
  allowlisted scanner actions

A proposal must be structured data. Natural-language explanation may accompany
it, but DëvSec must not parse prose into executable actions.

## What DëvSec Executes

DëvSec executes approved Agent Lab work only when every condition is true:

1. The proposal passed schema, size, and allowlist validation.
2. The user approved the specific plan.
3. Each requested tool exists in the Tool Catalog.
4. Each requested action maps to an existing scan profile or explicit scanner
   adapter path.
5. The catalog policy allows Agent Lab for that tool.
6. Lifecycle and install state make the tool runnable.
7. Network, credential, file-write, destructive, and external-target rules are
   not bypassed.
8. Missing or unavailable tools are recorded as evidence gaps instead of being
   silently ignored.

Execution must reuse the existing DëvSec pipeline:

```text
approved proposal -> existing scan/profile/tool run -> raw output -> normalizer -> SQLite -> dashboard evidence
```

There is no second runner for agent commands in the MVP.

## Approval Boundaries

The user needs an approval gate before DëvSec does anything that changes the
local machine, leaves the local boundary, uses credentials, writes outside
DëvSec report/runtime folders, touches external targets, installs or uninstalls
tools, or runs an advanced opt-in workflow.

Approval should show:

- proposal source and import time
- selected repository
- requested scan profiles and tool IDs
- policy-derived safety labels
- blocked, missing, unavailable, and skipped tools
- whether network access or credentials are involved
- what DëvSec will store locally
- what evidence gaps may remain after execution

Approval is not a blanket delegation. If a proposal changes, it needs a new
validation and approval decision.

## Audit Records

Agent Lab should leave a local audit trail that can be understood later without
replaying the agent conversation:

- context export time, repo, and summary hash or version
- proposal import time, source label, schema version, and validation result
- rejected validation reasons
- approval state: pending, approved, denied, executed, failed, or superseded
- user decision time and optional decision note
- requested tool IDs, pack IDs, scan profile IDs, permissions, and safety labels
- blocked or skipped actions with reasons
- scan IDs or report paths created from approved execution
- evidence gaps for missing or unavailable tools

Audit records may reference local reports, but they should not duplicate raw
security evidence unless the storage model already expects it.

## Blocked By Default

These actions are blocked even if an agent asks for them:

- arbitrary shell commands or scripts
- free-form markdown instructions that DëvSec would turn into commands
- pack execution as if a pack were a scan profile
- External Surface target entry, probing, active recon, or agent-triggered
  external scans
- tools with `allowed_for_agent_lab = false`
- Coming Soon, deprecated, hidden, missing, or unavailable tools as runnable
  actions
- actions that require credentials, network-required access, external targets,
  destructive behavior, or approval when the proposal tries to skip the approval
  gate
- installing, uninstalling, upgrading, relinking, or repairing tools
- writing files outside normal DëvSec report/runtime locations
- reading or exporting raw reports, secrets, credentials, honey-key raw values,
  private keys, environment variables, or unrelated local files
- changing scanner timeouts, sanitizer behavior, normalizer behavior, or storage
  rules through the proposal
- invoking provider OAuth, storing provider tokens, or starting a live provider
  session

Blocked requests should be visible to the user as blocked items or evidence
gaps. They should not be quietly dropped from the proposal.

## Hostile Proposal Import Rules

Imported proposals must be treated like untrusted files:

- enforce a maximum payload size before parsing
- parse only a strict JSON shape with a known schema version
- reject unknown top-level fields when they could hide intent
- require stable IDs for tools, packs, actions, permissions, and scan profiles
- reject unknown tools, unknown packs, unknown actions, unsupported scan
  profiles, and arbitrary command strings
- reject runnable-pack requests and External Surface requests
- reject attempts to override policy fields or safety labels
- reject embedded markdown instructions, shell snippets, URLs-as-commands, local
  file paths as commands, and prompt-injection language that asks DëvSec to
  ignore rules
- store validation errors separately from approved execution plans
- keep the original imported payload only if size and sensitivity rules make it
  safe to retain locally

Validation should produce precise reasons, such as `unknown_tool`,
`agent_lab_blocked`, `external_surface_blocked`, `pack_not_runnable`,
`unsupported_action`, `approval_required`, or `payload_too_large`.

## Agent Advice Versus Scanner Evidence

The agent can help the user decide what to try next. It can compare catalog
coverage, explain why a pack is useful, point out missing tools, and suggest a
safe scan profile. That advice is not proof.

Evidence comes from DëvSec-controlled scanner runs and normalized findings:

- scanner status says what actually ran
- raw reports show tool output
- normalized findings and cases show DëvSec's interpretation
- evidence gaps show what did not run or could not be verified
- scan history shows whether a finding is new, recurring, or resolved

The UI should keep that distinction visible. A recommendation can say "run the
Secrets Pack's recommended profile"; only a completed DëvSec scan can say what
secret evidence was found.

## What The User Needs To Understand

Before trusting an agent-run investigation, the user needs to see:

- the agent did not receive unbounded local access from DëvSec
- the proposal was validated before approval
- DëvSec, not the agent, executed the approved work
- network, credential, install, write, destructive, and external-target actions
  were either blocked or explicitly shown
- missing tools mean evidence gaps, not safety
- scanner findings are stronger evidence than agent explanations
- the final audit trail can explain what happened later

That is the core trust story: bring the AI you trust for thinking, keep DëvSec
in charge of doing.
