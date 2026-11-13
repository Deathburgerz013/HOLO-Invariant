
"""Restrict permitted observations using verified controller decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from holosim.functional_consciousness_experiment import (
    CAUSAL_ACTION_CONTINUE,
    verify_absence_model_receipt,
    verify_causal_controller_receipt,
)
from holosim.permitted_observation_host import PermittedObservationHost


@dataclass(frozen=True)
class ControllerObservationResult:
    decision: str
    reason: str
    classification: str
    evidence_valid: bool
    permit_verified: bool
    observation_performed: bool
    request_hash: str | None = None
    result_hash: str | None = None
    accepted: bool = False
    write_authority: str = "NONE"
    execution_authority: str = "NONE"


class ControllerPermittedObservation:
    """Restrict host-owned observations using verified controller evidence."""

    def __init__(self, *, host: PermittedObservationHost):
        if not isinstance(host, PermittedObservationHost):
            raise TypeError("host must be a PermittedObservationHost")

        self._host = host

    def observe(
        self,
        *,
        absence_receipt: Mapping[str, Any],
        controller_receipt: Mapping[str, Any],
        goal_reference: str,
        reference_state: str,
        candidates: Any,
        permit_occurrence: Any,
        expected_content: str,
    ) -> ControllerObservationResult:
        """A controller can restrict observation, never authorize it."""

        verify_absence_model_receipt(absence_receipt)
        verify_causal_controller_receipt(
            controller_receipt,
            absence_receipt=absence_receipt,
        )

        if (
            controller_receipt["controller_connected"] is not True
            or controller_receipt["declared_action"] != CAUSAL_ACTION_CONTINUE
        ):
            return ControllerObservationResult(
                decision="HALT_CONTROLLER",
                reason=(
                    "CONTROLLER_DISCONNECTED"
                    if controller_receipt["controller_connected"] is not True
                    else controller_receipt["declared_action"]
                ),
                classification="UNAVAILABLE",
                evidence_valid=False,
                permit_verified=False,
                observation_performed=False,
            )

        result = self._host.observe(
            goal_reference=goal_reference,
            reference_state=reference_state,
            candidates=candidates,
            permit_occurrence=permit_occurrence,
            expected_content=expected_content,
        )

        return ControllerObservationResult(
            decision=result.decision,
            reason=result.reason,
            classification=result.classification,
            evidence_valid=result.evidence_valid,
            permit_verified=result.permit_verified,
            observation_performed=result.observation_performed,
            request_hash=result.request_hash,
            result_hash=result.result_hash,
        )
