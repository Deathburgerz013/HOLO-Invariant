# Holo/Sim package init for HSSCE continuity engine 
from .core import HoloChain 
from .artifact_parser import main as run_artifact_parser, Artifact, extract_crystal 
 
__version__ = "0.4.8" 
__all__ = ["HoloChain", "run_artifact_parser", "Artifact", "extract_crystal"] 
from .cli import main as cli_main