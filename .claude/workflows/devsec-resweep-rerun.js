export const meta = {
  name: 'devsec-resweep-rerun',
  description: 'Re-run the 8 DevSec health lenses that did not emit structured output in the first pass (product-workflow, behavioral-ux, design-system-a11y, performance, ai-product, documentation, ai-maintainability, release-readiness).',
  phases: [
    { title: 'Re-audit-8', detail: '8 lens agents, concise, MUST end with the structured-output call' },
  ],
}

const GROUND_TRUTH = `
ORCHESTRATOR-VERIFIED GROUND TRUTH (current working tree = HEAD a323bc4 + uncommitted Stage D edits):
- Working tree has UNCOMMITTED Stage D edits: dashboard-ui/src/{App.tsx,Dialog.tsx,index.css}, src/security_observatory/dashboard/index.html, AGENTS.md, and new dashboard-ui/src/AddRepoDialog.a11y.test.tsx. So S-029 (code-split) and S-041 (AddRepoDialog focus-trap) fixes are ON DISK but NOT committed. Treat on-disk state as "current code"; note uncommitted status where relevant.
- uv run pytest -q => 535 passed. tsc --noEmit => clean (strict, S-021 holds). npm run build => clean, NO >500kB chunk warning; main chunk 438.06 kB; code-split chunks present (FixProposalsView 134.6kB, AgentLabView 23.19kB, 4 catalog routes); self-hosted Geist woff2 fonts. npx vitest run => 28 passed / 7 files: focusRing(4), SkipToContent(2), Dialog(7), ScanHistoryTrendsPanel(5), RotationTriggerFlow.a11y(3), AddRepoDialog.a11y(6), App.perf(1).
- NON-NEGOTIABLE #1 (no third-party call on default dashboard render path): orchestrator-verified PASS (no external URLs in built index.html/assets; Geist self-hosted; index.css local @font-face only).
- NON-NEGOTIABLE #2 (forged cross-origin POST cannot suppress high/critical): orchestrator-verified PASS (_guard_mutation 403s cross-origin; human_authorized needs X-DevSec-Confirm token minted same-origin; storage gate reads severity from recorded case and raises HumanConfirmationRequired).
- ORCHESTRATOR SPOT-CHECKS you should corroborate or rebut: (a) window.prompt/window.confirm = ZERO matches in dashboard-ui/src (S-033/034). (b) ⌘K handler real in main.tsx + App.tsx:1039, hint at App.tsx:1947 (S-037). (c) CHANGELOG.md has [Unreleased] at line 8 reconciling work, [0.1.0] at line 93 (S-046). (d) dashboard_server.py is 3751 lines / ~156kB despite the S-016 split (HTML extracted, route table real). (e) index.css still has 327 raw color literals incl. format-duplicates rgba(28,36,34,0.04) vs rgba(28, 36, 34, 0.04) and raw hex #6c1f1f (judge whether S-054 drift sweep is complete or sampled). (f) .adx manifests valid JSON, last_verified 2026-06-01, mcp-write-surface mapped.

DO NOT re-run heavy commands (pytest/build/lint/vitest) or any server/scanner. Quick greps + single-file reads only. Verify against CURRENT CODE, not the receipts.
`

const GRADING = `
HEALTH LABELS (5-point): Green > Green/Yellow > Yellow > Yellow/Red > Red. Grade against the EXCELLENCE BRIEF bar ("a tool a skeptical security engineer would prefer"), NOT a generic floor. No curve. Partial fix => not Green. Cite file:line. Distinguish fact from inference. If a receipt claims something the code does not show, say so (claimed-done-but-isn't).
`

const LENSES = [
  {
    key: 'product-workflow', label: 'product-workflow-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/10-product-workflow-health.initial.md',
    sids: [
      'S-035 — In-progress/verifying lifecycle state + proof-bound closure (resolved_by_scan_id). val: act->rescan->case resolved bound to scan id.',
      'S-038 — Differentiate scan-failure feedback into crafted error states. val: missing-scanner -> actionable error.',
      'S-039 — Surface scan-history + arbitrary scan-diff in the UI. val: history panel + base/head diff request.',
    ],
    extra: 'Walk scan->triage->act->rescan-to-closure by code-reading. Map remaining dead ends / CLI-or-JSON escape hatches / missing lifecycle steps. Note (do not grade) workflow features still obviously missing.',
  },
  {
    key: 'behavioral-ux', label: 'behavioral-ux-health', before: 'Yellow/Red',
    report: 'reports/codebase-health/devsec-industry-grade/11-behavioral-ux-health.initial.md',
    finalReport: 'reports/codebase-health/devsec-industry-grade/11-behavioral-ux-health.final.md',
    sids: [
      'S-033 — Replace first-run window.prompt repo-add with crafted Mistglass form (AddRepoDialog). val: no window.prompt in repo-add path.',
      'S-034 — Replace window.prompt note/close dialogs with inline inputs. val: no native dialog for note/close.',
      'S-036 — Delete orphaned off-Mistglass parallel case UI. val: deleted files no longer imported.',
      'S-037 — Make ⌘K real (focus search/palette) or remove the false hint. val: ⌘K acts, or hint gone.',
      'S-044 — Wire or retire dead Activity filter chips. val: chips filter, or static labels.',
    ],
    extra: 'HEADLINE lens. 11-behavioral-ux-health.final.md is PRIOR ART — re-verify against code. Does triage reduce noise to confident action without alarm-fatigue/false calm? Keyboard-first, scannable severity, progressive disclosure, no raw window.prompt, no dead-end Coming-Soon reached from a working-looking action.',
  },
  {
    key: 'design-system-accessibility', label: 'design-system-accessibility-health', before: 'Yellow/Red',
    report: 'reports/codebase-health/devsec-industry-grade/12-design-system-accessibility-health.initial.md',
    sids: [
      'S-040 — Global visible :focus-visible indicator on all controls. val: focusRing test; tab through views.',
      'S-041 — Shared Dialog primitive: focus-trap + Escape + restore (4 modals incl AddRepoDialog, UNCOMMITTED on disk). val: Dialog.test + AddRepoDialog.a11y.test.',
      'S-045 — Skip-to-content link past the sidebar. val: SkipToContent component/test.',
      'S-047 — a11y test harness (vitest + jest-axe smoke). val: 28 vitest pass.',
      'S-054 — Sweep token-inlining drift (hardcoded hex/rgba -> tokens). val: orchestrator counts 327 raw literals remaining in index.css — JUDGE whether the sweep is complete or merely sampled.',
    ],
    extra: 'Is Mistglass applied consistently+accessibly (contrast, focus order, keyboard, screen-reader, severity NEVER color-only)? Confirm all 4 modals use shared Dialog. Be honest on S-054 given the 327 remaining literals.',
  },
  {
    key: 'performance', label: 'performance-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/13-performance-health.initial.md',
    sids: [
      'S-027 — Batch dashboard_payload into set-based queries (kill N+1). val: read the SQL; O(1) in repo count, no per-repo query loop.',
      'S-028 — Memoize App.tsx derived state. val: App.perf.test passing; useMemo on derived passes.',
      'S-029 — Trim oversized assets + code-splitting (UNCOMMITTED on disk). val: build 438kB, no chunk warning.',
    ],
    extra: 'Confirm dashboard_payload (now assemble_dashboard_payload in dashboard_payload.py) is genuinely set-based — look for per-repo loops issuing queries. Note the per-repo filesystem rotation-state read in dashboard_server (_build_summary_payload) is by-design fresh, not a DB N+1 — judge if it is a perf risk at scale.',
  },
  {
    key: 'ai-product', label: 'ai-product-health', before: 'Green/Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/14-ai-product-health.initial.md',
    sids: [
      'S-012 — Close prompt-injection sliver + drop ignored safe_to_apply field. val: test_severity_gate.py, test_case_followup.py.',
    ],
    extra: 'Are agent handoff prompts + MCP outputs accurate, evidence-bound, injection-resistant (finding text cannot steer), never overconfident, genuinely time-saving? Note (do not grade) AI-native candidates captured.',
  },
  {
    key: 'documentation', label: 'documentation-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/15-documentation-health.initial.md',
    sids: [
      'S-010 — Correct mcp/README write-surface tool count (3 -> 7-8). val: mcp/README list vs mcp_server.py registrations.',
      'S-048 — Fix AGENTS.md MCP write-mode understatement (UNCOMMITTED edits on disk). val: AGENTS.md matches pyproject entry points + mcp/README.',
      'S-049 — Refresh stale .adx pytest-blocked verification caveat. val: note rewritten; pytest runs.',
      'S-050 — Canonical-vs-working-notes doc boundary in AGENTS.md. val: AGENTS.md demotes campaign/scratch docs.',
      'S-051 — Document security-sensitive CLI verbs/flags. val: prose covers verbs/flags or notes code-only.',
      'S-052 — Line-match destructive-surface doc claims to guards. val: each Honey Key claim has a guard assertion.',
    ],
    extra: 'Do README, PROVOCATION, AGENTS.md, mcp/README, trust-boundary diagram match BUILT behavior with zero drift? Flag any promise the code does not keep.',
  },
  {
    key: 'ai-maintainability', label: 'ai-maintainability-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/16-ai-maintainability-health.initial.md',
    sids: [
      'S-030 — Refresh .adx module map for the MCP write subsystem. val: json.load(.adx/modules/index.json); ls each key_file.',
      'S-031 — Make .adx safety/recovery/verification tell the truth (pytest runs). val: .adx/risks.json; bump last_verified.',
    ],
    extra: 'Can a fresh agent extend DevSec safely via .adx manifests/command registry/risk register/recovery notes — STILL ACCURATE after the campaign? Open .adx/*.json and check key_file paths still exist and reflect the split modules (scan_orchestrator.py, dashboard_payload.py, dashboard_pages.py, lifecycle.py, scanners registry).',
  },
  {
    key: 'release-readiness', label: 'release-readiness-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/17-release-readiness-health.initial.md',
    sids: [
      'S-046 — CHANGELOG/version discipline ([Unreleased] + reconcile commits since v0.1.0). val: git log v0.1.0..HEAD; changelog+version+tag agree.',
      'S-053 — Keep "real vs not yet" honest after the work lands. val: re-read table vs shipped behavior.',
    ],
    extra: 'Is version honesty real + reproducible from a clean machine: version, changelog, install paths (managed vs Homebrew vs uv), and a "real vs not yet" table true AFTER the work landed? Check pyproject version vs CHANGELOG [Unreleased]; note that Stage D work is uncommitted so the changelog cannot yet mention it.',
  },
]

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['lens', 'before', 'after', 'verdict', 'matches_brief', 'sids', 'residuals', 'new_issues', 'summary'],
  properties: {
    lens: { type: 'string' },
    before: { type: 'string' },
    after: { type: 'string', enum: ['Green', 'Green/Yellow', 'Yellow', 'Yellow/Red', 'Red'] },
    verdict: { type: 'string', enum: ['improved', 'unchanged', 'regressed'] },
    matches_brief: { type: 'boolean' },
    sids: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'status', 'evidence'],
        properties: {
          id: { type: 'string' },
          status: { type: 'string', enum: ['landed', 'partial', 'regressed', 'not_done'] },
          evidence: { type: 'string', description: 'file:line evidence, <= 55 words' },
        },
      },
    },
    residuals: { type: 'array', items: { type: 'string' } },
    new_issues: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string', description: '2-4 sentences, <= 130 words, honest verdict vs Brief' },
  },
}

phase('Re-audit-8')

const results = await parallel(LENSES.map((lens) => () => {
  const sidBlock = lens.sids.map((s) => '  - ' + s).join('\n')
  const finalLine = lens.finalReport
    ? `\nPRIOR re-audit (prior art, RE-VERIFY against code, do not trust): ${lens.finalReport}`
    : ''
  const prompt = `Re-audit ONE codebase-health lens for the DevSec (Security Observatory) repo after a 3-stage hardening campaign. Verify against CURRENT CODE, not receipts. cwd = repo root.

LENS: ${lens.label}
BASELINE report (the BEFORE state — read first): ${lens.report}${finalLine}
BEFORE label: ${lens.before}
Grading rubric: reports/codebase-health/devsec-industry-grade/excellence-brief.md
${GRADING}
${GROUND_TRUTH}

S-IDs to verify (status for EACH, with file:line evidence):
${sidBlock}

Lens focus: ${lens.extra}

METHOD: read baseline report -> read Brief's row for this lens -> verify current code (open files / grep, confirm each S-ID is really present) -> look for NEW issues the campaign introduced -> assign AFTER label on the 5-point scale, no curve.

CRITICAL OUTPUT CONTRACT: Keep every field concise (evidence <= 55 words; summary <= 130 words). Do work with at most ~12 tool calls, then STOP exploring. Your FINAL action MUST be a single StructuredOutput tool call populating ALL required fields. Do NOT end your turn with a prose report — the structured-output call IS the deliverable. If you have enough to grade, call it now.`
  return agent(prompt, { label: `lens:${lens.key}`, phase: 'Re-audit-8', schema: SCHEMA })
}))

return { lenses: results.filter(Boolean) }
