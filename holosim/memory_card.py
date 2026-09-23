"""Portable, hash-bound memory cards for cross-boundary state verification."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


MEMORY_CARD_TYPE = "holo_memory_card"
MEMORY_CARD_VERSION = 1

_MEMORY_CARD_FIELDS = {
    "type",
    "version",
    "card_id",
    "observation",
    "observation_hash",
    "source",
    "observed_at",
    "status",
    "corrections",
    "reobservations",
    "accepted",
    "write_authority",
    "execution_authority",
    "card_hash",
}


class MemoryCardError(ValueError):
    """Raised when a memory card violates its contract."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MemoryCardError(
            "value is not canonically serializable"
        ) from exc


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_card(card: Mapping[str, Any]) -> dict[str, Any]:
    if type(card) is not dict:
        raise MemoryCardError(
            "memory card must be a plain dictionary"
        )

    if set(card) != _MEMORY_CARD_FIELDS:
        raise MemoryCardError(
            "memory card fields do not match the expected schema"
        )

    if card["type"] != MEMORY_CARD_TYPE:
        raise MemoryCardError("invalid memory card type")

    if card["version"] != MEMORY_CARD_VERSION:
        raise MemoryCardError("unsupported memory card version")

    if (
        type(card["card_id"]) is not str
        or not card["card_id"].strip()
    ):
        raise MemoryCardError(
            "card_id must be a nonempty string"
        )

    if (
        type(card["observation_hash"]) is not str
        or len(card["observation_hash"]) != 64
    ):
        raise MemoryCardError(
            "observation_hash must be a SHA-256 hex digest"
        )

    if type(card["source"]) is not dict:
        raise MemoryCardError(
            "source must be a plain dictionary"
        )

    if (
        type(card["observed_at"]) is not str
        or not card["observed_at"].strip()
    ):
        raise MemoryCardError(
            "observed_at must be a nonempty string"
        )

    if (
        type(card["status"]) is not str
        or not card["status"].strip()
    ):
        raise MemoryCardError(
            "status must be a nonempty string"
        )

    if type(card["corrections"]) is not list:
        raise MemoryCardError(
            "corrections must be a list"
        )

    if type(card["reobservations"]) is not list:
        raise MemoryCardError(
            "reobservations must be a list"
        )

    if card["accepted"] is not False:
        raise MemoryCardError(
            "memory cards cannot be accepted"
        )

    if card["write_authority"] != "NONE":
        raise MemoryCardError(
            "memory cards cannot grant write authority"
        )

    if card["execution_authority"] != "NONE":
        raise MemoryCardError(
            "memory cards cannot grant execution authority"
        )

    if _hash(card["observation"]) != card["observation_hash"]:
        raise MemoryCardError(
            "observation hash does not match observation"
        )

    body = {
        key: card[key]
        for key in _MEMORY_CARD_FIELDS
        if key != "card_hash"
    }

    if (
        type(card["card_hash"]) is not str
        or len(card["card_hash"]) != 64
    ):
        raise MemoryCardError(
            "card_hash must be a SHA-256 hex digest"
        )

    if _hash(body) != card["card_hash"]:
        raise MemoryCardError(
            "card hash does not match card contents"
        )

    return deepcopy(card)


def build_memory_card(
    *,
    card_id: str,
    observation: Mapping[str, Any],
    source: Mapping[str, Any],
    observed_at: str | None = None,
    status: str = "OBSERVED",
    corrections: list[Mapping[str, Any]] | None = None,
    reobservations: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, authority-free memory card."""

    if type(observation) is not dict:
        raise MemoryCardError(
            "observation must be a plain dictionary"
        )

    if type(source) is not dict:
        raise MemoryCardError(
            "source must be a plain dictionary"
        )

    body = {
        "type": MEMORY_CARD_TYPE,
        "version": MEMORY_CARD_VERSION,
        "card_id": card_id,
        "observation": deepcopy(observation),
        "observation_hash": _hash(observation),
        "source": deepcopy(source),
        "observed_at": observed_at or _utc_now(),
        "status": status,
        "corrections": deepcopy(corrections or []),
        "reobservations": deepcopy(reobservations or []),
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }

    card = {
        **body,
        "card_hash": _hash(body),
    }

    return _validate_card(card)


def verify_memory_card(card: Mapping[str, Any]) -> bool:
    """Verify a memory card without modifying it."""

    _validate_card(card)
    return True


def _read_memory_card_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MemoryCardError(
            f"unable to read memory card: {path}"
        ) from exc

    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise MemoryCardError(
            f"memory card is not valid JSON: {path}"
        ) from exc

    if type(value) is not dict:
        raise MemoryCardError(
            "stored memory card must be a plain dictionary"
        )

    return value


def save_memory_card(
    path: str | Path,
    card: Mapping[str, Any],
) -> dict[str, Any]:
    """Save a verified memory card to a storage slot.

    The card is validated before persistence. The serialized bytes are
    written to a temporary file, flushed and fsynced, then atomically
    replaced into the destination slot.
    """

    validated = _validate_card(card)
    target = Path(path)

    if target.exists() and not target.is_file():
        raise MemoryCardError(
            "memory card path must be a file"
        )

    target.parent.mkdir(parents=True, exist_ok=True)

    encoded = (
        json.dumps(
            validated,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")

    temporary = target.with_name(
        f".{target.name}.tmp-{os.getpid()}"
    )

    try:
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, target)

    except Exception as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

        raise MemoryCardError(
            f"unable to save memory card: {target}"
        ) from exc

    loaded = load_memory_card(target)

    if loaded != validated:
        raise MemoryCardError(
            "saved memory card does not reconstruct identically"
        )

    return deepcopy(validated)


def load_memory_card(
    path: str | Path,
) -> dict[str, Any]:
    """Load and verify a memory card.

    Loading reconstructs the recorded card. It does not establish that
    the recorded observation remains current or correct.
    """

    target = Path(path)

    if not target.exists():
        raise MemoryCardError(
            "memory card does not exist"
        )

    if not target.is_file():
        raise MemoryCardError(
            "memory card path must be a file"
        )

    card = _read_memory_card_json(target)

    _validate_card(card)

    return card


def copy_memory_card(
    source: str | Path,
    target: str | Path,
) -> dict[str, Any]:
    """Copy a memory card while preserving its identity and contents."""

    source_path = Path(source)
    target_path = Path(target)

    if source_path.absolute() == target_path.absolute():
        raise MemoryCardError(
            "copy source and target must be different"
        )

    card = load_memory_card(source_path)

    return save_memory_card(target_path, card)


def delete_memory_card(
    path: str | Path,
) -> None:
    """Delete a memory-card storage slot."""

    target = Path(path)

    if not target.exists():
        raise MemoryCardError(
            "memory card does not exist"
        )

    if not target.is_file():
        raise MemoryCardError(
            "memory card path must be a file"
        )

    try:
        target.unlink()
    except OSError as exc:
        raise MemoryCardError(
            f"unable to delete memory card: {target}"
        ) from exc


def overwrite_memory_card(
    path: str | Path,
    card: Mapping[str, Any],
) -> dict[str, Any]:
    """Explicitly replace the contents of an existing card slot.

    This changes the active storage slot. It does not mutate the supplied
    card and does not rewrite the historical identity contained in that
    card.
    """

    target = Path(path)

    if target.exists() and not target.is_file():
        raise MemoryCardError(
            "memory card path must be a file"
        )

    return save_memory_card(target, card)
