# Glossary

Terms used inside DëvSec with precise internal meanings. Defining these once here keeps the rest of the docs short and the dashboard's labels readable.

## Raw finding

The atomic unit of scanner output. One raw finding represents one identified issue in the repo — a leaked secret, a vulnerable dependency, a misconfigured IaC resource, a risky AI-agent instruction. Raw findings are deduplicated across scanners via a stable fingerprint, so a secret detected by both Gitleaks and TruffleHog appears once, not twice. Raw findings carry severity, category, scanner provenance, and file location.

**Example:** *"Gitleaks detected an `aws_access_key_id` in `src/legacy/config.py:42`"* is one raw finding.

The normalized JSON keeps the historic `findings`, `active_findings`, and `suppressed_findings` fields for compatibility. In user-facing copy, call these **raw findings** or **scanner evidence**.

## Case

A group of related raw findings packaged for human or agent action. Cases are what the dashboard's **Cases** surface shows — not raw findings, but grouped work. A case bundles all raw findings of the same shape (e.g. *"42 stdlib CVE raw findings across the dependency tree"*) into one decision unit with a single recommended next step, a severity rollup, a confidence rollup, and an AI-prompt handoff.

**Cases vs. raw findings:** raw findings are scanner-level; cases are human-level. A scanner sees 41 individual CVE matches; a case is the one *"Upgrade vulnerable dependencies"* action that closes all 41 at once.

## Case lifecycle

The states a case moves through and the transitions between them. There is **one** canonical state machine — `src/security_observatory/lifecycle.py` — and every surface (storage, decisions, MCP, dashboard) derives its vocabulary from it. Two related-but-distinct things used to share the bare word "resolved"; they are now kept apart:

**Decision status (stored)** — what a human records on a case, persisted in `case_decisions.status`: `verified`, `false_positive`, `accepted_risk`, `fixed`, `in_progress`. `in_progress` (a.k.a. *awaiting rescan* / *verifying*) means *"fix applied, awaiting rescan proof."* Only `false_positive` and `accepted_risk` suppress a case.

**Lifecycle state (shown)** — what a case *is* at a glance. A single mapping table (also in the `lifecycle.py` docstring) translates the stored decision into what the dashboard and the MCP `cases(status=…)` filter show:

| Lifecycle state | Stored decision form | MCP presentation form |
| --- | --- | --- |
| `open` | (no decision) | `open` |
| `verified` | `verified` | `verified` |
| `in_progress` | `fixed` / `in_progress` (still present) | `resolved` (coarse fold) |
| `accepted_risk` | `accepted_risk` | `accepted_risk` |
| `resolved` | `false_positive`, or any case closed by a rescan | `resolved` |

So an agent querying MCP `status=resolved` can see, in one place, that `resolved` is a **display fold of `fixed` + `false_positive`**. The MCP label is coarse (no per-scan diff context); the dashboard has the diff axis and shows the richer `in_progress` (verifying) beat.

**Closure proof, not closure by absence:** when a rescan no longer finds a case, the case is bound to the scan that closed it (`resolved_by_scan_id`) and stays visible for one cycle as an affirmative *"Verified ✓ in scan X"* state, rather than silently dropping out of the attention list.

**Scan-diff axis (a separate machine):** `change_status ∈ new / recurring / resolved` (namespaced `DIFF_*` in `lifecycle.py`) describes how a case *moved between two scans* — it is **not** a lifecycle state. A case can be diff-`recurring` and lifecycle-`in_progress` at the same time. The shared word "resolved" names two unrelated axes; the diff axis is documented here as distinct so the ambiguity is explicit.

## Action level

How urgent a case is, separate from how severe its raw findings are. One of four values:

- **`fix_now`** — address immediately; severity and exploitability both warrant it.
- **`verify`** — looks real but needs human confirmation before action (high false-positive rate from the scanner, or context-dependent severity).
- **`watch`** — real but not currently exploitable; track for future regression.
- **`info`** — informational, no action required.

A case with high-severity raw findings can still be `verify` if the case-builder doesn't have enough context to recommend `fix_now` confidently. The two axes are independent.

## Confidence level

The scanner-reported certainty that a raw finding is real. Carried through to cases as a rollup. Distinct from severity — strong confidence can still apply to a low-severity issue, and weak confidence can still apply to a possible critical vulnerability that needs human verification.

Most scanners report confidence as a discrete level (high / medium / low) or a numeric score (0.0–1.0). DëvSec normalizes both into a four-level scale: `high`, `medium`, `low`, `unknown`.

## Agent-ready follow-up

The markdown handoff prompt generated locally from a case. Contains the case summary, all affected raw findings, scanner evidence, file locations, suggested fix steps, and explicit guardrails (*"verify before fixing, do not commit secrets, rotate before scrubbing history"*). Designed to be copied into an external coding agent — Claude Code, Cursor, Aider, or any LLM you trust — for follow-up work.

The agent-ready prompt is the local-first replacement for cloud LLM enrichment: the user's existing trust relationship with their agent is the one we route through, not a new one we manufacture. See [`docs/decisions/REJECTED/002-cloud-llm-for-finding-explanation.md`](decisions/REJECTED/002-cloud-llm-for-finding-explanation.md).

## Honey Key

A defensive decoy secret — generated by DëvSec, planted into a chosen file inside the user's repo, and tripped if anything ever touches it. Powerless: cannot authenticate to any real system. Trigger events fire alerts via redacted request metadata; the affected project turns critical when a key is touched.

Honey Keys are written under `.devsec/honeykeys/` by default. Advanced placement (anywhere in the repo) requires explicit confirmation. DëvSec refuses to overwrite existing files and refuses to write outside the selected repo's directory tree.

## Evidence gap

A scanner that should have run but didn't — missing binary, timed out, crashed, or returned incomplete output. Surfaced as a first-class field on the scan record so the user knows what wasn't proven. A scan with evidence gaps is still saved; the rest of the scan results remain useful, but the gap is named in the dashboard's coverage view.

**Why this matters:** without naming evidence gaps, a partial scan looks identical to a clean scan. *"No raw findings"* could mean *"the scanner ran and found nothing"* or *"the scanner failed to run."* The gap field disambiguates.

## Tool Catalog

The read-only contract describing every scanner DëvSec knows about. Each catalog entry names the scanner, its category, two independent state axes, and its safety policy (network access, credentials required, file writes, destructive actions, Agent Lab availability). The two axes are defined in [tool-catalog.md](tool-catalog.md):

- **`lifecycle`** — product availability: `available`, `beta`, `advanced`, `coming-soon`, `deprecated`, `hidden`.
- **`install_state`** — local truth about whether the tool can run here now: `built-in`, `managed`, `detected`, `missing`, `unavailable`, `not-configured`, `coming-soon`.

The catalog is the authoritative source for *"what can run here"* — Security Packs and individual scan profiles compose entries from the catalog rather than overriding their policies.

## Security Pack

A curated bundle of catalog entries grouped for a specific job — *Starter*, *Secrets*, *Dependencies*, *AI Agent*. A pack composes catalog entries but never weakens their policies; network access, credentials, file writes, and destructive-action gates come from the catalog, not the pack.

## Posture

The 0–10 score the dashboard displays at the top of every view, derived from the underlying 0–100 health score. Posture goes down when raw findings are present and up when they're resolved. The score is computed locally from the latest scan's raw findings, weighted by severity and category — see the *Health Score* section of the main README for the weighting table.

A posture of 0.0 / 10 does not mean the repo is unsalvageable; it means the open raw findings exceed the engine's penalty cap. The score is calibrated for relative comparison across scans of the same repo, not absolute comparison across different repos.
