"""
HoloSim — Minimal tamper-evident append-only continuity engine.
Invariant core v0.2.0
"""

from .core import HoloChain
from .operator import UnifiedOperator

__version__ = "0.2.0"
__all__ = ["HoloChain", "UnifiedOperator"]