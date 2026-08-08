from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.signed_occurrence import build_signed_occurrence
from holosim.temporal_activity_authorization_gate import (
    TemporalActivityGateError,
    run_permitted_temporal_activity,
)


SECRET = b"t" * 32
TARGET = {"service": "inventory", "resource": "item:42"}
ACTIVITY_INPUT = {"delta": 1}


def _permit(
    *,
    occurrence_id="permit:activity-1",
    workflow_id="workflow:inventory",
    run_id="run:0001",
    activity_id="activity:update-42",
    activity_type="inventory.increment",
    target=TARGET,
    activity_input=ACTIVITY_INPUT,
    not_before="2026-08-08T12:00:00-07:00",
    not_after="2026-08-08T13:00:00-07:00",
):
    return build_signed_occurrence(
        source_id="operator",
        occurrence_id=occurrence_id,
        payload={
            "type": "temporal_activity_permit",
            "version": 1,
            "workflow_id": workflow_id,
            "run_id": run_id,
            "activity_id": activity_id,
            "activity_type": activity_type,
            "target_sha256": stable_hash(target),
            "input_sha256": stable_hash(activity_input),
            "not_before": not_before,
            "not_after": not_after,
        },
        observed_at="2026-08-08T11:59:00-07:00",
        sequence=1,
        nonce=f"nonce:{occurrence_id}",
        secret=SECRET,
    )


def _run(permit, activity, **overrides):
    arguments = {
        "workflow_id": "workflow:inventory",
        "run_id": "run:0001",
        "activity_id": "activity:update-42",
        "activity_type": "inventory.increment",
        "target": TARGET,
        "activity_input": ACTIVITY_INPUT,
        "observed_at": "2026-08-08T12:30:00-07:00",
        "permit_occurrence": permit,
        "permit_source_secrets": {"operator": SECRET},
        "seen_occurrence_ids": set(),
        "activity": activity,
    }
    arguments.update(overrides)
    return run_permitted_temporal_activity(**arguments)


def test_matching_permit_executes_exact_activity_once():
    calls = []

    def activity(value):
        calls.append(value)
        return {"updated": True}

    result = _run(_permit(), activity)

    assert calls == [ACTIVITY_INPUT]
    assert result["decision"] == "EXECUTED"
    assert result["activity_executed"] is True
    assert result["activity_result"] == {"updated": True}
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_permit_for_different_activity_halts_before_callable_runs():
    calls = []

    result = _run(
        _permit(activity_id="activity:other"),
        lambda value: calls.append(value),
    )

    assert calls == []
    assert result["decision"] == "HALT_UNAUTHORIZED"
    assert result["reason"] == "permit is bound to a different activity_id"
    assert result["activity_executed"] is False


def test_permit_for_different_input_halts_before_callable_runs():
    calls = []

    result = _run(
        _permit(activity_input={"delta": 2}),
        lambda value: calls.append(value),
    )

    assert calls == []
    assert result["decision"] == "HALT_UNAUTHORIZED"
    assert result["reason"] == "permit is bound to a different input_sha256"


def test_replayed_permit_halts_before_callable_runs():
    permit = _permit()
    calls = []

    result = _run(
        permit,
        lambda value: calls.append(value),
        seen_occurrence_ids={permit["occurrence_id"]},
    )

    assert calls == []
    assert result["decision"] == "HALT_UNAUTHORIZED"
    assert result["reason"] == "REJECTED_REPLAY"


@pytest.mark.parametrize(
    ("observed_at", "reason"),
    [
        ("2026-08-08T11:59:59-07:00", "permit is not active yet"),
        ("2026-08-08T13:00:01-07:00", "permit has expired"),
    ],
)
def test_activity_outside_permit_window_halts(
    observed_at,
    reason,
):
    calls = []

    result = _run(
        _permit(),
        lambda value: calls.append(value),
        observed_at=observed_at,
    )

    assert calls == []
    assert result["decision"] == "HALT_UNAUTHORIZED"
    assert result["reason"] == reason


def test_undeclared_permit_field_is_rejected_before_execution():
    original = _permit()
    permit = build_signed_occurrence(
        source_id="operator",
        occurrence_id="permit:forged-schema",
        payload={**original["payload"], "approval": "GRANTED"},
        observed_at="2026-08-08T11:59:00-07:00",
        sequence=2,
        nonce="nonce:permit:forged-schema",
        secret=SECRET,
    )
    calls = []

    with pytest.raises(
        TemporalActivityGateError,
        match="payload fields do not match",
    ):
        _run(permit, lambda value: calls.append(value))

    assert calls == []


def test_inputs_are_not_mutated_by_activity():
    activity_input = {"delta": 1}
    before = deepcopy(activity_input)

    def activity(value):
        value["delta"] = 999
        return {"received": True}

    result = _run(
        _permit(activity_input=activity_input),
        activity,
        activity_input=activity_input,
    )

    assert result["decision"] == "EXECUTED"
    assert activity_input == before