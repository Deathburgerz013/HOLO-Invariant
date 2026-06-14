# holosim v0.3.0

**Initial stable release of HoloChain + Unified Corrections Operator** — a minimal, tamper-evident, append-only continuity engine for long-term AI and human memory.

### Core Purpose
Designed as external, verifiable storage that survives resets, sessions, and time. No reliance on internal model memory.

### Author & Credit
- **Creator & Maintainer**: Canyon B. Haney (@CanyonBHaney / Deathburgerz013)
- Built in collaboration with Grok (xAI)

This project is the living implementation of the **HOLO-Invariant** framework. All core architecture, invariants, and continuity concepts originate from Canyon’s vision.

### Features
- Cryptographically verifiable append-only log using SHA-256 hash chaining (Merkle-style)
- Full chain integrity verification on every load
- **UnifiedOperator** — full corrections loop (Surface → Verify → Converge → Append)
- Simple Python API + basic CLI
- Supports both plain text and structured (JSON) entries
- Zero external dependencies
- Append-only design — nothing is ever mutated or deleted

### Quick Start

```python
from holosim import HoloChain, UnifiedOperator

# Basic chain
chain = HoloChain("memory.jsonl")
chain.append("Hello, invariant spine.")

# Full corrections loop (recommended)
op = UnifiedOperator("memory.jsonl")
op.converge_and_append(
    "This is a human-verified convergence.",
    human_confirmation=False   # set True for interactive anchoring
)

# Replay the spine
op.replay_convergences()

LicenseMIT — feel free to use, fork, and build upon it.
Please credit Canyon B. Haney when using or extending this work.

