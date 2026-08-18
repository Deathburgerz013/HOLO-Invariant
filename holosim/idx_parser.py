"""Fail-closed loader for a frozen Holo/Sim IDX."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_idx_spine(
    file_path: str = "D:/death/documents/holo/states/IDX_SPINAL_v1.json",
) -> Dict[str, Any]:
    """Load an existing frozen IDX without creating or modifying it."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Frozen IDX file does not exist: {path}"
        )

    raw = path.read_text(encoding="utf-8")
    loaded = json.loads(raw)

    if not isinstance(loaded, dict):
        raise ValueError("Frozen IDX root must be a JSON object.")

    return loaded