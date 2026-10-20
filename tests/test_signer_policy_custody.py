"""Tests for bounded, externally pinned signer-policy bytes."""

import hashlib

import pytest

from holosim.signer_policy_custody import (
    MAX_POLICY_BYTES,
    SignerPolicyCustodyError,
    capture_pinned_signer_policy,
)


def test_matching_policy_is_captured(tmp_path):
    policy = tmp_path / "allowed"
    original = b"fixture ssh-ed25519 AAAATEST\n"
    policy.write_bytes(original)

    result = capture_pinned_signer_policy(
        allowed_signers_path=policy,
        expected_sha256=hashlib.sha256(original).hexdigest(),
    )

    assert result == original
    assert policy.read_bytes() == original


def test_substituted_policy_is_rejected(tmp_path):
    policy = tmp_path / "allowed"
    original = b"original signer\n"
    replacement = b"replacement signer\n"

    expected = hashlib.sha256(original).hexdigest()
    policy.write_bytes(replacement)

    with pytest.raises(SignerPolicyCustodyError, match="mismatch"):
        capture_pinned_signer_policy(
            allowed_signers_path=policy,
            expected_sha256=expected,
        )


@pytest.mark.parametrize("digest", [
    "",
    "0" * 63,
    "0" * 65,
    "G" * 64,
    None,
    True,
])
def test_invalid_digest_rejected(tmp_path, digest):
    policy = tmp_path / "allowed"
    policy.write_bytes(b"signer\n")

    with pytest.raises(SignerPolicyCustodyError):
        capture_pinned_signer_policy(
            allowed_signers_path=policy,
            expected_sha256=digest,
        )


@pytest.mark.parametrize("size", [0, MAX_POLICY_BYTES + 1])
def test_invalid_policy_size_rejected(tmp_path, size):
    policy = tmp_path / "allowed"
    data = b"x" * size
    policy.write_bytes(data)

    with pytest.raises(SignerPolicyCustodyError):
        capture_pinned_signer_policy(
            allowed_signers_path=policy,
            expected_sha256=hashlib.sha256(data).hexdigest(),
        )


def test_missing_policy_rejected(tmp_path):
    with pytest.raises(SignerPolicyCustodyError):
        capture_pinned_signer_policy(
            allowed_signers_path=tmp_path / "missing",
            expected_sha256="0" * 64,
        )


def test_attacker_controlled_digest_does_not_establish_custody(tmp_path):
    import hashlib

    from holosim.signer_policy_custody import capture_pinned_signer_policy

    attacker_policy = tmp_path / "attacker_allowed"
    attacker_policy.write_bytes(b"attacker-controlled signer policy\n")

    attacker_digest = hashlib.sha256(
        attacker_policy.read_bytes()
    ).hexdigest()

    captured = capture_pinned_signer_policy(
        allowed_signers_path=attacker_policy,
        expected_sha256=attacker_digest,
    )

    assert captured == attacker_policy.read_bytes()


def test_captured_policy_survives_source_replacement(tmp_path):
    import hashlib

    from holosim.signer_policy_custody import capture_pinned_signer_policy

    policy = tmp_path / "allowed"
    original = b"original trusted signer\n"
    replacement = b"attacker replacement signer\n"

    policy.write_bytes(original)

    captured = capture_pinned_signer_policy(
        allowed_signers_path=policy,
        expected_sha256=hashlib.sha256(original).hexdigest(),
    )

    policy.write_bytes(replacement)

    assert captured == original
    assert policy.read_bytes() == replacement
    assert captured != policy.read_bytes()
