from copy import deepcopy

import pytest

from holosim.environment_completion_comparison_binding import (
    EnvironmentCompletionComparisonBindingError,
    bind_completion_to_comparison,
    verify_environment_completion_comparison_binding_receipt,
)
from holosim.environment_snapshot_comparator import compare_snapshots
from holosim.environment_snapshot_comparison_identity import (
    build_environment_snapshot_comparison_check_identity,
)
from tests.test_environment_episode_reopen_receipt import (
    _completion_certificate,
    _snapshot,
)


def _inputs():
    certificate = _completion_certificate()
    before = _snapshot(2)
    after = _snapshot(4, episode_id="episode:camera-1")
    comparison = compare_snapshots(before, after)
    identity = build_environment_snapshot_comparison_check_identity(comparison)
    return certificate, before, after, identity


def test_exact_completed_boundary_binds_to_subsequent_comparison():
    certificate, before, after, identity = _inputs()

    receipt = bind_completion_to_comparison(
        completion_certificate=certificate,
        comparison_identity=identity,
    )

    assert before["snapshot_id"] == certificate["observation_hashes"][-1]
    assert before["observed_at"] == certificate["window_end"]
    assert receipt["comparison_after_snapshot_id"] == after["snapshot_id"]
    assert receipt["environment_matches"] is True
    assert receipt["boundary_matches"] is True
    assert receipt["before_matches_window_end"] is True
    assert receipt["after_is_later"] is True
    assert receipt["status"] == "BOUND"
    assert receipt["binding_complete"] is True
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_comparison_not_beginning_at_terminal_snapshot_does_not_bind():
    certificate = _completion_certificate()
    before = _snapshot(1)
    after = _snapshot(4, episode_id="episode:camera-1")
    comparison = compare_snapshots(before, after)
    identity = build_environment_snapshot_comparison_check_identity(comparison)

    receipt = bind_completion_to_comparison(
        completion_certificate=certificate,
        comparison_identity=identity,
    )

    assert receipt["boundary_matches"] is False
    assert receipt["binding_complete"] is False
    assert receipt["status"] == "BOUNDARY_MISMATCH"


def test_different_environment_does_not_bind():
    certificate, _, _, identity = _inputs()
    candidate = deepcopy(identity)
    candidate["subject"]["environment_id"] = "environment:other"

    with pytest.raises(
        EnvironmentCompletionComparisonBindingError,
        match="comparison identity hash mismatch",
    ):
        bind_completion_to_comparison(
            completion_certificate=certificate,
            comparison_identity=candidate,
        )


def test_tampered_completion_certificate_fails_closed():
    certificate, _, _, identity = _inputs()
    certificate["window_end"] = "2099-01-01T00:00:00Z"

    with pytest.raises(
        EnvironmentCompletionComparisonBindingError,
        match="completion certificate identity mismatch",
    ):
        bind_completion_to_comparison(
            completion_certificate=certificate,
            comparison_identity=identity,
        )


def test_tampered_comparison_identity_fails_closed():
    certificate, _, _, identity = _inputs()
    identity["reference_ids"][0] = "wrong-snapshot"

    with pytest.raises(
        EnvironmentCompletionComparisonBindingError,
        match="comparison identity hash mismatch",
    ):
        bind_completion_to_comparison(
            completion_certificate=certificate,
            comparison_identity=identity,
        )


def test_binding_receipt_regenerates_from_exact_evidence():
    certificate, _, _, identity = _inputs()

    receipt = bind_completion_to_comparison(
        completion_certificate=certificate,
        comparison_identity=identity,
    )

    assert verify_environment_completion_comparison_binding_receipt(
        receipt,
        completion_certificate=certificate,
        comparison_identity=identity,
    )


def test_tampered_binding_receipt_fails_closed():
    certificate, _, _, identity = _inputs()

    receipt = bind_completion_to_comparison(
        completion_certificate=certificate,
        comparison_identity=identity,
    )
    receipt["binding_complete"] = False

    with pytest.raises(
        EnvironmentCompletionComparisonBindingError,
        match="does not match supplied evidence",
    ):
        verify_environment_completion_comparison_binding_receipt(
            receipt,
            completion_certificate=certificate,
            comparison_identity=identity,
        )
from holosim.environment_completion_comparison_binding import (
    bind_completion_to_comparison,
)
from holosim.environment_reopen_condition import (
    evaluate_environment_reopen_condition,
)
from holosim.environment_snapshot_comparator import compare_snapshots
from holosim.environment_snapshot_comparison_identity import (
    build_environment_snapshot_comparison_check_identity,
)
from holosim.hook_contract import build_hook_request, build_hook_result
from tests.test_environment_episode_reopen_receipt import (
    _completion_certificate,
    _snapshot,
)


def test_boundary_and_reopen_condition_bind_the_same_comparison_identity():
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

    assert boundary["binding_complete"] is True
    assert boundary["status"] == "BOUND"
    assert condition["outcome"] == "SATISFIED"

    assert (
        identity["check_identity_hash"]
        == boundary["comparison_check_identity_hash"]
        == condition["comparison_check_identity_hash"]
    )

    assert condition["reopen_authorized"] is False
    assert condition["accepted"] is False
    assert condition["write_authority"] == "NONE"
