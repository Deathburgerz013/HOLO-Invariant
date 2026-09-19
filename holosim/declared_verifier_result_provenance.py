"""Bind verified declared-verifier/check provenance to an exact result binding.

This relation does not establish execution, truth, acceptance, or write authority.
"""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash


class DeclaredVerifierResultProvenanceError(ValueError):
    """Raised when supplied provenance cannot form one verified chain."""


def _verify_binding_hash(
    artifact: Mapping[str, Any],
    *,
    label: str,
) -> str:
    if not isinstance(artifact, Mapping):
        raise DeclaredVerifierResultProvenanceError(
            f"{label} must be a mapping"
        )

    supplied_hash = artifact.get("binding_hash")
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise DeclaredVerifierResultProvenanceError(
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
        raise DeclaredVerifierResultProvenanceError(str(exc)) from exc

    if supplied_hash != expected_hash:
        raise DeclaredVerifierResultProvenanceError(
            f"{label} binding hash mismatch"
        )

    return supplied_hash


def bind_declared_verifier_result_provenance(
    *,
    verifier_check_binding: Mapping[str, Any],
    result_binding: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind two verified artifacts only when they name the same exact check."""

    verifier_check_binding_hash = _verify_binding_hash(
        verifier_check_binding,
        label="verifier check binding",
    )
    result_binding_hash = _verify_binding_hash(
        result_binding,
        label="result binding",
    )

    if verifier_check_binding.get("check_id") != result_binding.get("check_id"):
        raise DeclaredVerifierResultProvenanceError("check_id mismatch")

    if (
        verifier_check_binding.get("check_identity_hash")
        != result_binding.get("check_identity_hash")
    ):
        raise DeclaredVerifierResultProvenanceError(
            "check_identity_hash mismatch"
        )

    payload = {
        "type": "declared_verifier_result_provenance",
        "version": 1,
        "verifier_check_binding_hash": verifier_check_binding_hash,
        "result_binding_hash": result_binding_hash,
        "check_id": verifier_check_binding["check_id"],
        "check_identity_hash": verifier_check_binding["check_identity_hash"],
        "execution_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }

    try:
        provenance_hash = stable_hash(payload)
    except CanonicalValueError as exc:
        raise DeclaredVerifierResultProvenanceError(str(exc)) from exc

    return {**payload, "provenance_hash": provenance_hash}