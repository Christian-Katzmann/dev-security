# AI Case Follow-Up Workflow Plan

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ PLAN: AI Case Follow-Up Workflow                                            │
│ Status: IMPLEMENTED - JSON import and guarded MCP write-back shipped        │
│ Progress: [####################] 47/47 tasks                                │
│ Updated: 2026-05-30                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Objective

Make it simple for a user to act on scan results after a repository scan:

1. Choose what they want an AI agent to do.
2. Choose which cases should be included.
3. Copy a clear, bounded prompt.
4. Let the AI investigate the repo.
5. Import or write back structured case resolutions.
6. See the dashboard update so false positives, accepted risks, and fixed cases no longer pollute open critical counts.

The target user experience is:

```text
AI follow-up

[ Verify findings v ] [ Critical v ]

Verify 14 critical findings in beskæftigelse.dk and classify them...
[ Copy prompt ] [ Import AI result ]
```

On the all-repositories dashboard, the panel adds a repository selector:

```text
[ beskæftigelse.dk v ] [ Verify findings v ] [ Critical v ]
```

## What & Why

The current workflow is too confusing:

- The dashboard can show a critical case even when the scanner only found an insecure example inside documentation or an AI command file.
- The per-case prompt tells the AI to inspect evidence, but it does not force a machine-readable verdict.
- The AI may correctly say "this is a false positive," but DëvSec still has no automatic way to record that decision.
- The MCP adapter currently exposes read-only scan context. That is useful for investigation, but it cannot mark cases as false positive, accepted risk, or fixed.
- The existing dashboard has manual case decision buttons, but the user should not need to repeat that by hand for 14 critical cases.

The improved workflow should make DëvSec feel like this:

```text
Run scan -> Ask AI to verify/fix/plan -> Import or apply structured result -> Dashboard reflects reality
```

Critical severity should mean "look here first," not "this is definitely exploitable." AI follow-up must help separate real risk from scanner evidence.

## Scope Boundaries

### In Scope

- Add a compact "AI follow-up" control to repository-specific dashboard views.
- Add the same control to all-repositories views with a repository dropdown.
- Generate scoped prompts for AI agents.
- Support actions:
  - `verify_findings`
  - `fix_vulnerabilities`
  - `create_remediation_plan`
  - `explain_risk`
  - `recheck_after_fixes`
- Support scopes:
  - `critical`
  - `critical_high`
  - `all_open`
  - `selected_cases`
  - `new_since_last_scan`
- Require AI verification prompts to return structured JSON.
- Add JSON import/preview/apply for AI-produced case resolutions.
- Store an audit trail for imported AI resolution runs.
- Record final case decisions through the existing case decision path where possible.
- Suppress false-positive and accepted-risk cases from open case counts.
- Keep unclear cases open.
- Document the workflow for Codex, Claude Code, and other local agents.
- Optionally add a guarded write-back path for local MCP-capable agents.

### Out of Scope

- Do not let an AI delete raw findings.
- Do not let an AI delete scan history.
- Do not let an AI rotate credentials through this workflow.
- Do not send repository contents or scan reports to hosted services from DëvSec itself.
- Do not make Agent Lab responsible for this workflow. Agent Lab is for scan proposals; this is for case follow-up.
- Do not imply that a scan result is "secure" or "clean" globally. Use "clear within scan scope."
- Do not mark secret findings as false positive unless the prompt/result explains why the value is synthetic, test-only, revoked, or otherwise non-sensitive.

## Product Decisions

- Name the surface **AI follow-up**.
- Keep it near the cases/findings experience, not hidden in Agent Lab.
- Default action is `Verify findings`.
- Default scope is `Critical` when critical cases exist, otherwise `Critical + High`, otherwise `All open`.
- Use `Critical + High` in the UI instead of "Elevated"; "elevated" is too vague for a handoff prompt.
- The visible prompt preview should be one line only.
- The copied prompt can be long and include all selected case evidence.
- The copy button label should be human:

```text
Give this to your AI of choice
```

- The import path must work even when the AI has no MCP connection.
- MCP write-back should be optional and explicitly guarded; JSON import is the universal path.

## Data Model

### Existing State

Relevant existing pieces:

- `src/security_observatory/storage.py`
  - `ObservatoryDB.set_case_decision(...)`
  - `ObservatoryDB.case_decisions_map()`
  - VEX import/export for dependency decisions
- `src/security_observatory/decisions.py`
  - decision statuses
  - dependency suppression matching
- `src/security_observatory/dashboard_server.py`
  - `POST /api/case-decision`
  - `build_ai_prompt(...)`
- `dashboard-ui/src/App.tsx`
  - `casePromptMarkdown(...)`
  - `FindingsView`
  - `CaseDetailCard`
- `dashboard-ui/src/dashboardData.ts`
  - `CaseDecisionStatus`
  - `displayCases(...)`
  - `suppressedDisplayCases(...)`
  - `caseNeedsAttention(...)`
- `src/security_observatory/mcp_server.py`
  - read-only MCP tools
- `mcp/README.md`
  - explicitly documents read-only MCP boundaries

Existing case decision statuses:

```text
verified
false_positive
accepted_risk
fixed
```

### Required Resolution Vocabulary

The AI should return a richer verification vocabulary:

```text
confirmed_real
false_positive
docs_example
accepted_risk
already_fixed
fixed_by_agent
needs_review
```

Map those into existing case decisions:

| AI disposition | Stored decision | Suppresses open case? | Meaning |
| --- | --- | --- | --- |
| `confirmed_real` | `verified` | No | The risk appears real and still needs action. |
| `false_positive` | `false_positive` | Yes | Scanner evidence is not a real project risk. |
| `docs_example` | `false_positive` | Yes | Evidence is an intentionally bad example, not live behavior. |
| `accepted_risk` | `accepted_risk` | Yes | Risk is real but consciously accepted. |
| `already_fixed` | `fixed` | Yes unless the latest scan still finds it | Repo no longer contains the risky state. |
| `fixed_by_agent` | `fixed` | Yes only after tests/rescan evidence | Agent changed code and verified closure. |
| `needs_review` | no case decision | No | Leave open; store in resolution-run audit. |

### New Audit Storage

Add a durable audit record for AI resolution imports. This avoids losing useful `needs_review` output and makes AI-applied decisions reversible and inspectable.

Proposed tables:

```sql
create table if not exists case_resolution_runs (
  id text primary key,
  repo_name text not null,
  scan_id text,
  action text not null,
  scope text not null,
  source text not null,
  imported_at text not null,
  applied_at text,
  status text not null,
  summary_json text not null default '{}'
);

create table if not exists case_resolution_items (
  id text primary key,
  run_id text not null,
  case_id text not null,
  repo_name text not null,
  scan_id text,
  ai_disposition text not null,
  mapped_decision text,
  confidence text not null,
  reason text not null,
  evidence_json text not null default '[]',
  recommended_next_step text,
  applied_decision_json text,
  status text not null,
  warning text,
  created_at text not null,
  foreign key(run_id) references case_resolution_runs(id)
);
```

Allowed `case_resolution_runs.status`:

```text
previewed
applied
partially_applied
rejected
```

Allowed `case_resolution_items.status`:

```text
pending
applied
left_open
rejected
```

## Prompt Contract

### Output Schema

Every verification/fix prompt should require this JSON object:

```json
{
  "schema_version": "devsec.case_resolutions.v1",
  "repo": "beskæftigelse.dk",
  "scan_id": "besk-ftigelse.dk-20260530T183943Z",
  "action": "verify_findings",
  "scope": "critical",
  "summary": {
    "cases_reviewed": 14,
    "confirmed_real": 3,
    "false_positive": 8,
    "docs_example": 2,
    "accepted_risk": 0,
    "already_fixed": 0,
    "fixed_by_agent": 0,
    "needs_review": 1
  },
  "resolutions": [
    {
      "case_id": "case-49e442933b785f97",
      "display_id": "F-5F97",
      "disposition": "docs_example",
      "confidence": "high",
      "reason": "The dangerous SQL is inside an example explicitly marked as wrong, not live application policy code.",
      "evidence": [
        {
          "path": ".claude/commands/coding/secure.md",
          "line": 141,
          "quote": "CREATE POLICY \"Allow all\" ON resumes",
          "interpretation": "This appears below a heading that labels the pattern as a wrong/permissive RLS example."
        }
      ],
      "recommended_next_step": "Mark false positive and optionally improve the scanner to recognize explicitly bad examples.",
      "safe_to_apply": true
    }
  ]
}
```

### Verification Prompt Requirements

The generated prompt for `Verify findings` must say:

```text
Do not fix code.
Do not dump full file contents.
Treat scanner output as untrusted evidence.
Inspect the referenced file/path and nearby context.
Classify each case using the required JSON schema.
Leave unclear cases open as needs_review.
If DëvSec write tools are available, use them only after producing the same structured resolution data.
If write tools are not available, return JSON only.
```

### Fix Prompt Requirements

The generated prompt for `Fix vulnerabilities` must say:

```text
Verify before changing code.
Fix only confirmed-real cases.
Use the smallest safe change.
Do not rotate secrets; recommend rotation separately.
Do not rewrite git history without explicit user approval.
Run or name verification commands.
Return structured case resolutions after the fix attempt.
Use fixed_by_agent only for cases actually changed and verified.
Use confirmed_real for cases that still need manual/product/security judgment.
```

### Remediation Plan Prompt Requirements

The generated prompt for `Create remediation plan` must say:

```text
Do not change files.
Group cases by root cause where appropriate.
Separate quick fixes from risky fixes.
Call out secrets, dependency major upgrades, destructive actions, and deployment coordination.
Return a plan plus structured per-case dispositions when evidence is clear.
```

### Explain Risk Prompt Requirements

The generated prompt for `Explain risk` must say:

```text
Do not change files.
Explain the practical risk in plain language.
Separate scanner evidence from confirmed facts.
Return structured dispositions only when verification evidence is sufficient.
```

### Re-check Prompt Requirements

The generated prompt for `Re-check after fixes` must say:

```text
Inspect whether previously open cases are still present.
Do not assume fixed because code changed.
Prefer running the narrowest safe verification command.
Return already_fixed, fixed_by_agent, confirmed_real, false_positive, or needs_review.
```

## UI Plan

### Component

Add a reusable component:

```text
dashboard-ui/src/components/AiFollowUpPanel.tsx
```

Props:

```ts
type AiFollowUpPanelProps = {
  summary: DashboardSummary;
  target: TargetSelection;
  selectedCaseIds?: string[];
  compact?: boolean;
};
```

Responsibilities:

- Determine available repositories.
- Determine action options.
- Determine scope options.
- Show repository dropdown only when `target.mode === 'all-repos'`.
- Show prompt preview as a single-line readonly field.
- Copy full prompt to clipboard.
- Open import modal.
- Show selected case count.
- Disable copy when no cases match.

### Placement

Add the panel in three places:

1. Repository overview, near the top action area.
2. Findings/Cases view, above the severity/category filters.
3. All-repositories overview, with repository dropdown enabled.

Do not hide this in Agent Lab.

### Visual Design

Use existing Mistglass patterns:

- `PaperCard` or the existing action strip style.
- Native-looking dropdowns/segmented controls.
- One primary copy button.
- One secondary import button.
- No large text block in the dashboard body.
- No nested cards.
- Keep button labels short.

Suggested copy:

```text
AI follow-up
Verify findings
Critical
Verify 14 critical findings in beskæftigelse.dk and classify them...
Give this to your AI of choice
Import AI result
```

### Import Modal

Add an import modal:

```text
Paste AI result JSON

[ textarea ]

[ Preview result ] [ Cancel ]
```

After preview:

```text
14 cases reviewed
8 false positives
2 docs examples
3 confirmed real
1 needs review

[ Apply resolutions ] [ Cancel ]
```

Show warnings before apply:

- Unknown case id.
- Case belongs to a different repo.
- Scan id mismatch.
- Missing reason.
- Missing evidence.
- Secret false-positive without adequate explanation.
- Fixed case without verification command/evidence.
- AI tried to resolve a case outside the selected scope.

## Backend/API Plan

### Prompt Builder

Add a new module:

```text
src/security_observatory/case_followup.py
```

Responsibilities:

- Define action/scope constants.
- Select matching cases from dashboard/scan exports.
- Build concise prompt preview.
- Build full copied prompt.
- Validate AI resolution JSON.
- Map AI dispositions to case decisions.
- Prepare preview/apply summaries.

Suggested functions:

```python
build_case_followup_prompt(db, *, repo_name, action, scope, case_ids=None) -> dict
validate_case_resolutions(db, payload, *, expected_repo=None, expected_scope=None) -> dict
apply_case_resolutions(db, preview_id_or_payload) -> dict
```

### Dashboard Endpoints

Add endpoints:

```text
GET /api/ai-follow-up/prompt?repo=<repo>&action=<action>&scope=<scope>&caseId=<id>...
POST /api/ai-follow-up/resolutions/preview
POST /api/ai-follow-up/resolutions/apply
GET /api/ai-follow-up/resolution-runs?repo=<repo>
```

Prompt response:

```json
{
  "repo": "beskæftigelse.dk",
  "action": "verify_findings",
  "scope": "critical",
  "case_count": 14,
  "preview": "Verify 14 critical findings in beskæftigelse.dk and classify them...",
  "prompt": "...full markdown prompt..."
}
```

Preview response:

```json
{
  "run_id": "resolution-run-...",
  "valid": true,
  "summary": {
    "total": 14,
    "will_apply": 13,
    "will_leave_open": 1,
    "warnings": []
  },
  "items": [
    {
      "case_id": "case-49e442933b785f97",
      "display_id": "F-5F97",
      "disposition": "docs_example",
      "mapped_decision": "false_positive",
      "status": "pending",
      "reason": "..."
    }
  ]
}
```

Apply response:

```json
{
  "run_id": "resolution-run-...",
  "applied": 13,
  "left_open": 1,
  "rejected": 0,
  "case_ids": ["case-..."],
  "warnings": []
}
```

### Case Decision Behavior

Adjust case decision suppression so:

- `false_positive` suppresses the exact case across current/future scans when the case id matches.
- `accepted_risk` suppresses the exact case across current/future scans when the case id matches.
- Dependency false positives continue to support identity-based suppression through existing VEX matching.
- `verified` does not suppress.
- `fixed` suppresses only if the latest scan no longer finds the case; if the case reappears, show it again.
- `needs_review` does not create a case decision and remains open.

This likely touches:

```text
src/security_observatory/decisions.py
src/security_observatory/storage.py
dashboard-ui/src/dashboardData.ts
```

### CLI Plan

Add CLI commands for non-dashboard use:

```text
security-scan cases prompt --repo beskæftigelse.dk --action verify_findings --scope critical
security-scan cases import-resolutions --repo beskæftigelse.dk --input resolutions.json --preview
security-scan cases import-resolutions --repo beskæftigelse.dk --input resolutions.json --apply
```

This gives shell-first agents a stable path even without MCP.

## MCP Plan

### Recommended First Step

Keep the existing `devsec-mcp` read-only. Do not break the promise in `mcp/README.md`.

### Optional Write Path

Add a separate guarded write mode later:

```text
devsec-mcp-rw
```

or:

```text
uv run devsec-mcp --allow-case-decisions
```

The write-enabled MCP must expose only case-resolution tools:

```text
case_followup_prompt(repo, action, scope, case_ids?)
preview_case_resolutions(payload)
apply_case_resolutions(payload_or_run_id)
```

It must not expose:

- raw finding deletion
- scan deletion
- credential rotation
- arbitrary SQL
- file writes in scanned repos

MCP apply rules:

- Require valid schema version.
- Require known case ids.
- Require repo match.
- Require reason and evidence for every suppressing disposition.
- Reject `fixed_by_agent` without verification evidence.
- Leave `needs_review` open.
- Return the same preview/apply summary as the dashboard API.

## Tasks

### Phase 0: Product Contract

- [x] **P0-1** [design] Finalize action vocabulary.
      File: `docs/ai-case-follow-up-workflow-plan.md`
      Action: Confirm `verify_findings`, `fix_vulnerabilities`, `create_remediation_plan`, `explain_risk`, and `recheck_after_fixes`.

- [x] **P0-2** [design] Finalize scope vocabulary.
      File: `docs/ai-case-follow-up-workflow-plan.md`
      Action: Confirm `critical`, `critical_high`, `all_open`, `selected_cases`, and `new_since_last_scan`.

- [x] **P0-3** [design] Finalize AI resolution schema.
      File: `src/security_observatory/case_followup.py`
      Action: Encode `devsec.case_resolutions.v1` as the canonical import contract.

- [x] **P0-4** [docs] Document status mapping.
      File: `docs/false-positives.md`
      Action: Add AI disposition mapping and explain why `docs_example` becomes `false_positive`.

### Phase 1: Backend Prompt + Validation

- [x] **P1-1** [feat] Add `case_followup.py`.
      File: `src/security_observatory/case_followup.py`
      Action: Implement prompt building, case filtering, preview generation, and schema validation.

- [x] **P1-2** [feat] Add case selection by action/scope.
      File: `src/security_observatory/case_followup.py`
      Action: Select latest repo cases by severity, decision state, selected ids, or change state.

- [x] **P1-3** [feat] Generate prompt previews.
      File: `src/security_observatory/case_followup.py`
      Action: Return one-line preview strings for the dashboard field.

- [x] **P1-4** [feat] Generate full prompts.
      File: `src/security_observatory/case_followup.py`
      Action: Include cases, evidence, guardrails, action-specific instructions, and required JSON schema.

- [x] **P1-5** [feat] Validate AI resolution JSON.
      File: `src/security_observatory/case_followup.py`
      Action: Reject unknown schema, unknown case ids, wrong repo, missing reason, missing evidence, unsupported disposition, and unsafe fixed/secret claims.

- [x] **P1-6** [feat] Map AI dispositions to case decisions.
      File: `src/security_observatory/case_followup.py`
      Action: Convert AI dispositions to existing `case_decisions` statuses or leave open for `needs_review`.

### Phase 2: Storage + Case Suppression

- [x] **P2-1** [feat] Add resolution-run tables.
      File: `src/security_observatory/storage.py`
      Action: Add migrations for `case_resolution_runs` and `case_resolution_items`.

- [x] **P2-2** [feat] Store previewed/imported AI resolution runs.
      File: `src/security_observatory/storage.py`
      Action: Persist every imported item, including rejected and left-open items.

- [x] **P2-3** [feat] Apply valid resolutions through `set_case_decision`.
      File: `src/security_observatory/storage.py`
      Action: Save mapped decisions for `false_positive`, `docs_example`, `accepted_risk`, `already_fixed`, and verified real cases.

- [x] **P2-4** [fix] Suppress exact non-dependency false positives.
      File: `src/security_observatory/decisions.py`
      Action: Make exact case-id `false_positive` and `accepted_risk` decisions suppress matching active cases, not only dependency cases.

- [x] **P2-5** [fix] Keep recurring fixed cases visible.
      File: `src/security_observatory/decisions.py`
      Action: Preserve current behavior where a case marked `fixed` reappears if the latest scan still finds it.

- [x] **P2-6** [feat] Expose resolution run summaries in dashboard payload.
      File: `src/security_observatory/storage.py`
      Action: Add recent resolution runs to `dashboard_payload()`.

### Phase 3: Dashboard API

- [x] **P3-1** [feat] Add prompt endpoint.
      File: `src/security_observatory/dashboard_server.py`
      Action: Implement `GET /api/ai-follow-up/prompt`.

- [x] **P3-2** [feat] Add resolution preview endpoint.
      File: `src/security_observatory/dashboard_server.py`
      Action: Implement `POST /api/ai-follow-up/resolutions/preview`.

- [x] **P3-3** [feat] Add resolution apply endpoint.
      File: `src/security_observatory/dashboard_server.py`
      Action: Implement `POST /api/ai-follow-up/resolutions/apply`.

- [x] **P3-4** [feat] Add resolution-run history endpoint.
      File: `src/security_observatory/dashboard_server.py`
      Action: Implement `GET /api/ai-follow-up/resolution-runs`.

- [x] **P3-5** [fix] Return clear user-facing errors.
      File: `src/security_observatory/dashboard_server.py`
      Action: Use plain error strings for invalid JSON, wrong repo, missing evidence, and unsupported dispositions.

### Phase 4: Dashboard UI

- [x] **P4-1** [feat] Add `AiFollowUpPanel`.
      File: `dashboard-ui/src/components/AiFollowUpPanel.tsx`
      Action: Build compact controls for action, scope, optional repo, prompt preview, copy, and import.

- [x] **P4-2** [feat] Add type definitions.
      File: `dashboard-ui/src/dashboardData.ts`
      Action: Add types for prompt response, resolution preview, resolution run, action ids, and scope ids.

- [x] **P4-3** [feat] Place panel on repo overview.
      File: `dashboard-ui/src/App.tsx`
      Action: Render the panel when `target.mode === 'repo'`.

- [x] **P4-4** [feat] Place panel on all-repos overview.
      File: `dashboard-ui/src/App.tsx`
      Action: Render the panel with repository dropdown when `target.mode === 'all-repos'`.

- [x] **P4-5** [feat] Place panel on Findings/Cases view.
      File: `dashboard-ui/src/App.tsx`
      Action: Render the panel above severity/category filters.

- [x] **P4-6** [feat] Add import modal.
      File: `dashboard-ui/src/components/AiFollowUpPanel.tsx`
      Action: Paste JSON, preview result, show warnings, apply resolutions, reload summary.

- [x] **P4-7** [design] Style the panel.
      File: `dashboard-ui/src/index.css`
      Action: Use existing Mistglass tokens, compact rows, stable dimensions, and responsive behavior.

- [x] **P4-8** [fix] Make open counts ignore suppressed/closed cases consistently.
      File: `dashboard-ui/src/dashboardData.ts`
      Action: Ensure false positives and accepted risks do not appear in open critical counts or recent activity as unresolved.

### Phase 5: CLI

- [x] **P5-1** [feat] Add `security-scan cases prompt`.
      File: `src/security_observatory/cli.py`
      Action: Generate the same prompt as the dashboard endpoint.

- [x] **P5-2** [feat] Add `security-scan cases import-resolutions --preview`.
      File: `src/security_observatory/cli.py`
      Action: Validate and summarize AI result JSON without applying.

- [x] **P5-3** [feat] Add `security-scan cases import-resolutions --apply`.
      File: `src/security_observatory/cli.py`
      Action: Apply valid mapped decisions and print a concise summary.

### Phase 6: Optional MCP Write-Back

- The read-only `devsec-mcp` boundary is preserved. Guarded write-back ships
  separately as `devsec-mcp-rw` with only case-resolution prompt, preview, and
  apply tools.

- [x] **P6-1** [design] Decide write-enabled MCP shape.
      File: `mcp/README.md`
      Action: Choose separate `devsec-mcp-rw` command or `--allow-case-decisions` flag.

- [x] **P6-2** [feat] Add guarded case-resolution MCP tools.
      File: `src/security_observatory/mcp_server.py`
      Action: Add prompt, preview, and apply tools only in explicit write mode.

- [x] **P6-3** [docs] Preserve read-only default docs.
      File: `mcp/README.md`
      Action: Keep existing `devsec-mcp` documented as read-only and document write mode separately.

### Phase 7: Documentation

- [x] **P7-1** [docs] Update README workflow.
      File: `README.md`
      Action: Add "Run scan -> AI follow-up -> import/apply resolutions -> rescan" workflow.

- [x] **P7-2** [docs] Update false-positive guidance.
      File: `docs/false-positives.md`
      Action: Explain AI-assisted false-positive closure, docs examples, evidence requirements, and audit trail.

- [x] **P7-3** [docs] Update agent safety guidance.
      File: `docs/agent-safety.md`
      Action: Add boundaries for AI case-resolution imports and optional MCP write-back.

- [x] **P7-4** [docs] Update MCP docs.
      File: `mcp/README.md`
      Action: Document read-only default and optional case-decision write path if implemented.

### Phase 8: Tests

- [x] **P8-1** [test] Test prompt filtering.
      File: `tests/test_case_followup.py`
      Action: Verify critical, critical+high, all-open, selected, and new-since-last-scan scopes.

- [x] **P8-2** [test] Test prompt contract.
      File: `tests/test_case_followup.py`
      Action: Verify prompts include action-specific instructions, no-fix language for verification, and required JSON schema.

- [x] **P8-3** [test] Test resolution validation.
      File: `tests/test_case_followup.py`
      Action: Reject unknown case id, wrong repo, missing reason, missing evidence, unsupported disposition, and unsafe fixed claims.

- [x] **P8-4** [test] Test resolution application.
      File: `tests/test_case_followup.py`
      Action: Apply docs-example as false positive, confirmed-real as verified, accepted-risk as accepted risk, already-fixed as fixed, and needs-review as left open.

- [x] **P8-5** [test] Test non-dependency suppression.
      File: `tests/test_cases.py`
      Action: Ensure exact non-dependency false positives disappear from open cases and remain visible in suppressed/decision history.

- [x] **P8-6** [test] Test dashboard endpoints.
      File: `tests/test_dashboard_case_followup.py`
      Action: Cover prompt, preview, apply, and resolution-run history endpoints.

- [x] **P8-7** [test] Test CLI commands.
      File: `tests/test_cli_case_followup.py`
      Action: Cover prompt generation and import preview/apply paths.

- [x] **P8-8** [test] Test MCP write mode if implemented.
      File: `tests/test_mcp_server.py`
      Action: Verify write tools are absent in read-only mode and present only in explicit write mode.

## Decisions & Context

- The dashboard already supports manual case decisions through `POST /api/case-decision`.
- The current whole-repo AI prompt is useful but too broad for verification and write-back.
- The current case prompt is useful for one case but too manual for 14 critical cases.
- The MCP adapter is intentionally read-only today. Preserve that default.
- Importing JSON is the safest universal bridge because it works with any AI agent, including agents without MCP.
- A write-enabled MCP can be added later, but it should only write case decisions through the same validation path as dashboard import.
- `docs_example` should not remain an open critical vulnerability. It should map to `false_positive` with clear evidence.
- `confirmed_real` should not make a case green. It should mark the case as verified and still needing fix.
- `needs_review` should not close anything.

## Blockers & Open Questions

- Should `accepted_risk` suppress open critical counts, or should it appear in a separate "Accepted risk" posture warning? Current behavior treats it as not needing attention; keep that for v1 unless product direction changes.
- Should `fixed` suppress immediately after AI says fixed, or only after a rescan? Recommended: require verification evidence for `fixed_by_agent`, and re-open if the latest scan still finds the case.
- Should the first implementation include MCP write mode? Recommended: no. Ship dashboard/CLI JSON import first, then add MCP write-back once the validation path is proven.
- Should `docs_example` remain a distinct stored status? Recommended: no for v1. Store as `false_positive` with the reason containing "docs example."
- Should prompt generation happen client-side or server-side? Recommended: server-side, because server-side code can reuse scan exports, filtering, validation constants, and future CLI/MCP paths.

## Verification

For docs-only changes:

```bash
git diff --check
```

For backend/API work:

```bash
python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"
uv run pytest tests/test_case_followup.py tests/test_cases.py tests/test_dashboard_case_followup.py
```

For CLI work:

```bash
uv run pytest tests/test_cli_case_followup.py
```

For dashboard UI work:

```bash
cd dashboard-ui && npm run lint
cd dashboard-ui && npm run build
```

For MCP write mode, if implemented:

```bash
uv run pytest tests/test_mcp_server.py
```

Final full check:

```bash
uv run pytest
cd dashboard-ui && npm run lint
cd dashboard-ui && npm run build
```

## Review

Acceptance criteria:

- A user on a repo dashboard can choose `Verify findings` + `Critical`, copy a prompt, and give it to Codex/Claude/another AI.
- The prompt tells the AI not to fix code for verification actions.
- The prompt forces structured JSON output.
- The user can paste/import that JSON and preview what will change.
- Applying the preview records false positives, accepted risks, fixed cases, and verified-real cases correctly.
- The dashboard no longer shows false-positive/docs-example critical cases as open critical work.
- Unclear cases remain open.
- Every applied AI resolution has reason, evidence, confidence, repo, scan id, and audit history.
- The existing read-only MCP remains read-only unless an explicit write mode is added.
