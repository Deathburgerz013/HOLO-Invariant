"""
HoloSim — Minimal tamper-evident append-only continuity engine.
Invariant core v0.1.0
"""

from .core import HoloChain
from .operator import UnifiedOperator

__version__ = "0.1.0"
__all__ = ["HoloChain", "UnifiedOperator"]