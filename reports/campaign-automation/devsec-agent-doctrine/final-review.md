# APPROVED

The devsec-agent-doctrine campaign delivered its stated intent with no material
gaps.

Evidence checked:

- `docs/agent-voice.md` exists at 514 lines, includes the five principles,
  DëvSec vocabulary, dual-axis `Action: <action_level> · Severity: <severity>`
  examples, local-first voice guidance, technique/profile/before-after sections,
  interaction patterns A-J, Pattern F as Security Brief, Pattern J for Honey Key
  triggers, anti-patterns, final guide, and compact MCP instructions. No
  bibliographic citations or blocked corporate phrasing were found.
- `docs/agent-safety.md` exists at 234 lines and defines all six tiers with
  examples, default behavior, language templates, confirmation language where
  needed, voice-doctrine cross-reference, and the LLM-boundary caveat.
- `src/security_observatory/mcp_server.py` uses the compact doctrine in
  `DEVSEC_MCP_INSTRUCTIONS`; the instructions are 26 lines and point to
  `docs/agent-voice.md` and `docs/agent-safety.md`.
- `mcp/README.md` documents that the JSON-RPC initialize response advertises
  the compact voice doctrine.
- All existing `/devsec-*` command files have the required voice treatment or,
  for `/devsec-voice`, directly print the doctrine primer and point to both
  full docs. `/devsec-pr` carries the Tier 3 note and preserves the read-only
  DëvSec store boundary.
- `/devsec` includes the `/devsec-voice` commands-menu row.
- `campaigns/devsec-agent-doctrine/notes/observed-output.md` is present and
  substantive. It records fresh non-persistent command runs, observed openings,
  drift, calibration edits, and a voice-calibration approval.

Verification run:

- `uv run pytest tests/test_mcp_server.py -q` — 29 passed.
- JSON-RPC initialize smoke via `uv run devsec-mcp` — initialize response
  included the compact instructions and `tools/list` returned the eight expected
  read-only tools.

No rework items.
