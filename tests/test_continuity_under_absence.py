from holosim.continuity_under_absence import build_continuity_receipt


def test_continuity_survives_observer_absence():
    prior = {"state": "before", "value": 1}
    current = {"state": "after", "value": 2}

    receipt = build_continuity_receipt(
        prior_state=prior,
        current_state=current,
        observer_present_before=True,
        observer_present_after=False,
    )

    assert receipt["prior_state"] == prior
    assert receipt["current_state"] == current
    assert receipt["observer_present_before"] is True
    assert receipt["observer_present_after"] is False
    assert receipt["continuity_claimed"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_absence_does_not_imply_environment_absence():
    prior = {"environment": "present", "value": 1}
    current = {"environment": "present", "value": 2}

    receipt = build_continuity_receipt(
        prior_state=prior,
        current_state=current,
        observer_present_before=True,
        observer_present_after=False,
    )

    assert receipt["observer_present_after"] is False
    assert receipt["current_state"]["environment"] == "present"
    assert receipt["current_state_hash"] != receipt["prior_state_hash"]


def test_environment_change_during_absence_is_preserved():
    prior = {"environment": "present", "value": 1}
    current = {"environment": "present", "value": 9}

    receipt = build_continuity_receipt(
        prior_state=prior,
        current_state=current,
        observer_present_before=True,
        observer_present_after=False,
    )

    assert receipt["prior_state"] == prior
    assert receipt["current_state"] == current
    assert receipt["prior_state_hash"] != receipt["current_state_hash"]
    assert receipt["current_state"]["value"] == 9
    assert receipt["continuity_claimed"] is False


def test_missing_observer_evidence_does_not_rewrite_prior_state():
    prior = {"environment": "present", "value": 1}
    current = {"environment": "present", "value": 9}

    receipt = build_continuity_receipt(
        prior_state=prior,
        current_state=current,
        observer_present_before=True,
        observer_present_after=False,
    )

    assert receipt["prior_state"] == prior
    assert receipt["prior_state_hash"] == __import__("holosim.canonical", fromlist=["stable_hash"]).stable_hash(prior)
    assert receipt["current_state"] == current
    assert receipt["prior_state"] != receipt["current_state"]
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"


def test_forged_post_absence_evidence_fails_closed():
    import pytest
    prior = {"environment": "present", "value": 1}
    current = {"environment": "present", "value": 9}

    receipt = build_continuity_receipt(
        prior_state=prior,
        current_state=current,
        observer_present_before=True,
        observer_present_after=False,
    )
    receipt["current_state"] = {"environment": "forged", "value": 999}

    from holosim.continuity_under_absence import (
        ContinuityUnderAbsenceError,
        verify_continuity_receipt,
    )
    with pytest.raises(ContinuityUnderAbsenceError):
        verify_continuity_receipt(receipt)



def test_rehashed_forgery_fails_closed():
    import pytest
    from holosim.canonical import stable_hash

    prior = {"environment": "present", "value": 1}
    current = {"environment": "present", "value": 9}

    receipt = build_continuity_receipt(
        prior_state=prior,
        current_state=current,
        observer_present_before=True,
        observer_present_after=False,
    )

    receipt["current_state"] = {"environment": "forged", "value": 999}
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)

    from holosim.continuity_under_absence import verify_continuity_receipt
    with pytest.raises(Exception, match="internally inconsistent"):
        verify_continuity_receipt(receipt)



def test_reconstruction_requires_verified_external_evidence():
    import pytest

    prior = {"environment": "present", "value": 1}
    current = {"environment": "present", "value": 9}

    receipt = build_continuity_receipt(
        prior_state=prior,
        current_state=current,
        observer_present_before=True,
        observer_present_after=False,
    )

    from holosim.continuity_under_absence import (
        ContinuityUnderAbsenceError,
        reconstruct_continuity,
    )
    with pytest.raises(ContinuityUnderAbsenceError, match="external evidence"):
        reconstruct_continuity(receipt, external_evidence=None)

