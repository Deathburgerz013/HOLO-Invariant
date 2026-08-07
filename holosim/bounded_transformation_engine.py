"""Deterministic, non-writing text transformation primitives.

The engine applies declared exact replacements to recognized source text,
validates resulting text, and verifies transformation receipts. It grants
no write, acceptance, truth, or execution authority.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable, Mapping
from typing import Any

from holosim.canonical import stable_hash


RECEIPT_TYPE = "bounded_transformation_receipt"
RECEIPT_VERSION = 1

_REQUIRED_RECEIPT_FIELDS = {
    "type",
    "version",
    "status",
    "changed",
    "match_count",
    "expected_fragment",
    "replacement_fragment",
    "source_text",
    "result_text",
    "source_hash",
    "result_hash",
    "diff",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}


def _unified_diff(
    source: str,
    result: str,
) -> str:
    return "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            result.splitlines(keepends=True),
            fromfile="source",
            tofile="result",
        )
    )


def replace_exact_once(
    source: str,
    *,
    expected: str,
    replacement: str,
) -> dict[str, Any]:
    """Replace one exact fragment and return an auditable receipt."""

    if not isinstance(source, str):
        raise TypeError("source must be a string")

    if not isinstance(expected, str):
        raise TypeError("expected must be a string")

    if not isinstance(replacement, str):
        raise TypeError("replacement must be a string")

    if not expected:
        raise ValueError("expected must not be empty")

    if expected == replacement:
        raise ValueError(
            "replacement must change the matched fragment"
        )

    match_count = source.count(expected)

    if match_count == 0:
        raise ValueError("expected fragment was not found")

    if match_count != 1:
        raise ValueError(
            "expected fragment must occur exactly once"
        )

    result = source.replace(
        expected,
        replacement,
        1,
    )

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "status": "TRANSFORMED",
        "changed": True,
        "match_count": match_count,
        "expected_fragment": expected,
        "replacement_fragment": replacement,
        "source_text": source,
        "result_text": result,
        "source_hash": stable_hash(source),
        "result_hash": stable_hash(result),
        "diff": _unified_diff(source, result),
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }


def replace_exact_once_validated(
    source: str,
    *,
    expected: str,
    replacement: str,
    validator: Callable[[str], Mapping[str, Any]],
) -> dict[str, Any]:
    """Replace one exact fragment and validate the resulting text."""

    if not callable(validator):
        raise TypeError("validator must be callable")

    transformation = replace_exact_once(
        source,
        expected=expected,
        replacement=replacement,
    )

    validator_result = validator(
        transformation["result_text"]
    )

    if (
        not isinstance(validator_result, Mapping)
        or "status" not in validator_result
    ):
        raise ValueError(
            "validator must return a receipt with status VALID"
        )

    validator_receipt = dict(validator_result)
    validation_status = validator_receipt["status"]

    if validation_status != "VALID":
        raise ValueError(
            "transformed result failed validation"
        )

    if (
        validator_receipt.get("validated_result_hash")
        != transformation["result_hash"]
    ):
        raise ValueError(
            "validator receipt is not bound to transformed result"
        )

    if (
        validator_receipt.get(
            "accepted",
            False,
        )
        is not False
        or validator_receipt.get(
            "truth_claimed",
            False,
        )
        is not False
        or validator_receipt.get(
            "write_authority",
            "NONE",
        )
        != "NONE"
        or validator_receipt.get(
            "execution_authority",
            "NONE",
        )
        != "NONE"
    ):
        raise ValueError(
            "invalid validator receipt authority boundaries"
        )

    body = {
        key: value
        for key, value in transformation.items()
        if key != "receipt_hash"
    }

    body.update(
        {
            "status": "TRANSFORMED_AND_VALIDATED",
            "validation_status": validation_status,
            "validator_receipt": validator_receipt,
        }
    )

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }


def verify_transformation_receipt(
    receipt: object,
) -> dict[str, Any]:
    """Verify receipt integrity and reproduce its declared transformation."""

    if not isinstance(receipt, Mapping):
        raise ValueError("invalid transformation receipt")

    candidate = dict(receipt)

    if not _REQUIRED_RECEIPT_FIELDS.issubset(candidate):
        raise ValueError("invalid transformation receipt")

    if (
        candidate["type"] != RECEIPT_TYPE
        or candidate["version"] != RECEIPT_VERSION
        or candidate["status"]
        not in {
            "TRANSFORMED",
            "TRANSFORMED_AND_VALIDATED",
        }
    ):
        raise ValueError("invalid transformation receipt")

    if (
        candidate["accepted"] is not False
        or candidate["truth_claimed"] is not False
        or candidate["write_authority"] != "NONE"
        or candidate["execution_authority"] != "NONE"
    ):
        raise ValueError(
            "invalid transformation authority boundaries"
        )

    source = candidate["source_text"]
    result = candidate["result_text"]
    expected = candidate["expected_fragment"]
    replacement = candidate["replacement_fragment"]

    if not all(
        isinstance(value, str)
        for value in (
            source,
            result,
            expected,
            replacement,
            candidate["source_hash"],
            candidate["result_hash"],
            candidate["receipt_hash"],
        )
    ):
        raise ValueError("invalid transformation receipt")

    if stable_hash(source) != candidate["source_hash"]:
        raise ValueError("source hash mismatch")

    if stable_hash(result) != candidate["result_hash"]:
        raise ValueError("result hash mismatch")

    if (
        not expected
        or expected == replacement
        or source.count(expected) != 1
        or source.replace(expected, replacement, 1) != result
        or candidate["match_count"] != 1
        or candidate["changed"] is not True
        or candidate["diff"] != _unified_diff(source, result)
    ):
        raise ValueError(
            "declared transformation does not reproduce result"
        )

    if candidate["status"] == "TRANSFORMED_AND_VALIDATED":
        validation_status = candidate.get(
            "validation_status"
        )
        validator_receipt = candidate.get(
            "validator_receipt"
        )

        if (
            validation_status != "VALID"
            or not isinstance(
                validator_receipt,
                Mapping,
            )
            or validator_receipt.get("status")
            != "VALID"
            or validator_receipt.get(
                "validated_result_hash"
            )
            != candidate["result_hash"]
        ):
            raise ValueError(
                "invalid validated transformation receipt"
            )

        if (
            validator_receipt.get(
                "accepted",
                False,
            )
            is not False
            or validator_receipt.get(
                "truth_claimed",
                False,
            )
            is not False
            or validator_receipt.get(
                "write_authority",
                "NONE",
            )
            != "NONE"
            or validator_receipt.get(
                "execution_authority",
                "NONE",
            )
            != "NONE"
        ):
            raise ValueError(
                "invalid validator receipt authority boundaries"
            )

    body = {
        key: value
        for key, value in candidate.items()
        if key != "receipt_hash"
    }

    if stable_hash(body) != candidate["receipt_hash"]:
        raise ValueError("receipt hash mismatch")

    verification_body: dict[str, Any] = {
        "type": "transformation_receipt_verification",
        "version": 1,
        "status": "TRANSFORMATION_RECEIPT_VERIFIED",
        "verified_receipt_hash": candidate["receipt_hash"],
        "source_hash": candidate["source_hash"],
        "result_hash": candidate["result_hash"],
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {
        **verification_body,
        "verification_hash": stable_hash(
            verification_body
        ),
    }