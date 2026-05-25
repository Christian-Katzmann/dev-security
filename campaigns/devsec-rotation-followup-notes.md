# Rotation follow-up — substance for the next campaign

> Findings intentionally deferred from **campaign #7 (devsec-rotation-hardening, 2026-05-25)**. Use this as the input when planning campaign #8 or whichever campaign picks up the rotation UX work.

---

## New finding (not in the 2026-05-25 audit punch list)

### Emergency rotation: `--no-grace` / single-shot incident flag [High]

**The gap:** when a Class B secret (Anthropic, Resend, Turso, GitHub OAuth, etc.) is actively being abused, the operator needs to rotate AND kill the old key immediately — not wait through a 24h grace window. Today this requires a two-step terminal dance:

1. `rotate <SECRET>` → enters IN_GRACE (new key live, old key still valid)
2. `rotate <SECRET> --force-revoke <id>` → old key killed now

Two commands during an incident at 2am is the wrong UX. The dashboard offers no surface for `--force-revoke` at all.

**Class A is already incident-safe.** Self-generated values (AUTH_SECRET, CRON_SECRET, etc.) have no grace — the moment the new value deploys, the old one is dead. This gap only affects Class B.

**Why grace is the default (for Class B):** background workers, webhook handlers, retry queues, long-running processes can all cache the old key in memory. Without grace, they hard-fail when the old key dies. Grace gives them time to refresh naturally. Right default for routine rotation; wrong default for an incident.

**Why incidents flip the calculus:** under attack, you WANT cached-old-key callers to fail loudly so you know what's still leaking the old credential. The collateral damage is the diagnostic signal.

**Suggested fix shape (rough sizing — medium):**

- Skill side: add `--no-grace` (skip the grace window entirely) and/or `--emergency` (composite: no soak, no grace, no health check — "I know what I'm doing, the key is compromised") to `rotate.ts.tmpl`.
- Receipt: surface emergency-mode loudly. Distinguish "operator chose to skip grace because of incident X" from "rotation completed normally" in the trust trail — auditors need to see this.
- Dashboard modal: expose under an "Advanced" disclosure with a deliberate "incident response" label and copy that names the trade-off (loud cached-caller failures vs. closing the attack window).
- Tier 5R confirmation phrase: needs its own variant since the irreversibility is different — provider key dies immediately instead of in 24h. Recommended: `Yes, rotate <SECRET> emergency-mode and accept that the old key dies immediately with no grace.`
- Audit contract: emergency mode writes a JSONL entry with `outcome: "emergency"` and a receipt explicitly labeled `EMERGENCY_ROTATION`. Surfaces in `rotation_status` rows as a new field (e.g., `emergency: true`) so the dashboard can show a "emergency rotation" badge alongside the existing "marked by operator" amber tone.

---

## Deferred from the 2026-05-25 audit punch list

Full audit lives at `/tmp/devsec-walkthrough-2026-05-25.md` (volatile — copy into the repo before relying on it). Items not closed by campaign #7:

### High
- **H2 — Status vs history consistency check.** `rotation_status` (reads state.json) and `rotation_history` (reads log.jsonl) can disagree. Campaign #7's `manually_marked` boolean closes part of this for overrides, but no consistency-check helper exists; the dashboard could surface a "trust trail consistent / inconsistent" badge.
- **H4 — Test mode toggle missing in dashboard modal.** Backend accepts `options.test_mode`; the slash command supports it; the modal exposes no checkbox. First-rotation operators have no GUI path to a safe `--test` run.
- **H5 — Job state in memory only.** `CHECK_JOBS` is a Python dict; dashboard restart mid-rotation loses tracking. Either persist to disk or rediscover via `rotation-log.jsonl` on startup.
- **H6 — Confirmation phrase has three sources of truth, no drift test.** Backend Python, frontend TS, doctrine markdown. Lock test that asserts all three produce identical strings for a fixture secret.
- **H7 — Phase track in modal shows 8 phases for all classes.** Class A has 3 effective phases; the modal renders 8 with mysterious skips. Class-aware phase list.

### Medium
- **M1 — Stdout phase classifier substring-brittle.** `_classify_stdout_line` matches phase tokens via substring; mis-classification possible on unusual log lines.
- **M2 — `requires_custom_plugin` enforcement is agent-only.** Catalog flags providers needing hand-written plugins; no scaffold-time guardrail prevents the generic template from being applied.
- **M3 — Class B-human (`WAITING_FOR_PASTE`) has no dashboard resume UI.** Operator forced back to terminal `npm run rotate -- <SECRET>` to paste the new value.
- **M4 — Cancellation/abort affordance is missing.** Frontend says "Cancellation isn't supported in v1" but offers no documented path to safely abort a stuck rotation.
- **M5 — `--skip-health-check` / `--soak-minutes` not exposed in modal.** Backend accepts them; slash command supports them; modal only exposes `--no-soak`. Inconsistent surface parity.
- **M6 — Class warning hard-coded in frontend.** Catalog has per-secret `rotation_warning` strings (e.g., NEXTAUTH_SECRET's session-invalidation note); modal shows the generic class-level warning instead.
- **M7 — No upgrade-path test.** `/secrets-rotation` UPGRADE mode is documented (re-running on a scaffolded repo applies diffs); no test exercises v0.1 → v0.2 upgrade. Now unblocked since campaign #7 shipped the reset command.
- **M8 — Receipt directory created lazily.** No scaffold-time sentinel distinguishing "never ran" from "pre-receipts v0.1 scaffold." Add a `data/rotation-receipts/.scaffolded-at` sentinel.

### Low
- **L1 — Binary stack support** (Vercel + Python CLI only). Other stacks see "not supported yet" with no path forward.
- **L2 — Scaffolding requires terminal + Claude Code.** Non-coder onboarding gap. Deliberate (scaffolding is interactive) but worth noting.
- **L3 — No `--status` quick view on dashboard.** Trigger error says "verify state with `npm run rotate --status`"; dashboard has no equivalent button.
- **L4 — No receipt-export affordance beyond copy.** Could add "Download as .md" or "Email to auditor."
- **L5 — Stdout leak prevention is by-convention.** If a future plugin accidentally logs a secret value, the dashboard's `stdout_tail` would render it. Belt-and-suspenders: a high-entropy pattern masker.

---

## Product gaps surfaced by Christian during live verification

### "Rotate all" / batch rotation [High]

Operator instinct seeing 12 NEVER-ROTATED secrets on besk: "I need a button to rotate all of these, not click-by-click." Campaign #4 (rotation-integration) deferred this explicitly: *"Batch rotation: in scope for v1 or defer? Lean: defer. Per-secret rotation is the primary use case; batch comes after we've watched single rotations work in practice."*

That deferral criterion is now met. We've watched single rotations work; batch is the obvious next move.

**Suggested fix shape (medium):**

- "Rotate all" button at the top of `RotationStatusCard`. Default behaviour: rotate every secret with `status === 'NEVER'` OR `needs_attention === true`. Optional "Rotate only overdue" / "Rotate only never-rotated" filters.
- Per-secret confirmation phrases don't scale to 18 secrets; the modal needs a single batch confirmation: `Yes, rotate <N> secrets and accept the irreversible provider-side changes.` (Tier 5R-style, names the count rather than each secret.)
- Sequential execution, not parallel. The concurrency lock from campaign #7 already refuses parallel rotations on the same secret; for different secrets, parallel could overwhelm provider rate limits. Sequential, with a live progress panel showing "Rotating 3 of 18 — CRON_SECRET in flight, AUTH_SECRET queued..."
- HALT semantics: if rotation N halts, the remaining queue STOPS by default. Operator gets a "continue with remaining" / "stop" choice. Don't blind-march through 18 rotations if 3 went wrong.
- Receipt: one batch-level Security Brief with per-secret sub-receipts; same shape as the existing override receipt but a level higher.

### One-button setup with BYOA disclosure [High]

Operator instinct after walking the v0.2 scaffolding: "The setup we just did should also be a one-button setup." The current flow — open terminal, cd, `claude`, `/secrets-rotation`, walk interactive prompts, ~20 minutes — assumes terminal comfort and AI-agent fluency. Non-coder operators (DëvSec's stated target user) can't get past step one.

**Tension to resolve:** the scaffolding flow is genuinely interactive (asks the operator to confirm tier, secret classifications, anti-scope), so it can't be fully one-button. But the manual context-switching is overkill for a one-time setup.

**Suggested fix shape (medium-large):**

- "Set up rotation" button in the dashboard's existing `ScaffoldEmptyState` already exists (returns command + working_directory). Extend it to optionally spawn the scaffolding agent in-process using the operator's own AI provider — bring-your-own-agent (BYOA) pattern.
- **Provider selection + token-cost disclosure:** before spawning, show a modal: *"This setup uses your own AI agent to walk through the scaffolding. Estimated cost: 5-15 cents in Claude tokens (10-20 minutes of agent work). The agent will run in-process and ask you to confirm classifications. Pick your provider: [Claude API key] [OpenAI key] [Local model]."* Token-cost surprise is a real Christian-pain — surface the cost up front.
- Connect-AI flow analogous to campaign #6's Connect-GitHub PAT flow: Keychain-stored API key, scoped permission ("rotation scaffolding only"), explicit "use this key for: $N tokens or until $M USD spent" cap.
- The interactive confirmations stay — but happen inside a dashboard modal with `AskUserQuestion`-style chips, not in a terminal session. The agent's responses stream into a panel; the operator only sees the decision points, not the file-write logs.
- Cost cap: an `--ai-budget-usd <N>` flag the scaffolder honors. If the agent exceeds the cap mid-scaffold, it pauses with "you've spent $X, continue with another $Y?" Operator opts in to spending more, opts out to bail.
- Documentation: explicit "what's your data sent to" disclosure. BYOA means the operator's API provider sees their repo's secret NAMES (never values). Spell it out.

This is bigger than the rotate-all change because it touches provider-credential management, billing telemetry, and a new in-dashboard agent-runtime surface. Worth its own campaign.

## Found during 2026-05-25 live verification (campaign #7 follow-up)

### CLI argparse gap in `reset` command [Medium — fixed inline]

`security-scan reset` accepts `--include-rotation-scaffold`, `--backup-to`, `--yes`, but the campaign #7 implementation read them via `sys.argv` sniffing without declaring them in argparse. Argparse rejected them before `reset_command()` ran. Unit tests passed (they call `reset_command()` directly with constructed Namespaces, bypassing argparse).

**Fixed in this session** (`src/security_observatory/cli.py:80-86`) by declaring the three flags with `help=argparse.SUPPRESS` so they're accepted but don't clutter top-level `--help`. The fix is unstaged — needs to be committed.

**Lesson worth recording for future autonomous campaigns:** code review and unit tests both passed; only a live invocation surfaced the gap. The reviewer's APPROVED verdict was correct given what they read, but reading code is not the same as running it.

### Frontend build pipeline isn't part of the campaign workflow [High — fixed inline]

Campaign #7 Step 3.2 wrote new TSX into `dashboard-ui/src/components/RotationStatusCard.tsx` and `RotationTriggerFlow.tsx`. Typecheck + lint + tests passed. The reviewer verified the source code lines.

**But the served bundle at `src/security_observatory/dashboard/assets/index-*.js` was never rebuilt.** The dashboard Christian opened was serving the pre-Step-3.2 build, with no `manually_marked` rendering, despite the API returning the new fields correctly. Found by direct grep against the bundled JS.

The vite config at `dashboard-ui/vite.config.ts:18-21` writes builds directly into `src/security_observatory/dashboard/` and empties the dir first — so `npm run build` is the single command needed. **It just wasn't part of the campaign #7 step's acceptance criteria.**

**Fixed in this session** by running `npm run build` from `dashboard-ui/` (new bundle: `index-C9mFW-mH.js`). Unstaged — needs commit.

**Lesson worth recording for the campaign template:** any step that touches `dashboard-ui/src/` MUST add `npm run build` (or a Makefile target that wraps it) to the acceptance criteria. The build-pipeline gap is invisible to typecheck, lint, and unit tests. Only manual verification catches it.

**Suggested fix shape (small):**

- Add a `dashboard:build` script to top-level `package.json` (or a Makefile target) that runs `cd dashboard-ui && npm run build`.
- Update `CONTRIBUTING.md` / `AGENTS.md` to require the build step after any `dashboard-ui/src/` change.
- Optional: a pre-commit hook that detects unbuilt `dashboard-ui/src/` changes and refuses the commit until `npm run build` has run.

### `reset` not discoverable in `--help`

`security-scan --help` doesn't list `reset` as a subcommand (it's dispatched by string-match on the positional `target` arg, not via a real subparser). Discoverability gap.

**Suggested fix:** refactor `security-scan` to use argparse subparsers (`dashboard`, `doctor`, `reset`, `ioc`, etc. all become real subparsers). Larger refactor than this campaign warrants; defer.

---

## Recommended grouping for campaign #8

Probably two campaigns, not one:

**Campaign #8a — Dashboard UX completeness.** Test-mode toggle, advanced options disclosure, class-aware phase track, B-human paste resume, cancellation affordance, per-secret `rotation_warning` plumbing. All frontend/dashboard work. Ship together so the modal stops feeling like it has missing buttons.

**Campaign #8b — Incident response + audit trail rigor.** Emergency rotation flag, status-vs-history consistency check, confirmation phrase drift test, job state persistence. Higher-stakes work; deserves its own focus.

Upgrade-path test (M7) slots into whichever campaign ships first since campaign #7's reset command now unblocks it.
