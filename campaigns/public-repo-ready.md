# Public Repo Readiness — make every button honest before the world sees it

> Right now there are 13 small lies on the screen — buttons that don't do what they say, a fake helper that doesn't exist, a docs link that dumps raw text at you. Fix every one of them, write the few files a stranger needs to understand the project, and only then put it online for the world to see.

## Scope

The walkthrough audit at `reports/walkthrough-audit-20260523-102224/` produced a 13-finding punch list across user-blocking, polished-but-lying, half-built, and stale-promise categories. This campaign closes every one of them without expanding scope, then earns the rest of "public-repo readiness" — a LICENSE, a CONTRIBUTING.md, a hardened `.gitignore`, a README opener that works for a stranger, a few screenshots, and a final clean walkthrough proving the punch list is empty. Done means (a) every visible affordance does what its label says, (b) the repo has the standard files a public GitHub project needs, and (c) the last walkthrough returns zero findings. The campaign does **not** make the repo public — that's Christian's flip when this lands.

## Context (locked decisions)

- **Source of truth for findings**: `reports/walkthrough-audit-20260523-102224/punch-list.md`. Each step lists which finding IDs it closes. If a step lands a fix that doesn't match the punch list, the punch list wins — re-read it before declaring done.
- **Bounded by the audit**: new findings discovered along the way get appended to the punch list under their phase, not expanded into separate work. No accidental scope creep.
- **Stays clear of `agent-lab-byom.md` Phase 2–3**: no Agent Lab planner UI, no proposal import flow, no provider connection state strings, no exportable agent context. Those belong to that campaign.
- **F-002's "Agent live · tailing scanners" header pill IS in scope here.** It is a different fake-agent (a fake scanner-tailing process), not the Agent Lab AI assistant. Removing or relabeling it now makes Agent Lab's eventual introduction cleaner — two "agents" in the UI would be confusing.
- **DESIGN.md is canon.** Same smell test, same §15 build checklist as catalog-polish. Sentence case, one primary action, mono only on telemetry, no looping motion. Don't redesign anything that already passes.
- **Smallest honest fix.** Each finding has one correct fix. Don't accidentally refactor neighbouring code. Don't add new abstractions. Don't introduce new components when an existing one would do.
- **Tests stay green at the end of every step**: `uv run pytest`, `cd dashboard-ui && npm run lint`, `cd dashboard-ui && npm run build`.
- **Branch**: `public-repo-ready`, off `main`. Merge to `main` when Final review is APPROVED. Do not push or open a PR until the final review verdict.
- **The repo flip itself is out of scope.** The last step proves "you can safely flip" — Christian runs `gh repo edit --visibility public` afterwards if and when he wants to. No automation that flips visibility.
- **Pre-public security sweep is non-negotiable.** Step 4.3 must confirm dëv-security's own git history is clean of real secrets, credentials, and personal paths before this lands. If anything dirty is found, that becomes a launch blocker — surface it, don't quietly scrub it.
- **Brand identity is locked**: the dashboard brand is **DëvSec**. The formal/PyPI/package name remains **security-observatory** (for backward-compat and CLI stability). The README opens with DëvSec and explains the package name once. The GitHub repo stays `dev-security` for now; renaming to `devsec` post-launch is a separate decision.
- **License is locked: Apache-2.0.** Patent grant matters for a security tool; matches the ecosystem (Trivy, Semgrep, OSV-Scanner, Syft are all Apache-2.0). Do not relitigate this in Step 4.1.
- **Audit evidence under `reports/walkthrough-audit-*/evidence/*.png` is committed**, not gitignored. The screenshots are part of the audit artifact, referenced from punch-list.md, and prove the discipline. Do not exclude them.
- **SECURITY.md is required, not optional.** This is a security tool — a missing disclosure path is a tell. Step 4.1 ships SECURITY.md (10 lines pointing at GHSA or email).
- **No issue templates / PR templates at launch.** Skip until a malformed issue from a stranger forces the question. Don't pad `.github/` with ceremony.
- **CHANGELOG.md is in scope.** One initial `## 0.1.0 — initial public release` entry. Step 5.1 tags `v0.1.0` before the public flip.
- **F-003 path locked: (A) in-app docs rendering, server-side, stdlib-only.** Docs render through a minimal Markdown→HTML converter in `src/security_observatory/docs_render.py`, wrapped in a DëvSec docs page shell served from `/docs/<file>.md`. Local-first ethos wins; Python `dependencies = []` stays intact; dashboard-ui bundle unchanged.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Silent gates and dishonest buttons

- [x] Step 1.1 — Fix the `target=dashboard` silent-gate pattern (F-001, F-006, F-008)
- [x] Step 1.2 — Remove the fake agent pill and wire the Export no-op (F-002, F-005, F-013)
- [x] Step 1.3 — Honest install labels for built-in and locally-detected tools (F-004, F-012)

### Phase 2 — Honest docs and disclosure

- [x] Step 2.1 — Render in-app docs or relink to vendor URLs (F-003)
- [x] Step 2.2 — Reconcile health score scale and surface the platform-posture token gate (F-009, F-010)

### Phase 3 — Half-built things, finish or hide

- [x] Step 3.1 — Real per-class recovery playbooks, or honest narrower title (F-007)
- [x] Step 3.2 — Ship the Activity heatmap, or replace it with something that earns its space (F-011)

### Phase 4 — Repo hygiene for a public audience

- [x] Step 4.1 — LICENSE, SECURITY.md, CONTRIBUTING.md, CHANGELOG.md, hardened `.gitignore` *(parallel with 4.2)*
- [x] Step 4.2 — README polish for strangers + screenshots/GIF + brand reconciliation *(parallel with 4.1)*
- [x] Step 4.3 — Pre-public security sweep on dëv-security's own git history *(runs LAST in Phase 4, after 4.1+4.2)*

### Phase 5 — Prove it

- [x] Step 5.1 — Re-run the product walkthrough audit, confirm punch list is empty, fix any new findings inline
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Fix the `target=dashboard` silent-gate pattern (F-001, F-006, F-008)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Three findings — Run all disabled with no tooltip, Rerun checks no-op on Recovery playbooks, Open profile sheet contradicting itself — share one root cause: the default target on first load is the synthetic `dashboard` aggregate, and every "run a scan" affordance silently gates on `target.type === 'repo'`. Fix the root, not the symptoms. **Path locked: (B) keep `dashboard` as default and explain every gated affordance.** Path A would change the dashboard's mental model ("see your whole world" → "see your last-scanned repo") which is a worse first impression for a public-repo debut than slightly-less-elegant tooltips.

```text
SCOPE: Close F-001, F-006, and F-008 by making every silent gate at target.type === 'dashboard' visibly explain itself.
REQUIRED READING:
1. reports/walkthrough-audit-20260523-102224/punch-list.md (read F-001, F-006, F-008 in full)
2. dashboard-ui/src/App.tsx (lines 553–800 — target state, isCheckOpen useEffect, RunCheckSheet, header toolbar)
3. dashboard-ui/src/App.tsx (lines 1468–1530 — PlaybooksView, VerificationView)
4. dashboard-ui/src/components/catalog/CatalogPackPage.tsx (Open profile button)
5. DESIGN.md (§0 smell test, §15 checklist)
PRE-FLIGHT (do this before editing):
- Grep for every caller of setIsCheckOpen and every conditional on target.type === 'dashboard' across dashboard-ui/. The useEffect at App.tsx:609 is a guard that hides broken behavior; removing it may surface other code paths that silently depended on it. Surface anything that looks load-bearing before changing it.
OUTPUT:
- Keep `dashboard` as the default target. Stop pretending the gated buttons are inert:
  · Run all (header toolbar): hover tooltip "Pick a repo first" via title= and aria-label. Keep button enabled; on click with target=dashboard, open the repo picker dropdown with a one-line note above it.
  · Rerun checks (Recovery playbooks): when target=dashboard, render a calm one-line note above the playbook cards ("Switch to the repo where the finding lives to rerun its check"), and visibly disable the per-card button with a matching tooltip.
  · Open profile (Pack page): on click with target=dashboard, the sheet that opens has a sane first row that says "Pick a repo to run checks against" with the repo dropdown inline. The Start button activates once a real repo is selected. No more "Choose a repo target" title with a disabled Start and no picker.
- Remove the useEffect at App.tsx:609 that silently slams setIsCheckOpen(false) — it is the mechanism that hides the bug — only after the pre-flight grep confirms no other code path depends on it.
- Introduce ONE shared "needs a repo target" inline-helper component (small one-line note + optional inline picker) and reuse it across all three affordances. Three slightly-different one-liners would be worse than one consistent primitive.
- npm run lint, npm run build, and uv run pytest all pass.
OPEN QUESTIONS:
- Once the shared helper exists, does Verification view's Run checks button suffer the same silent-gate problem? It's not in this finding set, but if it lights up dim-with-no-explanation on target=dashboard, fix it inline with the same primitive.
```

## Step 1.2 — Remove the fake agent pill and wire the Export no-op (F-002, F-005, F-013)

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

Three small lies, one clean diff. The "Agent live · tailing scanners" header pill and Pause/Resume toggle exist only in `useState` — no scanners are being tailed, no agent is being paused. Take them down. The Settings → Export button has no onClick handler — either wire it or remove it (preference: remove until there's a real export endpoint to call). The Trivy detail page's "Last runtime: ran" row has no timestamp — either render a real timestamp or drop the row.

```text
SCOPE: Close F-002, F-005, and F-013 by removing affordances that don't do anything and only render rows that have real data.
REQUIRED READING:
1. reports/walkthrough-audit-20260523-102224/punch-list.md (F-002, F-005, F-013 in full)
2. dashboard-ui/src/App.tsx (lines 555–565, 920–1030 — agentRunning state, sidebar status pill, toolbar Pause/Resume)
3. dashboard-ui/src/App.tsx (lines 1760–1775 — Settings Privacy and storage Export row)
4. dashboard-ui/src/components/catalog/CatalogToolPage.tsx (Setup and ownership block, Last runtime row)
5. DESIGN.md (§0 smell test)
OUTPUT:
- Remove the `agentRunning` useState, the Pause/Resume IconButton in MistToolbar, and the agent status pill block in the sidebar that reads "Agent live · tailing scanners" / "Agent paused · tap resume". The replacement, if any, should be honest — e.g. a "Last refresh 10:22 AM" line that already exists elsewhere. No pulsing dot, no "live" word.
- Settings → Generated reports row: remove the Export button entirely. Leave the row's subtext ("Reports remain local unless you export or share them.") — it remains true without a button. A button on this row implied a feature that doesn't exist.
- Tool detail Last runtime row: if there is no timestamp data, drop the row. If a real timestamp is available in tool.scanner_key runtime, render it as "12 d ago" / "Never run". The word "ran" alone is not acceptable.
- npm run lint, npm run build, uv run pytest pass.
OPEN QUESTIONS:
- The agent pill is also visible on every screen — does its removal leave the sidebar feeling top-heavy or empty? If so, the calm move is to leave that vertical space alone, not to fill it with a different widget.
- Note for handoff with [[agent-lab-byom]]: that campaign is building a real Agent Lab feature. The pill we are removing is unrelated — a fake scanner-tail process — and removing it makes Agent Lab's eventual introduction less confusing.
- PRE-FLIGHT cross-check: before removing the pill, grep `campaigns/agent-lab-byom.md` and `campaigns/agent-lab-byom/` for any reference to the existing sidebar agent pill or `agentRunning` state. If agent-lab-byom scaffolds onto that pill, surface the conflict before the diff lands — don't silently break the other campaign's primitive.
```

## Step 1.3 — Honest install labels for built-in and locally-detected tools (F-004, F-012)

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 1.2

The catalog uniformly labels every tool's primary CTA "Install plugin" — including built-in tools that can't be installed and already-detected tools that don't need re-installing. The detail page already disables the button correctly for built-ins, but the home-page popular-plugin cards and the Trivy detail page (state: Detected locally) lie about what's possible. Branch the label and the next-step text on install state.

```text
SCOPE: Close F-004 and F-012 by making the catalog CTA tell the truth about each tool's install state.
REQUIRED READING:
1. reports/walkthrough-audit-20260523-102224/punch-list.md (F-004, F-012 in full)
2. dashboard-ui/src/components/catalog/CatalogToolPage.tsx (CTA logic, install_state branching)
3. dashboard-ui/src/components/catalog/CatalogBrowse.tsx (Popular plugins cards, Featured banner)
4. src/security_observatory/catalog.py (homepage_url, install_state, lifecycle fields)
5. src/security_observatory/managed_tools.py (APPROVED_MANAGED_INSTALL_TOOL_IDS, previewCanInstall logic)
OUTPUT:
- CatalogBrowse Popular plugins cards: replace the universal "Install plugin" label with state-aware text:
  · install_state === 'built-in' → "View tool" (routes to detail page, no install promise)
  · install_state === 'detected-locally' → "View tool" (already installed; nothing for the user to install)
  · install_state === 'managed-install-available' → "Install plugin" (the current behavior, but only when truly installable)
  · install_state === 'coming-soon' or 'display-only' → no button (or the calm display-only note already used elsewhere)
- Trivy and other "Detected locally" tool detail pages: rework the install hero so the active CTA reads "Reinstall via Homebrew" (or hide it entirely) and the NEXT STEP no longer says "Install Trivy, then rerun…" when install_state proves it's already installed. The next-step text comes from tool.install.next_step — fix it at the source in src/security_observatory/managed_tools.py or wherever it's authored, not in the React layer.
- Featured banner ("Featured: Trivy") at the top of CatalogBrowse: the "Install" button next to "View tool" should follow the same state-aware logic.
- npm run lint, npm run build, uv run pytest pass.
OPEN QUESTIONS:
- Is "Reinstall via Homebrew" useful enough to keep, or is hiding the button entirely on detected-locally tools the calmer choice? A reinstall is rarely needed unless the user is debugging an outdated binary.
- Should the four Popular plugins cards on the catalog home be re-ranked to surface tools that actually have an installable action? Right now two of four are built-in and can't be installed at all from the UI.
```

## Step 2.1 — Render in-app docs or relink to vendor URLs (F-003)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 2.2

The "Read documentation" link on built-in tool detail pages serves the raw markdown source from `docs/<file>.md` to the browser with `Content-Type: text/markdown`. Most browsers render that as a wall of plain text — `#` and `|` characters and all. The link looks finished but delivers nothing readable. Two paths exist: render the docs in-app (a small markdown view at `/docs/<slug>`), or point the link at a hosted URL (the GitHub-rendered version of the file once the repo is public). Pick the path that holds up after the repo goes public.

```text
/innovate

SCOPE: Choose between in-app docs rendering and external linking for F-003, then implement.
REQUIRED READING:
1. reports/walkthrough-audit-20260523-102224/punch-list.md (F-003 in full)
2. reports/walkthrough-audit-20260523-102224/evidence/F003-docs-raw-markdown.png (what the user actually sees today)
3. src/security_observatory/dashboard_server.py (current docs path handling)
4. src/security_observatory/catalog.py (docs_path and homepage_url fields per tool)
5. docs/agent-lab.md (a representative file that this link currently points at — long, structured, with tables; renders as a useful styled page only when something interprets the markdown)
6. DESIGN.md (§0 smell test, §15 checklist)
OUTPUT:
- Innovate brief: compare (A) in-app docs rendered by a small `react-markdown` (or similar) component at `/docs/<slug>` that fetches `docs/<file>.md` and renders with the dashboard's existing typography, vs. (B) point docs_path at the public GitHub URL once the repo goes public (e.g. https://github.com/Christian-Katzmann/dev-security/blob/main/docs/agent-lab.md), accepting that the link breaks until the repo is public.
- Lock the choice in this campaign's Context section (append a one-line note).
- Implement the chosen path. If (A): add the renderer, update the docs_path resolution, drop the raw text/markdown route. If (B): catalog.py author every docs_path that currently points at a local docs/ file to the GitHub URL instead, and remove the raw markdown route on dashboard_server.py.
- Verify every "Read documentation" link in the catalog (built-in tools + external tools) renders something a stranger would call documentation, not source code.
- npm run lint, npm run build, uv run pytest pass.
OPEN QUESTIONS:
- (A) keeps the link working offline (local-first ethos), but adds a markdown renderer to the dashboard bundle. (B) keeps the bundle small and matches what external tools (Trivy, Gitleaks) already do (vendor URL), but the link breaks until the repo is public — which is a few steps from now in this campaign. Which fits the local-first stance better?
- If (B), are there docs files that contain repo-internal references unsafe to expose publicly (audit reports, plan dumps)? Those should stay private and not be linked from the catalog.
```

## Step 2.2 — Reconcile health score scale and surface the platform-posture token gate (F-009, F-010)

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 2.1

Two small honesty fixes about scales and prerequisites. The README's §Health Score table is written for a 0–100 scale; the dashboard renders the same score as `X / 10`. Pick one scale and propagate. Separately, the "Connected platform" checkbox in the run-check sheet sits as a peer to other scans, with a one-line description that doesn't mention it requires `SCM_TOKEN` set in the environment — a user ticking it without the token gets a silent partial scan.

```text
SCOPE: Close F-009 (health score scale mismatch between README and UI) and F-010 (platform-posture token requirement is invisible in the run-check sheet).
REQUIRED READING:
1. reports/walkthrough-audit-20260523-102224/punch-list.md (F-009, F-010 in full)
2. README.md (the §Health Score table and the §Platform posture paragraph that already explains the SCM_TOKEN requirement)
3. dashboard-ui/src/App.tsx (postureScore at line 311, RunCheckSheet around line 1032)
4. src/security_observatory/cli.py (how --platform-posture detects SCM_TOKEN absence)
5. DESIGN.md (§0 smell test)
OUTPUT:
- F-009: pick one scale. Recommended: update the README §Health Score table to express penalty values on the displayed 0–10 scale (so -40 capped at -80 becomes -4 capped at -8, etc.) AND add a single sentence to the table explaining that the engine computes internally on 0–100 and the dashboard normalizes for display. Alternatively, change the UI to show `33 / 100` instead of `3.3 / 10`. Either is acceptable; pick whichever needs fewer file touches and is calmer to read.
- F-010: in the run-check sheet, when "Connected platform" is rendered, append a small badge or sub-line that reads (calmly) "Needs SCM_TOKEN" and, on hover or click, opens an inline note explaining how to set it before relaunching the dashboard. Better still: detect SCM_TOKEN absence in the backend, expose it as a flag in the summary, and hide or visibly disable the checkbox when it's missing. Hidden-by-default may be the cleanest path.
- README and UI must agree on the scale after this step.
- npm run lint, npm run build, uv run pytest pass.
OPEN QUESTIONS:
- For F-009, does the CLI's JSON output (`security-scan . --json`) also emit the 0–100 number? If so, that's a third surface and a public consumer might depend on it — don't change the JSON without surfacing the impact.
- For F-010, hiding the option when SCM_TOKEN isn't set is calmer but means the user doesn't discover the feature exists. Is there a middle ground (show greyed out with "Needs SCM_TOKEN" label)?
```

## Step 3.1 — Real per-class recovery playbooks, or honest narrower title (F-007)

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 3.2

The Recovery playbooks screen plural-promises "playbooks" but renders six identical "Rotate live secret + scrub history" cards — all 4 steps, all sourced from `gitleaks`, only wall-clock estimates differ. With findings spanning leaked secrets, dependency CVEs, AI-agent risks, and IaC misconfigs, a user expects categorized recovery guidance. Either generate one playbook per case-class (the right answer), or relabel the screen so it stops over-promising.

```text
SCOPE: Close F-007 by either generating real per-class recovery playbooks or relabeling the screen to match what it actually shows.
REQUIRED READING:
1. reports/walkthrough-audit-20260523-102224/punch-list.md (F-007 in full)
2. reports/walkthrough-audit-20260523-102224/evidence/recovery-playbooks.png (current state)
3. dashboard-ui/src/App.tsx (PlaybooksView around line 1468)
4. src/security_observatory/cases.py (how cases are grouped — the natural place to derive playbook templates from)
5. src/security_observatory/normalize.py (finding categories: leaked-secrets, dependency-risks, ai-agent-risks, iac-misconfig)
OUTPUT:
- Lock a path: (A) generate playbooks per case-class, not per finding — one playbook per of: leaked secret rotation, dependency CVE upgrade, AI-agent config hardening, IaC misconfig remediation. Each playbook lists the matching open findings as items inside it. (B) leave generation as-is but relabel the screen "Cases waiting on: Rotate live secret + scrub history" (or whatever the dominant case is) so the screen's title matches its content. Path A is the higher-leverage fix; B is the smaller-diff fallback.
- If (A): the playbook records (steps, wall-clock estimate, "rerun matching DëvSec check" action) should be expressible as templates keyed on case category, instantiated with the affected files list. Don't hardcode 6 identical records.
- Either way, the screen should never render six copies of the same card.
- npm run lint, npm run build, uv run pytest pass. Add at least one cases.py test that exercises the new grouping if path A is taken.
OPEN QUESTIONS:
- Path A is real product work and might bleed into Phase 4 of this campaign. Is the calmer call to ship (B) now and queue (A) as a follow-up campaign? The audit lists this as half-built, not user-blocking — a relabel is honest enough for the public-repo bar.
- The "Rerun checks" button on each playbook will be fixed by Step 1.1's silent-gate work; don't redo that here.
```

## Step 3.2 — Ship the Activity heatmap, or replace it with something that earns its space (F-011)

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 3.1

The Activity page's "AUDITS · 24 H × 7 D" heading sits above an empty plot area — day labels (Sun–Sat) render fine, no cells. Below it the "Event mix · 7 D" panel does the same job in numbers, so this heatmap is purely decorative right now. Either render the cells from `summary.history` data, or replace the heading with something that earns the slot (a sparkline, a per-day count, or just remove the section).

```text
SCOPE: Close F-011 by either rendering the audits heatmap or replacing it with a useful summary that uses real data.
REQUIRED READING:
1. reports/walkthrough-audit-20260523-102224/punch-list.md (F-011 in full)
2. reports/walkthrough-audit-20260523-102224/evidence/activity.png (current empty state)
3. dashboard-ui/src/App.tsx (ActivityView and the heatmap heading block)
4. dashboard-ui/src/dashboardData.ts (history field shape)
5. DESIGN.md (§0 smell test — does the section earn its space?)
OUTPUT:
- Either:
  (A) Render the heatmap: a 24-row × 7-column grid of cells coloured by audit count per hour-bucket per day, sourced from summary.history. Cap visual complexity — calm, not heavy. Avoid traffic-light coloring; use a monotone scale.
  (B) Replace the section with a per-day count strip: "Sun 0 · Mon 0 · Tue 0 · Wed 1 · Thu 0 · Fri 0 · Sat 12" using the same history data. Compact, honest, takes a quarter of the vertical space.
  (C) If the heatmap and "Event mix · 7 D" panel below would say the same thing, drop the heatmap heading entirely and let "Event mix" carry the weight.
- Whichever is picked, no empty plot area with a heading above it.
- npm run lint, npm run build, uv run pytest pass.
OPEN QUESTIONS:
- For a local-first tool that one person uses, is a 24×7 heatmap actually the right shape? In a multi-developer org it'd be useful; in a solo setup the same datapoint mostly means "did Christian run scans today." Option B or C may be calmer and more honest.
```

## Step 4.1 — LICENSE, SECURITY.md, CONTRIBUTING.md, CHANGELOG.md, hardened `.gitignore`

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: YES — with Step 4.2

Five small files a stranger expects on a public GitHub repo. The current `.gitignore` is sparse (about 12 lines, mostly Python/Node basics) — security-relevant paths and macOS/IDE clutter need to be added so future commits don't accidentally ship sensitive state. No LICENSE means anyone landing on the repo can't legally reuse the code. No SECURITY.md on a *security tool* is a tell. No CONTRIBUTING.md means strangers don't know how to file a PR. No CHANGELOG means no one can pin to a release.

```text
SCOPE: Add LICENSE, SECURITY.md, CONTRIBUTING.md, CHANGELOG.md, and harden .gitignore for public-repo hygiene.
REQUIRED READING:
1. README.md (tone, voice, what's already promised about contributions and licensing)
2. .gitignore (the current 12 lines — see what's missing)
3. AGENTS.md (operating rules — anything in here that should also live in CONTRIBUTING)
4. .adx/recovery.md (any pointer to issue/PR conventions)
5. ~/.security-observatory/ path conventions (so .gitignore doesn't accidentally allow scan output)
OUTPUT:
- LICENSE: write Apache-2.0 (locked in Context). Use the canonical SPDX text, no edits except the copyright line: "Copyright (c) 2026 Christian Katzmann". Name the file LICENSE, no extension.
- SECURITY.md: ~10 lines. Cover: supported versions (just 0.x for now), how to report a vulnerability (default to GitHub Security Advisory: "Use the Report a vulnerability button on the Security tab — please do not open public issues for security bugs"), expected response time (one calm sentence — e.g. "I aim to acknowledge within 7 days; this is a solo project, response times reflect that"), scope (in-scope: the dashboard server, the CLI, the scanner orchestration. out-of-scope: third-party scanner binaries themselves — report those upstream). No PGP key boilerplate unless explicitly wanted.
- CONTRIBUTING.md: short, calm, honest about the project's bar. Cover: how to get the local stack running (point at install-security-observatory.sh and README §Installation), how the test suite is run (`uv run pytest`, `npm run lint`, `npm run build`), how to file an issue or PR, a one-line "security disclosure: see SECURITY.md, not here", and the project's "calm UI, no looping motion, sentence case" stance pointing at DESIGN.md. Don't pad with code-of-conduct boilerplate.
- CHANGELOG.md: Keep-a-Changelog format. One initial entry: `## [0.1.0] - 2026-MM-DD\n### Added\n- Initial public release. Local-first security scanning, dashboard, honey keys, named-campaign IOC matcher.`. Step 5.1 will tag v0.1.0 against this entry before the public flip.
- .gitignore additions (append, don't rewrite):
  · macOS/IDE: `.DS_Store`, `.idea/`, `.vscode/`, `*.swp`, `.Trash-*`
  · logs/temp: `*.log`, `*.tmp`
  · secret-shaped: `.env`, `.env.*`, `*.local`, `*.pem`, `*.key`, `*.crt`, `*.p12`, `*.pfx`
  · DO NOT gitignore `reports/walkthrough-audit-*/evidence/*.png` — these are part of the audit artifact and stay committed (locked in Context).
  · Pre-flight: run `git status -uall` after Phase 1–3 commits to surface anything new that needs ignoring.
- Don't add CODE_OF_CONDUCT.md (premature for a solo project). Don't add `.github/ISSUE_TEMPLATE/` or PULL_REQUEST_TEMPLATE.md (locked: skip at launch).
- uv run pytest passes (no test impact expected).
OPEN QUESTIONS:
- SECURITY.md disclosure path: GHSA (recommended — durable, surfaced by GitHub UI) or christian@katzmann.dk (more personal, but harder to keep visible)? Default: GHSA, mention email as fallback.
- CHANGELOG date: leave as "Unreleased" until Step 5.1 confirms ready-to-tag, then fill in the real date when v0.1.0 is tagged?
```

## Step 4.2 — README polish for strangers + screenshots/GIF

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: YES — with Step 4.1

The current README is long, accurate, and written for someone who already trusts the project enough to read installation steps. A first-time visitor needs the first screen to answer: "what is this?", "is it real?", "what would I see if I ran it?". That means a tight opener, a screenshot or GIF showing the dashboard, and a one-line "Why I built this" before the dense feature list. Don't rewrite the existing content — front-load it.

```text
/zero-generic

SCOPE: Restructure the README's opening so a stranger arriving from a Google search or HN link understands what DëvSec is in the first 30 seconds. Add a screenshot. Reconcile branding (DëvSec is the dashboard brand; security-observatory is the package name).
REQUIRED READING:
1. README.md (the whole file — don't lose anything that's correct)
2. AGENTS.md (the calm honest tone of voice — let that survive into the README opener)
3. DESIGN.md (the "calm, honest, local-first" stance — that should be the opener's spine)
4. reports/walkthrough-audit-20260523-102224/evidence/overview-initial.png (the dashboard hero — candidate for the README screenshot, AFTER the punch-list fixes land)
5. Existing screenshots in repo root (NOT in assets/): devsec-data-coverage-settings.png, devsec-data-surfacing-findings.png, named-campaign-matches.png — can any be reused? Move them to docs/images/ as part of this step regardless.
OUTPUT:
- New README opening (above the existing "What It Is" block): tight title ("DëvSec — local-first security observability"), 2-sentence tagline, 1 hero screenshot or GIF (PNG is fine — animated GIF only if it shows real motion, not loading spinners), a 4-line "Why this exists" paragraph aligned with the local-first / no-cloud-LLM stance.
- Brand reconciliation: open with **DëvSec** as the product name. Include one parenthetical line near the top: "(installed as the `security-observatory` Python package; the CLI is `security-scan`)" so the package/CLI/brand mismatch is explained once, not implicit.
- The screenshot should be the post-fix Overview screen (taken AFTER Phase 1–3 land), not the current one with the fake agent pill and 13 findings. Step 5.1 will regenerate and place it.
- Move the three repo-root screenshots into `docs/images/` (or `assets/screenshots/`, whichever is more consistent with the existing layout). Repo-root PNGs read as untidy on a public landing page.
- Add one calm "Status: 0.1.x — early. Local scanning works well; the dashboard is honest about what's still partial." line near the top.
- Existing sections stay where they are — don't shuffle "What It Is", "Current Features", "Installation", "Usage", "Local Data", "Privacy and Safety Defaults", "Health Score", "Development". Just front-load.
- Remove the "Coming Soon" badges from in-product features that are real already (Honey Keys, the catalog) and only keep them on External Surface and Pack-level install.
- README must pass /zero-generic's smell test: no "🚀 Easy to use!", no badges-for-badges'-sake row, no "Tech stack" list with logos. If a badge earns its place (license, Python version, build status), keep it; otherwise drop it.
- README must not promise anything the audit punch list flagged as broken. If a section describes a feature that's only partially built, the description has to match the level of finish.
OPEN QUESTIONS:
- Is an animated GIF (cast via vhs or asciinema) worth the file size for a local-first tool, or is a single PNG screenshot the calmer choice?
- Should the README mention DëvSec is the author's first public security project, or is that humble-bragging that doesn't help the reader? Default: leave it out; let the work speak.
```

## Step 4.3 — Pre-public security sweep on dëv-security's own git history

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO — runs as the LAST step of Phase 4, after 4.1 and 4.2 commits have landed. This is the final gate before Phase 5.

Before this repo goes public, run the same scanners DëvSec ships at DëvSec itself, then audit the result. The walkthrough audit showed lots of secrets findings — but those were in OTHER repos being scanned (beskæftigelse.dk: 371 findings, mostly secrets). This step confirms dëv-security itself has no real secrets, no personal paths committed, no internal URLs in test fixtures, and no audit artifacts that quote sensitive content from the other repos. Runs LAST in Phase 4 because the sweep must cover the final merge-ready state including the new files from 4.1 (LICENSE, SECURITY.md, CHANGELOG.md, hardened .gitignore) and the relocated screenshots from 4.2. If anything dirty is found, surface it — don't quietly scrub history without Christian's call.

```text
SCOPE: Run a clean security sweep on dëv-security itself in its final pre-merge state and audit the output for anything that would embarrass on a public repo.
REQUIRED READING:
1. README.md (Local Data section — where scan output normally lives)
2. .gitignore (the post-Step-4.1 version)
3. reports/ (everything currently committed under this folder — audit artifacts may quote external repo content)
4. campaigns/ (everything currently committed — campaign markdown may contain working notes with paths to other projects)
5. .adx/journal.jsonl, .adx/audit/, .adx/claims.jsonl (per-agent journals — may contain transcripts)
OUTPUT:
- Run: `security-scan . --full --fail-on critical` against the dëv-security repo itself. Save the raw report.
- Audit the report manually: every finding's location must be either (a) a true positive worth fixing before going public, or (b) a clean false-positive (e.g. an example string in a docs file) that's safe to ship.
- Audit grep checks not in scanner scope:
  · `git log --all -p | grep -iE 'password|secret|token|api.key|bearer'` — any actual credentials in history?
  · `git ls-files | xargs grep -l '/Users/christiankatzmann/' 2>/dev/null` — personal absolute paths that should be relative or templated?
  · `git ls-files reports/ campaigns/ .adx/` — do any committed files quote private content from beskæftigelse.dk or other client repos?
- If any true positive is found, STOP and flag to Christian as a launch blocker. Do not rewrite history without an explicit decision. The right tool when that decision is made is **BFG Repo-Cleaner** (faster, safer, designed for this), not `git filter-branch`.
- If everything is clean, write `reports/pre-public-sweep-<timestamp>.md` recording the sweep date, scanner versions, what was checked, and "clean" verdict.
OPEN QUESTIONS:
- Audit artifacts under reports/walkthrough-audit-*/evidence/ are screenshots of the dashboard, taken with the dashboard pointing at the user's full repo list. Do the screenshots reveal sensitive repo names (beskæftigelse.dk, monëy.com, etc.) that Christian doesn't want public? Default: probably fine — they're project names, not secrets — but worth a sanity check. If not, blur or rename before merge.
- The .adx/ journal files and the campaigns/ folder may contain working notes with internal context. Should anything in .adx/ be in .gitignore for the public repo, or is it intentional that agents arriving at the repo see the journal? Default: keep .adx/ contents committed — they're agent-onboarding infrastructure and a feature of this repo, not a leak. But scan them.
- If a real secret is found in history, what's the threshold for rewriting history vs. just rotating the secret? Default policy: rotate, then rewrite via BFG if the secret was sensitive enough to warrant losing git provenance.
```

## Step 5.1 — Re-run the product walkthrough audit and confirm the punch list is empty

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Boot the dashboard, walk every surface the original audit covered (plus the ones it skipped on safety grounds where now possible), and confirm zero open findings. Capture a fresh hero screenshot for the README (the one Step 4.2 promised). Fix any small new findings inline — this step is allowed to land tiny diffs (label tweaks, missing tooltips) without spawning a new step. Anything bigger gets appended to the punch list and surfaced.

```text
/product-walkthrough-audit DëvSec

SCOPE: Re-run the walkthrough audit on DëvSec after every fix in this campaign has landed. Confirm zero open findings from the original 13. Capture a fresh hero screenshot.
REQUIRED READING:
1. reports/walkthrough-audit-20260523-102224/punch-list.md (the original 13 findings — verify each is now genuinely fixed in the running app, not just in the diff)
2. reports/walkthrough-audit-20260523-102224/coverage-receipt.json (the surfaces skipped on safety grounds — some can be tested now that fixes are in)
3. campaigns/public-repo-ready.md (this file — to confirm every step's acceptance criteria landed)
OUTPUT:
- A new audit report at reports/walkthrough-audit-<new-timestamp>/punch-list.md.
- If the new punch list is empty: write "PUNCH LIST CLEAR" at the top and capture a fresh dashboard hero screenshot to reports/walkthrough-audit-<new-timestamp>/evidence/overview-final.png. That screenshot becomes the README hero (Step 4.2 placeholder gets replaced with this image).
- If the new punch list is not empty: each remaining finding gets a one-line classification (regression of original / new issue) and a recommendation: fix inline now (label tweaks, missing tooltips, copy fixes), or surface as a launch blocker that reopens a step in this campaign.
- Verify the a11y nit from the original audit (console: "A form field element should have an id or name attribute, count: 2") is also resolved.
- npm run lint, npm run build, uv run pytest all pass in the final state.
- **Pre-flip GitHub metadata checklist** (the public repo card people will land on):
  · `gh repo edit Christian-Katzmann/dev-security --description "<one-line description of DëvSec — local-first security observability for modern repositories>"`
  · `gh repo edit Christian-Katzmann/dev-security --add-topic security,sast,sca,sbom,local-first,python,react,security-scanner` (pick 4–6 that fit; topics drive discovery)
  · `gh repo edit Christian-Katzmann/dev-security --homepage ""` (leave empty unless there's a real landing page)
  · Pin DESIGN.md, AGENTS.md, and the latest audit report as repo highlights? Optional.
- **Tag v0.1.0**: update CHANGELOG.md's `[0.1.0]` entry with today's date, commit, then `git tag -a v0.1.0 -m "Initial public release"`. Do NOT push the tag yet — that's part of the flip Christian does himself.
- Final summary written at the bottom of this step: "Ready to flip" or "Not ready — see <items>".
OPEN QUESTIONS:
- Are there surfaces the first audit skipped (Add repo prompt, Place new key, Honey key Retire) that are worth testing now that the campaign has fixed neighbouring code? Test the ones you can without mutating user data; flag the ones that need mutation testing for a future pass.
- For the GitHub description, lean toward DëvSec's actual differentiator (local-first, no SaaS) over generic "security scanner" phrasing. Strangers scan repo cards; the differentiator is the hook.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the Public Repo Readiness campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/public-repo-ready.md
Campaign: campaigns/public-repo-ready.md

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

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign"). Campaign is done. Christian can now flip the repo to public when ready.
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick the checkbox until APPROVED.
