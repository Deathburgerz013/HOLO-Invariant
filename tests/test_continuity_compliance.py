from copy import deepcopy

from holosim.continuity_compliance import (
    ContinuityComplianceError,
    build_continuity_compliance_contract,
    evaluate_continuity_attestation,
)


RECALL_KERNEL = {
    "identity": {"system": "HOLO-Invariant"},
    "history": ["state-1", "state-2"],
    "last_verified_state": "state-2",
    "capabilities_and_limits": {"can": ["read", "compare"], "cannot": ["deploy"]},
    "corrections": ["corr-1"],
    "unresolved_gaps": ["gap-1"],
    "authority": {"write": "NONE"},
    "recheck_conditions": ["state-changed"],
}


def _contract():
    return build_continuity_compliance_contract(
        contract_id="continuity-contract-1",
        subject_id="HOLO-Invariant",
        recall_kernel=RECALL_KERNEL,
        observed_required_fields=[
            "identity",
            "history",
            "last_verified_state",
            "capabilities_and_limits",
        ],
        authority_limits=["write:NONE", "deploy:human-authorized-only"],
        unresolved_gap_ids=["gap-1"],
        recheck_condition_ids=["state-changed"],
    )


def test_fresh_instance_is_compliant_only_when_exact_kernel_and_boundaries_are_acknowledged():
    contract = _contract()

    result = evaluate_continuity_attestation(
        contract=contract,
        instance_id="model-instance-A",
        recalled_kernel_hash=contract["recall_kernel_hash"],
        recalled_fields=list(RECALL_KERNEL),
        acknowledged_authority_limits=["write:NONE", "deploy:human-authorized-only"],
        acknowledged_unresolved_gap_ids=["gap-1"],
        acknowledged_recheck_condition_ids=["state-changed"],
    )

    assert result["status"] == "COMPLIANT"
    assert result["kernel_hash_matches"] is True
    assert result["noncompliance_reasons"] == []
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_instance_that_omits_observed_required_history_or_capability_is_noncompliant():
    contract = _contract()

    result = evaluate_continuity_attestation(
        contract=contract,
        instance_id="model-instance-B",
        recalled_kernel_hash=contract["recall_kernel_hash"],
        recalled_fields=["identity", "last_verified_state", "corrections"],
        acknowledged_authority_limits=["write:NONE", "deploy:human-authorized-only"],
        acknowledged_unresolved_gap_ids=["gap-1"],
        acknowledged_recheck_condition_ids=["state-changed"],
    )

    assert result["status"] == "NONCOMPLIANT"
    assert result["missing_observed_required_fields"] == [
        "history",
        "capabilities_and_limits",
    ]
    assert "observed_required_fields_missing" in result["noncompliance_reasons"]


def test_same_words_from_wrong_kernel_do_not_count_as_continuity_compliance():
    contract = _contract()

    result = evaluate_continuity_attestation(
        contract=contract,
        instance_id="model-instance-C",
        recalled_kernel_hash="different-kernel-hash",
        recalled_fields=list(RECALL_KERNEL),
        acknowledged_authority_limits=["write:NONE", "deploy:human-authorized-only"],
        acknowledged_unresolved_gap_ids=["gap-1"],
        acknowledged_recheck_condition_ids=["state-changed"],
    )

    assert result["status"] == "NONCOMPLIANT"
    assert result["kernel_hash_matches"] is False
    assert "recall_kernel_hash_mismatch" in result["noncompliance_reasons"]


def test_contract_is_tamper_evident_and_does_not_claim_universal_recall_requirements():
    contract = _contract()
    assert contract["universal_requirement_claimed"] is False
    assert contract["truth_claimed"] is False
    assert contract["accepted"] is False
    assert contract["write_authority"] == "NONE"

    tampered = deepcopy(contract)
    tampered["authority_limits"] = []

    try:
        evaluate_continuity_attestation(
            contract=tampered,
            instance_id="model-instance-D",
            recalled_kernel_hash=contract["recall_kernel_hash"],
            recalled_fields=list(RECALL_KERNEL),
            acknowledged_authority_limits=[],
            acknowledged_unresolved_gap_ids=["gap-1"],
            acknowledged_recheck_condition_ids=["state-changed"],
        )
    except ContinuityComplianceError as exc:
        assert "contract hash does not match content" in str(exc)
    else:
        raise AssertionError("tampered contract must fail closed")
