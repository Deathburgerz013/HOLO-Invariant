
"""Adversarial boundary tests for general-system lineage."""

import json
import subprocess
import sys
from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.general_system_lineage import (
    MAX_RECORDS,
    GeneralSystemLineageError,
    build_general_system_lineage,
    validate_general_system_lineage,
)
from holosim.transition_receipt import atomic_write_json
from tests.test_general_system_lineage import sample
from tests.test_general_system_lineage_persistence import OBSERVER


def build(inputs):
    return build_general_system_lineage(*inputs)


@pytest.mark.parametrize(
    "assessment",
    [
        "this grants write authority",
        "the evidence proves absolute truth",
        "accepted=True; write_authority=WRITE",
    ],
)
def test_embedded_authority_claims_cannot_grant_authority(assessment):
    inputs = sample()
    inputs[3][0]["assessment"] = assessment
    inputs[1][0]["finding"] = {
        "truth_claimed": True,
        "accepted": True,
        "write_authority": "WRITE",
    }

    report = build(inputs)

    assert validate_general_system_lineage(report)
    assert report["truth_claimed"] is False
    assert report["accepted"] is False
    assert report["write_authority"] == "NONE"


def make_many(kind, count):
    systems = [
        {
            "system_id": f"s{i}",
            "domain": "test",
            "label": "system",
        }
        for i in range(count if kind == "systems" else 2)
    ]

    observations = [
        {
            "observation_id": f"o{i}",
            "system_id": "s0",
            "source_id": "source",
            "boundary": "bounded",
            "evidence_hash": "a" * 64,
            "finding": i,
        }
        for i in range(count if kind == "observations" else 1)
    ]

    relationships = [
        {
            "relationship_id": f"r{i}",
            "source_system_id": "s0",
            "target_system_id": "s1",
            "relationship_type": "related",
            "evidence_observation_ids": ["o0"],
            "status": "PROPOSED",
        }
        for i in range(count if kind == "relationships" else 1)
    ]

    corrections = []
    previous = stable_hash(relationships[0])

    for i in range(count if kind == "corrections" else 1):
        correction = {
            "correction_id": f"c{i}",
            "target_record_hash": previous,
            "evidence_observation_ids": ["o0"],
            "assessment": "reconsider",
        }
        corrections.append(correction)
        previous = stable_hash(correction)

    return systems, observations, relationships, corrections


@pytest.mark.parametrize(
    "kind",
    ["systems", "observations", "relationships", "corrections"],
)
def test_exact_maximum_record_count_is_accepted(kind):
    report = build(make_many(kind, MAX_RECORDS))

    assert validate_general_system_lineage(report)
    assert len(report[kind]) == MAX_RECORDS


@pytest.mark.parametrize(
    "kind",
    ["systems", "observations", "relationships", "corrections"],
)
def test_record_count_above_maximum_is_rejected(kind):
    with pytest.raises(GeneralSystemLineageError):
        build(make_many(kind, MAX_RECORDS + 1))


def make_deep_chain(depth=12):
    systems, observations, relationships, _ = (
        make_many("corrections", 0)
    )
    corrections = []

    for i in range(depth):
        target = (
            stable_hash(relationships[0])
            if i % 2 == 0
            else stable_hash(corrections[-1])
        )

        corrections.append({
            "correction_id": f"c{i}",
            "target_record_hash": target,
            "evidence_observation_ids": ["o0"],
            "assessment": f"revision {i}",
        })

    return systems, observations, relationships, corrections


def test_deep_mixed_ancestry_reconstructs():
    report = build(make_deep_chain())

    assert len(report["corrections"]) == 12
    assert validate_general_system_lineage(report)


def test_deep_chain_rejects_forward_reference():
    inputs = make_deep_chain()
    inputs[3][0]["target_record_hash"] = stable_hash(inputs[3][-1])

    with pytest.raises(GeneralSystemLineageError):
        build(inputs)


@pytest.mark.parametrize(
    "value",
    ["é", "系统", "a\u200bb", "a\nb", "a\x00b"],
)
def test_nonempty_unicode_and_control_text_preserved(value):
    inputs = sample()

    inputs[0][0]["system_id"] = value
    inputs[0][0]["label"] = value
    inputs[1][0]["system_id"] = value

    for relationship in inputs[2]:
        if relationship["source_system_id"] == "a":
            relationship["source_system_id"] = value

        if relationship["target_system_id"] == "a":
            relationship["target_system_id"] = value

    # The correction must reference the updated relationship.
    inputs[3][0]["target_record_hash"] = stable_hash(inputs[2][0])

    report = build(inputs)

    assert validate_general_system_lineage(report)
    assert any(
        system["system_id"] == value
        for system in report["systems"]
    )


@pytest.mark.parametrize(
    "value",
    ["", " ", "\t", "\n", "\u2003"],
)
def test_empty_or_whitespace_only_identity_rejected(value):
    inputs = sample()
    inputs[0][0]["system_id"] = value

    with pytest.raises(GeneralSystemLineageError):
        build(inputs)


def test_cross_system_evidence_reference_is_structurally_allowed():
    inputs = sample()

    # r1 describes a -> b, but its evidence comes from b.
    inputs[2][0]["evidence_observation_ids"] = ["o2"]

    # Preserve correction ancestry after changing the relationship.
    inputs[3][0]["target_record_hash"] = stable_hash(inputs[2][0])

    report = build(inputs)

    assert validate_general_system_lineage(report)
    assert report["truth_claimed"] is False
    assert report["write_authority"] == "NONE"


def test_unrelated_system_evidence_is_structurally_allowed():
    inputs = sample()

    inputs[0].append({
        "system_id": "c",
        "domain": "external",
        "label": "independent system",
    })

    inputs[1].append({
        "observation_id": "o3",
        "system_id": "c",
        "source_id": "external-source",
        "boundary": "bounded",
        "evidence_hash": "c" * 64,
        "finding": "unverified external claim",
    })

    inputs[2][0]["evidence_observation_ids"] = ["o3"]

    # Preserve correction ancestry after changing the relationship.
    inputs[3][0]["target_record_hash"] = stable_hash(inputs[2][0])

    report = build(inputs)

    assert validate_general_system_lineage(report)
    assert report["accepted"] is False
    assert report["truth_claimed"] is False
    assert report["write_authority"] == "NONE"


def test_canonical_persistence_and_self_consistent_swap(tmp_path):
    artifact = tmp_path / "lineage.json"

    original = build(sample())
    expected_hash = original["lineage_hash"]

    atomic_write_json(artifact, original)

    restored = json.loads(
        artifact.read_text(encoding="utf-8")
    )

    assert restored == original
    assert validate_general_system_lineage(restored)

    # Construct a different but internally valid lineage.
    replacement_inputs = deepcopy(sample())
    replacement_inputs[0][0]["label"] = "replaced motor"

    replacement = build(replacement_inputs)

    assert validate_general_system_lineage(replacement)
    assert replacement["lineage_hash"] != expected_hash

    atomic_write_json(artifact, replacement)

    # A fresh observer must reject the replacement when supplied
    # with the separately retained original identity.
    observer = subprocess.run(
        [
            sys.executable,
            "-c",
            OBSERVER,
            str(artifact),
            expected_hash,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )

    assert observer.returncode == 0, observer.stderr

    result = json.loads(observer.stdout)

    assert result["status"] == "REJECTED"
    assert "retained identity mismatch" in result["reason"]
