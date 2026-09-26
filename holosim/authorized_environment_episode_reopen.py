"""Bind one authorized environment episode reopen to one exact reopen receipt."""

from __future__ import annotations

from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.environment_reopen_condition import (
    verify_environment_reopen_condition_receipt,
)
from holosim.environment_episode_reopen_receipt import verify_reopen_receipt
from holosim.typed_operational_authorization import (
    ACTION_ENVIRONMENT_EPISODE_REOPEN,
    OperationalAuthorizationError,
    validate_operational_authorization,
)


RECEIPT_TYPE = "authorized_environment_episode_reopen_receipt"
RECEIPT_VERSION = 1


class AuthorizedEnvironmentEpisodeReopenError(ValueError):
    """Raised when reopen authorization does not bind exactly."""


def authorize_environment_episode_reopen(
    *,
    condition_receipt: Mapping[str, Any],
    comparison_identity: Mapping[str, Any],
    request: Mapping[str, Any],
    result: Mapping[str, Any],
    reopen_receipt: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind exact satisfied reopen evidence to exact external authorization."""

    try:
        verify_environment_reopen_condition_receipt(
            condition_receipt,
            condition_id=condition_receipt.get("condition_id"),
            comparison_identity=comparison_identity,
            request=request,
            result=result,
        )
    except Exception as exc:
        raise AuthorizedEnvironmentEpisodeReopenError(
            f"condition receipt is invalid: {exc}"
        ) from exc

    if condition_receipt["outcome"] != "SATISFIED":
        raise AuthorizedEnvironmentEpisodeReopenError(
            "reopen condition must be SATISFIED"
        )

    try:
        reopen_verification = verify_reopen_receipt(reopen_receipt)
    except Exception as exc:
        raise AuthorizedEnvironmentEpisodeReopenError(
            f"reopen receipt verification failed: {exc}"
        ) from exc

    if reopen_verification.get("valid") is not True:
        raise AuthorizedEnvironmentEpisodeReopenError(
            "reopen receipt did not verify"
        )

    target_hash = reopen_receipt["receipt_id"]

    try:
        validate_operational_authorization(
            authorization,
            expected_action=ACTION_ENVIRONMENT_EPISODE_REOPEN,
            expected_target_sha256=target_hash,
        )
    except OperationalAuthorizationError as exc:
        raise AuthorizedEnvironmentEpisodeReopenError(
            f"operational authorization is invalid: {exc}"
        ) from exc

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "condition_receipt_hash": condition_receipt["receipt_hash"],
        "comparison_check_identity_hash": comparison_identity[
            "check_identity_hash"
        ],
        "reopen_receipt_id": reopen_receipt["receipt_id"],
        "authorization_hash": authorization["authorization_hash"],
        "authorized_by_actor_id": authorization["actor_id"],
        "authorization_action": authorization["action"],
        "authorization_target_sha256": authorization["target_sha256"],
        "status": "AUTHORIZED",
        "authorization_requested": False,
        "authorization_validated": True,
        "authorization_consumed": False,
        "reopen_executed": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "promotion_authority": "EXACT_TARGET_ONLY",
        "canonical_mutation": False,
        "interpretation_notice": (
            "This receipt proves only that one satisfied environment reopen "
            "condition and one verified reopen receipt are bound to one exact "
            "external operational authorization. It does not execute reopening, "
            "mutate canonical state, establish truth, or grant general authority."
        ),
    }

    try:
        receipt_hash = stable_hash(body)
    except CanonicalValueError as exc:
        raise AuthorizedEnvironmentEpisodeReopenError(str(exc)) from exc

    return {**body, "receipt_hash": receipt_hash}


def verify_authorized_environment_episode_reopen(
    receipt: Mapping[str, Any],
    *,
    condition_receipt: Mapping[str, Any],
    comparison_identity: Mapping[str, Any],
    request: Mapping[str, Any],
    result: Mapping[str, Any],
    reopen_receipt: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> bool:
    """Regenerate the authorization binding and require exact equality."""

    if type(receipt) is not dict:
        raise AuthorizedEnvironmentEpisodeReopenError(
            "receipt must be a plain dictionary"
        )

    expected = authorize_environment_episode_reopen(
        condition_receipt=condition_receipt,
        comparison_identity=comparison_identity,
        request=request,
        result=result,
        reopen_receipt=reopen_receipt,
        authorization=authorization,
    )

    if set(receipt) != set(expected):
        raise AuthorizedEnvironmentEpisodeReopenError(
            "receipt fields do not match"
        )

    if receipt != expected:
        raise AuthorizedEnvironmentEpisodeReopenError(
            "receipt does not match supplied evidence or authorization"
        )

    return True
