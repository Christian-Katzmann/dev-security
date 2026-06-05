# app-it Migration Report

Migrated from legacy appify launcher(s) to current app-it templates during the 2026-06-02 final-batch migration.

Apps:
- Security Observatory: com.user.security-observatory, preferred port 8766, start command `bash scripts/run-dashboard.sh`
- DëvSec Design: com.user.devsec-design, preferred port 8788, start command `bash scripts/run-design-lab.sh`

Notes:
- Uses the pilot-proven native Mach-O `Contents/MacOS/run` stub plus generated `run.sh`.
- Swift wrapper is compiled without `-O` so doctor marker probes remain deterministic.
- Legacy Desktop bundle registration is handled separately during installation/verification.
- Existing non-launcher worktree changes were left untouched.

## Decision history

### 2026-06-04 — added "DëvSec Design" (second app)
- **Why:** a sealed, gitignore-free design lab (`design-lab/`) for rebuilding the product
  dashboard in the new dark design system, runnable as its own Dock app so it can sit
  beside the live Security Observatory app.
- **Strategy:** A1 native Swift WebKit shell + a static-file server start command
  (`python3 -m http.server` over `design-lab/`). No dev server, no watcher, no build step —
  the lab is zero-build (React UMD + Babel standalone + Tailwind CDN). Same wrapper as the
  main app, so it keeps its own Dock icon, single-instance, warm reattach, and Cmd+Q cleanup.
- **Icon:** `assets/devsec-design-icon.svg` (the DëvSec FocusLogo tile, white squares on dark
  green) — visually distinct from Security Observatory in the Dock.
- **Verification (headless session):** programmatic checks all pass — universal Mach-O wrapper,
  valid `AppIcon.icns`, plist id `com.user.devsec-design` with zero placeholder leakage, ad-hoc
  codesigned; start command smoke-tested (HTTP 200, correct title) then torn down;
  `desktop:doctor devsec-design` = 13 ok / 0 warn / 0 fail. GUI-only checks (window content,
  Dock icon, warm relaunch) deferred to the user. No processes left running.
- **Untouched:** Security Observatory's config, bundle, and icon (rebuild was idempotent).
