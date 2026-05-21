# Managed Security Packs

> Give DëvSec curated bundles of security tools that people can understand and adopt safely. First prove pack status, install previews, ownership tracking, and one reversible managed install before broad pack installation.

## Scope

This campaign builds Security Packs and the first safe managed-install proof on top of the Tool Catalog. Done means DëvSec can define curated packs, show what each pack contains, detect what is already available, preview what installation would do, prove ownership tracking with one low-risk managed install/uninstall path, avoid removing user-owned tools, and keep Docker as optional rather than required.

## Context (locked decisions)

- Tool Catalog is for individual tools with pages.
- Security Packs are curated bundles of tools/plugins/apps for specific purposes.
- MVP real packs are Starter Pack, Secrets Pack, Dependencies Pack, and AI Agent Pack.
- Coming Soon packs are IaC Pack, Platform Posture Pack, Advanced Dependency Pack, and External Surface Pack.
- Packs are not runnable in MVP. Scan profiles remain the only execution surface; packs recommend, describe, and install capability.
- DëvSec should provide batteries-included scanner capability, not merely advise users to install tools manually.
- Native managed installs are the default path; Docker is optional for tools that benefit from isolation or are painful to install natively.
- Uninstall only removes tools DëvSec installed or manages. Existing system tools are detected but not deleted.
- MVP pack pages are read-first: curated explanation, status, missing tools, recommended scans, and install previews before full pack install/uninstall.
- `DESIGN.md` is the canonical Mistglass design system for dashboard UI work. The pack mockups under `temporaty design mockups/` are useful wireframe references, especially the curated pack rhythm and restrained illustrated card ideas.
- Broad pack install/uninstall, Docker-backed installs, and high-risk tool install paths are deferred.
- External Surface Pack is a Coming Soon pack in this campaign.
- External Surface is display-only in MVP: no target input, no domain probing, no active recon, and no agent-triggered external scans.

## Prerequisites

- Tool Catalog Foundation has defined catalog policy fields, derived safety labels, install states, and Tool Catalog vs Security Pack vocabulary.
- Tool Catalog Storefront owns individual tool browsing and tool detail pages; this campaign owns pack pages and pack preview flows.
- A first managed install proof target must be chosen in Phase 1 before backend install/uninstall coding begins.
- Existing scan profiles remain the only execution surface for MVP.
- Root `DESIGN.md` has been read before pack UI implementation begins.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Pack strategy

- [x] Step 1.1 — Define first-party Security Packs
- [x] Step 1.2 — Design install ownership and uninstall rules

### Phase 2 — Managed install proof

- [x] Step 2.1 — Add install preview and ownership tracking
- [x] Step 2.2 — Implement one safe managed install path
- [x] Step 2.3 — Wire pack install status into scans

### Phase 3 — Pack UX and verification

- [x] Step 3.1 — Build pack pages and preview flows
- [x] Step 3.2 — Validate installs without overheating the machine
- [x] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Define first-party Security Packs

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.2

Turn the pack names into a concrete catalog: what each pack is for, which tools it includes, and which ones are intentionally deferred.

```text
/human-centered-design

SCOPE: Define the first-party DëvSec Security Packs.
REQUIRED READING:
1. docs/tool-catalog.md
2. docs/tool-catalog-current-scanners.md
3. docs/scanners.md
4. src/security_observatory/scanners.py
OUTPUT: Add docs/security-packs.md with real MVP packs for Starter Pack, Secrets Pack, Dependencies Pack, and AI Agent Pack; add Coming Soon entries for IaC Pack, Platform Posture Pack, Advanced Dependency Pack, and External Surface Pack. Include purpose, included tools, policy-derived safety labels, expected runtime, plain-English benefit, and the rule that packs are curated capability bundles, not runnable execution modes in MVP. State that External Surface is display-only.
OPEN QUESTIONS:
- Which Coming Soon packs should be visible by default versus tucked behind an Advanced label?
- Which scan profiles should each real pack recommend?
```

## Step 1.2 — Design install ownership and uninstall rules

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.1

This is the safety heart of the catalog. DëvSec must know the difference between “I found this on your Mac” and “I installed this for you.”

```text
/architecture-health-forensic

SCOPE: Design safe install ownership and uninstall rules for DëvSec-managed tools.
REQUIRED READING:
1. .adx/risks.json
2. docs/setup.md
3. install-security-observatory.sh
4. docs/adding-scanners.md
5. docs/tool-catalog.md
OUTPUT: Add an install ownership section to docs/tool-catalog.md or docs/security-packs.md covering managed copies, detected system tools, install locations, uninstall boundaries, version checks, update checks, no-Docker defaults, and the first allowed low-risk managed install target. Lock the proof target before any implementation step starts.
OPEN QUESTIONS:
- Should managed tools live under ~/.security-observatory/tools, ~/.local/bin, uv tool, Homebrew, or a mixed strategy by tool type?
- Should ownership tracking live in SQLite, a local manifest, or both?
- Which exact tool is the first proof target, and what makes it safe enough?
```

## Step 2.1 — Add install preview and ownership tracking

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Represent installs as plans before executing them. The app should be able to say what it would do, what it owns, and what it will leave alone, without installing a whole pack yet.

```text
SCOPE: Add install preview generation and ownership tracking for Tool Catalog entries.
REQUIRED READING:
1. docs/tool-catalog.md
2. docs/security-packs.md
3. src/security_observatory/scanners.py
4. src/security_observatory/storage.py
5. src/security_observatory/dashboard_server.py
OUTPUT: Backend changes that generate install previews for individual tools and packs, record DëvSec-managed ownership metadata locally, and distinguish managed, detected, missing, unavailable, and built-in tools. Do not implement broad pack install/uninstall or a generic installer framework here.
OPEN QUESTIONS:
- Which exact evidence proves a tool is DëvSec-managed rather than merely detected on PATH?
```

## Step 2.2 — Implement one safe managed install path

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Add one reversible managed install path, not the whole universe. This is the proof that DëvSec can safely own a tool without taking over the user's machine.

```text
SCOPE: Implement one safe backend install/uninstall proof for a low-risk DëvSec-managed tool.
REQUIRED READING:
1. .adx/risks.json
2. docs/security-packs.md
3. src/security_observatory/dashboard_server.py
4. install-security-observatory.sh
5. .adx/commands.json
OUTPUT: API changes for one approved low-risk install path, uninstall for DëvSec-owned copies only, and status refresh. Enforce ownership boundaries, no sudo by default, clear errors, timeouts, and no removal of detected system tools. Leave broad pack install, high-risk tools, and Docker-only paths disabled.
OPEN QUESTIONS:
- Which current tool is the safest first proof target without using the existing broad installer?
```

## Step 2.3 — Wire pack install status into scans

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Connect packs to existing scan profiles without making pack installation a hidden requirement or inventing a second scan mode. Missing tools should remain evidence gaps, not mysterious failures.

```text
SCOPE: Connect Security Pack status to scan profiles and evidence gap messaging.
REQUIRED READING:
1. src/security_observatory/scanners.py
2. src/security_observatory/cases.py
3. src/security_observatory/dashboard_server.py
4. dashboard-ui/src/dashboardData.ts
OUTPUT: Backend and data-shape changes so scan profiles can point to their recommended packs, scanner gaps can recommend the relevant pack/tool page, and installed pack state improves scanner doctor messaging. Keep existing scan profiles as the only execution path for MVP; do not add a “run pack” mode.
OPEN QUESTIONS:
- How should pack pages explain which scan profile to run after installing missing capability?
```

## Step 3.1 — Build pack pages and preview flows

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Make packs feel like curated security kits, not dependency bundles. The user should understand the job the pack does, what is already available, and what DëvSec would install before any install happens.

```text
/frontend-design

SCOPE: Build Security Pack pages and install-preview flows in the dashboard.
REQUIRED READING:
1. docs/security-packs.md
2. docs/tool-catalog-storefront.md
3. DESIGN.md
4. dashboard-ui/src/App.tsx
5. dashboard-ui/src/dashboardData.ts
6. dashboard-ui/src/index.css
7. temporaty design mockups/stitch_d_vsec_tool_marketplace (2)/screen.png
8. temporaty design mockups/stitch_d_vsec_tool_marketplace/screen.png
9. temporaty design mockups/stitch_d_vsec_tool_marketplace (3)/screen.png
OUTPUT: UI changes that show pack pages for real MVP packs, Coming Soon pages/cards for deferred packs, included tools, missing/detected/managed status, install preview, one safe managed install proof path if available, uninstall controls for managed proof tools only, and no “run pack” execution mode. Use the pack mockup for page rhythm and the dark mockup only for illustrated card inspiration or future dark-mode thinking. Avoid visual clutter and avoid implying that unavailable tools already ran.
OPEN QUESTIONS:
- Should pack pages live inside Tool Catalog or have their own Packs section?
```

## Step 3.2 — Validate installs without overheating the machine

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

Test the install workflow carefully. The point is not to install everything; the point is to prove the flow is bounded, honest, and reversible.

```text
SCOPE: Validate pack status, install preview, and one managed install proof with minimal machine impact.
REQUIRED READING:
1. .adx/risks.json
2. .adx/commands.json
3. docs/security-packs.md
4. DESIGN.md
5. src/security_observatory/dashboard_server.py
6. dashboard-ui/src/App.tsx
7. temporaty design mockups/stitch_d_vsec_tool_marketplace (2)/screen.png
OUTPUT: Run fast import checks and any focused unit/manual checks added by the campaign. Validate at least one preview path, one missing-tool state, one uninstall-protected detected-tool state, and the one managed install proof if it is safe in the current environment. Do not run broad installers, full pack installs, Docker installs, or full scans unless Christian explicitly approves.
OPEN QUESTIONS:
- Which test proves DëvSec will not uninstall a user-owned system tool?
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the Managed Security Packs campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/managed-security-packs.md
Campaign: campaigns/managed-security-packs.md

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
