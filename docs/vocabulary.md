# Vocabulary lock

DëvSec uses security words narrowly so the dashboard, CLI, docs, and agent handoffs do not make the user translate the same word twice.

## Severity

Use severity words only for security severity:

- **Critical**: live or time-sensitive security risk.
- **Elevated**: high-severity security issue that should be reviewed today.
- **Warning**: medium-severity security issue or risk signal.
- **Low**: minor security issue or informational security signal.

Do not use critical, elevated, warning, or low for install state, scanner state, setup state, sync state, validation, empty states, or generic priority. For those, use neutral additive words: **Not installed**, **Add**, **Needs setup**, **Pending**, **Empty**, **Connect**, **Run**, or **Choose**.

The red/orange severity palette follows the same rule. Setup gaps, not-installed tools, and unavailable optional checks should not look like active security severity.

## Cases and Raw Findings

Use **Cases** for the user-visible work items. A case groups related scanner evidence into one action with risk, severity, confidence, fix steps, and an agent-ready prompt.

Use **Raw findings** or **Scanner evidence** for the underlying scanner-level records. Raw findings are useful for audit and exports, but they should not be labeled as the primary user task.

## Compatibility

The normalized JSON and SQLite schema keep the historical field names `findings`, `active_findings`, and `suppressed_findings`. Those fields mean raw findings. Do not rename them in a breaking way without a versioned API plan.

The MCP adapter exposes `raw_findings(...)` as the preferred tool name and keeps `findings(...)` as a compatibility alias for existing clients.
