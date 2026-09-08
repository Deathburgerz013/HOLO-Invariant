from __future__ import annotations

from holosim.next_check_organizer import organize_next_checks


def _record(*, conditions: list[str], residual: list[str]) -> dict:
    return {
        "idx": 1,
        "entry_hash": "hash-1",
        "claim": "A bounded claim still has unresolved uncertainty",
        "status": "open",
        "resolution_conditions": conditions,
        "residual_uncertainty": residual,
        "source_refs": ["source-1"],
    }


def test_missing_resolution_condition_is_distinguished_from_runnable_check():
    with_check = organize_next_checks(
        [_record(
            conditions=["Reproduce the observation independently"],
            residual=["Independent reproduction has not been performed"],
        )]
    )
    without_check = organize_next_checks(
        [_record(
            conditions=[],
            residual=["No falsifiable resolution condition has been established"],
        )]
    )

    assert len(with_check["candidate_checks"]) == 1
    candidate = with_check["candidate_checks"][0]
    assert candidate["routing_status"] == "DECLARED_CHECK_AVAILABLE"
    assert candidate["invented"] is False
    assert candidate["execution_authorized"] is False

    assert without_check["candidate_checks"] == []
    assert len(without_check["unresolved_without_declared_check"]) == 1
    missing = without_check["unresolved_without_declared_check"][0]
    assert missing["routing_status"] == "RESOLUTION_CONDITION_REQUIRED"
    assert missing["condition_invented"] is False
    assert missing["execution_authorized"] is False
    assert missing["truth_claimed"] is False
    assert missing["accepted"] is False
    assert missing["write_authority"] == "NONE"
