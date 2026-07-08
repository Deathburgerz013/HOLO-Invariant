# Holo/Sim package init for HSSCE continuity engine
# █†█ HOLO_SUBSTRATE_STABILITY_V1 integrated - Canyon delta

from .core import HoloChain
from .artifact_parser import main as run_artifact_parser, Artifact, extract_crystal
from .cli import main as cli_main
from .rebirth_engine import run_rebirth
from .idx_manager import get_idx_manager

# Substrate stability guard (SUBSTRATE_PRIOR_V1)
from .substrate_prior_v1 import SubstrateGuard

__version__ = "0.4.9"
__all__ = [
    "HoloChain", 
    "run_artifact_parser", 
    "Artifact", 
    "extract_crystal", 
    "run_rebirth", 
    "get_idx_manager", 
    "cli_main",
    "SubstrateGuard"   # New: Exposed for continuity protection
]

# Initialize global guard instance for package-level use
_substrate_guard = SubstrateGuard()

def get_substrate_guard():
    """Return the shared substrate stability guard."""
    return _substrate_guard