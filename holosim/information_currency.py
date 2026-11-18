
"""Read-only information currency projection."""

from __future__ import annotations

from typing import Any

from holosim.continuity_checkpoint import (
    build_continuity_checkpoint,
    verify_continuity_checkpoint_against_chain,
)
from holosim.core import HoloChain


def project_information_currency(chain: HoloChain) -> dict[str, Any]:
    """Project source-bound recorded claim states without granting truth or authority."""
    if not isinstance(chain, HoloChain):
        raise TypeError("chain must be a HoloChain")

    # Build and verify the existing deterministic continuity checkpoint.
    checkpoint = build_continuity_checkpoint(chain)
    verification = verify_continuity_checkpoint_against_chain(
        checkpoint, chain
    )

    if verification["source_verified"] is not True:
        raise ValueError("Checkpoint source was not verified")

    # Obtain an independently verified snapshot for receipt reconstruction.
    snapshot = chain._load_verified_snapshot()
    admission = chain._admit_verified_entries(snapshot)

    if admission["decision"] != "ADMITTED":
        raise ValueError("Source snapshot was not admitted")

    if not snapshot.entries:
        raise ValueError("Cannot project an empty source snapshot")

    # Bind the provenance snapshot to the verified checkpoint source.
    if (
        len(snapshot.entries) != checkpoint["source"]["total_entries"]
        or snapshot.entries[-1]["hash"] != verification["root_hash"]
    ):
        raise ValueError(
            "Projection source does not match verified checkpoint"
        )

    # Reconstruct and validate receipts from the same snapshot.
    entries, _, effective, receipts = chain._revalidation_view(
        list(snapshot.entries)
    )

    claims = []

    for claim in checkpoint["claims"]:
        checks = chain._revalidations_from_view(
            entries,
            effective,
            receipts,
            claim["idx"],
        )

        # Require receipt lineage to match the verified checkpoint.
        if [check["idx"] for check in checks] != claim["revalidation_history"]:
            raise ValueError(
                "Revalidation history does not match verified checkpoint"
            )

        current_checks = [
            check for check in checks if check["current"]
        ]
        latest = current_checks[-1] if current_checks else None

        expected_status = (
            latest["outcome"]
            if latest is not None
            else "STALE"
            if checks
            else "UNCHECKED"
        )

        if expected_status != claim["status"]:
            raise ValueError(
                "Recorded status does not match verified receipts"
            )

        expected_revalidated_by = (
            latest["idx"] if latest is not None else None
        )

        if expected_revalidated_by != claim.get("revalidated_by"):
            raise ValueError(
                "Applicable revalidation does not match checkpoint"
            )

        claims.append({
            "idx": claim["idx"],
            "content": claim["content"],
            "content_hash": claim["content_hash"],
            "recorded_status": claim["status"],
            "correction_history": list(
                claim["correction_history"]
            ),
            "revalidation_history": list(
                claim["revalidation_history"]
            ),
            "corrected_by": claim.get("corrected_by"),
            "revalidated_by": claim.get("revalidated_by"),
            "revalidations": [
                {
                    "idx": check["idx"],
                    "outcome": check["outcome"],
                    "method": check["method"],
                    "evidence": check["evidence"],
                    "subject_hash": check["subject_hash"],
                    "subject_correction_idx": check[
                        "subject_correction_idx"
                    ],
                    "current": check["current"],
                }
                for check in checks
            ],
            "environmental_currency": "UNKNOWN",
        })

    # Reobserve the source after provenance reconstruction.
    # Reject detected changes rather than returning mixed-source claims.
    final_entries = chain.load_and_verify()

    if (
        len(final_entries) != len(snapshot.entries)
        or not final_entries
        or final_entries[-1]["hash"] != verification["root_hash"]
    ):
        raise ValueError(
            "Projection source changed during reconstruction"
        )

    return {
        "type": "information_currency_projection",
        "version": 1,
        "source_root_hash": verification["root_hash"],
        "checkpoint_hash": verification["checkpoint_hash"],
        "source_verified": verification["source_verified"],
        "claims": claims,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
