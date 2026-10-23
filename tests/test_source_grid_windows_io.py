"""Adversarial Windows source-reading regression tests."""

import ctypes
import os
from ctypes import wintypes
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

import holosim.source_grid_windows_io as source_grid_windows_io

from holosim.source_grid_windows_io import (
    read_bounded_windows_source,
    WindowsSourceReadError,
)


@pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
def test_parent_directory_replacement_must_not_substitute_source():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW

    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE

    with TemporaryDirectory() as directory:
        base = Path(directory)
        root = base / "root"
        root.mkdir()

        parent = root / "module"
        parent.mkdir()
        expected = b"def expected(): pass\n"
        (parent / "sample.py").write_bytes(expected)

        replacement = base / "replacement"
        replacement.mkdir()
        (replacement / "sample.py").write_bytes(
            b"def substituted(): pass\n"
        )

        swapped = False

        def intercepted_create(name, *args):
            nonlocal swapped

            if not swapped and Path(name) == parent / "sample.py":
                parent.rename(root / "module_original")
                replacement.rename(parent)
                swapped = True

            return create(name, *args)

        class KernelProxy:
            def __getattr__(self, name):
                if name == "CreateFileW":
                    return intercepted_create
                return getattr(kernel, name)

        original_windll = ctypes.WinDLL
        native = original_windll("ntdll")
        native_create = native.NtCreateFile

        class NativeProxy:
            def __getattr__(self, name):
                if name == "NtCreateFile":
                    return intercepted_native_create
                return getattr(native, name)

        def intercepted_native_create(*args):
            nonlocal swapped

            object_attributes = ctypes.cast(
                args[2],
                ctypes.POINTER(
                    source_grid_windows_io.OBJECT_ATTRIBUTES
                ),
            ).contents

            unicode_name = object_attributes.ObjectName.contents
            component = ctypes.wstring_at(
                unicode_name.Buffer,
                unicode_name.Length // 2,
            )

            if not swapped and component == "sample.py":
                parent.rename(root / "module_original")
                replacement.rename(parent)
                swapped = True

            return native_create(*args)

        def intercepted_windll(name, *args, **kwargs):
            if name.lower() == "kernel32":
                return KernelProxy()
            if name.lower() == "ntdll":
                return NativeProxy()
            return original_windll(name, *args, **kwargs)

        with patch(
            "holosim.source_grid_windows_io.ctypes.WinDLL",
            side_effect=intercepted_windll,
        ):
            try:
                result = read_bounded_windows_source(
                    root,
                    Path("module/sample.py"),
                    1024,
                )
            except WindowsSourceReadError:
                result = None

        assert swapped, "adversarial replacement was not exercised"
        assert result is None or result == expected, (
            "unvalidated replacement source was accepted"
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows-only identity validation")
def test_identity_mismatch_regressions():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        parent = root / "module"
        parent.mkdir()
        target = parent / "sample.py"
        expected = b"def original(): pass\\n"
        target.write_bytes(expected)

        def identity(path):
            info = path.stat(follow_symlinks=False)
            return (info.st_dev & 0xFFFFFFFF, info.st_ino)

        identities = {
            (): identity(root),
            ("module",): identity(parent),
            ("module", "sample.py"): identity(target),
        }

        assert read_bounded_windows_source(
            root,
            Path("module/sample.py"),
            1024,
            expected_identities=identities,
        ) == expected

        wrong_file = dict(identities)
        volume, file_id = wrong_file[("module", "sample.py")]
        wrong_file[("module", "sample.py")] = (volume, file_id + 1)

        with pytest.raises(
            WindowsSourceReadError, match="component identity changed"
        ):
            read_bounded_windows_source(
                root,
                Path("module/sample.py"),
                1024,
                expected_identities=wrong_file,
            )

        wrong_volume = dict(identities)
        volume, file_id = wrong_volume[("module",)]
        wrong_volume[("module",)] = (volume ^ 1, file_id)

        with pytest.raises(
            WindowsSourceReadError, match="component identity changed"
        ):
            read_bounded_windows_source(
                root,
                Path("module/sample.py"),
                1024,
                expected_identities=wrong_volume,
            )

        missing_parent = dict(identities)
        del missing_parent[("module",)]

        with pytest.raises(
            WindowsSourceReadError, match="component identity unavailable"
        ):
            read_bounded_windows_source(
                root,
                Path("module/sample.py"),
                1024,
                expected_identities=missing_parent,
            )
