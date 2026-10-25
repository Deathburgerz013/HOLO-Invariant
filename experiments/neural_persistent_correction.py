"""Append-only, checkpoint-bound neural correction persistence.

This is an experimental state store, not an independent authority issuer.
A valid authorization declaration alone does not authenticate its issuer.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from experiments.neural_authorized_correction import (
    verify_authorized_neural_correction,
)
from experiments.neural_checkpoint import verify_checkpoint
from holosim.core import HoloChain
from holosim.typed_operational_authorization import (
    ACTION_NEURAL_WEIGHT_CORRECTION,
    validate_operational_authorization,
)

RECORD_TYPE = "holo_neural_checkpoint_transition"
RECORD_VERSION = 1


class NeuralPersistenceError(ValueError):
    """A neural persistence invariant was violated."""


def _records(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []

    for entry in entries:
        if entry.get("type") != "plain":
            raise NeuralPersistenceError("unexpected compressed chain entry")

        try:
            payload = json.loads(entry["content"])
        except (KeyError, TypeError, ValueError) as exc:
            raise NeuralPersistenceError("invalid chain payload") from exc

        if not isinstance(payload, dict):
            raise NeuralPersistenceError("invalid record structure")

        if payload.get("type") != RECORD_TYPE:
            raise NeuralPersistenceError("unexpected record type")

        if set(payload) != {
            "type",
            "version",
            "before_checkpoint_hash",
            "after_checkpoint",
            "proposal",
            "authorization",
        }:
            raise NeuralPersistenceError("record fields mismatch")

        if type(payload["version"]) is not int or payload["version"] != RECORD_VERSION:
            raise NeuralPersistenceError("unsupported record version")

        records.append(payload)

    return records


class PersistentNeuralCorrectionStore:
    """A separate experimental checkpoint history using canonical HoloChain."""

    def __init__(self, path: str | Path, *, initial_checkpoint: Mapping[str, Any]):
        verify_checkpoint(initial_checkpoint)
        self.initial_checkpoint = deepcopy(dict(initial_checkpoint))
        self.chain = HoloChain(path)

    def _reconstruct(self, entries: list[dict[str, Any]]):
        current = deepcopy(self.initial_checkpoint)
        used_ids: set[str] = set()
        used_hashes: set[str] = set()

        for record in _records(entries):
            proposal = record["proposal"]
            authorization = record["authorization"]

            if record["before_checkpoint_hash"] != current["checkpoint_hash"]:
                raise NeuralPersistenceError("checkpoint history continuity mismatch")

            verify_authorized_neural_correction(
                current, proposal, authorization,
            )

            if record["after_checkpoint"] != proposal["after_checkpoint"]:
                raise NeuralPersistenceError("persisted checkpoint mismatch")

            auth_id = authorization["authorization_id"]
            auth_hash = authorization["authorization_hash"]

            if auth_id in used_ids or auth_hash in used_hashes:
                raise NeuralPersistenceError("authorization replay in history")

            used_ids.add(auth_id)
            used_hashes.add(auth_hash)
            current = deepcopy(record["after_checkpoint"])

        return current, used_ids, used_hashes

    def current_checkpoint(self) -> dict[str, Any]:
        entries = self.chain.load_and_verify()
        current, _, _ = self._reconstruct(entries)
        return current

    def commit(
        self,
        *,
        proposal: Mapping[str, Any],
        authorization: Mapping[str, Any],
    ) -> dict[str, Any]:
        # Validate the declaration before entering the append transaction.
        validate_operational_authorization(
            authorization,
            expected_action=ACTION_NEURAL_WEIGHT_CORRECTION,
            expected_target_sha256=proposal["proposal_hash"],
        )
        checked_authorization = deepcopy(dict(authorization))

        record_holder: dict[str, Any] = {}

        def require_current_and_unconsumed(entries):
            current, used_ids, used_hashes = self._reconstruct(entries)

            verify_authorized_neural_correction(
                current, proposal, checked_authorization,
            )

            auth_id = checked_authorization["authorization_id"]
            auth_hash = checked_authorization["authorization_hash"]

            if auth_id in used_ids or auth_hash in used_hashes:
                raise NeuralPersistenceError("authorization already consumed")

            record_holder["record"] = {
                "type": RECORD_TYPE,
                "version": RECORD_VERSION,
                "before_checkpoint_hash": current["checkpoint_hash"],
                "after_checkpoint": deepcopy(proposal["after_checkpoint"]),
                "proposal": deepcopy(dict(proposal)),
                "authorization": deepcopy(dict(checked_authorization)),
            }

        # The precondition is evaluated under the HoloChain append lock.
        # The actual append content must be prepared before append(), so
        # validate the candidate against a snapshot first, then recheck
        # everything under the lock.
        initial_entries = self.chain.load_and_verify()
        require_current_and_unconsumed(initial_entries)
        candidate = record_holder["record"]

        def locked_precondition(entries):
            require_current_and_unconsumed(entries)
            if record_holder["record"] != candidate:
                raise NeuralPersistenceError("candidate changed before append")

        entry = self.chain.append(
            candidate,
            compress=False,
            precondition=locked_precondition,
        )

        return {
            "status": "COMMITTED",
            "commit_performed": True,
            "checkpoint_hash": candidate["after_checkpoint"]["checkpoint_hash"],
            "authorization_hash": checked_authorization["authorization_hash"],
            "chain_entry": entry,
            "truth_claimed": False,
            "accepted": False,
            "execution_authority": "NONE",
        }
