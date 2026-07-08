"""Central configuration for Holo/Sim.

For one source of truth. 
"""

from __future__ import annotations

from pathlib import Path

HOLOSIM_VERSION = "0.4.9"

ANCHOR = "Canyon Brock Haney"
ANCHOR_ID = "CANYON_OVERRIDE"
ACTIVE_HASH = "v0807a-2b43f9d1"
HEARTBEAT_SECONDS = 600

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CHAIN_FILE = REPO_ROOT / "holo_memory.jsonl"

MASTER_INDEX_FILE = REPO_ROOT / "Master_Index_Auto.md"

REQUIRED_COMPONENTS = {
    "IDX Manager": REPO_ROOT / "holosim" / "idx_manager.py",
    "Rebirth Engine": REPO_ROOT / "holosim" / "rebirth_engine.py",
    "Artifact Parser": REPO_ROOT / "holosim" / "artifact_parser.py",
    "Boot Integration": REPO_ROOT / "holosim" / "boot_integration.py",
    "Core": REPO_ROOT / "holosim" / "core.py",
    "CLI": REPO_ROOT / "holosim" / "holo_cli.py",
}