"""Read-only association of absence evidence with a persisted correction."""

from __future__ import annotations

from typing import Any, Mapping

from holosim.absence_claim_correction_binding import (
    AbsenceClaimCorrectionBindingError,
    validate_absence_claim_correction_binding,
)
from holosim.canonical import CanonicalValueError, stable_hash
from holosim.persistent_baseline_transition import (
    PersistentBaselineTransitionError,
    PersistentBaselineTransitionStore,
    validate_persisted_verified_claim_correction_read,
)


ATTESTATION_TYPE = "persisted_absence_correction_attestation"
ATTESTATION_VERSION = 1


class PersistedAbsenceCorrectionAttestationError(ValueError):
    """Absence evidence cannot be associated with a persisted correction."""


def build_persisted_absence_correction_attestation(
    *,
    store: PersistentBaselineTransitionStore,
    record_id: str,
    continuity_receipt: Mapping[str, Any],
    external_evidence: Mapping[str, Any],
    absence_binding: Mapping[str, Any],
) -> dict[str, Any]:
    """Associate validated absence evidence with a freshly verified store record.

    This is a post-persistence association. It does not establish that absence
    evidence was checked before commit or that events during absence are known.
    """
    try:
        read = store.read_verified_claim_correction(record_id=record_id)
        validate_persisted_verified_claim_correction_read(read)

        authorized = read["record"]["authorized_correction"]
        candidate = authorized["transition_binding"]

        validate_absence_claim_correction_binding(
            absence_binding,
            continuity_receipt=continuity_receipt,
            external_evidence=external_evidence,
            transition_candidate=candidate,
        )

        if (
            candidate["binding_hash"] != authorized["binding_hash"]
            or candidate["previous_baseline_state_hash"]
            != authorized["previous_baseline_state_hash"]
            or candidate["next_baseline_state_hash"]
            != authorized["next_baseline_state_hash"]
        ):
            raise PersistedAbsenceCorrectionAttestationError(
                "persisted correction identity mismatch"
            )

        body = {
            "type": ATTESTATION_TYPE,
            "version": ATTESTATION_VERSION,
            "record_id": read["record_id"],
            "chain_entry_hash": read["chain_entry_hash"],
            "transition_binding_hash": absence_binding[
                "transition_binding_hash"
            ],
            "absence_binding_hash": absence_binding["binding_hash"],
            "continuity_receipt_hash": absence_binding[
                "continuity_receipt_hash"
            ],
            "external_evidence_hash": absence_binding[
                "external_evidence_hash"
            ],
            "previous_baseline_state_hash": absence_binding[
                "prior_state_hash"
            ],
            "next_baseline_state_hash": absence_binding[
                "current_state_hash"
            ],
            "post_persistence_association": True,
            "precommit_evidence_checked": False,
            "absence_interval_observed": False,
            "absence_interval_reconstructed": False,
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
            "canonical_mutation": False,
        }
        return {**body, "attestation_hash": stable_hash(body)}

    except PersistedAbsenceCorrectionAttestationError:
        raise
    except (
        AbsenceClaimCorrectionBindingError,
        PersistentBaselineTransitionError,
        CanonicalValueError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise PersistedAbsenceCorrectionAttestationError(
            f"attestation verification failed: {exc}"
        ) from exc


def validate_persisted_absence_correction_attestation(
    attestation: Mapping[str, Any],
    *,
    store: PersistentBaselineTransitionStore,
    continuity_receipt: Mapping[str, Any],
    external_evidence: Mapping[str, Any],
    absence_binding: Mapping[str, Any],
) -> bool:
    """Rebuild against the verified store and require exact attestation identity."""
    if type(attestation) is not dict:
        raise PersistedAbsenceCorrectionAttestationError(
            "attestation must be a plain dictionary"
        )

    expected = build_persisted_absence_correction_attestation(
        store=store,
        record_id=attestation.get("record_id"),
        continuity_receipt=continuity_receipt,
        external_evidence=external_evidence,
        absence_binding=absence_binding,
    )
    if attestation != expected:
        raise PersistedAbsenceCorrectionAttestationError(
            "attestation schema or identity mismatch"
        )
    return True
