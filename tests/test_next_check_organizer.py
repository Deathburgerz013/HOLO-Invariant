from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.next_check_organizer import (
    NextCheckOrganizerError,
    organize_next_checks,
)


def _record(
    *,
    idx: int,
    claim: str,
    status: str,
    conditions: list[str],
    residual: list[str] | None = None,
) -> dict:
    return {
        "idx": idx,
        "entry_hash": f"hash-{idx}",
        "claim": claim,
        "status": status,
        "resolution_conditions": conditions,
        "residual_uncertainty": residual or [],
        "source_refs": [f"source-{idx}"],
    }


def test_organizer_surfaces_only_declared_checks_in_source_order():
    records = [
        _record(
            idx=1,
            claim="Claim A",
            status="bounded",
            conditions=["Run verifier A", "Compare source A"],
            residual=["Replay not yet checked"],
        ),
        _record(
            idx=2,
            claim="Claim B",
            status="contradicted",
            conditions=["Reproduce contradiction B"],
        ),
    ]

    result = organize_next_checks(records)

    assert [
        item["condition"] for item in result["candidate_checks"]
    ] == [
        "Run verifier A",
        "Compare source A",
        "Reproduce contradiction B",
    ]
    assert [
        item["source"]["idx"] for item in result["candidate_checks"]
    ] == [1, 1, 2]
    assert all(item["invented"] is False for item in result["candidate_checks"])


def test_resolved_records_do_not_emit_next_checks():
    result = organize_next_checks(
        [
            _record(
                idx=1,
                claim="Resolved claim",
                status="resolved",
                conditions=["Old check that should not be routed"],
            )
        ]
    )

    assert result["candidate_checks"] == []
    assert [item["idx"] for item in result["ignored_terminal_records"]] == [1]


def test_active_record_without_declared_condition_is_reported_not_invented():
    result = organize_next_checks(
        [
            _record(
                idx=1,
                claim="Unresolved claim",
                status="open",
                conditions=[],
                residual=["Need a method"],
            )
        ]
    )

    assert result["candidate_checks"] == []
    assert result["conditions_invented"] is False
    assert result["unresolved_without_declared_check"][0]["idx"] == 1
    assert result["unresolved_without_declared_check"][0][
        "residual_uncertainty"
    ] == ["Need a method"]


def test_organizer_is_read_only_and_deterministic():
    records = [
        _record(
            idx=1,
            claim="Stable claim",
            status="reduced",
            conditions=["Perform the remaining check"],
        )
    ]
    before = deepcopy(records)

    first = organize_next_checks(records)
    second = organize_next_checks(records)

    assert records == before
    assert first == second
    assert first["organizer_id"] == second["organizer_id"]
    assert first["candidate_checks"][0]["candidate_id"] == second[
        "candidate_checks"
    ][0]["candidate_id"]


def test_organizer_grants_no_authority_or_truth():
    result = organize_next_checks(
        [
            _record(
                idx=1,
                claim="Claim",
                status="open",
                conditions=["Check it"],
            )
        ]
    )

    assert result["execution_authorized"] is False
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"

    candidate = result["candidate_checks"][0]
    assert candidate["execution_authorized"] is False
    assert candidate["truth_claimed"] is False
    assert candidate["accepted"] is False
    assert candidate["write_authority"] == "NONE"


def test_unknown_status_fails_closed():
    with pytest.raises(NextCheckOrganizerError):
        organize_next_checks(
            [
                _record(
                    idx=1,
                    claim="Claim",
                    status="mystery",
                    conditions=["Check it"],
                )
            ]
        )
