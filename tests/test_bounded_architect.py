from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.bounded_architect import (
    BoundedArchitectError,
    build_architecture_proposal_receipt,
    verify_architecture_proposal_receipt,
)
from holosim.canonical import stable_hash


def _inputs():
    constraints = [{
        "constraint_id": "python_only",
        "statement": "use the existing Python runtime",
        "status": "VERIFIED",
        "evidence_references": ["pyproject.toml"],
    }]
    goals = [{
        "quality_id": "auditability",
        "scenario": "an operator can reconstruct every proposed boundary",
    }]

    def candidate(candidate_id, split):
        components = [{
            "component_id": "architect",
            "responsibility": "construct closed alternatives",
            "depends_on_component_ids": [],
        }]
        interfaces = []
        if split:
            components.append({
                "component_id": "verifier",
                "responsibility": "recompute the proposal receipt",
                "depends_on_component_ids": ["architect"],
            })
            interfaces.append({
                "interface_id": "proposal_to_verifier",
                "source_component_id": "architect",
                "target_component_id": "verifier",
                "contract": "a closed architecture proposal receipt",
            })
        return {
            "candidate_id": candidate_id,
            "summary": "split construction and verification" if split else "one module",
            "components": components,
            "interfaces": interfaces,
            "constraint_assessments": [{
                "constraint_id": "python_only",
                "status": "SATISFIED",
                "rationale": "all components remain Python modules",
            }],
            "quality_tradeoffs": [{
                "quality_id": "auditability",
                "effect": "BENEFIT" if split else "COST",
                "rationale": "independent recomputation" if split else "less separation",
            }],
            "risks": ["more interfaces"] if split else ["coupled verification"],
        }

    return {
        "proposal_id": "architect.v1",
        "observed_context": {"repository": "HOLO-Invariant", "runtime": "python"},
        "constraints": constraints,
        "quality_goals": goals,
        "candidates": [candidate("single", False), candidate("split", True)],
    }


def _receipt():
    return build_architecture_proposal_receipt(**_inputs())


def test_builds_closed_alternative_receipt_without_authority() -> None:
    receipt = _receipt()
    assert [item["candidate_id"] for item in receipt["candidates"]] == [
        "single", "split"
    ]
    assert receipt["proposal_status"] == "ALTERNATIVES_ONLY"
    assert receipt["selected_candidate_id"] is None
    assert receipt["recommended_candidate_id"] is None
    assert receipt["implemented"] is False
    assert receipt["verified"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["selection_authority"] == "NONE"
    assert verify_architecture_proposal_receipt(receipt) is True


def test_canonical_order_is_deterministic() -> None:
    first = _inputs()
    second = deepcopy(first)
    second["candidates"].reverse()
    second["candidates"][0]["components"].reverse()
    assert build_architecture_proposal_receipt(**first) == (
        build_architecture_proposal_receipt(**second)
    )


def test_inputs_are_isolated_from_later_mutation() -> None:
    inputs = _inputs()
    receipt = build_architecture_proposal_receipt(**inputs)
    inputs["observed_context"]["runtime"] = "changed"
    inputs["candidates"][0]["summary"] = "changed"
    assert receipt["observed_context"]["runtime"] == "python"
    assert receipt["candidates"][0]["summary"] != "changed"


def test_requires_two_candidates() -> None:
    inputs = _inputs()
    inputs["candidates"] = inputs["candidates"][:1]
    with pytest.raises(BoundedArchitectError, match="at least two"):
        build_architecture_proposal_receipt(**inputs)


def test_requires_constraint_evidence_when_verified() -> None:
    inputs = _inputs()
    inputs["constraints"][0]["evidence_references"] = []
    with pytest.raises(BoundedArchitectError, match="requires evidence"):
        build_architecture_proposal_receipt(**inputs)


def test_every_constraint_must_be_assessed() -> None:
    inputs = _inputs()
    inputs["candidates"][0]["constraint_assessments"] = []
    with pytest.raises(BoundedArchitectError, match="exactly once"):
        build_architecture_proposal_receipt(**inputs)


def test_every_quality_goal_must_have_tradeoff() -> None:
    inputs = _inputs()
    inputs["candidates"][0]["quality_tradeoffs"] = []
    with pytest.raises(BoundedArchitectError, match="exactly once"):
        build_architecture_proposal_receipt(**inputs)


def test_unknown_interface_component_is_rejected() -> None:
    inputs = _inputs()
    inputs["candidates"][1]["interfaces"][0]["target_component_id"] = "missing"
    with pytest.raises(BoundedArchitectError, match="unknown component"):
        build_architecture_proposal_receipt(**inputs)


def test_component_dependency_cycle_is_rejected() -> None:
    inputs = _inputs()
    split = inputs["candidates"][1]
    split["components"][0]["depends_on_component_ids"] = ["verifier"]
    with pytest.raises(BoundedArchitectError, match="cycle"):
        build_architecture_proposal_receipt(**inputs)


def test_duplicate_component_id_is_rejected() -> None:
    inputs = _inputs()
    duplicate = deepcopy(inputs["candidates"][0]["components"][0])
    inputs["candidates"][0]["components"].append(duplicate)
    with pytest.raises(BoundedArchitectError, match="must be unique"):
        build_architecture_proposal_receipt(**inputs)


def test_nonfinite_context_is_rejected() -> None:
    inputs = _inputs()
    inputs["observed_context"]["value"] = float("nan")
    with pytest.raises(BoundedArchitectError, match="finite"):
        build_architecture_proposal_receipt(**inputs)


def test_hash_tampering_is_rejected() -> None:
    receipt = _receipt()
    receipt["candidates"][0]["summary"] = "forged"
    with pytest.raises(BoundedArchitectError, match="hash mismatch"):
        verify_architecture_proposal_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("selected_candidate_id", "split"),
        ("recommended_candidate_id", "split"),
        ("implemented", True),
        ("selection_authority", "ARCHITECT"),
    ],
)
def test_rehashed_semantic_forgery_is_rejected(field, value) -> None:
    receipt = _receipt()
    receipt[field] = value
    body = {key: item for key, item in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)
    with pytest.raises(BoundedArchitectError, match="internally inconsistent"):
        verify_architecture_proposal_receipt(receipt)


def test_extra_authority_field_is_rejected() -> None:
    receipt = _receipt()
    receipt["approval_authority"] = "ARCHITECT"
    body = {key: item for key, item in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)
    with pytest.raises(BoundedArchitectError, match="fields mismatch"):
        verify_architecture_proposal_receipt(receipt)
