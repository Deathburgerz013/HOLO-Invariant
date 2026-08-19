import json

from holosim.invariant_legacy_normalization import main


LEGACY = """| |List Known Invariants.
| |1. Conservation of energy: Energy remains conserved.

Additional/Missing Invariants
Searching and Matching
KMP: Current state represents the longest matching prefix.
"""


def test_cli_prints_normalization_without_source_mutation(
    tmp_path,
    capsys,
):
    source = tmp_path / "legacy.md"
    source.write_text(LEGACY, encoding="utf-8")
    before = source.read_bytes()

    result = main([
        str(source),
        "--max-chunk-chars",
        "48",
    ])

    normalization = json.loads(
        capsys.readouterr().out
    )

    assert result == 0
    assert normalization["region_count"] == 1
    assert normalization["chunk_count"] > 1
    assert normalization["accepted"] is False
    assert normalization["truth_claimed"] is False
    assert normalization["write_authority"] == "NONE"
    assert normalization["canonical_mutation"] is False
    assert source.read_bytes() == before


def test_cli_writes_review_json(tmp_path):
    source = tmp_path / "legacy.md"
    output = tmp_path / "normalization.json"
    source.write_text(LEGACY, encoding="utf-8")
    before = source.read_bytes()

    result = main([
        str(source),
        "--max-chunk-chars",
        "48",
        "--output",
        str(output),
    ])

    normalization = json.loads(
        output.read_text(encoding="utf-8")
    )

    assert result == 0
    assert normalization["region_count"] == 1
    assert len(normalization["normalization_hash"]) == 64
    assert source.read_bytes() == before


def test_cli_refuses_to_overwrite_source(tmp_path):
    source = tmp_path / "legacy.md"
    source.write_text(LEGACY, encoding="utf-8")
    before = source.read_bytes()

    result = main([
        str(source),
        "--output",
        str(source),
    ])

    assert result == 2
    assert source.read_bytes() == before


def test_cli_rejects_invalid_chunk_size(
    tmp_path,
    capsys,
):
    source = tmp_path / "legacy.md"
    source.write_text(LEGACY, encoding="utf-8")

    result = main([
        str(source),
        "--max-chunk-chars",
        "0",
    ])

    assert result == 2
    assert "max_chunk_chars" in capsys.readouterr().err