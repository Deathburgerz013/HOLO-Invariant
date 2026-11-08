"""Bounded, read-only decision cycle for the concrete runtime.

This module evaluates INV transitions but grants no execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from holosim.inv_runtime import (
    GreaterThanOrEqualInvariant,
    INVTransition,
    execute_inv_transition_with_receipt,
    verify_transition_receipt,
)


@dataclass(frozen=True)
class RuntimeDecision:
    status: str
    reason: str
    validation: int
    previous_state: int | None
    candidate_state: int | None
    resulting_state: int | None
    invariant_accepted: bool
    receipt_verified: bool
    accepted: bool = False
    write_authority: str = "NONE"
    execution_authority: str = "NONE"


def evaluate_runtime_cycle(
    *,
    state: int,
    transition: INVTransition,
    invariant: GreaterThanOrEqualInvariant,
) -> RuntimeDecision:
    """Recheck one transition without performing an external effect."""

    def blocked(reason, *, previous=None, candidate=None):
        return RuntimeDecision(
            status="BLOCKED",
            reason=reason,
            validation=0,
            previous_state=previous,
            candidate_state=candidate,
            resulting_state=previous,
            invariant_accepted=False,
            receipt_verified=False,
        )

    if type(state) is not int:
        return blocked("INVALID_INITIAL_STATE")

    try:
        receipt = execute_inv_transition_with_receipt(
            state=state,
            transition=transition,
            invariant=invariant,
        )
    except (ValueError, TypeError, OverflowError, ArithmeticError):
        return blocked("TRANSITION_EVALUATION_FAILED", previous=state)

    try:
        receipt_verified = verify_transition_receipt(receipt)
    except (ValueError, TypeError, OverflowError, ArithmeticError):
        receipt_verified = False

    if not receipt_verified:
        return blocked(
            "RECEIPT_VERIFICATION_FAILED",
            previous=state,
        )

    reason = (
        "NO_EXECUTION_AUTHORITY"
        if receipt.accepted
        else "INVARIANT_REJECTED"
    )

    return RuntimeDecision(
        status="BLOCKED",
        reason=reason,
        validation=0,
        previous_state=receipt.previous_state,
        candidate_state=receipt.candidate_state,
        resulting_state=receipt.previous_state,
        invariant_accepted=receipt.accepted,
        receipt_verified=True,
    )


@dataclass(frozen=True)
class PermittedRuntimeObservation:
    decision: str
    reason: str
    classification: str
    evidence_valid: bool
    permit_verified: bool
    observation_performed: bool
    request_hash: str | None
    result_hash: str | None
    accepted: bool = False
    write_authority: str = "NONE"
    execution_authority: str = "NONE"


def run_concrete_permitted_observation(
    *,
    goal_reference,
    reference_state,
    candidates,
    allowed_root,
    observed_at,
    permit_occurrence,
    permit_source_secrets,
    seen_occurrence_ids,
    permit_registry_path,
    expected_content,
) -> PermittedRuntimeObservation:
    """Perform a permitted observation before comparing its evidence.

    The caller cannot supply an observation result or verification receipt.
    This is an in-process boundary, not independently authenticated provenance.
    """
    from holosim.observation_permit import run_permitted_aligned_observation

    if type(expected_content) is not str:
        return PermittedRuntimeObservation(
            decision="HALT_INVALID_INPUT",
            reason="INVALID_EXPECTED_CONTENT",
            classification="UNAVAILABLE",
            evidence_valid=False,
            permit_verified=False,
            observation_performed=False,
            request_hash=None,
            result_hash=None,
        )

    run = run_permitted_aligned_observation(
        goal_reference=goal_reference,
        reference_state=reference_state,
        candidates=candidates,
        allowed_root=allowed_root,
        observed_at=observed_at,
        permit_occurrence=permit_occurrence,
        permit_source_secrets=permit_source_secrets,
        seen_occurrence_ids=seen_occurrence_ids,
        permit_registry_path=permit_registry_path,
    )

    verification = run["permit_verification"]
    permit_verified = (
        verification is not None
        and verification["verified"] is True
        and verification["status"] == "VERIFIED"
    )

    if (
        run["decision"] != "OBSERVED"
        or run["observation_performed"] is not True
        or not permit_verified
        or run["observation_result"] is None
    ):
        return PermittedRuntimeObservation(
            decision=run["decision"],
            reason=run["reason"],
            classification="UNAVAILABLE",
            evidence_valid=False,
            permit_verified=permit_verified,
            observation_performed=run["observation_performed"],
            request_hash=None,
            result_hash=None,
        )

    @dataclass(frozen=True)
    class ObservationComparison:
        classification: str
        reason: str
        request_hash: str | None
        result_hash: str | None
        evidence_valid: bool
        accepted: bool = False
        write_authority: str = "NONE"
        execution_authority: str = "NONE"

    def compare_observed_result(
        *,
        request,
        result,
        expected_content: str,
    ) -> ObservationComparison:
        """Compare one validated hook result with expected UTF-8 content.

        This returns MATCH or MISMATCH for reported evidence only. It does not establish that
        an observation was permitted, fresh, or independently reproduced.
        """
        from holosim.hook_contract import (
            HookContractError,
            validate_hook_request,
            validate_hook_result,
        )

        if type(expected_content) is not str:
            raise ValueError("expected_content must be a string")

        try:
            validate_hook_request(request)
            validate_hook_result(result, request=request)
        except (HookContractError, TypeError, ValueError):
            return ObservationComparison(
                classification="UNAVAILABLE",
                reason="INVALID_OBSERVATION_CONTRACT",
                request_hash=None,
                result_hash=None,
                evidence_valid=False,
            )

        request_hash = request["request_hash"]
        result_hash = result["result_hash"]

        if (
            request["action"] != "read_text"
            or request["payload"] != {"encoding": "utf-8"}
        ):
            return ObservationComparison(
                classification="UNAVAILABLE",
                reason="UNSUPPORTED_OBSERVATION_ACTION",
                request_hash=request_hash,
                result_hash=result_hash,
                evidence_valid=False,
            )

        if result["status"] != "OBSERVED":
            return ObservationComparison(
                classification="UNAVAILABLE",
                reason=f"OBSERVATION_{result['status']}",
                request_hash=request_hash,
                result_hash=result_hash,
                evidence_valid=False,
            )

        evidence = result["evidence"]
        if (
            evidence.get("operation") != "read_text"
            or evidence.get("reference") != request["reference"]
            or evidence.get("encoding") != "utf-8"
            or type(evidence.get("content")) is not str
        ):
            return ObservationComparison(
                classification="UNAVAILABLE",
                reason="INVALID_READ_TEXT_EVIDENCE",
                request_hash=request_hash,
                result_hash=result_hash,
                evidence_valid=False,
            )

        import hashlib

        content_bytes = evidence["content"].encode("utf-8")
        if (
            type(evidence.get("byte_count")) is not int
            or evidence["byte_count"] != len(content_bytes)
            or evidence.get("content_sha256")
            != hashlib.sha256(content_bytes).hexdigest()
        ):
            return ObservationComparison(
                classification="UNAVAILABLE",
                reason="CONTENT_INTEGRITY_MISMATCH",
                request_hash=request_hash,
                result_hash=result_hash,
                evidence_valid=False,
            )

        matches = evidence["content"] == expected_content

        return ObservationComparison(
            classification="MATCH" if matches else "MISMATCH",
            reason="CONTENT_MATCH" if matches else "CONTENT_MISMATCH",
            request_hash=request_hash,
            result_hash=result_hash,
            evidence_valid=True,
        )




    request = run["selection"]["selected_request"]
    comparison = compare_observed_result(
        request=request,
        result=run["observation_result"],
        expected_content=expected_content,
    )

    return PermittedRuntimeObservation(
        decision=run["decision"],
        reason=comparison.reason,
        classification={
            "MATCH": "SUPPORTED",
            "MISMATCH": "CONTRADICTED",
            "UNAVAILABLE": "UNAVAILABLE",
        }[comparison.classification],
        evidence_valid=comparison.evidence_valid,
        permit_verified=True,
        observation_performed=True,
        request_hash=comparison.request_hash,
        result_hash=comparison.result_hash,
    )
