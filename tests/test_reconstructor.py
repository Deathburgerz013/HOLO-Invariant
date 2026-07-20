import copy

import pytest

from holosim.reconstructor import (
    ReconstructionError,
    build_reconstruction_manifest,
    build_reconstruction_path,
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


def test_reconstruction_path_follows_direct_dependency():
    path = build_reconstruction_path(
        "current reference",
        ["answer"],
        [
            {"id": "answer", "requires": ["evidence"]},
            {"id": "evidence", "requires": []},
        ],
    )

    assert path["status"] == "COMPLETE"
    assert path["reachable_ids"] == ["answer", "evidence"]
    assert path["missing_ids"] == []


def test_reconstruction_path_follows_multi_hop_dependencies():
    path = build_reconstruction_path(
        "current reference",
        ["a"],
        [
            {"id": "a", "requires": ["b"]},
            {"id": "b", "requires": ["c"]},
            {"id": "c", "requires": []},
        ],
    )

    assert path["reachable_ids"] == ["a", "b", "c"]
    assert path["dependency_edges"] == [
        {"from": "a", "to": "b"},
        {"from": "b", "to": "c"},
    ]


def test_reconstruction_path_excludes_unrelated_branch():
    path = build_reconstruction_path(
        "current reference",
        ["needed"],
        [
            {"id": "needed", "requires": ["base"]},
            {"id": "base", "requires": []},
            {"id": "unrelated", "requires": ["other"]},
            {"id": "other", "requires": []},
        ],
    )

    assert path["reachable_ids"] == ["base", "needed"]
    assert path["excluded_ids"] == ["other", "unrelated"]


def test_reconstruction_path_exposes_missing_dependency():
    path = build_reconstruction_path(
        "current reference",
        ["needed"],
        [{"id": "needed", "requires": ["missing"]}],
    )

    assert path["status"] == "INCOMPLETE"
    assert path["reachable_ids"] == ["needed"]
    assert path["missing_ids"] == ["missing"]


def test_reconstruction_path_cycle_terminates_and_reports_edge():
    path = build_reconstruction_path(
        "current reference",
        ["a"],
        [
            {"id": "a", "requires": ["b"]},
            {"id": "b", "requires": ["a"]},
        ],
    )

    assert path["status"] == "COMPLETE"
    assert path["reachable_ids"] == ["a", "b"]
    assert path["cycle_edges"] == [{"from": "b", "to": "a"}]


def test_reconstruction_path_does_not_guess_semantic_links():
    path = build_reconstruction_path(
        "teacher learner relation",
        ["teacher"],
        [
            {"id": "teacher", "requires": []},
            {"id": "learner", "requires": []},
        ],
    )

    assert path["reachable_ids"] == ["teacher"]
    assert path["excluded_ids"] == ["learner"]


def test_reconstruction_path_rejects_duplicate_targets():
    with pytest.raises(ReconstructionError, match="unique"):
        build_reconstruction_path(
            "reference",
            ["a", "a"],
            [{"id": "a", "requires": []}],
        )
