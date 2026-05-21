# Security Observatory Dashboard

React source for the local dashboard.

The Python CLI still owns scanning, storage, and the `/api/summary` endpoint. This app owns the visual surface and builds static assets into `src/security_observatory/dashboard`.

## Local Development

```bash
npm install
npm run dev
```

For live data while developing, run the Python dashboard server on port `8766`.

## Production Build

```bash
npm run build
```
