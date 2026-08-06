"""Deterministic, non-writing text transformation primitives.

The engine applies declared exact replacements to recognized source text
and returns auditable receipts. It grants no write, acceptance, truth,
or execution authority.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable, Mapping
from typing import Any

from holosim.canonical import stable_hash


RECEIPT_TYPE = "bounded_transformation_receipt"
RECEIPT_VERSION = 1


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

    diff = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            result.splitlines(keepends=True),
            fromfile="source",
            tofile="result",
        )
    )

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "status": "TRANSFORMED",
        "changed": source != result,
        "match_count": match_count,
        "expected_fragment": expected,
        "replacement_fragment": replacement,
        "source_text": source,
        "result_text": result,
        "source_hash": stable_hash(source),
        "result_hash": stable_hash(result),
        "diff": diff,
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