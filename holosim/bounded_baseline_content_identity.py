"""Bind baseline content to a declared state identity under one exact function."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Callable

from holosim.bounded_python_callable_identity import (
    BoundedPythonCallableIdentityError,
    derive_python_callable_identity,
    verify_python_callable_identity,
)


RECEIPT_TYPE = "bounded_baseline_content_identity"
RECEIPT_VERSION = 1

BOUND = "BOUND"
IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
IDENTITY_FUNCTION_ERROR = "IDENTITY_FUNCTION_ERROR"


class BoundedBaselineContentIdentityError(ValueError):
    """Raised when baseline-content identity inputs are malformed."""


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise BoundedBaselineContentIdentityError(
            f"{label} must be a nonempty plain string"
        )
    return value


def _canonical(value: Any, label: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise BoundedBaselineContentIdentityError(
            f"{label} must contain only canonical JSON values"
        ) from exc


def _hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bind_baseline_content_identity(
    *,
    baseline: Any,
    baseline_id: str,
    declared_state_identity: str,
    identity_function: Callable[[Any], Any],
) -> dict[str, Any]:
    """Bind baseline content to one declared identity under one exact function.

    The identity function is itself identity-bound before execution.

    This establishes only that the supplied baseline produced the declared
    state identity under the exact Python function identified by this receipt.
    It does not establish that the baseline is true, current, persistent,
    authorized, complete, or suitable for compression.
    """

    checked_baseline_id = _text(baseline_id, "baseline_id")
    checked_declared_identity = _text(
        declared_state_identity,
        "declared_state_identity",
    )
    checked_baseline = _canonical(baseline, "baseline")

    try:
        function_identity = derive_python_callable_identity(
            identity_function
        )
    except BoundedPythonCallableIdentityError as exc:
        raise BoundedBaselineContentIdentityError(
            f"identity_function has unsupported identity: {exc}"
        ) from exc

    try:
        observed = identity_function(deepcopy(checked_baseline))
    except Exception:
        observed = None
        status = IDENTITY_FUNCTION_ERROR
        binding_complete = False
    else:
        if type(observed) is not str or not observed.strip():
            observed = None
            status = IDENTITY_FUNCTION_ERROR
            binding_complete = False
        elif observed == checked_declared_identity:
            status = BOUND
            binding_complete = True
        else:
            status = IDENTITY_MISMATCH
            binding_complete = False

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "baseline_id": checked_baseline_id,
        "baseline": checked_baseline,
        "declared_state_identity": checked_declared_identity,
        "observed_state_identity": observed,
        "identity_function_identity": function_identity,
        "status": status,
        "binding_complete": binding_complete,
        "baseline_truth_verified": False,
        "baseline_current_verified": False,
        "persistence_verified": False,
        "compression_preservation_verified": False,
        "compression_authorized": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {**body, "receipt_id": _hash(body)}


def verify_baseline_content_identity_receipt(
    receipt: Mapping[str, Any],
    *,
    identity_function: Callable[[Any], Any],
) -> dict[str, Any]:
    """Replay a baseline-content identity receipt against the exact function."""

    violations: list[str] = []
    expected_id: str | None = None
    actual_id = (
        receipt.get("receipt_id")
        if isinstance(receipt, Mapping)
        else None
    )

    if not isinstance(receipt, Mapping):
        return {
            "valid": False,
            "receipt_id": actual_id,
            "expected_receipt_id": None,
            "violations": ["receipt must be a mapping"],
            "accepted": False,
            "write_authority": "NONE",
        }

    supplied_function_identity = receipt.get(
        "identity_function_identity"
    )

    function_check = verify_python_callable_identity(
        identity_function,
        supplied_function_identity,
    )

    if not function_check["valid"]:
        violations.append(
            "identity_function does not match receipt identity"
        )

    if not violations:
        try:
            expected = bind_baseline_content_identity(
                baseline=receipt.get("baseline"),
                baseline_id=receipt.get("baseline_id"),
                declared_state_identity=receipt.get(
                    "declared_state_identity"
                ),
                identity_function=identity_function,
            )
            expected_id = expected["receipt_id"]

            if set(receipt) != set(expected):
                violations.append(
                    "receipt fields do not match replay"
                )

            for field, value in expected.items():
                if field in receipt and receipt[field] != value:
                    violations.append(
                        f"{field} does not match replay"
                    )

        except (
            BoundedBaselineContentIdentityError,
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