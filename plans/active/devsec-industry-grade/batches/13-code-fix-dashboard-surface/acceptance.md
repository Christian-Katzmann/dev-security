# Acceptance: 13-code-fix-dashboard-surface

## Acceptance Criteria
Exactly one of the two paths below must be fully satisfied. The dashboard-surface path (A) is preferred; the documentation path (B) is the acceptable minimum and its README row is mandatory if A is not shipped.

**Path A — dashboard surface (preferred):**
- **S-043 (proposals are listable from the dashboard)** — A `GET /api/fix-proposals` route returns the persisted code-fix proposals (backed by a new `list_fix_proposals` query mirroring `list_agent_lab_proposals`), and a Mistglass dashboard view renders that list. Observable: with one or more proposals seeded in a temp DB, the route returns them and the React view lists them; `tests/test_dashboard_fix_proposals.py` asserts the list route returns the seeded proposal(s).
- **S-043 (diff + clean-room verdict are viewable)** — A per-proposal detail route (e.g. `GET /api/fix-proposals/<id>`) exposes the stored diff and the clean-room verdict/invariants, and the view renders diff → clean-room status (approved / rejected / not-yet-eligible) without ever exposing finding text. Observable: the detail route returns the diff and clean-room status for a seeded proposal; the response carries no finding-text field.
- **S-043 (land decision goes through the proven gate)** — A `POST /api/fix-proposals/<id>/land` route delegates to `fix_proposals.decide_landing`, so a dashboard land decision is authorized only when the existing boundary allows it (clean-room `approved`, matching `diff_sha256`, allowlisted fix class; protected-branch and non-eligible classes refused). Observable: `tests/test_dashboard_fix_proposals.py` shows an approved+matching proposal lands, and a protected-branch / non-approved / class-not-allowlisted proposal is refused with no auto-merge — proving the dashboard adds no path to land code that the boundary would not already allow.
- **S-043 (boundary unchanged)** — The clean-room reviewer still receives only the diff + invariants (no finding text), and `decide_landing`'s gate logic is unchanged. Observable: existing `uv run pytest tests/test_fix_proposals.py tests/test_mcp_fix_proposals.py` continue to pass unmodified.

**Path B — documented as MCP-only (acceptable minimum):**
- **S-043 (honest "real vs not yet" entry)** — The README "real vs not yet" table (`README.md:22-36`) gains a row naming the hands-off code-fix flow (`propose_fix → clean_room_review_packet → record_clean_room_review → land_fix`), stating it is real, reachable today only via the `devsec-mcp-rw` adapter, and not yet surfaced in the dashboard. Observable: the README row exists and its tool names match `mcp_server.py:1000-1090`; the confident-falsehood (a built feature invisible in the product with no honest note) is demonstrably eliminated.

## Required Checks
| Check | Why |
| --- | --- |
| `uv run pytest tests/test_dashboard_fix_proposals.py` (Path A) | Exercises the new list / detail / land routes against a seeded DB — proves the proposals surface lists, shows diff + clean-room verdict, and lands only through `decide_landing`'s gate (the matrix + synthesis "Suggested validation" for S-043). |
| `uv run pytest tests/test_fix_proposals.py tests/test_mcp_fix_proposals.py` | Proves the proven code-fix boundary (clean-room fence, `diff_sha256` binding, protected-branch refusal, auto-merge allowlist) is unchanged — the dashboard surface adds no new land path. |
| `uv run pytest` | Full Python suite stays green after the new storage query + routes (per AGENTS.md verification). |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check confirms the new `dashboard_server`/`storage` code imports clean. |
| `cd dashboard-ui && npm run build` (Path A) | TypeScript (`tsc`) + `vite build` succeed, proving the new proposals view, its fetch hooks, and types compile and bundle (the matrix validation path for S-043). |
| `cd dashboard-ui && npm run lint` (Path A) | eslint/oxlint stay clean across the new React proposals surface, per AGENTS.md frontend verification. |
| `grep -n "propose_fix\|clean_room\|land_fix" README.md` (Path B) | Proves the "real vs not yet" table now names the code-fix flow if it is documented MCP-only rather than surfaced. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
