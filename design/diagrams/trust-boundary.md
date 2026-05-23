# Trust boundary

DëvSec's design is shaped by where data is allowed to go. The diagram below shows the *whole* system — and the boundary's strength is in what was deliberately left out, not in what's drawn.

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                          YOUR MACHINE                               │
│                                                                     │
│    git clone                                                        │
│        │                                                            │
│        ▼                                                            │
│    Local repo  ──────►  security-scan CLI  ──────►  Local scanners  │
│                                  │                  Semgrep         │
│    AGENTS.md,                    │                  Gitleaks        │
│    .mcp.json,        ────────────┤                  TruffleHog      │
│    Cursor rules,                 │                  Trivy           │
│    workflow YAML                 │                  OSV-Scanner     │
│                                  │                  Grype           │
│    package.json,                 │                  Syft            │
│    pyproject.toml,    ───────────┤                  Checkov         │
│    requirements.txt              │                  Medusa          │
│                                  │                  built-in checks │
│                                  ▼                                  │
│                          Normalizer + case builder                  │
│                                  │                                  │
│                                  ▼                                  │
│                       ~/.security-observatory                       │
│                            (local SQLite —                          │
│                          scan history,                              │
│                          findings, cases)                           │
│                                  │                                  │
│                                  ▼                                  │
│                   localhost:8765 dashboard  ──────►  You            │
│                   (bound to 127.0.0.1)                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

           Nothing crosses out. The local-first stance is
           enforced by what is deliberately absent from this
           diagram: there is no upload path, no third-party
           API call, no telemetry endpoint, no license server,
           no cloud LLM round-trip, no "anonymized usage data."

           The agent-ready follow-up is a markdown prompt
           generated locally. You take it to whichever agent
           you already trust, across whichever boundary you've
           already decided to accept.
```

## Explicit opt-ins (and where they cross)

Three things *can* cross the boundary, but only when you turn them on. Each is off by default.

```
   ┌────────── opt-in #1: connected platform-posture checks ──────────┐
   │                                                                  │
   │   OpenSSF Scorecard  ◄────  HTTPS  ◄────  security-scan          │
   │   legitify                  (your token)                         │
   │                                                                  │
   │   Triggered only when you provide a GitHub/GitLab token.         │
   │   No source code crosses — only repo metadata the platform       │
   │   already knows about (visibility, branch protection, etc.).     │
   └──────────────────────────────────────────────────────────────────┘

   ┌────────── opt-in #2: dependency trust enrichment ────────────────┐
   │                                                                  │
   │   security-scan  ────►  HTTPS  ────►  Public vulnerability       │
   │   --deps --trust                       databases (OSV.dev, etc.) │
   │                                                                  │
   │   Sends package name + version. Default profile uses the         │
   │   cache-only variant (--trust-cache-only) which never reaches    │
   │   the network.                                                   │
   └──────────────────────────────────────────────────────────────────┘

   ┌────────── opt-in #3: Honey Key callbacks ────────────────────────┐
   │                                                                  │
   │   Attacker exfiltrates a decoy secret                            │
   │                  │                                               │
   │                  ▼                                               │
   │           Their server                                           │
   │                  │  (uses the leaked key)                        │
   │                  ▼                                               │
   │           YOUR webhook  ◄──── you configure the endpoint         │
   │                                                                  │
   │   The callback never reaches DëvSec infrastructure — DëvSec      │
   │   doesn't operate any. You point Honey Keys at a webhook you     │
   │   own (your monitoring, your Slack, your incident system).       │
   └──────────────────────────────────────────────────────────────────┘
```

## What this diagram is for

This diagram exists so a stranger can answer one question in ten seconds: *if I run this tool, where does my code go?*

The honest answer is: **it doesn't go anywhere.** That answer takes a diagram to make legible, because the strength of the design is in absent paths, and absences don't show up in a screenshot.
