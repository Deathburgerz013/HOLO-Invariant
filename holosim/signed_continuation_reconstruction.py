"""Reconstruct an operator handoff only after signed continuation verification."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from holosim.operator_resume_handoff import (
    OperatorResumeHandoffError,
    resume_operator_handoff,
)
from holosim.portable_verified_reentry import PortableVerifiedReentryError
from holosim.signed_continuation_reentry import (
    verify_signed_continuation_reentry,
)


def reconstruct_signed_continuation(
    *,
    candidate: bytes,
    checkpoint: Mapping[str, Any],
    handoff: Mapping[str, Any],
    entry_id: str,
    allowed_signers_path: str | Path,
    expected_policy_sha256: str,
    ssh_keygen: str = "ssh-keygen",
) -> dict[str, Any]:
    """Verify signed binding before reconstructing non-authoritative state."""

    def rejected(status: str) -> dict[str, Any]:
        return {
            "type": "signed_continuation_reconstruction",
            "version": 1,
            "status": status,
            "verified": False,
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
            "policy_custody_verified": False,
        }

    verification = verify_signed_continuation_reentry(
        candidate=candidate,
        checkpoint=checkpoint,
        handoff=handoff,
        entry_id=entry_id,
        allowed_signers_path=allowed_signers_path,
        expected_policy_sha256=expected_policy_sha256,
        ssh_keygen=ssh_keygen,
    )

    if (
        verification.get("status") != "VERIFIED"
        or verification.get("verified") is not True
    ):
        return rejected("REJECTED_SIGNED_BINDING")

    try:
        resumed = resume_operator_handoff(handoff)
    except (
        OperatorResumeHandoffError,
        PortableVerifiedReentryError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return rejected("REJECTED_RECONSTRUCTION")

    if (
        resumed.get("status") != "OPERATOR_RESUME_READY"
        or resumed.get("truth_claimed") is not False
        or resumed.get("accepted") is not False
        or resumed.get("write_authority") != "NONE"
        or resumed.get("execution_authority") != "NONE"
    ):
        return rejected("REJECTED_RECONSTRUCTION")

    # A successful-looking resume must still match the verified handoff.
    # Never allow the reconstruction dependency to substitute state.
    packet = handoff["portable_bundle"]["packet"]

    expected_fields = {
        "handoff_id": handoff["handoff_id"],
        "handoff_hash": handoff["handoff_hash"],
        "packet_hash": packet["packet_hash"],
        "objective": handoff["objective"],
        "completed": handoff["completed"],
        "constraints": handoff["constraints"],
        "unresolved": handoff["unresolved"],
        "next_action": handoff["next_action"],
        "restart_cost": handoff["restart_cost"],
        "working_state": packet["reconstructed_state"],
    }

    if any(
        type(resumed.get(field)) is not type(expected)
        or resumed.get(field) != expected
        for field, expected in expected_fields.items()
    ):
        return rejected("REJECTED_RECONSTRUCTION_BINDING")

    return {
        "type": "signed_continuation_reconstruction",
        "version": 1,
        "status": "VERIFIED_RECONSTRUCTION",
        "verified": True,
        "handoff_id": resumed["handoff_id"],
        "handoff_hash": resumed["handoff_hash"],
        "packet_hash": resumed["packet_hash"],
        "objective": resumed["objective"],
        "completed": resumed["completed"],
        "constraints": resumed["constraints"],
        "unresolved": resumed["unresolved"],
        "next_action": resumed["next_action"],
        "restart_cost": resumed["restart_cost"],
        "working_state": resumed["working_state"],
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "policy_custody_verified": False,
    }
