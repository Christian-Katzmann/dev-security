from __future__ import annotations

import hashlib

import pytest

from security_observatory.verification import (
    PROOF_CHECKSUM_PINNED,
    PROOF_UNVERIFIED,
    PROOF_UPSTREAM_SIGNED,
    ChecksumProvider,
    CommandResult,
    CosignProvider,
    VerificationError,
    VerificationRequest,
    VerificationResult,
    is_executable_proof,
    proof_rank,
    verify_managed_download,
)


ARTIFACT = b"a-managed-scanner-tarball"
ARTIFACT_SHA = hashlib.sha256(ARTIFACT).hexdigest()
ASSET = "syft_1.44.0_linux_amd64.tar.gz"
BASE_URL = "https://github.com/anchore/syft/releases/download/v1.44.0"

COSIGN_CONFIG = {
    "method": "cosign",
    "checksums_asset": "{tool}_{version}_checksums.txt",
    "signature_asset": "{tool}_{version}_checksums.txt.sig",
    "certificate_asset": "{tool}_{version}_checksums.txt.pem",
    "certificate_identity": "https://github.com/anchore/{tool}/.github/workflows/release.yaml@refs/heads/main",
    "certificate_oidc_issuer": "https://token.actions.githubusercontent.com",
}


def _checksums(asset_sha: str = ARTIFACT_SHA, asset_name: str = ASSET) -> bytes:
    return (
        f"{asset_sha}  {asset_name}\n"
        "0000000000000000000000000000000000000000000000000000000000000000  other_1.44.0_darwin_arm64.tar.gz\n"
    ).encode("utf-8")


def _fetch_ok(checksums: bytes = None):
    checksums = checksums if checksums is not None else _checksums()

    def fetch(url: str, _timeout: int, _limit: int) -> bytes:
        name = url.rsplit("/", 1)[-1]
        if name.endswith("_checksums.txt"):
            return checksums
        if name.endswith(".sig"):
            return b"signature-bytes"
        if name.endswith(".pem"):
            return b"certificate-bytes"
        raise AssertionError(f"unexpected fetch for {name}")

    return fetch


def _request(*, config=None, fetch=None, runner=None, which=None) -> VerificationRequest:
    return VerificationRequest(
        tool_id="syft",
        version="1.44.0",
        asset_name=ASSET,
        artifact_bytes=ARTIFACT,
        expected_sha256=ARTIFACT_SHA,
        release_base_url=BASE_URL,
        config=config if config is not None else dict(COSIGN_CONFIG),
        fetch=fetch if fetch is not None else _fetch_ok(),
        runner=runner if runner is not None else _runner_returning(0),
        which=which if which is not None else (lambda name: "/usr/bin/cosign" if name == "cosign" else None),
    )


def _runner_returning(returncode: int, *, found: bool = True, stderr: str = ""):
    def runner(command: list[str], _timeout: int) -> CommandResult:
        assert command[0] == "cosign"
        assert command[1] == "verify-blob"
        assert "--certificate-identity" in command
        assert "--certificate-oidc-issuer" in command
        return CommandResult(returncode=returncode, stdout="Verified OK", stderr=stderr, found=found)

    return runner


# --- proof-level helpers ---------------------------------------------------


def test_proof_rank_orders_levels():
    assert proof_rank(PROOF_UPSTREAM_SIGNED) > proof_rank(PROOF_CHECKSUM_PINNED) > proof_rank(PROOF_UNVERIFIED)


def test_only_checksum_pinned_and_stronger_may_execute():
    assert is_executable_proof(PROOF_CHECKSUM_PINNED)
    assert is_executable_proof(PROOF_UPSTREAM_SIGNED)
    assert not is_executable_proof(PROOF_UNVERIFIED)
    assert not is_executable_proof("user-owned")


def test_verification_result_round_trips_through_dict():
    result = VerificationResult(
        proof_level=PROOF_UPSTREAM_SIGNED,
        verifier="cosign",
        verified_subject_digest=ARTIFACT_SHA,
        source_identity="identity",
        evidence=("a", "b"),
        summary="signed",
    )
    assert VerificationResult.from_dict(result.to_dict()) == result
    assert VerificationResult.from_dict({}) is None


# --- checksum provider -----------------------------------------------------


def test_checksum_provider_passes_on_match():
    result = ChecksumProvider().verify(_request(config={"method": "checksum"}))
    assert result.proof_level == PROOF_CHECKSUM_PINNED
    assert result.verified_subject_digest == ARTIFACT_SHA
    assert result.available is True


def test_checksum_provider_raises_on_mismatch():
    request = VerificationRequest(
        tool_id="syft",
        version="1.44.0",
        asset_name=ASSET,
        artifact_bytes=ARTIFACT,
        expected_sha256="deadbeef",
        release_base_url=BASE_URL,
        config={"method": "checksum"},
        fetch=_fetch_ok(),
        runner=_runner_returning(0),
    )
    with pytest.raises(VerificationError):
        ChecksumProvider().verify(request)


# --- cosign provider -------------------------------------------------------


def test_cosign_provider_verifies_signed_checksums():
    result = CosignProvider().verify(_request())
    assert result.proof_level == PROOF_UPSTREAM_SIGNED
    assert result.verifier == "cosign"
    assert result.available is True
    assert result.verified_subject_digest == ARTIFACT_SHA
    assert "anchore/syft" in (result.source_identity or "")


def test_cosign_absent_is_a_setup_gap_not_a_failure():
    result = CosignProvider().verify(_request(which=lambda _name: None))
    assert result.available is False
    assert result.proof_level == PROOF_UNVERIFIED
    assert any("cosign" in note for note in result.evidence)


def test_cosign_handles_binary_mode_checksums():
    # GNU coreutils binary-mode lines mark the filename with a leading '*'.
    binary_mode = (
        f"{ARTIFACT_SHA}  *{ASSET}\n"
        "0000000000000000000000000000000000000000000000000000000000000000  *other.tar.gz\n"
    ).encode("utf-8")
    result = CosignProvider().verify(_request(fetch=_fetch_ok(binary_mode)))
    assert result.proof_level == PROOF_UPSTREAM_SIGNED


def test_checksum_provider_is_case_insensitive():
    request = VerificationRequest(
        tool_id="syft",
        version="1.44.0",
        asset_name=ASSET,
        artifact_bytes=ARTIFACT,
        expected_sha256=ARTIFACT_SHA.upper(),  # pins are hand-pasted; case must not matter
        release_base_url=BASE_URL,
        config={"method": "checksum"},
        fetch=_fetch_ok(),
        runner=_runner_returning(0),
    )
    result = ChecksumProvider().verify(request)
    assert result.proof_level == PROOF_CHECKSUM_PINNED


def test_cosign_invalid_signature_raises():
    with pytest.raises(VerificationError):
        CosignProvider().verify(_request(runner=_runner_returning(1, stderr="bad signature")))


def test_cosign_artifact_missing_from_signed_checksums_raises():
    fetch = _fetch_ok(_checksums(asset_name="some_other_asset.tar.gz"))
    with pytest.raises(VerificationError):
        CosignProvider().verify(_request(fetch=fetch))


def test_cosign_artifact_digest_disagreement_raises():
    fetch = _fetch_ok(_checksums(asset_sha="f" * 64))
    with pytest.raises(VerificationError):
        CosignProvider().verify(_request(fetch=fetch))


def test_cosign_fetch_failure_is_a_setup_gap():
    def fetch(_url: str, _timeout: int, _limit: int) -> bytes:
        raise OSError("network down")

    result = CosignProvider().verify(_request(fetch=fetch))
    assert result.available is False
    assert result.proof_level == PROOF_UNVERIFIED


# --- orchestrator ----------------------------------------------------------


def test_verify_managed_download_returns_signed_when_cosign_succeeds():
    result = verify_managed_download(_request())
    assert result.proof_level == PROOF_UPSTREAM_SIGNED


def test_verify_managed_download_falls_back_to_checksum_when_cosign_absent():
    result = verify_managed_download(_request(which=lambda _name: None))
    assert result.proof_level == PROOF_CHECKSUM_PINNED
    assert any("cosign" in note for note in result.evidence)


def test_verify_managed_download_checksum_only_config():
    result = verify_managed_download(_request(config={"method": "checksum"}))
    assert result.proof_level == PROOF_CHECKSUM_PINNED
