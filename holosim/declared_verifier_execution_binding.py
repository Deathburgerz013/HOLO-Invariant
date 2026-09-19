"""Bind declared-verifier/check provenance to an execution receipt and result.

This relation records provenance linkage only. It does not establish truth,
acceptance, execution authority, or write authority.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash


_SHA256 = re.compile(r"[0-9a-f]{64}")


class DeclaredVerifierExecutionBindingError(ValueError):
    """Raised when execution provenance cannot form one verified binding."""


def _verify_binding_hash(
    artifact: Mapping[str, Any],
    *,
    label: str,
) -> str:
    if not isinstance(artifact, Mapping):
        raise DeclaredVerifierExecutionBindingError(
            f"{label} must be a mapping"
        )

    supplied_hash = artifact.get("binding_hash")
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise DeclaredVerifierExecutionBindingError(
            f"{label} requires binding_hash"
        )

    payload = {
        key: value
        for key, value in artifact.items()
        if key != "binding_hash"
    }

    try:
        expected_hash = stable_hash(payload)
    except CanonicalValueError as exc:
        raise DeclaredVerifierExecutionBindingError(str(exc)) from exc

    if supplied_hash != expected_hash:
        raise DeclaredVerifierExecutionBindingError(
            f"{label} binding hash mismatch"
        )

    return supplied_hash


def bind_declared_verifier_execution(
    *,
    verifier_check_binding: Mapping[str, Any],
    execution_receipt_hash: str,
    result_binding: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one declared verifier/check to execution evidence and its result."""

    verifier_check_binding_hash = _verify_binding_hash(
        verifier_check_binding,
        label="verifier check binding",
    )
    result_binding_hash = _verify_binding_hash(
        result_binding,
        label="result binding",
    )

    if (
        not isinstance(execution_receipt_hash, str)
        or _SHA256.fullmatch(execution_receipt_hash) is None
    ):
        raise DeclaredVerifierExecutionBindingError(
            "execution_receipt_hash must be a SHA-256 hex digest"
        )

    if verifier_check_binding.get("check_id") != result_binding.get("check_id"):
        raise DeclaredVerifierExecutionBindingError("check_id mismatch")

    if (
        verifier_check_binding.get("check_identity_hash")
        != result_binding.get("check_identity_hash")
    ):
        raise DeclaredVerifierExecutionBindingError(
            "check_identity_hash mismatch"
        )

    verifier_id = verifier_check_binding.get("verifier_id")
    if not isinstance(verifier_id, str) or not verifier_id:
        raise DeclaredVerifierExecutionBindingError(
            "verifier check binding requires verifier_id"
        )

    payload = {
        "type": "declared_verifier_execution_binding",
        "version": 1,
        "verifier_check_binding_hash": verifier_check_binding_hash,
        "verifier_id": verifier_id,
        "check_id": verifier_check_binding["check_id"],
        "check_identity_hash": verifier_check_binding["check_identity_hash"],
        "execution_receipt_hash": execution_receipt_hash,
        "result_binding_hash": result_binding_hash,
        "truth_claimed": False,
        "accepted": False,
        "execution_authority": "NONE",
        "write_authority": "NONE",
    }

    try:
        binding_hash = stable_hash(payload)
    except CanonicalValueError as exc:
        raise DeclaredVerifierExecutionBindingError(str(exc)) from exc

    return {**payload, "binding_hash": binding_hash}