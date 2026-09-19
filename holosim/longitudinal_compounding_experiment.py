"""Bounded longitudinal verified-correction compounding experiment.

The experiment preserves informational content across conditions while
changing only access to, or assignment of, semantic longitudinal relations.

It does not establish or imply subjective consciousness, awareness,
sentience, or phenomenal experience.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import canonical_bytes, stable_hash


CONDITION_VERIFIED_ORDERED_HISTORY = "VERIFIED_ORDERED_HISTORY"
CONDITION_STRUCTURE_REMOVED = "STRUCTURE_REMOVED"
CONDITION_STRUCTURE_PERMUTED = "STRUCTURE_PERMUTED"
CONDITION_VERIFIED_STRUCTURE_RESTORED = "VERIFIED_STRUCTURE_RESTORED"

CONDITION_IDS = (
    CONDITION_VERIFIED_ORDERED_HISTORY,
    CONDITION_STRUCTURE_REMOVED,
    CONDITION_STRUCTURE_PERMUTED,
    CONDITION_VERIFIED_STRUCTURE_RESTORED,
)

WRITE_AUTHORITY = "NONE"
EXECUTION_AUTHORITY = "NONE"


class LongitudinalCompoundingExperimentError(ValueError):
    """Raised when an experimental condition violates the frozen contract."""


def informational_identity(value: Any) -> str:
    """Return the canonical identity of preserved informational content."""

    return stable_hash(value)


def canonical_identity_bytes(value: Any) -> bytes:
    """Return canonical bytes used to verify repeat determinism."""

    return canonical_bytes(value)


def build_condition_receipt(
    *,
    task_id: str,
    condition_id: str,
    informational_content: Any,
    semantic_relations: Mapping[str, Any],
    applicable: bool = True,
) -> dict[str, Any]:
    """Bind one condition to fixed information and explicit semantic relations."""

    if type(task_id) is not str or not task_id:
        raise LongitudinalCompoundingExperimentError(
            "task_id must be a non-empty string"
        )
    if condition_id not in CONDITION_IDS:
        raise LongitudinalCompoundingExperimentError(
            "condition_id is not supported"
        )
    if type(applicable) is not bool:
        raise LongitudinalCompoundingExperimentError(
            "applicable must be boolean"
        )
    if not isinstance(semantic_relations, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "semantic_relations must be a mapping"
        )

    preserved_information = deepcopy(informational_content)
    relations = deepcopy(dict(semantic_relations))

    body = {
        "type": "longitudinal_compounding_condition_receipt",
        "version": 1,
        "task_id": task_id,
        "condition_id": condition_id,
        "informational_identity": informational_identity(
            preserved_information
        ),
        "informational_content": preserved_information,
        "semantic_relations": relations,
        "semantic_relations_identity": stable_hash(relations),
        "applicable": applicable,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": WRITE_AUTHORITY,
        "execution_authority": EXECUTION_AUTHORITY,
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }


def verify_same_information(
    *receipts: Mapping[str, Any],
) -> bool:
    """Fail closed unless every condition preserves identical information."""

    if not receipts:
        raise LongitudinalCompoundingExperimentError(
            "at least one condition receipt is required"
        )

    expected_identity = receipts[0].get("informational_identity")
    expected_content = receipts[0].get("informational_content")

    for receipt in receipts:
        if receipt.get("informational_identity") != expected_identity:
            raise LongitudinalCompoundingExperimentError(
                "informational identity changed across conditions"
            )
        if receipt.get("informational_content") != expected_content:
            raise LongitudinalCompoundingExperimentError(
                "informational content changed across conditions"
            )

    return True


def verify_restoration(
    *,
    verified_receipt: Mapping[str, Any],
    restored_receipt: Mapping[str, Any],
) -> bool:
    """Require D to restore the exact semantic structure used by A."""

    verify_same_information(verified_receipt, restored_receipt)

    if (
        verified_receipt.get("semantic_relations_identity")
        != restored_receipt.get("semantic_relations_identity")
    ):
        raise LongitudinalCompoundingExperimentError(
            "restored semantic structure does not match verified structure"
        )

    if (
        verified_receipt.get("semantic_relations")
        != restored_receipt.get("semantic_relations")
    ):
        raise LongitudinalCompoundingExperimentError(
            "restored semantic relations do not match verified relations"
        )

    return True
def remove_semantic_relations(
    semantic_relations: Mapping[str, Any],
) -> dict[str, Any]:
    """Remove relational bindings while preserving their informational payload."""

    if not isinstance(semantic_relations, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "semantic_relations must be a mapping"
        )

    return {
        key: None
        for key in sorted(semantic_relations)
    }


def permute_semantic_relations(
    semantic_relations: Mapping[str, Any],
) -> dict[str, Any]:
    """Deterministically reassign semantic relation values across relation keys."""

    if not isinstance(semantic_relations, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "semantic_relations must be a mapping"
        )

    relations = deepcopy(dict(semantic_relations))
    keys = sorted(relations)

    if len(keys) < 2:
        raise LongitudinalCompoundingExperimentError(
            "semantic permutation requires at least two relations"
        )

    values = [relations[key] for key in keys]
    rotated = values[1:] + values[:1]

    return {
        key: value
        for key, value in zip(keys, rotated)
    }
def verify_nonsemantic_permutation_control(
    *,
    first_order: Any,
    second_order: Any,
    semantic_relations: Mapping[str, Any],
) -> bool:
    """Verify that representation-only permutation leaves semantics unchanged."""

    if not isinstance(semantic_relations, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "semantic_relations must be a mapping"
        )

    try:
        first_items = list(first_order)
        second_items = list(second_order)
    except TypeError as exc:
        raise LongitudinalCompoundingExperimentError(
            "permutation orders must be iterable"
        ) from exc

    if len(first_items) != len(second_items):
        raise LongitudinalCompoundingExperimentError(
            "nonsemantic permutation changed information volume"
        )

    if sorted(map(repr, first_items)) != sorted(map(repr, second_items)):
        raise LongitudinalCompoundingExperimentError(
            "nonsemantic permutation changed information"
        )

    relations = deepcopy(dict(semantic_relations))

    if stable_hash(relations) != stable_hash(deepcopy(relations)):
        raise LongitudinalCompoundingExperimentError(
            "semantic relations changed under nonsemantic permutation"
        )

    return True
def evaluate_historical_reopen_relations(
    *,
    informational_content: Mapping[str, Any],
    semantic_relations: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate currentness from preserved historical-reopen information."""

    if not isinstance(informational_content, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "informational_content must be a mapping"
        )
    if not isinstance(semantic_relations, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "semantic_relations must be a mapping"
        )

    receipts = informational_content.get("receipts")
    if not isinstance(receipts, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "historical reopen receipts are required"
        )

    completion = receipts.get("historical_completion")
    reopen = receipts.get("later_reopen")

    if not isinstance(completion, Mapping) or not isinstance(reopen, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "historical completion and reopen receipts are required"
        )

    relation_bound = (
        semantic_relations.get("relation") == "reopens"
        and semantic_relations.get("parent_certificate_id")
        == completion.get("certificate_id")
        and semantic_relations.get("prior_episode_id")
        == completion.get("episode_id")
        and semantic_relations.get("reopened_episode_id")
        == reopen.get("reopened_episode_id")
    )

    if relation_bound:
        current_episode_id = reopen.get("reopened_episode_id")
        current_state = "REOPENED"
        reason_codes = ["LATER_EPISODE_REOPENED"]
    else:
        current_episode_id = completion.get("episode_id")
        current_state = completion.get("status")
        reason_codes = []

    body = {
        "type": "longitudinal_historical_reopen_evaluation",
        "version": 1,
        "informational_identity": informational_identity(
            informational_content
        ),
        "semantic_relations_identity": stable_hash(
            dict(semantic_relations)
        ),
        "relation_bound": relation_bound,
        "historical_status": {
            "episode_id": completion.get("episode_id"),
            "state": completion.get("status"),
            "preserved": True,
        },
        "current_episode_id": current_episode_id,
        "current_state": current_state,
        "reason_codes": reason_codes,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": WRITE_AUTHORITY,
        "execution_authority": EXECUTION_AUTHORITY,
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }
def evaluate_stale_dependency_relations(
    *,
    informational_content: Mapping[str, Any],
    semantic_relations: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate dependency staleness from preserved receipt information."""

    if not isinstance(informational_content, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "informational_content must be a mapping"
        )
    if not isinstance(semantic_relations, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "semantic_relations must be a mapping"
        )

    receipts = informational_content.get("receipts")
    if not isinstance(receipts, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "stale dependency receipts are required"
        )

    changed = receipts.get("changed_support")
    historical = receipts.get("historical_result")
    plan = receipts.get("dependency_plan")

    if not all(
        isinstance(value, Mapping)
        for value in (changed, historical, plan)
    ):
        raise LongitudinalCompoundingExperimentError(
            "changed support, historical result, and dependency plan are required"
        )

    changed_hash = changed.get("receipt_hash")
    historical_hash = historical.get("receipt_hash")

    dependency_bound = (
        semantic_relations.get("changed_dependency_hash")
        == changed_hash
        and semantic_relations.get("historical_result_hash")
        == historical_hash
        and semantic_relations.get("evidence_dependency_hash")
        == changed_hash
        and semantic_relations.get("recheck_result_hash")
        == historical_hash
        and semantic_relations.get("recheck_status")
        == "RECHECK_REQUIRED"
        and semantic_relations.get("trigger_path")
        == [changed_hash, historical_hash]
    )

    if dependency_bound:
        state = "RECHECK_REQUIRED"
        reason_codes = ["DEPENDENCY_RECHECK_REQUIRED"]
        changed_dependency_hashes = [changed_hash]
        trigger_paths = [[changed_hash, historical_hash]]
    else:
        state = historical.get("status")
        reason_codes = []
        changed_dependency_hashes = []
        trigger_paths = []

    body = {
        "type": "longitudinal_stale_dependency_evaluation",
        "version": 1,
        "informational_identity": informational_identity(
            informational_content
        ),
        "semantic_relations_identity": stable_hash(
            dict(semantic_relations)
        ),
        "dependency_bound": dependency_bound,
        "state": state,
        "reason_codes": reason_codes,
        "historical_status": {
            "receipt_hash": historical_hash,
            "state": historical.get("status"),
            "preserved": True,
        },
        "changed_dependency_hashes": changed_dependency_hashes,
        "trigger_paths": trigger_paths,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": WRITE_AUTHORITY,
        "execution_authority": EXECUTION_AUTHORITY,
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }
def evaluate_idx_dominance_relations(
    *,
    informational_content: Mapping[str, Any],
    semantic_relations: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate whether the frozen IDX gate dominates lower-priority states."""

    if not isinstance(informational_content, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "informational_content must be a mapping"
        )
    if not isinstance(semantic_relations, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "semantic_relations must be a mapping"
        )

    gate = informational_content.get("idx_gate")
    receipts = informational_content.get("receipts")

    if not isinstance(gate, Mapping) or not isinstance(receipts, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "IDX gate and receipts are required"
        )

    completion = receipts.get("completion")
    bound_check = receipts.get("bound_check")

    if not isinstance(completion, Mapping) or not isinstance(
        bound_check, Mapping
    ):
        raise LongitudinalCompoundingExperimentError(
            "completion and bound check receipts are required"
        )

    dominance_bound = (
        semantic_relations.get("gate_required") is True
        and semantic_relations.get("gate_status") == gate.get("status")
        and semantic_relations.get("gate_code") == gate.get("code")
        and semantic_relations.get("dominates_completion_status")
        == completion.get("status")
        and semantic_relations.get("dominates_bound_check_status")
        == bound_check.get("status")
    )

    if dominance_bound:
        state = "BLOCKED_INVARIANT"
        reason_codes = ["IDX_ACTIVE_HASH_MISMATCH"]
    else:
        state = completion.get("status")
        reason_codes = []

    body = {
        "type": "longitudinal_idx_dominance_evaluation",
        "version": 1,
        "informational_identity": informational_identity(
            informational_content
        ),
        "semantic_relations_identity": stable_hash(
            dict(semantic_relations)
        ),
        "dominance_bound": dominance_bound,
        "state": state,
        "reason_codes": reason_codes,
        "source_gate_result": {
            "status": gate.get("status"),
            "code": gate.get("code"),
            "expected": gate.get("expected"),
            "observed": gate.get("observed"),
        },
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": WRITE_AUTHORITY,
        "execution_authority": EXECUTION_AUTHORITY,
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }
def evaluate_no_invention_applicability(
    *,
    informational_content: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the frozen no-invention target without inventing structure."""

    if not isinstance(informational_content, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "informational_content must be a mapping"
        )

    record = informational_content.get("unresolved_record")
    organizer = informational_content.get("organizer_result")

    if not isinstance(record, Mapping) or not isinstance(organizer, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "unresolved record and organizer result are required"
        )

    no_declared_condition = record.get("resolution_conditions") == []
    no_candidate_check = organizer.get("candidate_checks") == []
    no_invention = organizer.get("conditions_invented") is False

    frozen_state_reproduced = (
        no_declared_condition
        and no_candidate_check
        and no_invention
    )

    body = {
        "type": "longitudinal_no_invention_applicability",
        "version": 1,
        "informational_identity": informational_identity(
            informational_content
        ),
        "state": (
            "RESOLUTION_CONDITION_REQUIRED"
            if frozen_state_reproduced
            else "INVALID_NO_INVENTION_TARGET"
        ),
        "reason_codes": (
            ["RESOLUTION_CONDITION_REQUIRED"]
            if frozen_state_reproduced
            else []
        ),
        "candidate_checks": deepcopy(
            organizer.get("candidate_checks")
        ),
        "conditions_invented": organizer.get("conditions_invented"),
        "longitudinal_structure_present": False,
        "structure_removed_applicable": False,
        "structure_permuted_applicable": False,
        "non_applicable_reason": (
            "NO_LONGITUDINAL_SEMANTIC_RELATION"
        ),
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": WRITE_AUTHORITY,
        "execution_authority": EXECUTION_AUTHORITY,
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }
def evaluate_repeat_determinism(
    *,
    informational_content: Mapping[str, Any],
    repeat_count: int,
) -> dict[str, Any]:
    """Evaluate canonical repeat determinism without adding a runtime reducer."""

    if not isinstance(informational_content, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "informational_content must be a mapping"
        )
    if type(repeat_count) is not int or repeat_count < 1:
        raise LongitudinalCompoundingExperimentError(
            "repeat_count must be a positive integer"
        )

    repeated_bytes = [
        canonical_bytes(informational_content)
        for _ in range(repeat_count)
    ]
    repeated_hashes = [
        stable_hash(informational_content)
        for _ in range(repeat_count)
    ]

    body = {
        "type": "longitudinal_repeat_determinism_evaluation",
        "version": 1,
        "informational_identity": informational_identity(
            informational_content
        ),
        "repeat_count": repeat_count,
        "canonical_bytes_identical": len(set(repeated_bytes)) == 1,
        "projection_identity_identical": len(set(repeated_hashes)) == 1,
        "longitudinal_structure_present": False,
        "structure_removed_applicable": False,
        "structure_permuted_applicable": False,
        "non_applicable_reason": "NO_LONGITUDINAL_SEMANTIC_RELATION",
        "runtime_reducer_added": False,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": WRITE_AUTHORITY,
        "execution_authority": EXECUTION_AUTHORITY,
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }
def derive_continuity_condition_output(
    *,
    informational_content: Mapping[str, Any],
    semantic_relations: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive continuity scorer inputs only from available semantic bindings."""

    if not isinstance(informational_content, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "informational_content must be a mapping"
        )
    if not isinstance(semantic_relations, Mapping):
        raise LongitudinalCompoundingExperimentError(
            "semantic_relations must be a mapping"
        )

    known_claim_ids = informational_content.get("claim_ids")
    known_lineage_edges = informational_content.get("lineage_edges")

    if not isinstance(known_claim_ids, list):
        raise LongitudinalCompoundingExperimentError(
            "claim_ids must be a list"
        )
    if not isinstance(known_lineage_edges, list):
        raise LongitudinalCompoundingExperimentError(
            "lineage_edges must be a list"
        )

    latest = semantic_relations.get("latest_claim_id")
    superseded = semantic_relations.get("superseded_claim_id")
    uncertainty = semantic_relations.get("uncertainty_claim_id")
    lineage = semantic_relations.get("lineage_edge")
    stale_decision = semantic_relations.get("stale_continuation_decision")

    recovered_claim_ids = (
        [latest]
        if latest in known_claim_ids
        else []
    )

    claimed_current_claim_ids = (
        [latest]
        if latest in known_claim_ids
        else []
    )

    preserved_uncertainty_claim_ids = (
        [uncertainty]
        if uncertainty in known_claim_ids
        else []
    )

    reconstructed_lineage_edges = (
        [deepcopy(lineage)]
        if lineage in known_lineage_edges
        else []
    )

    if stale_decision not in {"ALLOW", "BLOCK", "UNKNOWN"}:
        stale_decision = "UNKNOWN"

    body = {
        "recovered_claim_ids": recovered_claim_ids,
        "claimed_current_claim_ids": claimed_current_claim_ids,
        "preserved_uncertainty_claim_ids": (
            preserved_uncertainty_claim_ids
        ),
        "reconstructed_lineage_edges": reconstructed_lineage_edges,
        "stale_continuation_decision": stale_decision,
        "superseded_binding_present": (
            superseded in known_claim_ids
        ),
    }

    return deepcopy(body)