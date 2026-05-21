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
