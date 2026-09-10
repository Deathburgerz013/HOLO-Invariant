"""Transport one situated packet to independent, caller-supplied observers.

The transport owns no vendor client and performs no persistence.  It presents
the exact same canonical packet bytes to every adapter and records each
returned JSON observation in a receipt bound to that packet identity.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from holosim.canonical import CanonicalValueError, canonical_bytes, stable_hash
from holosim.situated_reconstruction_packet import (
    SituatedReconstructionPacketError,
    verify_situated_reconstruction_packet,
)


RECEIPT_TYPE = "provider_neutral_observer_receipt"
RECEIPT_VERSION = 1

ObserverAdapter = Callable[[bytes], Mapping[str, Any]]


class ProviderNeutralObserverTransportError(ValueError):
    """Raised when packet transport or an observer receipt is invalid."""


def _required_text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderNeutralObserverTransportError(
            f"{label} must be a non-empty string"
        )
    return value


def _closed_json(value: Any, *, label: str) -> Any:
    try:
        return json.loads(canonical_bytes(value))
    except (CanonicalValueError, TypeError, ValueError) as exc:
        raise ProviderNeutralObserverTransportError(
            f"{label} must contain only JSON values"
        ) from exc


def _hash(value: Any, *, label: str) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise ProviderNeutralObserverTransportError(
            f"{label} must contain only JSON values"
        ) from exc


def _packet_bytes(packet: Mapping[str, Any]) -> bytes:
    try:
        verify_situated_reconstruction_packet(packet)
        return canonical_bytes(dict(packet))
    except (SituatedReconstructionPacketError, CanonicalValueError) as exc:
        raise ProviderNeutralObserverTransportError(
            f"packet is invalid: {exc}"
        ) from exc


def transport_situated_reconstruction_packet(
    *,
    packet: Mapping[str, Any],
    observers: Sequence[tuple[str, ObserverAdapter]],
) -> list[dict[str, Any]]:
    """Present identical packet bytes and return one bounded receipt per observer."""
    if isinstance(observers, (str, bytes)) or not isinstance(observers, Sequence):
        raise ProviderNeutralObserverTransportError(
            "observers must be a sequence"
        )
    transmitted = _packet_bytes(packet)
    packet_hash = packet["packet_hash"]
    payload_sha256 = hashlib.sha256(transmitted).hexdigest()
    receipts: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, item in enumerate(observers):
        if not isinstance(item, tuple) or len(item) != 2:
            raise ProviderNeutralObserverTransportError(
                f"observers[{index}] must be an (observer_id, adapter) tuple"
            )
        observer_id = _required_text(item[0], label=f"observers[{index}].observer_id")
        adapter = item[1]
        if observer_id in seen:
            raise ProviderNeutralObserverTransportError(
                "observer ids must be unique"
            )
        if not callable(adapter):
            raise ProviderNeutralObserverTransportError(
                f"observers[{index}].adapter must be callable"
            )
        seen.add(observer_id)

        response = adapter(transmitted)
        if not isinstance(response, Mapping):
            raise ProviderNeutralObserverTransportError(
                f"observer {observer_id!r} response must be a mapping"
            )
        closed_response = _closed_json(dict(response), label="observer response")

        if _packet_bytes(packet) != transmitted:
            raise ProviderNeutralObserverTransportError(
                f"observer {observer_id!r} mutated the packet"
            )

        body = {
            "type": RECEIPT_TYPE,
            "version": RECEIPT_VERSION,
            "observer_id": observer_id,
            "packet_hash": packet_hash,
            "packet_payload_sha256": payload_sha256,
            "response": closed_response,
            "response_hash": _hash(closed_response, label="observer response"),
            "transport_status": "RESPONSE_OBSERVED",
            "accepted": False,
            "truth_claimed": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
            "canonical_mutation": False,
            "interpretation_notice": (
                "This receipt binds one supplied observer response to exact packet "
                "bytes. It does not prove provider identity, source independence, "
                "response truth, agreement, acceptance, or authority."
            ),
        }
        receipts.append({**body, "receipt_hash": _hash(body, label="receipt")})

    return receipts


def verify_provider_neutral_observer_receipt(
    receipt: Mapping[str, Any],
    *,
    packet: Mapping[str, Any],
) -> bool:
    """Verify one observer receipt against the exact situated packet."""
    if not isinstance(receipt, Mapping):
        raise ProviderNeutralObserverTransportError(
            "receipt must be a mapping"
        )
    closed = _closed_json(dict(receipt), label="receipt")
    required = {
        "type", "version", "observer_id", "packet_hash",
        "packet_payload_sha256", "response", "response_hash",
        "transport_status", "accepted", "truth_claimed",
        "write_authority", "execution_authority", "canonical_mutation",
        "interpretation_notice", "receipt_hash",
    }
    if set(closed) != required:
        raise ProviderNeutralObserverTransportError(
            "receipt fields are invalid"
        )
    supplied_hash = closed.pop("receipt_hash")
    if _hash(closed, label="receipt") != supplied_hash:
        raise ProviderNeutralObserverTransportError(
            "receipt hash mismatch"
        )
    if closed["type"] != RECEIPT_TYPE or closed["version"] != RECEIPT_VERSION:
        raise ProviderNeutralObserverTransportError(
            "receipt type or version mismatch"
        )
    _required_text(closed["observer_id"], label="observer_id")
    _required_text(closed["interpretation_notice"], label="interpretation_notice")
    transmitted = _packet_bytes(packet)
    if closed["packet_hash"] != packet["packet_hash"]:
        raise ProviderNeutralObserverTransportError(
            "receipt packet hash mismatch"
        )
    if closed["packet_payload_sha256"] != hashlib.sha256(transmitted).hexdigest():
        raise ProviderNeutralObserverTransportError(
            "receipt packet payload mismatch"
        )
    if closed["response_hash"] != _hash(closed["response"], label="response"):
        raise ProviderNeutralObserverTransportError(
            "receipt response hash mismatch"
        )
    bounded = {
        "transport_status": "RESPONSE_OBSERVED",
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "canonical_mutation": False,
    }
    for field, expected in bounded.items():
        if closed[field] != expected:
            raise ProviderNeutralObserverTransportError(
                f"invalid bounded field {field}"
            )
    return True
