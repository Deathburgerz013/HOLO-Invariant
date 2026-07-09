"""High-level Holo/Sim operator orchestration layer.

This module provides one stable entry point for running common Holo/Sim
operations without duplicating logic from core, rebirth, boot, IDX, or
artifact parsing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from holosim.artifact_parser import ArtifactParser
    from holosim.boot_integration import boot_validation
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
    from holosim.core import HoloChain
    from holosim.idx_manager import get_idx_manager
    from holosim.rebirth_engine import run_rebirth
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.artifact_parser import ArtifactParser
    from holosim.boot_integration import boot_validation
    from holosim.config import ACTIVE_HASH, ANCHOR, DEFAULT_CHAIN_FILE, HOLOSIM_VERSION
    from holosim.core import HoloChain
    from holosim.idx_manager import get_idx_manager
    from holosim.rebirth_engine import run_rebirth


class HoloOperator:
    """Operator-facing orchestration wrapper for Holo/Sim."""

    def __init__(self, chain_path: str | Path = DEFAULT_CHAIN_FILE) -> None:
        self.chain_path = Path(chain_path)
        self.chain = HoloChain(str(self.chain_path))
        self.idx_manager = get_idx_manager(self.chain)
        self.artifact_parser = ArtifactParser()

    def identity(self) -> Dict[str, Any]:
        """Return current Holo/Sim identity and anchor metadata."""
        return {
            "system": "Holo/Sim",
            "version": HOLOSIM_VERSION,
            "anchor": ANCHOR,
            "active_hash": ACTIVE_HASH,
            "chain_file": str(self.chain_path),
        }

    def health(self) -> Dict[str, Any]:
        """Return verified chain health."""
        return self.chain.health()

    def state(self) -> List[Any]:
        """Return reconstructed chain state."""
        return self.chain.get_state()

    def latest(self) -> Optional[Dict[str, Any]]:
        """Return latest verified chain entry."""
        return self.chain.get_latest()

    def checkpoint(self) -> Dict[str, Any]:
        """Create a checkpoint summary without appending it."""
        return self.chain.create_checkpoint()

    def rebirth(self, event: str = "MANUAL_OVERRIDE") -> Dict[str, Any]:
        """Run rebirth through the configured rebirth engine."""
        return run_rebirth(event)

    def idx_config(self) -> Dict[str, Any]:
        """Return current IDX-derived core configuration."""
        return self.idx_manager.get_core_config()

    def audit(self, path: str | Path | None = None) -> Dict[str, Any]:
        """Run artifact/CAP audit."""
        return self.artifact_parser.audit_caps(path)

    def boot(self) -> HoloChain:
        """Run boot validation."""
        return boot_validation(self.chain_path)

    def summary(self) -> Dict[str, Any]:
        """Return compact operator summary for dashboards or CLI use."""
        health = self.health()
        latest = self.latest()
        idx_config = self.idx_config()

        return {
            "identity": self.identity(),
            "health": {
                "recommendation": health.get("recommendation"),
                "total_entries": health.get("total_entries"),
                "compression_ratio": health.get("compression_ratio"),
                "chain_age_days": health.get("chain_age_days"),
            },
            "idx": {
                "anchor": idx_config.get("anchor"),
                "active_hash": idx_config.get("active_hash"),
            },
            "latest": {
                "idx": latest.get("idx") if latest else None,
                "timestamp": latest.get("timestamp") if latest else None,
                "hash": latest.get("hash") if latest else None,
                "type": latest.get("type") if latest else None,
            },
        }


def get_operator(chain_path: str | Path = DEFAULT_CHAIN_FILE) -> HoloOperator:
    """Create a HoloOperator instance."""
    return HoloOperator(chain_path)


def main() -> None:
    operator = get_operator()
    print(operator.summary())


if __name__ == "__main__":
    main()