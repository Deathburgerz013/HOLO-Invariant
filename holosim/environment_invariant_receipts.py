"""Bounded receipts for environment-observed invariant checks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any


RECEIPT_TYPE = "holo_environment_invariant_receipt"
RECEIPT_VERSION = 1
VALID_STATUSES = {
    "HELD",
    "FAILED",
    "UNKNOWN",
    "STALE",
}


class EnvironmentInvariantReceiptError(ValueError):
    """Raised when an environment receipt contract is invalid."""


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
        raise EnvironmentInvariantReceiptError(
            f"{label} must contain only JSON values"
        ) from exc


def _closed_json_copy(value: Any, *, label: str) -> Any:
    return json.loads(_canonical_json(value, label=label))


def _digest_json(value: Any, *, label: str) -> str:
    canonical = _canonical_json(value, label=label)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_nonempty_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EnvironmentInvariantReceiptError(
            f"{label} must be a non-empty string"
        )
    return value


def environment_fingerprint(
    environment: Mapping[str, Any],
) -> str:
    """Return the deterministic identity of an observed environment."""
    if not isinstance(environment, Mapping):
        raise EnvironmentInvariantReceiptError(
            "environment must be a mapping"
        )

    closed_environment = _closed_json_copy(
        dict(environment),
        label="environment",
    )
    if not isinstance(closed_environment, dict):
        raise EnvironmentInvariantReceiptError(
            "environment must be a JSON object"
        )

    return _digest_json(
        closed_environment,
        label="environment",
    )


def _build_error(
    error_type: str,
    message: str,
) -> dict[str, str]:
    return {
        "type": error_type,
        "message": message,
    }


def evaluate_environment_invariant(
    *,
    invariant_id: str,
    statement: str,
    scope: Mapping[str, Any],
    environment: Mapping[str, Any],
    environment_probe: Callable[[], Mapping[str, Any]],
    check_id: str,
    check: Callable[[], bool | None],
    observed_at: str,
    evidence: Mapping[str, Any] | None = None,
    expected_environment_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Observe an environment, then run one bounded invariant check."""
    invariant_id = _require_nonempty_string(
        invariant_id,
        label="invariant_id",
    )
    statement = _require_nonempty_string(
        statement,
        label="statement",
    )
    check_id = _require_nonempty_string(
        check_id,
        label="check_id",
    )
    observed_at = _require_nonempty_string(
        observed_at,
        label="observed_at",
    )

    if not isinstance(scope, Mapping):
        raise EnvironmentInvariantReceiptError(
            "scope must be a mapping"
        )
    if not isinstance(environment, Mapping):
        raise EnvironmentInvariantReceiptError(
            "environment must be a mapping"
        )
    if evidence is not None and not isinstance(evidence, Mapping):
        raise EnvironmentInvariantReceiptError(
            "evidence must be a mapping or None"
        )
    if not callable(environment_probe):
        raise EnvironmentInvariantReceiptError(
            "environment_probe must be callable"
        )
    if not callable(check):
        raise EnvironmentInvariantReceiptError(
            "check must be callable"
        )
    if (
        expected_environment_fingerprint is not None
        and (
            not isinstance(expected_environment_fingerprint, str)
            or not expected_environment_fingerprint
        )
    ):
        raise EnvironmentInvariantReceiptError(
            "expected_environment_fingerprint must be "
            "a non-empty string or None"
        )

    closed_scope = _closed_json_copy(
        dict(scope),
        label="scope",
    )
    declared_environment = _closed_json_copy(
        dict(environment),
        label="environment",
    )
    closed_evidence = _closed_json_copy(
        dict(evidence or {}),
        label="evidence",
    )

    declared_fingerprint = environment_fingerprint(
        declared_environment
    )

    status: str
    observed: bool | None = None
    stale_reason: str | None = None
    error: dict[str, str] | None = None
    observed_environment: dict[str, Any] | None = None
    observed_fingerprint: str | None = None

    try:
        probed_environment = environment_probe()
        if not isinstance(probed_environment, Mapping):
            raise EnvironmentInvariantReceiptError(
                "environment probe must return a mapping"
            )
        observed_environment = _closed_json_copy(
            dict(probed_environment),
            label="observed environment",
        )
        observed_fingerprint = environment_fingerprint(
            observed_environment
        )
    except Exception as exc:
        status = "UNKNOWN"
        error = _build_error(
            type(exc).__name__,
            str(exc),
        )
    else:
        if observed_fingerprint != declared_fingerprint:
            status = "STALE"
            stale_reason = "DECLARED_ENVIRONMENT_MISMATCH"
        elif (
            expected_environment_fingerprint is not None
            and observed_fingerprint
            != expected_environment_fingerprint
        ):
            status = "STALE"
            stale_reason = "ENVIRONMENT_FINGERPRINT_MISMATCH"
        else:
            try:
                result = check()
            except Exception as exc:
                status = "UNKNOWN"
                error = _build_error(
                    type(exc).__name__,
                    str(exc),
                )
            else:
                if result is True:
                    status = "HELD"
                    observed = True
                elif result is False:
                    status = "FAILED"
                    observed = False
                elif result is None:
                    status = "UNKNOWN"
                else:
                    status = "UNKNOWN"
                    error = _build_error(
                        "InvalidCheckResult",
                        "check must return True, False, or None",
                    )

    receipt: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "invariant_id": invariant_id,
        "statement": statement,
        "scope": closed_scope,
        "check_id": check_id,
        "observed_at": observed_at,
        "declared_environment": declared_environment,
        "declared_environment_fingerprint": declared_fingerprint,
        "observed_environment": observed_environment,
        "environment_fingerprint": observed_fingerprint,
        "expected_environment_fingerprint": (
            expected_environment_fingerprint
        ),
        "evidence": closed_evidence,
        "evidence_hash": _digest_json(
            closed_evidence,
            label="evidence",
        ),
        "status": status,
        "observed": observed,
        "stale_reason": stale_reason,
        "error": error,
        "constraint_authority": "ENVIRONMENT",
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    receipt["receipt_hash"] = _digest_json(
        receipt,
        label="receipt",
    )
    return receipt


def verify_environment_invariant_receipt(
    receipt: Mapping[str, Any],
) -> bool:
    """Verify receipt identity and bounded authority declarations."""
    if not isinstance(receipt, Mapping):
        raise EnvironmentInvariantReceiptError(
            "receipt must be a mapping"
        )

    closed_receipt = _closed_json_copy(
        dict(receipt),
        label="receipt",
    )

    supplied_hash = closed_receipt.pop(
        "receipt_hash",
        None,
    )
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise EnvironmentInvariantReceiptError(
            "receipt_hash must be a non-empty string"
        )

    expected_hash = _digest_json(
        closed_receipt,
        label="receipt",
    )
    if supplied_hash != expected_hash:
        raise EnvironmentInvariantReceiptError(
            "receipt hash mismatch"
        )

    if closed_receipt.get("type") != RECEIPT_TYPE:
        raise EnvironmentInvariantReceiptError(
            "receipt type mismatch"
        )
    if closed_receipt.get("version") != RECEIPT_VERSION:
        raise EnvironmentInvariantReceiptError(
            "receipt version mismatch"
        )
    if closed_receipt.get("status") not in VALID_STATUSES:
        raise EnvironmentInvariantReceiptError(
            "invalid receipt status"
        )

    declared_environment = closed_receipt.get(
        "declared_environment"
    )
    if not isinstance(declared_environment, dict):
        raise EnvironmentInvariantReceiptError(
            "declared environment must be a JSON object"
        )

    declared_fingerprint = environment_fingerprint(
        declared_environment
    )
    if (
        closed_receipt.get(
            "declared_environment_fingerprint"
        )
        != declared_fingerprint
    ):
        raise EnvironmentInvariantReceiptError(
            "declared environment fingerprint mismatch"
        )

    observed_environment = closed_receipt.get(
        "observed_environment"
    )
    observed_fingerprint = closed_receipt.get(
        "environment_fingerprint"
    )

    if observed_environment is None:
        if observed_fingerprint is not None:
            raise EnvironmentInvariantReceiptError(
                "unobserved environment cannot have a fingerprint"
            )
    else:
        if not isinstance(observed_environment, dict):
            raise EnvironmentInvariantReceiptError(
                "observed environment must be a JSON object or None"
            )
        if observed_fingerprint != environment_fingerprint(
            observed_environment
        ):
            raise EnvironmentInvariantReceiptError(
                "observed environment fingerprint mismatch"
            )

    evidence = closed_receipt.get("evidence")
    if not isinstance(evidence, dict):
        raise EnvironmentInvariantReceiptError(
            "receipt evidence must be a JSON object"
        )
    if closed_receipt.get("evidence_hash") != _digest_json(
        evidence,
        label="evidence",
    ):
        raise EnvironmentInvariantReceiptError(
            "evidence hash mismatch"
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
        if closed_receipt.get(field) != expected:
            raise EnvironmentInvariantReceiptError(
                f"invalid bounded field {field}"
            )

    return True