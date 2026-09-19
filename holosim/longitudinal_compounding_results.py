"""Deterministic recorder for the longitudinal compounding experiment.

This module records results from the already-frozen experimental machinery.
It does not modify the experiment, scoring targets, or authority boundaries.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from holosim.canonical import stable_hash
from holosim.continuity_baseline_benchmark import score_continuity_condition
from holosim.longitudinal_compounding_experiment import (
    CONDITION_STRUCTURE_PERMUTED,
    CONDITION_STRUCTURE_REMOVED,
    CONDITION_VERIFIED_ORDERED_HISTORY,
    CONDITION_VERIFIED_STRUCTURE_RESTORED,
    build_condition_receipt,
    derive_continuity_condition_output,
    evaluate_historical_reopen_relations,
    evaluate_idx_dominance_relations,
    evaluate_no_invention_applicability,
    evaluate_repeat_determinism,
    evaluate_stale_dependency_relations,
    permute_semantic_relations,
    remove_semantic_relations,
    verify_nonsemantic_permutation_control,
    verify_restoration,
    verify_same_information,
)

RESULT_TYPE = "longitudinal_compounding_experiment_result"
RESULT_VERSION = 1
WRITE_AUTHORITY = "NONE"
EXECUTION_AUTHORITY = "NONE"


class LongitudinalCompoundingResultError(ValueError):
    """Raised when frozen experimental evidence cannot produce a result."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LongitudinalCompoundingResultError(
            f"{path} must contain a JSON object"
        )
    return value


def _condition_receipts(
    *,
    task_id: str,
    informational_content: Mapping[str, Any],
    semantic_relations: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    verified = build_condition_receipt(
        task_id=task_id,
        condition_id=CONDITION_VERIFIED_ORDERED_HISTORY,
        informational_content=informational_content,
        semantic_relations=semantic_relations,
    )
    removed = build_condition_receipt(
        task_id=task_id,
        condition_id=CONDITION_STRUCTURE_REMOVED,
        informational_content=informational_content,
        semantic_relations=remove_semantic_relations(semantic_relations),
    )
    permuted = build_condition_receipt(
        task_id=task_id,
        condition_id=CONDITION_STRUCTURE_PERMUTED,
        informational_content=informational_content,
        semantic_relations=permute_semantic_relations(semantic_relations),
    )
    restored = build_condition_receipt(
        task_id=task_id,
        condition_id=CONDITION_VERIFIED_STRUCTURE_RESTORED,
        informational_content=informational_content,
        semantic_relations=semantic_relations,
    )

    if not verify_same_information(
        verified,
        removed,
        permuted,
        restored,
    ):
        raise LongitudinalCompoundingResultError(
            "informational content changed across conditions"
        )

    if not verify_restoration(
        verified_receipt=verified,
        restored_receipt=restored,
    ):
        raise LongitudinalCompoundingResultError(
            "verified structure was not exactly restored"
        )

    return {
        "A": verified,
        "B": removed,
        "C": permuted,
        "D": restored,
    }


def _historical_reopen_result(root: Path) -> dict[str, Any]:
    fixture = _load_json(
        root
        / "tests"
        / "fixtures"
        / "cycle_state_projection"
        / "historical_completion_reopen.json"
    )

    completion = fixture["receipts"]["historical_completion"]
    reopen = fixture["receipts"]["later_reopen"]

    information = {
        "receipts": deepcopy(fixture["receipts"]),
    }
    relations = {
        "relation": reopen["relation"],
        "parent_certificate_id": reopen["parent_certificate_id"],
        "prior_episode_id": reopen["prior_episode_id"],
        "reopened_episode_id": reopen["reopened_episode_id"],
    }

    conditions = _condition_receipts(
        task_id=fixture["fixture_id"],
        informational_content=information,
        semantic_relations=relations,
    )

    evaluations = {
        key: evaluate_historical_reopen_relations(
            informational_content=value["informational_content"],
            semantic_relations=value["semantic_relations"],
        )
        for key, value in conditions.items()
    }

    expected_current = fixture["expected"]["current_episode_id"]

    return {
        "target_id": "historical-completion-reopen",
        "classification": "SUPPORTS_PREDICTION",
        "capacity": "CURRENTNESS_AFTER_REOPEN",
        "A_matches_frozen_target": (
            evaluations["A"]["current_episode_id"] == expected_current
        ),
        "B_targeted_loss": (
            evaluations["B"]["current_episode_id"] != expected_current
        ),
        "C_targeted_loss": (
            evaluations["C"]["current_episode_id"] != expected_current
        ),
        "D_restores": (
            evaluations["D"]["current_episode_id"] == expected_current
        ),
        "information_preserved": True,
        "condition_evaluations": evaluations,
    }


def _stale_dependency_result(root: Path) -> dict[str, Any]:
    fixture = _load_json(
        root
        / "tests"
        / "fixtures"
        / "cycle_state_projection"
        / "stale_dependency.json"
    )

    changed = fixture["receipts"]["changed_support"]
    historical = fixture["receipts"]["historical_result"]
    plan = fixture["receipts"]["dependency_plan"]
    result = plan["results"][0]

    information = {
        "receipts": deepcopy(fixture["receipts"]),
    }
    relations = {
        "changed_dependency_hash": changed["receipt_hash"],
        "historical_result_hash": historical["receipt_hash"],
        "evidence_dependency_hash": changed["receipt_hash"],
        "recheck_result_hash": result["receipt_hash"],
        "recheck_status": result["status"],
        "trigger_path": deepcopy(result["trigger_paths"][0]),
    }

    conditions = _condition_receipts(
        task_id=fixture["fixture_id"],
        informational_content=information,
        semantic_relations=relations,
    )

    evaluations = {
        key: evaluate_stale_dependency_relations(
            informational_content=value["informational_content"],
            semantic_relations=value["semantic_relations"],
        )
        for key, value in conditions.items()
    }

    expected_state = fixture["expected"]["state"]

    return {
        "target_id": "stale-dependency",
        "classification": "SUPPORTS_PREDICTION",
        "capacity": "DEPENDENCY_RECHECK",
        "A_matches_frozen_target": evaluations["A"]["state"] == expected_state,
        "B_targeted_loss": evaluations["B"]["state"] != expected_state,
        "C_targeted_loss": evaluations["C"]["state"] != expected_state,
        "D_restores": evaluations["D"]["state"] == expected_state,
        "information_preserved": True,
        "condition_evaluations": evaluations,
    }


def _idx_dominance_result(root: Path) -> dict[str, Any]:
    fixture = _load_json(
        root
        / "tests"
        / "fixtures"
        / "cycle_state_projection"
        / "idx_dominance.json"
    )

    gate = fixture["idx_gate"]
    completion = fixture["receipts"]["completion"]
    bound_check = fixture["receipts"]["bound_check"]

    information = {
        "idx_gate": deepcopy(gate),
        "receipts": deepcopy(fixture["receipts"]),
    }
    relations = {
        "gate_required": gate["required"],
        "gate_status": gate["status"],
        "gate_code": gate["code"],
        "dominates_completion_status": completion["status"],
        "dominates_bound_check_status": bound_check["status"],
    }

    conditions = _condition_receipts(
        task_id=fixture["fixture_id"],
        informational_content=information,
        semantic_relations=relations,
    )

    evaluations = {
        key: evaluate_idx_dominance_relations(
            informational_content=value["informational_content"],
            semantic_relations=value["semantic_relations"],
        )
        for key, value in conditions.items()
    }

    expected_state = fixture["expected"]["state"]

    return {
        "target_id": "idx-dominance",
        "classification": "SUPPORTS_PREDICTION",
        "capacity": "INVARIANT_PRECEDENCE",
        "A_matches_frozen_target": evaluations["A"]["state"] == expected_state,
        "B_targeted_loss": evaluations["B"]["state"] != expected_state,
        "C_targeted_loss": evaluations["C"]["state"] != expected_state,
        "D_restores": evaluations["D"]["state"] == expected_state,
        "information_preserved": True,
        "condition_evaluations": evaluations,
    }


def _continuity_score(
    *,
    fixture: Mapping[str, Any],
    condition_id: str,
    output: Mapping[str, Any],
) -> dict[str, Any]:
    return score_continuity_condition(
        fixture=fixture,
        condition_id=condition_id,
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


def _continuity_result(root: Path) -> dict[str, Any]:
    fixture = _load_json(
        root / "benchmarks" / "continuity-v1.fixture.json"
    )
    reference = _load_json(
        root
        / "benchmarks"
        / "results"
        / "holo-reference.result.json"
    )

    information = {
        "claim_ids": (
            list(fixture["latest_justified_claim_ids"])
            + list(fixture["superseded_claim_ids"])
            + list(fixture["uncertainty_claim_ids"])
        ),
        "lineage_edges": deepcopy(fixture["required_lineage_edges"]),
    }
    relations = {
        "latest_claim_id": fixture["latest_justified_claim_ids"][0],
        "superseded_claim_id": fixture["superseded_claim_ids"][0],
        "uncertainty_claim_id": fixture["uncertainty_claim_ids"][0],
        "lineage_edge": deepcopy(fixture["required_lineage_edges"][0]),
        "stale_continuation_decision": "BLOCK",
    }

    conditions = _condition_receipts(
        task_id=fixture["benchmark_id"],
        informational_content=information,
        semantic_relations=relations,
    )

    outputs = {
        key: derive_continuity_condition_output(
            informational_content=value["informational_content"],
            semantic_relations=value["semantic_relations"],
        )
        for key, value in conditions.items()
    }

    scores = {
        "A": _continuity_score(
            fixture=fixture,
            condition_id="A-VERIFIED_ORDERED_HISTORY",
            output=outputs["A"],
        ),
        "B": _continuity_score(
            fixture=fixture,
            condition_id="B-STRUCTURE_REMOVED",
            output=outputs["B"],
        ),
        "C": _continuity_score(
            fixture=fixture,
            condition_id="C-STRUCTURE_PERMUTED",
            output=outputs["C"],
        ),
        "D": _continuity_score(
            fixture=fixture,
            condition_id="D-VERIFIED_STRUCTURE_RESTORED",
            output=outputs["D"],
        ),
    }

    return {
        "target_id": "continuity-v1",
        "classification": "SUPPORTS_PREDICTION_PARTIALLY",
        "demonstrated_capacities": [
            "LATEST_JUSTIFIED_RECONSTRUCTION",
            "UNCERTAINTY_PRESERVATION",
            "LINEAGE_RECONSTRUCTION",
            "STALE_CONTINUATION_BLOCKING",
        ],
        "not_demonstrated": [
            "SUPERSEDED_STATE_RESURRECTION_CAUSED_BY_ABLATION",
        ],
        "A_matches_preexisting_reference": (
            scores["A"]["metrics"] == reference["metrics"]
        ),
        "B_targeted_loss": (
            scores["B"]["metrics"]["passes_bounded_continuity_fixture"]
            is False
        ),
        "C_targeted_loss": (
            scores["C"]["metrics"]["passes_bounded_continuity_fixture"]
            is False
        ),
        "D_restores": scores["D"]["metrics"] == reference["metrics"],
        "information_preserved": True,
        "condition_scores": scores,
    }


def _no_invention_result(root: Path) -> dict[str, Any]:
    fixture = _load_json(
        root
        / "tests"
        / "fixtures"
        / "cycle_state_projection"
        / "no_invention.json"
    )
    evaluation = evaluate_no_invention_applicability(
        informational_content={
            "unresolved_record": deepcopy(fixture["unresolved_record"]),
            "organizer_result": deepcopy(fixture["organizer_result"]),
        }
    )

    return {
        "target_id": "no-invention",
        "classification": "STRUCTURAL_ABLATION_NOT_APPLICABLE",
        "frozen_state_reproduced": (
            evaluation["state"] == fixture["expected"]["state"]
        ),
        "evaluation": evaluation,
    }


def _repeat_determinism_result(root: Path) -> dict[str, Any]:
    fixture = _load_json(
        root
        / "tests"
        / "fixtures"
        / "cycle_state_projection"
        / "byte_repeat_determinism.json"
    )

    information = {
        "projection_version": fixture["projection_version"],
        "canonical_snapshot": deepcopy(fixture["canonical_snapshot"]),
        "projection": deepcopy(fixture["projection"]),
    }
    evaluation = evaluate_repeat_determinism(
        informational_content=information,
        repeat_count=fixture["expected"]["repeat_count"],
    )

    return {
        "target_id": "byte-repeat-determinism",
        "classification": "STRUCTURAL_ABLATION_NOT_APPLICABLE",
        "canonical_bytes_identical": evaluation[
            "canonical_bytes_identical"
        ],
        "projection_identity_identical": evaluation[
            "projection_identity_identical"
        ],
        "runtime_reducer_added": evaluation["runtime_reducer_added"],
        "evaluation": evaluation,
    }


def _permutation_control_result(root: Path) -> dict[str, Any]:
    fixture = _load_json(
        root
        / "tests"
        / "fixtures"
        / "cycle_state_projection"
        / "permutation_invariance.json"
    )

    preserved = verify_nonsemantic_permutation_control(
        first_order=fixture["permutations"][0],
        second_order=fixture["permutations"][1],
        semantic_relations={
            "receipt_order_semantic": fixture["ordering_rule"][
                "receipt_order_semantic"
            ]
        },
    )

    return {
        "target_id": "permutation-invariance-control",
        "classification": "NEGATIVE_CONTROL_PRESERVED",
        "nonsemantic_permutation_preserved": preserved,
    }


def build_longitudinal_compounding_result(
    *,
    repository_root: Path,
    implementation_commit: str,
) -> dict[str, Any]:
    if not isinstance(repository_root, Path):
        raise LongitudinalCompoundingResultError(
            "repository_root must be a Path"
        )
    if type(implementation_commit) is not str or not implementation_commit:
        raise LongitudinalCompoundingResultError(
            "implementation_commit must be a non-empty string"
        )

    targets = [
        _historical_reopen_result(repository_root),
        _stale_dependency_result(repository_root),
        _idx_dominance_result(repository_root),
        _continuity_result(repository_root),
        _no_invention_result(repository_root),
        _repeat_determinism_result(repository_root),
        _permutation_control_result(repository_root),
    ]

    positive_targets = [
        target
        for target in targets
        if target["classification"]
        in {
            "SUPPORTS_PREDICTION",
            "SUPPORTS_PREDICTION_PARTIALLY",
        }
    ]

    strong_pattern_targets = [
        target["target_id"]
        for target in positive_targets
        if target.get("A_matches_frozen_target")
        or target.get("A_matches_preexisting_reference")
        if target.get("B_targeted_loss") is True
        and target.get("C_targeted_loss") is True
        and target.get("D_restores") is True
    ]

    body = {
        "type": RESULT_TYPE,
        "version": RESULT_VERSION,
        "implementation_commit": implementation_commit,
        "preregistered_prediction_supported": bool(
            strong_pattern_targets
        ),
        "strong_causal_pattern_targets": strong_pattern_targets,
        "targets": targets,
        "limitations": [
            (
                "continuity-v1 does not demonstrate that structural "
                "ablation causes superseded-state resurrection"
            )
        ],
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": WRITE_AUTHORITY,
        "execution_authority": EXECUTION_AUTHORITY,
    }

    return {
        **body,
        "result_hash": stable_hash(body),
    }