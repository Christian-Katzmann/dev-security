# Consequence vs severity — the trust-gate judgment (Step 3.2)

**Verdict: GO (scoped).** The graph does not mis-rank. The consequence re-rank is
demonstrably truer on real data, it is purely additive, and it never buries a
higher-severity finding. Campaign 2 may proceed — but its honest promise must be
scoped to **dependency reachability** (the table-stakes win), because the *novel*
IaC blast-radius-to-a-datastore signal could not be exercised on any real repo in
this fleet. Details and conditions below.

---

## How this was measured (reproducible)

The existing scan history in `~/.security-observatory/db/observatory.sqlite`
predates the Honeygraph campaign: it has **no** `asset_nodes`/`asset_edges` tables
and **no** SBOM components, so it carries no graph and could not be used directly.
The default scan profile never runs Syft/Checkov, so no stored report has an SBOM
or IaC either.

So the comparison was built from **real findings + a real, freshly-generated
dependency graph**, run through the *exact* ranking code `scan_orchestrator.scan_repo`
runs — no toy fixtures, no reimplementation:

1. **Real findings** loaded from a stored `normalized-report.json` (the actual
   scanner output from the 2026-05-30 fleet scan).
2. **Real SBOM dependency graph** generated with the same Syft invocation DëvSec
   uses: `syft dir:<repo> -o cyclonedx-json`, then parsed by the production
   `load_sbom_components` / `load_sbom_dependency_edges`.
3. **Real correlation** via `enrichment.correlate_dependency_findings` (sets each
   dependency finding's `component_fingerprint`).
4. **Real pipeline**: `build_security_cases` → `derive_asset_nodes` →
   `mark_crown_jewels` → `attach_consequences` → `apply_consequence_priority`.

Harness + probe committed alongside this note (`notes/harness.py`, `notes/probe.py`).
Re-run:

```
syft "dir:/Users/christiankatzmann/Dev/Projects/Dashboard Studio" \
  -o cyclonedx-json=/tmp/honeygraph-32/dashboard-studio.cdx.json -q
uv run python campaigns/honeygraph-1-asset-graph/notes/harness.py \
  ~/.security-observatory/reports/Dashboard-Studio/Dashboard-Studio-20260530T184056Z/normalized-report.json \
  /tmp/honeygraph-32/dashboard-studio.cdx.json "express,@libsql/client"
```

**Repos / scans used:**

| Repo | Scan id | Findings | Ecosystem | Components | depends_on edges |
|------|---------|---------:|-----------|-----------:|-----------------:|
| Dashboard-Studio | `Dashboard-Studio-20260530T184056Z` | 148 | npm (`package-lock.json`) | 1319 | 1491 |
| gitslip | `gitslip-20260530T184136Z` | 197 | pnpm (`pnpm-lock.yaml`) | 2571 | 2163 |

**Crown jewels labeled** (chosen on security merit *before* looking at what they
promote — the honest protocol):

- Dashboard-Studio → `express` (the internet-facing web server) and
  `@libsql/client` (the database client — the path to the data).
- gitslip → `wrangler` (the Cloudflare deploy/runtime tool).

---

## Result 1 — Dashboard-Studio: the re-rank is truer

`reach-jewel = 4 (strong=4, weak=0)` out of 50 cases that mapped to a graph node.

**Top of the list — before (severity) vs after (consequence):**

```
TODAY (severity)                          AFTER (consequence)
 1 fix_now/critical  agent auto-approval   1 fix_now/critical  agent auto-approval
 …  (5 criticals)                          …  (same 5 criticals, untouched)
 5 fix_now/critical  exposed credential    5 fix_now/critical  exposed credential
 6 verify /high      broad workspace perm   6 fix_now/medium    qs vuln        <<reaches express, 1 hop, strong>>
 7 verify /high      broad workspace perm   7 fix_now/medium    path-to-regexp <<reaches express, 2 hops, strong>>
 8 verify /high      broad workspace perm   8 fix_now/medium    path-to-regexp <<reaches express, 2 hops, strong>>
 9 verify /high      broad workspace perm   9 fix_now/medium    ws vuln        <<reaches @libsql/client, 3 hops, strong>>
10 verify /high      hidden unicode        10 verify /high      broad workspace perm
```

**The four promoted findings** (`verify → fix_now`, each carrying its reason):

| Finding | Was rank | Now rank | Reason on the case |
|---------|---------:|---------:|--------------------|
| `qs` GHSA-Q8MJ-M7CP-5Q26 | 135 | 5 | "This finding can reach express@5.2.1 in 1 hop, so it outranks higher-severity findings that reach nothing." |
| `path-to-regexp` GHSA-27V5-C462-WPQ7 | 130 | 6 | "…reach express@5.2.1 in 2 hops…" |
| `path-to-regexp` GHSA-J3Q9-MXJG-W52F | 131 | 7 | "…reach express@5.2.1 in 2 hops…" |
| `ws` GHSA-58QX-3VCG-4XPX | 146 | 8 | "…reach @libsql/client@0.17.0 in 3 hops…" |

**Why this is genuinely truer, not just different.** `qs`, `path-to-regexp`, and
`ws` are all **HTTP / WebSocket request-path parsers** — code that processes
untrusted external input on the web server. A medium-severity parsing/ReDoS vuln
in code your internet-facing Express server actually runs is more urgent than a
medium-severity vuln in `vite`, `postcss`, or `picomatch` (build-time dev tooling
that never touches a production request). The flat severity list buries `qs` at
**rank 135**, indistinguishable from ~50 other rows that all read
"… dependency vulnerability (medium)". The consequence list lifts exactly the four
reachable ones into the actionable region and leaves the other ~50 untouched at the
bottom (ranks 90–147). That is the campaign's whole thesis, working on real data.

**It never hides anything.** All five `critical` findings (agent auto-approval
configs, exposed credentials) stay at ranks 1–5. The promoted mediums land *below*
the criticals (severity is still the dominant sort key inside the `fix_now` bucket)
and *above* the non-reachable `high`s — exactly "outranks higher-severity findings
that reach nothing," never "outranks a critical."

---

## Result 2 — gitslip: reproducible, and a failure mode surfaced

Crown jewel `wrangler`: `reach-jewel = 14 (strong=14, weak=0)`. The 14 reachable
vulns (`esbuild`, `defu`, `ws`, `undici`, …) promote `verify → fix_now` and land at
ranks 17–30, immediately **after** the 16 `critical` findings — never displacing
them. Same clean, additive behavior on a different ecosystem (pnpm) and a larger
finding set. The mechanism reproduces.

**The honest failure mode this repo exposes.** The `probe.py` blast-target ranking
for gitslip is dominated by **dev/test tooling**: the nodes reached by the most
vulns are `@cloudflare/vitest-pool-workers` (13), `@vitest/coverage-v8` (9),
`vitest`, `typescript-eslint`, `eslint-*`, `textlint`, `slopless`. If a user
naively labeled "the most-connected node" as a crown jewel, the re-rank would
**promote build-time/test-only vulns that never run in production** — actively
*worse* than flat severity. The graph cannot tell production runtime from dev
toolchain. **The signal is only as good as the human's crown-jewel judgment.**
This is consistent with the locked decision "crown jewels are human-labeled, never
inferred," but it means a careless label produces a misleading re-rank, not a safe
no-op.

---

## Where it helped, where it could mislead, and the false-promote rate

**Helped** (true positives): on Dashboard-Studio, 4/4 promotions are defensible —
all are request-path parsers reachable from the externally-exposed server / DB
client. On gitslip, promotions are deploy-toolchain vulns reachable from `wrangler`
— a weaker but still legitimate supply-chain-of-your-deploy-tool argument.

**False-promote rate on weak edges: not measurable — 0 weak edges exist.** Every
`depends_on` edge Syft emits is a *declared* relationship, so the graph contains
**only `strong` edges**. There were **zero `weak` edges in either repo**, so every
promotion was a `strong`-path promotion (`strong=4` and `strong=14`, `weak=0` both
times). The "never auto-promote on a low-confidence edge" rule and the
weakest-link confidence machinery are therefore **structurally untested on real
data** — they are proven only by the unit tests in `tests/test_priority.py` /
`tests/test_consequence.py`, not by this real-data run. Weak edges only ever come
from the IaC heuristic linker (step 1.3), which never fired (see below).

**Could mislead** (honest list):
1. **Crown-jewel choice drives everything.** Labeling the *root app* promotes all
   12 vulns (non-discriminating); labeling `@anthropic-ai/sdk` promotes **0** (the
   vulns aren't in its subtree). The same graph gives a useful, a useless, or a
   misleading re-rank depending purely on the label.
2. **Component crown jewels are labeled by `component_fingerprint`** — a 24-hex
   string, not a package name. No human will hand-author `.devsec/crown-jewels.json`
   for a component. The component-crown-jewel path is mechanically sound but **not
   usable** without a "mark this package" affordance. (Datastore/secret crown
   jewels use human-readable paths/addresses — but those need IaC.)
3. **Shallow graph → false negatives.** Syft's directory-scan dependency graph is
   partial (blast radii of 1–4 here). Real edges are missing, so some vulns that
   genuinely reach a crown jewel are silently not promoted. The signal is
   conservative — it under-claims rather than over-claims, which is the safe
   direction, but it is not complete.

---

## The signal that fired vs the signal that didn't (the OPEN QUESTION)

The campaign's open question asks this be stated plainly. **It must be.**

- ✅ **Dependency reachability fired.** A vulnerable package reaching a labeled
  high-value *component* (web server / DB client / deploy tool) via `depends_on`
  edges. This is the **table-stakes** reachability win — cloud ASPM tools do this;
  DëvSec's edge is "local-first, for individuals," not novelty.
- ❌ **The novel IaC blast-radius signal did NOT fire — at all.** The
  resource→datastore (`stored_in`) and secret→resource (`reachable_from`) edges
  that let a *secret* reach a *datastore crown jewel* require IaC. **There is zero
  Terraform anywhere under `~/Dev`** (`find ~/Dev -name '*.tf'` → empty), and the
  datastore classifier (`iac.DATASTORE_RESOURCE_TYPES`) is Terraform-only. So:
  zero `datastore` nodes, zero `resource` nodes, zero IaC edges, zero weak edges,
  zero secret-to-datastore paths across the entire fleet. The differentiated
  "blast radius to your crown-jewel database" story is **unproven on real repos**
  and provable today only by unit-test fixtures.

This bounds what Campaign 2 can honestly promise: **dependency reachability,
proven; IaC blast-radius, mechanism-only.**

---

## Verdict: GO (scoped) — and the conditions

**GO.** The trust-gate question is "does the graph mis-rank?" It does not:

- The re-rank is **additive and conservative** — criticals untouched, no-consequence
  cases unchanged, every promotion explained in plain English, no spurious
  promotions, strong-path-only.
- On real data it is **demonstrably truer** for the dependency class: it surfaced
  the request-path vulns reachable from the externally-exposed server above 50
  look-alike mediums and above non-reachable highs, on two repos, reproducibly.
- Its failure modes are **safe-direction** (under-promote on a sparse graph) or
  **bounded by an explicit human decision** (crown-jewel labels), not silent
  mis-ranking.

The loop in Campaign 2 (Tripwire Bridge + Confirmation) can therefore build on this
graph. **Conditions Campaign 2 must honor (read these into its Step 0.1):**

1. **Scope the promise to dependency reachability.** Do not market the
   IaC/datastore blast-radius as a delivered capability — it has never fired on a
   real repo. Treat it as proven only when a real-IaC repo demonstrates a
   secret→datastore promotion end-to-end.
2. **Make component crown jewels human-labelable** (mark-a-package by name, not by
   fingerprint), or the component-reachability win stays unusable in practice.
3. **Exercise the weak-edge path on real data.** Every real promotion so far was
   `strong`; the "don't auto-promote on a weak edge" honesty rule is unverified
   outside unit tests. Campaign 2 should not lean on it until a weak (IaC) edge has
   been seen in a real re-rank.
4. **Guard the crown-jewel choice.** gitslip shows a naive label promotes dev-tool
   vulns. Campaign 2's UX should steer users toward production-runtime crown jewels
   (and ideally flag when a labeled jewel is dev/test-only).

**This is an unambiguous GO with scope.** Proceed to Campaign 2; keep the marketing
honest.
