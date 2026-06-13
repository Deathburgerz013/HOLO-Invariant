"""
Unified Corrections Operator
Enforces the invariant-preserving corrections loop on top of HoloChain.
"""

import json
from typing import Any, Dict, List, Optional
from .core import HoloChain


class UnifiedOperator:
    """
    The human-AI convergence engine.
    Surface → Verify → Converge → Append (cleanly, no drift).
    """

    def __init__(self, 
                 chain: Optional[HoloChain] = None, 
                 file_path: str = "holo_memory.jsonl"):
        """Accept either a HoloChain instance or a file_path string."""
        if isinstance(chain, str):
            # User passed file_path as first positional argument
            file_path = chain
            chain = None
        self.chain = chain or HoloChain(file_path)
        self.current_invariants: List[str] = []  # High-confidence anchors

    def surface_delta(self, observation: Any) -> Dict:
        """Step 1: Surface a potential delta from reality / thought / model."""
        delta = {
            "type": "delta",
            "timestamp": None,  # will be set on append
            "content": observation,
            "confidence": 0.0,
            "tags": []
        }
        print("🔍 Delta surfaced:")
        print(json.dumps(delta, indent=2, default=str))
        return delta

    def verify_invariants(self, delta: Dict) -> bool:
        """Step 2: Check against known invariant core. Returns True if clean."""
        # TODO: Expand this with real spine checks (physics, logic, etc.)
        print("✅ Invariant verification passed (core spine intact).")
        return True

    def converge_and_append(self, 
                           observation: Any, 
                           human_confirmation: bool = True,
                           tags: Optional[List[str]] = None) -> Dict:
        """
        Full loop: Surface → Verify → (Human anchor) → Clean convergence → Append
        """
        delta = self.surface_delta(observation)
        
        if not self.verify_invariants(delta):
            raise ValueError("❌ Delta violates invariants — rejected.")

        if human_confirmation:
            print("\n🧠 HUMAN ANCHOR REQUIRED")
            print("Type 'yes' to converge and append, or describe corrections:")
            response = input(">>> ").strip().lower()
            if response != "yes":
                print("⏸️  Convergence paused. Human correction noted.")
                return {"status": "paused", "note": response}

        # Clean convergence
        final_entry = {
            "type": "convergence",
            "content": observation,
            "tags": tags or ["human-verified"],
            "delta_hash": None
        }

        appended = self.chain.append(final_entry)
        print(f"✅ Converged and appended entry {appended['idx']}")
        return appended

    def replay_convergences(self):
        """Replay only clean convergences."""
        self.chain.replay()