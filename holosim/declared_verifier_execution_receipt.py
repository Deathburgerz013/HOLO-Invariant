"""Execute one explicitly declared verifier and bind its actual result.

This module records execution provenance only. It does not establish truth,
acceptance, or write authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from holosim.canonical import CanonicalValueError, stable_hash


class DeclaredVerifierExecutionReceiptError(ValueError):
    """Raised when declared verifier execution cannot be bound safely."""


def _verify_hash(
    artifact: Mapping[str, Any],
    *,
    hash_field: str,
    label: str,
) -> str:
    if not isinstance(artifact, Mapping):
        raise DeclaredVerifierExecutionReceiptError(
            f"{label} must be a mapping"
        )

    supplied_hash = artifact.get(hash_field)
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise DeclaredVerifierExecutionReceiptError(
            f"{label} requires {hash_field}"
        )

    body = {
        key: value
        for key, value in artifact.items()
        if key != hash_field
    }

    try:
        expected_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise DeclaredVerifierExecutionReceiptError(str(exc)) from exc

    if supplied_hash != expected_hash:
        raise DeclaredVerifierExecutionReceiptError(
            f"{label} hash mismatch"
        )

    return supplied_hash


def execute_declared_verifier(
    *,
    verifier_check_binding: Mapping[str, Any],
    check_identity: Mapping[str, Any],
    available_verifiers: Mapping[str, Callable[..., Any]],
) -> dict[str, Any]:
    """Execute the explicitly declared verifier against the exact check identity."""

    verifier_check_binding_hash = _verify_hash(
        verifier_check_binding,
        hash_field="binding_hash",
        label="verifier check binding",
    )

    check_identity_hash = _verify_hash(
        check_identity,
        hash_field="check_identity_hash",
        label="check identity",
    )

    if verifier_check_binding.get("check_id") != check_identity.get("check_id"):
        raise DeclaredVerifierExecutionReceiptError("check_id mismatch")

    if (
        verifier_check_binding.get("check_identity_hash")
        != check_identity_hash
    ):
        raise DeclaredVerifierExecutionReceiptError(
            "check_identity_hash mismatch"
        )

    verifier_id = verifier_check_binding.get("verifier_id")
    if not isinstance(verifier_id, str) or not verifier_id.strip():
        raise DeclaredVerifierExecutionReceiptError(
            "verifier_id must be a non-empty string"
        )

    if not isinstance(available_verifiers, Mapping):
        raise DeclaredVerifierExecutionReceiptError(
            "available_verifiers must be a mapping"
        )

    verifier = available_verifiers.get(verifier_id)
    if verifier is None:
        raise DeclaredVerifierExecutionReceiptError(
            "declared verifier is unavailable"
        )

    if not callable(verifier):
        raise DeclaredVerifierExecutionReceiptError(
            "declared verifier must be callable"
        )

    result = verifier(deepcopy(dict(check_identity)))

    if not isinstance(result, Mapping) or not result:
        raise DeclaredVerifierExecutionReceiptError(
            "verifier must return a non-empty mapping"
        )

    normalized_result = deepcopy(dict(result))

    try:
        result_hash = stable_hash(normalized_result)
    except CanonicalValueError as exc:
        raise DeclaredVerifierExecutionReceiptError(str(exc)) from exc

    body = {
        "type": "declared_verifier_execution_receipt",
        "version": 1,
        "verifier_check_binding_hash": verifier_check_binding_hash,
        "verifier_id": verifier_id,
        "check_id": check_identity["check_id"],
        "check_identity_hash": check_identity_hash,
        "result": normalized_result,
        "result_hash": result_hash,
        "truth_claimed": False,
        "accepted": False,
        "execution_authority": "NONE",
        "write_authority": "NONE",
    }

    try:
        receipt_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise DeclaredVerifierExecutionReceiptError(str(exc)) from exc

    return {**body, "receipt_hash": receipt_hash}