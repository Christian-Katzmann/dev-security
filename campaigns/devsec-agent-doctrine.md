# 2 · DëvSec agent — voice doctrine and safety tiers

> Decides how the DëvSec security helper talks and behaves when an AI uses it. The helper will sound calm and precise — like a flight controller, not a chatbot or a movie hacker — and will openly explain what it will and won't do, and why. This is the bedrock everything else builds on.

## Scope

Establish DëvSec's agent personality across two related-but-distinct dimensions:

- **Voice doctrine** (`docs/agent-voice.md`) — *how* the agent communicates. Lead with status, bind authority to evidence, calm urgency proportional to risk, plain language, ordered procedures, no shame, no theatrics. Adapted from a frontier-model source draft (`campaigns/devsec-agent-doctrine/notes/source-doctrine.md`), customized to DëvSec's actual primitives.
- **Safety tiers** (`docs/agent-safety.md`) — *what* the agent will and won't do. Six risk tiers from "read scan history (no warning)" through "modify the security store (refuse by default, explain why, require explicit insistence)" through "install scanners (refuse, defer to user)." Each tier specifies default behavior + the language template for explaining the refusal or proceeding.

Both docs become the source of truth for the MCP server's `instructions` field (every connecting agent reads it), for every existing and future `/devsec-*` slash command, and for a new `/devsec-voice` command that lets users read the doctrine on demand.

Done when: both docs exist and are DëvSec-grounded, the MCP server's `instructions` field carries the compact distillation, every existing `/devsec-*` slash command references the doctrine in its body, a `/devsec-voice` slash command exposes the doctrine summary, and a fresh-session manual run confirms the agent's actual output follows the voice.

## Context (locked decisions)

- **Two docs, not one.** `docs/agent-voice.md` (HOW the agent talks) and `docs/agent-safety.md` (WHAT it will do). They cross-reference each other but stay separate — different questions deserve different artifacts.
- **The source doctrine is a draft, not canonical.** `campaigns/devsec-agent-doctrine/notes/source-doctrine.md` is the input. Phase 1 produces the customized canonical version. Specific harmonization tasks are listed in the source doctrine's preface block.
- **DëvSec's actual vocabulary leads.** The 11 case categories (`secrets`, `dependencies`, `ai-risk`, `iac`, `platform-posture`, `workflow`, `install-hooks`, `behavioral-drift`, `silent-upgrade`, `supply-chain-ioc`, `code-security`), four `action_level` values (`fix_now` / `verify` / `watch` / `info`), and five `severity` levels (`critical` / `high` / `medium` / `low` / `info`) all appear in DëvSec output today. The doctrine harmonizes the source's CRITICAL/HIGH/MEDIUM/LOW with this dual axis.
- **Dual-axis lead format: `Action: <action_level> · Severity: <severity>`.** Canonical opening for any finding output. Both axes always shown. The middle dot `·` (U+00B7) separator is intentional — visually distinct from a hyphen. See `campaigns/devsec-agent-doctrine/notes/calibration-examples.md` for the format in worked examples (#1, #2, #3 show the dual axis in action).
- **Read-only MCP boundary is non-negotiable.** The voice doctrine cannot promise behaviors the architecture can't deliver. Lines in the source like *"DËVSEC will mark this resolved..."* must be softened — the agent does not modify the security store, it surfaces what's true and tells the user how to act.
- **Safety tiers map to real boundaries.** Tier 1 (Read) and Tier 2 (Activate scan via Bash) are unproblematic. Tier 3+ (modify code, modify security store, touch Honey Keys, install scanners) all need explicit language templates the agent uses to surface trade-offs. The safety doc owns this taxonomy; the voice doctrine owns the *tone* of the refusal.
- **The MCP `instructions` field is the universal entry point.** Every MCP client reads it on connect. The compact distillation goes there — it must be short (~30 lines max) and reference the full doc for depth.
- **No emoji exceptions, with one named carve-out.** The voice doctrine forbids emoji. The single exception is `⚠` for actively triggered Honey Keys (a genuine incident-response moment). Documented in the doctrine so future maintainers don't generalize.
- **This campaign runs AFTER `/devsec-power-commands` ships.** Voice doctrine then applies to all 8 slash commands (5 existing + 3 new). If `/devsec-power-commands` hasn't shipped when this campaign runs, the Phase 2 prompt covers the 5 existing commands and the 3 new ones get the doctrine baked in as they're written.
- **Local-first identity surfaces in the voice.** The doctrine acknowledges DëvSec's stance: "your data did not leave the machine" appears where relevant in agent responses about findings, scope, and posture.
- **Honey Key trigger gets its own pattern.** The source doctrine has nine interaction patterns (A–I) but none for "an active defense decoy fired." Add a Pattern J: Honey Key trigger response — the most operationally serious event DëvSec can surface.
- **Pattern F kept but reshaped as "Security Brief."** Same five-part skeleton (Posture / Primary risk / Practical consequence / Decision needed / Next operational step) tuned for solo-to-low-end-corporate shareability — plain-language consequence framing, honest scope statement at the bottom, no corporate jargon (no "business impact," no "stakeholders," no "alignment"). Target audience: a developer who occasionally needs to share status with their team or a non-technical co-founder. Should pass low-end corporate without rolling eyes; should pass solo-developer-Slack without sounding bloated. The audience assumption "DëvSec is for individuals" was wrong — we don't know that yet, and the Security Brief is the shape that doesn't force us to commit. Calibration-examples.md #10 is the target shape — match it.
- **Citations are decoration, not operational.** The source doctrine's bibliographic citations belong with the source draft. Strip them from `docs/agent-voice.md` — the agent doesn't need them; humans who want them can read the source.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Customize and codify the doctrine

- [x] Step 1.1 — Write `docs/agent-voice.md` (DëvSec-customized voice doctrine)
- [x] Step 1.2 — Write `docs/agent-safety.md` (six risk tiers + language templates)

### Phase 2 — Wire the doctrine into agent surfaces

- [x] Step 2.1 — Update MCP `instructions` field + all existing `/devsec-*` slash commands to reference the doctrine
- [x] Step 2.2 — Add `/devsec-voice` slash command + add it to `/devsec`'s commands menu

### Phase 3 — Verify with a real run

- [x] Step 3.1 — Manual run-through in a fresh Claude Code session; calibrate prompts if observed output drifts from doctrine
- [x] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Write `docs/agent-voice.md`

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.2

Produce the canonical DëvSec voice doctrine at `docs/agent-voice.md`. The source draft (`campaigns/devsec-agent-doctrine/notes/source-doctrine.md`) is the starting point; do not copy it verbatim — harmonize with DëvSec's actual primitives and remove what overpromises or doesn't fit the audience.

Required harmonizations (from the source's preface block, restated here for the agent):

1. **Dual severity axis.** Use both `action_level` (fix_now / verify / watch / info — user-facing call, leads) AND `severity` (critical / high / medium / low / info — technical impact, accompanies). Show worked examples of both appearing in agent output.
2. **The 11 case categories.** Re-ground examples in DëvSec's actual category vocabulary (`secrets`, `dependencies`, `ai-risk`, `iac`, `platform-posture`, `workflow`, `install-hooks`, `behavioral-drift`, `silent-upgrade`, `supply-chain-ioc`, `code-security`). At least one worked example per top-frequency category.
3. **Read-only MCP boundary.** Soften any language that promises mutating behavior the MCP can't deliver. Cross-reference `docs/agent-safety.md` for what the agent will and won't do.
4. **Local-first stance.** Add a short section: "Local-first as a voice element" — when a finding is surfaced, the agent can plainly note that the data did not leave the machine. This is part of DëvSec's identity, not marketing.
5. **Pattern J: Honey Key trigger response.** Add a new interaction pattern alongside the source's A–I. Honey Keys are DëvSec's active defense surface; a triggered key is the most operationally serious event. The pattern should follow the source's structure (Template + Example) and emphasize: (a) calm clarity that this is a real signal, (b) the `⚠` emoji exception is allowed here, (c) ordered containment steps, (d) the explicit "review provider access logs, do not assume breach without log evidence" boundary.
6. **Reshape Pattern F as "Security Brief."** Keep the five-part skeleton (Posture / Primary risk / Practical consequence / Decision needed / Next operational step). Strip corporate jargon — no "stakeholders," no "alignment," no "business impact" (use "practical consequence" instead). Add an honest scope statement at the bottom. Target audience: a solo developer who occasionally needs to share status with their team or a non-technical co-founder. Calibration-examples.md #10 is the target shape — match it.
7. **Strip bibliographic citations.** The source's footnotes belong with the source. The operational doc the agent reads should not be cluttered with academic references.
8. **The "Compact system-prompt version" at the end of the source is the seed for the MCP `instructions` field.** Keep it in the doctrine as Section 9 (or similar), but mark clearly: "This is the version that goes into the MCP server's `instructions` field. Edit with care — every connecting agent reads it."

Acceptance criteria:

- `docs/agent-voice.md` exists, under 600 lines (the source is ~550 lines including citations — trimming citations alone should leave room; Pattern F stays as the Security Brief).
- Contains the five load-bearing principles, the technique table, the voice profile, the before/after transformations table, all 10 interaction patterns (A through J, with F reshaped as the Security Brief), the anti-patterns table, the final voice guide, and the compact system-prompt version.
- At least one worked example per high-frequency case category (`secrets`, `dependencies`, `ai-risk`, `code-security`).
- Includes the dual-axis vocabulary explainer (action_level + severity together).
- Includes the local-first voice element section.
- Includes Pattern J for Honey Key triggers.
- No bibliographic citations.
- Pattern F appears as "Security Brief" (renamed and reshaped per the locked decision), matching calibration-examples.md #10.
- Cross-references `docs/agent-safety.md` where the voice covers refusal scenarios.

Commit: one clean commit, `Add DëvSec agent voice doctrine`. Co-author line per repo convention. Do not push.

```text
/skill-creator

SCOPE: Produce docs/agent-voice.md — the canonical DëvSec voice doctrine. Adapt the source draft to DëvSec's actual primitives (case categories, action_level + severity dual axis, read-only MCP boundary, local-first stance, Honey Keys). Reshape Pattern F as the Security Brief (target shape: calibration-examples.md #10). Strip bibliographic citations.

REQUIRED READING:
1. campaigns/devsec-agent-doctrine/notes/source-doctrine.md (the source draft — read its preface block first, it lists the harmonization tasks)
2. campaigns/devsec-agent-doctrine/notes/calibration-examples.md — 10 worked examples that ARE the voice's ground truth. The doctrine's own worked examples should match this tone, density, and structure. If the doctrine drifts from these examples, the doctrine is wrong.
3. src/security_observatory/cases.py — the SecurityCase shape, the 11 category vocabulary in _PLAYBOOK_BY_CATEGORY, the action_level values
4. src/security_observatory/model.py — Finding shape, severity vocabulary
5. PROVOCATION.md — the local-first argument; the voice should reflect it
6. docs/threat-model.md — what DëvSec protects and what it doesn't; voice should match this honesty
7. docs/honey-keys.md (if it exists) — Honey Key design rationale for Pattern J
8. mcp/README.md — current MCP surface; voice doctrine must not promise behaviors the MCP can't deliver

OUTPUT: docs/agent-voice.md, under 600 lines, customized per the locked decisions block in this campaign. One git commit, do not push.

OPEN QUESTIONS:
- The compact system-prompt version goes into the MCP `instructions` field (Step 2.1). How short can it be while still load-bearing? Aim for under 50 lines — the field is read on every connect.
- Pattern J (Honey Key trigger) needs to balance "this is real, act now" with "do not assume breach without provider log evidence." The source's Pattern A (Critical finding) is the closest template — adapt, don't copy.
- Local-first as a voice element: is it a section or just a sentence sprinkled into worked examples? Lean: short dedicated section (under 100 words) plus targeted appearances in examples where relevant (scope statements, residual-risk notes).
- The dual-axis vocabulary format is LOCKED: `Action: <action_level> · Severity: <severity>` as the canonical lead. See calibration-examples.md #1, #2, #3 for the format in worked examples. Introduce the convention in Principle 1, use it in every finding-shape worked example. Do not invent a different format.

The source doctrine is well-written and largely right. Most of the work is harmonization, not rewriting. Resist the urge to restructure the source's five principles — they're load-bearing. The customization is in the examples, the dual-axis vocabulary, the read-only boundary acknowledgement, and the additions (local-first, Pattern J).
```

## Step 1.2 — Write `docs/agent-safety.md`

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.1

Produce `docs/agent-safety.md` — the six-tier risk model for what the agent will and won't do, and the language templates for each tier's default behavior. This is the WHAT to the voice doctrine's HOW.

Required structure:

1. **One-paragraph orientation.** Why a security tool needs an explicit risk-tier model for agents. (Most don't have one; the result is silent refusals or silent acceptance — both bad.)
2. **The six tiers, each as a subsection:**
   - **Tier 1 — Read** (no warning). Examples: query cases, findings, dependency trust, playbooks, Honey Key state. Default: just do it.
   - **Tier 2 — Activate existing capability** (do it with brief context). Examples: shell out to `security-scan` via Bash. Default: do it, plainly note "this is the same as you running it in terminal."
   - **Tier 3 — Modify code outside the security store** (proceed with normal review flow). Examples: open a PR via `/devsec-pr`, edit a file per a playbook. Default: proceed — the PR review is the gate.
   - **Tier 4 — Modify the security store** (refuse by default; explain; require explicit insistence). Examples: delete a case, mark accepted_risk via direct SQLite. Risk: corrupts source of truth, no audit trail, indistinguishable from cover-up.
   - **Tier 5 — Touch defensive instrumentation** (refuse harder; require two confirmations). Examples: generate/remove Honey Keys, ack triggers without investigation. Risk: tampering with active defense during a real incident is how you blind yourself.
   - **Tier 6 — Install scanners or modify dep state** (refuse; defer to user). Examples: run the installer, `brew install`, `pipx install`. Risk: arbitrary code execution via package manager supply chain.
3. **Language templates per tier.** Each tier specifies HOW the agent surfaces its decision, in the doctrine's voice. Tier 4 example template: *"This would modify the local security store directly. Specifically: [what changes]. Trade-off: [risk]. The MCP is read-only by design; the safer path is [dashboard/CLI path]. If you want me to proceed anyway, confirm with: '[explicit confirmation phrase]'."*
4. **Cross-reference to the voice doctrine** for tone. The safety doc owns the taxonomy; the voice doctrine owns how refusals sound.
5. **Honest caveat section.** LLMs follow instructions strongly but not absolutely. Hard guarantees come from what tools don't exist (the MCP not having write tools — physically can't). The risk-tier doc is the UX of communicating that boundary, not the boundary itself.

Acceptance criteria:

- `docs/agent-safety.md` exists, under 300 lines (this is a taxonomy doc, not a manual).
- All six tiers defined with examples + default behavior + language template.
- Cross-references `docs/agent-voice.md` for tone of refusals.
- Includes the honest caveat about LLM enforcement.
- Examples are DëvSec-grounded: real case categories, real MCP boundaries, the actual `security-scan` CLI.

Commit: one clean commit, `Add DëvSec agent safety tiers`. Co-author line per repo convention. Do not push.

```text
/skill-creator

SCOPE: Produce docs/agent-safety.md — the six-tier risk-tier model for agent behavior when using DëvSec. Defines what the agent will do silently, what it does with context, what it refuses by default, and the language templates for each tier's response.

REQUIRED READING:
1. mcp/README.md — the read-only boundary and hard rejections
2. mcp/SESSION-PROMPT.md — the original scope discipline, especially the "Hard rejections" section
3. docs/threat-model.md — the broader DëvSec threat model; risk-tier model is downstream of this
4. .adx/risks.json — existing risk register for the repo (different audience — humans editing the codebase — but useful framing)
5. PROVOCATION.md — local-first stance; safety tiers reinforce why mutating actions stay user-side

OUTPUT: docs/agent-safety.md, under 300 lines. One git commit, do not push.

OPEN QUESTIONS:
- Tier 4 (modify security store) and Tier 5 (touch defensive instrumentation): should the "explicit confirmation phrase" be the same across tiers, or different? Lean: different — Tier 4 wants something like "Yes, write to the store anyway," Tier 5 wants something like "Yes, modify the defensive instrumentation despite the risk." Different phrases enforce a moment of pause.
- For Tier 6 (install scanners): how strongly should the agent refuse? The risk is supply-chain — package managers can be compromised. But running `security-scan` itself isn't Tier 6 (that's Tier 2). Tier 6 is specifically the installer or new scanner installation. Suggest: agent should NOT attempt; should print the exact command the user should run and let the user execute it.
- Honest caveat section placement: at the top (sets context before the tiers) or at the bottom (lands after the user understands the tiers)? Lean: bottom — it's a meta-point about LLM behavior that's better understood once the tiers are clear.

This doc should be short and structurally clear. Six tiers, each with a tight definition + example + default behavior + language template. The taxonomy is the artifact; long discussion belongs in the voice doctrine.
```

## Step 2.1 — Wire the doctrine into existing surfaces

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Apply the doctrine to all agent-facing surfaces: the MCP `instructions` field and every existing `/devsec-*` slash command body. This is a cross-cutting consistency pass.

Two artifact families to update:

**A. MCP server `instructions` field.**

- Edit `src/security_observatory/mcp_server.py`. Find the `FastMCP("devsec", instructions=...)` constructor call.
- Replace the current short instructions with the compact distillation from `docs/agent-voice.md` (Section 9 — the "Compact system-prompt version").
- Keep it under 50 lines. The field is read on every client connection; bloat costs token budget for every user.
- Add a one-line pointer to `docs/agent-voice.md` and `docs/agent-safety.md` so agents and humans can find the full versions.
- Update the existing test that checks the `instructions` value if any. Likely none, but check.

**B. Each `/devsec-*` slash command body.**

For each of these files in `~/.claude/commands/`:
- `devsec.md`
- `devsec-brief.md`
- `devsec-cases.md`
- `devsec-fix.md`
- `devsec-deps.md`
- `devsec-diff.md` (if `/devsec-power-commands` shipped)
- `devsec-pr.md` (if `/devsec-power-commands` shipped)
- `devsec-honey.md` (if `/devsec-power-commands` shipped)

Add a "Voice" section near the bottom of each command body, before the "Rules" section, with heading `## Voice` and this consistent paragraph:

`This command speaks in DëvSec's operational voice — calm, evidence-bound, action-oriented, no theatrics. See docs/agent-voice.md for the full doctrine; the short version: lead with status, bind every claim to evidence, give the next concrete action, and never overstate certainty.`

Where a command implies an action that crosses safety tiers (`/devsec-pr` crosses Tier 3; future write commands would cross Tier 4+), add a brief tier-aware note pointing to `docs/agent-safety.md`.

Acceptance criteria:

- MCP `instructions` field updated; the JSON-RPC `initialize` response includes the new instructions string. Verify with the stdio one-shot pattern from the original session.
- All five (or eight, if power-commands shipped) `/devsec-*` slash commands have a "Voice" section referencing `docs/agent-voice.md`.
- Tier-aware notes added where commands cross safety tiers.
- The `mcp_server.py` change has tests — at minimum, the `test_server_lists_expected_tools` test should still pass; consider adding a small `test_server_instructions_references_doctrine` that asserts the field contains a recognizable substring.

Commit: one clean commit in the repo, `Wire voice doctrine into MCP instructions and slash command bodies`. Slash command edits are not version-controlled in this repo (they live in `~/.claude/`) and are not part of the commit.

```text
/skill-creator

SCOPE: Apply docs/agent-voice.md and docs/agent-safety.md to all agent-facing surfaces — the MCP server's `instructions` field (in src/security_observatory/mcp_server.py) and the bodies of every existing /devsec-* slash command in ~/.claude/commands/.

REQUIRED READING:
1. docs/agent-voice.md (delivered by Step 1.1 — the doctrine being applied)
2. docs/agent-safety.md (delivered by Step 1.2 — referenced for tier-aware notes)
3. src/security_observatory/mcp_server.py — the create_server function; find the FastMCP() constructor and its instructions kwarg
4. tests/test_mcp_server.py — existing pattern for asserting things about the FastMCP server instance
5. ~/.claude/commands/devsec*.md — all existing slash commands; read them all to understand the consistent shape before editing

OUTPUT:
- src/security_observatory/mcp_server.py — instructions field updated with the compact doctrine distillation + pointers to the docs
- tests/test_mcp_server.py — optional small test asserting the instructions reference the doctrine
- mcp/README.md — note in the connection-instructions section that the MCP advertises the voice doctrine; reference docs/agent-voice.md
- ~/.claude/commands/devsec*.md — all updated with a "Voice" section
- One git commit (only the repo files; slash command edits aren't in the repo)

OPEN QUESTIONS:
- How long is "compact" for the MCP instructions field? Aim 30-50 lines. Anything longer is too much for every-connect overhead.
- Should the Voice section in each slash command be identical text, or tailored per command? Lean: identical for consistency. The doctrine doesn't change per command; pointing to the same doc keeps maintenance trivial.
- Tier-aware notes: which existing commands cross safety tiers? /devsec-fix (gives playbooks — Tier 1, no note needed). /devsec-pr (opens PR — Tier 3, brief note about review-as-gate). /devsec-diff, /devsec-cases, /devsec-deps, /devsec-brief, /devsec-honey (all read-only — Tier 1, no note needed). So only /devsec-pr gets a tier note in the existing set.
- If /devsec-power-commands has NOT yet shipped, only the five original commands need updating. Note in the implementation report which case applied.
```

## Step 2.2 — Add `/devsec-voice` slash command

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Add a new `/devsec-voice` slash command at `~/.claude/commands/devsec-voice.md`. When invoked, it prints a tight summary of the voice doctrine and safety tiers — the user-facing way to ask "why does this agent talk like that?" Also adds a row to `/devsec`'s commands menu.

Behavior:

- No arguments. Prints the doctrine summary directly.
- Format: a short intro paragraph + a compact reference table covering the five voice principles + a compact reference table covering the six safety tiers + a one-line pointer to the full docs (`docs/agent-voice.md` and `docs/agent-safety.md`).
- Cap output at 50 lines. This is a primer, not the full doctrine — anyone who wants depth reads the docs.

Also update `/devsec`:

- Add a row to its commands menu table for `/devsec-voice`.
- One-line description: "You want to understand how DëvSec's agent voice works — the doctrine, the safety tiers, why refusals are explained the way they are."

Acceptance criteria:

- `~/.claude/commands/devsec-voice.md` exists, follows the existing `/devsec-*` frontmatter convention (name + description, no argument-hint needed).
- Output under 50 lines.
- Cross-references the full docs.
- `~/.claude/commands/devsec.md` updated with the new row in the commands menu table.

```text
/skill-creator

SCOPE: Write a new slash command at ~/.claude/commands/devsec-voice.md that prints a tight summary of the voice doctrine and safety tiers. Then update ~/.claude/commands/devsec.md's commands menu to surface it.

REQUIRED READING:
1. docs/agent-voice.md (delivered by Step 1.1)
2. docs/agent-safety.md (delivered by Step 1.2)
3. ~/.claude/commands/devsec.md (the home dashboard — for the menu update + tone reference)
4. ~/.claude/commands/devsec-fix.md (closest sibling — also a "reference printer" command)

OUTPUT:
- ~/.claude/commands/devsec-voice.md (new file)
- ~/.claude/commands/devsec.md (one row added to the commands menu table)

OPEN QUESTIONS:
- Should /devsec-voice accept an argument to filter (e.g., /devsec-voice safety to show only safety tiers)? Lean: no for v1. Add only if the unfiltered output is too long. Cap is 50 lines — should fit comfortably.
- Where in the /devsec menu table to add the new row? Lean: at the bottom — it's a meta/reference command, not a daily-use one.

This is a small, focused command. The body is mostly compact tables and pointers to the docs. The hardest part is what to leave OUT — the full doctrine doesn't belong in this command's output; this is the primer that points to it.
```

## Step 3.1 — Manual verification and calibration

Model: Manual run-through; Sonnet 4.6 · High / GPT-5.5 · High for any prompt edits the verification reveals
Parallel: NO

End-to-end verification that the voice doctrine actually shows up in agent output. Slash command instructions are only as good as what the model actually does with them — observed output is the truth.

Procedure:

1. **Start a fresh Claude Code session** (or `/restart`). This is non-optional — MCP servers and slash commands are loaded at session start; this session's caches are stale.
2. **Run each command and observe:**
   - `/devsec` — does the dashboard land in the doctrine's voice? Are the section headers crisp? Is the calm-urgency principle visible?
   - `/devsec-brief` — three bullets in the voice. Status leads. Specific action surfaces.
   - `/devsec-cases` — table format. No emoji except `⚠` for triggered Honey Keys (and only if any exist). Plain-English risk reads.
   - `/devsec-fix secrets` — the playbook renders. The agent's framing around the playbook follows the doctrine.
   - `/devsec-deps <repo>` — dependency table with low-trust callouts in the doctrine's voice.
   - `/devsec-voice` — the primer renders. Doctrine + tiers in a compact reference.
   - If `/devsec-power-commands` shipped: `/devsec-diff`, `/devsec-pr` (dry-read only, no actual PR), `/devsec-honey`.
3. **Note drift.** If observed output uses casual language ("oops," "looks like," "let's see…"), uses emoji outside the carve-out, hedges with "potentially could possibly," or makes promises the architecture can't keep — capture the specific output and the command it came from.
4. **Calibrate.** For each drift instance: edit the responsible slash command body (or, if it's a doctrine gap, edit `docs/agent-voice.md`) to add a more specific instruction. Re-run that command. Confirm drift is gone.
5. **Stop iterating when:** every command's first-paragraph output is recognizable as the DëvSec voice. Perfect calibration is impossible (LLMs vary); good-enough is when a reader who knows the doctrine would identify the output as following it.

Acceptance criteria:

- Every command was run in a fresh session.
- Observed drift instances are documented in a short report (paste into `campaigns/devsec-agent-doctrine/notes/observed-output.md` for future reference).
- Calibration edits made where drift was found.
- Re-runs confirm calibrated output follows the doctrine.

No commit gate here — calibration edits to slash commands are out-of-repo. If `docs/agent-voice.md` was edited during calibration, that's a small repo-side commit: `Calibrate voice doctrine after observed-output review`.

```text
/verify

SCOPE: Manual end-to-end verification that the DëvSec voice doctrine actually shows up in agent output after Phase 2 wired it in. Calibrate slash command prompts or the doctrine itself if observed output drifts.

REQUIRED READING:
1. docs/agent-voice.md (the doctrine being verified)
2. docs/agent-safety.md (the safety tiers being verified)
3. All ~/.claude/commands/devsec*.md files (the surfaces being verified)

PROCEDURE: 
1. Open a fresh Claude Code session in this repo.
2. Run each /devsec-* slash command. Capture the first 10-15 lines of output.
3. Compare against the doctrine. Note any drift (casual language, missing status-first framing, hedging, etc.).
4. Edit the responsible surface (slash command body, MCP instructions, or doctrine itself if it's a doctrine gap).
5. Re-run that command. Verify drift is gone.
6. Write a short report to campaigns/devsec-agent-doctrine/notes/observed-output.md — for each command, the observed output, any drift noted, the calibration made.

ACCEPTANCE: Every command's first-paragraph output is recognizable as the DëvSec voice. Drift instances documented and calibrated. If doctrine itself was edited, one small commit.

OPEN QUESTIONS:
- How sensitive should calibration be? Perfect adherence is impossible (LLMs vary across runs). Aim: a reader who knows the doctrine would identify the output as following it. Not: identical wording across runs.
- If observed drift is consistent across multiple commands, the issue is the doctrine or the MCP `instructions` field, not the individual command. Calibrate at the higher level, not per-command.
- If a command's first output is in voice but later output (after follow-up questions) drifts, that's a doctrine application problem the slash command body can't easily solve — note it for a future pass, don't try to over-engineer the prompt now.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the devsec-agent-doctrine campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-agent-doctrine.md
Campaign: campaigns/devsec-agent-doctrine.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff (for Phase 1 docs and Phase 2's MCP edits) and the actual files in ~/.claude/commands/ (for Phase 2 and 3 slash-command work) that the criteria actually landed. Don't trust step receipts — read the diff and read the files.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas. Specifically watch for:

- Did docs/agent-voice.md actually drop the bibliographic citations? Did it reshape Pattern F as the "Security Brief" (calibration-examples.md #10) — five-part skeleton, plain-language consequence framing, honest scope statement, no corporate jargon? Did it add Pattern J for Honey Key triggers?
- Did the dual-axis vocabulary (action_level + severity) actually show up in worked examples, not just in the explainer section?
- Did docs/agent-safety.md cover all six tiers with examples + default behavior + language template?
- Does the MCP instructions field carry the compact distillation, and is it under 50 lines?
- Do all existing /devsec-* slash commands have a Voice section pointing to docs/agent-voice.md?
- Does /devsec-pr (if it exists) carry the Tier 3 note pointing to docs/agent-safety.md?
- Does the /devsec dashboard's commands menu include the new /devsec-voice row?
- Was the manual verification actually done? Is campaigns/devsec-agent-doctrine/notes/observed-output.md present and substantive?

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
