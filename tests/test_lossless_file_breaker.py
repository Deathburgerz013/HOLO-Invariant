import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from holosim.lossless_file_breaker import (
    LosslessFileBreakerError,
    create_lossless_file_break,
    reconstruct_lossless_file,
    verify_lossless_file_break,
)


def canonical_hash(value):
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_binary_file_round_trips_without_source_mutation(
    tmp_path,
):
    source = tmp_path / "source.bin"
    original = (
        bytes(range(256))
        + b"\x00\xffHOLO\r\n"
        + bytes(range(255, -1, -1))
    )
    source.write_bytes(original)
    before = source.read_bytes()

    workspace = tmp_path / "broken"
    manifest = create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=73,
    )

    candidate = tmp_path / "candidate.bin"
    result = reconstruct_lossless_file(
        workspace,
        candidate,
    )

    assert source.read_bytes() == before
    assert candidate.read_bytes() == original
    assert result["output_hash"] == manifest[
        "source_hash"
    ]
    assert result["exact_round_trip"] is True
    assert result["source_mutation"] is False
    assert result["canonical_mutation"] is False


def test_chunks_are_bounded_contiguous_and_hash_bound(
    tmp_path,
):
    source = tmp_path / "large.txt"
    source.write_bytes(b"abcdefghij" * 30)

    workspace = tmp_path / "chunks"
    manifest = create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=64,
    )

    expected_offset = 0

    for chunk in manifest["chunks"]:
        chunk_path = workspace / chunk["filename"]
        content = chunk_path.read_bytes()

        assert len(content) <= 64
        assert chunk["offset"] == expected_offset
        assert chunk["length"] == len(content)
        assert chunk["hash"] == hashlib.sha256(
            content
        ).hexdigest()

        expected_offset += len(content)

    assert expected_offset == manifest["source_size"]
    assert verify_lossless_file_break(
        workspace
    ) == manifest


def test_manifest_is_deterministic_across_workspaces(
    tmp_path,
):
    source = tmp_path / "source.txt"
    source.write_text(
        "deterministic derived workspace",
        encoding="utf-8",
    )

    first = create_lossless_file_break(
        source,
        tmp_path / "first",
        max_chunk_bytes=8,
    )
    second = create_lossless_file_break(
        source,
        tmp_path / "second",
        max_chunk_bytes=8,
    )

    assert first == second
    assert first["manifest_hash"] == second[
        "manifest_hash"
    ]


def test_tampered_chunk_is_rejected(
    tmp_path,
):
    source = tmp_path / "source.txt"
    source.write_text(
        "one two three four five",
        encoding="utf-8",
    )
    workspace = tmp_path / "broken"
    manifest = create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=5,
    )

    first_chunk = (
        workspace
        / manifest["chunks"][0]["filename"]
    )
    first_chunk.write_bytes(
        first_chunk.read_bytes() + b"tampered"
    )

    with pytest.raises(
        LosslessFileBreakerError,
        match="chunk hash mismatch",
    ):
        verify_lossless_file_break(workspace)


def test_missing_chunk_is_rejected(
    tmp_path,
):
    source = tmp_path / "source.txt"
    source.write_text(
        "chunk disappearance must fail",
        encoding="utf-8",
    )
    workspace = tmp_path / "broken"
    manifest = create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=5,
    )

    (
        workspace
        / manifest["chunks"][0]["filename"]
    ).unlink()

    with pytest.raises(
        LosslessFileBreakerError,
        match="chunk file is missing",
    ):
        reconstruct_lossless_file(
            workspace,
            tmp_path / "candidate.txt",
        )


def test_reconstruction_refuses_existing_output(
    tmp_path,
):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    workspace = tmp_path / "broken"

    create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=3,
    )

    candidate = tmp_path / "candidate.txt"
    candidate.write_text(
        "do not overwrite",
        encoding="utf-8",
    )

    with pytest.raises(
        LosslessFileBreakerError,
        match="output path already exists",
    ):
        reconstruct_lossless_file(
            workspace,
            candidate,
        )

    assert candidate.read_text(
        encoding="utf-8"
    ) == "do not overwrite"


def test_empty_file_round_trips_exactly(
    tmp_path,
):
    source = tmp_path / "empty.bin"
    source.write_bytes(b"")
    workspace = tmp_path / "broken"

    manifest = create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=16,
    )

    assert manifest["source_size"] == 0
    assert manifest["chunks"] == []

    candidate = tmp_path / "empty-copy.bin"
    result = reconstruct_lossless_file(
        workspace,
        candidate,
    )

    assert candidate.read_bytes() == b""
    assert result["exact_round_trip"] is True


@pytest.mark.parametrize(
    "max_chunk_bytes",
    [
        0,
        -1,
        True,
        1.5,
        "64",
    ],
)
def test_chunk_size_must_be_positive_integer(
    tmp_path,
    max_chunk_bytes,
):
    source = tmp_path / "source.bin"
    source.write_bytes(b"content")

    with pytest.raises(
        LosslessFileBreakerError,
        match="max_chunk_bytes must be a positive integer",
    ):
        create_lossless_file_break(
            source,
            tmp_path / "broken",
            max_chunk_bytes=max_chunk_bytes,
        )


def test_rehashed_path_traversal_manifest_is_rejected(
    tmp_path,
):
    source = tmp_path / "source.bin"
    source.write_bytes(b"bounded content")
    workspace = tmp_path / "broken"

    manifest = create_lossless_file_break(
        source,
        workspace,
        max_chunk_bytes=8,
    )

    forged = deepcopy(manifest)
    forged["chunks"][0]["filename"] = (
        "../outside.part"
    )
    body = {
        key: value
        for key, value in forged.items()
        if key != "manifest_hash"
    }
    forged["manifest_hash"] = canonical_hash(body)

    (workspace / "manifest.json").write_text(
        json.dumps(forged, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(
        LosslessFileBreakerError,
        match="chunk path escapes workspace",
    ):
        verify_lossless_file_break(workspace)


def test_workspace_cannot_replace_source_or_existing_data(
    tmp_path,
):
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")

    with pytest.raises(
        LosslessFileBreakerError,
        match="workspace path already exists",
    ):
        create_lossless_file_break(
            source,
            source,
            max_chunk_bytes=4,
        )

    workspace = tmp_path / "existing"
    workspace.mkdir()
    (workspace / "user-data.txt").write_text(
        "preserve me",
        encoding="utf-8",
    )

    with pytest.raises(
        LosslessFileBreakerError,
        match="workspace path already exists",
    ):
        create_lossless_file_break(
            source,
            workspace,
            max_chunk_bytes=4,
        )

    assert (
        workspace / "user-data.txt"
    ).read_text(encoding="utf-8") == "preserve me"