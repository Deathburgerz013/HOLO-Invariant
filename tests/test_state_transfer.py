from __future__ import annotations

import copy
import hashlib
import json

import pytest

from holosim.state_transfer import (
    MAX_INVARIANT_IDS,
    MAX_KNOWN_STATE_HASHES,
    MAX_TEXT_UTF8_BYTES,
    StateTransferError,
    build_state_transfer,
    observe_state_transfer,
    validate_state_transfer,
    validate_state_transfer_observation,
)


BASE = {"version": 3, "claims": ["bounded"], "status": "CURRENT"}
PAYLOAD = {"operation": "append", "claim": "candidate"}
SENDER = {
    "provider_label": "Example Provider",
    "model_label": "Example Model",
    "model_version": "declared-version",
    "interface": "manual-transfer",
}
EVIDENCE = {
    "commands": ["python -m pytest -q"],
    "observed_results": ["436 passed"],
    "artifact_hashes": {"payload.json": "a" * 64},
    "execution_status": "CALLER_REPORTED",
}


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def rehash(root: dict, field: str) -> None:
    body = dict(root)
    body.pop(field)
    root[field] = canonical_hash(body)


def make_envelope() -> dict:
    return build_state_transfer(
        transfer_id="transfer-001",
        base_snapshot=BASE,
        payload=PAYLOAD,
        applied_invariant_ids=["INV-APPEND-ONLY", "INV-NO-AUTHORITY"],
        evidence=EVIDENCE,
        declared_sender=SENDER,
    )


def test_builds_self_contained_hash_bound_envelope() -> None:
    envelope = make_envelope()

    assert envelope["base_snapshot"] == BASE
    assert envelope["base_state_hash"] == canonical_hash(BASE)
    assert envelope["payload_hash"] == canonical_hash(PAYLOAD)
    assert envelope["authentication_status"] == "NOT_AUTHENTICATED"
    assert envelope["application_status"] == "NOT_APPLIED"
    assert envelope["accepted"] is False
    assert envelope["write_authority"] == "NONE"
    validate_state_transfer(envelope)


def test_build_does_not_mutate_or_alias_inputs() -> None:
    base = copy.deepcopy(BASE)
    payload = copy.deepcopy(PAYLOAD)
    evidence = copy.deepcopy(EVIDENCE)
    sender = copy.deepcopy(SENDER)
    originals = copy.deepcopy((base, payload, evidence, sender))

    envelope = build_state_transfer(
        transfer_id="transfer-001",
        base_snapshot=base,
        payload=payload,
        applied_invariant_ids=["INV-1"],
        evidence=evidence,
        declared_sender=sender,
    )
    envelope["base_snapshot"]["version"] = 99
    envelope["payload"]["operation"] = "replace"
    envelope["evidence"]["commands"].append("changed")
    envelope["declared_sender"]["model_label"] = "changed"

    assert (base, payload, evidence, sender) == tuple(originals)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("authentication_status", "AUTHENTICATED", "authentication status"),
        ("application_status", "APPLIED", "application status"),
        ("accepted", True, "acceptance or authority"),
        ("write_authority", "MODEL", "acceptance or authority"),
    ],
)
def test_envelope_cannot_promote_claims_after_rehash(
    field: str, value: object, message: str
) -> None:
    envelope = make_envelope()
    envelope[field] = value
    rehash(envelope, "envelope_hash")

    with pytest.raises(StateTransferError, match=message):
        validate_state_transfer(envelope)


def test_base_snapshot_tampering_is_rejected() -> None:
    envelope = make_envelope()
    envelope["base_snapshot"]["version"] = 4

    with pytest.raises(StateTransferError, match="base state hash mismatch"):
        validate_state_transfer(envelope)


def test_payload_tampering_is_rejected() -> None:
    envelope = make_envelope()
    envelope["payload"]["claim"] = "changed"

    with pytest.raises(StateTransferError, match="payload hash mismatch"):
        validate_state_transfer(envelope)


def test_outer_tampering_is_rejected() -> None:
    envelope = make_envelope()
    envelope["transfer_id"] = "changed"

    with pytest.raises(StateTransferError, match="envelope hash mismatch"):
        validate_state_transfer(envelope)


def test_current_means_exact_base_hash_only() -> None:
    envelope = make_envelope()
    observation = observe_state_transfer(envelope, receiver_snapshot=BASE)

    assert observation["state_status"] == "CURRENT"
    assert observation["payload_applied"] is False
    assert observation["accepted"] is False
    assert "does not prove truth" in observation["interpretation_notice"]
    validate_state_transfer_observation(envelope, observation)


def test_stale_requires_base_in_known_history() -> None:
    envelope = make_envelope()
    observation = observe_state_transfer(
        envelope,
        receiver_snapshot={"version": 4},
        known_state_hashes=[envelope["base_state_hash"]],
    )

    assert observation["state_status"] == "STALE"
    validate_state_transfer_observation(envelope, observation)


def test_conflict_when_base_is_not_current_or_known() -> None:
    envelope = make_envelope()
    observation = observe_state_transfer(
        envelope,
        receiver_snapshot={"version": 4},
        known_state_hashes=["b" * 64],
    )

    assert observation["state_status"] == "CONFLICT"
    validate_state_transfer_observation(envelope, observation)


def test_unavailable_without_receiver_snapshot() -> None:
    envelope = make_envelope()
    observation = observe_state_transfer(
        envelope,
        receiver_snapshot=None,
        known_state_hashes=[envelope["base_state_hash"]],
    )

    assert observation["state_status"] == "UNAVAILABLE"
    assert observation["receiver_state_hash"] is None
    validate_state_transfer_observation(envelope, observation)


def test_observation_status_tampering_fails_after_rehash() -> None:
    envelope = make_envelope()
    observation = observe_state_transfer(envelope, receiver_snapshot=BASE)
    observation["state_status"] = "CONFLICT"
    rehash(observation, "observation_hash")

    with pytest.raises(StateTransferError, match="semantically inconsistent"):
        validate_state_transfer_observation(envelope, observation)


def test_observation_cannot_claim_application_or_authority() -> None:
    envelope = make_envelope()
    observation = observe_state_transfer(envelope, receiver_snapshot=BASE)
    observation["payload_applied"] = True
    rehash(observation, "observation_hash")

    with pytest.raises(StateTransferError, match="cannot claim payload application"):
        validate_state_transfer_observation(envelope, observation)


def test_observation_must_bind_exact_envelope() -> None:
    envelope = make_envelope()
    other = copy.deepcopy(envelope)
    other["transfer_id"] = "transfer-002"
    rehash(other, "envelope_hash")
    observation = observe_state_transfer(envelope, receiver_snapshot=BASE)

    with pytest.raises(StateTransferError, match="does not match envelope"):
        validate_state_transfer_observation(other, observation)


def test_known_hashes_are_materialized_once() -> None:
    envelope = make_envelope()
    consumed = 0

    def hashes():
        nonlocal consumed
        consumed += 1
        yield envelope["base_state_hash"]

    observation = observe_state_transfer(
        envelope, receiver_snapshot={"version": 4}, known_state_hashes=hashes()
    )

    assert consumed == 1
    assert observation["state_status"] == "STALE"


@pytest.mark.parametrize(
    ("invariants", "message"),
    [
        ([], "must not be empty"),
        (["INV-1", "INV-1"], "unique"),
        ([""], "nonempty"),
        ("INV-1", "iterable of strings"),
        ((str(index) for index in range(MAX_INVARIANT_IDS + 1)), "item limit"),
    ],
)
def test_invalid_invariant_identifiers_fail_closed(invariants, message: str) -> None:
    with pytest.raises(StateTransferError, match=message):
        build_state_transfer(
            transfer_id="transfer-001",
            base_snapshot=BASE,
            payload=PAYLOAD,
            applied_invariant_ids=invariants,
            evidence=EVIDENCE,
            declared_sender=SENDER,
        )


def test_evidence_commands_and_results_must_align() -> None:
    evidence = copy.deepcopy(EVIDENCE)
    evidence["observed_results"] = []

    with pytest.raises(StateTransferError, match="equal length"):
        build_state_transfer(
            transfer_id="transfer-001",
            base_snapshot=BASE,
            payload=PAYLOAD,
            applied_invariant_ids=["INV-1"],
            evidence=evidence,
            declared_sender=SENDER,
        )


def test_not_run_evidence_cannot_claim_commands() -> None:
    evidence = copy.deepcopy(EVIDENCE)
    evidence["execution_status"] = "NOT_RUN"

    with pytest.raises(StateTransferError, match="cannot contain"):
        build_state_transfer(
            transfer_id="transfer-001",
            base_snapshot=BASE,
            payload=PAYLOAD,
            applied_invariant_ids=["INV-1"],
            evidence=evidence,
            declared_sender=SENDER,
        )


def test_caller_reported_evidence_requires_a_result_pair() -> None:
    evidence = {
        "commands": [],
        "observed_results": [],
        "artifact_hashes": {},
        "execution_status": "CALLER_REPORTED",
    }

    with pytest.raises(StateTransferError, match="requires a command"):
        build_state_transfer(
            transfer_id="transfer-001",
            base_snapshot=BASE,
            payload=PAYLOAD,
            applied_invariant_ids=["INV-1"],
            evidence=evidence,
            declared_sender=SENDER,
        )


def test_invalid_artifact_hash_is_rejected() -> None:
    evidence = copy.deepcopy(EVIDENCE)
    evidence["artifact_hashes"]["payload.json"] = "not-a-hash"

    with pytest.raises(StateTransferError, match="64 lowercase hex"):
        build_state_transfer(
            transfer_id="transfer-001",
            base_snapshot=BASE,
            payload=PAYLOAD,
            applied_invariant_ids=["INV-1"],
            evidence=evidence,
            declared_sender=SENDER,
        )


def test_nonfinite_and_cyclic_values_are_rejected() -> None:
    with pytest.raises(StateTransferError, match="finite"):
        build_state_transfer(
            transfer_id="transfer-001",
            base_snapshot={"value": float("inf")},
            payload=PAYLOAD,
            applied_invariant_ids=["INV-1"],
            evidence=EVIDENCE,
            declared_sender=SENDER,
        )
    cyclic: dict = {}
    cyclic["self"] = cyclic
    with pytest.raises(StateTransferError, match="cycles"):
        build_state_transfer(
            transfer_id="transfer-001",
            base_snapshot=BASE,
            payload=cyclic,
            applied_invariant_ids=["INV-1"],
            evidence=EVIDENCE,
            declared_sender=SENDER,
        )


def test_oversized_text_and_history_fail_closed() -> None:
    sender = copy.deepcopy(SENDER)
    sender["model_label"] = "x" * (MAX_TEXT_UTF8_BYTES + 1)
    with pytest.raises(StateTransferError, match="cannot exceed"):
        build_state_transfer(
            transfer_id="transfer-001",
            base_snapshot=BASE,
            payload=PAYLOAD,
            applied_invariant_ids=["INV-1"],
            evidence=EVIDENCE,
            declared_sender=sender,
        )
    envelope = make_envelope()
    with pytest.raises(StateTransferError, match="item limit"):
        observe_state_transfer(
            envelope,
            receiver_snapshot=BASE,
            known_state_hashes=("a" * 64 for _ in range(MAX_KNOWN_STATE_HASHES + 1)),
        )


def test_observation_is_deterministic_and_nonmutating() -> None:
    envelope = make_envelope()
    receiver = copy.deepcopy(BASE)
    original = copy.deepcopy((envelope, receiver))

    first = observe_state_transfer(envelope, receiver_snapshot=receiver)
    second = observe_state_transfer(envelope, receiver_snapshot=receiver)

    assert first == second
    assert (envelope, receiver) == tuple(original)