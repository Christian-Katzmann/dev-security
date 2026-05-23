# REJECTED: SaaS platform architecture

## What was proposed

Host DëvSec as a SaaS. Users sign up, grant repo access, the platform clones their repos, runs scanners centrally, presents findings via a hosted dashboard, and bills per repo per month.

This is the dominant pattern for security tooling: GitHub Advanced Security, Snyk, Semgrep Cloud, GitGuardian, Aikido, and roughly forty competitors all share this shape.

## What made it attractive

- **Network effects on signal quality.** A SaaS sees thousands of customer repos and can detect cross-org patterns — a malicious dependency landing in many repos at once — that a single-machine tool cannot.
- **No installation friction.** Users grant OAuth, the product works. No `brew install`, no `uv tool install checkov`, no shell-PATH debugging.
- **Standard business model.** Per-repo pricing is legible to procurement; recurring revenue is legible to investors.
- **Operational leverage.** Updates ship to all customers simultaneously; one team maintains one production deployment instead of supporting N user environments.

## What made it wrong for this project

Source code is concentrated context — secrets, infrastructure topology, customer-data shapes, internal hostnames, team patterns — and centralizing it across thousands of customers makes the SaaS itself the highest-value target in the security supply chain. The recent history of breached security-tool vendors is not a sequence of anomalies; it's the central tendency. Choosing the SaaS shape means accepting that the system whose job is to protect customer code is also the system most worth attacking *for* that code.

The local-first shape inverts the trade. Scanners run on the customer's machine; output stays under `~/.security-observatory`; the dashboard binds to `127.0.0.1`. The breach-surface argument doesn't apply because there is no central surface to breach. The cost is real — no cross-org signal, no zero-install onboarding — but it's the cost we're willing to pay to be honest about the shape of the trust relationship.

See `PROVOCATION.md` for the full version of this argument.

## When this might become right

For organizations whose threat model is genuinely dominated by cross-org behavioral patterns (likely nation-state-adjacent), where the value of the centralized signal exceeds the cost of the centralized risk. We are not building for that audience. If you are that audience, GitHub Advanced Security or Snyk are the established answers; DëvSec is not the right tool for you.

## Decided

2026-05-23 (alongside the public-repo-ready campaign).
