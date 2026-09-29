"""Bounded public-key checkpoint experiment using disposable SSH keys."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from holosim.signed_origin_checkpoint import (
    SignedOriginCheckpointError,
    sign_origin_checkpoint,
    verify_origin_checkpoint,
)


pytestmark = pytest.mark.skipif(
    shutil.which("ssh-keygen") is None, reason="OpenSSH ssh-keygen unavailable"
)


def _candidate() -> bytes:
    return b"""| |==============================================================|
| | \xe2\x96\x88\xe2\x80\xa0\xe2\x96\x88 Holo/Sim \xe2\x96\x88\xe2\x80\xa0\xe2\x96\x88 \xe2\x96\x88\xe2\x80\xa0\xe2\x96\x88 HSSCE \xe2\x96\x88\xe2\x80\xa0\xe2\x96\x88
| | }=============================================================|
| | SPINE_META
| | TEMPLATE_VERSION: SPINE_STORAGE_V1
| | SPINE_ID: spine-001
| | STATE: CANDIDATE
| | CREATED_BY: Canyon Brock Haney
| | }=============================================================|
| | RECOGNITION
| | PRIMARY_KEY: test
| | }=============================================================|
| | COLLECTION_CONTRACT
| | COLLECT: EVIDENCE
| | }=============================================================|
| | ENTRY
| | ENTRY_ID: E-001
| | ENTITY_ID: Canyon Brock Haney
| | ENTITY_TYPE: HUMAN
| | SOURCE_STATE_ID: state-1
| | INFORMATION_CLASS: EVIDENCE
| | SOURCE: commit:abc
| | VERIFICATION_STATUS: HELD
| | EVIDENCE_REFS: NONE
| | DERIVED_FROM: NONE
| | CORRECTS_ENTRY: NONE
| | UNCERTAINTY: NONE_DECLARED
| | }=============================================================|
| | COLLECTION_STATUS
| | REQUIRED_CLASSES: EVIDENCE
| | }=============================================================|
| | IDX_ADMISSION
| | SPINE_SHA256: CANDIDATE_BYTES_HASH_IN_RECEIPT
| | ADMISSION_STATUS: CANDIDATE
| | }=============================================================|
| | TERMINAL
| | RESIDUAL_UNCERTAINTY: NONE_DECLARED
| | }=============================================================|
| | \xe2\x96\x88\xe2\x80\xa0\xe2\x96\x88 Holo/Sim \xe2\x96\x88\xe2\x80\xa0\xe2\x96\x88 \xe2\x96\x88\xe2\x80\xa0\xe2\x96\x88 HSSCE \xe2\x96\x88\xe2\x80\xa0\xe2\x96\x88
| |==============================================================|
"""


def _key(tmp_path: Path, name: str) -> tuple[Path, Path]:
    key = tmp_path / name
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True, capture_output=True,
    )
    signers = tmp_path / f"{name}.allowed"
    signers.write_text("anchor " + key.with_suffix(".pub").read_text(), encoding="utf-8")
    return key, signers


def _signed(tmp_path: Path) -> tuple[bytes, dict, Path]:
    key, signers = _key(tmp_path, "origin")
    candidate = _candidate()
    checkpoint = sign_origin_checkpoint(
        candidate=candidate, validator_id="idx:v1", contributor_id=None,
        signer_identity="anchor", private_key_path=key,
    )
    return candidate, checkpoint, signers


def test_exact_candidate_and_external_public_key_verify(tmp_path: Path) -> None:
    candidate, checkpoint, signers = _signed(tmp_path)
    result = verify_origin_checkpoint(
        candidate=candidate, checkpoint=checkpoint, allowed_signers_path=signers,
    )
    assert result["status"] == "VERIFIED"
    assert result["verified"] is True
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert "private" not in str(checkpoint).lower()


def test_changed_bytes_cannot_reuse_checkpoint(tmp_path: Path) -> None:
    candidate, checkpoint, signers = _signed(tmp_path)
    result = verify_origin_checkpoint(
        candidate=candidate.replace(b"commit:abc", b"commit:xyz"),
        checkpoint=checkpoint, allowed_signers_path=signers,
    )
    assert result["status"] == "REJECTED_BINDING"


def test_different_trust_root_rejects(tmp_path: Path) -> None:
    candidate, checkpoint, _ = _signed(tmp_path)
    _, other_signers = _key(tmp_path, "other")
    result = verify_origin_checkpoint(
        candidate=candidate, checkpoint=checkpoint,
        allowed_signers_path=other_signers,
    )
    assert result["status"] == "REJECTED_SIGNATURE"


def test_signer_substitution_rejects(tmp_path: Path) -> None:
    candidate, checkpoint, signers = _signed(tmp_path)
    checkpoint["signer_identity"] = "someone-else"
    result = verify_origin_checkpoint(
        candidate=candidate, checkpoint=checkpoint, allowed_signers_path=signers,
    )
    assert result["status"] == "REJECTED_SIGNATURE"


def test_invalid_candidate_cannot_be_signed(tmp_path: Path) -> None:
    key, _ = _key(tmp_path, "origin")
    with pytest.raises(SignedOriginCheckpointError, match="failed Spine admission"):
        sign_origin_checkpoint(
            candidate=_candidate().replace(b"E-001", b" "),
            validator_id="idx:v1", contributor_id=None,
            signer_identity="anchor", private_key_path=key,
        )


def test_authority_injection_rejected(tmp_path: Path) -> None:
    candidate, checkpoint, signers = _signed(tmp_path)
    checkpoint["write_authority"] = "GRANTED"
    with pytest.raises(SignedOriginCheckpointError, match="schema mismatch"):
        verify_origin_checkpoint(
            candidate=candidate, checkpoint=checkpoint,
            allowed_signers_path=signers,
        )
