# Honeygraph 2 of 2 — Tripwire Bridge + Confirmation Loop

> This is the exciting part, and it only works if part 1 proved out. It hides a fake "bait" password right next to your project's most valuable spot — the one part 1's map flagged as most dangerous. If an intruder ever grabs the bait, DëvSec instantly lights up exactly where they are and what they can reach, turning a vague "you might have a problem here" into "someone is poking around right here." Part 1 is what makes the bait land in the right place.

## Scope

Wire DëvSec's honeytoken engine to the asset graph from Campaign 1: bind a decoy to the highest-consequence node, and when that decoy is touched, flip the case at that node into a live incident and illuminate the blast-radius path the intruder is on. DëvSec is uniquely positioned for this — it already owns *both* a findings engine and a honeytoken engine in one local store, and the plant-and-trigger plumbing already exists (`build_decoy_snippets`, `/api/honey/trigger`, the `honey_incidents` lifecycle). What's missing is the bridge: honeytokens are currently free-floating, with zero link to any finding or case. This campaign adds that link (`asset_node_id`), a new `active_incident` case state, the trigger→case→path loop, and the glowing graph view. It also confronts head-on the two things that gate real value — the trigger endpoint is local (`127.0.0.1`, unreachable by a real attacker) and decoys are written into local repo files, not deployed surfaces — and is honest that a trip proves *intrusion near a node*, not *exploitation of a specific finding*. Done means the loop runs end-to-end on one repo with an honest verdict on whether it earns its keep, for the user it's actually for: the indie/solo dev shipping an internet-exposed service.

## Context (locked decisions)

- **This is Campaign 2 of 2. Do NOT start it until Campaign 1 is merged and its Step 3.2 returned GO.** Campaign 1 is the trust-gate; this campaign builds the deception loop on top of its graph. A NO-GO from Campaign 1 means stop — the loop collapses without a trustworthy graph.
- **A tripped decoy proves "an adversary is inside this region and took the bait" — NOT "this specific finding was exploited."** Every label, reason string, and piece of copy must say "confirmed intrusion near this node / on this path." The real value is the blast-radius illumination for incident response; the "confirms a specific finding" framing outruns the logic and must not ship.
- **Honeytokens are free-floating today** — zero link to any finding or case. The bridge is a brand-new `asset_node_id` column on `honey_keys` linking a key to the graph node it guards.
- **Placement is human-in-the-loop.** DëvSec *suggests* the top-consequence node and the decoy content; a human confirms before anything is planted. Never auto-plant on an inferred or low-confidence node. The existing planting code already refuses to overwrite real files and restricts to safe decoy paths — keep those rails.
- **The local-trigger gap is real and must be faced, not papered over.** Today the trigger endpoint is the local dashboard (`127.0.0.1:8876`) and decoys land in local repo files — a remote attacker can reach neither. For a trip to mean "real external attacker," the decoy must live in a deployed surface and the trigger must be reachable. This campaign draws that boundary explicitly and builds only the smallest honest piece; it does not fake an internet deploy.
- **Re-aim the audience.** The loop pays off for someone with deployed, exposed assets worth attacking and the capacity to act on a live alert — the indie/solo dev shipping an internet-exposed service, not the offline-repo hobbyist. Don't oversell it for purely local code.
- **`active_incident` is a new top action_level — and the enum is a closed set in two places.** It must be added to BOTH `model.py` `SecurityCase.__post_init__` AND `priority.py` `ACTION_LEVELS`, or an unknown value silently falls back to "verify" and the new state vanishes.
- **Reuse, don't rebuild:** the `honey_incidents` IR lifecycle already exists; the loop opens an incident, it doesn't invent a new lifecycle.
- **Self-recalibrating Step 0.1:** this campaign was authored before Campaign 1 was built, so assumed schema names, field names, and paths will drift. Step 0.1 reads current `main` and trues up the later step prompts in place before any implementation.
- **Branch:** `honeygraph-tripwire` off `main` (after Campaign 1 has merged). Merge to `main` when Final review is APPROVED.
- **Out of scope (deferred):** the liveness/credential-revalidation prober (Layer 5 — highest-maintenance, lowest-priority; reuse existing validator rule sets if ever built, don't hand-roll). A live internet deploy of decoys.

## Unattended execution contract

This campaign runs fully unattended via `/claude-automate` — a chain of headless `claude --print` sessions, guarded by a watchdog, with no human at the keyboard. Every step MUST honor this contract or the run can stall for hours:

- **No interactive input, ever.** No step may pause for a prompt, confirmation, login, or `[y/N]` — there is no TTY to answer it.
- **Servers bind `127.0.0.1` only — never `0.0.0.0`/LAN.** A non-loopback listener triggers the macOS firewall "accept incoming connections?" dialog, which no flag can suppress and which blocks the whole run until someone clicks it. Use `--host 127.0.0.1` / `HOST=127.0.0.1`.
- **No blocking GUI/OS dialog.** Don't trip first-run macOS permission panels (screen recording, accessibility, Automation, Full Disk Access) or Gatekeeper. Strip quarantine from any downloaded binary (`xattr -dr com.apple.quarantine`); prefer brew/npm/uv over ad-hoc downloads.
- **No interactive auth.** No `gh auth login`, `ghost login`, MitID, or MCP `authenticate` mid-run — any credential a step needs must already be in place before launch.
- **Keep writes under the repo / `~/Dev`.** Avoid `~/Desktop`, `~/Documents`, `~/Downloads` (they trip macOS privacy prompts) unless Full Disk Access is pre-granted to the launcher.
- **A blocker means `fail` loudly, never `wait`.** If a prerequisite is missing, call `claude-automate fail` with a one-line reason so the watchdog escalates — never hang waiting for a human.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 0 — Recalibrate to what Campaign 1 actually shipped

- [ ] Step 0.1 — True up this plan against delivered Campaign 1

### Phase 1 — Wire decoys to the graph

- [ ] Step 1.1 — Bind a honey key to an asset node + suggest top-consequence placement
- [ ] Step 1.2 — Add the active_incident state (a closed enum in two places)

### Phase 2 — Close the loop

- [ ] Step 2.1 — Trigger → flip the case → light the path
- [ ] Step 2.2 — Confront the local-trigger gap honestly

### Phase 3 — Show it and prove it

- [ ] Step 3.1 — The blast-radius graph view
- [ ] Step 3.2 — End-to-end proof + honest verdict
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 0.1 — True up this plan against delivered Campaign 1

Model: Opus 4.8 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

This campaign was written before Campaign 1 existed. Read what actually shipped and edit the later step prompts in place so paths, schema names, and field names match reality — and confirm the GO gate.

```text
SCOPE: Reconcile this campaign with delivered Campaign 1. Edit Steps 1.1–3.2 in place to match real paths/schema/field names, and confirm Campaign 1's GO verdict.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py  (the asset_nodes / asset_edges schema as built; honey_keys schema ~441-456)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/priority.py  (the consequence boost + ACTION_LEVELS as built)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/model.py  (SecurityCase consequence field + the action_level enum in __post_init__)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/honey_keys.py  (build_decoy_snippets ~134; current key-creation flow)
5. campaigns/honeygraph-1-asset-graph/notes/consequence-vs-severity.md  (the GO/NO-GO gate)

OUTPUT:
- An audit note at campaigns/honeygraph-2-tripwire-loop/notes/0.1-recalibration.md: what Campaign 1 named things vs what this plan assumed, line by line.
- In-place edits to Steps 1.1–3.2 (REQUIRED READING, ACCEPTANCE, OPEN QUESTIONS, Model/Parallel) so they reference real, current paths and names. May merge or split steps; may NOT add a phase or weaken intent.

ACCEPTANCE:
- Every later step references real, current file paths and schema/field names.
- The recalibration note exists and names each change made.
- If Campaign 1's gate is NO-GO (or missing), this step calls it out at the top of the note and fails loudly via `claude-automate fail` — do not build the loop on an untrustworthy graph.

OPEN QUESTIONS: did Campaign 1 actually deliver crown-jewel reachability, or only dependency reachability? If only the latter, the "plant at the worst node" story is weaker — note exactly how that reshapes Phase 1 (you may be guarding a high-consequence dependency surface, not a datastore).

FORWARD SWEEP: you are the forward sweep for this campaign — leave every downstream step truthful to current main before any code is written.
```

## Step 1.1 — Bind a honey key to an asset node + suggest top-consequence placement

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.2

Add the `asset_node_id` link (brand-new column) and extend decoy minting so a key is bound to the node Campaign 1 flagged as worst — proposed to a human, never auto-planted.

```text
SCOPE: Add asset_node_id to honey_keys and a "suggest placement at the top-consequence node" surface that mints + binds a decoy for human confirmation. Keep all existing planting safety rails.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py  (honey_keys schema ~441-456 — add asset_node_id + migration)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/honey_keys.py  (build_decoy_snippets ~134; key material)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py  (honey create + planting ~2640-2801 — the no-overwrite / safe-path rails to keep; /api/honey routes)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_honey_keys.py

OUTPUT:
- asset_node_id column on honey_keys (+ migration) linking a key to an asset node.
- A "suggest placement" surface: given Campaign 1's consequence ranking, propose the top-consequence node + the decoy content for human confirmation. Keep existing rails: refuse to overwrite real files, restrict to safe decoy paths, gate advanced placement.
- Never auto-plant on a weak/low-confidence node — require explicit confirmation.
- Receipt to campaigns/honeygraph-2-tripwire-loop/receipts/1.1-bind-decoy-to-node.md

ACCEPTANCE:
- A honey key carries the node it guards.
- The existing planting safety rails are intact (no overwrite, safe paths).
- Placement is proposed, not performed, until a human confirms.
- Tests: key binds to a node; the suggestion picks the top-consequence node; a weak-confidence node is not offered for auto-placement.

OPEN QUESTIONS: if Campaign 1 delivered only dependency reachability (no datastore nodes), what IS the "worst node" to guard? Surface this — it may mean guarding a high-consequence dependency surface instead of a data store.

FORWARD SWEEP: if the binding column name or the suggestion payload differs from what 2.1 and 3.1 assume, true up their prompts now.
```

## Step 1.2 — Add the active_incident state (a closed enum in two places)

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.1

Introduce `active_incident` as the new top action_level. The validated enum lives in two files — miss one and the value is silently swallowed.

```text
SCOPE: Add active_incident as the top action_level (above fix_now) for a case with a confirmed intrusion near its node.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/model.py  (the action_level validation in SecurityCase.__post_init__ ~163 — a closed set with a SILENT fallback to "verify")
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/priority.py  (ACTION_LEVELS ~12 and _attention_rank ~214 — the second place the set lives)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py  (the ordering map {fix_now:0,...} ~201)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_priority.py

OUTPUT:
- Add active_incident to the action_level set in BOTH model.py __post_init__ AND priority.py ACTION_LEVELS. (Reminder: this set is validated in two places; an unknown value silently becomes "verify" — miss one and the new state disappears.)
- Place active_incident above fix_now in every ordering map (_attention_rank, the cases.py ordering dict, and any UI severity/level map).
- Receipt to campaigns/honeygraph-2-tripwire-loop/receipts/1.2-active-incident-state.md

ACCEPTANCE:
- active_incident is a first-class top state, not silently coerced to verify.
- It sorts above fix_now everywhere cases are ordered.
- No existing action_level behavior changes.
- Tests: a case set to active_incident survives __post_init__ and sorts to the very top.

OPEN QUESTIONS: is there dashboard code (filters, color/label maps) that hard-codes the four-value set? Find and extend it, or the new state renders blank.

FORWARD SWEEP: if you touched any shared ordering/label map, confirm 2.1 (which sets the state) and 3.1 (which renders it) still line up.
```

## Step 2.1 — Trigger → flip the case → light the path

Model: Opus 4.8 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

The payoff. When a honey key fires, map its node to the case at that node, flip it to `active_incident`, and illuminate the blast-radius path — using Campaign 1's edges. Be precise about what this proves.

```text
SCOPE: On a honey_key_event, resolve asset_node_id → the case at that node, set it to active_incident, open an incident, and compute the reachable path. Honest language throughout.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py  (/api/honey/trigger handler ~2350; honey_key_events write)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py  (honey_key_events / honey_incidents ~458-496; asset_edges traversal)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/honey_keys.py  (event recording)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py  (flip a case's action_level; attach incident context)

OUTPUT:
- On a honey_key_event, resolve asset_node_id → the finding/case at that node, set that case to active_incident, and open a honey_incident (reuse the existing IR lifecycle).
- Compute the blast-radius path from the tripped node (reachable nodes via asset_edges) and attach it to the incident.
- Honest language everywhere: "confirmed intrusion near this node / on this path" — NOT "this finding is proven exploited." A trip proves an adversary reached this region and took the bait, not that this specific vulnerability was the entry vector.
- Receipt to campaigns/honeygraph-2-tripwire-loop/receipts/2.1-confirmation-loop.md

ACCEPTANCE:
- A trip flips the correct case to active_incident and opens an incident.
- The illuminated path is real graph data, not a guess.
- No copy claims the specific finding was exploited — only intrusion near/along the path.
- Tests: trigger on a bound node flips exactly that case; trigger on an unbound key records the event without a false case flip; the path uses real edges.

OPEN QUESTIONS: if multiple cases sit at or near the tripped node, which flips — the nearest, or all on the path? Surface the rule rather than guessing.

FORWARD SWEEP: if the incident/path payload shape differs from what 3.1 renders and 3.2 asserts, true up those prompts.
```

## Step 2.2 — Confront the local-trigger gap honestly

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The architectural truth. The trigger endpoint is local and decoys land in local files — a real attacker reaches neither. Draw the boundary and build only the smallest honest piece. No overclaiming, no fake deploy.

```text
SCOPE: Decide and document how external confirmation actually works, and implement the smallest headless-safe piece — without a live internet deploy.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py  (/api/honey/trigger + open routes; how the decoy points at the trigger URL)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/honey_keys.py  (build_decoy_snippets — the trigger_url/open_url baked into the decoy ~134-172)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/AGENTS.md  (local-first promise; safe_base_url 127.0.0.1:8876; the External-Surface MVP-safety line — do not imply it's active)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/mcp/README.md  (how external / IR actions are framed and guarded)

OUTPUT:
- A design note at campaigns/honeygraph-2-tripwire-loop/notes/2.2-external-confirmation-boundary.md: for a trip to mean "real external attacker," the decoy must live in a deployed/exposed surface AND the trigger must be reachable. Lay out the honest options (deploy-the-decoy + a reachable trigger collector vs a documented manual path) and pick one.
- The smallest honest implementation WITHOUT a live internet deploy: e.g. a "deployed-decoy placement mode" that mints the decoy configured with a reachable trigger URL (config/placeholder, not a live host), plus docs. Everything stays bound to 127.0.0.1 locally.
- A plain statement of where local-first ends and operator action begins. Do not imply External Surface is live or that a local trip equals an internet attacker.
- Receipt to campaigns/honeygraph-2-tripwire-loop/receipts/2.2-external-confirmation-boundary.md

ACCEPTANCE:
- The note draws a clear line: what DëvSec automates vs what the operator must do for real external confirmation.
- Any implemented piece stays headless-safe (no live deploy, no 0.0.0.0, no credentials/dialogs).
- No surface overclaims that a local trip equals a remote attacker.

OPEN QUESTIONS: is a reachable trigger collector even in scope for a local-first tool, or is the honest MVP "we mint and bind; you deploy and point it at your collector"? Recommend — don't silently decide.

FORWARD SWEEP: if the boundary you draw changes what 3.2's end-to-end demo can claim, true up 3.2's acceptance now.
```

## Step 3.1 — The blast-radius graph view

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 3.2

Build the graph view the concept promised — now that the graph and the loop exist. Nodes glow by consequence; a tripped decoy lights its path. (This is the visualization deferred from Campaign 1.)

```text
SCOPE: A dashboard graph view — nodes sized/colored by consequence, crown jewels marked, and an active_incident path highlighted from the tripped node. Add a graph library (none is installed today).

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/package.json  (React 19 + Vite; NO graph/network lib is installed — add a suitable one)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/dashboardData.ts  + /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/uiTypes.ts  (carry nodes/edges/consequence/incident path to the UI)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/App.tsx  (where a new view mounts)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py  (expose a graph payload: nodes, edges, consequence, active-incident path)

OUTPUT:
- A graph payload endpoint (nodes + edges + consequence + any active-incident path).
- A dashboard graph view: nodes sized/colored by consequence, crown jewels marked, an active_incident path highlighted from the tripped node.
- Honest empty states: no graph data, no crown jewels, no incident.
- Receipt to campaigns/honeygraph-2-tripwire-loop/receipts/3.1-graph-view.md

ACCEPTANCE:
- The view renders from real payload data, not placeholders.
- A tripped decoy visibly lights its blast-radius path.
- Performance is sane on a realistic node count (don't naively render thousands of DOM nodes).
- `cd dashboard-ui && npm run lint` and `cd dashboard-ui && npm run build` pass.

OPEN QUESTIONS: which graph lib fits a local-first, bundle-conscious React 19 app (react-flow vs cytoscape vs a light force layout)? Pick the lightest that does glow + path-highlight; justify the choice briefly in the receipt.

FORWARD SWEEP: confirm the graph payload field names match what 2.1 emits; if you reshaped anything server-side, note it for 3.2.
```

## Step 3.2 — End-to-end proof + honest verdict

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 3.1

Demonstrate the whole loop on one repo, then judge honestly whether it earns its keep — for the exposed-service user, not the offline hobbyist.

```text
SCOPE: Drive the loop end-to-end (headless-safe, against 127.0.0.1) and write an honest verdict separating what it proves from what it doesn't.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py  (the trigger handler)
2. campaigns/honeygraph-2-tripwire-loop/receipts/2.1-confirmation-loop.md
3. campaigns/honeygraph-2-tripwire-loop/notes/2.2-external-confirmation-boundary.md
4. campaigns/honeygraph-1-asset-graph/notes/consequence-vs-severity.md  (what the graph could actually promise)

OUTPUT:
- Drive the loop end-to-end against 127.0.0.1: mint + bind a decoy at the top-consequence node, simulate a trigger, confirm the case flips to active_incident and the path lights up.
- A verdict note at campaigns/honeygraph-2-tripwire-loop/notes/3.2-loop-verdict.md: what this proves (plumbing + IR illumination near a node) vs what it does not (a real external attacker, a deployed surface). Does the loop earn its surface vs the existing case list, and for whom?
- Receipt to campaigns/honeygraph-2-tripwire-loop/receipts/3.2-end-to-end-proof.md

ACCEPTANCE:
- The simulated trip flips the right case and lights the right path, observed end-to-end (not just asserted in a unit test).
- The verdict separates "confirmed intrusion near node" from "finding proven exploited" — no overclaim survives.
- An honest "earns its keep for whom" conclusion that names the user it's for (the indie/solo dev shipping an exposed service).

OPEN QUESTIONS: if the demo only proves local plumbing (no external trip is possible in this environment), say so — and state exactly what a real external validation would require before the claim ships.

FORWARD SWEEP: last step — instead of a forward sweep, make sure the verdict note is honest and unambiguous, since it's what a reader will judge the whole Honeygraph bet on.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the Honeygraph 2 of 2 — Tripwire Bridge + Confirmation Loop campaign.

Plan: campaigns/honeygraph-2-tripwire-loop.md
Campaign: campaigns/honeygraph-2-tripwire-loop.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff that the criteria actually landed. Don't trust step receipts — read the diff.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas. Pay special attention to: any copy that claims a tripped decoy proves a specific finding was exploited (it must only claim intrusion near/along the path); active_incident added to only one of the two enum locations; auto-planting on a low-confidence node; the loop flipping the wrong case; and any implication that a local 127.0.0.1 trip equals a real external attacker.

Be honest. Lean. APPROVED if every step's acceptance criteria landed and there are no cross-step regressions or overclaims. NEEDS WORK if any step cut corners, a primitive was bypassed, or the honesty boundary was crossed.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.8 with Extra High thinking
(Your call — both are acceptable for this kind of cross-file review.)
```

**Verdict-to-action mapping:**

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign"). The Honeygraph build is complete.
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick the checkbox until APPROVED.
