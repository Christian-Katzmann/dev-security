# Pre-public Security Sweep — DëvSec

**Run:** 2026-05-23T13:56:50Z → 2026-05-23T14:00:11Z (3m21s)
**Scanner version surface:** `security-scan --full` (Semgrep, Trivy, Gitleaks, TruffleHog, OSV-Scanner, Grype, Syft, Checkov, plus built-in AI-static, workflow-audit, IOC, behavioral-drift, malcontent, install-hook-classifier).
**Repo head:** `645c54f` (step 4.2 — README polish), branch `public-repo-ready`.

## Verdict

**Clean of secrets and credentials. One noted finding (personal paths) and one accepted-with-caveat (CI install pattern) for Christian's eyes before flipping the repo public.**

| Class | Result |
| --- | --- |
| Leaked secrets in committed source | **0** |
| Leaked secrets in git history | **0** |
| Third-party repo content (beskæftigelse.dk, monëy, obedai, client repos) leaked into this repo | **0** outside expected references in `campaigns/public-repo-ready.md` (which mentions them by name only as audit context) |
| Personal absolute paths (`/Users/christiankatzmann/...`) in committed files | **31 files** — see below |
| Critical CVEs in committed code | **0** (the 4 reported are in gitignored `node_modules/`, not shipped) |
| Critical workflow finding | **1** — the CI install block uses `curl \| sh`; matches ecosystem practice but worth a fix |

## Scanner output summary

```
Repo                Health  Crit  High   Med Secrets AI-risk
de-v-security            0     5    43    78       0      42
```

Critical findings, by category:

1. **`workflow` — `.github/workflows/security.yml:25`** — "Workflow run block fetches and executes remote code." This is the install block that pulls `syft`, `grype`, and `gitleaks` install scripts via `curl -sSfL ... | sudo sh`. The file already carries a comment `# Prefer pinned releases in production workflows.` Matches what the upstream tools recommend, but ironic in a *security* tool's own CI. **Not a blocker — known/accepted practice ecosystem-wide.** Follow-up: pin the install scripts to a release SHA.
2–5. **`dependencies` — 4× esbuild CVEs (CVE-2026-27143, CVE-2025-68121) in `dashboard-ui/node_modules/esbuild/bin/esbuild` and `dashboard-ui/node_modules/@esbuild/darwin-arm64/bin/esbuild`.** These paths are inside `node_modules/`, which is gitignored (verified: `dashboard-ui/.gitignore:1: node_modules/`). They do **not** ship to the public repo. A visitor running `npm install` from a clean clone resolves esbuild via `package-lock.json` (currently `esbuild: ^0.25.0`). **Not a blocker for public flip.** Follow-up: bump esbuild to a non-vulnerable version in `dashboard-ui/package.json`.

High and medium findings reviewed: **0 of them are credential-shaped** (no `password|secret|token|api_key|bearer` patterns in high+credential categories). Sample of remaining categories: AI-static (42), code-misconfig, dependency advisories without critical CVEs.

## Off-scanner sweep greps

### 1. Credentials in git history

```bash
git log --all -p | grep -iE "(password|secret|token|api[_-]?key|bearer)\s*[:=]\s*['\"]?[A-Za-z0-9_/+=-]{20,}"
```

**Result:** 0 hits matching credential-shaped patterns. The only matches for the bare word `token` are references to a local function `extract_honey_key_from_request(...)` — no actual credential material.

### 2. Personal absolute paths in committed files

```bash
git ls-files | xargs grep -l "/Users/christiankatzmann/"
```

**Result: 31 files contain the path `/Users/christiankatzmann/`.** Concentrated in:

- `.adx/audit/history/*.json` and `.adx/audit/latest.json` — audit artifacts that record absolute file paths of audited files. Example line: `"path": "/Users/christiankatzmann/Dev/Projects/dëv-security/.adx/rails/advisory-rules.json"`.
- `.adx/implementation/2026-05-12T133503Z.json` — same pattern, implementation receipt.
- `campaigns/*.md` (~10 files) — campaign planning notes that occasionally reference local files by absolute path.
- `reports/campaign-automation/<slug>/state.json`, `timeline.md`, `README.md` — past `claude-automate` chain state files that record the absolute repo path.
- `docs/desktop-launcher.appify-report.md`, `docs/incidents/2026-05-12-npm-pypi-supply-chain-worm-ioc-scan.md` — incident notes that quote local commands.

**Severity assessment:** Cosmetic, not a credential leak. Exposes the macOS username (`christiankatzmann`) and the local project layout. Christian's GitHub handle is `Christian-Katzmann`, which is already public — but professional repos generally do not leak `/Users/<name>/` paths. **Christian's call** whether this is a launch blocker.

**If you want to scrub:** the fix is one command (not a history rewrite — just a new commit):

```bash
git ls-files | xargs sed -i '' \
  -e 's|/Users/christiankatzmann/Dev/Projects/de\\u0308v-security/|<repo>/|g' \
  -e 's|/Users/christiankatzmann/Dev/Projects/dëv-security/|<repo>/|g' \
  -e 's|/Users/christiankatzmann/|~/|g'
```

Then `git diff` to verify, and commit. **Don't run blindly without inspecting the diff first** — some files (e.g. AGENTS.md global at the user's home) may have intentional references to `/Users/christiankatzmann/` paths that need a different rewrite.

### 3. Third-party / client-repo content quoted in committed planning files

```bash
git ls-files | xargs grep -lE "beskæftigelse|besk-ftigelse|monëy|mon-y|obedai|obedai-learning"
```

**Result:** 1 hit — `campaigns/public-repo-ready.md` mentions `beskæftigelse.dk` once in the Step 4.3 narrative as part of the audit context ("the walkthrough audit showed lots of secrets findings — but those were in OTHER repos being scanned (beskæftigelse.dk: 371 findings, mostly secrets)"). This is metadata about the audit, not content quoted from the other repo. **Acceptable**, but worth a quick read pre-flip to confirm the surrounding sentences don't accidentally include other client-repo content.

## .adx/ committed content review

Per the Context lock ("keep .adx/ contents committed — they're agent-onboarding infrastructure"), the `.adx/` tree stays. Confirmed scan of its contents:

- `.adx/audit/history/*.json`, `.adx/audit/latest.json`: contain absolute paths (covered in Grep 2 above) but no secrets.
- `.adx/journal.jsonl`, `.adx/claims.jsonl`: present but did not surface anything credential-shaped in scanner output.
- `.adx/commands.json`, `.adx/risks.json`, `.adx/recovery.md`, `.adx/modules/`: pure operational metadata, safe to ship.

## Recommendation

**Ready for public flip with two open items for Christian's eyes:**

1. **Personal-path leak (cosmetic).** Decide: scrub via the `sed` block above, or accept that the macOS username is in the artifacts. Recommendation: scrub. ~1 minute of work, much tidier first impression.
2. **CI workflow `curl | sh` pattern (defer-OK).** Not a launch blocker — matches ecosystem norm — but the file's own comment flags it. Recommendation: open a tracked follow-up issue post-launch to pin installer scripts to release SHAs.

No secrets, no credentials, no third-party content leak. The sweep is clean on the criteria the campaign brief defined as launch blockers.

## Artifacts

- Raw scan output: `reports/pre-public-sweep/scan-raw.json`
- Normalized report (full 128 findings): `reports/pre-public-sweep/normalized-report.json`
- Scanner stderr: `reports/pre-public-sweep/scan-stderr.log` (empty — clean run)
