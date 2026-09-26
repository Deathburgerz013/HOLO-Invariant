"""Bind declared compression observers to the runtime callables supplied."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Callable

from holosim.bounded_python_callable_identity import (
    BoundedPythonCallableIdentityError,
    derive_python_callable_identity,
)
from holosim.compression_observer_coverage import (
    verify_compression_observer_coverage_receipt,
)


RECEIPT_TYPE = "compression_observer_runtime_binding"
RECEIPT_VERSION = 1


class CompressionObserverRuntimeBindingError(ValueError):
    """Raised when observer runtime binding inputs are malformed."""


def _hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bind_compression_observer_runtime(
    *,
    coverage_receipt: Mapping[str, Any],
    observers: Mapping[str, Callable[..., Any]],
) -> dict[str, Any]:
    """Bind a verified coverage receipt to the actual supplied observers.

    This establishes only whether the observer IDs and implementation
    identities committed to by the coverage receipt match the runtime
    callables supplied here.

    It does not execute observers, establish observation truth, establish
    compression preservation, authorize compression, or grant authority.
    """

    if not isinstance(coverage_receipt, Mapping):
        raise CompressionObserverRuntimeBindingError(
            "coverage_receipt must be a mapping"
        )

    coverage_check = verify_compression_observer_coverage_receipt(
        coverage_receipt
    )
    if not coverage_check["valid"]:
        raise CompressionObserverRuntimeBindingError(
            "coverage_receipt must verify before runtime binding"
        )

    if not isinstance(observers, Mapping) or not observers:
        raise CompressionObserverRuntimeBindingError(
            "observers must be a nonempty mapping"
        )

    declared_observers = coverage_receipt["declared_observers"]
    declared_identities = coverage_receipt["observer_identities"]

    actual_names = set(observers)
    declared_names = set(declared_observers)

    if actual_names != declared_names:
        raise CompressionObserverRuntimeBindingError(
            "runtime observer ids must exactly match declared_observers"
        )

    runtime_identities: dict[str, str] = {}
    mismatched_observers: list[str] = []

    for observer_id in sorted(declared_names):
        observer = observers[observer_id]

        try:
            identity = derive_python_callable_identity(observer)
        except BoundedPythonCallableIdentityError as exc:
            raise CompressionObserverRuntimeBindingError(
                f"runtime observer {observer_id} has unsupported identity: {exc}"
            ) from exc

        runtime_identity = identity["callable_identity"]
        runtime_identities[observer_id] = runtime_identity

        if runtime_identity != declared_identities[observer_id]:
            mismatched_observers.append(observer_id)

    binding_complete = not mismatched_observers
    status = "BOUND" if binding_complete else "IDENTITY_MISMATCH"

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "coverage_receipt_id": coverage_receipt["receipt_id"],
        "requirement_basis_ref": coverage_receipt[
            "requirement_basis_ref"
        ],
        "declared_observers": list(declared_observers),
        "declared_observer_identities": dict(declared_identities),
        "runtime_observer_identities": runtime_identities,
        "mismatched_observers": mismatched_observers,
        "binding_complete": binding_complete,
        "status": status,
        "observers_executed": False,
        "observation_truth_verified": False,
        "compression_preservation_verified": False,
        "compression_authorized": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {**body, "receipt_id": _hash(body)}