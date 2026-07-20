import copy

import pytest

from holosim.correction_cycle import (
    CorrectionCycleError,
    build_correction_cycle,
    validate_correction_cycle,
)
from holosim.reconstructor import build_reconstruction_manifest


def _manifest(reference, prior, current):
    return build_reconstruction_manifest(reference, prior, current)


def test_cycle_stops_immediately_when_no_relevant_difference_exists():
    items = [{"id": "a", "value": 1}]
    manifest = _manifest("task", items, copy.deepcopy(items))

    cycle = build_correction_cycle("task", [manifest])

    assert cycle["status"] == "NO_RELEVANT_DIFFERENCE"
    assert cycle["terminal_index"] == 0
    assert cycle["next_correction_targets"] == []
    assert cycle["steps"][0]["correction_targets"] == []
    assert validate_correction_cycle(cycle) is True


def test_cycle_exposes_only_changed_and_missing_ids_as_targets():
    prior = [
        {"id": "a", "value": 1},
        {"id": "b", "value": 2},
        {"id": "c", "value": 3},
    ]
    current = [
        {"id": "a", "value": 100},
        {"id": "c", "value": 3},
        {"id": "new", "value": 4},
    ]
    manifest = _manifest("task", prior, current)

    cycle = build_correction_cycle("task", [manifest])

    assert cycle["status"] == "CORRECTION_REQUIRED"
    assert cycle["next_correction_targets"] == ["a", "b"]
    assert "new" not in cycle["next_correction_targets"]
    assert cycle["terminal_index"] is None


def test_added_environmental_growth_alone_does_not_keep_cycle_open():
    prior = [{"id": "a", "value": 1}]
    current = [
        {"id": "a", "value": 1},
        {"id": "new", "value": 2},
    ]
    manifest = _manifest("task", prior, current)

    cycle = build_correction_cycle("task", [manifest])

    assert manifest["status"] == "RECONSTRUCTED"
    assert manifest["added_ids"] == ["new"]
    assert cycle["status"] == "NO_RELEVANT_DIFFERENCE"


def test_cycle_tracks_successive_deltas_until_terminal_manifest():
    baseline = [
        {"id": "a", "value": 1},
        {"id": "b", "value": 2},
    ]
    first = _manifest(
        "task",
        baseline,
        [{"id": "a", "value": 10}, {"id": "b", "value": 2}],
    )
    second = _manifest(
        "task",
        baseline,
        copy.deepcopy(baseline),
    )

    cycle = build_correction_cycle("task", [first, second])

    assert cycle["status"] == "NO_RELEVANT_DIFFERENCE"
    assert cycle["processed_step_count"] == 2
    assert cycle["steps"][0]["correction_targets"] == ["a"]
    assert cycle["steps"][1]["correction_targets"] == []
    assert cycle["terminal_index"] == 1
    assert validate_correction_cycle(cycle) is True


def test_cycle_does_not_process_manifests_after_terminal_state():
    baseline = [{"id": "a", "value": 1}]
    terminal = _manifest("task", baseline, copy.deepcopy(baseline))
    later_difference = _manifest(
        "task",
        baseline,
        [{"id": "a", "value": 2}],
    )

    cycle = build_correction_cycle("task", [terminal, later_difference])

    assert cycle["processed_step_count"] == 1
    assert cycle["unprocessed_after_terminal_count"] == 1
    assert cycle["status"] == "NO_RELEVANT_DIFFERENCE"
    assert validate_correction_cycle(cycle) is True


def test_cycle_rejects_reference_drift():
    manifest = _manifest("other", [{"id": "a"}], [{"id": "a"}])

    with pytest.raises(CorrectionCycleError, match="cycle reference"):
        build_correction_cycle("task", [manifest])


def test_cycle_rejects_tampered_reconstruction_manifest():
    manifest = _manifest("task", [{"id": "a"}], [{"id": "a"}])
    manifest["status"] = "DIFFERENCE"

    with pytest.raises(CorrectionCycleError, match="valid reconstruction"):
        build_correction_cycle("task", [manifest])


def test_cycle_never_grants_authority():
    manifest = _manifest("task", [{"id": "a"}], [{"id": "a"}])
    cycle = build_correction_cycle("task", [manifest])

    assert cycle["accepted"] is False
    assert cycle["write_authority"] == "NONE"


def test_tampered_cycle_hash_is_rejected():
    manifest = _manifest("task", [{"id": "a"}], [{"id": "a"}])
    cycle = build_correction_cycle("task", [manifest])
    cycle["status"] = "CORRECTION_REQUIRED"

    with pytest.raises(CorrectionCycleError):
        validate_correction_cycle(cycle)


def test_empty_cycle_is_rejected():
    with pytest.raises(CorrectionCycleError, match="must not be empty"):
        build_correction_cycle("task", [])
