# ADX Operating Layer

This directory is the repo-local operating layer for AI coding agents.

It exists so a cold agent can answer five questions quickly:

- What is this repo?
- Which commands are safe and authoritative?
- How should changes be verified?
- Which areas require extra care?
- How should common failures be recovered from?

## Contracts

- `adx.json` describes the installed ADX contracts and entrypoints.
- `commands.json` is the command registry; prefer it over commands hidden in prose.
- `verification.json` maps change types to checks.
- `risks.json` classifies dangerous areas and required behavior.
- `recovery.md` records repo-specific recovery paths.
- `modules/index.json` maps the main code areas.
- `audit/latest.json` is the latest ADX doctor receipt.
- `implementation/` stores ADX implementation receipts.

Safety is advisory in this pass. No blocking hooks or CI gates are installed.
