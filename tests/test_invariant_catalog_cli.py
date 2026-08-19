import json
from pathlib import Path

from holosim.invariant_catalog import main


RAW = """| |List Known Invariants.
| |1. Conservation of energy: Energy remains conserved.
| |2. Fundamental theorem of arithmetic: Prime factorization is unique.
"""


LEGACY = """| |List Known Invariants.
| |1. Conservation of energy: Energy remains conserved.

Additional/Missing Invariants
Unstructured legacy material.
"""


def test_cli_prints_json_without_modifying_source(
    tmp_path,
    capsys,
):
    source = tmp_path / "candidates.md"
    source.write_text(RAW, encoding="utf-8")
    before = source.read_bytes()

    result = main([
        str(source),
        "--format",
        "json",
    ])

    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output["candidate_count"] == 2
    assert output["parse_complete"] is True
    assert output["canonical_mutation"] is False
    assert output["write_authority"] == "NONE"
    assert source.read_bytes() == before


def test_cli_writes_review_report_not_canonical_source(
    tmp_path,
):
    source = tmp_path / "candidates.md"
    report = tmp_path / "proposal.md"
    source.write_text(RAW, encoding="utf-8")
    before = source.read_bytes()

    result = main([
        str(source),
        "--output",
        str(report),
    ])

    assert result == 0
    assert report.exists()
    assert report.read_text(
        encoding="utf-8",
    ).startswith("# Invariant Catalog Proposal")
    assert source.read_bytes() == before


def test_cli_signals_incomplete_legacy_parse(
    tmp_path,
    capsys,
):
    source = tmp_path / "legacy.md"
    source.write_text(LEGACY, encoding="utf-8")

    result = main([str(source)])

    output = capsys.readouterr().out

    assert result == 1
    assert "Parse complete: `False`" in output
    assert "UNPARSED_CONTENT" in output


def test_cli_refuses_to_overwrite_source(tmp_path):
    source = tmp_path / "candidates.md"
    source.write_text(RAW, encoding="utf-8")
    before = source.read_bytes()

    result = main([
        str(source),
        "--output",
        str(source),
    ])

    assert result == 2
    assert source.read_bytes() == before