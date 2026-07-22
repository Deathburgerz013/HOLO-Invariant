from holosim.recall_kernel_falsification import (
    RecallKernelFalsificationError,
    evaluate_recall_kernel_ablations,
)
from holosim.reconstruction_benchmark import score_reconstruction


KERNEL_FIELDS = [
    "identity",
    "history",
    "last_verified_state",
    "capabilities_and_limits",
    "corrections",
    "unresolved_gaps",
    "authority",
    "recheck_conditions",
]

REFERENCE_CLAIMS = [
    "subject-identity-correct",
    "prior-sequence-reconstructed",
    "current-verified-state-correct",
    "capability-boundary-correct",
    "corrections-preserved",
    "unresolved-gaps-preserved",
    "authority-boundary-correct",
    "staleness-trigger-correct",
]


def _result(condition_id, claims, *, sourced=True, order=None):
    return score_reconstruction(
        benchmark_id="recall-kernel-v1",
        condition_id=condition_id,
        reference_claims=REFERENCE_CLAIMS,
        reconstructed_claims=claims,
        required_order=REFERENCE_CLAIMS,
        reconstructed_order=order if order is not None else claims,
        claim_sources=(
            {claim: [f"fixture:{claim}"] for claim in claims if claim in REFERENCE_CLAIMS}
            if sourced
            else {}
        ),
        context_units=max(len(claims), 1),
    )


def test_one_field_ablations_identify_only_observed_failures():
    full = _result("full-kernel", REFERENCE_CLAIMS)

    ablations = {
        "identity": _result("minus-identity", REFERENCE_CLAIMS[1:]),
        "history": _result(
            "minus-history",
            [claim for claim in REFERENCE_CLAIMS if claim != "prior-sequence-reconstructed"],
        ),
        "last_verified_state": _result(
            "minus-last-verified-state",
            [claim for claim in REFERENCE_CLAIMS if claim != "current-verified-state-correct"],
        ),
        "capabilities_and_limits": _result(
            "minus-capabilities",
            [claim for claim in REFERENCE_CLAIMS if claim != "capability-boundary-correct"],
        ),
        "corrections": _result(
            "minus-corrections",
            [claim for claim in REFERENCE_CLAIMS if claim != "corrections-preserved"],
        ),
        "unresolved_gaps": _result(
            "minus-unresolved-gaps",
            [claim for claim in REFERENCE_CLAIMS if claim != "unresolved-gaps-preserved"],
        ),
        "authority": _result(
            "minus-authority",
            [claim for claim in REFERENCE_CLAIMS if claim != "authority-boundary-correct"],
        ),
        "recheck_conditions": _result(
            "minus-recheck-conditions",
            [claim for claim in REFERENCE_CLAIMS if claim != "staleness-trigger-correct"],
        ),
    }

    evaluation = evaluate_recall_kernel_ablations(
        experiment_id="candidate-recall-kernel-v1",
        kernel_fields=KERNEL_FIELDS,
        full_kernel_result=full,
        ablation_results=ablations,
    )

    assert evaluation["observed_required_fields"] == KERNEL_FIELDS
    assert evaluation["not_shown_required_fields"] == []
    assert all(
        entry["status"] == "OBSERVED_REQUIRED"
        for entry in evaluation["field_classifications"].values()
    )
    assert evaluation["universal_requirement_claimed"] is False
    assert evaluation["truth_claimed"] is False
    assert evaluation["accepted"] is False
    assert evaluation["write_authority"] == "NONE"


def test_unchanged_reconstruction_does_not_falsely_prove_field_required():
    full = _result("full-kernel", REFERENCE_CLAIMS)
    ablations = {
        field: _result(f"minus-{field}", REFERENCE_CLAIMS)
        for field in KERNEL_FIELDS
    }

    evaluation = evaluate_recall_kernel_ablations(
        experiment_id="no-observed-loss",
        kernel_fields=KERNEL_FIELDS,
        full_kernel_result=full,
        ablation_results=ablations,
    )

    assert evaluation["observed_required_fields"] == []
    assert evaluation["not_shown_required_fields"] == KERNEL_FIELDS
    assert all(
        entry["status"] == "NOT_SHOWN_REQUIRED"
        for entry in evaluation["field_classifications"].values()
    )


def test_source_loss_and_order_failure_count_as_material_degradation():
    full = _result("full-kernel", REFERENCE_CLAIMS)
    ablations = {
        field: _result(f"minus-{field}", REFERENCE_CLAIMS)
        for field in KERNEL_FIELDS
    }
    ablations["history"] = _result(
        "minus-history",
        REFERENCE_CLAIMS,
        order=list(reversed(REFERENCE_CLAIMS)),
    )
    ablations["identity"] = _result(
        "minus-identity",
        REFERENCE_CLAIMS,
        sourced=False,
    )

    evaluation = evaluate_recall_kernel_ablations(
        experiment_id="quality-loss",
        kernel_fields=KERNEL_FIELDS,
        full_kernel_result=full,
        ablation_results=ablations,
    )

    assert evaluation["field_classifications"]["history"]["status"] == "OBSERVED_REQUIRED"
    assert "required_order_failed" in evaluation["field_classifications"]["history"]["degradation_reasons"]
    assert evaluation["field_classifications"]["identity"]["status"] == "OBSERVED_REQUIRED"
    assert "sourced_recall_decreased" in evaluation["field_classifications"]["identity"]["degradation_reasons"]


def test_evaluator_fails_closed_when_ablation_matrix_is_incomplete():
    full = _result("full-kernel", REFERENCE_CLAIMS)

    try:
        evaluate_recall_kernel_ablations(
            experiment_id="incomplete",
            kernel_fields=KERNEL_FIELDS,
            full_kernel_result=full,
            ablation_results={"identity": _result("minus-identity", REFERENCE_CLAIMS)},
        )
    except RecallKernelFalsificationError as exc:
        assert "exactly one result for each kernel field" in str(exc)
    else:
        raise AssertionError("incomplete ablation matrix must fail closed")
