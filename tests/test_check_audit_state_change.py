from holosim.check_audit import AUDIT_STATUS_STALE, AUDIT_STATUS_VALID, audit_check
from holosim.check_identity import bind_check_result, build_check_identity


def _prior_check_package():
    identity = build_check_identity(
        check_id="prior-check-1",
        check_type="example_check",
        subject={"claim_id": "claim-1"},
        reference_ids=["reference-1"],
        scope={"boundary": "example"},
        evidence_references=["evidence-1"],
        rule_references=["rule-1"],
        input_state_hash="state-before",
    )
    binding = bind_check_result(
        check_identity=identity,
        result={"status": "SUPPORTED"},
        output_state_hash="state-after-check",
        justifier_reference="justifier-1",
    )
    return identity, binding


def test_same_prior_check_transitions_from_valid_to_stale_when_state_changes():
    identity, binding = _prior_check_package()
    available = ["reference-1", "evidence-1", "rule-1", "justifier-1"]

    valid_audit = audit_check(
        audit_check_id="audit-valid",
        check_identity=identity,
        result_binding=binding,
        current_state_hash="state-after-check",
        available_reference_ids=available,
    )
    stale_audit = audit_check(
        audit_check_id="audit-stale",
        check_identity=identity,
        result_binding=binding,
        current_state_hash="state-after-change",
        available_reference_ids=available,
    )

    valid_result = valid_audit["audit_result_binding"]["result"]
    stale_result = stale_audit["audit_result_binding"]["result"]

    assert valid_result["status"] == AUDIT_STATUS_VALID
    assert stale_result["status"] == AUDIT_STATUS_STALE
    assert stale_result["prior_output_state_hash"] == "state-after-check"
    assert stale_result["current_state_hash"] == "state-after-change"
    assert stale_result["audited_check_identity_hash"] == identity["check_identity_hash"]
    assert stale_result["audited_binding_hash"] == binding["binding_hash"]
    assert stale_result["truth_claimed"] is False
    assert stale_result["accepted"] is False
    assert stale_result["write_authority"] == "NONE"


def test_state_change_creates_a_distinct_identified_audit_without_rewriting_prior_check():
    identity, binding = _prior_check_package()
    identity_before = dict(identity)
    binding_before = dict(binding)
    available = ["reference-1", "evidence-1", "rule-1", "justifier-1"]

    valid_audit = audit_check(
        audit_check_id="audit-valid",
        check_identity=identity,
        result_binding=binding,
        current_state_hash="state-after-check",
        available_reference_ids=available,
    )
    stale_audit = audit_check(
        audit_check_id="audit-stale",
        check_identity=identity,
        result_binding=binding,
        current_state_hash="state-after-change",
        available_reference_ids=available,
    )

    assert identity == identity_before
    assert binding == binding_before
    assert valid_audit["audit_identity"]["check_identity_hash"] != stale_audit["audit_identity"]["check_identity_hash"]
    assert valid_audit["audit_result_binding"]["binding_hash"] != stale_audit["audit_result_binding"]["binding_hash"]
    assert stale_audit["audit_identity"]["subject"]["audited_check_identity_hash"] == identity["check_identity_hash"]
    assert stale_audit["audit_identity"]["subject"]["audited_binding_hash"] == binding["binding_hash"]
