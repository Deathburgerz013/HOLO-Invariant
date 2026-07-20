import copy

import pytest

from holosim.hook_contract import (
    HookContractError,
    build_hook_request,
    build_hook_result,
    validate_hook_request,
    validate_hook_result,
)


def _request():
    return build_hook_request(
        hook_id="pytest",
        action="run-tests",
        reference="verify current branch",
        payload={"targets": ["tests/test_example.py"], "mode": "focused"},
    )


def test_hook_request_is_deterministic_and_non_authoritative():
    left = _request()
    right = _request()

    assert left == right
    assert left["execution_status"] == "NOT_EXECUTED"
    assert left["accepted"] is False
    assert left["write_authority"] == "NONE"
    assert validate_hook_request(left) is True


def test_hook_result_binds_evidence_to_exact_request():
    request = _request()
    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"returncode": 0, "summary": "5 passed"},
    )

    assert result["request_hash"] == request["request_hash"]
    assert result["hook_id"] == "pytest"
    assert result["status"] == "OBSERVED"
    assert result["mutation_applied"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert validate_hook_result(result, request=request) is True


def test_failed_and_unavailable_are_evidence_statuses_not_authority():
    request = _request()

    failed = build_hook_result(
        request=request,
        status="FAILED",
        evidence={"returncode": 1, "summary": "1 failed"},
    )
    unavailable = build_hook_result(
        request=request,
        status="UNAVAILABLE",
        evidence={"reason": "pytest not installed"},
    )

    assert validate_hook_result(failed, request=request) is True
    assert validate_hook_result(unavailable, request=request) is True
    assert failed["accepted"] is False
    assert unavailable["write_authority"] == "NONE"


def test_result_cannot_be_rebound_to_different_request():
    request = _request()
    other = build_hook_request(
        hook_id="pytest",
        action="run-tests",
        reference="different reference",
        payload={"targets": ["tests/test_example.py"], "mode": "focused"},
    )
    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"returncode": 0},
    )

    with pytest.raises(HookContractError, match="different request|reference"):
        validate_hook_result(result, request=other)


def test_tampered_request_is_rejected():
    request = _request()
    request["payload"]["mode"] = "full"

    with pytest.raises(HookContractError, match="hash mismatch"):
        validate_hook_request(request)


def test_tampered_result_is_rejected():
    request = _request()
    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"returncode": 0, "summary": "5 passed"},
    )
    result["evidence"]["summary"] = "500 passed"

    with pytest.raises(HookContractError, match="hash mismatch"):
        validate_hook_result(result, request=request)


def test_request_cannot_claim_execution_or_authority():
    request = _request()

    execution_claim = copy.deepcopy(request)
    execution_claim["execution_status"] = "EXECUTED"
    with pytest.raises(HookContractError, match="cannot claim execution"):
        validate_hook_request(execution_claim)

    authority_claim = copy.deepcopy(request)
    authority_claim["accepted"] = True
    with pytest.raises(HookContractError, match="cannot grant"):
        validate_hook_request(authority_claim)


def test_result_cannot_claim_mutation_or_authority():
    request = _request()
    result = build_hook_result(
        request=request,
        status="OBSERVED",
        evidence={"returncode": 0},
    )

    mutation_claim = copy.deepcopy(result)
    mutation_claim["mutation_applied"] = True
    with pytest.raises(HookContractError, match="cannot claim mutation"):
        validate_hook_result(mutation_claim, request=request)

    authority_claim = copy.deepcopy(result)
    authority_claim["write_authority"] = "SELF"
    with pytest.raises(HookContractError, match="cannot grant"):
        validate_hook_result(authority_claim, request=request)


def test_nonfinite_and_cyclic_payloads_fail_closed():
    with pytest.raises(HookContractError, match="finite"):
        build_hook_request(
            hook_id="x",
            action="observe",
            reference="r",
            payload={"value": float("inf")},
        )

    cyclic = {}
    cyclic["self"] = cyclic
    with pytest.raises(HookContractError, match="cycles"):
        build_hook_request(
            hook_id="x",
            action="observe",
            reference="r",
            payload=cyclic,
        )


def test_invalid_result_status_fails_closed():
    request = _request()

    with pytest.raises(HookContractError, match="OBSERVED"):
        build_hook_result(
            request=request,
            status="SUCCESS",
            evidence={},
        )
