
from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.general_system_lineage import (
    GeneralSystemLineageError,
    build_general_system_lineage,
    validate_general_system_lineage,
)


def fixture():
    systems = [
        {"system_id": "a", "domain": "machine", "label": "motor"},
        {"system_id": "b", "domain": "software", "label": "controller"},
    ]

    observations = [
        {
            "observation_id": "o1",
            "system_id": "a",
            "source_id": "sensor",
            "boundary": "2026-11-08T10:00:00Z",
            "evidence_hash": "a" * 64,
            "finding": {"temperature": 42},
        }
    ]

    relationship = {
        "relationship_id": "r1",
        "source_system_id": "a",
        "target_system_id": "b",
        "relationship_type": "communicates_with",
        "evidence_observation_ids": ["o1"],
        "status": "PROPOSED",
    }

    first = {
        "correction_id": "z-first",
        "target_record_hash": stable_hash(relationship),
        "evidence_observation_ids": ["o1"],
        "assessment": "First correction",
    }

    second = {
        "correction_id": "a-second",
        "target_record_hash": stable_hash(first),
        "evidence_observation_ids": ["o1"],
        "assessment": "Second correction",
    }

    return systems, observations, [relationship], first, second


def test_correction_can_reference_earlier_correction():
    systems, observations, relationships, first, second = fixture()

    report = build_general_system_lineage(
        systems, observations, relationships, [first, second]
    )

    assert validate_general_system_lineage(report)
    assert [c["correction_id"] for c in report["corrections"]] == [
        "z-first", "a-second"
    ]


def test_correction_cannot_reference_future_correction():
    systems, observations, relationships, first, second = fixture()

    with pytest.raises(GeneralSystemLineageError):
        build_general_system_lineage(
            systems, observations, relationships, [second, first]
        )


def test_correction_cannot_reference_itself():
    systems, observations, relationships, first, _ = fixture()
    first["target_record_hash"] = stable_hash(first)

    with pytest.raises(GeneralSystemLineageError):
        build_general_system_lineage(
            systems, observations, relationships, [first]
        )


def test_correction_cannot_reference_missing_record():
    systems, observations, relationships, first, _ = fixture()
    first["target_record_hash"] = "f" * 64

    with pytest.raises(GeneralSystemLineageError):
        build_general_system_lineage(
            systems, observations, relationships, [first]
        )


def test_reordering_independent_systems_preserves_identity():
    systems, observations, relationships, first, second = fixture()

    original = build_general_system_lineage(
        systems, observations, relationships, [first, second]
    )

    reordered = build_general_system_lineage(
        list(reversed(systems)),
        deepcopy(observations),
        deepcopy(relationships),
        [first, second],
    )

    assert original == reordered


def test_reordering_corrections_does_not_preserve_validity():
    systems, observations, relationships, first, second = fixture()

    build_general_system_lineage(
        systems, observations, relationships, [first, second]
    )

    with pytest.raises(GeneralSystemLineageError):
        build_general_system_lineage(
            systems, observations, relationships, [second, first]
        )
