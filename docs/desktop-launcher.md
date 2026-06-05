# Desktop Launcher

This project is configured with app-it for Dock-launchable macOS apps:

- **Security Observatory** — the live product dashboard (port 8766, `bash scripts/run-dashboard.sh`).
- **DëvSec Design** — the sealed design lab in `design-lab/`, served static (port 8788, `bash scripts/run-design-lab.sh`). Open it next to Security Observatory to compare the new dark UI against the live app side by side.

- Build: `./scripts/desktop-build.sh` (or the repo's `desktop:build` script when present).
- Install: `./scripts/desktop-install.sh` copies the app bundle(s) to `~/Applications/App It/`.
- Quit: `./scripts/desktop-quit.sh` stops app-it-managed launcher processes for this project.
- Diagnose: `./scripts/desktop-doctor.sh <slug>` (`security-observatory` or `devsec-design`).

Both bundles use the native Swift WKWebView wrapper: click to open, red-X leaves the local static/dev server warm, **Cmd+Q** tears it down. First launch of an unsigned bundle: right-click → Open once.
