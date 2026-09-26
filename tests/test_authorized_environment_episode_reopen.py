from copy import deepcopy

import pytest

from holosim.authorized_environment_episode_reopen import (
    AuthorizedEnvironmentEpisodeReopenError,
    authorize_environment_episode_reopen,
    verify_authorized_environment_episode_reopen,
)
from holosim.environment_completion_comparison_binding import (
    bind_completion_to_comparison,
)
from holosim.environment_episode_reopen_receipt import (
    create_reopen_receipt,
)
from holosim.environment_reopen_condition import (
    evaluate_environment_reopen_condition,
)
from holosim.environment_snapshot_comparator import compare_snapshots
from holosim.environment_snapshot_comparison_identity import (
    build_environment_snapshot_comparison_check_identity,
)
from holosim.hook_contract import build_hook_request, build_hook_result
from holosim.typed_operational_authorization import (
    build_operational_authorization,
)
from tests.test_environment_episode_reopen_receipt import (
    _completion_certificate,
    _snapshot,
)


def _chain():
    certificate = _completion_certificate()

    before = _snapshot(2)
    after = _snapshot(4, episode_id="episode:camera-1")

    comparison = compare_snapshots(before, after)
    identity = build_environment_snapshot_comparison_check_identity(comparison)

    boundary = bind_completion_to_comparison(
        completion_certificate=certificate,
        comparison_identity=identity,
    )

    request = build_hook_request(
        hook_id="environment-recheck-1",
        action="verify-reopen-condition",
        reference="condition-environment-changed",
        payload={
            "comparison_check_identity_hash": identity["check_identity_hash"],
        },
    )

    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"condition_satisfied": True},
    )

    condition = evaluate_environment_reopen_condition(
        condition_id="condition-environment-changed",
        comparison_identity=identity,
        request=request,
        result=result,
    )

    trigger = _snapshot(
        4,
        episode_id="episode:camera-1:reopen-1",
    )

    reopen = create_reopen_receipt(
        completion_certificate=certificate,
        trigger_snapshot=trigger,
        relation="reopens",
        reasons=["new relevant evidence"],
        provenance={"source_id": "operator-review:1"},
    )

    authorization = build_operational_authorization(
        authorization_id="authorization-reopen-1",
        actor_id="operator-1",
        action="ENVIRONMENT_EPISODE_REOPEN",
        target_sha256=reopen["receipt_id"],
        approval_reference="approval:environment-reopen-1",
    )

    return (
        certificate,
        identity,
        boundary,
        request,
        result,
        condition,
        reopen,
        authorization,
    )


def test_authorization_binds_exact_reopen_receipt():
    (
        _certificate,
        identity,
        boundary,
        request,
        result,
        condition,
        reopen,
        authorization,
    ) = _chain()

    receipt = authorize_environment_episode_reopen(
        condition_receipt=condition,
        comparison_identity=identity,
        request=request,
        result=result,
        reopen_receipt=reopen,
        authorization=authorization,
    )

    assert boundary["binding_complete"] is True
    assert condition["outcome"] == "SATISFIED"
    assert receipt["status"] == "AUTHORIZED"
    assert receipt["authorization_validated"] is True
    assert receipt["authorization_consumed"] is False
    assert receipt["reopen_executed"] is False
    assert receipt["reopen_receipt_id"] == reopen["receipt_id"]
    assert receipt["authorization_target_sha256"] == reopen["receipt_id"]
    assert receipt["authorization_action"] == "ENVIRONMENT_EPISODE_REOPEN"
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["promotion_authority"] == "EXACT_TARGET_ONLY"


def test_authorization_must_target_exact_reopen_receipt():
    (
        _certificate,
        identity,
        _boundary,
        request,
        result,
        condition,
        reopen,
        _authorization,
    ) = _chain()

    wrong_authorization = build_operational_authorization(
        authorization_id="authorization-reopen-wrong-target",
        actor_id="operator-1",
        action="ENVIRONMENT_EPISODE_REOPEN",
        target_sha256="f" * 64,
        approval_reference="approval:wrong-target",
    )

    with pytest.raises(
        AuthorizedEnvironmentEpisodeReopenError,
        match="authorization target does not match",
    ):
        authorize_environment_episode_reopen(
            condition_receipt=condition,
            comparison_identity=identity,
            request=request,
            result=result,
            reopen_receipt=reopen,
            authorization=wrong_authorization,
        )


def test_unsatisfied_condition_cannot_be_authorized():
    (
        _certificate,
        identity,
        _boundary,
        request,
        _result,
        _condition,
        reopen,
        authorization,
    ) = _chain()

    false_result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"condition_satisfied": False},
    )

    false_condition = evaluate_environment_reopen_condition(
        condition_id="condition-environment-changed",
        comparison_identity=identity,
        request=request,
        result=false_result,
    )

    with pytest.raises(
        AuthorizedEnvironmentEpisodeReopenError,
        match="must be SATISFIED",
    ):
        authorize_environment_episode_reopen(
            condition_receipt=false_condition,
            comparison_identity=identity,
            request=request,
            result=false_result,
            reopen_receipt=reopen,
            authorization=authorization,
        )


def test_condition_and_authorization_must_name_same_comparison():
    (
        _certificate,
        identity,
        _boundary,
        request,
        result,
        condition,
        reopen,
        authorization,
    ) = _chain()

    tampered_identity = deepcopy(identity)
    tampered_identity["subject"]["environment_id"] = "environment:other"

    with pytest.raises(
        AuthorizedEnvironmentEpisodeReopenError,
        match="condition receipt is invalid",
    ):
        authorize_environment_episode_reopen(
            condition_receipt=condition,
            comparison_identity=tampered_identity,
            request=request,
            result=result,
            reopen_receipt=reopen,
            authorization=authorization,
        )


def test_tampered_authorization_cannot_validate():
    (
        _certificate,
        identity,
        _boundary,
        request,
        result,
        condition,
        reopen,
        authorization,
    ) = _chain()

    tampered = deepcopy(authorization)
    tampered["actor_id"] = "operator-2"

    with pytest.raises(
        AuthorizedEnvironmentEpisodeReopenError,
        match="operational authorization is invalid",
    ):
        authorize_environment_episode_reopen(
            condition_receipt=condition,
            comparison_identity=identity,
            request=request,
            result=result,
            reopen_receipt=reopen,
            authorization=tampered,
        )


def test_tampered_reopen_receipt_cannot_be_authorized():
    (
        _certificate,
        identity,
        _boundary,
        request,
        result,
        condition,
        reopen,
        authorization,
    ) = _chain()

    tampered = deepcopy(reopen)
    tampered["reasons"] = ["different evidence"]

    with pytest.raises(
        AuthorizedEnvironmentEpisodeReopenError,
        match="reopen receipt",
    ):
        authorize_environment_episode_reopen(
            condition_receipt=condition,
            comparison_identity=identity,
            request=request,
            result=result,
            reopen_receipt=tampered,
            authorization=authorization,
        )


def test_authorization_binding_receipt_regenerates_exactly():
    (
        _certificate,
        identity,
        _boundary,
        request,
        result,
        condition,
        reopen,
        authorization,
    ) = _chain()

    receipt = authorize_environment_episode_reopen(
        condition_receipt=condition,
        comparison_identity=identity,
        request=request,
        result=result,
        reopen_receipt=reopen,
        authorization=authorization,
    )

    assert verify_authorized_environment_episode_reopen(
        receipt,
        condition_receipt=condition,
        comparison_identity=identity,
        request=request,
        result=result,
        reopen_receipt=reopen,
        authorization=authorization,
    ) is True
