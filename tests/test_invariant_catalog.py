from holosim.invariant_catalog import (
    catalog_invariant_files,
    extract_numbered_invariants,
    inspect_invariant_text,
    organize_invariants,
    render_catalog_markdown,
)


RAW_COLLECTION = """| |===================================|
| |List Known Invariants.
| |1. Conservation of energy: Energy cannot be created or destroyed,
| |only converted from one form to another.
| |2. Logical non-contradiction: A proposition and its negation cannot
| |both be true in the same respect at the same time.
| |3. Conservation of energy: Energy cannot be created or destroyed,
| |only converted from one form to another.
| |4. Fundamental theorem of arithmetic: Every integer greater than 1
| |has a unique prime factorization.
| |===============================|
"""


LEGACY_COLLECTION = """| |List Known Invariants.
| |1. Conservation of energy: Energy cannot be created or destroyed,
| |only converted from one form to another.

Additional/Missing Invariants (Pass 8)
Searching and Matching
KMP: The current state represents the longest matching prefix.
More collection instructions that are not numbered candidates.
"""


def test_extracts_candidates_without_losing_continuations():
    candidates = extract_numbered_invariants(
        RAW_COLLECTION,
        source="raw.md",
    )

    assert [
        item["source_number"]
        for item in candidates
    ] == [1, 2, 3, 4]

    assert candidates[0] == {
        "source": "raw.md",
        "source_number": 1,
        "statement": (
            "Conservation of energy: Energy cannot be "
            "created or destroyed, only converted from "
            "one form to another."
        ),
    }


def test_organizer_classifies_without_promoting_candidates():
    catalog = organize_invariants(
        extract_numbered_invariants(
            RAW_COLLECTION,
            source="raw.md",
        )
    )

    assert catalog["type"] == (
        "holo_invariant_catalog_proposal"
    )
    assert catalog["version"] == 1
    assert catalog["candidate_count"] == 4
    assert catalog["unique_count"] == 3
    assert catalog["duplicate_count"] == 1

    energy, logic, duplicate, arithmetic = (
        catalog["candidates"]
    )

    assert energy["domain"] == "physics"
    assert energy["kind"] == "conservation"
    assert energy["proposed_destination"] == (
        "docs/Physics_Spine.md"
    )
    assert energy["status"] == "candidate"
    assert energy["duplicate_of"] is None

    assert logic["domain"] == "logic_epistemology"
    assert logic["kind"] == "logical"
    assert logic["proposed_destination"] == (
        "docs/Logic_Epistemology_Spine.md"
    )

    assert duplicate["duplicate_of"] == (
        energy["candidate_id"]
    )

    assert arithmetic["domain"] == "mathematics"
    assert arithmetic["kind"] == "theorem"
    assert arithmetic["proposed_destination"] == (
        "docs/Mathematics_Spine.md"
    )

    assert catalog["accepted"] is False
    assert catalog["truth_claimed"] is False
    assert catalog["write_authority"] == "NONE"
    assert catalog["canonical_mutation"] is False


def test_catalog_is_deterministic():
    candidates = extract_numbered_invariants(
        RAW_COLLECTION,
        source="raw.md",
    )

    first = organize_invariants(candidates)
    second = organize_invariants(candidates)

    assert first == second
    assert len(first["catalog_hash"]) == 64


def test_catalogs_markdown_files_without_modifying_sources(
    tmp_path,
):
    source_path = tmp_path / "raw-invariants.md"
    source_path.write_text(
        RAW_COLLECTION,
        encoding="utf-8",
    )
    before = source_path.read_bytes()

    catalog = catalog_invariant_files([source_path])

    assert catalog["candidate_count"] == 4
    assert catalog["source_files"] == [
        str(source_path),
    ]
    assert catalog["parse_complete"] is True
    assert catalog["parse_warnings"] == []
    assert catalog["unparsed_regions"] == []
    assert source_path.read_bytes() == before
    assert catalog["canonical_mutation"] is False


def test_renders_bounded_review_report(tmp_path):
    source_path = tmp_path / "raw-invariants.md"
    source_path.write_text(
        RAW_COLLECTION,
        encoding="utf-8",
    )

    report = render_catalog_markdown(
        catalog_invariant_files([source_path])
    )

    assert report.startswith(
        "# Invariant Catalog Proposal"
    )
    assert (
        "This report does not promote canonical knowledge."
        in report
    )
    assert "Parse complete: `True`" in report
    assert "## docs/Physics_Spine.md" in report
    assert (
        "## docs/Logic_Epistemology_Spine.md"
        in report
    )
    assert "## docs/Mathematics_Spine.md" in report
    assert "**Status:** candidate" in report
    assert "**Duplicate of:**" in report
    assert "Write authority: `NONE`" in report


def test_legacy_content_is_reported_instead_of_swallowed():
    inspection = inspect_invariant_text(
        LEGACY_COLLECTION,
        source="legacy.md",
    )

    assert len(inspection["candidates"]) == 1
    assert inspection["candidates"][0]["statement"] == (
        "Conservation of energy: Energy cannot be "
        "created or destroyed, only converted from "
        "one form to another."
    )
    assert inspection["parse_complete"] is False
    assert inspection["parse_warnings"] == [
        {
            "code": "UNPARSED_CONTENT",
            "source": "legacy.md",
            "region_count": 1,
        }
    ]
    assert inspection["unparsed_regions"] == [
        {
            "source": "legacy.md",
            "start_line": 5,
            "end_line": 8,
            "text": (
                "Additional/Missing Invariants (Pass 8)\n"
                "Searching and Matching\n"
                "KMP: The current state represents the "
                "longest matching prefix.\n"
                "More collection instructions that are "
                "not numbered candidates."
            ),
        }
    ]


def test_file_catalog_preserves_legacy_parse_diagnostics(
    tmp_path,
):
    source_path = tmp_path / "legacy.md"
    source_path.write_text(
        LEGACY_COLLECTION,
        encoding="utf-8",
    )
    before = source_path.read_bytes()

    catalog = catalog_invariant_files([source_path])

    assert catalog["candidate_count"] == 1
    assert catalog["parse_complete"] is False
    assert catalog["parse_warnings"][0]["code"] == (
        "UNPARSED_CONTENT"
    )
    assert len(catalog["unparsed_regions"]) == 1
    assert source_path.read_bytes() == before

    report = render_catalog_markdown(catalog)

    assert "Parse complete: `False`" in report
    assert "## Parse warnings" in report
    assert "`UNPARSED_CONTENT`" in report
    assert "## Unparsed legacy regions" in report
    assert "Additional/Missing Invariants" in report