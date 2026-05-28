"""Verification provider contract for DëvSec-managed tool downloads.

This module is the seam between the managed installer and real upstream proof
systems. A provider takes a downloaded artifact plus the per-tool verification
config and returns a :class:`VerificationResult` describing the strongest proof
level it could establish. Providers shell out to external verifiers (cosign)
through an injectable ``runner`` and fetch sidecar files through an injectable
``fetch``, so the whole contract is unit-testable without network access or a
real cosign binary.

Proof levels are policy vocabulary defined in ``docs/binary-trust.md``. Two
truths shape the design:

- A verifier that is *absent* is a setup gap, not a failure: it downgrades to
  the checksum-pinned floor and says so. A verifier that *ran and rejected* the
  artifact is a hard failure (possible tampering) and raises.
- Signing proves origin, not safety. A proof level never means "harmless".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import hashlib
import shutil
import subprocess
import tempfile


# Proof levels, ordered weakest to strongest. ``user-owned`` is a surfacing
# label for PATH tools, not a rank, so it is excluded from the ordering.
PROOF_UNVERIFIED = "unverified"
PROOF_CHECKSUM_PINNED = "checksum-pinned"
PROOF_UPSTREAM_SIGNED = "upstream-signed"
PROOF_PROVENANCE_VERIFIED = "provenance-verified"
PROOF_DEVSEC_SIGNED = "devsec-signed"
PROOF_USER_OWNED = "user-owned"

_PROOF_RANK: dict[str, int] = {
    PROOF_UNVERIFIED: 0,
    PROOF_CHECKSUM_PINNED: 1,
    PROOF_UPSTREAM_SIGNED: 2,
    PROOF_PROVENANCE_VERIFIED: 3,
    PROOF_DEVSEC_SIGNED: 4,
}


_PROOF_LABELS: dict[str, str] = {
    PROOF_UNVERIFIED: "Unverified",
    PROOF_CHECKSUM_PINNED: "Checksum-pinned",
    PROOF_UPSTREAM_SIGNED: "Upstream-signed",
    PROOF_PROVENANCE_VERIFIED: "Provenance-verified",
    PROOF_DEVSEC_SIGNED: "DëvSec-signed",
    PROOF_USER_OWNED: "User-owned",
}

# One honest line to pair with any proof level in the UI. Signing is provenance,
# not safety — see docs/binary-trust.md.
PROOF_SAFETY_CAVEAT = "Proof describes where the binary came from, not that it is safe to run. Managed scanners are not sandboxed."


def proof_rank(level: str | None) -> int:
    return _PROOF_RANK.get(str(level or ""), 0)


def is_executable_proof(level: str | None) -> bool:
    """Managed tools may execute at ``checksum-pinned`` or stronger."""
    return proof_rank(level) >= _PROOF_RANK[PROOF_CHECKSUM_PINNED]


def proof_level_label(level: str | None) -> str:
    return _PROOF_LABELS.get(str(level or ""), _PROOF_LABELS[PROOF_UNVERIFIED])


# (command, timeout_seconds) -> CommandResult. ``found`` distinguishes "the
# verifier is not installed" from "the verifier ran and returned non-zero".
Fetcher = Callable[[str, int, int], bytes]


class VerificationError(Exception):
    """A verifier ran and the artifact failed verification (possible tampering)."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    found: bool


CommandRunner = Callable[[list[str], int], CommandResult]


@dataclass(frozen=True, slots=True)
class VerificationResult:
    proof_level: str
    verifier: str
    available: bool = True
    verified_subject_digest: str | None = None
    source_identity: str | None = None
    evidence: tuple[str, ...] = ()
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_level": self.proof_level,
            "verifier": self.verifier,
            "available": self.available,
            "verified_subject_digest": self.verified_subject_digest,
            "source_identity": self.source_identity,
            "evidence": list(self.evidence),
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> VerificationResult | None:
        if not isinstance(data, dict) or not data.get("proof_level"):
            return None
        evidence = data.get("evidence")
        return cls(
            proof_level=str(data.get("proof_level")),
            verifier=str(data.get("verifier") or ""),
            available=bool(data.get("available", True)),
            verified_subject_digest=_opt_str(data.get("verified_subject_digest")),
            source_identity=_opt_str(data.get("source_identity")),
            evidence=tuple(str(item) for item in evidence) if isinstance(evidence, list) else (),
            summary=str(data.get("summary") or ""),
        )

    def with_extra_evidence(self, extra: list[str]) -> VerificationResult:
        if not extra:
            return self
        merged = tuple(item for item in (*extra, *self.evidence) if item)
        return VerificationResult(
            proof_level=self.proof_level,
            verifier=self.verifier,
            available=self.available,
            verified_subject_digest=self.verified_subject_digest,
            source_identity=self.source_identity,
            evidence=merged,
            summary=self.summary,
        )


@dataclass(frozen=True, slots=True)
class VerificationRequest:
    tool_id: str
    version: str
    asset_name: str
    artifact_bytes: bytes
    expected_sha256: str
    release_base_url: str
    config: dict[str, Any]
    fetch: Fetcher
    runner: CommandRunner
    which: Callable[[str], str | None] = shutil.which
    timeout_seconds: int = 30
    max_bytes: int = 40_000_000

    def asset_url(self, asset_name: str) -> str:
        return f"{self.release_base_url.rstrip('/')}/{asset_name}"


def default_runner(command: list[str], timeout_seconds: int) -> CommandResult:
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult(returncode=127, stdout="", stderr="", found=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(returncode=124, stdout="", stderr=str(exc), found=True)
    return CommandResult(
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        found=True,
    )


class ChecksumProvider:
    """The floor. Confirms the artifact matches the SHA-256 pinned in DëvSec source.

    This proves the bytes match what DëvSec's authors vetted at pin time — it does
    not prove the bytes came from upstream signing. That is why it is the floor,
    not the ceiling.
    """

    name = "checksum"

    def verify(self, request: VerificationRequest) -> VerificationResult:
        digest = hashlib.sha256(request.artifact_bytes).hexdigest()
        if digest.lower() != request.expected_sha256.lower():
            raise VerificationError(
                f"{request.asset_name} SHA-256 {digest} does not match the pinned "
                f"{request.expected_sha256}."
            )
        return VerificationResult(
            proof_level=PROOF_CHECKSUM_PINNED,
            verifier=self.name,
            available=True,
            verified_subject_digest=digest,
            evidence=(f"Archive SHA-256 matched the value pinned in DëvSec source ({digest[:12]}…).",),
            summary="Checksum matches the digest pinned in DëvSec source.",
        )


class CosignProvider:
    """Verifies an upstream keyless cosign signature over the release ``checksums.txt``.

    Detached style (Syft, Grype): fetch ``checksums.txt`` + ``.sig`` + ``.pem`` and
    run ``cosign verify-blob`` pinned to the upstream certificate identity and OIDC
    issuer; then confirm our artifact's digest is listed in the verified checksums
    file. Absence of cosign downgrades to the checksum floor with a setup note; an
    invalid signature or an artifact missing from the signed checksums raises.
    """

    name = "cosign"

    def verify(self, request: VerificationRequest) -> VerificationResult:
        config = request.config
        if not config.get("certificate_identity") or not config.get("certificate_oidc_issuer"):
            raise VerificationError(
                f"{request.tool_id} cosign config is missing certificate identity or issuer."
            )
        identity = _fmt(config["certificate_identity"], request)
        issuer = _fmt(config["certificate_oidc_issuer"], request)
        if request.which("cosign") is None:
            return VerificationResult(
                proof_level=PROOF_UNVERIFIED,
                verifier=self.name,
                available=False,
                evidence=("cosign is not on PATH; install cosign to verify upstream signatures.",),
                summary="cosign verifier unavailable.",
            )

        version = request.version
        checksums_asset = _fmt(config["checksums_asset"], request)
        signature_asset = _fmt(config["signature_asset"], request)
        certificate_asset = _fmt(config["certificate_asset"], request)

        try:
            checksums_bytes = request.fetch(request.asset_url(checksums_asset), request.timeout_seconds, request.max_bytes)
            signature_bytes = request.fetch(request.asset_url(signature_asset), request.timeout_seconds, request.max_bytes)
            certificate_bytes = request.fetch(request.asset_url(certificate_asset), request.timeout_seconds, request.max_bytes)
        except Exception as exc:  # noqa: BLE001 - network/IO failure is a setup gap, not tampering
            return VerificationResult(
                proof_level=PROOF_UNVERIFIED,
                verifier=self.name,
                available=False,
                evidence=(f"Could not fetch cosign signature material for {request.tool_id}: {exc}",),
                summary="cosign signature material unavailable.",
            )

        with tempfile.TemporaryDirectory(prefix="devsec-cosign-") as tmp:
            tmp_dir = Path(tmp)
            checksums_path = tmp_dir / checksums_asset
            signature_path = tmp_dir / signature_asset
            certificate_path = tmp_dir / certificate_asset
            checksums_path.write_bytes(checksums_bytes)
            signature_path.write_bytes(signature_bytes)
            certificate_path.write_bytes(certificate_bytes)
            command = [
                "cosign",
                "verify-blob",
                str(checksums_path),
                "--certificate",
                str(certificate_path),
                "--signature",
                str(signature_path),
                "--certificate-identity",
                identity,
                "--certificate-oidc-issuer",
                issuer,
            ]
            result = request.runner(command, request.timeout_seconds)

        if not result.found:
            return VerificationResult(
                proof_level=PROOF_UNVERIFIED,
                verifier=self.name,
                available=False,
                evidence=("cosign is not on PATH; install cosign to verify upstream signatures.",),
                summary="cosign verifier unavailable.",
            )
        if result.returncode != 0:
            raise VerificationError(
                f"cosign rejected the {request.tool_id} checksums signature "
                f"(identity {identity}): {(result.stderr or result.stdout).strip()[:500]}"
            )

        listed = _sha_for_asset(checksums_bytes.decode("utf-8", errors="replace"), request.asset_name)
        if listed is None:
            raise VerificationError(
                f"{request.asset_name} is not listed in the cosign-verified {checksums_asset}."
            )
        if listed.lower() != request.expected_sha256.lower():
            raise VerificationError(
                f"{request.asset_name} digest in the verified checksums ({listed}) does not "
                f"match the downloaded artifact ({request.expected_sha256})."
            )
        return VerificationResult(
            proof_level=PROOF_UPSTREAM_SIGNED,
            verifier=self.name,
            available=True,
            verified_subject_digest=request.expected_sha256,
            source_identity=identity,
            evidence=(
                f"cosign verified {checksums_asset} against identity {identity} (issuer {issuer}).",
                f"{request.asset_name} digest is listed in the verified checksums file.",
            ),
            summary="Upstream cosign signature verified over the release checksums.",
        )


def verify_managed_download(request: VerificationRequest) -> VerificationResult:
    """Establish the strongest proof level the artifact's config supports.

    Tries the configured signing provider first; if its verifier is merely absent,
    falls back to the checksum floor and carries the setup note forward. A verifier
    that ran and rejected the artifact propagates as :class:`VerificationError`.
    """
    notes: list[str] = []
    method = str(request.config.get("method") or "checksum")
    if method == "cosign":
        signed = CosignProvider().verify(request)
        if signed.available and proof_rank(signed.proof_level) > _PROOF_RANK[PROOF_CHECKSUM_PINNED]:
            return signed
        notes.extend(signed.evidence)
    return ChecksumProvider().verify(request).with_extra_evidence(notes)


def _fmt(template: Any, request: VerificationRequest) -> str:
    return str(template).format(
        tool=request.tool_id,
        version=request.version,
        asset_name=request.asset_name,
    )


def _sha_for_asset(checksums_text: str, asset_name: str) -> str | None:
    for line in checksums_text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        # GNU coreutils marks binary-mode entries as "<sha>  *<name>".
        name = parts[-1].lstrip("*")
        if Path(name).name == asset_name:
            return parts[0].strip()
    return None


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
