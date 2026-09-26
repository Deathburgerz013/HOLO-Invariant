from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.environment_reopen_condition import (
    EnvironmentReopenConditionError,
    evaluate_environment_reopen_condition,
    verify_environment_reopen_condition_receipt,
)
from holosim.environment_snapshot import build_snapshot
from holosim.environment_snapshot_comparator import compare_snapshots
from holosim.environment_snapshot_comparison_identity import (
    build_environment_snapshot_comparison_check_identity,
)
from holosim.hook_contract import build_hook_request, build_hook_result


def _snapshot(*, observed_at: str, temperature: int, evidence: str):
    return build_snapshot(
        episode_id="episode-1",
        environment_id="env-1",
        check_id=f"check-{observed_at}",
        check_purpose="observe bounded environment state",
        goal_reference="goal-1",
        observer_ids=["observer-1"],
        clock_id="clock-1",
        observed_at=observed_at,
        feature_schema_id="schema-1",
        observed={"temperature": temperature},
        missing=[],
        unknown=[],
        assumptions=[],
        falsifiers=["temperature differs"],
        evidence_sha256=[evidence],
        provenance={"source": "fixture"},
        uncertainty=[],
    )


def _inputs(*, satisfied=True, status="OBSERVED"):
    before = _snapshot(
        observed_at="2026-07-21T12:00:00+00:00",
        temperature=42,
        evidence="a" * 64,
    )
    after = _snapshot(
        observed_at="2026-07-21T13:00:00+00:00",
        temperature=43,
        evidence="b" * 64,
    )
    comparison = compare_snapshots(before, after)
    identity = build_environment_snapshot_comparison_check_identity(comparison)
    request = build_hook_request(
        hook_id="reopen-condition-hook-1",
        action="verify-reopen-condition",
        reference="condition-temperature-changed",
        payload={
            "comparison_check_identity_hash": identity["check_identity_hash"],
        },
    )
    evidence = {"condition_satisfied": satisfied} if status == "OBSERVED" else {}
    result = build_hook_result(
        request=request,
        status=status,
        evidence=evidence,
    )
    return identity, request, result


def _evaluate(*, satisfied=True, status="OBSERVED"):
    identity, request, result = _inputs(satisfied=satisfied, status=status)
    return evaluate_environment_reopen_condition(
        condition_id="condition-temperature-changed",
        comparison_identity=identity,
        request=request,
        result=result,
    )


def test_observed_true_condition_is_satisfied_without_authority():
    receipt = _evaluate(satisfied=True)
    assert receipt["outcome"] == "SATISFIED"
    assert receipt["reopen_authorized"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"


def test_observed_false_condition_is_not_satisfied():
    assert _evaluate(satisfied=False)["outcome"] == "NOT_SATISFIED"


@pytest.mark.parametrize("status", ["FAILED", "UNAVAILABLE"])
def test_missing_verification_remains_unknown(status):
    assert _evaluate(status=status)["outcome"] == "UNKNOWN"


def test_wrong_condition_reference_fails_closed():
    identity, request, result = _inputs()
    with pytest.raises(EnvironmentReopenConditionError, match="wrong condition"):
        evaluate_environment_reopen_condition(
            condition_id="different-condition",
            comparison_identity=identity,
            request=request,
            result=result,
        )


def test_wrong_action_fails_closed():
    identity, _, _ = _inputs()
    request = build_hook_request(
        hook_id="reopen-condition-hook-1",
        action="something-else",
        reference="condition-temperature-changed",
        payload={"comparison_check_identity_hash": identity["check_identity_hash"]},
    )
    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"condition_satisfied": True},
    )
    with pytest.raises(EnvironmentReopenConditionError, match="wrong action"):
        evaluate_environment_reopen_condition(
            condition_id="condition-temperature-changed",
            comparison_identity=identity,
            request=request,
            result=result,
        )


def test_request_bound_to_different_comparison_fails_closed():
    identity, _, _ = _inputs()
    request = build_hook_request(
        hook_id="reopen-condition-hook-1",
        action="verify-reopen-condition",
        reference="condition-temperature-changed",
        payload={"comparison_check_identity_hash": "f" * 64},
    )
    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"condition_satisfied": True},
    )
    with pytest.raises(EnvironmentReopenConditionError, match="different comparison evidence"):
        evaluate_environment_reopen_condition(
            condition_id="condition-temperature-changed",
            comparison_identity=identity,
            request=request,
            result=result,
        )


def test_observed_result_requires_exact_boolean_evidence():
    identity, request, _ = _inputs()
    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"condition_satisfied": "yes"},
    )
    with pytest.raises(EnvironmentReopenConditionError, match="must be a boolean"):
        evaluate_environment_reopen_condition(
            condition_id="condition-temperature-changed",
            comparison_identity=identity,
            request=request,
            result=result,
        )


def test_tampered_comparison_identity_fails_closed_even_when_field_is_present():
    identity, request, result = _inputs()
    tampered = deepcopy(identity)
    tampered["subject"]["environment_id"] = "other-env"
    with pytest.raises(EnvironmentReopenConditionError, match="identity hash mismatch"):
        evaluate_environment_reopen_condition(
            condition_id="condition-temperature-changed",
            comparison_identity=tampered,
            request=request,
            result=result,
        )


def test_receipt_hash_commits_to_entire_receipt_body():
    receipt = _evaluate()
    body = dict(receipt)
    supplied = body.pop("receipt_hash")
    assert supplied == stable_hash(body)


def test_reopen_condition_receipt_verifies_against_exact_evidence():
    identity, request, result = _inputs()
    receipt = evaluate_environment_reopen_condition(
        condition_id="condition-temperature-changed",
        comparison_identity=identity,
        request=request,
        result=result,
    )
    assert verify_environment_reopen_condition_receipt(
        receipt,
        condition_id="condition-temperature-changed",
        comparison_identity=identity,
        request=request,
        result=result,
    ) is True


def test_rehashed_semantic_tamper_is_rejected_by_regeneration():
    identity, request, result = _inputs()
    receipt = evaluate_environment_reopen_condition(
        condition_id="condition-temperature-changed",
        comparison_identity=identity,
        request=request,
        result=result,
    )
    tampered = deepcopy(receipt)
    tampered["outcome"] = "NOT_SATISFIED"
    body = dict(tampered)
    body.pop("receipt_hash")
    tampered["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        EnvironmentReopenConditionError,
        match="does not match supplied evidence",
    ):
        verify_environment_reopen_condition_receipt(
            tampered,
            condition_id="condition-temperature-changed",
            comparison_identity=identity,
            request=request,
            result=result,
        )


def test_foreign_receipt_field_is_rejected_even_when_rehashed():
    identity, request, result = _inputs()
    receipt = evaluate_environment_reopen_condition(
        condition_id="condition-temperature-changed",
        comparison_identity=identity,
        request=request,
        result=result,
    )
    forged = deepcopy(receipt)
    forged["approval"] = "GRANTED"
    body = dict(forged)
    body.pop("receipt_hash")
    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        EnvironmentReopenConditionError,
        match="fields do not match",
    ):
        verify_environment_reopen_condition_receipt(
            forged,
            condition_id="condition-temperature-changed",
            comparison_identity=identity,
            request=request,
            result=result,
        )


def test_receipt_cannot_verify_against_different_result_evidence():
    identity, request, result = _inputs(satisfied=True)
    receipt = evaluate_environment_reopen_condition(
        condition_id="condition-temperature-changed",
        comparison_identity=identity,
        request=request,
        result=result,
    )
    different_result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"condition_satisfied": False},
    )

    with pytest.raises(
        EnvironmentReopenConditionError,
        match="does not match supplied evidence",
    ):
        verify_environment_reopen_condition_receipt(
            receipt,
            condition_id="condition-temperature-changed",
            comparison_identity=identity,
            request=request,
            result=different_result,
        )
