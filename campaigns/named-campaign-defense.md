# Named-Campaign Defense and Tripwires

> Copy this to your notes. You can also read it from campaigns/named-campaign-defense.md in the repo. Follow it linearly. Each step tells you exactly what to do and what to paste.

**You only have to think when a step surfaces a real decision.** Everything else is mechanical: copy the prompt from the step, paste it into a fresh agent session, watch the receipt land, copy the REVIEW card, paste into Codex, advance.

## Scope

Turn Security Observatory from a change-aware scanner dashboard into a system that also defends against named supply-chain campaigns. Done means Observatory can ingest IOC packs (named compromised packages, versions, and domains) and match them against current SBOMs, classify install-time hooks and CI workflow surfaces by risk, tell the user whether a flagged package was probably executed recently, and advise on secret rotation when it was.

This campaign assumes the `change-aware-supply-chain` campaign has landed at least Phase 1 (SBOM history) and Phase 2 (vulnerability correlation), because Phase 1 of this campaign matches IOCs against SBOM component rows.

## Context (locked decisions)

- The motivating incident is documented at `docs/incidents/2026-05-12-npm-pypi-supply-chain-worm-ioc-scan.md`. Read it before starting Phase 1.
- Named-campaign defense is treated as a first-class scan surface alongside code, dependency, secret, IaC, and AI risk. It is not a sub-mode of dependency scanning.
- IOC packs are user-loadable YAML files plus optional published feeds. Default scans should ship with a small curated source on by default; advanced packs come from user-curated paths.
- Match logic relies on the SBOM component rows landed by the `change-aware-supply-chain` Phase 1. No re-parsing of lockfiles inside this campaign.
- Install-recency detection is local evidence only: `node_modules/.package-lock.json` mtime, pnpm-store mtimes, `~/.npm/_logs`, `package-lock.json` mtime vs git history. No remote calls.
- Secret rotation advice is enumerated from local evidence only: `.env`/`.envrc`, `secrets.*` references in workflows, `mcp.json` keys, AWS/SSH/GH config in the project tree. The product names surfaces; it never rotates anything.
- Scanner adapters stay boring: command construction, timeout, raw output, exit-code handling, sanitizer handoff.
- Uncertainty stays visible. Use unknown, not checked, weak match, and stale states instead of inventing certainty.
- This campaign is intentionally bundled into 4 larger steps. Each step should produce something coherent enough to review as a single user-visible capability.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

**`<STEP>` and `<PHASE>` are reserved.** They appear only in the review prompts below — the app substitutes them automatically when you copy from a step's REVIEW card or a phase's PHASE N REVIEW card. Don't use them as user-fillable placeholders elsewhere.

## Review protocol

After each implementation step lands, open a fresh Codex session inside the repo and copy this step's REVIEW card. The app fills the step number automatically:

```text
Review Step <STEP> for the Named-Campaign Defense campaign.

Project root: /Users/christiankatzmann/Dev/Projects/dëv-security
Campaign: campaigns/named-campaign-defense.md
Source plan: docs/incidents/2026-05-12-npm-pypi-supply-chain-worm-ioc-scan.md

Resolve the step by reading the campaign markdown and finding the heading `## Step <STEP> — ...`.

Review against:
- the step's stated scope
- the acceptance notes in that step prompt
- the actual code, tests, docs, and UI changes
- the current diff or changed files, not only the implementer's receipt

Return one of:
- APPROVED: the step delivered its scope cleanly and did not create obvious regressions.
- NEEDS WORK: name the smallest concrete follow-ups needed before the step should be checked.

Keep the review short, direct, and grounded in file paths and behavior.
```

**Verdict-to-action mapping:**

- **APPROVED** → check the step in the campaign, move to the next step.
- **NEEDS WORK** → reopen the same step, paste the review feedback, close the gaps, then review again.

### Phase-level review

At the end of each phase, open a fresh Codex session and copy the PHASE N REVIEW card. The app fills the phase number automatically:

```text
Review Phase <PHASE> for the Named-Campaign Defense campaign.

Project root: /Users/christiankatzmann/Dev/Projects/dëv-security
Campaign: campaigns/named-campaign-defense.md
Source plan: docs/incidents/2026-05-12-npm-pypi-supply-chain-worm-ioc-scan.md

Resolve the phase by reading the campaign markdown and finding `### Phase <PHASE> — ...` under `## Progress checklist`. Then list every step in that phase.

Review whether the phase delivered its stated intent across all steps. Inspect the cumulative changed files for the phase if available. Look especially for cross-step shortcuts: schema added but not used, data stored but not surfaced, UI added without real data, or optional network behavior leaking into default scans.

Return one of:
- APPROVED: the phase delivers its intent and each completed step holds together as one system.
- NEEDS WORK: name the smallest concrete follow-ups and which step should reopen.

Keep later-phase work out of the verdict. Only flag gaps inside this phase's own promise.
```

**Verdict-to-action mapping:**

- **APPROVED** → check `Final review — Phase N` and advance.
- **NEEDS WORK** → reopen the named step or steps, close the gaps, then rerun the phase review.

## Progress checklist

### Phase 1 — Named-campaign rapid response

- [x] Step 1.1 — Ship IOC Watch end-to-end
- [x] Step 1.2 — Add the recency-aware rotation advisor
- [x] Final review — Phase 1

### Phase 2 — Surface hardening

- [x] Step 2.1 — Add install-hook and workflow surface scanners
- [x] Step 2.2 — Add the silent-upgrade detector
- [x] Final review — Phase 2

## Step 1.1 — Ship IOC Watch end-to-end

Deliver the entire IOC Watch capability in one coherent slice: pack format, loader, matching, cases, dashboard, CLI verb, and a starter pack. This is the slice that would have answered the 2026-05-12 question in 30 seconds.

```text
SCOPE: Ship IOC Watch as one user-visible capability: ingest YAML IOC packs, match them against SBOM components, surface results in the dashboard, and expose a cross-repo CLI verb.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/incidents/2026-05-12-npm-pypi-supply-chain-worm-ioc-scan.md
2. /Users/christiankatzmann/Dev/Projects/dëv-security/next-step.md
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py
5. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/normalize.py
6. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cli.py
7. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/DependenciesView.tsx

OUTPUT:

- **Pack format and ingestion**
  - YAML pack schema: pack id, source, published_at, advisory_url, confidence, indicators[].
  - Indicator fields: ecosystem (npm | pypi | other), name, versions[] (exact pins for now), optional namespace_prefix watch, optional domain watch.
  - Loader that reads packs from an explicit path and from a directory; reports malformed entries per-pack with file and line where possible; never crashes the scan.
  - SQLite tables: ioc_packs, ioc_indicators. Reimport must be idempotent.
  - Ship a starter pack at src/security_observatory/iocs/starter/2026-05-12-supply-chain-worm.yaml containing the IOCs from the incident doc plus the namespace and domain watches.

- **Matching**
  - Match SBOM components by ecosystem + name + exact version (range matching is out of scope here).
  - Namespace-prefix watch produces a separate lower-confidence indicator finding.
  - Domain watch by scanning strings already collected during scans (package.json script bodies, lockfile registry hostnames, workflow run: blocks). Do not re-run scanners.

- **Cases and dashboard**
  - New finding category supply-chain-ioc, default severity critical for exact matches.
  - Per-match confidence label visible on the case: exact match | namespace watch | domain watch.
  - New Dependencies subview or panel "Named-campaign matches" listing affected package, source pack, advisory link, and repo path.
  - IOC cases flow through the existing case decision lifecycle (verified, false positive, accepted risk, fixed).

- **CLI verb**
  - security-scan ioc [TARGET] [--feed=<file-or-dir>] [--all-repos] [--dev-root=<path>] [--json] [--fail-on=<severity>]
  - Default: starter pack + current repo unless overridden.
  - --all-repos reuses existing dev-tree discovery from security-scan --all-repos.
  - --json emits the same payload shape as the dashboard panel.
  - Exit code respects --fail-on (default: critical fails).
  - README usage section gets two examples (single repo and --all-repos).

- **Docs and tests**
  - docs/iocs.md explaining the pack format in plain language with the 2026-05-12 IOCs as a worked example.
  - Tests covering: valid pack, malformed pack, duplicate import, namespace-watch entry, domain-watch entry, exact match, no match, namespace hit, domain hit, empty pack directory, CLI single-repo, CLI --all-repos, JSON output, --fail-on exit behavior.

- Write a receipt to campaigns/named-campaign-defense/receipts/1.1-ship-ioc-watch-end-to-end.md.

ACCEPTANCE:
- Packs round-trip from YAML → SQLite → in-memory model without information loss; reimport is idempotent.
- IOC matching is wired into the default scan and never crashes when packs are missing or malformed.
- One command (security-scan ioc --all-repos) answers the question the 2026-05-12 sweep had to answer manually.
- Exact, namespace, and domain matches are visibly distinct in both cases and CLI output.
- No network calls happen in default behavior.
- The Dependencies UI renders zero, one, and many matches without layout breakage.
```

## Step 1.2 — Add the recency-aware rotation advisor

Close the loop: when an IOC matches, answer "did I probably run this?" from local evidence and, if yes, name the secret surfaces the user must rotate.

```text
SCOPE: Detect install recency from local filesystem evidence and use it to upgrade IOC cases (and the AI handoff prompt) with a "probably executed → rotate the following surfaces" section. No network, no package-manager invocation.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/incidents/2026-05-12-npm-pypi-supply-chain-worm-ioc-scan.md
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/scanners.py
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py
5. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/priority.py
6. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/CaseCard.tsx

OUTPUT:

- **Install-recency probe (local evidence only)**
  - Inspect: node_modules/.package-lock.json mtime, top-level node_modules/<pkg>/package.json mtime for matched packages, pnpm-store directory mtimes (best effort), ~/.npm/_logs entries referencing the project or matched packages, package-lock.json / pnpm-lock.yaml / yarn.lock mtime, per-package mtime under ~/.cache/pip and ~/.cache/uv where available.
  - Combine into per-project and per-package last_install_signal_at with confidence (strong | weak | unknown).
  - Configurable recency window (default 14 days).
  - Probing is read-only: never invoke package managers, never make network calls.
  - Store recency facts alongside scan results so cases can reference them.

- **Secret-surface enumerator (names only, never values)**
  - List local surfaces likely to contain exfiltratable secrets: .env, .env.*, .envrc, project-scoped .npmrc and .pypirc, ${{ secrets.* }} references in .github/workflows/, mcp.json and mcp.local.json, env blocks in wrangler.toml and vercel.json, AWS/SSH config inside the project tree (not the home directory).
  - Output is a list of surface paths only. No file contents are read; no values are stored.

- **Case and AI handoff upgrades**
  - When an IOC match overlaps with recency = strong: case copy adds a "Rotate the following surfaces" section listing the enumerated surfaces and an explicit recommendation.
  - When recency = weak or unknown: softer language, no rotation recommendation.
  - The existing AI handoff Markdown prompt gains the same rotation section when applicable, with guardrails: "rotate at the provider first, update local config last, never commit rotated values."
  - --dry-run option on the handoff generator so rotation prompts can be inspected without writing them.

- **Tests**
  - Fixture filesystems for: project never built, project built today, project built two months ago, partial evidence (only lockfile mtime), missing node_modules entirely.
  - Surface-enumeration fixtures for each surface type, asserting they are enumerated by path and that no secret-looking string appears in rendered output.
  - Case-copy assertions for strong, weak, and unknown recency.

- Write a receipt to campaigns/named-campaign-defense/receipts/1.2-recency-aware-rotation-advisor.md.

ACCEPTANCE:
- Recency probing never touches package managers or networks.
- Missing evidence sources are tolerated and return unknown, not failure.
- "Probably executed" copy appears only under strong recency.
- The rotation list is fully repo-specific and enumerated from local evidence; never inferred.
- Fixtures contain no real-looking secret values.
- The AI handoff prompt remains parseable by the existing agent flow.
- The product never claims to rotate secrets, only to name surfaces.
```

## Step 2.1 — Add install-hook and workflow surface scanners

Two new boring scanner adapters sharing a common shape: walk files, apply tiered rules, surface high and critical findings as cases, with a project-local allow-list for known-good entries.

```text
SCOPE: Add the install-hook risk classifier and the GitHub Actions workflow surface audit as one matched pair of scanner adapters. Share the allow-list and case-shape design between them.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/scanners.py
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/normalize.py
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/rules/
5. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/IacView.tsx
6. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/scanners.md
7. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/adding-scanners.md

OUTPUT:

- **Install-hook classifier**
  - Parse: package.json scripts (preinstall, install, postinstall), Python pyproject.toml build hooks, setup.py install commands.
  - Tiers:
    - critical: literal curl|sh, wget|sh, base64 -d | sh, fetch-then-exec via eval, /tmp/<random> write+exec, modifications of ~/.npmrc or ~/.pypirc at install time.
    - high: shell-out to unaudited binaries, dynamic download of compiled artifacts, NODE_OPTIONS set mid-install, child_process invoked from install scripts.
    - medium: nested installer (npm run install:client), unknown-publisher node-gyp rebuild, native build steps with no published checksum.
    - info: pnpm enforcers, in-repo install chains for local subprojects.
  - Cases produced at high and critical only; medium and info appear in a secondary "Install hooks" view but are not cases.
  - Unknown patterns fall back to medium with low confidence.

- **Workflow surface audit**
  - Walk .github/workflows/*.yml in the scanned project.
  - Rules:
    - Unpinned action references (uses: org/action@main or @master without SHA pin).
    - Fetch-and-exec inside run: blocks (curl|sh, wget|sh, bash <(curl ...)).
    - Secrets piped through base64/echo/xxd/od or sent to a network destination.
    - pull_request_target with actions/checkout of the fork ref.
    - Untrusted-input templating (${{ github.event.*.body }} or *.title) into run: blocks.
    - permissions: write-all or per-job widening without a justification comment.
  - Severity: critical for active exfil patterns and untrusted-input exec; high for unpinned actions and write-all tokens; medium for pull_request_target + fork checkout.
  - Surface findings under either a new Workflows view or the existing IaC view filtered by category "workflow"; pick the lighter option.

- **Shared allow-list mechanism**
  - Project-local .devsec/install-hook-allowlist.yaml and .devsec/workflow-allowlist.yaml with rule + path + reason entries.
  - Allow-list entries require an explicit reason and are included in the case audit trail.
  - Pre-populate the workflow allow-list with the known-good Typst installer at Projects/Obedai_JobManagement/.github/workflows/template-validation.yml:52 as a worked example.

- **Docs and tests**
  - docs/install-hooks.md and docs/workflow-audit.md.
  - Fixture per tier for hooks; fixture per rule with one positive and one negative case for workflows; allow-list silencing exercised in tests.

- Write a receipt to campaigns/named-campaign-defense/receipts/2.1-install-hook-and-workflow-surface-scanners.md.

ACCEPTANCE:
- Every preinstall/install/postinstall in the scanned project appears somewhere in the report, even when classified info.
- Every workflow rule has fixture-tested positive and negative coverage.
- Tier classification is deterministic for documented patterns.
- Allow-lists require explicit reasons and audit cleanly.
- Both adapters are read-only and offline.
- Findings normalize into the same shape as other findings; no special UI fork.
- The Dashboard exposes workflow findings without breaking the existing IaC layout.
```

## Step 2.2 — Add the silent-upgrade detector

Small but high-signal: a dependency or version jump in a lockfile without a matching manifest change is a strong supply-chain signal.

```text
SCOPE: Flag dependencies whose lockfile entries changed without a matching change in the source manifest. Ride on the SBOM history from the change-aware-supply-chain Phase 1.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/next-step.md
2. /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/change-aware-supply-chain.md
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py
5. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/DependenciesView.tsx

OUTPUT:
- For each project, parse the source manifest (package.json / pyproject.toml / requirements.txt) and compare its declared dependencies to the SBOM components delta from the previous scan.
- When a new dependency or a major-version jump appears in the lockfile but the manifest declaration is byte-identical or semantically equivalent (no range change, no addition), emit a silent-upgrade case with medium default severity.
- Distinguish silent direct upgrades (manifest entry exists, unchanged) from silent transitive upgrades (no manifest entry at all).
- Show silent upgrades in the Dependencies "changed since last scan" panel with a distinct label.
- Tests: new direct dep without manifest change, version bump in lockfile with unchanged manifest, transitive package added with no manifest involvement, manifest change with matching lockfile change (must not flag), first scan with no baseline.
- Write a receipt to campaigns/named-campaign-defense/receipts/2.2-silent-upgrade-detector.md.

ACCEPTANCE:
- Detection reuses the existing SBOM history rather than re-parsing lockfiles end-to-end.
- Routine patch upgrades inside an unchanged manifest range do not flag.
- Direct vs transitive silent upgrades are visibly distinct in the UI.
- First scans show a "no baseline to compare" state rather than empty noise.
- Case copy stays calm: "verify or revert," not "you have been compromised."
```

## Deferred — Honey tripwires

Two Honey-Keys extensions originally planned as a Phase 3 of this campaign are deferred until a forcing function justifies the engineering cost:

- **Honey Package** — synthetic-dependency tripwire for dependency-confusion and typosquat attacks. Cute but speculative; no current incident pulls for it.
- **Credential tripwire** — filesystem watcher for reads of `~/.npmrc`, `~/.aws/credentials`, `~/.ssh/id_*`, etc. by descendants of package managers. High-signal but needs macOS Endpoint Security or a signed helper — non-trivial work for an opt-in feature with no current pull.

The full design notes live as Features 7 and 8 in `docs/incidents/2026-05-12-npm-pypi-supply-chain-worm-ioc-scan.md`. Reopen as a fresh small campaign when a real incident or user need promotes either one.
