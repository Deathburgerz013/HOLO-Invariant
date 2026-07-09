#!/usr/bin/env python3
"""Compatibility entrypoint for Holo/Sim CLI.

The canonical CLI implementation lives in holosim.holo_cli.
This wrapper exists so older commands that call holosim.cli still work.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from holosim.holo_cli import main
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.holo_cli import main


if __name__ == "__main__":
    main()