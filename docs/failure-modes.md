# Failure modes

How DëvSec fails, and what we have done about each failure. Listed by realistic frequency, not by severity.

For the broader attack surface, see [threat-model.md](threat-model.md). This document covers operational failure modes — the things that go wrong in normal use.

## 1. False positives — scanners flag things that aren't real risks

**What it is.** Every scanner has noise: Gitleaks flags a test fixture string that looks like a key, Trivy flags a CVE in a stdlib component you can't upgrade, Semgrep flags a pattern in code that is intentional.

**Why it matters.** Noise erodes trust. A dashboard full of flagged-but-irrelevant findings teaches the operator to skim — and skimming is how real findings get missed.

**Current mitigation.** Findings roll up into *cases* — the case builder groups related findings into one human-readable item with a single recommended action. A run that produces 41 stdlib CVE findings becomes one *"Upgrade vulnerable dependencies"* case with a wall-clock estimate, not 41 separate tickets. Cases can be marked `resolved` with a note (e.g., *"vendored stdlib, upgrade tracked elsewhere"*); the case stays in history but stops appearing as open.

**Remaining risk.** The case roll-up logic is heuristic. It groups by category + cluster key; novel finding shapes may not group cleanly and may produce a long tail of one-finding cases. Per-tool false-positive guidance lives in [false-positives.md](false-positives.md) — read it before triaging.

## 2. False negatives — *"clean scan ≠ safe"*

**What it is.** A scan that returns no findings is not proof the repository is safe. Scanner rules are best-effort, scanner coverage is partial, and the world generates new attack patterns faster than rules ship.

**Why it matters.** This is the project's load-bearing epistemic claim — it's in the README's *"What It Is Not"* and in [PROVOCATION.md](../PROVOCATION.md). Treating a green dashboard as a green light is the failure mode the entire project is shaped to prevent.

**Current mitigation.** The dashboard never shows a *"safe"* or *"secure"* status. Posture is shown as a numeric score (out of 10) with the explicit understanding that 10 means *"the checks we ran did not find these specific problems,"* not *"this repository is secure."* Recovery playbooks tell you what to do when something is found; they do not promise the absence of findings means anything.

**Remaining risk.** A motivated user can still misread the dashboard as a clearance. The mitigation is editorial — the language never promises safety, the [PROVOCATION.md](../PROVOCATION.md) frames the stance, the [threat-model.md](threat-model.md) names what isn't covered. We are betting on honest framing rather than UI gymnastics.

## 3. Scanner unavailable or crashes

**What it is.** A scanner binary is missing, the wrong version, or crashes mid-scan. Trivy not installed, Semgrep on a Python version it doesn't support, Gitleaks killed by the OS for memory pressure.

**Why it matters.** A scan that runs without one of its scanners is a different scan than the one the user expected. Silently degraded coverage is the worst kind of failure — the dashboard looks normal, but a whole category was skipped.

**Current mitigation.** The Tool Catalog records each scanner's install state (`built-in`, `managed`, `detected`, `missing`, `unavailable`, `not-configured`, `coming-soon` — see [tool-catalog.md](tool-catalog.md) for full definitions). The dashboard surfaces missing/unavailable scanners and never reports coverage it didn't actually run. The Scan Completeness Panel in the dashboard shows what was attempted vs. what succeeded.

**Remaining risk.** A scanner that *runs but exits zero with no findings due to an internal error* may look like a clean pass. We rely on each scanner's own exit code conventions; not all scanners distinguish *"found nothing"* from *"crashed silently."* If you suspect this, re-run with `security-scan --verbose` and read the per-scanner logs.

## 4. AI-static rule regressions

**What it is.** The built-in `ai-static` scanner uses pattern-matching heuristics over AGENTS.md, `.mcp.json`, Cursor rules, and similar agent-config files. When a rule's matcher gets rewritten and the test fixtures don't catch the regression, the rule silently stops firing.

**Why it matters.** A scanner that *looks* like it's checking a category but actually returns nothing is worse than no scanner at all — it builds false confidence.

**Current mitigation.** The pytest suite (`tests/test_ai_static.py`) has per-rule fixtures and CI runs them on every push. A real instance of this class was caught and fixed: the *"auto-approval"* detection silently stopped firing on Linux CI runners because `_candidate_files` was excluding any path containing `"tmp"` as a part — including `/tmp/pytest-of-runner/...`. The fix tightened the exclusion to apply relative to the repo root rather than the absolute path; a regression test now reproduces the bug on any platform.

**Remaining risk.** Pattern-matching rules are inherently incomplete — novel ways to phrase a risky agent config (synonyms, structural variations, encoded values) may slip past. The CI fixtures only catch the patterns we've thought of. Treat `ai-static` as a useful early signal, not as comprehensive coverage of agent-config risk.

## 5. Honey Key misattribution

**What it is.** Honey Keys are decoy secrets meant to be exfiltrated and trigger a callback. If a legitimate developer copies a Honey Key into a public location by mistake (a gist, a Stack Overflow paste, a screenshot in a Slack message), the resulting callback looks like an attack.

**Why it matters.** False positives in a tripwire system burn out the alarm. After three false fires, the operator stops responding.

**Current mitigation.** Each Honey Key has a placement record (which repo, which file, what time). When a callback fires, the dashboard shows the placement record alongside the trigger context. An operator can reason about *"this fired from an IP block I recognize, the key was in `README.md` of a repo I just open-sourced — this is me."*

**Remaining risk.** A determined misuse (operator forgets they placed a key, then sees an alert and panics) is not preventable by tooling. The cost of false alarms is the price of catching real exfiltration. We treat this as a feature, not a bug — the alternative is no decoys, which is strictly worse.

## 6. Stale data

**What it is.** The dashboard reads from local SQLite. If the last scan was a week ago, the dashboard shows week-old findings. The operator sees what *was* true, not what *is* true.

**Why it matters.** A green dashboard from last Tuesday is not a green dashboard today. New CVEs ship daily; a stale view can convey false reassurance.

**Current mitigation.** The dashboard surfaces the *last scan time* per repository. The recency module (`src/security_observatory/recency.py`) tags findings older than a threshold as stale. The Activity heatmap visualizes scan cadence; gaps are visible.

**Remaining risk.** The dashboard does not auto-rescan. If the operator does not run `security-scan` regularly, the data ages. We deliberately do not background-rescan because that would mean a daemon watching your filesystem — which is a different trust posture than the on-demand CLI shape.

## 7. Out-of-band store modification

**What it is.** Something writes to `~/.security-observatory/` that isn't `security-scan` — a backup restore overwrites the DB, a curious script appends rows, a previous-version DB gets restored.

**Why it matters.** The dashboard trusts the local store. Modified contents will be displayed as if `security-scan` produced them.

**Current mitigation.** None automated. The DB schema versions are recorded; loading an incompatible schema fails fast. There is no integrity check on contents.

**Remaining risk.** This is in [threat-model.md](threat-model.md) under *"known gaps"*. We do not consider this a high-probability failure mode for the current threat model (single-operator local tool), but it is named so a user with a different threat model can plan around it.

---

## What this document is not

This is not a roadmap of *"things we will fix soon."* Each failure mode here either has a real mitigation, has an accepted residual risk, or is honestly flagged as known-bad (#4). Listing the rest would be theater.
