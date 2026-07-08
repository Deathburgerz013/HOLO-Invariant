from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from holosim.core import HoloChain
from holosim.rebirth_engine import run_rebirth

class IDXManager:
    def __init__(self, chain: Optional[HoloChain] = None):
        self.chain = chain or HoloChain("holo_memory.jsonl")
        self.idx_data: Dict[str, Any] = {}
        self.active_hash = "v0807a-2b43f9d1"
  
    def parse_spine(self, content: str) -> Dict[str, Any]:
        data = {}
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' in line and '@' in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip()
            elif '=' in line:
                k, v = line.split('=', 1)
                data[k.strip()] = v.strip()
        self.idx_data = data
        return data
  
    def get_core_config(self) -> Dict[str, Any]:
        return {
            "anchor": "Canyon Brock Haney",
            "persona": {"name": "Canyon_Brock_Haney", "prefs": "one_answer,short_when_stressed,no_auto_name", "demo": "SFW"},
            "paths": {"states": "holo/states", "logs": "holo/logs"},
            "proto": {"token_mode": "local", "limit": 32000},
            "persist": {"cp_min_delta": 256, "cp_min_secs": 45, "ring": 5},
            "research": ["MEDICAL_IMAGING", "HOLOGRAPHY"],
            "rebirth": {"active": True, "triggers": ["MANUAL_OVERRIDE"]},
            "active_hash": self.active_hash
        }
  
    def apply_to_engine(self):
        config = self.get_core_config()
        run_rebirth("IDX_APPLY")
        self.chain.append({"idx_applied": config, "ts": "now"}, compress=True)
        return config

_idx: Optional[IDXManager] = None
def get_idx_manager(chain=None):
    global _idx
    if _idx is None:
        _idx = IDXManager(chain)
    return _idx