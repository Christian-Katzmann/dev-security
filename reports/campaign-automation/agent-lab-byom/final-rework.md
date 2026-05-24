# Agent Lab BYO AI Final Rework

Run time: 2026-05-24T10:10:18+00:00

## Gaps Addressed

- Tightened proposal list-field validation in `src/security_observatory/agent_lab.py`.
- Present but non-list `requested_permissions`, `requested_execution[].tool_ids`, and `recommended_tools[].safety_labels` now fail validation instead of being silently treated as omitted.
- Present but empty `requested_execution[].tool_ids` now fails validation instead of expanding to the whole scan profile.
- Omitted `requested_execution[].tool_ids` still intentionally defaults to the allowed tools for the selected scan profile.

## Files Changed

- `src/security_observatory/agent_lab.py`
- `tests/test_agent_lab.py`
- `reports/campaign-automation/agent-lab-byom/final-rework.md`

## Verification Run

- `uv run pytest tests/test_agent_lab.py` -> 14 passed
- `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` -> ok
- `uv run pytest` -> 187 passed

## Remaining Gaps

- None identified from the final review's NEEDS WORK list.

## Final Review Rerun

- Yes. The whole-campaign final review should be rerun now.
