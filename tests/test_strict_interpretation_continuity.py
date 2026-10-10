from holosim.interpretation_set_receipt import InterpretationSetReceipt
from holosim.bounded_investigation_continuity import (
    InvestigationContinuityError,
)
from holosim.strict_interpretation_continuity import (
    bind_strict_interpretation_continuity,
)
from holosim.experimental_distinguishability import derive_distinguishability
import pytest


def test_strict_continuity_rejects_hash_only_subtraction():
    before = InterpretationSetReceipt(
        observation_id="obs-001",
        prior_set=("A", "B"),
        ranks={"A": 1.0, "B": 1.0},
        subtract_receipts=(),
    )

    after = InterpretationSetReceipt(
        observation_id="obs-001",
        prior_set=("A", "B"),
        ranks={"A": 1.0, "B": 1.0},
        subtract_receipts=(
            {
                "member": "B",
                "evidence_receipt_hash": "fabricated-evidence",
            },
        ),
        evidence_receipt_hashes=("fabricated-evidence",),
    )

    distinguishability = derive_distinguishability(
        candidates={"A": 0, "B": 1},
        checks={"identity": lambda value: value},
    )

    with pytest.raises(InvestigationContinuityError):
        bind_strict_interpretation_continuity(
            investigation_id="investigation-001",
            question="Which interpretation survives?",
            interpretation_before=before,
            distinguishability_receipt=distinguishability,
            interpretation_after=after,
            evidence_bundles=(),
        )


def _valid_contraction_case(*, evidence_membership=('A', 'B')):
    from holosim.canonical import stable_hash
    from holosim.check_identity import build_check_identity, bind_check_result
    from holosim.declared_verifier_execution_receipt import execute_declared_verifier
    from holosim.verified_directional_check_outcome import (
        build_verified_directional_check_outcome,
    )
    from holosim.interpretation_subtraction_target_binding import (
        interpretation_subtraction_state_hash,
        verify_interpretation_subtraction_target,
    )

    before = InterpretationSetReceipt(
        observation_id="obs-001",
        prior_set=("A", "B"),
        ranks={"A": 1.0, "B": 1.0},
        subtract_receipts=(),
    )

    identity = build_check_identity(
        check_id="check:obs-001:B",
        check_type="interpretation_discrimination",
        subject={"observation_id": "obs-001", "interpretation_id": "B"},
        reference_ids=[],
        scope={"observation_id": "obs-001"},
        evidence_references=[],
        rule_references=[],
        input_state_hash=interpretation_subtraction_state_hash(
            observation_id="obs-001",
            interpretations=list(evidence_membership),
        ),
    )

    verifier_binding = {
        "type": "declared_verifier_check_identity_binding",
        "version": 1,
        "verifier_id": identity["check_type"],
        "check_id": identity["check_id"],
        "check_identity_hash": identity["check_identity_hash"],
    }
    verifier_binding["binding_hash"] = stable_hash(verifier_binding)

    execution = execute_declared_verifier(
        verifier_check_binding=verifier_binding,
        check_identity=identity,
        available_verifiers={
            "interpretation_discrimination": lambda _: {
                "status": "INCOMPATIBLE"
            }
        },
    )

    result = bind_check_result(
        check_identity=identity,
        result=execution["result"],
        output_state_hash="state:after",
    )

    rule = {
        "type": "exact_result_match",
        "expected_result": {"status": "COMPATIBLE"},
        "match_outcome": "SUPPORTS",
        "mismatch_outcome": "CONTRADICTS",
    }

    outcome = build_verified_directional_check_outcome(
        execution_receipt=execution,
        result_binding=result,
        evaluation_rule=rule,
    )

    binding = verify_interpretation_subtraction_target(
        observation_id="obs-001",
        interpretation_id="B",
        check_identity=identity,
        directional_outcome=outcome,
        execution_receipt=execution,
        result_binding=result,
        evaluation_rule=rule,
        expected_input_state_hash=identity["input_state_hash"],
    )

    after = InterpretationSetReceipt(
        observation_id="obs-001",
        prior_set=("A", "B"),
        ranks={"A": 1.0, "B": 1.0},
        subtract_receipts=(
            {
                "member": "B",
                "evidence_receipt_hash": binding["binding_hash"],
            },
        ),
        evidence_receipt_hashes=(binding["binding_hash"],),
    )

    distinguishability = derive_distinguishability(
        candidates={"A": 0, "B": 1},
        checks={"identity": lambda value: value},
    )

    return {
        "investigation_id": "investigation-001",
        "question": "Which interpretation survives?",
        "interpretation_before": before,
        "distinguishability_receipt": distinguishability,
        "interpretation_after": after,
        "evidence_bundles": (
            {
                "interpretation_id": "B",
                "check_identity": identity,
                "directional_outcome": outcome,
                "execution_receipt": execution,
                "result_binding": result,
                "evaluation_rule": rule,
            },
        ),
    }


def test_strict_continuity_accepts_reconstructed_contradiction():
    from holosim.canonical import stable_hash

    receipt = bind_strict_interpretation_continuity(
        **_valid_contraction_case()
    )

    assert receipt["removed_interpretations"] == ["B"]
    assert receipt["verified_removed_interpretations"] == ["B"]
    assert receipt["strict_target_verification"] is True
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"

    body = {k: v for k, v in receipt.items() if k != "receipt_hash"}
    assert receipt["receipt_hash"] == stable_hash(body)


def test_strict_continuity_rejects_stale_evidence():
    with pytest.raises(
        InvestigationContinuityError,
        match="subtraction evidence verification failed",
    ):
        bind_strict_interpretation_continuity(
            **_valid_contraction_case(
                evidence_membership=("A", "C"),
            )
        )


def test_strict_continuity_rejects_wrong_evidence_target():
    case = _valid_contraction_case()

    bundle = dict(case["evidence_bundles"][0])
    bundle["interpretation_id"] = "A"

    case["evidence_bundles"] = (bundle,)

    with pytest.raises(
        InvestigationContinuityError,
        match="evidence target is not removed",
    ):
        bind_strict_interpretation_continuity(**case)


def test_strict_continuity_accepts_empty_unchanged_set():
    case = _valid_contraction_case()

    before = case["interpretation_before"]
    after = case["interpretation_after"]

    case["interpretation_before"] = InterpretationSetReceipt(
        observation_id=before.observation_id,
        prior_set=(),
        ranks={},
        subtract_receipts=(),
    )

    case["interpretation_after"] = InterpretationSetReceipt(
        observation_id=after.observation_id,
        prior_set=(),
        ranks={},
        subtract_receipts=(),
    )

    case["evidence_bundles"] = ()
    case["distinguishability_receipt"] = {
        "outcome_matrix": {},
        "unresolved_pairs": [],
        "indistinguishable_pairs": [],
        "receipt_hash": case["distinguishability_receipt"]["receipt_hash"],
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }

    receipt = bind_strict_interpretation_continuity(**case)

    assert receipt["strict_target_verification"] is True
    assert receipt["verified_removed_interpretations"] == []
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"


def test_strict_continuity_rejects_extra_unverified_subtraction():
    case = _valid_contraction_case()
    after = case["interpretation_after"]

    case["interpretation_after"] = InterpretationSetReceipt(
        observation_id=after.observation_id,
        prior_set=after.prior_set,
        ranks=after.ranks,
        subtract_receipts=(
            *after.subtract_receipts,
            {
                "member": "A",
                "evidence_receipt_hash": "unverified-extra",
            },
        ),
        evidence_receipt_hashes=after.evidence_receipt_hashes,
    )

    with pytest.raises(
        InvestigationContinuityError,
        match="unverified subtraction receipt",
    ):
        bind_strict_interpretation_continuity(**case)


def test_strict_continuity_rejects_cross_target_evidence_reuse():
    case = _valid_contraction_case()
    after = case["interpretation_after"]
    valid_hash = after.subtract_receipts[0]["evidence_receipt_hash"]

    case["interpretation_after"] = InterpretationSetReceipt(
        observation_id=after.observation_id,
        prior_set=after.prior_set,
        ranks=after.ranks,
        subtract_receipts=(
            {
                "member": "A",
                "evidence_receipt_hash": valid_hash,
            },
        ),
        evidence_receipt_hashes=(valid_hash,),
    )

    with pytest.raises(
        InvestigationContinuityError,
        match="evidence target is not removed|not every removed interpretation has verified evidence|unverified subtraction receipt",
    ):
        bind_strict_interpretation_continuity(**case)
def test_strict_continuity_rejects_unhashable_evidence_target():
    case = _valid_contraction_case()

    bundle = dict(case["evidence_bundles"][0])
    bundle["interpretation_id"] = ["B"]
    case["evidence_bundles"] = (bundle,)

    with pytest.raises(
        InvestigationContinuityError,
        match="evidence target is not removed",
    ):
        bind_strict_interpretation_continuity(**case)
