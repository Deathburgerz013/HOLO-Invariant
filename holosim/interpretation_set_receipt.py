"""Immutable, non-authoritative interpretation-set receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class InterpretationSetReceipt:
    """
    Preserve surviving interpretations without allowing rank-only collapse.

    Membership may shrink only through an explicit subtraction receipt whose
    evidence receipt hash is present in the supplied verified evidence set.

    Justification notices document reasoning and provenance. They do not,
    by themselves, mutate the interpretation set.
    """

    observation_id: str
    prior_set: Sequence[str]
    ranks: Mapping[str, float]
    subtract_receipts: Sequence[Mapping[str, Any]]
    justification_notices: Sequence[Mapping[str, Any]] = ()
    evidence_receipt_hashes: Sequence[str] = ()

    @property
    def current_set(self) -> tuple[str, ...]:
        prior = tuple(self.prior_set)
        known_evidence = set(self.evidence_receipt_hashes)
        eliminated: set[str] = set()

        for receipt in self.subtract_receipts:
            member = receipt.get("member")
            evidence_hash = receipt.get("evidence_receipt_hash")

            if member not in prior:
                continue

            if not isinstance(evidence_hash, str):
                continue

            if evidence_hash not in known_evidence:
                continue

            eliminated.add(member)

        return tuple(
            member
            for member in prior
            if member not in eliminated
        )