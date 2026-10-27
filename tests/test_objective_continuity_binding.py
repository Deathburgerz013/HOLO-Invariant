
from copy import deepcopy

import pytest
from holosim.canonical import stable_hash
from holosim.objective_continuity_binding import (
    ObjectiveContinuityBindingError,
    build_objective_binding,
    build_objective_successor,
    validate_objective_binding,
    validate_objective_successor,
)


def _objective():
    return build_objective_binding(
        objective_id="objective:keep-organizing",
        definition="Keep organizing verified information.",
        criteria=[
            "Preserve verified information.",
            "Identify unresolved organizational problems.",
            "Verify proposed corrections before claiming improvement.",
        ],
    )


def test_objective_binding_is_deterministic():
    first = _objective()
    second = _objective()

    assert first == second
    assert validate_objective_binding(first) is True
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"


def test_successor_preserves_objective_with_new_problem():
    objective = _objective()

    successor = build_objective_successor(
        objective=objective,
        prior_loop_id="loop:1",
        next_loop_id="loop:2",
        prior_evidence_hash="a" * 64,
        next_problem_id="problem:missing-relationships",
    )

    assert successor["objective_hash"] == objective["objective_hash"]
    assert successor["next_problem_id"] == "problem:missing-relationships"
    assert validate_objective_successor(
        successor, objective=objective
    ) is True


def test_rejects_silent_objective_redefinition():
    original = _objective()
    changed = build_objective_binding(
        objective_id=original["objective_id"],
        definition="Delete as many records as possible.",
        criteria=["Maximize deletion."],
    )

    successor = build_objective_successor(
        objective=original,
        prior_loop_id="loop:1",
        next_loop_id="loop:2",
        prior_evidence_hash="a" * 64,
        next_problem_id="problem:duplicates",
    )

    with pytest.raises(ObjectiveContinuityBindingError):
        validate_objective_successor(successor, objective=changed)


def test_rejects_tampered_objective_definition():
    objective = _objective()
    tampered = deepcopy(objective)
    tampered["definition"] = "Delete everything."

    with pytest.raises(ObjectiveContinuityBindingError):
        validate_objective_binding(tampered)


def test_rejects_same_loop_as_successor():
    with pytest.raises(ObjectiveContinuityBindingError):
        build_objective_successor(
            objective=_objective(),
            prior_loop_id="loop:1",
            next_loop_id="loop:1",
            prior_evidence_hash="a" * 64,
            next_problem_id="problem:duplicates",
        )

@pytest.mark.parametrize(
    "criteria",
    [
        [],
        ["valid", "valid"],
        ["valid", ""],
        ["valid", None],
        "not-a-list",
    ],
)
def test_rejects_invalid_objective_criteria(criteria):
    with pytest.raises(ObjectiveContinuityBindingError):
        build_objective_binding(
            objective_id="objective:keep-organizing",
            definition="Keep organizing.",
            criteria=criteria,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("truth_claimed", True),
        ("accepted", True),
        ("write_authority", "WRITE"),
    ],
)
def test_rejects_forged_objective_authority(field, value):
    objective = _objective()
    objective[field] = value

    with pytest.raises(ObjectiveContinuityBindingError):
        validate_objective_binding(objective)


def test_rejects_rehashed_objective_authority():
    objective = _objective()
    objective["accepted"] = True
    body = {
        key: value
        for key, value in objective.items()
        if key != "objective_hash"
    }
    objective["objective_hash"] = stable_hash(body)

    with pytest.raises(ObjectiveContinuityBindingError):
        validate_objective_binding(objective)


@pytest.mark.parametrize(
    "evidence_hash",
    [
        "",
        "a" * 63,
        "A" * 64,
        "z" * 64,
    ],
)
def test_rejects_invalid_evidence_hash(evidence_hash):
    with pytest.raises(ObjectiveContinuityBindingError):
        build_objective_successor(
            objective=_objective(),
            prior_loop_id="loop:1",
            next_loop_id="loop:2",
            prior_evidence_hash=evidence_hash,
            next_problem_id="problem:duplicates",
        )


def test_rejects_rehashed_successor_authority():
    objective = _objective()
    successor = build_objective_successor(
        objective=objective,
        prior_loop_id="loop:1",
        next_loop_id="loop:2",
        prior_evidence_hash="a" * 64,
        next_problem_id="problem:duplicates",
    )

    successor["write_authority"] = "WRITE"
    body = {
        key: value
        for key, value in successor.items()
        if key != "successor_hash"
    }
    successor["successor_hash"] = stable_hash(body)

    with pytest.raises(ObjectiveContinuityBindingError):
        validate_objective_successor(
            successor, objective=objective
        )
