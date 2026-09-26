"""Bounded classification of feedback across architectural stories.

A story is an explicitly declared structural level in the architectural sense only. Story identity does not imply narrative sequence, chronology, rank, abstraction, truth, authority, or dependency.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from holosim.canonical import stable_hash

RECEIPT_TYPE = "structural_feedback_location_receipt"
RECEIPT_VERSION = 1
SAME_STORY = "SAME_STORY"
CROSS_STORY = "CROSS_STORY"
_LOCATION_FIELDS = {"story_id", "space_id"}


class StructuralFeedbackLocationError(ValueError):
    """Raised when a declared structural feedback location is invalid."""


def _required_identity(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise StructuralFeedbackLocationError(f"{field} must be a nonempty string")
    if value != value.strip():
        raise StructuralFeedbackLocationError(f"{field} cannot contain outer whitespace")
    return value


def _validate_location(location: Mapping[str, Any], label: str) -> dict[str, str]:
    if not isinstance(location, Mapping):
        raise StructuralFeedbackLocationError(f"{label} must be a mapping")
    if set(location) != _LOCATION_FIELDS:
        raise StructuralFeedbackLocationError(f"{label} fields must be exactly story_id and space_id")
    return {
        "story_id": _required_identity(location["story_id"], f"{label}.story_id"),
        "space_id": _required_identity(location["space_id"], f"{label}.space_id"),
    }


def classify_feedback_location(*, source: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    """Classify whether declared feedback locations cross a story boundary."""
    checked_source = _validate_location(source, "source")
    checked_target = _validate_location(target, "target")
    crosses_story_boundary = checked_source["story_id"] != checked_target["story_id"]
    relationship = CROSS_STORY if crosses_story_boundary else SAME_STORY
    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "source": checked_source,
        "target": checked_target,
        "relationship": relationship,
        "crosses_story_boundary": crosses_story_boundary,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
        "interpretation_notice": "Story means architectural structural level only. This receipt compares explicit story identity and does not infer narrative, chronology, rank, abstraction, truth, dependency, causality, acceptance, write authority, or execution authority.",
    }
    return {**body, "receipt_hash": stable_hash(body)}
