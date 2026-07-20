import copy

import pytest

from holosim.reconstructor import (
    ReconstructionError,
    build_reconstruction_manifest,
    validate_reconstruction_manifest,
)


def test_identical_explicit_items_reconstruct_without_difference():
    items = [
        {"id": "core", "state": "supported", "evidence": ["a"]},
        {"id": "rail", "state": "supported", "evidence": ["b"]},
    ]
    manifest = build_reconstruction_manifest("current task", items, copy.deepcopy(items))

    assert manifest["status"] == "RECONSTRUCTED"
    assert manifest["preserved_ids"] == ["core", "rail"]
    assert manifest["changed"] == []
    assert manifest["missing_ids"] == []
    assert manifest["added_ids"] == []
    assert manifest["accepted"] is False
    assert manifest["write_authority"] == "NONE"
    assert validate_reconstruction_manifest(manifest) is True


def test_difference_is_exposed_without_interpretation():
    prior = [
        {"id": "claim", "state": "inferred"},
        {"id": "stable", "value": 1},
        {"id": "gone", "value": 2},
    ]
    current = [
        {"id": "claim", "state": "corrected"},
        {"id": "stable", "value": 1},
        {"id": "new", "value": 3},
    ]
    manifest = build_reconstruction_manifest("reconstruct claim", prior, current)

    assert manifest["status"] == "DIFFERENCE"
    assert manifest["preserved_ids"] == ["stable"]
    assert [item["id"] for item in manifest["changed"]] == ["claim"]
    assert manifest["missing_ids"] == ["gone"]
    assert manifest["added_ids"] == ["new"]
    assert validate_reconstruction_manifest(manifest) is True


def test_added_information_does_not_make_preserved_state_a_difference():
    prior = [{"id": "known", "value": 1}]
    current = [{"id": "known", "value": 1}, {"id": "later", "value": 2}]

    manifest = build_reconstruction_manifest("later environment", prior, current)

    assert manifest["status"] == "RECONSTRUCTED"
    assert manifest["preserved_ids"] == ["known"]
    assert manifest["added_ids"] == ["later"]


def test_reconstructor_does_not_infer_semantic_equivalence():
    prior = [{"id": "teacher", "value": "learner"}]
    current = [{"id": "learner", "value": "teacher"}]

    manifest = build_reconstruction_manifest("roles", prior, current)

    assert manifest["preserved_ids"] == []
    assert manifest["missing_ids"] == ["teacher"]
    assert manifest["added_ids"] == ["learner"]


def test_duplicate_ids_fail_closed():
    with pytest.raises(ReconstructionError, match="duplicate"):
        build_reconstruction_manifest(
            "reference",
            [{"id": "same"}, {"id": "same"}],
            [],
        )


def test_nonfinite_values_fail_closed():
    with pytest.raises(ReconstructionError, match="finite"):
        build_reconstruction_manifest(
            "reference",
            [{"id": "bad", "value": float("inf")}],
            [],
        )


def test_cycles_fail_closed():
    cyclic = {"id": "cycle"}
    cyclic["self"] = cyclic
    with pytest.raises(ReconstructionError, match="cycles"):
        build_reconstruction_manifest("reference", [cyclic], [])


def test_tampered_manifest_is_rejected():
    manifest = build_reconstruction_manifest(
        "reference",
        [{"id": "a", "value": 1}],
        [{"id": "a", "value": 1}],
    )
    manifest["status"] = "DIFFERENCE"

    with pytest.raises(ReconstructionError):
        validate_reconstruction_manifest(manifest)


def test_authority_escalation_is_rejected_even_if_rehashed_is_not_available():
    manifest = build_reconstruction_manifest("reference", [], [])
    manifest["accepted"] = True

    with pytest.raises(ReconstructionError, match="cannot grant"):
        validate_reconstruction_manifest(manifest)


def test_empty_states_are_valid_and_bounded():
    manifest = build_reconstruction_manifest("nothing required", [], [])

    assert manifest["status"] == "RECONSTRUCTED"
    assert manifest["prior_count"] == 0
    assert manifest["current_count"] == 0
    assert validate_reconstruction_manifest(manifest) is True
