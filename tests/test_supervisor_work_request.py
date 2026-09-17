from copy import deepcopy
import hashlib

import pytest

from holosim.core import HoloChain
from holosim.deterministic_supervisor import decide_supervisor_state
from holosim.invariant_validity_lifecycle import append_validity_event
from holosim.supervisor_work_request import (
    REQUEST_FIELDS,
    REQUEST_STATUS,
    SupervisorWorkRequestError,
    build_supervisor_work_request,
    validate_supervisor_work_request,
)


ENVIRONMENT = "environment-head-001"
PAYLOAD_A = hashlib.sha256(b"payload-a").hexdigest()
PAYLOAD_B = hashlib.sha256(b"payload-b").hexdigest()


def append_event(history, *, claim_id="claim-001", status="ESTABLISHED"):
    event = append_validity_event(
        history=history,
        claim_id=claim_id,
        status=status,
        reason="bounded evidence supports the status",
        evidence=["evidence-001"],
        observed_at="2026-09-17T06:30:00Z",
        environment_fingerprint=None,
        reopen_reference=None,
    )
    history.append(event)
    return event


def current_decision(path, history, *, pending=("work-001",)):
    return decide_supervisor_state(
        path,
        history,
        current_environment_fingerprint=ENVIRONMENT,
        required_claim_ids=["claim-001"],
        pending_work_ids=pending,
    )


def build(path, history, decision, *, work_id="work-001", payload=PAYLOAD_A):
    return build_supervisor_work_request(
        path,
        history,
        decision,
        current_environment_fingerprint=ENVIRONMENT,
        required_claim_ids=["claim-001"],
        pending_work_ids=["work-001", "work-002"],
        selected_work_id=work_id,
        work_payload_sha256=payload,
    )


def ready_inputs(tmp_path):
    path = tmp_path / "chain.jsonl"
    HoloChain(path).append("verified-state")
    history = []
    append_event(history)
    decision = current_decision(
        path,
        history,
        pending=["work-001", "work-002"],
    )
    return path, history, decision


def test_current_run_decision_builds_exact_nonexecuting_request(tmp_path):
    path, history, decision = ready_inputs(tmp_path)
    history_before = deepcopy(history)
    chain_before = path.read_bytes()

    request = build(path, history, decision)

    assert set(request) == REQUEST_FIELDS
    assert request["request_status"] == REQUEST_STATUS
    assert request["decision_hash"] == decision["decision_hash"]
    assert request["chain_source_sha256"] == decision[
        "chain_observation"
    ]["source_sha256"]
    assert request["projection_hash"] == decision[
        "invariant_projection"
    ]["projection_hash"]
    assert request["work_id"] == "work-001"
    assert request["work_payload_sha256"] == PAYLOAD_A
    assert request["authorization_required"] is True
    assert request["action_performed"] is False
    assert request["recovery_performed"] is False
    assert request["accepted"] is False
    assert request["truth_claimed"] is False
    assert request["write_authority"] == "NONE"
    assert request["execution_authority"] == "NONE"
    assert request["promotion_authority"] == "NONE"
    assert history == history_before
    assert path.read_bytes() == chain_before


def test_request_regenerates_against_current_sources(tmp_path):
    path, history, decision = ready_inputs(tmp_path)
    request = build(path, history, decision, work_id="work-002")

    assert validate_supervisor_work_request(
        path,
        history,
        decision,
        request,
        current_environment_fingerprint=ENVIRONMENT,
        required_claim_ids=["claim-001"],
        pending_work_ids=["work-001", "work-002"],
    ) is True


def test_selected_work_must_be_declared_pending(tmp_path):
    path, history, decision = ready_inputs(tmp_path)

    with pytest.raises(
        SupervisorWorkRequestError,
        match="not declared pending work",
    ):
        build(path, history, decision, work_id="work-unknown")


def test_wait_decision_cannot_build_work_request(tmp_path):
    path = tmp_path / "chain.jsonl"
    HoloChain(path).append("verified-state")
    history = []
    append_event(history)
    decision = current_decision(path, history, pending=[])

    with pytest.raises(SupervisorWorkRequestError, match="not RUN"):
        build_supervisor_work_request(
            path,
            history,
            decision,
            current_environment_fingerprint=ENVIRONMENT,
            required_claim_ids=["claim-001"],
            pending_work_ids=[],
            selected_work_id="work-001",
            work_payload_sha256=PAYLOAD_A,
        )


def test_recover_decision_cannot_build_work_request(tmp_path):
    path = tmp_path / "chain.jsonl"
    HoloChain(path).append("verified-state")
    with path.open("ab") as stream:
        stream.write(b"{")
    history = []
    append_event(history)
    decision = current_decision(path, history)

    with pytest.raises(SupervisorWorkRequestError, match="not RUN"):
        build_supervisor_work_request(
            path,
            history,
            decision,
            current_environment_fingerprint=ENVIRONMENT,
            required_claim_ids=["claim-001"],
            pending_work_ids=["work-001"],
            selected_work_id="work-001",
            work_payload_sha256=PAYLOAD_A,
        )


def test_block_decision_cannot_build_work_request(tmp_path):
    path = tmp_path / "chain.jsonl"
    HoloChain(path).append("verified-state")
    history = []
    append_event(history, status="INVALID")
    decision = current_decision(path, history)

    with pytest.raises(SupervisorWorkRequestError, match="not RUN"):
        build_supervisor_work_request(
            path,
            history,
            decision,
            current_environment_fingerprint=ENVIRONMENT,
            required_claim_ids=["claim-001"],
            pending_work_ids=["work-001"],
            selected_work_id="work-001",
            work_payload_sha256=PAYLOAD_A,
        )


def test_tampered_decision_fails_current_recomputation(tmp_path):
    path, history, decision = ready_inputs(tmp_path)
    tampered = deepcopy(decision)
    tampered["state"] = "WAIT"

    with pytest.raises(
        SupervisorWorkRequestError,
        match="does not match current recomputation",
    ):
        build(path, history, tampered)


def test_decision_becomes_stale_when_chain_changes(tmp_path):
    path, history, decision = ready_inputs(tmp_path)
    HoloChain(path).append("newer-state")

    with pytest.raises(
        SupervisorWorkRequestError,
        match="does not match current recomputation",
    ):
        build(path, history, decision)


def test_decision_becomes_stale_when_validity_history_changes(tmp_path):
    path, history, decision = ready_inputs(tmp_path)
    append_event(history, status="INVALID")

    with pytest.raises(
        SupervisorWorkRequestError,
        match="does not match current recomputation",
    ):
        build(path, history, decision)


@pytest.mark.parametrize(
    "payload",
    ["not-a-digest", "A" * 64, "a" * 63],
)
def test_payload_identity_must_be_lowercase_sha256(tmp_path, payload):
    path, history, decision = ready_inputs(tmp_path)

    with pytest.raises(
        SupervisorWorkRequestError,
        match="lowercase SHA-256",
    ):
        build(path, history, decision, payload=payload)


def test_payload_change_changes_request_identity(tmp_path):
    path, history, decision = ready_inputs(tmp_path)

    first = build(path, history, decision, payload=PAYLOAD_A)
    second = build(path, history, decision, payload=PAYLOAD_B)

    assert first["request_hash"] != second["request_hash"]
    assert first["decision_hash"] == second["decision_hash"]


def test_extra_request_field_fails_closed(tmp_path):
    path, history, decision = ready_inputs(tmp_path)
    request = build(path, history, decision)
    request["execute"] = True

    with pytest.raises(
        SupervisorWorkRequestError,
        match="fields do not match",
    ):
        validate_supervisor_work_request(
            path,
            history,
            decision,
            request,
            current_environment_fingerprint=ENVIRONMENT,
            required_claim_ids=["claim-001"],
            pending_work_ids=["work-001", "work-002"],
        )


def test_missing_source_fails_without_creating_parent(tmp_path):
    parent = tmp_path / "absent"
    path = parent / "chain.jsonl"
    history = []
    append_event(history)
    fake_decision = {"state": "RUN"}

    with pytest.raises(
        SupervisorWorkRequestError,
        match="does not match current recomputation",
    ):
        build_supervisor_work_request(
            path,
            history,
            fake_decision,
            current_environment_fingerprint=ENVIRONMENT,
            required_claim_ids=["claim-001"],
            pending_work_ids=["work-001"],
            selected_work_id="work-001",
            work_payload_sha256=PAYLOAD_A,
        )

    assert not parent.exists()
