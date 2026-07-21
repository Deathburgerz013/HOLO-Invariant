from copy import deepcopy

import pytest

from holosim.check_audit import CheckAuditError, audit_check
from holosim.check_identity import bind_check_result, build_check_identity


def prior_package(*, justified: bool = True):
    identity = build_check_identity(
        check_id="check-1",
        check_type="example_check",
        subject={"claim_id": "claim-1"},
        reference_ids=["ref-1"],
        scope={"boundary": "fixture"},
        evidence_references=["evidence-1"],
        rule_references=["rule-1"],
        input_state_hash="state-in",
    )
    binding = bind_check_result(
        check_identity=identity,
        result={"outcome": "PASS"},
        output_state_hash="state-out",
        justifier_reference="justifier-1" if justified else None,
    )
    return identity, binding


def available_refs():
    return ["ref-1", "evidence-1", "rule-1", "justifier-1"]


def test_valid_double_check_has_its_own_identity_and_binding():
    identity, binding = prior_package()

    audit = audit_check(
        audit_check_id="audit-1",
        check_identity=identity,
        result_binding=binding,
        current_state_hash="state-out",
        available_reference_ids=available_refs(),
    )

    audit_identity = audit["audit_identity"]
    audit_binding = audit["audit_result_binding"]
    result = audit_binding["result"]

    assert audit_identity["type"] == "check_identity"
    assert audit_identity["check_id"] == "audit-1"
    assert audit_identity["check_type"] == "check_audit"
    assert audit_identity["subject"]["audited_check_id"] == "check-1"
    assert result["status"] == "VALID"
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert audit_binding["check_identity_hash"] == audit_identity["check_identity_hash"]
    assert audit_identity["check_identity_hash"] != identity["check_identity_hash"]


def test_changed_current_state_marks_prior_check_stale():
    identity, binding = prior_package()

    audit = audit_check(
        audit_check_id="audit-stale",
        check_identity=identity,
        result_binding=binding,
        current_state_hash="state-new",
        available_reference_ids=available_refs(),
    )

    assert audit["audit_result_binding"]["result"]["status"] == "STALE"


def test_missing_required_reference_blocks_reliance():
    identity, binding = prior_package()

    audit = audit_check(
        audit_check_id="audit-blocked",
        check_identity=identity,
        result_binding=binding,
        current_state_hash="state-out",
        available_reference_ids=["ref-1", "rule-1", "justifier-1"],
    )

    result = audit["audit_result_binding"]["result"]
    assert result["status"] == "BLOCKED"
    assert result["missing_reference_ids"] == ["evidence-1"]


def test_missing_justifier_is_unjustified_after_references_are_available():
    identity, binding = prior_package(justified=False)

    audit = audit_check(
        audit_check_id="audit-unjustified",
        check_identity=identity,
        result_binding=binding,
        current_state_hash="state-out",
        available_reference_ids=["ref-1", "evidence-1", "rule-1"],
    )

    assert audit["audit_result_binding"]["result"]["status"] == "UNJUSTIFIED"


def test_explicit_unresolved_conflict_wins_over_other_reliance_states():
    identity, binding = prior_package()

    audit = audit_check(
        audit_check_id="audit-conflicted",
        check_identity=identity,
        result_binding=binding,
        current_state_hash="state-new",
        available_reference_ids=[],
        unresolved_conflicts=["conflict-1"],
    )

    assert audit["audit_result_binding"]["result"]["status"] == "CONFLICTED"


def test_tampered_prior_check_identity_is_rejected():
    identity, binding = prior_package()
    tampered = deepcopy(identity)
    tampered["subject"]["claim_id"] = "claim-2"

    with pytest.raises(CheckAuditError, match="check_identity hash"):
        audit_check(
            audit_check_id="audit-tampered-identity",
            check_identity=tampered,
            result_binding=binding,
            current_state_hash="state-out",
            available_reference_ids=available_refs(),
        )


def test_tampered_result_binding_is_rejected():
    identity, binding = prior_package()
    tampered = deepcopy(binding)
    tampered["result"]["outcome"] = "FAIL"

    with pytest.raises(CheckAuditError, match="result_binding hash"):
        audit_check(
            audit_check_id="audit-tampered-binding",
            check_identity=identity,
            result_binding=tampered,
            current_state_hash="state-out",
            available_reference_ids=available_refs(),
        )
