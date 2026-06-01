# Acceptance: 08-severity-vocabulary

## Acceptance Criteria

### S-019 — Unified severity vocabulary
- [ ] Exactly one shared `severity→display` map exists (a single TS module/constant defining `high→Elevated`, `medium→Warning`, etc.); the previously separate UI call sites (`App.tsx:382-385` `severityMeta` and `App.tsx:677-682` `severityCounts`) both consume it — no second hand-rolled `high→elevated`/`medium→warning` mapping remains. A `grep -rn "Elevated\|Warning" dashboard-ui/src/` resolves every display occurrence to that one map (no duplicate inline string-to-display logic).
- [ ] The MCP/CLI agent persona severity language is reconciled with the UI by an explicit, documented decision in `docs/vocabulary.md`: either the agent emits the same display words, or the doc states that internal severities (`critical/high/medium/low/info`) are the agent contract and the UI display map is the only translation point. The chosen rule is true in code (`mcp_server.py:83` matches the documented decision). A user reading one case in the dashboard and via the handoff is never asked to translate the same severity twice.
- [ ] `cd dashboard-ui && npm run build` is clean after the map is centralized.

### S-032 — Domain-language drift polish (incl. the `unknown`→`medium` confident falsehood)
- [ ] **Confident falsehood eliminated:** an `unknown` case confidence is no longer silently coerced to `medium` at `model.py:164`. Either `unknown` is preserved through the case boundary and rendered honestly, or the coercion is deliberately retained *and* documented with a rationale; either way a unit test asserts the chosen behavior (a case built from an `unknown`-confidence finding does not read as a more-certain `medium` unless that drop is documented and the test pins it as intentional). A case never reads more certain than its evidence.
- [ ] Action level has one name and one encoding: the `fix_now`/`fix-now` split is gone (the `normalizeBucket` `_`→`-` shim at `dashboardData.ts:1645-1651` is deleted or reduced to a single explicit documented alias), and `grep -rn "fix-now\|fix_now" dashboard-ui/src/ src/` shows one consistent encoding per layer with no hidden rewrite.
- [ ] The internal `findings` surface is renamed to `cases` (route id, `TabId` member, `FindingsView` component) with user-facing copy still reading "Cases"; `grep -rn "FindingsView\|'findings'" dashboard-ui/src/` returns no stale route/component identifiers (or only an intentional deep-link redirect). `npm run lint` and `npm run build` pass.
- [ ] `glossary.md`'s Tool Catalog section mirrors `tool-catalog.md`'s two axes — `lifecycle` (`available/beta/advanced/coming-soon/deprecated/hidden`) and `install_state` (`built-in/managed/detected/missing/unavailable/not-configured/coming-soon`) — with the real value names; the invented states are gone (`grep -rn "detected-locally\|managed-install\|display-only" docs/glossary.md` returns nothing for the install-state axis).
- [ ] The PostureTier `watch` band is qualified so it does not collide with the action-level `watch` on the same view (`App.tsx:275,513-517`); compounded IOC `*-watch` names are left as-is.
- [ ] `cd dashboard-ui && npm run build && npm run lint` is clean; `uv run pytest` passes (covering the new/changed confidence behavior).

## Required Checks
| Check | Why |
| --- | --- |
| `cd dashboard-ui && npm run build` | Proves the centralized severity→display map (S-019) and the `findings`→`cases` rename (S-032) compile and render; matrix validation path for both rows. |
| `cd dashboard-ui && npm run lint` | `tsc --noEmit` confirms the renamed `TabId`/route/component and the consolidated action-level encoding type-check with no dangling references (S-032). |
| `grep -rn "Elevated\|Warning" dashboard-ui/src/` | Confirms severity display words resolve to one shared map, not three inline re-implementations (S-019 — synthesis "Suggested validation"). |
| `grep -rn "fix-now\|fix_now\|FindingsView\|'findings'\|detected-locally\|managed-install\|display-only" dashboard-ui/src/ src/ docs/` | Confirms the action-level encoding, the `findings`→`cases` rename, and the glossary install-state cleanup leave no stale/fictional vocabulary (S-032 — synthesis "Suggested validation"). |
| `uv run pytest` | Runs the unit test pinning case-confidence honesty (the `unknown`→`medium` confident-falsehood fix) and confirms no Python regression (S-032). |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check that the `model.py` confidence change and any persona/doc-aligned code still load cleanly (AGENTS.md verification rule). |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
