# 2026-05-12 — npm / PyPI supply-chain worm IOC scan

## Summary

On 2026-05-12, reports circulated of a supply-chain worm spreading through npm and PyPI, with named compromised versions across `@opensearch-project/opensearch`, `mistralai`, `guardrails-ai`, and a possible widening to `@tanstack/*`, `@squawk/*`, `@uipath/*`. A manual cross-repo IOC sweep was performed against the local development tree at `/Users/christiankatzmann/Dev`.

**Outcome: clean.** No named IOC matched any lockfile, manifest, workflow, or install hook in the dev tree. No secrets needed rotation as a result of this incident.

The interesting outcome is what the sweep had to be done *by hand* — and what DëvSec would need in order to do this kind of sweep in 30 seconds the next time, with auditable evidence.

## Scope of the manual sweep

Searched recursively across `~/Dev` (excluding `node_modules`, `.next`, `.git`, vendored `google-cloud-sdk`, Swift `.build` checkouts):

- All `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`
- All `requirements.txt`, `pyproject.toml`, `poetry.lock`, `uv.lock`, `Pipfile.lock`
- All `.github/workflows/*.yml` in user-owned repos
- `preinstall` / `install` / `postinstall` script blocks
- Curl-pipe-to-shell, base64-exec, `/tmp` writes, suspicious domains

## IOC results

| Indicator | Match |
| --- | --- |
| `@opensearch-project/opensearch` @ 3.5.3 / 3.6.2 / 3.7.0 / 3.8.0 | none |
| `mistralai==2.4.6` (PyPI) | none — package not referenced in any Python manifest |
| `guardrails-ai==0.10.1` (PyPI) | none — package not referenced in any Python manifest |
| `@squawk/*` | none |
| `@uipath/*` | none |
| Domain `git-tanstack.com` | none |

## `@tanstack/*` resolved versions present in lockfiles

All mainstream and legitimate; no anomalous versions:

- `@tanstack/react-query` — 5.66.0, 5.67.1, 5.90.5
- `@tanstack/query-core` — 5.66.0, 5.67.1, 5.90.5, 5.100.6
- `@tanstack/eslint-plugin-query` — 5.66.0
- `@tanstack/react-router` — `^1` (Reactive-Resume only)
- `@tanstack/vite-config` — 0.2.0, 0.4.3

## Install hooks audited (all benign)

| Repo | Hook | Verdict |
| --- | --- | --- |
| `Experiments/RollingFlow` | `postinstall: npm run install:server && npm run install:client` | Nested install of repo-local subprojects |
| `Projects/Toduu` | `preinstall: node -e "... Use pnpm ..."` | pnpm enforcer |
| `Projects/Obedai_JobManagement/_archive/.../services-resume-matcher` | `install: npm run install:frontend && npm run install:backend` | Archived nested installer |

## Workflow audit

Only one workflow line piped a remote script to a shell:

- `Projects/Obedai_JobManagement/.github/workflows/template-validation.yml:52` — `curl -fsSL https://typst.community/typst-install/install.sh | sh` (official Typst installer; benign)

No `base64 -d | sh`, no writes to `/tmp/<random>.sh`, no echoing of `secrets.*` to network endpoints.

## Remediation

None required. No tokens rotated. No CI jobs paused. No lockfiles modified.

---

# Lessons for DëvSec

The manual sweep took maybe five minutes of grep work. That is fast for one person on one tree, and far too slow for what is about to become a weekly cadence of named supply-chain campaigns. The right response is not to do this faster next time — it is to install the capability inside DëvSec.

The existing roadmap (`next-step.md`, campaign `change-aware-supply-chain`) is already pointing the product in the right direction: SBOM history first, then dependency trust, then VEX, then platform posture, then behavioral drift. This incident does not change that order. It clarifies which features to put *on top of* the SBOM history foundation, and where DëvSec currently has gaps that named-campaign IOCs make painful.

The features below are split into three groups: cheap wins that ride on the existing Phase 1 foundation, new scanner modules that earn their own slot, and Honey primitives that are deeper bets.

## A. Cheap wins on top of SBOM history

### 1. IOC Watch — named-campaign matching against SBOM components

Once SBOM components are first-class rows in SQLite (Phase 1, already in progress), an IOC match is a `WHERE name = ? AND version IN (?, ?, ?)` query. The product needs:

- A small ingestion format for IOC packs: YAML with `ecosystem`, `name`, `versions[]`, `advisory_url`, `published_at`, `confidence`.
- One curated source on by default (GitHub Security Advisories, OSV) and the ability to load user-curated packs from a directory.
- A new finding category `supply-chain-ioc` and a case template with critical severity and "this exact pinned version is named in a published advisory" copy.
- A CLI verb: `security-scan ioc --feed=<path-or-url> --all-repos`, which is exactly what today's manual sweep should have been.

This is the killer feature this incident points at. It is also small to ship because the foundation already lands in Phase 1.

### 2. Silent-upgrade detector

When SBOM diff sees a new dependency or a version jump that has no corresponding change in `package.json` / `pyproject.toml` / `requirements.txt`, that is a strong supply-chain signal. The component delta layer in Phase 1, Step 1.1 already has the data — the rule is a one-pager. Add it as a case type `silent-upgrade` with medium severity and a "verify or revert" action.

This is high signal-to-noise because legitimate version drift almost always shows up in both the manifest and the lockfile.

## B. New scanner modules

### 3. Install-hook risk classifier

`preinstall`, `install`, `postinstall` are the supply-chain payload's preferred door. DëvSec currently has Semgrep, which can be coerced into this with custom rules, but install hooks deserve their own first-class scanner adapter with explicit risk tiers:

- **Critical**: literal `curl ... | sh`, `wget ... | sh`, `base64 -d | sh`, network fetch and exec
- **High**: shell out to unaudited binaries, write to `/tmp/`, set `NODE_OPTIONS` mid-install, modify `~/.npmrc` or `~/.pypirc`
- **Medium**: nested installer (`npm run install:client`), `node-gyp rebuild` from unknown publishers
- **Info**: pnpm-enforcer, local-only repo scripts

Mirror this for Python `setup.py` / `pyproject.toml` build hooks. The case copy should be plain: "this dependency runs a script at install time. Here is what it runs. Here is the risk."

### 4. Workflow surface audit (GitHub Actions hardening)

DëvSec has Trivy misconfig and Checkov for IaC. GitHub Actions deserves its own audit because it is where supply-chain compromises become privilege escalations into the user's secrets. Rules to encode (custom Semgrep YAML or extended Checkov):

- Unpinned `uses: org/action@main` or `@master` (no SHA)
- `curl ... | sh` or equivalent inside `run:` blocks
- `secrets.*` piped into `base64`, `echo`, `xxd`, `od`, or any network egress
- `pull_request_target` triggers that check out fork code
- Untrusted inputs reaching `${{ ... }}` in `run:` blocks

Surface under a new "Workflows" tab in the dashboard, or fold into the existing IaC view with a workflow filter.

### 5. Cross-repo IOC sweep — one command

This is mostly CLI ergonomics, but it is the difference between "DëvSec saved me today" and "DëvSec could have, if I'd thought to drive it." The verb:

```text
security-scan ioc --feed=<file-or-url> --all-repos
```

Output: a single normalized report identical in shape to today's manual one. Group by repo, list match path, list risk tier, list whether install was recent.

Pairs naturally with feature 6.

## C. Bridges detection to action

### 6. Install-recency window and secret rotation advisor

The hard part of any supply-chain incident is not detection — it is the "did I actually run this code, and which secrets did it see?" question. DëvSec can answer this with data already on disk:

- `node_modules/.package-lock.json` mtime
- pnpm-store directory mtimes
- `~/.npm/_logs` install timestamps
- `package-lock.json` last-modified vs git history

When an IOC matches, check whether the affected repo's last install or build happened in the last N days. If yes, the case is upgraded with a structured **"Probably executed — rotate the following surfaces"** section. Generate the existing AI handoff prompt with explicit token surfaces detected in this repo: `.env`, `.envrc`, `secrets.*` references in `.github/workflows/`, any `mcp.json` API keys, any `.aws/credentials` symlinks in the project tree.

This is what closes the loop the manual sweep had to do by judgement: "should I rotate or not?" Today's answer needed a human to think. The product should answer it from evidence.

## D. Deeper Honey primitives

### 7. Honey Package — dependency-confusion tripwire

Companion to Honey Keys. Insert a deliberately-named fake dependency into a target `package.json` (e.g. `@christiankatzmann/internal-utils-do-not-publish`) marked as `optionalDependencies`. If anything ever resolves it from a real registry — meaning someone published a typosquat, or a CI builder is being attacked via dependency confusion — DëvSec alerts. Mirror for PyPI namespace prefixes. Phase-later; small but elegant.

### 8. Credential tripwire — real-asset filesystem watcher

Honey Keys today are synthetic decoys. The next tier: a daemon that watches reads of high-value real files — `~/.npmrc`, `~/.pypirc`, `~/.aws/credentials`, `~/.ssh/id_*`, `~/.config/gh/hosts.yml`, `~/.gnupg/`. macOS `Endpoint Security` (or `fs_events` as a softer fallback) can attribute the reading process. When a descendant of `npm install` / `pip install` / `uv` reads any of these, that is near-certain malicious-postinstall behavior. Surface as a critical alert with full process ancestry and the package most likely responsible.

This is the strongest single signal against the worm class. It is also the heaviest engineering lift (needs a privileged helper or signed daemon) and should probably wait until DëvSec is more mature.

## Where this fits the existing campaign

The existing `change-aware-supply-chain` campaign already lands Phase 1 (SBOM history) and Phase 2 (vulnerability correlation), which together unlock feature 1 (IOC Watch) and feature 2 (silent-upgrade detector) almost for free.

Features 3, 4, 5 are new scanner adapters that fit the project's "boring scanner adapters" rule — they should not require structural change to the model.

Feature 6 is the most product-y of the bunch — it changes what DëvSec *says* when something matches, not how it scans. It belongs in the Cases / Priority / Dashboard layer.

Features 7 and 8 are Honey Key system extensions and naturally belong in a separate later wave.

## Suggested next planning step

When ready, the natural sequence is:

1. Finish Phase 1 of the existing campaign (SBOM history landing cleanly).
2. Open a new short campaign — `named-ioc-watch` — that delivers feature 1 (IOC Watch), feature 5 (cross-repo CLI verb), and feature 6 (recency + rotation advisor) as one coherent slice. This is the slice that would have answered today's question in 30 seconds.
3. Treat features 3 (install-hook classifier) and 4 (workflow audit) as separate small campaigns that can run in parallel with the next phase of change-aware work.
4. Hold features 7 and 8 for after Phase 2 / Phase 3 of the existing roadmap.

Relevant skills for that planning step: `/plan` for the new campaign scope, `/campaign-planner` to scaffold the markdown campaign once decided.

## Evidence

This file documents the scan that produced the conclusions above. The IOC list checked:

```yaml
ecosystem: npm
name: "@opensearch-project/opensearch"
versions: ["3.5.3", "3.6.2", "3.7.0", "3.8.0"]

ecosystem: pypi
name: "mistralai"
versions: ["2.4.6"]

ecosystem: pypi
name: "guardrails-ai"
versions: ["0.10.1"]

watch_namespaces:
  - "@tanstack/"
  - "@squawk/"
  - "@uipath/"

watch_domains:
  - "git-tanstack.com"
```

When IOC Watch ships, this YAML shape is roughly what an IOC pack file should look like.
