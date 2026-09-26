from holosim.competing_head_detection import detect_competing_heads
from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_head_binding import build_continuity_head_binding, evaluate_continuity_head_binding
from holosim.continuation_conflict_composition import evaluate_continuation_admissibility


RECALL_KERNEL = {
    "identity": {"system": "HOLO-Invariant"},
    "last_verified_state": "state-10",
    "history": ["state-9", "state-10"],
}


def _head_check(*, current: bool):
    contract = build_continuity_compliance_contract(
        contract_id="continuity-contract-composition-1",
        subject_id="HOLO-Invariant",
        recall_kernel=RECALL_KERNEL,
        observed_required_fields=["identity", "last_verified_state", "history"],
        authority_limits=["write:NONE"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["head-changed"],
    )
    binding = build_continuity_head_binding(
        binding_id="continuity-binding-composition-1",
        contract=contract,
        originating_head_hash="head-hash-10",
        originating_head_idx=10,
    )
    return evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash="head-hash-10" if current else "head-hash-11",
        current_head_idx=10 if current else 11,
    )


def _fork_check(*, conflict: bool):
    heads = [{"head_hash": "head-a", "parent_hash": "parent-1"}]
    if conflict:
        heads.append({"head_hash": "head-b", "parent_hash": "parent-1"})
    return detect_competing_heads(heads=heads)


def test_current_without_fork_allows():
    result = evaluate_continuation_admissibility(
        head_check=_head_check(current=True),
        fork_check=_fork_check(conflict=False),
    )
    assert result["decision"] == "ALLOW"
    assert result["reasons"] == []
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_current_with_conflict_blocks():
    result = evaluate_continuation_admissibility(
        head_check=_head_check(current=True),
        fork_check=_fork_check(conflict=True),
    )
    assert result["decision"] == "BLOCK"
    assert result["reasons"] == ["competing_heads_conflict"]


def test_stale_without_fork_still_blocks():
    result = evaluate_continuation_admissibility(
        head_check=_head_check(current=False),
        fork_check=_fork_check(conflict=False),
    )
    assert result["decision"] == "BLOCK"
    assert result["reasons"] == ["continuity_head_status_stale"]


def test_stale_with_conflict_blocks_and_preserves_both_reasons():
    result = evaluate_continuation_admissibility(
        head_check=_head_check(current=False),
        fork_check=_fork_check(conflict=True),
    )
    assert result["decision"] == "BLOCK"
    assert result["reasons"] == ["continuity_head_status_stale", "competing_heads_conflict"]


from copy import deepcopy

import pytest

from holosim.continuation_conflict_composition import ContinuationConflictCompositionError


def test_tampered_head_check_cannot_force_allow():
    head_check = _head_check(current=False)
    tampered = deepcopy(head_check)
    tampered["status"] = "CURRENT"
    with pytest.raises(ContinuationConflictCompositionError, match="head_check hash does not match content"):
        evaluate_continuation_admissibility(head_check=tampered, fork_check=_fork_check(conflict=False))


def test_tampered_fork_check_cannot_hide_conflict():
    fork_check = _fork_check(conflict=True)
    tampered = deepcopy(fork_check)
    tampered["status"] = "NO_FORK"
    with pytest.raises(ContinuationConflictCompositionError, match="fork_check hash does not match content"):
        evaluate_continuation_admissibility(head_check=_head_check(current=True), fork_check=tampered)


@pytest.mark.parametrize(
    ("current_hash", "current_idx", "expected_reason"),
    [
        ("different-head-hash-10", 10, "continuity_head_status_invalid"),
        (None, None, "continuity_head_status_unknown"),
    ],
)
def test_noncurrent_head_states_block(current_hash, current_idx, expected_reason):
    contract = build_continuity_compliance_contract(
        contract_id="continuity-contract-composition-state",
        subject_id="HOLO-Invariant",
        recall_kernel=RECALL_KERNEL,
        observed_required_fields=["identity", "last_verified_state", "history"],
        authority_limits=["write:NONE"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["head-changed"],
    )
    binding = build_continuity_head_binding(
        binding_id="continuity-binding-composition-state",
        contract=contract,
        originating_head_hash="head-hash-10",
        originating_head_idx=10,
    )
    head_check = evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash=current_hash,
        current_head_idx=current_idx,
    )
    result = evaluate_continuation_admissibility(head_check=head_check, fork_check=_fork_check(conflict=False))
    assert result["decision"] == "BLOCK"
    assert result["reasons"] == [expected_reason]


def test_composition_receipt_is_deterministic():
    head_check = _head_check(current=True)
    fork_check = _fork_check(conflict=False)
    first = evaluate_continuation_admissibility(head_check=head_check, fork_check=fork_check)
    second = evaluate_continuation_admissibility(head_check=head_check, fork_check=fork_check)
    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]


def test_composition_does_not_mutate_inputs():
    head_check = _head_check(current=True)
    fork_check = _fork_check(conflict=True)
    head_before = deepcopy(head_check)
    fork_before = deepcopy(fork_check)
    evaluate_continuation_admissibility(head_check=head_check, fork_check=fork_check)
    assert head_check == head_before
    assert fork_check == fork_before
