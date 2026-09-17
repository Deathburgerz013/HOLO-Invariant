"""Exact, non-executable work requests from current supervisor decisions."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from holosim.canonical import stable_hash
from holosim.deterministic_supervisor import (
    STATE_RUN,
    decide_supervisor_state,
)


REQUEST_TYPE = "holo_supervisor_work_request"
REQUEST_VERSION = 1
REQUEST_STATUS = "DECLARED_NOT_AUTHORIZED"
SHA256 = re.compile(r"[0-9a-f]{64}")

REQUEST_FIELDS = {
    "type",
    "version",
    "request_status",
    "decision_hash",
    "chain_source_sha256",
    "projection_hash",
    "work_id",
    "work_payload_sha256",
    "authorization_required",
    "action_performed",
    "recovery_performed",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "promotion_authority",
    "interpretation_notice",
    "request_hash",
}

_NOTICE = (
    "This request binds one current RUN decision to one declared pending work "
    "identity and one externally supplied payload digest. It does not inspect "
    "or prove the payload's meaning, availability, safety, or origin. It does "
    "not execute work or grant acceptance, write, execution, promotion, "
    "recovery, or operational authority. Source state may change after the "
    "decision is recomputed."
)


class SupervisorWorkRequestError(ValueError):
    """Raised when a supervisor decision cannot produce an exact work request."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise SupervisorWorkRequestError(f"{field} must be nonempty text")
    return value.strip()


def _digest(value: Any, field: str) -> str:
    value = _text(value, field)
    if SHA256.fullmatch(value) is None:
        raise SupervisorWorkRequestError(
            f"{field} must be lowercase SHA-256"
        )
    return value


def build_supervisor_work_request(
    chain_path: str | Path,
    validity_history: Sequence[Mapping[str, Any]],
    decision: Mapping[str, Any],
    *,
    current_environment_fingerprint: str,
    required_claim_ids: Sequence[str],
    pending_work_ids: Sequence[str],
    selected_work_id: str,
    work_payload_sha256: str,
    genesis_hash: str = "0" * 64,
) -> dict[str, Any]:
    """Recompute one RUN decision and bind one pending work identity to it."""
    if type(decision) is not dict:
        raise SupervisorWorkRequestError("decision must be a plain object")

    recomputed = decide_supervisor_state(
        chain_path,
        validity_history,
        current_environment_fingerprint=current_environment_fingerprint,
        required_claim_ids=required_claim_ids,
        pending_work_ids=pending_work_ids,
        genesis_hash=genesis_hash,
    )
    if decision != recomputed:
        raise SupervisorWorkRequestError(
            "decision does not match current recomputation"
        )
    if recomputed["state"] != STATE_RUN:
        raise SupervisorWorkRequestError("decision state is not RUN")

    work_id = _text(selected_work_id, "selected_work_id")
    if work_id not in recomputed["pending_work_ids"]:
        raise SupervisorWorkRequestError(
            "selected_work_id is not declared pending work"
        )

    body = {
        "type": REQUEST_TYPE,
        "version": REQUEST_VERSION,
        "request_status": REQUEST_STATUS,
        "decision_hash": recomputed["decision_hash"],
        "chain_source_sha256": recomputed["chain_observation"][
            "source_sha256"
        ],
        "projection_hash": recomputed["invariant_projection"][
            "projection_hash"
        ],
        "work_id": work_id,
        "work_payload_sha256": _digest(
            work_payload_sha256,
            "work_payload_sha256",
        ),
        "authorization_required": True,
        "action_performed": False,
        "recovery_performed": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "promotion_authority": "NONE",
        "interpretation_notice": _NOTICE,
    }
    return {**body, "request_hash": stable_hash(body)}


def validate_supervisor_work_request(
    chain_path: str | Path,
    validity_history: Sequence[Mapping[str, Any]],
    decision: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    current_environment_fingerprint: str,
    required_claim_ids: Sequence[str],
    pending_work_ids: Sequence[str],
    genesis_hash: str = "0" * 64,
) -> bool:
    """Regenerate an exact request against current source observations."""
    if type(request) is not dict or set(request) != REQUEST_FIELDS:
        raise SupervisorWorkRequestError(
            "request fields do not match the versioned schema"
        )
    try:
        rebuilt = build_supervisor_work_request(
            chain_path,
            validity_history,
            decision,
            current_environment_fingerprint=current_environment_fingerprint,
            required_claim_ids=required_claim_ids,
            pending_work_ids=pending_work_ids,
            selected_work_id=request["work_id"],
            work_payload_sha256=request["work_payload_sha256"],
            genesis_hash=genesis_hash,
        )
    except (KeyError, TypeError) as exc:
        raise SupervisorWorkRequestError("request is malformed") from exc
    if rebuilt != request:
        raise SupervisorWorkRequestError("request identity is invalid")
    return True
