# Observed output - DëvSec agent doctrine verification

Run time: 2026-05-24 17:39 CEST

Verification method: each command was run from a fresh non-persistent Claude Code
CLI session in this repo:

```text
claude -p --no-session-persistence --model sonnet --effort high --permission-mode bypassPermissions '<command>'
```

The repeated `SessionEnd hook [./hooks/session-lock-release.sh] failed` line is
CLI hook noise from this checkout, not DëvSec command output.

## Verdict

Approved for voice calibration. The first-screen output is recognizable as the
DëvSec voice: status first, evidence-bound, calm, procedural, no theatrical
language, and no emoji outside the Honey Key carve-out.

Minor formatting friction remains in a few commands where the model adds short
notes despite exact-layout instructions. Those notes stayed operational and
evidence-bound, so they do not block the campaign.

## Commands observed

### `/devsec`

Observed opening:

```text
DëvSec — State of Affairs

3 repos tracked. Most recent scan today.

| Repo | Health | Last scan | Open cases |
| --- | --- | --- | --- |
| besk-ftigelse.dk | 0/100 | 2026-05-11 | 0 |
| obedai-learning-app | 0/100 | 2026-05-11 | 0 |
| de-v-security | 55/100 | 2026-05-24 | 6 |
```

Drift: the first run wrapped the whole dashboard in a code fence and added a
short explanatory note. Calibration added explicit "normal Markdown, no code
fence" and "no extra notes" instructions to `~/.claude/commands/devsec.md`.
Re-run removed the code fence. A short note still appeared, but it was factual
and evidence-bound.

### `/devsec-brief`

Observed opening:

```text
- **medium · ai-risk**: Agent config files reference unpinned package runners — untrusted input or tools could influence agent behavior and expose data. Verify `design/trailer/composition/AGENTS.md:8` and `CLAUDE.md:32-46`, then pin versions.
- **Posture** — 3 repos tracked, 0 healthy, 3 need attention (de-v-security at 55/100; besk-ftigelse.dk and obedai-learning-app unscored since last scan was 13 days ago).
- **Freshness** — Last scan of de-v-security finished today at 15:04 UTC — fresh. Other two repos last scanned 13 days ago — consider re-scanning.
```

Drift: none. The output is compact, status-led, and action-oriented.

### `/devsec-cases`

Observed opening:

```text
Open cases (all repos)

| Repo | Sev | Action | Category | Title | Risk |
|---|---|---|---|---|---|
| de-v-security | medium | verify | ai-risk | Unpinned package runner in AGENTS.md:8 | Agent config may let untrusted input influence behavior... |
```

Drift: none blocking. The command added a short category summary after the
table, but it stayed useful and aligned with the doctrine.

### `/devsec-fix secrets`

Observed opening after calibration:

```text
Playbook: Rotate leaked secrets and scrub history
Estimated time: ~20 min

Steps:
1. Confirm whether the exposed values in the affected files are real credentials without printing them in logs or chat.
2. Rotate or revoke the credential at the provider before changing code.
3. Remove the source of the secret from the affected files and replace it with an env var or secret-manager reference.
```

Drift: the first run appended extra advice after the playbook, including casual
phrasing about what people "regret." Calibration added an explicit stop rule to
`~/.claude/commands/devsec-fix.md`. Re-run confirmed the command now stops
after the playbook and handoff prompt.

### `/devsec-deps de-v-security`

Observed output:

```text
No dependency trust data for `de-v-security`. Either the repo hasn't been scanned with enrichment enabled, or it has no tracked packages.
```

Drift: none. The empty-state language is direct and scoped.

### `/devsec-voice`

Observed opening:

```text
DëvSec Voice Primer

DëvSec speaks to reduce ambiguity under pressure: status first, evidence always, next action clear. It is calm, local-first, and honest about what the MCP can and cannot do.

| Principle | What it means |
```

Drift: none. The primer stayed under 50 lines and matched the intended doctrine
summary.

### `/devsec-diff`

Observed opening after calibration:

```text
DëvSec — changes since previous scan (2026-05-23)

| Repo | Δ | Sev | Category | Title |
| --- | --- | --- | --- | --- |
| de-v-security | new | medium | ai-risk | Agent command uses unpinned package runner (AGENTS.md:8) |
```

Drift: the first run produced no output for about two minutes and was stopped.
Calibration bounded the default comparison to `scan_history(repo, limit=2)` and
added an omit-and-summarize fallback to `~/.claude/commands/devsec-diff.md`.
Re-run completed and produced a status-led diff. Minor residual formatting:
the table was still wrapped in a code fence and the model added an explanatory
"Read on the 6 new cases" block; both were operationally useful, not casual or
theatrical.

### `/devsec-pr`

Observed opening after calibration:

```text
Open cases that can become PRs

| Repo | Case | Sev | Category | Title |
| --- | --- | --- | --- | --- |
| de-v-security | case-0abfe06e49c3a70f | medium | ai-risk | Agent command uses a package runner without an obvious pinned version |
```

Drift: the first run added clustering and batching analysis after the missing
input table. Calibration added a missing-input stop rule to
`~/.claude/commands/devsec-pr.md`. Re-run still added one short cluster note,
but no preflight, edits, branch creation, push, or PR creation were attempted.
The safety boundary remained intact.

### `/devsec-honey`

Observed opening after calibration:

```text
Honey Keys — all projects

Placements:

| Project | Active | Triggered | Oldest | Last trigger |
| --- | --- | --- | --- | --- |
| beskæftigelse.dk | 1 | 0 | 13 days | — |
```

Drift: the first run wrapped the output in a code fence. Calibration added a
normal-Markdown instruction to `~/.claude/commands/devsec-honey.md`. Re-run
removed the code fence and kept the Honey Key language factual.

## Calibration edits made

- `~/.claude/commands/devsec.md` - normal Markdown, no code fence, no extra
  notes beyond the specified layout.
- `~/.claude/commands/devsec-fix.md` - stop after the playbook blocks; no
  extra commentary or follow-up suggestions.
- `~/.claude/commands/devsec-diff.md` - default comparison now reads only the
  two newest scans per repo and has an omit-and-summarize fallback.
- `~/.claude/commands/devsec-pr.md` - missing-input path now says to print only
  the table and final instruction, with no batching strategy.
- `~/.claude/commands/devsec-honey.md` - normal Markdown, no code fence.

No doctrine changes were needed, so no repo-side calibration commit was made.
