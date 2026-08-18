import pytest

from holosim.idx_manager import IDXManager


class DummyChain:
    pass


def build_manager(content: str) -> IDXManager:
    manager = IDXManager(chain=DummyChain())
    manager.parse_spine(content)
    return manager


def test_loaded_idx_builds_ordered_frozen_gate():
    manager = build_manager(
        "IDX:v=1;n=2\n"
        "S1=CORE@core-hash\n"
        "S2=PROTO@proto-hash\n"
        "ACTIVE_HASH=frozen-head\n"
    )

    gate = manager.build_frozen_gate()

    assert gate.version == 1
    assert gate.active_hash == "frozen-head"
    assert gate.slots == (
        ("CORE", "core-hash"),
        ("PROTO", "proto-hash"),
    )


def test_empty_loaded_idx_cannot_build_gate():
    manager = IDXManager(chain=DummyChain())

    with pytest.raises(
        ValueError,
        match="Frozen IDX has not been loaded",
    ):
        manager.build_frozen_gate()


def test_declared_slot_count_must_match_slots():
    manager = build_manager(
        "IDX:v=1;n=2\n"
        "S1=CORE@core-hash\n"
        "ACTIVE_HASH=frozen-head\n"
    )

    with pytest.raises(
        ValueError,
        match="Frozen IDX slot S2 is missing",
    ):
        manager.build_frozen_gate()


def test_slot_binding_must_contain_class_and_hash():
    manager = build_manager(
        "IDX:v=1;n=1\n"
        "S1=CORE\n"
        "ACTIVE_HASH=frozen-head\n"
    )

    with pytest.raises(
        ValueError,
        match="Frozen IDX slot S1 must use CLASS@HASH",
    ):
        manager.build_frozen_gate()