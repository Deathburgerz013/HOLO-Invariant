"""Verify signed Spine continuation binding without granting authority."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from holosim.operator_resume_handoff import (
    OperatorResumeHandoffError,
    validate_operator_resume_handoff,
)
from holosim.pinned_origin_checkpoint import verify_origin_with_pinned_policy
from holosim.signed_origin_checkpoint import SignedOriginCheckpointError
from holosim.spine_admission import (
    SpineAdmissionError,
    _compartments,
    build_spine_admission_receipt,
)


def verify_signed_continuation_reentry(
    *,
    candidate: bytes,
    checkpoint: Mapping[str, Any],
    handoff: Mapping[str, Any],
    entry_id: str,
    allowed_signers_path: str | Path,
    expected_policy_sha256: str,
    ssh_keygen: str = "ssh-keygen",
) -> dict[str, Any]:
    """Check one signed ENTRY reference against one validated handoff."""

    def result(status: str) -> dict[str, Any]:
        return {
            "type": "signed_continuation_reentry_verification",
            "version": 1,
            "status": status,
            "verified": status == "VERIFIED",
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
            "policy_custody_verified": False,
        }

    if type(candidate) is not bytes or not candidate:
        return result("REJECTED_CANDIDATE")

    if type(entry_id) is not str or not entry_id.strip():
        return result("REJECTED_ENTRY")

    try:
        validate_operator_resume_handoff(handoff)
    except OperatorResumeHandoffError:
        return result("REJECTED_HANDOFF")

    handoff_hash = handoff["handoff_hash"]

    try:
        origin = verify_origin_with_pinned_policy(
            candidate=candidate,
            checkpoint=checkpoint,
            allowed_signers_path=allowed_signers_path,
            expected_policy_sha256=expected_policy_sha256,
            ssh_keygen=ssh_keygen,
        )
    except (SignedOriginCheckpointError, OSError, ValueError):
        return result("REJECTED_ORIGIN")

    if (
        origin.get("status") != "VERIFIED"
        or origin.get("verified") is not True
        or origin.get("policy_digest_matched") is not True
    ):
        return result("REJECTED_ORIGIN")

    try:
        candidate_text = candidate.decode("utf-8")
    except UnicodeDecodeError:
        return result("REJECTED_CANDIDATE")

    try:
        admission = build_spine_admission_receipt(
            candidate_text,
            validator_id=checkpoint["validator_id"],
            contributor_id=checkpoint["contributor_id"],
        )
    except SpineAdmissionError:
        return result("REJECTED_CANDIDATE")

    if admission["decision"] != "ADMITTED":
        return result("REJECTED_CANDIDATE")

    entries = [
        item
        for item in _compartments(candidate_text)
        if item["name"] == "ENTRY"
    ]

    selected = [
        item
        for item in entries
        if item["fields"].get("ENTRY_ID") == entry_id
    ]

    if len(selected) != 1:
        return result("REJECTED_ENTRY")

    expected_reference = f"handoff-sha256:{handoff_hash}"

    references = [
        item
        for item in entries
        if item["fields"].get("SOURCE") == expected_reference
    ]

    if len(references) != 1:
        return result("REJECTED_BINDING")

    if selected[0] is not references[0]:
        return result("REJECTED_BINDING")

    return result("VERIFIED")
