from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from holosim.bounded_source_grid import (
    SourceGridError,
    compare_source_grids,
    observe_source_grid,
    verify_source_grid,
)



@pytest.mark.skipif(
    __import__("os").name != "nt",
    reason="Windows-specific source reader integration",
)
def test_observation_uses_windows_handle_relative_reader(monkeypatch):
    import hashlib
    import holosim.bounded_source_grid as grid_module

    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "sample.py"
        path.write_bytes(b"def original(): pass\n")

        expected = b"def observed(): pass\n"
        calls = []

        def controlled_reader(
            actual_root, relative, max_bytes, *, expected_identities
        ):
            assert len(expected_identities[()]) == 2
            assert all(value > 0 for value in expected_identities[()])
            assert len(expected_identities[relative.parts]) == 2
            assert all(
                value > 0 for value in expected_identities[relative.parts]
            )
            calls.append((actual_root, relative, max_bytes))
            return expected

        monkeypatch.setattr(
            grid_module,
            "read_bounded_windows_source",
            controlled_reader,
        )

        result = grid_module.observe_source_grid(
            root,
            max_file_bytes=1024,
        )

        assert calls == [(root, Path("sample.py"), 1024)]
        assert result["file_hashes"]["sample.py"] == (
            hashlib.sha256(expected).hexdigest()
        )
        assert [
            record["qualified_name"]
            for record in result["definitions"]
        ] == ["observed"]
        assert result["accepted"] is False
        assert result["write_authority"] == "NONE"


def test_directory_budget_rejects_excessive_empty_directories():
    with TemporaryDirectory() as directory:
        root = Path(directory)

        for index in range(11):
            (root / f"empty_{index}").mkdir()

        with pytest.raises(
            SourceGridError,
            match="directory budget exceeded",
        ):
            observe_source_grid(root, max_files=1)


def test_entry_budget_rejects_excessive_non_python_files():
    with TemporaryDirectory() as directory:
        root = Path(directory)

        for index in range(101):
            (root / f"ignored_{index}.txt").write_bytes(b"x")

        with pytest.raises(
            SourceGridError,
            match="directory entry budget exceeded",
        ):
            observe_source_grid(root, max_files=1)


def test_source_grid_rejects_symlink_entries():
    import os

    with TemporaryDirectory() as directory:
        root = Path(directory)
        target = root / "target.txt"
        target.write_bytes(b"data")
        link = root / "linked.txt"

        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation unavailable")

        with pytest.raises(
            SourceGridError,
            match="symlink entry unsupported",
        ):
            observe_source_grid(root)


@pytest.mark.skipif(
    __import__("os").name != "nt",
    reason="Windows junction regression",
)
def test_windows_junction_outside_root_is_rejected():
    import os
    import subprocess

    with TemporaryDirectory() as directory:
        base = Path(directory)
        root = base / "root"
        outside = base / "outside"
        root.mkdir()
        outside.mkdir()

        (outside / "external.py").write_text(
            "def outside_definition(): pass\\n",
            encoding="utf-8",
        )

        junction = root / "external"

        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.skip("Windows junction creation unavailable")

        assert junction.is_junction()

        with pytest.raises(
            SourceGridError,
            match="reparse point unsupported",
        ):
            observe_source_grid(root)



def test_symlink_rejection_without_symlink_privileges(monkeypatch):
    import os
    from unittest.mock import patch

    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "sample.py").write_text(
            "def example(): pass\\n",
            encoding="utf-8",
        )

        original_scandir = os.scandir

        class SimulatedSymlink:
            name = "linked.py"
            path = str(root / "linked.py")

            def is_symlink(self):
                return True

            def is_dir(self, *, follow_symlinks=True):
                raise AssertionError("symlink must be rejected first")

            def is_file(self, *, follow_symlinks=True):
                raise AssertionError("symlink must be rejected first")

        class ControlledEntries:
            def __enter__(self):
                return iter([SimulatedSymlink()])

            def __exit__(self, exc_type, exc_value, traceback):
                return False

        def controlled_scandir(path):
            if Path(path) == root:
                return ControlledEntries()
            return original_scandir(path)

        with patch(
            "holosim.bounded_source_grid.os.scandir",
            side_effect=controlled_scandir,
        ):
            try:
                observe_source_grid(root)
            except SourceGridError as exc:
                captured = exc
            else:
                captured = None

        assert captured is not None
        assert "symlink entry unsupported" in str(captured)


@pytest.mark.skipif(
    __import__("os").name != "nt",
    reason="Windows directory replacement regression",
)
def test_full_observation_rejects_or_preserves_directory_replacement():
    import holosim.bounded_source_grid as grid_module
    from unittest.mock import patch

    with TemporaryDirectory() as directory:
        base = Path(directory)
        root = base / "root"
        root.mkdir()

        original = root / "module"
        original.mkdir()
        (original / "sample.py").write_text(
            "def original(): pass\n",
            encoding="utf-8",
        )

        replacement = base / "replacement"
        replacement.mkdir()
        (replacement / "sample.py").write_text(
            "def substituted(): pass\n",
            encoding="utf-8",
        )

        real_reader = grid_module.read_bounded_windows_source
        swapped = False

        def intercepted_reader(
            actual_root, relative, max_bytes, *, expected_identities
        ):
            nonlocal swapped

            if not swapped:
                original.rename(root / "module_original")
                replacement.rename(original)
                swapped = True

            return real_reader(
                actual_root,
                relative,
                max_bytes,
                expected_identities=expected_identities,
            )

        with patch.object(
            grid_module,
            "read_bounded_windows_source",
            side_effect=intercepted_reader,
        ):
            try:
                result = grid_module.observe_source_grid(root)
            except SourceGridError:
                result = None

        assert swapped, "directory replacement was not exercised"

        if result is not None:
            names = {
                record["qualified_name"]
                for record in result["definitions"]
            }
            assert "substituted" not in names, (
                "replacement source was silently accepted"
            )

def test_ast_recursion_failure_is_contained(monkeypatch):
    import ast
    import holosim.bounded_source_grid as grid_module

    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "sample.py").write_text(
            "def example(): pass\n",
            encoding="utf-8",
        )

        original_iterator = ast.iter_child_nodes

        def failing_iterator(node):
            if isinstance(node, ast.Module):
                raise RecursionError("simulated traversal overflow")
            return original_iterator(node)

        from unittest.mock import patch

        with patch.object(
            grid_module.ast,
            "iter_child_nodes",
            failing_iterator,
        ):
            try:
                observe_source_grid(root)
            except SourceGridError as exc:
                captured = exc
            else:
                captured = None

        assert captured is not None
        assert "definition nesting budget exceeded" in str(captured)

def test_observes_nested_and_async_definitions():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "sample.py").write_text(
            "def outer():\n"
            "    def inner():\n"
            "        pass\n"
            "class Example:\n"
            "    async def method(self):\n"
            "        pass\n",
            encoding="utf-8",
        )

        grid = observe_source_grid(root)
        names = {item["qualified_name"] for item in grid["definitions"]}

        assert names == {"outer", "outer.inner", "Example.method"}
        assert grid["write_authority"] == "NONE"


def test_missing_definition_detected():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "sample.py"

        path.write_text("def first(): pass\ndef second(): pass\n")
        before = observe_source_grid(root)

        path.write_text("def first(): pass\n")
        after = observe_source_grid(root)

        result = compare_source_grids(before, after)
        assert len(result["missing"]) == 1
        assert result["same"] is False


def test_changed_definition_detected():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "sample.py"

        path.write_text("def first(): return 1\n")
        before = observe_source_grid(root)

        path.write_text("def first(): return 2\n")
        after = observe_source_grid(root)

        result = compare_source_grids(before, after)
        assert len(result["changed"]) == 1


def test_file_budget_fails_closed():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "a.py").write_text("pass\n")
        (root / "b.py").write_text("pass\n")

        with pytest.raises(SourceGridError):
            observe_source_grid(root, max_files=1)


def test_malformed_source_fails_closed():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "bad.py").write_text("def broken(\n")

        with pytest.raises(SourceGridError):
            observe_source_grid(root)


def test_no_authority():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "a.py").write_text("def example(): pass\n")

        grid = observe_source_grid(root)
        result = compare_source_grids(grid, grid)

        assert result["same"] is True
        assert result["accepted"] is False
        assert result["write_authority"] == "NONE"


def test_utf8_bom_source_is_supported():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "bom.py").write_text(
            "def example(): return 1\n",
            encoding="utf-8-sig",
        )

        grid = observe_source_grid(root)

        assert len(grid["definitions"]) == 1
        assert grid["definitions"][0]["qualified_name"] == "example"



def test_line_movement_preserves_identity():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "sample.py"

        path.write_text("def alpha(): return 1\n")
        before = observe_source_grid(root)

        path.write_text("# comment\ndef alpha(): return 1\n")
        after = observe_source_grid(root)

        result = compare_source_grids(before, after)

        assert result["same"] is False
        assert result["missing"] == []
        assert result["added"] == []
        assert result["changed"] == []
        assert result["changed_files"] == ["sample.py"]


def test_independent_recheck_detects_missing_record():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "sample.py").write_text(
            "def alpha(): pass\ndef beta(): pass\n"
        )

        claimed = observe_source_grid(root)
        claimed["definitions"].pop()

        result = verify_source_grid(root, claimed)

        assert result["valid"] is False
        assert len(result["added"]) == 1
        assert result["source_rechecked"] is True
        assert result["write_authority"] == "NONE"


def test_duplicate_identity_rejected():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "sample.py").write_text("def alpha(): pass\n")

        grid = observe_source_grid(root)
        grid["definitions"].append(dict(grid["definitions"][0]))

        with pytest.raises(SourceGridError):
            compare_source_grids(grid, grid)


def test_fabricated_authority_rejected():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "sample.py").write_text("def alpha(): pass\n")

        grid = observe_source_grid(root)
        grid["write_authority"] = "WRITE"

        with pytest.raises(SourceGridError):
            compare_source_grids(grid, grid)



def test_module_constant_change_invalidates_grid():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "sample.py"

        path.write_text(
            "FACTOR = 2\n"
            "def calculate(value): return value * FACTOR\n"
        )
        before = observe_source_grid(root)

        path.write_text(
            "FACTOR = 999\n"
            "def calculate(value): return value * FACTOR\n"
        )

        result = verify_source_grid(root, before)

        assert result["valid"] is False
        assert result["changed"] == []
        assert result["changed_files"] == ["sample.py"]
        assert result["write_authority"] == "NONE"


def test_file_hash_tampering_detected():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "sample.py").write_text("def alpha(): pass\n")

        grid = observe_source_grid(root)
        grid["file_hashes"]["sample.py"] = "0" * 64

        result = verify_source_grid(root, grid)

        assert result["valid"] is False
        assert result["changed_files"] == ["sample.py"]


def test_definition_without_file_rejected():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "sample.py").write_text("def alpha(): pass\n")

        grid = observe_source_grid(root)
        grid["file_hashes"] = {}

        with pytest.raises(SourceGridError):
            compare_source_grids(grid, grid)


def test_source_file_addition_detected():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "a.py").write_text("pass\n")
        before = observe_source_grid(root)

        (root / "b.py").write_text("pass\n")
        result = verify_source_grid(root, before)

        assert result["valid"] is False
        assert result["added_files"] == ["b.py"]



def test_fabricated_line_rejected_by_recheck():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "sample.py").write_text("def alpha(): pass\n")

        claimed = observe_source_grid(root)
        claimed["definitions"][0]["line"] = 999999

        result = verify_source_grid(root, claimed)

        assert result["valid"] is False
        assert result["moved"] == [("sample.py", "alpha")]
        assert result["write_authority"] == "NONE"


def test_duplicate_source_identity_fails_during_observation():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "dup.py").write_text(
            "def foo(): pass\n"
            "def foo(): return 1\n"
        )

        with pytest.raises(
            SourceGridError,
            match="duplicate qualified identity",
        ):
            observe_source_grid(root)


def test_file_enumeration_budget_fails_closed():
    with TemporaryDirectory() as directory:
        root = Path(directory)

        for number in range(30):
            (root / f"{number:03d}.py").write_text("pass\n")

        with pytest.raises(
            SourceGridError,
            match="file budget exceeded",
        ):
            observe_source_grid(root, max_files=3)
