"""Bounded Windows source reads using handle-relative traversal."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

FILE_READ_DATA = 0x0001
FILE_READ_ATTRIBUTES = 0x0080
FILE_SHARE_READ = 0x0001
FILE_SHARE_WRITE = 0x0002
FILE_SHARE_DELETE = 0x0004
OPEN_EXISTING = 3
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
FILE_ATTRIBUTE_DIRECTORY = 0x0010

FILE_OPEN = 1
FILE_OPEN_REPARSE_POINT = 0x00200000
FILE_DIRECTORY_FILE = 0x00000001
FILE_NON_DIRECTORY_FILE = 0x00000040
FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
SYNCHRONIZE = 0x00100000
OBJ_CASE_INSENSITIVE = 0x00000040

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class WindowsSourceReadError(ValueError):
    pass


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    ]


class OBJECT_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.ULONG),
        ("RootDirectory", wintypes.HANDLE),
        ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
        ("Attributes", wintypes.ULONG),
        ("SecurityDescriptor", ctypes.c_void_p),
        ("SecurityQualityOfService", ctypes.c_void_p),
    ]


class IO_STATUS_BLOCK(ctypes.Structure):
    _fields_ = [
        ("Status", wintypes.LONG),
        ("Information", ctypes.c_size_t),
    ]


class FILETIME(ctypes.Structure):
    _fields_ = [
        ("low", wintypes.DWORD),
        ("high", wintypes.DWORD),
    ]


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("attributes", wintypes.DWORD),
        ("creation", FILETIME),
        ("access", FILETIME),
        ("write", FILETIME),
        ("volume", wintypes.DWORD),
        ("size_high", wintypes.DWORD),
        ("size_low", wintypes.DWORD),
        ("links", wintypes.DWORD),
        ("index_high", wintypes.DWORD),
        ("index_low", wintypes.DWORD),
    ]


def read_bounded_windows_source(
    root: Path,
    relative: Path,
    max_bytes: int,
    *,
    expected_identities: dict[tuple[str, ...], tuple[int, int]] | None = None,
) -> bytes:
    """Read a bounded file through validated directory handles.

    Rejects observed reparse points. Recorded volume and file identifiers
    detect substitution only when replacement identifiers differ. Filesystems
    may reuse identifiers; equality does not prove uninterrupted object
    identity. Does not claim an atomic filesystem snapshot or protection
    from concurrent content writes.
    """
    if os.name != "nt":
        raise WindowsSourceReadError("Windows only")

    if type(max_bytes) is not int or max_bytes < 1:
        raise WindowsSourceReadError("invalid byte budget")

    relative = Path(relative)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in (".", "..") for part in relative.parts)
        or any(":" in part for part in relative.parts)
    ):
        raise WindowsSourceReadError("invalid relative path")

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")

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

    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL

    attributes = kernel.GetFileInformationByHandle
    attributes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(BY_HANDLE_FILE_INFORMATION),
    ]
    attributes.restype = wintypes.BOOL

    read_file = kernel.ReadFile
    read_file.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    read_file.restype = wintypes.BOOL

    nt_create = ntdll.NtCreateFile
    nt_create.argtypes = [
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        ctypes.POINTER(OBJECT_ATTRIBUTES),
        ctypes.POINTER(IO_STATUS_BLOCK),
        ctypes.c_void_p,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        ctypes.c_void_p,
        wintypes.ULONG,
    ]
    nt_create.restype = wintypes.LONG

    def validate(handle, directory, identity_key=None):
        info = BY_HANDLE_FILE_INFORMATION()
        if not attributes(handle, ctypes.byref(info)):
            raise WindowsSourceReadError("component cannot be inspected")
        if info.attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            raise WindowsSourceReadError("reparse point unsupported")
        if bool(info.attributes & FILE_ATTRIBUTE_DIRECTORY) != directory:
            raise WindowsSourceReadError("unexpected component type")

        if expected_identities is not None:
            if identity_key not in expected_identities:
                raise WindowsSourceReadError("component identity unavailable")
            expected = expected_identities[identity_key]
            observed = (
                info.volume,
                (info.index_high << 32) | info.index_low,
            )
            if (
                type(expected) is not tuple
                or len(expected) != 2
                or any(type(value) is not int or value <= 0 for value in expected)
                or observed != expected
            ):
                raise WindowsSourceReadError("component identity changed")

    def open_relative(parent, component, directory, identity_key):
        buffer = ctypes.create_unicode_buffer(component)
        name = UNICODE_STRING(
            Length=len(component.encode("utf-16-le")),
            MaximumLength=ctypes.sizeof(buffer),
            Buffer=ctypes.addressof(buffer),
        )
        attrs = OBJECT_ATTRIBUTES(
            Length=ctypes.sizeof(OBJECT_ATTRIBUTES),
            RootDirectory=parent,
            ObjectName=ctypes.pointer(name),
            Attributes=OBJ_CASE_INSENSITIVE,
            SecurityDescriptor=None,
            SecurityQualityOfService=None,
        )
        io = IO_STATUS_BLOCK()
        handle = wintypes.HANDLE()

        status = nt_create(
            ctypes.byref(handle),
            FILE_READ_ATTRIBUTES
            | SYNCHRONIZE
            | (0 if directory else FILE_READ_DATA),
            ctypes.byref(attrs),
            ctypes.byref(io),
            None,
            0,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            FILE_OPEN,
            FILE_OPEN_REPARSE_POINT
            | FILE_SYNCHRONOUS_IO_NONALERT
            | (FILE_DIRECTORY_FILE if directory else FILE_NON_DIRECTORY_FILE),
            None,
            0,
        )

        if status < 0 or handle.value in (None, INVALID_HANDLE_VALUE):
            raise WindowsSourceReadError("relative component cannot be opened")

        try:
            validate(handle, directory, identity_key)
        except BaseException:
            close(handle)
            raise

        return handle

    root = Path(os.path.abspath(root))
    handles = []

    try:
        root_handle = create(
            str(root),
            FILE_READ_ATTRIBUTES | SYNCHRONIZE,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if root_handle in (None, INVALID_HANDLE_VALUE):
            raise WindowsSourceReadError("root cannot be opened")

        handles.append(root_handle)
        validate(root_handle, True, ())

        parent = root_handle
        for depth, component in enumerate(relative.parts[:-1], 1):
            parent = open_relative(
                parent, component, True, relative.parts[:depth]
            )
            handles.append(parent)

        target = open_relative(
            parent, relative.parts[-1], False, relative.parts
        )
        handles.append(target)

        remaining = max_bytes + 1
        chunks = []

        while remaining:
            amount = min(remaining, 65536)
            buffer = ctypes.create_string_buffer(amount)
            count = wintypes.DWORD()

            if not read_file(
                target,
                buffer,
                amount,
                ctypes.byref(count),
                None,
            ):
                raise WindowsSourceReadError("source cannot be read")

            if count.value == 0:
                break

            chunks.append(buffer.raw[:count.value])
            remaining -= count.value

        data = b"".join(chunks)
        if len(data) > max_bytes:
            raise WindowsSourceReadError("file byte budget exceeded")

        return data

    finally:
        for handle in reversed(handles):
            close(handle)
