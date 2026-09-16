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
import hashlib
import json
from pathlib import Path
import zlib
from typing import Any, Mapping

from .authorized_verified_claim_correction_transition import (
    AuthorizedVerifiedClaimCorrectionTransitionError,
    validate_authorized_verified_claim_correction_transition,
)
from .canonical import CanonicalValueError, stable_hash
from .core import HoloChain
from .typed_operational_authorization import (
    ACTION_BASELINE_PROMOTION,
    ACTION_VERIFIED_CLAIM_CORRECTION_PROMOTION,
    OperationalAuthorizationError,
    validate_operational_authorization,
)


RECORD_TYPE = "persistent_baseline_transition"
RECORD_VERSION = 1
VERIFIED_CORRECTION_RECORD_TYPE = (
    "persistent_verified_claim_correction_transition"
)
VERIFIED_CORRECTION_RECORD_VERSION = 1
VERIFIED_CORRECTION_READ_TYPE = "persisted_verified_claim_correction_read"
VERIFIED_CORRECTION_READ_VERSION = 1

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

VERIFIED_CORRECTION_RECORD_FIELDS = {
    "type",
    "version",
    "store_initial_baseline_id",
    "store_initial_baseline_state_hash",
    "authorized_correction",
    "record_id",
}

VERIFIED_CORRECTION_READ_FIELDS = {
    "type",
    "version",
    "record",
    "record_id",
    "chain_entry",
    "chain_entry_hash",
    "transition_index",
    "transition_count",
    "current_baseline_id",
    "current_baseline_state_hash",
    "record_is_current_head",
    "read_only",
    "accepted",
    "truth_claimed",
    "write_authority",
    "execution_authority",
    "canonical_mutation",
    "interpretation_notice",
    "read_hash",
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
    expected_action: str = ACTION_BASELINE_PROMOTION,
) -> dict[str, Any]:
    try:
        validate_operational_authorization(
            authorization,
            expected_action=expected_action,
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


def _verify_authorized_correction(
    authorized_correction: Mapping[str, Any],
) -> dict[str, Any]:
    if type(authorized_correction) is not dict:
        raise PersistentBaselineTransitionError(
            "authorized_correction must be a plain dictionary"
        )

    try:
        validate_authorized_verified_claim_correction_transition(
            authorized_correction
        )
    except AuthorizedVerifiedClaimCorrectionTransitionError as exc:
        raise PersistentBaselineTransitionError(
            f"authorized correction is invalid: {exc}"
        ) from exc

    return deepcopy(authorized_correction)


def _build_verified_correction_record(
    *,
    initial_baseline_id: str,
    initial_baseline_state_hash: str,
    authorized_correction: Mapping[str, Any],
) -> dict[str, Any]:
    body = {
        "type": VERIFIED_CORRECTION_RECORD_TYPE,
        "version": VERIFIED_CORRECTION_RECORD_VERSION,
        "store_initial_baseline_id": _text(
            initial_baseline_id, "initial_baseline_id"
        ),
        "store_initial_baseline_state_hash": _text(
            initial_baseline_state_hash,
            "initial_baseline_state_hash",
        ),
        "authorized_correction": deepcopy(dict(authorized_correction)),
    }
    return {**body, "record_id": stable_hash(body)}


def _verify_verified_correction_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        type(record) is not dict
        or set(record) != VERIFIED_CORRECTION_RECORD_FIELDS
    ):
        raise PersistentBaselineTransitionError(
            "persisted verified correction fields do not match the "
            "versioned schema"
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
            "persisted verified correction identity is invalid"
        )
    if (
        record["type"] != VERIFIED_CORRECTION_RECORD_TYPE
        or record["version"] != VERIFIED_CORRECTION_RECORD_VERSION
    ):
        raise PersistentBaselineTransitionError(
            "persisted verified correction type or version is invalid"
        )

    checked_correction = _verify_authorized_correction(
        record["authorized_correction"]
    )
    checked_transition = _verify_transition(
        checked_correction["authorized_baseline_transition"]
    )
    checked_authorization = _verify_authorization_for_transition(
        checked_correction["operational_authorization"],
        transition=checked_transition,
        expected_action=ACTION_VERIFIED_CLAIM_CORRECTION_PROMOTION,
    )

    return {
        **deepcopy(record),
        "authorized_correction": checked_correction,
        "transition": checked_transition,
        "operational_authorization": checked_authorization,
    }


def _exact_persisted_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: deepcopy(record[field])
        for field in VERIFIED_CORRECTION_RECORD_FIELDS
    }


def _verify_chain_entry_for_record(
    entry: Mapping[str, Any],
    *,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    expected_fields = {
        "idx",
        "timestamp",
        "content",
        "prev_hash",
        "hash",
        "type",
        "original_size",
    }
    if type(entry) is not dict or set(entry) != expected_fields:
        raise PersistentBaselineTransitionError(
            "chain entry fields do not match the versioned schema"
        )
    if entry["type"] != "plain":
        raise PersistentBaselineTransitionError(
            "verified correction record must use a plain chain entry"
        )
    if type(entry["idx"]) is not int or entry["idx"] < 1:
        raise PersistentBaselineTransitionError("chain entry index is invalid")
    if type(entry["timestamp"]) is not str or not entry["timestamp"]:
        raise PersistentBaselineTransitionError(
            "chain entry timestamp is invalid"
        )
    if type(entry["prev_hash"]) is not str:
        raise PersistentBaselineTransitionError(
            "chain entry previous hash is invalid"
        )
    if type(entry["content"]) is not str:
        raise PersistentBaselineTransitionError(
            "chain entry content is invalid"
        )

    try:
        decoded = json.loads(entry["content"])
    except json.JSONDecodeError as exc:
        raise PersistentBaselineTransitionError(
            "chain entry content is not valid JSON"
        ) from exc
    if decoded != record:
        raise PersistentBaselineTransitionError(
            "chain entry does not contain the persisted correction record"
        )

    canonical = json.dumps(
        {
            "idx": entry["idx"],
            "timestamp": entry["timestamp"],
            "content": entry["content"],
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    expected_hash = hashlib.sha256(
        entry["prev_hash"].encode() + canonical.encode()
    ).hexdigest()
    if entry["hash"] != expected_hash:
        raise PersistentBaselineTransitionError(
            "chain entry identity is invalid"
        )
    if entry["original_size"] != len(entry["content"]):
        raise PersistentBaselineTransitionError(
            "chain entry original size is invalid"
        )
    return deepcopy(entry)


def validate_persisted_verified_claim_correction_read(
    receipt: Mapping[str, Any],
) -> bool:
    """Validate one read-only receipt for a persisted verified correction."""
    if type(receipt) is not dict or set(receipt) != VERIFIED_CORRECTION_READ_FIELDS:
        raise PersistentBaselineTransitionError(
            "persisted correction read fields do not match the versioned schema"
        )
    if (
        receipt["type"] != VERIFIED_CORRECTION_READ_TYPE
        or receipt["version"] != VERIFIED_CORRECTION_READ_VERSION
    ):
        raise PersistentBaselineTransitionError(
            "persisted correction read type or version is invalid"
        )

    checked_record = _verify_verified_correction_record(receipt["record"])
    exact_record = _exact_persisted_record(checked_record)
    checked_entry = _verify_chain_entry_for_record(
        receipt["chain_entry"],
        record=exact_record,
    )
    transition = checked_record["transition"]

    if receipt["record_id"] != exact_record["record_id"]:
        raise PersistentBaselineTransitionError(
            "persisted correction read record identity is invalid"
        )
    if receipt["chain_entry_hash"] != checked_entry["hash"]:
        raise PersistentBaselineTransitionError(
            "persisted correction read chain identity is invalid"
        )
    if (
        type(receipt["transition_index"]) is not int
        or receipt["transition_index"] < 1
        or type(receipt["transition_count"]) is not int
        or receipt["transition_count"] < receipt["transition_index"]
    ):
        raise PersistentBaselineTransitionError(
            "persisted correction read position is invalid"
        )
    if receipt["record_is_current_head"] is True:
        if receipt["transition_index"] != receipt["transition_count"]:
            raise PersistentBaselineTransitionError(
                "current persisted correction must be the latest transition"
            )
        if (
            receipt["current_baseline_id"] != transition["next_baseline_id"]
            or receipt["current_baseline_state_hash"]
            != transition["next_baseline_state_hash"]
        ):
            raise PersistentBaselineTransitionError(
                "current persisted correction does not match the current head"
            )
    elif receipt["record_is_current_head"] is not False:
        raise PersistentBaselineTransitionError(
            "record_is_current_head must be boolean"
        )

    body = {
        key: deepcopy(value)
        for key, value in receipt.items()
        if key != "read_hash"
    }
    if (
        body["read_only"] is not True
        or body["accepted"] is not False
        or body["truth_claimed"] is not False
        or body["write_authority"] != "NONE"
        or body["execution_authority"] != "NONE"
        or body["canonical_mutation"] is not False
    ):
        raise PersistentBaselineTransitionError(
            "persisted correction read must remain read-only"
        )
    if receipt["read_hash"] != stable_hash(body):
        raise PersistentBaselineTransitionError(
            "persisted correction read identity is invalid"
        )
    return True


def _records_from_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in entries:
        payload = _decode_entry_payload(entry)
        if not isinstance(payload, dict):
            continue
        if payload.get("type") == RECORD_TYPE:
            records.append(_verify_record(payload))
        elif payload.get("type") == VERIFIED_CORRECTION_RECORD_TYPE:
            records.append(_verify_verified_correction_record(payload))
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

    def read_verified_claim_correction(
        self,
        *,
        record_id: str,
    ) -> dict[str, Any]:
        """Read one verified-correction record from one verified chain snapshot."""
        checked_record_id = _text(record_id, "record_id")
        entries = self.chain.load_and_verify()
        records: list[dict[str, Any]] = []
        record_entries: list[dict[str, Any]] = []

        for entry in entries:
            payload = _decode_entry_payload(entry)
            if not isinstance(payload, dict):
                continue
            if payload.get("type") == RECORD_TYPE:
                records.append(_verify_record(payload))
                record_entries.append(deepcopy(entry))
            elif payload.get("type") == VERIFIED_CORRECTION_RECORD_TYPE:
                records.append(_verify_verified_correction_record(payload))
                record_entries.append(deepcopy(entry))

        current_id, current_hash, _, _ = _reconstruct_head(
            records,
            initial_baseline_id=self.initial_baseline_id,
            initial_baseline_state_hash=self.initial_baseline_state_hash,
        )
        matches = [
            index
            for index, record in enumerate(records)
            if record.get("type") == VERIFIED_CORRECTION_RECORD_TYPE
            and record.get("record_id") == checked_record_id
        ]
        if not matches:
            raise PersistentBaselineTransitionError(
                "persisted verified correction record was not found"
            )
        if len(matches) != 1:
            raise PersistentBaselineTransitionError(
                "persisted verified correction record identity is ambiguous"
            )

        index = matches[0]
        exact_record = _exact_persisted_record(records[index])
        checked_entry = _verify_chain_entry_for_record(
            record_entries[index],
            record=exact_record,
        )
        body = {
            "type": VERIFIED_CORRECTION_READ_TYPE,
            "version": VERIFIED_CORRECTION_READ_VERSION,
            "record": exact_record,
            "record_id": checked_record_id,
            "chain_entry": checked_entry,
            "chain_entry_hash": checked_entry["hash"],
            "transition_index": index + 1,
            "transition_count": len(records),
            "current_baseline_id": current_id,
            "current_baseline_state_hash": current_hash,
            "record_is_current_head": index == len(records) - 1,
            "read_only": True,
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
            "canonical_mutation": False,
            "interpretation_notice": (
                "This receipt is one read-only observation of a record in a "
                "verified append-only baseline-transition chain. It does not "
                "re-observe claim conditions, establish truth or acceptance, "
                "mutate state, or grant authority."
            ),
        }
        receipt = {**body, "read_hash": stable_hash(body)}
        validate_persisted_verified_claim_correction_read(receipt)
        return receipt

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

    def commit_verified_claim_correction(
        self,
        *,
        authorized_correction: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Atomically persist one fully bound verified-correction transition."""
        checked_correction = _verify_authorized_correction(
            authorized_correction
        )
        checked_transition = _verify_transition(
            checked_correction["authorized_baseline_transition"]
        )
        checked_authorization = _verify_authorization_for_transition(
            checked_correction["operational_authorization"],
            transition=checked_transition,
            expected_action=ACTION_VERIFIED_CLAIM_CORRECTION_PROMOTION,
        )
        record = _build_verified_correction_record(
            initial_baseline_id=self.initial_baseline_id,
            initial_baseline_state_hash=self.initial_baseline_state_hash,
            authorized_correction=checked_correction,
        )

        authorization_id = checked_authorization["authorization_id"]
        authorization_hash = checked_authorization["authorization_hash"]

        def require_current_and_unconsumed(
            entries: list[dict[str, Any]],
        ) -> None:
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
                or checked_transition["previous_baseline_state_hash"]
                != current_hash
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
            "status": "COMMITTED_VERIFIED_CLAIM_CORRECTION",
            "commit_performed": True,
            "record_id": record["record_id"],
            "verification_hash": checked_correction["verification_hash"],
            "proposal_hash": checked_correction["proposal_hash"],
            "binding_hash": checked_correction["binding_hash"],
            "authorization_binding_hash": checked_correction[
                "authorization_binding_hash"
            ],
            "candidate_hash": checked_correction["candidate_hash"],
            "transition_id": checked_transition["transition_id"],
            "authorization_hash": authorization_hash,
            "previous_baseline_id": checked_transition[
                "previous_baseline_id"
            ],
            "previous_baseline_state_hash": checked_transition[
                "previous_baseline_state_hash"
            ],
            "current_baseline_id": checked_transition["next_baseline_id"],
            "current_baseline_state_hash": checked_transition[
                "next_baseline_state_hash"
            ],
            "chain_entry": entry,
            "authorization_consumed": True,
            "transition_persisted": True,
            "correction_provenance_persisted": True,
            "current_baseline_advanced": True,
            "correction_applied": False,
            "supersession_performed": True,
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
            "promotion_authority": "EXACT_TARGET_ONLY",
            "canonical_mutation": True,
            "interpretation_notice": (
                "This receipt records one append-only baseline-head mutation "
                "whose complete verified-correction provenance and exact "
                "authorization were persisted atomically. It consumes only "
                "that authorization and supersedes only the store's current "
                "baseline head. It does not apply claim text to an external "
                "system, establish truth or acceptance, grant general write "
                "or execution authority, or perform post-persistence "
                "re-observation."
            ),
        }
