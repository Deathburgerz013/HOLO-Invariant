"""Deterministic, read-only lifecycle decisions for Holo/Sim runtime work."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from holosim.holochain_terminal_tail_diagnosis import (
    STATUS_CLEAN,
    STATUS_INTERIOR_INTEGRITY_FAILURE,
    STATUS_TERMINAL_INVALID_RECORD,
    diagnose_holochain_terminal_tail,
)
from holosim.invariant_validity_lifecycle import project_active_invariants


DECISION_TYPE = "holo_deterministic_supervisor_decision"
DECISION_VERSION = 1

STATE_WAIT = "WAIT"
STATE_RUN = "RUN"
STATE_BLOCK = "BLOCK"
STATE_RECOVER = "RECOVER"

REASON_CHAIN_SOURCE_MISSING = "CHAIN_SOURCE_MISSING"
REASON_CHAIN_INTERIOR_FAILURE = "CHAIN_INTERIOR_INTEGRITY_FAILURE"
REASON_CHAIN_TERMINAL_INVALID = "CHAIN_TERMINAL_INVALID_RECORD"
REASON_REQUIRED_INVARIANT_UNAVAILABLE = "REQUIRED_INVARIANT_UNAVAILABLE"
REASON_PENDING_WORK_READY = "PENDING_WORK_READY"
REASON_NO_PENDING_WORK = "NO_PENDING_WORK"

_NOTICE = (
    "This is a deterministic read-only lifecycle decision over the embedded "
    "chain observation, invariant projection, and declared work identities. "
    "It does not prove the supplied validity history came from the observed "
    "chain. "
    "RUN does not execute work. RECOVER identifies a recovery need but does "
    "not authorize recovery. No state grants truth, acceptance, write, "
    "execution, promotion, or operational authority."
)


class DeterministicSupervisorError(ValueError):
    """Raised when supervisor inputs are not closed and deterministic."""


def _canonical_hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DeterministicSupervisorError(
            "supervisor decision is not closed JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _identifier_list(value: Any, field: str) -> list[str]:
    if type(value) not in {list, tuple}:
        raise DeterministicSupervisorError(f"{field} must be a list or tuple")
    normalized: list[str] = []
    for item in value:
        if type(item) is not str or not item.strip():
            raise DeterministicSupervisorError(
                f"{field} must contain nonempty strings"
            )
        normalized.append(item.strip())
    if len(normalized) != len(set(normalized)):
        raise DeterministicSupervisorError(f"{field} contains duplicate ids")
    return sorted(normalized)


def decide_supervisor_state(
    chain_path: str | Path,
    validity_history: Sequence[Mapping[str, Any]],
    *,
    current_environment_fingerprint: str,
    required_claim_ids: Sequence[str],
    pending_work_ids: Sequence[str],
    genesis_hash: str = "0" * 64,
) -> dict[str, Any]:
    """Return one non-executing lifecycle decision from verified observations."""
    required = _identifier_list(required_claim_ids, "required_claim_ids")
    pending = _identifier_list(pending_work_ids, "pending_work_ids")
    chain_observation = diagnose_holochain_terminal_tail(
        chain_path,
        genesis_hash=genesis_hash,
    )
    projection = project_active_invariants(
        validity_history,
        current_environment_fingerprint=current_environment_fingerprint,
    )

    active_by_id = {
        item["claim_id"]: item for item in projection["active_claims"]
    }
    excluded_by_id = {
        item["claim_id"]: item for item in projection["excluded_claims"]
    }
    satisfied = [claim_id for claim_id in required if claim_id in active_by_id]
    unavailable = []
    for claim_id in required:
        if claim_id in active_by_id:
            continue
        excluded = excluded_by_id.get(claim_id)
        unavailable.append(
            {
                "claim_id": claim_id,
                "reason": (
                    excluded["exclusion_reason"]
                    if excluded is not None
                    else "MISSING"
                ),
            }
        )

    chain_status = chain_observation["status"]
    if not chain_observation["source_exists"]:
        state = STATE_BLOCK
        reasons = [REASON_CHAIN_SOURCE_MISSING]
    elif chain_status == STATUS_INTERIOR_INTEGRITY_FAILURE:
        state = STATE_BLOCK
        reasons = [REASON_CHAIN_INTERIOR_FAILURE]
    elif chain_status == STATUS_TERMINAL_INVALID_RECORD:
        state = STATE_RECOVER
        reasons = [REASON_CHAIN_TERMINAL_INVALID]
    elif chain_status != STATUS_CLEAN:
        raise DeterministicSupervisorError("chain diagnosis status is unsupported")
    elif unavailable:
        state = STATE_BLOCK
        reasons = [REASON_REQUIRED_INVARIANT_UNAVAILABLE]
    elif pending:
        state = STATE_RUN
        reasons = [REASON_PENDING_WORK_READY]
    else:
        state = STATE_WAIT
        reasons = [REASON_NO_PENDING_WORK]

    body = {
        "type": DECISION_TYPE,
        "version": DECISION_VERSION,
        "state": state,
        "reasons": reasons,
        "chain_observation": chain_observation,
        "invariant_projection": projection,
        "required_claim_ids": required,
        "satisfied_required_claim_ids": satisfied,
        "unavailable_required_claims": unavailable,
        "pending_work_ids": pending,
        "action_performed": False,
        "recovery_performed": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "promotion_authority": "NONE",
        "interpretation_notice": _NOTICE,
    }
    return {**body, "decision_hash": _canonical_hash(body)}
