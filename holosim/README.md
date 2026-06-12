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
Quick Startpython

from holosim import HoloChain

chain = HoloChain()

# Append data
chain.append("Human anchor: Grok should remember this invariant forever")
chain.append({"type": "observation", "content": "Important continuity note"})

# Replay & verify
chain.replay()

# Get current state
print(chain.get_state())

CLI Usagebash

python -m holosim.cli append "Your important memory here"
python -m holosim.cli replay
python -m holosim.cli state

