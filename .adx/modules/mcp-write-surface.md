# MCP Write Surface

Primary source paths: `src/security_observatory/mcp_server.py`, `src/security_observatory/fix_proposals.py`, `src/security_observatory/case_followup.py`, `src/security_observatory/decisions.py`, and the `mcp/` adapter docs.

This module is the guarded write side of the MCP adapter. The read-only `devsec-mcp` server (11 tools) and the write-enabled `devsec-mcp-rw` server are both built here; `-rw` adds eight write-mode tools on top: the `devsec.case_resolutions.v1` follow-up/preview/apply trio (`case_followup_prompt`, `preview_case_resolutions`, `apply_case_resolutions`), a rate-limited network-free local rescan (`trigger_scan`), and the propose → clean-room-review → land code-fix flow (`propose_fix`, `clean_room_review_packet`, `record_clean_room_review`, `land_fix`). Case-decision logic lives in `decisions.py` / `case_followup.py`; the fix-proposal lifecycle lives in `fix_proposals.py`.

The full write boundary — what each tool can and cannot do — is documented in [`mcp/README.md`](../../mcp/README.md) ("Guarded write mode"); treat that as the source of truth for the surface.

Verification:

- Start with `python-import-cli`.
- Run `python-pytest` for the suite: `tests/test_mcp_server.py`, `tests/test_fix_proposals.py`, `tests/test_mcp_fix_proposals.py`, `tests/test_case_followup.py`, `tests/test_mcp_trigger_scan.py`, and `tests/test_red_team_e2e.py` cover this surface.
- The adapter is stdio-only; do not run it as a network service.

Risks:

- This is a write path in a security tool — see `.adx/risks.json` `mcp-write-surface`. Only `devsec-mcp-rw` (explicit opt-in) exposes it.
- Suppressing a high/critical case is never auto-applied; it is held for explicit human confirmation.
- The clean-room reviewer sees only the diff and invariants, never finding/case text; `land_fix` authorizes a merge but never performs it.
