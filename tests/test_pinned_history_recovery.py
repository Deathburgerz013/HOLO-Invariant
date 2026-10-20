"""Integration tests for externally pinned history recovery."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from holosim.canonical import canonical_bytes
from holosim.core import HoloChain
from holosim.pinned_history_recovery import recover_with_pinned_signer_policy
from holosim.witnessed_history_recovery import sign_history_witness


pytestmark = pytest.mark.skipif(
    shutil.which("ssh-keygen") is None,
    reason="OpenSSH required",
)


def test_policy_substitution_rejected(tmp_path):
    def create_signer(folder):
        folder.mkdir()
        key = folder / "key"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
            check=True,
            capture_output=True,
        )
        policy = folder / "allowed"
        policy.write_text(
            "fixture " + Path(str(key) + ".pub").read_text(),
            encoding="utf-8",
        )
        return key, policy

    original_key, original_policy = create_signer(tmp_path / "original")
    attacker_key, attacker_policy = create_signer(tmp_path / "attacker")

    trusted_digest = hashlib.sha256(
        original_policy.read_bytes()
    ).hexdigest()

    chain = tmp_path / "attacker-chain.jsonl"
    HoloChain(chain).append("replacement history")

    witness = tmp_path / "attacker-witness.json"
    witness.write_bytes(canonical_bytes(sign_history_witness(
        chain_path=chain,
        chain_id="fixture-chain",
        signer_identity="fixture",
        private_key_path=attacker_key,
    )))

    common = dict(
        chain_path=chain,
        witness_path=witness,
        expected_chain_id="fixture-chain",
        expected_policy_sha256=trusted_digest,
    )

    # Substituted policy cannot satisfy the original trusted digest.
    rejected = recover_with_pinned_signer_policy(
        **common,
        allowed_signers_path=attacker_policy,
    )

    assert rejected["status"] == "REJECTED_POLICY"
    assert rejected["matched"] is False
    assert rejected["accepted"] is False
    assert rejected["policy_custody_verified"] is False

    # Original policy passes digest verification but rejects attacker key.
    rejected_signature = recover_with_pinned_signer_policy(
        **common,
        allowed_signers_path=original_policy,
    )

    assert rejected_signature["status"] == "REJECTED_SIGNATURE"
    assert rejected_signature["matched"] is False
    assert rejected_signature["policy_digest_matched"] is True

    # Legitimately signed history can still match the pinned policy.
    witness.write_bytes(canonical_bytes(sign_history_witness(
        chain_path=chain,
        chain_id="fixture-chain",
        signer_identity="fixture",
        private_key_path=original_key,
    )))

    matched = recover_with_pinned_signer_policy(
        **common,
        allowed_signers_path=original_policy,
    )

    assert matched["status"] == "MATCHED"
    assert matched["matched"] is True
    assert matched["policy_digest_matched"] is True
    assert matched["policy_custody_verified"] is False
    assert matched["accepted"] is False
    assert matched["truth_claimed"] is False
    assert matched["write_authority"] == "NONE"
    assert matched["execution_authority"] == "NONE"
def test_recovery_uses_captured_policy_after_source_replacement(
    tmp_path, monkeypatch
):
    import hashlib

    import holosim.pinned_history_recovery as module

    original = b"original signer policy\n"
    replacement = b"attacker signer policy\n"

    policy = tmp_path / "allowed"
    policy.write_bytes(original)

    observed = {}

    def fake_recovery(**kwargs):
        observed["verified_policy"] = Path(
            kwargs["allowed_signers_path"]
        ).read_bytes()

        return {
            "status": "MATCHED",
            "matched": True,
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }

    real_capture = module.capture_pinned_signer_policy

    def capture_then_replace(**kwargs):
        captured = real_capture(**kwargs)
        policy.write_bytes(replacement)
        return captured

    monkeypatch.setattr(
        module, "capture_pinned_signer_policy", capture_then_replace
    )
    monkeypatch.setattr(
        module, "recover_witnessed_history", fake_recovery
    )

    result = module.recover_with_pinned_signer_policy(
        chain_path=tmp_path / "chain",
        witness_path=tmp_path / "witness",
        expected_chain_id="fixture",
        allowed_signers_path=policy,
        expected_policy_sha256=hashlib.sha256(original).hexdigest(),
    )

    assert observed["verified_policy"] == original
    assert policy.read_bytes() == replacement
    assert result["policy_digest_matched"] is True
    assert result["policy_custody_verified"] is False
    assert result["accepted"] is False
