from pathlib import Path

import pytest

from holosim.idx_parser import load_idx_spine


def test_missing_idx_aborts_without_creating_default(tmp_path: Path):
    idx_path = tmp_path / "missing_idx.json"

    with pytest.raises(
        FileNotFoundError,
        match="Frozen IDX file does not exist",
    ):
        load_idx_spine(str(idx_path))

    assert not idx_path.exists()


def test_existing_idx_loads_without_mutation(tmp_path: Path):
    idx_path = tmp_path / "idx.json"
    original = (
        '{\n'
        '  "IDX": {\n'
        '    "v": 1,\n'
        '    "n": 1,\n'
        '    "ACTIVE_HASH": "frozen-hash"\n'
        '  },\n'
        '  "CORE": "preserve uncertainty"\n'
        '}\n'
    )
    idx_path.write_text(original, encoding="utf-8")

    result = load_idx_spine(str(idx_path))

    assert result["IDX"]["v"] == 1
    assert result["IDX"]["n"] == 1
    assert result["IDX"]["ACTIVE_HASH"] == "frozen-hash"
    assert idx_path.read_text(encoding="utf-8") == original