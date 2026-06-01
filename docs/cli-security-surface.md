# Security-Sensitive CLI Surface

`security-scan --help` lists the scan flags but deliberately hides the verbs and
flags that write, delete, or suppress. This page documents that surface so it is
not code-only. Everything here is derived from `src/security_observatory/cli.py`
and `src/security_observatory/scan_orchestrator.py`; line numbers are pinned to
the current tree.

## Destructive and write verbs

| Command | What it does | Guard (code) |
| --- | --- | --- |
| `security-scan reset <repo>` | Permanently deletes all local observatory data (SQLite rows + report files) for a repo. This is the factory reset. | Requires a typed confirmation phrase unless `--yes` is passed (`cli.py` `reset_command`, the `input()` prompt at ~:616–627). |
| `security-scan cases import-resolutions --repo <r> --input <f> --apply` | Writes AI case decisions (`devsec.case_resolutions.v1`) through the audited case-decision path. | `--preview` validates and audits without writing; only `--apply` mutates. Suppressing a high/critical case is refused unless `--confirm-suppression` is also passed (`cli.py` ~:385, ~:416). |
| `security-scan cases prompt --repo <r> --action <a> --scope <s>` | Builds a bounded AI follow-up prompt for open cases. Read-only (no store mutation). | — |
| `security-scan vex-import` / `security-scan vex-export` | Imports / exports local VEX case decisions for a repo. | Uses `--repo`, `--input`/`-i`, `--output`/`-o`. Import writes decisions; export only reads. |

## Suppressed (hidden) flags

These are registered with `argparse.SUPPRESS` so they do not clutter
`--help` (`scan_orchestrator.py:73–84`). They are real and accepted:

| Flag | Used by | Notes |
| --- | --- | --- |
| `--action`, `--scope`, `--case-id` | `cases prompt` | Select which open cases the follow-up prompt covers. |
| `--preview` | `cases import-resolutions` | Validate + audit a resolution payload without applying it. |
| **`--apply`** | `cases import-resolutions` | **Writes** case decisions. Irreversible without a re-scan. |
| **`--confirm-suppression`** | `cases import-resolutions` | Authorizes suppressing **high/critical** cases in the batch. Without it, those suppressions are held and refused, not silently applied. |
| `--include-rotation-scaffold` | `reset` | Also removes the secrets-rotation scaffold during a reset. |
| **`--backup-to <path>`** | `reset` | Writes a backup before deletion — the only safety net once a reset runs. |
| **`--yes`** | `reset` | Skips the typed confirmation phrase. Pair with care; this makes `reset` non-interactive and immediate. |

The bold flags gate destructive or irreversible behavior. Treat
`--apply`, `--confirm-suppression`, `--yes`, and `--backup-to` as the
human-confirmation boundary; do not pass them on behalf of a user without
intent.

## Verbs that are *not* on the CLI (common confusion)

Some write operations live on **other** surfaces, not the `security-scan` CLI.
Naming them here so an agent does not invent a non-existent verb:

- There is **no `factory-reset` verb** — factory reset is `security-scan reset`.
- There is **no `case-decision` or `resolve-cases` verb** — CLI case writes go
  through `cases import-resolutions`. `case-decision` is a *dashboard* API route
  (`/api/case-decision` in `dashboard_server.py`), not a CLI command.
- There is **no `propose-fix`, `land-fix`, `review-fix`, or
  `clean-room-review` CLI verb** — the propose → clean-room-review → land
  code-fix flow is **MCP-write-only**, exposed as the `devsec-mcp-rw` tools
  `propose_fix`, `clean_room_review_packet`, `record_clean_room_review`, and
  `land_fix`. See [../mcp/README.md](../mcp/README.md) "Guarded write mode".
