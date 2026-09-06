"""Persist and consume authorized baseline transitions exactly once.

This module is the mutation boundary after ``authorized_baseline_transition``.
The upstream transition receipt remains deterministic and non-mutating. This
store makes one such transition current only when:

1. the transition receipt is internally valid;
2. the supplied BASELINE_PROMOTION authorization exactly matches it;
3. that authorization has not already been consumed; and
4. the persisted current baseline head still matches the transition's
   declared previous baseline.

The append and all preconditions are evaluated under ``HoloChain``'s append
transaction, so concurrent attempts cannot both commit.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import zlib
from typing import Any, Mapping

from .canonical import CanonicalValueError, stable_hash
from .core import HoloChain
from .typed_operational_authorization import (
    ACTION_BASELINE_PROMOTION,
    OperationalAuthorizationError,
    validate_operational_authorization,
)


RECORD_TYPE = "persistent_baseline_transition"
RECORD_VERSION = 1

TRANSITION_TYPE = "authorized_baseline_transition"
TRANSITION_VERSION = 1
TRANSITION_FIELDS = {
    "type",
    "version",
    "previous_baseline_id",
    "previous_baseline_state_hash",
    "promotion_gate_id",
    "candidate_hash",
    "next_baseline_id",
    "next_baseline_state_hash",
    "authorization_hash",
    "authorized_by_actor_id",
    "status",
    "next_baseline_created",
    "truth_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "promotion_authority",
    "transition_id",
}

RECORD_FIELDS = {
    "type",
    "version",
    "store_initial_baseline_id",
    "store_initial_baseline_state_hash",
    "transition",
    "operational_authorization",
    "record_id",
}


class PersistentBaselineTransitionError(ValueError):
    """A baseline transition cannot be safely persisted."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise PersistentBaselineTransitionError(f"{field} must be nonempty text")
    return value.strip()


def _verify_transition(transition: Mapping[str, Any]) -> dict[str, Any]:
    if type(transition) is not dict or set(transition) != TRANSITION_FIELDS:
        raise PersistentBaselineTransitionError(
            "transition fields do not match the versioned schema"
        )

    body = {
        key: deepcopy(value)
        for key, value in transition.items()
        if key != "transition_id"
    }
    try:
        expected_id = stable_hash(body)
    except CanonicalValueError as exc:
        raise PersistentBaselineTransitionError(str(exc)) from exc

    if transition["transition_id"] != expected_id:
        raise PersistentBaselineTransitionError("transition identity is invalid")
    if (
        transition["type"] != TRANSITION_TYPE
        or transition["version"] != TRANSITION_VERSION
    ):
        raise PersistentBaselineTransitionError(
            "transition type or version is invalid"
        )
    if transition["status"] != "AUTHORIZED":
        raise PersistentBaselineTransitionError("transition is not authorized")
    if transition["next_baseline_created"] is not True:
        raise PersistentBaselineTransitionError(
            "transition must identify a created next baseline"
        )
    if transition["truth_claimed"] is not False or transition["accepted"] is not False:
        raise PersistentBaselineTransitionError(
            "transition must remain non-epistemic"
        )
    if transition["write_authority"] != "NONE":
        raise PersistentBaselineTransitionError(
            "transition must not grant write authority"
        )
    if transition["execution_authority"] != "NONE":
        raise PersistentBaselineTransitionError(
            "transition must not grant execution authority"
        )
    if transition["promotion_authority"] != "EXACT_TARGET_ONLY":
        raise PersistentBaselineTransitionError(
            "transition promotion authority is invalid"
        )

    _text(transition["previous_baseline_id"], "previous_baseline_id")
    _text(
        transition["previous_baseline_state_hash"],
        "previous_baseline_state_hash",
    )
    _text(transition["next_baseline_id"], "next_baseline_id")
    _text(transition["next_baseline_state_hash"], "next_baseline_state_hash")
    _text(transition["candidate_hash"], "candidate_hash")
    _text(transition["authorization_hash"], "authorization_hash")
    _text(transition["authorized_by_actor_id"], "authorized_by_actor_id")
    return deepcopy(transition)


def _verify_authorization_for_transition(
    authorization: Mapping[str, Any],
    *,
    transition: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        validate_operational_authorization(
            authorization,
            expected_action=ACTION_BASELINE_PROMOTION,
            expected_target_sha256=transition["candidate_hash"],
        )
    except OperationalAuthorizationError as exc:
        raise PersistentBaselineTransitionError(str(exc)) from exc

    if authorization["authorization_hash"] != transition["authorization_hash"]:
        raise PersistentBaselineTransitionError(
            "authorization hash does not match transition"
        )
    if authorization["actor_id"] != transition["authorized_by_actor_id"]:
        raise PersistentBaselineTransitionError(
            "authorization actor does not match transition"
        )
    return deepcopy(authorization)


def _decode_entry_payload(entry: Mapping[str, Any]) -> Any:
    stored = entry.get("content")
    if not isinstance(stored, str):
        raise PersistentBaselineTransitionError(
            "baseline transition history contains invalid content"
        )

    if entry.get("type") == "compressed":
        try:
            stored = zlib.decompress(bytes.fromhex(stored)).decode("utf-8")
        except (ValueError, zlib.error, UnicodeDecodeError) as exc:
            raise PersistentBaselineTransitionError(
                "baseline transition history cannot be reconstructed"
            ) from exc

    try:
        return json.loads(stored)
    except json.JSONDecodeError:
        return None


def _build_record(
    *,
    initial_baseline_id: str,
    initial_baseline_state_hash: str,
    transition: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    body = {
        "type": RECORD_TYPE,
        "version": RECORD_VERSION,
        "store_initial_baseline_id": _text(
            initial_baseline_id, "initial_baseline_id"
        ),
        "store_initial_baseline_state_hash": _text(
            initial_baseline_state_hash,
            "initial_baseline_state_hash",
        ),
        "transition": deepcopy(dict(transition)),
        "operational_authorization": deepcopy(dict(authorization)),
    }
    return {**body, "record_id": stable_hash(body)}


def _verify_record(record: Mapping[str, Any]) -> dict[str, Any]:
    if type(record) is not dict or set(record) != RECORD_FIELDS:
        raise PersistentBaselineTransitionError(
            "persisted transition fields do not match the versioned schema"
        )

    body = {
        key: deepcopy(value)
        for key, value in record.items()
        if key != "record_id"
    }
    try:
        expected_id = stable_hash(body)
    except CanonicalValueError as exc:
        raise PersistentBaselineTransitionError(str(exc)) from exc

    if record["record_id"] != expected_id:
        raise PersistentBaselineTransitionError(
            "persisted transition identity is invalid"
        )
    if record["type"] != RECORD_TYPE or record["version"] != RECORD_VERSION:
        raise PersistentBaselineTransitionError(
            "persisted transition type or version is invalid"
        )

    checked_transition = _verify_transition(record["transition"])
    checked_authorization = _verify_authorization_for_transition(
        record["operational_authorization"],
        transition=checked_transition,
    )

    return {
        **deepcopy(record),
        "transition": checked_transition,
        "operational_authorization": checked_authorization,
    }


def _records_from_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in entries:
        payload = _decode_entry_payload(entry)
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != RECORD_TYPE:
            continue
        records.append(_verify_record(payload))
    return records


def _reconstruct_head(
    records: list[dict[str, Any]],
    *,
    initial_baseline_id: str,
    initial_baseline_state_hash: str,
) -> tuple[str, str, set[str], set[str]]:
    initial_id = _text(initial_baseline_id, "initial_baseline_id")
    initial_hash = _text(initial_baseline_state_hash, "initial_baseline_state_hash")
    current_id = initial_id
    current_hash = initial_hash
    used_ids: set[str] = set()
    used_hashes: set[str] = set()

    for record in records:
        if (
            record["store_initial_baseline_id"] != initial_id
            or record["store_initial_baseline_state_hash"] != initial_hash
        ):
            raise PersistentBaselineTransitionError(
                "persisted store initial baseline does not match"
            )

        transition = record["transition"]
        authorization = record["operational_authorization"]

        if authorization["authorization_id"] in used_ids:
            raise PersistentBaselineTransitionError(
                "persisted authorization id was consumed more than once"
            )
        if authorization["authorization_hash"] in used_hashes:
            raise PersistentBaselineTransitionError(
                "persisted authorization hash was consumed more than once"
            )

        if (
            transition["previous_baseline_id"] != current_id
            or transition["previous_baseline_state_hash"] != current_hash
        ):
            raise PersistentBaselineTransitionError(
                "persisted baseline transition history is not contiguous"
            )

        used_ids.add(authorization["authorization_id"])
        used_hashes.add(authorization["authorization_hash"])
        current_id = transition["next_baseline_id"]
        current_hash = transition["next_baseline_state_hash"]

    return current_id, current_hash, used_ids, used_hashes


class PersistentBaselineTransitionStore:
    """Append-only current-baseline store with exact-once promotion consumption."""

    def __init__(
        self,
        path: str | Path,
        *,
        initial_baseline_id: str,
        initial_baseline_state_hash: str,
    ) -> None:
        self.path = Path(path)
        self.initial_baseline_id = _text(
            initial_baseline_id, "initial_baseline_id"
        )
        self.initial_baseline_state_hash = _text(
            initial_baseline_state_hash,
            "initial_baseline_state_hash",
        )
        self.chain = HoloChain(self.path)

    def current_head(self) -> dict[str, Any]:
        entries = self.chain.load_and_verify()
        records = _records_from_entries(entries)
        current_id, current_hash, _, _ = _reconstruct_head(
            records,
            initial_baseline_id=self.initial_baseline_id,
            initial_baseline_state_hash=self.initial_baseline_state_hash,
        )
        return {
            "baseline_id": current_id,
            "baseline_state_hash": current_hash,
            "transition_count": len(records),
        }

    def commit(
        self,
        *,
        transition: Mapping[str, Any],
        authorization: Mapping[str, Any],
    ) -> dict[str, Any]:
        checked_transition = _verify_transition(transition)
        checked_authorization = _verify_authorization_for_transition(
            authorization,
            transition=checked_transition,
        )
        record = _build_record(
            initial_baseline_id=self.initial_baseline_id,
            initial_baseline_state_hash=self.initial_baseline_state_hash,
            transition=checked_transition,
            authorization=checked_authorization,
        )

        authorization_id = checked_authorization["authorization_id"]
        authorization_hash = checked_authorization["authorization_hash"]

        def require_current_and_unconsumed(entries: list[dict[str, Any]]) -> None:
            records = _records_from_entries(entries)
            current_id, current_hash, used_ids, used_hashes = _reconstruct_head(
                records,
                initial_baseline_id=self.initial_baseline_id,
                initial_baseline_state_hash=self.initial_baseline_state_hash,
            )

            if authorization_id in used_ids or authorization_hash in used_hashes:
                raise PersistentBaselineTransitionError(
                    "authorization has already been consumed"
                )

            if (
                checked_transition["previous_baseline_id"] != current_id
                or checked_transition["previous_baseline_state_hash"] != current_hash
            ):
                raise PersistentBaselineTransitionError(
                    "transition previous baseline does not match current head"
                )

        entry = self.chain.append(
            record,
            compress=False,
            precondition=require_current_and_unconsumed,
        )

        return {
            "status": "COMMITTED",
            "commit_performed": True,
            "record_id": record["record_id"],
            "transition_id": checked_transition["transition_id"],
            "authorization_hash": authorization_hash,
            "previous_baseline_id": checked_transition["previous_baseline_id"],
            "previous_baseline_state_hash": checked_transition[
                "previous_baseline_state_hash"
            ],
            "current_baseline_id": checked_transition["next_baseline_id"],
            "current_baseline_state_hash": checked_transition[
                "next_baseline_state_hash"
            ],
            "chain_entry": entry,
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }
