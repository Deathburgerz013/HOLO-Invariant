from copy import deepcopy

from holosim.memory_card import (
    build_memory_card,
    copy_memory_card,
    load_memory_card,
    save_memory_card,
)
from holosim.reconstructor import (
    build_reconstructed_state,
    validate_reconstructed_state,
)


def _card(card_id, value):
    return build_memory_card(
        card_id=card_id,
        observation={
            "type": "recorded_state",
            "state": {
                "value": value,
            },
        },
        source={
            "kind": "state-block-test",
            "source_id": "memory-card-state-blocks",
        },
        observed_at="2026-09-22T20:00:00+00:00",
    )


def _item(card, requires=None):
    item = {
        "id": card["card_id"],
        "memory_card": deepcopy(card),
    }

    if requires is not None:
        item["requires"] = list(requires)

    return item


def test_multiple_memory_cards_reconstruct_as_explicit_state_blocks():
    root = _card("memory-card:root", "root")
    child = _card("memory-card:child", "child")

    items = [
        _item(root),
        _item(child, requires=["memory-card:root"]),
    ]

    state = build_reconstructed_state(
        "memory-card-state-blocks",
        ["memory-card:child"],
        items,
    )

    assert state["status"] == "COMPLETE"
    assert state["reachable_ids"] == [
        "memory-card:child",
        "memory-card:root",
    ]
    assert state["missing_ids"] == []

    assert [
        item["id"] for item in state["carried_items"]
    ] == [
        "memory-card:child",
        "memory-card:root",
    ]


def test_copied_state_blocks_reconstruct_identically(tmp_path):
    root = _card("memory-card:root", "root")
    child = _card("memory-card:child", "child")

    source_root = tmp_path / "root-a.json"
    source_child = tmp_path / "child-a.json"

    copied_root = tmp_path / "root-b.json"
    copied_child = tmp_path / "child-b.json"

    save_memory_card(source_root, root)
    save_memory_card(source_child, child)

    copy_memory_card(source_root, copied_root)
    copy_memory_card(source_child, copied_child)

    original_root = load_memory_card(source_root)
    original_child = load_memory_card(source_child)

    transported_root = load_memory_card(copied_root)
    transported_child = load_memory_card(copied_child)

    original_items = [
        _item(original_root),
        _item(
            original_child,
            requires=["memory-card:root"],
        ),
    ]

    transported_items = [
        _item(transported_root),
        _item(
            transported_child,
            requires=["memory-card:root"],
        ),
    ]

    original_state = build_reconstructed_state(
        "memory-card-transport",
        ["memory-card:child"],
        original_items,
    )

    transported_state = build_reconstructed_state(
        "memory-card-transport",
        ["memory-card:child"],
        transported_items,
    )

    assert (
        original_state["state_hash"]
        == transported_state["state_hash"]
    )


def test_missing_state_block_remains_missing():
    child = _card("memory-card:child", "child")

    items = [
        _item(
            child,
            requires=["memory-card:missing"],
        ),
    ]

    state = build_reconstructed_state(
        "memory-card-missing-dependency",
        ["memory-card:child"],
        items,
    )

    assert state["status"] == "INCOMPLETE"
    assert state["reachable_ids"] == [
        "memory-card:child",
    ]
    assert state["missing_ids"] == [
        "memory-card:missing",
    ]


def test_missing_state_block_is_not_invented_during_reconstruction():
    child = _card("memory-card:child", "child")

    items = [
        _item(
            child,
            requires=["memory-card:missing"],
        ),
    ]

    state = build_reconstructed_state(
        "memory-card-no-invention",
        ["memory-card:child"],
        items,
    )

    carried_ids = [
        item["id"] for item in state["carried_items"]
    ]

    assert "memory-card:missing" not in carried_ids
    assert "memory-card:missing" in state["missing_ids"]


def test_state_block_cycle_remains_explicit_and_safe():
    first = _card("memory-card:first", "first")
    second = _card("memory-card:second", "second")

    items = [
        _item(
            first,
            requires=["memory-card:second"],
        ),
        _item(
            second,
            requires=["memory-card:first"],
        ),
    ]

    state = build_reconstructed_state(
        "memory-card-cycle",
        ["memory-card:first"],
        items,
    )

    assert state["status"] == "COMPLETE"
    assert state["reachable_ids"] == [
        "memory-card:first",
        "memory-card:second",
    ]


def test_state_block_reconstruction_is_independently_validatable():
    root = _card("memory-card:root", "root")
    child = _card("memory-card:child", "child")

    items = [
        _item(root),
        _item(
            child,
            requires=["memory-card:root"],
        ),
    ]

    state = build_reconstructed_state(
        "memory-card-validation",
        ["memory-card:child"],
        items,
    )

    assert validate_reconstructed_state(
        state,
        items,
    ) is True


def test_changing_one_block_changes_reconstructed_state_identity():
    root = _card("memory-card:root", "root")
    child = _card("memory-card:child", "child")

    items = [
        _item(root),
        _item(
            child,
            requires=["memory-card:root"],
        ),
    ]

    original = build_reconstructed_state(
        "memory-card-change",
        ["memory-card:child"],
        items,
    )

    changed_child = _card(
        "memory-card:child",
        "changed-child",
    )

    changed_items = [
        _item(root),
        _item(
            changed_child,
            requires=["memory-card:root"],
        ),
    ]

    changed = build_reconstructed_state(
        "memory-card-change",
        ["memory-card:child"],
        changed_items,
    )

    assert original["state_hash"] != changed["state_hash"]


def test_state_block_reconstruction_does_not_mutate_cards():
    root = _card("memory-card:root", "root")
    child = _card("memory-card:child", "child")

    items = [
        _item(root),
        _item(
            child,
            requires=["memory-card:root"],
        ),
    ]

    before = deepcopy(items)

    build_reconstructed_state(
        "memory-card-no-mutation",
        ["memory-card:child"],
        items,
    )

    assert items == before