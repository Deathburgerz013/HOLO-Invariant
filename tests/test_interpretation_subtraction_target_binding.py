import pytest

from holosim.canonical import stable_hash
from holosim.check_identity import build_check_identity
from holosim.interpretation_subtraction_target_binding import (
    verify_interpretation_subtraction_target,
)


def test_contradiction_about_a_cannot_subtract_b():
    identity = build_check_identity(
        check_id="check:obs-001:A",
        check_type="interpretation_discrimination",
        subject={
            "observation_id": "obs-001",
            "interpretation_id": "A",
        },
        reference_ids=[],
        scope={"observation_id": "obs-001"},
        evidence_references=[],
        rule_references=[],
        input_state_hash="state:before",
    )

    outcome = {
        "type": "verified_directional_check_outcome",
        "version": 1,
        "check_id": identity["check_id"],
        "check_identity_hash": identity["check_identity_hash"],
        "outcome": "CONTRADICTS",
        "truth_claimed": False,
        "accepted": False,
        "execution_authority": "NONE",
        "write_authority": "NONE",
    }
    outcome["outcome_hash"] = stable_hash(outcome)

    with pytest.raises(ValueError):
        verify_interpretation_subtraction_target(
            observation_id="obs-001",
            interpretation_id="B",
            check_identity=identity,
            directional_outcome=outcome,
        )


def test_fabricated_directional_outcome_cannot_authorize_subtraction():
    identity = build_check_identity(
        check_id="check:obs-001:A",
        check_type="interpretation_discrimination",
        subject={
            "observation_id": "obs-001",
            "interpretation_id": "A",
        },
        reference_ids=[],
        scope={"observation_id": "obs-001"},
        evidence_references=[],
        rule_references=[],
        input_state_hash="state:before",
    )

    fabricated_outcome = {
        "type": "verified_directional_check_outcome",
        "version": 1,
        "check_id": identity["check_id"],
        "check_identity_hash": identity["check_identity_hash"],
        "outcome": "CONTRADICTS",
        "truth_claimed": False,
        "accepted": False,
        "execution_authority": "NONE",
        "write_authority": "NONE",
    }
    fabricated_outcome["outcome_hash"] = stable_hash(fabricated_outcome)

    with pytest.raises(ValueError):
        verify_interpretation_subtraction_target(
            observation_id="obs-001",
            interpretation_id="A",
            check_identity=identity,
            directional_outcome=fabricated_outcome,
        )


def test_verified_contradiction_binds_exact_target():
    from holosim.check_identity import bind_check_result
    from holosim.declared_verifier_execution_receipt import (
        execute_declared_verifier,
    )
    from holosim.verified_directional_check_outcome import (
        build_verified_directional_check_outcome,
    )

    identity = build_check_identity(
        check_id="check:obs-001:A",
        check_type="interpretation_discrimination",
        subject={
            "observation_id": "obs-001",
            "interpretation_id": "A",
        },
        reference_ids=[],
        scope={"observation_id": "obs-001"},
        evidence_references=[],
        rule_references=[],
        input_state_hash="state:before",
    )

    verifier_binding = {
        "type": "declared_verifier_check_identity_binding",
        "version": 1,
        "verifier_id": identity["check_type"],
        "check_id": identity["check_id"],
        "check_identity_hash": identity["check_identity_hash"],
        "execution_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
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
        interpretation_id="A",
        check_identity=identity,
        directional_outcome=outcome,
        execution_receipt=execution,
        result_binding=result,
        evaluation_rule=rule,
    )

    assert binding["target_binding_verified"] is True
    assert binding["interpretation_id"] == "A"
    assert binding["directional_outcome_hash"] == outcome["outcome_hash"]
    assert binding["truth_claimed"] is False
    assert binding["accepted"] is False
    assert binding["write_authority"] == "NONE"


def test_tampered_execution_receipt_fails_closed():
    from holosim.check_identity import bind_check_result
    from holosim.declared_verifier_execution_receipt import (
        execute_declared_verifier,
    )
    from holosim.verified_directional_check_outcome import (
        build_verified_directional_check_outcome,
    )

    identity = build_check_identity(
        check_id="check:obs-001:A",
        check_type="interpretation_discrimination",
        subject={
            "observation_id": "obs-001",
            "interpretation_id": "A",
        },
        reference_ids=[],
        scope={"observation_id": "obs-001"},
        evidence_references=[],
        rule_references=[],
        input_state_hash="state:before",
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

    execution["result"] = {"status": "TAMPERED"}

    with pytest.raises(ValueError):
        verify_interpretation_subtraction_target(
            observation_id="obs-001",
            interpretation_id="A",
            check_identity=identity,
            directional_outcome=outcome,
            execution_receipt=execution,
            result_binding=result,
            evaluation_rule=rule,
        )


def test_different_check_identity_cannot_reuse_outcome():
    from holosim.check_identity import bind_check_result
    from holosim.declared_verifier_execution_receipt import execute_declared_verifier
    from holosim.verified_directional_check_outcome import (
        build_verified_directional_check_outcome,
    )

    def make_identity(check_id):
        return build_check_identity(
            check_id=check_id,
            check_type="interpretation_discrimination",
            subject={
                "observation_id": "obs-001",
                "interpretation_id": "A",
            },
            reference_ids=[],
            scope={"observation_id": "obs-001"},
            evidence_references=[],
            rule_references=[],
            input_state_hash="state:before",
        )

    original = make_identity("check:original")
    substituted = make_identity("check:substituted")

    verifier_binding = {
        "type": "declared_verifier_check_identity_binding",
        "version": 1,
        "verifier_id": original["check_type"],
        "check_id": original["check_id"],
        "check_identity_hash": original["check_identity_hash"],
    }
    verifier_binding["binding_hash"] = stable_hash(verifier_binding)

    execution = execute_declared_verifier(
        verifier_check_binding=verifier_binding,
        check_identity=original,
        available_verifiers={
            "interpretation_discrimination": lambda _: {
                "status": "INCOMPATIBLE"
            }
        },
    )

    result = bind_check_result(
        check_identity=original,
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

    with pytest.raises(ValueError):
        verify_interpretation_subtraction_target(
            observation_id="obs-001",
            interpretation_id="A",
            check_identity=substituted,
            directional_outcome=outcome,
            execution_receipt=execution,
            result_binding=result,
            evaluation_rule=rule,
        )


@pytest.mark.parametrize("direction", ["SUPPORTS", "UNKNOWN"])
def test_noncontradictory_outcome_cannot_authorize_subtraction(direction):
    from holosim.check_identity import bind_check_result
    from holosim.declared_verifier_execution_receipt import execute_declared_verifier
    from holosim.verified_directional_check_outcome import (
        build_verified_directional_check_outcome,
    )

    identity = build_check_identity(
        check_id="check:obs-001:A",
        check_type="interpretation_discrimination",
        subject={
            "observation_id": "obs-001",
            "interpretation_id": "A",
        },
        reference_ids=[],
        scope={"observation_id": "obs-001"},
        evidence_references=[],
        rule_references=[],
        input_state_hash="state:before",
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
                "status": "COMPATIBLE"
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
        "match_outcome": direction,
        "mismatch_outcome": "CONTRADICTS",
    }

    outcome = build_verified_directional_check_outcome(
        execution_receipt=execution,
        result_binding=result,
        evaluation_rule=rule,
    )

    assert outcome["outcome"] == direction

    with pytest.raises(ValueError):
        verify_interpretation_subtraction_target(
            observation_id="obs-001",
            interpretation_id="A",
            check_identity=identity,
            directional_outcome=outcome,
            execution_receipt=execution,
            result_binding=result,
            evaluation_rule=rule,
        )


def test_subtraction_state_hash_is_deterministic_and_membership_sensitive():
    from holosim.interpretation_subtraction_target_binding import (
        interpretation_subtraction_state_hash,
    )

    original = interpretation_subtraction_state_hash(
        observation_id="obs-001",
        interpretations=["A", "B"],
    )

    repeated = interpretation_subtraction_state_hash(
        observation_id="obs-001",
        interpretations=["A", "B"],
    )

    changed = interpretation_subtraction_state_hash(
        observation_id="obs-001",
        interpretations=["A", "C"],
    )

    assert original == repeated
    assert original != changed
    assert len(original) == 64


def test_stale_input_state_is_rejected():
    from holosim.interpretation_subtraction_target_binding import (
        interpretation_subtraction_state_hash,
    )

    identity = build_check_identity(
        check_id="check:stale",
        check_type="interpretation_discrimination",
        subject={
            "observation_id": "obs-001",
            "interpretation_id": "A",
        },
        reference_ids=[],
        scope={"observation_id": "obs-001"},
        evidence_references=[],
        rule_references=[],
        input_state_hash=interpretation_subtraction_state_hash(
            observation_id="obs-001",
            interpretations=["A", "B"],
        ),
    )

    current_state_hash = interpretation_subtraction_state_hash(
        observation_id="obs-001",
        interpretations=["A", "C"],
    )

    with pytest.raises(ValueError, match="input state identity mismatch"):
        verify_interpretation_subtraction_target(
            observation_id="obs-001",
            interpretation_id="A",
            check_identity=identity,
            directional_outcome={},
            expected_input_state_hash=current_state_hash,
        )


def test_empty_interpretation_state_has_stable_hash():
    from holosim.interpretation_subtraction_target_binding import (
        interpretation_subtraction_state_hash,
    )

    empty_hash = interpretation_subtraction_state_hash(
        observation_id="observation-empty",
        interpretations=[],
    )

    assert empty_hash == interpretation_subtraction_state_hash(
        observation_id="observation-empty",
        interpretations=(),
    )

    assert empty_hash == stable_hash({
        "type": "interpretation_subtraction_input_state",
        "version": 1,
        "observation_id": "observation-empty",
        "interpretations": [],
    })
