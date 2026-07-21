from __future__ import annotations

import pytest

from holosim.environment_coverage import (
    EnvironmentCoverageError,
    evaluate_environment_coverage,
)


def test_complete_at_boundary_requires_all_required_functions_reproduced() -> None:
    result = evaluate_environment_coverage(
        environment_id="computer-core",
        environment_reference="computer-core@checked-state",
        required_function_ids=["STORE", "RETRIEVE"],
        observed_function_ids=["STORE", "RETRIEVE"],
        reproduced_function_ids=["STORE", "RETRIEVE"],
        unchecked_boundaries=[],
    )

    assert result["status"] == "COMPLETE_AT_BOUNDARY"
    assert result["unresolved_required_function_ids"] == []
    assert result["global_completeness_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_missing_required_function_is_incomplete() -> None:
    result = evaluate_environment_coverage(
        environment_id="computer-core",
        environment_reference="computer-core@checked-state",
        required_function_ids=["STORE", "RETRIEVE"],
        observed_function_ids=["STORE"],
        reproduced_function_ids=["STORE"],
        unchecked_boundaries=[],
    )

    assert result["status"] == "INCOMPLETE"
    assert result["unresolved_required_function_ids"] == ["RETRIEVE"]


def test_observed_but_not_reproduced_required_function_remains_unresolved() -> None:
    result = evaluate_environment_coverage(
        environment_id="computer-core",
        environment_reference="computer-core@checked-state",
        required_function_ids=["STORE", "RETRIEVE"],
        observed_function_ids=["STORE", "RETRIEVE"],
        reproduced_function_ids=["STORE"],
        unchecked_boundaries=[],
    )

    assert result["status"] == "INCOMPLETE"
    assert result["unresolved_required_function_ids"] == ["RETRIEVE"]
    assert result["observed_not_reproduced_function_ids"] == ["RETRIEVE"]


def test_unchecked_boundary_blocks_completion_after_functions_are_covered() -> None:
    result = evaluate_environment_coverage(
        environment_id="computer-core",
        environment_reference="computer-core@checked-state",
        required_function_ids=["STORE"],
        observed_function_ids=["STORE"],
        reproduced_function_ids=["STORE"],
        unchecked_boundaries=[
            {
                "id": "external-device-layer",
                "reason": "accessible but not yet examined",
            }
        ],
    )

    assert result["status"] == "BLOCKED"
    assert result["unresolved_required_function_ids"] == []
    assert result["unchecked_boundaries"][0]["id"] == "external-device-layer"


def test_unresolved_required_function_takes_precedence_over_boundary_block() -> None:
    result = evaluate_environment_coverage(
        environment_id="computer-core",
        environment_reference="computer-core@checked-state",
        required_function_ids=["STORE", "RETRIEVE"],
        observed_function_ids=["STORE"],
        reproduced_function_ids=["STORE"],
        unchecked_boundaries=[{"id": "external-device-layer"}],
    )

    assert result["status"] == "INCOMPLETE"


def test_observed_function_outside_required_scope_is_preserved_not_promoted() -> None:
    result = evaluate_environment_coverage(
        environment_id="computer-core",
        environment_reference="computer-core@checked-state",
        required_function_ids=["STORE"],
        observed_function_ids=["STORE", "SIGNAL"],
        reproduced_function_ids=["STORE"],
        unchecked_boundaries=[],
    )

    assert result["status"] == "COMPLETE_AT_BOUNDARY"
    assert result["observed_outside_required_scope"] == ["SIGNAL"]


def test_reproduced_function_must_be_observed() -> None:
    with pytest.raises(
        EnvironmentCoverageError,
        match="reproduced functions must also be present",
    ):
        evaluate_environment_coverage(
            environment_id="computer-core",
            environment_reference="computer-core@checked-state",
            required_function_ids=["STORE"],
            observed_function_ids=[],
            reproduced_function_ids=["STORE"],
            unchecked_boundaries=[],
        )


def test_duplicate_function_ids_fail_closed() -> None:
    with pytest.raises(EnvironmentCoverageError, match="duplicate required_function_id"):
        evaluate_environment_coverage(
            environment_id="computer-core",
            environment_reference="computer-core@checked-state",
            required_function_ids=["STORE", "STORE"],
            observed_function_ids=["STORE"],
            reproduced_function_ids=["STORE"],
            unchecked_boundaries=[],
        )


def test_duplicate_unchecked_boundaries_fail_closed() -> None:
    with pytest.raises(
        EnvironmentCoverageError,
        match="duplicate unchecked boundary id",
    ):
        evaluate_environment_coverage(
            environment_id="computer-core",
            environment_reference="computer-core@checked-state",
            required_function_ids=["STORE"],
            observed_function_ids=["STORE"],
            reproduced_function_ids=["STORE"],
            unchecked_boundaries=[{"id": "layer-a"}, {"id": "layer-a"}],
        )


def test_hash_is_deterministic() -> None:
    kwargs = {
        "environment_id": "computer-core",
        "environment_reference": "computer-core@checked-state",
        "required_function_ids": ["STORE", "RETRIEVE"],
        "observed_function_ids": ["STORE", "RETRIEVE"],
        "reproduced_function_ids": ["STORE", "RETRIEVE"],
        "unchecked_boundaries": [],
    }

    first = evaluate_environment_coverage(**kwargs)
    second = evaluate_environment_coverage(**kwargs)

    assert first == second
    assert len(first["coverage_hash"]) == 64
