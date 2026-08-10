from copy import deepcopy

import pytest

from holosim.baseline_observation_compare import (
    FINDING_CORRECTION,
    FINDING_SUPPORT,
    FINDING_UNKNOWN,
)
from holosim.baseline_promotion_gate import (
    STATUS_CONFLICTED,
    STATUS_INSUFFICIENT,
    STATUS_JUSTIFIED_TO_PROPOSE,
)
from holosim.canonical import stable_hash
from holosim.computer_observer import execute_observation
from holosim.evidence_bound_baseline_observation import (
    EvidenceBoundBaselineError,
    build_evidence_bound_baseline_observation,
    compare_evidence_bound_baseline_observations,
    evaluate_evidence_bound_baseline_promotion,
    validate_evidence_bound_baseline_observation,
)
from holosim.hook_contract import build_hook_request


def _observe(tmp_path, *, hook_id, reference, content):
    (tmp_path / reference).write_text(content, encoding="utf-8")
    request = build_hook_request(
        hook_id=hook_id,
        action="read_text",
        reference=reference,
        payload={"encoding": "utf-8"},
    )
    result = execute_observation(request=request, allowed_root=tmp_path)
    return request, result


def _bound(
    tmp_path,
    *,
    observer_id,
    hook_id,
    reference,
    content,
    finding=FINDING_CORRECTION,
):
    request, result = _observe(
        tmp_path,
        hook_id=hook_id,
        reference=reference,
        content=content,
    )
    return build_evidence_bound_baseline_observation(
        observer_id=observer_id,
        baseline_id="baseline-1",
        baseline_state_hash="state-1",
        findings={"claim-a": finding},
        request=request,
        observation_result=result,
    )


def test_observation_binds_finding_to_exact_executed_evidence(tmp_path):
    bound = _bound(
        tmp_path,
        observer_id="observer-a",
        hook_id="source-a",
        reference="a.txt",
        content="witness A",
    )

    assert bound["observation_result"]["status"] == "OBSERVED"
    assert bound["evidence_result_hash"] == bound["observation_result"][
        "result_hash"
    ]
    assert bound["observation"]["findings"] == {
        "claim-a": FINDING_CORRECTION
    }
    assert bound["truth_claimed"] is False
    assert bound["accepted"] is False
    assert bound["write_authority"] == "NONE"
    assert validate_evidence_bound_baseline_observation(bound) is True


def test_same_evidence_cannot_pose_as_two_independent_observers(tmp_path):
    first = _bound(
        tmp_path,
        observer_id="observer-a",
        hook_id="source-a",
        reference="a.txt",
        content="one witness",
    )
    alias = build_evidence_bound_baseline_observation(
        observer_id="observer-b",
        baseline_id="baseline-1",
        baseline_state_hash="state-1",
        findings={"claim-a": FINDING_CORRECTION},
        request=first["request"],
        observation_result=first["observation_result"],
    )

    with pytest.raises(EvidenceBoundBaselineError, match="distinct evidence"):
        compare_evidence_bound_baseline_observations(first, alias)


def test_two_distinct_evidence_receipts_can_justify_proposal(tmp_path):
    left = _bound(
        tmp_path,
        observer_id="observer-a",
        hook_id="source-a",
        reference="a.txt",
        content="first independent witness",
    )
    right = _bound(
        tmp_path,
        observer_id="observer-b",
        hook_id="source-b",
        reference="b.txt",
        content="second independent witness",
    )

    comparison = compare_evidence_bound_baseline_observations(left, right)
    result = evaluate_evidence_bound_baseline_promotion(comparison=comparison)

    assert result["gate"]["status"] == STATUS_JUSTIFIED_TO_PROPOSE
    assert result["evidence_result_hashes"] == sorted(
        [left["evidence_result_hash"], right["evidence_result_hash"]]
    )
    assert result["candidate_next_baseline_created"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_conflict_remains_blocking_with_bound_evidence(tmp_path):
    left = _bound(
        tmp_path,
        observer_id="observer-a",
        hook_id="source-a",
        reference="a.txt",
        content="support witness",
        finding=FINDING_SUPPORT,
    )
    right = _bound(
        tmp_path,
        observer_id="observer-b",
        hook_id="source-b",
        reference="b.txt",
        content="correction witness",
    )

    comparison = compare_evidence_bound_baseline_observations(left, right)
    result = evaluate_evidence_bound_baseline_promotion(comparison=comparison)

    assert result["gate"]["status"] == STATUS_CONFLICTED


def test_unknown_evidence_remains_insufficient(tmp_path):
    left = _bound(
        tmp_path,
        observer_id="observer-a",
        hook_id="source-a",
        reference="a.txt",
        content="unknown witness",
        finding=FINDING_UNKNOWN,
    )
    right = _bound(
        tmp_path,
        observer_id="observer-b",
        hook_id="source-b",
        reference="b.txt",
        content="support witness",
        finding=FINDING_SUPPORT,
    )

    comparison = compare_evidence_bound_baseline_observations(left, right)
    result = evaluate_evidence_bound_baseline_promotion(comparison=comparison)

    assert result["gate"]["status"] == STATUS_INSUFFICIENT


def test_rehashed_undeclared_authority_field_is_rejected(tmp_path):
    bound = deepcopy(
        _bound(
            tmp_path,
            observer_id="observer-a",
            hook_id="source-a",
            reference="a.txt",
            content="witness",
        )
    )
    bound["approval"] = "GRANTED"
    body = dict(bound)
    body.pop("binding_hash")
    bound["binding_hash"] = stable_hash(body)

    with pytest.raises(EvidenceBoundBaselineError, match="schema"):
        validate_evidence_bound_baseline_observation(bound)


def test_binding_is_deterministic_for_identical_inputs(tmp_path):
    request, result = _observe(
        tmp_path,
        hook_id="source-a",
        reference="a.txt",
        content="stable witness",
    )
    kwargs = {
        "observer_id": "observer-a",
        "baseline_id": "baseline-1",
        "baseline_state_hash": "state-1",
        "findings": {"claim-a": FINDING_CORRECTION},
        "request": request,
        "observation_result": result,
    }

    assert build_evidence_bound_baseline_observation(
        **kwargs
    ) == build_evidence_bound_baseline_observation(**kwargs)