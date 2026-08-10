from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.cold_start_retained_delta_ledger import (
    ColdStartRetainedDeltaError,
    append_cold_start_delta,
    build_cold_start_delta_ledger,
    validate_cold_start_delta_ledger,
    verify_cold_start_delta_evidence,
)
from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)
from holosim.reconstructor import build_reconstructed_state
from holosim.verified_cold_start_reentry_gateway import (
    build_verified_cold_start_reentry_packet,
)


def _head_check(head_hash, head_index):
    recall_kernel = {
        "identity": {"system": "HOLO-Invariant"},
        "last_verified_state": head_hash,
        "history": [head_hash],
    }
    contract = build_continuity_compliance_contract(
        contract_id=f"contract:{head_hash}",
        subject_id="HOLO-Invariant",
        recall_kernel=recall_kernel,
        observed_required_fields=list(recall_kernel),
        authority_limits=["write:NONE", "execution:NONE"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["head-changed"],
    )
    binding = build_continuity_head_binding(
        binding_id=f"binding:{head_hash}",
        contract=contract,
        originating_head_hash=head_hash,
        originating_head_idx=head_index,
    )
    return evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash=head_hash,
        current_head_idx=head_index,
    )


def _packet(packet_id, items, *, head_hash, head_index, conflicts=()):
    state = build_reconstructed_state(
        f"state:{packet_id}", ["active-goal"], items
    )
    return build_verified_cold_start_reentry_packet(
        packet_id=packet_id,
        reconstructed_state=state,
        source_items=items,
        head_check=_head_check(head_hash, head_index),
        conflicts=list(conflicts),
    )


def _items(*dependencies):
    return [
        {
            "id": "active-goal",
            "requires": list(dependencies),
            "value": "continue current work",
        },
        *[
            {"id": dependency, "requires": [], "value": dependency}
            for dependency in dependencies
        ],
    ]


def _ledger():
    return build_cold_start_delta_ledger(
        ledger_id="cold-start-deltas-1",
        continuity_id="HOLO-Invariant",
    )


def _append(
    ledger,
    previous_packet,
    previous_items,
    current_packet,
    current_items,
):
    return append_cold_start_delta(
        ledger=ledger,
        previous_packet=previous_packet,
        previous_source_items=previous_items,
        current_packet=current_packet,
        current_source_items=current_items,
    )


def _evidence(*pairs):
    return {
        packet["packet_hash"]: {
            "packet": packet,
            "source_items": items,
        }
        for packet, items in pairs
    }


def test_delta_preserves_retained_added_missing_and_head_transition():
    previous_items = _items("verified-boundary", "old-page")
    current_items = _items("verified-boundary", "new-page")
    previous = _packet(
        "packet-10", previous_items, head_hash="head-10", head_index=10
    )
    current = _packet(
        "packet-11", current_items, head_hash="head-11", head_index=11
    )

    ledger = _append(_ledger(), previous, previous_items, current, current_items)
    delta = ledger["entries"][0]

    assert delta["retained_item_ids"] == ["active-goal", "verified-boundary"]
    assert delta["added_item_ids"] == ["new-page"]
    assert delta["missing_item_ids"] == ["old-page"]
    assert delta["previous_head"] == {"hash": "head-10", "index": 10}
    assert delta["current_head"] == {"hash": "head-11", "index": 11}
    assert ledger["decision"] == "STOP"
    assert ledger["stop_condition"] == "RETENTION_LOSS_REQUIRES_REVIEW"
    assert ledger["truth_claimed"] is False
    assert ledger["accepted"] is False
    assert ledger["write_authority"] == "NONE"
    assert ledger["execution_authority"] == "NONE"


def test_added_items_without_loss_or_conflict_continue():
    previous_items = _items("verified-boundary")
    current_items = _items("verified-boundary", "new-page")
    previous = _packet(
        "packet-20", previous_items, head_hash="head-20", head_index=20
    )
    current = _packet(
        "packet-21", current_items, head_hash="head-21", head_index=21
    )

    ledger = _append(_ledger(), previous, previous_items, current, current_items)

    assert ledger["entries"][0]["added_item_ids"] == ["new-page"]
    assert ledger["entries"][0]["missing_item_ids"] == []
    assert ledger["decision"] == "CONTINUE"
    assert ledger["stop_condition"] is None


def test_new_conflict_is_retained_and_stops():
    items = _items("verified-boundary")
    conflict = {
        "id": "goal-conflict",
        "reason": "two current goal claims remain unresolved",
    }
    previous = _packet(
        "packet-30", items, head_hash="head-30", head_index=30
    )
    current = _packet(
        "packet-31",
        items,
        head_hash="head-31",
        head_index=31,
        conflicts=[conflict],
    )

    ledger = _append(_ledger(), previous, items, current, items)

    assert ledger["entries"][0]["added_conflict_hashes"] == [stable_hash(conflict)]
    assert ledger["entries"][0]["resolved_conflict_hashes"] == []
    assert ledger["decision"] == "STOP"
    assert ledger["stop_condition"] == "CURRENT_REENTRY_BLOCKED"


def test_resolved_conflict_is_retained_without_blocking_current_packet():
    items = _items("verified-boundary")
    conflict = {"id": "old-conflict", "reason": "previously unresolved"}
    previous = _packet(
        "packet-40",
        items,
        head_hash="head-40",
        head_index=40,
        conflicts=[conflict],
    )
    current = _packet(
        "packet-41", items, head_hash="head-41", head_index=41
    )

    ledger = _append(_ledger(), previous, items, current, items)

    assert ledger["entries"][0]["resolved_conflict_hashes"] == [
        stable_hash(conflict)
    ]
    assert ledger["entries"][0]["added_conflict_hashes"] == []
    assert ledger["decision"] == "CONTINUE"
    assert ledger["stop_condition"] is None


def test_entries_reference_packets_without_embedding_full_packet_bodies():
    items = _items("verified-boundary")
    previous = _packet(
        "packet-50", items, head_hash="head-50", head_index=50
    )
    current = _packet(
        "packet-51", items, head_hash="head-51", head_index=51
    )

    ledger = _append(_ledger(), previous, items, current, items)
    delta = ledger["entries"][0]

    assert delta["previous_packet_hash"] == previous["packet_hash"]
    assert delta["current_packet_hash"] == current["packet_hash"]
    assert "previous_packet" not in delta
    assert "current_packet" not in delta


def test_second_delta_must_continue_from_retained_packet_head():
    items = _items("verified-boundary")
    first = _packet("packet-60", items, head_hash="head-60", head_index=60)
    second = _packet("packet-61", items, head_hash="head-61", head_index=61)
    foreign = _packet("packet-x", items, head_hash="head-x", head_index=70)
    third = _packet("packet-62", items, head_hash="head-62", head_index=62)
    ledger = _append(_ledger(), first, items, second, items)

    with pytest.raises(ColdStartRetainedDeltaError, match="packet head"):
        _append(ledger, foreign, items, third, items)


def test_append_is_deterministic_and_does_not_mutate_parent():
    items = _items("verified-boundary")
    previous = _packet(
        "packet-70", items, head_hash="head-70", head_index=70
    )
    current = _packet(
        "packet-71", items, head_hash="head-71", head_index=71
    )
    initial = _ledger()
    before = deepcopy(initial)

    first = _append(initial, previous, items, current, items)
    second = _append(initial, previous, items, current, items)

    assert initial == before
    assert first == second
    assert validate_cold_start_delta_ledger(first) is True


def test_external_packet_evidence_regenerates_every_delta():
    items = _items("verified-boundary")
    first = _packet("packet-80", items, head_hash="head-80", head_index=80)
    second = _packet("packet-81", items, head_hash="head-81", head_index=81)
    third = _packet("packet-82", items, head_hash="head-82", head_index=82)
    ledger = _append(_ledger(), first, items, second, items)
    ledger = _append(ledger, second, items, third, items)

    evidence = _evidence((first, items), (second, items), (third, items))
    assert verify_cold_start_delta_evidence(
        ledger, packet_evidence=evidence
    ) is True


def test_rehashed_summary_forgery_fails_external_evidence_verification():
    items = _items("verified-boundary")
    previous = _packet(
        "packet-90", items, head_hash="head-90", head_index=90
    )
    current = _packet(
        "packet-91", items, head_hash="head-91", head_index=91
    )
    ledger = _append(_ledger(), previous, items, current, items)
    forged = deepcopy(ledger)
    forged["entries"][0]["retained_item_ids"] = []
    entry_body = dict(forged["entries"][0])
    entry_body.pop("delta_id")
    forged["entries"][0]["delta_id"] = stable_hash(entry_body)
    forged["head_delta_id"] = forged["entries"][0]["delta_id"]
    ledger_body = dict(forged)
    ledger_body.pop("ledger_hash")
    forged["ledger_hash"] = stable_hash(ledger_body)

    assert validate_cold_start_delta_ledger(forged) is True
    with pytest.raises(ColdStartRetainedDeltaError, match="evidence"):
        verify_cold_start_delta_evidence(
            forged,
            packet_evidence=_evidence((previous, items), (current, items)),
        )


def test_rehashed_undeclared_authority_field_fails_closed():
    ledger = _ledger()
    forged = deepcopy(ledger)
    forged["approval"] = "GRANTED"
    body = dict(forged)
    body.pop("ledger_hash")
    forged["ledger_hash"] = stable_hash(body)

    with pytest.raises(ColdStartRetainedDeltaError, match="schema"):
        validate_cold_start_delta_ledger(forged)