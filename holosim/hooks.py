"""Generalization hooks for Holo/Sim.

Hooks normalize different input types into a common payload shape before they
enter API, Collector, Runtime, or future adapters.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict


def stable_hash(value: Any) -> str:
    """Create a stable short hash for arbitrary JSON-like data."""
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def normalize_text(
    text: str,
    *,
    source: str = "text",
    thread_id: str | None = None,
    tags: list[str] | None = None,
) -> Dict[str, Any]:
    """Normalize plain text into a standard Holo payload."""
    content = text.strip()

    payload = {
        "type": "normalized_text",
        "source": source,
        "thread_id": thread_id,
        "tags": tags or [],
        "content": content,
        "chars": len(content),
        "timestamp": int(time.time()),
    }

    payload["id"] = stable_hash(payload)
    return payload


def normalize_file(
    path: str | Path,
    *,
    source: str = "file",
    thread_id: str | None = None,
    tags: list[str] | None = None,
) -> Dict[str, Any]:
    """Normalize a local text-like file into a standard Holo payload."""
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8", errors="ignore")

    payload = normalize_text(
        content,
        source=source,
        thread_id=thread_id,
        tags=tags or ["file", file_path.suffix.lower()],
    )

    payload["type"] = "normalized_file"
    payload["file"] = {
        "path": str(file_path),
        "name": file_path.name,
        "suffix": file_path.suffix.lower(),
    }
    payload["id"] = stable_hash(payload)
    return payload


def normalize_event(
    event: Dict[str, Any],
    *,
    source: str = "event",
    thread_id: str | None = None,
    tags: list[str] | None = None,
) -> Dict[str, Any]:
    """Normalize arbitrary event dictionaries into standard Holo payloads."""
    payload = {
        "type": "normalized_event",
        "source": source,
        "thread_id": thread_id,
        "tags": tags or [],
        "event": event,
        "timestamp": int(time.time()),
    }

    payload["id"] = stable_hash(payload)
    return payload


def to_collectable(payload: Dict[str, Any]) -> str:
    """Serialize normalized payload for Collector intake."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)