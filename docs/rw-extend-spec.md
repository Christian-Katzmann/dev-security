# Read+write MCP extension — decisions spec

Status: decided (Step 1.1 of the `devsec-rw-mcp` campaign). This is a
decisions document, not code. Steps 1.2 and 2.x build against it.

It pins three things before any code lands:

1. the **scan-trigger contract** and the constraints that keep it safe,
2. the **high/critical suppression gate** — where it lives and what
   "requires human confirmation" means for a tool with no human present,
3. the **auto-merge-eligible fix-class allowlist** for the Phase 2 fix loop.

The whole surface operates on attacker-influenceable text: a scanned repo can
contain crafted finding/case text, and the agent that reads it then calls these
tools. That is the same prompt-injection gap [threat-model.md](threat-model.md)
already names. Every decision here exists to make sure poisoned text cannot
steer a scan target, cannot widen a scan's reach, and cannot drive a serious
finding into hiding without a human.

---

## 1. Scan-trigger contract

Today the adapter advertises "cannot run scanners" as a hard limit
([mcp/README.md](../mcp/README.md)). This campaign deliberately moves that one
boundary: running a scan is **non-destructive** — it appends a new scan row and
never deletes a prior scan, raw finding, or case decision — so it is the safe
boundary to cross. It still ships behind a tight contract.

### Tool shape

- **Name:** `trigger_scan(repo, profile="quick")`.
- **Registered only in `main_rw`** (the `devsec-mcp-rw` write entrypoint),
  alongside the existing three write tools. Never in the read-only `main`
  adapter, never on the `dashboard_server.py` HTTP surface. A test asserts the
  read-only adapter and the dashboard do not expose it.
- **Wraps the existing scan path** (`scan_repo` in `cli.py`) — no
  reimplementation of scanning. `scan_repo` saves through `save_scan`, which is
  append-only.
- **Returns** the new scan summary (scan_id, timing, finding count, health
  score, status) — the same shape `latest_scan` already returns. Synchronous:
  the scan runs to completion and the result is the tool's return value.

### Constraints (the load-bearing part)

1. **No parameter is derived from finding text.** The two inputs are tightly
   bounded:
   - `repo` is a **name**, not a path. It must match a repo that already has
     scan history in the local DB — the same allowlist the read tools use
     (`list_repos`). It resolves to the recorded `repo_path` via
     `latest_scan_for_repo(repo)["repo_path"]`, reusing the existing
     `_resolve_repo_path` resolver. A repo with no scan history → refused.
     **The tool never accepts a raw filesystem path.** This is what stops
     poisoned text from saying "scan `/etc`" or "scan `../../other-repo`."
   - `profile` is a **fixed enum**: `{"quick", "default"}` only. It maps to the
     existing `scanner_names_for_profile`. No raw scanner names, no flags, no
     shell. Anything outside the enum → refused.
2. **Local-only, offline.** AI-triggered scans are restricted to local,
   network-free profiles. The agent **cannot** trigger `--trust` (network
   dependency-trust egress), `--platform-posture` (connected legitify), or the
   network artifact fetches in `--behavioral-drift`. This keeps poisoned text
   from steering the host into outbound calls.
3. **Rate-limited.** Refuse a trigger for a repo whose most recent scan started
   within a cooldown window (**default 10 minutes**). The refusal is a
   structured `rate_limited` outcome with the seconds remaining — not an
   exception that reads like a crash. This bounds the obvious resource-abuse /
   re-scan-spam vector. (The cooldown applies to MCP-triggered scans; manual
   CLI scans are unaffected.)
4. **Non-destructive by construction.** The tool calls `scan_repo` only. It
   never calls `reset`, never deletes scans/findings, and never clears case
   decisions. Case decisions live in a separate `case_decisions` table keyed by
   stable `case_id`, so a re-scan **cannot** wipe an existing decision or hide a
   prior finding — it only appends a fresh scan. "Masking via re-scan" is
   therefore not reachable through this tool.
5. **Racing an in-flight decision is a non-issue by design.** Decisions key on
   stable `case_id` in their own table; scans append. A scan landing mid-apply
   cannot corrupt a decision. The cooldown additionally prevents rapid
   re-trigger storms.
6. **Audited.** The resulting scan row already records repo, profile,
   timestamps, and outcome — that is the audit trail. The trigger adds nothing
   destructive and writes nothing outside the normal scan record.

### Weaponization review (summary)

| Vector | Reachable? | What blocks it |
|---|---|---|
| Resource abuse / scan spam | No | Per-repo cooldown; local-offline profiles only |
| Masking a finding via re-scan | No | Append-only `save_scan`; decisions in a separate stable-id table; no delete/reset path |
| Racing an in-flight decision | No | Decisions keyed by stable `case_id`; scans only append |
| Target injection from finding text | No | `repo` is an allowlisted name → recorded path; never a raw path |
| Scanner/flag injection from finding text | No | `profile` is a fixed `{quick, default}` enum; no raw scanner names/flags |
| Network egress steering | No | `--trust` / `--platform-posture` / network drift fetches not exposed |

---

## 2. The high/critical suppression gate

### Current state (verified)

**The gate does not exist yet.** `set_case_decision` in `storage.py` is the
single low-level apply chokepoint for every surface (dashboard, CLI import, MCP
write). Its only suppression guard requires a *justification string for
dependency* suppressions (`storage.py`, the `is_dependency_decision` branch). It
does **not** look at severity at all. A high/critical `false_positive` or
`accepted_risk` applied through `apply_case_resolutions` would write straight
through. The gate must be added.

The suppressing decisions are exactly
`SUPPRESSING_DECISION_STATUSES = {"false_positive", "accepted_risk"}`
(`decisions.py`). Those are the only two that hide a finding from the active
list. `verified` and `fixed` are not suppressions and are not gated by this.

### Decision: where the gate lives

**Two layers, defense-in-depth:**

- **Enforcement at the chokepoint — `set_case_decision` (storage.py).** Add an
  explicit human-authorization signal (a parameter, defaulting to *not*
  authorized). When the decision is a suppressing status **and** the case
  severity is `high` or `critical` **and** the call is not human-authorized,
  refuse. `set_case_decision` can read severity from the case it already infers
  via `_latest_case_for_decision` (the returned case dict carries `severity`).
  This is the chokepoint every present and future write path crosses, so no new
  caller can bypass the gate by accident.
- **The automated MCP path never asserts human authorization.** When
  `apply_case_resolutions` runs with `source="mcp_write"` (an AI, no human
  present), it does not pass the authorization signal. So high/critical
  suppressions proposed by the AI hit the gate and are refused at the
  chokepoint. To surface that cleanly (rather than as a late exception),
  `_validate_resolution_item` records the case `severity` on each item at
  validate/preview time, and the apply loop short-circuits gated items into the
  `requires_human_confirmation` outcome below.

Why not gate only in `apply_case_resolutions`? Because the dashboard and CLI
also call `set_case_decision` directly; a finding-hiding bug or a future write
tool that skipped the case_followup layer would slip past a gate that lived only
there. The chokepoint is the honest place for an irreversible-ish control.

### Who counts as "human-authorized"

- **Dashboard click → authorized.** A human clicking "false positive" /
  "accept risk" on a critical in the dashboard *is* the confirmation. The
  dashboard's call asserts authorization.
- **MCP `apply_case_resolutions` (`source="mcp_write"`) → never authorized.**
  No human is present. High/critical suppressions are blocked.
- **CLI `cases import-resolutions --apply` → not authorized by default.** The
  CLI apply path is scriptable and can run unattended, so it is treated like the
  automated path: a high/critical suppression is blocked and reported, unless
  the operator passes an explicit opt-in flag (e.g. `--confirm-suppression`)
  that asserts authorization for that run. Low/medium/info suppressions and all
  non-suppressing decisions apply normally.

### What "requires human confirmation" means concretely

Not a hard error that aborts the batch, and **not** silently leaving the case
open as if nothing was proposed. It is a **distinct pending outcome**:

- The case **stays open and visible** — the fail-safe direction is *never hide a
  serious finding without a human*.
- The run item is recorded as `requires_human_confirmation` in the audit trail,
  **preserving** the AI's proposed decision, reason, and evidence, so nothing is
  lost.
- The rest of the batch (non-suppressing decisions, and low/medium/info
  suppressions) applies normally in the same call.
- The apply result reports a `requires_confirmation` count alongside
  `applied` / `left_open` / `rejected`.
- A human later confirms with one dashboard click (or the CLI opt-in flag),
  which re-runs the same audited `set_case_decision` with authorization
  asserted.

This is strictly better than a bare refusal: the analysis survives, the human
gets a concrete queue, and the finding never disappears in the meantime.

Distinction from existing outcomes: `needs_review` → `left_open` (the AI itself
was unsure). `requires_human_confirmation` is different — the AI is confident,
but the decision is irreversible-enough and serious-enough that a human must
sign off. Keep them as separate statuses.

---

## 3. Auto-merge-eligible fix-class allowlist (Phase 2)

Phase 2 builds a propose → clean-room-review → land loop. The clean-room
reviewer is **structural, not a prompt**: it receives only the **diff + the
invariants**, never the finding text, and that separation is enforced by how the
agent is invoked. **No path reaches auto-merge without a clean-room approval
recorded in the audit trail** — that gate is in addition to the class allowlist
below, not a substitute for it. Everything starts on a branch/PR; nothing is
ever committed straight to a protected branch.

Keep this list as narrow as it can be. Widening later is cheap; a wrong
auto-merge is not.

### Auto-merge-eligible classes (ALL conditions must hold for the class)

1. **GitHub Actions SHA pin.** Replace a mutable action ref
   (`uses: owner/action@v3` or `@main`) with a pinned 40-hex commit SHA of the
   **same** already-referenced action. Diff touches only
   `.github/workflows/*.{yml,yaml}`, only `uses:` lines, only the ref portion —
   no other workflow changes.
2. **Single dependency version bump to a patched version.** Raise one existing
   dependency's version in a manifest (`package.json`, `pyproject.toml`,
   `requirements.txt`, `go.mod`, etc.) to the advisory's fixed version. Same
   package; **no** package added or removed; **no** registry/source URL change.
   Patch or minor only.
3. **Lockfile patch.** A regenerated lockfile (`package-lock.json`, `uv.lock`,
   `poetry.lock`, `Cargo.lock`, …) consistent with an accompanying allowed
   dependency bump, or a standalone lockfile-only patched-version update. No
   source-code changes.

### Always-human (never auto-merge), regardless of clean-room verdict

- Any change to application/source code (`.py`, `.js`, `.ts`, … outside
  manifests / lockfiles / workflow files).
- Any **secret** rotation or removal. Secrets are never auto-fixed; rotation is
  recommended separately (consistent with the existing follow-up instructions).
- Any **major** (semver-major) version bump.
- Any change that **adds or removes** a dependency, changes a registry/source
  URL, or touches install scripts/hooks (`postinstall`, `prepare`, etc.).
- Any IaC / cloud-permissions / branch-protection change.
- Multi-file changes spanning more than {a manifest + its lockfile + the
  workflow-file group}.
- **Any high/critical suppression** — that goes through the §2 gate, not the fix
  loop, and always needs a human.

---

## Forward sweep — drift corrected in this step

Skimmed the remaining campaign steps; corrected REQUIRED READING that pointed at
paths/shapes this spec changes:

- **Step 1.2** — the severity gate is added primarily in
  `set_case_decision` (`storage.py`), not only in `case_followup.py`. Added
  `storage.py` to its REQUIRED READING and named the gate's two-layer shape.
- **Step 2.1** — REQUIRED READING pointed at `src/security_observatory/recovery.py`,
  which **does not exist**. Repointed to the real remediation surface:
  `priority.py` (fix-class / action-level reasoning), the `devsec-pr` /
  `devsec-fix` command skills (existing remediation scaffolding), and
  `case_followup.py` (the audited decision path to record proposals/approvals
  through).
