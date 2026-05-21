# Desktop Launcher

Primary source path: `scripts/`

This module builds and manages the macOS desktop app wrapper for the local dashboard. It includes icon generation, app bundle build/install, launch templates, a Swift WebKit wrapper, and cleanup scripts.

Useful files:

- `scripts/appify.config.json`
- `scripts/desktop-build.sh`
- `scripts/desktop-install.sh`
- `scripts/desktop-quit.sh`
- `scripts/run-dashboard.sh`
- `scripts/wrapper.swift`
- `docs/desktop-launcher.md`

Verification:

- Use `desktop-build` for launcher source changes.
- Use `desktop-install` only when the installed app must be refreshed.
- Use `desktop-quit` after launcher testing to stop warm servers.

Risks:

- `desktop-quit` intentionally terminates local processes that match launcher ports and wrapper windows.
- `desktop-install` copies app bundles into `~/Desktop/MyApps/` and may refresh Dock state.
- The app bakes the project path into the bundle.
