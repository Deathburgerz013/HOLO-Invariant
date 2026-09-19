import copy

import pytest

from holosim.residual_next_check_routing import (
    ResidualNextCheckRoutingError,
    route_unresolved_residual,
)


def _residual():
    return {
        "fact_id": "fact:population",
        "finding_ids": ["finding:a", "finding:b"],
        "status": "UNRESOLVED",
        "reason": "AT_LEAST_ONE_SCOPE_UNRESOLVED",
        "statements": [
            "population is 8 billion",
            "population is 9 billion",
        ],
        "scope_results": [
            {
                "scope": "global",
                "status": "UNRESOLVED",
                "reason": "STATEMENT_IDENTITY_CONFLICT_WITHIN_SCOPE",
                "statements": [
                    "population is 8 billion",
                    "population is 9 billion",
                ],
                "observations": [
                    {
                        "finding_id": "finding:a",
                        "statement": "population is 8 billion",
                        "scope": "global",
                        "status": "SUPPORTED",
                        "analysis_id": "analysis:a",
                        "analysis_receipt_hash": "a" * 64,
                        "evidence_set_hash": "1" * 64,
                    },
                    {
                        "finding_id": "finding:b",
                        "statement": "population is 9 billion",
                        "scope": "global",
                        "status": "SUPPORTED",
                        "analysis_id": "analysis:b",
                        "analysis_receipt_hash": "b" * 64,
                        "evidence_set_hash": "2" * 64,
                    },
                ],
            }
        ],
    }


def test_without_declared_condition_stops_without_invention():
    residual = _residual()

    result = route_unresolved_residual(
        residual=residual,
        resolution_conditions=[],
    )

    assert result["routing_status"] == "RESOLUTION_CONDITION_REQUIRED"
    assert result["candidate_checks"] == []
    assert result["source_residual"] == residual
    assert result["conditions_invented"] is False
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["execution_authorized"] is False
    assert result["state_change_authorized"] is False
    assert result["write_authority"] == "NONE"


def test_declared_condition_routes_without_authority():
    residual = _residual()

    result = route_unresolved_residual(
        residual=residual,
        resolution_conditions=["Perform declared independent recheck"],
    )

    assert result["routing_status"] == "DECLARED_CHECK_AVAILABLE"
    assert result["source_residual"] == residual
    assert result["candidate_checks"] == [
        {
            "condition": "Perform declared independent recheck",
            "condition_index": 0,
            "invented": False,
            "execution_authorized": False,
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "NONE",
        }
    ]


def test_non_unresolved_residual_fails_closed():
    residual = _residual()
    residual["status"] = "SUPPORTED"

    with pytest.raises(
        ResidualNextCheckRoutingError,
        match="unresolved convergence status",
    ):
        route_unresolved_residual(
            residual=residual,
            resolution_conditions=["Recheck it"],
        )


def test_malformed_unresolved_residual_fails_closed():
    with pytest.raises(ResidualNextCheckRoutingError):
        route_unresolved_residual(
            residual={"status": "UNRESOLVED"},
            resolution_conditions=["Perform declared recheck"],
        )


def test_malformed_nested_observation_fails_closed():
    residual = _residual()
    del residual["scope_results"][0]["observations"][0][
        "analysis_receipt_hash"
    ]

    with pytest.raises(
        ResidualNextCheckRoutingError,
        match="analysis_receipt_hash",
    ):
        route_unresolved_residual(
            residual=residual,
            resolution_conditions=["Perform declared recheck"],
        )


def test_observation_scope_mismatch_fails_closed():
    residual = _residual()
    residual["scope_results"][0]["observations"][0]["scope"] = "other"

    with pytest.raises(
        ResidualNextCheckRoutingError,
        match="scope must match",
    ):
        route_unresolved_residual(
            residual=residual,
            resolution_conditions=["Perform declared recheck"],
        )


def test_nested_observation_identity_is_preserved_exactly():
    residual = _residual()

    result = route_unresolved_residual(
        residual=residual,
        resolution_conditions=["Perform declared recheck"],
    )

    assert (
        result["source_residual"]["scope_results"][0]["observations"]
        == residual["scope_results"][0]["observations"]
    )


def test_source_and_result_are_isolated_in_both_directions():
    residual = _residual()
    original = copy.deepcopy(residual)

    result = route_unresolved_residual(
        residual=residual,
        resolution_conditions=["Perform declared recheck"],
    )

    residual["statements"][0] = "mutated source"
    assert result["source_residual"] == original

    result["source_residual"]["statements"][0] = "mutated result"
    assert residual["statements"][0] == "mutated source"


def test_same_input_has_same_routing_identity():
    residual = _residual()

    first = route_unresolved_residual(
        residual=residual,
        resolution_conditions=["Perform declared recheck"],
    )
    second = route_unresolved_residual(
        residual=residual,
        resolution_conditions=["Perform declared recheck"],
    )

    assert first == second
    assert first["routing_id"] == second["routing_id"]


def test_changed_condition_changes_routing_identity():
    residual = _residual()

    first = route_unresolved_residual(
        residual=residual,
        resolution_conditions=["Perform declared recheck A"],
    )
    second = route_unresolved_residual(
        residual=residual,
        resolution_conditions=["Perform declared recheck B"],
    )

    assert first["source_residual"] == second["source_residual"]
    assert first["routing_id"] != second["routing_id"]


def test_condition_text_must_be_nonempty():
    with pytest.raises(
        ResidualNextCheckRoutingError,
        match=r"resolution_conditions\[0\]",
    ):
        route_unresolved_residual(
            residual=_residual(),
            resolution_conditions=["   "],
        )
