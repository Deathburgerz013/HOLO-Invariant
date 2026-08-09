from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)
from holosim.reconstructor import build_reconstructed_state
from holosim.verified_cold_start_reentry_gateway import (
    VerifiedColdStartReentryError,
    build_verified_cold_start_reentry_packet,
    validate_verified_cold_start_reentry_packet,
)


SOURCE_ITEMS = [
    {
        "id": "active-goal",
        "requires": ["verified-boundary"],
        "value": "continue current work",
    },
    {
        "id": "verified-boundary",
        "requires": [],
        "value": "observation does not grant authority",
    },
]


def _head_check(*, current_hash="head-10", current_idx=10):
    recall_kernel = {
        "identity": {"system": "HOLO-Invariant"},
        "last_verified_state": "head-10",
        "history": ["head-9", "head-10"],
    }
    contract = build_continuity_compliance_contract(
        contract_id="cold-start-contract-1",
        subject_id="HOLO-Invariant",
        recall_kernel=recall_kernel,
        observed_required_fields=list(recall_kernel),
        authority_limits=["write:NONE", "execution:NONE"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["head-changed"],
    )
    binding = build_continuity_head_binding(
        binding_id="cold-start-binding-1",
        contract=contract,
        originating_head_hash="head-10",
        originating_head_idx=10,
    )
    return evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash=current_hash,
        current_head_idx=current_idx,
    )


def _state(items=SOURCE_ITEMS, targets=("active-goal",)):
    return build_reconstructed_state("cold-start", list(targets), items)


def _packet(*, state=None, head_check=None, conflicts=()):
    return build_verified_cold_start_reentry_packet(
        packet_id="cold-start-packet-1",
        reconstructed_state=state or _state(),
        source_items=SOURCE_ITEMS,
        head_check=head_check or _head_check(),
        conflicts=list(conflicts),
    )


def test_complete_current_conflict_free_state_is_ready_without_authority():
    packet = _packet()

    assert packet["status"] == "READY_FOR_REENTRY"
    assert packet["gate_decision"] == "ALLOW"
    assert packet["carried_item_ids"] == ["active-goal", "verified-boundary"]
    assert packet["conflicts"] == []
    assert packet["truth_claimed"] is False
    assert packet["accepted"] is False
    assert packet["write_authority"] == "NONE"
    assert packet["execution_authority"] == "NONE"
    assert validate_verified_cold_start_reentry_packet(
        packet,
        source_items=SOURCE_ITEMS,
    ) is True


def test_missing_reconstruction_dependency_blocks_reentry():
    incomplete_items = [
        {"id": "active-goal", "requires": ["missing-evidence"], "value": "continue"}
    ]
    state = _state(incomplete_items)
    packet = build_verified_cold_start_reentry_packet(
        packet_id="cold-start-packet-incomplete",
        reconstructed_state=state,
        source_items=incomplete_items,
        head_check=_head_check(),
        conflicts=[],
    )

    assert state["status"] == "INCOMPLETE"
    assert packet["status"] == "BLOCKED_INCOMPLETE"
    assert packet["gate_decision"] == "BLOCK"
    assert packet["reasons"] == ["reconstruction_incomplete"]


@pytest.mark.parametrize(
    ("current_hash", "current_idx", "head_status"),
    [
        ("head-11", 11, "STALE"),
        ("other-head-10", 10, "INVALID"),
        (None, None, "UNKNOWN"),
    ],
)
def test_noncurrent_head_blocks_reentry(current_hash, current_idx, head_status):
    packet = _packet(
        head_check=_head_check(current_hash=current_hash, current_idx=current_idx)
    )

    assert packet["head_status"] == head_status
    assert packet["status"] == "BLOCKED_HEAD"
    assert packet["gate_decision"] == "BLOCK"
    assert packet["reasons"] == [f"continuity_head_status_{head_status.lower()}"]


def test_conflicts_remain_explicit_and_block_silent_reentry():
    conflicts = [
        {
            "id": "goal-conflict",
            "left_item_id": "active-goal",
            "right_item_id": "active-goal-correction",
            "reason": "two current goal claims remain unresolved",
        }
    ]

    packet = _packet(conflicts=conflicts)

    assert packet["status"] == "BLOCKED_CONFLICT"
    assert packet["gate_decision"] == "BLOCK"
    assert packet["conflicts"] == conflicts
    assert packet["reasons"] == ["unresolved_conflicts"]


def test_foreign_authority_field_is_rejected_even_after_body_is_rehashed():
    forged = deepcopy(_packet())
    forged["approval"] = "GRANTED"
    body = dict(forged)
    body.pop("packet_hash")
    forged["packet_hash"] = stable_hash(body)

    with pytest.raises(VerifiedColdStartReentryError, match="schema"):
        validate_verified_cold_start_reentry_packet(
            forged,
            source_items=SOURCE_ITEMS,
        )


def test_changed_source_invalidates_previously_valid_packet():
    packet = _packet()
    changed = deepcopy(SOURCE_ITEMS)
    changed[1]["value"] = "changed after packet construction"

    with pytest.raises(VerifiedColdStartReentryError, match="reconstructed state"):
        validate_verified_cold_start_reentry_packet(
            packet,
            source_items=changed,
        )


def test_packet_is_deterministic_for_identical_bound_inputs():
    first = _packet()
    second = _packet()

    assert first == second
    assert first["packet_hash"] == second["packet_hash"]


def test_tampered_ready_status_cannot_force_reentry():
    packet = _packet(head_check=_head_check(current_hash="head-11", current_idx=11))
    forged = deepcopy(packet)
    forged["status"] = "READY_FOR_REENTRY"
    forged["gate_decision"] = "ALLOW"

    with pytest.raises(VerifiedColdStartReentryError):
        validate_verified_cold_start_reentry_packet(
            forged,
            source_items=SOURCE_ITEMS,
        )
