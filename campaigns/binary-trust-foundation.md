# DevSec Binary Trust Foundation

> Make DevSec prove what it runs before it scans private code. This campaign adds the first trust layers: checked local binaries, verified downloads for managed scanners, signed DevSec releases, and guardrails before any future auto-update path.

## Scope

This campaign builds the first practical binary-trust foundation for DevSec without trying to solve every supply-chain problem at once. Done means DevSec records and checks the exact managed scanner artifact it installed, verifies supported third-party scanner downloads with real upstream signing or provenance evidence, signs DevSec's own release artifacts, gives users a clear way to verify them, and prevents future update work from bypassing anti-rollback rules.

## Context (locked decisions)

- Full Apple PCC-style verifiability is too much for the current app; the first 3-4 trust layers are appropriate because DevSec reads source code, findings, and secret evidence.
- The first execution boundary is DevSec-managed scanner copies, not every user-owned tool already on `PATH`.
- Checksum pinning is useful but not sufficient; the checksum has to be tied to stronger proof when upstream provides it.
- Sigstore/cosign and SLSA provenance are authenticity/provenance controls, not runtime safety controls.
- TUF-style update protection is only needed before real auto-update; this campaign adds the policy and guardrails, not a full updater.
- Runtime scanner sandboxing stays out of scope for this campaign and should become a later campaign.
- Existing ADX contracts matter: read `.adx/commands.json` before verification runs and `.adx/risks.json` before installer, scanner, or process-control work.

## How prompts work in this campaign

Each step activates a skill or runs a command and pastes a short prompt. The prompt provides only what the agent cannot know on its own:

- **Scope** — the specific thing this run is about.
- **Required reading** — file paths the agent must read first.
- **Output target** — where the result goes.
- **Open questions** — what to surface, not assume.

`<UPPERCASE_TOKENS>` are user-fillable placeholders. The Campaigns app shows an editable bar in the prompt card for them; copies use the substituted text.

## Progress checklist

### Phase 1 — Local Execution Integrity

- [x] Step 1.1 — Define scanner proof policy and evidence states
- [x] Step 1.2 — Enforce pre-execution digest checks for managed scanners

### Phase 2 — Verified Managed Scanner Downloads

- [x] Step 2.1 — Add a verification provider contract
- [x] Step 2.2 — Wire real cosign and SLSA verification where upstream supports it
- [x] Step 2.3 — Surface proof levels in status, doctor, and catalog copy

### Phase 3 — Verifiable DevSec Releases

- [ ] Step 3.1 — Add release artifact signing and provenance workflow
- [ ] Step 3.2 — Add user verification docs and a self-check command

### Phase 4 — Update Guardrails

- [ ] Step 4.1 — Add anti-rollback policy before any updater exists
- [ ] Final review

Each step heading is followed by a `Model:` line (recommended agent + thinking effort) and a `Parallel:` line (which sibling steps can run alongside it).

## Step 1.1 — Define scanner proof policy and evidence states

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Create the vocabulary and policy DevSec will use before code starts enforcing it. The important outcome is a small, durable contract: what counts as checksum-only, upstream-signed, provenance-verified, DevSec-signed, user-owned, and unverified.

```text
/adx-forensic

SCOPE: Define DevSec's binary proof policy for scanner execution and managed installs.
REQUIRED READING:
1. docs/threat-model.md
2. src/security_observatory/managed_tools.py
3. src/security_observatory/scanners.py
4. docs/security-packs.md
5. docs/tool-catalog-current-scanners.md
6. .adx/risks.json
OUTPUT:
- Add or update a concise design note at docs/binary-trust.md.
- Add a receipt at campaigns/binary-trust-foundation/receipts/1.1-proof-policy.md.
ACCEPTANCE CRITERIA:
- The policy distinguishes user-owned PATH tools from DevSec-managed tools.
- The policy names at least these proof levels: unverified, checksum-pinned, upstream-signed, provenance-verified, devsec-signed.
- The policy says which proof levels are allowed to execute by default for managed tools.
- The policy explains that signing proves origin, not harmless behavior.
- The receipt lists follow-up code surfaces for Step 1.2 and Phase 2.
OPEN QUESTIONS:
- Surface any current UI wording that would overclaim binary authenticity.
```

## Step 1.2 — Enforce pre-execution digest checks for managed scanners

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Close the cheap local tampering gap: if DevSec installed a managed scanner and later the binary is replaced, DevSec should detect that before launching it.

```text
/adx-implement

SCOPE: Re-hash DevSec-managed scanner binaries immediately before execution and refuse mismatches.
REQUIRED READING:
1. docs/binary-trust.md
2. src/security_observatory/managed_tools.py
3. src/security_observatory/scanners.py
4. src/security_observatory/storage.py
5. tests/test_scanners.py
6. tests/test_managed_tools.py if present; otherwise locate the nearest managed-tool tests with rg.
OUTPUT:
- Code and tests for pre-execution digest verification of managed scanner binaries.
- A receipt at campaigns/binary-trust-foundation/receipts/1.2-pre-exec-digest.md.
ACCEPTANCE CRITERIA:
- Managed scanner execution checks the recorded sha256 against the executable on disk before subprocess launch.
- A mismatch produces a skipped/error scanner status that is visible in scan output rather than falling back silently to PATH.
- User-owned PATH scanners keep their current behavior and are not deleted, relinked, or modified.
- Tests cover a passing managed binary, a mismatched managed binary, and a missing recorded checksum.
- Verification uses the repo's existing fast import check and relevant pytest subset from .adx/commands.json.
OPEN QUESTIONS:
- If current storage records cannot distinguish old checksum-only installs cleanly, surface the migration choice and choose the safest backward-compatible behavior.
```

## Step 2.1 — Add a verification provider contract

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Add the internal shape that Phase 2 can reuse across tools. This is the seam between DevSec's managed installer and real upstream proof systems such as cosign, SLSA verifier, signed checksum files, or checksum-only fallback.

```text
/adx-implement

SCOPE: Introduce a small verification provider contract for managed tool downloads.
REQUIRED READING:
1. docs/binary-trust.md
2. src/security_observatory/managed_tools.py
3. src/security_observatory/model.py
4. src/security_observatory/storage.py
5. tests/test_scanners.py
6. .adx/commands.json
OUTPUT:
- Code and tests for a verification result model used during managed install.
- A receipt at campaigns/binary-trust-foundation/receipts/2.1-verification-contract.md.
ACCEPTANCE CRITERIA:
- Managed install records can store proof level, verifier name, verified subject digest, source identity when available, and human-readable evidence.
- The contract supports checksum-only fallback without pretending it is signed verification.
- The contract allows external command verifiers to be unavailable and reports that state cleanly.
- Existing managed install tests still pass after storage/model changes.
- No broad installer behavior changes happen in this step beyond storing and reporting verification results.
OPEN QUESTIONS:
- Surface whether old install records need a one-time migration label such as checksum-pinned.
```

## Step 2.2 — Wire real cosign and SLSA verification where upstream supports it

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Connect the provider contract to concrete implementations for tools that already publish real verification evidence. Prefer upstream-supported verification over custom trust guesses.

```text
/adx-implement

SCOPE: Add real upstream verification for DevSec-managed scanner downloads where concrete upstream evidence exists.
REQUIRED READING:
1. docs/binary-trust.md
2. src/security_observatory/managed_tools.py
3. docs/security-packs.md
4. docs/tool-catalog-current-scanners.md
5. .adx/risks.json
6. Upstream verification docs for each managed target being enabled.
OUTPUT:
- Managed install verification for supported tools, plus tests with command runners mocked.
- A receipt at campaigns/binary-trust-foundation/receipts/2.2-upstream-verifiers.md.
ACCEPTANCE CRITERIA:
- At least one managed scanner with real upstream support verifies via cosign or SLSA instead of checksum-only.
- Verification pins expected publisher identity, issuer, repository, workflow, or provenance fields where the upstream format exposes them.
- Unsupported tools remain installable only under their honest weaker proof level, or are held back if the policy says so.
- Verifier command absence is reported as a setup gap, not hidden as success.
- Tests do not require network or real cosign/SLSA binaries.
OPEN QUESTIONS:
- For each candidate tool, document whether upstream evidence is strong enough to trust or only enough to label checksum-pinned.
```

## Step 2.3 — Surface proof levels in status, doctor, and catalog copy

Model: Sonnet 4.6 · High / GPT-5.5 · High
Parallel: NO

Make the new proof evidence understandable. Users should see the difference between a detected user-owned scanner, a checksum-pinned DevSec-managed scanner, and a provenance-verified managed scanner without reading implementation details.

```text
/adx-implement

SCOPE: Show scanner proof levels in user-facing status without overclaiming safety.
REQUIRED READING:
1. docs/binary-trust.md
2. src/security_observatory/cli.py
3. src/security_observatory/catalog.py
4. src/security_observatory/managed_tools.py
5. src/security_observatory/dashboard_server.py
6. dashboard-ui/src if the dashboard renders catalog proof state client-side.
OUTPUT:
- User-facing proof labels in CLI doctor/check output, scanner status payloads, and catalog/install preview surfaces.
- A receipt at campaigns/binary-trust-foundation/receipts/2.3-proof-status-ui.md.
ACCEPTANCE CRITERIA:
- The UI and CLI distinguish user-owned, checksum-pinned, upstream-signed, provenance-verified, and unverified states where data exists.
- Wording avoids implying that a signed scanner is harmless or sandboxed.
- Missing proof appears as an evidence gap, not as a scan failure unless the managed execution policy blocks it.
- Relevant Python tests and dashboard lint/build checks run if touched.
OPEN QUESTIONS:
- Surface any existing catalog wording that conflicts with the proof policy and fix it in the same pass if tightly related.
```

## Step 3.1 — Add release artifact signing and provenance workflow

Model: Opus 4.7 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Give DevSec's own releases a verifiable origin. This should create signed release artifacts and build provenance without turning release engineering into a giant platform project.

```text
/adx-implement

SCOPE: Add DevSec release signing and provenance generation for release artifacts.
REQUIRED READING:
1. pyproject.toml
2. install-security-observatory.sh
3. .github/workflows if present
4. docs/binary-trust.md
5. .adx/risks.json
OUTPUT:
- A release workflow or workflow draft that signs DevSec release artifacts and emits provenance.
- Any needed docs updates for release maintainers.
- A receipt at campaigns/binary-trust-foundation/receipts/3.1-release-signing.md.
ACCEPTANCE CRITERIA:
- The workflow signs the actual artifacts users download, not only source archives.
- The workflow uses keyless signing or a documented signing-key path with clear secret-handling tradeoffs.
- Provenance ties artifact identity to the repo, tag/ref, and workflow where feasible.
- Release signing is gated to release/tag contexts and does not run on ordinary local scans.
- Verification is tested by static checks or dry-runable workflow validation where practical.
OPEN QUESTIONS:
- If no release workflow exists, create a minimal draft and document what manual release step still remains.
```

## Step 3.2 — Add user verification docs and a self-check command

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

A signed release only helps if a user, installer, or support workflow can verify it. This step adds the plain-English path and an optional local command that reports what proof is present.

```text
/adx-implement

SCOPE: Add user-facing release verification instructions and a local self-check command.
REQUIRED READING:
1. docs/binary-trust.md
2. README.md
3. src/security_observatory/cli.py
4. install-security-observatory.sh
5. .adx/commands.json
OUTPUT:
- Verification docs for DevSec releases.
- A CLI command or doctor extension that reports DevSec package/release proof when available.
- A receipt at campaigns/binary-trust-foundation/receipts/3.2-user-verification.md.
ACCEPTANCE CRITERIA:
- Docs include copy-pasteable verification commands for the produced artifact types.
- The command explains unavailable proof plainly instead of failing mysteriously on editable/local checkouts.
- The command does not upload source code, findings, or local scan data.
- Tests cover the command's happy path and unavailable-proof path.
- The fast Python import check and relevant pytest subset pass.
OPEN QUESTIONS:
- Decide whether the installer should verify DevSec itself in this phase or only document manual verification for the next campaign.
```

## Step 4.1 — Add anti-rollback policy before any updater exists

Model: Opus 4.7 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Prevent future auto-update work from accidentally becoming a signed-but-rollbackable update channel. This is a guardrail and design artifact, not a full TUF implementation.

```text
/adx-implement

SCOPE: Add update-channel guardrails so future updater work cannot skip rollback protection.
REQUIRED READING:
1. docs/binary-trust.md
2. docs/threat-model.md
3. install-security-observatory.sh
4. src/security_observatory/managed_tools.py
5. .adx/risks.json
OUTPUT:
- A concise update trust note, either in docs/binary-trust.md or a linked docs/update-trust.md.
- Code or contract guardrails that keep DevSec from adding silent auto-update without an explicit anti-rollback design.
- A receipt at campaigns/binary-trust-foundation/receipts/4.1-update-guardrails.md.
ACCEPTANCE CRITERIA:
- The docs name rollback, freeze, mix-and-match, and compromised-signing-path risks in plain language.
- The repo has an obvious marker that auto-update requires TUF-style metadata or equivalent before execution.
- Existing installer and managed-tool flows are not converted into auto-update in this campaign.
- Any user-facing wording says this is future update protection, not a completed updater.
- Relevant tests and import checks pass.
OPEN QUESTIONS:
- Surface whether a follow-up campaign should implement TUF metadata or defer until DevSec has a real updater.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the DevSec Binary Trust Foundation campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/binary-trust-foundation.md
Campaign: campaigns/binary-trust-foundation.md

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
