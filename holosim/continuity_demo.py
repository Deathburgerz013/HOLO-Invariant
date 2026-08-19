"""Disposable evidence chain for the one-command continuity demo."""

from __future__ import annotations

import logging
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from holosim.core import HoloChain


DEMO_CHAIN_NAME = "continuity-demo.jsonl"


@contextmanager
def _quiet_demo_construction() -> Iterator[None]:
    """Suppress routine core INFO records only while building demo evidence."""
    logger = logging.getLogger("holosim.core")
    previous_level = logger.level
    if logger.isEnabledFor(logging.INFO):
        logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.setLevel(previous_level)


def build_continuity_demo(demo_dir: str | Path) -> Path:
    """Create a new demonstration chain without replacing existing evidence."""
    directory = Path(demo_dir)
    directory.mkdir(parents=True, exist_ok=True)
    chain_path = directory / DEMO_CHAIN_NAME
    if chain_path.exists():
        raise FileExistsError(f"Demo chain already exists: {chain_path}")

    with _quiet_demo_construction():
        chain = HoloChain(chain_path)
        original = chain.append(
            {
                "claim": "The retained observation is blue.",
                "source": "demonstration sensor A",
            }
        )
        chain.correct(
            original["idx"],
            {
                "claim": "The retained observation is cyan.",
                "source": "demonstration sensor A + calibrated sensor B",
            },
            "new calibrated evidence refines the observation",
        )
        chain.revalidate(
            original["idx"],
            "REVISED",
            "the original remains retained while the correction carries forward",
            "deterministic demonstration comparison",
        )
    return chain_path


def run_continuity_demo(
    demo_dir: str | Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> int:
    """Build disposable evidence and open its verified topology."""
    if demo_dir is None:
        demo_dir = Path(tempfile.mkdtemp(prefix="holo-continuity-demo-"))
    chain_path = build_continuity_demo(demo_dir)
    print(f"HOLO continuity demo evidence: {chain_path}")
    print("Disposable example only. No existing chain was modified.")

    # Resolve through the CLI module so tests and embedders can replace the
    # serving boundary without weakening the evidence-building contract.
    from holosim import holo_cli

    return holo_cli.serve_operator_console(
        chain_path,
        host=host,
        port=port,
        open_browser=open_browser,
        initial_path="/topology",
    )
