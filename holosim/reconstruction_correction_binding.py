"""Read-only identity binding between continuity reconstruction and correction."""

from copy import deepcopy
from typing import Any, Mapping

from holosim.bounded_claim_correction import validate_bounded_claim_correction
from holosim.canonical import stable_hash
from holosim.continuity_under_absence import reconstruct_continuity


class ReconstructionCorrectionBindingError(ValueError):
    """Reconstruction and correction cannot be safely bound."""


def build_reconstruction_correction_binding(
    *,
    continuity_receipt: Mapping[str, Any],
    external_evidence: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind independently validated inputs without granting authority."""
    try:
        reconstruction = reconstruct_continuity(
            continuity_receipt,
            external_evidence=external_evidence,
            collection_closed=True,
        )
        validate_bounded_claim_correction(proposal)

        pairs = (
            ("prior_state", "current_claims"),
            ("prior_state_hash", "baseline_state_hash"),
            ("current_state", "candidate_claims"),
            ("current_state_hash", "candidate_baseline_hash"),
        )

        for reconstruction_field, proposal_field in pairs:
            if reconstruction[reconstruction_field] != proposal[proposal_field]:
                raise ReconstructionCorrectionBindingError(
                    f"identity mismatch: {reconstruction_field}"
                )

        body = {
            "type": "reconstruction_correction_binding",
            "version": 1,
            "continuity_receipt": deepcopy(continuity_receipt),
            "external_evidence": deepcopy(external_evidence),
            "proposal": deepcopy(proposal),
            "reconstruction": deepcopy(reconstruction),
            "continuity_receipt_hash": continuity_receipt["receipt_hash"],
            "external_evidence_hash": external_evidence["receipt_hash"],
            "proposal_hash": proposal["proposal_hash"],
            "status": "IDENTITY_BOUND",
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
            "canonical_mutation": False,
            "correction_applied": False,
            "supersession_performed": False,
        }
        return {**body, "binding_hash": stable_hash(body)}

    except ReconstructionCorrectionBindingError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise ReconstructionCorrectionBindingError(
            f"binding inputs failed validation: {exc}"
        ) from exc


def validate_reconstruction_correction_binding(
    binding: Mapping[str, Any],
) -> bool:
    """Rebuild from source receipts and require exact identity."""
    if type(binding) is not dict:
        raise ReconstructionCorrectionBindingError("binding must be a dictionary")

    expected_fields = {
        "type", "version", "continuity_receipt", "external_evidence",
        "proposal", "reconstruction", "continuity_receipt_hash",
        "external_evidence_hash", "proposal_hash", "status",
        "accepted", "truth_claimed", "write_authority",
        "execution_authority", "canonical_mutation",
        "correction_applied", "supersession_performed", "binding_hash",
    }
    if set(binding) != expected_fields:
        raise ReconstructionCorrectionBindingError("binding fields mismatch")

    rebuilt = build_reconstruction_correction_binding(
        continuity_receipt=binding["continuity_receipt"],
        external_evidence=binding["external_evidence"],
        proposal=binding["proposal"],
    )
    if binding != rebuilt:
        raise ReconstructionCorrectionBindingError(
            "binding does not match validated inputs"
        )
    return True
