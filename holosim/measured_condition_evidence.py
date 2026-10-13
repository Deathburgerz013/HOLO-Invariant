"""Derive bounded condition evidence from an existing permitted file observation.

Research boundary: structural validation and deterministic measurement only.
No independent signer authentication, acceptance, execution, or write authority.
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from typing import Any, Mapping

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.hook_contract import (
    HookContractError,
    build_hook_request,
    build_hook_result,
    validate_hook_request,
    validate_hook_result,
)


class MeasuredConditionEvidenceError(ValueError):
    """A measured condition cannot be justified from the supplied receipt."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except (CanonicalValueError, TypeError, ValueError) as exc:
        raise MeasuredConditionEvidenceError(
            "receipt contains invalid canonical data"
        ) from exc


def _required_text(value: Any, field: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise MeasuredConditionEvidenceError(
            f"{field} must be a nonempty plain string without outer whitespace"
        )
    return value


def _sha256(value: Any, field: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise MeasuredConditionEvidenceError(
            f"{field} must be a lowercase SHA-256 hexadecimal digest"
        )
    return value


def derive_measured_condition_evidence(
    *,
    permitted_run: Mapping[str, Any],
    condition_id: str,
    claim_set_hash: str,
    expected_content_sha256: str,
) -> dict[str, Any]:
    """Derive an exact file-hash condition from a permitted observation receipt.

    This validates the supplied receipt's internal structure and hash bindings.
    It cannot independently establish who performed the observation or whether
    the recorded permit was genuinely authorized.
    """
    condition_id = _required_text(condition_id, "condition_id")
    claim_set_hash = _sha256(claim_set_hash, "claim_set_hash")
    expected_content_sha256 = _sha256(
        expected_content_sha256, "expected_content_sha256"
    )

    if type(permitted_run) is not dict:
        raise MeasuredConditionEvidenceError(
            "permitted_run must be a plain dictionary"
        )

    expected_run_fields = {
        "type",
        "version",
        "selection",
        "permit_verification",
        "decision",
        "reason",
        "observation_performed",
        "observation_result",
        "accepted",
        "write_authority",
        "execution_authority",
        "run_hash",
    }
    if set(permitted_run) != expected_run_fields:
        raise MeasuredConditionEvidenceError("run fields do not match schema")

    if (
        permitted_run["type"] != "permitted_aligned_observation"
        or permitted_run["version"] != 1
        or permitted_run["decision"] != "OBSERVED"
        or permitted_run["observation_performed"] is not True
        or permitted_run["accepted"] is not False
        or permitted_run["write_authority"] != "NONE"
        or permitted_run["execution_authority"] != "NONE"
    ):
        raise MeasuredConditionEvidenceError(
            "run is not a completed, non-authoritative permitted observation"
        )

    run_body = {
        key: value for key, value in permitted_run.items() if key != "run_hash"
    }
    if _hash(run_body) != permitted_run["run_hash"]:
        raise MeasuredConditionEvidenceError("run hash does not match run body")

    verification = permitted_run["permit_verification"]
    if (
        type(verification) is not dict
        or verification.get("verified") is not True
        or verification.get("status") != "VERIFIED"
    ):
        raise MeasuredConditionEvidenceError(
            "run does not record successful permit verification"
        )

    selection = permitted_run["selection"]
    if type(selection) is not dict:
        raise MeasuredConditionEvidenceError("selection must be a dictionary")

    selection_body = {
        key: value
        for key, value in selection.items()
        if key != "selection_hash"
    }
    if _hash(selection_body) != selection.get("selection_hash"):
        raise MeasuredConditionEvidenceError(
            "selection hash does not match selection body"
        )

    source_request = selection.get("selected_request")

    evaluations = selection.get("evaluations")
    selected_id = selection.get("selected_candidate_id")

    if (
        selection.get("decision") != "SELECTED"
        or type(selected_id) is not str
        or not selected_id
        or type(evaluations) is not list
    ):
        raise MeasuredConditionEvidenceError(
            "selection does not describe a selected candidate"
        )

    matches = [
        item
        for item in evaluations
        if type(item) is dict and item.get("candidate_id") == selected_id
    ]

    if (
        len(matches) != 1
        or matches[0].get("eligible") is not True
        or matches[0].get("request") != source_request
    ):
        raise MeasuredConditionEvidenceError(
            "selected candidate is not bound to its eligible evaluation"
        )
    source_result = permitted_run["observation_result"]

    try:
        validate_hook_request(source_request)
        validate_hook_result(source_result, request=source_request)
    except (HookContractError, TypeError, KeyError) as exc:
        raise MeasuredConditionEvidenceError(
            "source observation hook is invalid"
        ) from exc

    if (
        source_request["action"] != "read_text"
        or source_request["payload"] != {"encoding": "utf-8"}
        or source_result["status"] != "OBSERVED"
    ):
        raise MeasuredConditionEvidenceError(
            "source must be an observed UTF-8 read_text operation"
        )

    evidence = source_result["evidence"]
    if type(evidence) is not dict:
        raise MeasuredConditionEvidenceError(
            "source evidence must be a dictionary"
        )

    content = evidence.get("content")
    byte_count = evidence.get("byte_count")
    recorded_hash = evidence.get("content_sha256")

    if type(content) is not str or type(byte_count) is not int:
        raise MeasuredConditionEvidenceError(
            "source content or byte count is invalid"
        )

    _sha256(recorded_hash, "source content_sha256")

    try:
        actual_bytes = content.encode("utf-8")
    except UnicodeError as exc:
        raise MeasuredConditionEvidenceError(
            "source content cannot be encoded as UTF-8"
        ) from exc
    actual_hash = hashlib.sha256(actual_bytes).hexdigest()

    if byte_count != len(actual_bytes) or recorded_hash != actual_hash:
        raise MeasuredConditionEvidenceError(
            "observed content does not match its byte count and SHA-256"
        )

    condition_request = build_hook_request(
        hook_id="measured-condition-evidence",
        action="verify-claim-condition",
        reference=condition_id,
        payload={
            "condition_id": condition_id,
            "claim_set_hash": claim_set_hash,
        },
    )

    condition_result = build_hook_result(
        request=condition_request,
        status="OBSERVED",
        evidence={
            "condition_satisfied": actual_hash == expected_content_sha256
        },
    )

    body = {
        "type": "measured_condition_evidence",
        "version": 1,
        "condition_id": condition_id,
        "claim_set_hash": claim_set_hash,
        "expected_content_sha256": expected_content_sha256,
        "observed_content_sha256": actual_hash,
        "source_run_hash": permitted_run["run_hash"],
        "source_observation_result_hash": source_result["result_hash"],
        "source_run": deepcopy(permitted_run),
        "condition_evidence": {
            "request": condition_request,
            "result": condition_result,
        },
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "This receipt deterministically compares supplied observed content "
            "against a declared digest. It does not independently authenticate "
            "the permit signer, establish external truth, accept a correction, "
            "or grant mutation or execution authority."
        ),
    }
    return {**body, "derivation_hash": _hash(body)}


def validate_measured_condition_evidence(receipt: Mapping[str, Any]) -> bool:
    """Regenerate a measured condition receipt and require exact equality."""
    if type(receipt) is not dict:
        raise MeasuredConditionEvidenceError(
            "receipt must be a plain dictionary"
        )

    expected_fields = {
        "type",
        "version",
        "condition_id",
        "claim_set_hash",
        "expected_content_sha256",
        "observed_content_sha256",
        "source_run_hash",
        "source_observation_result_hash",
        "source_run",
        "condition_evidence",
        "accepted",
        "write_authority",
        "execution_authority",
        "interpretation_notice",
        "derivation_hash",
    }

    if set(receipt) != expected_fields:
        raise MeasuredConditionEvidenceError(
            "receipt fields do not match schema"
        )

    if receipt["type"] != "measured_condition_evidence" or receipt["version"] != 1:
        raise MeasuredConditionEvidenceError(
            "receipt type or version is invalid"
        )

    try:
        rebuilt = derive_measured_condition_evidence(
            permitted_run=receipt["source_run"],
            condition_id=receipt["condition_id"],
            claim_set_hash=receipt["claim_set_hash"],
            expected_content_sha256=receipt["expected_content_sha256"],
        )
    except (KeyError, TypeError) as exc:
        raise MeasuredConditionEvidenceError(
            "receipt contains malformed source data"
        ) from exc

    if rebuilt != receipt:
        raise MeasuredConditionEvidenceError(
            "receipt does not match reconstructed measurement"
        )

    return True
