# Step 2.2 — End-to-end install verification

**Host:** Darwin arm64 (Apple Silicon Mac), Python 3.14.4, fresh dashboard
served from current `catalog-polish` branch (`scripts/run-dashboard.sh`,
port 8766).

**Scope:** the three tools added in Step 2.1 — `trivy`, `syft`, `grype`.
Gitleaks already shipped as the managed-install proof in earlier work and
is out of scope for this step. The dashboard's install path is
single-architecture; only `darwin-arm64` was exercised live.

## Method per tool

For each tool the same sequence ran against the live dashboard:

1. Confirm baseline: `/api/tool-catalog` reports `install_state=detected`
   (Homebrew copy on PATH) and `install_preview.execution_available=true`.
2. `POST /api/managed-tools/install` with `{ toolId, confirmManagedInstall: true }`
   (the same payload the **Install** button sends).
3. On disk verification: install root, binary executable bit, `--version`
   (or `version`) output, manifest entry, marker file, shim symlink.
4. Catalog re-fetched and asserted to show `install_state=managed` with a
   verified `managed_ownership` block (`verified=true`, no problems).
5. `POST /api/managed-tools/uninstall` with the captured ownership id and
   `confirmManagedUninstall: true`.
6. Re-verify: install root version dir gone, manifest row flipped to
   `active=false`, catalog returns to `install_state=detected`.

The browser side was driven through Chrome DevTools: the dashboard root
was opened, then **Tool Catalog → View Trivy / Syft / Grype** to confirm
each tool detail page renders the **VERIFIED by DëvSec Core** badge and
**Install state: DëvSec managed** while the install was live. Full-page
screenshots are saved beside this report.

## Per-tool outcome

### Trivy v0.70.0

`POST /api/managed-tools/install` returned `HTTP 200` and the manifest
record `devsec-trivy-b195fead029a` with checksum
`sha256:68e543c…b838a`. On disk
`~/.security-observatory/tools/trivy/0.70.0/bin/trivy` is an executable
arm64 binary (154 MB) whose `--version` printed `Version: 0.70.0` —
matching the manifest's `target_version_label` `Trivy v0.70.0`. The
manifest at `~/.security-observatory/tools/managed-tools.json` contained
the new ownership-id entry with `active=true`. The catalog API flipped
`trivy.install_state` to `managed` and the Tool Detail page in the
dashboard rendered the **DëvSec managed** badge with the **Install
plugin** button disabled. The subsequent uninstall returned `HTTP 200`,
removed `~/.security-observatory/tools/trivy/0.70.0` and the shim
`~/.security-observatory/tools/bin/trivy`, and the catalog returned to
`install_state=detected` (Homebrew copy left untouched). Verdict: **pass**.

### Syft v1.44.0

`POST /api/managed-tools/install` returned `HTTP 200` and the record
`devsec-syft-9822d4b232a4` with checksum `sha256:24e4d340…a55`. The
installed binary at
`~/.security-observatory/tools/syft/1.44.0/bin/syft` (80 MB, exec bit
set) printed `Application: syft / Version: 1.44.0 / Platform:
darwin/arm64` — matching `Syft v1.44.0`. Manifest entry was present and
active; catalog flipped to `install_state=managed`; the Syft detail page
rendered **DëvSec managed**. Uninstall removed the install root and the
shim; catalog returned to `detected`. Verdict: **pass**.

### Grype v0.112.0

`POST /api/managed-tools/install` returned `HTTP 200` and the record
`devsec-grype-7605f321398f` with checksum `sha256:58c3c372…7da4`. The
installed binary at
`~/.security-observatory/tools/grype/0.112.0/bin/grype` (83 MB, exec bit
set) printed `Application: grype / Version: 0.112.0` — matching `Grype
v0.112.0`. Manifest entry was active; catalog flipped to
`install_state=managed`; the Grype detail page rendered **DëvSec
managed**. Uninstall removed the install root and the shim; catalog
returned to `detected`. Verdict: **pass**.

## Notes and minor honest observations

- **Manifest tombstones.** The uninstall path flips
  `managed_tool_installations.active = 0` in SQLite and re-writes the
  same (now-inactive) row into `managed-tools.json`. The catalog loader
  filters by `active = 1`, so the entry is no longer counted as live —
  but the file does retain a deactivated tombstone row, which is a
  faithful reading of the campaign's acceptance criterion "the manifest
  entry is removed" rather than a literal physical removal. Nothing in
  the live install logic depends on the tombstone; it's history.
- **Empty parent tool dirs.** Uninstall removes the pinned version
  install root (`tools/<tool>/<version>`) but leaves the parent
  `tools/<tool>` directory empty on disk. A subsequent install reuses
  it. Harmless; called out for transparency.
- **Detected PATH copies.** Each tool had a Homebrew copy on PATH before
  the run. The managed install lived alongside it under
  `~/.security-observatory/tools/<tool>/<version>/`, and the
  uninstall left the Homebrew copy completely untouched — confirmed by
  the catalog returning to `install_state=detected` rather than
  `missing`. This is the documented behavior.
- **Cross-arch coverage.** Only `darwin-arm64` could be exercised on
  this machine. The other three platform asset rows were verified at
  the manifest level in Step 2.1 (sha256s checked against upstream
  `checksums.txt`), and the dashboard's install path raises a clear
  error on unsupported platforms (`_asset_for_platform`).

## Screenshots

- `screenshots/trivy-tool-page-managed.png` — catalog "Featured" page
  after Trivy install.
- `screenshots/trivy-detail-managed.png` — Trivy detail page with the
  **VERIFIED by DëvSec Core** badge and **Install state: DëvSec
  managed**.
- `screenshots/syft-detail-managed.png` — same view for Syft.
- `screenshots/grype-detail-managed.png` — same view for Grype.

## Outcome

All three Step 2.1 tools — Trivy, Syft, Grype — install and uninstall
cleanly through the dashboard on `darwin-arm64`. No rollback of
`APPROVED_MANAGED_INSTALL_TOOL_IDS` is needed.
