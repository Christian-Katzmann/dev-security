## Appify report

**1. Project type detected:**
Python project with `pyproject.toml`, a local HTTP dashboard served by `security-scan dashboard`, bundled Vite/React dashboard assets under `dashboard-ui/`, no existing Electron/Tauri/NW.js config, no FSA usage, `swiftc` available, no git worktree detected because this directory is not currently a git repository.

**1.5. Name resolution** *(if multiple naming sources disagreed)*
Picked: "Security Observatory". Sources surveyed: folder name `dëv-security`, `pyproject.toml` project name `security-observatory`, README title, existing `scripts/appify.config.json`. Reason: README, package metadata, and existing launcher config describe the actual user-facing system. To override: edit `scripts/appify.config.json`, then `make desktop-build && make desktop-install`.

**2. Apps detected:** 1
- **Security Observatory** — single-server local dashboard, preferred port `8766`, start command `bash scripts/run-dashboard.sh`.

**3. Strategy chosen per app:**
- Security Observatory: A1 native — Swift WebKit shell.

**4. Why these are the lowest-effort robust approaches:**
The project already has a local web dashboard, so the smallest reliable desktop app is a native WebKit wrapper around the existing local server. Chrome fallback remains unnecessary because there is no Chromium-only API need, and the Swift shell keeps the Dock icon, single-instance behavior, and warm relaunch behavior clean. Electron/Tauri would add dependencies without improving this brand asset refresh.

**5. Files added/changed:**
- `assets/security-observatory-icon.png` — replaced with `/Users/christiankatzmann/Downloads/ChatGPT Image May 11, 2026, 11_39_15 PM.png`
- `assets/icons/security-observatory/...` — regenerated from the new icon source
- `assets/security-observatory-logo-new.png`
- `assets/security-observatory-logo.png` — canonical copy of the new transparent logo
- `assets/security-observatory-brand-sheet.png`
- Removed `assets/security-observatory-icon.svg` placeholder
- `dashboard-ui/public/favicon.png`, `dashboard-ui/public/apple-touch-icon.png`, `dashboard-ui/public/logo.png`
- `dashboard-ui/index.html`, `dashboard-ui/src/App.tsx`, `dashboard-ui/src/index.css`, `dashboard-ui/src/components/*.tsx` — favicon links, wordmark header, palette refresh
- `src/security_observatory/dashboard_server.py` — serves `/favicon.ico` from the bundled favicon image
- `src/security_observatory/dashboard/...` — rebuilt dashboard bundle with logo/favicon assets
- `desktop/Security Observatory.app/...` — rebuilt with the new `AppIcon.icns`
- `scripts/wrapper.swift`, `scripts/run-template.sh`, `scripts/run-template-chrome.sh`, `scripts/run-template-multiserver.sh`, `scripts/info-plist-template.xml`
- `scripts/desktop-build.sh`, `scripts/desktop-icons.sh`, `scripts/desktop-install.sh`, `scripts/desktop-quit.sh`
- `scripts/inspect.sh`, `scripts/placeholder-icon-gen.sh`
- `scripts/appify.config.json`
- `scripts/run-dashboard.sh`
- `Makefile` — desktop helper targets
- `docs/desktop-launcher.md`, `docs/desktop-launcher.appify-report.md`
- `.gitignore` — contains: `desktop/`, `assets/icons/build/`, `assets/icons/security-observatory/`

**6. Icon source per app:**
- Security Observatory: `/Users/christiankatzmann/Downloads/ChatGPT Image May 11, 2026, 11_39_15 PM.png` copied to `assets/security-observatory-icon.png` — 1254 x 1254 PNG, dedicated square app-icon source. Generated `assets/icons/security-observatory/icon_1024.png` and both repo/installed `AppIcon.icns` files from this source. Considered: existing `assets/security-observatory-icon.png`, `assets/security-observatory-logo.png`, `assets/security-observatory-brand-sheet.png`.

**7. To change an app icon later:**
Replace `assets/security-observatory-icon.png`, then `make desktop-icons && make desktop-build && make desktop-install`. The install step refreshes the Dock and Finder icon caches automatically when icon bytes change.

**8. Build / install / quit commands:**
- Build: `make desktop-build`
- Install: `make desktop-install` (-> `~/Desktop/MyApps/`)
- Quit: `make desktop-quit` (stops daemonized dashboard server)

**9. Generated launcher locations:**
- Repo: `desktop/Security Observatory.app`
- Installed: `~/Desktop/MyApps/Security Observatory.app`
- Runtime port (after first click): `~/Library/Logs/Security Observatory/server.port`

**10. Verification (per app):**
- [x] Build succeeded; `.app` exists; wrapper is universal Mach-O; `.icns` is multi-resolution
- [x] Bundle metadata correct (no `__PLACEHOLDER__` leakage)
- [x] Cold launch: `server.port` recorded; HTTP responds on runtime port `8766` with HTTP `200` over IPv4
- [x] Single instance; `lsappinfo` confirms bundle id `com.user.security-observatory`
- [x] Cmd+Q (via osascript) kills server tree
- [ ] deferred — macOS Apple Events permission: Red-X scripted close was blocked with `Not authorized to send Apple events to Security Observatory. (-1743)`. User-action one-liner: click the window close button manually; the server should stay warm, or run `make desktop-quit` to stop it.
- [x] Warm re-launch responds in `0.468s` (descendant-walk reattach works)
- [x] Install-path open exits 0; `lsregister` shows exactly one installed bundle entry
- [ ] needs human: actual `.app` window content and Dock icon identity. Browser smoke check loaded title `Dëv Security Observatory`, confirmed `/logo.png`, `/favicon.png`, and `/favicon.ico` return the new PNG assets.
- [ ] deferred — env hostile: n/a

**11. Dock Stack:**
- [x] `~/Desktop/MyApps/` exists
- [ ] User has dragged `~/Desktop/MyApps/` to the right side of the Dock (one-time setup; likely already done based on existing appified apps)

**12. Known limitations:**
- Unsigned bundle — Gatekeeper warns on first launch; right-click -> Open once.
- WebKit, not Chromium — open the runtime URL in a regular browser for Chromium devtools.
- Baked `PROJECT_ROOT` — rerun `make desktop-build && make desktop-install` if the repo moves.
- This directory is not a git repository, so `git add` staging could not be performed.
- Universal arm64+x86_64 wrapper binary was built.

## Decision history
- 2026-05-11: Initial build (Strategy A1 native, bundle-id `com.user.security-observatory`, preferred port `8766`, icon: `assets/security-observatory-icon.svg`).
- 2026-05-11: Brand refresh (Strategy A1 native unchanged, bundle-id `com.user.security-observatory`, preferred port `8766`, icon replaced with `assets/security-observatory-icon.png`; wordmark copied to `assets/security-observatory-logo.png`; brand sheet copied to `assets/security-observatory-brand-sheet.png`).
- 2026-05-11: Logo source updated to transparent high-resolution PNG (`assets/security-observatory-logo-new.png`, 4000 x 796 RGBA); canonical `assets/security-observatory-logo.png`, dashboard public `logo.png`, and bundled dashboard `logo.png` now use those bytes.
- 2026-05-11: App icon replaced from `/Users/christiankatzmann/Downloads/ChatGPT Image May 11, 2026, 11_39_15 PM.png` (1254 x 1254 PNG); rebuilt and reinstalled `Security Observatory.app`; installed `AppIcon.icns` refreshed in `~/Desktop/MyApps/`.
