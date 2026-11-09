
from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.general_system_lineage import (
    GeneralSystemLineageError,
    build_general_system_lineage,
    validate_general_system_lineage,
)


def sample():
    systems = [
        {"system_id": "a", "domain": "machine", "label": "motor"},
        {"system_id": "b", "domain": "software", "label": "controller"},
    ]
    observations = [
        {"observation_id": "o1", "system_id": "a", "source_id": "sensor-1",
         "boundary": "2026-11-08T10:00:00Z", "evidence_hash": "a" * 64,
         "finding": {"temperature": 42}},
        {"observation_id": "o2", "system_id": "b", "source_id": "log-1",
         "boundary": "2026-11-08T10:01:00Z", "evidence_hash": "b" * 64,
         "finding": {"status": "running"}},
    ]
    relationships = [
        {"relationship_id": "r1", "source_system_id": "a", "target_system_id": "b",
         "relationship_type": "communicates_with", "evidence_observation_ids": ["o1"],
         "status": "PROPOSED"},
        {"relationship_id": "r2", "source_system_id": "b", "target_system_id": "a",
         "relationship_type": "controls", "evidence_observation_ids": ["o2"],
         "status": "UNKNOWN"},
    ]
    corrections = [
        {"correction_id": "c1", "target_record_hash": stable_hash(relationships[0]),
         "evidence_observation_ids": ["o2"], "assessment": "Reconsider link"},
    ]
    return systems, observations, relationships, corrections


def test_build_and_validate():
    assert validate_general_system_lineage(build_general_system_lineage(*sample()))


def test_input_order_does_not_change_identity():
    inputs = sample()
    other = deepcopy(inputs)
    other[0].reverse()
    other[1].reverse()
    other[2].reverse()
    assert build_general_system_lineage(*inputs) == build_general_system_lineage(*other)


def test_input_is_not_mutated():
    inputs = sample()
    original = deepcopy(inputs)
    build_general_system_lineage(*inputs)
    assert inputs == original


@pytest.mark.parametrize("index,mutation", [
    (0, lambda x: x[0].update(system_id="a")),
    (1, lambda x: x[0].update(system_id="missing")),
    (1, lambda x: x[0].update(evidence_hash="bad")),
    (1, lambda x: x[0].update(finding={"bad": float("nan")})),
    (2, lambda x: x[0].update(target_system_id="missing")),
    (2, lambda x: x[0].update(evidence_observation_ids=["missing"])),
    (3, lambda x: x[0].update(target_record_hash="f" * 64)),
    (3, lambda x: x[0].update(evidence_observation_ids=["missing"])),
])
def test_invalid_records_fail(index, mutation):
    inputs = sample()
    mutation(inputs[index])
    if index == 0:
        inputs[0].append(deepcopy(inputs[0][0]))
    with pytest.raises(GeneralSystemLineageError):
        build_general_system_lineage(*inputs)


def test_duplicate_observation_fails():
    inputs = sample()
    inputs[1].append(deepcopy(inputs[1][0]))
    with pytest.raises(GeneralSystemLineageError, match="duplicate"):
        build_general_system_lineage(*inputs)


def test_correction_cannot_target_itself():
    inputs = sample()
    inputs[3][0]["target_record_hash"] = stable_hash(inputs[3][0])
    with pytest.raises(GeneralSystemLineageError):
        build_general_system_lineage(*inputs)


@pytest.mark.parametrize("field,value", [
    ("truth_claimed", True), ("accepted", True), ("write_authority", "WRITE"),
    ("version", True), ("lineage_hash", "0" * 64),
])
def test_report_tampering_fails(field, value):
    report = build_general_system_lineage(*sample())
    report[field] = value
    with pytest.raises(GeneralSystemLineageError):
        validate_general_system_lineage(report)


def test_nested_record_tampering_fails():
    report = build_general_system_lineage(*sample())
    report["observations"][0]["finding"] = {"temperature": 999}
    with pytest.raises(GeneralSystemLineageError):
        validate_general_system_lineage(report)


def test_no_observations_does_not_imply_contradiction():
    report = build_general_system_lineage(
        [{"system_id": "a", "domain": "human", "label": "learner"}], [], [], []
    )
    assert validate_general_system_lineage(report)
