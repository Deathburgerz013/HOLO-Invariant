from __future__ import annotations

import pytest

from holosim.bounded_correction_dampener import (
    INSUFFICIENT_HISTORY,
    NO_OSCILLATION_OBSERVED,
    OSCILLATION_OBSERVED,
    REVERSAL_OBSERVED,
    CorrectionDampenerError,
    assess_correction_oscillation,
)


def test_repeated_two_state_transition_is_active_oscillation() -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "A", "B"),
    )

    assert receipt["status"] == OSCILLATION_OBSERVED
    assert receipt["active_oscillation"] is True
    assert receipt["damping_candidate"] is True
    assert receipt["damping_applied"] is False
    assert receipt["reversal_indices"] == [2, 3]
    assert receipt["oscillation_windows"] == [
        {
            "start_index": 0,
            "end_index": 3,
            "state_ids": ["A", "B"],
        }
    ]


def test_single_return_is_reversal_not_oscillation() -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "A"),
    )

    assert receipt["status"] == REVERSAL_OBSERVED
    assert receipt["reversal_indices"] == [2]
    assert receipt["oscillation_windows"] == []
    assert receipt["active_oscillation"] is False
    assert receipt["damping_candidate"] is False


def test_distinct_progression_has_no_observed_oscillation() -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "C", "D"),
    )

    assert receipt["status"] == NO_OSCILLATION_OBSERVED
    assert receipt["change_indices"] == [1, 2, 3]
    assert receipt["reversal_indices"] == []
    assert receipt["oscillation_windows"] == []
    assert receipt["damping_candidate"] is False


def test_unchanged_history_is_not_oscillation() -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "A", "A", "A"),
    )

    assert receipt["status"] == NO_OSCILLATION_OBSERVED
    assert receipt["change_indices"] == []
    assert receipt["reversal_indices"] == []
    assert receipt["active_oscillation"] is False
    assert receipt["damping_candidate"] is False


@pytest.mark.parametrize(
    "state_ids",
    [
        ("A",),
        ("A", "B"),
    ],
)
def test_short_history_is_insufficient(state_ids) -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=state_ids,
    )

    assert receipt["status"] == INSUFFICIENT_HISTORY
    assert receipt["active_oscillation"] is False
    assert receipt["damping_candidate"] is False


def test_multiple_alternating_windows_are_preserved() -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "A", "B", "A"),
    )

    assert receipt["status"] == OSCILLATION_OBSERVED
    assert receipt["oscillation_windows"] == [
        {
            "start_index": 0,
            "end_index": 3,
            "state_ids": ["A", "B"],
        },
        {
            "start_index": 1,
            "end_index": 4,
            "state_ids": ["B", "A"],
        },
    ]
    assert receipt["active_oscillation"] is True


def test_trailing_oscillation_can_follow_unrelated_history() -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=("initial", "A", "B", "A", "B"),
    )

    assert receipt["status"] == OSCILLATION_OBSERVED
    assert receipt["oscillation_windows"] == [
        {
            "start_index": 1,
            "end_index": 4,
            "state_ids": ["A", "B"],
        }
    ]
    assert receipt["damping_candidate"] is True


def test_historical_oscillation_does_not_remain_active() -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "A", "B", "C", "C"),
    )

    assert receipt["oscillation_windows"] == [
        {
            "start_index": 0,
            "end_index": 3,
            "state_ids": ["A", "B"],
        }
    ]
    assert receipt["status"] == REVERSAL_OBSERVED
    assert receipt["active_oscillation"] is False
    assert receipt["damping_candidate"] is False


def test_period_three_recurrence_is_not_invented_as_two_state() -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "C", "A", "B", "C"),
    )

    assert receipt["status"] == NO_OSCILLATION_OBSERVED
    assert receipt["oscillation_windows"] == []
    assert receipt["damping_candidate"] is False


def test_receipt_preserves_ordered_identity_information() -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "A", "B"),
    )

    assert receipt["target_id"] == "model"
    assert receipt["state_ids"] == ["A", "B", "A", "B"]
    assert receipt["history_length"] == 4
    assert receipt["latest_state_id"] == "B"
    assert receipt["distinct_state_ids"] == ["A", "B"]


def test_receipt_is_deterministic_across_supported_containers() -> None:
    first = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "A", "B"),
    )
    second = assess_correction_oscillation(
        target_id="model",
        state_ids=["A", "B", "A", "B"],
    )

    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]


def test_receipt_identity_binds_target_and_history() -> None:
    baseline = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "A", "B"),
    )
    other_target = assess_correction_oscillation(
        target_id="other-model",
        state_ids=("A", "B", "A", "B"),
    )
    other_history = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "A", "C"),
    )

    assert baseline["receipt_hash"] != other_target["receipt_hash"]
    assert baseline["receipt_hash"] != other_history["receipt_hash"]


def test_receipt_cannot_apply_damping_or_claim_authority() -> None:
    receipt = assess_correction_oscillation(
        target_id="model",
        state_ids=("A", "B", "A", "B"),
    )

    assert receipt["damping_applied"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["canonical_mutation"] is False


@pytest.mark.parametrize(
    "target_id",
    [
        "",
        "   ",
        " model",
        1,
    ],
)
def test_target_identity_fails_closed(target_id) -> None:
    with pytest.raises(CorrectionDampenerError):
        assess_correction_oscillation(
            target_id=target_id,
            state_ids=("A",),
        )


@pytest.mark.parametrize(
    "state_ids",
    [
        "ABAB",
        (),
    ],
)
def test_state_history_container_fails_closed(state_ids) -> None:
    with pytest.raises(CorrectionDampenerError):
        assess_correction_oscillation(
            target_id="model",
            state_ids=state_ids,
        )


@pytest.mark.parametrize(
    "state_ids",
    [
        ("",),
        ("   ",),
        (" A",),
        (1,),
    ],
)
def test_state_identities_fail_closed(state_ids) -> None:
    with pytest.raises(CorrectionDampenerError):
        assess_correction_oscillation(
            target_id="model",
            state_ids=state_ids,
        )


def test_history_length_is_bounded() -> None:
    with pytest.raises(
        CorrectionDampenerError,
        match="cannot exceed 256",
    ):
        assess_correction_oscillation(
            target_id="model",
            state_ids=tuple(
                f"state-{index}"
                for index in range(257)
            ),
        )


def test_inputs_are_not_mutated() -> None:
    state_ids = ["A", "B", "A", "B"]
    original = list(state_ids)

    assess_correction_oscillation(
        target_id="model",
        state_ids=state_ids,
    )

    assert state_ids == original