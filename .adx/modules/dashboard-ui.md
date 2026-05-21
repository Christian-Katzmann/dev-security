# Dashboard UI

Primary source path: `dashboard-ui/`

This module is the React/Vite dashboard source. It consumes the Python dashboard API and builds static assets that are served from `src/security_observatory/dashboard/`.

Useful files:

- `dashboard-ui/src/App.tsx`
- `dashboard-ui/src/dashboardData.ts`
- `dashboard-ui/src/components/`
- `dashboard-ui/src/index.css`
- `dashboard-ui/package.json`

Verification:

- Use `dashboard-lint` after TypeScript/React edits.
- Use `dashboard-build` when the bundled dashboard output should be refreshed.

Risks:

- Do not hand-edit `dashboard-ui/node_modules/`.
- Treat `src/security_observatory/dashboard/assets/` as generated output from the Vite build.
