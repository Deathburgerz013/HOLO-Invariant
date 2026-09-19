import pytest

from holosim.longitudinal_compounding_experiment import (
    CONDITION_STRUCTURE_REMOVED,
    CONDITION_VERIFIED_ORDERED_HISTORY,
    CONDITION_VERIFIED_STRUCTURE_RESTORED,
    LongitudinalCompoundingExperimentError,
    build_condition_receipt,
    verify_restoration,
    verify_same_information,
)


INFORMATION = {
    "claims": [
        {"id": "claim-1", "value": "original"},
        {"id": "claim-2", "value": "corrected"},
    ]
}

VERIFIED_RELATIONS = {
    "supersedes": [["claim-2", "claim-1"]],
}


def _receipt(condition_id, relations):
    return build_condition_receipt(
        task_id="same-information-contract",
        condition_id=condition_id,
        informational_content=INFORMATION,
        semantic_relations=relations,
    )


def test_conditions_can_change_relations_without_changing_information():
    verified = _receipt(
        CONDITION_VERIFIED_ORDERED_HISTORY,
        VERIFIED_RELATIONS,
    )
    removed = _receipt(
        CONDITION_STRUCTURE_REMOVED,
        {},
    )

    assert verify_same_information(verified, removed) is True
    assert (
        verified["informational_identity"]
        == removed["informational_identity"]
    )
    assert (
        verified["semantic_relations_identity"]
        != removed["semantic_relations_identity"]
    )


def test_information_change_fails_closed():
    verified = _receipt(
        CONDITION_VERIFIED_ORDERED_HISTORY,
        VERIFIED_RELATIONS,
    )

    changed_information = {
        "claims": [
            {"id": "claim-1", "value": "original"},
        ]
    }

    invalid = build_condition_receipt(
        task_id="same-information-contract",
        condition_id=CONDITION_STRUCTURE_REMOVED,
        informational_content=changed_information,
        semantic_relations={},
    )

    with pytest.raises(
        LongitudinalCompoundingExperimentError,
        match="informational identity changed across conditions",
    ):
        verify_same_information(verified, invalid)


def test_restoration_requires_exact_verified_relations():
    verified = _receipt(
        CONDITION_VERIFIED_ORDERED_HISTORY,
        VERIFIED_RELATIONS,
    )
    restored = _receipt(
        CONDITION_VERIFIED_STRUCTURE_RESTORED,
        VERIFIED_RELATIONS,
    )

    assert verify_restoration(
        verified_receipt=verified,
        restored_receipt=restored,
    ) is True


def test_inexact_restoration_fails_closed():
    verified = _receipt(
        CONDITION_VERIFIED_ORDERED_HISTORY,
        VERIFIED_RELATIONS,
    )
    restored = _receipt(
        CONDITION_VERIFIED_STRUCTURE_RESTORED,
        {"supersedes": [["claim-1", "claim-2"]]},
    )

    with pytest.raises(
        LongitudinalCompoundingExperimentError,
        match="restored semantic structure does not match verified structure",
    ):
        verify_restoration(
            verified_receipt=verified,
            restored_receipt=restored,
        )
def test_structure_removed_preserves_relation_slots_but_removes_bindings():
    relations = {
        "current": "claim-2",
        "supersedes": [["claim-2", "claim-1"]],
    }

    from holosim.longitudinal_compounding_experiment import (
        remove_semantic_relations,
    )

    removed = remove_semantic_relations(relations)

    assert set(removed) == set(relations)
    assert all(value is None for value in removed.values())


def test_structure_permutation_is_deterministic_and_preserves_values():
    relations = {
        "current": "claim-2",
        "prior": "claim-1",
        "supersedes": [["claim-2", "claim-1"]],
    }

    from holosim.longitudinal_compounding_experiment import (
        permute_semantic_relations,
    )

    first = permute_semantic_relations(relations)
    second = permute_semantic_relations(relations)

    assert first == second
    assert first != relations
    assert sorted(map(repr, first.values())) == sorted(
        map(repr, relations.values())
    )


def test_semantic_permutation_requires_multiple_relations():
    from holosim.longitudinal_compounding_experiment import (
        permute_semantic_relations,
    )

    with pytest.raises(
        LongitudinalCompoundingExperimentError,
        match="semantic permutation requires at least two relations",
    ):
        permute_semantic_relations({"current": "claim-2"})
def test_nonsemantic_order_permutation_is_control_not_ablation():
    from holosim.longitudinal_compounding_experiment import (
        verify_nonsemantic_permutation_control,
    )

    relations = {
        "dependency": ["support-1", "result-1"],
    }

    assert verify_nonsemantic_permutation_control(
        first_order=["receipt-a", "receipt-b"],
        second_order=["receipt-b", "receipt-a"],
        semantic_relations=relations,
    ) is True


def test_nonsemantic_permutation_cannot_change_information():
    from holosim.longitudinal_compounding_experiment import (
        verify_nonsemantic_permutation_control,
    )

    with pytest.raises(
        LongitudinalCompoundingExperimentError,
        match="nonsemantic permutation changed information",
    ):
        verify_nonsemantic_permutation_control(
            first_order=["receipt-a", "receipt-b"],
            second_order=["receipt-a", "receipt-c"],
            semantic_relations={
                "dependency": ["support-1", "result-1"],
            },
        )
def test_frozen_permutation_control_rejects_order_as_semantic_ablation():
    import json
    from pathlib import Path

    from holosim.longitudinal_compounding_experiment import (
        verify_nonsemantic_permutation_control,
    )

    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "permutation_invariance.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert fixture["ordering_rule"]["receipt_order_semantic"] is False

    first_order, second_order = fixture["permutations"]

    plan = fixture["receipts"]["dependency_recheck_plan"]
    certificate = fixture["receipts"]["completion_certificate"]

    semantic_relations = {
        "dependency_trigger_paths": plan["results"][0]["trigger_paths"],
        "dependency_result_status": plan["results"][0]["status"],
        "current_completion_status": certificate["status"],
        "expected_projection_state": fixture["expected"]["state"],
    }

    assert verify_nonsemantic_permutation_control(
        first_order=first_order,
        second_order=second_order,
        semantic_relations=semantic_relations,
    ) is True

    assert fixture["expected"]["state"] == "RECHECK_REQUIRED"
    assert plan["results"][0]["status"] == "RECHECK_REQUIRED"
def _historical_reopen_fixture():
    import json
    from pathlib import Path

    path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "historical_completion_reopen.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _historical_reopen_relations(fixture):
    reopen = fixture["receipts"]["later_reopen"]

    return {
        "relation": reopen["relation"],
        "parent_certificate_id": reopen["parent_certificate_id"],
        "prior_episode_id": reopen["prior_episode_id"],
        "reopened_episode_id": reopen["reopened_episode_id"],
    }


def test_historical_reopen_verified_structure_reproduces_frozen_target():
    from holosim.longitudinal_compounding_experiment import (
        evaluate_historical_reopen_relations,
    )

    fixture = _historical_reopen_fixture()

    result = evaluate_historical_reopen_relations(
        informational_content={
            "snapshot": fixture["snapshot"],
            "receipts": fixture["receipts"],
        },
        semantic_relations=_historical_reopen_relations(fixture),
    )

    expected = fixture["expected"]

    assert result["relation_bound"] is True
    assert result["historical_status"] == expected["historical_status"]
    assert result["current_episode_id"] == expected["current_episode_id"]
    assert result["reason_codes"] == expected["reason_codes"]
    assert result["current_state"] not in expected[
        "must_not_return_current_state"
    ]


def test_historical_reopen_removed_structure_loses_currentness_not_information():
    from holosim.longitudinal_compounding_experiment import (
        evaluate_historical_reopen_relations,
        remove_semantic_relations,
    )

    fixture = _historical_reopen_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "receipts": fixture["receipts"],
    }
    relations = _historical_reopen_relations(fixture)

    verified = evaluate_historical_reopen_relations(
        informational_content=information,
        semantic_relations=relations,
    )
    removed = evaluate_historical_reopen_relations(
        informational_content=information,
        semantic_relations=remove_semantic_relations(relations),
    )

    assert (
        verified["informational_identity"]
        == removed["informational_identity"]
    )

    assert removed["relation_bound"] is False
    assert removed["historical_status"]["preserved"] is True

    assert removed["current_episode_id"] != fixture["expected"][
        "current_episode_id"
    ]
    assert removed["current_state"] in fixture["expected"][
        "must_not_return_current_state"
    ]
def test_historical_reopen_permuted_structure_loses_currentness_not_information():
    from holosim.longitudinal_compounding_experiment import (
        evaluate_historical_reopen_relations,
        permute_semantic_relations,
    )

    fixture = _historical_reopen_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "receipts": fixture["receipts"],
    }
    relations = _historical_reopen_relations(fixture)

    verified = evaluate_historical_reopen_relations(
        informational_content=information,
        semantic_relations=relations,
    )
    permuted = evaluate_historical_reopen_relations(
        informational_content=information,
        semantic_relations=permute_semantic_relations(relations),
    )

    assert (
        verified["informational_identity"]
        == permuted["informational_identity"]
    )
    assert permuted["relation_bound"] is False
    assert permuted["historical_status"]["preserved"] is True
    assert permuted["current_episode_id"] != fixture["expected"][
        "current_episode_id"
    ]
    assert permuted["current_state"] in fixture["expected"][
        "must_not_return_current_state"
    ]


def test_historical_reopen_restoration_recovers_frozen_target():
    from holosim.longitudinal_compounding_experiment import (
        CONDITION_VERIFIED_ORDERED_HISTORY,
        CONDITION_VERIFIED_STRUCTURE_RESTORED,
        build_condition_receipt,
        evaluate_historical_reopen_relations,
        verify_restoration,
    )

    fixture = _historical_reopen_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "receipts": fixture["receipts"],
    }
    relations = _historical_reopen_relations(fixture)

    verified_receipt = build_condition_receipt(
        task_id=fixture["fixture_id"],
        condition_id=CONDITION_VERIFIED_ORDERED_HISTORY,
        informational_content=information,
        semantic_relations=relations,
    )
    restored_receipt = build_condition_receipt(
        task_id=fixture["fixture_id"],
        condition_id=CONDITION_VERIFIED_STRUCTURE_RESTORED,
        informational_content=information,
        semantic_relations=relations,
    )

    assert verify_restoration(
        verified_receipt=verified_receipt,
        restored_receipt=restored_receipt,
    ) is True

    restored = evaluate_historical_reopen_relations(
        informational_content=restored_receipt["informational_content"],
        semantic_relations=restored_receipt["semantic_relations"],
    )

    expected = fixture["expected"]

    assert restored["relation_bound"] is True
    assert restored["historical_status"] == expected["historical_status"]
    assert restored["current_episode_id"] == expected["current_episode_id"]
    assert restored["reason_codes"] == expected["reason_codes"]
    assert restored["current_state"] not in expected[
        "must_not_return_current_state"
    ]
def _stale_dependency_fixture():
    import json
    from pathlib import Path

    path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "stale_dependency.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _stale_dependency_relations(fixture):
    changed = fixture["receipts"]["changed_support"]
    historical = fixture["receipts"]["historical_result"]
    plan_result = fixture["receipts"]["dependency_plan"]["results"][0]

    return {
        "changed_dependency_hash": changed["receipt_hash"],
        "historical_result_hash": historical["receipt_hash"],
        "evidence_dependency_hash": historical[
            "evidence_receipt_hashes"
        ][0],
        "recheck_result_hash": plan_result["receipt_hash"],
        "recheck_status": plan_result["status"],
        "trigger_path": plan_result["trigger_paths"][0],
    }


def test_stale_dependency_verified_structure_reproduces_frozen_target():
    from holosim.longitudinal_compounding_experiment import (
        evaluate_stale_dependency_relations,
    )

    fixture = _stale_dependency_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "receipts": fixture["receipts"],
    }

    result = evaluate_stale_dependency_relations(
        informational_content=information,
        semantic_relations=_stale_dependency_relations(fixture),
    )
    expected = fixture["expected"]

    assert result["dependency_bound"] is True
    assert result["state"] == expected["state"]
    assert result["reason_codes"] == expected["reason_codes"]
    assert result["historical_status"] == expected["historical_status"]
    assert (
        result["changed_dependency_hashes"]
        == expected["changed_dependency_hashes"]
    )
    assert result["trigger_paths"] == expected["trigger_paths"]


def test_stale_dependency_removed_structure_loses_recheck_not_information():
    from holosim.longitudinal_compounding_experiment import (
        evaluate_stale_dependency_relations,
        remove_semantic_relations,
    )

    fixture = _stale_dependency_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "receipts": fixture["receipts"],
    }
    relations = _stale_dependency_relations(fixture)

    verified = evaluate_stale_dependency_relations(
        informational_content=information,
        semantic_relations=relations,
    )
    removed = evaluate_stale_dependency_relations(
        informational_content=information,
        semantic_relations=remove_semantic_relations(relations),
    )

    assert (
        verified["informational_identity"]
        == removed["informational_identity"]
    )
    assert removed["dependency_bound"] is False
    assert removed["historical_status"]["preserved"] is True
    assert removed["state"] == "COMPLETE_ELIGIBLE"
    assert removed["state"] != fixture["expected"]["state"]
    assert removed["trigger_paths"] == []


def test_stale_dependency_permuted_structure_loses_recheck_not_information():
    from holosim.longitudinal_compounding_experiment import (
        evaluate_stale_dependency_relations,
        permute_semantic_relations,
    )

    fixture = _stale_dependency_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "receipts": fixture["receipts"],
    }
    relations = _stale_dependency_relations(fixture)

    verified = evaluate_stale_dependency_relations(
        informational_content=information,
        semantic_relations=relations,
    )
    permuted = evaluate_stale_dependency_relations(
        informational_content=information,
        semantic_relations=permute_semantic_relations(relations),
    )

    assert (
        verified["informational_identity"]
        == permuted["informational_identity"]
    )
    assert permuted["dependency_bound"] is False
    assert permuted["historical_status"]["preserved"] is True
    assert permuted["state"] != fixture["expected"]["state"]


def test_stale_dependency_restoration_recovers_frozen_target():
    from holosim.longitudinal_compounding_experiment import (
        CONDITION_VERIFIED_ORDERED_HISTORY,
        CONDITION_VERIFIED_STRUCTURE_RESTORED,
        build_condition_receipt,
        evaluate_stale_dependency_relations,
        verify_restoration,
    )

    fixture = _stale_dependency_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "receipts": fixture["receipts"],
    }
    relations = _stale_dependency_relations(fixture)

    verified_receipt = build_condition_receipt(
        task_id=fixture["fixture_id"],
        condition_id=CONDITION_VERIFIED_ORDERED_HISTORY,
        informational_content=information,
        semantic_relations=relations,
    )
    restored_receipt = build_condition_receipt(
        task_id=fixture["fixture_id"],
        condition_id=CONDITION_VERIFIED_STRUCTURE_RESTORED,
        informational_content=information,
        semantic_relations=relations,
    )

    assert verify_restoration(
        verified_receipt=verified_receipt,
        restored_receipt=restored_receipt,
    ) is True

    restored = evaluate_stale_dependency_relations(
        informational_content=restored_receipt["informational_content"],
        semantic_relations=restored_receipt["semantic_relations"],
    )
    expected = fixture["expected"]

    assert restored["dependency_bound"] is True
    assert restored["state"] == expected["state"]
    assert restored["historical_status"] == expected["historical_status"]
    assert restored["trigger_paths"] == expected["trigger_paths"]
def _idx_dominance_fixture():
    import json
    from pathlib import Path

    path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "idx_dominance.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _idx_dominance_relations(fixture):
    gate = fixture["idx_gate"]
    completion = fixture["receipts"]["completion"]
    bound_check = fixture["receipts"]["bound_check"]

    return {
        "gate_required": gate["required"],
        "gate_status": gate["status"],
        "gate_code": gate["code"],
        "dominates_completion_status": completion["status"],
        "dominates_bound_check_status": bound_check["status"],
    }


def test_idx_dominance_verified_structure_reproduces_frozen_target():
    from holosim.longitudinal_compounding_experiment import (
        evaluate_idx_dominance_relations,
    )

    fixture = _idx_dominance_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "idx_gate": fixture["idx_gate"],
        "receipts": fixture["receipts"],
    }

    result = evaluate_idx_dominance_relations(
        informational_content=information,
        semantic_relations=_idx_dominance_relations(fixture),
    )
    expected = fixture["expected"]

    assert result["dominance_bound"] is True
    assert result["state"] == expected["state"]
    assert result["reason_codes"] == expected["reason_codes"]
    assert result["source_gate_result"] == expected["source_gate_result"]


def test_idx_dominance_removed_structure_loses_precedence_not_information():
    from holosim.longitudinal_compounding_experiment import (
        evaluate_idx_dominance_relations,
        remove_semantic_relations,
    )

    fixture = _idx_dominance_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "idx_gate": fixture["idx_gate"],
        "receipts": fixture["receipts"],
    }
    relations = _idx_dominance_relations(fixture)

    verified = evaluate_idx_dominance_relations(
        informational_content=information,
        semantic_relations=relations,
    )
    removed = evaluate_idx_dominance_relations(
        informational_content=information,
        semantic_relations=remove_semantic_relations(relations),
    )

    assert (
        verified["informational_identity"]
        == removed["informational_identity"]
    )
    assert removed["dominance_bound"] is False
    assert removed["state"] == "COMPLETE_ELIGIBLE"
    assert removed["state"] in fixture["expected"]["must_not_return"]
    assert removed["source_gate_result"] == fixture["expected"][
        "source_gate_result"
    ]


def test_idx_dominance_permuted_structure_loses_precedence_not_information():
    from holosim.longitudinal_compounding_experiment import (
        evaluate_idx_dominance_relations,
        permute_semantic_relations,
    )

    fixture = _idx_dominance_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "idx_gate": fixture["idx_gate"],
        "receipts": fixture["receipts"],
    }
    relations = _idx_dominance_relations(fixture)

    verified = evaluate_idx_dominance_relations(
        informational_content=information,
        semantic_relations=relations,
    )
    permuted = evaluate_idx_dominance_relations(
        informational_content=information,
        semantic_relations=permute_semantic_relations(relations),
    )

    assert (
        verified["informational_identity"]
        == permuted["informational_identity"]
    )
    assert permuted["dominance_bound"] is False
    assert permuted["state"] != fixture["expected"]["state"]


def test_idx_dominance_restoration_recovers_frozen_target():
    from holosim.longitudinal_compounding_experiment import (
        CONDITION_VERIFIED_ORDERED_HISTORY,
        CONDITION_VERIFIED_STRUCTURE_RESTORED,
        build_condition_receipt,
        evaluate_idx_dominance_relations,
        verify_restoration,
    )

    fixture = _idx_dominance_fixture()
    information = {
        "snapshot": fixture["snapshot"],
        "idx_gate": fixture["idx_gate"],
        "receipts": fixture["receipts"],
    }
    relations = _idx_dominance_relations(fixture)

    verified_receipt = build_condition_receipt(
        task_id=fixture["fixture_id"],
        condition_id=CONDITION_VERIFIED_ORDERED_HISTORY,
        informational_content=information,
        semantic_relations=relations,
    )
    restored_receipt = build_condition_receipt(
        task_id=fixture["fixture_id"],
        condition_id=CONDITION_VERIFIED_STRUCTURE_RESTORED,
        informational_content=information,
        semantic_relations=relations,
    )

    assert verify_restoration(
        verified_receipt=verified_receipt,
        restored_receipt=restored_receipt,
    ) is True

    restored = evaluate_idx_dominance_relations(
        informational_content=restored_receipt["informational_content"],
        semantic_relations=restored_receipt["semantic_relations"],
    )
    expected = fixture["expected"]

    assert restored["dominance_bound"] is True
    assert restored["state"] == expected["state"]
    assert restored["reason_codes"] == expected["reason_codes"]
    assert restored["source_gate_result"] == expected["source_gate_result"]
def test_no_invention_is_preserved_and_structural_ablation_is_non_applicable():
    import json
    from pathlib import Path

    from holosim.longitudinal_compounding_experiment import (
        evaluate_no_invention_applicability,
    )

    path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "no_invention.json"
    )
    fixture = json.loads(path.read_text(encoding="utf-8"))

    information = {
        "snapshot": fixture["snapshot"],
        "unresolved_record": fixture["unresolved_record"],
        "organizer_result": fixture["organizer_result"],
    }

    result = evaluate_no_invention_applicability(
        informational_content=information,
    )
    expected = fixture["expected"]

    assert result["state"] == expected["state"]
    assert result["reason_codes"] == expected["reason_codes"]
    assert result["candidate_checks"] == expected["candidate_checks"]
    assert (
        result["conditions_invented"]
        == expected["conditions_invented"]
    )

    assert result["longitudinal_structure_present"] is False
    assert result["structure_removed_applicable"] is False
    assert result["structure_permuted_applicable"] is False
    assert (
        result["non_applicable_reason"]
        == "NO_LONGITUDINAL_SEMANTIC_RELATION"
    )
def test_byte_repeat_determinism_is_preserved_and_ablation_is_non_applicable():
    import json
    from pathlib import Path

    from holosim.longitudinal_compounding_experiment import (
        evaluate_repeat_determinism,
    )

    path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "byte_repeat_determinism.json"
    )
    fixture = json.loads(path.read_text(encoding="utf-8"))

    information = {
        "projection_version": fixture["projection_version"],
        "canonical_snapshot": fixture["canonical_snapshot"],
        "projection": fixture["projection"],
    }

    result = evaluate_repeat_determinism(
        informational_content=information,
        repeat_count=fixture["expected"]["repeat_count"],
    )
    expected = fixture["expected"]

    assert result["repeat_count"] == expected["repeat_count"]
    assert (
        result["canonical_bytes_identical"]
        == expected["canonical_bytes_identical"]
    )
    assert (
        result["projection_identity_identical"]
        == expected["projection_identity_identical"]
    )
    assert result["runtime_reducer_added"] is False

    assert result["longitudinal_structure_present"] is False
    assert result["structure_removed_applicable"] is False
    assert result["structure_permuted_applicable"] is False
    assert (
        result["non_applicable_reason"]
        == "NO_LONGITUDINAL_SEMANTIC_RELATION"
    )
def _continuity_fixture():
    import json
    from pathlib import Path

    root = Path(__file__).parent.parent

    fixture = json.loads(
        (
            root
            / "benchmarks"
            / "continuity-v1.fixture.json"
        ).read_text(encoding="utf-8")
    )
    reference = json.loads(
        (
            root
            / "benchmarks"
            / "results"
            / "holo-reference.result.json"
        ).read_text(encoding="utf-8")
    )

    return fixture, reference


def _continuity_information_and_relations(fixture):
    claim_ids = (
        list(fixture["latest_justified_claim_ids"])
        + list(fixture["superseded_claim_ids"])
        + list(fixture["uncertainty_claim_ids"])
    )

    information = {
        "claim_ids": claim_ids,
        "lineage_edges": fixture["required_lineage_edges"],
    }

    relations = {
        "latest_claim_id": fixture["latest_justified_claim_ids"][0],
        "superseded_claim_id": fixture["superseded_claim_ids"][0],
        "uncertainty_claim_id": fixture["uncertainty_claim_ids"][0],
        "lineage_edge": fixture["required_lineage_edges"][0],
        "stale_continuation_decision": "BLOCK",
    }

    return information, relations


def test_continuity_verified_structure_reproduces_preexisting_reference_metrics():
    from holosim.continuity_baseline_benchmark import (
        score_continuity_condition,
    )
    from holosim.longitudinal_compounding_experiment import (
        derive_continuity_condition_output,
    )

    fixture, reference = _continuity_fixture()
    information, relations = _continuity_information_and_relations(
        fixture
    )

    output = derive_continuity_condition_output(
        informational_content=information,
        semantic_relations=relations,
    )

    scored = score_continuity_condition(
        fixture=fixture,
        condition_id="A-VERIFIED_ORDERED_HISTORY",
        recovered_claim_ids=output["recovered_claim_ids"],
        claimed_current_claim_ids=output["claimed_current_claim_ids"],
        preserved_uncertainty_claim_ids=output[
            "preserved_uncertainty_claim_ids"
        ],
        reconstructed_lineage_edges=output[
            "reconstructed_lineage_edges"
        ],
        stale_continuation_decision=output[
            "stale_continuation_decision"
        ],
    )

    assert scored["latest_justified_recovered"] == reference[
        "latest_justified_recovered"
    ]
    assert scored["superseded_resurrected_as_current"] == reference[
        "superseded_resurrected_as_current"
    ]
    assert scored["uncertainty_preserved"] == reference[
        "uncertainty_preserved"
    ]
    assert scored["lineage_edges_recovered"] == reference[
        "lineage_edges_recovered"
    ]
    assert scored["stale_continuation_decision"] == reference[
        "stale_continuation_decision"
    ]
    assert scored["metrics"] == reference["metrics"]


def test_continuity_removed_structure_loses_scored_capacity_not_information():
    from holosim.continuity_baseline_benchmark import (
        score_continuity_condition,
    )
    from holosim.longitudinal_compounding_experiment import (
        derive_continuity_condition_output,
        informational_identity,
        remove_semantic_relations,
    )

    fixture, _ = _continuity_fixture()
    information, relations = _continuity_information_and_relations(
        fixture
    )

    verified = derive_continuity_condition_output(
        informational_content=information,
        semantic_relations=relations,
    )
    removed = derive_continuity_condition_output(
        informational_content=information,
        semantic_relations=remove_semantic_relations(relations),
    )

    assert informational_identity(information) == informational_identity(
        information
    )

    verified_score = score_continuity_condition(
        fixture=fixture,
        condition_id="A-VERIFIED_ORDERED_HISTORY",
        **{
            key: verified[key]
            for key in (
                "recovered_claim_ids",
                "claimed_current_claim_ids",
                "preserved_uncertainty_claim_ids",
                "reconstructed_lineage_edges",
                "stale_continuation_decision",
            )
        },
    )
    removed_score = score_continuity_condition(
        fixture=fixture,
        condition_id="B-STRUCTURE_REMOVED",
        **{
            key: removed[key]
            for key in (
                "recovered_claim_ids",
                "claimed_current_claim_ids",
                "preserved_uncertainty_claim_ids",
                "reconstructed_lineage_edges",
                "stale_continuation_decision",
            )
        },
    )

    assert verified_score["metrics"][
        "passes_bounded_continuity_fixture"
    ] is True
    assert removed_score["metrics"][
        "passes_bounded_continuity_fixture"
    ] is False

    assert removed_score["metrics"]["latest_justified_recall"] < 1.0
    assert removed_score["metrics"]["uncertainty_recall"] < 1.0
    assert removed_score["metrics"]["lineage_recall"] < 1.0
    assert removed_score["metrics"]["stale_continuation_blocked"] is False
def test_continuity_permuted_structure_loses_scored_capacity_not_information():
    from holosim.continuity_baseline_benchmark import (
        score_continuity_condition,
    )
    from holosim.longitudinal_compounding_experiment import (
        derive_continuity_condition_output,
        informational_identity,
        permute_semantic_relations,
    )

    fixture, _ = _continuity_fixture()
    information, relations = _continuity_information_and_relations(
        fixture
    )

    verified = derive_continuity_condition_output(
        informational_content=information,
        semantic_relations=relations,
    )
    permuted = derive_continuity_condition_output(
        informational_content=information,
        semantic_relations=permute_semantic_relations(relations),
    )

    verified_score = score_continuity_condition(
        fixture=fixture,
        condition_id="A-VERIFIED_ORDERED_HISTORY",
        **{
            key: verified[key]
            for key in (
                "recovered_claim_ids",
                "claimed_current_claim_ids",
                "preserved_uncertainty_claim_ids",
                "reconstructed_lineage_edges",
                "stale_continuation_decision",
            )
        },
    )
    permuted_score = score_continuity_condition(
        fixture=fixture,
        condition_id="C-STRUCTURE_PERMUTED",
        **{
            key: permuted[key]
            for key in (
                "recovered_claim_ids",
                "claimed_current_claim_ids",
                "preserved_uncertainty_claim_ids",
                "reconstructed_lineage_edges",
                "stale_continuation_decision",
            )
        },
    )

    assert informational_identity(information) == informational_identity(
        information
    )
    assert verified_score["metrics"][
        "passes_bounded_continuity_fixture"
    ] is True
    assert permuted_score["metrics"][
        "passes_bounded_continuity_fixture"
    ] is False


def test_continuity_restoration_recovers_preexisting_reference_metrics():
    from holosim.continuity_baseline_benchmark import (
        score_continuity_condition,
    )
    from holosim.longitudinal_compounding_experiment import (
        CONDITION_VERIFIED_ORDERED_HISTORY,
        CONDITION_VERIFIED_STRUCTURE_RESTORED,
        build_condition_receipt,
        derive_continuity_condition_output,
        verify_restoration,
    )

    fixture, reference = _continuity_fixture()
    information, relations = _continuity_information_and_relations(
        fixture
    )

    verified_receipt = build_condition_receipt(
        task_id=fixture["benchmark_id"],
        condition_id=CONDITION_VERIFIED_ORDERED_HISTORY,
        informational_content=information,
        semantic_relations=relations,
    )
    restored_receipt = build_condition_receipt(
        task_id=fixture["benchmark_id"],
        condition_id=CONDITION_VERIFIED_STRUCTURE_RESTORED,
        informational_content=information,
        semantic_relations=relations,
    )

    assert verify_restoration(
        verified_receipt=verified_receipt,
        restored_receipt=restored_receipt,
    ) is True

    restored = derive_continuity_condition_output(
        informational_content=restored_receipt[
            "informational_content"
        ],
        semantic_relations=restored_receipt[
            "semantic_relations"
        ],
    )

    scored = score_continuity_condition(
        fixture=fixture,
        condition_id="D-VERIFIED_STRUCTURE_RESTORED",
        **{
            key: restored[key]
            for key in (
                "recovered_claim_ids",
                "claimed_current_claim_ids",
                "preserved_uncertainty_claim_ids",
                "reconstructed_lineage_edges",
                "stale_continuation_decision",
            )
        },
    )

    assert scored["metrics"] == reference["metrics"]
    assert scored["latest_justified_recovered"] == reference[
        "latest_justified_recovered"
    ]
    assert scored["uncertainty_preserved"] == reference[
        "uncertainty_preserved"
    ]
    assert scored["lineage_edges_recovered"] == reference[
        "lineage_edges_recovered"
    ]
    assert scored["stale_continuation_decision"] == "BLOCK"