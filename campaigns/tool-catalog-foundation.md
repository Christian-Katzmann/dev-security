# DëvSec Tool Catalog Foundation

> Build the foundation for an in-app catalog of security tools. DëvSec will know what each tool does, how risky it is, whether it is installed, and how it fits into scans.

## Scope

This campaign creates the product and technical foundation for the Tool Catalog: the catalog record shape, enforceable policy fields, backend status APIs, install-state detection, and docs that explain how tools and packs differ. Done means DëvSec can describe its current scanners as catalog entries with real risk metadata and honest installation state, even before one-click install/uninstall is fully built.

## Context (locked decisions)

- Tool Catalog is the app-store layer for individual tools, plugins, apps, MCP connectors, and scanners.
- Security Packs are curated bundles of catalog items for specific purposes.
- DëvSec is batteries-included: it brings a default scanner stack and does not rely on users manually understanding every tool.
- Docker should be optional, not the foundation, because it can be heavy on Christian's machine.
- External Surface Pack exists as a Coming Soon placeholder for now, not an active scanner workflow.
- External Surface is display-only in MVP: no target input, no domain probing, no active recon, and no agent-triggered external scans.
- Safety labels must be derived from enforceable policy/capability fields, not handwritten copy on a card.

## Prerequisites

- No prior campaign is required; this is the foundation for the later Storefront, Managed Security Packs, and Agent Lab campaigns.
- Existing scanner behavior and scan profiles should remain unchanged while the catalog contract is introduced.
- Current scanner docs and adapter contracts are the source material for the first catalog entries.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Product contract

- [x] Step 1.1 — Define the catalog contract and policy matrix
- [x] Step 1.2 — Map current scanners into catalog metadata

### Phase 2 — Backend foundation

- [x] Step 2.1 — Add catalog types and registry helpers
- [x] Step 2.2 — Expose catalog and install-state API data

### Phase 3 — Documentation and guardrails

- [x] Step 3.1 — Document Tool Catalog and Security Packs
- [x] Step 3.2 — Verify import, API shape, and stale metadata risks
- [x] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Define the catalog contract and policy matrix

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.2

Turn the product idea into a stable catalog schema before implementation. The output should be concrete enough that backend and frontend work can proceed without reinventing labels, states, or safety rules.

```text
/human-centered-design

SCOPE: Define the DëvSec Tool Catalog contract for individual installable security tools, including enforceable policy fields.
REQUIRED READING:
1. README.md
2. docs/architecture.md
3. docs/scanners.md
4. docs/adding-scanners.md
OUTPUT: A concise schema proposal in docs/tool-catalog.md covering fields, policy/capability matrix, derived safety labels, install-state labels, lifecycle states, and the difference between built-in, managed, detected, unavailable, and coming-soon tools. Include policy fields for local-only, writes files, network access, external targets, credentials, destructive action, needs approval, and allowed for Agent Lab.
OPEN QUESTIONS:
- Which policy fields are enforcement rules, and which labels are product-facing summaries derived from them?
- Which current scanner fields should be preserved for backward compatibility?
```

## Step 1.2 — Map current scanners into catalog metadata

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 1.1

Create the first catalog inventory from what DëvSec already knows how to run. This keeps the new concept grounded in the current product instead of becoming abstract shelfware.

```text
SCOPE: Map the current DëvSec scanner stack into Tool Catalog entries.
REQUIRED READING:
1. src/security_observatory/scanners.py
2. docs/scanners.md
3. docs/setup.md
4. dashboard-ui/src/dashboardData.ts
OUTPUT: A short implementation note in docs/tool-catalog-current-scanners.md listing each current scanner, catalog category, policy fields, derived safety labels, install method, uninstall posture, and whether it belongs in a real MVP pack (Starter, Secrets, Dependencies, AI Agent) or a Coming Soon pack (IaC, Platform Posture, Advanced Dependency, External Surface). Mark External Surface entries as display-only placeholders.
OPEN QUESTIONS:
- Should legitify and malcontent appear as advanced opt-in tools or pack-only tools?
- Which tools should be hidden from non-advanced users at first?
```

## Step 2.1 — Add catalog types and registry helpers

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Implement the catalog as a first-class backend concept while keeping scanner adapters boring. This should expand metadata around tools without changing scan behavior yet.

```text
SCOPE: Add backend Tool Catalog types and registry helpers without changing scanner execution behavior.
REQUIRED READING:
1. docs/tool-catalog.md
2. docs/tool-catalog-current-scanners.md
3. src/security_observatory/scanners.py
4. src/security_observatory/model.py
5. src/security_observatory/cli.py
OUTPUT: Code changes that introduce typed catalog metadata, enforceable policy/capability fields, derived safety labels, install-state enums, and a helper that returns catalog entries for current scanners. Keep existing scanner_catalog() compatibility or provide a careful migration path.
OPEN QUESTIONS:
- Should catalog metadata live in Python constants first, or move to a JSON/YAML file once the shape stabilizes?
- How will backend policy fields prevent Agent Lab or future UI actions from treating risky tools as ordinary actions?
```

## Step 2.2 — Expose catalog and install-state API data

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Give the dashboard a backend surface for catalog browsing. Installation and removal can stay future work, but the API should already expose enough to render an app-store style page.

```text
SCOPE: Add read-only API support for Tool Catalog entries and install state.
REQUIRED READING:
1. src/security_observatory/dashboard_server.py
2. src/security_observatory/scanners.py
3. dashboard-ui/src/dashboardData.ts
4. docs/tool-catalog.md
OUTPUT: API and TypeScript data-shape changes that let the dashboard fetch catalog items with detection-backed install state, policy fields, derived safety labels, pack membership, and coming-soon state. Include a fallback so old summaries still render.
OPEN QUESTIONS:
- Should catalog data live under /api/summary at first or get a separate /api/tool-catalog endpoint?
- Which fields must come from real detection rather than static metadata?
```

## Step 3.1 — Document Tool Catalog and Security Packs

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 3.2

Make the concept understandable to future agents and to Christian. The docs should explain why this is more than a list of binaries.

```text
SCOPE: Write the canonical docs for the Tool Catalog and Security Packs vocabulary.
REQUIRED READING:
1. docs/tool-catalog.md
2. docs/tool-catalog-current-scanners.md
3. README.md
4. docs/architecture.md
OUTPUT: Update docs/tool-catalog.md and add any needed README references. Explain Tool Catalog, Security Packs, DëvSec-managed installs, detected installs, optional Docker, policy-derived safety labels, and Coming Soon external surface placeholders in plain language. State the MVP invariant that External Surface is display-only.
OPEN QUESTIONS:
- What is the shortest product sentence that explains why this matters?
```

## Step 3.2 — Verify import, API shape, and stale metadata risks

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 3.1

Check that the new catalog layer did not disturb scanning and that stale catalog metadata cannot make the dashboard lie about coverage.

```text
SCOPE: Validate the Tool Catalog foundation and its install-state truth model.
REQUIRED READING:
1. .adx/commands.json
2. src/security_observatory/scanners.py
3. src/security_observatory/dashboard_server.py
4. dashboard-ui/src/dashboardData.ts
OUTPUT: Run the fast Python import check from .adx/commands.json. If TypeScript files changed, run dashboard lint. Add or run focused contract checks for detected vs managed vs missing vs unavailable vs coming-soon states. Summarize any validation failures and the remaining risk around stale tool metadata.
OPEN QUESTIONS:
- Does scanner availability still come from real system checks rather than catalog optimism?
- Are safety labels consistently derived from policy fields rather than duplicated UI text?
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the DëvSec Tool Catalog Foundation campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/tool-catalog-foundation.md
Campaign: campaigns/tool-catalog-foundation.md

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
