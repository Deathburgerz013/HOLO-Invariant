"""Version-bound registry for explicit software guarantees."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


GUARANTEE_REGISTRY_TYPE = "holo_guarantee_registry"
GUARANTEE_REGISTRY_VERSION = 1


class GuaranteeRegistryError(ValueError):
    """Raised when a guarantee registry cannot be built honestly."""


def _canonical_hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise GuaranteeRegistryError(
            "guarantee registry could not be canonicalized"
        ) from exc

    return hashlib.sha256(encoded).hexdigest()


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GuaranteeRegistryError(f"{field} must be a non-empty string")
    return value


def _validate_string_list(value: Any, field: str) -> list[str]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
        or not value
    ):
        raise GuaranteeRegistryError(
            f"{field} must be a non-empty sequence"
        )

    result: list[str] = []
    for index, item in enumerate(value):
        result.append(
            _require_nonempty_string(item, f"{field}[{index}]")
        )

    return result


def _validate_guarantee(
    guarantee: Mapping[str, Any],
) -> dict[str, Any]:
    required_fields = {
        "guarantee_id",
        "guarantee_type",
        "scope",
        "dependencies",
        "validator",
        "failure_condition",
        "evidence",
    }

    if set(guarantee) != required_fields:
        raise GuaranteeRegistryError("guarantee fields are invalid")

    return {
        "guarantee_id": _require_nonempty_string(
            guarantee["guarantee_id"],
            "guarantee_id",
        ),
        "guarantee_type": _require_nonempty_string(
            guarantee["guarantee_type"],
            "guarantee_type",
        ),
        "scope": _require_nonempty_string(
            guarantee["scope"],
            "scope",
        ),
        "dependencies": _validate_string_list(
            guarantee["dependencies"],
            "dependencies",
        ),
        "validator": _require_nonempty_string(
            guarantee["validator"],
            "validator",
        ),
        "failure_condition": _require_nonempty_string(
            guarantee["failure_condition"],
            "failure_condition",
        ),
        "evidence": _validate_string_list(
            guarantee["evidence"],
            "evidence",
        ),
    }


def build_guarantee_registry(
    guarantees: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic, read-only registry of bounded guarantees."""
    if (
        isinstance(guarantees, (str, bytes))
        or not isinstance(guarantees, Sequence)
        or not guarantees
    ):
        raise GuaranteeRegistryError(
            "guarantees must be a non-empty sequence"
        )

    validated_guarantees: list[dict[str, Any]] = []
    guarantee_ids: set[str] = set()

    for index, guarantee in enumerate(guarantees):
        if not isinstance(guarantee, Mapping):
            raise GuaranteeRegistryError(
                f"guarantee at index {index} must be a mapping"
            )

        validated = _validate_guarantee(guarantee)
        guarantee_id = validated["guarantee_id"]

        if guarantee_id in guarantee_ids:
            raise GuaranteeRegistryError("duplicate guarantee_id")

        guarantee_ids.add(guarantee_id)
        validated_guarantees.append(validated)

    body = {
        "type": GUARANTEE_REGISTRY_TYPE,
        "version": GUARANTEE_REGISTRY_VERSION,
        "guarantees": validated_guarantees,
        "accepted": False,
        "write_authority": "NONE",
    }

    return {
        **body,
        "registry_hash": _canonical_hash(body),
    }