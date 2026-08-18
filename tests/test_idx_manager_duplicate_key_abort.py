import pytest

from holosim.idx_manager import IDXManager


class DummyChain:
    pass


@pytest.mark.parametrize(
    ("duplicate_key", "content"),
    [
        (
            "IDX:v",
            "IDX:v=1;n=1\n"
            "IDX:v=2;n=1\n"
            "S1=CORE@core-hash\n",
        ),
        (
            "S1",
            "IDX:v=1;n=1\n"
            "S1=CORE@trusted-hash\n"
            "S1=CORE@replacement-hash\n",
        ),
        (
            "ACTIVE_HASH",
            "IDX:v=1;n=1\n"
            "S1=CORE@core-hash\n"
            "ACTIVE_HASH=trusted-head\n"
            "ACTIVE_HASH=replacement-head\n",
        ),
    ],
)
def test_duplicate_frozen_idx_key_aborts(
    duplicate_key: str,
    content: str,
):
    manager = IDXManager(chain=DummyChain())

    with pytest.raises(
        ValueError,
        match=rf"Frozen IDX contains duplicate key {duplicate_key}",
    ):
        manager.parse_spine(content)


def test_duplicate_key_abort_preserves_previous_loaded_idx():
    manager = IDXManager(chain=DummyChain())
    manager.parse_spine(
        "IDX:v=1;n=1\n"
        "S1=CORE@trusted-hash\n"
        "ACTIVE_HASH=trusted-head\n"
    )
    previous = dict(manager.idx_data)

    with pytest.raises(
        ValueError,
        match="Frozen IDX contains duplicate key S1",
    ):
        manager.parse_spine(
            "IDX:v=1;n=1\n"
            "S1=CORE@trusted-hash\n"
            "S1=CORE@replacement-hash\n"
            "ACTIVE_HASH=replacement-head\n"
        )

    assert manager.idx_data == previous