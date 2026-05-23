# 2. In-app documentation rendering — stdlib only, no external dependencies

## Status

Accepted (2026-05-23). Implements F-003 from the `walkthrough-audit-20260523-102224` punch list.

## Context

The Tool Catalog detail pages render "Read documentation" links that point at `docs/<file>.md`. The original implementation served the markdown source directly to the browser with `Content-Type: text/markdown`. Most browsers render that as a wall of plain text — `#` characters, pipe-table syntax, raw link markdown, no styling. The link looked finished but delivered nothing readable.

Two paths were considered:

- **(A)** Render the markdown in-app via a server-side Markdown→HTML converter wrapped in a DëvSec docs page shell, served at `/docs/<file>.md`.
- **(B)** Point the docs links at the public GitHub URL (e.g. `https://github.com/Christian-Katzmann/dev-security/blob/main/docs/agent-lab.md`), accepting that links break until the repo is public.

## Decision

**Path (A)** — in-app rendering — with the additional constraint that the converter uses only the Python standard library, no external dependencies.

The renderer lives in `src/security_observatory/docs_render.py`. It parses the markdown subset DëvSec's docs actually use (headings, paragraphs, lists, fenced code blocks, tables, links) and emits semantic HTML, which is then wrapped in the dashboard's docs page shell.

## Consequences

**Positive**

- The link works offline. A user can read DëvSec's docs without an internet connection — matching the local-first stance of the rest of the product.
- Python `dependencies = []` is preserved. Adding `markdown` or `mistune` would break the "zero runtime dependencies" promise that the install story rests on.
- The dashboard-ui React bundle is unchanged — no `react-markdown` dependency in the frontend.
- Docs styling is consistent with the rest of the dashboard (typography, spacing, link treatment) because the shell is the dashboard's.

**Negative**

- The stdlib-only converter supports a markdown subset, not full CommonMark. Footnotes, definition lists, and inline HTML are unsupported. If a contributor writes docs that rely on those features, the renderer silently drops them. Mitigation: docs follow a style guide that uses the supported subset.
- We own a small Markdown parser. Markdown parsing edge cases (nested lists, code blocks inside blockquotes) are routinely a source of bugs. Mitigation: only the subset of features actually used by DëvSec's docs is implemented; new features are added only when a doc actually needs them.

## Alternatives considered

**Path (B) — GitHub URL.** Cleanest implementation; near-zero maintenance; lets GitHub handle markdown rendering. Rejected because:

- Links break for the period between writing the docs and flipping the repo public.
- Once public, links break for any user without an internet connection — directly contradicting the local-first stance.
- Repo-internal docs containing references unsafe for public consumption (audit reports, plan dumps) would have to be filtered manually before each link change.

**Path (C) — bundle a JS markdown renderer in the dashboard.** `react-markdown`, `marked`, or `mistune` running in the dashboard-ui bundle. Rejected because:

- Adds 30–80 kB to the dashboard bundle for a feature most users encounter only via the catalog detail pages.
- Pushes the rendering work client-side, which is fine for the dashboard but adds complexity for headless / CLI-only docs access.
- Server-side rendering with stdlib is simpler and matches the rest of the Python CLI.

**Path (D) — pre-render docs to HTML at build time.** Run `pandoc` or similar in CI; ship pre-rendered HTML files. Rejected because:

- Requires a build step in CI that doesn't exist today.
- The "edit a doc, refresh the dashboard" loop becomes "edit a doc, run the build, refresh the dashboard" — real friction for contributors.
- The local-first stance includes "the running app is the canonical state of your repo," and pre-rendering means the running app is showing yesterday's docs.
