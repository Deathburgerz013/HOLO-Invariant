from holosim.architectural_boundary_experiment import (
    CLASSIFICATION_NECESSARY,
    CLASSIFICATION_REDUNDANT,
    CLASSIFICATION_UNRESOLVED,
    classify_boundary_comparison,
)


def test_distinguished_failure_is_necessary() -> None:
    receipt = classify_boundary_comparison(
        boundary_id="probe-boundary",
        candidate_with_boundary={"allows_failure": False},
        candidate_without_boundary={"allows_failure": True},
        checks={
            "allows_failure": lambda candidate: candidate["allows_failure"],
        },
        declared_failure=lambda observed: observed["allows_failure"] is True,
        equivalent_rejection_proven=False,
    )

    assert receipt["distinguished"] is True
    assert receipt["indistinguishable"] is False
    assert receipt["unresolved"] is False
    assert receipt["failure_with_boundary"] is False
    assert receipt["failure_without_boundary"] is True
    assert receipt["removal_permits_declared_failure"] is True
    assert receipt["classification"] == CLASSIFICATION_NECESSARY
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_indistinguishable_with_equivalent_rejection_is_redundant() -> None:
    receipt = classify_boundary_comparison(
        boundary_id="probe-boundary",
        candidate_with_boundary={"allows_failure": False},
        candidate_without_boundary={"allows_failure": False},
        checks={
            "allows_failure": lambda candidate: candidate["allows_failure"],
        },
        declared_failure=lambda observed: observed["allows_failure"] is True,
        equivalent_rejection_proven=True,
    )

    assert receipt["distinguished"] is False
    assert receipt["indistinguishable"] is True
    assert receipt["unresolved"] is False
    assert receipt["failure_with_boundary"] is False
    assert receipt["failure_without_boundary"] is False
    assert receipt["removal_permits_declared_failure"] is False
    assert receipt["classification"] == CLASSIFICATION_REDUNDANT


def test_indistinguishable_without_equivalent_rejection_stays_unresolved() -> None:
    receipt = classify_boundary_comparison(
        boundary_id="probe-boundary",
        candidate_with_boundary={"allows_failure": False},
        candidate_without_boundary={"allows_failure": False},
        checks={
            "allows_failure": lambda candidate: candidate["allows_failure"],
        },
        declared_failure=lambda observed: observed["allows_failure"] is True,
        equivalent_rejection_proven=None,
    )

    assert receipt["indistinguishable"] is True
    assert receipt["removal_permits_declared_failure"] is False
    assert receipt["classification"] == CLASSIFICATION_UNRESOLVED


def test_distinguished_behavior_without_declared_failure_stays_unresolved() -> None:
    receipt = classify_boundary_comparison(
        boundary_id="probe-boundary",
        candidate_with_boundary={"state": "A"},
        candidate_without_boundary={"state": "B"},
        checks={"state": lambda candidate: candidate["state"]},
        declared_failure=lambda observed: observed["state"] == "FAILURE",
        equivalent_rejection_proven=False,
    )

    assert receipt["distinguished"] is True
    assert receipt["failure_with_boundary"] is False
    assert receipt["failure_without_boundary"] is False
    assert receipt["removal_permits_declared_failure"] is False
    assert receipt["classification"] == CLASSIFICATION_UNRESOLVED


def test_environmental_reopening_boundary_is_behaviorally_distinguishable() -> None:
    import json
    from pathlib import Path

    from holosim.longitudinal_compounding_experiment import (
        evaluate_historical_reopen_relations,
    )

    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "cycle_state_projection"
        / "historical_completion_reopen.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    reopen = fixture["receipts"]["later_reopen"]
    completion = fixture["receipts"]["historical_completion"]

    with_relation = {
        "relation": reopen["relation"],
        "parent_certificate_id": reopen["parent_certificate_id"],
        "prior_episode_id": reopen["prior_episode_id"],
        "reopened_episode_id": reopen["reopened_episode_id"],
    }

    without_relation = {}

    def currentness(candidate):
        result = evaluate_historical_reopen_relations(
            informational_content=fixture,
            semantic_relations=candidate["semantic_relations"],
        )
        return {
            "relation_bound": result["relation_bound"],
            "current_episode_id": result["current_episode_id"],
            "current_state": result["current_state"],
            "reason_codes": result["reason_codes"],
        }

    def historical_completion_remains_current(observed):
        currentness_observation = observed["historical_completion_currentness"]
        return (
            currentness_observation["current_episode_id"]
            == completion["episode_id"]
            and currentness_observation["current_state"]
            == completion["status"]
        )

    receipt = classify_boundary_comparison(
        boundary_id="environmental-reopening",
        candidate_with_boundary={"semantic_relations": with_relation},
        candidate_without_boundary={"semantic_relations": without_relation},
        checks={"historical_completion_currentness": currentness},
        declared_failure=historical_completion_remains_current,
        equivalent_rejection_proven=False,
    )

    assert receipt["distinguished"] is True
    assert receipt["indistinguishable"] is False
    assert receipt["unresolved"] is False

    assert receipt["failure_with_boundary"] is False
    assert receipt["failure_without_boundary"] is True
    assert receipt["removal_permits_declared_failure"] is True
    assert receipt["classification"] == CLASSIFICATION_NECESSARY

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_failure_on_both_sides_does_not_establish_necessity() -> None:
    receipt = classify_boundary_comparison(
        boundary_id="probe-boundary",
        candidate_with_boundary={"allows_failure": True, "state": "A"},
        candidate_without_boundary={"allows_failure": True, "state": "B"},
        checks={
            "allows_failure": lambda candidate: candidate["allows_failure"],
            "state": lambda candidate: candidate["state"],
        },
        declared_failure=lambda observed: observed["allows_failure"] is True,
        equivalent_rejection_proven=False,
    )

    assert receipt["distinguished"] is True
    assert receipt["failure_with_boundary"] is True
    assert receipt["failure_without_boundary"] is True
    assert receipt["removal_permits_declared_failure"] is False
    assert receipt["classification"] == CLASSIFICATION_UNRESOLVED


def test_removal_that_eliminates_failure_does_not_establish_necessity() -> None:
    receipt = classify_boundary_comparison(
        boundary_id="probe-boundary",
        candidate_with_boundary={"allows_failure": True},
        candidate_without_boundary={"allows_failure": False},
        checks={
            "allows_failure": lambda candidate: candidate["allows_failure"],
        },
        declared_failure=lambda observed: observed["allows_failure"] is True,
        equivalent_rejection_proven=False,
    )

    assert receipt["distinguished"] is True
    assert receipt["failure_with_boundary"] is True
    assert receipt["failure_without_boundary"] is False
    assert receipt["removal_permits_declared_failure"] is False
    assert receipt["classification"] == CLASSIFICATION_UNRESOLVED
