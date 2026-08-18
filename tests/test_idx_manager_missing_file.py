from pathlib import Path

import pytest

from holosim.idx_manager import IDXManager


class DummyChain:
    pass


def test_missing_idx_file_aborts_without_clearing_current_state(
    tmp_path: Path,
):
    missing = tmp_path / "missing_idx.txt"
    manager = IDXManager(chain=DummyChain())
    manager.idx_data = {
        "IDX:v": "1;n=1",
        "S1": "CORE@frozen",
    }

    with pytest.raises(
        FileNotFoundError,
        match="Frozen IDX file does not exist",
    ):
        manager.load_idx_file(missing)

    assert manager.idx_data == {
        "IDX:v": "1;n=1",
        "S1": "CORE@frozen",
    }
    assert not missing.exists()


def test_existing_idx_file_loads_normally(tmp_path: Path):
    idx_path = tmp_path / "idx_spine.txt"
    idx_path.write_text(
        "IDX:v=1;n=1\n"
        "S1=CORE@frozen\n"
        "ACTIVE_HASH=frozen-head\n",
        encoding="utf-8",
    )

    manager = IDXManager(chain=DummyChain())

    result = manager.load_idx_file(idx_path)

    assert result == {
        "IDX:v": "1;n=1",
        "S1": "CORE@frozen",
        "ACTIVE_HASH": "frozen-head",
    }