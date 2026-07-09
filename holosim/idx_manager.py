"""IDX manager for Holo/Sim.

Centralizes IDX parsing and exposes the core configuration used by the
continuity engine. This file now reads anchor/hash/path values from
holosim.config instead of carrying duplicate hardcoded state.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from holosim.core import HoloChain
    from holosim.rebirth_engine import run_rebirth
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        DEFAULT_CHAIN_FILE,
        HEARTBEAT_SECONDS,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.core import HoloChain
    from holosim.rebirth_engine import run_rebirth
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        DEFAULT_CHAIN_FILE,
        HEARTBEAT_SECONDS,
    )


class IDXManager:
    """Manage IDX spine parsing and configuration handoff."""

    def __init__(self, chain: Optional[HoloChain] = None) -> None:
        self.chain = chain or HoloChain(str(DEFAULT_CHAIN_FILE))
        self.idx_data: Dict[str, Any] = {}
        self.active_hash = ACTIVE_HASH

    def parse_spine(self, content: str) -> Dict[str, Any]:
        """Parse simple IDX/key-value spine text into a dictionary."""
        data: Dict[str, Any] = {}

        for raw_line in content.strip().splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            if ":" in line and "@" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
                continue

        self.idx_data = data
        return data

    def load_idx_file(self, idx_path: str | Path = "idx_spine.txt") -> Dict[str, Any]:
        """Load and parse an IDX spine file if present."""
        path = Path(idx_path)

        if not path.exists():
            self.idx_data = {}
            return {}

        content = path.read_text(encoding="utf-8")
        return self.parse_spine(content)

    def get_core_config(self) -> Dict[str, Any]:
        """Return the current core IDX configuration."""
        return {
            "anchor": ANCHOR,
            "persona": {
                "name": "Canyon_Brock_Haney",
                "prefs": "one_answer,short_when_stressed,no_auto_name",
                "demo": "SFW",
            },
            "paths": {
                "states": str(DEFAULT_CHAIN_FILE.parent),
                "chain_file": str(DEFAULT_CHAIN_FILE),
                "logs": "holo/logs",
            },
            "proto": {
                "token_mode": "local",
                "limit": 32000,
            },
            "persist": {
                "cp_min_delta": 256,
                "cp_min_secs": 45,
                "ring": 5,
                "heartbeat_seconds": HEARTBEAT_SECONDS,
            },
            "research": [
                "MEDICAL_IMAGING",
                "HOLOGRAPHY",
            ],
            "rebirth": {
                "active": True,
                "triggers": ["MANUAL_OVERRIDE", "HARD_RESET", "FAULT_HEARTBEAT"],
            },
            "active_hash": self.active_hash,
            "idx_data": self.idx_data,
        }

    def apply_to_engine(self) -> Dict[str, Any]:
        """Append IDX config to the chain and trigger a valid rebirth event."""
        config = self.get_core_config()

        result = run_rebirth("MANUAL_OVERRIDE")

        self.chain.append(
            {
                "type": "idx_applied",
                "config": config,
                "rebirth_result": result,
                "active_hash": self.active_hash,
                "ts": "now",
            },
            compress=True,
        )

        return config


_idx: Optional[IDXManager] = None


def get_idx_manager(chain: Optional[HoloChain] = None) -> IDXManager:
    """Return the process-local IDX manager singleton."""
    global _idx

    if _idx is None:
        _idx = IDXManager(chain)

    return _idx