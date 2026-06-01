# Privacy Boundary Health Forensic — DëvSec (Security Observatory)

## Executive Finding

DëvSec's privacy boundary is, on its core promise, genuinely strong and demonstrable
from the code: the default scan path makes zero network calls, all outbound HTTP is
gated behind explicit `allow_network` / `--trust` opt-ins, detected secrets are scrubbed
at the model layer before they ever reach SQLite, the dashboard binds to `127.0.0.1`
only and suppresses HTTP access logs, the MCP adapter is stdio-only with an enforced
path-anonymization invariant covered by a test, credentials live in the macOS Keychain
(never plaintext), Honey Key trigger metadata is redacted and stays on the local
machine, and there is no telemetry/analytics library anywhere in the tree (Homebrew
analytics is actively disabled during tool installs). The one real default-path egress
that contradicts the product's headline trust claim is the **Google Fonts `@import` in
the shipped dashboard CSS** (`src/security_observatory/dashboard/assets/index-DXDjm9a7.css`),
which fires an outbound request to `fonts.googleapis.com` (and `fonts.gstatic.com`)
every time the dashboard renders — an un-opted-in third-party call that the
trust-boundary diagram explicitly claims does not exist ("no third-party API call").
This leaks the user's IP and visit timing to Google but not source, findings, or
secrets, so it is a trust-narrative drift, not a catastrophic data leak. A few smaller
items (EPSS sends CVE IDs to a third party under `--trust`; the path-leak test uses a
`startswith`-only assertion; managed-tool binary downloads are real egress not named in
the trust diagram) round out the picture. No non-negotiable failure mode (silent source
egress, leaked secrets, dropped findings, unsafe AI write) was found on the privacy axis.

## Scope

- Repo: `/Users/christiankatzmann/Dev/Projects/dëv-security`
- Skill/lens: `privacy-boundary-health-forensic`
- Date: `2026-06-01`
- Requested focus: Per the Excellence Brief's `privacy-boundary` domain risk cue —
  *trace every network-capable call; prove no source/findings/telemetry leave on a
  default path; confirm Scorecard / Honey Key / enrichment callbacks are opt-in and
  visibly so.* Graded against the Brief's non-negotiable failure modes (silent egress,
  confident falsehood, unsafe AI write, broken trust on destructive ops) and its
  "Definition of excellent" trust bar, not the generic Green floor. External Surface and
  runnable packs are out of scope (honest "Coming Soon").

## Validation Run

| Check | Result | Notes |
| --- | --- | --- |
| `python3 -c "import sys; sys.path.insert(0,'src'); import security_observatory.cli"` | Pass | Fast CLI import check per AGENTS.md; exit 0, "cli import ok". |
| `uv run pytest tests/test_honey_keys.py tests/test_trust_enrichment.py tests/test_enrichment.py -q` | Pass | 25 passed in 1.31s. Covers no-network default (`allow_network=False` → `not_checked`), Honey Key metadata redaction, KEV cache-only behavior. |
| `grep` outbound HTTP call sites (`urlopen`/`Request`/`requests.`/`httpx`) across `src/`, `mcp/` | Pass (read-only) | Only 3 modules make real outbound calls: `enrichment.py`, `managed_tools.py`, `setup_runner.py`. All others use `urllib.parse`/`urllib.error` (non-network). |
| `grep` telemetry/analytics libs (sentry/posthog/mixpanel/segment/GA/datadog) in `src/`, `dashboard-ui/src/` | Pass | None present. `HOMEBREW_NO_ANALYTICS=1` actively set during managed installs. |
| `grep` external hosts in built dashboard bundle (`src/security_observatory/dashboard/assets/`) | **Drift found** | `https://fonts.googleapis.com` present as live `@import` in shipped CSS. |
| `git ls-files` for committed secrets/DBs/reports | Pass | No `.db`, `.sqlite`, `.env`, or credential JSON committed; runtime data lives under `~/.security-observatory`. |
| Live network calls to Scorecard / EPSS / CISA / Google to verify behavior | Not run | Prohibited by skill cross-lens "no live calls" guardrail and `.adx/risks.json`. Behavior inferred from code + offline tests only. |

## Ranked Health Table

| Rank | Area | Health | Confidence | Evidence | Impact (user/privacy) | Next repair target | Validation path |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Dashboard loads Google Fonts from third-party CDN on default render path | Yellow/Red | High | `dashboard-ui/src/index.css:1` `@import url('https://fonts.googleapis.com/css2?family=Geist...')`; the same import survives into the **shipped** bundle `src/security_observatory/dashboard/assets/index-DXDjm9a7.css` (verified present, exactly 1 `@import`). The trust-boundary diagram (`design/diagrams/trust-boundary.md:40-49`) asserts "there is no upload path, no third-party API call, no telemetry endpoint" by default, and `README.md:69` says reports "never leave the machine." | Every dashboard open silently contacts Google (IP + visit timing + referer), with no opt-in and no UI disclosure — directly contradicting the headline trust claim a skeptical security engineer would check first. Not source/findings/secret egress, so not the worst class, but it is an un-opted-in third-party call the docs deny exists. | Self-host the Geist/Geist Mono fonts as local `@font-face` assets bundled under the dashboard build (Vite), remove the remote `@import`, and rebuild so the served CSS contacts no external host. | After rebuild: `grep -r googleapis src/security_observatory/dashboard/assets/` returns nothing; `cd dashboard-ui && npm run build`. |
| 2 | Default scan path is fully offline; all enrichment egress gated behind explicit opt-in | Green | High | Default scan never calls trust enrichment (`enrichment.py:167-170` docstring + `cli.py:220-226`: network only when `--trust` and not `--trust-cache-only`). `scorecard_lookup`/`criticality_lookup`/`epss_lookup`/`cisa_kev_lookup` all default `allow_network=False` and return `not_checked`/`unavailable` offline (`enrichment.py:261,319,600,633`). Tests assert this: `test_trust_enrichment.py:44-57`, `test_enrichment.py:41-53`. Trust-boundary diagram documents the three opt-ins (`design/diagrams/trust-boundary.md:51-95`). | The product's central privacy promise — "if I run this tool, where does my code go? It doesn't." — holds for the default path. Source code never crosses; enrichment requires a deliberate flag. | None (healthy). Keep the no-network default test as a regression guard. | `uv run pytest tests/test_trust_enrichment.py tests/test_enrichment.py` (already green). |
| 3 | Detected secrets redacted at model layer before persistence | Green | High | `model.py:42-45` `TOKEN_RE` matches `sk-`, `ghp_`, `github_pat_`, `xox[baprs]-`, `AKIA…`, and 32+ char high-entropy strings; `Finding.__post_init__` (`model.py:87-122`) runs `redact_text` over title, remediation, and ~25 evidence fields at construction time; `SecurityCase` redacts title, risk, affected_files, fix_steps, agent_prompt (`model.py:161-175`). | A scanner that surfaces a live API key never writes that key to SQLite history in plaintext — the highest-value secret-leak vector is closed at the boundary, not patched downstream. | Minor: `TOKEN_RE` scrubs secrets/high-entropy strings but not free-text PII (emails, names) in titles/remediation. Consider a follow-up email/name redaction pass if findings can carry user identities. | Add a unit test feeding a known secret into `Finding(...)` and asserting `[REDACTED]` in the persisted row (partial coverage exists via red-team e2e). |
| 4 | MCP adapter is stdio-only with enforced path anonymization | Green | High | `mcp_server.py:3-10` docstring: stdio-only, no network listener (no `HTTPServer`/`bind`/`socket` present — verified by grep). `_redact_path` (`mcp_server.py:138-176`) makes paths repo-relative or strips `/Users/<name>`; applied to `path` and `affected_files` (`:218,243`). Path-leak invariant test `test_mcp_server.py:969-1044` asserts no `/Users/`, `/home/`, `/root/` prefix in MCP output (passes). | The AI-handoff / MCP surface — the brief's highest-leverage trust risk — cannot leak the operator's username or absolute paths, and exposes no network port. | The path-leak test asserts only `startswith` (an absolute path embedded mid-string would slip through). Harden the test to substring scanning and ensure `_redact_path` is applied to any free-text field that could embed an absolute path. | Extend `test_mcp_server.py` invariant to `prefix in text` (not just `startswith`); re-run `uv run pytest tests/test_mcp_server.py`. |
| 5 | Credentials stored in macOS Keychain, never plaintext; local index holds names only | Green | High | `credentials.py:193-214` routes every secret through the macOS `security` CLI (`add-generic-password`); `_run_security` (`:200-205`) is documented never to log the secret value; the local JSON index (`_write_index`, `:151-160`) stores only `{tool_id: [key_names]}`, no values. Doc match: `docs/credentials.md:105-117` ("no remote store, no telemetry that touches…", values "do not leave the device"). | Connected-platform tokens (GitHub/GitLab) are protected at rest by the OS keystore, and a leaked local index reveals only which credentials exist, not their values. | None (healthy). | `uv run pytest tests/test_credentials.py tests/test_dashboard_credentials_endpoints.py` (not run this pass; safe to run). |
| 6 | Honey Key trigger metadata redacted; callback stays on local machine | Green | High | `honey_keys.py:175-208`: `sanitize_headers` allowlists 8 safe headers and redacts auth/cookie/secret headers; `summarize_body` stores only JSON key names + redacted sensitive keys, never raw bodies, and runs `redact_text` + `redact_honey_material`. Decoy snippets point `trigger_url`/`open_url` at `base_url` = the local dashboard (`dashboard_server.py:3237-3238` → `request_base_url()` → `127.0.0.1`). Trust diagram is candid that DëvSec operates no callback infra (`design/diagrams/trust-boundary.md:76-92`). Test `test_honey_keys.py:174`. | When an attacker uses a leaked decoy secret, the captured forensic record cannot itself become a PII/secret leak, and the beacon never phones home to a vendor. | None (healthy). The trust diagram's "you configure the webhook" framing is slightly ahead of the shipped local-only default; documentation lens should confirm no over-claim. | Cross-ref documentation-health for the webhook-config claim vs. shipped local trigger. |
| 7 | Local data deletion (`reset`) is comprehensive and guarded; honey events auto-prune | Green | Medium | `reset.py:303-374` deletes across all child tables (findings, SBOM, dependency manifests, trust enrichments, posture snapshots), case_decisions, agent_lab_proposals, honey_key_events + honey_keys, project status, scans, **and** the filesystem report dir (`shutil.rmtree`), behind a confirmation-phrase guard (`:37-59`). Retention: `storage.py:1324-1325,2186-2200` prune honey_key_events at a configurable 90-day default. | A user who resets a repo's history actually removes derived artifacts and report files, not just the parent row — deletion is real, not cosmetic. Honey-event retention is bounded and exercised. | Minor: the `dependency-trust`/KEV/criticality caches under `~/.security-observatory/cache/` are not cleared by per-repo reset, but they hold only public threat-intel (no personal data), so not a privacy gap. No test was confirmed exercising the full filesystem cleanup. | Add/verify a reset test asserting the report dir is removed and all named tables return 0 rows. |
| 8 | Dependency-trust / EPSS opt-in sends repo identifiers and CVE IDs to third parties | Green/Yellow | High | Under `--trust`: Scorecard sends the dependency's **public source repo** identifier in-URL (`enrichment.py:286` `_scorecard_url(repo)`); EPSS sends CVE IDs in the query string (`enrichment.py:643`, `epss_lookup`). CISA KEV downloads the **whole feed** with no per-CVE query (`enrichment.py:609-610`) — privacy-preserving. Managed-tool downloads pull binaries from GitHub release URLs (`managed_tools.py:65,105,147,194,526-542`). | These are public package/vuln identifiers, not the user's private source or findings, so impact is low. But under `--trust` a third party (api.first.org / api.scorecard.dev) learns *which* CVEs and dependency repos the user is researching — worth surfacing in the UI as part of the opt-in disclosure. | Ensure the dashboard's `--trust` opt-in copy names exactly what crosses (CVE IDs to EPSS, source-repo IDs to Scorecard, binary downloads from GitHub) so the egress is "visibly so in the UI" per the brief. | Cross-ref behavioral-ux / documentation lenses for the opt-in disclosure text. |
| 9 | No telemetry/analytics; dashboard binds localhost-only and suppresses access logs | Green | High | No sentry/posthog/mixpanel/segment/GA/datadog import anywhere (`grep` across `src/`, `dashboard-ui/src/`). `dashboard_server.py:4228` binds `("127.0.0.1", port)` (never `0.0.0.0`); `log_message` is a no-op (`:2035-2036`), suppressing default HTTP access logs that would otherwise record honey-key tokens/paths to stderr. `HOMEBREW_NO_ANALYTICS=1` set during managed installs (`:2009`). | Zero background usage tracking; the dashboard is not reachable off-host; request URLs (which can carry tokens) are not logged. The absent-paths design the trust diagram leans on is real. | None (healthy). | Manual: confirmed by static inspection; no safe runtime check needed. |

## Undocumented Or Hidden Surfaces

| Surface | Evidence | Why it matters |
| --- | --- | --- |
| Google Fonts CDN fetch on every dashboard load | `src/security_observatory/dashboard/assets/index-DXDjm9a7.css` contains live `@import url('https://fonts.googleapis.com/css2?...')`; source at `dashboard-ui/src/index.css:1`. Not listed among the three opt-ins in `design/diagrams/trust-boundary.md`. | A default-path third-party network call (Google) that the trust diagram explicitly says does not exist. Highest-priority privacy-narrative drift; an external auditor watching network traffic on first dashboard load would immediately see a request the docs deny. |
| Managed-tool binary downloads from GitHub releases | `managed_tools.py:65,105,147,194` (gitleaks/trivy/syft/grype release URLs) + `download_bytes` (`:526-542`). User-initiated install action (`install_managed_tool_files` `:315`), not on the default scan path (`cli.py` only uses read-only `managed_tool_evidence`/`resolve_managed_scanner_binary`). | Real outbound egress to GitHub that is *not* named among the trust diagram's three opt-ins. It is user-initiated (so not "silent"), but the trust diagram's "three things can cross" list is incomplete — a fourth (tool acquisition) exists. Worth a one-line mention so the diagram stays exhaustive. |
| EPSS query reveals researched CVEs to api.first.org | `enrichment.py:643` builds `EPSS_URL?cve=CVE-...,CVE-...`. Only under `--trust`. | Under the opt-in, a third party learns the exact set of vulnerabilities present in the user's dependencies. Public IDs, low sensitivity, but it is finding-adjacent metadata crossing the boundary and should be in the opt-in disclosure. |
| `setup_runner.py` HTTP probe to a catalog-configured URL | `setup_runner.py:375-384` `_run_http_probe` issues `urllib.request` to a probe URL from the tool catalog. | A catalog-driven outbound call path. Scope-limited to setup verification, but it is a network surface reachable from catalog data; confirm probe URLs are always first-party/health-check, never user-data carriers. |

## Top Repair Targets

1. **Eliminate the Google Fonts default-path egress (Rank 1, Yellow/Red).** Self-host
   Geist / Geist Mono as bundled `@font-face` assets in the dashboard build, remove the
   `@import url('https://fonts.googleapis.com/...')` from `dashboard-ui/src/index.css`,
   and rebuild so `src/security_observatory/dashboard/assets/*.css` contacts no external
   host. This is the single change that makes the trust-boundary diagram's "no
   third-party API call" claim literally true on the default path. Validate with
   `grep -r googleapis src/security_observatory/dashboard/assets/` returning nothing and
   a clean `npm run build`.

2. **Harden the MCP path-leak invariant + extend redaction coverage (Rank 4).** Change
   the `test_mcp_server.py:969-1044` assertion from `startswith` to substring scanning so
   an absolute path embedded mid-string (e.g. inside an agent prompt) is caught, and
   confirm `_redact_path` is applied to every free-text MCP field that could embed one.

3. **Make the `--trust` opt-in egress disclosure exhaustive and visible (Ranks 8 + the
   managed-download surface).** Surface, in the dashboard's trust opt-in copy and the
   trust-boundary diagram, exactly what crosses: CVE IDs → EPSS, source-repo IDs →
   Scorecard, and managed-tool binary downloads → GitHub. Closes the gap between the
   diagram's "three opt-ins" framing and the four real egress surfaces, satisfying the
   brief's "every egress is opt-in, named, and visible" bar.

## SocratiCode Value

SocratiCode was not used this pass. Per the suite's SocratiCode cost-discipline rule,
this lens is dominated by exact-evidence work — enumerating concrete outbound call sites,
reading specific files, and asserting no-egress against named tests — for which
Read / Grep / Glob / Bash are the correct, cheaper instruments and provide direct proof
rather than orientation. The network-surface map was small and fully enumerable by grep
(three modules with real `urllib.request` calls, plus the built-CSS external-host scan),
so a structural librarian pass would not have changed the findings. No claim here rests
on SocratiCode; every health label cites a file/line, a test, or a validation command.

## Limits

- **No live network verification.** Per the skill's cross-lens "no live calls" guardrail
  and `.adx/risks.json`, I did not actually fetch from Google Fonts, Scorecard, EPSS,
  CISA, or GitHub releases. The Google Fonts egress is proven by the live `@import` in the
  shipped CSS (a render-time browser fetch is the standard, well-understood behavior of a
  CSS `@import url(https://...)`), not by an observed request. Egress *payloads* (what
  exactly Scorecard/EPSS receive) are read from the URL-construction code, not captured
  on the wire.
- **No dashboard runtime walk.** I did not start the dashboard server (prohibited:
  long-running server). Whether the running UI textually discloses the `--trust` egress to
  the user is left to the behavioral-ux / documentation lenses; I assessed only the code
  and copy strings present in source.
- **Test depth not exhaustively confirmed.** I ran the three highest-signal privacy test
  files (25 tests, green) but did not run the full suite (`test_credentials.py`,
  `test_mcp_server.py` path-leak invariant, reset deletion) this pass — those are cited
  from source reads and are safe to run.
- **PII beyond secrets/paths not deeply audited.** Redaction strongly covers secrets and
  (in MCP) absolute paths/usernames. Free-text PII such as emails or human names that a
  scanner could surface into a finding title or remediation is not specifically
  redacted; whether scanner output can carry such PII in this product was not exhaustively
  traced and is flagged as a Rank-3 follow-up, not a confirmed leak.
- **External Surface and runnable packs** were treated as out of scope per the Excellence
  Brief and not penalized.
