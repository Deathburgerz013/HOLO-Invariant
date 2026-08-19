from copy import deepcopy

import pytest

from holosim.invariant_catalog import (
    catalog_invariant_files,
)
from holosim.invariant_legacy_normalization import (
    LegacyNormalizationError,
    build_legacy_normalization,
    reconstruct_legacy_region,
)


LEGACY = """| |List Known Invariants.
| |1. Conservation of energy: Energy remains conserved.

Additional/Missing Invariants (Pass 8)
Searching and Matching
KMP: The current state represents the longest matching prefix.
More collection instructions that are not numbered candidates.
"""


def test_legacy_regions_become_bounded_review_chunks(
    tmp_path,
):
    source = tmp_path / "legacy.md"
    source.write_text(LEGACY, encoding="utf-8")
    before = source.read_bytes()

    catalog = catalog_invariant_files([source])
    normalization = build_legacy_normalization(
        catalog,
        max_chunk_chars=48,
    )

    assert normalization["type"] == (
        "holo_invariant_legacy_normalization"
    )
    assert normalization["version"] == 1
    assert normalization["region_count"] == 1
    assert normalization["chunk_count"] > 1

    assert normalization["accepted"] is False
    assert normalization["truth_claimed"] is False
    assert normalization["write_authority"] == "NONE"
    assert normalization["canonical_mutation"] is False

    for index, chunk in enumerate(
        normalization["chunks"],
    ):
        assert chunk["chunk_index"] == index
        assert chunk["status"] == "needs_review"
        assert len(chunk["chunk_id"]) == 64
        assert len(chunk["content_hash"]) == 64
        assert len(chunk["text"]) <= 48

    assert source.read_bytes() == before


def test_chunks_reconstruct_exact_unparsed_region(tmp_path):
    source = tmp_path / "legacy.md"
    source.write_text(LEGACY, encoding="utf-8")

    catalog = catalog_invariant_files([source])
    normalization = build_legacy_normalization(
        catalog,
        max_chunk_chars=37,
    )

    expected = catalog["unparsed_regions"][0]["text"]
    reconstructed = reconstruct_legacy_region(
        normalization["chunks"]
    )

    assert reconstructed == expected


def test_normalization_is_deterministic(tmp_path):
    source = tmp_path / "legacy.md"
    source.write_text(LEGACY, encoding="utf-8")
    catalog = catalog_invariant_files([source])

    first = build_legacy_normalization(
        catalog,
        max_chunk_chars=48,
    )
    second = build_legacy_normalization(
        catalog,
        max_chunk_chars=48,
    )

    assert first == second
    assert len(first["normalization_hash"]) == 64


def test_reconstruction_rejects_tampered_chunk(tmp_path):
    source = tmp_path / "legacy.md"
    source.write_text(LEGACY, encoding="utf-8")
    catalog = catalog_invariant_files([source])

    normalization = build_legacy_normalization(
        catalog,
        max_chunk_chars=48,
    )
    tampered = deepcopy(normalization["chunks"])
    tampered[0]["text"] += " altered"

    with pytest.raises(
        LegacyNormalizationError,
        match="content hash mismatch",
    ):
        reconstruct_legacy_region(tampered)


def test_complete_catalog_produces_empty_normalization(
    tmp_path,
):
    source = tmp_path / "clean.md"
    source.write_text(
        "| |List Known Invariants.\n"
        "| |1. Conservation of energy: Energy remains "
        "conserved.\n",
        encoding="utf-8",
    )

    catalog = catalog_invariant_files([source])
    normalization = build_legacy_normalization(catalog)

    assert catalog["parse_complete"] is True
    assert normalization["region_count"] == 0
    assert normalization["chunk_count"] == 0
    assert normalization["chunks"] == []