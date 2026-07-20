import copy

from holosim.reconstructor import (
    build_reconstructed_state,
    build_reconstruction_manifest,
    validate_reconstructed_state,
    validate_reconstruction_manifest,
)


def _source_items():
    return [
        {"id": "a", "requires": ["b"], "state": "supported", "value": 1},
        {"id": "b", "requires": ["c"], "state": "supported", "value": 2},
        {"id": "c", "requires": [], "state": "supported", "value": 3},
        {"id": "x", "requires": [], "state": "unrelated", "value": 99},
    ]


def test_receiver_revalidates_exact_reconstructed_state_as_current():
    source = _source_items()
    state = build_reconstructed_state("receiver task", ["a"], source)
    assert validate_reconstructed_state(state, source) is True

    present = copy.deepcopy(state["carried_items"])
    result = build_reconstruction_manifest(
        state["reference"],
        state["carried_items"],
        present,
    )

    assert result["status"] == "RECONSTRUCTED"
    assert result["preserved_ids"] == ["a", "b", "c"]
    assert result["changed"] == []
    assert result["missing_ids"] == []
    assert result["added_ids"] == []
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert validate_reconstruction_manifest(result) is True


def test_receiver_exposes_changed_dependency_without_correcting_it():
    source = _source_items()
    state = build_reconstructed_state("receiver task", ["a"], source)
    present = copy.deepcopy(state["carried_items"])
    present_by_id = {item["id"]: item for item in present}
    present_by_id["b"]["value"] = 200

    result = build_reconstruction_manifest(
        state["reference"],
        state["carried_items"],
        present,
    )

    assert result["status"] == "DIFFERENCE"
    assert result["preserved_ids"] == ["a", "c"]
    assert [entry["id"] for entry in result["changed"]] == ["b"]
    assert result["missing_ids"] == []
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_receiver_exposes_missing_dependency_without_inventing_state():
    source = _source_items()
    state = build_reconstructed_state("receiver task", ["a"], source)
    present = [item for item in copy.deepcopy(state["carried_items"]) if item["id"] != "c"]

    result = build_reconstruction_manifest(
        state["reference"],
        state["carried_items"],
        present,
    )

    assert result["status"] == "DIFFERENCE"
    assert result["missing_ids"] == ["c"]
    assert result["added_ids"] == []


def test_receiver_preserves_explicit_unknown_as_difference_not_truth():
    source = _source_items()
    state = build_reconstructed_state("receiver task", ["a"], source)
    present = copy.deepcopy(state["carried_items"])
    present_by_id = {item["id"]: item for item in present}
    present_by_id["c"] = {
        "id": "c",
        "requires": [],
        "state": "unknown",
        "value": None,
    }

    result = build_reconstruction_manifest(
        state["reference"],
        state["carried_items"],
        present,
    )

    assert result["status"] == "DIFFERENCE"
    assert [entry["id"] for entry in result["changed"]] == ["c"]
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_receiver_environment_growth_does_not_invalidate_preserved_reconstruction():
    source = _source_items()
    state = build_reconstructed_state("receiver task", ["a"], source)
    present = copy.deepcopy(state["carried_items"])
    present.append({"id": "new", "requires": [], "state": "supported", "value": 4})

    result = build_reconstruction_manifest(
        state["reference"],
        state["carried_items"],
        present,
    )

    assert result["status"] == "RECONSTRUCTED"
    assert result["preserved_ids"] == ["a", "b", "c"]
    assert result["added_ids"] == ["new"]
    assert result["missing_ids"] == []
