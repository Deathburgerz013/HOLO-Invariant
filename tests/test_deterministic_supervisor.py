import json

import pytest

from holosim.core import HoloChain
from holosim.deterministic_supervisor import (
    REASON_CHAIN_INTERIOR_FAILURE,
    REASON_CHAIN_SOURCE_MISSING,
    REASON_CHAIN_TERMINAL_INVALID,
    REASON_NO_PENDING_WORK,
    REASON_PENDING_WORK_READY,
    REASON_REQUIRED_INVARIANT_UNAVAILABLE,
    STATE_BLOCK,
    STATE_RECOVER,
    STATE_RUN,
    STATE_WAIT,
    DeterministicSupervisorError,
    decide_supervisor_state,
)
from holosim.invariant_validity_lifecycle import (
    InvariantValidityLifecycleError,
    append_validity_event,
)


ENVIRONMENT = "environment-head-001"

EXPECTED_KEYS = {
    "type",
    "version",
    "state",
    "reasons",
    "chain_observation",
    "invariant_projection",
    "required_claim_ids",
    "satisfied_required_claim_ids",
    "unavailable_required_claims",
    "pending_work_ids",
    "action_performed",
    "recovery_performed",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "promotion_authority",
    "interpretation_notice",
    "decision_hash",
}


def append_event(
    history,
    *,
    claim_id="claim-001",
    status="ESTABLISHED",
    environment_fingerprint=None,
):
    event = append_validity_event(
        history=history,
        claim_id=claim_id,
        status=status,
        reason="bounded evidence supports the status",
        evidence=["evidence-001"],
        observed_at="2026-09-17T05:30:00Z",
        environment_fingerprint=environment_fingerprint,
        reopen_reference=None,
    )
    history.append(event)
    return event


def decide(path, history, *, required=(), pending=()):
    return decide_supervisor_state(
        path,
        history,
        current_environment_fingerprint=ENVIRONMENT,
        required_claim_ids=required,
        pending_work_ids=pending,
    )


def test_missing_chain_blocks_without_creating_source_or_parent(tmp_path):
    parent = tmp_path / "absent"
    path = parent / "chain.jsonl"

    result = decide(path, [], pending=["work-001"])

    assert set(result) == EXPECTED_KEYS
    assert result["state"] == STATE_BLOCK
    assert result["reasons"] == [REASON_CHAIN_SOURCE_MISSING]
    assert result["action_performed"] is False
    assert result["recovery_performed"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert result["promotion_authority"] == "NONE"
    assert not path.exists()
    assert not parent.exists()


def test_clean_chain_without_pending_work_waits(tmp_path):
    path = tmp_path / "chain.jsonl"
    path.write_bytes(b"")

    result = decide(path, [])

    assert result["state"] == STATE_WAIT
    assert result["reasons"] == [REASON_NO_PENDING_WORK]
    assert result["chain_observation"]["status"] == "CLEAN"


def test_clean_chain_with_satisfied_requirements_marks_run_without_execution(
    tmp_path,
):
    path = tmp_path / "chain.jsonl"
    HoloChain(path).append("verified-state")
    history = []
    append_event(history, claim_id="claim-001")

    result = decide(
        path,
        history,
        required=["claim-001"],
        pending=["work-001"],
    )

    assert result["state"] == STATE_RUN
    assert result["reasons"] == [REASON_PENDING_WORK_READY]
    assert result["satisfied_required_claim_ids"] == ["claim-001"]
    assert result["unavailable_required_claims"] == []
    assert result["pending_work_ids"] == ["work-001"]
    assert result["action_performed"] is False
    assert result["execution_authority"] == "NONE"
    assert "RUN does not execute work" in result["interpretation_notice"]
    assert "does not prove the supplied validity history" in result[
        "interpretation_notice"
    ]


def test_terminal_invalid_record_requires_recovery_without_repair(tmp_path):
    path = tmp_path / "chain.jsonl"
    HoloChain(path).append("verified-state")
    with path.open("ab") as stream:
        stream.write(b"{")
    before = path.read_bytes()

    result = decide(path, [], pending=["work-001"])

    assert result["state"] == STATE_RECOVER
    assert result["reasons"] == [REASON_CHAIN_TERMINAL_INVALID]
    assert result["recovery_performed"] is False
    assert result["execution_authority"] == "NONE"
    assert path.read_bytes() == before


def test_interior_chain_failure_blocks_even_when_work_is_pending(tmp_path):
    path = tmp_path / "chain.jsonl"
    HoloChain(path).append("verified-state")
    with path.open("ab") as stream:
        stream.write(b'{"broken":\n')
        stream.write(b'{"later": "data"}\n')

    result = decide(path, [], pending=["work-001"])

    assert result["state"] == STATE_BLOCK
    assert result["reasons"] == [REASON_CHAIN_INTERIOR_FAILURE]
    assert result["action_performed"] is False


def test_missing_required_claim_blocks(tmp_path):
    path = tmp_path / "chain.jsonl"
    path.write_bytes(b"")

    result = decide(
        path,
        [],
        required=["claim-missing"],
        pending=["work-001"],
    )

    assert result["state"] == STATE_BLOCK
    assert result["reasons"] == [REASON_REQUIRED_INVARIANT_UNAVAILABLE]
    assert result["unavailable_required_claims"] == [
        {"claim_id": "claim-missing", "reason": "MISSING"}
    ]


def test_stale_contingent_required_claim_blocks(tmp_path):
    path = tmp_path / "chain.jsonl"
    path.write_bytes(b"")
    history = []
    append_event(
        history,
        claim_id="claim-001",
        status="CONTINGENT",
        environment_fingerprint="older-environment",
    )

    result = decide(
        path,
        history,
        required=["claim-001"],
        pending=["work-001"],
    )

    assert result["state"] == STATE_BLOCK
    assert result["unavailable_required_claims"] == [
        {"claim_id": "claim-001", "reason": "STALE_ENVIRONMENT"}
    ]


def test_invalid_required_claim_blocks(tmp_path):
    path = tmp_path / "chain.jsonl"
    path.write_bytes(b"")
    history = []
    append_event(history, claim_id="claim-001", status="INVALID")

    result = decide(
        path,
        history,
        required=["claim-001"],
        pending=["work-001"],
    )

    assert result["state"] == STATE_BLOCK
    assert result["unavailable_required_claims"] == [
        {"claim_id": "claim-001", "reason": "INVALID"}
    ]


def test_unrelated_excluded_claim_does_not_block_required_active_claim(tmp_path):
    path = tmp_path / "chain.jsonl"
    path.write_bytes(b"")
    history = []
    append_event(history, claim_id="required", status="ESTABLISHED")
    append_event(history, claim_id="unrelated", status="INVALID")

    result = decide(
        path,
        history,
        required=["required"],
        pending=["work-001"],
    )

    assert result["state"] == STATE_RUN
    assert result["satisfied_required_claim_ids"] == ["required"]
    assert result["unavailable_required_claims"] == []


def test_decision_is_deterministic_across_declared_id_order(tmp_path):
    path = tmp_path / "chain.jsonl"
    path.write_bytes(b"")
    history = []
    append_event(history, claim_id="a")
    append_event(history, claim_id="b")

    first = decide(
        path,
        history,
        required=["b", "a"],
        pending=["work-b", "work-a"],
    )
    second = decide(
        path,
        history,
        required=["a", "b"],
        pending=["work-a", "work-b"],
    )

    assert first == second
    assert first["required_claim_ids"] == ["a", "b"]
    assert first["pending_work_ids"] == ["work-a", "work-b"]


@pytest.mark.parametrize("field", ["required_claim_ids", "pending_work_ids"])
def test_duplicate_declared_ids_fail_closed(tmp_path, field):
    path = tmp_path / "chain.jsonl"
    path.write_bytes(b"")
    arguments = {
        "current_environment_fingerprint": ENVIRONMENT,
        "required_claim_ids": [],
        "pending_work_ids": [],
    }
    arguments[field] = ["duplicate", "duplicate"]

    with pytest.raises(DeterministicSupervisorError, match="duplicate ids"):
        decide_supervisor_state(path, [], **arguments)


def test_tampered_validity_history_fails_without_decision(tmp_path):
    path = tmp_path / "chain.jsonl"
    path.write_bytes(b"")
    history = []
    event = append_event(history)
    event["status"] = "INVARIANT"

    with pytest.raises(InvariantValidityLifecycleError, match="hash mismatch"):
        decide(path, history, pending=["work-001"])


def test_decision_hash_changes_when_declared_work_changes(tmp_path):
    path = tmp_path / "chain.jsonl"
    path.write_bytes(b"")

    first = decide(path, [], pending=["work-001"])
    second = decide(path, [], pending=["work-002"])

    assert first["state"] == second["state"] == STATE_RUN
    assert first["decision_hash"] != second["decision_hash"]
    json.dumps(first, allow_nan=False)
