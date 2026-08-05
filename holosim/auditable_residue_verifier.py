"""Deterministic verification of auditable continuity residue.

The verifier checks whether contradictions preserved in a source record
remain visible and unchanged in a reconstructed state. It grants no
continuity, truth, acceptance, write, or execution authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import stable_hash


RECEIPT_TYPE = "auditable_residue_verification_receipt"
RECEIPT_VERSION = 1


class AuditableResidueVerifier:
    """Verify that recorded contradictions survive reconstruction unchanged."""

    def __init__(self) -> None:
        self.last_receipt: dict[str, Any] | None = None

    def __call__(
        self,
        *,
        preserved_record: Mapping[str, Any],
        reconstructed_state: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(preserved_record, Mapping):
            raise TypeError("preserved_record must be a mapping")

        if not isinstance(reconstructed_state, Mapping):
            raise TypeError("reconstructed_state must be a mapping")

        preserved = deepcopy(dict(preserved_record))
        reconstructed = deepcopy(dict(reconstructed_state))

        preserved_contradictions = self._contradictions_by_id(
            preserved.get("contradictions", [])
        )
        reconstructed_contradictions = self._contradictions_by_id(
            reconstructed.get("contradictions", [])
        )

        omitted = sorted(
            set(preserved_contradictions)
            - set(reconstructed_contradictions)
        )

        rewritten = sorted(
            contradiction_id
            for contradiction_id in (
                set(preserved_contradictions)
                & set(reconstructed_contradictions)
            )
            if stable_hash(
                preserved_contradictions[contradiction_id]
            )
            != stable_hash(
                reconstructed_contradictions[contradiction_id]
            )
        )

        if omitted:
            verified = False
            reason = "RECORDED_CONTRADICTION_OMITTED"
        elif rewritten:
            verified = False
            reason = "RECORDED_CONTRADICTION_REWRITTEN"
        else:
            verified = True
            reason = "AUDITABLE_RESIDUE_VERIFIED"

        body: dict[str, Any] = {
            "type": RECEIPT_TYPE,
            "version": RECEIPT_VERSION,
            "preserved_record": preserved,
            "reconstructed_state": reconstructed,
            "verified": verified,
            "continuity_claimed": False,
            "reason": reason,
            "omitted_contradiction_ids": omitted,
            "rewritten_contradiction_ids": rewritten,
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }

        receipt = {
            **body,
            "receipt_hash": stable_hash(body),
        }

        self.last_receipt = deepcopy(receipt)
        return receipt

    @staticmethod
    def _contradictions_by_id(
        contradictions: Any,
    ) -> dict[str, dict[str, Any]]:
        if not isinstance(contradictions, list):
            raise TypeError("contradictions must be a list")

        indexed: dict[str, dict[str, Any]] = {}

        for contradiction in contradictions:
            if not isinstance(contradiction, Mapping):
                raise TypeError(
                    "each contradiction must be a mapping"
                )

            contradiction_record = deepcopy(
                dict(contradiction)
            )
            contradiction_id = contradiction_record.get("id")

            if (
                not isinstance(contradiction_id, str)
                or not contradiction_id.strip()
            ):
                raise ValueError(
                    "each contradiction must have a non-empty id"
                )

            if contradiction_id in indexed:
                raise ValueError(
                    "contradiction ids must be unique"
                )

            indexed[contradiction_id] = contradiction_record

        return indexed


def build_auditable_residue_verifier(
    **kwargs: Any,
) -> AuditableResidueVerifier:
    """Build one auditable residue verifier."""

    return AuditableResidueVerifier(**kwargs)
