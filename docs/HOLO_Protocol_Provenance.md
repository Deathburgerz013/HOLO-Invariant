# HOLO Protocol Provenance

## Purpose

This document records the traceable development of HOLO-Invariant from compact continuity notes into an executable, testable repository.

It is a provenance record, not proof that every historical proposal was implemented. Historical statements are separated from behavior that can be reproduced in the current codebase.

## Evidence Classes

- **Specification** — a written rule or proposed behavior.
- **Public record** — a timestamped description published independently of the repository.
- **Transfer record** — a manifest describing ordered artifacts and expected hashes.
- **Implementation** — behavior present in repository code.
- **Verification** — behavior exercised by reproducible tests.

## Development Lineage

### 1. Compact indexed state

The early `IDX` format described seven named state compartments, short identifiers, an active version hash, token thresholds, checkpoint rules, truth markers, and a restricted sentinel mode.

Useful contribution:

- compact state addressing;
- explicit active-state identity;
- bounded loading behavior;
- separation of read/verify capabilities from mutation;
- `UNKNOWN`, `BLOCKED`, and `RESTRICTED` truth states.

Status: **historical specification**. Short identifiers are treated as recorded labels unless their source bytes and derivation can be reproduced.

### 2. Manual fuse and guarded reload

By August 22, 2025, the protocol was publicly described as slot-based persistence using a compact index and version hash.

The public description included:

- `ASSERT_FUSE=MANUAL_OVERRIDE`;
- same hash returning an already-fused result;
- refusal to rewrite an already-fused state;
- rejection of an unrecognized trigger;
- rejection of stale state;
- rejection of missing tags or mismatched input;
- no dependency on plugins or background tasks.

Status: **public timestamped design record**. This supports the existence and intended behavior of the protocol, not implementation correctness by itself.

### 3. Ordered transfer and verification

The later transfer manifest described sixteen ordered chunks with filenames, SHA-256 values, continuity tags, an anchor identifier, and receiver-side verification steps.

Useful contribution:

- metadata remains attached to content;
- ordering is explicit;
- expected and observed digests are compared before ingestion;
- mismatches block acceptance;
- continuity transfer becomes independently checkable.

Status: **transfer record**. Individual matches are reproducible only when the corresponding source chunks are available.

### 4. Snapshot, delta, and rollback discipline

Historical recovery notes progressively converged on:

- a last-known-good snapshot;
- append-only deltas;
- checksum verification before load;
- rollback after mismatch;
- failed snapshots marked unusable;
- promotion only after verification;
- side processes reading published snapshots instead of mutable live state;
- idempotent changes disabled by default until explicitly enabled.

Status: **historical specification with current architectural descendants**.

### 5. Divergence and self-correction

The divergence protocol introduced a bounded challenge loop:

1. record the active hypothesis;
2. test its inverse or strongest failure case;
3. compare the outcomes;
4. preserve the disagreement when evidence does not resolve it;
5. correct the smallest verified difference.

This is the historical basis for treating continuity as correction-preserving rather than conclusion-preserving.

Status: **design rule**. It does not imply autonomous or hidden background reasoning.

### 6. Executable repository boundary

HOLO-Invariant now implements testable continuity mechanics including append-only persistence, hash-chain verification, replay, provenance, Spine parsing, lineage analysis, bounded feedback, and measured visualizer export.

The visualizer/export boundary verifies:

- deterministic output;
- stable export hashing;
- exact-byte source hashing;
- fail-closed handling of missing explicit inputs;
- visible parse failures;
- evidence-backed relationships;
- link and metric consistency;
- JSON round-trip integrity.

Status: **implementation and automated verification**. The repository and its tests are authoritative for current behavior.

## Claim Boundary

HOLO-Invariant does not claim that a language model persists independently, thinks while disconnected, or preserves an identity without external state.

The supported claim is narrower:

> Continuity can be externalized into ordered, inspectable artifacts whose integrity, provenance, reconstruction, and correction behavior can be tested.

## Verification Rule

A historical statement may guide investigation, but it enters the active specification only when:

1. its source is identifiable;
2. its terms are operationally defined;
3. its behavior is implemented or explicitly marked as proposed;
4. its result can be reproduced;
5. uncertainty and failure remain visible.

## Current Principle

The anchor preserves identity and verified invariants, not a frozen course. Present evidence may correct direction without breaking continuity.