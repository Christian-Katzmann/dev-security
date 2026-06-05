# Honeygraph 1 of 2 — Asset Graph + Consequence Re-Ranking

> Right now DëvSec shouts about every possible security problem at the same volume. This builds a map of how the pieces of your project connect, then uses that map to push the findings that can actually reach your most valuable stuff to the top — and quietly hush the ones that lead nowhere. It is also the honesty test: if the map can't be made trustworthy on a real project, we stop here and never build part 2.

## Scope

Build the asset graph (nodes + edges) that DëvSec has never had, then re-rank security cases by *reachable consequence* instead of severity label. Today every cited "signal" DëvSec collects is a flat inventory — `sbom_components`, `dependency_manifest_entries`, component fingerprints, rotation surfaces are all lists with no relationships, and Checkov's resource graph is parsed and thrown away. This campaign turns the nodes (nearly free from existing data) into a confidence-scored graph by recovering the edges scanners already compute but DëvSec discards, then folds a "reaches a crown jewel" consequence signal into the existing priority engine. Done means: a real repo's consequence-ordered top-10 is demonstrably truer than its severity-ordered top-10, with a written GO/NO-GO verdict that gates Campaign 2. This is the trust-gate: if the graph mis-ranks, the whole Honeygraph idea collapses and we don't proceed.

## Context (locked decisions)

- **This is Campaign 1 of 2. Start here.** Campaign 2 (Tripwire Bridge + Confirmation Loop) depends entirely on this campaign producing a *trustworthy* graph. Do not start Campaign 2 until this campaign's final step returns GO.
- **Nodes are nearly free; edges are the whole job.** DëvSec already identifies components, secrets, surfaces, and IaC resources, but stores zero relationships. The work is recovering edges: the dependency graph (currently discarded from SBOM output) and IaC resource relationships (currently discarded from Checkov — `normalize.py` keeps only `failed_checks`).
- **Confidence on every node and edge.** Reuse DëvSec's existing honesty vocabulary (`unknown` / `weak` / `strong`). Never invent certainty. Consequence carries the *weakest* confidence along its path.
- **"Crown jewels" are human-labeled, never inferred.** No signal DëvSec collects implies which data store matters. A committed repo-local file declares them; absent file = no crown jewels = graceful, not a crash.
- **Re-ranking plugs into the existing boost precedent.** `priority.py` already promotes a case's `action_level` across buckets via `_with_dependency_trust` (~line 121). A consequence booster mirrors it: append a plain-English reason to `priority_reasons`, promote on a trustworthy path, **never auto-promote on a low-confidence edge**, and never hide a high-severity finding.
- **Ranking today is 4 categorical buckets + a severity-label tiebreak** (`cases.py` ordering ~line 198). Consequence becomes a finer tiebreak within buckets — additive. Findings with no consequence data must rank exactly as they do today.
- **Be honest about what this proves.** Dependency reachability re-ranking is *table-stakes* (cloud ASPM tools do it) — its edge here is "local-first, for individuals." The novel blast-radius-to-crown-jewel signal needs the IaC/resource edges and a labeled crown jewel. The validation step must say which signal actually fired.
- **Local-first promise intact:** SQLite stays the source of truth, default scans stay offline-capable, no new network dependency.
- **Branch:** `honeygraph-asset-graph` off `main`. Merge to `main` when Final review is APPROVED. Shared seam files with Campaign 2 — `priority.py`, `cases.py`, `model.py`, `storage.py`: Campaign 2 builds on this campaign's *merged* result, so finish and merge here first.
- **Out of scope (deferred):** the glowing graph visualization (Campaign 2), the liveness/credential-revalidation prober (deferred indefinitely — highest-maintenance, lowest-priority).

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

### Phase 1 — Build the asset graph (nodes + structural edges)

- [x] Step 1.1 — Asset-graph schema + node derivation
- [x] Step 1.2 — Recover dependency edges (the graph scanners discard)
- [x] Step 1.3 — Recover IaC resource edges (Checkov's discarded graph)

### Phase 2 — Rank by reachable consequence

- [x] Step 2.1 — Crown-jewel labels + reachability scoring
- [x] Step 2.2 — Consequence boost in the priority engine

### Phase 3 — Surface it, then prove it (the gate)

- [x] Step 3.1 — Show "why this ranks here" in the dashboard
- [x] Step 3.2 — Prove the re-rank is truer (the trust-gate for Campaign 2)
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Asset-graph schema + node derivation

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Lay the foundation DëvSec has never had: two new SQLite tables and node derivation from data the scanner already stores. Edges arrive in 1.2/1.3 — this step is the node set and the edge-table shape.

```text
SCOPE: Create the asset-graph foundation — asset_nodes and asset_edges tables plus scan-time node derivation from data DëvSec already collects.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py  (the CREATE TABLE block ~108-210: findings, sbom_components, dependency_manifest_entries; the migration pattern lower in the file)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/sbom.py  (component identity/fingerprint ~43-66 — reuse as node identity)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/recency.py  (enumerate_rotation_surfaces ~118 — secret-bearing surfaces become nodes)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py  (how findings cluster into cases ~190-205 — node identity must line up with case grouping)
5. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_storage_migrations.py  (the migration test pattern to follow)

OUTPUT:
- asset_nodes table: id, scan_id, repo_name, node_type (secret|component|resource|datastore|endpoint), identity_key (reuse component_fingerprint / package_key / surface path), label, is_crown_jewel (default 0; set by humans in 2.1), confidence (unknown|weak|strong), created_at, FK to scans.
- asset_edges table: id, scan_id, src_node_id, dst_node_id, edge_type (unlocks|depends_on|reachable_from|stored_in), confidence, reason (plain English), created_at.
- Scan-time node derivation: components from sbom_components; secrets from gitleaks/trufflehog findings + rotation surfaces; IaC resources from checkov findings; coarse endpoints only where cheaply known.
- A migration so existing DBs gain the tables with no data loss.
- Receipt to campaigns/honeygraph-1-asset-graph/receipts/1.1-asset-graph-schema-and-nodes.md

ACCEPTANCE:
- Nodes tie to scan_id + repo, mirroring findings/sbom_components.
- Every node and edge carries unknown|weak|strong confidence — never invented certainty.
- Adding the tables does not change existing scan / finding / case / dashboard behavior.
- A scan with no SBOM and no IaC still produces a valid (smaller) node set, not a crash.
- Tests: schema creation, node derivation from a fixture scan, stable identity for same component/version, distinct identity on version change.

OPEN QUESTIONS:
- What is the minimal node_type set Phase 2's consequence signal actually traverses? Don't add node types nothing will use.
- Should endpoints be in scope for the MVP at all, or deferred until something produces them? Surface, don't assume.

FORWARD SWEEP: before checking this step off, scan the remaining step prompts. If your schema names or node identity differ from what 1.2/1.3/2.1 assume, make a surgical edit to those prompts now — a quick pass, not a rewrite.
```

## Step 1.2 — Recover dependency edges (the graph scanners discard)

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: NO

DëvSec runs Syft/CycloneDX but keeps only a flat component list — the dependency relationships in that same output are parsed and thrown away. Stop discarding them.

```text
SCOPE: Parse the SBOM dependency graph (CycloneDX `dependencies`, Syft relationships) into asset_edges as depends_on edges. This is the cheapest, most universal edge source.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/sbom.py  (where SBOM JSON becomes flat components today)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/normalize.py  (normalizer patterns)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/asset_graph.py  (1.1 delivered: `AssetEdge`, `EDGE_TYPES`, `derive_asset_nodes`; component node identity_key = `component_fingerprint`)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py  (1.1 delivered: `replace_asset_edges(scan_id, repo_name, edges)` resolves `AssetEdge` endpoints by identity_key; `list_asset_nodes`; how sbom_components are written in `save_scan`)
5. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_sbom.py  (fixture + assertion style)

FROM 1.1 (use, don't rebuild): emit `asset_graph.AssetEdge(src_identity_key, dst_identity_key, edge_type='depends_on', confidence, reason)` addressed by component `component_fingerprint`, then persist via `db.replace_asset_edges(...)` — it maps identities to the node ids already stored for the scan and skips edges whose endpoints don't exist (no duplicate nodes). Confidence vocab is `unknown|weak|strong`.

OUTPUT:
- Parse CycloneDX `dependencies` (and Syft relationship data when present) into depends_on edges between existing component nodes.
- Confidence-score edges: a declared dependency is strong; a heuristic/inferred link is weak.
- Edges tie to the same scan as their nodes and reference existing asset_nodes by identity (no duplicate nodes).
- Receipt to campaigns/honeygraph-1-asset-graph/receipts/1.2-dependency-edges.md

ACCEPTANCE:
- A vulnerable transitive package can be traced through depends_on edges back to a direct dependency.
- SBOMs without a dependency block still parse (flat nodes, no edges), not a crash.
- No double-counting: edges reference nodes from 1.1, they don't mint new ones.
- Tests with a real CycloneDX fixture: direct deps, transitive deps, missing/partial dependency block.

OPEN QUESTIONS: which SBOM formats DëvSec actually produces carry the dependency graph vs only a component list? Note real coverage honestly — it bounds how universal this signal is.

FORWARD SWEEP: if the depends_on edge shape or confidence words differ from what 2.1's reachability assumes, true up 2.1's prompt now.
```

## Step 1.3 — Recover IaC resource edges (Checkov's discarded graph)

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The Checkov normalizer keeps only `failed_checks` and discards Checkov's resource graph. These resource edges are load-bearing: dependency edges connect component→component, but only resource edges let a *secret* node reach a *datastore* node — which is what makes "blast radius to a crown jewel" mean anything.

```text
SCOPE: Recover Checkov's resource relationships into asset_edges (reachable_from / stored_in). Conditional on the repo having IaC.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/normalize.py  (the _checkov parser ~285-301 — today only failed_checks)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/scanners.py  (the checkov command builder ~926 — may need a json/graph output flag)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/asset_graph.py  (1.1 delivered: `derive_asset_nodes` is the single node-derivation seam; today it mints only COARSE file-level `resource` nodes (identity_key = IaC file path, confidence `weak`) and NO `datastore` nodes — `datastore` is a valid node_type but reserved for this step. `AssetEdge`, `EDGE_TYPES` incl. `reachable_from`/`stored_in`.)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py  (1.1 delivered: nodes are derived inside `save_scan` via `derive_asset_nodes`; edges persist via `replace_asset_edges`)
5. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_sbom.py  (fixture style to mirror for a checkov graph fixture)

FROM 1.1 (use, don't rebuild): to get real per-resource and `datastore` nodes (not just the coarse file-level `resource` nodes 1.1 mints), EXTEND `derive_asset_nodes` so richer Checkov resource data flows into it — keep node derivation in that one function so `save_scan` stays the single derivation path. Then add `reachable_from`/`stored_in` edges via `replace_asset_edges` (it resolves endpoints by identity_key alone, so give resource and datastore nodes distinct identity_keys). Confidence vocab is `unknown|weak|strong`.

OUTPUT:
- Extend the Checkov invocation/parse to retain resource identity + cross-resource references (file_abs_path, resource_id, references between resources).
- Emit reachable_from / stored_in edges between resource and datastore/secret nodes, confidence-scored.
- Repos without IaC produce no resource edges — correct, not a failure, and no implied coverage.
- Receipt to campaigns/honeygraph-1-asset-graph/receipts/1.3-iac-resource-edges.md

ACCEPTANCE:
- At least one realistic "resource references a data store" relationship becomes a stored_in/reachable_from edge.
- Repos with no IaC are unaffected (no edges, no crash).
- Checkov failures/timeouts still yield a partial scan.
- Tests with a Terraform/IaC fixture showing a resource→datastore relationship becoming an edge.

OPEN QUESTIONS: Checkov's graph output is far less standardized than SBOM. If a clean resource graph isn't actually available from the JSON DëvSec already collects, say so and scope to what IS available rather than forcing a brittle parse. This is the riskiest edge source — budget a rework cycle.

FORWARD SWEEP: if resource/datastore node types or edge types changed, true up 2.1's reachability prompt.
```

## Step 2.1 — Crown-jewel labels + reachability scoring

Model: Opus 4.8 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Let a human mark which nodes are crown jewels, then compute — for each finding's node — whether it can reach one through the graph, plus a coarse blast-radius size. This is the consequence signal the whole product rests on.

```text
SCOPE: Human-labeled crown jewels + graph traversal that scores each finding's node by reachable consequence, confidence-aware.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py  (asset_nodes/asset_edges from Phase 1; the is_crown_jewel column; read the graph via `list_asset_nodes(scan_id, repo_name)` / `list_asset_edges(...)`)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/asset_graph.py  (node identity_key reuses existing identities: component = `component_fingerprint`, secret = file path, resource/datastore = IaC resource address; confidence vocab `unknown|weak|strong`)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py  (case ↔ node identity; where a consequence field attaches ~340-395)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/model.py  (SecurityCase ~141-180 — add a consequence field cleanly)
5. campaigns/honeygraph-1-asset-graph/receipts/1.1-asset-graph-schema-and-nodes.md  (the delivered schema)

FROM 1.1: crown jewels are matched by node `identity_key` — `.devsec/crown-jewels.json` lists identity_keys (and ideally node_type to disambiguate), and a scan-time pass sets `asset_nodes.is_crown_jewel = 1` where they match. The graph is read back with `list_asset_nodes` / `list_asset_edges`; both carry `confidence`, so the weakest-link rule walks edge + node confidence together.

OUTPUT:
- A committed, human-edited `.devsec/crown-jewels.json` (node identities) read at scan time. No interactive prompt (unattended-safe); absent file = no crown jewels = graceful.
- Traversal: per finding node, compute reaches_crown_jewel (bool + min hop distance + the path) and blast_radius (count of reachable nodes), each carrying the weakest-link confidence along the path.
- Persist a consequence summary per case (reaches_crown_jewel, distance, blast_radius, path, confidence).
- Receipt to campaigns/honeygraph-1-asset-graph/receipts/2.1-crown-jewel-reachability.md

ACCEPTANCE:
- Crown jewels are human-set, never inferred.
- Consequence carries the lowest confidence on its path (one weak edge ⇒ weak consequence).
- No crown jewels labeled ⇒ consequence is "unknown", not "zero", and not a crash.
- Tests: strong-path reach; only a weak-confidence path exists; no crown jewels labeled; node unreachable to any crown jewel.

OPEN QUESTIONS: what's the honest blast-radius metric for the MVP — hop distance, reachable-node count, or both? Pick the simplest that makes the top-10 truer; don't over-engineer a score nobody can read.

FORWARD SWEEP: if the consequence field name/shape differs from what 2.2 and 3.1 assume, true up their prompts now.
```

## Step 2.2 — Consequence boost in the priority engine

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Fold consequence into ranking by mirroring the boost pattern that already exists — promote on a trustworthy path, with a reason a non-coder can read, and break ties by consequence finer than the severity label.

```text
SCOPE: A consequence booster in priority.py modeled on _with_dependency_trust, plus consequence as a tiebreak in case ordering. Additive — never a silent override.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/priority.py  (decide_action_level ~26-71; the _with_dependency_trust boost precedent ~121-142; ACTION_LEVELS ~12; _attention_rank ~214)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py  (case ordering ~198-205 — action_level bucket then severity label)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/model.py  (priority_reasons list on SecurityCase; the `consequence` field 2.1 added)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_priority.py  (boost test patterns)

FROM 2.1 (use, don't rebuild): each `SecurityCase` now carries a `consequence` dict (or `None` when the case maps to no graph node — those must rank EXACTLY as today). Shape: `{reaches_crown_jewel: bool, distance: int|None, blast_radius: int, confidence: "unknown"|"weak"|"strong", crown_jewels_defined: bool, path: [...], crown_jewel: {...}|None}`. The confidence vocab is `unknown|weak|strong` — there is NO "medium" tier. The weakest-link rule already collapsed the whole path to one confidence, so the booster reads `consequence["confidence"]` directly.

OUTPUT:
- A consequence booster: `reaches_crown_jewel` on a STRONG path (`confidence == "strong"`) can raise action_level (e.g. verify→fix_now); a `weak` path may add a reason but must NOT auto-promote; `unknown`/`None` consequence changes nothing.
- A plain-English reason appended to priority_reasons, e.g. "This finding's API key can reach the customer database in 2 hops, so it outranks higher-severity findings that reach nothing." (The path + distance + crown_jewel label for the sentence are all on the `consequence` dict.)
- Consequence breaks ties within an action_level bucket (finer than the severity-label tiebreak), without overriding severity — order by reaches_crown_jewel, then path confidence, then nearer distance, then larger blast_radius.
- Receipt to campaigns/honeygraph-1-asset-graph/receipts/2.2-consequence-boost.md

ACCEPTANCE:
- Consequence can raise attention and re-order, but never hides a high-severity finding.
- Every boost has a reason a non-coder can read.
- Findings with no consequence data rank exactly as today — pure additive change, no regression.
- Never auto-promotes on a low-confidence edge.
- Tests: strong-path reach boosts; weak path does not; no-consequence case unchanged.

OPEN QUESTIONS: should consequence ever DEMOTE (hush) a high-severity finding that reaches nothing, or only promote? Demotion is higher-risk — surface the call and default to promote-only for the MVP.

FORWARD SWEEP: if the reason strings or ordering keys changed, make sure 3.1 surfaces them and 3.2 measures them.
```

## Step 3.1 — Show "why this ranks here" in the dashboard

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 3.2

Surface the consequence reason and a short reachability path where attention already is. Text-first — the full glowing graph view is deliberately deferred to Campaign 2.

```text
SCOPE: Carry consequence through the payload and show a compact "why this ranks here" line + textual path on the case surface. No graph-viz library yet.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/dashboardData.ts  (API→UI mapping)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/uiTypes.ts  (types to extend)
3. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/App.tsx  (find the case-rendering surface — there is no CaseCard.tsx in the current tree)
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py  (the payload that carries cases — add consequence fields)

FROM 2.1 (use, don't rebuild): the consequence already rides on each case as a `consequence` dict (it serializes through `SecurityCase.to_dict()` → `cases_json` and the normalized report). Exact shape: `{reaches_crown_jewel: bool, distance: int|None, blast_radius: int, confidence: "unknown"|"weak"|"strong", crown_jewels_defined: bool, path: [{identity_key, node_type, label, via?}], crown_jewel: {identity_key, node_type, label}|None}`. `path` is ordered finding-node → crown jewel; each step after the first carries `via` (the edge_type traversed, e.g. `reachable_from`/`stored_in`/`depends_on`) so "api-key → unlocks → prod-db" renders straight from it. `crown_jewels_defined=false` means no crown jewels were labeled (render "unknown", not "reaches nothing"); `consequence` absent/`null` means the case isn't in the graph (render nothing new).

OUTPUT:
- Carry the consequence summary (the full dict above) through the dashboard payload and UI types.
- On the case surface, a compact line: the consequence reason + a textual path built from `path` steps + `via`, e.g. "api-key → unlocks → prod-db (2 hops, strong)".
- Honest empty/weak states: `crown_jewels_defined=false` reads as unknown; a `weak`-confidence path reads as weak — never false certainty.
- Receipt to campaigns/honeygraph-1-asset-graph/receipts/3.1-surface-consequence.md

ACCEPTANCE:
- The UI uses real payload consequence data, not placeholders.
- A case with no consequence shows nothing new (no empty scaffolding).
- Confidence is visible; a weak path never looks like proof.
- `cd dashboard-ui && npm run lint` and `cd dashboard-ui && npm run build` pass.

OPEN QUESTIONS: where do users actually look — the case list or a detail view? Put the one-line reason where attention already is; don't build a new panel for the MVP.

FORWARD SWEEP: confirm the payload field names you consume match what 2.2 emits; if you renamed anything UI-side, note it for 3.2.
```

## Step 3.2 — Prove the re-rank is truer (the trust-gate for Campaign 2)

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 3.1

The honesty test this whole campaign exists to pass. Compare the two top-10s on real data and make an explicit GO/NO-GO call. A NO-GO is a first-class, acceptable outcome — if the graph mis-ranks, the loop in Campaign 2 collapses.

```text
SCOPE: On real stored scan data, compare the severity-ordered top-10 against the consequence-ordered top-10 and decide GO/NO-GO for Campaign 2.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py  (final ordering after 2.2)
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/priority.py  (the consequence boost from 2.2)
3. campaigns/honeygraph-1-asset-graph/receipts/2.2-consequence-boost.md
4. /Users/christiankatzmann/Dev/Projects/dëv-security/AGENTS.md  (local runtime data lives in ~/.security-observatory — use existing scan history; do NOT require a fresh live scan)

OUTPUT:
- Using existing scan history (or one representative repo with real dependency + IaC signal and a labeled crown jewel), a side-by-side: top-10 by severity vs top-10 by consequence, with the one-line reason each consequence-promoted case carries.
- A written judgment in campaigns/honeygraph-1-asset-graph/notes/consequence-vs-severity.md: is the consequence top-10 demonstrably truer? Where did it help, where did it mislead, and what's the false-promote rate on weak edges?
- An explicit recommendation: GO (graph is trustworthy enough — build Campaign 2) or NO-GO (graph mis-ranks — stop).
- Receipt to campaigns/honeygraph-1-asset-graph/receipts/3.2-validation-gate.md

ACCEPTANCE:
- The comparison uses real findings, not toy fixtures.
- The verdict is honest about failure modes, not a rubber stamp — NO-GO is acceptable and expected if the graph isn't trustworthy.
- The note names the repo/scan used and the crown jewels labeled, so the result is reproducible.

OPEN QUESTIONS: if the only signal that fired was dependency reachability (no IaC edges, no crown-jewel reach), say so plainly — that's the table-stakes reachability win, not the novel blast-radius win, and it changes how much Campaign 2 can honestly promise.

FORWARD SWEEP: this is the last step — instead of a forward sweep, make sure the GO/NO-GO verdict in the note is unambiguous, since Campaign 2's Step 0.1 reads it as a gate.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the Honeygraph 1 of 2 — Asset Graph + Consequence Re-Ranking campaign.

Plan: campaigns/honeygraph-1-asset-graph.md
Campaign: campaigns/honeygraph-1-asset-graph.md

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff that the criteria actually landed. Don't trust step receipts — read the diff.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas. Pay special attention to: nodes/edges stored but never traversed; consequence computed but not surfaced; the priority boost silently overriding severity instead of adding to it; findings with no consequence data ranking differently than before (must be a pure-additive change).

Be honest. Lean. APPROVED if every step's acceptance criteria landed and there are no cross-step regressions. NEEDS WORK if any step cut corners or a primitive was bypassed.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.8 with Extra High thinking
(Your call — both are acceptable for this kind of cross-file review.)
```

**Verdict-to-action mapping:**

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign"). Campaign is done. If Step 3.2 returned GO, proceed to Campaign 2.
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick the checkbox until APPROVED.
