from holosim.frame_relative_navigator import relate_frames


def _frame(frame_id: str, order: int) -> dict:
    return {
        "frame_id": frame_id,
        "order": order,
    }


def _projection(state: str) -> dict:
    return {
        "state": state,
    }


def test_distinct_frames_can_return_same_projection_without_identity_collapse():
    relation = relate_frames(
        earlier_frame=_frame("frame:F0", 0),
        later_frame=_frame("frame:F2", 2),
        earlier_projection=_projection("A"),
        later_projection=_projection("A"),
    )

    assert relation["same_frame"] is False
    assert relation["same_projection"] is True
    assert relation["relation"] == "DIFFERENT_FRAME_SAME_PROJECTION"


def test_same_frame_same_projection_is_preserved():
    relation = relate_frames(
        earlier_frame=_frame("frame:F0", 0),
        later_frame=_frame("frame:F0", 0),
        earlier_projection=_projection("A"),
        later_projection=_projection("A"),
    )

    assert relation["same_frame"] is True
    assert relation["same_projection"] is True
    assert relation["relation"] == "SAME_FRAME_SAME_PROJECTION"


def test_same_frame_can_expose_changed_projection():
    relation = relate_frames(
        earlier_frame=_frame("frame:F0", 0),
        later_frame=_frame("frame:F0", 0),
        earlier_projection=_projection("A"),
        later_projection=_projection("B"),
    )

    assert relation["same_frame"] is True
    assert relation["same_projection"] is False
    assert relation["relation"] == "SAME_FRAME_CHANGED_PROJECTION"


def test_distinct_frames_can_expose_changed_projection():
    relation = relate_frames(
        earlier_frame=_frame("frame:F0", 0),
        later_frame=_frame("frame:F1", 1),
        earlier_projection=_projection("A"),
        later_projection=_projection("B"),
    )

    assert relation["same_frame"] is False
    assert relation["same_projection"] is False
    assert relation["relation"] == "DIFFERENT_FRAME_CHANGED_PROJECTION"
def test_navigation_relation_is_repeat_deterministic():
    kwargs = {
        "earlier_frame": _frame("frame:F0", 0),
        "later_frame": _frame("frame:F2", 2),
        "earlier_projection": _projection("A"),
        "later_projection": _projection("A"),
    }

    first = relate_frames(**kwargs)
    second = relate_frames(**kwargs)

    assert first == second
    assert first["navigation_hash"] == second["navigation_hash"]