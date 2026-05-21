# Next Step: Change-Aware Supply Chain Observatory

Security Observatory is already useful as a local scanner dashboard. The strongest next step is to make it excellent at answering a more valuable question: "What changed since the last scan, and why does that change matter?" Point-in-time security scans find known problems; a world-class security system also catches drift, surprise dependency movement, false-positive decisions, and supply-chain trust signals over time. This is the right next step because it builds directly on the current SQLite history, case model, SBOM generation, and dashboard instead of adding a pile of disconnected scanners.

## Product Thesis

Security Observatory should evolve from "runs open-source scanners locally" into a local-first change detector for modern codebases.

The product wedge:

- Show what changed since the last scan.
- Explain whether the change increased, reduced, or clarified risk.
- Separate known vulnerability risk from maintenance trust, platform posture, and behavioral drift.
- Keep heavy or token-requiring integrations optional.
- Preserve the current simplicity: scanner adapters stay boring, SQLite stays the source of local truth, and the dashboard turns raw evidence into plain next actions.

## The Five High-Value Moves

### 1. Store SBOM Components And Diff Them

This is the foundation for everything else. Syft already generates CycloneDX and Syft JSON, but Observatory does not yet store individual components as first-class records.

Build:

- Add SQLite tables for SBOM components, component relationships if available, licenses, package URLs, and per-scan component fingerprints.
- Parse the existing Syft/CycloneDX output after `syft` runs.
- Save normalized component rows alongside findings in `src/security_observatory/storage.py`.
- Add a diff layer that compares the current scan against the previous scan for the same repo.
- Surface added, removed, upgraded, downgraded, and license-changed packages.
- Correlate dependency changes with vulnerability findings: "this upgrade introduced CVE-X", "this upgrade fixed CVE-Y", "this package appeared for the first time."

How to do it well:

- Do not add a separate SBOM service. Keep this inside the current local pipeline.
- Normalize only the fields Observatory needs first: name, version, type/ecosystem, purl, license, supplier if present, source file, and component hash.
- Treat missing metadata as a quality signal, not a crash.
- Keep raw SBOM files saved as evidence, but query from SQLite for dashboard speed.
- Add tests with tiny fixture SBOMs for added, removed, changed version, changed license, and missing metadata.

Primary files:

- `src/security_observatory/scanners.py`
- `src/security_observatory/storage.py`
- `src/security_observatory/model.py`
- `dashboard-ui/src/components/DependenciesView.tsx`
- `dashboard-ui/src/components/SinceLastScanPanel.tsx`
- `tests/`

### 2. Add Dependency Trust Enrichment With Scorecard And Criticality

Known CVEs are only one layer of dependency risk. Observatory should also show whether important dependencies are maintained safely.

Build:

- Add optional enrichment for OpenSSF Scorecard and OpenSSF Criticality Score.
- Cache enrichment results locally under the Observatory home directory.
- Attach trust facts to dependency components, not only vulnerability findings.
- Show a small dependency trust card: vulnerability status, hygiene score, criticality, freshness, and confidence.
- Use this enrichment as a priority multiplier, not as a replacement for severity.

How to do it well:

- Start with GitHub-hosted packages where the source repository can be inferred reliably.
- Mark uncertain repo resolution as "unknown", not "bad".
- Avoid network calls during the default quick scan unless the user opts in.
- Cache results with timestamps and clear "last checked" labels.
- Make scoring explainable in plain English: "high-impact dependency with weak project hygiene" beats opaque math.

Primary files:

- `src/security_observatory/enrichment.py`
- `src/security_observatory/priority.py`
- `src/security_observatory/storage.py`
- `dashboard-ui/src/components/DependenciesView.tsx`
- `docs/scanners.md`

### 3. Turn Case Decisions Into VEX-Backed Suppression

Observatory already lets users mark cases as false positive, accepted risk, verified, or fixed. The next step is to make those decisions portable and auditable with VEX-style records.

Build:

- Extend case decisions with a structured "not affected / affected / fixed / under investigation" status compatible with VEX concepts.
- Let users export a VEX document for accepted or false-positive dependency cases.
- Let Observatory import existing VEX documents and suppress matching findings on future scans.
- Show suppressed findings separately from active findings.
- Keep the visible experience simple: "Suppressed by VEX" with a reason and timestamp.

How to do it well:

- Keep existing case decisions as the user-facing workflow.
- Add VEX as the standards-backed layer underneath, not as a confusing new dashboard mode.
- Require a reason when suppressing a dependency vulnerability.
- Never delete suppressed findings from history. Store them and exclude them from active counts.
- Add tests proving the same CVE/package pair stays suppressed across scans, while unrelated packages do not.

Primary files:

- `src/security_observatory/storage.py`
- `src/security_observatory/cases.py`
- `src/security_observatory/priority.py`
- `dashboard-ui/src/components/FindingsView.tsx`
- `docs/false-positives.md`

### 4. Add Optional Platform Posture With Legitify

Observatory scans repository contents today. Platform posture covers the GitHub/GitLab settings around the repo: branch protection, Actions permissions, webhooks, admin access, and organization security settings.

Build:

- Add `legitify` as an optional scanner profile, not part of the default local scan.
- Store platform findings as a distinct category, for example `platform-posture`.
- Add drift detection between platform posture scans.
- Surface high-value alerts like "branch protection was disabled" or "Actions token permissions widened."
- Deduplicate overlap with Scorecard where possible.

How to do it well:

- Keep this opt-in because it needs account tokens and can inspect organization-level settings.
- Do not make GitHub required for local-first value.
- Store only sanitized posture findings, not tokens or sensitive organization metadata.
- Treat platform scans as partial when credentials are missing or scoped too narrowly.
- Add clear docs for what permissions are needed and what Observatory will inspect.

Primary files:

- `src/security_observatory/scanners.py`
- `src/security_observatory/normalize.py`
- `src/security_observatory/storage.py`
- `install-security-observatory.sh`
- `dashboard-ui/src/components/IacView.tsx` or a new platform view
- `docs/scanners.md`

### 5. Add Behavioral Drift With Malcontent

Behavioral drift asks whether a package started doing something suspicious between versions. This should come after SBOM history exists, because the trigger is a dependency version change.

Build:

- Detect package version changes from the SBOM diff layer.
- For selected high-risk changes, run `malcontent` diff between old and new artifacts when artifacts can be fetched safely.
- Store behavioral anomaly findings as their own category, for example `behavioral-drift`.
- Show before/after behavior changes: new network behavior, new process execution, new file writes, suspicious binary capability changes.
- Use this as an advanced investigation mode first, not a default quick scan.

How to do it well:

- Do not block scans when old artifacts cannot be resolved.
- Run only on changed dependencies, not the whole dependency tree.
- Cache fetched artifacts and analysis results.
- Make artifact fetching explicit and bounded.
- Avoid scary labels unless the evidence is clear. "New network capability observed" is better than "backdoor" unless proven.

Primary files:

- `src/security_observatory/scanners.py`
- `src/security_observatory/normalize.py`
- `src/security_observatory/storage.py`
- `dashboard-ui/src/components/DependenciesView.tsx`
- `docs/scanners.md`

## Implementation Order

### Phase 1: SBOM History Foundation

[ ] Add normalized SBOM component tables to SQLite.

[ ] Parse Syft/CycloneDX output into component records after each dependency scan.

[ ] Add a `component_delta` query for added, removed, version-changed, and license-changed packages.

[ ] Add fixture-based tests for component parsing and scan-to-scan diffing.

[ ] Add a simple dashboard panel under Dependencies: "Changed since last scan."

Exit criteria:

- Running two scans with changed fixture SBOMs produces accurate component deltas.
- The dashboard can show dependency changes even when there are zero CVEs.
- Existing finding/case behavior remains unchanged.

### Phase 2: Vulnerability Correlation

[ ] Link dependency findings to SBOM components by package name, purl, ecosystem, and version where available.

[ ] Mark dependency changes as introduced, resolved, unchanged, or unknown risk.

[ ] Add tests for "upgrade fixed CVE" and "upgrade introduced CVE."

[ ] Update case copy so dependency cases explain whether the issue is new, recurring, or resolved by a version change.

Exit criteria:

- A package upgrade can be shown as security-positive, security-negative, or neutral.
- The dashboard avoids pretending certainty when package matching is weak.

### Phase 3: Dependency Trust Enrichment

[ ] Add an optional enrichment command/profile for Scorecard and criticality data.

[ ] Add cache files with TTLs and clear stale-data handling.

[ ] Store enrichment facts separately from findings so they can be refreshed without rewriting scan history.

[ ] Add priority rules that boost attention for high-criticality, low-hygiene dependencies.

[ ] Add dependency trust UI with simple labels and "last checked" metadata.

Exit criteria:

- Observatory can show "known CVEs", "project hygiene", and "ecosystem importance" as separate signals.
- Default scans still work offline.

### Phase 4: VEX Suppression

[ ] Extend case decisions to support VEX-compatible dependency status and justification.

[ ] Add export for user-generated VEX records.

[ ] Add import for existing VEX records.

[ ] Apply VEX suppression during report assembly while preserving suppressed evidence in history.

[ ] Add tests for stable suppression across scans.

Exit criteria:

- False positives become auditable decisions instead of one-off dismissals.
- Active risk counts exclude valid suppressions, while the dashboard still shows how many were suppressed.

### Phase 5: Optional Platform Posture

[ ] Add `legitify` installer and scanner adapter behind an explicit opt-in profile.

[ ] Normalize platform findings into the common finding shape.

[ ] Store platform posture snapshots and compare them over time.

[ ] Add platform drift cases for changes that weaken repo or organization protections.

[ ] Document required token scopes and privacy boundaries.

Exit criteria:

- Users can see platform posture beside code, dependency, secret, IaC, and AI findings.
- Missing credentials produce a partial scan, not a broken scan.

### Phase 6: Behavioral Drift

[ ] Add a dependency-change trigger for behavioral analysis.

[ ] Add `malcontent` as an advanced optional scanner.

[ ] Store behavioral diff findings with old version, new version, and observed behavior change.

[ ] Add a before/after UI for behavioral anomalies.

[ ] Add tests using tiny controlled fixtures, not live package downloads.

Exit criteria:

- Observatory can flag suspicious behavior changes after dependency upgrades.
- The feature remains bounded and optional.

## Pro-Grade Implementation Standards

- Keep scanner adapters boring. Each scanner owns command construction, timeout, raw output, and exit-code handling only.
- Keep normalized models small. Add specific tables for SBOM components, enrichment facts, VEX decisions, and platform snapshots instead of stuffing everything into generic JSON blobs.
- Preserve raw evidence. Store raw reports for auditability, but query normalized SQLite rows for product behavior.
- Prefer deterministic local behavior. Network-backed intelligence should be optional, cached, and labeled.
- Show uncertainty honestly. Use "unknown", "not checked", and "weak match" states instead of filling gaps with guesses.
- Make every risk multiplier explainable. If a case is boosted, show the reason in plain language.
- Test with fixtures. Do not rely on live registries, GitHub, or network APIs in unit tests.
- Keep dashboard language practical. Christian should be able to understand each panel without knowing SBOM, VEX, SLSA, or CVSS jargon.

## Data Model Sketch

Add tables along these lines:

- `sbom_components`: one row per component per scan.
- `sbom_component_deltas`: optional materialized deltas, or compute on read if simple enough.
- `dependency_enrichment`: cached Scorecard, criticality, source repo, and timestamps.
- `vex_statements`: structured suppression and applicability decisions.
- `platform_posture_snapshots`: raw posture summary per scan.
- `platform_posture_findings`: normalized platform findings and drift markers.
- `behavioral_drift_findings`: old version, new version, behavior category, evidence summary.

Keep the existing `findings`, `cases`, and `case_decisions` as the primary user-facing surfaces.

## Dashboard Direction

The Dependencies view should become the center of the new work.

Add sections in this order:

1. Changed since last scan.
2. Vulnerabilities introduced or fixed.
3. Key dependencies by trust and importance.
4. Suppressed by VEX.
5. Behavioral drift, only when available.

Avoid a busy compliance dashboard. The best UX is a small set of high-signal cards that answer:

- What changed?
- Is it worse or better?
- What should I do next?
- How confident are we?

## Non-Goals For This Step

- Do not add Raven, cimon, GHAS tooling, Allstar, or CI log scanning yet.
- Do not make GitHub tokens required.
- Do not make cloud APIs part of the default scan path.
- Do not replace the current scanner set.
- Do not turn Observatory into a SaaS-shaped enterprise platform.

## First PR Recommendation

Start with one vertical slice:

[ ] Parse Syft SBOM output into SQLite component rows.

[ ] Compute component deltas against the previous scan.

[ ] Add a small "Dependency changes since last scan" dashboard panel.

[ ] Add fixture tests for component parsing and diffing.

[ ] Update docs to explain that Observatory now tracks dependency change over time.

This first PR is small enough to finish cleanly, but it creates the foundation for Scorecard, criticality, VEX, platform drift, and behavioral drift.
