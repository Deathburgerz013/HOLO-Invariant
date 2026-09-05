from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.python_surface_inventory import (
    PythonSurfaceInventoryError,
    _hash,
    build_python_surface_inventory,
    discover_python_paths,
    verify_python_surface_inventory,
)


def write(root, path, source):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


def test_inventory_records_syntax_visible_surfaces_without_execution(tmp_path) -> None:
    write(
        tmp_path,
        "holosim/worker.py",
        '"""worker"""\n'
        "raise RuntimeError('must not execute')\n"
        "RECEIPT_TYPE = 'worker_receipt'\n"
        "RECEIPT_VERSION = 1\n"
        "import json\n"
        "from pathlib import Path\n"
        "class Worker:\n    pass\n"
        "def verify_worker_receipt(value):\n    return value\n"
        "if __name__ == '__main__':\n    main()\n",
    )
    receipt = build_python_surface_inventory(
        root=tmp_path, python_paths=["holosim/worker.py"]
    )
    item = receipt["files"][0]
    assert item["surface_kind"] == "IMPLEMENTATION"
    assert item["top_level_classes"] == ["Worker"]
    assert item["top_level_functions"] == ["verify_worker_receipt"]
    assert item["imported_modules"] == ["json", "pathlib"]
    assert item["has_main_guard"] is True
    assert item["declared_receipt_contracts"][0]["type"] == "worker_receipt"
    assert verify_python_surface_inventory(receipt, root=tmp_path)["status"] == "PASS"


def test_input_order_cannot_change_inventory(tmp_path) -> None:
    write(tmp_path, "holosim/b.py", "B = 1\n")
    write(tmp_path, "tests/test_a.py", "def test_a():\n    pass\n")
    first = build_python_surface_inventory(
        root=tmp_path, python_paths=["holosim/b.py", "tests/test_a.py"]
    )
    second = build_python_surface_inventory(
        root=tmp_path, python_paths=["tests/test_a.py", "holosim/b.py"]
    )
    assert first == second
    assert [item["surface_kind"] for item in first["files"]] == [
        "IMPLEMENTATION",
        "TEST",
    ]


def test_scoped_discovery_finds_every_python_file_in_declared_roots(tmp_path) -> None:
    write(tmp_path, "holosim/a.py", "A = 1\n")
    write(tmp_path, "holosim/nested/b.py", "B = 2\n")
    write(tmp_path, "tests/test_a.py", "def test_a():\n    pass\n")
    write(tmp_path, "outside.py", "OUTSIDE = True\n")
    assert discover_python_paths(
        root=tmp_path, surface_roots=("tests", "holosim")
    ) == ["holosim/a.py", "holosim/nested/b.py", "tests/test_a.py"]


def test_current_repository_scoped_inventory_is_rebuildable() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    paths = discover_python_paths(root=root)
    receipt = build_python_surface_inventory(root=root, python_paths=paths)
    assert receipt["file_count"] == len(paths)
    assert receipt["file_count"] >= 338
    assert verify_python_surface_inventory(receipt, root=root)["status"] == "PASS"


def test_line_endings_have_one_portable_source_identity(tmp_path) -> None:
    target = tmp_path / "worker.py"
    target.write_bytes(b"def work():\r\n    return 1\r\n")
    crlf = build_python_surface_inventory(root=tmp_path, python_paths=["worker.py"])
    target.write_bytes(b"def work():\n    return 1\n")
    lf = build_python_surface_inventory(root=tmp_path, python_paths=["worker.py"])
    assert crlf == lf


@pytest.mark.parametrize(
    "paths",
    [[], ["../escape.py"], ["worker.txt"], ["worker.py", "worker.py"], [r"x\\y.py"]],
)
def test_ambiguous_or_unsafe_path_sets_fail_closed(tmp_path, paths) -> None:
    with pytest.raises(PythonSurfaceInventoryError):
        build_python_surface_inventory(root=tmp_path, python_paths=paths)


def test_missing_or_invalid_python_fails_closed(tmp_path) -> None:
    with pytest.raises(PythonSurfaceInventoryError, match="unreadable"):
        build_python_surface_inventory(root=tmp_path, python_paths=["missing.py"])
    write(tmp_path, "broken.py", "def broken(:\n")
    with pytest.raises(PythonSurfaceInventoryError, match="invalid Python syntax"):
        build_python_surface_inventory(root=tmp_path, python_paths=["broken.py"])


def test_changed_source_is_detected(tmp_path) -> None:
    write(tmp_path, "worker.py", "VALUE = 1\n")
    receipt = build_python_surface_inventory(root=tmp_path, python_paths=["worker.py"])
    write(tmp_path, "worker.py", "VALUE = 2\n")
    result = verify_python_surface_inventory(receipt, root=tmp_path)
    assert result["status"] == "FAIL"
    assert "files_mismatch" in result["failures"]


def test_declared_paths_do_not_invent_repository_completeness(tmp_path) -> None:
    write(tmp_path, "included.py", "VALUE = 1\n")
    write(tmp_path, "unlisted.py", "VALUE = 2\n")
    receipt = build_python_surface_inventory(
        root=tmp_path, python_paths=["included.py"]
    )
    assert receipt["python_paths"] == ["included.py"]
    assert receipt["file_count"] == 1
    assert "completeness" in receipt["interpretation_notice"]
    assert "agent identity" in receipt["interpretation_notice"]


def test_rehashed_authority_claim_still_fails(tmp_path) -> None:
    write(tmp_path, "worker.py", "VALUE = 1\n")
    receipt = build_python_surface_inventory(root=tmp_path, python_paths=["worker.py"])
    receipt["accepted"] = True
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = _hash(body)
    result = verify_python_surface_inventory(receipt, root=tmp_path)
    assert result["status"] == "FAIL"
    assert result["failures"] == ["forbidden_authority"]


def test_inventory_tampering_is_detected(tmp_path) -> None:
    write(tmp_path, "worker.py", "VALUE = 1\n")
    receipt = build_python_surface_inventory(root=tmp_path, python_paths=["worker.py"])
    tampered = deepcopy(receipt)
    tampered["files"][0]["surface_kind"] = "AGENT"
    result = verify_python_surface_inventory(tampered, root=tmp_path)
    assert result["status"] == "FAIL"
    assert result["failures"] == ["files_mismatch", "receipt_hash_mismatch"]


def test_receipt_never_promotes_observation_to_authority(tmp_path) -> None:
    write(tmp_path, "worker.py", "VALUE = 1\n")
    receipt = build_python_surface_inventory(root=tmp_path, python_paths=["worker.py"])
    assert receipt["observation_only"] is True
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
