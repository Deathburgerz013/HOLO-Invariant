"""Bounded authentication for externally produced claim occurrences.

The mechanism is derived from the HMAC pulse gate in ProteusKernel-, with
authority separation and replay rejection added for HOLO/Sim.

Provenance:
    Admin135158/ProteusKernel-, gatekeeper.cpp, commit 3a9ce359311e1c5808cfc167ecb25807f053e1c2
    Copyright (c) 2026 Fernando De Jesus Garcia Gonzalez, MIT License.

Verification proves only that a registered shared secret authenticated the
canonical occurrence bytes. It does not prove truth, grant acceptance, or
authorize writes or execution.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Collection, Mapping
from copy import deepcopy
from typing import Any

from holosim.canonical import CanonicalValueError, canonical_bytes, stable_hash


OCCURRENCE_TYPE = "signed_claim_occurrence"
OCCURRENCE_VERSION = 1
MIN_SECRET_BYTES = 32
OCCURRENCE_FIELDS = {
    "type",
    "version",
    "source_id",
    "occurrence_id",
    "payload",
    "payload_sha256",
    "observed_at",
    "sequence",
    "nonce",
    "algorithm",
    "signature",
}
VALID_REJECTION_STATUSES = {
    "REJECTED_UNKNOWN_SOURCE",
    "REJECTED_REPLAY",
    "REJECTED_TAMPERED",
}


class SignedOccurrenceError(ValueError):
    """Raised when an occurrence is outside the bounded schema."""


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SignedOccurrenceError(f"{field} must be a non-empty string")
    return value


def _secret_bytes(value: Any) -> bytes:
    if not isinstance(value, bytes) or len(value) < MIN_SECRET_BYTES:
        raise SignedOccurrenceError(
            f"secret must be bytes containing at least {MIN_SECRET_BYTES} bytes"
        )
    return value


def _canonical_hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise SignedOccurrenceError(str(exc)) from exc


def _signing_body(occurrence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(occurrence[key])
        for key in sorted(OCCURRENCE_FIELDS - {"signature"})
    }


def _signature(body: Mapping[str, Any], secret: bytes) -> str:
    try:
        encoded = canonical_bytes(dict(body))
    except CanonicalValueError as exc:
        raise SignedOccurrenceError(str(exc)) from exc
    return hmac.new(secret, encoded, hashlib.sha256).hexdigest()


def _validate_structure(occurrence: Mapping[str, Any]) -> None:
    if not isinstance(occurrence, Mapping):
        raise SignedOccurrenceError("occurrence must be an object")
    if set(occurrence) != OCCURRENCE_FIELDS:
        raise SignedOccurrenceError(
            "occurrence fields do not match the versioned schema"
        )
    if occurrence["type"] != OCCURRENCE_TYPE:
        raise SignedOccurrenceError("occurrence type is invalid")
    if occurrence["version"] != OCCURRENCE_VERSION:
        raise SignedOccurrenceError("occurrence version is invalid")
    _required_text(occurrence["source_id"], "source_id")
    _required_text(occurrence["occurrence_id"], "occurrence_id")
    _required_text(occurrence["observed_at"], "observed_at")
    _required_text(occurrence["nonce"], "nonce")
    if (
        isinstance(occurrence["sequence"], bool)
        or not isinstance(occurrence["sequence"], int)
        or occurrence["sequence"] < 0
    ):
        raise SignedOccurrenceError("sequence must be a non-negative integer")
    if occurrence["algorithm"] != "hmac-sha256":
        raise SignedOccurrenceError("algorithm is invalid")
    if not isinstance(occurrence["signature"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", occurrence["signature"]
    ):
        raise SignedOccurrenceError("signature is invalid")
    if occurrence["payload_sha256"] != _canonical_hash(occurrence["payload"]):
        return


def build_signed_occurrence(
    *,
    source_id: str,
    occurrence_id: str,
    payload: Any,
    observed_at: str,
    sequence: int,
    nonce: str,
    secret: bytes,
) -> dict[str, Any]:
    """Build and sign one canonical occurrence without exporting the secret."""
    source = _required_text(source_id, "source_id")
    identity = _required_text(occurrence_id, "occurrence_id")
    observed = _required_text(observed_at, "observed_at")
    nonce_value = _required_text(nonce, "nonce")
    key = _secret_bytes(secret)
    payload_hash = _canonical_hash(payload)
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise SignedOccurrenceError("sequence must be a non-negative integer")
    body = {
        "type": OCCURRENCE_TYPE,
        "version": OCCURRENCE_VERSION,
        "source_id": source,
        "occurrence_id": identity,
        "payload": deepcopy(payload),
        "payload_sha256": payload_hash,
        "observed_at": observed,
        "sequence": sequence,
        "nonce": nonce_value,
        "algorithm": "hmac-sha256",
    }
    return {**body, "signature": _signature(body, key)}


def verify_signed_occurrence(
    *,
    occurrence: Mapping[str, Any],
    source_secrets: Mapping[str, bytes],
    seen_occurrence_ids: Collection[str],
) -> dict[str, Any]:
    """Verify origin and freshness while granting no downstream authority."""
    _validate_structure(occurrence)
    source_id = occurrence["source_id"]
    occurrence_id = occurrence["occurrence_id"]

    if source_id not in source_secrets:
        status = "REJECTED_UNKNOWN_SOURCE"
        verified = False
    elif occurrence_id in seen_occurrence_ids:
        status = "REJECTED_REPLAY"
        verified = False
    else:
        key = _secret_bytes(source_secrets[source_id])
        payload_matches = occurrence["payload_sha256"] == _canonical_hash(
            occurrence["payload"]
        )
        expected = _signature(_signing_body(occurrence), key)
        signature_matches = hmac.compare_digest(
            occurrence["signature"], expected
        )
        verified = payload_matches and signature_matches
        status = "VERIFIED" if verified else "REJECTED_TAMPERED"

    body = {
        "type": "signed_occurrence_verification",
        "version": 1,
        "source_id": source_id,
        "occurrence_id": occurrence_id,
        "occurrence_sha256": _canonical_hash(dict(occurrence)),
        "status": status,
        "verified": verified,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "verification_hash": _canonical_hash(body)}
