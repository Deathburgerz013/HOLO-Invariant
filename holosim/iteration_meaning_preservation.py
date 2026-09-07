"""Bounded composition receipt for meaning-preserving concept iterations.

This module does not simplify text, infer semantics, accept a declaration, or
mutate canonical state.  It binds a caller-declared iteration stage to the
existing semantic-signal-loss receipt so loss cannot be silently treated as a
meaning-preserving transformation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from holosim.semantic_signal_loss_receipts import (
    SemanticSignalLossReceiptError,
    build_semantic_signal_loss_receipt,
    verify_semantic_signal_loss_receipt,
)


RECEIPT_TYPE = "holo_iteration_meaning_preservation_receipt"
RECEIPT_VERSION = 1

ALLOWED_STAGES = {
    "EVOLUTION",
    "SIMPLIFICATION",
    "REDUNDANCY_REMOVAL",
    "CLARIFICATION",
    "DECLARATION",
}

PRESERVATION_STATES = {
    "PRESERVED",
    "LOSS_DETECTED",
    "NOT_DECLARED",
}


class IterationMeaningPreservationReceiptError(ValueError):
    """Raised when an iteration meaning-preservation receipt is invalid."""


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
        raise IterationMeaningPreservationReceiptError(
            f"{label} must contain only JSON values"
        ) from exc


def _canonical_hash(value: Any, *, label: str) -> str:
    return hashlib.sha256(
        _canonical_json(value, label=label).encode("utf-8")
    ).hexdigest()


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IterationMeaningPreservationReceiptError(
            f"{label} must be a non-empty string"
        )
    return value


def _signal_list(value: Any, *, label: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise IterationMeaningPreservationReceiptError(
            f"{label} must be a sequence"
        )

    signals: list[str] = []
    seen: set[str] = set()
    for index, signal in enumerate(value):
        validated = _required_text(signal, label=f"{label}[{index}]")
        if validated in seen:
            raise IterationMeaningPreservationReceiptError(
                f"{label} must not contain duplicates"
            )
        seen.add(validated)
        signals.append(validated)
    return sorted(signals)


def _preservation_state(context_preservation: str) -> str:
    if context_preservation == "COMPLETE_DECLARED_SCOPE":
        return "PRESERVED"
    if context_preservation in {"PARTIAL", "NONE"}:
        return "LOSS_DETECTED"
    if context_preservation == "NOT_DECLARED":
        return "NOT_DECLARED"
    raise IterationMeaningPreservationReceiptError(
        "semantic context preservation is invalid"
    )


def build_iteration_meaning_preservation_receipt(
    *,
    iteration_id: str,
    stage: str,
    source_content: str,
    transformed_content: str,
    declared_signals: Sequence[str],
    preserved_signals: Sequence[str],
    inferred_signals: Sequence[str],
    observed_at: str,
) -> dict[str, Any]:
    """Bind one declared iteration stage to an existing semantic-loss check."""

    iteration_id = _required_text(iteration_id, label="iteration_id")
    stage = _required_text(stage, label="stage").upper()
    if stage not in ALLOWED_STAGES:
        raise IterationMeaningPreservationReceiptError(
            "stage is not an allowed iteration stage"
        )

    declared = _signal_list(declared_signals, label="declared_signals")
    preserved = _signal_list(preserved_signals, label="preserved_signals")
    inferred = _signal_list(inferred_signals, label="inferred_signals")

    try:
        semantic_receipt = build_semantic_signal_loss_receipt(
            transformation_id=f"{iteration_id}:{stage}",
            source_content=source_content,
            observed_content=transformed_content,
            declared_signals=declared,
            preserved_signals=preserved,
            inferred_signals=inferred,
            observed_at=observed_at,
        )
        verify_semantic_signal_loss_receipt(semantic_receipt)
    except SemanticSignalLossReceiptError as exc:
        raise IterationMeaningPreservationReceiptError(
            "semantic signal-loss receipt is invalid"
        ) from exc

    preservation = _preservation_state(
        semantic_receipt["context_preservation"]
    )

    receipt: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "iteration_id": iteration_id,
        "stage": stage,
        "semantic_signal_loss_receipt": semantic_receipt,
        "semantic_signal_loss_receipt_hash": semantic_receipt["receipt_hash"],
        "preservation": preservation,
        "meaning_preservation_claimed": preservation == "PRESERVED",
        "state_change_authorized": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    receipt["receipt_hash"] = _canonical_hash(receipt, label="receipt")
    return receipt


def verify_iteration_meaning_preservation_receipt(
    receipt: Mapping[str, Any],
) -> bool:
    """Verify integrity, composition, and fixed authority boundaries."""

    if not isinstance(receipt, Mapping):
        raise IterationMeaningPreservationReceiptError(
            "receipt must be a mapping"
        )

    closed = json.loads(_canonical_json(dict(receipt), label="receipt"))

    required_fields = {
        "type",
        "version",
        "iteration_id",
        "stage",
        "semantic_signal_loss_receipt",
        "semantic_signal_loss_receipt_hash",
        "preservation",
        "meaning_preservation_claimed",
        "state_change_authorized",
        "accepted",
        "truth_claimed",
        "write_authority",
        "execution_authority",
        "canonical_mutation",
        "receipt_hash",
    }
    if set(closed) != required_fields:
        raise IterationMeaningPreservationReceiptError(
            "receipt fields are invalid"
        )

    supplied_hash = closed.pop("receipt_hash")
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise IterationMeaningPreservationReceiptError(
            "receipt_hash must be a non-empty string"
        )
    if supplied_hash != _canonical_hash(closed, label="receipt"):
        raise IterationMeaningPreservationReceiptError(
            "receipt hash mismatch"
        )

    if closed["type"] != RECEIPT_TYPE or closed["version"] != RECEIPT_VERSION:
        raise IterationMeaningPreservationReceiptError(
            "receipt type or version mismatch"
        )

    _required_text(closed["iteration_id"], label="iteration_id")
    stage = _required_text(closed["stage"], label="stage")
    if stage not in ALLOWED_STAGES:
        raise IterationMeaningPreservationReceiptError(
            "stage is not an allowed iteration stage"
        )

    semantic_receipt = closed["semantic_signal_loss_receipt"]
    try:
        verify_semantic_signal_loss_receipt(semantic_receipt)
    except SemanticSignalLossReceiptError as exc:
        raise IterationMeaningPreservationReceiptError(
            "semantic signal-loss receipt is invalid"
        ) from exc

    if (
        closed["semantic_signal_loss_receipt_hash"]
        != semantic_receipt["receipt_hash"]
    ):
        raise IterationMeaningPreservationReceiptError(
            "semantic receipt hash binding mismatch"
        )

    expected_transformation_id = f"{closed['iteration_id']}:{stage}"
    if semantic_receipt["transformation_id"] != expected_transformation_id:
        raise IterationMeaningPreservationReceiptError(
            "semantic receipt iteration binding mismatch"
        )

    expected_preservation = _preservation_state(
        semantic_receipt["context_preservation"]
    )
    if closed["preservation"] != expected_preservation:
        raise IterationMeaningPreservationReceiptError(
            "preservation state is inconsistent"
        )
    if closed["preservation"] not in PRESERVATION_STATES:
        raise IterationMeaningPreservationReceiptError(
            "preservation state is invalid"
        )

    expected_claim = expected_preservation == "PRESERVED"
    if closed["meaning_preservation_claimed"] is not expected_claim:
        raise IterationMeaningPreservationReceiptError(
            "meaning preservation claim is inconsistent"
        )

    bounded_fields = {
        "state_change_authorized": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    for field, expected in bounded_fields.items():
        if closed[field] != expected:
            raise IterationMeaningPreservationReceiptError(
                f"invalid bounded field {field}"
            )

    return True
