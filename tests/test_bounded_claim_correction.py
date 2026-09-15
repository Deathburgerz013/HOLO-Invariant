from copy import deepcopy

import pytest

from holosim.baseline_observation_compare import (
    FINDING_CORRECTION,
    FINDING_EXTENSION,
    FINDING_SUPPORT,
)
from holosim.bounded_claim_correction import (
    BoundedClaimCorrectionError,
    validate_bounded_claim_correction,
    propose_bounded_claim_correction,
)
from holosim.canonical import stable_hash
from holosim.evidence_bound_baseline_observation import (
    build_evidence_bound_baseline_observation,
    compare_evidence_bound_baseline_observations,
    evaluate_evidence_bound_baseline_promotion,
)
from holosim.hook_contract import build_hook_request, build_hook_result


def _source_receipts(
    *,
    current_claims=None,
    findings=None,
    left_replacements=None,
    right_replacements=None,
):
    if current_claims is None:
        current_claims = {
            "color": {"value": "blue"},
            "shape": {"value": "flat"},
        }
    if findings is None:
        findings = {
            "color": FINDING_SUPPORT,
            "shape": FINDING_CORRECTION,
        }
    if left_replacements is None:
        left_replacements = {
            "shape": {"value": "round"},
        }
    if right_replacements is None:
        right_replacements = deepcopy(left_replacements)

    baseline_hash = stable_hash(current_claims)

    left_request = build_hook_request(
        hook_id="observer-left",
        action="observe-baseline",
        reference="baseline-1",
        payload={"baseline_state_hash": baseline_hash},
    )
    right_request = build_hook_request(
        hook_id="observer-right",
        action="observe-baseline",
        reference="baseline-1",
        payload={"baseline_state_hash": baseline_hash},
    )

    left_result = build_hook_result(
        request=left_request,
        status="OBSERVED",
        evidence={
            "source": "left",
            "proposed_claim_replacements": deepcopy(left_replacements),
        },
    )
    right_result = build_hook_result(
        request=right_request,
        status="OBSERVED",
        evidence={
            "source": "right",
            "proposed_claim_replacements": deepcopy(right_replacements),
        },
    )

    left_binding = build_evidence_bound_baseline_observation(
        observer_id="observer-left",
        baseline_id="baseline-1",
        baseline_state_hash=baseline_hash,
        findings=findings,
        request=left_request,
        observation_result=left_result,
    )
    right_binding = build_evidence_bound_baseline_observation(
        observer_id="observer-right",
        baseline_id="baseline-1",
        baseline_state_hash=baseline_hash,
        findings=findings,
        request=right_request,
        observation_result=right_result,
    )

    comparison = compare_evidence_bound_baseline_observations(
        left_binding,
        right_binding,
    )
    promotion = evaluate_evidence_bound_baseline_promotion(
        comparison=comparison
    )
    return current_claims, comparison, promotion


def _proposal():
    current_claims, comparison, promotion = _source_receipts()
    proposal = propose_bounded_claim_correction(
        comparison=comparison,
        promotion=promotion,
        current_claims=current_claims,
        proposed_replacements={
            "shape": {"value": "round"},
        },
    )
    return current_claims, comparison, promotion, proposal


def test_creates_exact_successor_candidate_without_applying_it() -> None:
    current_claims, comparison, promotion, proposal = _proposal()

    assert proposal["status"] == "CORRECTION_CANDIDATE_CREATED"
    assert proposal["baseline_id"] == "baseline-1"
    assert proposal["baseline_state_hash"] == stable_hash(current_claims)
    assert proposal["corrected_claim_ids"] == ["shape"]
    assert proposal["current_claims"] == {
        "color": {"value": "blue"},
        "shape": {"value": "flat"},
    }
    assert proposal["proposed_replacements"] == {
        "shape": {"value": "round"},
    }
    assert proposal["candidate_claims"] == {
        "color": {"value": "blue"},
        "shape": {"value": "round"},
    }
    assert proposal["candidate_baseline_hash"] == stable_hash(
        proposal["candidate_claims"]
    )
    assert proposal["comparison"] == comparison
    assert proposal["promotion"] == promotion
    assert proposal["candidate_claim_set_created"] is True
    assert proposal["correction_applied"] is False
    assert proposal["supersession_performed"] is False


def test_preserves_unaffected_claims() -> None:
    current_claims = {
        "alpha": {"value": [1, 2, 3]},
        "shape": {"value": "flat"},
        "zeta": {"nested": {"preserved": True}},
    }
    findings = {
        "alpha": FINDING_SUPPORT,
        "shape": FINDING_CORRECTION,
        "zeta": FINDING_SUPPORT,
    }
    current_claims, comparison, promotion = _source_receipts(
        current_claims=current_claims,
        findings=findings,
    )

    proposal = propose_bounded_claim_correction(
        comparison=comparison,
        promotion=promotion,
        current_claims=current_claims,
        proposed_replacements={
            "shape": {"value": "round"},
        },
    )

    assert proposal["candidate_claims"]["alpha"] == {"value": [1, 2, 3]}
    assert proposal["candidate_claims"]["zeta"] == {
        "nested": {"preserved": True}
    }


def test_records_both_exact_evidence_receipts_for_corrected_claim() -> None:
    _, comparison, _, proposal = _proposal()

    expected_hashes = sorted(
        [
            comparison["left_binding"]["observation_result"]["result_hash"],
            comparison["right_binding"]["observation_result"]["result_hash"],
        ]
    )

    assert proposal["replacement_evidence"] == {
        "shape": expected_hashes,
    }
    assert proposal["evidence_result_hashes"] == expected_hashes


def test_valid_proposal_regenerates_exactly() -> None:
    _, _, _, proposal = _proposal()

    assert validate_bounded_claim_correction(proposal) is True


def test_logically_identical_mapping_order_is_deterministic() -> None:
    current_claims, comparison, promotion = _source_receipts()

    first = propose_bounded_claim_correction(
        comparison=comparison,
        promotion=promotion,
        current_claims={
            "color": {"value": "blue"},
            "shape": {"value": "flat"},
        },
        proposed_replacements={
            "shape": {"value": "round"},
        },
    )
    second = propose_bounded_claim_correction(
        comparison=comparison,
        promotion=promotion,
        current_claims={
            "shape": {"value": "flat"},
            "color": {"value": "blue"},
        },
        proposed_replacements={
            "shape": {"value": "round"},
        },
    )

    assert first == second
    assert first["proposal_hash"] == second["proposal_hash"]


def test_different_replacement_changes_candidate_and_proposal_identity() -> None:
    current_claims, first_comparison, first_promotion = _source_receipts()
    first = propose_bounded_claim_correction(
        comparison=first_comparison,
        promotion=first_promotion,
        current_claims=current_claims,
        proposed_replacements={
            "shape": {"value": "round"},
        },
    )

    current_claims, second_comparison, second_promotion = _source_receipts(
        left_replacements={"shape": {"value": "sphere"}},
        right_replacements={"shape": {"value": "sphere"}},
    )
    second = propose_bounded_claim_correction(
        comparison=second_comparison,
        promotion=second_promotion,
        current_claims=current_claims,
        proposed_replacements={
            "shape": {"value": "sphere"},
        },
    )

    assert first["candidate_baseline_hash"] != second["candidate_baseline_hash"]
    assert first["proposal_hash"] != second["proposal_hash"]


def test_current_claims_must_match_baseline_hash() -> None:
    current_claims, comparison, promotion = _source_receipts()
    current_claims["shape"] = {"value": "changed-after-observation"}

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="current claims do not match baseline_state_hash",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


def test_current_claim_ids_must_match_compared_set() -> None:
    current_claims, comparison, promotion = _source_receipts()
    current_claims["unobserved"] = {"value": True}

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="current claim ids must exactly match compared claim ids",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


def test_replacement_ids_must_exactly_match_corrections() -> None:
    current_claims, comparison, promotion = _source_receipts()

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="replacement ids must exactly match corrected claim ids",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "color": {"value": "green"},
                "shape": {"value": "round"},
            },
        )


def test_replacement_must_change_original_claim() -> None:
    current_claims, comparison, promotion = _source_receipts(
        left_replacements={"shape": {"value": "flat"}},
        right_replacements={"shape": {"value": "flat"}},
    )

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="replacement must change claim shape",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "shape": {"value": "flat"},
            },
        )


def test_both_observers_must_name_exact_replacement() -> None:
    current_claims, comparison, promotion = _source_receipts(
        right_replacements={},
    )

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="evidence replacement ids must exactly match corrected claim ids",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


def test_conflicting_replacement_evidence_fails_closed() -> None:
    current_claims, comparison, promotion = _source_receipts(
        left_replacements={"shape": {"value": "round"}},
        right_replacements={"shape": {"value": "sphere"}},
    )

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="observers do not agree on replacement for shape",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


def test_missing_structured_replacement_evidence_fails_closed() -> None:
    current_claims, comparison, promotion = _source_receipts()
    right_result = comparison["right_binding"]["observation_result"]
    right_result["evidence"].pop("proposed_claim_replacements")

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="comparison is invalid",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


def test_forged_comparison_fails_closed() -> None:
    current_claims, comparison, promotion = _source_receipts()
    comparison["comparison"]["correction"] = []

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="comparison does not match its evidence bindings",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


def test_forged_promotion_fails_closed() -> None:
    current_claims, comparison, promotion = _source_receipts()
    promotion["gate"]["status"] = "JUSTIFIED_TO_PROPOSE_FORGED"

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="promotion does not match the supplied comparison",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


def test_non_justified_promotion_cannot_create_candidate() -> None:
    findings = {
        "color": FINDING_SUPPORT,
        "shape": FINDING_SUPPORT,
    }
    current_claims, comparison, promotion = _source_receipts(
        findings=findings,
        left_replacements={},
        right_replacements={},
    )

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="promotion is not justified to propose",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


def test_extensions_are_not_silently_dropped_into_correction_candidate() -> None:
    findings = {
        "color": FINDING_SUPPORT,
        "shape": FINDING_EXTENSION,
    }
    current_claims, comparison, promotion = _source_receipts(
        findings=findings,
        left_replacements={},
        right_replacements={},
    )

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="extensions outside this correction boundary",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=current_claims,
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


@pytest.mark.parametrize(
    "invalid_claims",
    [
        [],
        (),
        "claims",
        None,
    ],
)
def test_current_claims_must_be_plain_dictionary(invalid_claims) -> None:
    _, comparison, promotion = _source_receipts()

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="current_claims must be a plain dictionary",
    ):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims=invalid_claims,
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


@pytest.mark.parametrize(
    "invalid_id",
    [
        "",
        "   ",
        " padded ",
        1,
    ],
)
def test_invalid_claim_id_fails_closed(invalid_id) -> None:
    _, comparison, promotion = _source_receipts()

    with pytest.raises(BoundedClaimCorrectionError):
        propose_bounded_claim_correction(
            comparison=comparison,
            promotion=promotion,
            current_claims={
                "color": {"value": "blue"},
                invalid_id: {"value": "flat"},
            },
            proposed_replacements={
                "shape": {"value": "round"},
            },
        )


def test_inputs_are_not_mutated() -> None:
    current_claims, comparison, promotion = _source_receipts()
    replacements = {
        "shape": {
            "value": "round",
            "support": ["measurement-a", "measurement-b"],
        }
    }

    current_claims, comparison, promotion = _source_receipts(
        current_claims=current_claims,
        left_replacements=replacements,
        right_replacements=replacements,
    )

    original_current = deepcopy(current_claims)
    original_comparison = deepcopy(comparison)
    original_promotion = deepcopy(promotion)
    original_replacements = deepcopy(replacements)

    propose_bounded_claim_correction(
        comparison=comparison,
        promotion=promotion,
        current_claims=current_claims,
        proposed_replacements=replacements,
    )

    assert current_claims == original_current
    assert comparison == original_comparison
    assert promotion == original_promotion
    assert replacements == original_replacements


def test_authority_and_mutation_remain_absent() -> None:
    _, _, _, proposal = _proposal()

    assert proposal["accepted"] is False
    assert proposal["truth_claimed"] is False
    assert proposal["write_authority"] == "NONE"
    assert proposal["execution_authority"] == "NONE"
    assert proposal["canonical_mutation"] is False
    assert proposal["correction_applied"] is False
    assert proposal["supersession_performed"] is False


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("candidate_claim_set_created", False),
        ("correction_applied", True),
        ("supersession_performed", True),
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
        ("canonical_mutation", True),
        ("candidate_baseline_hash", "0" * 64),
        ("proposal_hash", "0" * 64),
    ],
)
def test_validator_rejects_tampering(field, forged_value) -> None:
    _, _, _, proposal = _proposal()
    proposal[field] = forged_value

    with pytest.raises(
        BoundedClaimCorrectionError,
        match="proposal does not match its source evidence",
    ):
        validate_bounded_claim_correction(proposal)