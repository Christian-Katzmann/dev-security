# Implementation Receipt: 14-scan-orchestrator-extract

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 14-scan-orchestrator-extract
- Source report item(s): S-015 (Extract a `scan_orchestrator`/pipeline module from `cli.py`; break the `cli ↔ dashboard_server` cycle and the `mcp → cli` reach)

## Before Health

S-015 = Yellow. The canonical scan path `scan_repo` (~199 lines) lived in `cli.py` (the CLI presentation/entry-point module), forcing two non-CLI subsystems to import the CLI:

- `cli.py:22` top-level `from .dashboard_server import build_ai_prompt, serve_dashboard`
- `dashboard_server.py:1846` lazy `from .cli import scan_repo` (the other half of the cycle)
- `mcp_server.py:29` `from .cli import build_parser, scan_repo` (the `mcp → cli` reach)

AST cycle scan over `src/security_observatory/*.py` (top-level + `from . import` + nested/lazy import forms) — **before**:

```
Cycles: 2  →  ['catalog', 'setup_runner']  and  ['cli', 'dashboard_server']
Cycles touching cli/dashboard_server/mcp_server triangle: 1  →  ['cli', 'dashboard_server']
```

## Changes Made

Behavior-preserving relocation — no scan logic changed.

- **New module `src/security_observatory/scan_orchestrator.py`** (application layer). Moved verbatim from `cli.py`: `scan_repo`, `build_parser`, `profile_name`, `import_ioc_feeds`, `_ioc_status`, and `package_root`. It imports only domain/pipeline layers (`model`, `scanners`, `storage`, `cases`, `enrichment`, `iocs`, `sbom`, `silent_upgrades`, `platform_posture`, `recency`, `rotation`, `behavioral`) and **none** of `cli`/`mcp_server`/`dashboard_server`.
- **`cli.py`** — removed the six moved functions; now does `from .scan_orchestrator import build_parser, import_ioc_feeds, package_root, profile_name, scan_repo` (preserving the public CLI surface so `from security_observatory.cli import scan_repo/build_parser/profile_name` still works). Pruned the imports that only the moved code used (datetime/Callable, behavioral, enrichment, sbom, silent_upgrades, platform_posture, several `model`/`scanners`/`iocs`/`rotation` names). Kept the legitimate one-directional `from .dashboard_server import build_ai_prompt, serve_dashboard` (no cycle, since dashboard_server no longer imports cli).
- **`mcp_server.py:29`** — repointed `_build_scan_parser`/`_scan_repo` to `from .scan_orchestrator import ...`.
- **`dashboard_server.py`** — deleted the `:1846` lazy `from .cli import scan_repo` inside `run_check_job`; added a clean top-level `from .scan_orchestrator import scan_repo` in the import block (safe now that the cycle is gone).
- **Tests** — `tests/test_sbom.py` and `tests/test_scan_rotation_detection.py` monkeypatch `scan_repo`'s collaborators (`scanner_names_for_profile`, `run_scanner`) on the module that defines `scan_repo`. Repointed their alias from `cli` to `scan_orchestrator` (the "patch where it's used" rule). No assertions changed.
- **Downstream batch docs** — corrected now-stale references to the deleted `:1844` lazy import in `15-split-dashboard-server/context.md` and refreshed the S-015 dependency note in `17-scanner-adapter-registry/context.md`. No target S-IDs changed.

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/test_mcp_trigger_scan.py -v` | PASS | 10/10 — guarded MCP scan-trigger still drives the relocated `scan_repo` |
| `python3 -c "...import security_observatory.cli; print('ok')"` | PASS | fast import check, cli imports cleanly after the move |
| `uv run python3 -c "...import dashboard_server, mcp_server, scan_orchestrator..."` | PASS | all three consumers + orchestrator import together under uv |
| AST dependency/cycle scan over `src/security_observatory/*.py` | PASS | triangle cycles **0** (see After Health); `catalog ↔ setup_runner` left untouched (out of scope) |
| `grep "from .cli import\|from .dashboard_server import" cli.py mcp_server.py dashboard_server.py` | PASS | only `cli.py:19 from .dashboard_server import build_ai_prompt, serve_dashboard` remains; no `from .cli import` in either non-CLI module |
| `uv run python3 -m security_observatory.cli --help` | PASS | public CLI entry point still works |
| `uv run pytest` | PASS | 516 passed in ~62s |

## After Health

S-015 = Green. AST cycle scan — **after**:

```
Cycles: 1  →  ['catalog', 'setup_runner']   (out of scope, untouched)
Cycles touching cli/dashboard_server/mcp_server triangle: 0
```

Triangle edges after the move:
- `cli → ... scan_orchestrator, dashboard_server ...` (one-directional to dashboard_server; no return edge)
- `dashboard_server → ... scan_orchestrator ...` (no `cli`)
- `mcp_server → ... scan_orchestrator ...` (no `cli`)

`scan_orchestrator` imports zero entry-point modules. The `cli ↔ dashboard_server` cycle and the `mcp → cli` reach are eliminated.

## Remaining Risk

None for S-015. The `catalog ↔ setup_runner` cycle is a separate seam explicitly out of this batch's scope and was left intact. This was a pure relocation: scan output is byte-for-byte identical (same functions, same call order); the full suite confirms no collateral breakage.

## Next Batch

15-split-dashboard-server (S-016) — its context.md was updated to note S-015 has landed and to import `scan_repo` from `scan_orchestrator`, not `cli`.
