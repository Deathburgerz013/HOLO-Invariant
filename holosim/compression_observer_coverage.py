"""Read-only coverage check for compression observer requirements."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any


RECEIPT_TYPE = "compression_observer_coverage"
RECEIPT_VERSION = 1


class CompressionObserverCoverageError(ValueError):
    """Raised when compression observer coverage inputs are malformed."""


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise CompressionObserverCoverageError(
            f"{label} must be a nonempty plain string"
        )
    return value


def _names(values: Any, label: str) -> list[str]:
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes, bytearray))
        or not values
    ):
        raise CompressionObserverCoverageError(
            f"{label} must be a nonempty sequence"
        )

    result: list[str] = []
    seen: set[str] = set()

    for index, value in enumerate(values):
        name = _text(value, f"{label}[{index}]")
        if name in seen:
            raise CompressionObserverCoverageError(
                f"duplicate {label} value: {name}"
            )
        seen.add(name)
        result.append(name)

    return sorted(result)


def _observer_identities(
    values: Any,
    declared_observers: Sequence[str],
) -> dict[str, str]:
    if not isinstance(values, Mapping):
        raise CompressionObserverCoverageError(
            "observer_identities must be a mapping"
        )

    declared = set(declared_observers)

    if set(values) != declared:
        raise CompressionObserverCoverageError(
            "observer_identities must exactly match declared_observers"
        )

    result: dict[str, str] = {}

    for observer_id in sorted(values):
        identity = values[observer_id]

        if type(identity) is not str or len(identity) != 64:
            raise CompressionObserverCoverageError(
                f"observer_identities[{observer_id}] must be a sha256 identity"
            )

        try:
            int(identity, 16)
        except ValueError as exc:
            raise CompressionObserverCoverageError(
                f"observer_identities[{observer_id}] must be a sha256 identity"
            ) from exc

        result[observer_id] = identity.lower()

    return result


def _hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate_compression_observer_coverage(
    *,
    required_observations: Sequence[str],
    declared_observers: Sequence[str],
    observer_identities: Mapping[str, str],
    requirement_basis_ref: str,
) -> dict[str, Any]:
    """Check whether declared compression observers cover every requirement.

    Coverage establishes only that every declared verification requirement has
    a corresponding declared observer and that each declared observer is bound
    to a supplied implementation identity.

    It does not establish that those identities correspond to the runtime
    callables actually executed, that observations are correct, that
    compression preserves them, or that compression is authorized.
    """

    required = _names(required_observations, "required_observations")
    declared = _names(declared_observers, "declared_observers")
    identities = _observer_identities(observer_identities, declared)
    basis = _text(requirement_basis_ref, "requirement_basis_ref")

    required_set = set(required)
    declared_set = set(declared)

    covered = sorted(required_set & declared_set)
    missing = sorted(required_set - declared_set)
    extra = sorted(declared_set - required_set)

    status = "COVERAGE_COMPLETE" if not missing else "COVERAGE_INCOMPLETE"

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "requirement_basis_ref": basis,
        "required_observations": deepcopy(required),
        "declared_observers": deepcopy(declared),
        "observer_identities": deepcopy(identities),
        "covered_observations": covered,
        "missing_observations": missing,
        "extra_observers": extra,
        "status": status,
        "coverage_complete": not missing,
        "observation_truth_verified": False,
        "compression_preservation_verified": False,
        "compression_authorized": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }

    return {**body, "receipt_id": _hash(body)}


def verify_compression_observer_coverage_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Replay a coverage receipt without granting compression authority."""

    violations: list[str] = []
    expected_id: str | None = None
    actual_id = (
        receipt.get("receipt_id")
        if isinstance(receipt, Mapping)
        else None
    )

    try:
        if not isinstance(receipt, Mapping):
            raise CompressionObserverCoverageError(
                "receipt must be a mapping"
            )

        expected = evaluate_compression_observer_coverage(
            required_observations=receipt.get("required_observations"),
            declared_observers=receipt.get("declared_observers"),
            observer_identities=receipt.get("observer_identities"),
            requirement_basis_ref=receipt.get("requirement_basis_ref"),
        )
        expected_id = expected["receipt_id"]

        if set(receipt) != set(expected):
            violations.append("receipt fields do not match replay")

        for field, value in expected.items():
            if field in receipt and receipt[field] != value:
                violations.append(f"{field} does not match replay")

    except (
        CompressionObserverCoverageError,
        TypeError,
        ValueError,
    ) as exc:
        violations.append(str(exc))

    return {
        "valid": not violations,
        "receipt_id": actual_id,
        "expected_receipt_id": expected_id,
        "violations": violations,
        "accepted": False,
        "write_authority": "NONE",
    }