"""IDX manager for Holo/Sim.

Centralizes IDX parsing and exposes the core configuration used by the
continuity engine. A moving Spine must pass the frozen IDX gate before
rebirth or chain mutation can occur.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

try:
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        DEFAULT_CHAIN_FILE,
        HEARTBEAT_SECONDS,
    )
    from holosim.core import HoloChain
    from holosim.frozen_idx_gate import FrozenIDXGate
    from holosim.rebirth_engine import run_rebirth
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        DEFAULT_CHAIN_FILE,
        HEARTBEAT_SECONDS,
    )
    from holosim.core import HoloChain
    from holosim.frozen_idx_gate import FrozenIDXGate
    from holosim.rebirth_engine import run_rebirth


class IDXManager:
    """Manage IDX parsing and fail-closed admission into the engine."""

    def __init__(self, chain: Optional[HoloChain] = None) -> None:
        self.chain = chain or HoloChain(str(DEFAULT_CHAIN_FILE))
        self.idx_data: Dict[str, Any] = {}
        self.active_hash = ACTIVE_HASH

    def parse_spine(self, content: str) -> Dict[str, Any]:
        """Parse simple IDX/key-value Spine text without ambiguity."""
        data: Dict[str, Any] = {}

        for raw_line in content.strip().splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            parsed: tuple[str, str] | None = None

            if ":" in line and "@" in line:
                key, value = line.split(":", 1)
                parsed = (key.strip(), value.strip())
            elif "=" in line:
                key, value = line.split("=", 1)
                parsed = (key.strip(), value.strip())

            if parsed is None:
                continue

            key, value = parsed

            if key in data:
                raise ValueError(
                    f"Frozen IDX contains duplicate key {key}."
                )

            data[key] = value

        self.idx_data = data
        return data

    def load_idx_file(
        self,
        idx_path: str | Path = "idx_spine.txt",
    ) -> Dict[str, Any]:
        """Load an existing frozen IDX without fabricating missing state."""
        path = Path(idx_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Frozen IDX file does not exist: {path}"
            )

        content = path.read_text(encoding="utf-8")
        return self.parse_spine(content)

    def build_frozen_gate(self) -> FrozenIDXGate:
        """Build the immutable admission gate from the loaded IDX."""
        if not self.idx_data:
            raise ValueError("Frozen IDX has not been loaded.")

        header = self.idx_data.get("IDX:v")
        if not isinstance(header, str) or not header:
            raise ValueError("Frozen IDX header IDX:v is missing.")

        parts = [part.strip() for part in header.split(";")]
        try:
            version = int(parts[0])
        except (TypeError, ValueError) as exc:
            raise ValueError("Frozen IDX version is invalid.") from exc

        metadata: Dict[str, str] = {}
        for part in parts[1:]:
            if "=" not in part:
                raise ValueError("Frozen IDX header metadata is invalid.")
            key, value = part.split("=", 1)
            metadata[key.strip()] = value.strip()

        try:
            slot_count = int(metadata["n"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Frozen IDX slot count n is invalid.") from exc

        if slot_count < 1:
            raise ValueError("Frozen IDX must declare at least one slot.")

        expected_keys = [
            f"S{index}" for index in range(1, slot_count + 1)
        ]

        for key in expected_keys:
            if key not in self.idx_data:
                raise ValueError(f"Frozen IDX slot {key} is missing.")

        observed_keys = [
            key
            for key in self.idx_data
            if re.fullmatch(r"S\d+", key)
        ]
        unexpected_keys = [
            key for key in observed_keys if key not in expected_keys
        ]
        if unexpected_keys:
            raise ValueError(
                f"Frozen IDX contains unexpected slot {unexpected_keys[0]}."
            )

        slots: list[tuple[str, str]] = []
        for key in expected_keys:
            binding = self.idx_data[key]
            if not isinstance(binding, str):
                raise ValueError(
                    f"Frozen IDX slot {key} must use CLASS@HASH."
                )

            class_name, separator, content_hash = binding.partition("@")
            if not separator or not class_name or not content_hash:
                raise ValueError(
                    f"Frozen IDX slot {key} must use CLASS@HASH."
                )

            slots.append((class_name, content_hash))

        active_hash = self.idx_data.get("ACTIVE_HASH")
        if not isinstance(active_hash, str) or not active_hash:
            raise ValueError("Frozen IDX ACTIVE_HASH is missing.")

        return FrozenIDXGate(
            version=version,
            active_hash=active_hash,
            slots=tuple(slots),
        )
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
                "triggers": [
                    "MANUAL_OVERRIDE",
                    "HARD_RESET",
                    "FAULT_HEARTBEAT",
                ],
            },
            "active_hash": self.active_hash,
            "idx_data": self.idx_data,
        }

    def apply_to_engine(
        self,
        *,
        spine_version: int,
        spine_active_hash: str,
        slots: Sequence[tuple[str, str]],
    ) -> Dict[str, Any]:
        """Apply state only after the moving Spine matches the frozen IDX."""
        gate = self.build_frozen_gate()
        admission = gate.check(
            version=spine_version,
            active_hash=spine_active_hash,
            slots=slots,
        )

        admission_record = {
            "status": admission.status,
            "code": admission.code,
            "fused": admission.fused,
            "slot": admission.slot,
            "expected": admission.expected,
            "observed": admission.observed,
        }

        if admission.status != "PASS":
            return {
                "status": "abort",
                "code": admission.code,
                "fused": False,
                "admission": admission_record,
            }

        self.active_hash = gate.active_hash
        config = self.get_core_config()
        rebirth_result = run_rebirth("MANUAL_OVERRIDE")

        if rebirth_result.get("status") != "ok":
            return {
                "status": "abort",
                "code": "REBIRTH_ABORTED",
                "fused": False,
                "admission": admission_record,
                "rebirth_result": rebirth_result,
            }

        record = {
            "type": "idx_applied",
            "config": config,
            "admission": admission_record,
            "rebirth_result": rebirth_result,
            "active_hash": self.active_hash,
            "ts": "now",
        }

        self.chain.append(record, compress=True)

        return {
            "status": "ok",
            "action": "idx_applied",
            "fused": bool(rebirth_result.get("fused", False)),
            "admission": admission_record,
            "rebirth_result": rebirth_result,
            "config": config,
        }


_idx: Optional[IDXManager] = None


def get_idx_manager(chain: Optional[HoloChain] = None) -> IDXManager:
    """Return the process-local IDX manager singleton."""
    global _idx

    if _idx is None:
        _idx = IDXManager(chain)

    return _idx