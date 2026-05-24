# Step 0.2 receipt

Status: implemented and verified on 2026-05-24.

Changes shipped:
- Dashboard selector click target now covers the full workspace control.
- Toolbar exposes Choose, Run quick, and Run all as separate top-level actions.
- Critical severity badges are visually stronger than Elevated.
- Overview Open findings KPI uses the raw severity total instead of a loaded-row cap.
- Recent Activity mini-chart now mirrors the six visible activity rows.
- Findings keeps whole-repo prompt as a global action and makes the case action copy per-case markdown.
- Case detail displays the table-style case ID instead of the raw internal ID.
- Doctor output separates optional missing scanners from common-scan missing scanners.
- README dashboard tab list matches the live navigation.

Verification:
- `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"`
- `python3 -c "import sys; sys.path.insert(0, 'src'); from security_observatory.cli import main; raise SystemExit(main(['doctor']))"`
- `cd dashboard-ui && npm run lint`
- `cd dashboard-ui && npm run build`
- `uv run pytest`
- Playwright screenshots captured under `reports/campaign-automation/devsec-dashboard-coherence/visuals/`.

Notes:
- No per-case prompt endpoint was needed. The saved case payload already carries `agent_prompt`; the dashboard copies a case-scoped markdown prompt client-side.
- `runFullCheck` remains the only top-level full-scan fire path. The new Choose action opens the sheet without firing, and Run quick fires only the quick profile.
