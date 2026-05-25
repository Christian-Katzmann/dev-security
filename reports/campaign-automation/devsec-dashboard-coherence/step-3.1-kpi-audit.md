# Step 3.1 KPI Scope Audit

## Decision

Pre-cases scans are preserved and labeled. The dashboard does not rescan automatically on app open. Repos whose latest scan has active raw findings but no saved cases are treated as "pre-cases" scans: raw evidence stays visible, case KPIs exclude those raw-only scans, and the Overview prompts a fresh scan to build cases.

Confirmed local raw-only scans:

| Repo | Active raw findings | Cases | Handling |
|---|---:|---:|---|
| `besk-ftigelse.dk` | 371 | 0 | Labeled pre-cases; rescan needed for cases |
| `obedai-learning-app` | 53 | 0 | Labeled pre-cases; rescan needed for cases |

## Audit Table

| KPI / surface | Previous risk | New source | Scope label |
|---|---|---|---|
| Overview posture score and 7-day trend | Could look all-repos while viewing one repo | `posture` derived from `filterSummaryByTarget(summary, target)` | `All repos` or selected repo |
| Overview open cases | Raw-only old scans could become fake cases through the fallback path | `activeCaseList(scopedSummary)` only uses case arrays when the API provides them | `All repos` or selected repo |
| Overview raw evidence detail | Old raw findings inflated the detail without explanation | Splits `caseBackedRawFindingCount(scopedSummary)` from `preCaseRawFindingCount(scopedSummary)` | Pre-cases copy in KPI + notice |
| Overview severity distribution | Raw severity totals could be read as case severity | `caseSeverityCounts(activeCaseList(scopedSummary))` | `All repos` or selected repo |
| Honey keys armed | Needed confirmation that it scoped with selected repo | `honeyKeyCounts(scopedSummary)` | `All repos` or selected repo |
| Tool Catalog status | Global catalog could appear repo-scoped | `topScannerItems(globalSummary)` + `toolCatalogItems(globalSummary)` | `Across all repos` |
| Recent activity mini feed | All-repos feed lacked repo context | `buildActivity(scopedSummary, target.mode === 'all-repos')` | `All repos` or selected repo |
| Activity raw findings | Loaded row cap could hide the real raw count | `activeRawFindingCount(scopedSummary)` from repo counts | Pre-cases detail when present |
| Activity event mix | Raw-only scans were blended into normal raw evidence | Separate `Case-backed raw` and `Pre-cases raw` rows | Inherits Activity scope |
| Reports metrics and tables | Needed confirmation that data was scoped | Existing `scopedSummary` flow, plus pre-cases label in repo snapshot rows | `All repos` or selected repo |
| Suppression reasons | Direct aggregate + repo rows could double-count | Prefer repo-scoped reasons when present, direct aggregate only as fallback | Inherits current view scope |

## Verification

- `cd dashboard-ui && npm run lint` passed.
- `cd dashboard-ui && npm run build` passed.
- Local dashboard smoke check at `http://127.0.0.1:8766` showed:
  - Open cases: `6`
  - Detail: `All repos · 6 case-backed raw · 424 pre-cases raw need rescan`
  - Tool Catalog detail: `Across all repos · 16 catalog entries`
  - Pre-cases notice listing `besk-ftigelse.dk, obedai-learning-app`
- Screenshot: `reports/campaign-automation/devsec-dashboard-coherence/visuals/step-3.1-overview.png`
