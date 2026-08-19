"""Receipts for contextual signals lost during representation changes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


RECEIPT_TYPE = "holo_semantic_signal_loss_receipt"
RECEIPT_VERSION = 1

CONTENT_IDENTITIES = {
    "MATCH",
    "DIFFERENT",
}
CONTEXT_STATES = {
    "NOT_DECLARED",
    "NONE",
    "PARTIAL",
    "COMPLETE_DECLARED_SCOPE",
}


class SemanticSignalLossReceiptError(ValueError):
    """Raised when a semantic signal-loss receipt is invalid."""


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
        raise SemanticSignalLossReceiptError(
            f"{label} must contain only JSON values"
        ) from exc


def _canonical_hash(value: Any, *, label: str) -> str:
    return hashlib.sha256(
        _canonical_json(
            value,
            label=label,
        ).encode("utf-8")
    ).hexdigest()


def _content_hash(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise SemanticSignalLossReceiptError(
            f"{label} must be a string"
        )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticSignalLossReceiptError(
            f"{label} must be a non-empty string"
        )
    return value


def _signal_list(
    value: Any,
    *,
    label: str,
) -> list[str]:
    if (
        isinstance(value, (str, bytes))
        or not isinstance(value, Sequence)
    ):
        raise SemanticSignalLossReceiptError(
            f"{label} must be a sequence"
        )

    signals: list[str] = []
    seen: set[str] = set()

    for index, signal in enumerate(value):
        validated = _required_text(
            signal,
            label=f"{label}[{index}]",
        )

        if validated in seen:
            raise SemanticSignalLossReceiptError(
                f"{label} must not contain duplicates"
            )

        seen.add(validated)
        signals.append(validated)

    return sorted(signals)


def _context_preservation(
    declared: Sequence[str],
    preserved: Sequence[str],
) -> str:
    if not declared:
        return "NOT_DECLARED"
    if not preserved:
        return "NONE"
    if set(declared) == set(preserved):
        return "COMPLETE_DECLARED_SCOPE"
    return "PARTIAL"


def build_semantic_signal_loss_receipt(
    *,
    transformation_id: str,
    source_content: str,
    observed_content: str,
    declared_signals: Sequence[str],
    preserved_signals: Sequence[str],
    inferred_signals: Sequence[str],
    observed_at: str,
) -> dict[str, Any]:
    """Describe representation loss without claiming semantic identity."""
    transformation_id = _required_text(
        transformation_id,
        label="transformation_id",
    )
    observed_at = _required_text(
        observed_at,
        label="observed_at",
    )

    source_hash = _content_hash(
        source_content,
        label="source_content",
    )
    observed_hash = _content_hash(
        observed_content,
        label="observed_content",
    )

    declared = _signal_list(
        declared_signals,
        label="declared_signals",
    )
    preserved = _signal_list(
        preserved_signals,
        label="preserved_signals",
    )
    inferred = _signal_list(
        inferred_signals,
        label="inferred_signals",
    )

    undeclared_preserved = (
        set(preserved) - set(declared)
    )
    if undeclared_preserved:
        raise SemanticSignalLossReceiptError(
            "preserved signals must be declared"
        )

    if set(inferred) & set(preserved):
        raise SemanticSignalLossReceiptError(
            "inferred signals cannot be preserved"
        )

    lost = sorted(
        set(declared) - set(preserved)
    )

    receipt: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "transformation_id": transformation_id,
        "observed_at": observed_at,
        "source_content_hash": source_hash,
        "observed_content_hash": observed_hash,
        "content_identity": (
            "MATCH"
            if source_hash == observed_hash
            else "DIFFERENT"
        ),
        "declared_signals": declared,
        "preserved_signals": preserved,
        "lost_signals": lost,
        "inferred_signals": inferred,
        "context_preservation": (
            _context_preservation(
                declared,
                preserved,
            )
        ),
        "interpretation_identity": "UNKNOWN",
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    receipt["receipt_hash"] = _canonical_hash(
        receipt,
        label="receipt",
    )
    return receipt


def verify_semantic_signal_loss_receipt(
    receipt: Mapping[str, Any],
) -> bool:
    """Verify receipt integrity and semantic boundary consistency."""
    if not isinstance(receipt, Mapping):
        raise SemanticSignalLossReceiptError(
            "receipt must be a mapping"
        )

    try:
        closed = json.loads(
            _canonical_json(
                dict(receipt),
                label="receipt",
            )
        )
    except (TypeError, ValueError) as exc:
        raise SemanticSignalLossReceiptError(
            "receipt must contain only JSON values"
        ) from exc

    required_fields = {
        "type",
        "version",
        "transformation_id",
        "observed_at",
        "source_content_hash",
        "observed_content_hash",
        "content_identity",
        "declared_signals",
        "preserved_signals",
        "lost_signals",
        "inferred_signals",
        "context_preservation",
        "interpretation_identity",
        "accepted",
        "truth_claimed",
        "write_authority",
        "execution_authority",
        "canonical_mutation",
        "receipt_hash",
    }
    if set(closed) != required_fields:
        raise SemanticSignalLossReceiptError(
            "receipt fields are invalid"
        )

    supplied_hash = closed.pop(
        "receipt_hash"
    )
    if not isinstance(supplied_hash, str) or not supplied_hash:
        raise SemanticSignalLossReceiptError(
            "receipt_hash must be a non-empty string"
        )

    expected_hash = _canonical_hash(
        closed,
        label="receipt",
    )
    if supplied_hash != expected_hash:
        raise SemanticSignalLossReceiptError(
            "receipt hash mismatch"
        )

    if closed["type"] != RECEIPT_TYPE:
        raise SemanticSignalLossReceiptError(
            "receipt type mismatch"
        )
    if closed["version"] != RECEIPT_VERSION:
        raise SemanticSignalLossReceiptError(
            "receipt version mismatch"
        )

    _required_text(
        closed["transformation_id"],
        label="transformation_id",
    )
    _required_text(
        closed["observed_at"],
        label="observed_at",
    )

    for field in (
        "source_content_hash",
        "observed_content_hash",
    ):
        value = closed[field]
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(
                character not in "0123456789abcdef"
                for character in value
            )
        ):
            raise SemanticSignalLossReceiptError(
                f"{field} must be a SHA-256 hex digest"
            )

    declared = _signal_list(
        closed["declared_signals"],
        label="declared_signals",
    )
    preserved = _signal_list(
        closed["preserved_signals"],
        label="preserved_signals",
    )
    lost = _signal_list(
        closed["lost_signals"],
        label="lost_signals",
    )
    inferred = _signal_list(
        closed["inferred_signals"],
        label="inferred_signals",
    )

    if declared != closed["declared_signals"]:
        raise SemanticSignalLossReceiptError(
            "declared signals are not canonical"
        )
    if preserved != closed["preserved_signals"]:
        raise SemanticSignalLossReceiptError(
            "preserved signals are not canonical"
        )
    if inferred != closed["inferred_signals"]:
        raise SemanticSignalLossReceiptError(
            "inferred signals are not canonical"
        )

    if set(preserved) - set(declared):
        raise SemanticSignalLossReceiptError(
            "preserved signals must be declared"
        )
    if set(inferred) & set(preserved):
        raise SemanticSignalLossReceiptError(
            "inferred signals cannot be preserved"
        )

    expected_lost = sorted(
        set(declared) - set(preserved)
    )
    if lost != expected_lost:
        raise SemanticSignalLossReceiptError(
            "lost signals do not match declared scope"
        )

    expected_content_identity = (
        "MATCH"
        if (
            closed["source_content_hash"]
            == closed["observed_content_hash"]
        )
        else "DIFFERENT"
    )
    if (
        closed["content_identity"]
        != expected_content_identity
    ):
        raise SemanticSignalLossReceiptError(
            "content identity is inconsistent"
        )
    if (
        closed["content_identity"]
        not in CONTENT_IDENTITIES
    ):
        raise SemanticSignalLossReceiptError(
            "content identity is invalid"
        )

    expected_context = _context_preservation(
        declared,
        preserved,
    )
    if closed["context_preservation"] != expected_context:
        raise SemanticSignalLossReceiptError(
            "context preservation is inconsistent"
        )
    if closed["context_preservation"] not in CONTEXT_STATES:
        raise SemanticSignalLossReceiptError(
            "context preservation is invalid"
        )

    if closed["interpretation_identity"] != "UNKNOWN":
        raise SemanticSignalLossReceiptError(
            "interpretation identity must remain UNKNOWN"
        )

    bounded_fields = {
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    for field, expected in bounded_fields.items():
        if closed.get(field) != expected:
            raise SemanticSignalLossReceiptError(
                f"invalid bounded field {field}"
            )

    return True