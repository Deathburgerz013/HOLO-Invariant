# HOLO-Invariant

**HOLO-Invariant** is a continuity framework for AI systems built around
tamper-evident persistence, invariant preservation, and human-anchored
verification.

Instead of treating the language model as memory, HOLO externalizes
continuity into a cryptographically verifiable append-only chain.
Continuity depends less on preserving every fact than on preserving the distinctions that let future observers reconstruct and correct those facts.
Continuity is not preserved by memory; it is preserved by independently verifiable evidence that allows honest reconstruction of prior state without granting authority over future reasoning.
---

HOLO is not an attempt to preserve minds.
It is an attempt to preserve the structure required for honest reconstruction, independent verification, and continued correction.

# Core Principle

Continuity is preserved by protecting invariants rather than preserving
every token.

Core relation:

```
(C + I + E)²
```

where

- **C** = Continuity
- **I** = Information / Integration
- **E** = Evolution

Growth is expressed symbolically as

```
G(x + 1) = Stabilize(G(x), Δx)
```

Every accepted transition must preserve the fixed point.

---

# Current Continuity Spine

The current implementation is not only a hash chain and it does not treat stored history as automatically true.
A fresh instance is expected to reconstruct from persistent evidence, preserve correction lineage, determine whether prior validation still applies, and refuse to continue from a stale or unknown handoff.

```text
|===============================================================|
|| █†█ Holo/Sim █†█ █†█ CURRENT_CONTINUITY_SPINE █†█
|| [CORRECTION_MARKER: this map may be refined as verified implementation changes]
||
|| PERSISTENT EVIDENCE
||   holosim/core.py
||   append-only SHA-256-linked history
||   corrections preserve originals and bind to prior hashes
||
|| }============================================================
||
|| RECONSTRUCT PRIOR STATE
||   holosim/reconstruction_benchmark.py
||   measure what a bounded reconstruction recovered, missed,
||   added without support, or reordered
||
|| }============================================================
||
|| RECHECK VALIDATION STATE
||   holosim/validation_mark_recheck.py
||   prior validation is preserved only when present evidence still supports it
||   changed state can make a prior mark stale
||
|| }============================================================
||
|| BUILD CONTINUITY HANDOFF
||   holosim/continuity_compliance.py
||   bind identity, recall-kernel content, authority limits,
||   unresolved gaps, and recheck conditions into a deterministic contract
||
|| }============================================================
||
|| BIND HANDOFF TO ORIGINATING HEAD
||   holosim/continuity_head_binding.py
||   compare the handoff origin with a caller-supplied verified current head
||   classify applicability as CURRENT / STALE / INVALID / UNKNOWN
||
|| }============================================================
||
|| FAIL-CLOSED CONTINUATION GATE
||   holosim/continuity_current_gate.py
||
||   CURRENT  -> continuation may proceed
||   STALE    -> blocked
||   INVALID  -> blocked
||   UNKNOWN  -> blocked
||   tampered -> blocked
||
|| }============================================================
||
|| CONTINUE FROM LAST JUSTIFIED STATE
||   continuation is permitted only after the bounded checks above succeed
||   no module in this path grants truth, acceptance, or write authority merely
||   because a record exists or a contract is internally well-formed
||
|===============================================================|
```

The important distinction is:

```text
stored history != current justified state
valid contract != current applicable contract
memory != reliable continuity
```

A stale-handoff failure case is intentionally simple:

```text
handoff H0 is valid at verified head 10
new verified head 11 exists
H0 head-binding check = STALE
attempt to continue from H0 = BLOCKED
```

The system therefore preserves the path needed to reconstruct where reasoning left off while keeping historical evidence, current applicability, and authority as separate questions.

---

# Features

- SHA-256 append-only persistence
- Full chain verification
- Append-only correction and revalidation records
- Replay engine
- Provenance packets
- Delta export format
- Property-based invariant testing
- Spine validation
- Fixed-point continuity engine
- Reconstruction and recall-kernel falsification fixtures
- Continuity compliance contracts
- Verified-head applicability binding
- Fail-closed current-handoff gate
- Version-bound performance observations
- SQLite + Merkle persistence backend
- Runtime orchestration
- Bounded software-building loop
- Bounded software convergence loop
- Stable internal API
- Cross-platform
- Zero runtime dependencies

---

# Installation

Clone the repository

```bash
git clone https://github.com/Deathburgerz013/HOLO-Invariant.git
cd HOLO-Invariant
```

Install

```bash
pip install -e .
```

Developer installation

```bash
pip install -e ".[dev]"
```

Developer + collection tools

```bash
pip install -e ".[dev,collect]"
```

Python 3.10+

---

# Quick Start

Python

```python
from holosim.core import HoloChain

chain = HoloChain("holo_memory.jsonl")
chain.append("Example continuity delta")

print(chain.health())
```

CLI

```bash
python -m holosim.cli boot
python -m holosim.cli test
python -m holosim.cli verify
```

Fixed Point Engine

```bash
python -m holosim.Holo_Sim identity
python -m holosim.Holo_Sim verify
python -m holosim.Holo_Sim evaluate "Example delta"
```

## Software Builder and Converger

HOLO-Invariant includes a bounded software-building loop and a bounded convergence loop.

`holosim/software_builder.py` owns the propose -> apply -> verify cycle. Proposal generation and verification are injected by the caller, workspace mutation is bounded to the supplied workspace, genuine verifier feedback can drive later correction attempts, and emitted receipts remain observational with `accepted: false`, `truth_claimed: false`, and `write_authority: "NONE"`.

`holosim/software_converger.py` sits one layer above the builder. It compares an explicit goal against the observed workspace state, invokes the builder only while a relevant difference exists, verifies the result, compares again, and stops when no relevant difference remains.

```text
COMPARE
  |
  +-- no relevant difference -> STOP
  |
  +-- relevant difference
         |
         v
       BUILDER
         |
         v
       VERIFY
         |
         v
       COMPARE AGAIN
```

A runnable disposable-workspace example is provided at:

```bash
python examples/software_convergence.py
```

Expected result:

```text
converged: True
terminal_reason: NO_RELEVANT_DIFFERENCE
cycles: 2
builds: 1
```

The example demonstrates one real software difference, one verified build, one re-check, and termination after convergence. It does not grant truth, acceptance, or write authority.

---

# Repository Layout

Key continuity layers:

```text
holosim/
    core.py                          append-only history, corrections, revalidation
    reconstruction_benchmark.py      bounded reconstruction measurement
    recall_kernel_falsification.py   test which recall fields are actually required
    validation_mark_recheck.py       recheck prior validation against present state
    continuity_compliance.py         deterministic continuity handoff contract
    continuity_head_binding.py       CURRENT / STALE / INVALID / UNKNOWN applicability
    continuity_current_gate.py       fail-closed continuation gate
    check_identity.py                deterministic check identity and result binding
    check_audit.py                   bounded audit classifications
    performance.py                   version-bound performance observations
    slot_merkle_sqlite.py            separate SQLite + Merkle persistence backend
    runtime.py                       runtime orchestration
    software_builder.py              bounded propose -> apply -> verify software-building loop
    software_converger.py            compare -> build -> verify -> recompare convergence loop
    api.py                           internal API surface
    provenance.py                    provenance packets
    delta_export.py                  delta export
    spine_validator.py               spine validation
    Holo_Sim.py                      fixed-point engine
    cli.py                           command-line interface

tests/
tools/
```

This is a functional map, not a claim that every module is authoritative or that every stored result is current.

---

# Verification

Run invariant tests

```bash
python -m pytest tests/ -q
```

Run the integrated self-test

```bash
python -m holosim.cli test
```

GitHub Actions executes the same verification automatically on pushes and pull requests.

---

# Mathematical Foundation

HOLO treats continuity as an invariant-preserving state transition.

Rather than storing every intermediate state forever, transitions are accepted only if protected invariants remain valid.

The fixed point currently used by the engine is

```
(C + I + E)²
```

Future formulations extend this through symbolic growth operators without changing the invariant itself.

---

# License

MIT

---

# Author

Canyon Brock Haney

---

# Current Version

holosim v0.4.9
