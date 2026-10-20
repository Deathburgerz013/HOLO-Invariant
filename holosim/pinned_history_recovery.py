"""Recovery with an externally pinned SSH allowed-signers policy."""

from __future__ import annotations

import tempfile
from pathlib import Path

from holosim.signer_policy_custody import (
    SignerPolicyCustodyError,
    capture_pinned_signer_policy,
)
from holosim.witnessed_history_recovery import recover_witnessed_history


def recover_with_pinned_signer_policy(
    *,
    chain_path,
    witness_path,
    expected_chain_id,
    allowed_signers_path,
    expected_policy_sha256,
    ssh_keygen="ssh-keygen",
):
    """Require a matching external policy digest before witness verification.

    The caller must independently authenticate expected_policy_sha256.
    No historical occurrence, policy provenance, or authority is established.
    """
    try:
        policy_bytes = capture_pinned_signer_policy(
            allowed_signers_path=allowed_signers_path,
            expected_sha256=expected_policy_sha256,
        )
    except SignerPolicyCustodyError:
        return {
            "status": "REJECTED_POLICY",
            "matched": False,
            "accepted": False,
            "truth_claimed": False,
            "policy_custody_verified": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }

    with tempfile.TemporaryDirectory(prefix="holo-pinned-policy-") as folder:
        captured_policy = Path(folder) / "allowed_signers"
        captured_policy.write_bytes(policy_bytes)

        receipt = recover_witnessed_history(
            chain_path=chain_path,
            witness_path=witness_path,
            expected_chain_id=expected_chain_id,
            allowed_signers_path=captured_policy,
            ssh_keygen=ssh_keygen,
        )

    return {
        **receipt,
        "policy_digest_matched": True,
        "policy_custody_verified": False,
    }
