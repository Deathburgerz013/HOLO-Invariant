import pytest

from holosim.environment_invariant_receipts import (
    evaluate_environment_invariant,
)
from holosim.invariant_failure_extraction import (
    InvariantFailureExtractionError,
    extract_invariant_failure,
    verify_invariant_failure_extraction,
)


def _failed_receipt():
    environment = {"value": 7}

    return evaluate_environment_invariant(
        invariant_id="value-must-be-8",
        statement="the observed value is 8",
        scope={"phase": "test"},
        environment=environment,
        environment_probe=lambda: environment,
        check=lambda: False,
        check_id="value-check",
        observed_at="2026-09-21T21:00:00-07:00",
    )


def _held_receipt():
    environment = {"value": 8}

    return evaluate_environment_invariant(
        invariant_id="value-must-be-8",
        statement="the observed value is 8",
        scope={"phase": "test"},
        environment=environment,
        environment_probe=lambda: environment,
        check=lambda: True,
        check_id="value-check",
        observed_at="2026-09-21T21:00:00-07:00",
    )


def test_extracts_environment_invariant_failure():
    receipt = _failed_receipt()

    failure = extract_invariant_failure(receipt)

    assert failure["status"] == "DEMONSTRATED_FAILURE"
    assert failure["invariant_id"] == "value-must-be-8"
    assert failure["source_receipt_hash"] == receipt["receipt_hash"]


def test_failed_invariant_does_not_claim_truth():
    failure = extract_invariant_failure(_failed_receipt())

    assert failure["truth_claimed"] is False
    assert failure["accepted"] is False
    assert failure["write_authority"] == "NONE"
    assert failure["execution_authority"] == "NONE"


def test_held_invariant_is_not_extracted_as_failure():
    with pytest.raises(InvariantFailureExtractionError, match="not FAILED"):
        extract_invariant_failure(_held_receipt())


def test_failure_preserves_environment_identity():
    receipt = _failed_receipt()
    failure = extract_invariant_failure(receipt)

    assert failure["declared_environment_fingerprint"] == (
        receipt["declared_environment_fingerprint"]
    )
    assert failure["observed_environment"] == receipt["observed_environment"]
    assert failure["environment_fingerprint"] == receipt["environment_fingerprint"]


def test_failure_preserves_source_provenance():
    receipt = _failed_receipt()
    failure = extract_invariant_failure(receipt)

    assert failure["source_receipt_hash"] == receipt["receipt_hash"]
    assert failure["invariant_id"] == receipt["invariant_id"]
    assert failure["check_id"] == receipt["check_id"]
    assert failure["observed_at"] == receipt["observed_at"]


def test_tampered_failure_fails_verification():
    receipt = _failed_receipt()
    failure = extract_invariant_failure(receipt)

    failure["statement"] = "invented statement"

    with pytest.raises(InvariantFailureExtractionError):
        verify_invariant_failure_extraction(
            failure,
            invariant_receipt=receipt,
        )


def test_verifier_rebuilds_exact_failure():
    receipt = _failed_receipt()
    failure = extract_invariant_failure(receipt)

    assert verify_invariant_failure_extraction(
        failure,
        invariant_receipt=receipt,
    )


def test_stale_invariant_is_not_extracted_as_failure():
    environment = {"value": 7}

    receipt = evaluate_environment_invariant(
        invariant_id="value-must-be-8",
        statement="the observed value is 8",
        scope={"phase": "test"},
        environment={"value": 8},
        environment_probe=lambda: environment,
        check=lambda: False,
        check_id="value-check",
        observed_at="2026-09-21T21:00:00-07:00",
    )

    assert receipt["status"] == "STALE"

    with pytest.raises(InvariantFailureExtractionError, match="not FAILED"):
        extract_invariant_failure(receipt)

def test_extracted_failure_propagates_source_change_to_recheck():
    from holosim.receipt_graph import (
        RECHECK_REQUIRED,
        build_receipt_graph,
        plan_dependency_rechecks,
    )

    source = _failed_receipt()
    failure = extract_invariant_failure(source)

    graph = build_receipt_graph([source, failure])
    plan = plan_dependency_rechecks(graph, [source["receipt_hash"]])

    statuses = {
        item["receipt_hash"]: item["status"]
        for item in plan["results"]
    }

    assert statuses[source["receipt_hash"]] == RECHECK_REQUIRED
    assert statuses[failure["receipt_hash"]] == RECHECK_REQUIRED

    failure_result = next(
        item
        for item in plan["results"]
        if item["receipt_hash"] == failure["receipt_hash"]
    )

    assert failure_result["trigger_paths"] == [[
        source["receipt_hash"],
        failure["receipt_hash"],
    ]]
