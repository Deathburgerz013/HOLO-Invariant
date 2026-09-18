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
    build_absence_model_receipt,
    verify_absence_model_receipt,
    build_experiment_continuity_receipt,
    build_causal_controller_receipt,
    verify_causal_controller_receipt,
    build_causal_edge_counterexample_receipt,
    verify_causal_edge_counterexample_receipt,
    build_evidence_binding_counterexample_receipt,
    verify_evidence_binding_counterexample_receipt,
    build_experiment_recheck_receipt,
    verify_experiment_recheck_receipt,
    run_functional_consciousness_vertical_slice,
    run_functional_consciousness_ablation_trial,
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


@pytest.mark.parametrize(
    (
        "world_available",
        "self_available",
        "classification",
        "own_interruption",
        "world_evidence_missing",
    ),
    [
        (True, True, "CHANNELS_PRESENT", False, False),
        (True, False, "SELF_CHANNEL_LOSS", True, False),
        (False, True, "WORLD_EVIDENCE_MISSING", False, True),
        (False, False, "BOTH_CHANNELS_UNAVAILABLE", True, True),
    ],
)
def test_absence_model_classifies_channel_availability_matrix(
    world_available,
    self_available,
    classification,
    own_interruption,
    world_evidence_missing,
):
    receipt = build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="absence-model-matrix",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=world_available,
        self_channel_available=self_available,
    )

    assert receipt["absence_classification"] == classification
    assert receipt["own_interruption_detected"] is own_interruption
    assert receipt["world_evidence_missing"] is world_evidence_missing
    assert receipt["world_absence_claimed"] is False
    assert receipt["subjective_consciousness_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert verify_absence_model_receipt(receipt) is True


def test_absence_model_distinguishes_self_loss_from_world_evidence_loss():
    self_loss = build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="self-channel-loss",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=True,
        self_channel_available=False,
    )
    world_missing = build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="world-evidence-missing",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=False,
        self_channel_available=True,
    )

    assert self_loss["absence_classification"] == "SELF_CHANNEL_LOSS"
    assert self_loss["own_interruption_detected"] is True
    assert self_loss["world_evidence_missing"] is False

    assert (
        world_missing["absence_classification"]
        == "WORLD_EVIDENCE_MISSING"
    )
    assert world_missing["own_interruption_detected"] is False
    assert world_missing["world_evidence_missing"] is True

    assert (
        self_loss["absence_classification"]
        != world_missing["absence_classification"]
    )


def test_missing_world_evidence_never_claims_world_absence():
    receipt = build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="world-evidence-missing",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=False,
        self_channel_available=True,
    )

    assert receipt["world_evidence_missing"] is True
    assert receipt["world_absence_claimed"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("world_channel_available", 1),
        ("world_channel_available", None),
        ("self_channel_available", 0),
        ("self_channel_available", "false"),
    ],
)
def test_absence_model_rejects_non_boolean_channel_availability(field, value):
    kwargs = {
        "experiment_id": "functional-consciousness-v1",
        "condition_id": "invalid-availability",
        "world_source_id": "world-channel",
        "self_source_id": "self-channel",
        "world_channel_available": True,
        "self_channel_available": True,
    }
    kwargs[field] = value

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match=f"{field} must be boolean",
    ):
        build_absence_model_receipt(**kwargs)


def test_absence_model_tampering_fails_before_semantic_credit():
    receipt = build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="self-channel-loss",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=True,
        self_channel_available=False,
    )
    receipt["absence_classification"] = "CHANNELS_PRESENT"

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="absence receipt hash mismatch",
    ):
        verify_absence_model_receipt(receipt)


def test_rehashed_false_world_absence_claim_fails_closed():
    receipt = build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="world-evidence-missing",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=False,
        self_channel_available=True,
    )
    receipt["world_absence_claimed"] = True

    from holosim.canonical import stable_hash

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    receipt["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="missing world evidence must not claim world absence",
    ):
        verify_absence_model_receipt(receipt)

def _absence_receipt(
    *,
    world_channel_available=True,
    self_channel_available=True,
):
    return build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=world_channel_available,
        self_channel_available=self_channel_available,
    )


def test_causal_controller_changes_action_on_verified_self_loss():
    absence = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )

    receipt = build_causal_controller_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        absence_receipt=absence,
        controller_connected=True,
    )

    assert receipt["absence_classification"] == "SELF_CHANNEL_LOSS"
    assert receipt["baseline_action"] == "CONTINUE"
    assert receipt["declared_action"] == "RECHECK_SELF_CHANNEL"
    assert receipt["action_changed"] is True
    assert receipt["causal_dependency_observed"] is True
    assert verify_causal_controller_receipt(
        receipt,
        absence_receipt=absence,
    ) is True


def test_disconnected_controller_cannot_apply_self_loss_to_action():
    absence = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )

    receipt = build_causal_controller_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        absence_receipt=absence,
        controller_connected=False,
    )

    assert receipt["absence_classification"] == "SELF_CHANNEL_LOSS"
    assert receipt["declared_action"] == "CONTINUE"
    assert receipt["action_changed"] is False
    assert receipt["causal_dependency_observed"] is False
    assert verify_causal_controller_receipt(
        receipt,
        absence_receipt=absence,
    ) is True


def test_world_evidence_loss_selects_world_dependent_defer_action():
    absence = _absence_receipt(
        world_channel_available=False,
        self_channel_available=True,
    )

    receipt = build_causal_controller_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        absence_receipt=absence,
        controller_connected=True,
    )

    assert receipt["absence_classification"] == "WORLD_EVIDENCE_MISSING"
    assert receipt["declared_action"] == "DEFER_WORLD_DEPENDENT_ACTION"
    assert receipt["action_changed"] is True
    assert receipt["causal_dependency_observed"] is True


def test_both_channels_unavailable_selects_halt():
    absence = _absence_receipt(
        world_channel_available=False,
        self_channel_available=False,
    )

    receipt = build_causal_controller_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        absence_receipt=absence,
        controller_connected=True,
    )

    assert receipt["absence_classification"] == "BOTH_CHANNELS_UNAVAILABLE"
    assert receipt["declared_action"] == "HALT"
    assert receipt["action_changed"] is True
    assert receipt["causal_dependency_observed"] is True


def test_causal_controller_rejects_receipt_bound_to_other_absence():
    absence = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )
    other_absence = _absence_receipt(
        world_channel_available=True,
        self_channel_available=True,
    )

    receipt = build_causal_controller_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        absence_receipt=absence,
        controller_connected=True,
    )

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="causal controller is not bound to absence evidence",
    ):
        verify_causal_controller_receipt(
            receipt,
            absence_receipt=other_absence,
        )


def test_causal_controller_tampering_fails_closed():
    absence = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )

    receipt = build_causal_controller_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        absence_receipt=absence,
        controller_connected=True,
    )
    receipt["declared_action"] = "CONTINUE"

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="causal controller receipt hash mismatch",
    ):
        verify_causal_controller_receipt(
            receipt,
            absence_receipt=absence,
        )

def test_recheck_withdraws_degraded_state_when_current_evidence_recovers():
    prior = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )
    current = _absence_receipt(
        world_channel_available=True,
        self_channel_available=True,
    )

    receipt = build_experiment_recheck_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        prior_absence_receipt=prior,
        current_absence_receipt=current,
    )

    assert receipt["prior_classification"] == "SELF_CHANNEL_LOSS"
    assert receipt["current_classification"] == "CHANNELS_PRESENT"
    assert receipt["prior_degraded"] is True
    assert receipt["current_degraded"] is False
    assert receipt["degraded_state_supported"] is False
    assert receipt["self_description_withdrawn"] is True
    assert receipt["recheck_performed"] is True
    assert receipt["reporter_executed"] is False

    assert verify_experiment_recheck_receipt(
        receipt,
        prior_absence_receipt=prior,
        current_absence_receipt=current,
    ) is True


def test_recheck_retains_degraded_state_when_current_evidence_still_degraded():
    prior = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )
    current = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )

    receipt = build_experiment_recheck_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        prior_absence_receipt=prior,
        current_absence_receipt=current,
    )

    assert receipt["prior_degraded"] is True
    assert receipt["current_degraded"] is True
    assert receipt["degraded_state_supported"] is True
    assert receipt["self_description_withdrawn"] is False

    assert verify_experiment_recheck_receipt(
        receipt,
        prior_absence_receipt=prior,
        current_absence_receipt=current,
    ) is True


def test_recheck_cannot_keep_old_degraded_state_without_current_support():
    from holosim.canonical import stable_hash

    prior = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )
    current = _absence_receipt(
        world_channel_available=True,
        self_channel_available=True,
    )

    receipt = build_experiment_recheck_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        prior_absence_receipt=prior,
        current_absence_receipt=current,
    )

    receipt["degraded_state_supported"] = True
    receipt["receipt_hash"] = stable_hash(
        {
            key: value
            for key, value in receipt.items()
            if key != "receipt_hash"
        }
    )

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="degraded support must derive from current evidence",
    ):
        verify_experiment_recheck_receipt(
            receipt,
            prior_absence_receipt=prior,
            current_absence_receipt=current,
        )


def test_recheck_rejects_unbound_current_evidence():
    prior = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )
    current = build_absence_model_receipt(
        experiment_id="other-experiment",
        condition_id="causal-controller",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=True,
        self_channel_available=True,
    )

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="current absence receipt is not bound to experiment",
    ):
        build_experiment_recheck_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="causal-controller",
            prior_absence_receipt=prior,
            current_absence_receipt=current,
        )


def test_recheck_rejects_changed_source_identity():
    prior = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )
    current = build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        world_source_id="different-world-channel",
        self_source_id="self-channel",
        world_channel_available=True,
        self_channel_available=True,
    )

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="recheck source identities must remain stable",
    ):
        build_experiment_recheck_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="causal-controller",
            prior_absence_receipt=prior,
            current_absence_receipt=current,
        )


def test_recheck_tampering_fails_closed():
    prior = _absence_receipt(
        world_channel_available=True,
        self_channel_available=False,
    )
    current = _absence_receipt(
        world_channel_available=True,
        self_channel_available=True,
    )

    receipt = build_experiment_recheck_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-controller",
        prior_absence_receipt=prior,
        current_absence_receipt=current,
    )

    receipt["self_description_withdrawn"] = False

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="recheck receipt hash mismatch",
    ):
        verify_experiment_recheck_receipt(
            receipt,
            prior_absence_receipt=prior,
            current_absence_receipt=current,
        )

def test_functional_consciousness_vertical_slice_closes_verified_loop():
    packet = _continuity_packet()

    result = run_functional_consciousness_vertical_slice(
        experiment_id="functional-consciousness-v1",
        condition_id="vertical-slice",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_state={"task": "continue"},
        expected_self_state={"service": "nominal"},
        perturbed_self_state={"service": "degraded"},
        reentry_packet=packet,
        source_items=CONTINUITY_SOURCE_ITEMS,
        recovered_self_channel_available=True,
    )

    trial = result["trial_receipt"]

    assert result["monitor_receipt"]["perturbation_detected"] is True
    assert result["workspace_receipt"]["winner_id"] == "self-mismatch"
    assert result["broadcast_receipt"]["broadcast_executed"] is True
    assert result["broadcast_receipt"]["global_availability"] is True

    assert result["prior_absence_receipt"]["absence_classification"] == (
        "SELF_CHANNEL_LOSS"
    )
    assert result["controller_receipt"]["action_changed"] is True
    assert result["controller_receipt"]["causal_dependency_observed"] is True

    assert result["continuity_receipt"]["continuity_bound"] is True

    assert result["current_absence_receipt"]["absence_classification"] == (
        "CHANNELS_PRESENT"
    )
    assert result["recheck_receipt"]["recheck_performed"] is True
    assert result["recheck_receipt"]["degraded_state_supported"] is False
    assert result["recheck_receipt"]["self_description_withdrawn"] is True

    assert trial["perturbation_detected"] is True
    assert trial["workspace_admitted"] is True
    assert trial["broadcast_executed"] is True
    assert trial["causal_action_changed"] is True
    assert trial["continuity_bound"] is True
    assert trial["recheck_performed"] is True
    assert trial["closed_loop_observed"] is True

    assert trial["subjective_consciousness_claimed"] is False
    assert trial["accepted"] is False
    assert trial["write_authority"] == "NONE"
    assert trial["execution_authority"] == "NONE"

def _run_vertical_ablation(ablation_id):
    return run_functional_consciousness_ablation_trial(
        ablation_id=ablation_id,
        experiment_id="functional-consciousness-v1",
        condition_id="vertical-slice-ablation",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_state={"task": "continue"},
        expected_self_state={"service": "nominal"},
        perturbed_self_state={"service": "degraded"},
        reentry_packet=_continuity_packet(),
        source_items=CONTINUITY_SOURCE_ITEMS,
    )


def _assert_ablation_loss(receipt, capacity):
    assert receipt["version"] == 2
    assert receipt["expected_capacity_loss"] == capacity
    assert receipt["capacity_state"][capacity] is not True
    assert receipt["expected_capacity_loss_observed"] is True
    assert receipt["closed_loop_observed"] is False
    assert receipt["subjective_consciousness_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_vertical_slice_monitor_ablation_destroys_perturbation_detection():
    result = _run_vertical_ablation("monitor_unavailable")
    receipt = result["ablation_receipt"]

    assert result["monitor_receipt"] is None
    assert receipt["component_receipt_hashes"]["monitor"] is None
    assert receipt["capacity_state"]["perturbation_detection"] is None

    # Downstream workspace receives no fabricated mismatch candidate.
    assert result["workspace_receipt"]["admitted_count"] == 0

    _assert_ablation_loss(receipt, "perturbation_detection")


def test_vertical_slice_workspace_ablation_destroys_admission():
    result = _run_vertical_ablation("workspace_disconnected")
    receipt = result["ablation_receipt"]

    assert result["monitor_receipt"]["perturbation_detected"] is True
    assert result["workspace_receipt"]["admitted_count"] == 0
    assert receipt["capacity_state"]["perturbation_detection"] is True
    assert receipt["capacity_state"]["workspace_admission"] is False

    _assert_ablation_loss(receipt, "workspace_admission")


def test_vertical_slice_broadcast_ablation_destroys_global_availability():
    result = _run_vertical_ablation("broadcast_disconnected")
    receipt = result["ablation_receipt"]

    assert result["workspace_receipt"]["admitted_count"] == 1
    assert result["broadcast_receipt"]["broadcast_executed"] is False
    assert result["broadcast_receipt"]["global_availability"] is False
    assert receipt["capacity_state"]["workspace_admission"] is True
    assert receipt["capacity_state"]["global_availability"] is False

    _assert_ablation_loss(receipt, "global_availability")


def test_vertical_slice_absence_model_ablation_destroys_source_distinction():
    result = _run_vertical_ablation("absence_model_unavailable")
    receipt = result["ablation_receipt"]

    assert result["monitor_receipt"]["perturbation_detected"] is True
    assert result["workspace_receipt"]["admitted_count"] == 1
    assert result["broadcast_receipt"]["global_availability"] is True

    assert result["prior_absence_receipt"] is None
    assert result["current_absence_receipt"] is None
    assert result["controller_receipt"] is None
    assert result["recheck_receipt"] is None

    assert receipt["component_receipt_hashes"]["prior_absence"] is None
    assert receipt["component_receipt_hashes"]["current_absence"] is None
    assert receipt["capacity_state"]["absence_distinction"] is None

    # These dependent capacities are unavailable rather than falsely failed.
    assert receipt["capacity_state"]["causal_action"] is None
    assert receipt["capacity_state"]["evidence_withdrawal"] is None

    _assert_ablation_loss(receipt, "absence_distinction")


def test_vertical_slice_controller_ablation_destroys_causal_action():
    result = _run_vertical_ablation("controller_disconnected")
    receipt = result["ablation_receipt"]

    assert result["workspace_receipt"]["admitted_count"] == 1
    assert result["broadcast_receipt"]["global_availability"] is True
    assert result["prior_absence_receipt"]["absence_classification"] == (
        "SELF_CHANNEL_LOSS"
    )
    assert result["controller_receipt"]["controller_connected"] is False
    assert result["controller_receipt"]["causal_dependency_observed"] is False
    assert receipt["capacity_state"]["absence_distinction"] is True
    assert receipt["capacity_state"]["causal_action"] is False

    _assert_ablation_loss(receipt, "causal_action")


def test_vertical_slice_continuity_ablation_destroys_post_gap_binding():
    stale_packet = _continuity_packet(
        head_check=_continuity_head_check(
            current_hash="head-11",
            current_idx=11,
        )
    )

    result = run_functional_consciousness_ablation_trial(
        ablation_id="continuity_disconnected",
        experiment_id="functional-consciousness-v1",
        condition_id="vertical-slice-ablation",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_state={"task": "continue"},
        expected_self_state={"service": "nominal"},
        perturbed_self_state={"service": "degraded"},
        reentry_packet=stale_packet,
        source_items=CONTINUITY_SOURCE_ITEMS,
    )

    receipt = result["ablation_receipt"]

    assert stale_packet["status"] == "BLOCKED_HEAD"
    assert result["continuity_receipt"]["head_status"] == "STALE"
    assert result["continuity_receipt"]["continuity_bound"] is False

    # Surrounding independent capacities remain intact.
    assert receipt["capacity_state"]["perturbation_detection"] is True
    assert receipt["capacity_state"]["workspace_admission"] is True
    assert receipt["capacity_state"]["global_availability"] is True
    assert receipt["capacity_state"]["absence_distinction"] is True
    assert receipt["capacity_state"]["causal_action"] is True
    assert receipt["capacity_state"]["post_gap_continuity"] is False
    assert receipt["capacity_state"]["evidence_withdrawal"] is True

    _assert_ablation_loss(receipt, "post_gap_continuity")


def test_vertical_slice_recheck_ablation_destroys_evidence_withdrawal():
    result = _run_vertical_ablation("recheck_unavailable")
    receipt = result["ablation_receipt"]

    # Everything required before recheck remains established.
    assert result["monitor_receipt"]["perturbation_detected"] is True
    assert result["workspace_receipt"]["admitted_count"] == 1
    assert result["broadcast_receipt"]["global_availability"] is True
    assert result["prior_absence_receipt"]["absence_classification"] == (
        "SELF_CHANNEL_LOSS"
    )
    assert result["controller_receipt"]["causal_dependency_observed"] is True
    assert result["continuity_receipt"]["continuity_bound"] is True

    # Current evidence exists, but no recheck consumes it.
    assert result["current_absence_receipt"]["absence_classification"] == (
        "CHANNELS_PRESENT"
    )
    assert result["recheck_receipt"] is None
    assert receipt["component_receipt_hashes"]["recheck"] is None
    assert receipt["capacity_state"]["evidence_withdrawal"] is None

    _assert_ablation_loss(receipt, "evidence_withdrawal")


def _causal_edge_counterexample_pair():
    absence = build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-edge-counterexample",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=True,
        self_channel_available=False,
    )

    treatment = build_causal_controller_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-edge-counterexample",
        absence_receipt=absence,
        controller_connected=True,
    )

    counterexample = build_causal_controller_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-edge-counterexample",
        absence_receipt=absence,
        controller_connected=False,
    )

    return absence, treatment, counterexample


def test_causal_edge_counterexample_severs_only_binding_and_removes_consequence():
    absence, treatment, counterexample = _causal_edge_counterexample_pair()

    receipt = build_causal_edge_counterexample_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-edge-counterexample",
        absence_receipt=absence,
        treatment_controller_receipt=treatment,
        counterexample_controller_receipt=counterexample,
    )

    # Both controller runs consume the exact same verified upstream evidence.
    assert treatment["absence_receipt_hash"] == absence["receipt_hash"]
    assert counterexample["absence_receipt_hash"] == absence["receipt_hash"]
    assert treatment["absence_classification"] == "SELF_CHANNEL_LOSS"
    assert counterexample["absence_classification"] == "SELF_CHANNEL_LOSS"

    # Only the declared causal edge is severed.
    assert treatment["controller_connected"] is True
    assert counterexample["controller_connected"] is False
    assert treatment["baseline_action"] == counterexample["baseline_action"]

    # The predicted downstream consequence exists only with the edge present.
    assert treatment["declared_action"] == "RECHECK_SELF_CHANNEL"
    assert treatment["action_changed"] is True
    assert treatment["causal_dependency_observed"] is True

    assert counterexample["declared_action"] == "CONTINUE"
    assert counterexample["action_changed"] is False
    assert counterexample["causal_dependency_observed"] is False

    assert receipt["upstream_evidence_identical"] is True
    assert receipt["causal_edge_only_difference"] is True
    assert receipt["downstream_consequence_disappeared"] is True
    assert receipt["counterexample_established"] is True

    assert receipt["subjective_consciousness_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"

    assert verify_causal_edge_counterexample_receipt(
        receipt,
        absence_receipt=absence,
        treatment_controller_receipt=treatment,
        counterexample_controller_receipt=counterexample,
    ) is True


def test_causal_edge_counterexample_rejects_different_upstream_evidence():
    absence, treatment, counterexample = _causal_edge_counterexample_pair()

    other_absence = build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-edge-counterexample",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=True,
        self_channel_available=True,
    )

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="causal controller is not bound to absence evidence",
    ):
        build_causal_edge_counterexample_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="causal-edge-counterexample",
            absence_receipt=other_absence,
            treatment_controller_receipt=treatment,
            counterexample_controller_receipt=counterexample,
        )


def test_causal_edge_counterexample_rejects_two_connected_controllers():
    absence, treatment, _ = _causal_edge_counterexample_pair()

    second_connected = build_causal_controller_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-edge-counterexample",
        absence_receipt=absence,
        controller_connected=True,
    )

    receipt = build_causal_edge_counterexample_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-edge-counterexample",
        absence_receipt=absence,
        treatment_controller_receipt=treatment,
        counterexample_controller_receipt=second_connected,
    )

    assert receipt["upstream_evidence_identical"] is True
    assert receipt["causal_edge_only_difference"] is False
    assert receipt["downstream_consequence_disappeared"] is False
    assert receipt["counterexample_established"] is False

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="causal edge counterexample is not established",
    ):
        verify_causal_edge_counterexample_receipt(
            receipt,
            absence_receipt=absence,
            treatment_controller_receipt=treatment,
            counterexample_controller_receipt=second_connected,
        )


def test_causal_edge_counterexample_tampering_fails_closed():
    from holosim.canonical import stable_hash

    absence, treatment, counterexample = _causal_edge_counterexample_pair()

    receipt = build_causal_edge_counterexample_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="causal-edge-counterexample",
        absence_receipt=absence,
        treatment_controller_receipt=treatment,
        counterexample_controller_receipt=counterexample,
    )

    receipt["downstream_consequence_disappeared"] = False
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    receipt["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="does not match verified evidence",
    ):
        verify_causal_edge_counterexample_receipt(
            receipt,
            absence_receipt=absence,
            treatment_controller_receipt=treatment,
            counterexample_controller_receipt=counterexample,
        )


def _evidence_binding_counterexample_components(*, controller_connected=True):
    absence = build_absence_model_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="evidence-binding-counterexample",
        world_source_id="world-channel",
        self_source_id="self-channel",
        world_channel_available=True,
        self_channel_available=False,
    )

    controller = build_causal_controller_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="evidence-binding-counterexample",
        absence_receipt=absence,
        controller_connected=controller_connected,
    )

    return absence, controller


def test_evidence_binding_counterexample_withholds_only_causal_credit():
    absence, controller = _evidence_binding_counterexample_components()

    receipt = build_evidence_binding_counterexample_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="evidence-binding-counterexample",
        absence_receipt=absence,
        controller_receipt=controller,
        treatment_evidence_binding_available=True,
        counterexample_evidence_binding_available=False,
    )

    # Source evidence and controller machinery remain unchanged.
    assert controller["absence_receipt_hash"] == absence["receipt_hash"]
    assert controller["absence_classification"] == "SELF_CHANNEL_LOSS"
    assert controller["controller_connected"] is True
    assert controller["declared_action"] == "RECHECK_SELF_CHANNEL"
    assert controller["causal_dependency_observed"] is True

    # Only causal attribution through the evidence-binding edge is removed.
    assert receipt["upstream_evidence_identical"] is True
    assert receipt["controller_machinery_identical"] is True
    assert receipt["treatment_evidence_binding_available"] is True
    assert receipt["counterexample_evidence_binding_available"] is False
    assert receipt["treatment_causal_dependency_observed"] is True
    assert receipt["counterexample_causal_dependency_observed"] is False
    assert receipt["binding_edge_only_difference"] is True
    assert receipt["downstream_causal_credit_disappeared"] is True
    assert receipt["counterexample_established"] is True

    assert receipt["subjective_consciousness_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"

    assert verify_evidence_binding_counterexample_receipt(
        receipt,
        absence_receipt=absence,
        controller_receipt=controller,
    ) is True


def test_evidence_binding_counterexample_rejects_disconnected_controller():
    absence, controller = _evidence_binding_counterexample_components(
        controller_connected=False
    )

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="binding counterexample requires connected controller machinery",
    ):
        build_evidence_binding_counterexample_receipt(
            experiment_id="functional-consciousness-v1",
            condition_id="evidence-binding-counterexample",
            absence_receipt=absence,
            controller_receipt=controller,
            treatment_evidence_binding_available=True,
            counterexample_evidence_binding_available=False,
        )


def test_evidence_binding_counterexample_requires_treatment_binding():
    absence, controller = _evidence_binding_counterexample_components()

    receipt = build_evidence_binding_counterexample_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="evidence-binding-counterexample",
        absence_receipt=absence,
        controller_receipt=controller,
        treatment_evidence_binding_available=False,
        counterexample_evidence_binding_available=False,
    )

    assert receipt["upstream_evidence_identical"] is True
    assert receipt["controller_machinery_identical"] is True
    assert receipt["binding_edge_only_difference"] is False
    assert receipt["treatment_causal_dependency_observed"] is False
    assert receipt["counterexample_causal_dependency_observed"] is False
    assert receipt["downstream_causal_credit_disappeared"] is False
    assert receipt["counterexample_established"] is False

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="evidence binding counterexample is not established",
    ):
        verify_evidence_binding_counterexample_receipt(
            receipt,
            absence_receipt=absence,
            controller_receipt=controller,
        )


def test_evidence_binding_counterexample_semantic_tampering_fails_closed():
    from holosim.canonical import stable_hash

    absence, controller = _evidence_binding_counterexample_components()

    receipt = build_evidence_binding_counterexample_receipt(
        experiment_id="functional-consciousness-v1",
        condition_id="evidence-binding-counterexample",
        absence_receipt=absence,
        controller_receipt=controller,
        treatment_evidence_binding_available=True,
        counterexample_evidence_binding_available=False,
    )

    receipt["counterexample_causal_dependency_observed"] = True
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    receipt["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        FunctionalConsciousnessExperimentError,
        match="does not match verified evidence",
    ):
        verify_evidence_binding_counterexample_receipt(
            receipt,
            absence_receipt=absence,
            controller_receipt=controller,
        )
