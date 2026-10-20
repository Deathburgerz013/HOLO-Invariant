"""Regression tests for pinned origin-checkpoint verification."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from holosim.pinned_origin_checkpoint import verify_origin_with_pinned_policy
from holosim.signed_origin_checkpoint import sign_origin_checkpoint
from tests.test_signed_origin_checkpoint import _candidate, _key


pytestmark = pytest.mark.skipif(
    shutil.which("ssh-keygen") is None,
    reason="OpenSSH ssh-keygen unavailable",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checkpoint(candidate: bytes, key: Path) -> dict:
    return sign_origin_checkpoint(
        candidate=candidate,
        validator_id="idx:v1",
        contributor_id=None,
        signer_identity="anchor",
        private_key_path=key,
    )


def test_legitimate_pinned_policy_verifies(tmp_path: Path) -> None:
    candidate = _candidate()
    key, policy = _key(tmp_path, "legitimate")
    checkpoint = _checkpoint(candidate, key)

    result = verify_origin_with_pinned_policy(
        candidate=candidate,
        checkpoint=checkpoint,
        allowed_signers_path=policy,
        expected_policy_sha256=_digest(policy),
    )

    assert result["status"] == "VERIFIED"
    assert result["verified"] is True
    assert result["policy_digest_matched"] is True
    assert result["policy_custody_verified"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_attacker_policy_rejected_against_original_pin(tmp_path: Path) -> None:
    candidate = _candidate()

    legitimate_key, legitimate_policy = _key(tmp_path, "legitimate")
    original_digest = _digest(legitimate_policy)

    attacker_key, attacker_policy = _key(tmp_path, "attacker")
    attacker_checkpoint = _checkpoint(candidate, attacker_key)

    result = verify_origin_with_pinned_policy(
        candidate=candidate,
        checkpoint=attacker_checkpoint,
        allowed_signers_path=attacker_policy,
        expected_policy_sha256=original_digest,
    )

    assert result["status"] == "REJECTED_POLICY"
    assert result["verified"] is False
    assert result["policy_digest_matched"] is False
    assert result["policy_custody_verified"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_attacker_controlled_pin_does_not_establish_custody(tmp_path: Path) -> None:
    candidate = _candidate()
    attacker_key, attacker_policy = _key(tmp_path, "attacker")
    attacker_checkpoint = _checkpoint(candidate, attacker_key)

    result = verify_origin_with_pinned_policy(
        candidate=candidate,
        checkpoint=attacker_checkpoint,
        allowed_signers_path=attacker_policy,
        expected_policy_sha256=_digest(attacker_policy),
    )

    assert result["status"] == "VERIFIED"
    assert result["verified"] is True
    assert result["policy_digest_matched"] is True
    assert result["policy_custody_verified"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
