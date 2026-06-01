# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

> Staged for release as **0.2.0** (intended tag `v0.2.0`). `pyproject.toml` is
> already bumped to `0.2.0`; the git tag is intentionally left for a human to
> cut. When cutting, rename this heading to `## [0.2.0] - YYYY-MM-DD` and open a
> fresh `[Unreleased]` above it. This section reconciles the work that landed
> after the `v0.1.0` tag across the trust, experience, and structure campaigns.

### Added

- Guarded MCP write mode (`devsec-mcp-rw`): a separate, stdio-only adapter that
  adds case-resolution write-back (preview → apply through the audited
  resolution path) on top of the read-only surface. Suppressing a high/critical
  case is never auto-applied — it is held for explicit human confirmation.
- Guarded local-offline scan-trigger (`trigger_scan`): rescans an already-scanned
  repo by name on a fixed profile, rate-limited and network-free, behind a human
  gate.
- Clean-room code-fix flow (`propose_fix` → `clean_room_review_packet` →
  `record_clean_room_review` → `land_fix`): the reviewer sees only the diff and
  the invariants, never the finding text; `land_fix` authorizes but never
  performs a merge, and only narrow low-risk classes (action SHA pins, single
  patch/minor dependency bumps, lockfile updates) are auto-merge-eligible.
- Code-fix dashboard surface: `GET /api/fix-proposals`, `GET /api/fix-proposals/<id>`,
  and `POST /api/fix-proposals/<id>/land`, plus a "Code fixes" dashboard view —
  an operator can list proposals, read each diff and its clean-room verdict, and
  trigger a land decision, authorized only where the existing guarded boundary
  already allowed it (no new bypass; no finding text in the store).
- Scan history, posture-over-time trend, and arbitrary scan-to-scan diff in the
  dashboard: `GET /api/scan-diff?base=&head=` compares any two saved scans, with
  an honest health sparkline and a base/head picker on the Overview.
- Case lifecycle: explicit case states and follow-up handling surfaced through
  storage, the dashboard, and the MCP read surface.
- Secret rotation: rotation-status card, "rotate now" / rotate-all flows,
  emergency rotation, a guarded reset command, and a `/devsec-rotate` command.
- Tool Catalog and setup flow: catalog schema (`setup_kind`, `setup_requirement`,
  `setup_probe`), a typed `SetupCard`, the legitify Connect-GitHub PAT/OAuth
  flow, source logos with an accent palette, and a macOS Keychain
  credential-storage layer.
- Binary-trust foundation: managed scanners are verified before they run, with
  `gitleaks v8.30.1` shipping as the first managed-install proof.
- Extended MCP read surface: `honey_keys`, `scan_history`, and scan-id-aware
  `cases`, plus `rotation_status` / `rotation_history` read tools.
- Accessibility foundation across the dashboard (focus, semantics, keyboard
  reachability).
- DëvSec voice doctrine and agent safety tiers, wired into the MCP instructions
  and the slash commands.
- Two-mode dashboard infrastructure.

### Changed

- Replaced `window.prompt`-driven dashboard interactions with proper in-app UI.
- Normalized the severity vocabulary across the scanner, payload, and dashboard.
- Locked the dashboard vocabulary and resolved dashboard-coherence drift.
- Generalized the install affordance beyond Homebrew (uv-tool, manual-with-copy).
- Finished previously dead/half-built dashboard surfaces so no partial feature is
  presented as complete.
- Internal structure: extracted the scan orchestrator, split the dashboard
  server, introduced a scanner-adapter registry, and raised the type floor /
  tightened data contracts.
- Storage payload and query performance, plus dashboard frontend performance and
  bundle/code-split improvements.
- Refreshed `.adx` manifests, the risk register, and the docs so the repo's
  self-description matches the shipped code.

### Fixed

- Egress honesty: removed implied network behavior that did not match local-first
  reality.
- Dashboard CSRF / suppression gate hardening.
- Backend read-path resilience, including self-healing a corrupt SQLite history
  store instead of failing hard.
- Dashboard error surfacing for backend failures.
- Preserve unknown case confidence instead of coercing it to `medium`.
- `ai_static` no longer silently skips when the repo lives under `/tmp` on Linux.
- Resolved the React 19 / `@types/react` type mismatch in the dashboard build.

### Security

- Trust-integrity test suite covering the write-guard, prompt-injection,
  clean-room, red-team end-to-end, and corrupt-store recovery paths.
- Guarded-write boundary: high/critical case suppression is held for explicit
  human confirmation; the clean-room reviewer is fenced to diff + invariants only
  (never finding text); the auto-merge-eligible fix classes are narrow and the
  audit trail is preserved.

## [0.1.0] - 2026-05-23

### Added

- Initial public release. Local-first security scanning, dashboard, honey keys, named-campaign IOC matcher.
