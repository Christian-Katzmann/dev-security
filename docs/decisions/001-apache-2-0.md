# 1. License — Apache-2.0

## Status

Accepted (2026-05-23). Locked in the `public-repo-ready` campaign Context.

## Context

DëvSec is a security tool that orchestrates open-source scanners (Trivy, Semgrep, Gitleaks, OSV-Scanner, Syft, Grype, Checkov, Medusa), normalizes their output, and ships its own custom code for case grouping, honey-key generation, and the dashboard UI. Two questions drove the license choice:

1. **Patent grant.** A tool that catalogs vulnerability detection methods, normalizes scanner output, and produces remediation guidance contains patentable surface area (or surface area that adjacent actors might *claim* is patentable). The license needs to grant patents alongside copyright, or the project carries permanent latent risk.
2. **Ecosystem match.** Every scanner DëvSec orchestrates is Apache-2.0 licensed. Mismatched licensing creates contributor confusion and downstream friction.

## Decision

**Apache-2.0.** Full canonical SPDX text in `LICENSE`, copyright line *"Copyright (c) 2026 Christian Katzmann"*. No modifications to the standard text.

## Consequences

**Positive**

- Patent grant scoped to contributors who actually wrote the code, with a retaliation clause that protects the project against patent attacks.
- Same license as every scanner being orchestrated — no contributor confusion about which terms govern.
- Compatible with most downstream uses, including commercial use, modification, and private use.
- GitHub's "Cite this repository" UI and dependency-license analysis tools recognize Apache-2.0 as a known SPDX identifier.

**Negative**

- Slightly longer license text than MIT (~12 kB vs. ~1 kB) means newcomers reading `LICENSE` may bounce off the legal density. The README's positioning sentence has to do the audience-filtering instead.
- Apache-2.0 cannot be combined with GPL v2 (Apache's patent grant is incompatible with GPLv2's). Unlikely to matter — no current dependency is GPLv2 — but worth flagging if a contributor ever proposes vendoring GPLv2 code.

## Alternatives considered

**MIT.** Shorter, more permissive in style. Rejected because MIT is silent on patents — a contributor or downstream user could later assert patent claims that the license neither prevents nor licenses. For a security tool, silence is not safety.

**GPL-3.0 / AGPL-3.0.** Stronger copyleft; would prevent a SaaS vendor from forking DëvSec into a proprietary cloud product. Rejected because the goal is to make the local-first stance the default, which means *encouraging* downstream adoption (including in proprietary settings) rather than restricting it. The breach-surface argument in `PROVOCATION.md` applies to any vendor regardless of license; we are not trying to win that fight via copyright law.

**BSD-3-Clause.** Functionally similar to MIT but with an explicit no-endorsement clause. Same patent silence problem as MIT.
