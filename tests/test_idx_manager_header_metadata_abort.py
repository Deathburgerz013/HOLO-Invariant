import pytest

from holosim.idx_manager import IDXManager


class DummyChain:
    pass


@pytest.mark.parametrize(
    "header",
    [
        "IDX:v=1;n=1;n=2",
        "IDX:v=1;n=2;n=2",
    ],
)
def test_duplicate_header_metadata_aborts(header: str):
    manager = IDXManager(chain=DummyChain())
    manager.parse_spine(
        f"{header}\n"
        "S1=CORE@core-hash\n"
        "S2=PROTO@proto-hash\n"
        "ACTIVE_HASH=frozen-head\n"
    )

    with pytest.raises(
        ValueError,
        match="Frozen IDX header contains duplicate metadata n",
    ):
        manager.build_frozen_gate()


def test_unique_header_metadata_still_builds():
    manager = IDXManager(chain=DummyChain())
    manager.parse_spine(
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