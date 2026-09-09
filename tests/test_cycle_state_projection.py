import json
from pathlib import Path


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "cycle_state_projection"
    / "snapshot_coherence.json"
)


def test_snapshot_coherence_fixture_is_self_consistent():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert fixture["projection_version"] == "0.1"

    snapshot = fixture["snapshot"]
    receipts = fixture["receipts"]
    expected = fixture["expected"]

    assert len(receipts) == 2
    assert {
        receipt["receipt_hash"]
        for receipt in receipts
    } == set(snapshot["receipt_hashes"])

    assert all(receipt["valid"] is True for receipt in receipts)

    receipt_idx_identities = {
        receipt["idx_identity"]
        for receipt in receipts
    }

    assert snapshot["idx_identity"] in receipt_idx_identities
    assert len(receipt_idx_identities) > 1

    assert expected["state"] == "BLOCKED_INVARIANT"
    assert "IDX_IDENTITY_MISMATCH" in expected["reason_codes"]
    assert expected["state"] not in expected["must_not_return"]

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"
def test_permutation_invariance_fixture_preserves_projection_result():
    fixture = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "cycle_state_projection"
            / "permutation_invariance.json"
        ).read_text(encoding="utf-8")
    )

    assert fixture["projection_version"] == "0.1"
    assert fixture["ordering_rule"]["receipt_order_semantic"] is False

    snapshot = fixture["snapshot"]
    receipts = fixture["receipts"]
    permutations = fixture["permutations"]
    expected = fixture["expected"]

    known_hashes = {
        receipt["receipt_hash"]
        for receipt in receipts.values()
    }

    assert known_hashes == set(snapshot["receipt_hashes"])
    assert len(permutations) == 2

    for permutation in permutations:
        assert set(permutation) == known_hashes

    assert permutations[0] == list(reversed(permutations[1]))

    plan = receipts["dependency_recheck_plan"]
    certificate = receipts["completion_certificate"]

    assert plan["type"] == "dependency_recheck_plan"
    assert plan["plan_hash"] == plan["receipt_hash"]
    assert plan["recheck_required_count"] == 1
    assert any(
        result["status"] == "RECHECK_REQUIRED"
        for result in plan["results"]
    )

    assert certificate["type"] == "environment_completion_certificate"
    assert certificate["certificate_id"] == certificate["receipt_hash"]
    assert certificate["status"] == "COMPLETE_ELIGIBLE"

    assert expected["state"] == "RECHECK_REQUIRED"
    assert "DEPENDENCY_RECHECK_REQUIRED" in expected["reason_codes"]

    assert expected["source_receipt_identities"] == [
        {
            "type": "dependency_recheck_plan",
            "hash": plan["receipt_hash"],
        }
    ]

    assert expected["scope"]["frame_identity"] == certificate["frame_identity"]
    assert expected["scope"]["episode_identity"] == certificate["episode_id"]
    assert expected["scope"]["environment_id"] == certificate["environment_id"]

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"
def test_historical_completion_reopen_fixture_preserves_history_and_changes_currentness():
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "historical_completion_reopen.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["projection_version"] == "0.1"

    snapshot = fixture["snapshot"]
    receipts = fixture["receipts"]
    expected = fixture["expected"]

    completion = receipts["historical_completion"]
    reopen = receipts["later_reopen"]

    assert completion["type"] == "environment_completion_certificate"
    assert completion["certificate_id"] == completion["receipt_hash"]
    assert completion["status"] == "COMPLETE_ELIGIBLE"

    assert reopen["type"] == "environment_episode_reopen_receipt"
    assert reopen["receipt_id"] == reopen["receipt_hash"]
    assert reopen["relation"] == "reopens"

    assert reopen["parent_certificate_id"] == completion["certificate_id"]
    assert reopen["prior_episode_id"] == completion["episode_id"]
    assert reopen["reopened_episode_id"] != completion["episode_id"]
    assert reopen["environment_id"] == completion["environment_id"]

    assert set(snapshot["receipt_hashes"]) == {
        completion["receipt_hash"],
        reopen["receipt_hash"],
    }

    assert set(snapshot["episode_identities"]) == {
        completion["episode_id"],
        reopen["reopened_episode_id"],
    }

    historical = expected["historical_status"]

    assert historical["episode_id"] == completion["episode_id"]
    assert historical["state"] == "COMPLETE_ELIGIBLE"
    assert historical["preserved"] is True

    assert expected["current_episode_id"] == reopen["reopened_episode_id"]
    assert "LATER_EPISODE_REOPENED" in expected["reason_codes"]
    assert "COMPLETE_ELIGIBLE" in expected["must_not_return_current_state"]

    assert expected["source_receipt_identities"] == [
        {
            "type": "environment_completion_certificate",
            "hash": completion["receipt_hash"],
        },
        {
            "type": "environment_episode_reopen_receipt",
            "hash": reopen["receipt_hash"],
        },
    ]

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"
def test_stale_dependency_fixture_requires_recheck_without_erasing_history() -> None:
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "stale_dependency.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert fixture["projection_version"] == "0.1"

    changed = fixture["receipts"]["changed_support"]
    historical = fixture["receipts"]["historical_result"]
    plan = fixture["receipts"]["dependency_plan"]
    expected = fixture["expected"]

    assert changed["receipt_hash"] in historical["evidence_receipt_hashes"]
    assert historical["status"] == "COMPLETE_ELIGIBLE"

    assert plan["type"] == "dependency_recheck_plan"
    assert plan["changed_dependency_hashes"] == [changed["receipt_hash"]]
    assert plan["unobserved_changed_hashes"] == []

    assert plan["results"] == [
        {
            "receipt_hash": historical["receipt_hash"],
            "status": "RECHECK_REQUIRED",
            "trigger_paths": [
                [
                    changed["receipt_hash"],
                    historical["receipt_hash"],
                ]
            ],
        }
    ]
    assert plan["recheck_required_count"] == 1

    assert expected["state"] == "RECHECK_REQUIRED"
    assert "DEPENDENCY_RECHECK_REQUIRED" in expected["reason_codes"]

    assert expected["historical_status"] == {
        "receipt_hash": historical["receipt_hash"],
        "state": "COMPLETE_ELIGIBLE",
        "preserved": True,
    }

    assert expected["changed_dependency_hashes"] == [
        changed["receipt_hash"]
    ]
    assert expected["trigger_paths"] == [
        [
            changed["receipt_hash"],
            historical["receipt_hash"],
        ]
    ]

    snapshot_hashes = set(fixture["snapshot"]["receipt_hashes"])
    assert snapshot_hashes == {
        changed["receipt_hash"],
        historical["receipt_hash"],
        plan["receipt_hash"],
    }

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"
def test_idx_dominance_blocks_lower_priority_projection_states() -> None:
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "idx_dominance.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert fixture["projection_version"] == "0.1"

    gate = fixture["idx_gate"]
    receipts = fixture["receipts"]
    expected = fixture["expected"]

    completion = receipts["completion"]
    bound_check = receipts["bound_check"]

    assert gate["required"] is True
    assert gate["status"] == "ABORT"
    assert gate["code"] == "ACTIVE_HASH_MISMATCH"
    assert gate["expected"] != gate["observed"]
    assert gate["fused"] is False

    assert completion["status"] == "COMPLETE_ELIGIBLE"
    assert completion["evaluation_eligible"] is True

    assert bound_check["status"] == "DECLARED_VERIFIER_BOUND"
    assert bound_check["verifier_available"] is True

    assert expected["state"] == "BLOCKED_INVARIANT"
    assert expected["reason_codes"] == [
        "IDX_ACTIVE_HASH_MISMATCH"
    ]

    assert expected["source_gate_result"] == {
        "status": "ABORT",
        "code": "ACTIVE_HASH_MISMATCH",
        "expected": gate["expected"],
        "observed": gate["observed"],
    }

    assert "BOUND_CHECK_AVAILABLE" in expected["must_not_return"]
    assert "COMPLETE_ELIGIBLE" in expected["must_not_return"]
    assert expected["state"] not in expected["must_not_return"]

    snapshot_hashes = set(fixture["snapshot"]["receipt_hashes"])
    assert snapshot_hashes == {
        completion["receipt_hash"],
        bound_check["receipt_hash"],
    }

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"
def test_no_invention_requires_declared_resolution_condition() -> None:
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "no_invention.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert fixture["projection_version"] == "0.1"

    record = fixture["unresolved_record"]
    organizer = fixture["organizer_result"]
    expected = fixture["expected"]

    assert record["status"] == "open"
    assert record["resolution_conditions"] == []
    assert record["residual_uncertainty"] == [
        "Need a declared method"
    ]

    assert organizer["type"] == "holo_next_check_organizer"
    assert organizer["version"] == 1
    assert organizer["candidate_checks"] == []
    assert organizer["conditions_invented"] is False

    unresolved = organizer["unresolved_without_declared_check"]
    assert len(unresolved) == 1
    assert unresolved[0]["entry_hash"] == record["entry_hash"]
    assert unresolved[0]["routing_status"] == (
        "RESOLUTION_CONDITION_REQUIRED"
    )
    assert unresolved[0]["condition_invented"] is False

    assert expected["state"] == "RESOLUTION_CONDITION_REQUIRED"
    assert expected["reason_codes"] == [
        "RESOLUTION_CONDITION_REQUIRED"
    ]
    assert expected["candidate_checks"] == []
    assert expected["conditions_invented"] is False

    assert "DECLARED_CHECK_UNBOUND" in expected["must_not_return"]
    assert "BOUND_CHECK_AVAILABLE" in expected["must_not_return"]
    assert "COMPLETE_ELIGIBLE" in expected["must_not_return"]

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"
def test_verifier_non_inference_requires_explicit_verifier_identity() -> None:
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "verifier_non_inference.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert fixture["projection_version"] == "0.1"

    declared = fixture["declared_check"]
    binding = fixture["binding_result"]
    known = fixture["known_verifier_that_must_not_be_inferred"]
    expected = fixture["expected"]

    assert declared["condition"] == "Run replay verifier"
    assert declared["routing_status"] == "DECLARED_CHECK_AVAILABLE"
    assert declared["invented"] is False

    assert known["available"] is True

    assert binding["bound"] is False
    assert binding["binding_status"] == "VERIFIER_ID_REQUIRED"
    assert binding["verifier_id"] is None
    assert binding["verifier_inferred"] is False

    assert expected["state"] == "DECLARED_CHECK_UNBOUND"
    assert expected["reason_codes"] == [
        "VERIFIER_ID_REQUIRED"
    ]
    assert expected["bound"] is False
    assert expected["verifier_inferred"] is False

    assert expected["must_not_infer_verifier_id"] == known["verifier_id"]
    assert "BOUND_CHECK_AVAILABLE" in expected["must_not_return"]
    assert "COMPLETE_ELIGIBLE" in expected["must_not_return"]

    snapshot_hashes = set(fixture["snapshot"]["receipt_hashes"])
    assert snapshot_hashes == {
        declared["receipt_hash"],
        binding["receipt_hash"],
    }

    assert binding["truth_claimed"] is False
    assert binding["accepted"] is False
    assert binding["execution_authorized"] is False
    assert binding["write_authority"] == "NONE"

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"
def test_binding_is_not_verification_or_authority() -> None:
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "binding_not_verification.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert fixture["projection_version"] == "0.1"

    declared = fixture["declared_check"]
    binding = fixture["binding_result"]
    expected = fixture["expected"]

    assert declared["routing_status"] == "DECLARED_CHECK_AVAILABLE"
    assert declared["invented"] is False

    assert binding["type"] == "declared_check_verifier_binding"
    assert binding["version"] == 1
    assert binding["verifier_id"] == "verifier:replay:v1"
    assert binding["bound"] is True
    assert binding["binding_status"] == "DECLARED_VERIFIER_BOUND"
    assert binding["verifier_available"] is True
    assert binding["verifier_inferred"] is False

    assert expected["state"] == "BOUND_CHECK_AVAILABLE"
    assert expected["reason_codes"] == [
        "DECLARED_VERIFIER_BOUND"
    ]
    assert expected["bound"] is True
    assert expected["verifier_available"] is True
    assert expected["verifier_inferred"] is False

    forbidden_states = {
        "PASS",
        "VERIFIED",
        "TRUE",
        "ACCEPTED",
        "COMPLETE_ELIGIBLE",
    }
    assert set(expected["must_not_return"]) == forbidden_states
    assert expected["state"] not in forbidden_states

    snapshot_hashes = set(fixture["snapshot"]["receipt_hashes"])
    assert snapshot_hashes == {
        declared["receipt_hash"],
        binding["receipt_hash"],
    }

    assert binding["truth_claimed"] is False
    assert binding["accepted"] is False
    assert binding["execution_authorized"] is False
    assert binding["write_authority"] == "NONE"

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"
def test_frame_conflict_fails_closed_without_collapsing_results() -> None:
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "frame_conflict.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert fixture["projection_version"] == "0.1"

    evaluations = fixture["frame_relative_evaluations"]
    expected = fixture["expected"]

    assert len(evaluations) == 2

    results_by_frame = {
        evaluation["frame_identity"]: evaluation["result"]
        for evaluation in evaluations
    }

    assert results_by_frame == {
        "frame:accuracy:v1": "PASS",
        "frame:latency:v1": "FAIL",
    }

    assert len({
        evaluation["frame_hash"]
        for evaluation in evaluations
    }) == 2

    assert expected["state"] == "BLOCKED_INVARIANT"
    assert expected["reason_codes"] == [
        "FRAME_IDENTITY_CONFLICT"
    ]
    assert expected["must_preserve_frame_relative_results"] == results_by_frame
    assert expected["must_not_collapse_frames"] is True

    forbidden_states = {
        "PASS",
        "FAIL",
        "BOUND_CHECK_AVAILABLE",
        "COMPLETE_ELIGIBLE",
        "CURRENTLY_RESTRAINED",
    }
    assert set(expected["must_not_return"]) == forbidden_states
    assert expected["state"] not in forbidden_states

    snapshot_hashes = set(fixture["snapshot"]["receipt_hashes"])
    evaluation_hashes = {
        evaluation["receipt_hash"]
        for evaluation in evaluations
    }
    assert snapshot_hashes == evaluation_hashes

    assert set(fixture["snapshot"]["frame_identities"]) == set(results_by_frame)

    for evaluation in evaluations:
        assert evaluation["truth_claimed"] is False
        assert evaluation["accepted"] is False
        assert evaluation["state_change_authorized"] is False
        assert evaluation["write_authority"] == "NONE"
        assert evaluation["execution_authority"] == "NONE"

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"
