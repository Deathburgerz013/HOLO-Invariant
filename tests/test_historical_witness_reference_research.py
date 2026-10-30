"""Research: historical witness digest comparison under replacement."""

import shutil
import subprocess
from pathlib import Path

import pytest

from holosim.canonical import canonical_bytes, stable_hash
from holosim.core import HoloChain
from holosim.policy_anchor_consistency import compare_policy_anchor
from holosim.witnessed_history_recovery import (
    recover_witnessed_history,
    sign_history_witness,
)

pytestmark = pytest.mark.skipif(
    shutil.which("ssh-keygen") is None,
    reason="OpenSSH required",
)


def test_historical_witness_reference_under_replacement(tmp_path: Path):
    key = tmp_path / "key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
        capture_output=True,
    )

    policy = tmp_path / "allowed"
    policy.write_text(
        "fixture " + Path(str(key) + ".pub").read_text(),
        encoding="utf-8",
    )

    chain = tmp_path / "chain.jsonl"
    HoloChain(chain).append("original")

    witness_path = tmp_path / "witness.json"
    original_witness = sign_history_witness(
        chain_path=chain,
        chain_id="fixture-chain",
        signer_identity="fixture",
        private_key_path=key,
    )
    witness_path.write_bytes(canonical_bytes(original_witness))

    original_digest = stable_hash(original_witness)

    args = dict(
        chain_path=chain,
        witness_path=witness_path,
        expected_chain_id="fixture-chain",
        allowed_signers_path=policy,
    )

    original_receipt = recover_witnessed_history(**args)
    assert original_receipt["status"] == "MATCHED"
    assert original_receipt["witness_hash"] == original_digest

    original_comparison = compare_policy_anchor(
        proposed_sha256=original_receipt["witness_hash"],
        provisioned_sha256=original_digest,
    )
    assert original_comparison.status == "MATCHED"

    # Replace both history and witness using the same authorized key.
    HoloChain(chain).append("replacement")

    replacement_witness = sign_history_witness(
        chain_path=chain,
        chain_id="fixture-chain",
        signer_identity="fixture",
        private_key_path=key,
    )
    witness_path.write_bytes(canonical_bytes(replacement_witness))

    replacement_receipt = recover_witnessed_history(**args)

    # Signature validity alone cannot identify the original witness.
    assert replacement_receipt["status"] == "MATCHED"

    replacement_digest = replacement_receipt["witness_hash"]
    assert replacement_digest != original_digest

    retained_reference = compare_policy_anchor(
        proposed_sha256=replacement_digest,
        provisioned_sha256=original_digest,
    )
    assert retained_reference.status == "MISMATCH"

    attacker_reference = compare_policy_anchor(
        proposed_sha256=replacement_digest,
        provisioned_sha256=replacement_digest,
    )
    assert attacker_reference.status == "MATCHED"

    missing_reference = compare_policy_anchor(
        proposed_sha256=replacement_digest,
        provisioned_sha256=None,
    )
    assert missing_reference.status == "UNKNOWN"

    for comparison in (
        original_comparison,
        retained_reference,
        attacker_reference,
        missing_reference,
    ):
        assert comparison.provenance_authenticated is False
        assert comparison.accepted is False
        assert comparison.truth_claimed is False
        assert comparison.write_authority == "NONE"
        assert comparison.execution_authority == "NONE"
        assert comparison.trust_root_authority == "NONE"

    assert replacement_receipt["accepted"] is False
    assert replacement_receipt["truth_claimed"] is False
    assert replacement_receipt["write_authority"] == "NONE"
    assert replacement_receipt["execution_authority"] == "NONE"
