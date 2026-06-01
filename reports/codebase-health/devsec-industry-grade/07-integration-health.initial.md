# Integration Health Forensic — DëvSec (Security Observatory)

## Executive Finding

DëvSec's integration layer is, for a security tool that sells trust, unusually
disciplined and honest. The dominant pattern is **fail-closed, surface-the-gap**:
every external system — local scanner binaries (subprocess), the four read-only
enrichment endpoints (CISA KEV, EPSS, OpenSSF Scorecard, OpenSSF Criticality),
the managed-tool downloader, the legitify GitHub-PAT auth path, and the inbound
Honey Key listener — has a timeout, normalizes provider failure into a stable
"not_checked / skipped / unavailable / stale" contract, never blocks the scan,
and (critically) **says so in the UI**. A missing or errored scanner does not
silently produce zero findings: it taints the scan `status` to `partial`
(`cli.py:307`), becomes an explicit evidence-gap row with a remediation path
(`cases.py:208`), and renders in the dashboard's "Checks that ran / Skipped or
not installed / Cannot prove" panel with the honest headline "A clean result is
useful, but it is not a promise that everything is safe"
(`ScanCompletenessPanel.tsx:60`). The trust-critical integration guarantees —
honest degradation, tampered-binary refusal, verifier-rejected-vs-verifier-absent,
no-network trust enrichment, idempotent SQLite writes, and the guarded MCP scan
trigger — are each protected by tests that fail if the guarantee breaks (86
integration tests pass). No silent-egress path exists on the default scan: all
four enrichment endpoints are gated behind an explicit `--trust` opt-in
(`cli.py:226`), and the MCP trigger forces every egress flag off
(`mcp_server.py:579-582`). The only blemishes are a small wiring gap (CISA
KEV/EPSS lookups are implemented and documented as "fail-closed online checks"
but are unreachable — no CLI flag wires `check_cisa_kev`/`check_epss`) and the
absence of retry/backoff on outbound calls (correct-by-design for optional,
cache-backed reads, but worth a one-line note). Lens verdict: **Green/Yellow**.

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security`
- Skill/lens: `integration-health-forensic`
- Date: `2026-06-01`
- Requested focus: Per the Excellence Brief's integration-health domain risk cue —
  "Each scanner adapter: does it degrade *honestly and legibly* when the tool is
  missing or errors, rather than silently producing zero findings — and does the
  UI say so?" Extended in practice to every external/service boundary: scanner
  subprocesses, the four network enrichment endpoints, the managed-tool
  download/verify pipeline, the legitify auth-provider path, setup-card probes,
  inbound Honey Key handling, SQLite write idempotency, and the guarded MCP scan
  trigger. Read-only audit; respects the Brief's "Out of scope" (External Surface
  stays an honest Coming Soon and is not penalized).

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli"` | Pass (`import-ok`) | Fast import check per AGENTS.md Verification. |
| `uv run pytest tests/test_scanners.py tests/test_enrichment.py tests/test_trust_enrichment.py tests/test_managed_tools.py tests/test_verification.py tests/test_setup_runner.py tests/test_honey_keys.py -q` | Pass (86 passed in 4.58s) | Covers honest-degradation, tampered-binary refusal, cosign verifier-absent-vs-rejected, no-network trust enrichment, legitify token-absent skip, Honey Key hashing/redaction. All mocked; no live provider calls. |
| Live provider calls (KEV/EPSS/Scorecard/Criticality, GitHub PAT, downloads) | Not run | Forbidden by skill guardrail `#cross-lens-no-live-calls` and `.adx/risks.json`. Resilience verified by code + mocked tests, not live traffic. |
| Scanner/dashboard/installer/desktop execution | Not run | `.adx/risks.json` dangerous-command patterns; AGENTS.md operating rules. |

## Ranked Health Table

| Rank | Area | Health | Confidence | Evidence | Impact (user/operational) | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | CISA KEV / EPSS enrichment: implemented + documented but unreachable (no caller wires `check_cisa_kev`/`check_epss`) | Green/Yellow | High | `enrichment.py:128-151` defines the flags defaulting `False`; the only internal call (`enrichment.py:521`) passes neither; no CLI flag exists (`cli.py:67-68` only wire `--trust`/`--trust-cache-only`); `docs/scanners.md:41` describes them as active "optional online checks" | A documented capability never runs. Not a false claim (docs describe the mechanism, which is correct) and not silent egress (the path is dead), but a reader could expect KEV/EPSS to be applied. Dead opt-in surface invites drift. | Either wire the flags to a CLI/scan opt-in and surface the result, or mark them clearly as not-yet-wired in `docs/scanners.md`. Coordinate with documentation-health and feature-health lenses. | `uv run pytest tests/test_enrichment.py`; grep for any caller passing `check_cisa_kev=True` |
| 2 | Outbound calls have timeouts but no retry/backoff/circuit-breaker | Green/Yellow | High | `_fetch_json`/`_fetch_bytes` single-attempt with `timeout` (`enrichment.py:1039-1055`); `download_bytes` single-attempt + max-bytes cap (`managed_tools.py:526-542`); no `retry`/`backoff`/`sleep` loops anywhere in `enrichment.py`/`managed_tools.py`/`scanners.py` | Low: all outbound reads are optional and cache-backed; a transient failure degrades to `not_checked`/stale, never a hang or a blocked scan. Correct-by-design for this product (no write-side provider integrations exist). Flagged only so it is a recorded decision, not an oversight. | None required for the scan path. If the managed-tool *download* (a one-shot, user-initiated install) is ever made unattended, a single bounded retry on transient network error would reduce install friction. Document the "single attempt, fail-closed" decision. | Code read; `tests/test_managed_tools.py` exercises download failure → `ManagedToolInstallError` |
| 3 | Network enrichment egress gating (KEV/EPSS/Scorecard/Criticality) | Green | High | `allow_network=False` default on `scorecard_lookup`/`criticality_lookup`/`epss_lookup`/`cisa_kev_lookup` (`enrichment.py:261,319,633,600`); scan path only sets `allow_network=True` when `--trust` and not `--trust-cache-only` (`cli.py:226`); `enrich_dependency_trust` docstring states "The default scan path does not call this function" (`enrichment.py:165-170`); MCP forces `args.trust=False` (`mcp_server.py:579`) | No source, findings, or repo identifiers leave the machine on any default path. Opt-in is explicit and per-call. Directly satisfies the Brief's "no silent egress" non-negotiable for this lens's surface. | None. Keep `allow_network` default `False` invariant under test. | `uv run pytest tests/test_trust_enrichment.py` (asserts `not_checked` when `allow_network=False`) |
| 4 | Scanner-missing / scanner-error honest degradation + UI surfacing | Green | High | `status.available` from `shutil.which` (`scanners.py:177`); unavailable → empty `ScannerResult` + explicit `error` (`scanners.py:182-186`); non-zero exit not in `EXIT_CODES_WITH_FINDINGS` → `status.error` set (`scanners.py:205-206`); scan→`partial` if any errored/unavailable (`cli.py:307`); `scanner_evidence_gaps` builds per-scanner gap rows with reason + tool/profile/pack remediation (`cases.py:208-243`); UI panel renders ran/missing/error/not-run (`ScanCompletenessPanel.tsx`, `dashboardData.ts:440,1907-1963`); honest copy "not a promise that everything is safe" (`ScanCompletenessPanel.tsx:60`); coverage line "before clean results mean much" (`dashboardData.ts:1958`) | This is the Brief's central integration cue, met end-to-end: a missing tool never masquerades as a clean result; the UI names the gap and the fix. Excellent, not merely present. | None. | `uv run pytest tests/test_scanners.py` (`...uses_runtime_binary_detection_not_catalog_metadata` asserts exact error; `...skips_with_helpful_error_when_no_token` asserts `skipped`) |
| 5 | Managed-tool download → verify → install pipeline (origin-proof, not safety) | Green | High | `download_bytes` max-bytes + timeout (`managed_tools.py:526-542`); `verify_managed_download` tries cosign then falls to checksum floor (`verification.py:323-337`); ChecksumProvider raises on mismatch (`verification.py:200-204`); CosignProvider pins cert identity + OIDC issuer and confirms artifact digest is in signed checksums (`verification.py:227-320`); shim writes refuse to overwrite non-DëvSec binaries (`managed_tools.py:557-569`); `PROOF_SAFETY_CAVEAT` "describes where the binary came from, not that it is safe to run" (`verification.py:60`); tampered managed binary → scanner `skipped` (`scanners.py:158-169`) | A compromised upstream artifact is blocked (raise), an absent verifier degrades honestly to the checksum floor with a setup note, and the tool never claims "safe" from "signed". Trust-airtight on the install boundary. | None. | `uv run pytest tests/test_verification.py tests/test_managed_tools.py` (mismatch/invalid-sig/missing-from-checksums all raise; cosign-absent is a setup gap) |
| 6 | Guarded MCP `trigger_scan` (write-mode scan trigger) | Green | High | Repo resolved by NAME from scan history, never a raw caller path (`mcp_server.py:629-632`); profile validated against fixed `SCAN_PROFILES` enum (`mcp_server.py:624-628`); per-repo 10-minute cooldown returns structured `rate_limited` (`mcp_server.py:590-642`); `_scan_args` forces `trust`/`trust_cache_only`/`behavioral_drift`/`platform_posture`/`full` off (`mcp_server.py:578-583`); routes through existing append-only `scan_repo` (`mcp_server.py:644`); "No parameter is derived from finding text" (`mcp_server.py:621`) | The highest-leverage AI write path cannot reach an arbitrary filesystem path, cannot trigger network egress, and cannot be scan-spammed. Matches the Brief's "guarded local-offline scan, by name, fixed profile, rate-limited." | None (cross-ref permission-boundary lens for the broader MCP write surface). | Code read; cross-check with permission-boundary-health report |
| 7 | SQLite write idempotency (retries/reruns do not duplicate) | Green | High | `save_scan` uses `insert or replace into scans` and `delete from findings where scan_id = ?` before re-insert, inside one transaction `with self.conn:` (`storage.py:914-941`); child tables keyed by `scan_id` with replace semantics; scan ids are append-only per run | A re-saved or retried scan cannot double-count findings or corrupt history. Satisfies the skill's "retries that do not duplicate writes" cue. | None. | Code read; `tests/test_storage.py` (storage suite, not re-run here) |
| 8 | legitify GitHub-PAT auth-provider isolation | Green | High | Token read from macOS Keychain only at subprocess launch (`scanners.py:603-617`, `credentials.py:360-394`); "never touches disk, shell history, or a config file" (`credentials.py:372-375`); token-absent → `skipped` with setup guidance, not a crash (`scanners.py:473-484`); legitify payload sanitized via `sanitize_legitify_payload` + `redact_text` before write (`scanners.py:502-503`, `platform_posture.py:51,231-239`); legitify is opt-in via `--platform-posture` | The only auth-provider integration leaks neither the PAT nor finding text into reports/logs, and degrades to a helpful skip when unconfigured. | None. | `uv run pytest tests/test_scanners.py` (keychain read / env fallback / unsupported-host / no-token skip) |
| 9 | Setup-card probes (shell / binary-version / http / directory) | Green | Medium | `_run_subprocess` uses `shell=True` but command is catalog-authored with credentials injected via env, not interpolated (`setup_runner.py:425-446`, comment 432-435); HTTP probe validates scheme + bounds output (`setup_runner.py:375-417`); all probes timed out; credential-absent probes return a clear "paste the value and Store" result (`setup_runner.py:303-314`) | Probes cannot be steered by user paste into shell injection, and a missing credential is a legible message, not a failure. Medium confidence only because `shell=True` correctness rests on the catalog never templating user input — true today but a standing invariant. | Keep the "no user input in probe command strings" invariant under review when the catalog grows. | `uv run pytest tests/test_setup_runner.py tests/test_dashboard_setup_endpoints.py` |
| 10 | Inbound Honey Key listener + decoy callbacks | Green | High | Decoy tokens point to the LOCAL listener `{base_url}/api/honey/trigger` where base_url=`http://127.0.0.1:8876` (`honey_keys.py:135-136`, AGENTS.md memory); HMAC-signed tokens, SHA-256 hashed storage (`honey_keys.py:49-96`); inbound request headers/body sanitized + honey-material redacted (`honey_keys.py:175-212`); dashboard binds `127.0.0.1` only (`dashboard_server.py:4228`) | The "callback" is an attacker hitting the user's *local* listener — the intended honeytoken design, not outbound egress. No external port is opened; trigger evidence is redacted. Honest and local-first. | None (cross-ref privacy-boundary lens). | `uv run pytest tests/test_honey_keys.py`; code read of bind address |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| CISA KEV / EPSS enrichment flags exist but are wired to no caller | `enrich_dependency_finding(check_cisa_kev, check_epss)` default `False` (`enrichment.py:133-134`); no CLI flag; only internal caller passes neither (`enrichment.py:521`) | An implemented, network-capable code path that is currently unreachable. Harmless today (dead → no egress) but it is exactly the kind of half-wired surface that becomes a confident-falsehood or silent-egress risk if a future change flips it on without a UI opt-in. Should be either wired-with-surfacing or documented as not-yet-active. |
| Six outbound endpoints, each a single network dependency | `CISA_KEV_URL`, `EPSS_URL`, `SCORECARD_API_TEMPLATE`, `CRITICALITY_OBJECTS_URL` + object base (`enrichment.py:18-25`); managed-tool `release_base_url` + cosign sidecars (`verification.py:148-163`) | All are read-only and opt-in, but they are the complete egress inventory for the privacy-boundary lens to confirm against the trust-boundary diagram. Each has a 4–6s timeout and fail-closed handling; none is on a default path. Recording them here so the inventory is explicit and reviewable. |
| `start_new_session=True` process-group kill on scanner timeout/exception | `scanners.py:200,213-215,678-684` | Scanner subprocesses are launched in a new session and the whole process group is SIGKILLed on timeout/exception. Good operational hygiene (no orphaned scanner children), but it is a process-control behavior worth knowing for anyone debugging a hung scan — it is not surfaced in user-facing docs. |
| legitify target auto-derived from `git remote.origin.url` | `_legitify_target`/`_repo_target_from_remote` (`scanners.py:562-600`) | When `--platform-posture` runs, the repo's GitHub `owner/repo` (derived from the local git remote) is sent to GitHub's API with the user's PAT. This is opt-in and expected for a platform-posture scan, but it means an identifier (the repo slug) leaves the machine on that explicit path. Privacy-boundary lens should confirm the UI makes this visible at opt-in time. |

## Top Repair Targets

1. **Resolve the CISA KEV / EPSS wiring gap (Rank 1).** Decide: either wire
   `check_cisa_kev`/`check_epss` to an explicit opt-in (mirroring `--trust`) and
   surface the KEV/EPSS result in cases/UI, or update `docs/scanners.md:41` to
   state these online checks are designed-but-not-yet-wired. Pick one so promise
   and code agree. Cross-cut with documentation-health and feature-health.
2. **Record the "single attempt, fail-closed, no retry" decision for outbound
   calls (Rank 2).** Add a one-line rationale near the enrichment/download
   fetchers (or in `docs/scanners.md` / the trust-boundary doc) so the absence of
   retry/backoff reads as a deliberate local-first choice, not an omission. If
   managed-tool installs ever go unattended, add a single bounded retry on
   transient network error only.
3. **Lock the setup-probe `shell=True` invariant (Rank 9).** Add a focused test
   (or a guard) asserting that no catalog-authored probe command string contains
   user-supplied config values, so the "command cannot be steered by a paste"
   property cannot silently regress as the tool catalog grows.

## SocratiCode Value

SocratiCode was not used. Per the suite standard's cost-discipline rule, the
integration surface here was small and precisely locatable by direct means: the
egress and subprocess inventory came from a single targeted grep
(`subprocess|requests|urllib|httpx|socket|urlopen`), and the remaining work was
exact-file reads (`scanners.py`, `enrichment.py`, `verification.py`,
`managed_tools.py`, `mcp_server.py`, `honey_keys.py`, `credentials.py`,
`setup_runner.py`) plus the React mapping (`dashboardData.ts`,
`ScanCompletenessPanel.tsx`) and a focused pytest run. A structural map would not
have improved confidence over reading the actual call sites and their tests.

## Limits

- **No live provider traffic.** KEV/EPSS/Scorecard/Criticality fetches, GitHub
  PAT auth, managed-tool downloads, and cosign verification were verified by code
  inspection and the repo's mocked/fixture tests only — never by live calls
  (skill guardrail + `.adx/risks.json`). Real provider 5xx/timeout/redirect/
  malformed-payload behavior is therefore inferred from the `except (OSError,
  TimeoutError, URLError, JSONDecodeError)` handlers, not observed.
- **No scanner/dashboard/installer execution.** Honest-degradation and the
  evidence-gap UI were verified by reading `cli.py` + `cases.py` + the React
  components + the passing `tests/test_scanners.py`, not by running a real scan
  with a tool removed from PATH.
- **Storage idempotency** was verified from `save_scan`'s SQL and transaction
  structure; `tests/test_storage.py` was not re-run in this session (only the
  integration-relevant suites were), so the idempotency claim rests on code
  evidence plus the documented replace semantics rather than a fresh test run.
- **`shell=True` setup-probe safety** depends on the standing invariant that the
  tool catalog never templates user input into a probe command; that invariant
  holds in the current catalog but was not exhaustively proven across every
  catalog entry, hence Medium confidence on Rank 9.
- Frontend lint/build (`npm run lint`/`npm run build`) were not run; the React
  evidence is source-read only, since this lens's findings are server/contract
  side and the UI claims are about presence and wording of honest states.
