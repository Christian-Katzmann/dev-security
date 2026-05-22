# DëvSec Agent Lab BYO AI

> Let people bring the AI they already trust, such as Codex or Claude Code, without handing DëvSec provider tokens on day one. The first version exports safe context, imports a structured proposal, and lets DëvSec control approval, execution, and evidence.

## Scope

This campaign designs and builds the first DëvSec Agent Lab: an agent-agnostic control surface where Codex, Claude Code, or later local/internal agents can inspect exported catalog context, propose a tool stack, request approval, and route approved existing DëvSec scans through DëvSec. Done means the product has a clear user-mediated adapter model, OAuth/token deferral decision, planner workflow, approval gates, and an MVP UI that can support Codex and Claude first without making DëvSec dependent on either provider.

## Context (locked decisions)

- Agent Lab is bring-your-own-AI: the user's trusted intelligence layer plugs into DëvSec.
- Codex and Claude Code are the first adapters if scoping is needed, but the design should remain agent agnostic.
- Agents recommend and investigate; DëvSec governs tool access, policy, execution, audit history, and normalized evidence.
- The agent sees Tool Catalog metadata and Security Pack state, not an unbounded shell playground.
- Risky actions need DëvSec/user approval before execution.
- Agent Lab MVP is user-mediated: export DëvSec context, use it in Codex/Claude/local agent, then import a structured proposal. No provider OAuth tokens are stored in the first version.
- Imported proposals are hostile input. DëvSec validates schema, size, known tools, known actions, and allowed scan-profile IDs before anything is stored or approved.
- OAuth is deferred, not ignored. Token storage, revocation, scopes, local callbacks, and provider differences are part of the later security design.
- Approved execution is limited to existing DëvSec-supported local scan profiles/tools. Missing tools become evidence gaps.
- Packs are not runnable in MVP. Agents may recommend packs or tools, but execution can only target explicit existing scan-profile IDs after approval.
- External Surface is display-only in MVP: no target input, no domain probing, no active recon, and no agent-triggered external scans.
- `DESIGN.md` is the canonical Mistglass design system for the Agent Lab interface.

## Prerequisites

- Tool Catalog Foundation has defined policy fields, derived safety labels, install-state truth, and allowed-for-Agent-Lab flags.
- Managed Security Packs has defined real MVP packs, Coming Soon packs, and the rule that packs are not runnable execution surfaces.
- Existing scan profile IDs and scanner availability states are exposed clearly enough for Agent Lab to allowlist execution.
- External Surface remains display-only before Agent Lab work starts.
- Root `DESIGN.md` has been read before Agent Lab UI implementation begins.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Trust and user-mediated adapter design

- [x] Step 1.1 — Define the Agent Lab trust model
- [x] Step 1.2 — Design user-mediated adapters for Codex and Claude
- [x] Step 1.3 — Grill: OAuth and token risk boundaries for later

### Phase 2 — Planner and approval loop

- [ ] Step 2.1 — Add exportable agent context
- [ ] Step 2.2 — Build proposal import and approval records
- [ ] Step 2.3 — Route approved existing scans through DëvSec

### Phase 3 — Agent Lab interface

- [ ] Step 3.1 — Build the user-mediated Agent Lab planner UI
- [ ] Step 3.2 — Validate with mocked and pasted proposals
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Define the Agent Lab trust model

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.2

Define the product promise and security boundary. The agent should feel powerful, but only because DëvSec is containing the risky parts.

```text
/ai-product-health-forensic

SCOPE: Define the trust model for DëvSec Agent Lab.
REQUIRED READING:
1. README.md
2. docs/tool-catalog.md
3. docs/security-packs.md
4. .adx/risks.json
5. docs/architecture.md
OUTPUT: Create docs/agent-lab.md with the Agent Lab product promise, roles and responsibilities, prerequisites, user-mediated MVP flow, what the agent can see, what the agent can propose, what DëvSec executes, approval boundaries, audit records, blocked-by-default actions, hostile proposal import rules, and the difference between agent advice and scanner evidence.
OPEN QUESTIONS:
- Which actions should be blocked by default even if an agent asks for them?
- What does the user need to understand before trusting an agent-run investigation?
```

## Step 1.2 — Design user-mediated adapters for Codex and Claude

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.1

Sketch the adapter layer without marrying the product to one AI provider. The first version should prove bring-your-own-AI through export/import rather than live provider connections.

```text
/architecture-health-forensic

SCOPE: Design a user-mediated agent adapter contract for Codex, Claude Code, and future agents.
REQUIRED READING:
1. docs/agent-lab.md
2. docs/tool-catalog.md
3. src/security_observatory/dashboard_server.py
4. src/security_observatory/cli.py
5. dashboard-ui/src/App.tsx
OUTPUT: Add an Agent adapters section to docs/agent-lab.md covering exportable context, copy/paste prompt format, strict structured proposal import schema, adapter capabilities, future connection state, future auth mechanism, execution handoff, evidence return, and fallback behavior when an agent is unavailable. Make OAuth/provider invocation explicitly later work. Avoid flexible natural-language parsing for proposal actions.
OPEN QUESTIONS:
- What exact proposal JSON shape should Codex and Claude return?
- What is the lowest-risk MVP that still proves bring-your-own-AI?
```

## Step 1.3 — Grill: OAuth and token risk boundaries for later

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Use a thinking step before building auth. The expected result for MVP is deferral, but the campaign should still capture the later auth boundary so it is not rediscovered sloppily.

```text
/grill-me

SCOPE: Stress-test OAuth and token handling for DëvSec Agent Lab as a later phase, while keeping MVP user-mediated.
REQUIRED READING:
1. docs/agent-lab.md
2. .adx/risks.json
3. src/security_observatory/dashboard_server.py
4. src/security_observatory/storage.py
OUTPUT: A short decision note in docs/agent-lab.md or docs/agent-lab-auth.md that explicitly defers OAuth for MVP, then covers later local OAuth callback, provider scopes, token storage, token revocation, refresh strategy, audit events, user disconnect, and what not to store. Be especially clear about what is easy and what is security-sensitive.
OPEN QUESTIONS:
- What would make OAuth worth adding after the user-mediated loop proves itself?
- If tokens are stored, what local storage mechanism is acceptable on macOS?
```

## Step 2.1 — Add exportable agent context

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Let agents reason from a clean, safe menu. They should receive an exportable context bundle with catalog summaries and pack state, not raw internal implementation sprawl or sensitive report dumps.

```text
SCOPE: Add an exportable backend context payload for user-mediated Agent Lab planners.
REQUIRED READING:
1. docs/agent-lab.md
2. docs/tool-catalog.md
3. docs/security-packs.md
4. src/security_observatory/scanners.py
5. src/security_observatory/dashboard_server.py
OUTPUT: Backend code that builds an exportable agent context payload containing repo summary, catalog tools, packs, policy fields, derived safety labels, installed/detected/missing state, scan history summary, allowed existing scan-profile IDs/tools, blocked actions, non-runnable pack rules, and explicit policy boundaries. Do not expose secrets or raw local report contents unnecessarily.
OPEN QUESTIONS:
- Which parts of scan history are helpful enough to show the agent, and which are too sensitive or noisy?
```

## Step 2.2 — Build proposal import and approval records

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Represent the pasted/imported agent recommendation as a structured proposal that DëvSec can approve, deny, edit, and audit.

```text
SCOPE: Implement structured proposal import, validation, and approval decisions for Agent Lab.
REQUIRED READING:
1. docs/agent-lab.md
2. src/security_observatory/storage.py
3. src/security_observatory/dashboard_server.py
4. src/security_observatory/model.py
OUTPUT: Data model and API changes for imported agent proposals: recommended tools/packs, reason, expected benefit, policy fields, safety labels, requested permissions, validation status, approval state, audit timestamps, and final execution plan. Treat proposal import as untrusted data: enforce schema validation, size limits, known tool/action IDs, explicit scan-profile allowlists, no arbitrary commands, no markdown instruction execution, and rejection for unsupported tools, external surface actions, runnable-pack requests, or high-risk requests.
OPEN QUESTIONS:
- Should proposal records live in SQLite from the first version, or start as in-memory jobs until the workflow proves itself?
```

## Step 2.3 — Route approved existing scans through DëvSec

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

This is the central rule: agents do not bypass DëvSec. Approved proposals can only preview or run explicit existing DëvSec-supported local scan profiles/tools in MVP, producing normal evidence.

```text
SCOPE: Route approved Agent Lab proposals through existing DëvSec-controlled scan execution.
REQUIRED READING:
1. docs/agent-lab.md
2. src/security_observatory/scanners.py
3. src/security_observatory/normalize.py
4. src/security_observatory/cli.py
5. src/security_observatory/dashboard_server.py
OUTPUT: Backend changes that convert approved agent proposals into dry-run previews or existing scan/profile/tool runs where possible, enforce policy gates, capture raw output, normalize findings, and record skipped/unavailable tools as evidence gaps rather than silent failures. Do not add arbitrary command execution, external-surface execution, pack execution, or a second runner.
OPEN QUESTIONS:
- Should MVP stop at proposal validation and approval records, or include approved existing scan-profile execution behind a dry-run/preview gate?
```

## Step 3.1 — Build the user-mediated Agent Lab planner UI

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Create the first user experience: export DëvSec context, paste it into the user's chosen AI, import the returned proposal, then approve or decline.

```text
/frontend-design

SCOPE: Build the first user-mediated Agent Lab planner interface in the dashboard.
REQUIRED READING:
1. docs/agent-lab.md
2. docs/tool-catalog-storefront.md
3. DESIGN.md
4. dashboard-ui/src/App.tsx
5. dashboard-ui/src/dashboardData.ts
6. dashboard-ui/src/index.css
OUTPUT: UI changes for Agent Lab with Codex/Claude/local agent choice, export-context prompt, import-proposal input, untrusted-import warnings, proposed stack review, policy-derived safety labels, approval controls, dry-run/preview state if execution exists, audit trail, and clear disabled/future states for OAuth or live adapters not yet wired. Keep the interface aligned to DESIGN.md and avoid making provider connection the first-screen promise. Do not ask the user to connect provider accounts in MVP.
OPEN QUESTIONS:
- Should Agent Lab be a top-level nav item immediately, or live inside Tool Catalog until the workflow is real?
```

## Step 3.2 — Validate with mocked and pasted proposals

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

Prove the loop without provider auth. Mocked and pasted proposals can confirm that the UI, proposal model, validation, and approval gates behave correctly.

```text
SCOPE: Validate Agent Lab with mocked Codex/Claude responses and pasted structured proposals.
REQUIRED READING:
1. .adx/commands.json
2. docs/agent-lab.md
3. DESIGN.md
4. src/security_observatory/dashboard_server.py
5. dashboard-ui/src/App.tsx
6. dashboard-ui/src/dashboardData.ts
OUTPUT: Add or run focused validation for mocked/pasted agent proposal flow, schema failures, size-limit failures, unknown tool rejection, runnable-pack rejection, approval gates, denied requests, external-surface rejection, arbitrary-command rejection, missing tool states, and execution routing through explicit existing DëvSec scan-profile IDs only. Run fast Python import checks and dashboard lint/build if UI changed. Do not connect real OAuth credentials unless Christian explicitly asks.
OPEN QUESTIONS:
- Does the mocked flow prove the product idea, or does it need one real local-agent handoff before it feels credible?
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the DëvSec Agent Lab BYO AI campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/agent-lab-byom.md
Campaign: campaigns/agent-lab-byom.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff that the criteria actually landed. Don't trust step receipts — read the diff.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas.

Be honest. Lean. APPROVED if every step's acceptance criteria landed and there are no cross-step regressions. NEEDS WORK if any step cut corners or a primitive was bypassed.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.7 with Extra High thinking
(Your call — both are acceptable for this kind of cross-file review.)
```

**Verdict-to-action mapping:**

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign"). Campaign is done.
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick the checkbox until APPROVED.
