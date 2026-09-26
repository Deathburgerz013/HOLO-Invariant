from copy import deepcopy

import pytest

from holosim.bounded_investigation_continuity import (
    InvestigationContinuityError,
    bind_investigation_continuity,
)
from holosim.experimental_distinguishability import derive_distinguishability
from holosim.interpretation_set_receipt import InterpretationSetReceipt


def interpretation(
    *,
    prior=("A", "B"),
    subtract=(),
    evidence=(),
    observation_id="obs-1",
):
    return InterpretationSetReceipt(
        observation_id=observation_id,
        prior_set=prior,
        ranks={member: 1.0 for member in prior},
        subtract_receipts=subtract,
        evidence_receipt_hashes=evidence,
    )


def distinguishability():
    return derive_distinguishability(
        candidates={"A": 0, "B": 1},
        checks={"parity": lambda value: value % 2},
    )


def next_check():
    return {
        "type": "residual_next_check_routing",
        "routing_id": "route-1",
        "candidate_checks": [
            {
                "condition": "perform independent observation",
            }
        ],
        "truth_claimed": False,
        "accepted": False,
        "execution_authorized": False,
        "write_authority": "NONE",
    }


def bind(**overrides):
    values = {
        "investigation_id": "investigation-1",
        "question": "Which interpretation survives?",
        "interpretation_before": interpretation(),
        "distinguishability_receipt": distinguishability(),
        "interpretation_after": interpretation(),
        "next_check_receipt": None,
    }
    values.update(overrides)
    return bind_investigation_continuity(**values)


def test_unresolved_investigation_stops_without_inventing_next_check():
    receipt = bind()

    assert receipt["status"] == "BOUNDED_UNRESOLVED_STOP"
    assert receipt["before_interpretations"] == ["A", "B"]
    assert receipt["after_interpretations"] == ["A", "B"]
    assert receipt["removed_interpretations"] == []
    assert receipt["next_check"] is None


def test_declared_next_check_continues_investigation():
    receipt = bind(next_check_receipt=next_check())

    assert receipt["status"] == "CONTINUES"
    assert receipt["next_check"]["candidate_check_count"] == 1


def test_verified_subtraction_can_remove_interpretation():
    after = interpretation(
        subtract=(
            {
                "member": "B",
                "evidence_receipt_hash": "evidence-1",
            },
        ),
        evidence=("evidence-1",),
    )

    receipt = bind(interpretation_after=after)

    assert receipt["after_interpretations"] == ["A"]
    assert receipt["removed_interpretations"] == ["B"]
    assert receipt["status"] == "NO_REMAINING_ALTERNATIVES"


def test_unverified_subtraction_does_not_remove_interpretation():
    after = interpretation(
        subtract=(
            {
                "member": "B",
                "evidence_receipt_hash": "unknown-evidence",
            },
        ),
        evidence=(),
    )

    receipt = bind(interpretation_after=after)

    assert receipt["after_interpretations"] == ["A", "B"]
    assert receipt["removed_interpretations"] == []
    assert receipt["status"] == "BOUNDED_UNRESOLVED_STOP"


def test_rank_change_alone_cannot_remove_interpretation():
    before = interpretation()
    after = InterpretationSetReceipt(
        observation_id="obs-1",
        prior_set=("A", "B"),
        ranks={"A": 100.0, "B": 0.0},
        subtract_receipts=(),
        evidence_receipt_hashes=(),
    )

    receipt = bind(
        interpretation_before=before,
        interpretation_after=after,
    )

    assert receipt["after_interpretations"] == ["A", "B"]
    assert receipt["removed_interpretations"] == []


def test_contracted_prior_set_cannot_fake_verified_subtraction():
    after = interpretation(prior=("A",))

    with pytest.raises(
        InvestigationContinuityError,
        match="not justified by verified subtraction",
    ):
        bind(interpretation_after=after)


def test_after_set_cannot_introduce_new_interpretation():
    after = interpretation(prior=("A", "B", "C"))

    with pytest.raises(
        InvestigationContinuityError,
        match="introduced a new interpretation",
    ):
        bind(interpretation_after=after)


def test_observation_identity_must_remain_stable():
    after = interpretation(observation_id="different-observation")

    with pytest.raises(
        InvestigationContinuityError,
        match="observation identity changed",
    ):
        bind(interpretation_after=after)


def test_distinguishability_cannot_reference_unknown_interpretation():
    receipt = derive_distinguishability(
        candidates={"A": 0, "B": 1, "C": 2},
        checks={"identity": lambda value: value},
    )

    with pytest.raises(
        InvestigationContinuityError,
        match="unknown interpretation",
    ):
        bind(distinguishability_receipt=receipt)


def test_distinguishability_cannot_claim_truth():
    receipt = deepcopy(distinguishability())
    receipt["truth_claimed"] = True

    with pytest.raises(
        InvestigationContinuityError,
        match="must not claim truth",
    ):
        bind(distinguishability_receipt=receipt)


def test_distinguishability_cannot_claim_acceptance():
    receipt = deepcopy(distinguishability())
    receipt["accepted"] = True

    with pytest.raises(
        InvestigationContinuityError,
        match="must not claim acceptance",
    ):
        bind(distinguishability_receipt=receipt)


def test_distinguishability_cannot_gain_write_authority():
    receipt = deepcopy(distinguishability())
    receipt["write_authority"] = "WRITE"

    with pytest.raises(
        InvestigationContinuityError,
        match="no write authority",
    ):
        bind(distinguishability_receipt=receipt)


def test_next_check_cannot_claim_truth():
    receipt = next_check()
    receipt["truth_claimed"] = True

    with pytest.raises(
        InvestigationContinuityError,
        match="must not claim truth",
    ):
        bind(next_check_receipt=receipt)


def test_next_check_cannot_claim_acceptance():
    receipt = next_check()
    receipt["accepted"] = True

    with pytest.raises(
        InvestigationContinuityError,
        match="must not claim acceptance",
    ):
        bind(next_check_receipt=receipt)


def test_next_check_cannot_authorize_execution():
    receipt = next_check()
    receipt["execution_authorized"] = True

    with pytest.raises(
        InvestigationContinuityError,
        match="must not authorize execution",
    ):
        bind(next_check_receipt=receipt)


def test_next_check_cannot_gain_write_authority():
    receipt = next_check()
    receipt["write_authority"] = "WRITE"

    with pytest.raises(
        InvestigationContinuityError,
        match="no write authority",
    ):
        bind(next_check_receipt=receipt)


def test_output_never_acquires_authority():
    receipt = bind(next_check_receipt=next_check())

    assert receipt["distinguishability_grants_elimination"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["execution_authorized"] is False
    assert receipt["state_change_authorized"] is False
    assert receipt["write_authority"] == "NONE"


def test_receipt_is_deterministic():
    first = bind()
    second = bind()

    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]