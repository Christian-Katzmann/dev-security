# Threat model (lite)

A security tool has to be honest about its own threat model, because *"we ran a scanner"* is not a synonym for *"we are safe."* This document covers what DëvSec protects, what it doesn't, and what an attacker could realistically do.

For the system-shape view, see [design/diagrams/trust-boundary.md](../design/diagrams/trust-boundary.md). This document covers attack surface and mitigations.

For the read+write MCP extension — the guarded scan-trigger, the high/critical suppression gate, and the auto-merge fix-class allowlist — see [rw-extend-spec.md](rw-extend-spec.md). That surface operates on attacker-influenceable finding text, so its decisions directly harden the prompt-injection gap named in [Known gaps](#known-gaps-the-load-bearing-section) below.

## Assets

What DëvSec stores or touches that has value to an attacker:

- **Local source code under scan.** Whatever repository you point `security-scan` at — the scanner reads files there. Nothing is uploaded, but a compromised scanner binary could read or exfiltrate.
- **`~/.security-observatory/`** — local SQLite database containing scan history, raw finding text (which can include short snippets of secret matches and source patterns), and repo metadata.
- **Honey Keys metadata** — the decoy secrets DëvSec generates, their placement records, and their trigger logs. The decoys themselves are designed to be exfiltrated; the *metadata about where they were placed* is sensitive because it reveals defensive posture.
- **`.adx/` operational contracts** — `risks.json`, `commands.json`, `verification.json`. Not secrets, but a roadmap of where to look for sensitive paths.

## Trust boundaries

Three boundaries, in order of how seriously DëvSec treats them:

1. **The machine boundary** (load-bearing). Nothing crosses out of your machine by default. The local-first stance lives or dies on this boundary — see [PROVOCATION.md](../PROVOCATION.md) for the argument.
2. **The dashboard `127.0.0.1` binding.** The dashboard server binds to localhost only, not `0.0.0.0`. Sharing requires deliberate effort (SSH tunnel, explicit reverse proxy). It is not reachable from the LAN as configured.
3. **The scanner-binary boundary.** Each scanner runs in-process or as a subprocess and reads only what `security-scan` points it at. DëvSec does not sandbox scanners further than the OS does.

## Main risks

| # | Risk | Realistic attacker | Mitigation today | Residual risk |
|---|---|---|---|---|
| 1 | **Scanner binary supply chain.** Trivy, Gitleaks, Semgrep, etc. are third-party. A compromised release could read files, exfiltrate, or persist. | Anyone who can land a malicious release in the upstream scanner. | DëvSec uses Homebrew/uv/pipx-installed scanners when detected, and pins the managed-install proof (`gitleaks v8.30.1`) by version. No binary signature verification yet. | A 0-day in an upstream scanner release would not be caught by DëvSec. We rely on the upstream's release pipeline. |
| 2 | **Local file traversal during scan.** Scanners walk the scan target — including `.env`, `.git/`, `node_modules/`, and anything else readable. | Already-local attacker who controls the scan path. | DëvSec stores raw findings locally and shows redacted-evidence snippets in the dashboard. It does not transmit them. | If your scan history is exfiltrated by some other means (e.g. someone walks off with your laptop), it contains the same sensitive snippets the scanners saw. Encrypt your disk. |
| 3 | **Dashboard exposure.** The dashboard listens on `127.0.0.1`. If a user reverse-proxies it without auth, anyone with network reach can read cases and raw findings. | Anyone who can reach the proxied port. | The dashboard binds to localhost by default; there is no built-in auth because there's no shared listener. | We do not ship an authentication layer because we do not ship a remote-access mode. If you build one yourself, the auth is your responsibility. |
| 4 | **Honey Key misuse.** Honey Keys are decoys *meant* to be exfiltrated and trigger a callback. A legitimate developer who copies a key into a public gist generates a false alarm. | The user themselves. | Each Honey Key carries a placement record; the dashboard explains which key fired and where it was placed. | A noisy false alarm is the cost of catching real exfiltration. The alternative — no decoys — is worse. |
| 5 | **AI-static rule misfire (false negative).** The built-in `ai-static` scanner uses pattern-matching heuristics for AGENTS.md / `.mcp.json` / Cursor rules. A real risky config can slip past if the wording is novel. | The user who writes a novel agent config; or an attacker who plants one. | The detection rules are themselves source-readable and extensible (`src/security_observatory/ai_static.py`); CI runs per-rule fixture tests on every push to catch regressions before they ship. See [failure-modes.md §4](failure-modes.md) for a worked example of this class. | This is heuristic detection; perfect recall is not on the table. |
| 6 | **Installer behavior on first run.** `install-security-observatory.sh` calls Homebrew, uv, pipx, and remote shell installers to set up scanners. | A user who runs the installer on an already-compromised machine, or against a tampered URL. | The installer pins each scanner version and tags itself as a `human_recommended` approval risk in `.adx/risks.json`. Install URLs are pinned to release tags after the recent workflow-allowlist pass. | The installer trusts the upstream package managers — if Homebrew or uv themselves are compromised, the installer carries that compromise. |

## Known gaps (the load-bearing section)

What DëvSec does **not** defend against today, said plainly:

- **No cryptographic verification of scanner binaries.** We trust the package-manager release pipeline. If you need verified-signature installs, that has to be done outside DëvSec.
- **No sandboxing of scanner subprocesses.** A malicious scanner has the same filesystem access as your shell. macOS App Sandbox / Linux namespaces are not used.
- **No protection against a local attacker who already has shell access.** If they're on your machine, they can read `~/.security-observatory/` directly; DëvSec gives them no new capability they didn't already have.
- **No multi-user model.** The single operator who runs `security-scan` is assumed to be the owner of the cases and raw findings. There is no RBAC, no audit log against the dashboard user, no read-only role.
- **No anti-tampering on the local SQLite store.** If your local store is modified out-of-band, DëvSec will trust the modified contents on next dashboard load.
- **No protection from prompt injection in case/raw-finding output displayed to LLMs.** If you paste a case's "agent-ready follow-up" into a chat with a code-edit-capable agent, and its raw findings included attacker-controlled text from a scanned repo, the agent could be steered. Read the prompt before pasting.
- **No External Surface scanning.** The catalog has External Surface as a `coming-soon` placeholder. No active recon, no probing, no target-input UI in MVP. The placeholder exists so we do not silently grow that capability without the approval rails first.

## What this document is not

This is not a SOC-2 control matrix. It is a one-page honest read of the actual attack surface and what we have done about it. If you need a formal assessment for a procurement process, do one against your own controls; this document is here so you start from accurate ground.
