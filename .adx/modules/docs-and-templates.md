# Docs And Templates

Primary paths: `docs/`, `README.md`, `templates/`

This module holds human-facing setup, scanner explanations, troubleshooting, desktop launcher notes, Honey Key guidance, and the optional GitHub Actions workflow template.

Verification:

- Validate any edited JSON/YAML if applicable.
- No project tests are required for prose-only changes unless commands or templates change.

Risks:

- Keep docs aligned with `.adx/commands.json` when command behavior changes.
- The CI template installs scanner tools from package managers and remote installers; treat changes there as security-relevant.
