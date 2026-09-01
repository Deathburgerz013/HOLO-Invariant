from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

from holosim.verified_artifact_recovery import (
    VerifiedArtifactRecoveryError,
    recover_verified_artifact,
    validate_verified_artifact_recovery_receipt,
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_corrupted_artifact_is_preserved_and_atomically_recovered(tmp_path):
    good = b"known-good-binary\x00\x01"
    bad = b"corrupted-binary\xff"
    source = tmp_path / "trusted" / "program.exe"
    target = tmp_path / "runtime" / "program.exe"
    quarantine = tmp_path / "quarantine"
    source.parent.mkdir()
    target.parent.mkdir()
    source.write_bytes(good)
    target.write_bytes(bad)

    receipt = recover_verified_artifact(
        target, source, expected_sha256=sha(good),
        quarantine_directory=quarantine,
    )

    assert target.read_bytes() == good
    assert receipt["status"] == "RECOVERED"
    assert receipt["observed_target_sha256"] == sha(bad)
    assert receipt["recovered_target_sha256"] == sha(good)
    assert receipt["mutation_applied"] is True
    assert receipt["live_process_memory_modified"] is False
    assert receipt["automatic_execution"] is False
    assert receipt["execution_authority"] == "NONE"
    assert receipt["quarantine_path"]
    assert __import__("pathlib").Path(receipt["quarantine_path"]).read_bytes() == bad
    assert validate_verified_artifact_recovery_receipt(receipt) is True


def test_untrusted_replacement_is_rejected_before_target_mutation(tmp_path):
    target = tmp_path / "program.bin"
    source = tmp_path / "claimed-good.bin"
    quarantine = tmp_path / "quarantine"
    target.write_bytes(b"corrupt")
    source.write_bytes(b"wrong-source")

    receipt = recover_verified_artifact(
        target, source, expected_sha256=sha(b"actual-good"),
        quarantine_directory=quarantine,
    )

    assert receipt["status"] == "REJECTED_SOURCE_MISMATCH"
    assert receipt["mutation_applied"] is False
    assert target.read_bytes() == b"corrupt"
    assert list(quarantine.iterdir()) == []
    assert validate_verified_artifact_recovery_receipt(receipt) is True


def test_matching_target_requires_no_write_or_quarantine(tmp_path):
    data = b"already-correct"
    target = tmp_path / "target.bin"
    source = tmp_path / "source.bin"
    quarantine = tmp_path / "quarantine"
    target.write_bytes(data)
    source.write_bytes(data)

    receipt = recover_verified_artifact(
        target, source, expected_sha256=sha(data),
        quarantine_directory=quarantine,
    )

    assert receipt["status"] == "NO_ACTION"
    assert receipt["mutation_applied"] is False
    assert receipt["quarantine_path"] is None
    assert target.read_bytes() == data


def test_missing_target_can_be_recovered_without_fabricated_quarantine(tmp_path):
    data = b"restored"
    source = tmp_path / "source.bin"
    target = tmp_path / "missing" / "target.bin"
    source.write_bytes(data)

    receipt = recover_verified_artifact(
        target, source, expected_sha256=sha(data),
        quarantine_directory=tmp_path / "quarantine",
    )

    assert receipt["status"] == "RECOVERED"
    assert receipt["observed_target_sha256"] is None
    assert receipt["quarantine_path"] is None
    assert receipt["corrupted_bytes_preserved"] is False
    assert target.read_bytes() == data


def test_symlink_target_fails_closed(tmp_path):
    source = tmp_path / "source.bin"
    real_target = tmp_path / "real.bin"
    link = tmp_path / "link.bin"
    source.write_bytes(b"good")
    real_target.write_bytes(b"bad")
    try:
        link.symlink_to(real_target)
    except OSError:
        pytest.skip("symlink creation unavailable")

    with pytest.raises(VerifiedArtifactRecoveryError, match="symbolic link"):
        recover_verified_artifact(
            link, source, expected_sha256=sha(b"good"),
            quarantine_directory=tmp_path / "quarantine",
        )
    assert real_target.read_bytes() == b"bad"


def test_tampered_recovery_receipt_fails_closed(tmp_path):
    data = b"correct"
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(data)
    target.write_bytes(b"wrong")
    receipt = recover_verified_artifact(
        target, source, expected_sha256=sha(data),
        quarantine_directory=tmp_path / "quarantine",
    )
    tampered = deepcopy(receipt)
    tampered["recovered_target_sha256"] = "0" * 64

    with pytest.raises(VerifiedArtifactRecoveryError, match="target hash mismatch"):
        validate_verified_artifact_recovery_receipt(tampered)
