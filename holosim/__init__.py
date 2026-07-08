# Holo/Sim package init for HSSCE continuity engine
from .core import HoloChain
from .artifact_parser import main as run_artifact_parser, Artifact, extract_crystal
from .cli import main as cli_main
from .rebirth_engine import run_rebirth
from .idx_manager import get_idx_manager

__version__ = "0.4.9"
__all__ = ["HoloChain", "run_artifact_parser", "Artifact", "extract_crystal", "run_rebirth", "get_idx_manager", "cli_main"]