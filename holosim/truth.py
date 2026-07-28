"""Version-bound truth states that move only through verified evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any


TRUTH_STATE_TYPE = "holo_truth_state"
TRUTH_STATE_VERSION = 1

TruthEvidenceValidator = Callable[[Mapping[str, Any]], None]


class TruthStateError(ValueError):
    """Raised when a truth state cannot be honestly created or revised."""


def _canonical_hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise TruthStateError("value could not be canonicalized") from exc

    return hashlib.sha256(encoded).hexdigest()


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TruthStateError(f"{field} must be a non-empty string")
    return value


def _validate_evidence(
    evidence_receipts: Sequence[Mapping[str, Any]],
    evidence_validator: TruthEvidenceValidator,
) -> tuple[list[dict[str, Any]], list[str]]:
    if isinstance(evidence_receipts, (str, bytes)) or not isinstance(
        evidence_receipts,
        Sequence,
    ):
        raise TruthStateError("evidence_receipts must be a sequence")

    if not evidence_receipts:
        raise TruthStateError("at least one evidence receipt is required")

    if not callable(evidence_validator):
        raise TruthStateError("evidence_validator must be callable")

    receipts: list[dict[str, Any]] = []
    hashes: list[str] = []
    seen_hashes: set[str] = set()

    for index, receipt in enumerate(evidence_receipts):
        if not isinstance(receipt, Mapping):
            raise TruthStateError(
                f"evidence receipt at index {index} must be a mapping"
            )

        try:
            evidence_validator(receipt)
        except Exception as exc:
            raise TruthStateError(
                f"evidence receipt at index {index} is invalid"
            ) from exc

        receipt_copy = dict(receipt)
        evidence_hash = _canonical_hash(receipt_copy)

        if evidence_hash in seen_hashes:
            raise TruthStateError("duplicate evidence receipt")

        receipts.append(receipt_copy)
        hashes.append(evidence_hash)
        seen_hashes.add(evidence_hash)

    return receipts, hashes


def _build_truth_state(
    *,
    statement: str,
    evidence_receipts: list[dict[str, Any]],
    evidence_hashes: list[str],
    parent_truth_hash: str | None,
    transition: str,
) -> dict[str, Any]:
    body = {
        "type": TRUTH_STATE_TYPE,
        "version": TRUTH_STATE_VERSION,
        "statement": statement,
        "evidence_receipts": evidence_receipts,
        "evidence_hashes": evidence_hashes,
        "parent_truth_hash": parent_truth_hash,
        "transition": transition,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This state records a statement currently justified by verified "
            "evidence. It does not grant acceptance or write authority. The "
            "statement may move only through a later evidence-bound revision."
        ),
    }

    return {
        **body,
        "truth_hash": _canonical_hash(body),
    }


def crystallize_truth(
    statement: str,
    evidence_receipts: Sequence[Mapping[str, Any]],
    evidence_validator: TruthEvidenceValidator,
) -> dict[str, Any]:
    """
    Create an initial truth state from verified evidence.

    The evidence validator determines whether each supplied receipt is valid.
    The resulting state records evidence and its canonical hashes without
    granting acceptance or authority.
    """
    normalized_statement = _require_nonempty_string(statement, "statement")
    receipts, hashes = _validate_evidence(
        evidence_receipts,
        evidence_validator,
    )

    return _build_truth_state(
        statement=normalized_statement,
        evidence_receipts=receipts,
        evidence_hashes=hashes,
        parent_truth_hash=None,
        transition="crystallized",
    )


def revise_truth(
    current_truth: Mapping[str, Any],
    statement: str,
    evidence_receipts: Sequence[Mapping[str, Any]],
    evidence_validator: TruthEvidenceValidator,
) -> dict[str, Any]:
    """
    Re-justify a truth state using its prior evidence plus new verified evidence.

    At least one newly verified evidence receipt is required. Existing evidence
    cannot be silently removed or replaced. If the statement changes, the truth
    is reported as moved. If it survives the new evidence unchanged, it is
    reported as further crystallized.
    """
    validate_truth_state(current_truth)

    normalized_statement = _require_nonempty_string(statement, "statement")
    receipts, hashes = _validate_evidence(
        evidence_receipts,
        evidence_validator,
    )

    current_hashes = list(current_truth["evidence_hashes"])
    current_hash_set = set(current_hashes)
    supplied_hash_set = set(hashes)

    missing_prior = [
        evidence_hash
        for evidence_hash in current_hashes
        if evidence_hash not in supplied_hash_set
    ]
    if missing_prior:
        raise TruthStateError(
            "revision cannot remove previously recorded evidence"
        )

    new_hashes = [
        evidence_hash
        for evidence_hash in hashes
        if evidence_hash not in current_hash_set
    ]
    if not new_hashes:
        raise TruthStateError(
            "revision requires at least one new verified evidence receipt"
        )

    transition = (
        "crystallized"
        if normalized_statement == current_truth["statement"]
        else "moved"
    )

    return _build_truth_state(
        statement=normalized_statement,
        evidence_receipts=receipts,
        evidence_hashes=hashes,
        parent_truth_hash=current_truth["truth_hash"],
        transition=transition,
    )


def validate_truth_state(state: Mapping[str, Any]) -> None:
    """Validate the structure and canonical hash of a truth state."""
    if not isinstance(state, Mapping):
        raise TruthStateError("truth state must be a mapping")

    required_fields = {
        "type",
        "version",
        "statement",
        "evidence_receipts",
        "evidence_hashes",
        "parent_truth_hash",
        "transition",
        "accepted",
        "write_authority",
        "interpretation_notice",
        "truth_hash",
    }
    if set(state) != required_fields:
        raise TruthStateError("truth state fields are invalid")

    if state["type"] != TRUTH_STATE_TYPE:
        raise TruthStateError("truth state type is invalid")

    if state["version"] != TRUTH_STATE_VERSION:
        raise TruthStateError("truth state version is invalid")

    _require_nonempty_string(state["statement"], "statement")

    receipts = state["evidence_receipts"]
    hashes = state["evidence_hashes"]

    if not isinstance(receipts, list) or not receipts:
        raise TruthStateError("evidence_receipts must be a non-empty list")

    if not isinstance(hashes, list) or len(hashes) != len(receipts):
        raise TruthStateError(
            "evidence_hashes must correspond to evidence_receipts"
        )

    expected_hashes: list[str] = []
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, Mapping):
            raise TruthStateError(
                f"evidence receipt at index {index} must be a mapping"
            )
        expected_hashes.append(_canonical_hash(receipt))

    if hashes != expected_hashes:
        raise TruthStateError("evidence hashes do not match evidence receipts")

    if len(set(hashes)) != len(hashes):
        raise TruthStateError("truth state contains duplicate evidence")

    parent_truth_hash = state["parent_truth_hash"]
    if parent_truth_hash is not None:
        if (
            not isinstance(parent_truth_hash, str)
            or len(parent_truth_hash) != 64
        ):
            raise TruthStateError("parent_truth_hash is invalid")

    if state["transition"] not in {"crystallized", "moved"}:
        raise TruthStateError("truth transition is invalid")

    if parent_truth_hash is None and state["transition"] != "crystallized":
        raise TruthStateError("initial truth state must be crystallized")

    if state["accepted"] is not False:
        raise TruthStateError("truth state cannot grant acceptance")

    if state["write_authority"] != "NONE":
        raise TruthStateError("truth state cannot grant write authority")

    _require_nonempty_string(
        state["interpretation_notice"],
        "interpretation_notice",
    )

    body = {
        key: value
        for key, value in state.items()
        if key != "truth_hash"
    }
    if state["truth_hash"] != _canonical_hash(body):
        raise TruthStateError("truth hash is invalid")