# Contributing

Thanks for your interest in DëvSec. This is a small, opinionated project — please read this before opening a large PR.

## Local setup

The full installation steps (scanners, Python CLI, dashboard assets) live in [`README.md`](README.md#installation). The short version:

```bash
./install-security-observatory.sh
```

The installer is idempotent. It uses Homebrew for compiled scanners and `uv` for Python CLIs.

## Running the tests

```bash
uv run pytest                   # Python test suite
cd dashboard-ui && npm run lint # Dashboard lint
cd dashboard-ui && npm run build # Dashboard build
```

All three must pass before a PR is mergeable.

## Filing issues and PRs

- Issues: include the command you ran, the output you saw, and what you expected. Logs from `~/.security-observatory/logs/` help.
- PRs: keep them small and focused. One concern per PR. Describe the user-visible change and link any related issue.
- For UI work, read [`DESIGN.md`](DESIGN.md) first. The dashboard follows the Mistglass design system: calm UI, sentence case, no looping motion, one primary action per surface, mono type reserved for telemetry.
- For agent-facing work, follow [`AGENTS.md`](AGENTS.md) and the contracts under `.adx/`.

## Security disclosure

Do not open public issues for security bugs. See [`SECURITY.md`](SECURITY.md) for the disclosure path.
