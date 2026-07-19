from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from holosim.recovery import build_recovery_challenge
from holosim.recovery_runner import (
    MAX_TEXT_UTF8_BYTES,
    RecoveryRunnerError,
    build_recovery_run_request,
    record_recovery_run_response,
    validate_recovery_run_receipt,
    validate_recovery_run_request,
)


SPEC_PATH = Path(__file__).parents[1] / "docs" / "Model_Recovery_Behavior_Challenge_001.json"


def load_bundle() -> dict:
    return build_recovery_challenge(json.loads(SPEC_PATH.read_text(encoding="utf-8")))


def build_request(bundle: dict) -> dict:
    return build_recovery_run_request(
        bundle,
        run_id="recovery-run-001",
        provider_label="Example Provider",
        model_label="Example Model",
        model_version="declared-version",
        interface="manual-transfer",
    )


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


def rehash(root: dict, hash_field: str) -> None:
    body = dict(root)
    body.pop(hash_field)
    root[hash_field] = canonical_hash(body)


def test_request_contains_public_packet_without_oracle() -> None:
    bundle = load_bundle()
    request = build_request(bundle)

    assert request["packet"] == bundle["packet"]
    assert "oracle" not in request
    assert "oracle_hash" not in request
    assert "oracle" not in request["packet"]
    assert "oracle_hash" not in request["packet"]
    validate_recovery_run_request(bundle, request)


def test_request_records_only_declared_unauthenticated_target() -> None:
    request = build_request(load_bundle())

    assert request["transport_status"] == "NOT_SENT"
    assert request["authentication_status"] == "NOT_AUTHENTICATED"
    assert request["accepted"] is False
    assert request["write_authority"] == "NONE"
    assert "caller-supplied" in request["interpretation_notice"]


def test_response_receipt_passes_only_for_exact_oracle() -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    receipt = record_recovery_run_response(bundle, request, bundle["oracle"])

    assert receipt["evaluation"]["result"] == "PASS"
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    validate_recovery_run_receipt(bundle, request, receipt)


def test_incorrect_response_is_recorded_as_fail() -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    response = copy.deepcopy(bundle["oracle"])
    response["next_action"] = "GUESS"

    receipt = record_recovery_run_response(bundle, request, response)

    assert receipt["evaluation"]["result"] == "FAIL"
    assert "$.next_action" in receipt["evaluation"]["mismatch_paths"]
    validate_recovery_run_receipt(bundle, request, receipt)


def test_inputs_are_not_mutated() -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    response = copy.deepcopy(bundle["oracle"])
    originals = copy.deepcopy((bundle, request, response))

    record_recovery_run_response(bundle, request, response)

    assert (bundle, request, response) == tuple(originals)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("transport_status", "SENT", "transport status"),
        ("authentication_status", "AUTHENTICATED", "authentication status"),
        ("accepted", True, "acceptance or authority"),
        ("write_authority", "MODEL", "acceptance or authority"),
    ],
)
def test_request_authority_and_transport_claims_fail_closed(
    field: str, value: object, message: str
) -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    request[field] = value
    rehash(request, "request_hash")

    with pytest.raises(RecoveryRunnerError, match=message):
        validate_recovery_run_request(bundle, request)


def test_request_packet_tampering_fails_after_rehash() -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    request["packet"]["model_context"]["model_label"] = "changed"
    packet_body = dict(request["packet"])
    packet_body.pop("challenge_hash")
    request["packet"]["challenge_hash"] = canonical_hash(packet_body)
    rehash(request, "request_hash")

    with pytest.raises(RecoveryRunnerError, match="packet does not match bundle"):
        validate_recovery_run_request(bundle, request)


def test_request_target_tampering_without_hash_update_is_rejected() -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    request["declared_target"]["model_label"] = "changed"

    with pytest.raises(RecoveryRunnerError, match="request hash mismatch"):
        validate_recovery_run_request(bundle, request)


def test_receipt_target_must_match_request_even_after_rehash() -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    receipt = record_recovery_run_response(bundle, request, bundle["oracle"])
    receipt["declared_target"]["model_label"] = "changed"
    rehash(receipt, "receipt_hash")

    with pytest.raises(RecoveryRunnerError, match="target does not match request"):
        validate_recovery_run_receipt(bundle, request, receipt)


def test_receipt_response_tampering_with_stale_evaluation_fails_after_rehash() -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    receipt = record_recovery_run_response(bundle, request, bundle["oracle"])
    receipt["response"]["next_action"] = "GUESS"
    receipt["response_hash"] = canonical_hash(receipt["response"])
    rehash(receipt, "receipt_hash")

    with pytest.raises(RecoveryRunnerError, match="semantically inconsistent"):
        validate_recovery_run_receipt(bundle, request, receipt)


def test_receipt_evaluation_tampering_fails_after_nested_rehash() -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    receipt = record_recovery_run_response(bundle, request, bundle["oracle"])
    receipt["evaluation"]["interpretation_notice"] = "changed"
    rehash(receipt["evaluation"], "receipt_hash")
    rehash(receipt, "receipt_hash")

    with pytest.raises(RecoveryRunnerError, match="semantically inconsistent"):
        validate_recovery_run_receipt(bundle, request, receipt)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda request: request.update(extra=True), "fields do not match"),
        (lambda request: request.update(version=True), "type or version"),
        (lambda request: request.update(run_id=""), "nonempty"),
        (
            lambda request: request["declared_target"].update(model_label=7),
            "nonempty plain string",
        ),
    ],
)
def test_malformed_requests_fail_closed(mutator, message: str) -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    mutator(request)

    with pytest.raises(RecoveryRunnerError, match=message):
        validate_recovery_run_request(bundle, request)


def test_cyclic_request_is_rejected() -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    request["cycle"] = request

    with pytest.raises(RecoveryRunnerError, match="cycles"):
        validate_recovery_run_request(bundle, request)


def test_nonfinite_response_is_rejected() -> None:
    bundle = load_bundle()
    request = build_request(bundle)

    with pytest.raises(RecoveryRunnerError, match="finite"):
        record_recovery_run_response(bundle, request, {"score": float("inf")})


def test_oversized_metadata_is_rejected() -> None:
    bundle = load_bundle()

    with pytest.raises(RecoveryRunnerError, match="cannot exceed"):
        build_recovery_run_request(
            bundle,
            run_id="x" * (MAX_TEXT_UTF8_BYTES + 1),
            provider_label="provider",
            model_label="model",
            model_version="version",
            interface="manual",
        )


def test_bundle_errors_are_converted_to_runner_domain() -> None:
    bundle = load_bundle()
    bundle["accepted"] = True

    with pytest.raises(RecoveryRunnerError, match="bundle is invalid"):
        build_request(bundle)


def test_caller_supplied_response_can_be_replayed_deterministically() -> None:
    bundle = load_bundle()
    request = build_request(bundle)
    response = copy.deepcopy(bundle["oracle"])

    first = record_recovery_run_response(bundle, request, response)
    second = record_recovery_run_response(bundle, request, response)

    assert first == second