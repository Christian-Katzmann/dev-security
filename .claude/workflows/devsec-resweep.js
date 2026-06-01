export const meta = {
  name: 'devsec-resweep',
  description: 'Post-campaign health re-sweep: re-audit all 17 DevSec health lenses against current code, graded vs the Excellence Brief, with per-S-ID landing verification.',
  phases: [
    { title: 'Re-audit', detail: '17 lens agents, fresh context, verify current code not receipts' },
  ],
}

// ---------------------------------------------------------------------------
// Orchestrator-verified ground truth (gathered centrally before fan-out so no
// agent re-runs heavy/conflicting commands). Agents treat these as established
// facts and focus on code-level verification of their own lens.
// ---------------------------------------------------------------------------
const GROUND_TRUTH = `
ORCHESTRATOR-VERIFIED GROUND TRUTH (current working tree, $(HEAD a323bc4) + uncommitted Stage D edits):
- Working tree has UNCOMMITTED Stage D edits: dashboard-ui/src/{App.tsx,Dialog.tsx,index.css}, src/security_observatory/dashboard/index.html, AGENTS.md, and new dashboard-ui/src/AddRepoDialog.a11y.test.tsx. So fixes for S-029 (code-split) and S-041 (AddRepoDialog focus-trap) are PRESENT ON DISK but NOT yet committed. Treat on-disk state as "current code", and note the uncommitted status where it matters.
- uv run pytest -q  => 535 passed (63s).
- cd dashboard-ui && npm run lint (tsc --noEmit) => clean (TypeScript strict mode holds, S-021).
- cd dashboard-ui && npm run build => clean, NO >500kB chunk-size warning. Main chunk index-*.js = 438.06 kB (gzip 126.79). Code-split on-demand chunks: FixProposalsView 134.6kB, AgentLabView 23.19kB, CatalogToolPage 10.99kB, useCatalogData 10.67kB, CatalogBrowse 4.42kB, CatalogPackPage 3.96kB, CatalogHome 3.48kB. Self-hosted fonts in assets: Geist-Variable 69.74kB, GeistMono-Variable 71.25kB. CSS index-*.css 164.8kB.
- cd dashboard-ui && npx vitest run => 28 passed across 7 files: focusRing(4), SkipToContent(2), Dialog(7), ScanHistoryTrendsPanel(5), RotationTriggerFlow.a11y(3), AddRepoDialog.a11y(6), App.perf(1).
- NON-NEGOTIABLE #1 (no third-party call on default dashboard render path): orchestrator-verified PASS. Built index.html + assets have zero external URLs; no googleapis/gstatic anywhere; Geist self-hosted woff2; source index.css uses local @font-face + tailwind import only.
- NON-NEGOTIABLE #2 (forged cross-origin POST cannot suppress a high/critical case): orchestrator-verified PASS. dashboard_server._guard_mutation() returns 403 for cross-origin (Origin host must be loopback + matching port; Sec-Fetch-Site must be same-origin/none); human_authorized on the dashboard path == _human_confirmation_present(), which requires the X-DevSec-Confirm header echoing a per-process token minted only on a same-origin GET /api/csrf-token (secrets.compare_digest). Defense in depth: storage.record_case_decision reads severity from the RECORDED case (never caller text) and raises HumanConfirmationRequired for high/critical suppression when human_authorized is False. test_dashboard_csrf.py exists.

DO NOT re-run: full pytest, npm build, npm lint, vitest, or any dashboard/scanner/server process. Quick targeted greps and single-test reads are fine. Verify your lens against CURRENT CODE, not against the implementation receipts.
`

const GRADING = `
HEALTH LABELS (5-point, same scale as the baseline synthesis): Green > Green/Yellow > Yellow > Yellow/Red > Red.
Grade against the EXCELLENCE BRIEF's bar ("a tool a skeptical security engineer would prefer"), NOT the generic "no obvious problems" floor. Do not grade on a curve. If a finding is only partially addressed, the lens is not Green. Green/Yellow means a residual is real but explicitly minor/accepted. Be specific and evidence-bound: cite file:line. Distinguish confirmed facts from inference. If the receipts claim something landed but the code does not show it, say so plainly (claimed-done-but-isn't).
`

// Each lens: key, label, baseline report, optional final report, BEFORE label,
// and the S-IDs for which THIS lens is the primary landing-verifier.
// All 54 S-IDs are assigned to exactly one primary lens across the 17.
const LENSES = [
  {
    key: 'feature', label: 'feature-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/01-feature-health.initial.md',
    finalReport: 'reports/codebase-health/devsec-industry-grade/feature-health-final.md',
    sids: [
      'S-042 — Render posture-over-time trend (or remove dead helper). val: trend sparkline renders on Overview; ScanHistoryTrendsPanel.',
      'S-043 — Dashboard surface for the hands-off code-fix flow (fix-proposals). val: /api/fix-proposals + FixProposalsView.',
    ],
    extra: 'feature-health-final.md is PRIOR ART — re-verify against code, do not trust it. Also note (do not grade) whether the feature-discovery short-list was captured.',
  },
  {
    key: 'architecture', label: 'architecture-health', before: 'Yellow/Red',
    report: 'reports/codebase-health/devsec-industry-grade/02-architecture-health.initial.md',
    sids: [
      'S-015 — Extract scan_orchestrator from cli.py (break cli<->dashboard cycle). val: scan_orchestrator module exists; import cycle gone.',
      'S-016 — Split dashboard_server.py (route table + extract inline HTML pages). val: route tables _GET_ROUTES etc.; note dashboard_server.py is still ~156kB.',
      'S-017 — Lift payload assembly out of storage.py (remove persistence->scanner inversion). val: assemble_summary_payload in dashboard_server, not storage.',
      'S-018 — Scanner adapter registry (one entry per scanner). val: registry structure in scanners.py.',
    ],
    extra: 'Judge whether a new scanner / finding category / lifecycle state can be added without cross-layer surgery. dashboard_server.py is still very large — assess whether the split is real or cosmetic.',
  },
  {
    key: 'domain-language', label: 'domain-language-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/03-domain-language-health.initial.md',
    sids: [
      'S-019 — Unify severity vocabulary across surfaces (one severity->display map). val: grep Elevated/Warning resolves to one map.',
      'S-020 — Canonical case-lifecycle module + reconcile divergent enums. val: lifecycle.py LIFECYCLE_STATES; one mapping table.',
      'S-032 — Domain-language drift polish incl. unknown->medium confident-falsehood (preserve unknown confidence). val: model.py keeps unknown.',
    ],
    extra: 'Check raw-finding vs case, severity vs confidence, "clear within scan scope" vs "secure", lifecycle states used consistently across CLI, dashboard, MCP, docs.',
  },
  {
    key: 'permission-boundary', label: 'permission-boundary-health', before: 'Yellow/Red',
    report: 'reports/codebase-health/devsec-industry-grade/04-permission-boundary-health.initial.md',
    sids: [
      'S-001 — Dashboard CSRF/Origin harden + re-arm suppression gate (human_authorized not hardcoded). val: test_dashboard_csrf.py; forged cross-origin POST 403, cannot suppress critical.',
      'S-009 — Harden MCP path-leak invariant (startswith->substring) + redaction coverage. val: test_mcp_server.py.',
    ],
    extra: 'This lens owns NON-NEGOTIABLE #2 (orchestrator marked PASS — independently re-verify the guard + storage gate code and say whether you agree). Confirm MCP write mode stays stdio-only, no auto-suppress of high/critical, audited path; dashboard exposes nothing it should not.',
  },
  {
    key: 'privacy-boundary', label: 'privacy-boundary-health', before: 'Yellow/Red',
    report: 'reports/codebase-health/devsec-industry-grade/05-privacy-boundary-health.initial.md',
    sids: [
      'S-002 — Eliminate Google Fonts default-path egress (self-host Geist). val: grep googleapis in dashboard/assets empty; build.',
      'S-007 — Make --trust egress disclosure exhaustive & visible (UI + trust-boundary diagram lists all egress surfaces). val: diagram lists all 4 egress surfaces; opt-in copy names them.',
    ],
    extra: 'This lens owns NON-NEGOTIABLE #1 (orchestrator marked PASS — independently re-verify). Trace EVERY network-capable call. Prove no source/findings/telemetry leave on a default path; confirm legitify/Scorecard/Honey Key callbacks are opt-in AND visibly so in the UI.',
  },
  {
    key: 'data-contract-type', label: 'data-contract-type-health', before: 'Yellow/Red',
    report: 'reports/codebase-health/devsec-industry-grade/06-data-contract-type-health.initial.md',
    sids: [
      'S-021 — Enable TypeScript strict mode. val: tsc --noEmit green under strict (orchestrator: clean).',
      'S-022 — Tighten case-write contracts (trim FE type; typed save_scan). val: model/storage typing.',
      'S-023 — Guard cases_json JSON reads against corrupt rows. val: dashboard_payload survives non-JSON row.',
      'S-026 — Versioned migrations via PRAGMA user_version. val: migration round-trip; user_version in storage.py.',
    ],
    extra: 'Are the normalized raw-finding shape, case schema, lifecycle transitions, and MCP case_resolutions.v1 contract typed, validated, and versioned so malformed scanner output cannot corrupt history?',
  },
  {
    key: 'integration', label: 'integration-health', before: 'Green/Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/07-integration-health.initial.md',
    sids: [
      'S-008 — Resolve CISA KEV/EPSS wiring gap (wire-or-document). val: test_enrichment.py; grep callers.',
      'S-011 — Lock setup-probe shell=True invariant + record no-retry decision. val: test_setup_runner.py.',
      'S-013 — Reset-cache cleanup + reset full-cleanup test. val: reset removes report dir, tables 0 rows.',
      'S-014 — Prune terminal _JOBS entries after a TTL. val: rotation/check-status branches.',
    ],
    extra: 'Each scanner adapter: does it degrade honestly and legibly when the tool is missing or errors, rather than silently producing zero findings — and does the UI say so?',
  },
  {
    key: 'error-edge-state', label: 'error-edge-state-health', before: 'Yellow/Red',
    report: 'reports/codebase-health/devsec-industry-grade/08-error-edge-state-health.initial.md',
    sids: [
      'S-003 — Self-healing SQLite (quarantine + rebuild on corrupt store). val: test_storage_corruption.py.',
      'S-004 — Surface case-decision failures on the Findings tab. val: inline error on failed Verify.',
      'S-005 — React error boundary + fetch-retry + /api/summary shape guard. val: ErrorBoundary component; Retry on reconnect.',
      'S-006 — Wrap do_GET routes in top-level error handling. val: do_GET try/except JSON 500.',
    ],
    extra: 'Partial scans, crashed scanner, empty/huge repo, corrupt SQLite, first-ever run, zero-findings clean repo — is every state crafted and safe, never a raw stack trace or a degraded scan shown as complete?',
  },
  {
    key: 'test-confidence', label: 'test-confidence-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/09-test-confidence-health.initial.md',
    sids: [
      'S-024 — Normalization count-conservation / dropped-findings test. val: test_normalize.py / test_cases.py.',
      'S-025 — Repo-wide no-egress sentinel + redact_text tests + non-skippable mcp test. val: test_no_egress.py, test_model.py (no longer a stub).',
    ],
    extra: 'Are trust-critical paths (normalization fidelity, no-egress, case-building, MCP write guards, Honey Key hashing, lifecycle transitions) covered by tests that FAIL if the guarantee breaks? Inspect the test files; check test_model.py is no longer a stub.',
  },
  {
    key: 'product-workflow', label: 'product-workflow-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/10-product-workflow-health.initial.md',
    sids: [
      'S-035 — In-progress/verifying lifecycle state + proof-bound closure (resolved_by_scan_id). val: act->rescan->case shows resolved bound to scan id.',
      'S-038 — Differentiate scan-failure feedback into crafted error states. val: missing-scanner -> actionable error.',
      'S-039 — Surface scan-history + arbitrary scan-diff in the UI. val: history panel + base/head diff request.',
    ],
    extra: 'Walk scan->triage->act->rescan-to-closure as a first-time user (by code-reading). Map every dead end, every CLI/JSON escape hatch, every missing lifecycle step. Note (do not grade) any workflow-level features still obviously missing.',
  },
  {
    key: 'behavioral-ux', label: 'behavioral-ux-health', before: 'Yellow/Red',
    report: 'reports/codebase-health/devsec-industry-grade/11-behavioral-ux-health.initial.md',
    finalReport: 'reports/codebase-health/devsec-industry-grade/11-behavioral-ux-health.final.md',
    sids: [
      'S-033 — Replace first-run window.prompt repo-add with crafted Mistglass form (AddRepoDialog). val: no window.prompt in repo-add path.',
      'S-034 — Replace window.prompt note/close dialogs with inline inputs. val: no native dialog for note/close.',
      'S-036 — Delete orphaned off-Mistglass parallel case UI. val: deleted files no longer imported.',
      'S-037 — Make Cmd+K real (focus search/palette) or remove the false hint. val: Cmd+K acts, or hint gone.',
      'S-044 — Wire or retire dead Activity filter chips. val: chips filter, or rendered as static labels.',
    ],
    extra: 'HEADLINE lens. 11-behavioral-ux-health.final.md is PRIOR ART — re-verify against code. Does triage reduce noise to confident action without alarm-fatigue or false calm? Speed, keyboard-first, scannable severity, progressive disclosure, no raw window.prompt, no dead-end "Coming Soon" reached from a working-looking action. grep for window.prompt/window.confirm across dashboard-ui/src.',
  },
  {
    key: 'design-system-accessibility', label: 'design-system-accessibility-health', before: 'Yellow/Red',
    report: 'reports/codebase-health/devsec-industry-grade/12-design-system-accessibility-health.initial.md',
    sids: [
      'S-040 — Global visible :focus-visible indicator on all controls. val: focusRing test; tab through views.',
      'S-041 — Shared Dialog primitive: focus-trap + Escape + focus restore (4 modals incl AddRepoDialog). val: Dialog.test.tsx + AddRepoDialog.a11y.test.tsx. NOTE: AddRepoDialog migration is UNCOMMITTED on disk.',
      'S-045 — Skip-to-content link past the sidebar. val: SkipToContent component/test.',
      'S-047 — a11y test harness (vitest + jest-axe smoke). val: vitest a11y suites (orchestrator: 28 passed).',
      'S-054 — Sweep token-inlining drift (hardcoded hex/rgba -> tokens). val: grep raw hex/rgba in index.css.',
    ],
    extra: 'Is Mistglass applied consistently and accessibly (contrast, focus order, keyboard, screen-reader, severity NEVER signaled by color alone)? Confirm all 4 modals use the shared Dialog. Spot-check S-054 by grepping for remaining hardcoded hex/rgba in index.css and judging whether drift is meaningfully swept or just sampled.',
  },
  {
    key: 'performance', label: 'performance-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/13-performance-health.initial.md',
    sids: [
      'S-027 — Batch dashboard_payload into set-based queries (kill N+1). val: set-based queries; O(1) in repo count.',
      'S-028 — Memoize App.tsx derived state. val: App.perf.test.tsx (orchestrator: passing); useMemo on derived passes.',
      'S-029 — Trim oversized assets + code-splitting. val: build no chunk warning (orchestrator: 438kB, split). NOTE: code-split is UNCOMMITTED on disk.',
    ],
    extra: 'Confirm dashboard_payload is genuinely set-based (read the SQL — look for per-repo loops issuing queries). Real-repo scan + dashboard snappy on a large history store: no O(n^2) case-building, no UI lock on big finding sets, fast trends/diff queries.',
  },
  {
    key: 'ai-product', label: 'ai-product-health', before: 'Green/Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/14-ai-product-health.initial.md',
    sids: [
      'S-012 — Close prompt-injection sliver + drop ignored safe_to_apply field. val: test_severity_gate.py, test_case_followup.py.',
    ],
    extra: 'Are agent handoff prompts and MCP outputs accurate, evidence-bound, resistant to prompt-injection from finding text, never overconfident, genuinely time-saving? Note (do not grade) AI-native capability candidates captured.',
  },
  {
    key: 'documentation', label: 'documentation-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/15-documentation-health.initial.md',
    sids: [
      'S-010 — Correct mcp/README write-surface tool count (3 -> 7-8). val: mcp/README tool list vs mcp_server.py registrations.',
      'S-048 — Fix AGENTS.md MCP write-mode understatement. val: AGENTS.md matches pyproject entry points + mcp/README.',
      'S-049 — Refresh stale .adx pytest-blocked verification caveat. val: note rewritten; pytest runs.',
      'S-050 — Canonical-vs-working-notes doc boundary in AGENTS.md. val: AGENTS.md demotes campaign/automation/scratch docs.',
      'S-051 — Document security-sensitive CLI verbs/flags. val: prose covers verbs/flags or notes code-only.',
      'S-052 — Line-match destructive-surface doc claims to guards. val: each Honey Key claim has a guard assertion.',
    ],
    extra: 'Do README, PROVOCATION, AGENTS.md, mcp/README, and the trust-boundary diagram match BUILT behavior with zero drift between promise and code? NOTE: AGENTS.md has UNCOMMITTED Stage D edits (route/tab memory) on disk.',
  },
  {
    key: 'ai-maintainability', label: 'ai-maintainability-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/16-ai-maintainability-health.initial.md',
    sids: [
      'S-030 — Refresh .adx module map for the MCP write subsystem. val: json.load(.adx/modules/index.json); ls each key_file.',
      'S-031 — Make .adx safety/recovery/verification tell the truth (pytest runs). val: .adx/risks.json; bump last_verified.',
    ],
    extra: 'Can a fresh agent extend DevSec safely via the .adx manifests, command registry, risk register, recovery notes — and are those STILL ACCURATE after the campaign changes? Open the .adx/*.json files and check key_file paths still exist and reflect the split modules.',
  },
  {
    key: 'release-readiness', label: 'release-readiness-health', before: 'Yellow',
    report: 'reports/codebase-health/devsec-industry-grade/17-release-readiness-health.initial.md',
    sids: [
      'S-046 — CHANGELOG/version discipline ([Unreleased] + reconcile commits since v0.1.0). val: git log v0.1.0..HEAD; changelog + version + tag agree.',
      'S-053 — Keep "real vs not yet" honest after the work lands. val: re-read table vs shipped behavior.',
    ],
    extra: 'Is version honesty real and reproducible from a clean machine: version, changelog, install paths (managed vs Homebrew vs uv), and a "real vs not yet" table that is true AFTER the polish/feature work landed? Check CHANGELOG.md for an [Unreleased] section.',
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
    matches_brief: { type: 'boolean', description: 'true only if this lens meets the Excellence Brief bar (effectively Green)' },
    sids: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'status', 'evidence'],
        properties: {
          id: { type: 'string' },
          status: { type: 'string', enum: ['landed', 'partial', 'regressed', 'not_done'] },
          evidence: { type: 'string', description: 'file:line or concrete code evidence; cite what you actually saw' },
        },
      },
    },
    residuals: { type: 'array', items: { type: 'string' }, description: 'remaining soft/partial issues, each one line' },
    new_issues: { type: 'array', items: { type: 'string' }, description: 'NEW problems the campaign introduced (regressions), each one line; [] if none' },
    summary: { type: 'string', description: '2-4 sentences: what genuinely improved, what is still soft, honest verdict vs the Brief' },
  },
}

phase('Re-audit')

const results = await parallel(LENSES.map((lens) => () => {
  const sidBlock = lens.sids.map((s) => '  - ' + s).join('\n')
  const finalLine = lens.finalReport
    ? `\nPRIOR re-audit (treat as prior art, RE-VERIFY against code, do not trust): ${lens.finalReport}`
    : ''
  const prompt = `You are re-auditing ONE codebase-health lens for the DevSec (Security Observatory) repo after a 3-stage hardening campaign. Repo cwd is the working dir. Verify against CURRENT CODE, not the implementation receipts.

LENS: ${lens.label}
BASELINE forensic report (the BEFORE state, read it first): ${lens.report}${finalLine}
BEFORE health label (from baseline synthesis): ${lens.before}

Read the EXCELLENCE BRIEF (the grading rubric): reports/codebase-health/devsec-industry-grade/excellence-brief.md
${GRADING}
${GROUND_TRUTH}

S-IDs THIS lens must verify landed (give a status for EACH, with concrete code evidence — file:line):
${sidBlock}

Lens-specific focus:
${lens.extra}

METHOD:
1. Read the baseline report to load the BEFORE findings for this lens.
2. Read the Excellence Brief's bar for this lens (the "Domain risk cues per lens" table row + non-negotiables).
3. Verify the CURRENT code: open the actual source/test/doc files, grep for the patterns, confirm each S-ID's fix is really present (not just claimed). Cite file:line.
4. Look for NEW issues the campaign introduced in this lens's domain (regressions, half-migrations, dead code left behind, contradictions).
5. Assign an AFTER label on the 5-point scale, graded against the Brief, not a curve.

Be honest and specific. If something is still Yellow, say Yellow. Return the structured object.`
  return agent(prompt, { label: `lens:${lens.key}`, phase: 'Re-audit', schema: SCHEMA })
}))

return { lenses: results.filter(Boolean) }
