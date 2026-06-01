# Acceptance: 17-scanner-adapter-registry

## Acceptance Criteria
- **S-018 (single registry exists):** There is one keyed scanner registry in `src/security_observatory/scanners.py` (a dataclass/`Protocol` entry per scanner) where each entry co-locates that scanner's command builder, timeout, exit-codes-with-findings, and normalizer reference. Every scanner the code previously knew — the external binaries (`semgrep`, `gitleaks`, `trufflehog`, `trivy`, `osv-scanner`, `grype`, `checkov`, `malcontent`, `legitify`, `medusa`) and the built-ins (`ai-static`, the install-hook scanner, the workflow scanner) — is registered exactly once.
- **S-018 (dispatch sites read from the registry):** `run_scanner`, `_command`, `_timeout`, and the `EXIT_CODES_WITH_FINDINGS` lookup in `scanners.py`, plus the `normalize()` dispatch in `normalize.py`, resolve their per-scanner behavior from the one registry rather than their own parallel `if scanner == ...` chains. The standalone `EXIT_CODES_WITH_FINDINGS` dict (was `scanners.py:27`) and the long `_command`/`_timeout`/`normalize` if-chains (was `scanners.py:362`–`:438` / `:727` and `normalize.py:91`–`:114`) no longer exist as independent per-scanner branch lists — they derive from the registry.
- **S-018 (no behavior change):** Each scanner's command line, timeout, exit-codes-with-findings, and normalized findings are byte-for-byte identical to before the refactor. The "Unknown scanner" error path is preserved for an unregistered key (a `ValueError`/raise still occurs rather than silently returning empty). `uv run pytest tests/test_scanners.py tests/test_normalize.py` passes unchanged, and the full `uv run pytest` suite stays green.
- **S-018 (half-wiring is now impossible / regression guard):** A test asserts the registry's key set is the single source of truth — i.e. the set of scanners known to command-building, timeout, exit-code, and normalization is one and the same set (a scanner cannot be wired into `run_scanner` but missing from `_timeout` or `EXIT_CODES_WITH_FINDINGS`). This is the structural property that made S-018 Yellow.
- **S-018 (docs tell the truth):** `docs/adding-scanners.md` and the `docs/architecture.md` "Scanner Adapter Contract" section (the "Each adapter owns command / timeout / exit-code / sanitizer" claim near `architecture.md:17`–`:27`) are updated so they describe adding a scanner as one co-located registry entry — the documented path now matches the enforced structure instead of overstating co-location.

## Required Checks
| Check | Why |
| --- | --- |
| `uv run pytest tests/test_scanners.py tests/test_normalize.py` | Matrix + synthesis validation path for S-018; proves the registry-backed command/timeout/exit-code dispatch and the registry-backed `normalize()` produce identical results per scanner. |
| `uv run pytest` | Confirms the wider suite (orchestration, storage, dashboard payload that transitively touches scanners) is unaffected by the re-shape. |
| `python3 -c "import sys; sys.path.insert(0, 'src'); import security_observatory.cli; print('ok')"` | Fast import check per AGENTS.md; proves the registry introduction imports cleanly and did not create an import error or cycle through `scanners`/`normalize`. |
| New test asserting registry key-set is the single source of truth (scanners known to command/timeout/exit-code/normalize are one identical set) | Proves the half-wiring class of bug is structurally eliminated — the core reason S-018 was Yellow. |
| `git diff docs/adding-scanners.md docs/architecture.md` shows the add-a-scanner path rewritten to "one registry entry" | Proves the documentation was brought in line with the new single-seam structure, not left overstating the old per-facet contract. |

## Receipt
When complete, write a receipt using:
`/Users/christiankatzmann/Dev/skills/codebase-health-kit/templates/implementation-receipt.md`
Save it under this plan's `receipts/` directory.
