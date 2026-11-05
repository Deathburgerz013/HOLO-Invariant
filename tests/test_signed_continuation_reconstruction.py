"""Tests for signed continuation reconstruction boundaries."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest

from holosim.signed_continuation_reconstruction import (
    reconstruct_signed_continuation,
)
from tests.test_signed_continuation_reentry import evidence as signed_evidence


@pytest.fixture
def evidence(signed_evidence):
    return signed_evidence


def run_reconstruction(evidence, **overrides):
    arguments = {
        "candidate": evidence["candidate"],
        "checkpoint": evidence["checkpoint"],
        "handoff": evidence["original"],
        "entry_id": "E-001",
        "allowed_signers_path": evidence["policy"],
        "expected_policy_sha256": evidence["pin"],
    }
    arguments.update(overrides)
    return reconstruct_signed_continuation(**arguments)


def assert_no_authority(result):
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert result["policy_custody_verified"] is False


def test_valid_signed_continuation_reconstructs(evidence):
    result = run_reconstruction(evidence)

    assert result["status"] == "VERIFIED_RECONSTRUCTION"
    assert result["verified"] is True
    assert result["handoff_hash"] == evidence["original"]["handoff_hash"]
    assert result["packet_hash"] == evidence["original"]["portable_bundle"]["packet"]["packet_hash"]
    assert_no_authority(result)


def test_wrong_entry_never_reaches_resume(evidence):
    with patch(
        "holosim.signed_continuation_reconstruction.resume_operator_handoff"
    ) as resume:
        result = run_reconstruction(evidence, entry_id="NONEXISTENT")

    assert result["status"] == "REJECTED_SIGNED_BINDING"
    assert result["verified"] is False
    resume.assert_not_called()
    assert_no_authority(result)


def test_tampered_candidate_never_reaches_resume(evidence):
    with patch(
        "holosim.signed_continuation_reconstruction.resume_operator_handoff"
    ) as resume:
        result = run_reconstruction(
            evidence,
            candidate=evidence["candidate"] + b"\nTAMPER",
        )

    assert result["status"] == "REJECTED_SIGNED_BINDING"
    resume.assert_not_called()
    assert_no_authority(result)


def test_different_valid_handoff_never_reaches_resume(evidence):
    with patch(
        "holosim.signed_continuation_reconstruction.resume_operator_handoff"
    ) as resume:
        result = run_reconstruction(
            evidence,
            handoff=evidence["replacement"],
        )

    assert result["status"] == "REJECTED_SIGNED_BINDING"
    resume.assert_not_called()
    assert_no_authority(result)


def test_resume_exception_fails_closed(evidence):
    from holosim.operator_resume_handoff import OperatorResumeHandoffError

    with patch(
        "holosim.signed_continuation_reconstruction.resume_operator_handoff",
        side_effect=OperatorResumeHandoffError("reconstruction failed"),
    ):
        result = run_reconstruction(evidence)

    assert result["status"] == "REJECTED_RECONSTRUCTION"
    assert result["verified"] is False
    assert_no_authority(result)


def test_resume_authority_escalation_rejected(evidence):
    with patch(
        "holosim.signed_continuation_reconstruction.resume_operator_handoff",
        return_value={
            "status": "OPERATOR_RESUME_READY",
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "WRITE",
            "execution_authority": "NONE",
        },
    ):
        result = run_reconstruction(evidence)

    assert result["status"] == "REJECTED_RECONSTRUCTION"
    assert_no_authority(result)


def test_reconstructed_state_is_not_same_object_as_source(evidence):
    result = run_reconstruction(evidence)

    assert result["status"] == "VERIFIED_RECONSTRUCTION"
    assert result["working_state"] == evidence["original"]["portable_bundle"]["packet"]["reconstructed_state"]
    assert result["working_state"] is not evidence["original"]["portable_bundle"]["packet"]["reconstructed_state"]
    assert_no_authority(result)


def test_successful_looking_resume_cannot_substitute_state(evidence):
    from holosim.operator_resume_handoff import resume_operator_handoff

    substituted = resume_operator_handoff(evidence["original"])
    substituted["working_state"] = {"substituted": True}

    with patch(
        "holosim.signed_continuation_reconstruction.resume_operator_handoff",
        return_value=substituted,
    ):
        result = run_reconstruction(evidence)

    assert result["status"] == "REJECTED_RECONSTRUCTION_BINDING"
    assert result["verified"] is False
    assert "working_state" not in result
    assert_no_authority(result)


def test_successful_looking_resume_cannot_substitute_identity(evidence):
    from holosim.operator_resume_handoff import resume_operator_handoff

    substituted = resume_operator_handoff(evidence["original"])
    substituted["handoff_hash"] = "0" * 64

    with patch(
        "holosim.signed_continuation_reconstruction.resume_operator_handoff",
        return_value=substituted,
    ):
        result = run_reconstruction(evidence)

    assert result["status"] == "REJECTED_RECONSTRUCTION_BINDING"
    assert result["verified"] is False
    assert_no_authority(result)
