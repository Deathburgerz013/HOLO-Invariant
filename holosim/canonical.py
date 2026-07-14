"""Strict canonical identity primitives for HOLO/Sim.

This module defines a versioned, deterministic Python JSON identity contract.
It does not add timestamps, provenance, acceptance, or write authority. Callers
must supply every field that belongs to the identity being hashed.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


CANONICAL_TYPE = "holo_canonical_json"
CANONICAL_VERSION = 1
HASH_ALGORITHM = "sha256"


class CanonicalValueError(ValueError):
    """Raised when a value is outside the canonical JSON contract."""


def _validate_json_value(value: Any, *, path: str = "$") -> None:
    """Reject values that require implicit or platform-specific conversion."""
    if value is None or isinstance(value, (str, bool, int)):
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalValueError(
                f"{path} contains a non-finite float"
            )
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalValueError(
                    f"{path} contains a non-string object key"
                )
            _validate_json_value(item, path=f"{path}.{key}")
        return

    raise CanonicalValueError(
        f"{path} contains unsupported type {type(value).__name__}"
    )


def canonical_json(value: Any) -> str:
    """Serialize a strict JSON value deterministically.

    The contract deliberately rejects ``default=str`` conversion, tuples,
    sets, bytes, paths, datetime objects, non-string keys, NaN, and infinity.
    """
    _validate_json_value(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_bytes(value: Any) -> bytes:
    """Return UTF-8 bytes for the canonical JSON representation."""
    return canonical_json(value).encode("utf-8")


def stable_hash(value: Any) -> str:
    """Return the full lowercase SHA-256 identity of a strict JSON value."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def identity_packet(value: Any) -> dict[str, Any]:
    """Return a self-describing canonical identity packet."""
    rendered = canonical_json(value)
    encoded = rendered.encode("utf-8")
    return {
        "type": CANONICAL_TYPE,
        "version": CANONICAL_VERSION,
        "algorithm": HASH_ALGORITHM,
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "canonical_size_bytes": len(encoded),
        "write_authority": "NONE",
    }