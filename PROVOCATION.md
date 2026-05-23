# Provocation

> The dominant default in repo security tooling is to send source code to a SaaS for analysis. The argument is convenience — and the cost is treated as accepted. We think the cost *is* the analysis itself: *"clean scans came back from our third-party SaaS"* is a worse epistemic state than *"I ran an open-source scanner on my machine and read the output myself."*

## The cost of being wrong

Source code is concentrated context. A repo contains, in compressed form:

- Secret defaults in `.env.example` and config templates that mirror real defaults in production
- Infrastructure topology in `terraform/`, `docker-compose.yml`, and CI config
- Customer-data shapes in fixtures and seed data
- Internal hostnames and service names referenced in tests
- Branch-naming and review patterns that signal team structure
- The full history of how all of the above evolved

Centralizing this across thousands of customer repos makes the security SaaS itself the highest-value target in the security supply chain. The recent history of breached security-tool vendors is not a sequence of anomalies — it's the central tendency. The vendor whose product was meant to protect your code becomes the vector through which it leaks.

The standard counter-argument is that the SaaS is *"well-secured."* The same counter-argument applied to every breached security vendor the day before each breach.

## What DëvSec does as a consequence

- **Scanners run on your machine.** Trivy, Semgrep, Gitleaks, OSV-Scanner, Syft, Grype, Checkov, Medusa — all installed locally, all invoked locally, all output stays under `~/.security-observatory`.
- **History lives in local SQLite.** The dashboard's *Recent Activity* view reads from your machine. No telemetry. No remote analytics.
- **No cloud LLM is required.** The "agent-ready follow-up" is a markdown prompt generated locally — you take it to whichever agent you already trust, on whatever boundary you've already decided. See `docs/decisions/REJECTED/002-cloud-llm-for-finding-explanation.md`.
- **The dashboard binds to `127.0.0.1`.** It is not exposable from the box without deliberate effort. If you want to share findings, you export them deliberately.
- **Connected checks are explicit opt-ins.** OpenSSF Scorecard and `legitify` platform-posture checks are off by default, gated on tokens you provide.
- **The README opens with the *"what it is not"* list.** Filtering the audience matters more than maximizing reach.

## Where we might be wrong

- **Behavioral analysis across orgs.** A SaaS with thousands of customer repos can in principle detect cross-org attack patterns — a malicious dependency landing in many repos at once — that a single-machine tool cannot. We're betting that signal is worth less than the breach-surface cost; that bet may be wrong for organizations whose threat model includes nation-state-adjacent campaigns where cross-org telemetry is decisive.
- **Local install friction.** Some organizations cannot or will not have engineers install scanners locally. For those, a SaaS is operationally the only option. We are not solving for that audience.
- **Solo-developer scale.** DëvSec is shaped for a developer or small team scanning their own repos. A 500-engineer enterprise with thousands of repos wants something else — and that something else may legitimately involve centralized infrastructure, though it does not have to involve a third-party SaaS.

We are arguing the *default* should flip, not that SaaS analysis is universally wrong. If your threat model genuinely requires it, choose it deliberately — but choose it. Don't accept it as the only available shape.
