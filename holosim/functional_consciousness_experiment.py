"""Deterministic input contract for the functional-consciousness experiment.

This module establishes source-separated world and self state for the bounded
reference experiment. It does not monitor internal state, broadcast workspace
content, control action, establish subjective consciousness, accept a result,
or grant write or execution authority.
"""

from __future__ import annotations

import math
import re
from typing import Any, Mapping

from holosim.canonical import stable_hash


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