from copy import deepcopy

from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_head_binding import (
    ContinuityHeadBindingError,
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)


RECALL_KERNEL = {
    "identity": {"system": "HOLO-Invariant"},
    "history": ["state-1", "state-2"],
    "last_verified_state": "state-2",
    "capabilities_and_limits": {"can": ["read", "compare"], "cannot": ["deploy"]},
}


def _contract(contract_id="continuity-contract-1"):
    return build_continuity_compliance_contract(
        contract_id=contract_id,
        subject_id="HOLO-Invariant",
        recall_kernel=RECALL_KERNEL,
        observed_required_fields=list(RECALL_KERNEL),
        authority_limits=["write:NONE"],
        unresolved_gap_ids=["gap-1"],
        recheck_condition_ids=["state-changed"],
    )


def _binding(contract=None):
    contract = contract or _contract()
    return build_continuity_head_binding(
        binding_id="continuity-head-binding-1",
        contract=contract,
        originating_head_hash="head-hash-10",
        originating_head_idx=10,
    )


def test_bound_contract_is_current_only_when_verified_head_identity_still_matches():
    contract = _contract()
    binding = _binding(contract)

    result = evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash="head-hash-10",
        current_head_idx=10,
    )

    assert result["status"] == "CURRENT"
    assert result["reasons"] == []
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_newer_verified_head_makes_prior_continuity_contract_stale():
    contract = _contract()
    binding = _binding(contract)

    result = evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash="head-hash-11",
        current_head_idx=11,
    )

    assert result["status"] == "STALE"
    assert result["reasons"] == ["newer_verified_head_exists"]


def test_missing_or_older_current_head_cannot_be_promoted_to_current():
    contract = _contract()
    binding = _binding(contract)

    unavailable = evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash=None,
        current_head_idx=None,
    )
    older = evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash="head-hash-9",
        current_head_idx=9,
    )

    assert unavailable["status"] == "UNKNOWN"
    assert unavailable["reasons"] == ["current_head_unavailable"]
    assert older["status"] == "UNKNOWN"
    assert older["reasons"] == ["current_head_precedes_origin"]


def test_same_index_different_hash_or_wrong_contract_is_invalid():
    contract = _contract()
    binding = _binding(contract)

    same_index_mismatch = evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash="different-head-hash-10",
        current_head_idx=10,
    )
    assert same_index_mismatch["status"] == "INVALID"
    assert same_index_mismatch["reasons"] == ["same_index_head_hash_mismatch"]

    other_contract = _contract("continuity-contract-2")
    wrong_contract = evaluate_continuity_head_binding(
        binding=binding,
        contract=other_contract,
        current_head_hash="head-hash-10",
        current_head_idx=10,
    )
    assert wrong_contract["status"] == "INVALID"
    assert wrong_contract["reasons"] == ["contract_binding_mismatch"]


def test_binding_is_tamper_evident():
    contract = _contract()
    binding = _binding(contract)
    tampered = deepcopy(binding)
    tampered["originating_head_idx"] = 999

    try:
        evaluate_continuity_head_binding(
            binding=tampered,
            contract=contract,
            current_head_hash="head-hash-10",
            current_head_idx=10,
        )
    except ContinuityHeadBindingError as exc:
        assert "binding hash does not match content" in str(exc)
    else:
        raise AssertionError("tampered binding must fail closed")
