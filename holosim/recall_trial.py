"""Deterministic evaluation of reconstructed claims against evidence receipts.

The recall trial classifies candidate claims as supported, stale, or
unsupported. It evaluates evidence references without granting truth,
acceptance, or write authority.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from holosim.receipt_graph import build_receipt_graph


_SUPPORTED = "supported"
_STALE = "stale"
_UNSUPPORTED = "unsupported"


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return value


def _require_claim_id(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _candidate_evidence_hashes(
    candidate: Mapping[str, Any],
) -> tuple[Any, ...]:
    evidence_hashes = candidate.get("evidence_receipt_hashes", ())

    if isinstance(evidence_hashes, (str, bytes)) or not isinstance(
        evidence_hashes,
        Iterable,
    ):
        raise ValueError(
            "candidate evidence_receipt_hashes must be an iterable"
        )

    return tuple(evidence_hashes)


def _receipt_state(
    receipts: Iterable[Mapping[str, Any]],
) -> tuple[set[str], set[str], set[str]]:
    """Return available, current, and superseded state receipt hashes."""

    available_receipt_hashes: set[str] = set()
    stale_receipt_hashes: set[str] = set()
    corrected_result_hashes: set[str] = set()

    for receipt in receipts:
        receipt_hash = receipt.get("receipt_hash")
        if isinstance(receipt_hash, str):
            available_receipt_hashes.add(receipt_hash)

        if receipt.get("type") != "correction_receipt":
            continue

        previous_hash = receipt.get("previous_receipt_hash")
        resulting_hash = receipt.get("resulting_receipt_hash")

        if isinstance(previous_hash, str):
            stale_receipt_hashes.add(previous_hash)

        if isinstance(resulting_hash, str):
            corrected_result_hashes.add(resulting_hash)

    current_receipt_hashes = (
        available_receipt_hashes - stale_receipt_hashes
    )

    return (
        current_receipt_hashes,
        stale_receipt_hashes,
        corrected_result_hashes,
    )


def _classify_candidate(
    candidate: Mapping[str, Any],
    *,
    receipt_by_hash: Mapping[str, Mapping[str, Any]],
    current_receipt_hashes: set[str],
    stale_receipt_hashes: set[str],
) -> tuple[str, str, set[str]]:
    """Classify one candidate and return its matching current evidence."""

    claim_id = _require_claim_id(
        candidate.get("claim_id"),
        "candidate claim_id",
    )
    evidence_hashes = _candidate_evidence_hashes(candidate)

    referenced_receipts = [
        receipt_by_hash[evidence_hash]
        for evidence_hash in evidence_hashes
        if evidence_hash in receipt_by_hash
    ]

    matching_receipt_hashes = {
        receipt["receipt_hash"]
        for receipt in referenced_receipts
        if receipt.get("claim_id") == claim_id
        and receipt.get("value") == candidate.get("value")
    }

    matched_current_hashes = (
        matching_receipt_hashes & current_receipt_hashes
    )

    if matched_current_hashes:
        return _SUPPORTED, claim_id, matched_current_hashes

    if matching_receipt_hashes & stale_receipt_hashes:
        return _STALE, claim_id, set()

    return _UNSUPPORTED, claim_id, set()


def evaluate_reconstruction(
    *,
    evidence_receipts: Iterable[Mapping[str, Any]],
    required_claim_ids: Iterable[str],
    candidate_claims: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify reconstructed claims against available evidence receipts."""

    receipts = list(evidence_receipts)
    candidates = list(candidate_claims)
    required = [
        _require_claim_id(claim_id, "required claim id")
        for claim_id in required_claim_ids
    ]

    graph = build_receipt_graph(receipts)
    receipt_by_hash = {
        receipt_hash: node["receipt"]
        for receipt_hash, node in graph.items()
    }

    (
        current_receipt_hashes,
        stale_receipt_hashes,
        corrected_result_hashes,
    ) = _receipt_state(receipts)

    supported_claim_indexes: list[int] = []
    stale_claim_indexes: list[int] = []
    unsupported_claim_indexes: list[int] = []
    supported_claim_ids: set[str] = set()
    reconstructed_current_hashes: set[str] = set()

    for index, candidate_value in enumerate(candidates):
        candidate = _require_mapping(candidate_value, "candidate claim")

        classification, claim_id, matched_current_hashes = (
            _classify_candidate(
                candidate,
                receipt_by_hash=receipt_by_hash,
                current_receipt_hashes=current_receipt_hashes,
                stale_receipt_hashes=stale_receipt_hashes,
            )
        )

        if classification == _SUPPORTED:
            supported_claim_indexes.append(index)
            supported_claim_ids.add(claim_id)
            reconstructed_current_hashes.update(matched_current_hashes)
        elif classification == _STALE:
            stale_claim_indexes.append(index)
        else:
            unsupported_claim_indexes.append(index)

    missing_required_claim_ids = [
        claim_id
        for claim_id in required
        if claim_id not in supported_claim_ids
    ]

    correction_survived = corrected_result_hashes.issubset(
        reconstructed_current_hashes
    )

    valid = (
        not stale_claim_indexes
        and not unsupported_claim_indexes
        and not missing_required_claim_ids
        and correction_survived
    )

    return {
        "supported_claim_indexes": supported_claim_indexes,
        "stale_claim_indexes": stale_claim_indexes,
        "unsupported_claim_indexes": unsupported_claim_indexes,
        "missing_required_claim_ids": missing_required_claim_ids,
        "correction_survived": correction_survived,
        "valid": valid,
    }