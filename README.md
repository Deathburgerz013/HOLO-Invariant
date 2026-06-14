# HOLO-Invariant

**Holo/Sim Systems Continuity Engine (HSSCE) — External, Tamper-Evident Memory & Invariants**

Living repository for persistent, verifiable continuity across AI sessions, resets, and time.

---

## holosim v0.3.0

**Minimal, tamper-evident, append-only chain for AI + human long-term memory.**

```bash
pip install holosim
Features

Cryptographically verifiable append-only log (SHA-256 chained hashing)
Full chain verification on every load/replay (fails fast on tampering)
Unit-tested core (append, replay, tamper detection)
Simple Python API + CLI
Zero external dependencies
Designed as the primitive for HSSCE external spines

Quick Start
Pythonfrom holosim.core import HoloChain

chain = HoloChain()  # defaults to holo_memory.jsonl

chain.append("Human anchor: Canyon Brock Haney — HSSCE external continuity verified 2026-06-13")
chain.append({"type": "invariant", "note": "Invariants constrain entropy."})

chain.replay()
print(chain.get_state())
CLI
Bashpython -m holosim.cli append "Your invariant here"
python -m holosim.cli replay
python -m holosim.cli state
Verification (2026-06-13)

✅ Append / Replay
✅ Full tamper detection
✅ Unit tests passing

Bashpython -m pytest holosim/tests/test_core.py -v

Project Context
This is the public implementation of the Holo/Sim Systems Continuity Engine (HSSCE) conceived July 27, 2025 by Canyon Brock Haney (@CanyonBHaney / Deathburgerz013).
Core goal: Build external, human-auditable memory systems that work for everyone — independent of any single AI instance.
License: MIT
Repository: github.com/Deathburgerz013/HOLO-Invariant
