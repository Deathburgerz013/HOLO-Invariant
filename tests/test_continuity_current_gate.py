from copy import deepcopy

import pytest

from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_current_gate import (
    ContinuityCurrentGateError,
    evaluate_continuity_current_gate,
    require_current_continuity,
)
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)


RECALL_KERNEL = {
    "identity": {"system": "HOLO-Invariant"},
    "last_verified_state": "state-10",
    "history": ["state-9", "state-10"],
}


def _contract():
    return build_continuity_compliance_contract(
        contract_id="continuity-contract-gate-1",
        subject_id="HOLO-Invariant",
        recall_kernel=RECALL_KERNEL,
        observed_required_fields=["identity", "last_verified_state", "history"],
        authority_limits=["write:NONE"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["head-changed"],
    )


def _head_check(*, current_hash, current_idx):
    contract = _contract()
    binding = build_continuity_head_binding(
        binding_id="continuity-binding-gate-1",
        contract=contract,
        originating_head_hash="head-hash-10",
        originating_head_idx=10,
    )
    return evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash=current_hash,
        current_head_idx=current_idx,
    )


def test_current_handoff_is_the_only_status_allowed_through_gate():
    head_check = _head_check(current_hash="head-hash-10", current_idx=10)

    result = require_current_continuity(head_check=head_check)

    assert head_check["status"] == "CURRENT"
    assert result["decision"] == "ALLOW"
    assert result["head_status"] == "CURRENT"
    assert result["reasons"] == []
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


@pytest.mark.parametrize(
    ("current_hash", "current_idx", "expected_status"),
    [
        ("head-hash-11", 11, "STALE"),
        ("different-head-hash-10", 10, "INVALID"),
        (None, None, "UNKNOWN"),
    ],
)
def test_stale_invalid_and_unknown_handoffs_fail_closed_before_continuation(
    current_hash, current_idx, expected_status
):
    head_check = _head_check(current_hash=current_hash, current_idx=current_idx)
    continuation_called = False

    def continue_from_handoff():
        nonlocal continuation_called
        continuation_called = True

    with pytest.raises(ContinuityCurrentGateError, match="continuation blocked"):
        require_current_continuity(head_check=head_check)
        continue_from_handoff()

    assert head_check["status"] == expected_status
    assert continuation_called is False


def test_gate_decision_exposes_block_reason_without_granting_authority():
    head_check = _head_check(current_hash="head-hash-11", current_idx=11)

    result = evaluate_continuity_current_gate(head_check=head_check)

    assert result["decision"] == "BLOCK"
    assert result["head_status"] == "STALE"
    assert result["reasons"] == ["continuity_head_status_stale"]
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_tampered_head_check_cannot_be_used_to_force_allow():
    head_check = _head_check(current_hash="head-hash-11", current_idx=11)
    tampered = deepcopy(head_check)
    tampered["status"] = "CURRENT"

    with pytest.raises(ContinuityCurrentGateError, match="head_check hash does not match content"):
        require_current_continuity(head_check=tampered)
