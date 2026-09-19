"""Bind one declared verifier artifact to one exact check identity.

This relation does not claim execution, truth, acceptance, or write authority.
"""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash


class DeclaredVerifierCheckIdentityBindingError(ValueError):
    """Raised when supplied binding provenance is invalid."""


def _verify_hash(
    artifact: Mapping[str, Any],
    *,
    hash_field: str,
    label: str,
) -> str:
    supplied_hash = artifact.get(hash_field)
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise DeclaredVerifierCheckIdentityBindingError(
            f"{label} requires {hash_field}"
        )

    payload = {
        key: value
        for key, value in artifact.items()
        if key != hash_field
    }

    try:
        expected_hash = stable_hash(payload)
    except CanonicalValueError as exc:
        raise DeclaredVerifierCheckIdentityBindingError(str(exc)) from exc

    if supplied_hash != expected_hash:
        raise DeclaredVerifierCheckIdentityBindingError(
            f"{label} hash mismatch"
        )

    return supplied_hash


def bind_declared_verifier_check_identity(
    *,
    declared_verifier_binding: Mapping[str, Any],
    check_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind verified declared-verifier provenance to one verified check identity."""

    if not isinstance(declared_verifier_binding, Mapping):
        raise DeclaredVerifierCheckIdentityBindingError(
            "declared_verifier_binding must be a mapping"
        )
    if not isinstance(check_identity, Mapping):
        raise DeclaredVerifierCheckIdentityBindingError(
            "check_identity must be a mapping"
        )

    declared_binding_hash = _verify_hash(
        declared_verifier_binding,
        hash_field="binding_hash",
        label="declared verifier binding",
    )
    check_identity_hash = _verify_hash(
        check_identity,
        hash_field="check_identity_hash",
        label="check identity",
    )

    verifier_id = declared_verifier_binding.get("verifier_id")
    check_type = check_identity.get("check_type")
    if verifier_id != check_type:
        raise DeclaredVerifierCheckIdentityBindingError(
            "declared verifier_id must match check identity check_type"
        )

    payload = {
        "type": "declared_verifier_check_identity_binding",
        "version": 1,
        "declared_verifier_binding_hash": declared_binding_hash,
        "verifier_id": declared_verifier_binding["verifier_id"],
        "check_id": check_identity["check_id"],
        "check_identity_hash": check_identity_hash,
        "execution_claimed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }

    try:
        binding_hash = stable_hash(payload)
    except CanonicalValueError as exc:
        raise DeclaredVerifierCheckIdentityBindingError(str(exc)) from exc

    return {**payload, "binding_hash": binding_hash}
