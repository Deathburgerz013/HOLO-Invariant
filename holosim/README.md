# holosim

**Holo/Sim** — A minimal, tamper-evident, append-only chain for AI continuity and long-term memory.

## Features
- Cryptographically verifiable append-only log (SHA-256 Merkle-style chaining)
- Full chain verification on every load
- Simple Python API + CLI
- Dependency-free
- Designed for external memory across sessions/resets

## Installation

```bash
pip install holosim

cd HOLO-Invariant-main
pip install -e .

python -m holosim.cli append "Your important memory here"
python -m holosim.cli replay
python -m holosim.cli state