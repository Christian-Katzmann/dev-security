# Honey Keys

Honey Keys are DëvSec’s honeytoken feature: powerless decoy secrets that act as tripwires.

They are defensive deception tooling. A Honey Key is designed to look like an internal API key, but it cannot authenticate against DëvSec, a cloud provider, a payment provider, or any customer system.

## Safe Usage

Create a Honey Key from a repo dashboard, then either copy a decoy snippet or let DëvSec insert it safely.

By default, DëvSec writes inserted decoys under `.devsec/honeykeys/` so the file is inert and clearly owned by DëvSec. Advanced placement can use more realistic decoy names such as:

- `.env.backup`
- `legacy-prod-config.json`
- `internal-admin-notes.md`

DëvSec never commits these files. It refuses to overwrite existing files, refuses to write outside the selected repo, and requires explicit confirmation before writing.

## What Happens When One Is Touched

If the key or its trackable URL is used, DëvSec records a security event and turns the affected project red/critical. The alert means possible unauthorized access or that a decoy secret was touched. It does not identify the attacker personally.

DëvSec stores only a secure hash of the raw Honey Key after creation. Trigger events keep security-relevant metadata such as source IP, user-agent, request path, method, and a redacted body summary.

## Recommended Response

1. Check whether this repo was public, leaked, cloned, scraped, or accessed unexpectedly.
2. Review recent commits, CI logs, deploy logs, dependency activity, and access logs.
3. Rotate real secrets in this repo if exposure is plausible.
4. Review third-party integrations and AI-agent activity.
5. Archive or reset the Honey Key after investigation.

Honey Keys are fake, powerless decoy secrets. They alert you when touched. They do not prevent breaches by themselves.

## Guard Fidelity

Each safety claim above is enforced by a concrete guard in code. This table
binds the claim to its guard so the documentation can be audited against the
implementation. Each guard is cited by the **exact source line it must contain**
(line numbers pinned to the current tree). The line numbers are kept honest by
`tests/test_honey_keys.py::test_doc_guard_map_citations_resolve`, which reads
this table and fails if any cited line stops containing its named guard string —
so the citations cannot silently drift the way they once did:

| Claim | Guard | Location |
| --- | --- | --- |
| Refuses to overwrite existing files | `if target_path.exists():` → HTTP 409 "Placement file already exists." | `src/security_observatory/dashboard_server.py:2823` (the 409 message at `:2824`) |
| Refuses to write outside the selected repo | `target_path.relative_to(repo_path)` (400 "Placement path must stay inside the repo." if it escapes); a key whose `repo_id` differs is rejected with "Honey Key belongs to a different repo." | `src/security_observatory/dashboard_server.py:2816` and `:2839` |
| No duplicate Honey Key created | `except sqlite3.IntegrityError:` → HTTP 409 "Honey Key already exists." | `src/security_observatory/dashboard_server.py:2725` (the 409 message at `:2726`) |
| Stores only a secure hash of the raw key | `hash_honey_key` = `hashlib.sha256("honeykey:v1:" + token)`; the raw token is never persisted, only `token_hash` | `src/security_observatory/honey_keys.py:86` (declared `token_hash` at `:41`, stored at `:57`) |

