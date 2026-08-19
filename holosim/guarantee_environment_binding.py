"""Bind declared software guarantees to observed environment receipts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from holosim.environment_invariant_receipts import (
    EnvironmentInvariantReceiptError,
    verify_environment_invariant_receipt,
)
from holosim.guarantee_registry import (
    GUARANTEE_REGISTRY_TYPE,
    GUARANTEE_REGISTRY_VERSION,
)


BINDING_TYPE = "holo_guarantee_environment_binding"
BINDING_VERSION = 1

VALID_STATUSES = {
    "BOUND",
    "FAILED",
    "UNKNOWN",
    "STALE",
    "MISMATCH",
}

VALID_REASONS = {
    "REGISTERED_CHECK_HELD",
    "REGISTERED_CHECK_FAILED",
    "REGISTERED_CHECK_UNKNOWN",
    "REGISTERED_CHECK_STALE",
    "GUARANTEE_ID_MISMATCH",
    "GUARANTEE_NOT_REGISTERED",
    "VALIDATOR_MISMATCH",
    "SCOPE_MISMATCH",
    "EVIDENCE_MISMATCH",
}


class GuaranteeEnvironmentBindingError(ValueError):
    """Raised when a guarantee binding is invalid."""


def _canonical_json(value: Any, *, label: str) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise GuaranteeEnvironmentBindingError(
            f"{label} must contain only JSON values"
        ) from exc


def _closed_json_copy(value: Any, *, label: str) -> Any:
    return json.loads(_canonical_json(value, label=label))


def _canonical_hash(value: Any, *, label: str) -> str:
    encoded = _canonical_json(
        value,
        label=label,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_nonempty_string(
    value: Any,
    *,
    label: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GuaranteeEnvironmentBindingError(
            f"{label} must be a non-empty string"
        )
    return value


def _verify_registry(
    registry: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(registry, Mapping):
        raise GuaranteeEnvironmentBindingError(
            "registry must be a mapping"
        )

    closed_registry = _closed_json_copy(
        dict(registry),
        label="registry",
    )

    required_fields = {
        "type",
        "version",
        "guarantees",
        "accepted",
        "write_authority",
        "registry_hash",
    }
    if set(closed_registry) != required_fields:
        raise GuaranteeEnvironmentBindingError(
            "registry fields are invalid"
        )

    supplied_hash = closed_registry.pop(
        "registry_hash"
    )
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise GuaranteeEnvironmentBindingError(
            "registry_hash must be a non-empty string"
        )

    expected_hash = _canonical_hash(
        closed_registry,
        label="registry",
    )
    if supplied_hash != expected_hash:
        raise GuaranteeEnvironmentBindingError(
            "registry hash mismatch"
        )

    if closed_registry["type"] != GUARANTEE_REGISTRY_TYPE:
        raise GuaranteeEnvironmentBindingError(
            "registry type mismatch"
        )
    if (
        closed_registry["version"]
        != GUARANTEE_REGISTRY_VERSION
    ):
        raise GuaranteeEnvironmentBindingError(
            "registry version mismatch"
        )
    if closed_registry["accepted"] is not False:
        raise GuaranteeEnvironmentBindingError(
            "registry acceptance boundary is invalid"
        )
    if closed_registry["write_authority"] != "NONE":
        raise GuaranteeEnvironmentBindingError(
            "registry write authority is invalid"
        )

    guarantees = closed_registry["guarantees"]
    if (
        isinstance(guarantees, (str, bytes))
        or not isinstance(guarantees, Sequence)
        or not guarantees
    ):
        raise GuaranteeEnvironmentBindingError(
            "registry guarantees must be a non-empty sequence"
        )

    for index, guarantee in enumerate(guarantees):
        if not isinstance(guarantee, dict):
            raise GuaranteeEnvironmentBindingError(
                f"guarantee at index {index} must be an object"
            )

    return {
        **closed_registry,
        "registry_hash": supplied_hash,
    }


def _select_guarantee(
    guarantees: Sequence[Mapping[str, Any]],
    invariant_id: str,
) -> tuple[Mapping[str, Any] | None, str | None]:
    matches = [
        guarantee
        for guarantee in guarantees
        if guarantee.get("guarantee_id") == invariant_id
    ]

    if len(matches) == 1:
        return matches[0], None

    if len(matches) > 1:
        raise GuaranteeEnvironmentBindingError(
            "registry contains duplicate guarantee_id"
        )

    if len(guarantees) == 1:
        return guarantees[0], "GUARANTEE_ID_MISMATCH"

    return None, "GUARANTEE_NOT_REGISTERED"


def _string_sequence(
    value: Any,
    *,
    label: str,
) -> list[str]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
    ):
        raise GuaranteeEnvironmentBindingError(
            f"{label} must be a sequence"
        )

    result: list[str] = []
    for index, item in enumerate(value):
        result.append(
            _require_nonempty_string(
                item,
                label=f"{label}[{index}]",
            )
        )
    return result


def _binding_result(
    *,
    guarantee: Mapping[str, Any] | None,
    receipt: Mapping[str, Any],
    mismatch_reason: str | None,
) -> tuple[str, str, str]:
    invariant_id = _require_nonempty_string(
        receipt.get("invariant_id"),
        label="receipt invariant_id",
    )

    if guarantee is None:
        return (
            "MISMATCH",
            mismatch_reason or "GUARANTEE_NOT_REGISTERED",
            invariant_id,
        )

    guarantee_id = _require_nonempty_string(
        guarantee.get("guarantee_id"),
        label="guarantee_id",
    )

    if mismatch_reason is not None:
        return "MISMATCH", mismatch_reason, guarantee_id

    if invariant_id != guarantee_id:
        return (
            "MISMATCH",
            "GUARANTEE_ID_MISMATCH",
            guarantee_id,
        )

    validator = _require_nonempty_string(
        guarantee.get("validator"),
        label="validator",
    )
    if receipt.get("check_id") != validator:
        return (
            "MISMATCH",
            "VALIDATOR_MISMATCH",
            guarantee_id,
        )

    scope = receipt.get("scope")
    if not isinstance(scope, Mapping):
        raise GuaranteeEnvironmentBindingError(
            "receipt scope must be an object"
        )
    if scope.get("target") != guarantee.get("scope"):
        return (
            "MISMATCH",
            "SCOPE_MISMATCH",
            guarantee_id,
        )

    evidence = receipt.get("evidence")
    if not isinstance(evidence, Mapping):
        raise GuaranteeEnvironmentBindingError(
            "receipt evidence must be an object"
        )

    registered_evidence = _string_sequence(
        guarantee.get("evidence"),
        label="guarantee evidence",
    )
    receipt_sources = _string_sequence(
        evidence.get("sources"),
        label="receipt evidence sources",
    )
    if receipt_sources != registered_evidence:
        return (
            "MISMATCH",
            "EVIDENCE_MISMATCH",
            guarantee_id,
        )

    receipt_status = receipt.get("status")
    status_map = {
        "HELD": (
            "BOUND",
            "REGISTERED_CHECK_HELD",
        ),
        "FAILED": (
            "FAILED",
            "REGISTERED_CHECK_FAILED",
        ),
        "UNKNOWN": (
            "UNKNOWN",
            "REGISTERED_CHECK_UNKNOWN",
        ),
        "STALE": (
            "STALE",
            "REGISTERED_CHECK_STALE",
        ),
    }

    if receipt_status not in status_map:
        raise GuaranteeEnvironmentBindingError(
            "receipt status is invalid"
        )

    status, reason = status_map[receipt_status]
    return status, reason, guarantee_id


def bind_guarantee_environment(
    *,
    registry: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one registered guarantee to one verified receipt."""
    verified_registry = _verify_registry(registry)

    if not isinstance(receipt, Mapping):
        raise GuaranteeEnvironmentBindingError(
            "receipt must be a mapping"
        )

    closed_receipt = _closed_json_copy(
        dict(receipt),
        label="receipt",
    )

    try:
        verify_environment_invariant_receipt(
            closed_receipt
        )
    except EnvironmentInvariantReceiptError as exc:
        raise GuaranteeEnvironmentBindingError(
            f"environment receipt is invalid: {exc}"
        ) from exc

    invariant_id = _require_nonempty_string(
        closed_receipt.get("invariant_id"),
        label="receipt invariant_id",
    )

    guarantee, mismatch_reason = _select_guarantee(
        verified_registry["guarantees"],
        invariant_id,
    )

    status, reason, guarantee_id = _binding_result(
        guarantee=guarantee,
        receipt=closed_receipt,
        mismatch_reason=mismatch_reason,
    )

    binding: dict[str, Any] = {
        "type": BINDING_TYPE,
        "version": BINDING_VERSION,
        "guarantee_id": guarantee_id,
        "registry_hash": verified_registry[
            "registry_hash"
        ],
        "receipt_hash": closed_receipt[
            "receipt_hash"
        ],
        "environment_fingerprint": closed_receipt.get(
            "environment_fingerprint"
        ),
        "status": status,
        "reason": reason,
        "constraint_authority": "ENVIRONMENT",
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    binding["binding_hash"] = _canonical_hash(
        binding,
        label="binding",
    )
    return binding


def verify_guarantee_environment_binding(
    binding: Mapping[str, Any],
) -> bool:
    """Verify a binding's identity and bounded declarations."""
    if not isinstance(binding, Mapping):
        raise GuaranteeEnvironmentBindingError(
            "binding must be a mapping"
        )

    closed_binding = _closed_json_copy(
        dict(binding),
        label="binding",
    )

    required_fields = {
        "type",
        "version",
        "guarantee_id",
        "registry_hash",
        "receipt_hash",
        "environment_fingerprint",
        "status",
        "reason",
        "constraint_authority",
        "accepted",
        "truth_claimed",
        "write_authority",
        "execution_authority",
        "canonical_mutation",
        "binding_hash",
    }
    if set(closed_binding) != required_fields:
        raise GuaranteeEnvironmentBindingError(
            "binding fields are invalid"
        )

    supplied_hash = closed_binding.pop(
        "binding_hash"
    )
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise GuaranteeEnvironmentBindingError(
            "binding_hash must be a non-empty string"
        )

    expected_hash = _canonical_hash(
        closed_binding,
        label="binding",
    )
    if supplied_hash != expected_hash:
        raise GuaranteeEnvironmentBindingError(
            "binding hash mismatch"
        )

    if closed_binding["type"] != BINDING_TYPE:
        raise GuaranteeEnvironmentBindingError(
            "binding type mismatch"
        )
    if closed_binding["version"] != BINDING_VERSION:
        raise GuaranteeEnvironmentBindingError(
            "binding version mismatch"
        )
    if closed_binding["status"] not in VALID_STATUSES:
        raise GuaranteeEnvironmentBindingError(
            "binding status is invalid"
        )
    if closed_binding["reason"] not in VALID_REASONS:
        raise GuaranteeEnvironmentBindingError(
            "binding reason is invalid"
        )

    _require_nonempty_string(
        closed_binding["guarantee_id"],
        label="guarantee_id",
    )
    _require_nonempty_string(
        closed_binding["registry_hash"],
        label="registry_hash",
    )
    _require_nonempty_string(
        closed_binding["receipt_hash"],
        label="receipt_hash",
    )

    bounded_fields = {
        "constraint_authority": "ENVIRONMENT",
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    for field, expected in bounded_fields.items():
        if closed_binding.get(field) != expected:
            raise GuaranteeEnvironmentBindingError(
                f"invalid bounded field {field}"
            )

    return True