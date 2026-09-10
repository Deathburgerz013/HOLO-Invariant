"""Purpose-bound composition for one bounded software production request.

This boundary validates a pre-existing justification notice against the exact
software request before invoking the existing convergence entrypoint.  It then
binds the resulting production receipt to that purpose and its declared,
machine-checkable stop condition.

It does not invent a need, authenticate external evidence, accept a result,
persist state, or grant write or execution authority.
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.justification_notice import (
    JustificationNoticeError,
    validate_justification_notice,
)
from holosim.software_convergence_entrypoint import (
    RECEIPT_TYPE as SOFTWARE_RECEIPT_TYPE,
    RECEIPT_VERSION as SOFTWARE_RECEIPT_VERSION,
    run_software_convergence_request,
)


RECEIPT_TYPE = "verified_need_to_result_receipt"
RECEIPT_VERSION = 1
SOFTWARE_TARGET_TYPE = "software_request"
RUNNABLE_STOP_CONDITION = "PROJECT_VERIFIED_RUNNABLE"

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SOFTWARE_RECEIPT_FIELDS = {
    "type", "version", "software_request", "workspace",
    "environmental_constraints", "plan_receipt_hash",
    "planned_capabilities", "generation_receipts",
    "completed_capability_ids", "blocked_capability_id",
    "final_verification", "residue_verification", "status",
    "terminal_reason", "converged", "runnable", "accepted",
    "truth_claimed", "write_authority", "receipt_hash",
}
_RECEIPT_FIELDS = {
    "type", "version", "path_id", "purpose_notice",
    "purpose_notice_hash", "software_request", "software_request_hash",
    "production_receipt", "production_receipt_hash",
    "declared_stop_condition", "status", "terminal_reason",
    "stop_reached", "persistence_performed", "truth_claimed",
    "accepted", "write_authority", "execution_authority",
    "interpretation_notice", "receipt_hash",
}


class VerifiedNeedToResultError(ValueError):
    """A purpose-bound production path is malformed or inconsistent."""


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise VerifiedNeedToResultError(f"{label} is invalid")
    return value


def _hash(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise VerifiedNeedToResultError(f"{label} must be lowercase SHA-256")
    return value


def _canonical_copy(value: Any, label: str) -> Any:
    try:
        stable_hash(value)
    except CanonicalValueError as exc:
        raise VerifiedNeedToResultError(
            f"{label} must contain strict canonical JSON values"
        ) from exc
    return deepcopy(value)


def _validated_purpose(
    purpose_notice: Mapping[str, Any],
    software_request: Any,
) -> tuple[dict[str, Any], Any, str]:
    if type(purpose_notice) is not dict:
        raise VerifiedNeedToResultError("purpose_notice must be a plain dictionary")
    try:
        validate_justification_notice(purpose_notice)
    except JustificationNoticeError as exc:
        raise VerifiedNeedToResultError(
            f"purpose_notice is invalid: {exc}"
        ) from exc

    request = _canonical_copy(software_request, "software_request")
    request_hash = stable_hash(request)
    target = purpose_notice["target"]
    if target["target_type"] != SOFTWARE_TARGET_TYPE:
        raise VerifiedNeedToResultError(
            f"purpose target_type must be {SOFTWARE_TARGET_TYPE}"
        )
    if target["target_sha256"] != request_hash:
        raise VerifiedNeedToResultError(
            "purpose target does not match the exact software request"
        )

    scope = purpose_notice["declared_scope"]
    stop_condition = scope.get("stop_condition")
    if stop_condition != RUNNABLE_STOP_CONDITION:
        raise VerifiedNeedToResultError(
            "declared stop_condition must be PROJECT_VERIFIED_RUNNABLE"
        )

    return deepcopy(purpose_notice), request, request_hash


def _validated_production_receipt(
    production_receipt: Mapping[str, Any],
    *,
    software_request: Any,
    purpose_notice_hash: str,
) -> dict[str, Any]:
    if type(production_receipt) is not dict or set(production_receipt) != _SOFTWARE_RECEIPT_FIELDS:
        raise VerifiedNeedToResultError(
            "production_receipt fields do not match the versioned schema"
        )
    if (
        production_receipt["type"] != SOFTWARE_RECEIPT_TYPE
        or production_receipt["version"] != SOFTWARE_RECEIPT_VERSION
    ):
        raise VerifiedNeedToResultError("production_receipt schema is invalid")
    if (
        production_receipt["accepted"] is not False
        or production_receipt["truth_claimed"] is not False
        or production_receipt["write_authority"] != "NONE"
    ):
        raise VerifiedNeedToResultError(
            "production_receipt grants forbidden authority"
        )
    if production_receipt["software_request"] != software_request:
        raise VerifiedNeedToResultError(
            "production_receipt does not belong to the software request"
        )
    constraints = production_receipt["environmental_constraints"]
    if not isinstance(constraints, Mapping) or constraints.get(
        "purpose_notice_hash"
    ) != purpose_notice_hash:
        raise VerifiedNeedToResultError(
            "production_receipt is not bound to the purpose notice"
        )

    supplied_hash = _hash(
        production_receipt["receipt_hash"],
        "production_receipt.receipt_hash",
    )
    body = {
        key: deepcopy(value)
        for key, value in production_receipt.items()
        if key != "receipt_hash"
    }
    try:
        expected_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise VerifiedNeedToResultError(
            "production_receipt cannot be canonically verified"
        ) from exc
    if supplied_hash != expected_hash:
        raise VerifiedNeedToResultError("production_receipt hash mismatch")

    complete = (
        production_receipt["status"] == "CONVERGED"
        and production_receipt["terminal_reason"] == RUNNABLE_STOP_CONDITION
        and production_receipt["converged"] is True
        and production_receipt["runnable"] is True
    )
    if complete:
        final = production_receipt["final_verification"]
        if not isinstance(final, Mapping):
            raise VerifiedNeedToResultError(
                "complete production requires final_verification"
            )
        command = final.get("command")
        if (
            final.get("passed") is not True
            or final.get("runnable") is not True
            or type(command) is not str
            or not command.strip()
        ):
            raise VerifiedNeedToResultError(
                "complete production lacks a verified runnable result"
            )
    elif production_receipt["converged"] is True or production_receipt["runnable"] is True:
        raise VerifiedNeedToResultError(
            "production convergence fields contradict its terminal state"
        )

    return deepcopy(production_receipt)


def _compose_receipt(
    *,
    path_id: str,
    purpose_notice: Mapping[str, Any],
    software_request: Any,
    production_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    purpose, request, request_hash = _validated_purpose(
        purpose_notice,
        software_request,
    )
    production = _validated_production_receipt(
        production_receipt,
        software_request=request,
        purpose_notice_hash=purpose["notice_hash"],
    )
    stop_reached = (
        production["status"] == "CONVERGED"
        and production["terminal_reason"] == RUNNABLE_STOP_CONDITION
        and production["converged"] is True
        and production["runnable"] is True
    )
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "path_id": _identifier(path_id, "path_id"),
        "purpose_notice": purpose,
        "purpose_notice_hash": purpose["notice_hash"],
        "software_request": request,
        "software_request_hash": request_hash,
        "production_receipt": production,
        "production_receipt_hash": production["receipt_hash"],
        "declared_stop_condition": RUNNABLE_STOP_CONDITION,
        "status": "COMPLETE" if stop_reached else "BLOCKED",
        "terminal_reason": production["terminal_reason"],
        "stop_reached": stop_reached,
        "persistence_performed": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "COMPLETE means the existing bounded software path reported a "
            "verified runnable result matching the purpose notice's exact stop "
            "token. This receipt binds identities only; it does not authenticate "
            "external evidence, prove usefulness or truth, accept or persist the "
            "result, or grant write or execution authority."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def run_verified_need_to_result(
    *,
    path_id: str,
    purpose_notice: Mapping[str, Any],
    software_request: Any,
    workspace: str | Path,
    decomposer: Callable[[Any, Mapping[str, Any]], Sequence[Mapping[str, Any]]],
    comparator: Callable[[Any, Path], Mapping[str, Any]],
    proposer: Callable[..., Mapping[str, Any]],
    capability_verifier: Any,
    project_verifier: Callable[[Path], Mapping[str, Any]],
    max_cycles: int = 3,
    max_builder_attempts: int = 3,
    environmental_constraints: Mapping[str, Any] | None = None,
    residue_verifier: Callable[..., Mapping[str, Any]] | None = None,
    preserved_record: Mapping[str, Any] | None = None,
    reconstructed_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce one result only after its exact purpose and stop are bound."""
    checked_id = _identifier(path_id, "path_id")
    purpose, request, _ = _validated_purpose(
        purpose_notice,
        software_request,
    )
    constraints = deepcopy(dict(environmental_constraints or {}))
    supplied_purpose_hash = constraints.get("purpose_notice_hash")
    if (
        supplied_purpose_hash is not None
        and supplied_purpose_hash != purpose["notice_hash"]
    ):
        raise VerifiedNeedToResultError(
            "environmental_constraints contain a conflicting purpose binding"
        )
    constraints["purpose_notice_hash"] = purpose["notice_hash"]

    production = run_software_convergence_request(
        request,
        workspace,
        decomposer,
        comparator,
        proposer,
        capability_verifier,
        project_verifier,
        max_cycles=max_cycles,
        max_builder_attempts=max_builder_attempts,
        environmental_constraints=constraints,
        residue_verifier=residue_verifier,
        preserved_record=preserved_record,
        reconstructed_state=reconstructed_state,
    )
    return _compose_receipt(
        path_id=checked_id,
        purpose_notice=purpose,
        software_request=request,
        production_receipt=production,
    )


def verify_need_to_result_receipt(receipt: Mapping[str, Any]) -> bool:
    """Rebuild one recorded path and fail closed on substitution or tampering."""
    if type(receipt) is not dict or set(receipt) != _RECEIPT_FIELDS:
        raise VerifiedNeedToResultError(
            "receipt fields do not match the versioned schema"
        )
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        raise VerifiedNeedToResultError("receipt schema is invalid")
    if (
        receipt["truth_claimed"] is not False
        or receipt["accepted"] is not False
        or receipt["persistence_performed"] is not False
        or receipt["write_authority"] != "NONE"
        or receipt["execution_authority"] != "NONE"
    ):
        raise VerifiedNeedToResultError("receipt grants forbidden authority")

    rebuilt = _compose_receipt(
        path_id=receipt["path_id"],
        purpose_notice=receipt["purpose_notice"],
        software_request=receipt["software_request"],
        production_receipt=receipt["production_receipt"],
    )
    if rebuilt != receipt:
        raise VerifiedNeedToResultError(
            "receipt does not match its purpose-bound production identity"
        )
    return True
