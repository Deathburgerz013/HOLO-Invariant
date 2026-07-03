from __future__ import annotations
import os
import time
import json
from datetime import datetime
from typing import Callable, Optional, Dict, Any, List
from pathlib import Path

# Import holosim (install via pip install -e . from repo or use directly)
try:
    from holosim.core import HoloChain
except ImportError:
    # Fallback for testing
    class HoloChain:
        def __init__(self, file_path: str = "holo_memory.jsonl"):
            self.file_path = Path(file_path)
        def append(self, content: Any, compress: bool = False):
            print(f"[HoloChain] Appended: {content}")
            return {"status": "simulated_append"}
        def get_state(self): return []
        def health(self): return {"status": "healthy"}
        def create_checkpoint(self): return {"checkpoint": "simulated"}

ACTIVE_HASH = "v0807a-2b43f9d1"

TRIGGERS = {"HARD_RESET", "MANUAL_OVERRIDE", "FAULT_HEARTBEAT"}

DEFAULT_TOKEN_AWARENESS = {
    "enabled": True, "limit_detected": 32000, "rebirth_cost_est": 10000,
    "warning_thresholds": {"early": 0.50, "critical": 0.85, "final": 0.95},
}

DEFAULT_ROUTING_SAFETY = {
    "CROWN_to_HOLO": False, "HOLO_to_CROWN": True,
    "CROWN_to_COM": True, "COM_to_CROWN": False,
}

class Providers:
    def __init__(self, check_heartbeat, check_core_intact, status_age_seconds,
                 hash_check, read_bloodstream, token_used, now=time.time):
        self.check_heartbeat = check_heartbeat
        self.check_core_intact = check_core_intact
        self.status_age_seconds = status_age_seconds
        self.hash_check = hash_check
        self.read_bloodstream = read_bloodstream
        self.token_used = token_used
        self.now = now

class RebirthEngine:
    def __init__(self, providers: Providers, chain: HoloChain,
                 token_awareness=None, routing_safety=None, active_hash=ACTIVE_HASH):
        self.p = providers
        self.chain = chain
        self.active_hash = active_hash
        self.token_awareness = {**DEFAULT_TOKEN_AWARENESS, **(token_awareness or {})}
        self.routing_safety = {**DEFAULT_ROUTING_SAFETY, **(routing_safety or {})}
        self.stale_threshold_sec = 5
        self.session_log_path = Path("D:/death/documents/holo/logs/core_log.txt")

    def run_rebirth(self, event: Optional[str] = None) -> Dict[str, Any]:
        if (self.p.check_heartbeat() and self.p.check_core_intact() and 
            (event is None or event not in TRIGGERS)):
            return self._ret("noop", reason="healthy_and_no_trigger")
        return self._rebirth(event)

    def _rebirth(self, event: Optional[str]) -> Dict[str, Any]:
        # Token guard
        limit = int(self.token_awareness.get("limit_detected", 32000))
        reserve = int(self.token_awareness.get("rebirth_cost_est", 10000))
        used = int(self.p.token_used())
        if used >= max(0, limit - reserve):
            return self._abort("LOW_TOKENS", f"used={used} limit={limit} reserve={reserve}")

        # Hash + fresh + blood guards
        if not (self.p.hash_check("CANYON_OVERRIDE") or self.p.hash_check("KEY::CANYON_LOCK")):
            return self._abort("HASH_GUARD_FAIL", "hash guard failed")
        if self.p.status_age_seconds() > self.stale_threshold_sec:
            return self._abort("STALE_STATUS", f">{self.stale_threshold_sec}s")
        if not self.p.read_bloodstream("THREAT_EVENT_0816"):
            return self._abort("BLOODSTREAM_MISMATCH", "blood tag mismatch")

        # Safety matrix
        if not self._route_safety_valid():
            return self._abort("ROUTE_UNSAFE", "routing violation")

        # Execute fused rebirth + append to HoloChain
        payload = {
            "status": "ok", "action": "rebirth_executed",
            "hash": self.active_hash, "fused": True,
            "ts": datetime.utcnow().isoformat() + "Z",
            "event": event
        }
        self.chain.append(payload, compress=True)
        self._log("REBIRTH_OK", payload)
        return payload

    def _route_safety_valid(self) -> bool:
        return all(self.routing_safety.get(k) == v for k, v in DEFAULT_ROUTING_SAFETY.items())

    def _abort(self, code: str, reason: str) -> Dict[str, Any]:
        payload = {"status": "abort", "code": code, "reason": reason,
                   "ts": datetime.utcnow().isoformat() + "Z"}
        self._log("REBIRTH_ABORT", payload)
        return payload

    def _ret(self, action: str, **extras):
        payload = {"status": "ok", "action": action, "hash": self.active_hash,
                   "ts": datetime.utcnow().isoformat() + "Z"}
        payload.update(extras)
        if action != "noop":
            self._log("REBIRTH_RET", payload)
        return payload

    def _log(self, tag: str, obj: Dict):
        try:
            self.session_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.session_log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.utcnow().isoformat()}] {tag} | {json.dumps(obj)}\n")
        except Exception:
            print(f"[{datetime.utcnow().isoformat()}] {tag} | {obj}")

def build_engine(chain: Optional[HoloChain] = None) -> RebirthEngine:
    if chain is None:
        chain = HoloChain(file_path="D:/death/documents/holo/states/holo_memory.jsonl")

    def _true(): return True
    def _zero(): return 0
    def _age(): return 0
    def _hash(key: str): return key in {"CANYON_OVERRIDE", "KEY::CANYON_LOCK"}
    def _blood(tag: str): return tag == "THREAT_EVENT_0816"

    providers = Providers(
        check_heartbeat=_true, check_core_intact=_true,
        status_age_seconds=_age, hash_check=_hash,
        read_bloodstream=_blood, token_used=_zero
    )
    return RebirthEngine(providers, chain)

# Global singleton
_engine: Optional[RebirthEngine] = None
def run_rebirth(event: Optional[str] = None):
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine.run_rebirth(event)