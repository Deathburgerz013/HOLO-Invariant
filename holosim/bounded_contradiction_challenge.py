"""Bounded contradiction challenge receipts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any


RECEIPT_TYPE = "bounded_contradiction_challenge"
RECEIPT_VERSION = 1

CONTRADICTION_FOUND = "CONTRADICTION_FOUND"
NO_CONTRADICTION_FOUND = "NO_CONTRADICTION_FOUND"
SEARCH_INSUFFICIENT = "SEARCH_INSUFFICIENT"


class BoundedContradictionChallengeError(ValueError):
    """Raised when contradiction-challenge inputs are malformed."""


def _hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise BoundedContradictionChallengeError(
            f"{field} must be a nonempty string"
        )
    return value


def _checks(
    checks: Mapping[str, Callable[[Any, Any], Any]],
) -> dict[str, Callable[[Any, Any], Any]]:
    if not isinstance(checks, Mapping) or not checks:
        raise BoundedContradictionChallengeError(
            "checks must be a nonempty mapping"
        )

    result: dict[str, Callable[[Any, Any], Any]] = {}

    for check_id in sorted(checks):
        _text(check_id, "check id")
        check = checks[check_id]

        if not callable(check):
            raise BoundedContradictionChallengeError(
                f"check {check_id} must be callable"
            )

        result[check_id] = check

    return result


def challenge_for_contradiction(
    *,
    challenge_id: str,
    target_state_hash: str,
    evidence_hash: str,
    state: Any,
    evidence: Any,
    checks: Mapping[str, Callable[[Any, Any], Any]],
) -> dict[str, Any]:
    """Run a bounded declared challenge against one state/evidence pair.

    A check returning True is interpreted as a contradiction.
    A check returning False is interpreted as no contradiction.
    Exceptions or non-boolean results make the search insufficient.

    This function does not establish truth, authorize a transition,
    mutate state, or grant authority.
    """

    challenge_id = _text(challenge_id, "challenge_id")
    target_state_hash = _text(target_state_hash, "target_state_hash")
    evidence_hash = _text(evidence_hash, "evidence_hash")

    declared_checks = _checks(checks)

    check_results: dict[str, str] = {}
    contradictions: list[str] = []
    insufficient_checks: list[str] = []

    for check_id in sorted(declared_checks):
        try:
            result = declared_checks[check_id](state, evidence)
        except Exception:
            insufficient_checks.append(check_id)
            continue

        if type(result) is not bool:
            insufficient_checks.append(check_id)
            continue

        if result:
            check_results[check_id] = CONTRADICTION_FOUND
            contradictions.append(check_id)
        else:
            check_results[check_id] = NO_CONTRADICTION_FOUND

    if insufficient_checks:
        status = SEARCH_INSUFFICIENT
    elif contradictions:
        status = CONTRADICTION_FOUND
    else:
        status = NO_CONTRADICTION_FOUND

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "challenge_id": challenge_id,
        "target_state_hash": target_state_hash,
        "evidence_hash": evidence_hash,
        "declared_checks": sorted(declared_checks),
        "check_results": check_results,
        "contradictions_found": contradictions,
        "insufficient_checks": insufficient_checks,
        "search_complete": not insufficient_checks,
        "result": status,
        "truth_verified": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {
        **body,
        "receipt_id": _hash(body),
    }


def verify_bounded_contradiction_challenge_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify structural integrity and semantic consistency."""

    violations: list[str] = []

    if not isinstance(receipt, Mapping):
        return {
            "valid": False,
            "violations": ["receipt must be a mapping"],
            "accepted": False,
            "write_authority": "NONE",
        }

    receipt_id = receipt.get("receipt_id")

    if not isinstance(receipt_id, str) or not receipt_id:
        violations.append("receipt_id must be a nonempty string")

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_id"
    }

    if isinstance(receipt_id, str) and receipt_id:
        try:
            if _hash(body) != receipt_id:
                violations.append("receipt_id does not match content")
        except (TypeError, ValueError):
            violations.append("receipt content is not canonical")

    if receipt.get("type") != RECEIPT_TYPE:
        violations.append("type does not match")

    if receipt.get("version") != RECEIPT_VERSION:
        violations.append("version does not match")

    declared = receipt.get("declared_checks")
    results = receipt.get("check_results")
    contradictions = receipt.get("contradictions_found")
    insufficient = receipt.get("insufficient_checks")

    if not isinstance(declared, list) or not all(
        type(item) is str and item.strip()
        for item in declared
    ):
        violations.append(
            "declared_checks must contain nonempty strings"
        )

    if not isinstance(results, Mapping):
        violations.append("check_results must be a mapping")

    if not isinstance(contradictions, list):
        violations.append("contradictions_found must be a list")

    if not isinstance(insufficient, list):
        violations.append("insufficient_checks must be a list")

    if (
        isinstance(declared, list)
        and isinstance(results, Mapping)
        and isinstance(contradictions, list)
        and isinstance(insufficient, list)
    ):
        declared_set = set(declared)
        result_set = set(results)
        contradiction_set = set(contradictions)
        insufficient_set = set(insufficient)

        if len(declared_set) != len(declared):
            violations.append("declared_checks must contain unique ids")

        if result_set - declared_set:
            violations.append(
                "check_results contain undeclared checks"
            )

        if contradiction_set - declared_set:
            violations.append(
                "contradictions_found contain undeclared checks"
            )

        if insufficient_set - declared_set:
            violations.append(
                "insufficient_checks contain undeclared checks"
            )

        if contradiction_set & insufficient_set:
            violations.append(
                "checks cannot be both contradictory and insufficient"
            )

        for check_id, result in results.items():
            if result not in {
                CONTRADICTION_FOUND,
                NO_CONTRADICTION_FOUND,
            }:
                violations.append(
                    f"check result {check_id} has unsupported status"
                )

        expected_contradictions = {
            check_id
            for check_id, result in results.items()
            if result == CONTRADICTION_FOUND
        }

        expected_noncontradictions = {
            check_id
            for check_id, result in results.items()
            if result == NO_CONTRADICTION_FOUND
        }

        if contradiction_set != expected_contradictions:
            violations.append(
                "contradictions_found does not match check_results"
            )

        if (
            result_set
            != expected_contradictions | expected_noncontradictions
        ):
            violations.append(
                "check_results contain invalid result coverage"
            )

        if result_set & insufficient_set:
            violations.append(
                "a check cannot have both a result and insufficient status"
            )

        expected_complete = not insufficient

        if receipt.get("search_complete") is not expected_complete:
            violations.append(
                "search_complete does not match insufficient_checks"
            )

        if expected_complete:
            if contradictions:
                expected_result = CONTRADICTION_FOUND
            else:
                expected_result = NO_CONTRADICTION_FOUND

            if receipt.get("result") != expected_result:
                violations.append(
                    "result does not match completed check results"
                )
        elif receipt.get("result") != SEARCH_INSUFFICIENT:
            violations.append(
                "result must be SEARCH_INSUFFICIENT when checks are insufficient"
            )

    if receipt.get("result") not in {
        CONTRADICTION_FOUND,
        NO_CONTRADICTION_FOUND,
        SEARCH_INSUFFICIENT,
    }:
        violations.append("result has unsupported status")

    if receipt.get("truth_verified") is not False:
        violations.append("truth_verified must be False")

    if receipt.get("truth_claimed") is not False:
        violations.append("truth_claimed must be False")

    if receipt.get("accepted") is not False:
        violations.append("accepted must be False")

    if receipt.get("write_authority") != "NONE":
        violations.append("write_authority must be NONE")

    if receipt.get("execution_authority") != "NONE":
        violations.append("execution_authority must be NONE")

    return {
        "valid": not violations,
        "violations": violations,
        "accepted": False,
        "write_authority": "NONE",
    }