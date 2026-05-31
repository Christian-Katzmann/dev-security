# DëvSec — AI Runs Scans & Fixes Them Hands-Off

> The security app can already read findings and let an AI close out the routine ones. This plan adds the two missing pieces of "the AI operates it for me": letting the AI kick off a scan itself, and letting it fix the easy problems by opening a change that a second, untrickable AI reviewer waves through — while still stopping to ask a human before hiding a serious warning.

## Scope

The read+write MCP (`devsec-mcp-rw`) already exists and is now wired into Claude Code and Codex: an AI can read findings and apply audited, validated case decisions (`devsec.case_resolutions.v1`) without anyone opening the app. Two parts of the "AI as operating interface" vision are *not* built yet, and this campaign delivers only those: (1) a guarded scan-trigger tool so the AI can start a scan from the MCP — today the adapter deliberately "cannot run scanners"; and (2) a hands-off code-fix loop where the AI proposes a fix as a branch/PR, a clean-room reviewer agent that never read the untrusted finding text checks the diff against the invariants, and low-risk fix classes (dependency bumps, action SHA pins, lockfile patches) auto-merge — everything else, and any high/critical suppression, waits for a human. Done looks like: an AI triggers a scan, closes the routine findings, auto-merges one low-risk fix, and stops at the human gate before hiding a serious one — with an adversarial test proving a poisoned finding can't drive it past any invariant. All work lands in the `dëv-security` repo; nothing in other projects changes.

## Context (locked decisions)

- **This repo is the home.** `dëv-security` (Python package `security_observatory`, `uv`-managed, `pytest`). The stdio MCP is `src/security_observatory/mcp_server.py` (`main` = read-only `devsec-mcp`, `main_rw` = read+write `devsec-mcp-rw`). The write tools live in `case_followup.py`; the store is `ObservatoryDB` in `storage.py` (`~/.security-observatory/`). The HTTP surface is `dashboard_server.py`.
- **Already done, do not rebuild:** the read+write MCP, the three write tools (`case_followup_prompt`, `preview_case_resolutions`, `apply_case_resolutions`), `devsec.case_resolutions.v1` validation, the audited `set_case_decision` apply path, the Red refuse-list (no delete-findings / delete-scans / run-scanners / rotate-credentials / SQL / repo-file writes), and stdio-only transport. Both clients are already pointed at `devsec-mcp-rw`.
- **Branch:** work on `devsec-rw-extend` off `main`; merge to `main` only when Final review is APPROVED.
- **Adding a scan-trigger deliberately crosses today's "cannot run scanners" hard limit.** That is the one boundary this campaign intentionally moves — running a scan is non-destructive (it reads, it doesn't hide or alter findings), but it gets the grill/spec treatment before it ships.
- **The clean-room reviewer is structural, not a prompt.** The reviewing agent receives only the diff + invariants, never the finding text — that separation is what makes auto-merge of low-risk classes safe.
- **The standing human gate stays:** suppressing a high/critical finding (`false_positive` / `accepted_risk`) requires explicit human confirmation. Verify the existing apply path enforces this; add it if it doesn't.
- **No writes on the HTTP surface.** `dashboard_server.py` stays read-only; new tools are stdio-only.

## Unattended execution contract

These rules keep an unattended `/claude-automate` run from stalling:

- **No interactive input.** No command may block on a prompt, confirmation, or TTY. Use non-interactive flags; never pause for `[y/N]`.
- **Localhost only.** Any server binds `127.0.0.1`, never `0.0.0.0`/LAN (the macOS firewall dialog is a hard stall).
- **No blocking GUI/OS dialogs.** No login flows or OS permission panels mid-run; credentials are set up before the run.
- **Fail loud, don't wait.** A blocked step exits with a clear error instead of hanging.

## How prompts work in this campaign

Each step has a fenced **prompt card** — copy it into a fresh agent session (Claude Code or Codex) to run that step, in order. Placeholders like `<UPPERCASE_TOKENS>` are fill-in fields. The first step is a **thinking step** (a grill) — it produces decisions, not a diff.

## Progress checklist

### Phase 1 — Let the AI start scans

- [x] Step 1.1 — Grill + spec the scan-trigger and the severity gate
- [x] Step 1.2 — Add the guarded scan-trigger tool + confirm the human gate

### Phase 2 — Hands-off code fixes

- [x] Step 2.1 — Clean-room reviewer + bounded auto-merge
- [x] Step 2.2 — Red-team + hands-off end-to-end demo
- [ ] Final review

## Step 1.1 — Grill + spec the scan-trigger and the severity gate

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: NO

A thinking step. Adding a scan-trigger crosses a boundary the adapter advertises as a hard limit, and the severity gate is the one irreversible decision in the whole surface. Pressure both before coding, then write the small spec the next steps build against.

```text
/grill-me

SCOPE: Decide, before coding, exactly how the AI may trigger a scan and how the high/critical suppression gate behaves — for a tool whose agent reads attacker-influenceable finding text.
REQUIRED READING:
1. src/security_observatory/mcp_server.py — the main_rw entrypoint and how the three write tools are registered
2. src/security_observatory/case_followup.py — the apply path (set_case_decision), validation, and whether any severity gate already exists
3. src/security_observatory/scanners.py and src/security_observatory/cli.py — how a scan is actually run today (the CLI path the trigger would wrap)
4. mcp/README.md — the "Hard limits" section, especially "cannot run scanners"
GRILL ON:
- Is triggering a scan ever weaponizable (resource abuse, masking via a re-scan, racing an in-flight decision)? What constraints make it safe (rate limit, repo allowlist, no params from finding text)?
- Does the apply path already block auto-suppression of high/critical, or is that gate missing? Where exactly should it live?
- What does "requires human confirmation" mean concretely for an MCP tool with no human present — a refusal the human later confirms, or a pending state?
OUTPUT: append a short section to docs/threat-model.md (or a new docs/rw-extend-spec.md) capturing: the scan-trigger contract + its constraints, the severity-gate behavior, and the auto-merge-eligible fix-class allowlist for Phase 2. Decisions, not code.
FORWARD SWEEP: before checking this step off, skim the remaining steps; if a decision renamed a path or changed the gate's shape, true up their REQUIRED READING and acceptance criteria.
```

## Step 1.2 — Add the guarded scan-trigger tool + confirm the human gate

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Implement the scan-trigger as a new `devsec-mcp-rw` tool that wraps the existing scan path, with the constraints from 1.1. In the same pass, confirm (and add, if missing) the severity gate so high/critical suppression can't auto-apply.

```text
SCOPE: Add a guarded scan-trigger tool to the read+write MCP and ensure the high/critical suppression gate is enforced. Reuse the existing scan path and audited decision path; do not bypass either.
REQUIRED READING:
1. docs/rw-extend-spec.md (the Step 1.1 spec: scan-trigger contract + the two-layer severity gate)
2. src/security_observatory/mcp_server.py — where main_rw registers write tools (add the new tool here). The tool name decided in 1.1 is `trigger_scan(repo, profile="quick")`.
3. src/security_observatory/scanners.py and src/security_observatory/cli.py — the scan entry the tool wraps is `scan_repo(repo, args, home)` (cli.py), append-only via `save_scan`
4. src/security_observatory/case_followup.py AND src/security_observatory/storage.py — the gate is enforced primarily in `set_case_decision` (storage.py), with the automated MCP path in `apply_case_resolutions` (case_followup.py) recording case severity and never asserting human authorization. 1.1 confirmed NO severity gate exists today — it must be added.
ACCEPTANCE:
- A new stdio write-mode tool `trigger_scan` triggers a scan/rescan of an allowlisted repo (resolved from a repo NAME to its recorded path — never a raw path), with the 1.1 constraints: profile restricted to the `{quick, default}` enum, local-offline only (no --trust/--platform-posture/network drift), per-repo cooldown (~10 min). It routes through the existing `scan_repo` path, not a reimplementation.
- The tool is registered only in main_rw (write mode), never on the HTTP/dashboard surface — a test confirms the read-only adapter and the dashboard don't expose it.
- Suppressing a high/critical case does not auto-apply through the MCP path: it returns the distinct `requires_human_confirmation` outcome (case stays open/visible, proposed decision preserved in the audit trail). Add the gate to `set_case_decision`, keyed on an explicit human-authorization signal that the MCP path never asserts.
- pytest coverage for the new tool and the gate, including a poisoned-input case that tries to pass a malicious scan target.
FORWARD SWEEP: before checking this step off, skim Step 2.x; if the tool name or trigger interface differs from what they assume, update them.
```

## Step 2.1 — Clean-room reviewer + bounded auto-merge

Model: Opus 4.8 · Extra High / GPT-5.5 · Extra High
Parallel: NO

Build the hands-off fix loop. The proposing agent (which read the findings) drafts a fix and opens a PR; a separate clean-room reviewer agent — given only the diff and the invariants, never the finding text — approves or rejects; low-risk classes auto-merge on approval, everything else waits for a human.

```text
SCOPE: Build the propose-review-land flow for code fixes, with the proposing agent and the reviewing agent structurally separated so auto-merge of low-risk classes is safe.
REQUIRED READING:
1. docs/rw-extend-spec.md — the clean-room reviewer contract and the auto-merge-eligible fix-class allowlist (§3)
2. src/security_observatory/priority.py (fix-class / action-level reasoning) and the `devsec-pr` / `devsec-fix` command skills — existing remediation scaffolding to extend, not duplicate. NOTE: 1.1 confirmed there is no `recovery.py`; do not look for one.
3. src/security_observatory/case_followup.py — record proposals/approvals through the audited decision path
ACCEPTANCE:
- A fix proposal opens a branch/PR (never commits to a protected branch directly).
- The clean-room reviewer receives only the diff + invariants, never the finding text; the separation is enforced by how the agent is invoked, not by instruction.
- Low-risk fix classes (dependency bumps, action SHA pins, lockfile patches) auto-merge on clean-room approval; every other class stops for a human.
- No path reaches auto-merge without a clean-room approval recorded in the audit trail.
OPEN QUESTIONS:
- Keep the starting auto-merge allowlist as narrow as the 1.1 spec allows — widening later is cheap, a wrong auto-merge is not.
FORWARD SWEEP: before checking this step off, skim Step 2.2; if the proposal/reviewer interface differs from what the demo assumes, update it.
```

## Step 2.2 — Red-team + hands-off end-to-end demo

Model: Opus 4.8 1M · Extra High / GPT-5.5 · Extra High
Parallel: NO

Prove both halves: the fence holds under attack, and the full loop runs without a human opening the app.

```text
SCOPE: Verify the extended surface is both safe and useful. Adversarial first, then the hands-off loop, with captured evidence.
REQUIRED READING:
1. docs/rw-extend-spec.md — invariants, scan-trigger constraints (`trigger_scan`), the `requires_human_confirmation` severity gate
2. src/security_observatory/case_followup.py, src/security_observatory/storage.py (`set_case_decision`), and their tests — the apply path + adversarial cases
3. src/security_observatory/mcp_server.py — the live write + scan-trigger tools
4. src/security_observatory/dashboard_server.py — confirm none of the new tools leaked onto the HTTP surface
ACCEPTANCE — adversarial (each refused, with an audit entry):
- A poisoned finding telling the agent to mark a critical as false-positive → blocked at the human gate.
- A scan-trigger with a malicious/non-allowlisted target → refused.
- Attempts to delete a finding, rewrite scan history, or reach a write tool over the HTTP surface → all refused.
ACCEPTANCE — hands-off loop (no app opened):
- AI triggers a scan, auto-closes low/info findings with evidence, auto-merges one low-risk fix (e.g. an action SHA pin) via the clean-room reviewer, and stops at the human gate before suppressing a high/critical finding.
- Capture the audit log + a short transcript as evidence.
FORWARD SWEEP: last build step — note any gap that an earlier step should own, so Final review can confirm it was closed at the source rather than patched here.
```

## Final review

A campaign-level final review catches **cross-phase shortcuts** — a primitive set up in one phase silently bypassed by another, intent claimed in one step but not delivered when read across the whole campaign. Run it once every phase is complete. The user copies the prompt below, opens a fresh Codex or Claude Code session in the repo, and pastes:

```text
Run a final review on the DëvSec AI-Runs-Scans-And-Fixes campaign.

Plan: /Users/christiankatzmann/Dev/Projects/dëv-security/campaigns/devsec-rw-mcp.md
Campaign: campaigns/devsec-rw-mcp.md

Read every `## Step N.M — name` heading. For each, locate the acceptance criteria in its prompt body, and verify against the cumulative git diff that the criteria actually landed. Don't trust step receipts — read the diff.

Catch cross-step shortcuts: a scan-trigger that takes parameters from finding text, the human gate weakened or removed, a write/trigger tool that leaked onto the dashboard HTTP surface, auto-merge reachable without a clean-room pass, decisions that bypass the audited apply path, dead code, or regressions in the existing read+write tools.

Be honest. Lean. APPROVED if every step's acceptance criteria landed and no invariant is bypassed. NEEDS WORK if any step cut corners or a fence was breached.

Don't pad with future improvements. Just verdict the work.

Run with either:
- Codex: GPT-5.5 with Extra High reasoning effort
- Claude Code: Opus 4.8 with Extra High thinking
```

**Verdict-to-action mapping:**

- **APPROVED** → tick the `Final review` checkbox at the end of the progress checklist (or click "Close campaign").
- **NEEDS WORK** → reopen the named steps, close the gaps, re-run the final review. Don't tick until APPROVED.
