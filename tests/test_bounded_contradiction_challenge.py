from copy import deepcopy

import pytest

from holosim.bounded_contradiction_challenge import (
    CONTRADICTION_FOUND,
    NO_CONTRADICTION_FOUND,
    SEARCH_INSUFFICIENT,
    BoundedContradictionChallengeError,
    challenge_for_contradiction,
    verify_bounded_contradiction_challenge_receipt,
)


STATE = {"value": 7}
EVIDENCE = {"value": 7}
STATE_HASH = "state-hash"
EVIDENCE_HASH = "evidence-hash"


def no_contradiction(state, evidence):
    return state["value"] == evidence["value"]


def contradiction(state, evidence):
    return state["value"] == evidence["value"]


def test_no_contradiction_found_when_all_checks_return_false():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:1",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    assert receipt["result"] == NO_CONTRADICTION_FOUND
    assert receipt["search_complete"] is True
    assert receipt["contradictions_found"] == []
    assert receipt["insufficient_checks"] == []
    assert receipt["truth_verified"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_contradiction_found_when_check_returns_true():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:2",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence=EVIDENCE,
        checks={"same_value": contradiction},
    )

    assert receipt["result"] == CONTRADICTION_FOUND
    assert receipt["contradictions_found"] == ["same_value"]
    assert receipt["search_complete"] is True


def test_multiple_checks_record_each_result():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:3",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence=EVIDENCE,
        checks={
            "same_value": contradiction,
            "different_value": lambda state, evidence: state["value"] != evidence["value"],
        },
    )

    assert receipt["result"] == CONTRADICTION_FOUND
    assert receipt["check_results"] == {
        "different_value": NO_CONTRADICTION_FOUND,
        "same_value": CONTRADICTION_FOUND,
    }
    assert receipt["contradictions_found"] == ["same_value"]


def test_check_exception_makes_search_insufficient():
    def exploding_check(state, evidence):
        raise RuntimeError("cannot evaluate")

    receipt = challenge_for_contradiction(
        challenge_id="challenge:4",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence=EVIDENCE,
        checks={"exploding": exploding_check},
    )

    assert receipt["result"] == SEARCH_INSUFFICIENT
    assert receipt["search_complete"] is False
    assert receipt["insufficient_checks"] == ["exploding"]


def test_non_boolean_check_result_makes_search_insufficient():
    def ambiguous_check(state, evidence):
        return "maybe"

    receipt = challenge_for_contradiction(
        challenge_id="challenge:5",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence=EVIDENCE,
        checks={"ambiguous": ambiguous_check},
    )

    assert receipt["result"] == SEARCH_INSUFFICIENT
    assert receipt["search_complete"] is False
    assert receipt["insufficient_checks"] == ["ambiguous"]


def test_insufficient_search_takes_precedence_over_found_contradiction():
    def found(state, evidence):
        return True

    def insufficient(state, evidence):
        raise RuntimeError("unavailable")

    receipt = challenge_for_contradiction(
        challenge_id="challenge:6",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence=EVIDENCE,
        checks={
            "found": found,
            "insufficient": insufficient,
        },
    )

    assert receipt["result"] == SEARCH_INSUFFICIENT
    assert receipt["contradictions_found"] == ["found"]
    assert receipt["insufficient_checks"] == ["insufficient"]
    assert receipt["search_complete"] is False


def test_empty_checks_fail_closed():
    with pytest.raises(
        BoundedContradictionChallengeError,
        match="checks must be a nonempty mapping",
    ):
        challenge_for_contradiction(
            challenge_id="challenge:7",
            target_state_hash=STATE_HASH,
            evidence_hash=EVIDENCE_HASH,
            state=STATE,
            evidence=EVIDENCE,
            checks={},
        )


def test_non_mapping_checks_fail_closed():
    with pytest.raises(
        BoundedContradictionChallengeError,
        match="checks must be a nonempty mapping",
    ):
        challenge_for_contradiction(
            challenge_id="challenge:8",
            target_state_hash=STATE_HASH,
            evidence_hash=EVIDENCE_HASH,
            state=STATE,
            evidence=EVIDENCE,
            checks=["check"],
        )


def test_non_callable_check_fails_closed():
    with pytest.raises(
        BoundedContradictionChallengeError,
        match="must be callable",
    ):
        challenge_for_contradiction(
            challenge_id="challenge:9",
            target_state_hash=STATE_HASH,
            evidence_hash=EVIDENCE_HASH,
            state=STATE,
            evidence=EVIDENCE,
            checks={"bad": "not-callable"},
        )


def test_empty_challenge_id_fails_closed():
    with pytest.raises(
        BoundedContradictionChallengeError,
        match="challenge_id must be a nonempty string",
    ):
        challenge_for_contradiction(
            challenge_id=" ",
            target_state_hash=STATE_HASH,
            evidence_hash=EVIDENCE_HASH,
            state=STATE,
            evidence=EVIDENCE,
            checks={"check": no_contradiction},
        )


def test_empty_state_hash_fails_closed():
    with pytest.raises(
        BoundedContradictionChallengeError,
        match="target_state_hash must be a nonempty string",
    ):
        challenge_for_contradiction(
            challenge_id="challenge:10",
            target_state_hash="",
            evidence_hash=EVIDENCE_HASH,
            state=STATE,
            evidence=EVIDENCE,
            checks={"check": no_contradiction},
        )


def test_receipt_verifies():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:11",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    result = verify_bounded_contradiction_challenge_receipt(receipt)

    assert result["valid"] is True
    assert result["violations"] == []


def test_tampered_receipt_is_rejected():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:12",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    tampered = deepcopy(receipt)
    tampered["result"] = CONTRADICTION_FOUND

    result = verify_bounded_contradiction_challenge_receipt(tampered)

    assert result["valid"] is False
    assert "receipt_id does not match content" in result["violations"]


def test_truth_claim_cannot_be_added_to_verified_receipt():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:13",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    tampered = deepcopy(receipt)
    tampered["truth_verified"] = True

    result = verify_bounded_contradiction_challenge_receipt(tampered)

    assert result["valid"] is False


def test_authority_cannot_be_added_to_receipt():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:14",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    tampered = deepcopy(receipt)
    tampered["accepted"] = True

    result = verify_bounded_contradiction_challenge_receipt(tampered)

    assert result["valid"] is False


def test_same_inputs_are_deterministic():
    first = challenge_for_contradiction(
        challenge_id="challenge:15",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    second = challenge_for_contradiction(
        challenge_id="challenge:15",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    assert first == second


def test_check_order_does_not_change_receipt():
    first = challenge_for_contradiction(
        challenge_id="challenge:16",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence=EVIDENCE,
        checks={
            "same": contradiction,
            "different": no_contradiction,
        },
    )

    second = challenge_for_contradiction(
        challenge_id="challenge:16",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence=EVIDENCE,
        checks={
            "different": no_contradiction,
            "same": contradiction,
        },
    )

    assert first == second


def test_no_contradiction_is_not_truth():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:17",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    assert receipt["result"] == NO_CONTRADICTION_FOUND
    assert receipt["truth_verified"] is False
    assert receipt["truth_claimed"] is False


def test_insufficient_search_is_not_contradiction():
    def unavailable(state, evidence):
        raise RuntimeError("not enough information")

    receipt = challenge_for_contradiction(
        challenge_id="challenge:18",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence=EVIDENCE,
        checks={"unavailable": unavailable},
    )

    assert receipt["result"] == SEARCH_INSUFFICIENT
    assert receipt["contradictions_found"] == []
    assert receipt["truth_verified"] is False


def test_verifier_rejects_non_mapping_receipt():
    result = verify_bounded_contradiction_challenge_receipt(None)

    assert result["valid"] is False
    assert result["violations"] == ["receipt must be a mapping"]


def test_verifier_rejects_wrong_type():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:19",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    tampered = deepcopy(receipt)
    tampered["type"] = "wrong_type"

    result = verify_bounded_contradiction_challenge_receipt(tampered)

    assert result["valid"] is False


def test_verifier_rejects_wrong_version():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:20",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    tampered = deepcopy(receipt)
    tampered["version"] = 999

    result = verify_bounded_contradiction_challenge_receipt(tampered)

    assert result["valid"] is False


def test_verifier_rejects_false_search_complete():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:21",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    tampered = deepcopy(receipt)
    tampered["search_complete"] = False

    result = verify_bounded_contradiction_challenge_receipt(tampered)

    assert result["valid"] is False


def test_verifier_rejects_undeclared_check_result():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:22",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    tampered = deepcopy(receipt)
    tampered["check_results"]["invented"] = NO_CONTRADICTION_FOUND

    result = verify_bounded_contradiction_challenge_receipt(tampered)

    assert result["valid"] is False


def test_verifier_rejects_invalid_result():
    receipt = challenge_for_contradiction(
        challenge_id="challenge:23",
        target_state_hash=STATE_HASH,
        evidence_hash=EVIDENCE_HASH,
        state=STATE,
        evidence={"value": 8},
        checks={"value_differs": no_contradiction},
    )

    tampered = deepcopy(receipt)
    tampered["result"] = "TRUE"

    result = verify_bounded_contradiction_challenge_receipt(tampered)

    assert result["valid"] is False