# DëvSec MCP adapter

A read-only [Model Context Protocol](https://modelcontextprotocol.io) server
that lets local agents (Claude Desktop, Cursor, Codex, any MCP-capable client)
ask focused questions about the scan history sitting in your local
`~/.security-observatory/` database. Stdio-only, no network listener, no write
tools, no telemetry. The same posture as the rest of DëvSec.

## What it exposes — and what it doesn't

Six read-only tools wrap existing query methods on `ObservatoryDB` and the
case-builder vocabulary in `cases.py`. The adapter does not add new query
logic, mutate state, or open a network port. See
[../docs/threat-model.md](../docs/threat-model.md) for the project's overall
attack-surface posture; the adapter inherits it.

## Install

```bash
uv sync --extra mcp
```

This pulls in the official `mcp` Python SDK (FastMCP) and registers the
`devsec-mcp` script entry point in the local uv-managed venv.

Verify it starts:

```bash
uv run devsec-mcp <<< '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

You should see a single line of JSON listing six tools.

## Connect — Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or the equivalent on your OS, then restart Claude Desktop:

```json
{
  "mcpServers": {
    "devsec": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/dev-security",
        "run",
        "devsec-mcp"
      ]
    }
  }
}
```

Replace the path with the absolute path to your local checkout.

## Connect — Cursor / Codex / generic MCP client

Same shape as the Claude Desktop config — most clients accept the
`{command, args}` form. For Cursor, the file is `~/.cursor/mcp.json`. For
Codex, add the server to your `~/.codex/config.json` `mcp_servers` section.
The launch command is identical: `uv --directory <repo> run devsec-mcp`.

## The six tools

| Tool | What it returns |
|---|---|
| `list_repos` | Repositories with scan history, with last-scan timestamps. |
| `latest_scan(repo)` | Most recent scan summary: timing, scanner count, finding count, health score, status. |
| `findings(repo, severity?, limit?)` | Raw findings from the latest scan. Filter by severity. |
| `cases(repo, status?)` | Action-level cases — the project's primary unit of value. Each carries a plain-English risk read, suggested steps, and an agent-ready handoff prompt. Filter by `open` / `verified` / `accepted_risk` / `resolved`. |
| `recovery_playbook(category)` | The category-specific recovery playbook (steps, estimated minutes, and a ready-to-paste agent prompt). No DB access needed. |
| `dependency_trust(repo)` | OpenSSF-style trust enrichments per dependency, when collected. |

Paths returned to the agent are repo-relative wherever possible. Absolute
home-directory paths are never returned — the operator's username never leaves
the local machine via this surface.

## Hard limits — deliberate, not yet-to-do

- **Read-only.** No `mark_resolved`, `add_note`, `delete_*`, or any tool that
  mutates state. The store is your source of truth; the adapter does not
  touch it.
- **Local-only.** Stdio transport only. No `--http`, no `--sse`, no port
  listening. The consumer is a parent process (your MCP client), not the
  network.
- **No new query methods.** The adapter wraps what `ObservatoryDB` already
  exposes. If a question needs a new query, that's a separate piece of work
  — bring it to the storage layer first.
- **No telemetry.** No analytics, no "phone home." This is a local-first
  project; the MCP adapter is local-only too.

## Why no write tools yet

Writes in a security tool need explicit thinking about agent safety. An agent
that can mark findings as resolved, dismiss cases, or rotate Honey Keys is an
agent that can also accidentally erase evidence or close incidents that
shouldn't be closed. We chose to ship the read surface first, get it in use,
and design the write surface separately — with confirmation, audit, and
scope-limited tools. No dates promised; the read surface is useful on its
own, and writes are deferred until they can be shipped with the same care as
the rest of the project.
