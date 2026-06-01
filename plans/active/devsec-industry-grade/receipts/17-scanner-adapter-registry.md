# Implementation Receipt: 17-scanner-adapter-registry

## Target

- Plan: `plans/active/devsec-industry-grade`
- Batch: 17-scanner-adapter-registry
- Source report item(s): S-018 (Yellow → Green)

## Before Health

Scanner knowledge lived in five parallel string-keyed dispatch sites with
nothing forcing them to stay in sync — easy to wire `run_scanner` but forget a
facet:

- `EXIT_CODES_WITH_FINDINGS` standalone dict — `scanners.py:27`
- `run_scanner` per-scanner branches — `scanners.py:127`–`:153`
- `_command` if-chain — `scanners.py:362`–`:438` (`raise ValueError("Unknown scanner")` tail)
- `_timeout` branch dict — `scanners.py:727`
- `normalize()` dispatch — `normalize.py:91`–`:114`

`docs/architecture.md:17`–`:27` claimed "Each adapter owns command / timeout /
exit-code / sanitizer" co-location the code did not enforce; `docs/adding-scanners.md`
documented adding a scanner as a multi-file edit. Evidence re-verified against
the current files before changing anything.

## Changes Made

- **One adapter type, one registry.** Added a frozen `ScannerAdapter` dataclass
  (`name`, `timeout`, `exit_codes_with_findings`, `command`, `normalizer`, `run`)
  and a single `SCANNER_REGISTRY` table in `scanners.py` with exactly one entry
  per scanner — the 10 external binaries (semgrep, gitleaks, trufflehog, trivy,
  osv-scanner, syft, grype, checkov, medusa, legitify) and the 3 built-ins
  (ai-static, install-hooks, workflow-audit). 14 entries total.
- **`run` strategy field** distinguishes the generic external-binary path
  (`run=None` → `_run_external_scanner`) from built-in/bespoke scanners that
  carry their own runner (`ai-static`, `install-hooks`, `workflow-audit`,
  `legitify`). Extracted `_run_ai_static_scanner` and three thin run wrappers
  from the old `run_scanner` if-chain; `run_scanner` is now a 6-line dispatcher.
- **Every dispatch site now derives from the registry:**
  - `run_scanner` looks up the adapter (raises `ValueError("Unknown scanner")`
    for an unregistered key — error path preserved).
  - `_run_external_scanner` uses `adapter.timeout` and
    `adapter.exit_codes_with_findings`.
  - `_command` resolves `adapter.command` (split into one `_<name>_command`
    builder per scanner); raises for an unknown/commandless key.
  - `_timeout` returns `adapter.timeout` (default 300 for unknown — lenient
    `.get` semantics preserved).
  - `EXIT_CODES_WITH_FINDINGS` is now a derived view of the registry, kept as a
    public module symbol for back-compat.
  - `normalize()` in `normalize.py` defers to `scanners.normalizer_for()`
    (deferred import avoids a top-level `scanners`↔`normalize` cycle).
- **Behavior preserved byte-for-byte:** verified timeouts, exit-code sets, and
  command tails are identical to the pre-refactor values (semgrep 600/{1},
  gitleaks 300/{1}, trufflehog 600/{183}, trivy 900/{1}, osv-scanner 600/{1},
  syft 300/none, grype 600/{1}, checkov 600/{1}, medusa 180/{1}, malcontent
  900/none, legitify 600/{1}; built-ins default 300). medusa normalizer wired via
  `partial(_generic_ai, "medusa")`. syft/ai-static carry no normalizer →
  `normalize()` returns `[]`, matching old behavior.
- **Docs tell the truth:** rewrote `docs/adding-scanners.md` (add-a-scanner is
  now "one `ScannerAdapter` entry") and the `docs/architecture.md` "Scanner
  Adapter Contract" section to describe the single registry.
- **Regression guard:** added `test_scanner_registry_is_single_source_of_truth`
  (asserts the registry key set, that timeouts/exit-codes/normalizers all derive
  from the one registry, and that half-wiring is impossible) and
  `test_run_scanner_raises_for_unknown_scanner`.

Files touched:
- `src/security_observatory/scanners.py`
- `src/security_observatory/normalize.py`
- `docs/adding-scanners.md`
- `docs/architecture.md`
- `tests/test_scanners.py`

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `uv run pytest tests/test_scanners.py tests/test_normalize.py` | ✅ 25 passed | Registry-backed command/timeout/exit-code dispatch and registry-backed `normalize()` produce identical results per scanner. |
| `uv run pytest` | ✅ 520 passed (61s) | Wider suite (orchestration, storage, dashboard payload) unaffected by the re-shape. |
| `python3 -c "...import security_observatory.cli; print('ok')"` | ✅ ok | Registry imports cleanly; no import cycle through `scanners`/`normalize` (verified both import directions). |
| New single-source-of-truth test | ✅ pass | Half-wiring class of bug structurally eliminated. |
| `git diff docs/adding-scanners.md docs/architecture.md` | ✅ rewritten | Add-a-scanner path now "one registry entry"; adapter contract matches enforced structure. |

## After Health

S-018 → Green. Scanner knowledge is one co-located `ScannerAdapter` per scanner
in `SCANNER_REGISTRY`. The five former dispatch sites no longer exist as
independent per-scanner branch lists — they read from the one registry. A
scanner cannot be wired into `run_scanner` but missing from `_timeout` or
`EXIT_CODES_WITH_FINDINGS`, and a test enforces that property. Docs match.

## Remaining Risk

None for S-018. The normalizer implementations stay private in `normalize.py`
and are imported by `scanners.py` to wire the registry (the adapter "owns" its
normalizer reference); `normalize()` reaches back via a documented deferred
import. This is the intended single-registry shape, not debt.

## Downstream (campaign step 7)

Re-read batches 18–21. Batch 19 (`19-adx-and-docs-truth`) references S-018 only
as a non-goal boundary ("scanner registry S-018 … separate batches"), not as an
edit target on the old dispatch sites — accurate, no change made. Batch 21
(`21-integration-and-mcp-hygiene`) has no references to the scanner dispatch.
No surgical downstream edits were required; target S-IDs untouched.

## Next Batch

18-type-floor-and-contracts (S-021).
