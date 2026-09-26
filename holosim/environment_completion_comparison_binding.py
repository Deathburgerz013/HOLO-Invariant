"""Bind one completed environment boundary to one exact subsequent comparison."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash


RECEIPT_TYPE = "environment_completion_comparison_binding_receipt"
RECEIPT_VERSION = 1


class EnvironmentCompletionComparisonBindingError(ValueError):
    """Raised when a comparison cannot be bound to a completed boundary."""


def _instant(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise EnvironmentCompletionComparisonBindingError(
            f"{label} must be a timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EnvironmentCompletionComparisonBindingError(
            f"{label} is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise EnvironmentCompletionComparisonBindingError(
            f"{label} must include timezone"
        )
    return parsed


def _verify_certificate(certificate: Mapping[str, Any]) -> str:
    if not isinstance(certificate, Mapping):
        raise EnvironmentCompletionComparisonBindingError(
            "completion_certificate must be a mapping"
        )
    if certificate.get("type") != "environment_completion_certificate":
        raise EnvironmentCompletionComparisonBindingError(
            "completion certificate type is invalid"
        )
    if certificate.get("status") != "COMPLETE_ELIGIBLE":
        raise EnvironmentCompletionComparisonBindingError(
            "completion certificate must be COMPLETE_ELIGIBLE"
        )
    if certificate.get("evaluation_eligible") is not True:
        raise EnvironmentCompletionComparisonBindingError(
            "completion certificate must be evaluation eligible"
        )
    if (
        certificate.get("accepted") is not False
        or certificate.get("write_authority") != "NONE"
    ):
        raise EnvironmentCompletionComparisonBindingError(
            "completion certificate grants authority"
        )

    supplied = certificate.get("certificate_id")
    if not isinstance(supplied, str) or not supplied:
        raise EnvironmentCompletionComparisonBindingError(
            "completion certificate requires certificate_id"
        )
    try:
        expected = stable_hash(
            {k: v for k, v in certificate.items() if k != "certificate_id"}
        )
    except CanonicalValueError as exc:
        raise EnvironmentCompletionComparisonBindingError(str(exc)) from exc
    if supplied != expected:
        raise EnvironmentCompletionComparisonBindingError(
            "completion certificate identity mismatch"
        )
    return supplied


def _verify_comparison_identity(identity: Mapping[str, Any]) -> str:
    if not isinstance(identity, Mapping):
        raise EnvironmentCompletionComparisonBindingError(
            "comparison_identity must be a mapping"
        )
    if identity.get("type") != "check_identity":
        raise EnvironmentCompletionComparisonBindingError(
            "comparison identity type is invalid"
        )
    if identity.get("check_type") != "environment_snapshot_comparison":
        raise EnvironmentCompletionComparisonBindingError(
            "comparison identity check_type is invalid"
        )
    if (
        identity.get("accepted") is not False
        or identity.get("write_authority") != "NONE"
    ):
        raise EnvironmentCompletionComparisonBindingError(
            "comparison identity grants authority"
        )

    supplied = identity.get("check_identity_hash")
    if not isinstance(supplied, str) or not supplied:
        raise EnvironmentCompletionComparisonBindingError(
            "comparison identity requires check_identity_hash"
        )
    try:
        expected = stable_hash(
            {k: v for k, v in identity.items() if k != "check_identity_hash"}
        )
    except CanonicalValueError as exc:
        raise EnvironmentCompletionComparisonBindingError(str(exc)) from exc
    if supplied != expected:
        raise EnvironmentCompletionComparisonBindingError(
            "comparison identity hash mismatch"
        )
    return supplied


def bind_completion_to_comparison(
    *,
    completion_certificate: Mapping[str, Any],
    comparison_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind a comparison that begins exactly at a completed observation boundary."""
    certificate_id = _verify_certificate(completion_certificate)
    comparison_identity_hash = _verify_comparison_identity(comparison_identity)

    observations = completion_certificate.get("observation_hashes")
    if type(observations) is not list or not observations:
        raise EnvironmentCompletionComparisonBindingError(
            "completion certificate requires observation_hashes"
        )
    if not all(isinstance(value, str) and value for value in observations):
        raise EnvironmentCompletionComparisonBindingError(
            "observation_hashes must contain nonempty strings"
        )
    terminal_snapshot_id = observations[-1]

    references = comparison_identity.get("reference_ids")
    if type(references) is not list or len(references) != 2:
        raise EnvironmentCompletionComparisonBindingError(
            "comparison identity requires exactly two snapshot references"
        )
    if not all(isinstance(value, str) and value for value in references):
        raise EnvironmentCompletionComparisonBindingError(
            "comparison snapshot references must be nonempty strings"
        )

    subject = comparison_identity.get("subject")
    scope = comparison_identity.get("scope")
    if not isinstance(subject, Mapping) or not isinstance(scope, Mapping):
        raise EnvironmentCompletionComparisonBindingError(
            "comparison identity subject and scope are required"
        )

    environment_matches = (
        subject.get("environment_id")
        == completion_certificate.get("environment_id")
    )
    boundary_matches = references[0] == terminal_snapshot_id
    before_matches_window_end = (
        scope.get("before_observed_at")
        == completion_certificate.get("window_end")
    )
    after_is_later = _instant(
        scope.get("after_observed_at"),
        "after_observed_at",
    ) > _instant(
        completion_certificate.get("window_end"),
        "window_end",
    )

    binding_complete = (
        environment_matches
        and boundary_matches
        and before_matches_window_end
        and after_is_later
    )

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "completion_certificate_id": certificate_id,
        "comparison_check_identity_hash": comparison_identity_hash,
        "environment_id": completion_certificate["environment_id"],
        "terminal_snapshot_id": terminal_snapshot_id,
        "comparison_before_snapshot_id": references[0],
        "comparison_after_snapshot_id": references[1],
        "completion_window_end": completion_certificate["window_end"],
        "comparison_before_observed_at": scope.get("before_observed_at"),
        "comparison_after_observed_at": scope.get("after_observed_at"),
        "environment_matches": environment_matches,
        "boundary_matches": boundary_matches,
        "before_matches_window_end": before_matches_window_end,
        "after_is_later": after_is_later,
        "status": "BOUND" if binding_complete else "BOUNDARY_MISMATCH",
        "binding_complete": binding_complete,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "BOUND establishes only that the comparison begins at the exact "
            "terminal snapshot and time of this completed environment boundary "
            "and proceeds to a later observation. It does not establish "
            "relevance, satisfy a reopen condition, reopen an episode, "
            "establish truth, or grant authority."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_environment_completion_comparison_binding_receipt(
    receipt: Mapping[str, Any],
    *,
    completion_certificate: Mapping[str, Any],
    comparison_identity: Mapping[str, Any],
) -> bool:
    """Regenerate the boundary binding from exact inputs and require equality."""
    if type(receipt) is not dict:
        raise EnvironmentCompletionComparisonBindingError(
            "binding receipt must be a plain dictionary"
        )

    expected = bind_completion_to_comparison(
        completion_certificate=completion_certificate,
        comparison_identity=comparison_identity,
    )

    if set(receipt) != set(expected):
        raise EnvironmentCompletionComparisonBindingError(
            "binding receipt fields do not match"
        )
    if receipt != expected:
        raise EnvironmentCompletionComparisonBindingError(
            "binding receipt does not match supplied evidence"
        )
    return True
