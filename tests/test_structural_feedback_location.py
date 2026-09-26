import pytest

from holosim.structural_feedback_location import (
    StructuralFeedbackLocationError,
    classify_feedback_location,
)


def test_same_story_feedback_is_classified_without_inference():
    receipt = classify_feedback_location(
        source={"story_id": "story-1", "space_id": "room-a"},
        target={"story_id": "story-1", "space_id": "room-b"},
    )
    assert receipt["relationship"] == "SAME_STORY"
    assert receipt["crosses_story_boundary"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"


def test_cross_story_feedback_is_explicitly_distinguished():
    receipt = classify_feedback_location(
        source={"story_id": "story-1", "space_id": "room-a"},
        target={"story_id": "story-2", "space_id": "room-c"},
    )
    assert receipt["relationship"] == "CROSS_STORY"
    assert receipt["crosses_story_boundary"] is True


def test_story_identity_does_not_imply_order_or_rank():
    forward = classify_feedback_location(
        source={"story_id": "alpha", "space_id": "a"},
        target={"story_id": "omega", "space_id": "b"},
    )
    reverse = classify_feedback_location(
        source={"story_id": "omega", "space_id": "b"},
        target={"story_id": "alpha", "space_id": "a"},
    )
    assert forward["relationship"] == reverse["relationship"] == "CROSS_STORY"
    assert "higher_story" not in forward
    assert "lower_story" not in forward


@pytest.mark.parametrize("bad", ["", " ", None, 1, True])
def test_invalid_story_identity_fails_closed(bad):
    with pytest.raises(StructuralFeedbackLocationError):
        classify_feedback_location(
            source={"story_id": bad, "space_id": "room-a"},
            target={"story_id": "story-2", "space_id": "room-b"},
        )


def test_location_schema_is_closed():
    with pytest.raises(StructuralFeedbackLocationError):
        classify_feedback_location(
            source={"story_id": "story-1", "space_id": "a", "meaning": "narrative"},
            target={"story_id": "story-1", "space_id": "b"},
        )


@pytest.mark.parametrize("bad", ["", " ", None, 1, True])
def test_invalid_space_identity_fails_closed(bad):
    with pytest.raises(StructuralFeedbackLocationError):
        classify_feedback_location(
            source={"story_id": "story-1", "space_id": bad},
            target={"story_id": "story-1", "space_id": "room-b"},
        )


def test_target_location_schema_is_closed():
    with pytest.raises(StructuralFeedbackLocationError):
        classify_feedback_location(
            source={"story_id": "story-1", "space_id": "a"},
            target={"story_id": "story-1", "space_id": "b", "rank": 2},
        )


def test_receipt_is_deterministic():
    kwargs = {
        "source": {"story_id": "story-1", "space_id": "a"},
        "target": {"story_id": "story-2", "space_id": "b"},
    }
    first = classify_feedback_location(**kwargs)
    second = classify_feedback_location(**kwargs)
    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]


def test_inputs_are_not_mutated():
    source = {"story_id": "story-1", "space_id": "a"}
    target = {"story_id": "story-2", "space_id": "b"}
    source_before = dict(source)
    target_before = dict(target)
    classify_feedback_location(source=source, target=target)
    assert source == source_before
    assert target == target_before
