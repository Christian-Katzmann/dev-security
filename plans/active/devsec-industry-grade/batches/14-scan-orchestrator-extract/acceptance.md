# Acceptance: 14-scan-orchestrator-extract

## Acceptance Criteria
- **S-015 (orchestrator module exists):** `scan_repo` (and the parser/profile resolution it needs to stand alone — at minimum `build_parser` and `profile_name`) now lives in a dedicated application-layer module (e.g. `src/security_observatory/scan_orchestrator.py`), not in `cli.py`. The new module imports only domain/pipeline layers (`model`, `scanners`, `storage`, etc.) and imports **none** of the entry-point modules `cli`, `mcp_server`, or `dashboard_server`.
- **S-015 (`cli ↔ dashboard_server` cycle eliminated):** A dependency/cycle scan over `src/security_observatory/*.py` (top-level + `from . import` forms, as in the lens report) reports **zero** cycles involving the `cli`/`dashboard_server`/`mcp_server` triangle — specifically the `cli → dashboard_server → cli` cycle the lens report found at `cli.py:22` ↔ `dashboard_server.py:1844` is gone.
- **S-015 (`mcp → cli` scan reach removed):** `mcp_server.py` no longer imports `scan_repo`/`build_parser` from `cli` (the `mcp_server.py:29` `from .cli import ...` scan reach is repointed at the orchestrator module). `dashboard_server.py` no longer imports `scan_repo` from `cli` (the `dashboard_server.py:1844` lazy `from .cli import scan_repo` is repointed at the orchestrator).
- **S-015 (public CLI surface preserved):** `python -m security_observatory.cli --help` still works and any code/tests that do `from security_observatory.cli import scan_repo` / `build_parser` / `profile_name` still import successfully (via re-export or direct import from the orchestrator) — no caller is broken by the move.
- **S-015 (behavior unchanged):** The MCP `trigger_scan` path and the dashboard scan path produce the same scans as before — this is a pure relocation. The existing `tests/test_mcp_trigger_scan.py` suite passes unchanged, proving the guarded scan-trigger still routes through the relocated append-only `scan_repo` path.

## Required Checks
| Check | Why |
| --- | --- |
| `uv run pytest tests/test_mcp_trigger_scan.py -v` | The matrix/synthesis-named validation for S-015: proves the guarded MCP scan-trigger still drives the relocated `scan_repo` and that the `mcp_server` import repoint did not break the scan path. |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check per AGENTS.md that `cli` (which re-exports/imports from the new orchestrator) still imports cleanly after the move. |
| `uv run python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.dashboard_server, security_observatory.mcp_server, security_observatory.scan_orchestrator; print('ok')"` | Proves all three repointed consumers and the new orchestrator module import cleanly together (uv env is authoritative for `mcp_server` per AGENTS.md). |
| Re-run the lens report's dependency/cycle scan (AST/regex over `src/security_observatory/*.py`) and assert the `cli ↔ dashboard_server` cycle is absent | Direct evidence of the matrix validation "re-run cycle scan → 0 cycles" for the cli/dashboard/mcp triangle; the headline structural claim of S-015. |
| `grep -n "from .cli import\|from .dashboard_server import" src/security_observatory/cli.py src/security_observatory/mcp_server.py src/security_observatory/dashboard_server.py` | Evidence that the entry-point cross-imports that formed the cycle/reach (`cli.py:22`, `mcp_server.py:29`, `dashboard_server.py:1844`) no longer point the wrong way through `scan_repo`. |
| `uv run pytest` | Full Python suite green per AGENTS.md — confirms the relocation caused no collateral breakage across the scan, MCP, dashboard, and CLI tests. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
