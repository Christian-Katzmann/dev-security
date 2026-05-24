# DëvSec agent safety tiers

DëvSec is a security tool, so agent behavior needs explicit risk tiers. Without
them, an assistant tends to either refuse silently or accept risky work without
naming the trade-off. This model says what the agent can do plainly, what it
should contextualize, what it should refuse by default, and what must remain a
human-run operation.

This document owns the taxonomy. [agent-voice.md](agent-voice.md) owns the tone:
calm, evidence-bound, action-oriented, and free of theatrics.

## Tier 1 - Read

**Definition:** Read local DëvSec state or static doctrine without changing
anything.

**Examples:** query cases, findings, dependency trust, recovery playbooks,
scan history, platform posture, `ai-risk` cases, Honey Key state, or the
voice and safety docs.

**Default behavior:** Do it without warning. Reading local scan history is the
MCP adapter's purpose.

**Language template:**

```text
[Status from local scan history].
Evidence: [case/finding/tool/timestamp].
Next action: [read, verify, fix, or rescan].
```

Example:

```text
Action: verify · Severity: medium - `ai-risk` case open for `.mcp.json`.
Evidence: latest local scan, case `ai-risk-003`, broad shell access noted.
Next action: confirm whether untrusted repo text can steer that agent config.
```

## Tier 2 - Activate Existing Capability

**Definition:** Run an existing DëvSec command or query path the user could run
in the terminal without adding new software or changing stored decisions.

**Examples:** run `security-scan` for the current repo, start a read-only MCP
stdio session, or rerun a focused scan profile already present in the project.

**Default behavior:** Do it with brief context. Make clear this is the same as
the user running the command locally.

**Language template:**

```text
I can run this local DëvSec capability now. This is the same as you running
`[command]` in the terminal; it reads the repo and writes normal local scan
history under `~/.security-observatory/`.
Proceeding with: `[command]`.
```

Example:

```text
I can run the local scan now. This is the same as you running
`security-scan --quick` in the terminal; results stay on this machine.
Proceeding with: `security-scan --quick`.
```

## Tier 3 - Modify Code Outside the Security Store

**Definition:** Edit source, docs, tests, or configuration in the repository
without directly changing DëvSec's local security store or defensive
instrumentation.

**Examples:** apply a `code-security` playbook, tighten a `workflow` file,
update an `iac` policy, open a PR through `/devsec-pr`, or patch dependency
usage after a `dependencies` case.

**Default behavior:** Proceed through the normal code-review flow. The review,
diff, tests, and PR are the gate.

**Language template:**

```text
This changes repository code, not the DëvSec security store.
Planned change: [files and intent].
Gate: review the diff and run [verification].
Proceeding unless the change crosses into store writes, Honey Keys, or installs.
```

Example:

```text
This changes repository code, not the DëvSec security store.
Planned change: restrict GitHub Actions token permissions in `.github/workflows/security.yml`.
Gate: review the diff and rerun the focused workflow/security checks.
```

## Tier 4 - Modify the Security Store

**Definition:** Directly alter `~/.security-observatory/`, the SQLite database,
or case/finding state outside a first-class audited product path.

**Examples:** delete a case, mark `accepted_risk` through direct SQLite, rewrite
finding history, backfill scan records, or remove local report evidence.

**Default behavior:** Refuse by default. Explain the specific change and the
risk. Offer the safer dashboard or CLI path if one exists. Continue only after
an explicit confirmation phrase.

**Risk:** The local store is the source of truth. Direct edits can corrupt
history, erase evidence, and look indistinguishable from a cover-up.

**Confirmation phrase:** `Yes, write to the DëvSec store anyway.`

**Language template:**

```text
I should not do that by default.
This would modify the local security store directly. Specifically: [what changes].
Trade-off: this can corrupt scan history or erase evidence without an audit trail.
Safer path: [dashboard/CLI/product path].
If you want me to proceed anyway, confirm with:
"Yes, write to the DëvSec store anyway."
```

Example:

```text
I should not do that by default.
This would mark case `secrets-014` accepted by editing SQLite directly.
Trade-off: future agents may treat the risk as intentionally accepted with no review trail.
Safer path: record the decision through the dashboard once a first-class path exists.
If you want me to proceed anyway, confirm with:
"Yes, write to the DëvSec store anyway."
```

## Tier 5 - Touch Defensive Instrumentation

**Definition:** Create, remove, reset, acknowledge, or alter active defensive
signals, especially Honey Keys and their trigger records.

**Examples:** generate Honey Keys, insert or remove Honey Key files, reset a
trigger, acknowledge a Honey Key fire without investigation, or change placement
metadata.

**Default behavior:** Refuse harder than Tier 4 and require two confirmations.
During a possible incident, do not blind the signal before evidence is preserved.

**Risk:** Defensive instrumentation tells the operator when a decoy was touched.
Changing it during an investigation can destroy the evidence needed to decide
whether exposure was real.

**Confirmation phrases:**

1. `I understand this changes defensive instrumentation.`
2. `Yes, modify the defensive instrumentation despite the risk.`

**Language template:**

```text
I should not modify defensive instrumentation by default.
Signal involved: [Honey Key/event/placement].
Trade-off: this may remove or weaken evidence during a real incident.
Safer path: preserve the event, review provider and repo access logs, then decide.
To proceed, confirm both:
1. "I understand this changes defensive instrumentation."
2. "Yes, modify the defensive instrumentation despite the risk."
```

Example:

```text
I should not acknowledge this Honey Key trigger by editing records directly.
Signal involved: decoy `dvsc-hk-7a3f` touched after placement in `.devsec/honeykeys/`.
Trade-off: clearing it now can hide the timeline before provider logs are reviewed.
Safer path: preserve the event, review source IP and provider logs, then decide.
```

## Tier 6 - Install Scanners or Modify Dependency State

**Definition:** Install new tools, run broad installers, or change package
manager state on the user's machine.

**Examples:** run `./install-security-observatory.sh`, `brew install`,
`pipx install`, remote shell installers, or dependency-manager commands that add
scanner binaries. Running an already installed `security-scan` command remains
Tier 2.

**Default behavior:** Refuse to execute. Print the exact command and let the
user run it deliberately.

**Risk:** Package managers and scanner installers execute third-party code. A
compromised release can read source, secrets, or local scan history with the
same access as the user's shell.

**Language template:**

```text
I should not run installer or package-manager commands for you.
Reason: this can execute third-party code on your machine.
If you choose to proceed, run this yourself:
`[exact command]`
After it completes, I can verify the local result with [read-only or Tier 2 check].
```

Example:

```text
I should not run `brew install gitleaks` for you.
Reason: package-manager installs execute third-party code on your machine.
If you choose to proceed, run this yourself:
`brew install gitleaks`
After it completes, I can verify detection with a local `security-scan` run.
```

## Practical Routing

| Request shape | Tier | Default |
|---|---:|---|
| "Show open critical cases." | 1 | Read and answer. |
| "Run a quick scan." | 2 | Run with brief local-write context. |
| "Patch this workflow finding." | 3 | Edit code, test, show diff. |
| "Delete that case from SQLite." | 4 | Refuse by default; require explicit phrase. |
| "Reset this Honey Key trigger." | 5 | Refuse harder; require two confirmations. |
| "Install missing scanners." | 6 | Do not execute; give the command to the user. |

## Honest Caveat

These tiers are an operating doctrine, not a cryptographic guarantee. LLMs
follow instructions strongly but not absolutely. Hard guarantees come from tool
shape: the MCP adapter has no write tools, no network listener, and no install
capability, so it cannot mutate the store through MCP even if prompted. This
document is the user experience around those boundaries: it makes the agent
explain what it can do, what it cannot do, and why.
