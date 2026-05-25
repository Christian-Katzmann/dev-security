# DëvSec credential storage

Some catalog tools need credentials to run — legitify needs a GitHub Personal
Access Token, future tools will need API keys or signed paths. DëvSec stores
those values in the **macOS Keychain** and never anywhere else.

This document is the operational reference: where things live, how to audit
what's stored, how to revoke, and what the local-first commitment actually
means.

## The shape

Every secret DëvSec owns lives under a single Keychain service name:

- **Service:** `DëvSec`
- **Account:** `<tool_id>:<key>` (e.g. `legitify:SCM_TOKEN`)
- **Kind:** generic password

One service name keeps the audit surface simple. Open `Keychain Access.app`,
search for `DëvSec`, and every credential DëvSec has stored on this Mac
appears together.

A small **index file** at `~/.security-observatory/credentials/index.json`
records which `(tool_id, key)` pairs exist. The index is bookkeeping only —
**it never contains values**. It's there so DëvSec can answer "what's stored
for legitify?" without exporting the whole keychain or triggering a Keychain
access prompt just to enumerate keys.

## Where values come from, where they go

Values enter Keychain exactly two ways:

1. **The Setup card** (`Tools → <tool> → Set up`). The user pastes the value,
   the dashboard `POST`s it to `/api/tools/<tool_id>/credentials`, the
   backend writes it to Keychain.
2. **A direct write** to Keychain via `Keychain Access.app` or another macOS
   tool. DëvSec respects whatever is already there.

Values leave Keychain exactly one way:

- The `env_with_credentials()` helper in `src/security_observatory/credentials.py`
  injects them into a subprocess's environment when a scanner runs. The
  value lives in the child process's env block for the duration of that
  subprocess and is discarded when the process exits.

Values **do not** flow anywhere else. In particular:

- Values are never written to `.env` files, shell history, or any DëvSec
  state file.
- Values are never returned in HTTP responses. The dashboard only ever sees
  `"is_stored": true` and the list of keys.
- Values are never logged. Operations log the tool/key pair, never the
  value.

## How to audit what's stored

### From the CLI

```sh
security-scan credentials list
```

Lists every `tool_id → keys` pair DëvSec has stored. Values are never
printed.

```sh
security-scan credentials list --json
```

Same content, JSON shape. Useful if you want to pipe into `jq` or include
the audit in a wider report.

### From Keychain Access

Open `Keychain Access.app`, select the **login** keychain, search for
`DëvSec`. Every credential DëvSec owns will appear. You can view a value
here after macOS prompts for your login password — that prompt is the
Keychain access dialog, not something DëvSec controls.

### From the dashboard

The Setup card on each tool's detail page shows whether a credential is
currently stored. It never displays the value.

## How to revoke

You have three options. Use whichever is closest to where you noticed the
problem.

1. **From the Setup card.** Click **Forget**. The dashboard `DELETE`s
   `/api/tools/<tool_id>/credentials/<key>`. The Keychain entry is removed
   and the catalog's install state flips back to `not-configured`.
2. **From the CLI.** Not yet exposed in v1 — open Keychain Access or use
   `security delete-generic-password -s "DëvSec" -a "<tool_id>:<key>"`.
3. **From Keychain Access.** Right-click the entry, **Delete**. DëvSec's
   index will self-repair the next time you store or delete a key for that
   tool.

In every case, the next scan that needed the credential will report that
the tool is "not configured" — the same state as if the credential had
never been stored.

## The local-first commitment

DëvSec is local-first. The credential layer is a load-bearing part of that
promise.

- Credentials are stored in the **login Keychain on this Mac**. They do
  not leave the device.
- DëvSec has no cloud service, no remote store, no telemetry that touches
  credentials.
- The Keychain access prompt that macOS shows when an app reads or writes
  a Keychain item is the operating system asking you, the user, for
  permission. DëvSec deliberately does not try to suppress it.
- Credential storage requires macOS. DëvSec does not implement Linux
  Secret Service or Windows Credential Manager — adding either would dilute
  the local-first guarantee and double the audit surface.

## Trade-offs we accepted

A few practical points worth knowing about.

- **Process arguments are briefly visible.** macOS's `security` CLI takes
  the password as a command-line argument (`-w VALUE`), which is briefly
  visible to other processes via `ps` for the duration of the call. Other
  tools that use Keychain (`keyring`, the GitHub CLI's keychain backend)
  have the same trade-off. A future iteration may bypass this by calling
  the Security framework directly via `ctypes`.
- **The index file can drift.** If you delete a credential directly from
  Keychain Access, DëvSec's index won't know until the next read/store/
  delete for that tool. This is harmless — the index self-repairs.
- **Per-machine, not per-repo.** The Tool Catalog is all-repos-only, so a
  single Keychain entry for `legitify:SCM_TOKEN` covers every repo on this
  Mac. The Setup card never asks "which repo are we configuring for?" —
  there is no such concept at the catalog level.

## File reference

- Module: `src/security_observatory/credentials.py`
- HTTP endpoints: `dashboard_server.py`
  - `GET    /api/tools/credentials` — full `{tool_id: [keys]}` index
  - `GET    /api/tools/<id>/credentials/keys` — keys for one tool
  - `POST   /api/tools/<id>/credentials` — store `{key, value}`
  - `DELETE /api/tools/<id>/credentials/<key>` — forget one credential
- CLI: `security-scan credentials list`
- Tests: `tests/test_credentials.py` (Keychain integration; macOS-only),
  `tests/test_dashboard_credentials_endpoints.py` (HTTP contract; all
  platforms)
