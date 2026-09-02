"""Closed, target-bound declarations of operational authorization.

This record separates permission to perform one effect from evidence that a
claim is correct.  It is deliberately not proof of the issuer's identity; an
adapter that creates one is responsible for obtaining the external approval.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .canonical import stable_hash


AUTHORIZATION_TYPE = "holo_operational_authorization"
VERSION = 1
ACTION_SERVICE_APPEND = "SERVICE_APPEND"
SHA256 = re.compile(r"[0-9a-f]{64}")

AUTHORIZATION_FIELDS = {
    "type", "version", "authorization_id", "authority_type", "actor_id",
    "action", "target_sha256", "approval_reference", "decision",
    "write_authority", "execution_authority", "promotion_authority",
    "trust_root_authority", "truth_claimed", "interpretation_notice",
    "authorization_hash",
}


class OperationalAuthorizationError(ValueError):
    """An authorization violates the closed operational contract."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise OperationalAuthorizationError(f"{field} must be nonempty text")
    return value.strip()


def _digest(value: Any, field: str) -> str:
    value = _text(value, field)
    if SHA256.fullmatch(value) is None:
        raise OperationalAuthorizationError(f"{field} must be lowercase SHA-256")
    return value


def build_operational_authorization(
    *,
    authorization_id: str,
    actor_id: str,
    action: str,
    target_sha256: str,
    approval_reference: str,
) -> dict[str, Any]:
    """Declare external-human permission for one action on one exact target."""
    reference = _text(approval_reference, "approval_reference")
    if SHA256.fullmatch(reference) is not None:
        raise OperationalAuthorizationError(
            "approval_reference cannot be a bare proof or artifact digest"
        )
    if action != ACTION_SERVICE_APPEND:
        raise OperationalAuthorizationError("action is not supported")
    body = {
        "type": AUTHORIZATION_TYPE,
        "version": VERSION,
        "authorization_id": _text(authorization_id, "authorization_id"),
        "authority_type": "EXTERNAL_HUMAN",
        "actor_id": _text(actor_id, "actor_id"),
        "action": action,
        "target_sha256": _digest(target_sha256, "target_sha256"),
        "approval_reference": reference,
        "decision": "AUTHORIZED",
        "write_authority": "EXACT_TARGET_ONLY",
        "execution_authority": "NONE",
        "promotion_authority": "NONE",
        "trust_root_authority": "NONE",
        "truth_claimed": False,
        "interpretation_notice": (
            "This record declares permission for one exact operational target. "
            "It does not prove truth or the issuer's identity."
        ),
    }
    return {**body, "authorization_hash": stable_hash(body)}


def validate_operational_authorization(
    authorization: Mapping[str, Any],
    *,
    expected_action: str,
    expected_target_sha256: str,
) -> bool:
    """Require exact schema, identity, action, target, and effect boundaries."""
    if type(authorization) is not dict or set(authorization) != AUTHORIZATION_FIELDS:
        raise OperationalAuthorizationError(
            "authorization fields do not match the versioned schema"
        )
    if authorization.get("type") != AUTHORIZATION_TYPE or authorization.get("version") != VERSION:
        raise OperationalAuthorizationError("authorization type or version is invalid")
    try:
        rebuilt = build_operational_authorization(
            authorization_id=authorization["authorization_id"],
            actor_id=authorization["actor_id"],
            action=authorization["action"],
            target_sha256=authorization["target_sha256"],
            approval_reference=authorization["approval_reference"],
        )
    except (KeyError, TypeError) as exc:
        raise OperationalAuthorizationError("authorization is malformed") from exc
    if rebuilt != authorization:
        raise OperationalAuthorizationError("authorization identity is invalid")
    if authorization["action"] != expected_action:
        raise OperationalAuthorizationError("authorization action does not match")
    if authorization["target_sha256"] != _digest(
        expected_target_sha256, "expected_target_sha256"
    ):
        raise OperationalAuthorizationError("authorization target does not match")
    return True
