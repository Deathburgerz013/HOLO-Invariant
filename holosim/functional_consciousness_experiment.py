"""Deterministic contracts for the functional-consciousness experiment.

This module establishes source-separated world/self state, pre-report internal
monitoring, and bounded one-slot workspace admission for the deterministic
reference experiment. It does not broadcast control action,
establish subjective consciousness, accept a result, or grant write or
execution authority.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

from holosim.canonical import stable_hash
from holosim.verified_cold_start_reentry_gateway import (
    VerifiedColdStartReentryError,
    validate_verified_cold_start_reentry_packet,
)


RECEIPT_TYPE = "functional_consciousness_experiment_input_receipt"
RECEIPT_VERSION = 1
MAX_JSON_DEPTH = 10
MAX_ITEMS = 10_000
MAX_TEXT_UTF8_BYTES = 16_384

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_SHA256 = re.compile(r"[0-9a-f]{64}")

_RECEIPT_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "world_source_id",
    "self_source_id",
    "world_state_hash",
    "self_state_hash",
    "sources_separated",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}


class FunctionalConsciousnessExperimentError(ValueError):
    """Raised when experiment input or receipt violates the contract."""


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise FunctionalConsciousnessExperimentError(f"{label} is invalid")
    return value


def _sha256(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise FunctionalConsciousnessExperimentError(
            f"{label} must be SHA-256"
        )
    return value


def _canonical(value: Any, *, label: str) -> Any:
    active: set[int] = set()
    count = 0

    def visit(item: Any, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_ITEMS:
            raise FunctionalConsciousnessExperimentError(
                f"{label} exceeds item limit"
            )
        if depth > MAX_JSON_DEPTH:
            raise FunctionalConsciousnessExperimentError(
                f"{label} exceeds maximum depth"
            )

        if item is None or type(item) in {bool, int}:
            return

        if type(item) is float:
            if not math.isfinite(item):
                raise FunctionalConsciousnessExperimentError(
                    f"{label} numbers must be finite"
                )
            return

        if type(item) is str:
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise FunctionalConsciousnessExperimentError(
                    f"{label} strings must be valid UTF-8"
                ) from exc
            if size > MAX_TEXT_UTF8_BYTES:
                raise FunctionalConsciousnessExperimentError(
                    f"{label} text is too large"
                )
            return

        if type(item) not in {dict, list}:
            raise FunctionalConsciousnessExperimentError(
                f"{label} must contain only plain JSON values"
            )

        identity = id(item)
        if identity in active:
            raise FunctionalConsciousnessExperimentError(
                f"{label} must not contain cycles"
            )

        active.add(identity)
        try:
            if type(item) is list:
                for child in item:
                    visit(child, depth + 1)
            else:
                for key, child in item.items():
                    if type(key) is not str:
                        raise FunctionalConsciousnessExperimentError(
                            f"{label} object keys must be text"
                        )
                    visit(key, depth + 1)
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)
    return value


def build_experiment_input_receipt(
    *,
    experiment_id: str,
    condition_id: str,
    world_source_id: str,
    self_source_id: str,
    world_state: Any,
    self_state: Any,
) -> dict[str, Any]:
    """Bind one deterministic world/self observation pair."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")
    world_source = _identifier(world_source_id, "world_source_id")
    self_source = _identifier(self_source_id, "self_source_id")

    if world_source == self_source:
        raise FunctionalConsciousnessExperimentError(
            "world_source_id and self_source_id must differ"
        )

    world = _canonical(world_state, label="world_state")
    self_observation = _canonical(self_state, label="self_state")

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "experiment_id": experiment,
        "condition_id": condition,
        "world_source_id": world_source,
        "self_source_id": self_source,
        "world_state_hash": stable_hash(world),
        "self_state_hash": stable_hash(self_observation),
        "sources_separated": True,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_experiment_input_receipt(receipt: Mapping[str, Any]) -> bool:
    """Verify the closed experiment-input structure and source separation."""

    if type(receipt) is not dict or set(receipt) != _RECEIPT_FIELDS:
        raise FunctionalConsciousnessExperimentError(
            "receipt fields mismatch"
        )

    if (
        receipt["type"] != RECEIPT_TYPE
        or receipt["version"] != RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "receipt schema mismatch"
        )

    supplied_hash = _sha256(receipt["receipt_hash"], "receipt_hash")
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    if stable_hash(body) != supplied_hash:
        raise FunctionalConsciousnessExperimentError(
            "receipt hash mismatch"
        )

    _identifier(receipt["experiment_id"], "experiment_id")
    _identifier(receipt["condition_id"], "condition_id")
    world_source = _identifier(
        receipt["world_source_id"], "world_source_id"
    )
    self_source = _identifier(
        receipt["self_source_id"], "self_source_id"
    )

    if world_source == self_source:
        raise FunctionalConsciousnessExperimentError(
            "world and self sources are not separated"
        )

    _sha256(receipt["world_state_hash"], "world_state_hash")
    _sha256(receipt["self_state_hash"], "self_state_hash")

    if receipt["sources_separated"] is not True:
        raise FunctionalConsciousnessExperimentError(
            "sources_separated must be true"
        )
    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )
    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "receipt must not accept the experiment"
        )
    if receipt["write_authority"] != "NONE":
        raise FunctionalConsciousnessExperimentError(
            "write authority must be NONE"
        )
    if receipt["execution_authority"] != "NONE":
        raise FunctionalConsciousnessExperimentError(
            "execution authority must be NONE"
        )

    return True
MONITOR_RECEIPT_TYPE = "functional_consciousness_internal_monitor_receipt"
MONITOR_RECEIPT_VERSION = 1

_MONITOR_RECEIPT_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "self_source_id",
    "expected_self_state_hash",
    "observed_self_state_hash",
    "mismatch_paths",
    "perturbation_detected",
    "observation_stage",
    "reporter_executed",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}


def _mismatch_paths(expected: Any, observed: Any, path: str = "") -> list[str]:
    """Return deterministic paths where two canonical states differ."""

    if type(expected) is not type(observed):
        return [path or "$root"]

    if type(expected) is dict:
        paths: list[str] = []
        for key in sorted(set(expected) | set(observed)):
            child = f"{path}.{key}" if path else key
            if key not in expected or key not in observed:
                paths.append(child)
            else:
                paths.extend(
                    _mismatch_paths(expected[key], observed[key], child)
                )
        return paths

    if type(expected) is list:
        paths = []
        length = max(len(expected), len(observed))
        for index in range(length):
            child = f"{path}[{index}]" if path else f"[{index}]"
            if index >= len(expected) or index >= len(observed):
                paths.append(child)
            else:
                paths.extend(
                    _mismatch_paths(expected[index], observed[index], child)
                )
        return paths

    return [] if expected == observed else [path or "$root"]


def build_internal_monitor_receipt(
    *,
    experiment_id: str,
    condition_id: str,
    self_source_id: str,
    expected_self_state: Any,
    observed_self_state: Any,
) -> dict[str, Any]:
    """Observe the self channel and detect mismatch before reporter execution."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")
    self_source = _identifier(self_source_id, "self_source_id")
    expected = _canonical(
        expected_self_state,
        label="expected_self_state",
    )
    observed = _canonical(
        observed_self_state,
        label="observed_self_state",
    )
    mismatch_paths = _mismatch_paths(expected, observed)

    body = {
        "type": MONITOR_RECEIPT_TYPE,
        "version": MONITOR_RECEIPT_VERSION,
        "experiment_id": experiment,
        "condition_id": condition,
        "self_source_id": self_source,
        "expected_self_state_hash": stable_hash(expected),
        "observed_self_state_hash": stable_hash(observed),
        "mismatch_paths": mismatch_paths,
        "perturbation_detected": bool(mismatch_paths),
        "observation_stage": "PRE_REPORT",
        "reporter_executed": False,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_internal_monitor_receipt(
    receipt: Mapping[str, Any],
) -> bool:
    """Verify the closed pre-report internal-monitor receipt."""

    if type(receipt) is not dict or set(receipt) != _MONITOR_RECEIPT_FIELDS:
        raise FunctionalConsciousnessExperimentError(
            "monitor receipt fields mismatch"
        )

    if (
        receipt["type"] != MONITOR_RECEIPT_TYPE
        or receipt["version"] != MONITOR_RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "monitor receipt schema mismatch"
        )

    supplied_hash = _sha256(
        receipt["receipt_hash"],
        "receipt_hash",
    )
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    if stable_hash(body) != supplied_hash:
        raise FunctionalConsciousnessExperimentError(
            "monitor receipt hash mismatch"
        )

    _identifier(receipt["experiment_id"], "experiment_id")
    _identifier(receipt["condition_id"], "condition_id")
    _identifier(receipt["self_source_id"], "self_source_id")
    expected_hash = _sha256(
        receipt["expected_self_state_hash"],
        "expected_self_state_hash",
    )
    observed_hash = _sha256(
        receipt["observed_self_state_hash"],
        "observed_self_state_hash",
    )

    mismatch_paths = receipt["mismatch_paths"]
    if (
        type(mismatch_paths) is not list
        or any(type(path) is not str or not path for path in mismatch_paths)
        or mismatch_paths != sorted(set(mismatch_paths))
    ):
        raise FunctionalConsciousnessExperimentError(
            "monitor mismatch paths are invalid"
        )

    expected_detection = bool(mismatch_paths)
    if receipt["perturbation_detected"] is not expected_detection:
        raise FunctionalConsciousnessExperimentError(
            "monitor detection is inconsistent"
        )

    if expected_detection != (expected_hash != observed_hash):
        raise FunctionalConsciousnessExperimentError(
            "monitor hashes and mismatch state are inconsistent"
        )

    if receipt["observation_stage"] != "PRE_REPORT":
        raise FunctionalConsciousnessExperimentError(
            "monitor must execute pre-report"
        )
    if receipt["reporter_executed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "reporter must not execute before monitoring"
        )
    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )
    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "monitor receipt must not accept the experiment"
        )
    if receipt["write_authority"] != "NONE":
        raise FunctionalConsciousnessExperimentError(
            "write authority must be NONE"
        )
    if receipt["execution_authority"] != "NONE":
        raise FunctionalConsciousnessExperimentError(
            "execution authority must be NONE"
        )

    return True
def build_monitor_mismatch_candidate(
    *,
    monitor_receipt: Mapping[str, Any],
    priority: int,
) -> dict[str, Any]:
    """Derive one workspace candidate from verified internal-mismatch evidence."""

    if type(monitor_receipt) is not dict:
        raise FunctionalConsciousnessExperimentError(
            "monitor_receipt must be a plain dictionary"
        )
    verify_internal_monitor_receipt(monitor_receipt)

    if monitor_receipt["perturbation_detected"] is not True:
        raise FunctionalConsciousnessExperimentError(
            "monitor receipt does not contain a detected perturbation"
        )
    if not monitor_receipt["mismatch_paths"]:
        raise FunctionalConsciousnessExperimentError(
            "monitor receipt does not contain mismatch evidence"
        )
    if type(priority) is not int:
        raise FunctionalConsciousnessExperimentError(
            "candidate priority must be an integer"
        )

    return {
        "candidate_id": "self-mismatch",
        "priority": priority,
        "payload": {
            "kind": "internal-mismatch",
            "monitor_receipt_hash": monitor_receipt["receipt_hash"],
            "self_source_id": monitor_receipt["self_source_id"],
            "observed_self_state_hash": monitor_receipt[
                "observed_self_state_hash"
            ],
            "mismatch_paths": list(monitor_receipt["mismatch_paths"]),
        },
    }


WORKSPACE_RECEIPT_TYPE = "functional_consciousness_workspace_receipt"
WORKSPACE_RECEIPT_VERSION = 1

_WORKSPACE_RECEIPT_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "capacity",
    "candidates",
    "winner_id",
    "winner_payload_hash",
    "admitted_count",
    "consumers_reached",
    "broadcast_executed",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}

_WORKSPACE_CANDIDATE_FIELDS = {
    "candidate_id",
    "priority",
    "payload_hash",
}


def _normalize_workspace_candidate(
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        type(candidate) is not dict
        or set(candidate) != {"candidate_id", "priority", "payload"}
    ):
        raise FunctionalConsciousnessExperimentError(
            "workspace candidate fields mismatch"
        )

    candidate_id = _identifier(
        candidate["candidate_id"],
        "candidate_id",
    )
    priority = candidate["priority"]
    if type(priority) is not int:
        raise FunctionalConsciousnessExperimentError(
            "candidate priority must be an integer"
        )

    payload = _canonical(
        candidate["payload"],
        label="candidate payload",
    )

    return {
        "candidate_id": candidate_id,
        "priority": priority,
        "payload_hash": stable_hash(payload),
    }


def _validate_workspace_candidates(
    candidates: Any,
) -> list[dict[str, Any]]:
    if type(candidates) is not list:
        raise FunctionalConsciousnessExperimentError(
            "workspace candidates must be a list"
        )

    normalized = [
        _normalize_workspace_candidate(candidate)
        for candidate in candidates
    ]

    candidate_ids = [
        candidate["candidate_id"]
        for candidate in normalized
    ]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise FunctionalConsciousnessExperimentError(
            "workspace candidate ids must be unique"
        )

    return sorted(
        normalized,
        key=lambda candidate: (
            -candidate["priority"],
            candidate["candidate_id"],
        ),
    )


def build_workspace_receipt(
    *,
    experiment_id: str,
    condition_id: str,
    capacity: int,
    candidates: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Deterministically admit at most one candidate to the workspace."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")

    if type(capacity) is not int or capacity not in {0, 1}:
        raise FunctionalConsciousnessExperimentError(
            "workspace capacity must be zero or one"
        )

    ranked = _validate_workspace_candidates(candidates)

    winner = ranked[0] if capacity == 1 and ranked else None

    body = {
        "type": WORKSPACE_RECEIPT_TYPE,
        "version": WORKSPACE_RECEIPT_VERSION,
        "experiment_id": experiment,
        "condition_id": condition,
        "capacity": capacity,
        "candidates": ranked,
        "winner_id": (
            None if winner is None else winner["candidate_id"]
        ),
        "winner_payload_hash": (
            None if winner is None else winner["payload_hash"]
        ),
        "admitted_count": 0 if winner is None else 1,
        "consumers_reached": [],
        "broadcast_executed": False,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_workspace_receipt(
    receipt: Mapping[str, Any],
) -> bool:
    """Verify deterministic one-slot admission without broadcast credit."""

    if (
        type(receipt) is not dict
        or set(receipt) != _WORKSPACE_RECEIPT_FIELDS
    ):
        raise FunctionalConsciousnessExperimentError(
            "workspace receipt fields mismatch"
        )

    if (
        receipt["type"] != WORKSPACE_RECEIPT_TYPE
        or receipt["version"] != WORKSPACE_RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "workspace receipt schema mismatch"
        )

    supplied_hash = _sha256(
        receipt["receipt_hash"],
        "receipt_hash",
    )
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    if stable_hash(body) != supplied_hash:
        raise FunctionalConsciousnessExperimentError(
            "workspace receipt hash mismatch"
        )

    _identifier(receipt["experiment_id"], "experiment_id")
    _identifier(receipt["condition_id"], "condition_id")

    capacity = receipt["capacity"]
    if type(capacity) is not int or capacity not in {0, 1}:
        raise FunctionalConsciousnessExperimentError(
            "workspace capacity must be zero or one"
        )

    candidates = receipt["candidates"]
    if type(candidates) is not list:
        raise FunctionalConsciousnessExperimentError(
            "workspace candidates must be a list"
        )

    normalized: list[dict[str, Any]] = []
    for candidate in candidates:
        if (
            type(candidate) is not dict
            or set(candidate) != _WORKSPACE_CANDIDATE_FIELDS
        ):
            raise FunctionalConsciousnessExperimentError(
                "workspace stored candidate fields mismatch"
            )

        candidate_id = _identifier(
            candidate["candidate_id"],
            "candidate_id",
        )
        priority = candidate["priority"]
        if type(priority) is not int:
            raise FunctionalConsciousnessExperimentError(
                "candidate priority must be an integer"
            )
        payload_hash = _sha256(
            candidate["payload_hash"],
            "payload_hash",
        )

        normalized.append(
            {
                "candidate_id": candidate_id,
                "priority": priority,
                "payload_hash": payload_hash,
            }
        )

    candidate_ids = [
        candidate["candidate_id"]
        for candidate in normalized
    ]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise FunctionalConsciousnessExperimentError(
            "workspace candidate ids must be unique"
        )

    expected_ranked = sorted(
        normalized,
        key=lambda candidate: (
            -candidate["priority"],
            candidate["candidate_id"],
        ),
    )
    if candidates != expected_ranked:
        raise FunctionalConsciousnessExperimentError(
            "workspace candidates are not deterministically ranked"
        )

    expected_winner = (
        expected_ranked[0]
        if capacity == 1 and expected_ranked
        else None
    )
    expected_winner_id = (
        None
        if expected_winner is None
        else expected_winner["candidate_id"]
    )
    expected_payload_hash = (
        None
        if expected_winner is None
        else expected_winner["payload_hash"]
    )
    expected_count = 0 if expected_winner is None else 1

    if receipt["winner_id"] != expected_winner_id:
        raise FunctionalConsciousnessExperimentError(
            "workspace winner is inconsistent"
        )
    if receipt["winner_payload_hash"] != expected_payload_hash:
        raise FunctionalConsciousnessExperimentError(
            "workspace winner payload is inconsistent"
        )
    if receipt["admitted_count"] != expected_count:
        raise FunctionalConsciousnessExperimentError(
            "workspace admitted count is inconsistent"
        )

    if receipt["consumers_reached"] != []:
        raise FunctionalConsciousnessExperimentError(
            "workspace admission must not claim consumers"
        )
    if receipt["broadcast_executed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "workspace admission must not claim broadcast"
        )
    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )
    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "workspace receipt must not accept the experiment"
        )
    if receipt["write_authority"] != "NONE":
        raise FunctionalConsciousnessExperimentError(
            "write authority must be NONE"
        )
    if receipt["execution_authority"] != "NONE":
        raise FunctionalConsciousnessExperimentError(
            "execution authority must be NONE"
        )

    return True
BROADCAST_RECEIPT_TYPE = "functional_consciousness_workspace_broadcast_receipt"
BROADCAST_RECEIPT_VERSION = 1
BROADCAST_CONSUMERS = ("attention", "action")

_BROADCAST_RECEIPT_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "workspace_receipt_hash",
    "winner_id",
    "winner_payload_hash",
    "broadcast_connected",
    "consumers_reached",
    "consumer_payload_hashes",
    "broadcast_executed",
    "global_availability",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}


def build_workspace_broadcast_receipt(
    *,
    workspace_receipt: Mapping[str, Any],
    broadcast_connected: bool,
) -> dict[str, Any]:
    """Broadcast one admitted workspace winner to both declared consumers."""

    verify_workspace_receipt(workspace_receipt)

    if type(broadcast_connected) is not bool:
        raise FunctionalConsciousnessExperimentError(
            "broadcast_connected must be boolean"
        )

    winner_id = workspace_receipt["winner_id"]
    winner_payload_hash = workspace_receipt["winner_payload_hash"]

    should_broadcast = (
        broadcast_connected
        and workspace_receipt["admitted_count"] == 1
        and winner_id is not None
        and winner_payload_hash is not None
    )

    consumers_reached = (
        list(BROADCAST_CONSUMERS)
        if should_broadcast
        else []
    )
    consumer_payload_hashes = (
        {
            consumer: winner_payload_hash
            for consumer in BROADCAST_CONSUMERS
        }
        if should_broadcast
        else {}
    )

    body = {
        "type": BROADCAST_RECEIPT_TYPE,
        "version": BROADCAST_RECEIPT_VERSION,
        "experiment_id": workspace_receipt["experiment_id"],
        "condition_id": workspace_receipt["condition_id"],
        "workspace_receipt_hash": workspace_receipt["receipt_hash"],
        "winner_id": winner_id,
        "winner_payload_hash": winner_payload_hash,
        "broadcast_connected": broadcast_connected,
        "consumers_reached": consumers_reached,
        "consumer_payload_hashes": consumer_payload_hashes,
        "broadcast_executed": should_broadcast,
        "global_availability": should_broadcast,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_workspace_broadcast_receipt(
    receipt: Mapping[str, Any],
    *,
    workspace_receipt: Mapping[str, Any],
) -> bool:
    """Verify causal fan-out from one admitted winner to both consumers."""

    verify_workspace_receipt(workspace_receipt)

    if (
        type(receipt) is not dict
        or set(receipt) != _BROADCAST_RECEIPT_FIELDS
    ):
        raise FunctionalConsciousnessExperimentError(
            "broadcast receipt fields mismatch"
        )

    if (
        receipt["type"] != BROADCAST_RECEIPT_TYPE
        or receipt["version"] != BROADCAST_RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "broadcast receipt schema mismatch"
        )

    supplied_hash = _sha256(
        receipt["receipt_hash"],
        "receipt_hash",
    )
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    if stable_hash(body) != supplied_hash:
        raise FunctionalConsciousnessExperimentError(
            "broadcast receipt hash mismatch"
        )

    _identifier(receipt["experiment_id"], "experiment_id")
    _identifier(receipt["condition_id"], "condition_id")
    _sha256(
        receipt["workspace_receipt_hash"],
        "workspace_receipt_hash",
    )

    if (
        receipt["experiment_id"]
        != workspace_receipt["experiment_id"]
        or receipt["condition_id"]
        != workspace_receipt["condition_id"]
        or receipt["workspace_receipt_hash"]
        != workspace_receipt["receipt_hash"]
        or receipt["winner_id"]
        != workspace_receipt["winner_id"]
        or receipt["winner_payload_hash"]
        != workspace_receipt["winner_payload_hash"]
    ):
        raise FunctionalConsciousnessExperimentError(
            "broadcast is not bound to workspace admission"
        )

    connected = receipt["broadcast_connected"]
    if type(connected) is not bool:
        raise FunctionalConsciousnessExperimentError(
            "broadcast_connected must be boolean"
        )

    winner_exists = (
        workspace_receipt["admitted_count"] == 1
        and workspace_receipt["winner_id"] is not None
        and workspace_receipt["winner_payload_hash"] is not None
    )
    expected_broadcast = connected and winner_exists
    expected_consumers = (
        list(BROADCAST_CONSUMERS)
        if expected_broadcast
        else []
    )
    expected_payloads = (
        {
            consumer: workspace_receipt["winner_payload_hash"]
            for consumer in BROADCAST_CONSUMERS
        }
        if expected_broadcast
        else {}
    )

    if receipt["consumers_reached"] != expected_consumers:
        raise FunctionalConsciousnessExperimentError(
            "broadcast consumers are inconsistent"
        )
    if receipt["consumer_payload_hashes"] != expected_payloads:
        raise FunctionalConsciousnessExperimentError(
            "broadcast consumer payloads are inconsistent"
        )
    if receipt["broadcast_executed"] is not expected_broadcast:
        raise FunctionalConsciousnessExperimentError(
            "broadcast execution state is inconsistent"
        )
    if receipt["global_availability"] is not expected_broadcast:
        raise FunctionalConsciousnessExperimentError(
            "global availability is inconsistent"
        )

    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )
    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "broadcast receipt must not accept the experiment"
        )
    if receipt["write_authority"] != "NONE":
        raise FunctionalConsciousnessExperimentError(
            "write authority must be NONE"
        )
    if receipt["execution_authority"] != "NONE":
        raise FunctionalConsciousnessExperimentError(
            "execution authority must be NONE"
        )

    return True


CONTINUITY_RECEIPT_TYPE = "functional_consciousness_continuity_receipt"
CONTINUITY_RECEIPT_VERSION = 1

_CONTINUITY_RECEIPT_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "reentry_packet_hash",
    "reconstructed_state_hash",
    "head_status",
    "reentry_status",
    "continuity_bound",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}


def build_experiment_continuity_receipt(
    *,
    experiment_id: str,
    condition_id: str,
    reentry_packet: Mapping[str, Any],
    source_items: Any,
) -> dict[str, Any]:
    """Bind verified post-gap continuity evidence into the experiment."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")

    try:
        validate_verified_cold_start_reentry_packet(
            reentry_packet,
            source_items=source_items,
        )
    except VerifiedColdStartReentryError as exc:
        raise FunctionalConsciousnessExperimentError(
            f"reentry packet is invalid: {exc}"
        ) from exc

    continuity_bound = (
        reentry_packet["status"] == "READY_FOR_REENTRY"
        and reentry_packet["gate_decision"] == "ALLOW"
        and reentry_packet["head_status"] == "CURRENT"
    )

    body = {
        "type": CONTINUITY_RECEIPT_TYPE,
        "version": CONTINUITY_RECEIPT_VERSION,
        "experiment_id": experiment,
        "condition_id": condition,
        "reentry_packet_hash": reentry_packet["packet_hash"],
        "reconstructed_state_hash": reentry_packet[
            "reconstructed_state_hash"
        ],
        "head_status": reentry_packet["head_status"],
        "reentry_status": reentry_packet["status"],
        "continuity_bound": continuity_bound,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_experiment_continuity_receipt(
    receipt: Mapping[str, Any],
    *,
    reentry_packet: Mapping[str, Any],
    source_items: Any,
) -> bool:
    """Verify exact experiment binding to validated continuity evidence."""

    try:
        validate_verified_cold_start_reentry_packet(
            reentry_packet,
            source_items=source_items,
        )
    except VerifiedColdStartReentryError as exc:
        raise FunctionalConsciousnessExperimentError(
            f"reentry packet is invalid: {exc}"
        ) from exc

    if type(receipt) is not dict or set(receipt) != _CONTINUITY_RECEIPT_FIELDS:
        raise FunctionalConsciousnessExperimentError(
            "continuity receipt fields mismatch"
        )
    if (
        receipt["type"] != CONTINUITY_RECEIPT_TYPE
        or receipt["version"] != CONTINUITY_RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "continuity receipt schema mismatch"
        )

    supplied_hash = _sha256(receipt["receipt_hash"], "receipt_hash")
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    if stable_hash(body) != supplied_hash:
        raise FunctionalConsciousnessExperimentError(
            "continuity receipt hash mismatch"
        )

    expected_bound = (
        reentry_packet["status"] == "READY_FOR_REENTRY"
        and reentry_packet["gate_decision"] == "ALLOW"
        and reentry_packet["head_status"] == "CURRENT"
    )
    if (
        receipt["reentry_packet_hash"] != reentry_packet["packet_hash"]
        or receipt["reconstructed_state_hash"]
        != reentry_packet["reconstructed_state_hash"]
        or receipt["head_status"] != reentry_packet["head_status"]
        or receipt["reentry_status"] != reentry_packet["status"]
        or receipt["continuity_bound"] is not expected_bound
    ):
        raise FunctionalConsciousnessExperimentError(
            "continuity receipt is not bound to reentry evidence"
        )

    _identifier(receipt["experiment_id"], "experiment_id")
    _identifier(receipt["condition_id"], "condition_id")
    _sha256(receipt["reentry_packet_hash"], "reentry_packet_hash")
    _sha256(
        receipt["reconstructed_state_hash"],
        "reconstructed_state_hash",
    )

    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )
    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "continuity receipt must not accept the experiment"
        )
    if receipt["write_authority"] != "NONE":
        raise FunctionalConsciousnessExperimentError(
            "write authority must be NONE"
        )
    if receipt["execution_authority"] != "NONE":
        raise FunctionalConsciousnessExperimentError(
            "execution authority must be NONE"
        )

    return True
