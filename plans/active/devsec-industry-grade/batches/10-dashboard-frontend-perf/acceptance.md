# Acceptance: 10-dashboard-frontend-perf

## Acceptance Criteria

- **S-028 (memoized derived state):** `scopedSummary`, `activeCases`, `posture`, and `buildActivity` in `App.tsx` (currently inline at `App.tsx:947-953` / `:601-659`) are each wrapped in `useMemo` keyed on `[summary, target]` (and `search` only where search is genuinely an input). The component tree is otherwise unchanged — no decomposition.
- **S-028 (typing no longer re-derives):** A React Profiler pass on a large seeded summary shows that typing in the search box (`App.tsx:912`) does not re-run `filterSummaryByTarget`/`activeCaseList`/`buildActivity` — the memoized values are reused while only `summary`/`target` are stable, so per-keystroke derived-state cost is eliminated.
- **S-029 (assets trimmed):** `favicon.png`, `apple-touch-icon.png`, and `logo.png` under `src/security_observatory/dashboard/` are re-exported to KB-scale (down from 2,104,121 B / 2,104,121 B / 606,592 B), visually identical to the user; `ls -la src/security_observatory/dashboard/*.png` confirms the new sizes.
- **S-029 (code-splitting decision made):** The build either gains explicit `React.lazy`/`import()` split boundaries for rarely-first views (Agent Lab, Catalog, Rotation), reflected in the `vite build` chunk report, OR the single-bundle is explicitly accepted and that decision is recorded in the receipt with its rationale (local-only delivery). Either way the decision is no longer implicit, and static-asset cache headers were spot-checked.
- **S-054 (tokens swept):** The high-frequency inline hex/rgba on shared primitives (`#fff`×32, brand-green `#2f6656`×5) are replaced with their existing `:root` tokens, and the raw Tailwind `black/white` opacities in `OverviewView.tsx` (`OverviewView.tsx:45,49,65`) are reconciled toward Mistglass tokens; the inline-value count outside `:root` drops materially from the 60 hex + 212 rgba baseline, with only genuine one-off rgba effects left inline.
- **S-054 (no visual regression, one idiom):** The swept surfaces render identically (same colors), and the styling-idiom drift between named Mistglass classes and raw Tailwind opacities is resolved on the touched primitives — a documented decision on the one idiom going forward.

## Required Checks

| Check | Why |
| --- | --- |
| `cd dashboard-ui && npm run lint` (`tsc --noEmit`) | Proves the `useMemo` changes (S-028), any `React.lazy` boundaries (S-029), and the token sweep (S-054) are type-sound. |
| `cd dashboard-ui && npm run build` (`vite build`) | Proves the production bundle still builds clean (it was clean before — must stay clean) and emits the chunk report used to confirm the S-029 code-splitting decision. |
| `ls -la src/security_observatory/dashboard/favicon.png src/security_observatory/dashboard/apple-touch-icon.png src/security_observatory/dashboard/logo.png` | Proves S-029: the two ~2 MB icons and the 607 KB logo are now KB-scale. |
| React Profiler on a large seeded summary while typing in the search box | Proves S-028: typing no longer re-runs `filterSummaryByTarget`/`buildActivity`; the memoized derived passes are reused. |
| `grep -nE "#fff|#2f6656" dashboard-ui/src/index.css dashboard-ui/src/components/OverviewView.tsx` before vs after | Proves S-054: the high-frequency inline hex on shared primitives is gone (now `var(--…)` tokens), with the count materially reduced. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
