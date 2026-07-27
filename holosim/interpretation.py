"""Version-bound interpretation receipts for HOLO/Sim.

An interpretation receipt declares the inputs, rules, assumptions, scope, and
transformations that produced a result.  It records a reconstructible account
of interpretation without granting truth, acceptance, or write authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from holosim.canonical import stable_hash


RECEIPT_TYPE = "interpretation_receipt"
RECEIPT_VERSION = 1

_INTERPRETATION_DIMENSIONS = (
    "inputs",
    "rules",
    "assumptions",
    "scope",
    "transformations",
)


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _normalize_statements(
    values: Iterable[Any],
    field_name: str,
    *,
    allow_empty: bool,
) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must be an iterable of strings")

    normalized = [
        _require_non_empty_string(value, field_name)
        for value in values
    ]

    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must contain at least one statement")

    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} statements must be unique")

    return normalized


def _normalize_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(inputs, Mapping):
        raise ValueError("inputs must be a mapping")
    if not inputs:
        raise ValueError("inputs must contain at least one declared input")

    copied = deepcopy(dict(inputs))
    for key in copied:
        _require_non_empty_string(key, "input key")

    # stable_hash performs the strict canonical JSON validation used across
    # the repository.  The result is intentionally discarded here.
    stable_hash(copied)
    return copied


def record_interpretation(
    *,
    inputs: Mapping[str, Any],
    rules: Iterable[Any],
    assumptions: Iterable[Any] = (),
    scope: Any,
    transformations: Iterable[Any],
    result: Any,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record one declared interpretation chain.

    The receipt does not prove that the interpretation is true.  It makes the
    path to the result explicit and deterministically identifiable.
    """

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "inputs": _normalize_inputs(inputs),
        "rules": _normalize_statements(
            rules,
            "rules",
            allow_empty=False,
        ),
        "assumptions": _normalize_statements(
            assumptions,
            "assumptions",
            allow_empty=True,
        ),
        "scope": _require_non_empty_string(scope, "scope"),
        "transformations": _normalize_statements(
            transformations,
            "transformations",
            allow_empty=False,
        ),
        "result": deepcopy(result),
        "metadata": deepcopy(dict(metadata or {})),
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }


def validate_interpretation_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and return a detached interpretation receipt."""

    if not isinstance(receipt, Mapping):
        raise ValueError("receipt must be a mapping")

    copied = deepcopy(dict(receipt))
    receipt_hash = copied.pop("receipt_hash", None)

    if copied.get("type") != RECEIPT_TYPE:
        raise ValueError("receipt type must be interpretation_receipt")
    if copied.get("version") != RECEIPT_VERSION:
        raise ValueError("receipt version must be 1")
    if not isinstance(receipt_hash, str) or receipt_hash != stable_hash(copied):
        raise ValueError("receipt_hash does not match receipt body")

    if copied.get("accepted") is not False:
        raise ValueError("interpretation receipt cannot grant acceptance")
    if copied.get("truth_claimed") is not False:
        raise ValueError("interpretation receipt cannot claim truth")
    if copied.get("write_authority") != "NONE":
        raise ValueError("interpretation receipt cannot grant write authority")

    return {
        **copied,
        "receipt_hash": receipt_hash,
    }


def compare_interpretations(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    """Explain whether a result difference has a declared cause.

    A changed result is justified only in the narrow structural sense that at
    least one declared interpretation dimension changed.  This function does
    not decide whether the new rule, input, assumption, scope, or
    transformation is itself correct.
    """

    left_receipt = validate_interpretation_receipt(left)
    right_receipt = validate_interpretation_receipt(right)

    changed_dimensions = [
        field_name
        for field_name in _INTERPRETATION_DIMENSIONS
        if left_receipt[field_name] != right_receipt[field_name]
    ]
    result_changed = left_receipt["result"] != right_receipt["result"]
    unexplained_result_difference = (
        result_changed and not changed_dimensions
    )

    return {
        "left_receipt_hash": left_receipt["receipt_hash"],
        "right_receipt_hash": right_receipt["receipt_hash"],
        "changed_dimensions": changed_dimensions,
        "result_changed": result_changed,
        "difference_justified": not unexplained_result_difference,
        "unexplained_result_difference": unexplained_result_difference,
        "valid": not unexplained_result_difference,
    }
