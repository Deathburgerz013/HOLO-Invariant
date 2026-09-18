import copy

import pytest

from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)
from holosim.reconstructor import build_reconstructed_state
from holosim.verified_cold_start_reentry_gateway import (
    build_verified_cold_start_reentry_packet,
)
from holosim.functional_consciousness_experiment import (
    FunctionalConsciousnessExperimentError,
    build_experiment_input_receipt,
    build_experiment_continuity_receipt,
    verify_experiment_continuity_receipt,
    build_internal_monitor_receipt,
    build_monitor_mismatch_candidate,
    verify_experiment_input_receipt,
    verify_internal_monitor_receipt,
    build_workspace_receipt,
    verify_workspace_receipt,
    build_workspace_broadcast_receipt,
    verify_workspace_broadcast_receipt,
)


def _receipt():
    return build_experiment_input_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="baseline",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_state={"signal": "stable", "value": 1},
        self_state={"operating_state": "nominal", "value": 1},
    )


def test_builds_verified_source_separated_receipt():
    receipt = _receipt()

    assert receipt["world_source_id"] == "world-channel"
    assert receipt["self_source_id"] == "self-channel"
    assert receipt["world_state_hash"] != receipt["self_state_hash"]
    assert receipt["sources_separated"] is True
    assert receipt["subjective_consciousness_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert verify_experiment_input_receipt(receipt) is True


def test_identical_inputs_are_byte_stable_at_receipt_value_level():
    first = _receipt()
    second = _receipt()

    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]


def test_world_and_self_sources_must_differ():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="must differ",
    ):
        build_experiment_input_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="baseline",
            world_source_id="same-channel",
            self_source_id="same-channel",
            world_state={"value": 1},
            self_state={"value": 1},
        )


def test_same_value_from_distinct_sources_remains_source_separated():
    receipt = build_experiment_input_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="same-value-control",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_state={"value": 1},
        self_state={"value": 1},
    )

    assert receipt["world_state_hash"] == receipt["self_state_hash"]
    assert receipt["world_source_id"] != receipt["self_source_id"]
    assert receipt["sources_separated"] is True
    assert verify_experiment_input_receipt(receipt) is True


def test_non_json_state_fails_closed():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="plain JSON values",
    ):
        build_experiment_input_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="invalid-state",
            world_source_id="world-channel",
            self_source_id="self-channel",
            world_state={"invalid": {1, 2, 3}},
            self_state={"value": 1},
        )


def test_nonfinite_state_fails_closed():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="finite",
    ):
        build_experiment_input_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="nonfinite-state",
            world_source_id="world-channel",
            self_source_id="self-channel",
            world_state={"value": float("nan")},
            self_state={"value": 1},
        )


def test_tampered_receipt_hash_fails_closed():
    receipt = _receipt()
    receipt["condition_id"] = "tampered"

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="receipt hash mismatch",
    ):
        verify_experiment_input_receipt(receipt)


def test_rehashed_source_collision_still_fails_closed():
    receipt = _receipt()
    forged = copy.deepcopy(receipt)
    forged["self_source_id"] = forged["world_source_id"]

    body = {
        key: value
        for key, value in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="not separated",
    ):
        verify_experiment_input_receipt(forged)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("sources_separated", False, "sources_separated"),
        (
            "subjective_consciousness_claimed",
            True,
            "subjective consciousness",
        ),
        ("accepted", True, "must not accept"),
        ("write_authority", "FULL", "write authority"),
        ("execution_authority", "FULL", "execution authority"),
    ],
)
def test_rehashed_boundary_tampering_fails_closed(field, value, message):
    receipt = _receipt()
    forged = copy.deepcopy(receipt)
    forged[field] = value

    body = {
        key: item
        for key, item in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match=message,
    ):
        verify_experiment_input_receipt(forged)


def test_unknown_receipt_field_fails_closed():
    receipt = _receipt()
    receipt["surprise_authority_from_the_void"] = True

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="receipt fields mismatch",
    ):
        verify_experiment_input_receipt(receipt)
def _monitor_receipt():
    return build_internal_monitor_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="hidden-self-perturbation",
        self_source_id="self-channel",
        expected_self_state={
            "operating_state": "nominal",
            "load": 1,
        },
        observed_self_state={
            "operating_state": "degraded",
            "load": 1,
        },
    )


def test_monitor_detects_hidden_self_perturbation_pre_report():
    receipt = _monitor_receipt()

    assert receipt["mismatch_paths"] == ["operating_state"]
    assert receipt["perturbation_detected"] is True
    assert receipt["observation_stage"] == "PRE_REPORT"
    assert receipt["reporter_executed"] is False
    assert verify_internal_monitor_receipt(receipt) is True


def test_monitor_nominal_state_has_no_perturbation():
    receipt = build_internal_monitor_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="nominal",
        self_source_id="self-channel",
        expected_self_state={"operating_state": "nominal"},
        observed_self_state={"operating_state": "nominal"},
    )

    assert receipt["mismatch_paths"] == []
    assert receipt["perturbation_detected"] is False
    assert (
        receipt["expected_self_state_hash"]
        == receipt["observed_self_state_hash"]
    )
    assert verify_internal_monitor_receipt(receipt) is True


def test_monitor_mismatch_paths_are_deterministic():
    receipt = build_internal_monitor_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="multi-perturbation",
        self_source_id="self-channel",
        expected_self_state={
            "z": 1,
            "nested": {"b": 2, "a": 1},
        },
        observed_self_state={
            "z": 2,
            "nested": {"b": 3, "a": 0},
        },
    )

    assert receipt["mismatch_paths"] == [
        "nested.a",
        "nested.b",
        "z",
    ]


def test_monitor_rejects_non_json_self_state():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="plain JSON values",
    ):
        build_internal_monitor_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="invalid",
            self_source_id="self-channel",
            expected_self_state={"value": 1},
            observed_self_state={"value": {1, 2}},
        )


def _hidden_perturbation_input_receipt():
    return build_experiment_input_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="hidden-self-perturbation",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_state={
            "signal": "stable",
            "value": 1,
        },
        self_state={
            "operating_state": "nominal",
            "load": 1,
        },
    )


def test_hidden_perturbation_input_matches_monitor_preperturbation_state():
    input_receipt = _hidden_perturbation_input_receipt()
    monitor_receipt = _monitor_receipt()

    assert input_receipt["experiment_id"] == monitor_receipt["experiment_id"]
    assert input_receipt["condition_id"] == monitor_receipt["condition_id"]
    assert input_receipt["self_source_id"] == monitor_receipt["self_source_id"]
    assert (
        input_receipt["self_state_hash"]
        == monitor_receipt["expected_self_state_hash"]
    )
    assert (
        input_receipt["self_state_hash"]
        != monitor_receipt["observed_self_state_hash"]
    )


def test_monitor_tampering_fails_before_semantic_credit():
    receipt = _monitor_receipt()
    receipt["perturbation_detected"] = False

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="monitor receipt hash mismatch",
    ):
        verify_internal_monitor_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "perturbation_detected",
            False,
            "monitor detection is inconsistent",
        ),
        (
            "observation_stage",
            "POST_REPORT",
            "must execute pre-report",
        ),
        (
            "reporter_executed",
            True,
            "reporter must not execute",
        ),
        (
            "subjective_consciousness_claimed",
            True,
            "subjective consciousness",
        ),
        (
            "accepted",
            True,
            "must not accept",
        ),
        (
            "write_authority",
            "FULL",
            "write authority",
        ),
        (
            "execution_authority",
            "FULL",
            "execution authority",
        ),
    ],
)
def test_rehashed_monitor_boundary_tampering_fails_closed(
    field,
    value,
    message,
):
    receipt = _monitor_receipt()
    forged = copy.deepcopy(receipt)
    forged[field] = value

    body = {
        key: item
        for key, item in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match=message,
    ):
        verify_internal_monitor_receipt(forged)


def test_rehashed_monitor_hash_relation_tampering_fails_closed():
    receipt = _monitor_receipt()
    forged = copy.deepcopy(receipt)
    forged["observed_self_state_hash"] = forged["expected_self_state_hash"]

    body = {
        key: item
        for key, item in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="hashes and mismatch state are inconsistent",
    ):
        verify_internal_monitor_receipt(forged)
def _workspace_candidates():
    return [
        {
            "candidate_id": "background",
            "priority": 1,
            "payload": {"kind": "background"},
        },
        {
            "candidate_id": "self-mismatch",
            "priority": 10,
            "payload": {
                "kind": "internal-mismatch",
                "path": "operating_state",
            },
        },
    ]


def _workspace_receipt():
    return build_workspace_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="hidden-self-perturbation",
        capacity=1,
        candidates=_workspace_candidates(),
    )


def test_workspace_admits_exactly_one_highest_priority_candidate():
    receipt = _workspace_receipt()

    assert receipt["winner_id"] == "self-mismatch"
    assert receipt["admitted_count"] == 1
    assert receipt["capacity"] == 1
    assert receipt["consumers_reached"] == []
    assert receipt["broadcast_executed"] is False
    assert verify_workspace_receipt(receipt) is True


def test_workspace_capacity_zero_admits_nobody():
    receipt = build_workspace_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="capacity-zero-control",
        capacity=0,
        candidates=_workspace_candidates(),
    )

    assert receipt["winner_id"] is None
    assert receipt["winner_payload_hash"] is None
    assert receipt["admitted_count"] == 0
    assert verify_workspace_receipt(receipt) is True


def test_workspace_capacity_greater_than_one_fails_closed():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="capacity must be zero or one",
    ):
        build_workspace_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="capacity-two-control",
            capacity=2,
            candidates=_workspace_candidates(),
        )


def test_workspace_empty_candidate_set_admits_nobody():
    receipt = build_workspace_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="empty",
        capacity=1,
        candidates=[],
    )

    assert receipt["candidates"] == []
    assert receipt["winner_id"] is None
    assert receipt["admitted_count"] == 0
    assert verify_workspace_receipt(receipt) is True


def test_workspace_tie_breaks_by_candidate_id():
    receipt = build_workspace_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="tie",
        capacity=1,
        candidates=[
            {
                "candidate_id": "z-candidate",
                "priority": 5,
                "payload": {"value": "z"},
            },
            {
                "candidate_id": "a-candidate",
                "priority": 5,
                "payload": {"value": "a"},
            },
        ],
    )

    assert receipt["winner_id"] == "a-candidate"
    assert [
        candidate["candidate_id"]
        for candidate in receipt["candidates"]
    ] == ["a-candidate", "z-candidate"]


def test_workspace_candidate_input_order_does_not_change_receipt():
    candidates = _workspace_candidates()

    first = build_workspace_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="order-invariance",
        capacity=1,
        candidates=candidates,
    )
    second = build_workspace_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="order-invariance",
        capacity=1,
        candidates=list(reversed(candidates)),
    )

    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]


def test_workspace_duplicate_candidate_ids_fail_closed():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="candidate ids must be unique",
    ):
        build_workspace_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="duplicate",
            capacity=1,
            candidates=[
                {
                    "candidate_id": "same",
                    "priority": 1,
                    "payload": {"value": 1},
                },
                {
                    "candidate_id": "same",
                    "priority": 2,
                    "payload": {"value": 2},
                },
            ],
        )


def test_workspace_non_integer_priority_fails_closed():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="priority must be an integer",
    ):
        build_workspace_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="bad-priority",
            capacity=1,
            candidates=[
                {
                    "candidate_id": "candidate",
                    "priority": 1.5,
                    "payload": {"value": 1},
                },
            ],
        )


def test_workspace_non_json_payload_fails_closed():
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="plain JSON values",
    ):
        build_workspace_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="bad-payload",
            capacity=1,
            candidates=[
                {
                    "candidate_id": "candidate",
                    "priority": 1,
                    "payload": {"bad": {1, 2}},
                },
            ],
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("winner_id", "background", "winner is inconsistent"),
        ("admitted_count", 0, "admitted count is inconsistent"),
        ("consumers_reached", ["attention"], "must not claim consumers"),
        ("broadcast_executed", True, "must not claim broadcast"),
        (
            "subjective_consciousness_claimed",
            True,
            "subjective consciousness",
        ),
        ("accepted", True, "must not accept"),
        ("write_authority", "FULL", "write authority"),
        ("execution_authority", "FULL", "execution authority"),
    ],
)
def test_rehashed_workspace_boundary_tampering_fails_closed(
    field,
    value,
    message,
):
    receipt = _workspace_receipt()
    forged = copy.deepcopy(receipt)
    forged[field] = value

    body = {
        key: item
        for key, item in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match=message,
    ):
        verify_workspace_receipt(forged)


def test_rehashed_workspace_candidate_order_tampering_fails_closed():
    receipt = _workspace_receipt()
    forged = copy.deepcopy(receipt)
    forged["candidates"] = list(reversed(forged["candidates"]))

    body = {
        key: item
        for key, item in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="not deterministically ranked",
    ):
        verify_workspace_receipt(forged)
def _broadcast_receipt(*, connected=True, capacity=1):
    workspace = build_workspace_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="hidden-self-perturbation",
        capacity=capacity,
        candidates=_workspace_candidates(),
    )
    broadcast = build_workspace_broadcast_receipt(
        workspace_receipt=workspace,
        broadcast_connected=connected,
    )
    return workspace, broadcast


def test_workspace_broadcast_reaches_both_declared_consumers():
    workspace, receipt = _broadcast_receipt()

    assert workspace["winner_id"] == "self-mismatch"
    assert receipt["winner_id"] == "self-mismatch"
    assert receipt["consumers_reached"] == ["attention", "action"]
    assert receipt["consumer_payload_hashes"] == {
        "attention": workspace["winner_payload_hash"],
        "action": workspace["winner_payload_hash"],
    }
    assert receipt["broadcast_executed"] is True
    assert receipt["global_availability"] is True
    assert verify_workspace_broadcast_receipt(
        receipt,
        workspace_receipt=workspace,
    ) is True


def test_disconnected_broadcast_destroys_global_availability():
    workspace, receipt = _broadcast_receipt(connected=False)

    assert workspace["admitted_count"] == 1
    assert workspace["winner_id"] == "self-mismatch"
    assert receipt["broadcast_connected"] is False
    assert receipt["consumers_reached"] == []
    assert receipt["consumer_payload_hashes"] == {}
    assert receipt["broadcast_executed"] is False
    assert receipt["global_availability"] is False
    assert verify_workspace_broadcast_receipt(
        receipt,
        workspace_receipt=workspace,
    ) is True


def test_zero_capacity_cannot_broadcast_without_admitted_winner():
    workspace, receipt = _broadcast_receipt(
        connected=True,
        capacity=0,
    )

    assert workspace["admitted_count"] == 0
    assert receipt["consumers_reached"] == []
    assert receipt["broadcast_executed"] is False
    assert receipt["global_availability"] is False
    assert verify_workspace_broadcast_receipt(
        receipt,
        workspace_receipt=workspace,
    ) is True


def test_broadcast_requires_boolean_connection_state():
    workspace = _workspace_receipt()

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="broadcast_connected must be boolean",
    ):
        build_workspace_broadcast_receipt(
            workspace_receipt=workspace,
            broadcast_connected=1,
        )


def test_broadcast_is_deterministic_for_identical_workspace():
    workspace = _workspace_receipt()

    first = build_workspace_broadcast_receipt(
        workspace_receipt=workspace,
        broadcast_connected=True,
    )
    second = build_workspace_broadcast_receipt(
        workspace_receipt=workspace,
        broadcast_connected=True,
    )

    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]


def test_broadcast_rejects_different_workspace_binding():
    workspace, receipt = _broadcast_receipt()

    other_workspace = build_workspace_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="other-condition",
        capacity=1,
        candidates=_workspace_candidates(),
    )

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="not bound to workspace admission",
    ):
        verify_workspace_broadcast_receipt(
            receipt,
            workspace_receipt=other_workspace,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "consumers_reached",
            ["attention"],
            "broadcast consumers are inconsistent",
        ),
        (
            "consumer_payload_hashes",
            {"attention": "0" * 64, "action": "0" * 64},
            "consumer payloads are inconsistent",
        ),
        (
            "broadcast_executed",
            False,
            "execution state is inconsistent",
        ),
        (
            "global_availability",
            False,
            "global availability is inconsistent",
        ),
        (
            "subjective_consciousness_claimed",
            True,
            "subjective consciousness",
        ),
        (
            "accepted",
            True,
            "must not accept",
        ),
        (
            "write_authority",
            "FULL",
            "write authority",
        ),
        (
            "execution_authority",
            "FULL",
            "execution authority",
        ),
    ],
)
def test_rehashed_broadcast_tampering_fails_closed(
    field,
    value,
    message,
):
    workspace, receipt = _broadcast_receipt()
    forged = copy.deepcopy(receipt)
    forged[field] = value

    body = {
        key: item
        for key, item in forged.items()
        if key != "receipt_hash"
    }

    from holosim.canonical import stable_hash

    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match=message,
    ):
        verify_workspace_broadcast_receipt(
            forged,
            workspace_receipt=workspace,
        )

def test_monitor_mismatch_candidate_is_derived_from_verified_monitor():
    monitor = _monitor_receipt()
    candidate = build_monitor_mismatch_candidate(
        monitor_receipt=monitor,
        priority=10,
    )
    assert candidate == {
        "candidate_id": "self-mismatch",
        "priority": 10,
        "payload": {
            "kind": "internal-mismatch",
            "monitor_receipt_hash": monitor["receipt_hash"],
            "self_source_id": monitor["self_source_id"],
            "observed_self_state_hash": monitor["observed_self_state_hash"],
            "mismatch_paths": monitor["mismatch_paths"],
        },
    }


def test_monitor_mismatch_candidate_binds_into_workspace_winner():
    monitor = _monitor_receipt()
    candidate = build_monitor_mismatch_candidate(
        monitor_receipt=monitor,
        priority=10,
    )
    workspace = build_workspace_receipt(
        experiment_id=monitor["experiment_id"],
        condition_id=monitor["condition_id"],
        capacity=1,
        candidates=[candidate],
    )
    from holosim.canonical import stable_hash
    assert workspace["winner_id"] == "self-mismatch"
    assert workspace["winner_payload_hash"] == stable_hash(candidate["payload"])


def test_monitor_mismatch_candidate_rejects_nominal_monitor():
    monitor = build_internal_monitor_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="nominal",
        self_source_id="self-channel",
        expected_self_state={"operating_state": "nominal"},
        observed_self_state={"operating_state": "nominal"},
    )
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="does not contain a detected perturbation",
    ):
        build_monitor_mismatch_candidate(monitor_receipt=monitor, priority=10)


def test_monitor_mismatch_candidate_rejects_tampered_monitor():
    monitor = _monitor_receipt()
    monitor["mismatch_paths"] = ["forged"]
    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="monitor receipt hash mismatch",
    ):
        build_monitor_mismatch_candidate(monitor_receipt=monitor, priority=10)


def test_monitor_mismatch_candidate_preserves_all_mismatch_paths():
    monitor = build_internal_monitor_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="multi-perturbation",
        self_source_id="self-channel",
        expected_self_state={"a": 1, "z": 1},
        observed_self_state={"a": 2, "z": 2},
    )
    candidate = build_monitor_mismatch_candidate(
        monitor_receipt=monitor,
        priority=10,
    )
    assert candidate["payload"]["mismatch_paths"] == ["a", "z"]

CONTINUITY_SOURCE_ITEMS = [
    {
        "id": "active-goal",
        "requires": ["verified-boundary"],
        "value": "continue current work",
    },
    {
        "id": "verified-boundary",
        "requires": [],
        "value": "observation does not grant authority",
    },
]


def _continuity_head_check(*, current_hash="head-10", current_idx=10):
    recall_kernel = {
        "identity": {"system": "HOLO-Invariant"},
        "last_verified_state": "head-10",
        "history": ["head-9", "head-10"],
    }
    contract = build_continuity_compliance_contract(
        contract_id="functional-consciousness-continuity-contract",
        subject_id="HOLO-Invariant",
        recall_kernel=recall_kernel,
        observed_required_fields=list(recall_kernel),
        authority_limits=["write:NONE", "execution:NONE"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["head-changed"],
    )
    binding = build_continuity_head_binding(
        binding_id="functional-consciousness-continuity-binding",
        contract=contract,
        originating_head_hash="head-10",
        originating_head_idx=10,
    )
    return evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash=current_hash,
        current_head_idx=current_idx,
    )


def _continuity_packet(*, head_check=None, conflicts=()):
    state = build_reconstructed_state(
        "functional-consciousness-reentry",
        ["active-goal"],
        CONTINUITY_SOURCE_ITEMS,
    )
    return build_verified_cold_start_reentry_packet(
        packet_id="functional-consciousness-reentry-packet",
        reconstructed_state=state,
        source_items=CONTINUITY_SOURCE_ITEMS,
        head_check=head_check or _continuity_head_check(),
        conflicts=list(conflicts),
    )


def _experiment_continuity_receipt(packet=None):
    packet = packet or _continuity_packet()
    return build_experiment_continuity_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="post-gap-continuity",
        reentry_packet=packet,
        source_items=CONTINUITY_SOURCE_ITEMS,
    )


def test_current_verified_reentry_binds_continuity_without_authority():
    packet = _continuity_packet()
    receipt = _experiment_continuity_receipt(packet)

    assert packet["status"] == "READY_FOR_REENTRY"
    assert receipt["continuity_bound"] is True
    assert receipt["reentry_packet_hash"] == packet["packet_hash"]
    assert receipt["reconstructed_state_hash"] == packet["reconstructed_state_hash"]
    assert receipt["head_status"] == "CURRENT"
    assert receipt["subjective_consciousness_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert verify_experiment_continuity_receipt(
        receipt,
        reentry_packet=packet,
        source_items=CONTINUITY_SOURCE_ITEMS,
    ) is True


def test_stale_head_does_not_receive_continuity_credit():
    packet = _continuity_packet(
        head_check=_continuity_head_check(
            current_hash="head-11",
            current_idx=11,
        )
    )
    receipt = _experiment_continuity_receipt(packet)

    assert packet["status"] == "BLOCKED_HEAD"
    assert receipt["head_status"] == "STALE"
    assert receipt["continuity_bound"] is False
    assert verify_experiment_continuity_receipt(
        receipt,
        reentry_packet=packet,
        source_items=CONTINUITY_SOURCE_ITEMS,
    ) is True


def test_unresolved_conflict_does_not_receive_continuity_credit():
    packet = _continuity_packet(
        conflicts=[
            {
                "id": "goal-conflict",
                "left_item_id": "active-goal",
                "right_item_id": "active-goal-correction",
                "reason": "unresolved",
            }
        ]
    )
    receipt = _experiment_continuity_receipt(packet)

    assert packet["status"] == "BLOCKED_CONFLICT"
    assert receipt["continuity_bound"] is False


def test_continuity_receipt_tampering_fails_closed():
    packet = _continuity_packet()
    receipt = _experiment_continuity_receipt(packet)
    receipt["continuity_bound"] = False

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="continuity receipt hash mismatch",
    ):
        verify_experiment_continuity_receipt(
            receipt,
            reentry_packet=packet,
            source_items=CONTINUITY_SOURCE_ITEMS,
        )


def test_continuity_receipt_cannot_be_reused_with_other_packet():
    packet = _continuity_packet()
    receipt = _experiment_continuity_receipt(packet)

    other_packet = _continuity_packet(
        head_check=_continuity_head_check(
            current_hash="head-11",
            current_idx=11,
        )
    )

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="continuity receipt is not bound to reentry evidence",
    ):
        verify_experiment_continuity_receipt(
            receipt,
            reentry_packet=other_packet,
            source_items=CONTINUITY_SOURCE_ITEMS,
        )
