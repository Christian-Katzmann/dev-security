# Domain Language Health Forensic — DëvSec (Security Observatory)

## Executive Finding

DëvSec's core trust vocabulary is, where it matters most, disciplined: the
raw-finding-vs-case distinction, the "clear within scan scope" (never "secure")
rule, and the MCP `raw_findings`-preferred / `findings`-alias contract are all
honored in code, not just asserted in docs. The product clearly knows that it
exists to keep the user from translating the same security word twice. But that
exact promise leaks at three boundaries. (1) **Severity speaks two languages at
once**: the dashboard renders `Elevated` / `Warning` while the data model, CLI,
and the MCP agent persona render the *same* cases as `high` / `medium` — so a
user reading a case in the UI and then via the agent handoff must translate it
themselves, the precise failure `docs/vocabulary.md` says the lock exists to
prevent. (2) **Case state is named by two different four-value enums** (MCP
`open/verified/accepted_risk/resolved` vs storage `verified/false_positive/
accepted_risk/fixed`) plus a third diff-axis (`new/recurring/resolved`), with
`fixed`↔`resolved` and `false_positive` silently folded together. (3) **The
user-facing catalog vocabulary in `glossary.md` does not match the canonical
`tool-catalog.md` spec or the code** — it collapses the two orthogonal axes
(`lifecycle` vs `install_state`) into one list and invents value names
(`detected-locally`, `managed-install`, `display-only`) the code never uses.
Lower-severity drift compounds this: `action_level` is also called
`attention bucket` and encoded as both `fix_now` and `fix-now`; the React `Cases`
surface is still routed, filed, and componentized under the old name `findings`;
`watch` carries three unrelated meanings; the case API shape is implicit, so the
UI defensively reads ~10 alias field names the backend never emits; and `unknown`
confidence is silently coerced to `medium` at the case boundary. None of this is
a runtime break — bridging code absorbs every mismatch — but it is real
conceptual drift that slows every future developer or agent and, in the severity
and confidence cases, risks mis-presenting trust signals. Worst health:
**Yellow** (no Red — the safety-critical "secure" and `raw_findings` contracts
hold; the drift is in cross-surface naming, not in guardrails).

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security`
- Skill/lens: `domain-language-health-forensic`
- Date: `2026-06-01`
- Requested focus: Per the Excellence Brief domain-risk cue for this lens — are
  `raw finding` vs `case`, `severity` vs `confidence`, "clear within scan scope"
  vs "secure", and the case lifecycle states used consistently across CLI,
  dashboard, MCP, and docs. Graded against the Brief's "Definition of excellent"
  (the user never translates the same security word twice; cases never overstate
  certainty) and its non-negotiable "Confident falsehood" failure mode, not just
  the generic Green floor. External Surface "Coming Soon" treated as out of scope
  per the Brief.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "import security_observatory.{cli,model,decisions,cases,normalize,priority}"` | Pass | Core (non-MCP) modules import clean with `src` on path. |
| `python3 -c "import security_observatory.mcp_server"` | Fail (expected) | `ModuleNotFoundError: No module named 'mcp.server'` — the optional `mcp` FastMCP dependency is absent from this base env. Read-only inspection of `mcp_server.py` used instead. Not a domain-language defect. |
| `grep` enum/vocabulary cross-surface census | Pass | All drift claims below verified against exact file:line evidence in Python, TS/TSX, and docs. |
| `uv run pytest` | Not run | Out of scope for a read-only language audit and not required to verify naming drift; recorded under Limits. |

## Ranked Health Table

| Rank | Area | Health | Confidence | Evidence | Impact (user/developer) | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Severity vocabulary splits per surface** (`Elevated`/`Warning` in UI vs `high`/`medium` in data/CLI/MCP) | Yellow | High | UI display words: `dashboard-ui/src/App.tsx:382-385` (`severityMeta` → `WARNING`/`ELEVATED`) and `App.tsx:677-682` (`severityCounts` maps `high→elevated`, `medium→warning`). Data axis: `src/security_observatory/model.py:12` `SEVERITY_ORDER={"info","low","medium","high","critical"}`. MCP persona: `mcp_server.py:83` instructs "Severity: <critical\|high\|medium\|low\|info>". Doc mapping exists only as prose: `docs/vocabulary.md:10-11`. Zero `Elevated`/`Warning` in any Python/MCP code path. | A user reads "Elevated" in the dashboard but the same case via the agent handoff / MCP / CLI says "high" — the user translates the same severity twice, the exact failure `docs/vocabulary.md` preamble says the lock exists to prevent. The UI→data mapping is re-implemented in 3 places with no shared source of truth. | Single shared severity→display map (one module/constant) consumed by UI, and align the MCP/CLI agent persona to emit the same display words OR explicitly document that internal severities are the agent contract. | `cd dashboard-ui && npm run build`; `grep -rn "Elevated\|Warning"` should resolve to one map. |
| 2 | **Case lifecycle named by two divergent four-value enums** | Yellow | High | MCP query enum: `mcp_server.py:51` `SUPPORTED_CASE_STATUSES=("open","verified","accepted_risk","resolved")`. Storage/decision enum: `decisions.py:10` `CASE_DECISION_STATUSES={"verified","false_positive","accepted_risk","fixed"}`, enforced at `storage.py:231` CHECK constraint. Bridge: `mcp_server.py:224-231` `_case_status_label` folds `false_positive`+`fixed`→`resolved`. Third axis: `change_status` ∈ `new/recurring/resolved` (`storage.py:1362,1403-1405`; `dashboardData.ts:856`). The Brief's `open→in-progress→verifying→closed` lifecycle appears in no enum. | Two four-value status lists overlap on only `verified`/`accepted_risk`. `fixed` (stored) ≠ `resolved` (MCP-shown), and `false_positive` disappears under `resolved`, so an agent querying MCP `status=resolved` cannot tell a fix from a dismissal. "resolved" also means a *diff* outcome (change_status) — same word, two unrelated state machines. | Name one canonical case-state vocabulary; document the presentation collapse (`fixed`/`false_positive`→`resolved`) as an explicit, named mapping; rename the diff axis off the shared word `resolved` or qualify it (`diff_status`). | Read `decisions.py`, `mcp_server.py:224-231`, `dashboardData.ts:855-857`; confirm one documented mapping table. |
| 3 | **`glossary.md` Tool Catalog vocabulary contradicts canonical `tool-catalog.md` and code** | Yellow | High | `glossary.md:56` lists install states `built-in / detected-locally / managed-install / coming-soon / display-only` as one axis. Canonical `tool-catalog.md:113-140` defines TWO axes — `lifecycle` (`available/beta/advanced/coming-soon/deprecated/hidden`) and `install_state` (`built-in/managed/detected/missing/unavailable/not-configured/coming-soon`). Code uses `detected`/`managed`, never `detected-locally`/`managed-install` (`grep detected-locally` = 0 hits repo-wide); `display-only` is a lifecycle/label, not an install state. | The user-facing glossary teaches a *different and partly fictional* catalog vocabulary than the spec and code, conflating product-availability with local-install truth. A developer/agent reading the glossary to extend the catalog is misdirected — the lens's headline "outdated docs that misdirect repair work" concern. | Rewrite `glossary.md` "Tool Catalog" to mirror `tool-catalog.md`'s two-axis model with the real value names; drop invented states. | `grep` the glossary values against `catalog.py` and `tool-catalog.md`; all should match. |
| 4 | **`action_level` aka `attention bucket`, encoded `fix_now` and `fix-now`** | Yellow | High | Canonical: `model.py:163` `action_level ∈ {fix_now,verify,watch,info}` (underscore); 36 `fix_now` hits in Python/docs. UI: `dashboardData.ts:853` `AttentionBucket='fix-now'\|...` (hyphen), 7 `fix-now` hits; concept renamed to `AttentionBucket` (30 hits) vs `action_level` (45 hits). Bridge: `dashboardData.ts:1645-1651` `normalizeBucket` rewrites `_`→`-`. "attention bucket" appears in **no** doc/glossary (`grep` docs = NONE). | One concept, two names and two encodings, with a normalization shim hiding the split. The UI's user-facing name (`attention bucket`) is undocumented, so docs and code teach different words for case urgency. | Pick one name (glossary uses "Action level") and one encoding; document it; delete the rename shim or keep a single explicit alias. | `grep -rn "fix-now\|attention" dashboard-ui/src/`; `npm run build`. |
| 5 | **Cases surface still routed/filed/componentized as `findings`** | Yellow | High | Tab id `findings` with label `Cases`: `App.tsx:308` `{id:'findings',label:'Cases'}`; `App.tsx:171` `TabId='...\|findings\|...'`; `App.tsx:1389` `tab==='findings'`; component `components/FindingsView.tsx` renders `<h2>Cases</h2>` (line 84). 11 `findings`-as-route identifiers in UI. | User-facing copy is correct ("Cases"), but every developer/agent touching routing, the tab enum, or the component sees the *old* concept name for the *new* surface — the "route/file/component names preserving old strategy" drift. Collapses Cases onto the retired `findings` label internally. | Rename the route id, `TabId` member, and `FindingsView` → `CasesView`/`cases`; keep a redirect if any deep link relies on `findings`. | `grep -rn "FindingsView\|'findings'" dashboard-ui/src/`; `npm run build` + `npm run lint`. |
| 6 | **`watch` overloaded across three unrelated meanings** | Green/Yellow | High | (a) action-level urgency: `cases.py:201`, `priority.py:12,62`, `dashboardData.ts:853`. (b) PostureTier score band: `App.tsx:275` `PostureTier='...\|watch\|...'`, `App.tsx:516` `{label:'Watch',tier:'watch'}`. (c) IOC monitoring type: `iocs.py:148` `namespace watch`, `iocs.py:449-460` `domain watch`, `catalog.py:1090` `IOC Watch`. | The bare word `watch` means "case is non-urgent but tracked", "posture score is in the 5.5–7 band", and "an IOC monitoring rule" — two of these (action-level vs PostureTier) co-occur on the same dashboard. Mostly context-disambiguated (IOC always compounded), so lower severity. | Qualify the PostureTier band (`monitor`/`steady-watch`) or the action level so the two on-screen meanings don't collide; leave compounded IOC `*-watch` as-is. | Read `App.tsx:275,513-517` and `dashboardData.ts:853`; confirm no bare-`watch` collision on one view. |
| 7 | **`SecurityCase` API shape implicit; UI reads ~10 alias fields the backend never emits** | Green/Yellow | High | `dashboardData.ts:1115-1142` type declares `id\|case_id`, `repo\|repo_name`, `title\|plain_title`, `summary\|plain_english_risk\|why_matters\|why_it_matters`, `affected_files\|affected_path\|path\|file`, `source_scanners\|scanners\|scanner`, `action_level\|bucket\|action_bucket`. Verified backend emitters: `plain_title`, `why_matters`, `why_it_matters`, `affected_path`, `source_scanners`, `bucket`, `action_bucket` = **0 hits** in `src/security_observatory/*.py`. Canonical shape: `model.py:142-179` `SecurityCase`. | The case contract across the Python↔React boundary is implicit and fuzzy, so the UI defends against many imagined names for one concept. Dead alias reads are harmless at runtime but blur the canonical name of each case field for any future reader. | Type the case API once (shared schema / documented contract), drop dead aliases, keep at most one explicit compatibility alias where a real legacy payload exists. | `grep` each alias against `src/**.py`; `npm run build` after pruning. |
| 8 | **`unknown` confidence silently coerced to `medium` at case boundary** | Green/Yellow | Medium | `glossary.md:34` declares confidence scale `high/medium/low/unknown` (4 values); `unknown` is produced widely upstream (`cases.py:308,503,659,723`; `priority.py:161,188`). But `model.py:164`: `self.confidence = ... if self.confidence in {"high","medium","low"} else "medium"` — `unknown` becomes `medium`. | A case the glossary says could be "unknown" confidence is presented as "medium" — a higher, more certain-sounding value. Touches the Brief's "Confident falsehood" cue: a case should never read more certain than its evidence. Bounded (case-level only; raw findings keep `unknown`), hence Green/Yellow not Yellow/Red. | Either add `unknown` to the case confidence enum and render it honestly, or document that case-level confidence intentionally drops `unknown` and why. | Read `model.py:160-166`; add a unit test asserting case confidence preserves `unknown`, or assert+document the coercion. |
| 9 | **"clear within scan scope" vs "secure" discipline** | Green | High | Rule enforced: `mcp_server.py:95` "Say 'clear within scan scope,' not 'secure.'"; `docs/agent-voice.md:153,216,455,478` repeat it. UI honors it: `ScanCompletenessPanel.tsx:60` "A clean result is useful, but it is not a promise that everything is safe." Only legitimate `secure` uses found (a "secure hash"; an explicit negative claim `dashboardData.ts:2060` "cannot prove... are secure"). | The single most safety-critical language rule in a trust product is consistently held across UI, MCP, and docs. No "you're secure" / "no breach" overstatement on any surface inspected. | None required; protect with a snapshot/copy test if this becomes regression-prone. | `grep -rni "\bsecure\b"` returns only legitimate uses. |
| 10 | **`raw finding` vs `case` core distinction (incl. MCP alias contract)** | Green | High | Glossary defines both (`glossary.md:6-17`); UI keeps them distinct in copy (`FindingsView.tsx:86,249,262` "Active cases... Suppressed raw findings kept separate"; `App.tsx:3264-3265` "Active/Suppressed raw findings"). MCP: `mcp_server.py:804` `raw_findings` (preferred) + `:820` `findings` (documented compatibility alias) + `:833` separate `cases` tool — exactly matching `vocabulary.md:28`'s claim. | The product's central conceptual split (scanner-level evidence vs human-level work) is correctly maintained in user copy and the MCP tool surface. The compatibility-alias plan is implemented as documented. The only residual is the internal route name (Rank 5). | None on the concept itself; fix the internal `findings` route naming under Rank 5. | `grep "def raw_findings\|def findings\|def cases" mcp_server.py` confirms all three. |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| "Attention bucket" as the UI's name for action level | `dashboardData.ts:853,1319` (`AttentionBucket`, `attentionBuckets`); 30 code hits; **0** mentions in `docs/`, `glossary.md`, `README.md`. | A user-facing concept (case urgency grouping) has a code name that no documentation teaches. A fresh agent reading the glossary's "Action level" will not connect it to `AttentionBucket` in the UI. |
| MCP `SUPPORTED_CASE_STATUSES` presentation enum | `mcp_server.py:51` + collapse logic `:224-231`. Not described in `glossary.md`, `mcp/README.md`, or `vocabulary.md` as distinct from the stored decision statuses. | An MCP consumer querying `status=resolved` gets both fixes and false-positives, with no documented note that `resolved` is a *display* fold of two distinct stored states. Hidden semantic collapse on the agent-facing boundary. |
| Glossary install-state list that the code does not implement | `glossary.md:56` names `detected-locally` / `managed-install` / `display-only`; repo-wide `grep` finds `detected-locally`=0, and code uses `detected`/`managed` and treats `display-only` as a label, not a state. | The published glossary documents a catalog vocabulary that does not exist in the catalog engine — a documented surface with no code behind those exact names. |
| Dead case-field aliases on the API boundary | `dashboardData.ts:1115-1142` `plain_title`, `why_matters`, `why_it_matters`, `affected_path`, `source_scanners`, `bucket`, `action_bucket` — all 0 backend emitters. | These read as a real, multi-named contract but are speculative. They imply concept names the backend never uses, obscuring the canonical case shape for future readers. |

## Top Repair Targets

1. **Unify the severity vocabulary across surfaces (Rank 1).** Create one
   shared severity→display map (`high→Elevated`, `medium→Warning`, …) consumed by
   the dashboard, and decide explicitly whether the MCP/CLI agent persona speaks
   the display words or the internal severities — then make all three call sites
   (`App.tsx:382-385`, `:677-682`, and any other) and the agent persona agree, so
   a user never reads "Elevated" in one place and "high" in another for one case.
2. **Reconcile the case-state vocabulary (Rank 2).** Name one canonical
   case-state set, document the presentation collapse (`fixed`/`false_positive`
   → `resolved`) as an explicit mapping in `glossary.md` / `mcp/README.md`, and
   stop reusing the bare word `resolved` for the unrelated scan-diff axis.
3. **Make the glossary's catalog section match `tool-catalog.md` and the code
   (Rank 3),** restoring the two distinct axes (`lifecycle` vs `install_state`)
   with their real value names and deleting the invented `detected-locally` /
   `managed-install` / `display-only` install states. (Runner-up, lower cost:
   collapse `action_level`/`attention-bucket` and `fix_now`/`fix-now` to one
   name + one encoding — Rank 4 — and rename the internal `findings` route to
   `cases` — Rank 5.)

## SocratiCode Value

SocratiCode tools were not used for this lens. The drift here is exact-string and
enum-census work — comparing literal vocabulary across `model.py`, `decisions.py`,
`mcp_server.py`, `dashboardData.ts`, `App.tsx`, and the `docs/` set — which the
Cost Discipline Rule explicitly assigns to direct Grep/Read over structural
search, and the file paths were already known from `AGENTS.md` and the Excellence
Brief. Every claim in this report is anchored to a verified `file:line`, not to a
structural map. SocratiCode would add no fidelity to a literal naming audit and
was correctly skipped per the standard; its graph/impact tools would only be
warranted to scope blast radius for a chosen rename, which is `health-plan` /
`health-implement` work, not diagnosis.

## Limits

- `mcp_server` could not be imported in this base environment (`mcp` package
  absent); its vocabulary was verified by reading `mcp_server.py` directly rather
  than by exercising the live tool surface. Runtime behavior of the MCP status
  collapse was inferred from `_case_status_label` (`:224-231`), not executed.
- `uv run pytest` was not run; this is a read-only language audit and tests do
  not assert naming consistency. No test exists that would fail on the severity,
  lifecycle, or confidence-coercion drifts — itself a gap better owned by the
  `test-confidence-health` lens, not duplicated here.
- The dashboard was not launched (per AGENTS.md operating rules / risk register),
  so user-visible label rendering was verified from JSX/TSX source, not a live
  screen. Rendering of `Elevated`/`Warning` is inferred High-confidence from
  `severityMeta`/`severityCounts` but not visually confirmed.
- Counts (e.g. "36 `fix_now`", "11 `findings`-route identifiers") are `grep`
  tallies over `src/`, `dashboard-ui/src/`, and `docs/`, excluding generated
  output and `node_modules`; they bound the drift, they are not exhaustive AST
  references.
- Sibling-lens boundary: the *encoding* of contracts (typed/validated/versioned
  case schema, malformed-input handling) belongs to `data-contract-type-health`;
  this report flags the *naming* inconsistency and the implicit API shape but does
  not assess schema validation. The severity-as-trust-signal *UX* belongs to
  `behavioral-ux-health`; this report stops at the vocabulary split.
