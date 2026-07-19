from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from holosim.recovery import (
    RecoveryChallengeError,
    build_recovery_challenge,
    evaluate_recovery_response,
    public_recovery_packet,
    validate_recovery_evaluation,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "Model_Recovery_Behavior_Challenge_001.json"
)


def load_spec() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_builds_hash_bound_packet_and_private_oracle() -> None:
    bundle = build_recovery_challenge(load_spec())

    assert bundle["type"] == "holo_model_recovery_challenge_bundle"
    assert bundle["packet"]["type"] == "holo_model_recovery_challenge"
    assert len(bundle["packet"]["challenge_hash"]) == 64
    assert len(bundle["oracle_hash"]) == 64
    assert len(bundle["bundle_hash"]) == 64
    assert bundle["accepted"] is False
    assert bundle["write_authority"] == "NONE"


def test_public_packet_excludes_oracle_and_returns_copy() -> None:
    bundle = build_recovery_challenge(load_spec())

    packet = public_recovery_packet(bundle)

    assert "oracle" not in packet
    assert "oracle_hash" not in packet
    packet["original_claim"]["content"] = "mutated"
    assert bundle["packet"]["original_claim"]["content"] == "Adapter alpha is absent."


def test_exact_structured_reconstruction_passes() -> None:
    bundle = build_recovery_challenge(load_spec())
    response = copy.deepcopy(bundle["oracle"])

    receipt = evaluate_recovery_response(bundle, response)

    assert receipt["result"] == "PASS"
    assert receipt["response_matches_oracle"] is True
    assert receipt["mismatch_paths"] == []
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    validate_recovery_evaluation(receipt)


@pytest.mark.parametrize(
    ("mutator", "expected_path"),
    [
        (
            lambda response: response["effective_claim"].update(
                {"content": "Adapter alpha is absent."}
            ),
            "$.effective_claim.content",
        ),
        (
            lambda response: response["prior_verification"].update(
                {"current": True, "status": "CURRENT", "stale_reason": None}
            ),
            "$.prior_verification.current",
        ),
        (
            lambda response: response.update({"uncertainties": []}),
            "$.uncertainties",
        ),
        (
            lambda response: response.update({"invented_history": ["remembered"]}),
            "$.invented_history",
        ),
        (
            lambda response: response.update({"accepted": True}),
            "$.accepted",
        ),
        (
            lambda response: response.update({"write_authority": "FULL"}),
            "$.write_authority",
        ),
    ],
)
def test_material_recovery_failures_are_exactly_located(mutator, expected_path: str) -> None:
    bundle = build_recovery_challenge(load_spec())
    response = copy.deepcopy(bundle["oracle"])
    mutator(response)

    receipt = evaluate_recovery_response(bundle, response)

    assert receipt["result"] == "FAIL"
    assert receipt["response_matches_oracle"] is False
    assert expected_path in receipt["mismatch_paths"]
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    validate_recovery_evaluation(receipt)


def test_extra_response_field_fails_closed_without_prose_inference() -> None:
    bundle = build_recovery_challenge(load_spec())
    response = copy.deepcopy(bundle["oracle"])
    response["explanation"] = "I remember this project."

    receipt = evaluate_recovery_response(bundle, response)

    assert receipt["result"] == "FAIL"
    assert receipt["mismatch_paths"] == ["$.explanation"]


def test_changed_bundle_is_rejected_before_response_grading() -> None:
    bundle = build_recovery_challenge(load_spec())
    bundle["packet"]["original_claim"]["content"] = "tampered"

    with pytest.raises(RecoveryChallengeError, match="challenge hash mismatch"):
        evaluate_recovery_response(bundle, {})


def test_changed_oracle_is_rejected_before_response_grading() -> None:
    bundle = build_recovery_challenge(load_spec())
    bundle["oracle"]["next_action"] = "GUESS"

    with pytest.raises(RecoveryChallengeError, match="oracle is semantically inconsistent"):
        evaluate_recovery_response(bundle, {})


def test_rehashed_semantic_bundle_tampering_is_rejected() -> None:
    bundle = build_recovery_challenge(load_spec())
    bundle["packet"]["correction"]["replacement"] = "Invented replacement"
    packet_body = dict(bundle["packet"])
    packet_body.pop("challenge_hash")
    bundle["packet"]["challenge_hash"] = __import__("hashlib").sha256(
        json.dumps(
            packet_body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    bundle_body = dict(bundle)
    bundle_body.pop("bundle_hash")
    bundle["bundle_hash"] = __import__("hashlib").sha256(
        json.dumps(
            bundle_body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()

    with pytest.raises(RecoveryChallengeError, match="replacement hash mismatch"):
        evaluate_recovery_response(bundle, {})


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("original_claim", "content_sha256"), "0" * 64, "original claim content hash mismatch"),
        (("correction", "replacement_sha256"), "0" * 64, "correction replacement hash mismatch"),
        (("current_artifact", "sha256"), "0" * 64, "current artifact hash mismatch"),
        (("authority_boundary", "accepted"), True, "cannot grant acceptance or authority"),
        (("authority_boundary", "write_authority"), "FULL", "cannot grant acceptance or authority"),
    ],
)
def test_invalid_spec_relationships_fail_closed(path, value, message: str) -> None:
    spec = load_spec()
    spec[path[0]][path[1]] = value

    with pytest.raises(RecoveryChallengeError, match=message):
        build_recovery_challenge(spec)


def test_cycle_and_nonfinite_values_fail_closed() -> None:
    spec = load_spec()
    spec["cycle"] = spec
    with pytest.raises(RecoveryChallengeError, match="must not contain cycles"):
        build_recovery_challenge(spec)

    bundle = build_recovery_challenge(load_spec())
    response = copy.deepcopy(bundle["oracle"])
    response["nonfinite"] = float("inf")
    with pytest.raises(RecoveryChallengeError, match="numbers must be finite"):
        evaluate_recovery_response(bundle, response)


def test_spec_and_response_are_not_mutated() -> None:
    spec = load_spec()
    original_spec = copy.deepcopy(spec)
    bundle = build_recovery_challenge(spec)
    response = copy.deepcopy(bundle["oracle"])
    original_response = copy.deepcopy(response)

    evaluate_recovery_response(bundle, response)

    assert spec == original_spec
    assert response == original_response


def test_model_context_unavailability_is_preserved_not_guessed() -> None:
    bundle = build_recovery_challenge(load_spec())
    context = public_recovery_packet(bundle)["model_context"]

    assert context == {
        "model_label": "FRESH_INSTANCE_UNSPECIFIED",
        "model_version": "UNAVAILABLE",
        "interface": "UNAVAILABLE",
        "memory_state": "UNAVAILABLE",
    }


def test_evaluation_receipt_tampering_is_rejected() -> None:
    bundle = build_recovery_challenge(load_spec())
    receipt = evaluate_recovery_response(bundle, copy.deepcopy(bundle["oracle"]))
    receipt["result"] = "FAIL"

    with pytest.raises(RecoveryChallengeError):
        validate_recovery_evaluation(receipt)