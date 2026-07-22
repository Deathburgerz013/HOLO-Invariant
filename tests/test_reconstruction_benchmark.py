from holosim.reconstruction_benchmark import (
    ReconstructionBenchmarkError,
    compare_reconstruction_conditions,
    score_reconstruction,
)


REFERENCE_CLAIMS = [
    "continuity-is-enforced-not-stored",
    "replay-reduces-interpretive-drift",
    "history-preserves-prior-action-and-consequence",
    "compression-without-boundaries-causes-loss",
    "dated-ordered-artifacts-help-reconstruction",
]

REQUIRED_ORDER = [
    "continuity-is-enforced-not-stored",
    "replay-reduces-interpretive-drift",
    "history-preserves-prior-action-and-consequence",
    "compression-without-boundaries-causes-loss",
    "dated-ordered-artifacts-help-reconstruction",
]


def test_grounded_artifact_condition_outperforms_sparse_baseline_without_more_unsupported_claims():
    baseline = score_reconstruction(
        benchmark_id="continuity-findings-reconstruction-v1",
        condition_id="sparse-cue",
        reference_claims=REFERENCE_CLAIMS,
        reconstructed_claims=[
            "continuity-is-enforced-not-stored",
            "ai-has-perfect-internal-long-term-memory",
        ],
        required_order=REQUIRED_ORDER,
        reconstructed_order=["continuity-is-enforced-not-stored"],
        claim_sources={},
        context_units=1,
    )

    grounded = score_reconstruction(
        benchmark_id="continuity-findings-reconstruction-v1",
        condition_id="ordered-grounded-artifacts",
        reference_claims=REFERENCE_CLAIMS,
        reconstructed_claims=REFERENCE_CLAIMS,
        required_order=REQUIRED_ORDER,
        reconstructed_order=REQUIRED_ORDER,
        claim_sources={
            "continuity-is-enforced-not-stored": ["docs/Continuity_findings:22-24"],
            "replay-reduces-interpretive-drift": ["docs/Continuity_findings:29-30"],
            "history-preserves-prior-action-and-consequence": [
                "docs/Continuity_findings:41-43"
            ],
            "compression-without-boundaries-causes-loss": [
                "docs/Continuity_findings:50-53"
            ],
            "dated-ordered-artifacts-help-reconstruction": [
                "docs/Continuity_findings:101-107"
            ],
        },
        context_units=5,
    )

    comparison = compare_reconstruction_conditions(
        baseline=baseline,
        candidate=grounded,
    )

    assert baseline["metrics"]["recovered_count"] == 1
    assert baseline["metrics"]["unsupported_count"] == 1
    assert grounded["metrics"]["recovered_count"] == 5
    assert grounded["metrics"]["unsupported_count"] == 0
    assert grounded["metrics"]["sourced_recall"] == 1.0
    assert grounded["metrics"]["order_correct"] is True
    assert comparison["delta"]["recovered_count"] == 4
    assert comparison["delta"]["unsupported_count"] == -1
    assert comparison["candidate_improves_reconstruction"] is True
    assert comparison["accepted"] is False
    assert comparison["write_authority"] == "NONE"


def test_same_claims_with_wrong_order_do_not_pass_order_check():
    result = score_reconstruction(
        benchmark_id="continuity-findings-reconstruction-v1",
        condition_id="wrong-order",
        reference_claims=REFERENCE_CLAIMS,
        reconstructed_claims=REFERENCE_CLAIMS,
        required_order=REQUIRED_ORDER,
        reconstructed_order=list(reversed(REQUIRED_ORDER)),
        context_units=5,
    )

    assert result["metrics"]["recall"] == 1.0
    assert result["metrics"]["order_correct"] is False


def test_comparison_refuses_different_reference_fixtures():
    baseline = score_reconstruction(
        benchmark_id="same-id",
        condition_id="baseline",
        reference_claims=["a"],
        reconstructed_claims=["a"],
    )
    candidate = score_reconstruction(
        benchmark_id="same-id",
        condition_id="candidate",
        reference_claims=["b"],
        reconstructed_claims=["b"],
    )

    try:
        compare_reconstruction_conditions(baseline=baseline, candidate=candidate)
    except ReconstructionBenchmarkError as exc:
        assert "reference_claims must match" in str(exc)
    else:
        raise AssertionError("comparison must fail closed on a changed reference fixture")


def test_result_is_deterministic_and_non_authoritative():
    kwargs = dict(
        benchmark_id="deterministic",
        condition_id="fixture",
        reference_claims=["a", "b"],
        reconstructed_claims=["a"],
        required_order=["a", "b"],
        reconstructed_order=["a"],
        claim_sources={"a": ["source:a"]},
        context_units=1,
    )

    first = score_reconstruction(**kwargs)
    second = score_reconstruction(**kwargs)

    assert first == second
    assert first["truth_claimed"] is False
    assert first["accepted"] is False
    assert first["write_authority"] == "NONE"
