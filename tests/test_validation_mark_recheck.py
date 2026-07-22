from copy import deepcopy

from holosim.check_audit import AUDIT_STATUS_STALE, AUDIT_STATUS_VALID
from holosim.validation_mark_recheck import (
    MARK_FALSIFIED,
    MARK_SUPPORTED,
    RELATION_CHANGED,
    RELATION_PRESERVED,
    RELATION_REVALIDATED,
    build_validation_mark,
    recheck_validation_mark,
)


REFERENCE_IDS = ["artifact:source", "rule:scope", "justifier:human-check"]


def _prior_mark():
    return build_validation_mark(
        check_id="validation:claim-x:t0",
        subject={"claim_id": "claim-x", "claim": "X holds"},
        reference_ids=["artifact:source"],
        scope={"environment": "fixture", "state": "t0"},
        evidence_references=["artifact:source"],
        rule_references=["rule:scope"],
        input_state_hash="state:t0:input",
        mark=MARK_SUPPORTED,
        output_state_hash="state:t0",
        justifier_reference="justifier:human-check",
    )


def test_same_bounded_state_preserves_prior_mark_without_rewriting_history():
    prior = _prior_mark()
    original = deepcopy(prior)

    result = recheck_validation_mark(
        recheck_check_id="validation:claim-x:t0:recheck",
        prior_check_identity=prior["check_identity"],
        prior_result_binding=prior["result_binding"],
        current_state_hash="state:t0",
        available_reference_ids=REFERENCE_IDS,
        current_mark=MARK_SUPPORTED,
        current_output_state_hash="state:t0",
        current_justifier_reference="justifier:human-check",
    )

    recheck = result["recheck_result_binding"]["result"]
    assert result["prior_audit"]["audit_result_binding"]["result"]["status"] == AUDIT_STATUS_VALID
    assert recheck["relation"] == RELATION_PRESERVED
    assert recheck["prior_mark"] == MARK_SUPPORTED
    assert recheck["current_mark"] == MARK_SUPPORTED
    assert prior == original
    assert result["prior"] == original


def test_changed_state_stales_old_mark_and_emits_new_linked_revalidation():
    prior = _prior_mark()

    result = recheck_validation_mark(
        recheck_check_id="validation:claim-x:t1:recheck",
        prior_check_identity=prior["check_identity"],
        prior_result_binding=prior["result_binding"],
        current_state_hash="state:t1",
        available_reference_ids=REFERENCE_IDS,
        current_mark=MARK_SUPPORTED,
        current_output_state_hash="state:t1",
        current_justifier_reference="justifier:human-check",
    )

    audit_result = result["prior_audit"]["audit_result_binding"]["result"]
    recheck = result["recheck_result_binding"]["result"]
    assert audit_result["status"] == AUDIT_STATUS_STALE
    assert recheck["relation"] == RELATION_REVALIDATED
    assert recheck["prior_check_identity_hash"] == prior["check_identity"]["check_identity_hash"]
    assert recheck["prior_binding_hash"] == prior["result_binding"]["binding_hash"]
    assert result["recheck_identity"]["check_identity_hash"] != prior["check_identity"]["check_identity_hash"]
    assert result["recheck_result_binding"]["binding_hash"] != prior["result_binding"]["binding_hash"]


def test_present_falsification_changes_mark_without_rewriting_prior_supported_mark():
    prior = _prior_mark()
    original_identity_hash = prior["check_identity"]["check_identity_hash"]
    original_binding_hash = prior["result_binding"]["binding_hash"]

    result = recheck_validation_mark(
        recheck_check_id="validation:claim-x:t1:falsified",
        prior_check_identity=prior["check_identity"],
        prior_result_binding=prior["result_binding"],
        current_state_hash="state:t1",
        available_reference_ids=REFERENCE_IDS,
        current_mark=MARK_FALSIFIED,
        current_output_state_hash="state:t1",
        current_justifier_reference="justifier:human-check",
    )

    recheck = result["recheck_result_binding"]["result"]
    assert recheck["prior_mark"] == MARK_SUPPORTED
    assert recheck["current_mark"] == MARK_FALSIFIED
    assert recheck["relation"] == RELATION_CHANGED
    assert prior["check_identity"]["check_identity_hash"] == original_identity_hash
    assert prior["result_binding"]["binding_hash"] == original_binding_hash
    assert result["recheck_result_binding"]["accepted"] is False
    assert result["recheck_result_binding"]["write_authority"] == "NONE"


def test_recheck_is_deterministic_for_identical_present_inputs():
    prior = _prior_mark()
    kwargs = dict(
        recheck_check_id="validation:claim-x:t1:repeatable",
        prior_check_identity=prior["check_identity"],
        prior_result_binding=prior["result_binding"],
        current_state_hash="state:t1",
        available_reference_ids=REFERENCE_IDS,
        current_mark=MARK_SUPPORTED,
        current_output_state_hash="state:t1",
        current_justifier_reference="justifier:human-check",
    )

    first = recheck_validation_mark(**kwargs)
    second = recheck_validation_mark(**kwargs)
    assert first == second
