from copy import deepcopy

import pytest

from holosim.bounded_contradiction_challenge import challenge_for_contradiction
from holosim.current_observation_challenge_binding import (
    CurrentObservationChallengeBindingError,
    bind_current_observation_to_challenge,
    verify_current_observation_challenge_binding_receipt,
)
from holosim.canonical import stable_hash
from holosim.check_identity import build_check_identity, bind_check_result
from holosim.declared_verifier_execution_receipt import execute_declared_verifier
from holosim.time_scoped_truth import build_time_scoped_truth_receipt

def _check(check_id="license", outcome="SUPPORTS", status="VERIFIED", output_state_hash=None):
    if status != "VERIFIED":
        result = {"status": "UNAVAILABLE"}
        expected = {"status": "COMPLETE"}
        mismatch_outcome = "UNKNOWN"
    elif outcome == "SUPPORTS":
        result = {"status": "COMPLETE"}
        expected = {"status": "COMPLETE"}
        mismatch_outcome = "CONTRADICTS"
    elif outcome == "CONTRADICTS":
        result = {"status": "INCOMPLETE"}
        expected = {"status": "COMPLETE"}
        mismatch_outcome = "CONTRADICTS"
    else:
        result = {"status": "INCOMPLETE"}
        expected = {"status": "COMPLETE"}
        mismatch_outcome = "UNKNOWN"

    identity = build_check_identity(
        check_id=check_id,
        check_type="environment_snapshot_comparison",
        subject={"target": f"environment:{check_id}"},
        reference_ids=[f"reference:{check_id}"],
        scope={"field": "status"},
        evidence_references=[f"evidence:{check_id}"],
        rule_references=[f"rule:{check_id}"],
        input_state_hash=stable_hash({"state": "before", "check": check_id}),
    )

    verifier_check_binding = {
        "type": "declared_verifier_check_identity_binding",
        "version": 1,
        "declared_verifier_binding_hash": stable_hash(
            {"declared": "binding", "check": check_id}
        ),
        "verifier_id": "environment_snapshot_comparison",
        "check_id": identity["check_id"],
        "check_identity_hash": identity["check_identity_hash"],
        "execution_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    verifier_check_binding["binding_hash"] = stable_hash(
        verifier_check_binding
    )

    execution_receipt = execute_declared_verifier(
        verifier_check_binding=verifier_check_binding,
        check_identity=identity,
        available_verifiers={
            "environment_snapshot_comparison": lambda _: result
        },
    )

    if output_state_hash is None:
        output_state_hash = stable_hash(
            {"state": "after", "check": check_id}
        )

    result_binding = bind_check_result(
        check_identity=identity,
        result=execution_receipt["result"],
        output_state_hash=output_state_hash,
    )

    return {
        "check_id": check_id,
        "check_type": "EVIDENCE",
        "execution_receipt": execution_receipt,
        "result_binding": result_binding,
        "evaluation_rule": {
            "type": "exact_result_match",
            "expected_result": expected,
            "match_outcome": "SUPPORTS",
            "mismatch_outcome": mismatch_outcome,
        },
    }


def _inputs(*, outcome="SUPPORTS", temporal_scope="AT_OBSERVATION", observed_at="2026-09-03T10:00:00-07:00"):
    check = _check(outcome=outcome)
    return {
        "claim": {
            "claim_id": "holo.free",
            "statement": "HOLO is free under the observed repository terms",
            "temporal_scope": temporal_scope,
        },
        "observation": {
            "observation_id": f"repo.{stable_hash(observed_at)[:16]}",
            "environment_id": "github.holo-invariant",
            "observed_at": observed_at,
            "clock_id": "operator.clock",
            "state_hash": check["result_binding"]["output_state_hash"],
        },
        "checks": [check],
    }


def _receipt(**kwargs):
    return build_time_scoped_truth_receipt(**_inputs(**kwargs))



def _truth():
    return _receipt()


def _challenge(state_hash):
    return challenge_for_contradiction(
        challenge_id="challenge:current-observation",
        target_state_hash=state_hash,
        evidence_hash="evidence:current-observation",
        state={"value": 8},
        evidence={"value": 8},
        checks={"different": lambda state, evidence: state["value"] != evidence["value"]},
    )


def test_matching_observation_and_challenge_bind():
    truth = _truth()
    challenge = _challenge(truth["observation"]["state_hash"])
    receipt = bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    assert receipt["status"] == "BOUND"
    assert receipt["identity_matches"] is True
    assert receipt["binding_complete"] is True
    assert receipt["observed_state_hash"] == challenge["target_state_hash"]
    assert receipt["current_truth_receipt_hash"] == truth["receipt_hash"]
    assert receipt["challenge_receipt_id"] == challenge["receipt_id"]
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_different_state_identity_does_not_bind():
    truth = _truth()
    challenge = _challenge("f" * 64)
    assert challenge["target_state_hash"] != truth["observation"]["state_hash"]
    receipt = bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    assert receipt["status"] == "IDENTITY_MISMATCH"
    assert receipt["identity_matches"] is False
    assert receipt["binding_complete"] is False


def test_tampered_truth_receipt_is_rejected():
    truth = _truth()
    challenge = _challenge(truth["observation"]["state_hash"])
    tampered = deepcopy(truth)
    tampered["truth_status"] = "FALSE"
    with pytest.raises(CurrentObservationChallengeBindingError, match="current truth receipt is invalid"):
        bind_current_observation_to_challenge(
            current_truth_receipt=tampered,
            challenge_receipt=challenge,
        )


def test_tampered_challenge_receipt_is_rejected():
    truth = _truth()
    challenge = _challenge(truth["observation"]["state_hash"])
    tampered = deepcopy(challenge)
    tampered["target_state_hash"] = "e" * 64
    with pytest.raises(CurrentObservationChallengeBindingError, match="challenge receipt"):
        bind_current_observation_to_challenge(
            current_truth_receipt=truth,
            challenge_receipt=tampered,
        )


def test_binding_is_deterministic():
    truth = _truth()
    challenge = _challenge(truth["observation"]["state_hash"])
    first = bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    second = bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]


def test_binding_does_not_mutate_inputs():
    truth = _truth()
    challenge = _challenge(truth["observation"]["state_hash"])
    truth_before = deepcopy(truth)
    challenge_before = deepcopy(challenge)
    bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    assert truth == truth_before
    assert challenge == challenge_before


def test_no_contradiction_found_does_not_become_truth_or_authority():
    truth = _truth()
    challenge = _challenge(truth["observation"]["state_hash"])
    assert challenge["result"] == "NO_CONTRADICTION_FOUND"
    receipt = bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    assert receipt["status"] == "BOUND"
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_binding_receipt_verifies_against_exact_evidence():
    truth = _truth()
    challenge = _challenge(truth["observation"]["state_hash"])
    receipt = bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    assert verify_current_observation_challenge_binding_receipt(
        receipt,
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    ) is True


def test_rehashed_semantic_tamper_is_rejected_by_regeneration():
    truth = _truth()
    challenge = _challenge(truth["observation"]["state_hash"])
    receipt = bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    tampered = deepcopy(receipt)
    tampered["status"] = "IDENTITY_MISMATCH"
    body = dict(tampered)
    body.pop("receipt_hash")
    tampered["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        CurrentObservationChallengeBindingError,
        match="does not match supplied evidence",
    ):
        verify_current_observation_challenge_binding_receipt(
            tampered,
            current_truth_receipt=truth,
            challenge_receipt=challenge,
        )


def test_foreign_binding_field_is_rejected_even_when_rehashed():
    truth = _truth()
    challenge = _challenge(truth["observation"]["state_hash"])
    receipt = bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    forged = deepcopy(receipt)
    forged["approval"] = "GRANTED"
    body = dict(forged)
    body.pop("receipt_hash")
    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        CurrentObservationChallengeBindingError,
        match="fields do not match",
    ):
        verify_current_observation_challenge_binding_receipt(
            forged,
            current_truth_receipt=truth,
            challenge_receipt=challenge,
        )


def test_binding_receipt_cannot_verify_against_different_challenge_evidence():
    truth = _truth()
    challenge = _challenge(truth["observation"]["state_hash"])
    receipt = bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    different = challenge_for_contradiction(
        challenge_id="challenge:different-evidence",
        target_state_hash=truth["observation"]["state_hash"],
        evidence_hash="evidence:different",
        state={"value": 8},
        evidence={"value": 8},
        checks={"different": lambda state, evidence: False},
    )

    with pytest.raises(
        CurrentObservationChallengeBindingError,
        match="does not match supplied evidence",
    ):
        verify_current_observation_challenge_binding_receipt(
            receipt,
            current_truth_receipt=truth,
            challenge_receipt=different,
        )
