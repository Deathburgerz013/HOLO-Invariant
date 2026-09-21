import pytest

from holosim.continuity_under_absence import (
    ContinuityUnderAbsenceError,
    build_continuity_receipt,
    reconstruct_continuity,
)
from holosim.environment_invariant_receipts import (
    EnvironmentInvariantReceiptError,
    evaluate_environment_invariant,
)


def _receipt():
    return build_continuity_receipt(
        prior_state={"environment": "present", "value": 1},
        current_state={"environment": "present", "value": 7},
        observer_present_before=True,
        observer_present_after=False,
    )


def _verified_environment_receipt():
    environment = {"environment": "present", "value": 7}
    return evaluate_environment_invariant(
        invariant_id="absence-current-state",
        statement="the externally observed environment matches the declared state",
        scope={"phase": "post_absence"},
        environment=environment,
        environment_probe=lambda: environment,
        check=lambda: True,
        check_id="absence-current-state-check",
        observed_at="2026-09-20T21:00:00-07:00",
    )


def test_reconstruction_requires_external_evidence():
    with pytest.raises(ContinuityUnderAbsenceError, match="external evidence"):
        reconstruct_continuity(_receipt(), external_evidence=None)


def test_malformed_external_evidence_fails_verification():
    with pytest.raises(ContinuityUnderAbsenceError, match="failed verification"):
        reconstruct_continuity(_receipt(), external_evidence={})


def test_verified_environment_receipt_is_valid_external_evidence():
    evidence = _verified_environment_receipt()

    from holosim.environment_invariant_receipts import verify_environment_invariant_receipt
    assert verify_environment_invariant_receipt(evidence) is True


def test_unverified_environment_receipt_cannot_be_used():
    evidence = _verified_environment_receipt()
    evidence["observed_environment"]["value"] = 999

    with pytest.raises(EnvironmentInvariantReceiptError):
        from holosim.environment_invariant_receipts import verify_environment_invariant_receipt
        verify_environment_invariant_receipt(evidence)


def test_rehashed_forged_environment_receipt_is_detected_as_stale():
    from holosim.canonical import stable_hash
    from holosim.environment_invariant_receipts import verify_environment_invariant_receipt

    evidence = _verified_environment_receipt()
    evidence["observed_environment"] = {"environment": "forged", "value": 999}
    evidence["environment_fingerprint"] = stable_hash(evidence["observed_environment"])
    evidence["status"] = "STALE"
    evidence["stale_reason"] = "DECLARED_ENVIRONMENT_MISMATCH"
    body = {key: value for key, value in evidence.items() if key != "receipt_hash"}
    evidence["receipt_hash"] = stable_hash(body)

    assert verify_environment_invariant_receipt(evidence) is True
    assert evidence["status"] == "STALE"


def test_stale_verified_receipt_cannot_reconstruct_continuity():
    from holosim.canonical import stable_hash

    receipt = _receipt()
    evidence = _verified_environment_receipt()
    evidence["observed_environment"] = {"environment": "changed", "value": 999}
    evidence["environment_fingerprint"] = stable_hash(evidence["observed_environment"])
    evidence["status"] = "STALE"
    evidence["stale_reason"] = "DECLARED_ENVIRONMENT_MISMATCH"
    body = {key: value for key, value in evidence.items() if key != "receipt_hash"}
    evidence["receipt_hash"] = stable_hash(body)

    with pytest.raises(ContinuityUnderAbsenceError, match="STALE"):
        reconstruct_continuity(receipt, external_evidence=evidence)


def test_held_external_evidence_must_match_current_state():
    receipt = build_continuity_receipt(
        prior_state={"environment": "present", "value": 1},
        current_state={"environment": "present", "value": 8},
        observer_present_before=True,
        observer_present_after=False,
    )
    evidence = _verified_environment_receipt()

    with pytest.raises(ContinuityUnderAbsenceError, match="current state"):
        reconstruct_continuity(receipt, external_evidence=evidence)
