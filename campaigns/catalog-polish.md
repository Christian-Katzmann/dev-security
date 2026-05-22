# Catalog Polish — Stop the Small Lies

> The tool catalog looks great, but some of its buttons don't do what they say. This fixes the broken links and misleading buttons, and lets you install a few more security tools straight from the catalog instead of just one.

## Scope

The Catalog UI Design Salvage shipped a clean, calm catalog — but several visible affordances are dishonest. The "Read documentation" link 404s for every tool. The "View docs" button on Browse routes to the tool detail page, not docs. The "Snooze / later" button has no snooze mechanism — it just goes back. And the catalog's "Install" button works for exactly one of ~11 third-party tools (Gitleaks). This campaign fixes the four lies and expands the managed-install set to 3–4 tools so the catalog stops feeling like a one-trick demo. Done means every visible button does what its label says, broken doc links are gone, and the install path is real for more than one tool. Backend is touched only where it must be: catalog `homepage_url` data and the managed-install manifest blocks.

## Context (locked decisions)

- **Backend touched in two places only**: (a) `homepage_url` populated per entry in `src/security_observatory/catalog.py`; (b) `APPROVED_MANAGED_INSTALL_TOOL_IDS` + `MANAGED_INSTALL_PROOF_TARGETS` extended for 2–3 more tools in `src/security_observatory/managed_tools.py`. No new endpoints, no schema migrations.
- **DESIGN.md remains canon.** Same smell test, same §15 build checklist as `catalog-design-salvage`. Sentence case, one primary action, mono only on telemetry, no looping motion.
- **Tests stay green**: `uv run pytest`, `npm run lint`, and `npm run build` all pass at the end of every step.
- **Each newly-installable tool needs a vetted release manifest** — release URLs and per-architecture sha256 checksums — modelled on the Gitleaks block at `src/security_observatory/managed_tools.py:27`. No "we'll fill it in later" stubs.
- **Tool selection for install widening prioritises MVP-pack tools**: Semgrep first (Starter pack), then Trivy (Dependencies/IaC), then OSV-Scanner if the third feels real. No display-only or hidden tools enter the installable set.
- **The Snooze button is removed, not built.** There is no snooze concept anywhere in DëvSec; the button was a known stand-in and it's time to take it down.
- **Pack page's disabled "Install Bundle" + "View Contents" CTAs collapse into one calm note** pointing at the utility grid. No two-disabled-buttons pattern in the rebuild.
- **External Surface stays display-only** across all routes. No regression of the safety rule.
- **Branch**: `catalog-polish`, off `main`. Merge to `main` when Final review is APPROVED.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Honesty pass (no lies in the existing surface)

- [x] Step 1.1 — UI cleanup: remove Snooze, rename "View docs" → "View tool", collapse pack-page disabled CTAs
- [x] Step 1.2 — Wire the "Read documentation" link to real homepage URLs

### Phase 2 — Widen the managed install set

- [x] Step 2.1 — Add 2–3 new installable tools (research release manifests, implement, test)
- [x] Step 2.2 — End-to-end install verification on a real Mac

### Phase 3 — Validation

- [x] Step 3.1 — Full catalog sweep: every button, every route, no lies left
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — UI cleanup: remove Snooze, rename "View docs" → "View tool", collapse pack-page disabled CTAs

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

Mechanical UI fixes with taste. Three small dishonesties get removed in one focused diff so the catalog stops promising things it can't deliver. No new components, no new tokens — just deletes and a rename.

```text
SCOPE: Remove three dishonest affordances from the catalog UI without redesigning anything.
REQUIRED READING:
1. dashboard-ui/src/components/catalog/CatalogToolPage.tsx
2. dashboard-ui/src/components/catalog/CatalogBrowse.tsx
3. dashboard-ui/src/components/catalog/CatalogPackPage.tsx
4. dashboard-ui/src/index.css (catalog-scoped sections)
5. DESIGN.md (§0 smell test, §15 checklist)
OUTPUT:
- CatalogToolPage.tsx: delete the "Snooze / later" button and the catalog-tool-cta-secondary slot on the hero actions row. The hero keeps one primary action (Install) for installable tools and the existing "Display only" note for display-only tools. Remove the related CSS rule for .catalog-tool-cta-secondary if it isn't used elsewhere.
- CatalogBrowse.tsx: rename "View docs" → "View tool" on the featured banner. Swap the BookOpen icon for ArrowRight. The button still calls onOpenTool — the label now matches the destination.
- CatalogPackPage.tsx: collapse the two disabled CTAs ("Install bundle" + "View contents") into one calm note that points at the utility grid. The note should explain that pack-level install is on the roadmap and that each utility installs individually below. The "Recommended scan profile" line below stays as-is — it's already a real action.
- `npm run lint` and `npm run build` pass. No backend or test changes.
OPEN QUESTIONS:
- The collapsed pack-page note replaces two buttons that occupied a clear visual slot. Is one short sentence enough, or does the slot need a small icon (Info / Package) to keep the rhythm? Pick the calmer option.
- After removing Snooze, the tool hero may feel light. Confirm 30–40% air still reads — if it suddenly feels barren, the hero copy may need a one-line tightening, nothing more.
```

## Step 1.2 — Wire the "Read documentation" link to real homepage URLs

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

The current default `docs_path = "docs/scanners.md"` resolves to nowhere — the dashboard server only serves the built frontend, and from a nested route the relative URL resolves to a second 404. Replace it with real upstream documentation URLs the tool detail page already knows how to render via `tool.homepage_url`.

```text
SCOPE: Populate homepage_url on every catalog entry so the "Read documentation" link goes to real docs instead of 404ing.
REQUIRED READING:
1. src/security_observatory/catalog.py
2. dashboard-ui/src/components/catalog/CatalogToolPage.tsx (docsHref logic around line 125)
3. dashboard-ui/src/dashboardData.ts (ToolCatalogItem type)
4. tests/test_catalog.py (or equivalent — confirm where catalog assertions live)
OUTPUT:
- catalog.py: every ToolCatalogEntry sets a real homepage_url. Built-in scanners (ai-static, ioc-watch, install-hooks, workflow-audit) point at the in-repo docs that document them; third-party tools (Semgrep, Gitleaks, TruffleHog, Trivy, OSV-Scanner, Syft, Grype, Checkov, Medusa, malcontent, legitify) point at the canonical upstream documentation URL (typically the GitHub README or the project's docs site). External Surface placeholder may stay with no homepage_url — the display-only path renders the empty state already.
- docs_path default in catalog.py drops to None. Built-in entries that genuinely have a real in-repo docs file may keep a docs_path pointing at it, but only where the file exists and the path is absolute from the project root.
- CatalogToolPage.tsx: confirm docsHref still prefers docs_path over homepage_url for built-in tools (in-repo docs are more authoritative) and falls through to homepage_url for third-party tools. The target=_blank + rel=noreferrer behaviour stays for external URLs.
- Add or extend a catalog test asserting every entry has at least one of {docs_path, homepage_url} set, or is explicitly the External Surface placeholder. This prevents future regressions where a new tool ships with no docs link.
- `uv run pytest`, `npm run lint`, `npm run build` all pass.
OPEN QUESTIONS:
- Some upstream tools have both a README and a dedicated docs site (e.g., Semgrep). Prefer the docs site over the README when one exists, since "Read documentation" implies docs, not source.
- For in-repo docs paths, the dashboard server currently doesn't serve docs/ — confirm whether built-in tools should keep docs_path (and we accept the click won't work today) or also point at a hosted README in the GitHub repo. The honest answer is the second; pick it unless there's a strong reason to wait.
```

## Step 2.1 — Add 2–3 new installable tools (research release manifests, implement, test)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The catalog has 11 third-party tools and an Install button on every detail page, but only Gitleaks actually installs. Widen the set to Semgrep and Trivy (and OSV-Scanner if the manifest verifies cleanly) so the catalog stops feeling like a one-trick demo. The Gitleaks block at `managed_tools.py:27` is the exact shape — vetted release URLs, per-architecture sha256s, version label, binary name. Don't invent shortcuts.

```text
SCOPE: Add 2–3 new tools to APPROVED_MANAGED_INSTALL_TOOL_IDS with vetted MANAGED_INSTALL_PROOF_TARGETS blocks, and prove the install path works in tests.
REQUIRED READING:
1. src/security_observatory/managed_tools.py (especially the Gitleaks block at line 27 and APPROVED_MANAGED_INSTALL_TOOL_IDS at line 26)
2. src/security_observatory/catalog.py (Semgrep, Trivy, OSV-Scanner entries — for install method context)
3. tests/test_managed_tools.py (or equivalent — existing install/uninstall test patterns)
4. DESIGN.md (§0 smell test — no decoration on the catalog page when these become installable)
OUTPUT:
- managed_tools.py: APPROVED_MANAGED_INSTALL_TOOL_IDS becomes a frozenset of {gitleaks, semgrep, trivy} (or {gitleaks, semgrep, trivy, osv-scanner} if the third manifest verifies cleanly). Each new entry has a full MANAGED_INSTALL_PROOF_TARGETS block matching the Gitleaks shape: tool_id, label, binary, managed_package, target_version, target_version_label, source, network_access, version_check_args, version_check_timeout_seconds, download_timeout_seconds, max_download_bytes, and an assets dict keyed by {darwin-arm64, darwin-x64, linux-arm64, linux-x64} with asset_name and sha256.
- The release URLs and sha256s come from the upstream project's official releases page — not third-party mirrors. Document the source URL in a comment above each block so future updates can re-verify against the same channel.
- Each new tool's catalog entry in catalog.py updates its install method to reflect that DëvSec can manage it (install_state stays driven by the runtime check, but the install metadata may surface a "DëvSec can install this" hint where useful).
- Tests: extend the managed-install test suite so every entry in APPROVED_MANAGED_INSTALL_TOOL_IDS has a corresponding MANAGED_INSTALL_PROOF_TARGETS block, all four platform keys are present, all sha256 values are 64 hex chars, and the build_tool_install_preview path returns execution_available=true for each. Do NOT add a test that downloads the artifact — that belongs in Step 2.2.
- `uv run pytest` passes. No UI changes in this step — the catalog already picks up the wider install set through previewCanInstall.
OPEN QUESTIONS:
- Semgrep and Trivy ship as Homebrew-first projects with binary release tarballs. Confirm the binary release path exists on the official GitHub releases page for the chosen target_version — if a tool publishes only via Homebrew/pip, drop it from this campaign and pick the next candidate. Don't fabricate a download URL.
- target_version freshness: lock to a recent stable release as of campaign run, not "latest" — newer releases can be picked up in a follow-up. Document the version chosen and the date it was vetted in a comment.
- OSV-Scanner is the soft third pick. If its release shape doesn't fit (e.g., no per-architecture binary), prefer adding Syft or Grype instead — both ship per-arch tarballs like Gitleaks. Make a judgement call and document it.
```

## Step 2.2 — End-to-end install verification on a real Mac

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

The schema tests in Step 2.1 prove the manifest blocks are well-formed; this step proves the bytes actually arrive, verify, install, and uninstall cleanly. Run on the real machine, not in a unit test. Record what happens.

```text
SCOPE: Verify each newly-installable tool installs and uninstalls cleanly through the dashboard's managed-install path on a real Mac.
REQUIRED READING:
1. src/security_observatory/managed_tools.py (install/uninstall flow)
2. src/security_observatory/dashboard_server.py (/api/managed-tools/install and /api/managed-tools/uninstall handlers around line 1028)
3. .adx/commands.json (for dashboard run command)
OUTPUT:
- For each tool added in Step 2.1: start the dashboard, navigate to /catalog/tool/<id>, click Install. Confirm: (a) the dashboard reports success; (b) ~/.security-observatory/tools/<tool>/<version>/bin/<binary> exists and is executable; (c) the binary's --version (or equivalent) output matches the target_version label; (d) the manifest at ~/.security-observatory/tools/managed-tools.json contains the new entry with the correct ownership_id; (e) the catalog page refreshes to show install_state=managed.
- Then uninstall through the dashboard. Confirm: (a) the dashboard reports success; (b) the install root is gone; (c) the manifest entry is removed; (d) the catalog page refreshes to install_state=missing or detected (if Homebrew installed a parallel copy).
- Save the verification log under reports/campaign-automation/catalog-polish/step-2.2-install-verification.md — one short paragraph per tool with the outcome. Include the dashboard screenshot showing install success and the post-install catalog state.
- Stop the dashboard when finished. Kill any orphan processes.
OPEN QUESTIONS:
- If any install fails (checksum mismatch, archive layout differs, version mismatch), do NOT loosen the manifest. Roll the tool back out of APPROVED_MANAGED_INSTALL_TOOL_IDS in Step 2.1's code and document why it failed in the verification log. Honest narrower set beats dishonest wider one.
- The dashboard's install path is single-architecture (the running Mac). Cross-architecture verification (e.g., darwin-x64 when the running Mac is darwin-arm64) is out of scope for this step — the unit tests in Step 2.1 cover the manifest correctness.
```

## Step 3.1 — Full catalog sweep: every button, every route, no lies left

Model: Opus 4.7 · High / GPT-5.5 · High
Parallel: NO

End-to-end walk of every catalog route at desktop and mobile widths. The acceptance criterion is "no button promises something the code doesn't deliver." Screenshot every route, walk the §15 checklist for each, fix any regression in place.

```text
SCOPE: Verify the catalog UI has zero remaining "small lies" and still passes the DESIGN.md §15 build checklist after Phases 1 and 2.
REQUIRED READING:
1. DESIGN.md (§15 build checklist)
2. .adx/commands.json (dashboard-lint, dashboard-build, dashboard start command)
3. reports/campaign-automation/catalog-design-salvage/ (the prior screenshot baseline for comparison)
OUTPUT:
- Run dashboard-lint and dashboard-build. Both pass.
- Start the local dashboard. Take desktop (≥1280px) and mobile (375px) screenshots of each catalog route — home, browse, tool detail (using one of the newly-installable tools from Step 2.1), pack detail — and save under reports/campaign-automation/catalog-polish/ as step-3.1-<route>-<viewport>.png. 8 screenshots total.
- For each route, write a short paragraph confirming: (a) no Snooze button anywhere; (b) Browse banner secondary button reads "View tool", not "View docs"; (c) Tool Detail "Read documentation" link opens a real upstream URL in a new tab — verify by clicking; (d) Pack Detail hero shows one calm note instead of two disabled CTAs; (e) Tool Detail Install button is enabled and functional for at least 3 tools (Gitleaks + the new additions); (f) §15 checklist still passes — sentence case, one primary action, mono only on telemetry, no looping motion, prefers-reduced-motion honoured, tap targets ≥ 44 px, empty/loading/error states drawn.
- Walk the rest of the dashboard (Findings, Honey keys, Overview, Verification) at desktop to confirm nothing regressed.
- If any check fails: fix in place, re-screenshot, re-walk. The campaign isn't done until every checkbox holds.
- Stop the dashboard. Kill any orphan processes.
OPEN QUESTIONS:
- If a "Read documentation" link opens an upstream page that doesn't render well (404, login wall, redirect loop), it's still a lie even with a real URL. Catch these during the click walk and route them back to Step 1.2 with the broken URLs called out by tool id.
- If install verification in Step 2.2 was partial (e.g., OSV-Scanner dropped), confirm the catalog page for the dropped tool shows the disabled Install button with its install instructions — not a half-broken state where the button looks enabled but does nothing.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the Catalog Polish — Stop the Small Lies campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/catalog-polish.md
Campaign: campaigns/catalog-polish.md

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
