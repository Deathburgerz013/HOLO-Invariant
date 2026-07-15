from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.environment_snapshot import (
    COLLECTION_COMPLETE,
    COMPRESSION_BLOCKED_BY_REQUIRED_DISTINCTION,
    COMPRESSION_BUDGET_EXHAUSTED,
    COMPRESSION_FIXED_POINT,
    FALSE_CONVERGENCE,
    NO_STOP_FINDING,
    RECONSTRUCTION_FAILED,
    REOPENED,
    SNAPSHOT_TYPE,
    SNAPSHOT_VERSION,
    TEMPORARY_PAUSE,
    CompressionStopValidationError,
    SnapshotValidationError,
    build_snapshot,
    evaluate_compression_stop,
    verify_snapshot,
)


EVIDENCE_A = "a" * 64
EVIDENCE_B = "b" * 64


def snapshot_kwargs():
    return {
        "episode_id": "episode:camera-1",
        "environment_id": "environment:lab",
        "check_id": "check:frame-analysis:v1",
        "check_purpose": "Observe whether recorded motion changed.",
        "goal_reference": "goal:determine-next-useful-check",
        "observer_ids": ["observer:camera-north", "tool:frame-reader:v1"],
        "clock_id": "clock:camera-north:v1",
        "observed_at": "2026-07-14T23:30:00Z",
        "feature_schema_id": "schema:camera-motion:v1",
        "observed": {"motion": True, "frame": 42},
        "missing": [{"signal": "camera-south", "reason": "not sampled"}],
        "unknown": [{"field": "occluded_region"}],
        "assumptions": [{"claim": "camera clock is calibrated"}],
        "falsifiers": [{"check": "compare independent camera"}],
        "evidence_sha256": [EVIDENCE_A, EVIDENCE_B],
        "provenance": {
            "source_id": "video-loop:frame-42",
            "tool_id": "frame-reader:v1",
            "git_commit": "abc123",
        },
        "uncertainty": [{"kind": "partial_occlusion"}],
    }


def compression_kwargs():
    return {
        "reconstruction_contract_satisfied": True,
        "required_operator_ids": [
            "operator:classification-correction",
            "operator:falsifier-correction",
            "operator:source-binding-correction",
            "operator:wording-narrowing",
        ],
        "evaluated_operator_ids": [
            "operator:classification-correction",
            "operator:falsifier-correction",
            "operator:source-binding-correction",
            "operator:wording-narrowing",
        ],
        "lower_cost_candidates": [],
        "audit_budget_exhausted": False,
        "reported_finding": None,
        "false_convergence_reasons": [],
        "pause_reasons": [],
        "reopen_reasons": [],
        "uncertainty": [
            {"kind": "large-file behavior remains untested"},
            {"kind": "concurrent append guarantees remain unknown"},
        ],
    }


def lower_cost_candidate(
    *,
    candidate_id="candidate:one",
    operator_id="operator:source-binding-correction",
    contract_satisfied=False,
    lost_required_distinctions=None,
):
    if lost_required_distinctions is None:
        lost_required_distinctions = ["distinction:source-binding"]
    return {
        "candidate_id": candidate_id,
        "operator_id": operator_id,
        "contract_satisfied": contract_satisfied,
        "lost_required_distinctions": lost_required_distinctions,
    }


def test_snapshot_is_deterministic_under_object_key_reordering():
    first_kwargs = snapshot_kwargs()
    second_kwargs = snapshot_kwargs()
    second_kwargs["observed"] = {"frame": 42, "motion": True}
    second_kwargs["provenance"] = {
        "git_commit": "abc123",
        "tool_id": "frame-reader:v1",
        "source_id": "video-loop:frame-42",
    }

    first = build_snapshot(**first_kwargs)
    second = build_snapshot(**second_kwargs)

    assert first == second
    assert len(first["snapshot_id"]) == 64


def test_snapshot_preserves_observed_missing_unknown_and_assumed_separately():
    snapshot = build_snapshot(**snapshot_kwargs())

    assert snapshot["observed"] == {"motion": True, "frame": 42}
    assert snapshot["missing"][0]["signal"] == "camera-south"
    assert snapshot["unknown"][0]["field"] == "occluded_region"
    assert snapshot["assumptions"][0]["claim"] == (
        "camera clock is calibrated"
    )
    assert snapshot["falsifiers"][0]["check"] == (
        "compare independent camera"
    )


def test_snapshot_is_non_accepting_and_read_only_by_contract():
    snapshot = build_snapshot(**snapshot_kwargs())

    assert snapshot["type"] == SNAPSHOT_TYPE
    assert snapshot["version"] == SNAPSHOT_VERSION
    assert snapshot["accepted"] is False
    assert snapshot["write_authority"] == "NONE"
    assert verify_snapshot(snapshot)["valid"] is True


def test_observation_time_is_caller_supplied_and_identity_significant():
    first_kwargs = snapshot_kwargs()
    second_kwargs = snapshot_kwargs()
    second_kwargs["observed_at"] = "2026-07-14T23:31:00Z"

    first = build_snapshot(**first_kwargs)
    second = build_snapshot(**second_kwargs)

    assert first["observed_at"] == "2026-07-14T23:30:00Z"
    assert first["snapshot_id"] != second["snapshot_id"]


@pytest.mark.parametrize(
    "observed_at",
    ["2026-07-14T23:30:00", "not-a-time", ""],
)
def test_observation_time_requires_valid_explicit_timezone(observed_at):
    kwargs = snapshot_kwargs()
    kwargs["observed_at"] = observed_at

    with pytest.raises(SnapshotValidationError):
        build_snapshot(**kwargs)


@pytest.mark.parametrize(
    "evidence",
    [[], ["not-a-hash"], [EVIDENCE_A, EVIDENCE_A], ["A" * 64]],
)
def test_evidence_hashes_are_required_strict_and_unique(evidence):
    kwargs = snapshot_kwargs()
    kwargs["evidence_sha256"] = evidence

    with pytest.raises(SnapshotValidationError):
        build_snapshot(**kwargs)


def test_observers_are_required_and_unique():
    kwargs = snapshot_kwargs()
    kwargs["observer_ids"] = ["observer:camera", "observer:camera"]

    with pytest.raises(SnapshotValidationError):
        build_snapshot(**kwargs)


def test_snapshot_does_not_alias_mutable_caller_values():
    kwargs = snapshot_kwargs()
    observed = kwargs["observed"]
    snapshot = build_snapshot(**kwargs)

    observed["frame"] = 99

    assert snapshot["observed"]["frame"] == 42
    assert verify_snapshot(snapshot)["valid"] is True


def test_verification_detects_tampering_without_repair():
    snapshot = build_snapshot(**snapshot_kwargs())
    tampered = deepcopy(snapshot)
    tampered["observed"]["frame"] = 99

    result = verify_snapshot(tampered)

    assert result["valid"] is False
    assert "snapshot identity mismatch" in result["violations"]
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert tampered["observed"]["frame"] == 99


def test_unsupported_nested_value_is_rejected():
    kwargs = snapshot_kwargs()
    kwargs["observed"] = {"unsupported": {"set"}}

    with pytest.raises(SnapshotValidationError):
        build_snapshot(**kwargs)


def test_verification_rejects_invalid_fields_even_with_recomputed_hash():
    snapshot = build_snapshot(**snapshot_kwargs())
    invalid = deepcopy(snapshot)
    invalid["observed_at"] = "2026-07-14T23:30:00"
    invalid["snapshot_id"] = stable_hash(
        {
            key: value
            for key, value in invalid.items()
            if key != "snapshot_id"
        }
    )

    result = verify_snapshot(invalid)

    assert result["valid"] is False
    assert any(
        "explicit timezone" in violation
        for violation in result["violations"]
    )


def test_fixture_evidence_derives_fixed_point_not_blocked_finding():
    kwargs = compression_kwargs()
    kwargs["reported_finding"] = (
        COMPRESSION_BLOCKED_BY_REQUIRED_DISTINCTION
    )

    result = evaluate_compression_stop(**kwargs)

    assert result["finding"] == COMPRESSION_FIXED_POINT
    assert result["terminal"] is True
    assert result["reported_finding_matches"] is False
    assert result["missing_operator_ids"] == []
    assert result["contract_preserving_lower_cost_candidate_ids"] == []
    assert result["required_distinction_blocked_candidate_ids"] == []


def test_fixed_point_requires_complete_operator_coverage():
    result = evaluate_compression_stop(**compression_kwargs())

    assert result["finding"] == COMPRESSION_FIXED_POINT
    assert result["terminal"] is True
    assert "Every required operator was evaluated" in (
        result["decision_reasons"][0]
    )


def test_blocked_finding_requires_every_lower_cost_candidate_to_lose_distinction():
    kwargs = compression_kwargs()
    kwargs["lower_cost_candidates"] = [
        lower_cost_candidate(
            candidate_id="candidate:a",
            lost_required_distinctions=["distinction:provenance"],
        ),
        lower_cost_candidate(
            candidate_id="candidate:b",
            operator_id="operator:wording-narrowing",
            lost_required_distinctions=["distinction:uncertainty"],
        ),
    ]

    result = evaluate_compression_stop(**kwargs)

    assert result["finding"] == (
        COMPRESSION_BLOCKED_BY_REQUIRED_DISTINCTION
    )
    assert result["terminal"] is True
    assert result["required_distinction_blocked_candidate_ids"] == [
        "candidate:a",
        "candidate:b",
    ]


def test_safe_lower_cost_candidate_requires_compression_to_continue():
    kwargs = compression_kwargs()
    kwargs["lower_cost_candidates"] = [
        lower_cost_candidate(
            contract_satisfied=True,
            lost_required_distinctions=[],
        )
    ]

    result = evaluate_compression_stop(**kwargs)

    assert result["finding"] == NO_STOP_FINDING
    assert result["terminal"] is False
    assert result["contract_preserving_lower_cost_candidate_ids"] == [
        "candidate:one"
    ]


def test_budget_exhaustion_requires_missing_operator_coverage():
    kwargs = compression_kwargs()
    kwargs["evaluated_operator_ids"] = [
        "operator:source-binding-correction"
    ]
    kwargs["audit_budget_exhausted"] = True

    result = evaluate_compression_stop(**kwargs)

    assert result["finding"] == COMPRESSION_BUDGET_EXHAUSTED
    assert result["terminal"] is True
    assert result["missing_operator_ids"] == [
        "operator:classification-correction",
        "operator:falsifier-correction",
        "operator:wording-narrowing",
    ]


def test_incomplete_search_without_exhaustion_has_no_stop_finding():
    kwargs = compression_kwargs()
    kwargs["evaluated_operator_ids"] = [
        "operator:source-binding-correction"
    ]

    result = evaluate_compression_stop(**kwargs)

    assert result["finding"] == NO_STOP_FINDING
    assert result["terminal"] is False


def test_reconstruction_failure_precedes_search_completion_findings():
    kwargs = compression_kwargs()
    kwargs["reconstruction_contract_satisfied"] = False
    kwargs["evaluated_operator_ids"] = []
    kwargs["audit_budget_exhausted"] = True

    result = evaluate_compression_stop(**kwargs)

    assert result["finding"] == RECONSTRUCTION_FAILED
    assert result["terminal"] is True


def test_reopening_precedes_all_other_compression_findings():
    kwargs = compression_kwargs()
    kwargs["reconstruction_contract_satisfied"] = False
    kwargs["reopen_reasons"] = ["new source evidence arrived"]

    result = evaluate_compression_stop(**kwargs)

    assert result["finding"] == REOPENED
    assert result["terminal"] is False
    assert result["reopen_reasons"] == ["new source evidence arrived"]


def test_temporary_pause_does_not_claim_terminal_completion():
    kwargs = compression_kwargs()
    kwargs["pause_reasons"] = ["human requested pause"]

    result = evaluate_compression_stop(**kwargs)

    assert result["finding"] == TEMPORARY_PAUSE
    assert result["terminal"] is False


def test_explicit_false_convergence_reason_prevents_fixed_point():
    kwargs = compression_kwargs()
    kwargs["false_convergence_reasons"] = [
        "repetition was treated as proof"
    ]

    result = evaluate_compression_stop(**kwargs)

    assert result["finding"] == FALSE_CONVERGENCE
    assert result["terminal"] is False


def test_invalid_reported_fixed_point_is_classified_false_convergence():
    kwargs = compression_kwargs()
    kwargs["reported_finding"] = COMPRESSION_FIXED_POINT
    kwargs["evaluated_operator_ids"] = [
        "operator:source-binding-correction"
    ]

    result = evaluate_compression_stop(**kwargs)

    assert result["finding"] == FALSE_CONVERGENCE
    assert result["reported_finding_matches"] is False
    assert result["false_convergence_reasons"] == [
        "reported fixed point fails its decision conditions"
    ]


def test_collection_finding_cannot_be_imported_into_compression_phase():
    kwargs = compression_kwargs()
    kwargs["reported_finding"] = COLLECTION_COMPLETE

    with pytest.raises(
        CompressionStopValidationError,
        match="not a compression-phase finding",
    ):
        evaluate_compression_stop(**kwargs)


def test_evaluated_operator_must_belong_to_declared_operator_set():
    kwargs = compression_kwargs()
    kwargs["evaluated_operator_ids"] = [
        "operator:undeclared"
    ]

    with pytest.raises(
        CompressionStopValidationError,
        match="undeclared operators",
    ):
        evaluate_compression_stop(**kwargs)


def test_lower_cost_candidate_must_bind_to_evaluated_operator():
    kwargs = compression_kwargs()
    kwargs["evaluated_operator_ids"] = []
    kwargs["lower_cost_candidates"] = [
        lower_cost_candidate()
    ]

    with pytest.raises(
        CompressionStopValidationError,
        match="operator_id must be evaluated",
    ):
        evaluate_compression_stop(**kwargs)


def test_contract_satisfied_candidate_cannot_lose_required_distinction():
    kwargs = compression_kwargs()
    kwargs["lower_cost_candidates"] = [
        lower_cost_candidate(contract_satisfied=True)
    ]

    with pytest.raises(
        CompressionStopValidationError,
        match="cannot lose a required distinction",
    ):
        evaluate_compression_stop(**kwargs)


def test_duplicate_lower_cost_candidate_ids_are_rejected():
    kwargs = compression_kwargs()
    kwargs["lower_cost_candidates"] = [
        lower_cost_candidate(),
        lower_cost_candidate(
            operator_id="operator:wording-narrowing",
        ),
    ]

    with pytest.raises(
        CompressionStopValidationError,
        match="candidate_id cannot contain duplicates",
    ):
        evaluate_compression_stop(**kwargs)


def test_unexpected_lower_cost_candidate_fields_are_rejected():
    kwargs = compression_kwargs()
    candidate = lower_cost_candidate()
    candidate["undeclared"] = True
    kwargs["lower_cost_candidates"] = [candidate]

    with pytest.raises(
        CompressionStopValidationError,
        match="unexpected fields",
    ):
        evaluate_compression_stop(**kwargs)


def test_compression_finding_is_deterministic_under_set_reordering():
    first_kwargs = compression_kwargs()
    second_kwargs = compression_kwargs()
    second_kwargs["required_operator_ids"] = list(
        reversed(second_kwargs["required_operator_ids"])
    )
    second_kwargs["evaluated_operator_ids"] = list(
        reversed(second_kwargs["evaluated_operator_ids"])
    )

    first = evaluate_compression_stop(**first_kwargs)
    second = evaluate_compression_stop(**second_kwargs)

    assert first == second
    assert len(first["finding_id"]) == 64


def test_compression_finding_does_not_alias_uncertainty_input():
    kwargs = compression_kwargs()
    uncertainty = kwargs["uncertainty"]

    result = evaluate_compression_stop(**kwargs)
    uncertainty[0]["kind"] = "changed after evaluation"

    assert result["uncertainty"][0]["kind"] == (
        "large-file behavior remains untested"
    )


def test_compression_finding_is_non_accepting_and_has_no_write_authority():
    result = evaluate_compression_stop(**compression_kwargs())

    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert "does not establish global optimality" in (
        result["interpretation_notice"]
    )