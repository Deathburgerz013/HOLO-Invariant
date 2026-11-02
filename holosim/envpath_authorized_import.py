"""Explicit, evidence-bound import of EnvPath note proposals."""

import hashlib
import json
import zlib
from pathlib import Path
from typing import Any, Mapping

from .core import HoloChain
from .typed_operational_authorization import (
    ACTION_ENVPATH_NOTE_IMPORT,
    OperationalAuthorizationError,
    validate_operational_authorization,
)


class EnvPathImportError(ValueError):
    """An EnvPath proposal failed import validation."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "commit_performed": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "reason": reason,
    }


def import_note_draft(
    chain_path: str | Path,
    *,
    draft: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    """Import an externally reviewed note without exposing model write tools."""

    try:
        if type(draft) is not dict:
            raise EnvPathImportError("draft must be an object")

        required = {
            "type", "version", "status", "kind", "content",
            "target", "source_head_hash", "source_sha256",
            "accepted", "truth_claimed", "write_authority",
            "execution_authority", "draft_hash",
        }
        if set(draft) != required:
            raise EnvPathImportError("draft schema mismatch")

        if (
            draft["type"] != "envpath_draft"
            or type(draft["version"]) is not int
            or draft["version"] != 1
            or draft["status"] != "PROPOSAL_ONLY"
            or draft["kind"] != "note"
            or draft["target"] is not None
            or type(draft["content"]) is not str
            or not draft["content"].strip()
            or draft["accepted"] is not False
            or draft["truth_claimed"] is not False
            or draft["write_authority"] != "NONE"
            or draft["execution_authority"] != "NONE"
        ):
            raise EnvPathImportError("invalid note proposal")

        body = {key: value for key, value in draft.items() if key != "draft_hash"}
        if _digest(_canonical(body)) != draft["draft_hash"]:
            raise EnvPathImportError("draft hash mismatch")

        validate_operational_authorization(
            authorization,
            expected_action=ACTION_ENVPATH_NOTE_IMPORT,
            expected_target_sha256=draft["draft_hash"],
        )

        chain = HoloChain(chain_path)
        source_path = Path(chain_path)

        payload = {
            "type": "envpath_imported_note",
            "version": 1,
            "content": draft["content"],
            "draft_hash": draft["draft_hash"],
            "source_sha256": draft["source_sha256"],
            "operational_authorization": dict(authorization),
            "accepted": False,
            "truth_claimed": False,
        }

        precondition_completed = False

        def require_current_and_unconsumed(entries):
            nonlocal precondition_completed
            raw = source_path.read_bytes() if source_path.exists() else b""

            if _digest(raw) != draft["source_sha256"]:
                raise EnvPathImportError("source changed before import")

            actual_head = entries[-1]["hash"] if entries else None
            if actual_head != draft["source_head_hash"]:
                raise EnvPathImportError("source head changed before import")

            for entry in entries:
                stored = entry.get("content")
                if entry.get("type") == "compressed":
                    stored = zlib.decompress(
                        bytes.fromhex(stored)
                    ).decode("utf-8")

                try:
                    previous = json.loads(stored)
                except (TypeError, ValueError):
                    continue

                if not isinstance(previous, dict):
                    continue

                if previous.get("type") != "envpath_imported_note":
                    continue

                required_import_fields = {
                    "type",
                    "version",
                    "content",
                    "draft_hash",
                    "source_sha256",
                    "operational_authorization",
                    "accepted",
                    "truth_claimed",
                }

                if (
                    set(previous) != required_import_fields
                    or type(previous["version"]) is not int
                    or previous["version"] != 1
                    or type(previous["content"]) is not str
                    or not previous["content"].strip()
                    or type(previous["draft_hash"]) is not str
                    or type(previous["source_sha256"]) is not str
                    or previous["accepted"] is not False
                    or previous["truth_claimed"] is not False
                ):
                    raise EnvPathImportError(
                        "malformed prior EnvPath import payload"
                    )

                prior = previous["operational_authorization"]

                if type(prior) is not dict:
                    raise EnvPathImportError(
                        "malformed prior EnvPath import authorization"
                    )

                try:
                    validate_operational_authorization(
                        prior,
                        expected_action=ACTION_ENVPATH_NOTE_IMPORT,
                        expected_target_sha256=previous["draft_hash"],
                    )
                except (
                    OperationalAuthorizationError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    raise EnvPathImportError(
                        "invalid prior EnvPath import authorization"
                    ) from exc

                if (
                    prior["authorization_id"] == authorization["authorization_id"]
                    or prior["authorization_hash"] == authorization["authorization_hash"]
                ):
                    raise EnvPathImportError("authorization already consumed")

            precondition_completed = True

        try:
            entry = chain.append(
                payload,
                compress=False,
                precondition=require_current_and_unconsumed,
            )
        except Exception as exc:
            if precondition_completed:
                return {
                    "status": "OUTCOME_UNKNOWN",
                    "commit_performed": None,
                    "accepted": False,
                    "truth_claimed": False,
                    "write_authority": "NONE",
                    "execution_authority": "NONE",
                    "reason": str(exc),
                }
            raise

        try:
            verified = HoloChain(chain_path).load_and_verify()
            if (
                type(entry.get("idx")) is not int
                or entry["idx"] < 1
                or entry["idx"] > len(verified)
                or verified[entry["idx"] - 1]["hash"] != entry["hash"]
            ):
                raise EnvPathImportError("post-commit verification failed")

            persisted_entry = verified[entry["idx"] - 1]

            if persisted_entry.get("type") != "plain":
                raise EnvPathImportError("unexpected persisted entry type")

            persisted_payload = json.loads(persisted_entry["content"])

            if (
                type(persisted_payload) is not dict
                or persisted_payload != payload
            ):
                raise EnvPathImportError(
                    "post-commit payload does not match authorized proposal"
                )
        except Exception as exc:
            return {
                "status": "COMMITTED_UNVERIFIED",
                "commit_performed": True,
                "entry": entry,
                "accepted": False,
                "truth_claimed": False,
                "write_authority": "NONE",
                "execution_authority": "NONE",
                "reason": str(exc),
            }

        return {
            "status": "COMMITTED",
            "commit_performed": True,
            "entry": entry,
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
        }

    except (
        EnvPathImportError,
        OperationalAuthorizationError,
        TypeError,
        ValueError,
        KeyError,
        OSError,
        UnicodeError,
        zlib.error,
    ) as exc:
        return _blocked(str(exc))
