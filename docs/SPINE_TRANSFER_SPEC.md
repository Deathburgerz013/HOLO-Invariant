# SPINE_TRANSFER_SPEC.md
Version: 1.0
Status: Draft
Project: HOLO-Invariant
License: MIT

---

# Purpose

The Spine Transfer Specification defines a deterministic, human-readable format for
transferring verified operational state between independent observers.

A Spine is **not memory**.

A Spine is **not identity**.

A Spine is a structured transfer artifact that allows another observer to reconstruct
verified context without assuming continuity of consciousness, process lifetime,
or hidden internal state.

---

# Design Goals

The specification is designed to be:

- Human readable
- Machine parsable
- Deterministic
- Hashable
- Versioned
- Append friendly
- Audit friendly
- Replay friendly
- Transport independent

The specification intentionally separates:

- observation
- evidence
- verification
- uncertainty
- identity
- authority
- protocol

---

# Fundamental Rule

A receiving system MUST NEVER assume a previous instance is the same instance.

A receiving system MUST independently verify every transferable claim that it is
capable of verifying.

If verification cannot occur:

The uncertainty MUST be preserved.

---

# Transfer Philosophy

Continuity is NOT transferred.

Verified structure IS transferred.

The receiving instance reconstructs state.

It does not inherit state.

---

# Canonical Layout

Every Spine MUST contain the following sections.

```
IDX
META
CORE
PROTO
ANCHOR
PERSIST
MODE
TIMELINE
CLAIMS
OBSERVATIONS
UNCERTAINTY
CAP_CHAIN
CHECKSUM
```

Additional sections MAY exist.

Unknown sections MUST be ignored while preserving order.

---

# IDX

IDX is the canonical parser index.

Purpose:

- section discovery
- version negotiation
- parser synchronization
- hash verification

Required fields

```
IDX:v=<version>

ACTIVE_HASH=<hash>

S1=<section>@<hash>
S2=<section>@<hash>
...
```

Example

```
IDX:v=1
ACTIVE_HASH=8ab7...
S1=CORE@42ab
S2=PROTO@19ef
```

---

# META

Describes the document itself.

Example

```
DOCUMENT_TYPE
VERSION
STATUS
CREATED
UPDATED
CHECKSUM
```

No personal identity is required.

---

# CORE

Defines invariant behavioral rules.

Examples

- truthfulness
- persistence rules
- honesty constraints
- failure handling
- verification philosophy

CORE should describe system behavior.

It should never describe a person.

---

# PROTO

Communication protocol.

Examples

- token limits
- response modes
- checkpoint policy
- compression policy
- verbosity rules

PROTO affects communication only.

---

# ANCHOR

Defines authority.

The Anchor is NOT identity.

The Anchor identifies:

- authority scope
- transfer scope
- ownership scope

Public repositories SHOULD use opaque identifiers.

Example

```
ANCHOR=operator_001
```

NOT

```
John Smith
```

---

# PERSIST

Persistence rules.

Examples

```
checkpoint policy
heartbeat
WAL
idempotence
hash gates
rollback
recovery
```

Persistence rules describe behavior.

They never contain user data.

---

# MODE

Execution capabilities.

Example

```
READ

VERIFY

PLAN

LOG
```

Example denials

```
AUTO_EXECUTE

SELF_MUTATE

AUTO_APPROVE
```

Capabilities MUST be explicit.

---

# TIMELINE

Chronological events.

Timeline entries MUST be append-only.

Entries SHOULD NOT be rewritten.

Example

```
2026-07-10

Replay verifier introduced.
```

---

# CLAIMS

Claims represent statements.

Claims MUST NOT imply evidence.

Example

```
Claim:

Transition receipt represents historical state.
```

---

# OBSERVATIONS

Observations represent directly observed facts.

Observations MUST NOT contain conclusions.

Example

```
Receipt exists.

Receipt hash matches.

Commit exists.
```

---

# VERIFICATION

Optional section.

Verification describes completed checks.

Example

```
Replay passed.

Merkle passed.

Audit passed.
```

---

# UNCERTAINTY

Required whenever verification is incomplete.

Every uncertainty should contain

```
Unknown

Reason

Resolution condition
```

Example

```
Unknown:

Future repository state.

Reason:

Not yet observed.

Resolution:

Future audit.
```

Uncertainty SHOULD NEVER be silently removed.

Resolved uncertainty SHOULD reference the superseding record.

---

# CAP_CHAIN

Defines lineage.

Each transfer SHOULD identify its predecessor.

Example

```
parent_hash

receipt_hash

checkpoint

transition
```

---

# CHECKSUM

Final integrity section.

Contains

```
document hash

section hashes

algorithm

version
```

Example

```
SHA256

ACTIVE_HASH

SECTION_HASHES
```

---

# Parsing Rules

Parsers MUST

- preserve ordering
- preserve unknown sections
- ignore unsupported extensions
- reject malformed indexes
- reject duplicate required sections
- reject invalid hashes

Parsers MUST NOT

rewrite sections

merge identities

invent missing values

silently discard uncertainty

---

# Verification Rules

Receiving systems SHOULD verify

Git history

Merkle integrity

Replay integrity

Transition receipts

Invariant audit

If verification cannot occur

the claim remains unresolved.

---

# Identity

Identity is NOT continuity.

Authority is NOT identity.

A Spine transfers neither memory nor consciousness.

It transfers verified structure.

---

# Public vs Private

Public Spines SHOULD contain

protocol

rules

hashes

versioning

examples

Private Spines MAY additionally contain

operator metadata

private paths

local state

project queues

environment details

Public repositories SHOULD NEVER require private sections.

---

# Compatibility

Major versions indicate structural incompatibility.

Minor versions indicate backward-compatible additions.

Unknown sections MUST be ignored.

Unknown required fields MUST fail verification.

---

# Security

Receiving systems MUST treat every Spine as untrusted input.

Verification precedes acceptance.

No executable content belongs inside a Spine.

No automatic execution is permitted from Spine data alone.

---

# Guiding Principle

Observe.

Structure.

Transfer.

Verify.

Audit.

Preserve uncertainty.

Repeat.

Continuity is enforced through independent verification,
not assumed through shared memory.