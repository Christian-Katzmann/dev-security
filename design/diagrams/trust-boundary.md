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

           Nothing crosses out on the default path. The
           local-first stance is enforced by what is deliberately
           absent from this diagram: there is no upload path, no
           third-party API call, no telemetry endpoint, no license
           server, no cloud LLM round-trip, no "anonymized usage
           data." The dashboard even self-hosts its fonts (Geist,
           bundled into the build), so loading the UI in a browser
           contacts no external host either.

           The agent-ready follow-up is a markdown prompt
           generated locally. You take it to whichever agent
           you already trust, across whichever boundary you've
           already decided to accept.
```

## Explicit opt-ins (and where they cross)

Egress *can* cross the boundary, but only when you turn it on. Each surface
below is off by default. There are **four third-party egress surfaces** — the
exact host and the exact data that leaves are named for each — plus the Honey
Key callback, which crosses only to infrastructure **you** own.

The four third-party surfaces:

```
   ┌── #1: EPSS exploit-probability lookup  (dependency trust enrichment) ──┐
   │                                                                       │
   │   security-scan        ────►  HTTPS  ────►  api.first.org             │
   │   --deps --trust                            (EPSS, FIRST.org)         │
   │                                                                       │
   │   Sends: CVE IDs of the advisories found in your dependencies.        │
   │   The default profile uses the cache-only variant                     │
   │   (--trust-cache-only), which never reaches the network.              │
   └───────────────────────────────────────────────────────────────────────┘

   ┌── #2: OpenSSF Scorecard project hygiene  (dependency trust enrichment) ┐
   │                                                                       │
   │   security-scan        ────►  HTTPS  ────►  api.scorecard.dev         │
   │   --deps --trust                            (OpenSSF Scorecard)       │
   │                                                                       │
   │   Sends: source-repo identifiers (org/repo slugs) of your            │
   │   dependencies. Cache-only by default, as above. No source           │
   │   code crosses — only the repo identifier.                            │
   └───────────────────────────────────────────────────────────────────────┘

   ┌── #3: connected platform-posture checks (legitify) ───────────────────┐
   │                                                                       │
   │   security-scan        ────►  HTTPS  ────►  GitHub                    │
   │   --platform-posture       (your SCM token)  (legitify queries the    │
   │                                               platform API)           │
   │                                                                       │
   │   Triggered only when you run --platform-posture with an SCM token.   │
   │   Sends: the repo slug (derived from your git remote) and the         │
   │   platform metadata legitify reads. No source code crosses — only     │
   │   repo metadata the platform already knows (visibility, branch        │
   │   protection, etc.).                                                  │
   └───────────────────────────────────────────────────────────────────────┘

   ┌── #4: managed-tool binary downloads ──────────────────────────────────┐
   │                                                                       │
   │   security-scan / setup  ──►  HTTPS  ──►  github.com/<vendor>/releases │
   │   (when you install a                                                 │
   │    managed scanner)                                                   │
   │                                                                       │
   │   Sends: a plain GitHub release download request (no repo data).      │
   │   Fires only when you choose to install a managed scanner binary      │
   │   (gitleaks, trivy, syft, grype, …); each download is checksum-       │
   │   /signature-verified before install.                                 │
   └───────────────────────────────────────────────────────────────────────┘
```

And the Honey Key callback, which never reaches a third party:

```
   ┌── Honey Key callbacks (cross only to infrastructure you own) ─────────┐
   │                                                                       │
   │   Attacker exfiltrates a decoy secret                                 │
   │                  │                                                    │
   │                  ▼                                                    │
   │           Their server                                                │
   │                  │  (uses the leaked key)                             │
   │                  ▼                                                    │
   │           YOUR webhook  ◄──── you configure the endpoint              │
   │                                                                       │
   │   The callback never reaches DëvSec infrastructure — DëvSec           │
   │   doesn't operate any. You point Honey Keys at a webhook you          │
   │   own (your monitoring, your Slack, your incident system).            │
   └───────────────────────────────────────────────────────────────────────┘
```

## What this diagram is for

This diagram exists so a stranger can answer one question in ten seconds: *if I run this tool, where does my code go?*

The honest answer is: **it doesn't go anywhere.** That answer takes a diagram to make legible, because the strength of the design is in absent paths, and absences don't show up in a screenshot.
