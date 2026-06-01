# Dashboard Pages

Primary source path: `src/security_observatory/dashboard_pages.py`

Two dashboard surfaces render as standalone HTML, parallel to the React app:
the `/report/` export page (AI-handoff prompt + full raw report) and the
`/docs/` shell. They live here, out of the request handler, so
`dashboard_server` stays a routing layer rather than also being a second
templating engine. Every function here is pure: it takes a scan/doc payload
and returns a string (or bytes, for the raw export).

Verification:

- Start with `python-import-cli`.
- Run `python-pytest`; `tests/test_dashboard_report_exports.py` and `tests/test_cases.py` cover the rendered output.

Risks:

- The report page renders local scan output; do not paste or upload full reports casually (`local-security-data` in `.adx/risks.json`).
