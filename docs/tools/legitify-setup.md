# Set up legitify (Connect GitHub)

legitify is the only catalog tool today that needs you to do something after
`brew install`. It connects to GitHub on your behalf to read repository,
Actions, and webhook settings, so it needs a Personal Access Token. The
DëvSec dashboard owns the whole flow — paste once, store in macOS Keychain,
test the connection, and the next platform-posture scan picks it up.

This page walks through the flow end-to-end and explains where things live
on disk and in Keychain.

> **Why this is a setup card, not a config file.** legitify's token never
> touches `.env`, shell history, or any file in this repo. It lives in the
> macOS Keychain under `(DëvSec, legitify:SCM_TOKEN)`. See
> [`credentials.md`](../credentials.md) for the full storage convention.

## What you need

- macOS (Keychain is the only supported credential store on DëvSec today).
- `legitify` on PATH. The catalog can install it for you via
  `brew install legitify`; the **Install** button on the legitify card runs
  exactly that command. If you've already installed it manually, the catalog
  will detect it the next time the dashboard refreshes.
- A **GitHub Personal Access Token (classic)** with two scopes:
  - `repo`
  - `admin:repo_hook`

  The setup card surfaces a **Generate a token →** link that opens GitHub's
  token-creation page with those scopes preselected and a `DëvSec legitify`
  description prefilled. You only need to set an expiration and click
  *Generate*.

## The flow

1. **Install** — open the DëvSec dashboard, go to **Tool Catalog → legitify**.
   If the install state shows `missing`, click **Install** and let Homebrew
   run. The state flips to `not-configured` once the binary is on PATH.

2. **Open the setup card** — the `not-configured` state renders a setup card
   with three things: a one-line requirement ("GitHub Personal Access Token
   with `repo` + `admin:repo_hook` scopes"), a paste field, and the
   **Generate a token →** link.

3. **Paste and store** — paste the token into the value field and click
   **Store in Keychain**. macOS may show its standard Keychain access
   prompt the first time DëvSec writes; approve it. The card now shows
   "Stored" plus a **Forget credential** affordance.

4. **Test the connection** — click **Test connection**. The card runs the
   catalog probe:

   ```text
   legitify analyze --scm github --namespace repository \
       --repo Legit-Labs/legitify --color false
   ```

   That command targets a small public repo (`Legit-Labs/legitify` itself —
   the upstream project) with one namespace, so it stays fast (~15s on a
   warm token). The probe reads `SCM_TOKEN` from Keychain via DëvSec's
   subprocess-env helper and injects it into the child process — the value
   never lands in a file, env file, or shell history.

   legitify exits `1` whenever it finds policy violations on the target.
   The probe treats `0` *and* `1` as success because both prove the token
   authenticated; any other exit code (or a network failure) is reported
   verbatim in the card's output panel (truncated to 20 lines).

5. **Catalog state flips to `detected`** — on success, the SetupCard
   collapses, the eyebrow flips to **Detected locally**, and legitify
   becomes runnable from the dashboard and the CLI:

   ```bash
   security-scan --platform-posture
   ```

   The dashboard also surfaces a **Run platform posture scan** affordance
   in the SetupCard's success state — it triggers the same `/api/run-check`
   endpoint the rest of the dashboard uses, so progress and results route
   through the existing check pipeline.

6. **Forget when needed** — clicking **Forget credential** deletes the
   Keychain entry and removes legitify's row from the credentials index.
   The catalog state immediately flips back to `not-configured`. The
   binary is left alone; only the token is removed.

## What the CLI does without the dashboard

`security-scan --platform-posture` calls `_run_legitify_scanner` in
`src/security_observatory/scanners.py`. It now consults the Keychain first
via `_legitify_env` and falls back to environment variables in this order:

1. `SCM_TOKEN` overlay from Keychain (`legitify:SCM_TOKEN`).
2. `SCM_TOKEN` from the inherited environment.
3. `SECURITY_OBSERVATORY_SCM_TOKEN` from the inherited environment.
4. `LEGITIFY_TOKEN` from the inherited environment.

So shell-set tokens from before this campaign still work — they just lose
the race when both are present, and the dashboard-stored value wins.

If none of those resolves a token, the scan is skipped with a message
pointing the user back at the setup card.

## Troubleshooting

- **"No credential stored for legitify (SCM_TOKEN)"** on Test connection —
  the paste didn't actually land in Keychain. Re-paste and click *Store* again.
  If that fails, open Keychain Access, search for `DëvSec`, and confirm the
  entry exists.
- **Probe exits non-zero with "401 Bad credentials"** in the output panel —
  the token is malformed, expired, or missing scopes. Generate a new token
  with the scopes preselected via the **Generate a token →** link.
- **Probe times out at 90s** — GitHub API may be slow or your network is
  blocking traffic. The probe targets `github.com`; if a corporate proxy
  intercepts that, legitify will hang until the timeout fires. Re-test from
  a network that can reach `api.github.com`.
- **State doesn't flip to `detected` even after a successful probe** — the
  catalog state is computed from the credential index. If the dashboard
  hasn't reloaded, refresh the page. If it still doesn't flip, check
  `~/.security-observatory/credentials/index.json` — it should list
  `SCM_TOKEN` under the `legitify` tool.

## Pointers

- Catalog entry: `src/security_observatory/catalog.py` (search for
  `_scanner_entry(scanner="legitify"`).
- Probe runner: `src/security_observatory/setup_runner.py`.
- Subprocess-env injection: `credentials.env_with_credentials`.
- Scanner invocation that consumes the Keychain value:
  `src/security_observatory/scanners.py` — `_run_legitify_scanner`.
- The SetupCard UI: `dashboard-ui/src/components/catalog/SetupCard.tsx`.
