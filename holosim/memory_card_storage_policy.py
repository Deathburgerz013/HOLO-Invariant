"""Validated storage policy for portable memory cards."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


DEFAULT_AUTOSAVE_INTERVAL_SECONDS = 300
DEFAULT_MAX_GENERATIONS = 3

_POLICY_FIELDS = {
    "enabled",
    "interval_seconds",
    "max_generations",
}


class MemoryCardStoragePolicyError(ValueError):
    """Raised when a memory-card storage policy is invalid."""


def _validate_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    if type(policy) is not dict:
        raise MemoryCardStoragePolicyError(
            "storage policy must be a plain dictionary"
        )

    if set(policy) != _POLICY_FIELDS:
        raise MemoryCardStoragePolicyError(
            "storage policy fields do not match the expected schema"
        )

    if type(policy["enabled"]) is not bool:
        raise MemoryCardStoragePolicyError(
            "enabled must be a boolean"
        )

    if (
        type(policy["interval_seconds"]) is not int
        or isinstance(policy["interval_seconds"], bool)
        or policy["interval_seconds"] <= 0
    ):
        raise MemoryCardStoragePolicyError(
            "interval_seconds must be a positive integer"
        )

    if (
        type(policy["max_generations"]) is not int
        or isinstance(policy["max_generations"], bool)
        or policy["max_generations"] <= 0
    ):
        raise MemoryCardStoragePolicyError(
            "max_generations must be a positive integer"
        )

    return deepcopy(policy)


def build_storage_policy(
    *,
    enabled: bool = True,
    interval_seconds: int = DEFAULT_AUTOSAVE_INTERVAL_SECONDS,
    max_generations: int = DEFAULT_MAX_GENERATIONS,
) -> dict[str, Any]:
    """Build a validated memory-card storage policy."""

    policy = {
        "enabled": enabled,
        "interval_seconds": interval_seconds,
        "max_generations": max_generations,
    }

    return _validate_policy(policy)


def verify_storage_policy(
    policy: Mapping[str, Any],
) -> bool:
    """Verify a storage policy without modifying it."""

    _validate_policy(policy)
    return True


def default_storage_policy() -> dict[str, Any]:
    """Return the default storage policy."""

    return build_storage_policy()