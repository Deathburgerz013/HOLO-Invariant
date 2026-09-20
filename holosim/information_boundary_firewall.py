"""Fail-closed information boundary firewall for HOLO/Sim.

Information may not be promoted across a semantic boundary merely because it
exists or has source provenance. Crossing requires the evidence explicitly
required by the requested boundary.
"""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import stable_hash

from holosim.time_scoped_truth import TimeScopedTruthError, verify_time_scoped_truth_receipt

from holosim.extraction_claim_binding import (
    ExtractionClaimBindingError,
    verify_extraction_claim_correspondence,
)


class InformationBoundaryFirewallError(ValueError):
    """Raised when information cannot cross a requested boundary."""


def evaluate_information_crossing(
    *,
    information: Mapping[str, Any],
    requested_boundary: str,
    verification_receipt: Mapping[str, Any] | None,
    claim_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one requested information-boundary crossing fail-closed."""
    if requested_boundary == "VERIFIED_TRUTH":
        if verification_receipt is None:
            raise InformationBoundaryFirewallError(
                "verified truth requires an explicit verification receipt"
            )
        if (
            type(verification_receipt) is not dict
            or verification_receipt.get("type") != "time_scoped_truth_state_receipt"
            or verification_receipt.get("version") != 1
        ):
            raise InformationBoundaryFirewallError(
                "verification receipt is not supported"
            )
        if claim_binding is None:
            raise InformationBoundaryFirewallError(
                "verified truth requires an exact extraction-to-claim binding"
            )
        try:
            verify_extraction_claim_correspondence(
                claim_binding,
                extraction_hash=information["extraction_hash"],
                claim_id=verification_receipt["claim"]["claim_id"],
            )
        except ExtractionClaimBindingError as exc:
            raise InformationBoundaryFirewallError(str(exc)) from exc

        try:
            verify_time_scoped_truth_receipt(verification_receipt)
        except TimeScopedTruthError as exc:
            raise InformationBoundaryFirewallError(
                f"verified truth receipt is invalid: {exc}"
            ) from exc

        if (
            verification_receipt["truth_status"] != "TRUE"
            or verification_receipt["bounded_truth_established"] is not True
        ):
            raise InformationBoundaryFirewallError(
                "verified truth boundary requires bounded TRUE"
            )

        body = {
            "type": "information_boundary_crossing",
            "version": 1,
            "status": "PERMITTED",
            "boundary": "VERIFIED_TRUTH",
            "extraction_hash": information["extraction_hash"],
            "claim_id": verification_receipt["claim"]["claim_id"],
            "truth_receipt_hash": verification_receipt["receipt_hash"],
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }
        return {**body, "crossing_hash": stable_hash(body)}

    raise InformationBoundaryFirewallError(
        "requested information boundary is not supported"
    )



def verify_information_crossing(
    crossing: Mapping[str, Any],
    *,
    information: Mapping[str, Any],
    verification_receipt: Mapping[str, Any],
    claim_binding: Mapping[str, Any],
) -> bool:
    """Reconstruct one permitted crossing and reject semantic tampering."""
    expected_fields = {
        "type", "version", "status", "boundary", "extraction_hash",
        "claim_id", "truth_receipt_hash", "write_authority",
        "execution_authority", "crossing_hash",
    }
    if type(crossing) is not dict or set(crossing) != expected_fields:
        raise InformationBoundaryFirewallError("crossing fields mismatch")

    expected = evaluate_information_crossing(
        information=information,
        requested_boundary=crossing["boundary"],
        verification_receipt=verification_receipt,
        claim_binding=claim_binding,
    )
    if dict(crossing) != expected:
        raise InformationBoundaryFirewallError(
            "crossing is internally inconsistent"
        )
    return True
