from pathlib import Path

import pytest

from holosim.idx_parser import load_idx_spine


@pytest.mark.parametrize(
    ("duplicate_key", "content"),
    [
        (
            "v",
            '{\n'
            '  "IDX": {\n'
            '    "v": 1,\n'
            '    "v": 2,\n'
            '    "n": 1\n'
            '  },\n'
            '  "CORE": "frozen"\n'
            '}\n',
        ),
        (
            "CORE",
            '{\n'
            '  "IDX": {\n'
            '    "v": 1,\n'
            '    "n": 1\n'
            '  },\n'
            '  "CORE": "trusted",\n'
            '  "CORE": "replacement"\n'
            '}\n',
        ),
    ],
)
def test_duplicate_json_key_aborts(
    tmp_path: Path,
    duplicate_key: str,
    content: str,
):
    idx_path = tmp_path / "idx.json"
    idx_path.write_text(content, encoding="utf-8")

    with pytest.raises(
        ValueError,
        match=rf"Frozen IDX contains duplicate key {duplicate_key}",
    ):
        load_idx_spine(str(idx_path))

    assert idx_path.read_text(encoding="utf-8") == content


def test_unique_json_keys_still_load(tmp_path: Path):
    idx_path = tmp_path / "idx.json"
    idx_path.write_text(
        '{\n'
        '  "IDX": {\n'
        '    "v": 1,\n'
        '    "n": 1\n'
        '  },\n'
        '  "CORE": "frozen"\n'
        '}\n',
        encoding="utf-8",
    )

    result = load_idx_spine(str(idx_path))

    assert result == {
        "IDX": {
            "v": 1,
            "n": 1,
        },
        "CORE": "frozen",
    }