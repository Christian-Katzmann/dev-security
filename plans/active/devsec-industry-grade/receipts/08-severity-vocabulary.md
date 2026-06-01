# Implementation Receipt: 08-severity-vocabulary

## Target

- Plan: `plans/active/devsec-industry-grade/`
- Batch: 08-severity-vocabulary
- Source report item(s): S-019 (unify severity vocabulary), S-032 (domain-language drift polish incl. `unknown`→`medium` confident falsehood)

## Before Health

- **S-019** — Severity display words re-implemented in several places: `severityMeta` held literal `'WARNING'`/`'ELEVATED'` labels (`App.tsx:384-391`), `severityCounts`/`caseSeverityCounts` mapped `high→elevated`/`medium→warning` as bucket keys (`App.tsx:678-685, 735-746`), and the MetricBlock strip (`App.tsx:2644-2646`) and RiskLandscape legend (`App.tsx:3841-3844`) hard-coded title-case `'Elevated'`/`'Warning'`. No single source; `docs/vocabulary.md` had no explicit agent-vs-UI contract.
- **S-032** — `model.py:164` coerced any non-`{high,medium,low}` case confidence (including `unknown`, empty, garbage) to `"medium"` → a case could read more certain than its evidence. `normalizeBucket` (`dashboardData.ts:1645-1651`) did a blanket `[_\s]+ → -` regex rewrite. Internal `findings` route id / `TabId` / inline `FindingsView` plus an orphaned `components/FindingsView.tsx` carried stale vocabulary. `glossary.md:56` invented a single install-state axis (`detected-locally`/`managed-install`/`display-only`) that didn't match `tool-catalog.md`'s two real axes. `PostureTier` had a `'watch'` member colliding with the action-level `watch` bucket.

## Changes Made

**S-019 — one severity→display map**
- Added `severityDisplay: Record<Tone, string>` (`App.tsx`) as the single source of truth (`crit→Critical, high→Elevated, warn→Warning, low→Low, info→Info, neutral→Ready`).
- `severityMeta` labels now derive from it via `.toUpperCase()` — byte-identical uppercase chips/badges, no duplicated literal.
- MetricBlock strip and RiskLandscape legend now read `severityDisplay.{crit,high,warn,low}` instead of hard-coded strings. Title-case `Elevated`/`Warning` literals now exist only in the one map.
- `docs/vocabulary.md` — added a "One map, one translation point" subsection: **internal severities (`critical/high/medium/low/info`) are the canonical contract that the MCP/CLI agent persona speaks; the dashboard `severityDisplay` map is the only translation point.** This matches `mcp_server.py:83` (agent leads with `Severity: <critical|high|medium|low|info>`), which was left as-is per the documented decision.

**S-032 — confident falsehood + naming polish**
- `model.py:163-165` (committed separately, `82e1681`): allow `"unknown"`; unclassifiable confidence now falls back to `"unknown"` (honest), never `"medium"`. Pinned by 5 new unit tests in `tests/test_model.py`.
- `normalizeBucket` (`dashboardData.ts`): replaced the blanket `[_\s]+ → -` regex with a single explicit, documented `fix_now → fix-now` boundary alias. Python layer is uniformly `fix_now`; TS layer uniformly `fix-now`.
- `findings → cases` internal rename: `TabId` member, nav item id, `tabTitles`/`viewsByMode`/`navCounts` keys, `setActiveTab`/`onOpenTab('cases')` calls, the `tab === 'cases'` guard, and the inline `FindingsView → CasesView` component. **`App.tsx:942 REQUIRED_SUMMARY_ARRAYS` keeps `'findings'`** — that is the backend data-field name (raw findings), preserved per `vocabulary.md` Compatibility, not a route id. `activeTab` is in-memory React state (no URL/hash deep-links), so no redirect needed.
- Renamed orphaned `components/FindingsView.tsx → components/CasesView.tsx` (`git mv`, component + props type) so no stale `FindingsView` identifier remains in `dashboard-ui/src/`. The file is still orphaned (imported by nothing) — left for batch 09 (S-036) to delete; not deleted here to avoid broadening scope.
- `glossary.md:54-56`: rewrote the Tool Catalog install-state line to mirror `tool-catalog.md`'s two real axes — `lifecycle` (`available/beta/advanced/coming-soon/deprecated/hidden`) and `install_state` (`built-in/managed/detected/missing/unavailable/not-configured/coming-soon`). Invented states removed.
- `PostureTier` `'watch' → 'monitor'` (type + return + label "Watch"→"Monitor") so the posture band no longer collides with the action-level `watch` bucket. The `.tier` value was previously unused (only `.label`/`.tone` are read), so the rename is type-hygiene with no consumer impact.

**Downstream adjustment (batches 09, 12)**
- Batch 09 (S-036) and batch 12 (S-039) referenced `FindingsView`; renamed those refs to `CasesView` and added a "(added by batch 08)" note to 09's context so its "delete the orphaned trio" step targets `components/CasesView.tsx`. No target S-IDs changed.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `cd dashboard-ui && npm run build` | PASS | vite build clean, 1692 modules, built in ~1.4s |
| `cd dashboard-ui && npm run lint` | PASS | `tsc --noEmit` clean — rename + map + PostureTier type-check |
| `cd dashboard-ui && npm test` | PASS | 16/16 vitest (no test referenced renamed symbols) |
| `grep -rn "Elevated\|Warning" dashboard-ui/src/` | PASS | Only severity-display hits resolve to the one `severityDisplay` map (line 387 comment + 391-392); other `Warning` hits are unrelated rotation-consistency identifiers |
| `grep -rn "fix-now\|fix_now\|FindingsView\|'findings'\|detected-locally\|managed-install\|display-only" dashboard-ui/src/ src/ docs/` | PASS | Remaining hits all legitimate: `fix-now` (TS layer), `fix_now` (Python layer + one documented boundary alias), `'findings'` (backend data field, line 942), `managed-install`/`display-only` (separate catalog-preview / card-action concepts, not the install-state axis). `detected-locally` gone. `FindingsView` gone from `dashboard-ui/src/` (one historical mention remains in `docs/ai-case-follow-up-workflow-plan.md` — out of rename scope) |
| `grep -rn "detected-locally\|managed-install\|display-only" docs/glossary.md` | PASS | Empty — invented install states removed |
| `uv run pytest` | PASS | 498 passed (incl. 5 new confidence-honesty tests) |
| `python3 -c "...import security_observatory.cli..."` | PASS | import ok |

## After Health

- **S-019 → Green** — Exactly one `severity→display` map; `severityMeta` + every display site consume it; agent-vs-UI contract documented and true in code. No duplicate inline string-to-display logic.
- **S-032 → Green** — `unknown` confidence preserved and rendered honestly (a case never reads more certain than its evidence; pinned by tests); action level has one encoding per layer + one explicit boundary alias; `findings→cases` internal rename complete with user-facing "Cases" intact; glossary mirrors the canonical two axes; PostureTier `watch` collision removed.

## Remaining Risk

- The orphaned `components/CasesView.tsx` (ex-`FindingsView.tsx`) is still present-but-unused — intentionally left for batch 09 (S-036) to delete. Batch 09 context/acceptance updated to point at the new name.
- `docs/ai-case-follow-up-workflow-plan.md:132` still lists `FindingsView` as a historical planning reference — outside the `dashboard-ui/src/` rename scope; left untouched to avoid rewriting historical plan docs.
- Severity *ordering*, suppression/priority gates, and the high/critical auto-suppression behavior were not touched. `unknown` and `medium` confidence behave identically in `priority.py` (`!= "low"`), so no gate/priority change.

## Next Batch

09-finish-dead-ui-surfaces (S-036/S-037/S-038/S-044) — note its S-036 now deletes `components/CasesView.tsx`.
