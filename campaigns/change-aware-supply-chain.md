# Change-Aware Supply Chain Observatory

> Copy this to your notes. You can also read it from campaigns/change-aware-supply-chain.md in the repo. Follow it linearly. Each step tells you exactly what to do and what to paste.

**You only have to think when a step surfaces a real decision.** Everything else is mechanical: copy the prompt from the step, paste it into a fresh agent session, watch the receipt land, copy the REVIEW card, paste into Codex, advance.

## Scope

Turn Security Observatory from a point-in-time local scanner dashboard into a change-aware supply-chain security system. Done means Observatory stores SBOM components as first-class scan history, shows dependency changes since the last scan, correlates those changes with vulnerabilities, adds optional trust enrichment, supports VEX-backed suppression, and prepares bounded optional paths for platform posture and behavioral drift.

## Context (locked decisions)

- The product direction is change-aware security: answer "what changed since the last scan, and why does it matter?"
- The local-first promise stays intact: SQLite remains the local source of truth, raw reports remain evidence, network intelligence is optional and cached.
- SBOM history is the foundation. Scorecard, criticality, VEX, platform posture, and behavioral drift all depend on dependable component history.
- The first implementation slice should be small but meaningful: parse Syft SBOM output into SQLite, compute component deltas, and show a dashboard panel.
- Scanner adapters stay boring: command construction, timeout, raw output, exit-code handling, sanitizer handoff.
- Uncertainty should be visible. Use unknown, not checked, stale, and weak match states instead of inventing certainty.
- The Dependencies view becomes the main product surface for this campaign.
- Heavy or token-requiring tools, especially legitify and malcontent, are optional advanced modes, not default scan behavior.
- This campaign is intentionally bundled into 10 larger batches. Each batch should produce something coherent enough to review as a unit.

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
Review Step <STEP> for the Change-Aware Supply Chain Observatory campaign.

Project root: /Users/christiankatzmann/Dev/Projects/dëv-security
Campaign: campaigns/change-aware-supply-chain.md
Source plan: next-step.md

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
Review Phase <PHASE> for the Change-Aware Supply Chain Observatory campaign.

Project root: /Users/christiankatzmann/Dev/Projects/dëv-security
Campaign: campaigns/change-aware-supply-chain.md
Source plan: next-step.md

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

### Phase 1 — SBOM history wedge

- [x] Step 1.1 — Build the SBOM history slice
- [x] Step 1.2 — Add the dependency delta dashboard
- [x] Final review — Phase 1

### Phase 2 — Vulnerability movement

- [x] Step 2.1 — Correlate dependency findings with component changes
- [x] Step 2.2 — Harden correlation edge cases
- [x] Final review — Phase 2

### Phase 3 — Dependency trust layer

- [x] Step 3.1 — Add optional Scorecard and criticality enrichment
- [x] Step 3.2 — Add trust-aware prioritization and UI
- [x] Final review — Phase 3

### Phase 4 — Auditable decisions

- [x] Step 4.1 — Add VEX-backed decisions and safe suppression
- [x] Step 4.2 — Add VEX import, export, and suppressed-finding visibility
- [x] Final review — Phase 4

### Phase 5 — Optional advanced checks

- [x] Step 5.1 — Add optional platform posture drift
- [x] Step 5.2 — Add optional behavioral drift investigation
- [x] Final review — Phase 5

## Step 1.1 — Build the SBOM history slice

Create the first real foundation: normalized SBOM components stored in SQLite during scans, with fixture coverage.

```text
SCOPE: Build the SBOM history foundation in one vertical slice: normalized component model, SQLite schema, Syft/CycloneDX parsing, scan-time persistence, and tests.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/next-step.md
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/scanners.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cli.py
5. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/architecture.md

OUTPUT:
- Add normalized SBOM component tables to SQLite.
- Add a small parser/helper for Syft/CycloneDX component records.
- Save component rows for scans that produce SBOM output.
- Add fixture tests for package URL, name, version, ecosystem/type, license, supplier, source path, stable component fingerprint, and missing metadata.
- Write a receipt to campaigns/change-aware-supply-chain/receipts/1.1-build-sbom-history-slice.md.

ACCEPTANCE:
- Components are tied to scan id and repo.
- Missing optional metadata is allowed and visible as missing, not treated as failure.
- Syft missing, failing, or producing partial metadata still produces a partial scan, not a crash.
- Existing scan, finding, case, and dashboard payload behavior stays compatible.
- Tests cover schema creation, parsing, and stable identity for same package/version plus changed identity for version changes.
```

## Step 1.2 — Add the dependency delta dashboard

Make the new product wedge visible: what changed since the last scan.

```text
SCOPE: Compute component deltas against the previous scan and surface them in the Dependencies view.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py
3. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/dashboardData.ts
4. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/DependenciesView.tsx
5. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/scanners.md

OUTPUT:
- Add component delta computation for added, removed, upgraded, downgraded, version-changed, and license-changed packages.
- Include dependency deltas in the dashboard/API payload.
- Add a compact Dependencies section for "changed since last scan."
- Add first-scan and no-SBOM empty states.
- Update docs to explain SBOM history and dependency changes.
- Write a receipt to campaigns/change-aware-supply-chain/receipts/1.2-add-dependency-delta-dashboard.md.

ACCEPTANCE:
- Deltas are repo-specific and compare only against the previous scan for that repo.
- License changes are visible even when version is unchanged.
- A first scan explains that there is no previous scan to compare.
- The UI uses real API payload data, not placeholder scanner counts.
- Long package names and small screens do not break the layout.
- Relevant Python tests and the dashboard build pass.
```

## Step 2.1 — Correlate dependency findings with component changes

Connect CVE findings to dependency movement so Observatory can say whether a change made risk better or worse.

```text
SCOPE: Link dependency findings from Trivy, OSV, and Grype to normalized SBOM components, then classify risk movement as introduced, fixed, recurring, or unknown.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/normalize.py
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/enrichment.py
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py
5. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_cases.py

OUTPUT:
- Add matching logic by purl when available, then package name/ecosystem/version when reliable.
- Store or expose match confidence.
- Classify dependency changes as vulnerability introduced, vulnerability fixed, recurring risk, or unknown.
- Upgrade dependency case language so users can tell whether an issue is new, recurring, or resolved by a version change.
- Add tests for strong match, weak match, missing match, upgrade introduced CVE, and upgrade fixed CVE.
- Write a receipt to campaigns/change-aware-supply-chain/receipts/2.1-correlate-findings-with-component-changes.md.

ACCEPTANCE:
- Strong matches are explicit and explainable.
- Weak matches do not pretend to be proof.
- A package upgrade can be shown as security-positive, security-negative, recurring, or unknown.
- Dependency case language stays simple and does not require SBOM/VEX/CVSS vocabulary.
- Existing vulnerability normalization and case grouping remain stable.
```

## Step 2.2 — Harden correlation edge cases

Protect the system from false confidence.

```text
SCOPE: Add edge-case behavior and tests for uncertain dependency matching, dependency changes without CVEs, missing metadata, and no-SBOM scans.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/next-step.md
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/priority.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/dashboardData.ts
5. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/DependenciesView.tsx

OUTPUT:
- Add tests for package rename ambiguity, missing version, missing purl, unknown ecosystem, no vulnerability findings, and no SBOM output.
- Add UI/API labels for unknown, weak-match, not checked, and no-CVE states.
- Ensure dependency changes without CVEs still appear as supply-chain changes.
- Write a receipt to campaigns/change-aware-supply-chain/receipts/2.2-harden-correlation-edge-cases.md.

ACCEPTANCE:
- Ambiguous matches are labeled as uncertain.
- No-CVE dependency changes remain visible and do not look like failures.
- No-SBOM scans explain what could not be compared.
- The dashboard avoids false confidence.
- Relevant tests and the dashboard build pass.
```

## Step 3.1 — Add optional Scorecard and criticality enrichment

Add the trust layer without breaking local-first defaults.

```text
SCOPE: Design and implement optional dependency trust enrichment for OpenSSF Scorecard and criticality data, including cache boundaries and offline behavior.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/next-step.md
2. /Users/christiankatzmann/Dev/Projects/dëv-security/README.md
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/enrichment.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
5. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/scanners.md

OUTPUT:
- Add an explicit optional command/profile or enrichment path for trust data.
- Add cache-backed enrichment records for source repo, scorecard score, criticality score, checked_at, freshness, and status.
- Define source-repo resolution confidence and fallback behavior.
- Add tests with mocked/static payloads only.
- Update docs to explain optional network-backed trust enrichment.
- Write a receipt to campaigns/change-aware-supply-chain/receipts/3.1-add-optional-trust-enrichment.md.

ACCEPTANCE:
- Default scans remain offline-capable.
- Network-backed trust data is optional, cached, and labeled by freshness.
- Unknown source repositories are not treated as bad hygiene.
- Stale or unavailable data is visible.
- Unit tests do not depend on GitHub or external APIs.
```

## Step 3.2 — Add trust-aware prioritization and UI

Use trust facts to guide attention in plain language.

```text
SCOPE: Apply dependency trust facts to prioritization and surface them compactly in the Dependencies view.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/priority.py
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py
3. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/DependenciesView.tsx
4. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/dashboardData.ts
5. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_priority.py

OUTPUT:
- Add priority reasoning for high-criticality, low-hygiene dependencies.
- Include reason strings that a non-coder can understand.
- Show vulnerability risk, project hygiene, ecosystem importance, freshness, and unknown/stale states as separate signals.
- Add tests for low hygiene, high criticality, stale enrichment, no enrichment, and no penalty for missing data.
- Write a receipt to campaigns/change-aware-supply-chain/receipts/3.2-add-trust-prioritization-and-ui.md.

ACCEPTANCE:
- Trust data can increase attention but does not silently override severity.
- Every boost has a readable reason.
- Missing enrichment does not penalize the repo.
- Users can distinguish CVEs from project hygiene and ecosystem importance.
- Dashboard build succeeds and text fits on small screens.
```

## Step 4.1 — Add VEX-backed decisions and safe suppression

Make false-positive and accepted-risk decisions auditable without hiding evidence.

```text
SCOPE: Extend case decisions with VEX-compatible dependency status and apply safe suppression during report assembly.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cases.py
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/dashboard_server.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/false-positives.md
5. /Users/christiankatzmann/Dev/Projects/dëv-security/tests/test_dashboard_report_exports.py

OUTPUT:
- Add VEX-style fields for affected, not affected, fixed, or under investigation where appropriate.
- Require a human-readable justification for dependency suppressions.
- Apply suppression to active counts and cases while retaining suppressed findings in scan history.
- Expose suppressed counts and reasons in the dashboard payload.
- Add tests for existing decision migration/default behavior, same package/CVE suppression, and unrelated package non-suppression.
- Write a receipt to campaigns/change-aware-supply-chain/receipts/4.1-add-vex-decisions-and-safe-suppression.md.

ACCEPTANCE:
- Existing case decisions still work.
- Suppressed findings do not inflate active risk counts.
- Suppressed evidence remains inspectable.
- Matching is precise enough to avoid suppressing unrelated dependencies.
- Dependency suppressions can carry a VEX-compatible status and reason.
```

## Step 4.2 — Add VEX import, export, and suppressed-finding visibility

Make decisions portable and visible without cluttering the main path.

```text
SCOPE: Add VEX import/export support and UI visibility for suppressed findings.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/cli.py
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
3. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/FindingsView.tsx
4. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/CaseCard.tsx
5. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/false-positives.md

OUTPUT:
- Add a local VEX-compatible export path for accepted/not-affected dependency decisions.
- Add an import path for existing VEX-like decisions.
- Show active findings separately from suppressed findings.
- Add concise labels for suppression status, reason, and date.
- Document the supported VEX subset plainly.
- Write a receipt to campaigns/change-aware-supply-chain/receipts/4.2-add-vex-import-export-and-ui.md.

ACCEPTANCE:
- Users can export accepted/not-affected decisions.
- Users can import matching decisions and have them apply on future scans.
- Unsupported fields fail gracefully or are ignored with a clear note.
- Suppression is visible and auditable.
- The active "what needs attention" path remains focused.
- Dashboard build succeeds.
```

## Step 5.1 — Add optional platform posture drift

Add connected-mode platform posture as one bundled, opt-in capability.

```text
SCOPE: Define the connected-mode privacy boundary, add legitify as an optional scanner, store sanitized platform posture snapshots, detect drift, and surface platform findings.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/next-step.md
2. /Users/christiankatzmann/Dev/Projects/dëv-security/README.md
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/scanners.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/normalize.py
5. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
6. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/IacView.tsx
7. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/scanners.md

OUTPUT:
- Write a short boundary note to campaigns/change-aware-supply-chain/notes/platform-posture-boundary.md.
- Add legitify scanner/profile plumbing behind explicit opt-in.
- Normalize findings into category platform-posture.
- Store sanitized platform posture snapshots.
- Detect important posture regressions such as branch protection disabled or token permissions widened.
- Surface platform posture findings or integrate them cleanly with Infrastructure.
- Update docs for token requirements and privacy boundaries.
- Write a receipt to campaigns/change-aware-supply-chain/receipts/5.1-add-optional-platform-posture-drift.md.

ACCEPTANCE:
- Default, quick, and local scans do not require legitify or tokens.
- Missing credentials produce a partial/skipped platform scan, not a broken run.
- Raw token values are not stored.
- Platform posture can produce change-aware alerts.
- The UI does not imply platform posture was checked when credentials were absent.
- Dashboard build succeeds.
```

## Step 5.2 — Add optional behavioral drift investigation

Use SBOM deltas to drive bounded malcontent checks.

```text
SCOPE: Define the behavioral evidence threshold, select changed dependencies for analysis, integrate malcontent as an optional advanced check, and show before/after behavioral drift when available.

REQUIRED READING:
1. /Users/christiankatzmann/Dev/Projects/dëv-security/next-step.md
2. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/scanners.py
3. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/normalize.py
4. /Users/christiankatzmann/Dev/Projects/dëv-security/src/security_observatory/storage.py
5. /Users/christiankatzmann/Dev/Projects/dëv-security/dashboard-ui/src/components/DependenciesView.tsx
6. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/adding-scanners.md
7. /Users/christiankatzmann/Dev/Projects/dëv-security/docs/scanners.md

OUTPUT:
- Write a short decision note to campaigns/change-aware-supply-chain/notes/behavioral-drift-threshold.md.
- Select only changed dependency versions for advanced behavioral analysis.
- Add bounds around package count, artifact size, and unavailable old versions.
- Add malcontent scanner adapter and normalization for behavioral drift output.
- Store findings with old version, new version, behavior category, and evidence summary.
- Add a before/after behavioral drift section when findings exist.
- Document what behavioral drift can and cannot prove.
- Write a receipt to campaigns/change-aware-supply-chain/receipts/5.2-add-optional-behavioral-drift.md.

ACCEPTANCE:
- Behavioral analysis is driven by dependency deltas.
- The default scan path remains unaffected.
- Missing old artifacts are reported as not checked, not as failures.
- Scanner failures or unavailable artifacts do not break the scan.
- The UI explains behavior change without overclaiming compromise.
- Tests use controlled fixtures, not live package downloads.
- Dashboard build succeeds.
```
