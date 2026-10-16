"""Replay-verifiable, read-only reproduction evidence.

Verifies exact computations over supplied inputs, not observation truth,
requirement completeness, external provenance, or global obsolescence.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.reproduction import build_reproduction_check

TYPE = "evidence_bound_reproduction"
VERSION = 1

INPUT_FIELDS = (
    "reference",
    "baseline_substrate",
    "candidate_substrate",
    "baseline_outcomes",
    "candidate_outcomes",
)

BODY_FIELDS = {
    "type",
    "version",
    "inputs",
    "reproduction",
    "accepted",
    "truth_claimed",
    "write_authority",
}

RECEIPT_FIELDS = BODY_FIELDS | {"verification_hash"}


class EvidenceBoundReproductionError(ValueError):
    """Invalid or inconsistent evidence-bound reproduction receipt."""


def build_evidence_bound_reproduction(
    *,
    reference: str,
    baseline_substrate: list[dict[str, Any]],
    candidate_substrate: list[dict[str, Any]],
    baseline_outcomes: list[dict[str, Any]],
    candidate_outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Preserve inputs and bind them to a replayable reproduction result."""

    inputs = deepcopy({
        "reference": reference,
        "baseline_substrate": baseline_substrate,
        "candidate_substrate": candidate_substrate,
        "baseline_outcomes": baseline_outcomes,
        "candidate_outcomes": candidate_outcomes,
    })

    try:
        reproduction = build_reproduction_check(**inputs)
    except (ValueError, TypeError, RecursionError) as exc:
        raise EvidenceBoundReproductionError('invalid reproduction inputs') from exc

    body = {
        "type": TYPE,
        "version": VERSION,
        "inputs": inputs,
        "reproduction": reproduction,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }

    try:
        verification_hash = stable_hash(body)
    except (CanonicalValueError, RecursionError, UnicodeError) as exc:
        raise EvidenceBoundReproductionError(
            "receipt cannot be canonicalized"
        ) from exc

    return {**body, "verification_hash": verification_hash}


def validate_evidence_bound_reproduction(
    receipt: Mapping[str, Any],
) -> bool:
    """Rebuild the entire receipt from its inputs and require exact identity."""

    if type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS:
        raise EvidenceBoundReproductionError("invalid receipt schema")

    if receipt.get("type") != TYPE or type(receipt.get("version")) is not int or receipt["version"] != VERSION:
        raise EvidenceBoundReproductionError("invalid receipt type or version")

    inputs = receipt.get("inputs")
    if type(inputs) is not dict or set(inputs) != set(INPUT_FIELDS):
        raise EvidenceBoundReproductionError("invalid reproduction inputs")

    try:
        rebuilt = build_evidence_bound_reproduction(**inputs)
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise EvidenceBoundReproductionError(
            "invalid or unreplayable reproduction evidence"
        ) from exc

    try:
        matches = stable_hash(rebuilt) == stable_hash(receipt)
    except (CanonicalValueError, RecursionError, UnicodeError) as exc:
        raise EvidenceBoundReproductionError('receipt cannot be canonicalized') from exc
    if not matches:
        raise EvidenceBoundReproductionError(
            "receipt does not match reconstructed evidence"
        )

    return True
