"""Strict, read-only verification of interpretation contractions.

Requires reconstructed target evidence for every removed interpretation.
Does not establish semantic truth or grant execution/write authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from holosim.bounded_investigation_continuity import (
    InvestigationContinuityError,
    bind_investigation_continuity,
)
from holosim.canonical import stable_hash
from holosim.interpretation_set_receipt import InterpretationSetReceipt
from holosim.interpretation_subtraction_target_binding import (
    interpretation_subtraction_state_hash,
    verify_interpretation_subtraction_target,
)


def bind_strict_interpretation_continuity(
    *,
    investigation_id: str,
    question: str,
    interpretation_before: InterpretationSetReceipt,
    distinguishability_receipt: Mapping[str, Any],
    interpretation_after: InterpretationSetReceipt,
    evidence_bundles: Sequence[Mapping[str, Any]],
    next_check_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Require target- and state-bound evidence for every contraction."""

    if not isinstance(interpretation_before, InterpretationSetReceipt):
        raise InvestigationContinuityError("invalid starting interpretation receipt")

    if not isinstance(interpretation_after, InterpretationSetReceipt):
        raise InvestigationContinuityError("invalid ending interpretation receipt")

    if (
        interpretation_before.observation_id
        != interpretation_after.observation_id
    ):
        raise InvestigationContinuityError("observation identity changed")

    before = tuple(interpretation_before.current_set)
    after = tuple(interpretation_after.current_set)
    removed = set(before) - set(after)

    if (
        isinstance(evidence_bundles, (str, bytes))
        or not isinstance(evidence_bundles, (list, tuple))
    ):
        raise InvestigationContinuityError("invalid evidence bundles")

    try:
        state_hash = interpretation_subtraction_state_hash(
            observation_id=interpretation_before.observation_id,
            interpretations=before,
        )
    except ValueError as exc:
        raise InvestigationContinuityError("invalid starting state") from exc

    for subtraction in interpretation_after.subtract_receipts:
        if (
            not isinstance(subtraction, Mapping)
            or not isinstance(subtraction.get("member"), str)
            or not subtraction["member"].strip()
            or not isinstance(subtraction.get("evidence_receipt_hash"), str)
            or not subtraction["evidence_receipt_hash"]
        ):
            raise InvestigationContinuityError(
                "unverified subtraction receipt"
            )

    verified = set()
    verified_binding_pairs = set()

    for bundle in evidence_bundles:
        if not isinstance(bundle, Mapping):
            raise InvestigationContinuityError("invalid evidence bundle")

        member = bundle.get("interpretation_id")

        if not isinstance(member, str) or member not in removed:
            raise InvestigationContinuityError("evidence target is not removed")

        try:
            binding = verify_interpretation_subtraction_target(
                observation_id=interpretation_before.observation_id,
                interpretation_id=member,
                check_identity=bundle["check_identity"],
                directional_outcome=bundle["directional_outcome"],
                execution_receipt=bundle["execution_receipt"],
                result_binding=bundle["result_binding"],
                evaluation_rule=bundle["evaluation_rule"],
                expected_input_state_hash=state_hash,
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise InvestigationContinuityError(
                "subtraction evidence verification failed"
            ) from exc

        matching_receipts = [
            receipt
            for receipt in interpretation_after.subtract_receipts
            if (
                receipt.get("member") == member
                and receipt.get("evidence_receipt_hash")
                == binding["binding_hash"]
            )
        ]

        if not matching_receipts:
            raise InvestigationContinuityError(
                "subtraction evidence hash does not match verified binding"
            )

        if binding["binding_hash"] not in interpretation_after.evidence_receipt_hashes:
            raise InvestigationContinuityError(
                "verified binding is absent from evidence set"
            )

        verified.add(member)
        verified_binding_pairs.add((member, binding["binding_hash"]))

    if verified != removed:
        raise InvestigationContinuityError(
            "not every removed interpretation has verified evidence"
        )

    for subtraction in interpretation_after.subtract_receipts:
        if not isinstance(subtraction, Mapping):
            raise InvestigationContinuityError(
                "unverified subtraction receipt"
            )

        member = subtraction.get("member")
        evidence_hash = subtraction.get("evidence_receipt_hash")

        if (member, evidence_hash) not in verified_binding_pairs:
            raise InvestigationContinuityError(
                "unverified subtraction receipt"
            )

    receipt = bind_investigation_continuity(
        investigation_id=investigation_id,
        question=question,
        interpretation_before=interpretation_before,
        distinguishability_receipt=distinguishability_receipt,
        interpretation_after=interpretation_after,
        next_check_receipt=next_check_receipt,
    )

    body = {
        **{key: value for key, value in receipt.items() if key != "receipt_hash"},
        "type": "strict_interpretation_continuity",
        "strict_target_verification": True,
        "verified_removed_interpretations": sorted(verified),
        "legacy_continuity_receipt_hash": receipt["receipt_hash"],
    }

    return {**body, "receipt_hash": stable_hash(body)}
