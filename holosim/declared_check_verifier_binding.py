"""Explicit binding between declared next checks and supplied verifier identities.

This module does not infer verifier identity from natural-language conditions,
discover verifiers, execute checks, or grant authority. A binding can exist
only when the caller explicitly declares a verifier identity and supplies a
callable under that exact identity.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from holosim.canonical import stable_hash


BINDING_TYPE = "declared_check_verifier_binding"
BINDING_VERSION = 1


class DeclaredCheckVerifierBindingError(ValueError):
    """Raised when declared-check binding input is invalid."""


def bind_declared_check_verifier(
    candidate: Mapping[str, Any],
    *,
    verifier_id: str | None,
    available_verifiers: Mapping[str, Callable[..., Any]],
) -> dict[str, Any]:
    """Bind one declared check to one explicitly identified supplied verifier."""
    if not isinstance(candidate, Mapping):
        raise TypeError("candidate must be a mapping")
    if not isinstance(available_verifiers, Mapping):
        raise TypeError("available_verifiers must be a mapping")

    source = deepcopy(dict(candidate))

    if source.get("routing_status") != "DECLARED_CHECK_AVAILABLE":
        raise DeclaredCheckVerifierBindingError(
            "candidate must have routing_status DECLARED_CHECK_AVAILABLE"
        )

    base: dict[str, Any] = {
        "type": BINDING_TYPE,
        "version": BINDING_VERSION,
        "candidate": source,
        "verifier_inferred": False,
        "execution_authorized": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }

    if not isinstance(verifier_id, str) or not verifier_id.strip():
        body = {
            **base,
            "verifier_id": None,
            "bound": False,
            "binding_status": "VERIFIER_ID_REQUIRED",
            "verifier_available": False,
        }
        return {**body, "binding_hash": stable_hash(body)}

    declared_id = verifier_id.strip()
    verifier = available_verifiers.get(declared_id)

    if verifier is None:
        body = {
            **base,
            "verifier_id": declared_id,
            "bound": False,
            "binding_status": "DECLARED_VERIFIER_UNAVAILABLE",
            "verifier_available": False,
        }
        return {**body, "binding_hash": stable_hash(body)}

    if not callable(verifier):
        raise DeclaredCheckVerifierBindingError(
            "declared verifier must be callable"
        )

    body = {
        **base,
        "verifier_id": declared_id,
        "bound": True,
        "binding_status": "DECLARED_VERIFIER_BOUND",
        "verifier_available": True,
    }
    return {**body, "binding_hash": stable_hash(body)}
