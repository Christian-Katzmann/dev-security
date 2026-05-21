# Desktop launcher

Click **Security Observatory.app** in `~/Desktop/MyApps/` or its Dock Stack to launch the local dashboard.

## First launch

1. Right-click the app icon and choose **Open**, then click **Open** in the dialog. macOS remembers and skips this on later launches.
2. The first cold start should only take a few seconds.
3. If a launch alert appears, open `~/Library/Logs/Security Observatory/server.log`.

## App

- **Security Observatory** (`Security Observatory.app`) — local dashboard for the security scan history stored in `~/.security-observatory`.

The app uses a small Swift WebKit shell, so it keeps its own Dock icon instead of becoming a Chrome window.

## Launch behavior

- Closing the window leaves the dashboard server warm for fast relaunch.
- Cmd+Q kills the dashboard server.
- If port `8766` is busy, the launcher scans upward and records the actual port at `~/Library/Logs/Security Observatory/server.port`.

## Install / update

```bash
make desktop-build
make desktop-install
```

To stop any warm server from the terminal:

```bash
make desktop-quit
```

## Replace the icon

Replace `assets/security-observatory-icon.png`, then run:

```bash
make desktop-icons
make desktop-build
make desktop-install
```

## Known limitations

- The bundle is unsigned, so macOS Gatekeeper requires right-click -> Open on first launch.
- The project path is baked into the app. If this repo moves, rerun `make desktop-build && make desktop-install`.
- The app uses WebKit. For browser devtools, open the recorded runtime URL in a normal browser.
