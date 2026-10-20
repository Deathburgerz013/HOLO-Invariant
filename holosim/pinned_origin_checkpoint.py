"""Origin-checkpoint verification against externally pinned policy bytes.

The caller must independently authenticate the expected digest.
Digest agreement does not establish policy provenance or authority.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from holosim.signed_origin_checkpoint import verify_origin_checkpoint
from holosim.signer_policy_custody import (
    SignerPolicyCustodyError,
    capture_pinned_signer_policy,
)


def verify_origin_with_pinned_policy(
    *,
    candidate,
    checkpoint,
    allowed_signers_path,
    expected_policy_sha256,
    ssh_keygen="ssh-keygen",
):
    try:
        policy_bytes = capture_pinned_signer_policy(
            allowed_signers_path=allowed_signers_path,
            expected_sha256=expected_policy_sha256,
        )
    except SignerPolicyCustodyError:
        return {
            "status": "REJECTED_POLICY",
            "verified": False,
            "policy_digest_matched": False,
            "policy_custody_verified": False,
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }

    with tempfile.TemporaryDirectory(prefix="holo-origin-pinned-") as folder:
        captured_path = Path(folder) / "allowed_signers"
        captured_path.write_bytes(policy_bytes)

        result = verify_origin_checkpoint(
            candidate=candidate,
            checkpoint=checkpoint,
            allowed_signers_path=captured_path,
            ssh_keygen=ssh_keygen,
        )

    return {
        **result,
        "policy_digest_matched": True,
        "policy_custody_verified": False,
    }
