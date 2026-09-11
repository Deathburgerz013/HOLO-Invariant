"""Deterministic frame-relative navigation for bounded observations.

This module compares explicit frame identities and explicit observable
projections. It does not infer physical location, semantic equivalence,
truth, acceptance, authority, or historical identity from matching
projection content.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from holosim.canonical import stable_hash


RELATION_TYPE = "frame_relative_navigation"
RELATION_VERSION = 1


class FrameRelativeNavigationError(ValueError):
    """Raised when frame-relative navigation inputs are malformed."""


def _require_mapping(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FrameRelativeNavigationError(f"{name} must be a dict")
    return deepcopy(value)


def _require_string(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FrameRelativeNavigationError(
            f"{name} must be a non-empty string"
        )
    return value


def relate_frames(
    *,
    earlier_frame: dict[str, Any],
    later_frame: dict[str, Any],
    earlier_projection: dict[str, Any],
    later_projection: dict[str, Any],
) -> dict[str, Any]:
    """Relate two declared frames and their exact bounded projections."""

    earlier = _require_mapping(earlier_frame, name="earlier_frame")
    later = _require_mapping(later_frame, name="later_frame")
    earlier_view = _require_mapping(
        earlier_projection,
        name="earlier_projection",
    )
    later_view = _require_mapping(
        later_projection,
        name="later_projection",
    )

    earlier_frame_id = _require_string(
        earlier.get("frame_id"),
        name="earlier_frame.frame_id",
    )
    later_frame_id = _require_string(
        later.get("frame_id"),
        name="later_frame.frame_id",
    )

    same_frame = earlier_frame_id == later_frame_id

    earlier_projection_hash = stable_hash(earlier_view)
    later_projection_hash = stable_hash(later_view)
    same_projection = earlier_projection_hash == later_projection_hash

    if same_frame and same_projection:
        relation = "SAME_FRAME_SAME_PROJECTION"
    elif same_frame:
        relation = "SAME_FRAME_CHANGED_PROJECTION"
    elif same_projection:
        relation = "DIFFERENT_FRAME_SAME_PROJECTION"
    else:
        relation = "DIFFERENT_FRAME_CHANGED_PROJECTION"

    body = {
        "type": RELATION_TYPE,
        "version": RELATION_VERSION,
        "earlier_frame": earlier,
        "later_frame": later,
        "earlier_frame_hash": stable_hash(earlier),
        "later_frame_hash": stable_hash(later),
        "earlier_projection": earlier_view,
        "later_projection": later_view,
        "earlier_projection_hash": earlier_projection_hash,
        "later_projection_hash": later_projection_hash,
        "same_frame": same_frame,
        "same_projection": same_projection,
        "relation": relation,
        "truth_claimed": False,
        "accepted": False,
        "state_change_authorized": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Matching projection hashes establish exact canonical projection "
            "equality only. They do not establish identical historical state, "
            "physical location, semantic equivalence, truth, or authority."
        ),
    }

    return {
        **body,
        "navigation_hash": stable_hash(body),
    }