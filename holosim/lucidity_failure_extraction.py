from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.bounded_evidence_analyst import (
    BoundedEvidenceAnalystError,
    verify_evidence_analysis_receipt,
)
from holosim.canonical import CanonicalValueError, stable_hash


RECEIPT_TYPE = "lucidity_failure_extraction_receipt"
RECEIPT_VERSION = 1


class LucidityFailureExtractionError(ValueError):
    """Raised when demonstrated failures cannot be extracted honestly."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise LucidityFailureExtractionError(str(exc)) from exc


def extract_demonstrated_failures(
    analysis_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract only contradictions already derived by a verified analysis receipt."""
    try:
        verify_evidence_analysis_receipt(analysis_receipt)
    except BoundedEvidenceAnalystError as exc:
        raise LucidityFailureExtractionError("analysis_receipt is invalid") from exc

    findings_by_id = {
        finding["finding_id"]: finding
        for finding in analysis_receipt["findings"]
    }
    evidence_by_id = {
        evidence["evidence_id"]: evidence
        for evidence in analysis_receipt["evidence"]
    }

    failures = []
    for result in analysis_receipt["finding_results"]:
        if result["status"] != "CONTRADICTED":
            continue

        finding = findings_by_id[result["finding_id"]]
        evidence_ids = list(result["contradicting_evidence_ids"])
        failures.append(
            {
                "finding_id": result["finding_id"],
                "statement": finding["statement"],
                "status": "CONTRADICTED",
                "status_reason": result["status_reason"],
                "contradicting_evidence_ids": evidence_ids,
                "contradicting_evidence": [
                    deepcopy(evidence_by_id[evidence_id])
                    for evidence_id in evidence_ids
                ],
            }
        )

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "source_analysis_id": analysis_receipt["analysis_id"],
        "source_receipt_hash": analysis_receipt["receipt_hash"],
        "source_evidence_set_hash": analysis_receipt["evidence_set_hash"],
        "failures": failures,
        "failure_count": len(failures),
        "status": (
            "DEMONSTRATED_FAILURES_EXTRACTED"
            if failures
            else "NO_DEMONSTRATED_FAILURE"
        ),
        "truth_claimed": False,
        "accepted": False,
        "selection_authority": "NONE",
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Lucidity extracts only findings already derived as CONTRADICTED by "
            "the supplied verified evidence-analysis receipt. It does not "
            "authenticate evidence, execute methods, infer additional failures, "
            "establish truth, recommend corrections, accept results, or grant "
            "selection, write, or execution authority."
        ),
    }
    return {**body, "receipt_hash": _hash(body)}


def verify_lucidity_failure_extraction(
    receipt: Mapping[str, Any],
    *,
    analysis_receipt: Mapping[str, Any],
) -> bool:
    """Rebuild extraction from its source analysis and require exact identity."""
    if type(receipt) is not dict:
        raise LucidityFailureExtractionError("receipt must be a plain object")

    expected = extract_demonstrated_failures(analysis_receipt)
    if dict(receipt) != expected:
        raise LucidityFailureExtractionError(
            "receipt does not match source analysis"
        )
    return True
