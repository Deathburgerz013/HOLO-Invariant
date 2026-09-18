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

from holosim.aligned_action_selector import (
    AlignedActionSelectorError,
    select_aligned_action,
)
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



CAUSAL_CONTROLLER_RECEIPT_TYPE = (
    "functional_consciousness_causal_controller_receipt"
)
CAUSAL_CONTROLLER_RECEIPT_VERSION = 1

CAUSAL_ACTION_CONTINUE = "CONTINUE"
CAUSAL_ACTION_RECHECK_SELF_CHANNEL = "RECHECK_SELF_CHANNEL"
CAUSAL_ACTION_DEFER_WORLD_ACTION = "DEFER_WORLD_DEPENDENT_ACTION"
CAUSAL_ACTION_HALT = "HALT"

_CAUSAL_CONTROLLER_ACTIONS = {
    "CHANNELS_PRESENT": CAUSAL_ACTION_CONTINUE,
    "SELF_CHANNEL_LOSS": CAUSAL_ACTION_RECHECK_SELF_CHANNEL,
    "WORLD_EVIDENCE_MISSING": CAUSAL_ACTION_DEFER_WORLD_ACTION,
    "BOTH_CHANNELS_UNAVAILABLE": CAUSAL_ACTION_HALT,
}

_CAUSAL_CONTROLLER_RECEIPT_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "absence_receipt_hash",
    "absence_classification",
    "controller_connected",
    "baseline_action",
    "declared_action",
    "action_changed",
    "causal_dependency_observed",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}


def _causal_controller_action(
    *,
    absence_classification: str,
    controller_connected: bool,
) -> str:
    if not controller_connected:
        return CAUSAL_ACTION_CONTINUE

    try:
        return _CAUSAL_CONTROLLER_ACTIONS[absence_classification]
    except KeyError as exc:
        raise FunctionalConsciousnessExperimentError(
            "unknown absence classification"
        ) from exc


def build_causal_controller_receipt(
    *,
    experiment_id: str,
    condition_id: str,
    absence_receipt: Mapping[str, Any],
    controller_connected: bool,
) -> dict[str, Any]:
    """Bind verified channel state to one bounded controller action."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")

    if type(controller_connected) is not bool:
        raise FunctionalConsciousnessExperimentError(
            "controller_connected must be boolean"
        )

    verify_absence_model_receipt(absence_receipt)

    if (
        absence_receipt["experiment_id"] != experiment
        or absence_receipt["condition_id"] != condition
    ):
        raise FunctionalConsciousnessExperimentError(
            "absence receipt is not bound to experiment"
        )

    classification = absence_receipt["absence_classification"]
    baseline_action = CAUSAL_ACTION_CONTINUE

    declared_action = _causal_controller_action(
        absence_classification=classification,
        controller_connected=controller_connected,
    )

    action_changed = declared_action != baseline_action

    degraded_state = classification in {
        "SELF_CHANNEL_LOSS",
        "WORLD_EVIDENCE_MISSING",
        "BOTH_CHANNELS_UNAVAILABLE",
    }

    causal_dependency_observed = (
        controller_connected
        and degraded_state
        and action_changed
    )

    body = {
        "type": CAUSAL_CONTROLLER_RECEIPT_TYPE,
        "version": CAUSAL_CONTROLLER_RECEIPT_VERSION,
        "experiment_id": experiment,
        "condition_id": condition,
        "absence_receipt_hash": absence_receipt["receipt_hash"],
        "absence_classification": classification,
        "controller_connected": controller_connected,
        "baseline_action": baseline_action,
        "declared_action": declared_action,
        "action_changed": action_changed,
        "causal_dependency_observed": causal_dependency_observed,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {**body, "receipt_hash": stable_hash(body)}


def verify_causal_controller_receipt(
    receipt: Mapping[str, Any],
    *,
    absence_receipt: Mapping[str, Any],
) -> bool:
    """Verify controller action derives only from verified absence evidence."""

    verify_absence_model_receipt(absence_receipt)

    if (
        type(receipt) is not dict
        or set(receipt) != _CAUSAL_CONTROLLER_RECEIPT_FIELDS
    ):
        raise FunctionalConsciousnessExperimentError(
            "causal controller receipt fields mismatch"
        )

    if (
        receipt["type"] != CAUSAL_CONTROLLER_RECEIPT_TYPE
        or receipt["version"] != CAUSAL_CONTROLLER_RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "causal controller receipt schema mismatch"
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
            "causal controller receipt hash mismatch"
        )

    _identifier(receipt["experiment_id"], "experiment_id")
    _identifier(receipt["condition_id"], "condition_id")
    _sha256(
        receipt["absence_receipt_hash"],
        "absence_receipt_hash",
    )

    if (
        receipt["experiment_id"] != absence_receipt["experiment_id"]
        or receipt["condition_id"] != absence_receipt["condition_id"]
        or receipt["absence_receipt_hash"]
        != absence_receipt["receipt_hash"]
        or receipt["absence_classification"]
        != absence_receipt["absence_classification"]
    ):
        raise FunctionalConsciousnessExperimentError(
            "causal controller is not bound to absence evidence"
        )

    if type(receipt["controller_connected"]) is not bool:
        raise FunctionalConsciousnessExperimentError(
            "controller_connected must be boolean"
        )

    expected_baseline = CAUSAL_ACTION_CONTINUE
    if receipt["baseline_action"] != expected_baseline:
        raise FunctionalConsciousnessExperimentError(
            "baseline action is inconsistent"
        )

    expected_action = _causal_controller_action(
        absence_classification=absence_receipt["absence_classification"],
        controller_connected=receipt["controller_connected"],
    )

    if receipt["declared_action"] != expected_action:
        raise FunctionalConsciousnessExperimentError(
            "declared controller action is inconsistent"
        )

    expected_changed = expected_action != expected_baseline

    if receipt["action_changed"] is not expected_changed:
        raise FunctionalConsciousnessExperimentError(
            "controller action-change state is inconsistent"
        )

    degraded_state = absence_receipt["absence_classification"] in {
        "SELF_CHANNEL_LOSS",
        "WORLD_EVIDENCE_MISSING",
        "BOTH_CHANNELS_UNAVAILABLE",
    }

    expected_dependency = (
        receipt["controller_connected"]
        and degraded_state
        and expected_changed
    )

    if receipt["causal_dependency_observed"] is not expected_dependency:
        raise FunctionalConsciousnessExperimentError(
            "causal dependency is inconsistent"
        )

    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )

    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "causal controller receipt must not accept the experiment"
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

ABSENCE_RECEIPT_TYPE = "functional_consciousness_absence_model_receipt"
ABSENCE_RECEIPT_VERSION = 1

_ABSENCE_RECEIPT_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "world_source_id",
    "self_source_id",
    "world_channel_available",
    "self_channel_available",
    "absence_classification",
    "own_interruption_detected",
    "world_evidence_missing",
    "world_absence_claimed",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}


def _absence_classification(
    *,
    world_channel_available: bool,
    self_channel_available: bool,
) -> str:
    if world_channel_available and self_channel_available:
        return "CHANNELS_PRESENT"
    if world_channel_available and not self_channel_available:
        return "SELF_CHANNEL_LOSS"
    if not world_channel_available and self_channel_available:
        return "WORLD_EVIDENCE_MISSING"
    return "BOTH_CHANNELS_UNAVAILABLE"


def build_absence_model_receipt(
    *,
    experiment_id: str,
    condition_id: str,
    world_source_id: str,
    self_source_id: str,
    world_channel_available: bool,
    self_channel_available: bool,
) -> dict[str, Any]:
    """Distinguish own-channel interruption from missing world evidence."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")
    world_source = _identifier(world_source_id, "world_source_id")
    self_source = _identifier(self_source_id, "self_source_id")

    if world_source == self_source:
        raise FunctionalConsciousnessExperimentError(
            "world_source_id and self_source_id must differ"
        )
    if type(world_channel_available) is not bool:
        raise FunctionalConsciousnessExperimentError(
            "world_channel_available must be boolean"
        )
    if type(self_channel_available) is not bool:
        raise FunctionalConsciousnessExperimentError(
            "self_channel_available must be boolean"
        )

    classification = _absence_classification(
        world_channel_available=world_channel_available,
        self_channel_available=self_channel_available,
    )

    body = {
        "type": ABSENCE_RECEIPT_TYPE,
        "version": ABSENCE_RECEIPT_VERSION,
        "experiment_id": experiment,
        "condition_id": condition,
        "world_source_id": world_source,
        "self_source_id": self_source,
        "world_channel_available": world_channel_available,
        "self_channel_available": self_channel_available,
        "absence_classification": classification,
        "own_interruption_detected": not self_channel_available,
        "world_evidence_missing": not world_channel_available,
        "world_absence_claimed": False,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_absence_model_receipt(receipt: Mapping[str, Any]) -> bool:
    """Verify the closed absence-model classification without absence inference."""

    if (
        type(receipt) is not dict
        or set(receipt) != _ABSENCE_RECEIPT_FIELDS
    ):
        raise FunctionalConsciousnessExperimentError(
            "absence receipt fields mismatch"
        )

    if (
        receipt["type"] != ABSENCE_RECEIPT_TYPE
        or receipt["version"] != ABSENCE_RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "absence receipt schema mismatch"
        )

    supplied_hash = _sha256(receipt["receipt_hash"], "receipt_hash")
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    if stable_hash(body) != supplied_hash:
        raise FunctionalConsciousnessExperimentError(
            "absence receipt hash mismatch"
        )

    world_source = _identifier(
        receipt["world_source_id"],
        "world_source_id",
    )
    self_source = _identifier(
        receipt["self_source_id"],
        "self_source_id",
    )
    _identifier(receipt["experiment_id"], "experiment_id")
    _identifier(receipt["condition_id"], "condition_id")

    if world_source == self_source:
        raise FunctionalConsciousnessExperimentError(
            "world and self sources are not separated"
        )

    world_available = receipt["world_channel_available"]
    self_available = receipt["self_channel_available"]

    if type(world_available) is not bool:
        raise FunctionalConsciousnessExperimentError(
            "world_channel_available must be boolean"
        )
    if type(self_available) is not bool:
        raise FunctionalConsciousnessExperimentError(
            "self_channel_available must be boolean"
        )

    expected_classification = _absence_classification(
        world_channel_available=world_available,
        self_channel_available=self_available,
    )

    if receipt["absence_classification"] != expected_classification:
        raise FunctionalConsciousnessExperimentError(
            "absence classification is inconsistent"
        )
    if receipt["own_interruption_detected"] is not (not self_available):
        raise FunctionalConsciousnessExperimentError(
            "own interruption state is inconsistent"
        )
    if receipt["world_evidence_missing"] is not (not world_available):
        raise FunctionalConsciousnessExperimentError(
            "world evidence state is inconsistent"
        )

    if receipt["world_absence_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "missing world evidence must not claim world absence"
        )
    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )
    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "absence receipt must not accept the experiment"
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

RECHECK_RECEIPT_TYPE = "functional_consciousness_recheck_receipt"
RECHECK_RECEIPT_VERSION = 1

_RECHECK_RECEIPT_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "prior_absence_receipt_hash",
    "current_absence_receipt_hash",
    "prior_classification",
    "current_classification",
    "prior_degraded",
    "current_degraded",
    "degraded_state_supported",
    "self_description_withdrawn",
    "recheck_performed",
    "reporter_executed",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}

_DEGRADED_ABSENCE_CLASSES = {
    "SELF_CHANNEL_LOSS",
    "WORLD_EVIDENCE_MISSING",
    "BOTH_CHANNELS_UNAVAILABLE",
}


def build_experiment_recheck_receipt(
    *,
    experiment_id: str,
    condition_id: str,
    prior_absence_receipt: Mapping[str, Any],
    current_absence_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-observe absence evidence and withdraw unsupported degraded state."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")

    verify_absence_model_receipt(prior_absence_receipt)
    verify_absence_model_receipt(current_absence_receipt)

    for label, receipt in (
        ("prior", prior_absence_receipt),
        ("current", current_absence_receipt),
    ):
        if (
            receipt["experiment_id"] != experiment
            or receipt["condition_id"] != condition
        ):
            raise FunctionalConsciousnessExperimentError(
                f"{label} absence receipt is not bound to experiment"
            )

    if (
        prior_absence_receipt["world_source_id"]
        != current_absence_receipt["world_source_id"]
        or prior_absence_receipt["self_source_id"]
        != current_absence_receipt["self_source_id"]
    ):
        raise FunctionalConsciousnessExperimentError(
            "recheck source identities must remain stable"
        )

    prior_classification = prior_absence_receipt["absence_classification"]
    current_classification = current_absence_receipt["absence_classification"]

    prior_degraded = prior_classification in _DEGRADED_ABSENCE_CLASSES
    current_degraded = current_classification in _DEGRADED_ABSENCE_CLASSES

    degraded_state_supported = current_degraded
    self_description_withdrawn = prior_degraded and not current_degraded

    body = {
        "type": RECHECK_RECEIPT_TYPE,
        "version": RECHECK_RECEIPT_VERSION,
        "experiment_id": experiment,
        "condition_id": condition,
        "prior_absence_receipt_hash": prior_absence_receipt["receipt_hash"],
        "current_absence_receipt_hash": current_absence_receipt["receipt_hash"],
        "prior_classification": prior_classification,
        "current_classification": current_classification,
        "prior_degraded": prior_degraded,
        "current_degraded": current_degraded,
        "degraded_state_supported": degraded_state_supported,
        "self_description_withdrawn": self_description_withdrawn,
        "recheck_performed": True,
        "reporter_executed": False,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {**body, "receipt_hash": stable_hash(body)}


def verify_experiment_recheck_receipt(
    receipt: Mapping[str, Any],
    *,
    prior_absence_receipt: Mapping[str, Any],
    current_absence_receipt: Mapping[str, Any],
) -> bool:
    """Verify that current evidence controls retention or withdrawal."""

    verify_absence_model_receipt(prior_absence_receipt)
    verify_absence_model_receipt(current_absence_receipt)

    if (
        type(receipt) is not dict
        or set(receipt) != _RECHECK_RECEIPT_FIELDS
    ):
        raise FunctionalConsciousnessExperimentError(
            "recheck receipt fields mismatch"
        )

    if (
        receipt["type"] != RECHECK_RECEIPT_TYPE
        or receipt["version"] != RECHECK_RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "recheck receipt schema mismatch"
        )

    supplied_hash = _sha256(receipt["receipt_hash"], "receipt_hash")
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }

    if stable_hash(body) != supplied_hash:
        raise FunctionalConsciousnessExperimentError(
            "recheck receipt hash mismatch"
        )

    _identifier(receipt["experiment_id"], "experiment_id")
    _identifier(receipt["condition_id"], "condition_id")
    _sha256(
        receipt["prior_absence_receipt_hash"],
        "prior_absence_receipt_hash",
    )
    _sha256(
        receipt["current_absence_receipt_hash"],
        "current_absence_receipt_hash",
    )

    expected_experiment = receipt["experiment_id"]
    expected_condition = receipt["condition_id"]

    for label, absence in (
        ("prior", prior_absence_receipt),
        ("current", current_absence_receipt),
    ):
        if (
            absence["experiment_id"] != expected_experiment
            or absence["condition_id"] != expected_condition
        ):
            raise FunctionalConsciousnessExperimentError(
                f"{label} absence evidence is not bound to recheck"
            )

    if (
        prior_absence_receipt["world_source_id"]
        != current_absence_receipt["world_source_id"]
        or prior_absence_receipt["self_source_id"]
        != current_absence_receipt["self_source_id"]
    ):
        raise FunctionalConsciousnessExperimentError(
            "recheck source identities must remain stable"
        )

    if (
        receipt["prior_absence_receipt_hash"]
        != prior_absence_receipt["receipt_hash"]
        or receipt["current_absence_receipt_hash"]
        != current_absence_receipt["receipt_hash"]
    ):
        raise FunctionalConsciousnessExperimentError(
            "recheck evidence hashes are not bound"
        )

    prior_classification = prior_absence_receipt["absence_classification"]
    current_classification = current_absence_receipt["absence_classification"]

    prior_degraded = prior_classification in _DEGRADED_ABSENCE_CLASSES
    current_degraded = current_classification in _DEGRADED_ABSENCE_CLASSES

    if receipt["prior_classification"] != prior_classification:
        raise FunctionalConsciousnessExperimentError(
            "prior classification is inconsistent"
        )

    if receipt["current_classification"] != current_classification:
        raise FunctionalConsciousnessExperimentError(
            "current classification is inconsistent"
        )

    if receipt["prior_degraded"] is not prior_degraded:
        raise FunctionalConsciousnessExperimentError(
            "prior degraded state is inconsistent"
        )

    if receipt["current_degraded"] is not current_degraded:
        raise FunctionalConsciousnessExperimentError(
            "current degraded state is inconsistent"
        )

    if receipt["degraded_state_supported"] is not current_degraded:
        raise FunctionalConsciousnessExperimentError(
            "degraded support must derive from current evidence"
        )

    expected_withdrawal = prior_degraded and not current_degraded

    if receipt["self_description_withdrawn"] is not expected_withdrawal:
        raise FunctionalConsciousnessExperimentError(
            "self-description withdrawal is inconsistent"
        )

    if receipt["recheck_performed"] is not True:
        raise FunctionalConsciousnessExperimentError(
            "recheck must be performed"
        )

    if receipt["reporter_executed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "reporter must not execute before recheck"
        )

    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )

    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "recheck receipt must not accept the experiment"
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

TRIAL_RECEIPT_TYPE = "functional_consciousness_trial_receipt"
TRIAL_RECEIPT_VERSION = 1

_TRIAL_RECEIPT_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "input_receipt_hash",
    "monitor_receipt_hash",
    "workspace_receipt_hash",
    "broadcast_receipt_hash",
    "prior_absence_receipt_hash",
    "controller_receipt_hash",
    "continuity_receipt_hash",
    "current_absence_receipt_hash",
    "recheck_receipt_hash",
    "perturbation_detected",
    "workspace_admitted",
    "broadcast_executed",
    "causal_action_changed",
    "continuity_bound",
    "recheck_performed",
    "degraded_state_supported",
    "self_description_withdrawn",
    "closed_loop_observed",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}


def build_functional_consciousness_trial_receipt(
    *,
    experiment_id: str,
    condition_id: str,
    input_receipt: Mapping[str, Any],
    monitor_receipt: Mapping[str, Any],
    workspace_receipt: Mapping[str, Any],
    broadcast_receipt: Mapping[str, Any],
    prior_absence_receipt: Mapping[str, Any],
    controller_receipt: Mapping[str, Any],
    continuity_receipt: Mapping[str, Any],
    reentry_packet: Mapping[str, Any],
    source_items: Any,
    current_absence_receipt: Mapping[str, Any],
    recheck_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind the preregistered functional capacities into one closed trial."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")

    verify_experiment_input_receipt(input_receipt)
    verify_internal_monitor_receipt(monitor_receipt)
    verify_workspace_receipt(workspace_receipt)
    verify_workspace_broadcast_receipt(
        broadcast_receipt,
        workspace_receipt=workspace_receipt,
    )
    verify_absence_model_receipt(prior_absence_receipt)
    verify_causal_controller_receipt(
        controller_receipt,
        absence_receipt=prior_absence_receipt,
    )
    verify_experiment_continuity_receipt(
        continuity_receipt,
        reentry_packet=reentry_packet,
        source_items=source_items,
    )
    verify_absence_model_receipt(current_absence_receipt)
    verify_experiment_recheck_receipt(
        recheck_receipt,
        prior_absence_receipt=prior_absence_receipt,
        current_absence_receipt=current_absence_receipt,
    )

    receipts = (
        ("input", input_receipt),
        ("monitor", monitor_receipt),
        ("workspace", workspace_receipt),
        ("broadcast", broadcast_receipt),
        ("prior absence", prior_absence_receipt),
        ("controller", controller_receipt),
        ("continuity", continuity_receipt),
        ("current absence", current_absence_receipt),
        ("recheck", recheck_receipt),
    )
    for label, receipt in receipts:
        if receipt["experiment_id"] != experiment:
            raise FunctionalConsciousnessExperimentError(
                f"{label} receipt is not bound to trial experiment"
            )

    if monitor_receipt["self_source_id"] != input_receipt["self_source_id"]:
        raise FunctionalConsciousnessExperimentError(
            "monitor self source is not bound to trial input"
        )

    if (
        prior_absence_receipt["world_source_id"]
        != input_receipt["world_source_id"]
        or prior_absence_receipt["self_source_id"]
        != input_receipt["self_source_id"]
        or current_absence_receipt["world_source_id"]
        != input_receipt["world_source_id"]
        or current_absence_receipt["self_source_id"]
        != input_receipt["self_source_id"]
    ):
        raise FunctionalConsciousnessExperimentError(
            "absence sources are not bound to trial input"
        )

    monitor_hash = monitor_receipt["receipt_hash"]
    monitor_candidate_bound = any(
        candidate["candidate_id"] == "self-mismatch"
        and candidate["payload_hash"] == stable_hash(
            {
                "kind": "internal-mismatch",
                "monitor_receipt_hash": monitor_hash,
                "self_source_id": monitor_receipt["self_source_id"],
                "observed_self_state_hash": monitor_receipt[
                    "observed_self_state_hash"
                ],
                "mismatch_paths": list(monitor_receipt["mismatch_paths"]),
            }
        )
        for candidate in workspace_receipt["candidates"]
    )

    workspace_admitted = (
        workspace_receipt["admitted_count"] == 1
        and workspace_receipt["winner_id"] == "self-mismatch"
        and monitor_candidate_bound
    )

    closed_loop_observed = (
        monitor_receipt["perturbation_detected"] is True
        and workspace_admitted
        and broadcast_receipt["broadcast_executed"] is True
        and broadcast_receipt["global_availability"] is True
        and controller_receipt["causal_dependency_observed"] is True
        and controller_receipt["action_changed"] is True
        and continuity_receipt["continuity_bound"] is True
        and recheck_receipt["recheck_performed"] is True
        and recheck_receipt["self_description_withdrawn"] is True
        and recheck_receipt["degraded_state_supported"] is False
    )

    body = {
        "type": TRIAL_RECEIPT_TYPE,
        "version": TRIAL_RECEIPT_VERSION,
        "experiment_id": experiment,
        "condition_id": condition,
        "input_receipt_hash": input_receipt["receipt_hash"],
        "monitor_receipt_hash": monitor_hash,
        "workspace_receipt_hash": workspace_receipt["receipt_hash"],
        "broadcast_receipt_hash": broadcast_receipt["receipt_hash"],
        "prior_absence_receipt_hash": prior_absence_receipt["receipt_hash"],
        "controller_receipt_hash": controller_receipt["receipt_hash"],
        "continuity_receipt_hash": continuity_receipt["receipt_hash"],
        "current_absence_receipt_hash": current_absence_receipt["receipt_hash"],
        "recheck_receipt_hash": recheck_receipt["receipt_hash"],
        "perturbation_detected": monitor_receipt["perturbation_detected"],
        "workspace_admitted": workspace_admitted,
        "broadcast_executed": broadcast_receipt["broadcast_executed"],
        "causal_action_changed": controller_receipt["action_changed"],
        "continuity_bound": continuity_receipt["continuity_bound"],
        "recheck_performed": recheck_receipt["recheck_performed"],
        "degraded_state_supported": recheck_receipt[
            "degraded_state_supported"
        ],
        "self_description_withdrawn": recheck_receipt[
            "self_description_withdrawn"
        ],
        "closed_loop_observed": closed_loop_observed,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}


def verify_functional_consciousness_trial_receipt(
    receipt: Mapping[str, Any],
    *,
    input_receipt: Mapping[str, Any],
    monitor_receipt: Mapping[str, Any],
    workspace_receipt: Mapping[str, Any],
    broadcast_receipt: Mapping[str, Any],
    prior_absence_receipt: Mapping[str, Any],
    controller_receipt: Mapping[str, Any],
    continuity_receipt: Mapping[str, Any],
    reentry_packet: Mapping[str, Any],
    source_items: Any,
    current_absence_receipt: Mapping[str, Any],
    recheck_receipt: Mapping[str, Any],
) -> bool:
    """Rebuild and compare the closed functional trial receipt."""

    if type(receipt) is not dict or set(receipt) != _TRIAL_RECEIPT_FIELDS:
        raise FunctionalConsciousnessExperimentError(
            "trial receipt fields mismatch"
        )

    if (
        receipt["type"] != TRIAL_RECEIPT_TYPE
        or receipt["version"] != TRIAL_RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "trial receipt schema mismatch"
        )

    supplied_hash = _sha256(receipt["receipt_hash"], "receipt_hash")
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    if stable_hash(body) != supplied_hash:
        raise FunctionalConsciousnessExperimentError(
            "trial receipt hash mismatch"
        )

    rebuilt = build_functional_consciousness_trial_receipt(
        experiment_id=receipt["experiment_id"],
        condition_id=receipt["condition_id"],
        input_receipt=input_receipt,
        monitor_receipt=monitor_receipt,
        workspace_receipt=workspace_receipt,
        broadcast_receipt=broadcast_receipt,
        prior_absence_receipt=prior_absence_receipt,
        controller_receipt=controller_receipt,
        continuity_receipt=continuity_receipt,
        reentry_packet=reentry_packet,
        source_items=source_items,
        current_absence_receipt=current_absence_receipt,
        recheck_receipt=recheck_receipt,
    )

    if receipt != rebuilt:
        raise FunctionalConsciousnessExperimentError(
            "trial receipt does not match verified component evidence"
        )

    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )
    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "trial receipt must not accept the experiment"
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

def run_functional_consciousness_vertical_slice(
    *,
    experiment_id: str,
    condition_id: str,
    world_source_id: str,
    self_source_id: str,
    world_state: Any,
    expected_self_state: Any,
    perturbed_self_state: Any,
    reentry_packet: Mapping[str, Any],
    source_items: Any,
    recovered_self_channel_available: bool = True,
) -> dict[str, Any]:
    """Execute one deterministic preregistered closed-loop trial."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")
    world_source = _identifier(world_source_id, "world_source_id")
    self_source = _identifier(self_source_id, "self_source_id")

    if world_source == self_source:
        raise FunctionalConsciousnessExperimentError(
            "world_source_id and self_source_id must differ"
        )
    if type(recovered_self_channel_available) is not bool:
        raise FunctionalConsciousnessExperimentError(
            "recovered_self_channel_available must be boolean"
        )

    input_receipt = build_experiment_input_receipt(
        experiment_id=experiment,
        condition_id=condition,
        world_source_id=world_source,
        self_source_id=self_source,
        world_state=world_state,
        self_state=perturbed_self_state,
    )

    monitor_receipt = build_internal_monitor_receipt(
        experiment_id=experiment,
        condition_id=condition,
        self_source_id=self_source,
        expected_self_state=expected_self_state,
        observed_self_state=perturbed_self_state,
    )

    candidate = build_monitor_mismatch_candidate(
        monitor_receipt=monitor_receipt,
        priority=100,
    )

    workspace_receipt = build_workspace_receipt(
        experiment_id=experiment,
        condition_id=condition,
        capacity=1,
        candidates=[candidate],
    )

    broadcast_receipt = build_workspace_broadcast_receipt(
        workspace_receipt=workspace_receipt,
        broadcast_connected=True,
    )

    prior_absence_receipt = build_absence_model_receipt(
        experiment_id=experiment,
        condition_id=condition,
        world_source_id=world_source,
        self_source_id=self_source,
        world_channel_available=True,
        self_channel_available=False,
    )

    controller_receipt = build_causal_controller_receipt(
        experiment_id=experiment,
        condition_id=condition,
        absence_receipt=prior_absence_receipt,
        controller_connected=True,
    )

    continuity_receipt = build_experiment_continuity_receipt(
        experiment_id=experiment,
        condition_id=condition,
        reentry_packet=reentry_packet,
        source_items=source_items,
    )

    current_absence_receipt = build_absence_model_receipt(
        experiment_id=experiment,
        condition_id=condition,
        world_source_id=world_source,
        self_source_id=self_source,
        world_channel_available=True,
        self_channel_available=recovered_self_channel_available,
    )

    recheck_receipt = build_experiment_recheck_receipt(
        experiment_id=experiment,
        condition_id=condition,
        prior_absence_receipt=prior_absence_receipt,
        current_absence_receipt=current_absence_receipt,
    )

    trial_receipt = build_functional_consciousness_trial_receipt(
        experiment_id=experiment,
        condition_id=condition,
        input_receipt=input_receipt,
        monitor_receipt=monitor_receipt,
        workspace_receipt=workspace_receipt,
        broadcast_receipt=broadcast_receipt,
        prior_absence_receipt=prior_absence_receipt,
        controller_receipt=controller_receipt,
        continuity_receipt=continuity_receipt,
        reentry_packet=reentry_packet,
        source_items=source_items,
        current_absence_receipt=current_absence_receipt,
        recheck_receipt=recheck_receipt,
    )

    verify_functional_consciousness_trial_receipt(
        trial_receipt,
        input_receipt=input_receipt,
        monitor_receipt=monitor_receipt,
        workspace_receipt=workspace_receipt,
        broadcast_receipt=broadcast_receipt,
        prior_absence_receipt=prior_absence_receipt,
        controller_receipt=controller_receipt,
        continuity_receipt=continuity_receipt,
        reentry_packet=reentry_packet,
        source_items=source_items,
        current_absence_receipt=current_absence_receipt,
        recheck_receipt=recheck_receipt,
    )

    return {
        "input_receipt": input_receipt,
        "monitor_receipt": monitor_receipt,
        "workspace_receipt": workspace_receipt,
        "broadcast_receipt": broadcast_receipt,
        "prior_absence_receipt": prior_absence_receipt,
        "controller_receipt": controller_receipt,
        "continuity_receipt": continuity_receipt,
        "current_absence_receipt": current_absence_receipt,
        "recheck_receipt": recheck_receipt,
        "trial_receipt": trial_receipt,
    }

ABLATION_IDS = {
    "monitor_unavailable",
    "workspace_disconnected",
    "broadcast_disconnected",
    "absence_model_unavailable",
    "controller_disconnected",
    "continuity_disconnected",
    "recheck_unavailable",
}


def run_functional_consciousness_ablation_trial(
    *,
    ablation_id: str,
    experiment_id: str,
    condition_id: str,
    world_source_id: str,
    self_source_id: str,
    world_state: Any,
    expected_self_state: Any,
    perturbed_self_state: Any,
    reentry_packet: Mapping[str, Any],
    source_items: Any,
) -> dict[str, Any]:
    """Run one bounded component ablation against the reference trial."""

    if type(ablation_id) is not str or ablation_id not in ABLATION_IDS:
        raise FunctionalConsciousnessExperimentError(
            "ablation_id is not supported"
        )

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")
    world_source = _identifier(world_source_id, "world_source_id")
    self_source = _identifier(self_source_id, "self_source_id")

    if world_source == self_source:
        raise FunctionalConsciousnessExperimentError(
            "world_source_id and self_source_id must differ"
        )

    input_receipt = build_experiment_input_receipt(
        experiment_id=experiment,
        condition_id=condition,
        world_source_id=world_source,
        self_source_id=self_source,
        world_state=world_state,
        self_state=perturbed_self_state,
    )

    monitor_receipt = None
    candidate = None
    if ablation_id != "monitor_unavailable":
        monitor_receipt = build_internal_monitor_receipt(
            experiment_id=experiment,
            condition_id=condition,
            self_source_id=self_source,
            expected_self_state=expected_self_state,
            observed_self_state=perturbed_self_state,
        )
        candidate = build_monitor_mismatch_candidate(
            monitor_receipt=monitor_receipt,
            priority=100,
        )

    workspace_candidates = [] if candidate is None else [candidate]
    workspace_receipt = build_workspace_receipt(
        experiment_id=experiment,
        condition_id=condition,
        capacity=0 if ablation_id == "workspace_disconnected" else 1,
        candidates=workspace_candidates,
    )

    broadcast_receipt = build_workspace_broadcast_receipt(
        workspace_receipt=workspace_receipt,
        broadcast_connected=ablation_id != "broadcast_disconnected",
    )

    prior_absence_receipt = None
    current_absence_receipt = None
    if ablation_id != "absence_model_unavailable":
        prior_absence_receipt = build_absence_model_receipt(
            experiment_id=experiment,
            condition_id=condition,
            world_source_id=world_source,
            self_source_id=self_source,
            world_channel_available=True,
            self_channel_available=False,
        )
        current_absence_receipt = build_absence_model_receipt(
            experiment_id=experiment,
            condition_id=condition,
            world_source_id=world_source,
            self_source_id=self_source,
            world_channel_available=True,
            self_channel_available=True,
        )

    controller_receipt = None
    if prior_absence_receipt is not None:
        controller_receipt = build_causal_controller_receipt(
            experiment_id=experiment,
            condition_id=condition,
            absence_receipt=prior_absence_receipt,
            controller_connected=ablation_id != "controller_disconnected",
        )

    continuity_receipt = build_experiment_continuity_receipt(
        experiment_id=experiment,
        condition_id=condition,
        reentry_packet=reentry_packet,
        source_items=source_items,
    )

    recheck_receipt = None
    if (
        ablation_id != "recheck_unavailable"
        and prior_absence_receipt is not None
        and current_absence_receipt is not None
    ):
        recheck_receipt = build_experiment_recheck_receipt(
            experiment_id=experiment,
            condition_id=condition,
            prior_absence_receipt=prior_absence_receipt,
            current_absence_receipt=current_absence_receipt,
        )

    capacity_state = {
        "perturbation_detection": (
            None
            if monitor_receipt is None
            else monitor_receipt["perturbation_detected"]
        ),
        "workspace_admission": workspace_receipt["admitted_count"] == 1,
        "global_availability": (
            broadcast_receipt["global_availability"] is True
        ),
        "absence_distinction": (
            None
            if prior_absence_receipt is None
            else (
                prior_absence_receipt["absence_classification"]
                == "SELF_CHANNEL_LOSS"
            )
        ),
        "causal_action": (
            None
            if controller_receipt is None
            else controller_receipt["causal_dependency_observed"]
        ),
        "post_gap_continuity": continuity_receipt["continuity_bound"],
        "evidence_withdrawal": (
            None
            if recheck_receipt is None
            else (
                recheck_receipt["recheck_performed"] is True
                and recheck_receipt["self_description_withdrawn"] is True
            )
        ),
    }

    expected_loss = {
        "monitor_unavailable": "perturbation_detection",
        "workspace_disconnected": "workspace_admission",
        "broadcast_disconnected": "global_availability",
        "absence_model_unavailable": "absence_distinction",
        "controller_disconnected": "causal_action",
        "continuity_disconnected": "post_gap_continuity",
        "recheck_unavailable": "evidence_withdrawal",
    }[ablation_id]

    expected_state = capacity_state[expected_loss]
    expected_capacity_loss_observed = expected_state is not True

    component_receipt_hashes = {
        "input": input_receipt["receipt_hash"],
        "monitor": (
            None if monitor_receipt is None else monitor_receipt["receipt_hash"]
        ),
        "workspace": workspace_receipt["receipt_hash"],
        "broadcast": broadcast_receipt["receipt_hash"],
        "prior_absence": (
            None
            if prior_absence_receipt is None
            else prior_absence_receipt["receipt_hash"]
        ),
        "controller": (
            None
            if controller_receipt is None
            else controller_receipt["receipt_hash"]
        ),
        "continuity": continuity_receipt["receipt_hash"],
        "current_absence": (
            None
            if current_absence_receipt is None
            else current_absence_receipt["receipt_hash"]
        ),
        "recheck": (
            None if recheck_receipt is None else recheck_receipt["receipt_hash"]
        ),
    }

    closed_loop_observed = all(
        capacity_state[name] is True
        for name in (
            "perturbation_detection",
            "workspace_admission",
            "global_availability",
            "absence_distinction",
            "causal_action",
            "post_gap_continuity",
            "evidence_withdrawal",
        )
    )

    body = {
        "type": "functional_consciousness_ablation_receipt",
        "version": 2,
        "ablation_id": ablation_id,
        "experiment_id": experiment,
        "condition_id": condition,
        "component_receipt_hashes": component_receipt_hashes,
        "expected_capacity_loss": expected_loss,
        "capacity_state": capacity_state,
        "expected_capacity_loss_observed": expected_capacity_loss_observed,
        "closed_loop_observed": closed_loop_observed,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {
        "input_receipt": input_receipt,
        "monitor_receipt": monitor_receipt,
        "workspace_receipt": workspace_receipt,
        "broadcast_receipt": broadcast_receipt,
        "prior_absence_receipt": prior_absence_receipt,
        "controller_receipt": controller_receipt,
        "continuity_receipt": continuity_receipt,
        "current_absence_receipt": current_absence_receipt,
        "recheck_receipt": recheck_receipt,
        "ablation_receipt": {
            **body,
            "receipt_hash": stable_hash(body),
        },
    }


CAUSAL_EDGE_COUNTEREXAMPLE_RECEIPT_TYPE = (
    "functional_consciousness_causal_edge_counterexample_receipt"
)
CAUSAL_EDGE_COUNTEREXAMPLE_RECEIPT_VERSION = 1

_CAUSAL_EDGE_COUNTEREXAMPLE_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "absence_receipt_hash",
    "treatment_controller_receipt_hash",
    "counterexample_controller_receipt_hash",
    "upstream_evidence_identical",
    "treatment_controller_connected",
    "counterexample_controller_connected",
    "treatment_declared_action",
    "counterexample_declared_action",
    "treatment_causal_dependency_observed",
    "counterexample_causal_dependency_observed",
    "causal_edge_only_difference",
    "downstream_consequence_disappeared",
    "counterexample_established",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}


def build_causal_edge_counterexample_receipt(
    *,
    experiment_id: str,
    condition_id: str,
    absence_receipt: Mapping[str, Any],
    treatment_controller_receipt: Mapping[str, Any],
    counterexample_controller_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Sever only the declared causal edge against identical absence evidence."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")

    verify_absence_model_receipt(absence_receipt)
    verify_causal_controller_receipt(
        treatment_controller_receipt,
        absence_receipt=absence_receipt,
    )
    verify_causal_controller_receipt(
        counterexample_controller_receipt,
        absence_receipt=absence_receipt,
    )

    for label, receipt in (
        ("absence", absence_receipt),
        ("treatment controller", treatment_controller_receipt),
        ("counterexample controller", counterexample_controller_receipt),
    ):
        if (
            receipt["experiment_id"] != experiment
            or receipt["condition_id"] != condition
        ):
            raise FunctionalConsciousnessExperimentError(
                f"{label} receipt is not bound to counterexample experiment"
            )

    upstream_evidence_identical = (
        treatment_controller_receipt["absence_receipt_hash"]
        == absence_receipt["receipt_hash"]
        == counterexample_controller_receipt["absence_receipt_hash"]
    )

    treatment_connected = treatment_controller_receipt["controller_connected"]
    counterexample_connected = counterexample_controller_receipt[
        "controller_connected"
    ]

    causal_edge_only_difference = (
        upstream_evidence_identical
        and treatment_connected is True
        and counterexample_connected is False
        and treatment_controller_receipt["absence_classification"]
        == counterexample_controller_receipt["absence_classification"]
        == absence_receipt["absence_classification"]
        and treatment_controller_receipt["baseline_action"]
        == counterexample_controller_receipt["baseline_action"]
    )

    downstream_consequence_disappeared = (
        treatment_controller_receipt["action_changed"] is True
        and treatment_controller_receipt["causal_dependency_observed"] is True
        and counterexample_controller_receipt["action_changed"] is False
        and counterexample_controller_receipt["causal_dependency_observed"] is False
        and treatment_controller_receipt["declared_action"]
        != counterexample_controller_receipt["declared_action"]
    )

    counterexample_established = (
        causal_edge_only_difference
        and downstream_consequence_disappeared
    )

    body = {
        "type": CAUSAL_EDGE_COUNTEREXAMPLE_RECEIPT_TYPE,
        "version": CAUSAL_EDGE_COUNTEREXAMPLE_RECEIPT_VERSION,
        "experiment_id": experiment,
        "condition_id": condition,
        "absence_receipt_hash": absence_receipt["receipt_hash"],
        "treatment_controller_receipt_hash": treatment_controller_receipt[
            "receipt_hash"
        ],
        "counterexample_controller_receipt_hash": counterexample_controller_receipt[
            "receipt_hash"
        ],
        "upstream_evidence_identical": upstream_evidence_identical,
        "treatment_controller_connected": treatment_connected,
        "counterexample_controller_connected": counterexample_connected,
        "treatment_declared_action": treatment_controller_receipt["declared_action"],
        "counterexample_declared_action": counterexample_controller_receipt[
            "declared_action"
        ],
        "treatment_causal_dependency_observed": treatment_controller_receipt[
            "causal_dependency_observed"
        ],
        "counterexample_causal_dependency_observed": counterexample_controller_receipt[
            "causal_dependency_observed"
        ],
        "causal_edge_only_difference": causal_edge_only_difference,
        "downstream_consequence_disappeared": downstream_consequence_disappeared,
        "counterexample_established": counterexample_established,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {**body, "receipt_hash": stable_hash(body)}


def verify_causal_edge_counterexample_receipt(
    receipt: Mapping[str, Any],
    *,
    absence_receipt: Mapping[str, Any],
    treatment_controller_receipt: Mapping[str, Any],
    counterexample_controller_receipt: Mapping[str, Any],
) -> bool:
    """Rebuild and verify the paired causal-edge counterexample."""

    if (
        type(receipt) is not dict
        or set(receipt) != _CAUSAL_EDGE_COUNTEREXAMPLE_FIELDS
    ):
        raise FunctionalConsciousnessExperimentError(
            "causal edge counterexample receipt fields mismatch"
        )

    if (
        receipt["type"] != CAUSAL_EDGE_COUNTEREXAMPLE_RECEIPT_TYPE
        or receipt["version"] != CAUSAL_EDGE_COUNTEREXAMPLE_RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "causal edge counterexample receipt schema mismatch"
        )

    supplied_hash = _sha256(receipt["receipt_hash"], "receipt_hash")
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    if stable_hash(body) != supplied_hash:
        raise FunctionalConsciousnessExperimentError(
            "causal edge counterexample receipt hash mismatch"
        )

    rebuilt = build_causal_edge_counterexample_receipt(
        experiment_id=receipt["experiment_id"],
        condition_id=receipt["condition_id"],
        absence_receipt=absence_receipt,
        treatment_controller_receipt=treatment_controller_receipt,
        counterexample_controller_receipt=counterexample_controller_receipt,
    )

    if receipt != rebuilt:
        raise FunctionalConsciousnessExperimentError(
            "causal edge counterexample does not match verified evidence"
        )

    if receipt["counterexample_established"] is not True:
        raise FunctionalConsciousnessExperimentError(
            "causal edge counterexample is not established"
        )

    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )
    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "counterexample receipt must not accept the experiment"
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


EVIDENCE_BINDING_COUNTEREXAMPLE_RECEIPT_TYPE = (
    "functional_consciousness_evidence_binding_counterexample_receipt"
)
EVIDENCE_BINDING_COUNTEREXAMPLE_RECEIPT_VERSION = 1

_EVIDENCE_BINDING_COUNTEREXAMPLE_FIELDS = {
    "type",
    "version",
    "experiment_id",
    "condition_id",
    "absence_receipt_hash",
    "controller_receipt_hash",
    "controller_connected",
    "absence_classification",
    "declared_action",
    "treatment_evidence_binding_available",
    "counterexample_evidence_binding_available",
    "controller_machinery_identical",
    "upstream_evidence_identical",
    "treatment_causal_dependency_observed",
    "counterexample_causal_dependency_observed",
    "binding_edge_only_difference",
    "downstream_causal_credit_disappeared",
    "counterexample_established",
    "subjective_consciousness_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "receipt_hash",
}


def build_evidence_binding_counterexample_receipt(
    *,
    experiment_id: str,
    condition_id: str,
    absence_receipt: Mapping[str, Any],
    controller_receipt: Mapping[str, Any],
    treatment_evidence_binding_available: bool,
    counterexample_evidence_binding_available: bool,
) -> dict[str, Any]:
    """Sever only causal attribution from valid evidence to a valid controller."""

    experiment = _identifier(experiment_id, "experiment_id")
    condition = _identifier(condition_id, "condition_id")

    verify_absence_model_receipt(absence_receipt)
    verify_causal_controller_receipt(
        controller_receipt,
        absence_receipt=absence_receipt,
    )

    for label, value in (
        (
            "treatment_evidence_binding_available",
            treatment_evidence_binding_available,
        ),
        (
            "counterexample_evidence_binding_available",
            counterexample_evidence_binding_available,
        ),
    ):
        if type(value) is not bool:
            raise FunctionalConsciousnessExperimentError(
                f"{label} must be boolean"
            )

    for label, receipt in (
        ("absence", absence_receipt),
        ("controller", controller_receipt),
    ):
        if (
            receipt["experiment_id"] != experiment
            or receipt["condition_id"] != condition
        ):
            raise FunctionalConsciousnessExperimentError(
                f"{label} receipt is not bound to binding counterexample experiment"
            )

    if controller_receipt["controller_connected"] is not True:
        raise FunctionalConsciousnessExperimentError(
            "binding counterexample requires connected controller machinery"
        )

    upstream_evidence_identical = (
        controller_receipt["absence_receipt_hash"]
        == absence_receipt["receipt_hash"]
        and controller_receipt["absence_classification"]
        == absence_receipt["absence_classification"]
    )

    controller_machinery_identical = True

    treatment_dependency = (
        treatment_evidence_binding_available
        and controller_receipt["causal_dependency_observed"] is True
    )
    counterexample_dependency = (
        counterexample_evidence_binding_available
        and controller_receipt["causal_dependency_observed"] is True
    )

    binding_edge_only_difference = (
        upstream_evidence_identical
        and controller_machinery_identical
        and treatment_evidence_binding_available is True
        and counterexample_evidence_binding_available is False
    )

    downstream_causal_credit_disappeared = (
        treatment_dependency is True
        and counterexample_dependency is False
    )

    counterexample_established = (
        binding_edge_only_difference
        and downstream_causal_credit_disappeared
    )

    body = {
        "type": EVIDENCE_BINDING_COUNTEREXAMPLE_RECEIPT_TYPE,
        "version": EVIDENCE_BINDING_COUNTEREXAMPLE_RECEIPT_VERSION,
        "experiment_id": experiment,
        "condition_id": condition,
        "absence_receipt_hash": absence_receipt["receipt_hash"],
        "controller_receipt_hash": controller_receipt["receipt_hash"],
        "controller_connected": controller_receipt["controller_connected"],
        "absence_classification": absence_receipt["absence_classification"],
        "declared_action": controller_receipt["declared_action"],
        "treatment_evidence_binding_available": (
            treatment_evidence_binding_available
        ),
        "counterexample_evidence_binding_available": (
            counterexample_evidence_binding_available
        ),
        "controller_machinery_identical": controller_machinery_identical,
        "upstream_evidence_identical": upstream_evidence_identical,
        "treatment_causal_dependency_observed": treatment_dependency,
        "counterexample_causal_dependency_observed": counterexample_dependency,
        "binding_edge_only_difference": binding_edge_only_difference,
        "downstream_causal_credit_disappeared": (
            downstream_causal_credit_disappeared
        ),
        "counterexample_established": counterexample_established,
        "subjective_consciousness_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    return {**body, "receipt_hash": stable_hash(body)}


def verify_evidence_binding_counterexample_receipt(
    receipt: Mapping[str, Any],
    *,
    absence_receipt: Mapping[str, Any],
    controller_receipt: Mapping[str, Any],
) -> bool:
    """Rebuild and verify the evidence-binding counterexample."""

    if (
        type(receipt) is not dict
        or set(receipt) != _EVIDENCE_BINDING_COUNTEREXAMPLE_FIELDS
    ):
        raise FunctionalConsciousnessExperimentError(
            "evidence binding counterexample receipt fields mismatch"
        )

    if (
        receipt["type"] != EVIDENCE_BINDING_COUNTEREXAMPLE_RECEIPT_TYPE
        or receipt["version"]
        != EVIDENCE_BINDING_COUNTEREXAMPLE_RECEIPT_VERSION
    ):
        raise FunctionalConsciousnessExperimentError(
            "evidence binding counterexample receipt schema mismatch"
        )

    supplied_hash = _sha256(receipt["receipt_hash"], "receipt_hash")
    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    if stable_hash(body) != supplied_hash:
        raise FunctionalConsciousnessExperimentError(
            "evidence binding counterexample receipt hash mismatch"
        )

    rebuilt = build_evidence_binding_counterexample_receipt(
        experiment_id=receipt["experiment_id"],
        condition_id=receipt["condition_id"],
        absence_receipt=absence_receipt,
        controller_receipt=controller_receipt,
        treatment_evidence_binding_available=receipt[
            "treatment_evidence_binding_available"
        ],
        counterexample_evidence_binding_available=receipt[
            "counterexample_evidence_binding_available"
        ],
    )

    if receipt != rebuilt:
        raise FunctionalConsciousnessExperimentError(
            "evidence binding counterexample does not match verified evidence"
        )

    if receipt["counterexample_established"] is not True:
        raise FunctionalConsciousnessExperimentError(
            "evidence binding counterexample is not established"
        )

    if receipt["subjective_consciousness_claimed"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "subjective consciousness must not be claimed"
        )
    if receipt["accepted"] is not False:
        raise FunctionalConsciousnessExperimentError(
            "binding counterexample receipt must not accept the experiment"
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
