# Binary trust

A security tool runs other programs. DëvSec shells out to Trivy, Gitleaks, Semgrep, and others, and those programs read your source code. So DëvSec has to be honest about a plain question: *does it know what it is about to run?*

This document is the policy. It defines the proof levels DëvSec uses to describe a scanner binary, which levels are allowed to execute, and — just as important — what a strong proof level does **not** promise. It is the first of the binary-trust layers; [threat-model.md](threat-model.md) lists "scanner binary supply chain" as risk #1 and names the lack of binary verification as a load-bearing gap. This is the start of closing that gap, for the tools DëvSec installs itself.

## Two kinds of tools

DëvSec runs scanners from two different places, and it treats them differently because it controls one and not the other.

- **User-owned tools.** A scanner already on your `PATH` — installed by Homebrew, uv, pipx, or your system. DëvSec detects it and uses it, but it did not install it and **cannot vouch for it**. DëvSec will not relink, overwrite, upgrade, or remove a user-owned copy. You can't meaningfully verify a binary someone else's package manager placed, so DëvSec doesn't pretend to.
- **DëvSec-managed tools.** A copy DëvSec downloaded itself into `~/.security-observatory/tools/`, recorded, and owns. This is the only execution boundary the proof policy governs. Today the managed set is **Gitleaks, Trivy, Syft, and Grype**.

The honest consequence: "DëvSec verifies what it runs" means *the scanners DëvSec installs itself* — not every scanner on your machine. A user-owned Semgrep is still user-owned and unverified, by design.

## Proof levels

Every managed tool carries a proof level describing the strongest evidence DëvSec has about its origin. User-owned tools are reported as `user-owned`, which is a category, not a rank.

| Level | What it means | What it proves |
|---|---|---|
| `user-owned` | Found on `PATH`; DëvSec did not install it. | Nothing about origin. DëvSec defers to your package manager. |
| `unverified` | A managed artifact with no integrity evidence. | Nothing. Not allowed to run as a managed copy. |
| `checksum-pinned` | The downloaded archive's SHA-256 matched a value pinned in DëvSec's own source. | The bytes match what DëvSec's authors vetted at pin time. It does **not** prove the bytes came from the upstream project. |
| `upstream-signed` | The release (or its checksums file) carries a valid upstream **cosign** signature tied to the publisher's identity and OIDC issuer. | The artifact was signed by the upstream project's release identity. |
| `provenance-verified` | **SLSA** build provenance verifies the artifact was produced by the upstream's official build workflow. | The artifact was built by the expected pipeline, from the expected source. |
| `devsec-signed` | *Reserved.* DëvSec's own release artifacts, signed by DëvSec. | Origin of DëvSec itself. Not yet implemented — see the deferred release-signing work. |

Levels are ordered weakest to strongest from `checksum-pinned` up. `checksum-pinned` is a real control — it pins the exact bytes — but it is trust-on-pin, not trust-from-signature: it only proves the artifact matches what a human recorded in this repo, which is why stronger levels exist.

## What is allowed to execute

For **managed** tools, two gates apply, and both must pass:

1. **Download proof.** The install must reach `checksum-pinned` or stronger. An `unverified` managed artifact is refused at install. A weaker-than-expected result for a tool that should be signed is surfaced, not silently accepted as success.
2. **Pre-execution integrity.** Immediately before launching a managed scanner, DëvSec re-hashes the binary on disk and compares it to the digest recorded at install. **A mismatch refuses the run and surfaces a skipped/error status — it does not silently fall back to a `PATH` copy.** This catches the cheap attack the download check misses: replacing the binary *after* a clean install.

User-owned tools are governed by neither gate. They run as they always have; their status is reported as `user-owned` so the difference is visible.

### Legacy installs

A managed install created before DëvSec recorded per-binary digests has no integrity baseline to compare against. Such an install keeps running at its recorded download proof level, labeled so the missing baseline is visible, until it is reinstalled (a reinstall records the baseline). DëvSec does not block a previously trusted install on upgrade, and it does not invent a baseline it cannot trust.

## Signing proves origin, not safety

This is the most important line in the document, so it gets its own section.

cosign and SLSA answer *"who built this artifact, and was it tampered with after the build?"* They do **not** answer *"is this program safe to run against my private code?"* A correctly signed scanner with a supply-chain backdoor, a bug, or simply a lot of filesystem access is still a correctly signed scanner. DëvSec does not sandbox scanner subprocesses (see [threat-model.md](threat-model.md), "Known gaps") — a verified scanner runs with the same access as your shell.

So nowhere in the UI does a proof level mean "harmless," "safe," or "sandboxed." It means "we have this much evidence about where the bytes came from." Authenticity is necessary, not sufficient. Treat the proof level as provenance, and keep reading the [threat model](threat-model.md) for everything provenance doesn't cover.
