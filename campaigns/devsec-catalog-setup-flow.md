# 6 · DëvSec catalog setup flow — install, configure, and brand the tools you orchestrate

> Makes the security tools inside DëvSec actually configurable from inside DëvSec. Today you can install missing tools with a click, but some of them (like the one that checks GitHub settings) still need credentials that you have to set up outside the app. This campaign closes that gap, stores credentials safely on your computer, and gives each tool its own logo so you can tell them apart at a glance.

## Scope

Turn the DëvSec Tool Catalog from a viewer into a real surface that owns the full "go from zero to running" experience for any orchestrated tool. Four phases:

1. **Phase 0** — Self-recalibrate against campaigns 5 (dashboard-coherence) and 4 (rotation-integration), then generalize the install button beyond Homebrew (uv-tool, manual-with-copy).
2. **Phase 1** — Setup foundation: catalog schema additions (`setup_kind`, `setup_requirement`, `setup_probe`) + macOS Keychain credential-storage layer.
3. **Phase 2** — Typed `SetupCard` component, instantiated for legitify with a Connect-GitHub PAT/OAuth flow as the first concrete case.
4. **Phase 3** — Per-tool branding: each tool's logo and a small accent stripe on cards and detail pages.

Done when: a user lands on the Tool Catalog, sees missing tools instantly (visual hierarchy from #5 + brand recognition from #3), installs a Homebrew/uv/manual tool with one click, completes the tool's setup inside DëvSec (Connect GitHub for legitify, paste PAT, store in Keychain, probe-validate), and sees the state flip to `detected`. The catalog is now a real surface, not just a viewer. Reinforces DëvSec's local-first positioning commercially: credentials live in macOS Keychain, never touch a network.

## Context (locked decisions)

- **Campaign number `6 ·` in the sequence**, runs **after #4 (devsec-rotation-integration) lands**. Slot reason: this campaign's surface is the Tool Catalog, which doesn't conflict with #4's rotation surface. Running after #4 means we can reuse whatever credential-storage pattern #4 establishes for rotation, instead of inventing two conventions.
- **Hard dependency: #5 (devsec-dashboard-coherence) must be merged.** This campaign assumes the two-mode model exists, the vocabulary is locked, the install button from Step 0.1 is committed, and the bug-bash polish has landed. Step 0.1 verifies this before any new work starts.
- **Branch: `devsec-catalog-setup-flow`** off `main`. Each phase lands as a reviewable batch. Merge to `main` when Final review is APPROVED.
- **macOS Keychain is the credential-storage convention.** On-brand for local-first (credentials never leave the machine), industry-standard on Mac. If #4 (rotation-integration) ships first and chose a different storage convention, Step 0.1's self-recalibrate decides whether to align Phase 1.2 to #4's convention or to refactor #4 to use Keychain. Don't ship two conventions.
- **Setup is a first-class lifecycle stage, equal to install.** Tools have four states a user can act on: `missing` (install), `not-configured` (setup), `detected` (use), `broken` (repair). The Tool Catalog surfaces an affordance for each.
- **Catalog schema additions**:
  - `setup_kind`: `none | env-var | api-key | oauth | file-path | config-block`
  - `setup_requirement`: human-readable string surfacing what's missing ("Set SCM_TOKEN environment variable" or "GitHub Personal Access Token with `repo` + `admin:repo_hook` scopes")
  - `setup_probe`: structured spec for a cheap validation call ("run `legitify --version` to confirm binary; run `legitify analyze --token=<token>` against a public repo to confirm token works")
  - Adding a new not-configured tool becomes data, not code.
- **One typed `SetupCard` component reads `setup_kind` and renders the right input.** Five kinds → five render branches. No per-tool React components. legitify's Connect-GitHub flow is the first concrete instantiation; future tools that need API keys, OAuth, or file paths reuse the same component with different data.
- **Per-tool branding discipline: moderate respect, not full takeover.** Each card shows the tool's logo + a small accent stripe sampled from its brand. Detail page picks up one accent color, keeps DëvSec layout structure. Reference patterns: VS Code Marketplace, Raycast Store, Linear integrations page. Don't do 16-different-theme chaos.
- **Logo sourcing**: pull from each tool's official repo or brand assets page. SVG preferred where available. Store in `dashboard-ui/public/tool-logos/<id>.svg`. The 4 built-in DëvSec-internal tools don't need external logos.
- **Self-recalibrating Step 0.1 protocol**: this campaign is written while campaigns 5, 4, 3 are still pending. Step 0.1 reads current `main` after those campaigns land, then surgically edits this campaign's later step prompts in place to reflect reality (changed file paths, evolved schemas, different storage conventions, refined vocabulary).
- **Out of scope (deferred)**: secret rotation (lives in campaign #3 + #4 — this campaign integrates with whatever storage #4 establishes, doesn't reinvent it); cloud-hosted credential storage (against the local-first stance); team-shared catalog config (single-user only for v1); custom user-defined tools (catalog stays curated).

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 0 — Self-recalibrate and generalize the install button

- [ ] Step 0.1 — Self-recalibrate against shipped campaigns 5, 4, 3; edit later step prompts in place
- [ ] Step 0.2 — Generalize the install button beyond Homebrew (uv-tool, manual-with-copy)

### Phase 1 — Setup foundation

- [ ] Step 1.1 — Catalog schema additions (`setup_kind`, `setup_requirement`, `setup_probe`)
- [ ] Step 1.2 — macOS Keychain credential-storage layer

### Phase 2 — SetupCard component and first concrete case

- [ ] Step 2.1 — Typed `SetupCard` component (renders by `setup_kind`)
- [ ] Step 2.2 — legitify Connect-GitHub PAT/OAuth flow (first instantiation)

### Phase 3 — Per-tool branding

- [ ] Step 3.1 — Source logos, define accent palette, render on cards and detail pages

### Close

- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 0.1 — Self-recalibrate against shipped campaigns 5, 4, 3; edit later step prompts in place

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

This campaign was written while #5, #4, #3 were still pending. By the time it runs, the dashboard structure, rotation integration, and rotation foundation will all have shipped — which means file paths, schema shapes, vocabulary choices, and storage conventions referenced in later steps may have shifted. Step 0.1's job is to read what actually exists and surgically rewrite the later step prompts in place so the next agent isn't acting on stale assumptions.

```text
SCOPE: Read current main against the assumptions baked into this campaign's later steps. Edit any stale step prompts in place. Produce a short audit report alongside the edits.

REQUIRED READING:
1. campaigns/devsec-dashboard-coherence.md (campaign #5) — confirm what shipped: two-mode model, vocabulary lock, install-button salvage, etc.
2. campaigns/devsec-rotation-foundation.md (campaign #3) — confirm what the universal rotation skill stores and where
3. campaigns/devsec-rotation-integration.md (campaign #4) — CRITICAL: did #4 introduce a credential-storage layer for rotation? If yes, what convention did it use (Keychain, encrypted file, OS-level secret store, etc.)?
4. src/security_observatory/catalog/* — current schema
5. dashboard-ui/src/components/catalog/* — current component shape (post-#5)
6. /tmp/devsec-walkthrough-2026-05-24.md if still present — historical context

AUTHORITY (this step may):
- Update REQUIRED READING file paths in Step 0.2, 1.1, 1.2, 2.1, 2.2, 3.1
- Update acceptance criteria where reality has shifted
- Update OPEN QUESTIONS where they've been answered already
- Update Model: / Parallel: lines if the work has merged or split
- Merge two steps if reality made them redundant
- Split one step if reality made it too big
- Update Context (locked decisions) entries inline if a decision was overtaken

AUTHORITY (this step MAY NOT):
- Silently add a new phase
- Remove a phase
- Weaken any intent (e.g. dropping the Keychain requirement just because it's easier)
- Skip the credential-storage layer (Step 1.2) — security is non-negotiable

OUTPUT:
- Edited campaign markdown (in place at campaigns/devsec-catalog-setup-flow.md)
- A short audit report at /tmp/catalog-setup-recalibration-<DATE>.md noting:
  - What shifted (per-step delta)
  - Open assumptions remaining
  - Confidence in each later step's accuracy after edits

OPEN QUESTIONS (resolve before editing later steps):
- Did #4 establish a Keychain pattern for rotation? If yes, Step 1.2 aligns to it. If no, Step 1.2 establishes Keychain as the convention and notes that future credential-storing work uses the same layer.
- Did the vocabulary lock from #5 land cleanly (no surviving "warning" used for UI state, "cases" everywhere instead of ambiguous "findings")? If gaps remain, flag them — they could affect Step 2.1's SetupCard copy.
- Did #5's two-mode model classify Tool Catalog as all-repos-only? Confirm. Affects how the SetupCard surfaces credential state (is it per-repo or per-machine?).
```

## Step 0.2 — Generalize the install button beyond Homebrew (uv-tool, manual-with-copy)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

The Homebrew install button shipped in campaign #5 (Step 0.1 of that campaign). Today only `method: homebrew` enables the install action; `method: uv tool` and `method: manual` fall back to disabled-button + instructions. Extend the install pipeline so every catalog-declared method gets a real Install affordance — automatic where possible, copy-to-clipboard where the user has to act.

```text
SCOPE: Extend the install button so every catalog-declared install method is actionable from the app. Generalize the backend endpoint, the frontend helper, and the button UI.

REQUIRED READING:
1. campaigns/devsec-catalog-setup-flow.md (this campaign's Context block + Step 0.1's audit report)
2. src/security_observatory/dashboard_server.py — the existing `install_via_homebrew` method + route from #5
3. dashboard-ui/src/components/catalog/useCatalogData.ts — existing `installViaHomebrew()` helper
4. dashboard-ui/src/components/catalog/catalogHelpers.tsx — existing `canInstallViaHomebrew()` helper + `catalogCardAction()`
5. dashboard-ui/src/components/catalog/CatalogToolPage.tsx — existing button wire-up
6. src/security_observatory/catalog/ — install method definitions, especially for `checkov` (uv tool) and `malcontent` (manual)

INSTALL METHODS TO HANDLE:
- **homebrew** (already shipped in #5) — runs `brew install <binary>` via /api/tools/install-via-pkg
- **uv tool** — runs `uv tool install <binary>` via the same endpoint pattern; validate `uv` is available before invoking
- **manual** — surface install instructions in a panel with a one-click "Copy install command" button; flip state to "Waiting for manual install" until the next catalog re-detect
- **built-in** — no action needed (already shipped from DëvSec; just confirm it's still gracefully handled)

OUTPUT:
- Extended /api/tools/install-via-pkg endpoint that dispatches on `install.method` (homebrew → brew, uv-tool → uv tool, etc.), with the same binary-name regex validation and timeout for each
- Generalized `installViaPackageManager()` helper in useCatalogData.ts (rename from `installViaHomebrew`)
- Generalized `canInstallViaPackageManager()` helper in catalogHelpers.tsx, returns true for any tool where `install_state === 'missing'` and `install.method ∈ {homebrew, uv-tool}`
- Manual-install tools get a different affordance: not the same Install button, but a "Copy install command" + a "Mark installed" button that triggers a catalog re-detect
- Endpoint guardrails extended: 400 for unknown method, 400 for missing prerequisite tool (brew/uv not installed), 504 for timeout
- pytest coverage for each new path

OPEN QUESTIONS:
- What other install methods exist in the catalog beyond homebrew/uv/manual that I'm missing? Read the full catalog to enumerate.
- For uv-tool, should we validate that `uv` itself is installed before showing the Install button? Recommend yes; if `uv` is missing, the button should say "Install uv first" with a link to uv's install docs.
- For manual-install tools, should "Mark installed" be exposed in the UI or auto-detected by polling for the binary on PATH? Recommend a manual button to avoid filesystem polling, with a "Re-check" affordance.
```

## Step 1.1 — Catalog schema additions (`setup_kind`, `setup_requirement`, `setup_probe`)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.2

Adds three new fields to the Tool Catalog schema so the UI can drive setup flows without per-tool code. `setup_kind` types the input UX. `setup_requirement` is the human-readable hint surfaced in the UI. `setup_probe` is the validation call that flips state from `not-configured` to `detected`.

```text
SCOPE: Extend the catalog schema with three setup-related fields. Populate them for legitify (the first concrete case) and any other tool currently in not-configured state. Update the TypeScript types and the Python catalog model.

REQUIRED READING:
1. campaigns/devsec-catalog-setup-flow.md (this campaign's Context block + Step 0.1's audit)
2. src/security_observatory/catalog/ — current Python catalog schema (likely Pydantic models or TypedDicts)
3. dashboard-ui/src/dashboardData.ts — current TypeScript ToolCatalogItem type
4. src/security_observatory/catalog/tools/legitify.* — the legitify catalog entry (today's `next_step` is "Run security-scan --platform-posture..." which doesn't mention SCM_TOKEN — fix this)
5. Step 0.1's audit report if vocabulary has shifted

SCHEMA ADDITIONS:
- `setup_kind: 'none' | 'env-var' | 'api-key' | 'oauth' | 'file-path' | 'config-block'` — required field, defaults to 'none' for tools that don't need setup
- `setup_requirement: string | null` — human-readable description of what's missing ("Set SCM_TOKEN environment variable" or "GitHub Personal Access Token with `repo` + `admin:repo_hook` scopes")
- `setup_probe: {kind: 'shell' | 'http' | 'binary-version', spec: <kind-specific>} | null` — structured spec for the validation call. For legitify: `{kind: 'shell', spec: {command: 'legitify analyze --repo <test-repo> --token-from-env SCM_TOKEN'}}`

POPULATE FOR:
- **legitify**: `setup_kind: 'api-key'`, `setup_requirement: 'GitHub Personal Access Token with repo + admin:repo_hook scopes'`, `setup_probe: <shell call against a known-good public repo>`
- **malcontent**: `setup_kind: 'file-path'`, `setup_requirement: 'Path to behavioral artifact cache directory'`, `setup_probe: <directory-exists check>`
- All other detected/built-in tools: `setup_kind: 'none'`, others null

OUTPUT:
- Updated Python catalog schema + populated legitify/malcontent entries
- Updated TypeScript ToolCatalogItem type
- Migration: existing catalog API responses get the new fields with sensible defaults (no breaking change for downstream consumers)
- /api/tool-catalog returns the new fields
- Three pytest tests: schema validation, legitify-specific spec, default-none fallthrough

OPEN QUESTIONS:
- For `oauth` setup_kind, what's the spec shape? GitHub PAT can be done as `api-key`; true OAuth (browser redirect, code exchange) is heavier. Recommend defer the full OAuth spec to a future iteration where a tool actually needs it; for v1, OAuth is a placeholder.
- For `config-block`, what's the spec? Probably "block of YAML/TOML pasted by the user, written to a known path". Recommend defer until needed.
- Should `setup_probe` be runnable from MCP (read-only) or only from the dashboard? Probably dashboard-only (probes shell out, MCP is read-only). Confirm against the safety doctrine from campaign #2.
```

## Step 1.2 — macOS Keychain credential-storage layer

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 1.1

A small Python module that stores credentials in the macOS Keychain via `security` CLI (built-in on macOS) or the `keyring` library. Used by Step 2.2's Connect-GitHub flow as the first consumer. Establishes the convention: credentials live in Keychain, configuration lives in `~/.security-observatory/config/<tool>.toml`.

```text
SCOPE: New backend module for macOS Keychain credential storage. Used by future setup flows; legitify's PAT (Step 2.2) is the first consumer.

REQUIRED READING:
1. campaigns/devsec-catalog-setup-flow.md (Context block on storage convention)
2. Step 0.1's audit report — did campaign #4 establish a credential-storage pattern? If yes, ALIGN to it (use the same module, extend if needed). Don't ship two conventions.
3. src/security_observatory/ — module layout convention
4. https://pypi.org/project/keyring/ if using keyring; otherwise the macOS `security` CLI man page

API SHAPE (proposed — refine if Step 0.1 surfaced a different convention from #4):
- `store_credential(tool_id: str, key: str, value: str) -> None` — writes to Keychain under service "DëvSec" + account "<tool_id>:<key>"
- `read_credential(tool_id: str, key: str) -> str | None` — returns None if not found, raises only on Keychain access failure
- `delete_credential(tool_id: str, key: str) -> bool` — returns True if existed and was deleted
- `list_credentials(tool_id: str) -> list[str]` — returns keys (NOT values) for a given tool

REQUIREMENTS:
- macOS Keychain only (out-of-scope: Linux Secret Service, Windows Credential Manager — DëvSec is macOS-first per the README)
- Never log credential values
- Never echo to stdout/stderr
- Keychain access prompt: rely on macOS's built-in approval dialog; don't try to suppress it
- A small CLI command (`security-scan credentials list`) for the user to audit what's stored — keys only, never values

OUTPUT:
- New module src/security_observatory/credentials.py (or similar)
- Three integration tests gated on macOS availability (skip elsewhere): write+read roundtrip, delete, list
- A short docs/credentials.md explaining: where stuff is stored, how to audit, how to revoke, the local-first commitment
- CLI command (one new subcommand) for listing stored credentials
- HTTP endpoints if needed by Step 2.2's frontend (likely: POST /api/tools/<id>/credentials, GET /api/tools/<id>/credentials/keys — never returns values to the frontend)

OPEN QUESTIONS:
- Should the frontend ever see credential values? Recommend NO — frontend POSTs the value, backend stores in Keychain, backend never returns it. UI shows "Stored" or "Not stored" only.
- Keychain access prompts can be jarring on first use. Should the install/setup flow surface "macOS will ask permission to store credentials in Keychain" copy ahead of time? Recommend yes.
- If campaign #4 chose `~/.security-observatory/secrets.json` (encrypted file) instead of Keychain, what's the migration path? Surface the answer; don't silently keep both.
```

## Step 2.1 — Typed `SetupCard` component (renders by `setup_kind`)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

One React component, five render branches keyed off `setup_kind`. Replaces the "Installed — needs setup." dead-end with an actual interactive surface. Step 2.2 instantiates it for legitify; future tools reuse without new code.

```text
SCOPE: Build a typed SetupCard component that reads a tool's setup fields (setup_kind, setup_requirement, setup_probe) and renders the right input UX. Used in the Tool detail page when install_state === 'not-configured'.

REQUIRED READING:
1. campaigns/devsec-catalog-setup-flow.md (Context block)
2. dashboard-ui/src/components/catalog/CatalogToolPage.tsx — where the SetupCard mounts (replace today's "Installed — needs setup." eyebrow with the actual card when not-configured)
3. Step 1.1's PR — the new schema fields
4. Step 1.2's PR — the credential-storage HTTP endpoints
5. Voice doctrine from campaign #2 (docs/agent-voice.md) — copy register for the SetupCard's prompts and confirmations

RENDER BRANCHES (one per setup_kind):
- **env-var** — show the env var name + value-paste field + a "Store in Keychain" button. After storage, show "Stored" + "Forget" button.
- **api-key** — same as env-var, plus an optional "Generate a token →" link that deep-links to the provider's token-creation page with correct scopes preselected.
- **oauth** — "Connect <Provider>" button that opens an OAuth flow in the system browser. (v1: stub this to fall back to api-key behavior if oauth is too heavy for the first concrete case.)
- **file-path** — file picker (or text input + file-exists validation) + "Save path" button.
- **config-block** — multiline textarea + "Save" button that writes to ~/.security-observatory/config/<tool>.toml.
- **none** — never rendered (a tool without setup needs doesn't trigger SetupCard).

EVERY BRANCH ALSO:
- Shows the `setup_requirement` text prominently as the explanation of what's needed and why
- Surfaces the `setup_probe` after credential entry: "Test connection" button that runs the probe and reports success/failure with the probe's actual output (truncated to 5 lines)
- On probe success, flips the tool's install_state to 'detected' (server-side) and the UI re-renders with the "Detected locally" eyebrow
- On probe failure, shows the error inline and keeps the credential stored (user may want to fix scopes and retry rather than re-paste)

OUTPUT:
- New component dashboard-ui/src/components/catalog/SetupCard.tsx
- Wired into CatalogToolPage.tsx as the body when install_state === 'not-configured' and setup_kind !== 'none'
- The previous "Installed — needs setup." eyebrow becomes a header inside SetupCard instead of a standalone affordance
- Mocked storybook-style examples for each kind so the visual hierarchy is verified in isolation (or just walk through each in the running app)

OPEN QUESTIONS:
- Should there be a "Cancel setup" affordance? Recommend NO — leaving the setup card alone is the cancel. Adding a cancel button implies the setup is destructive.
- For api-key kind, how does the "Generate a token →" deep link know which scopes to preselect? Recommend a new optional field on the catalog entry: `setup.token_create_url` (e.g. https://github.com/settings/tokens/new?scopes=repo,admin:repo_hook&description=DëvSec%20legitify).
- For env-var kind, after storing in Keychain, do we also export it as an env var when DëvSec invokes the tool? Probably yes — the tool literally needs SCM_TOKEN in its env. Confirm the invocation path injects it.
```

## Step 2.2 — legitify Connect-GitHub PAT/OAuth flow (first instantiation)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Take the generic SetupCard from Step 2.1 and prove it works end-to-end with legitify. Paste a PAT, store in Keychain, run the probe (legitify against a public repo), flip state. The user goes from "Installed — needs setup" → fully-running platform-posture scan without leaving the app.

```text
SCOPE: Make legitify's Connect-GitHub flow work end-to-end. This is the first concrete instantiation of SetupCard; the test of whether the architecture from Step 2.1 actually delivers.

REQUIRED READING:
1. campaigns/devsec-catalog-setup-flow.md (Context block)
2. Step 1.1's PR — legitify's populated setup fields
3. Step 1.2's PR — credential-storage layer + HTTP endpoints
4. Step 2.1's PR — the SetupCard component (especially the api-key branch)
5. legitify's docs — confirm the actual command line for a probe call and the minimum scopes a token needs
6. src/security_observatory/scanners/ — wherever legitify is invoked; confirm SCM_TOKEN env var injection

CONCRETE FLOW (target):
1. User installs legitify via Step 0.2's install button → state flips to 'not-configured'
2. CatalogToolPage renders SetupCard with api-key branch
3. Card explains "GitHub Personal Access Token with `repo` + `admin:repo_hook` scopes" + a "Generate a token →" deep link to https://github.com/settings/tokens/new with scopes preselected and a description hint
4. User pastes PAT into the value field, clicks "Store in Keychain" → backend writes to Keychain under (DëvSec, legitify:SCM_TOKEN)
5. UI shows "Stored. Test connection?" with a "Test connection" button
6. Test connection runs the probe (legitify against a small public repo, with SCM_TOKEN from Keychain injected as env var)
7. On success, state flips to 'detected', SetupCard collapses, "Detected locally" eyebrow renders
8. User can now run `security-scan --platform-posture` from the CLI or click "Run platform posture scan" from the SetupCard's success state
9. (Optional) "Forget credential" button revokes the Keychain entry and flips state back to 'not-configured'

OUTPUT:
- Working end-to-end Connect-GitHub flow for legitify
- legitify's catalog entry has `setup.token_create_url` populated
- The legitify invocation path (scanners/legitify.py or wherever) reads SCM_TOKEN from Keychain via Step 1.2's API, falls back to env var if not in Keychain (preserving CLI-set token behavior)
- Live test: paste a real PAT, run the probe against a small public repo, confirm posture scan succeeds
- Documentation: short docs/tools/legitify-setup.md walking through the flow with screenshots

OPEN QUESTIONS:
- What public repo should the probe target by default? Recommend a small DëvSec-owned test repo (or this repo itself). User can override.
- Does legitify need to write any state to disk that we should treat as a credential too? If yes, extend Step 1.2's API to handle it.
- For Honey Keys + legitify both being in the catalog with different setup needs, does the SetupCard scale to those flows too? Quick mental walkthrough — surface any gaps.
- Should the "Run platform posture scan" button trigger via the same /api/run-check endpoint, or shell out via subprocess? Recommend /api/run-check for consistency with the rest of the dashboard.
```

## Step 3.1 — Source logos, define accent palette, render on cards and detail pages

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

Visual layer. Source each tool's logo, sample a single accent color from its brand, render both on the catalog cards and detail pages. Discipline: moderate respect, not theme takeover.

```text
SCOPE: Add per-tool branding (logo + one accent color) to catalog cards and detail pages. Source logos from each tool's official repo or brand assets page. Keep DëvSec's layout structure unchanged; brand the contents, not the chrome.

REQUIRED READING:
1. campaigns/devsec-catalog-setup-flow.md (Context block, especially the branding discipline)
2. dashboard-ui/src/components/catalog/CatalogBrowse.tsx — card rendering (today: identical DëvSec-styled cards)
3. dashboard-ui/src/components/catalog/CatalogToolPage.tsx — detail page
4. Reference patterns: VS Code Marketplace, Raycast Store, Linear integrations page

TOOLS NEEDING LOGOS (12 — excluding the 4 DëvSec-internal built-ins):
- Semgrep, Gitleaks, TruffleHog, Trivy, OSV-Scanner, Syft, Grype, Checkov, Medusa, legitify, malcontent
- (External Surface is coming-soon, no logo needed yet)

LOGO SOURCING:
- Pull SVG where available, PNG fallback
- Most OSS projects publish brand assets — check the project's repo `brand/` or `assets/` folder, or their README header
- Store in dashboard-ui/public/tool-logos/<id>.svg (or .png)
- License: most OSS tools allow logo use under their brand guidelines; quick check per logo, flag any that require explicit permission

ACCENT COLOR EXTRACTION:
- One color per tool, sampled from the tool's official wordmark/logo
- Stored as a hex in the catalog entry under `branding.accent_color`
- Used as a 4px stripe on the left edge of each card and as the underline beneath the tool name on the detail page

CARD RENDERING CHANGES:
- Logo replaces the generic category icon today shown on the card
- 4px accent stripe on the left edge of the card
- All other layout unchanged

DETAIL PAGE RENDERING CHANGES:
- Logo at top of hero section (where today there's just text)
- 1px accent underline beneath the tool name
- All other layout unchanged

DISCIPLINE:
- No background color changes
- No font changes
- No card-shape changes
- No theme takeover — VS Code Marketplace pattern, not theme switcher

OUTPUT:
- 12 logos sourced and stored
- `branding.accent_color` added to each tool's catalog entry
- CatalogBrowse.tsx + CatalogToolPage.tsx updated to render logo + accent
- Side-by-side before/after screenshots of the catalog browse grid (16 cards) and one detail page in the PR description
- License audit table: tool, license, brand-asset permission status

OPEN QUESTIONS:
- For tools without a published wordmark or with a generic icon, what's the fallback? Recommend: a category icon + a neutral accent (DëvSec's own accent color) so the card doesn't look broken.
- Should the 4 DëvSec-internal built-ins (Install hook classifier, IOC Watch, Workflow surface audit, Built-in AI static checks) get a DëvSec-internal accent + a "Built in" mark? Recommend yes — same visual language, just sourced from DëvSec instead of an upstream project.
- Where do we document the branding discipline (subtraction principle) for future contributors? Recommend a short docs/branding.md so the next person doing this doesn't drift into theme takeover.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the devsec-catalog-setup-flow campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-catalog-setup-flow.md
Campaign: campaigns/devsec-catalog-setup-flow.md (read inline against the cumulative diff on the devsec-catalog-setup-flow branch)

Read every `## Step N.M — name` heading in the campaign markdown. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff that the criteria actually landed. Don't trust step receipts — read the diff.

Catch cross-step shortcuts: a primitive set up in one step silently bypassed by another, intent claimed in early steps but undermined by later ones, dead code left behind, regressions in unrelated areas.

Specific things to verify:
- The Keychain credential layer from Step 1.2 is the only credential-storage path used in the codebase (no parallel "encrypted file in repo" shortcut taken in Step 2.2)
- SetupCard's render branches from Step 2.1 are actually used in Step 2.2's legitify flow (not bypassed by a per-tool React component)
- Schema additions from Step 1.1 (setup_kind, setup_requirement, setup_probe) are populated for every not-configured tool, not just legitify
- The install button generalization from Step 0.2 covers homebrew, uv-tool, and manual — verify each path works end-to-end
- Per-tool branding from Step 3.1 honors the subtraction discipline (no theme takeover, no font/background changes per tool)
- Credential values are never logged, never returned to the frontend, never echoed to stdout (Step 1.2)
- The vocabulary lock from campaign #5 holds in every new piece of UI copy this campaign added
- Step 0.1's self-recalibration edits are reflected in the work that followed (don't trust that Step 0.1 ran — verify the later steps actually used its updates)

Be honest. Lean. APPROVED if every step's acceptance criteria landed and there are no cross-step regressions. NEEDS WORK if any step cut corners or a primitive was bypassed.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.7 with Extra High thinking
(Your call — both are acceptable for this kind of cross-file review.)
```

**Verdict-to-action mapping:**

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign"). Merge the `devsec-catalog-setup-flow` branch into `main`. Campaign is done.
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick the checkbox until APPROVED.
