from holosim.competing_head_detection import detect_competing_heads


def test_single_head_is_not_a_fork():
    result = detect_competing_heads(
        heads=[{"head_hash": "head-a", "parent_hash": "parent-1"}],
    )
    assert result["status"] == "NO_FORK"
    assert result["competing_heads"] == []
    assert result["selected_head"] is None


def test_distinct_heads_with_shared_parent_are_a_structural_fork():
    result = detect_competing_heads(
        heads=[
            {"head_hash": "head-a", "parent_hash": "parent-1"},
            {"head_hash": "head-b", "parent_hash": "parent-1"},
        ],
    )
    assert result["status"] == "CONFLICT"
    assert result["fork_parent_hashes"] == ["parent-1"]
    assert result["competing_heads"] == [["head-a", "head-b"]]
    assert result["selected_head"] is None
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_different_parents_do_not_establish_sibling_conflict():
    result = detect_competing_heads(
        heads=[
            {"head_hash": "head-a", "parent_hash": "parent-1"},
            {"head_hash": "head-b", "parent_hash": "parent-2"},
        ],
    )
    assert result["status"] == "NO_FORK"
    assert result["fork_parent_hashes"] == []
    assert result["competing_heads"] == []
    assert result["selected_head"] is None


import pytest

from holosim.competing_head_detection import CompetingHeadDetectionError


@pytest.mark.parametrize("bad", ["", " ", None, 1, True])
def test_invalid_head_identity_fails_closed(bad):
    with pytest.raises(CompetingHeadDetectionError):
        detect_competing_heads(heads=[{"head_hash": bad, "parent_hash": "parent-1"}])


@pytest.mark.parametrize("bad", ["", " ", None, 1, True])
def test_invalid_parent_identity_fails_closed(bad):
    with pytest.raises(CompetingHeadDetectionError):
        detect_competing_heads(heads=[{"head_hash": "head-a", "parent_hash": bad}])


def test_head_schema_is_closed():
    with pytest.raises(CompetingHeadDetectionError):
        detect_competing_heads(heads=[{"head_hash": "head-a", "parent_hash": "parent-1", "preferred": True}])


def test_duplicate_head_identity_fails_closed():
    with pytest.raises(CompetingHeadDetectionError):
        detect_competing_heads(heads=[{"head_hash": "head-a", "parent_hash": "parent-1"}, {"head_hash": "head-a", "parent_hash": "parent-1"}])


def test_multiple_independent_forks_are_preserved():
    result = detect_competing_heads(heads=[{"head_hash": "b", "parent_hash": "p1"}, {"head_hash": "a", "parent_hash": "p1"}, {"head_hash": "d", "parent_hash": "p2"}, {"head_hash": "c", "parent_hash": "p2"}])
    assert result["status"] == "CONFLICT"
    assert result["fork_parent_hashes"] == ["p1", "p2"]
    assert result["competing_heads"] == [["a", "b"], ["c", "d"]]
    assert result["selected_head"] is None


def test_receipt_is_deterministic():
    heads = [{"head_hash": "head-b", "parent_hash": "parent-1"}, {"head_hash": "head-a", "parent_hash": "parent-1"}]
    assert detect_competing_heads(heads=heads) == detect_competing_heads(heads=heads)


def test_inputs_are_not_mutated():
    heads = [{"head_hash": "head-a", "parent_hash": "parent-1"}, {"head_hash": "head-b", "parent_hash": "parent-1"}]
    before = [dict(head) for head in heads]
    detect_competing_heads(heads=heads)
    assert heads == before
