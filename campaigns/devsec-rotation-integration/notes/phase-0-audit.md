# Phase 0 audit — devsec-rotation-integration

Recalibration pass before Phases 1-3. Verifies the three dependency campaigns
landed cleanly and captures the actual artifact shapes Phases 1-3 will consume.

## Dependency campaigns — verdict

| Campaign | Status | Evidence |
| --- | --- | --- |
| 1 · devsec-power-commands | COMPLETE | `~/.claude/commands/devsec-{diff,pr,honey}.md` present; mcp_server.py exposes 8 tools (`list_repos`, `latest_scan`, `scan_history`, `findings`, `cases` with `scan_id=`, `recovery_playbook`, `dependency_trust`, `honey_keys`). |
| 2 · devsec-agent-doctrine | COMPLETE | `docs/agent-voice.md` and `docs/agent-safety.md` exist; mcp_server.py `DEVSEC_MCP_INSTRUCTIONS` carries the compact doctrine; every `/devsec-*` has a `## Voice` section; `/devsec-voice` ships. |
| 3 · devsec-rotation-foundation | COMPLETE | `~/.claude/skills/secrets-rotation/templates/adapters/{vercel,python-cli}.ts.tmpl` present; SKILL.md is at v0.2 with HEALTH_CHECK / canary / SOAK / verification report; three sample receipts in `campaigns/devsec-rotation-foundation/notes/sample-receipts/`. |

No campaign is incomplete. Phase 1-3 may proceed.

## MCP tool inventory (post-campaign 1)

Read `src/security_observatory/mcp_server.py`. Eight `@server.tool()` decorators:

1. `list_repos()` — repos with scan history.
2. `honey_keys()` — Honey Key placements + trigger state.
3. `latest_scan(repo)` — most-recent scan summary.
4. `scan_history(repo, limit=10)` — recent scans, most-recent first.
5. `findings(repo, severity=None, limit=50)` — findings on the latest scan.
6. `cases(repo, status=None, scan_id=None)` — cases on a scan (latest or named).
7. `recovery_playbook(category)` — category playbook (no DB).
8. `dependency_trust(repo)` — OpenSSF trust enrichments.

All read-only. The MCP `instructions` field explicitly rejects rotation:
> "It cannot delete findings, mark cases resolved, modify the store, install scanners, or rotate credentials."

**Implication for Phase 1.** Adding `rotation_status(repo)` and
`rotation_history(repo)` brings the surface to 10 tools. Both are pure reads
of skill state files in the target repo — they do NOT touch the security
store. The MCP `instructions` line that says "cannot ... rotate credentials"
stays true: the new tools READ the skill's state, the skill itself does the
rotating, triggered from a non-MCP surface.

The `instructions` field should be updated to mention rotation visibility
(e.g., "It can report scan history, cases, playbooks, dependency trust,
Honey Key state, **and rotation state for repos that have the
secrets-rotation skill scaffolded**.") so connecting agents know the
surface grew.

## Doctrine artifact paths

- `docs/agent-voice.md` — exact path (confirmed). No `docs/agent/voice.md` variant.
- `docs/agent-safety.md` — exact path (confirmed). Six tiers; cross-references
  `docs/agent-voice.md`.

## **DIVERGENCE — Tier 5 doctrine mismatch (LOAD-BEARING)**

The integration campaign's locked decisions state:

> "Rotation is Tier 5 per the safety doctrine. Confirmation gates apply per
> docs/agent-safety.md."

The actual `docs/agent-safety.md` reserves Tier 5 for **"Touch Defensive
Instrumentation"** (Honey Keys). Rotation is NOT covered by any existing tier.

Tier 5's confirmation phrases are about defensive instrumentation, not rotation:

1. "I understand this changes defensive instrumentation."
2. "Yes, modify the defensive instrumentation despite the risk."

Borrowing those phrases verbatim for rotation would be wrong on its face — the
operator confirms what they are doing, not a phrase about Honey Keys.

**Where rotation actually sits in the current doctrine:**

- Not Tier 1-2 (rotation mutates external state).
- Closest to Tier 3 (modify code outside the security store — rotation does
  modify `.env` and provider state), but Tier 3 treats normal code review as
  the gate. Rotation cannot route through PR review — it acts on live
  credentials.
- Tier 4 is about modifying the local security store, not external state.
- Tier 5 is Honey Keys.
- Tier 6 is installers.

Rotation is closest in *risk profile* to Tier 5 (irreversible at the provider,
requires elevated confirmation), but the existing Tier 5 *language* is about
defensive instrumentation. Using Tier 5 verbatim mislabels the action.

**Resolution.** The integration campaign cannot silently re-label Tier 5. Two
honest paths:

A. **Extend agent-safety.md with rotation-specific language.** Either as a
   new Tier 5a / Tier 7, or as a documented Tier 3-with-elevated-confirmation
   subsection. This is doctrine work — it belongs in Step 2.2 or Step 3.1's
   prompt (whichever first authors the modal/slash language). Adding a
   doctrine section is in-scope for *this* campaign because the doctrine is
   load-bearing for the modal copy.
B. **Pattern the rotation modal on Tier 4/5's STYLE** (refuse-by-default +
   explicit confirmation phrase) without quoting the Tier 5 phrases. Add an
   explicit one-paragraph rotation note inside docs/agent-safety.md so the
   doctrine and the modal are aligned.

Recommendation: **path A**. Add a "Rotation" subsection to docs/agent-safety.md
during Step 2.2 (or Step 3.1, whichever ships first). Use a confirmation
phrase like "Yes, rotate `<SECRET>` and accept the irreversible provider-side
change." This keeps the doctrine the source of truth — exactly as the campaign
intends.

**The campaign's locked decisions cannot be quietly changed, but the in-place
edits to Steps 2.2 and 3.1 carry the resolution: "The Tier 5 reference in the
locked decisions block was made before the doctrine was authored; treat it as
'use Tier-4/5 STYLE confirmation patterns and extend agent-safety.md with
rotation-specific language.'"** Step 2.2 and Step 3.1 prompts both now name
this explicitly.

## Verification receipt format (sample receipts inspection)

Read `campaigns/devsec-rotation-foundation/notes/sample-receipts/01-success-class-a-python-cli.md`,
`02-in-grace-class-b-api-vercel.md`, `03-halted-at-health-check-vercel.md`.

**Success/IN_GRACE shape (lock for the dashboard renderer):**

```markdown
# Rotation verified — `<SECRET_NAME>`

- **Status:** <ROTATED | IN_GRACE>
- **Action: completed · Severity: <info | medium>**
- **Provider check:** ✓ <provider> <result>
- **Application probe:** ✓ <stack-flavored probe description> returned ok
- **Soak test:** ✓ <N> min window, 0 new auth-related errors above baseline (<baseline-window> baseline)
- **Old key status:** <replaced | valid until <ISO timestamp> (24h grace; revoke runs automatically)>
- **Audit trail:** rotation_id `<uuid>`, events emitted to `<rotation-log.jsonl | audit-events.ts>`
- **New key fingerprint:** `sha256:<short>…` (cross-reference at the provider console)

Scope of this verification: <one line>. Outside scope: <one line>.
```

**Halted shape:**

```markdown
# Rotation HALTED — `<SECRET_NAME>` at <STEP>

- **Status:** <HEALTH_CHECK_FAILED | CANARY_VERIFY_FAILED | SOAK_FAILED | HALTED_AT_<STEP>>
- **Why:** <plain-English from errors.ts.tmpl>
- **What was preserved:** <one line>
- **Recovery:** <one line + command>
- **Audit trail:** rotation_id `<uuid>`, events emitted to `<...>`

The rotation did NOT complete. The old credential is still in use.
```

Both shapes match `campaigns/devsec-agent-doctrine/notes/calibration-examples.md`
#10 in tone. The dashboard renderer reads these files verbatim (markdown);
no shape translation needed.

## Skill invocation entry point (unified)

SKILL.md confirms a unified entry point regardless of stack:

```
rotate <SECRET>                         # zsh alias
npm run rotate -- <SECRET>              # raw form (npm flag-eating workaround)
```

The `rotate` shell function offered during scaffolding (Step 6 of the operator
procedure) bypasses npm's flag-eating quirk and is installed at user scope.
For both Vercel and Python CLI targets, the dispatch happens inside
`rotate.ts.tmpl` via `selectAdapter()` — the operator-facing command is
identical.

**Implication for Phase 2.2 / Step 3.1.** Shell-out invocation should be
`npm run rotate -- <SECRET>` (raw form) from the dashboard subprocess and
`rotate <SECRET>` from the slash command (when it's a Claude Code session
inside a scaffolded repo with the alias). For both surfaces, working
directory must be the target repo.

**No special-casing needed per stack** in either the dashboard backend or
the slash command. That removes a whole branch of conditional logic the
draft prompts assumed would be necessary.

## Status board emoji vs dashboard no-emoji

`~/.claude/skills/secrets-rotation/SKILL.md` shows the terminal status board
using emoji symbols: 🟢 ROTATED, 🟡 IN GRACE, ⏸ WAITING_FOR_PASTE, 🔴 OVERDUE,
⚪ MANUAL, ⚠️ NEVER.

This is the operator's terminal view, which lives outside the doctrine.

The integration campaign's locked decision for the dashboard is:

> "use words like ROTATED, IN GRACE, OVERDUE instead of symbols. Reserve the
> one ⚠ carve-out for IN_GRACE secrets approaching revoke time."

No conflict. The dashboard is a different surface and follows the doctrine
strictly; the terminal status board is the skill's own UX and isn't bound
by the doctrine. Phase 2 prompts already state this — no edit needed.

## Slash command convention (post-campaign-2)

Read `~/.claude/commands/devsec-pr.md` (closest sibling — also a write-action
command). Format:

- YAML frontmatter: `name`, `description`, `argument-hint`.
- Body sections (rough order): intent paragraph → Resolve / Preflight / Action
  / Confirm / final-output sections (named for the command's task).
- Mandatory `## Voice` section near the bottom referencing
  `docs/agent-voice.md`.
- For commands crossing safety tiers: an explicit "Tier note" paragraph
  after Voice, naming the tier and pointing to `docs/agent-safety.md`.
- Final `## Rules` section listing terse, enforceable constraints.

`/devsec-rotate` mirrors this shape exactly. The Tier note must call out
the rotation-specific tier language (per the DIVERGENCE resolution above).

## Dashboard code surface

`src/security_observatory/dashboard_server.py` — 2055 lines, single-file
ThreadingHTTPServer. Existing endpoints follow the `/api/<noun>/<action>`
convention with method-based routing. No streaming pattern in use today;
long-running ops (e.g., `CHECK_JOBS`) use a polled job-status pattern with
a `CHECK_JOBS_LOCK` threading lock. The repository has no SSE / WebSocket
infrastructure.

**Implication for Phase 2.2.** Rotation pipeline streaming should use the
existing polled-job pattern (`POST /api/rotation/trigger` returns a job_id;
`GET /api/rotation/jobs/<id>` returns current pipeline phase). Don't
introduce SSE/WebSocket as a one-off — match the dashboard's existing
mechanic.

`dashboard-ui/src/components/` — 13 view components. Closest analog for a
rotation card: `HoneyKeysView.tsx` (status list with per-row actions).
Imports lucide-react icons; reads from `dashboardData.ts`; uses Tailwind
classes; `useMemo` / `useState` for local UI state.

**Existing "rotation" references in the UI are unrelated:** Incident
response steps in App.tsx reference "Real secrets rotated" as a checklist
item; CaseCard.tsx renders `rotation_surfaces` for install-hooks cases.
Neither implements rotation status display — no duplication risk.

## Open questions (carried to Phase 1-3)

1. **(RESOLVED above)** Did Campaign 1-3 change a locked decision? Yes — the
   doctrine doesn't have a rotation tier. Resolution captured in the in-place
   edits to Steps 2.2 and 3.1.
2. **(RESOLVED above)** Did the MCP boundary become writable? No. Still
   read-only.
3. **(RESOLVED above)** Did the verification receipt format change? No. Locked
   shape captured above.
4. **(RESOLVED above)** Does the dashboard duplicate work? No. Existing
   rotation references are unrelated.

## Summary of in-place edits to this campaign markdown

| Step | Edit |
| --- | --- |
| 1.1 | Replaced `(populated by Step 0.1)` with the audited 8-tool inventory + state-file path notes. |
| 2.1 | Replaced placeholder with HoneyKeysView.tsx as the closest component analog; noted no SSE/WebSocket pattern; noted no existing rotation card. |
| 2.2 | Replaced placeholder with the Tier-5-doctrine divergence note and explicit guidance to extend agent-safety.md with rotation language; named polled-job streaming pattern. |
| 3.1 | Replaced placeholder with `npm run rotate -- <SECRET>` unified entry point + same Tier divergence note. |
| 3.2 | Confirmed case shape from cases.py (read via Read tool earlier in the audit); no placeholder to fill. |
