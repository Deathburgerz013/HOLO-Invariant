"""Portable, verified, zero-authority cold-start re-entry bundles."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash
from holosim.verified_cold_start_reentry_gateway import (
    VerifiedColdStartReentryError,
    validate_verified_cold_start_reentry_packet,
)

BUNDLE_TYPE = "portable_verified_reentry_bundle"
BUNDLE_VERSION = 1

BUNDLE_FIELDS = {
    "type",
    "version",
    "bundle_id",
    "packet",
    "packet_hash",
    "source_items",
    "source_items_hash",
    "truth_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "bundle_hash",
}


class PortableVerifiedReentryError(ValueError):
    """Raised when a portable re-entry bundle fails closed."""


def _required_text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise PortableVerifiedReentryError(
            f"{field} must be a non-empty plain string"
        )
    return value


def _plain_source_items(
    source_items: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if type(source_items) not in {list, tuple}:
        raise PortableVerifiedReentryError(
            "source_items must be a list or tuple"
        )
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(source_items):
        if type(item) is not dict:
            raise PortableVerifiedReentryError(
                f"source_items[{index}] must be a plain dictionary"
            )
        try:
            stable_hash(item)
        except CanonicalValueError as exc:
            raise PortableVerifiedReentryError(
                f"source_items[{index}] is outside the canonical JSON contract"
            ) from exc
        normalized.append(deepcopy(item))
    return normalized


def build_portable_reentry_bundle(
    *,
    bundle_id: str,
    packet: Mapping[str, Any],
    source_items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind a verified re-entry packet to the evidence needed to regenerate it."""
    checked_bundle_id = _required_text(bundle_id, "bundle_id")
    if type(packet) is not dict:
        raise PortableVerifiedReentryError(
            "packet must be a plain dictionary"
        )
    checked_items = _plain_source_items(source_items)
    try:
        validate_verified_cold_start_reentry_packet(
            packet,
            source_items=checked_items,
        )
    except VerifiedColdStartReentryError as exc:
        raise PortableVerifiedReentryError(
            f"packet evidence is invalid: {exc}"
        ) from exc

    body = {
        "type": BUNDLE_TYPE,
        "version": BUNDLE_VERSION,
        "bundle_id": checked_bundle_id,
        "packet": deepcopy(packet),
        "packet_hash": packet["packet_hash"],
        "source_items": checked_items,
        "source_items_hash": stable_hash(checked_items),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "bundle_hash": stable_hash(body)}


def validate_portable_reentry_bundle(
    bundle: Mapping[str, Any],
) -> bool:
    """Regenerate the complete bundle and require exact equality."""
    if type(bundle) is not dict:
        raise PortableVerifiedReentryError(
            "bundle must be a plain dictionary"
        )
    if set(bundle) != BUNDLE_FIELDS:
        raise PortableVerifiedReentryError(
            "bundle fields do not match the versioned schema"
        )
    if (
        bundle.get("type") != BUNDLE_TYPE
        or bundle.get("version") != BUNDLE_VERSION
    ):
        raise PortableVerifiedReentryError(
            "bundle type or version is invalid"
        )
    if (
        bundle.get("truth_claimed") is not False
        or bundle.get("accepted") is not False
        or bundle.get("write_authority") != "NONE"
        or bundle.get("execution_authority") != "NONE"
    ):
        raise PortableVerifiedReentryError(
            "bundle cannot grant authority"
        )
    try:
        rebuilt = build_portable_reentry_bundle(
            bundle_id=bundle["bundle_id"],
            packet=bundle["packet"],
            source_items=bundle["source_items"],
        )
    except PortableVerifiedReentryError:
        raise
    except (KeyError, TypeError) as exc:
        raise PortableVerifiedReentryError(
            "bundle evidence is malformed"
        ) from exc
    if rebuilt != bundle:
        raise PortableVerifiedReentryError(
            "bundle does not match its packet and source evidence"
        )
    return True


def consume_portable_reentry_bundle(
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    """Return exact carried state only when the retained packet allows re-entry."""
    validate_portable_reentry_bundle(bundle)
    packet = bundle["packet"]
    if (
        packet["status"] != "READY_FOR_REENTRY"
        or packet["gate_decision"] != "ALLOW"
    ):
        raise PortableVerifiedReentryError(
            "packet is not ready for re-entry"
        )
    return {
        "status": "REENTRY_RECONSTRUCTED",
        "bundle_id": bundle["bundle_id"],
        "bundle_hash": bundle["bundle_hash"],
        "packet_id": packet["packet_id"],
        "packet_hash": packet["packet_hash"],
        "carried_item_ids": list(packet["carried_item_ids"]),
        "working_state": deepcopy(packet["reconstructed_state"]),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


def _load_bundle(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PortableVerifiedReentryError(
            f"could not load portable bundle: {exc}"
        ) from exc
    if type(value) is not dict:
        raise PortableVerifiedReentryError(
            "portable bundle JSON must contain an object"
        )
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Consume a portable verified cold-start re-entry bundle."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    consume_parser = subparsers.add_parser("consume")
    consume_parser.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)

    try:
        result = consume_portable_reentry_bundle(
            _load_bundle(args.bundle)
        )
    except PortableVerifiedReentryError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
