from copy import deepcopy

import pytest

from holosim.canonical import canonical_bytes, stable_hash
from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)
from holosim.reconstructor import build_reconstructed_state
from holosim.verified_cold_start_reentry_gateway import (
    VerifiedColdStartReentryError,
    build_verified_cold_start_reentry_packet,
    compare_observer_reentry_packets,
    evaluate_reentry_packet_budget,
    validate_observer_reentry_comparison,
    validate_reentry_packet_budget_check,
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


def _comparison(left, right, *, right_items=SOURCE_ITEMS):
    return compare_observer_reentry_packets(
        left=left,
        left_source_items=SOURCE_ITEMS,
        right=right,
        right_source_items=right_items,
        left_observer_id="observer-a",
        right_observer_id="observer-b",
    )


def test_matching_independent_packets_do_not_grant_truth_or_authority():
    left = _packet()
    right = build_verified_cold_start_reentry_packet(
        packet_id="other-observer-packet",
        reconstructed_state=_state(),
        source_items=SOURCE_ITEMS,
        head_check=_head_check(),
        conflicts=[],
    )
    comparison = _comparison(left, right)

    assert comparison["status"] == "MATCHED"
    assert comparison["conflicts"] == []
    assert comparison["truth_claimed"] is False
    assert comparison["accepted"] is False
    assert comparison["write_authority"] == "NONE"
    assert comparison["execution_authority"] == "NONE"
    assert validate_observer_reentry_comparison(
        comparison, left=left, left_source_items=SOURCE_ITEMS,
        right=right, right_source_items=SOURCE_ITEMS,
    ) is True


def test_disagreement_is_explicit_and_blocks_existing_gateway():
    changed_items = deepcopy(SOURCE_ITEMS)
    changed_items[0]["value"] = "stop current work"
    left = _packet()
    right = build_verified_cold_start_reentry_packet(
        packet_id="other-observer-packet",
        reconstructed_state=_state(changed_items),
        source_items=changed_items,
        head_check=_head_check(),
        conflicts=[],
    )
    comparison = _comparison(left, right, right_items=changed_items)
    blocked = _packet(conflicts=comparison["conflicts"])

    assert comparison["status"] == "BLOCKED_CONFLICT"
    assert comparison["conflicts"][0]["left_state_hash"] == left["reconstructed_state_hash"]
    assert comparison["conflicts"][0]["right_state_hash"] == right["reconstructed_state_hash"]
    assert blocked["status"] == "BLOCKED_CONFLICT"
    assert blocked["gate_decision"] == "BLOCK"
    assert validate_observer_reentry_comparison(
        comparison, left=left, left_source_items=SOURCE_ITEMS,
        right=right, right_source_items=changed_items,
    ) is True


def test_different_head_or_scope_does_not_claim_agreement():
    left = _packet()
    other_scope = build_verified_cold_start_reentry_packet(
        packet_id="other-scope",
        reconstructed_state=_state(targets=("verified-boundary",)),
        source_items=SOURCE_ITEMS,
        head_check=_head_check(),
        conflicts=[],
    )
    assert _comparison(left, other_scope)["status"] == "BLOCKED_SCOPE"
    stale = _packet(head_check=_head_check(current_hash="head-11", current_idx=11))
    assert _comparison(left, stale)["status"] == "BLOCKED_INPUT"


def test_comparison_rejects_tampering_and_changed_source_items():
    left = _packet()
    right = _packet()
    comparison = _comparison(left, right)
    forged = deepcopy(comparison)
    forged["status"] = "BLOCKED_CONFLICT"
    with pytest.raises(VerifiedColdStartReentryError, match="does not match"):
        validate_observer_reentry_comparison(
            forged, left=left, left_source_items=SOURCE_ITEMS,
            right=right, right_source_items=SOURCE_ITEMS,
        )
    changed = deepcopy(SOURCE_ITEMS)
    changed[0]["value"] = "altered source"
    with pytest.raises(VerifiedColdStartReentryError, match="reconstructed state"):
        _comparison(left, right, right_items=changed)


def test_packet_budget_boundary_blocks_without_truncating_required_state():
    packet = _packet()
    before = deepcopy(packet)
    size = len(canonical_bytes(packet))
    exact = evaluate_reentry_packet_budget(
        packet=packet, source_items=SOURCE_ITEMS, max_bytes=size,
    )
    overflow = evaluate_reentry_packet_budget(
        packet=packet, source_items=SOURCE_ITEMS, max_bytes=size - 1,
    )
    assert exact["status"] == "READY_WITHIN_BUDGET"
    assert exact["gate_decision"] == "ALLOW"
    assert overflow["status"] == "BLOCKED_BUDGET"
    assert overflow["gate_decision"] == "BLOCK"
    assert overflow["fits_budget"] is False
    assert overflow["packet_size_bytes"] == size
    assert overflow["reasons"] == ["packet_exceeds_byte_budget"]
    assert packet == before
    assert exact["truth_claimed"] is False
    assert exact["accepted"] is False
    assert exact["write_authority"] == "NONE"
    assert exact["execution_authority"] == "NONE"
    assert validate_reentry_packet_budget_check(
        exact, packet=packet, source_items=SOURCE_ITEMS, max_bytes=size,
    ) is True


def test_budget_counts_utf8_bytes_and_required_uncertainty():
    items = deepcopy(SOURCE_ITEMS)
    items[0]["value"] = "\u672a\u78ba\u5b9a"
    items[0]["uncertainty"] = "\u00e9" * 100
    packet = build_verified_cold_start_reentry_packet(
        packet_id="utf8-packet", reconstructed_state=_state(items),
        source_items=items, head_check=_head_check(), conflicts=[],
    )
    encoded = canonical_bytes(packet)
    character_count = len(encoded.decode("utf-8"))
    assert len(encoded) > character_count
    check = evaluate_reentry_packet_budget(
        packet=packet, source_items=items, max_bytes=character_count,
    )
    assert check["packet_size_bytes"] == len(encoded)
    assert check["status"] == "BLOCKED_BUDGET"
    assert packet["reconstructed_state"]["carried_items"][0]["uncertainty"] == "\u00e9" * 100


def test_large_budget_does_not_clear_conflicts_or_stale_heads():
    conflict = {"id": "unresolved", "reason": "x" * 5000}
    packet = _packet(conflicts=[conflict])
    check = evaluate_reentry_packet_budget(
        packet=packet, source_items=SOURCE_ITEMS, max_bytes=100_000,
    )
    assert check["packet_size_bytes"] == len(canonical_bytes(packet))
    assert check["fits_budget"] is True
    assert check["status"] == "BLOCKED_INPUT"
    assert check["gate_decision"] == "BLOCK"
    assert packet["conflicts"] == [conflict]
    stale = _packet(head_check=_head_check(current_hash="head-11", current_idx=11))
    stale_check = evaluate_reentry_packet_budget(
        packet=stale, source_items=SOURCE_ITEMS, max_bytes=100_000,
    )
    assert stale_check["gate_decision"] == "BLOCK"
    too_small = evaluate_reentry_packet_budget(
        packet=packet, source_items=SOURCE_ITEMS, max_bytes=1,
    )
    assert too_small["reasons"] == ["input_packet_not_ready", "packet_exceeds_byte_budget"]


def test_budget_replay_rejects_rehashed_forgery_and_changed_external_budget():
    packet = _packet()
    size = len(canonical_bytes(packet))
    check = evaluate_reentry_packet_budget(
        packet=packet, source_items=SOURCE_ITEMS, max_bytes=size - 1,
    )
    forged = deepcopy(check)
    forged["fits_budget"] = True
    forged["status"] = "READY_WITHIN_BUDGET"
    forged["gate_decision"] = "ALLOW"
    forged["reasons"] = []
    body = {key: value for key, value in forged.items() if key != "budget_check_hash"}
    forged["budget_check_hash"] = stable_hash(body)
    with pytest.raises(VerifiedColdStartReentryError, match="does not match"):
        validate_reentry_packet_budget_check(
            forged, packet=packet, source_items=SOURCE_ITEMS, max_bytes=size - 1,
        )
    with pytest.raises(VerifiedColdStartReentryError, match="does not match"):
        validate_reentry_packet_budget_check(
            check, packet=packet, source_items=SOURCE_ITEMS, max_bytes=size,
        )


def test_budget_replay_rejects_a_replacement_packet_with_conflicts_removed():
    original = _packet(conflicts=[{"id": "unresolved"}])
    check = evaluate_reentry_packet_budget(
        packet=original, source_items=SOURCE_ITEMS, max_bytes=100_000,
    )
    with pytest.raises(VerifiedColdStartReentryError, match="does not match"):
        validate_reentry_packet_budget_check(
            check, packet=_packet(), source_items=SOURCE_ITEMS, max_bytes=100_000,
        )


@pytest.mark.parametrize("field", ["fits_budget", "truth_claimed", "accepted"])
def test_budget_replay_rejects_boolean_integer_substitution(field):
    packet = _packet()
    check = evaluate_reentry_packet_budget(
        packet=packet, source_items=SOURCE_ITEMS, max_bytes=100_000,
    )
    check[field] = int(check[field])
    with pytest.raises(VerifiedColdStartReentryError, match="does not match"):
        validate_reentry_packet_budget_check(
            check, packet=packet, source_items=SOURCE_ITEMS, max_bytes=100_000,
        )


def test_budget_revalidates_source_items_and_packet_status():
    packet = _packet()
    changed = deepcopy(SOURCE_ITEMS)
    changed[0]["value"] = "changed source"
    with pytest.raises(VerifiedColdStartReentryError, match="reconstructed state"):
        evaluate_reentry_packet_budget(
            packet=packet, source_items=changed, max_bytes=100_000,
        )
    forged = _packet(head_check=_head_check(current_hash="head-11", current_idx=11))
    forged["status"] = "READY_FOR_REENTRY"
    with pytest.raises(VerifiedColdStartReentryError):
        evaluate_reentry_packet_budget(
            packet=forged, source_items=SOURCE_ITEMS, max_bytes=100_000,
        )


@pytest.mark.parametrize("budget", [True, False, 0, -1, 1.0, "1000", None])
def test_packet_budget_rejects_invalid_limits(budget):
    with pytest.raises(VerifiedColdStartReentryError, match="positive plain integer"):
        evaluate_reentry_packet_budget(
            packet=_packet(), source_items=SOURCE_ITEMS, max_bytes=budget,
        )
