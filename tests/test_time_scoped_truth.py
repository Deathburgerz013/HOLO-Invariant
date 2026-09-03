from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.time_scoped_truth import (
    TimeScopedTruthError,
    build_time_scoped_truth_receipt,
    compare_time_scoped_truth_receipts,
    verify_time_scoped_truth_comparison,
    verify_time_scoped_truth_receipt,
)


def _check(check_id="license", outcome="SUPPORTS", status="VERIFIED"):
    return {
        "check_id": check_id,
        "check_type": "EVIDENCE",
        "verification_receipt_hash": stable_hash({"check": check_id, "outcome": outcome}),
        "verification_status": status,
        "outcome": outcome,
    }


def _inputs(*, outcome="SUPPORTS", temporal_scope="AT_OBSERVATION", observed_at="2026-09-03T10:00:00-07:00"):
    return {
        "claim": {
            "claim_id": "holo.free",
            "statement": "HOLO is free under the observed repository terms",
            "temporal_scope": temporal_scope,
        },
        "observation": {
            "observation_id": f"repo.{stable_hash(observed_at)[:16]}",
            "environment_id": "github.holo-invariant",
            "observed_at": observed_at,
            "clock_id": "operator.clock",
            "state_hash": stable_hash({"state": observed_at}),
        },
        "checks": [_check(outcome=outcome)],
    }


def _receipt(**kwargs):
    return build_time_scoped_truth_receipt(**_inputs(**kwargs))


def test_verified_support_establishes_true_only_at_observation() -> None:
    receipt = _receipt()
    assert receipt["truth_status"] == "TRUE"
    assert receipt["bounded_truth_established"] is True
    assert receipt["global_truth_claimed"] is False
    assert receipt["future_truth_claimed"] is False
    assert verify_time_scoped_truth_receipt(receipt) is True


def test_verified_contradiction_establishes_false_only_at_observation() -> None:
    receipt = _receipt(outcome="CONTRADICTS")
    assert receipt["truth_status"] == "FALSE"
    assert receipt["bounded_truth_established"] is True


def test_unbounded_future_claim_is_unknown_even_with_present_support() -> None:
    receipt = _receipt(temporal_scope="UNBOUNDED_FUTURE")
    assert receipt["truth_status"] == "UNKNOWN"
    assert receipt["status_reason"] == "UNBOUNDED_FUTURE_NOT_OBSERVED"
    assert receipt["bounded_truth_established"] is False


def test_unavailable_check_keeps_truth_unknown() -> None:
    inputs = _inputs()
    inputs["checks"] = [_check(outcome="UNKNOWN", status="UNAVAILABLE")]
    receipt = build_time_scoped_truth_receipt(**inputs)
    assert receipt["truth_status"] == "UNKNOWN"
    assert receipt["status_reason"] == "UNRESOLVED_CHECKS_REMAIN"


def test_conflicting_verified_checks_keep_truth_unknown() -> None:
    inputs = _inputs()
    inputs["checks"] = [
        _check("support", "SUPPORTS"),
        _check("contradiction", "CONTRADICTS"),
    ]
    receipt = build_time_scoped_truth_receipt(**inputs)
    assert receipt["truth_status"] == "UNKNOWN"
    assert receipt["status_reason"] == "CONFLICTING_VERIFIED_CHECKS"


def test_unverified_directional_outcome_is_rejected() -> None:
    inputs = _inputs()
    inputs["checks"] = [_check(status="INVALID")]
    with pytest.raises(TimeScopedTruthError, match="UNKNOWN outcome"):
        build_time_scoped_truth_receipt(**inputs)


def test_formal_proof_can_support_bounded_truth() -> None:
    inputs = _inputs()
    inputs["claim"] = {
        "claim_id": "math.even",
        "statement": "two plus two is even under the declared arithmetic system",
        "temporal_scope": "AT_OBSERVATION",
    }
    inputs["checks"][0]["check_type"] = "FORMAL_PROOF"
    receipt = build_time_scoped_truth_receipt(**inputs)
    assert receipt["truth_status"] == "TRUE"
    assert receipt["checks"][0]["check_type"] == "FORMAL_PROOF"


def test_timestamp_requires_timezone() -> None:
    inputs = _inputs(observed_at="2026-09-03T10:00:00")
    with pytest.raises(TimeScopedTruthError, match="timezone"):
        build_time_scoped_truth_receipt(**inputs)


def test_receipt_is_deterministic_under_check_reordering() -> None:
    inputs = _inputs()
    inputs["checks"] = [_check("a", "SUPPORTS"), _check("b", "SUPPORTS")]
    reversed_inputs = deepcopy(inputs)
    reversed_inputs["checks"].reverse()
    assert build_time_scoped_truth_receipt(**inputs) == (
        build_time_scoped_truth_receipt(**reversed_inputs)
    )


def test_changed_later_truth_preserves_prior_receipt() -> None:
    prior = _receipt()
    original = deepcopy(prior)
    current = _receipt(
        outcome="CONTRADICTS",
        observed_at="2027-09-03T10:00:00-07:00",
    )
    comparison = compare_time_scoped_truth_receipts(prior, current)
    assert comparison["prior_truth_status"] == "TRUE"
    assert comparison["current_truth_status"] == "FALSE"
    assert comparison["relation"] == "CHANGED"
    assert comparison["historical_rewritten"] is False
    assert prior == original
    assert verify_time_scoped_truth_comparison(comparison) is True


def test_same_later_truth_is_preserved_relation() -> None:
    prior = _receipt()
    current = _receipt(observed_at="2027-09-03T10:00:00-07:00")
    comparison = compare_time_scoped_truth_receipts(prior, current)
    assert comparison["relation"] == "PRESERVED"


def test_comparison_rejects_different_claims() -> None:
    prior = _receipt()
    current = _receipt(observed_at="2027-09-03T10:00:00-07:00")
    current_inputs = _inputs(observed_at="2027-09-03T10:00:00-07:00")
    current_inputs["claim"]["claim_id"] = "different"
    current = build_time_scoped_truth_receipt(**current_inputs)
    with pytest.raises(TimeScopedTruthError, match="same claim_id"):
        compare_time_scoped_truth_receipts(prior, current)


def test_comparison_rejects_reverse_time() -> None:
    prior = _receipt(observed_at="2027-09-03T10:00:00-07:00")
    current = _receipt(observed_at="2026-09-03T10:00:00-07:00")
    with pytest.raises(TimeScopedTruthError, match="cannot precede"):
        compare_time_scoped_truth_receipts(prior, current)


def test_truth_receipt_hash_tampering_is_rejected() -> None:
    receipt = _receipt()
    receipt["truth_status"] = "FALSE"
    with pytest.raises(TimeScopedTruthError, match="hash mismatch"):
        verify_time_scoped_truth_receipt(receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("truth_status", "FALSE"),
        ("bounded_truth_established", False),
        ("global_truth_claimed", True),
        ("future_truth_claimed", True),
        ("accepted", True),
        ("write_authority", "MODEL"),
    ],
)
def test_rehashed_truth_semantic_forgery_is_rejected(field, value) -> None:
    receipt = _receipt()
    receipt[field] = value
    body = {key: item for key, item in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)
    with pytest.raises(TimeScopedTruthError, match="internally inconsistent"):
        verify_time_scoped_truth_receipt(receipt)


def test_rehashed_comparison_change_forgery_is_rejected() -> None:
    prior = _receipt()
    current = _receipt(observed_at="2027-09-03T10:00:00-07:00")
    comparison = compare_time_scoped_truth_receipts(prior, current)
    comparison["relation"] = "CHANGED"
    body = {key: item for key, item in comparison.items() if key != "receipt_hash"}
    comparison["receipt_hash"] = stable_hash(body)
    with pytest.raises(TimeScopedTruthError, match="relation is inconsistent"):
        verify_time_scoped_truth_comparison(comparison)
