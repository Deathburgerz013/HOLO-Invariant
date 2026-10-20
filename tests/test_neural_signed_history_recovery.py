"""Adversarial tests for signed neural history recovery."""
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.neural_continuity_absence import NeuralContinuityError
from experiments.neural_signed_history_recovery import recover_signed_neural_history
from holosim.canonical import canonical_bytes
from holosim.core import HoloChain
from holosim.witnessed_history_recovery import sign_history_witness

pytestmark = pytest.mark.skipif(
    shutil.which("ssh-keygen") is None,
    reason="OpenSSH required",
)


def test_chain_replacement_after_witness_verification_is_rejected(tmp_path):
    external = tmp_path / "external"
    external.mkdir()

    key = external / "key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
        capture_output=True,
    )

    policy = external / "allowed"
    policy.write_text(
        "fixture " + Path(str(key) + ".pub").read_text(),
        encoding="utf-8",
    )

    chain = tmp_path / "chain.jsonl"
    HoloChain(chain).append([[1, 1], 1])
    original = chain.read_bytes()

    witness = external / "witness.json"
    witness.write_bytes(canonical_bytes(sign_history_witness(
        chain_path=chain,
        chain_id="neural-fixture",
        signer_identity="fixture",
        private_key_path=key,
    )))

    replacement = tmp_path / "replacement.jsonl"
    HoloChain(replacement).append([[0, 0], 1])
    forged = replacement.read_bytes()

    import experiments.neural_signed_history_recovery as module

    original_verify = module.recover_witnessed_history

    def replace_after_verification(**kwargs):
        receipt = original_verify(**kwargs)
        assert receipt["status"] == "MATCHED"
        chain.write_bytes(forged)
        return receipt

    try:
        with patch.object(
            module,
            "recover_witnessed_history",
            side_effect=replace_after_verification,
        ):
            result = recover_signed_neural_history(
                chain_path=chain,
                witness_path=witness,
                expected_chain_id="neural-fixture",
                allowed_signers_path=policy,
                dimensions=2,
            )
            assert result["signed_chain_matched"] is True
            assert result["weights"] == [1, 1]
            assert result["bias"] == 1
            assert result["event_count"] == 1
            assert result["accepted"] is False
            assert result["write_authority"] == "NONE"
            assert result["execution_authority"] == "NONE"
    finally:
        chain.write_bytes(original)


def test_verified_snapshot_replacement_preserves_captured_history(tmp_path):
    external = tmp_path / "external"
    external.mkdir()

    key = external / "key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
        capture_output=True,
    )

    policy = external / "allowed"
    policy.write_text(
        "fixture " + Path(str(key) + ".pub").read_text(),
        encoding="utf-8",
    )

    chain = tmp_path / "chain.jsonl"
    HoloChain(chain).append([[1, 1], 1])

    witness = external / "witness.json"
    witness.write_bytes(canonical_bytes(sign_history_witness(
        chain_path=chain,
        chain_id="neural-fixture",
        signer_identity="fixture",
        private_key_path=key,
    )))

    replacement = tmp_path / "replacement.jsonl"
    HoloChain(replacement).append([[0, 0], 1])
    forged = replacement.read_bytes()

    import experiments.neural_signed_history_recovery as module

    original_verify = module.recover_witnessed_history

    def replace_verified_snapshot(**kwargs):
        receipt = original_verify(**kwargs)
        assert receipt["status"] == "MATCHED"
        Path(kwargs["chain_path"]).write_bytes(forged)
        return receipt

    with patch.object(
        module,
        "recover_witnessed_history",
        side_effect=replace_verified_snapshot,
    ):
        result = recover_signed_neural_history(
            chain_path=chain,
            witness_path=witness,
            expected_chain_id="neural-fixture",
            allowed_signers_path=policy,
            dimensions=2,
        )

        assert result["signed_chain_matched"] is True
        assert result["weights"] == [1, 1]
        assert result["bias"] == 1
        assert result["event_count"] == 1
        assert result["accepted"] is False
        assert result["truth_claimed"] is False
        assert result["write_authority"] == "NONE"
        assert result["execution_authority"] == "NONE"


def test_replay_copy_tampering_is_rejected(tmp_path):
    external = tmp_path / "external"
    external.mkdir()

    key = external / "key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
        capture_output=True,
    )

    policy = external / "allowed"
    policy.write_text(
        "fixture " + Path(str(key) + ".pub").read_text(),
        encoding="utf-8",
    )

    chain = tmp_path / "chain.jsonl"
    HoloChain(chain).append([[1, 1], 1])

    witness = external / "witness.json"
    witness.write_bytes(canonical_bytes(sign_history_witness(
        chain_path=chain,
        chain_id="neural-fixture",
        signer_identity="fixture",
        private_key_path=key,
    )))

    replacement = tmp_path / "replacement.jsonl"
    HoloChain(replacement).append([[0, 0], 1])
    forged = replacement.read_bytes()

    import experiments.neural_signed_history_recovery as module

    original_load = module.HoloChain.load_and_verify

    def tamper_replay(self):
        if self.file_path.name == "replay.jsonl":
            self.file_path.write_bytes(forged)
        return original_load(self)

    with patch.object(
        module.HoloChain,
        "load_and_verify",
        tamper_replay,
    ):
        with pytest.raises(NeuralContinuityError):
            recover_signed_neural_history(
                chain_path=chain,
                witness_path=witness,
                expected_chain_id="neural-fixture",
                allowed_signers_path=policy,
                dimensions=2,
            )


def test_empty_signed_history_is_rejected(tmp_path):
    external = tmp_path / "external"
    external.mkdir()

    key = external / "key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
        capture_output=True,
    )

    policy = external / "allowed"
    policy.write_text(
        "fixture " + Path(str(key) + ".pub").read_text(),
        encoding="utf-8",
    )

    chain = tmp_path / "empty.jsonl"
    chain.write_bytes(b"")

    witness = external / "witness.json"
    witness.write_bytes(canonical_bytes(sign_history_witness(
        chain_path=chain,
        chain_id="neural-fixture",
        signer_identity="fixture",
        private_key_path=key,
    )))

    with pytest.raises(NeuralContinuityError):
        recover_signed_neural_history(
            chain_path=chain,
            witness_path=witness,
            expected_chain_id="neural-fixture",
            allowed_signers_path=policy,
            dimensions=2,
        )
