# Implementation Receipt: 13-code-fix-dashboard-surface

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 13-code-fix-dashboard-surface
- Source report item(s): S-043 (hands-off code-fix flow reachable only via MCP rw; no dashboard surface)

## Before Health

S-043 = Yellow. The propose → clean-room-review → land flow (`fix_proposals.py`)
was fully built, fenced, and test-pinned but reachable **only** through the
`devsec-mcp-rw` adapter (`mcp_server.py:1031-1120`). No `/api/*` route or React
component surfaced it, so a dashboard-only operator could not see or act on a
code-fix proposal. Two tests actively **encoded** the gap, asserting the
dashboard source must not reference the flow at all:
`test_mcp_fix_proposals.py::test_dashboard_http_surface_does_not_expose_fix_tools`
and `test_red_team_e2e.py::test_http_dashboard_surface_exposes_no_write_or_trigger_tool`.

Re-verified evidence against current files:
- `fix_proposals.py` still exposes `propose_fix`, `clean_room_review_packet`,
  `record_clean_room_review`, `decide_landing`, with the clean-room fence
  (`build_review_packet`) and the diff-bytes-only classification intact.
- `storage.py` **already** had `list_fix_proposals` (`storage.py:2123`) — the
  evidence's "no list query" had since been added; no storage change needed.
- README "real vs not yet" table (`README.md:26-36`) still omits the flow.

## Changes Made

Shipped **Path A — the dashboard proposals surface** (the preferred path),
read-mostly and fenced; the land path delegates to the proven gate.

Backend (`src/security_observatory/dashboard_server.py`):
- `GET /api/fix-proposals` — lists persisted proposals via the existing
  `db.list_fix_proposals`, projected to a list row (`_fix_proposal_summary`):
  no diff body, no finding text.
- `GET /api/fix-proposals/<id>` — detail (`_fix_proposal_detail`): the stored
  diff, the recorded clean-room verdict, and the diff-class invariant checklist
  (`invariants_for`). Carries no finding text — the store holds none.
- `POST /api/fix-proposals/<id>/land` — `decide_fix_landing` delegates to
  `fix_proposals.decide_landing`. The dashboard adds **no** new land path: the
  gate (clean-room `approved` + matching `diff_sha256` + allowlisted re-derived
  class; protected-branch refusal) is unchanged and unbypassable.
- New path regexes; routes wrapped by the existing top-level GET error handler.

Frontend:
- New Mistglass view `dashboard-ui/src/components/FixProposalsView.tsx`
  (list → diff → clean-room verdict → land decision), mirroring the existing
  view shape. Boundary chips make the read-mostly fence explicit.
- Wired a new "Code fixes" nav tab in `App.tsx` (TabId, navGroups, tabTitles,
  viewsByMode, render switch, `GitPullRequest` icon).

Tests:
- New `tests/test_dashboard_fix_proposals.py` (7 cases): list returns seeded
  proposals; detail exposes diff + clean-room + invariants with no finding text;
  approved+allowlisted+hash-matching lands (`auto_merge`); non-approved →
  `requires_human`; non-allowlisted class (`source_change`) → `requires_human`;
  protected branch → `blocked`.
- Updated the two guard tests that encoded the now-closed gap. Their genuine
  security intent is preserved and strengthened: the dashboard never gains the
  authoring half (`propose_fix` / `clean_room_review_packet` /
  `record_clean_room_review` absent from source), never imports `mcp_server`,
  and routes landing only through `decide_landing`. The red-team test passes
  **unmodified** (the dashboard method is `decide_fix_landing`, not the MCP
  `land_fix` tool name).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/test_dashboard_fix_proposals.py` | PASS | 7 passed — list/detail/land routes against a seeded DB. |
| `uv run pytest tests/test_fix_proposals.py tests/test_mcp_fix_proposals.py` | PASS | Boundary (fence, hash binding, protected-branch refusal, allowlist) unchanged. |
| `uv run pytest` | PASS | 516 passed. |
| `python3 -c "...import security_observatory.cli; print('ok')"` | PASS | Clean import of new dashboard/storage code. |
| `cd dashboard-ui && npm run build` | PASS | tsc + vite build green; bundle emitted to served assets. |
| `cd dashboard-ui && npm run lint` | PASS | `tsc --noEmit` clean. |

## After Health

S-043 = Green. The hands-off code-fix flow is now honest and reachable from the
dashboard: an operator can list proposals, read each diff and its clean-room
verdict, and trigger a land decision — which is authorized only where the proven
boundary already allowed it. The clean-room fence and the auto-merge gate are
untouched; the dashboard surfaces the existing guarded flow, adding no bypass.

## Remaining Risk

None for S-043. Two pre-existing guard tests were updated because they asserted
the *absence* of the surface this batch intentionally adds; the genuine
fence/gate security tests in `test_fix_proposals.py` /
`test_mcp_fix_proposals.py` round-trip pass unchanged. Built dashboard assets
(`dashboard/assets/`) are gitignored per repo convention; only the
`index.html` hash reference is committed (as in prior dashboard batches).

## Next Batch

Last implementation batch of Stage B. Full Python suite + dashboard build green.
