from copy import deepcopy

import pytest

from holosim.bounded_contradiction_challenge import challenge_for_contradiction
from holosim.canonical import stable_hash
from holosim.challenged_continuity_reentry import (
    ChallengedContinuityReentryError,
    evaluate_challenged_continuity_reentry,
    verify_challenged_continuity_reentry_receipt,
)
from holosim.current_observation_challenge_binding import (
    bind_current_observation_to_challenge,
)
from holosim.reconstructor import build_reconstructed_state
from holosim.verified_cold_start_reentry_gateway import (
    build_verified_cold_start_reentry_packet,
)
from holosim.time_scoped_truth import build_time_scoped_truth_receipt
from tests.test_current_observation_challenge_binding import _check, _inputs
from tests.test_verified_cold_start_reentry_gateway import (
    SOURCE_ITEMS,
    _head_check,
)


def _packet(*, current=True):
    state = build_reconstructed_state(
        "cold-start",
        ["active-goal"],
        SOURCE_ITEMS,
    )
    head = _head_check(
        current_hash="head-10" if current else "head-11",
        current_idx=10 if current else 11,
    )
    return build_verified_cold_start_reentry_packet(
        packet_id="challenged-reentry-packet",
        reconstructed_state=state,
        source_items=SOURCE_ITEMS,
        head_check=head,
        conflicts=[],
    )



def _receipt(*, state_hash=None, **kwargs):
    inputs = _inputs(**kwargs)
    if state_hash is None:
        state_hash = _packet()["reconstructed_state_hash"]
    inputs["observation"]["state_hash"] = state_hash
    inputs["checks"] = [_check(output_state_hash=state_hash)]
    return build_time_scoped_truth_receipt(**inputs)


def _truth():
    return _receipt()


def _challenge(*, state_hash, mode="none"):
    if mode == "none":
        checks = {
            "different": lambda state, evidence: state["value"] != evidence["value"]
        }
    elif mode == "contradiction":
        checks = {
            "different": lambda state, evidence: state["value"] == evidence["value"]
        }
    elif mode == "insufficient":
        checks = {"broken": lambda state, evidence: "UNKNOWN"}
    else:
        raise AssertionError("unsupported test mode")

    return challenge_for_contradiction(
        challenge_id="challenge:challenged-reentry",
        target_state_hash=state_hash,
        evidence_hash="evidence:challenged-reentry",
        state={"value": 8},
        evidence={"value": 8},
        checks=checks,
    )


def _bound_inputs(*, challenge_mode="none", target_hash=None, current=True):
    truth = _truth()
    if target_hash is None:
        target_hash = truth["observation"]["state_hash"]
    challenge = _challenge(state_hash=target_hash, mode=challenge_mode)
    binding = bind_current_observation_to_challenge(
        current_truth_receipt=truth,
        challenge_receipt=challenge,
    )
    packet = _packet(current=current)
    return packet, binding, challenge


def _evaluate(packet, binding, challenge, truth=None):
    return evaluate_challenged_continuity_reentry(
        reentry_packet=packet,
        source_items=SOURCE_ITEMS,
        observation_challenge_binding=binding,
        challenge_receipt=challenge,
        current_truth_receipt=_truth() if truth is None else truth,
    )


def test_ready_current_bound_completed_challenge_without_contradiction_allows():
    packet, binding, challenge = _bound_inputs()
    result = _evaluate(packet, binding, challenge)

    assert packet["gate_decision"] == "ALLOW"
    assert binding["status"] == "BOUND"
    assert challenge["result"] == "NO_CONTRADICTION_FOUND"
    assert result["decision"] == "ALLOW"
    assert result["reasons"] == []
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_contradiction_blocks_reentry():
    packet, binding, challenge = _bound_inputs(challenge_mode="contradiction")
    result = _evaluate(packet, binding, challenge)

    assert challenge["result"] == "CONTRADICTION_FOUND"
    assert result["decision"] == "BLOCK"
    assert result["reasons"] == ["contradiction_found"]


def test_insufficient_contradiction_search_blocks_reentry():
    packet, binding, challenge = _bound_inputs(challenge_mode="insufficient")
    result = _evaluate(packet, binding, challenge)

    assert challenge["result"] == "SEARCH_INSUFFICIENT"
    assert result["decision"] == "BLOCK"
    assert result["reasons"] == ["contradiction_search_insufficient"]


def test_challenge_for_different_current_state_blocks_reentry():
    packet, binding, challenge = _bound_inputs(target_hash="f" * 64)
    result = _evaluate(packet, binding, challenge)

    assert binding["status"] == "IDENTITY_MISMATCH"
    assert result["decision"] == "BLOCK"
    assert result["reasons"] == [
        "challenge_target_not_bound_to_current_observation"
    ]


def test_base_reentry_block_remains_blocked_even_when_challenge_passes():
    packet, binding, challenge = _bound_inputs(current=False)
    result = _evaluate(packet, binding, challenge)

    assert packet["gate_decision"] == "BLOCK"
    assert challenge["result"] == "NO_CONTRADICTION_FOUND"
    assert result["decision"] == "BLOCK"
    assert result["reasons"] == ["base_reentry_blocked"]


def test_binding_for_different_challenge_cannot_be_substituted():
    packet, binding, challenge = _bound_inputs()
    replacement = _challenge(
        state_hash=binding["observed_state_hash"],
        mode="none",
    )
    assert replacement["receipt_id"] == challenge["receipt_id"]

    different = challenge_for_contradiction(
        challenge_id="challenge:different",
        target_state_hash=binding["observed_state_hash"],
        evidence_hash="evidence:different",
        state={"value": 8},
        evidence={"value": 8},
        checks={"different": lambda state, evidence: False},
    )
    assert different["receipt_id"] != challenge["receipt_id"]

    with pytest.raises(
        ChallengedContinuityReentryError,
        match="binding does not reference supplied challenge",
    ):
        _evaluate(packet, binding, different)


def test_tampered_binding_hash_is_rejected():
    packet, binding, challenge = _bound_inputs()
    tampered = deepcopy(binding)
    tampered["status"] = "IDENTITY_MISMATCH"

    with pytest.raises(
        ChallengedContinuityReentryError,
        match="binding hash mismatch",
    ):
        _evaluate(packet, tampered, challenge)


def test_tampered_reentry_packet_is_rejected():
    packet, binding, challenge = _bound_inputs()
    tampered = deepcopy(packet)
    tampered["gate_decision"] = "BLOCK"

    with pytest.raises(
        ChallengedContinuityReentryError,
        match="reentry packet is invalid",
    ):
        _evaluate(tampered, binding, challenge)


def test_composition_is_deterministic_and_does_not_mutate_inputs():
    packet, binding, challenge = _bound_inputs()
    packet_before = deepcopy(packet)
    binding_before = deepcopy(binding)
    challenge_before = deepcopy(challenge)
    truth = _truth()
    truth_before = deepcopy(truth)

    first = _evaluate(packet, binding, challenge, truth=truth)
    second = _evaluate(packet, binding, challenge, truth=truth)

    assert first == second
    assert first["receipt_hash"] == second["receipt_hash"]
    assert packet == packet_before
    assert binding == binding_before
    assert challenge == challenge_before
    assert truth == truth_before


def test_challenged_reentry_receipt_verifies_against_exact_evidence():
    packet, binding, challenge = _bound_inputs()
    receipt = _evaluate(packet, binding, challenge)

    assert verify_challenged_continuity_reentry_receipt(
        receipt,
        reentry_packet=packet,
        source_items=SOURCE_ITEMS,
        observation_challenge_binding=binding,
        challenge_receipt=challenge,
        current_truth_receipt=_truth(),
    ) is True


def test_rehashed_challenged_reentry_semantic_tamper_is_rejected():
    packet, binding, challenge = _bound_inputs()
    receipt = _evaluate(packet, binding, challenge)
    tampered = deepcopy(receipt)
    tampered["decision"] = "BLOCK"
    body = dict(tampered)
    body.pop("receipt_hash")
    tampered["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        ChallengedContinuityReentryError,
        match="does not match supplied evidence",
    ):
        verify_challenged_continuity_reentry_receipt(
            tampered,
            reentry_packet=packet,
            source_items=SOURCE_ITEMS,
            observation_challenge_binding=binding,
            challenge_receipt=challenge,
            current_truth_receipt=_truth(),
        )


def test_foreign_challenged_reentry_field_is_rejected_even_when_rehashed():
    packet, binding, challenge = _bound_inputs()
    receipt = _evaluate(packet, binding, challenge)
    forged = deepcopy(receipt)
    forged["approval"] = "GRANTED"
    body = dict(forged)
    body.pop("receipt_hash")
    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(
        ChallengedContinuityReentryError,
        match="fields do not match",
    ):
        verify_challenged_continuity_reentry_receipt(
            forged,
            reentry_packet=packet,
            source_items=SOURCE_ITEMS,
            observation_challenge_binding=binding,
            challenge_receipt=challenge,
            current_truth_receipt=_truth(),
        )


def test_challenged_reentry_receipt_cannot_verify_against_different_evidence():
    packet, binding, challenge = _bound_inputs()
    receipt = _evaluate(packet, binding, challenge)
    different_packet = _packet(current=False)

    with pytest.raises(
        ChallengedContinuityReentryError,
        match="does not match supplied evidence",
    ):
        verify_challenged_continuity_reentry_receipt(
            receipt,
            reentry_packet=different_packet,
            source_items=SOURCE_ITEMS,
            observation_challenge_binding=binding,
            challenge_receipt=challenge,
            current_truth_receipt=_truth(),
        )


@pytest.mark.parametrize("changes", [
    {"status": "BOUND", "identity_matches": True, "binding_complete": True},
    {"observed_state_hash": "0" * 64},
    {"challenge_target_state_hash": "0" * 64},
    {"current_truth_receipt_hash": "0" * 64},
    {"accepted": True},
    {"write_authority": "GRANTED"},
    {"extra": "unbound"},
])
def test_rehashed_false_binding_is_rejected_against_observation(changes):
    packet, binding, challenge = _bound_inputs(target_hash="f" * 64)
    forged = deepcopy(binding)
    forged.update(changes)
    body = dict(forged)
    body.pop("receipt_hash")
    forged["receipt_hash"] = stable_hash(body)

    with pytest.raises(ChallengedContinuityReentryError, match="binding is invalid"):
        _evaluate(packet, forged, challenge)


def test_missing_observation_evidence_is_rejected_by_both_entrypoints():
    packet, binding, challenge = _bound_inputs()
    receipt = _evaluate(packet, binding, challenge)
    arguments = dict(
        reentry_packet=packet, source_items=SOURCE_ITEMS,
        observation_challenge_binding=binding, challenge_receipt=challenge,
    )
    with pytest.raises(ChallengedContinuityReentryError, match="current truth receipt is required"):
        evaluate_challenged_continuity_reentry(**arguments)
    with pytest.raises(ChallengedContinuityReentryError, match="current truth receipt is required"):
        verify_challenged_continuity_reentry_receipt(receipt, **arguments)


def test_changed_observation_evidence_is_rejected():
    packet, binding, challenge = _bound_inputs()
    truth = _truth()
    truth["observation"]["state_hash"] = "f" * 64
    with pytest.raises(ChallengedContinuityReentryError, match="current truth receipt is invalid"):
        _evaluate(packet, binding, challenge, truth=truth)


def test_receipt_replay_rejects_rehashed_false_binding():
    packet, binding, challenge = _bound_inputs()
    receipt = _evaluate(packet, binding, challenge)
    forged = deepcopy(binding)
    forged["observed_state_hash"] = "f" * 64
    body = dict(forged)
    body.pop("receipt_hash")
    forged["receipt_hash"] = stable_hash(body)
    with pytest.raises(ChallengedContinuityReentryError, match="binding is invalid"):
        verify_challenged_continuity_reentry_receipt(
            receipt, reentry_packet=packet, source_items=SOURCE_ITEMS,
            observation_challenge_binding=forged, challenge_receipt=challenge,
            current_truth_receipt=_truth(),
        )


def test_different_valid_observation_receipt_cannot_replace_original():
    packet, binding, challenge = _bound_inputs()
    replacement = _receipt(observed_at="2026-09-03T11:00:00-07:00")
    assert replacement["observation"]["state_hash"] == binding["observed_state_hash"]
    assert replacement["receipt_hash"] != binding["current_truth_receipt_hash"]
    with pytest.raises(ChallengedContinuityReentryError, match="binding is invalid"):
        _evaluate(packet, binding, challenge, truth=replacement)


@pytest.mark.parametrize("current, mode, other_reasons", [
    (True, "none", []),
    (False, "none", ["base_reentry_blocked"]),
    (True, "contradiction", ["contradiction_found"]),
    (True, "insufficient", ["contradiction_search_insufficient"]),
])
def test_valid_challenge_of_other_state_cannot_allow_reentry(current, mode, other_reasons):
    packet = _packet(current=current)
    truth = _receipt(state_hash="f" * 64)
    challenge = _challenge(state_hash=truth["observation"]["state_hash"], mode=mode)
    binding = bind_current_observation_to_challenge(
        current_truth_receipt=truth, challenge_receipt=challenge,
    )
    assert binding["status"] == "BOUND"
    assert binding["observed_state_hash"] != packet["reconstructed_state_hash"]
    before = deepcopy((packet, truth, challenge, binding))
    receipt = _evaluate(packet, binding, challenge, truth=truth)
    assert receipt["decision"] == "BLOCK"
    assert set(receipt["reasons"]) == set(other_reasons + [
        "current_observation_not_bound_to_reconstructed_state"
    ])
    assert receipt["truth_claimed"] is False
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert (packet, truth, challenge, binding) == before
    assert verify_challenged_continuity_reentry_receipt(
        receipt, reentry_packet=packet, source_items=SOURCE_ITEMS,
        observation_challenge_binding=binding, challenge_receipt=challenge,
        current_truth_receipt=truth,
    ) is True
    forged = dict(receipt, decision="ALLOW", reasons=[])
    body = dict(forged)
    body.pop("receipt_hash")
    forged["receipt_hash"] = stable_hash(body)
    with pytest.raises(ChallengedContinuityReentryError, match="does not match supplied evidence"):
        verify_challenged_continuity_reentry_receipt(
            forged, reentry_packet=packet, source_items=SOURCE_ITEMS,
            observation_challenge_binding=binding, challenge_receipt=challenge,
            current_truth_receipt=truth,
        )


def test_valid_replacement_reconstruction_cannot_reuse_other_state_challenge():
    packet, binding, challenge = _bound_inputs()
    sources = deepcopy(SOURCE_ITEMS)
    sources[0]["value"] = "different current work"
    state = build_reconstructed_state("cold-start", ["active-goal"], sources)
    replacement = build_verified_cold_start_reentry_packet(
        packet_id=packet["packet_id"], reconstructed_state=state,
        source_items=sources, head_check=packet["head_check"], conflicts=[],
    )
    assert replacement["gate_decision"] == "ALLOW"
    assert replacement["reconstructed_state_hash"] != binding["observed_state_hash"]
    receipt = evaluate_challenged_continuity_reentry(
        reentry_packet=replacement, source_items=sources,
        observation_challenge_binding=binding, challenge_receipt=challenge,
        current_truth_receipt=_truth(),
    )
    assert receipt["decision"] == "BLOCK"
    assert receipt["reasons"] == ["current_observation_not_bound_to_reconstructed_state"]
    original = _evaluate(packet, binding, challenge)
    with pytest.raises(ChallengedContinuityReentryError, match="does not match supplied evidence"):
        verify_challenged_continuity_reentry_receipt(
            original, reentry_packet=replacement, source_items=sources,
            observation_challenge_binding=binding, challenge_receipt=challenge,
            current_truth_receipt=_truth(),
        )
