import copy
import hashlib

import pytest

from holosim.baseline_observation_compare import (
    build_baseline_observation,
    compare_baseline_observations,
)
from holosim.baseline_promotion_gate import (
    STATUS_JUSTIFIED_TO_PROPOSE,
    evaluate_baseline_promotion,
)
from holosim.authorized_baseline_transition import (
    AuthorizedBaselineTransitionError,
    authorize_baseline_transition,
    build_baseline_transition_candidate,
)
from holosim.typed_operational_authorization import (
    ACTION_BASELINE_PROMOTION,
    ACTION_SERVICE_APPEND,
    build_operational_authorization,
)


NEXT_STATE = hashlib.sha256(b"next-state").hexdigest()


def _gate(*, left=None, right=None, refs=None):
    left_findings = left or {"claim-a": "EXTENSION"}
    right_findings = right or {"claim-a": "EXTENSION"}
    comparison = compare_baseline_observations(
        build_baseline_observation(
            observer_id="observer-a",
            baseline_id="baseline-1",
            baseline_state_hash="state-1",
            findings=left_findings,
        ),
        build_baseline_observation(
            observer_id="observer-b",
            baseline_id="baseline-1",
            baseline_state_hash="state-1",
            findings=right_findings,
        ),
    )
    return evaluate_baseline_promotion(
        comparison=comparison,
        justification_references=refs or {"claim-a": "justifier:claim-a:v1"},
    )


def _candidate(gate):
    return build_baseline_transition_candidate(
        promotion_gate=gate,
        next_baseline_id="baseline-2",
        next_baseline_state_hash=NEXT_STATE,
    )


def _authorization(candidate, *, action=ACTION_BASELINE_PROMOTION):
    return build_operational_authorization(
        authorization_id="approval:baseline-promotion-1",
        actor_id="external-reviewer",
        action=action,
        target_sha256=candidate["candidate_hash"],
        approval_reference="approval:baseline-promotion-1",
    )


def test_justified_proposal_plus_exact_authorization_creates_transition():
    gate = _gate()
    assert gate["status"] == STATUS_JUSTIFIED_TO_PROPOSE
    candidate = _candidate(gate)
    authorization = _authorization(candidate)

    result = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=candidate,
        authorization=authorization,
    )

    assert result["status"] == "AUTHORIZED"
    assert result["next_baseline_created"] is True
    assert result["next_baseline_id"] == "baseline-2"
    assert result["next_baseline_state_hash"] == NEXT_STATE
    assert result["candidate_hash"] == candidate["candidate_hash"]
    assert result["promotion_gate_id"] == gate["gate_id"]
    assert result["authorization_hash"] == authorization["authorization_hash"]


def test_baseline_promotion_authorization_is_promotion_only():
    gate = _gate()
    authorization = _authorization(_candidate(gate))

    assert authorization["write_authority"] == "NONE"
    assert authorization["promotion_authority"] == "EXACT_TARGET_ONLY"
    assert authorization["execution_authority"] == "NONE"
    assert authorization["truth_claimed"] is False


def test_service_append_authorization_cannot_promote_baseline():
    gate = _gate()
    candidate = _candidate(gate)
    authorization = _authorization(candidate, action=ACTION_SERVICE_APPEND)

    with pytest.raises(
        AuthorizedBaselineTransitionError,
        match="authorization action does not match",
    ):
        authorize_baseline_transition(
            promotion_gate=gate,
            candidate=candidate,
            authorization=authorization,
        )


def test_authorization_for_different_candidate_is_rejected():
    gate = _gate()
    candidate = _candidate(gate)
    other = build_baseline_transition_candidate(
        promotion_gate=gate,
        next_baseline_id="baseline-other",
        next_baseline_state_hash=hashlib.sha256(b"other-state").hexdigest(),
    )
    authorization = _authorization(other)

    with pytest.raises(
        AuthorizedBaselineTransitionError,
        match="authorization target does not match",
    ):
        authorize_baseline_transition(
            promotion_gate=gate,
            candidate=candidate,
            authorization=authorization,
        )


def test_non_justified_gate_cannot_create_candidate():
    gate = _gate(
        left={"claim-a": "UNKNOWN"},
        right={"claim-a": "UNKNOWN"},
        refs={"claim-a": "justifier:claim-a:v1"},
    )

    with pytest.raises(
        AuthorizedBaselineTransitionError,
        match="not justified to propose",
    ):
        _candidate(gate)


def test_tampered_gate_is_rejected():
    gate = _gate()
    gate["status"] = "BLOCKED"

    with pytest.raises(
        AuthorizedBaselineTransitionError,
        match="promotion_gate identity is invalid",
    ):
        _candidate(gate)


def test_tampered_candidate_is_rejected():
    gate = _gate()
    candidate = _candidate(gate)
    authorization = _authorization(candidate)
    candidate["next_baseline_id"] = "tampered"

    with pytest.raises(
        AuthorizedBaselineTransitionError,
        match="candidate identity is invalid",
    ):
        authorize_baseline_transition(
            promotion_gate=gate,
            candidate=candidate,
            authorization=authorization,
        )


def test_candidate_is_bound_to_exact_gate():
    gate = _gate()
    candidate = _candidate(gate)

    other_gate = _gate(refs={"claim-a": "different-justification"})

    with pytest.raises(
        AuthorizedBaselineTransitionError,
        match="candidate identity is invalid",
    ):
        authorize_baseline_transition(
            promotion_gate=other_gate,
            candidate=candidate,
            authorization=_authorization(candidate),
        )


def test_transition_remains_non_epistemic_and_non_executing():
    gate = _gate()
    candidate = _candidate(gate)
    result = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=candidate,
        authorization=_authorization(candidate),
    )

    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert result["promotion_authority"] == "EXACT_TARGET_ONLY"


def test_same_inputs_produce_same_transition_identity_and_inputs_are_unchanged():
    gate = _gate()
    candidate = _candidate(gate)
    authorization = _authorization(candidate)

    before_gate = copy.deepcopy(gate)
    before_candidate = copy.deepcopy(candidate)
    before_authorization = copy.deepcopy(authorization)

    first = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=candidate,
        authorization=authorization,
    )
    second = authorize_baseline_transition(
        promotion_gate=gate,
        candidate=candidate,
        authorization=authorization,
    )

    assert first == second
    assert first["transition_id"] == second["transition_id"]
    assert gate == before_gate
    assert candidate == before_candidate
    assert authorization == before_authorization
