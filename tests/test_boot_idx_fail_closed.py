import pytest
from holosim.boot_integration import load_idx_spine


def test_missing_boot_idx_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_idx_spine(tmp_path / "missing_idx.json")


def test_malformed_boot_idx_fails_closed(tmp_path):
    path = tmp_path / "malformed_idx.json"
    path.write_text("not valid JSON", encoding="utf-8")
    with pytest.raises(ValueError):
        load_idx_spine(path)

def test_valid_boot_idx_loads(tmp_path):
    path = tmp_path / "valid_idx.json"
    expected = {
        "IDX": {
            "v": 2,
            "ACTIVE_HASH": "test-hash",
        }
    }
    import json
    path.write_text(json.dumps(expected), encoding="utf-8")
    assert load_idx_spine(path) == expected
