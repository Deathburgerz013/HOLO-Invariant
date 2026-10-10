"""Bind a directional contradiction to its exact interpretation target.

Structural provenance only. This does not authenticate historical execution,
establish semantic truth, accept a claim, or grant write authority.
"""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.verified_directional_check_outcome import (
    build_verified_directional_check_outcome,
)


class InterpretationSubtractionTargetError(ValueError):
    """Raised when subtraction evidence fails its declared target checks."""


def _verified_hash(artifact: Mapping[str, Any], field: str) -> str:
    if not isinstance(artifact, Mapping):
        raise InterpretationSubtractionTargetError("artifact must be a mapping")

    supplied = artifact.get(field)
    if not isinstance(supplied, str) or not supplied:
        raise InterpretationSubtractionTargetError(f"missing {field}")

    body = {k: v for k, v in artifact.items() if k != field}

    try:
        expected = stable_hash(body)
    except (CanonicalValueError, ValueError, TypeError) as exc:
        raise InterpretationSubtractionTargetError(
            f"invalid {field} payload"
        ) from exc

    if supplied != expected:
        raise InterpretationSubtractionTargetError(f"{field} mismatch")

    return supplied


def verify_interpretation_subtraction_target(
    *,
    observation_id: str,
    interpretation_id: str,
    check_identity: Mapping[str, Any],
    directional_outcome: Mapping[str, Any],
    execution_receipt: Mapping[str, Any] | None = None,
    result_binding: Mapping[str, Any] | None = None,
    evaluation_rule: Mapping[str, Any] | None = None,
    expected_input_state_hash: str | None = None,
) -> dict[str, Any]:
    """Verify exact target linkage and reconstruct the directional result."""

    if not isinstance(observation_id, str) or not observation_id.strip():
        raise InterpretationSubtractionTargetError("invalid observation_id")
    if not isinstance(interpretation_id, str) or not interpretation_id.strip():
        raise InterpretationSubtractionTargetError("invalid interpretation_id")

    identity_hash = _verified_hash(check_identity, "check_identity_hash")

    if (
        check_identity.get("type") != "check_identity"
        or check_identity.get("version") != 1
    ):
        raise InterpretationSubtractionTargetError("invalid check identity")

    subject = check_identity.get("subject")
    scope = check_identity.get("scope")

    if not isinstance(subject, Mapping) or not isinstance(scope, Mapping):
        raise InterpretationSubtractionTargetError("missing subject or scope")

    if (
        subject.get("observation_id") != observation_id
        or subject.get("interpretation_id") != interpretation_id
        or scope.get("observation_id") != observation_id
    ):
        raise InterpretationSubtractionTargetError("interpretation target mismatch")

    if expected_input_state_hash is not None:
        if (
            not isinstance(expected_input_state_hash, str)
            or len(expected_input_state_hash) != 64
            or any(c not in "0123456789abcdef" for c in expected_input_state_hash)
            or check_identity.get("input_state_hash") != expected_input_state_hash
        ):
            raise InterpretationSubtractionTargetError(
                "input state identity mismatch"
            )

    outcome_hash = _verified_hash(directional_outcome, "outcome_hash")

    if (
        execution_receipt is None
        or result_binding is None
        or evaluation_rule is None
    ):
        raise InterpretationSubtractionTargetError(
            "complete directional evidence bundle required"
        )

    try:
        reconstructed = build_verified_directional_check_outcome(
            execution_receipt=execution_receipt,
            result_binding=result_binding,
            evaluation_rule=evaluation_rule,
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise InterpretationSubtractionTargetError(
            "directional evidence reconstruction failed"
        ) from exc

    if (
        reconstructed != directional_outcome
        or reconstructed["outcome_hash"] != outcome_hash
    ):
        raise InterpretationSubtractionTargetError(
            "directional outcome does not match reconstructed evidence"
        )

    if (
        reconstructed["check_id"] != check_identity.get("check_id")
        or reconstructed["check_identity_hash"] != identity_hash
    ):
        raise InterpretationSubtractionTargetError("check identity mismatch")

    if reconstructed["outcome"] != "CONTRADICTS":
        raise InterpretationSubtractionTargetError(
            "outcome does not contradict target"
        )

    body = {
        "type": "interpretation_subtraction_target_binding",
        "version": 1,
        "observation_id": observation_id,
        "interpretation_id": interpretation_id,
        "check_identity_hash": identity_hash,
        "directional_outcome_hash": outcome_hash,
        "target_binding_verified": True,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }

    return {**body, "binding_hash": stable_hash(body)}


def interpretation_subtraction_state_hash(
    *,
    observation_id: str,
    interpretations: list[str] | tuple[str, ...],
) -> str:
    """Identify declared starting interpretation membership, not truth."""
    if not isinstance(observation_id, str) or not observation_id.strip():
        raise InterpretationSubtractionTargetError("invalid observation_id")

    if not isinstance(interpretations, (list, tuple)):
        raise InterpretationSubtractionTargetError("invalid interpretations")

    if (
        any(not isinstance(item, str) or not item.strip() for item in interpretations)
        or len(set(interpretations)) != len(interpretations)
    ):
        raise InterpretationSubtractionTargetError("invalid interpretation membership")

    return stable_hash({
        "type": "interpretation_subtraction_input_state",
        "version": 1,
        "observation_id": observation_id,
        "interpretations": list(interpretations),
    })
