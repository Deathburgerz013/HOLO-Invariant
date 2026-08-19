from copy import deepcopy

import pytest

from holosim.invariant_validity_lifecycle import (
    InvariantValidityLifecycleError,
    append_validity_event,
    project_active_invariants,
    verify_validity_event,
)


ENVIRONMENT = "environment-head-001"


def append(
    history,
    *,
    claim_id="claim-001",
    status="ESTABLISHED",
    reason="bounded evidence supports the claim",
    evidence=None,
    environment_fingerprint=None,
    reopen_reference=None,
):
    if evidence is None:
        evidence = ["evidence-001"]

    event = append_validity_event(
        history=history,
        claim_id=claim_id,
        status=status,
        reason=reason,
        evidence=evidence,
        observed_at="2026-08-19T21:00:00Z",
        environment_fingerprint=(
            environment_fingerprint
        ),
        reopen_reference=reopen_reference,
    )
    history.append(event)
    return event


@pytest.mark.parametrize(
    "status",
    [
        "INVARIANT",
        "ESTABLISHED",
    ],
)
def test_stable_valid_statuses_enter_active_recall(
    status,
):
    history = []
    event = append(
        history,
        status=status,
    )

    projection = project_active_invariants(
        history,
        current_environment_fingerprint=ENVIRONMENT,
    )

    assert projection["active_claims"] == [
        {
            "claim_id": "claim-001",
            "status": status,
            "event_hash": event["event_hash"],
        }
    ]
    assert projection["excluded_claims"] == []
    assert projection["event_count"] == 1
    assert projection["history_hash"]


@pytest.mark.parametrize(
    "status",
    [
        "UNKNOWN",
        "SUPERSEDED",
        "INVALID",
        "LIQUIDATED",
    ],
)
def test_nonusable_statuses_are_excluded_from_active_recall(
    status,
):
    history = []
    event = append(
        history,
        status=status,
    )

    projection = project_active_invariants(
        history,
        current_environment_fingerprint=ENVIRONMENT,
    )

    assert projection["active_claims"] == []
    assert projection["excluded_claims"] == [
        {
            "claim_id": "claim-001",
            "status": status,
            "event_hash": event["event_hash"],
            "exclusion_reason": status,
        }
    ]


def test_latest_validity_event_controls_active_projection():
    history = []
    established = append(
        history,
        status="ESTABLISHED",
    )
    invalid = append(
        history,
        status="INVALID",
        reason="contradicted by reproduced evidence",
        evidence=["counterevidence-001"],
    )

    projection = project_active_invariants(
        history,
        current_environment_fingerprint=ENVIRONMENT,
    )

    assert projection["active_claims"] == []
    assert projection["excluded_claims"][0][
        "status"
    ] == "INVALID"
    assert projection["excluded_claims"][0][
        "event_hash"
    ] == invalid["event_hash"]
    assert projection["event_count"] == 2
    assert verify_validity_event(established) is True
    assert verify_validity_event(invalid) is True


def test_liquidation_removes_influence_not_history():
    history = []
    append(
        history,
        status="ESTABLISHED",
    )
    liquidated = append(
        history,
        status="LIQUIDATED",
        reason="claim is invalid and no longer usable",
        evidence=["counterevidence-001"],
    )

    projection = project_active_invariants(
        history,
        current_environment_fingerprint=ENVIRONMENT,
    )

    assert len(history) == 2
    assert history[-1] == liquidated
    assert projection["event_count"] == 2
    assert projection["active_claims"] == []
    assert projection["excluded_claims"][0][
        "status"
    ] == "LIQUIDATED"


def test_liquidated_claim_cannot_silently_reenter():
    history = []
    liquidated = append(
        history,
        status="LIQUIDATED",
    )

    with pytest.raises(
        InvariantValidityLifecycleError,
        match="liquidated claim requires explicit reopen",
    ):
        append(
            history,
            status="ESTABLISHED",
            evidence=["new-evidence"],
        )

    reopened = append(
        history,
        status="UNKNOWN",
        reason="new evidence requires fresh evaluation",
        evidence=["new-evidence"],
        reopen_reference=liquidated["event_hash"],
    )

    assert reopened["reopen_reference"] == liquidated[
        "event_hash"
    ]
    assert reopened["status"] == "UNKNOWN"


def test_reopened_claim_requires_new_validation_before_use():
    history = []
    liquidated = append(
        history,
        status="LIQUIDATED",
    )
    append(
        history,
        status="UNKNOWN",
        reason="reopened for evaluation",
        evidence=["new-evidence"],
        reopen_reference=liquidated["event_hash"],
    )

    reopened_projection = project_active_invariants(
        history,
        current_environment_fingerprint=ENVIRONMENT,
    )
    assert reopened_projection["active_claims"] == []

    established = append(
        history,
        status="ESTABLISHED",
        reason="new evidence reproduced",
        evidence=["new-evidence", "validator-001"],
    )
    final_projection = project_active_invariants(
        history,
        current_environment_fingerprint=ENVIRONMENT,
    )

    assert final_projection["active_claims"][0][
        "event_hash"
    ] == established["event_hash"]


def test_contingent_claim_is_active_only_in_matching_environment():
    history = []
    event = append(
        history,
        status="CONTINGENT",
        environment_fingerprint=ENVIRONMENT,
    )

    current = project_active_invariants(
        history,
        current_environment_fingerprint=ENVIRONMENT,
    )
    stale = project_active_invariants(
        history,
        current_environment_fingerprint="different-head",
    )

    assert current["active_claims"] == [
        {
            "claim_id": "claim-001",
            "status": "CONTINGENT",
            "event_hash": event["event_hash"],
        }
    ]
    assert stale["active_claims"] == []
    assert stale["excluded_claims"][0][
        "exclusion_reason"
    ] == "STALE_ENVIRONMENT"


def test_contingent_claim_requires_environment_fingerprint():
    history = []

    with pytest.raises(
        InvariantValidityLifecycleError,
        match="CONTINGENT status requires environment_fingerprint",
    ):
        append(
            history,
            status="CONTINGENT",
        )


def test_tampered_history_is_rejected():
    history = []
    append(history)
    tampered = deepcopy(history)
    tampered[0]["status"] = "INVARIANT"

    with pytest.raises(
        InvariantValidityLifecycleError,
        match="event hash mismatch",
    ):
        project_active_invariants(
            tampered,
            current_environment_fingerprint=ENVIRONMENT,
        )


def test_projection_is_deterministic_and_non_authoritative():
    history = []
    append(
        history,
        claim_id="claim-b",
        status="ESTABLISHED",
    )
    append(
        history,
        claim_id="claim-a",
        status="INVARIANT",
    )

    first = project_active_invariants(
        history,
        current_environment_fingerprint=ENVIRONMENT,
    )
    second = project_active_invariants(
        history,
        current_environment_fingerprint=ENVIRONMENT,
    )

    assert first == second
    assert [
        item["claim_id"]
        for item in first["active_claims"]
    ] == [
        "claim-a",
        "claim-b",
    ]
    assert first["accepted"] is False
    assert first["truth_claimed"] is False
    assert first["write_authority"] == "NONE"
    assert first["canonical_mutation"] is False