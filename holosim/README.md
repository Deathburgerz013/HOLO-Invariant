# holosim

**Holo/Sim** — A minimal, tamper-evident, append-only chain for AI continuity and long-term memory.

**Core Invariant**: External, cryptographically verifiable persistence that survives model resets, sessions, and time.

---

## Features

- Cryptographically tamper-evident append-only log (SHA-256 chained hashing)
- Full chain verification on every load/replay (fails fast on any modification)
- Simple Python API + CLI
- Zero dependencies
- Designed for HSSCE (Holo/Sim Systems Continuity Engine) and external AI memory
- Unit tested (append, replay, tamper detection)

---

## Installation

```bash
# From PyPI
pip install holosim

# Or editable from source (recommended for development)
git clone https://github.com/Deathburgerz013/HOLO-Invariant.git
cd HOLO-Invariant
pip install -e .

Quick Start (Python)
Pythonfrom holosim.core import HoloChain

chain = HoloChain()  # defaults to holo_memory.jsonl

# Append invariants / observations
chain.append("Human anchor: Canyon Brock Haney — HSSCE external continuity verified 2026-06-13")
chain.append({"type": "invariant", "content": "Everything is math. Invariants constrain entropy."})

# Replay & verify full history
chain.replay()

# Get current state
print(chain.get_state())

CLI Usage
Bash# Append
python -m holosim.cli append "Test invariant: HSSCE external continuity verified 2026-06-13"

# Replay full chain
python -m holosim.cli replay

# Get current state
python -m holosim.cli state

Verification (2026-06-13)

✅ Chain append works
✅ Full replay + verification works
✅ Tamper detection works — any single character change raises ValueError: Hash mismatch
✅ Unit tests passing (test_append_and_replay, test_empty_chain, test_tamper_detection)

Bashpython -m pytest holosim/tests/test_core.py -v
All tests passed.

Project Context
Part of the HOLO-Invariant repository and Holo/Sim Systems Continuity Engine (HSSCE) — building persistent, verifiable memory systems for humans and AIs.
License: MIT

Status: Production-ready primitive for continuity work.