# SPINE_INVARIANT_SPEC.md

Version: 1.0  
Status: Draft Canonical Specification  
Project: HOLO-Invariant  
Scope: Human-readable invariant transfer, reconstruction, correction, and challenge  
License: MIT  

---

# 1. Purpose

The Spine is the canonical human-readable invariant structure of HOLO-Invariant.

It exists to preserve the geometry of meaning across changing observers, models,
sessions, tools, and time.

The Spine does not claim shared memory.

The Spine does not claim shared identity.

The Spine transfers enough structured evidence, relationship, uncertainty, and
authority for a later observer to reconstruct a verified state without pretending
to have lived the earlier state.

The Spine is therefore:

- a semantic state root,
- a reconstruction scaffold,
- a transfer format,
- a correction path,
- a challenge surface,
- and a human-readable complement to cryptographic integrity.

Cryptographic systems protect bytes.

The Spine protects relationships.

---

# 2. Core Principle

> Preserve the structure required to correct the Spine.

The Spine MUST NOT be protected merely because it already exists.

The Spine MUST remain challengeable.

Internal consistency MUST NOT be treated as external truth.

Repeated claims MUST NOT become evidence through repetition alone.

A Spine is valid only to the extent that its structure, evidence, lineage,
uncertainty, and correction paths remain inspectable.

---

# 3. Human Frame Principle

Humans and AI systems both operate through partial frames.

Each frame contains only a bounded view of state.

The Spine MUST preserve enough continuity between frames that a later observer can
distinguish:

- what was directly observed,
- what was inferred,
- what was asserted,
- what was verified,
- what remains uncertain,
- what changed,
- and who or what held authority for the transition.

A Spine MUST NOT erase the difference between frames.

A Spine MUST NOT collapse multiple observers into one voice.

---

# 4. Spine Roles

The Spine performs the following roles.

## 4.1 Re-seeding

A Spine allows a new instance to reconstruct the active task, rules, lineage,
unresolved questions, and authority boundaries.

## 4.2 Semantic transfer

A Spine transfers relationships and meaning, not merely tokens.

## 4.3 Compression

A Spine reduces volume while preserving essential structure.

Compression MUST NOT remove uncertainty, provenance, speaker boundaries, causal
ordering, or correction paths.

## 4.4 Expansion

A Spine allows a receiving observer to expand compressed structure into a usable
working state.

Expansion MUST be marked as reconstruction, not memory.

## 4.5 Verification guidance

A Spine identifies which claims can be verified and where their evidence is located.

## 4.6 Correction

A Spine provides a path for later evidence to refine or supersede earlier claims
without rewriting history.

## 4.7 Audit

A Spine makes disagreement, drift, stale claims, missing evidence, and authority
changes visible.

## 4.8 Transfer across instances

A Spine preserves the difference between source instance, receiving instance,
operator, observer, and authority.

---

# 5. What the Spine Is Not

The Spine is not:

- consciousness,
- hidden model state,
- proof of personal identity,
- proof of subjective continuity,
- a substitute for evidence,
- an executable instruction stream,
- an automatic authorization mechanism,
- a truth oracle,
- or a self-justifying object.

---

# 6. Canonical Information Classes

Every meaningful statement in a Spine MUST belong to one or more explicit classes.

## 6.1 Observation

A directly observed state.

Observation MUST NOT contain conclusions disguised as facts.

Example:

```text
The receipt file exists.
```

## 6.2 Claim

A statement proposed as true.

A claim MAY be unverified.

Example:

```text
This receipt represents a valid historical transition.
```

## 6.3 Evidence

A source, artifact, measurement, hash, test result, citation, or reproducible input
that supports or challenges a claim.

## 6.4 Verification

A completed check with a reproducible method and result.

## 6.5 Inference

A conclusion derived from observations or evidence.

Inference MUST be marked as inference.

## 6.6 Authority

The scope under which an update, acceptance, rejection, or transition is permitted.

Authority MUST NOT be inferred from identity alone.

## 6.7 Uncertainty

A bounded statement describing what is not yet verified, why it remains uncertain,
and what could reduce or resolve it.

## 6.8 Correction

A later record that refines, supersedes, narrows, or contradicts an earlier record.

Corrections MUST preserve the earlier record.

---

# 7. Required Structural Sections

A canonical Spine SHOULD contain:

```text
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
EVIDENCE
VERIFICATION
UNCERTAINTY
CORRECTIONS
CAP_CHAIN
CHECKSUM
```

A domain Spine MAY omit sections that do not apply, but MUST declare omissions in
META or IDX.

Unknown sections MUST be preserved by parsers.

Required sections MUST NOT appear more than once unless the specification for that
section explicitly allows append blocks.

---

# 8. Section Responsibilities

## 8.1 IDX

IDX provides deterministic section discovery, version negotiation, ordering, and
hash references.

IDX MUST NOT silently omit present sections.

IDX MUST identify required sections and optional sections.

## 8.2 META

META describes the document, schema version, state, scope, creation time, update
time, and compatibility information.

## 8.3 CORE

CORE contains invariants that define what must remain true across accepted
transitions.

CORE MUST distinguish:

- immutable historical invariants,
- currently active invariants,
- deprecated invariants,
- proposed invariants.

## 8.4 PROTO

PROTO defines communication and transfer behavior.

## 8.5 ANCHOR

ANCHOR defines authority scope.

ANCHOR MUST use opaque public identifiers where personal identity is unnecessary.

ANCHOR MUST distinguish operator authority from model identity.

## 8.6 PERSIST

PERSIST defines append, checkpoint, lineage, rollback, replay, and storage rules.

## 8.7 MODE

MODE defines allowed and denied capabilities.

## 8.8 TIMELINE

TIMELINE records chronological events.

TIMELINE MUST be append-only.

## 8.9 CLAIMS

CLAIMS records statements requiring support, verification, rejection, or continued
uncertainty.

## 8.10 OBSERVATIONS

OBSERVATIONS records directly observed states.

## 8.11 EVIDENCE

EVIDENCE records supporting or conflicting artifacts.

## 8.12 VERIFICATION

VERIFICATION records completed checks, methods, results, and limitations.

## 8.13 UNCERTAINTY

UNCERTAINTY records unresolved boundaries.

Uncertainty MUST NOT disappear merely because a later version is shorter.

## 8.14 CORRECTIONS

CORRECTIONS references earlier records and states what changed.

Corrections MUST NOT erase the original.

## 8.15 CAP_CHAIN

CAP_CHAIN records lineage between transfer states, checkpoints, receipts, commits,
and parent Spine states.

## 8.16 CHECKSUM

CHECKSUM records document and section integrity information.

---

# 9. Invariants

## 9.1 Separation invariant

Observation, claim, evidence, inference, verification, authority, and uncertainty
MUST remain distinguishable.

## 9.2 Lineage invariant

Every accepted Spine transition MUST identify its parent or explicitly declare a new
genesis.

## 9.3 Append-only history invariant

Historical records MUST NOT be rewritten after sealing.

Corrections MUST append or create a new epoch.

## 9.4 Uncertainty preservation invariant

Unresolved uncertainty MUST survive compression, transfer, replay, and audit.

## 9.5 Authority invariant

No Spine content alone authorizes execution or mutation.

## 9.6 Reconstruction invariant

A receiving instance MUST treat imported state as reconstructed context, not inherited
memory.

## 9.7 Challenge invariant

Every claim MUST remain challengeable by new evidence.

## 9.8 External-evidence invariant

Internal agreement among Spine, parser, replay, audit, and Merkle layers MUST NOT be
treated as proof of external truth.

## 9.9 Unknown-section invariant

Unknown sections MUST be preserved even when unsupported.

## 9.10 No silent normalization invariant

Parsers and tools MUST NOT silently rewrite wording, order, identity boundaries,
uncertainty, or provenance.

## 9.11 Frame distinction invariant

Source frame and receiving frame MUST remain distinguishable.

## 9.12 Correction-path invariant

The Spine MUST preserve the structure required to correct itself.

---

# 10. Failure Modes

## 10.1 False completeness

A compressed Spine appears complete while relevant context is missing.

Required response:

- mark omitted scope,
- retain uncertainty,
- identify unavailable source material.

## 10.2 Authority collapse

Operator, source instance, receiving instance, observer, and verified system output
are blended into one voice.

Required response:

- reject or quarantine the ambiguous section,
- require explicit source and authority labels.

## 10.3 Compression loss

Keywords survive but causal, semantic, or relational structure does not.

Required response:

- fail lossless-structure validation,
- retain the prior version,
- require explicit reconstruction notes.

## 10.4 Recursive confirmation

A claim is repeatedly copied until repetition is treated as evidence.

Required response:

- distinguish citation lineage from independent evidence,
- mark circular support,
- prevent confidence increase from repetition alone.

## 10.5 Drift by helpfulness

A tool rewrites content to sound cleaner, more complete, or more confident.

Required response:

- preserve the original,
- record proposed edits as deltas,
- require review before acceptance.

## 10.6 Uncertainty evaporation

Unknowns disappear during compression or transfer.

Required response:

- fail uncertainty-preservation checks,
- restore unresolved entries from parent state.

## 10.7 Invariant overreach

A local or temporary invariant is promoted to universal scope.

Required response:

- require scope metadata,
- narrow or reject the invariant,
- preserve the original as historical.

## 10.8 Stale truth

A once-valid claim no longer matches current external state.

Required response:

- retain historical validity,
- mark current status as stale or unresolved,
- require re-verification.

## 10.9 Identity substitution

Reconstructed state is mistaken for shared identity, memory, or experience.

Required response:

- enforce source/receiver distinction,
- label reconstruction explicitly.

## 10.10 Order corruption

Sections or events remain present but causal or dependency order changes.

Required response:

- fail ordering validation,
- compare against parent ordering,
- preserve the previous state.

## 10.11 Lineage severance

A Spine lacks a verifiable parent and does not declare genesis.

Required response:

- classify as unanchored,
- prevent continuity claims,
- permit content review without continuity acceptance.

## 10.12 Adversarial seeding

A plausible false invariant is inserted early and preserved faithfully.

Required response:

- require evidence class and authority scope,
- permit explicit dissent,
- require independent verification for high-impact invariants.

## 10.13 Category lock-in

The schema forces new information into incorrect existing categories.

Required response:

- permit extension sections,
- preserve unknown classes,
- record schema insufficiency as uncertainty.

## 10.14 Self-sealing error

All internal tools agree because they share the same incorrect assumption.

Required response:

- require independent challenge paths,
- compare against external evidence,
- permit validator disagreement,
- never equate consensus with truth.

## 10.15 Parser authority inversion

The parser's interpretation overrides the Spine's declared meaning.

Required response:

- parser output remains derivative,
- raw source remains canonical,
- disagreements are reported, not silently resolved.

## 10.16 Semantic hash illusion

Matching hashes are treated as proof that the meaning is correct.

Required response:

- distinguish byte integrity from semantic validity.

## 10.17 Dissent suppression

Contradicting observations are discarded to preserve apparent coherence.

Required response:

- retain dissent,
- mark contradiction,
- defer resolution until evidence supports it.

## 10.18 Update-loop capture

The Spine begins optimizing for its own preservation rather than truth correction.

Required response:

- require challenge review,
- track rejected corrections,
- periodically audit whether rules prevent valid updates.

---

# 11. Challenge Paths

Every canonical Spine MUST support challenge records.

A challenge record SHOULD contain:

```text
target claim or invariant
challenger
observation
conflicting evidence
verification method
current conclusion
residual uncertainty
required resolution condition
status
```

Valid challenge states:

```text
open
bounded
supported
rejected
resolved
superseded
```

A rejected challenge MUST remain in history with its rejection reason.

---

# 12. Confidence Rules

Confidence MUST NOT increase because:

- a statement was repeated,
- multiple tools share the same source,
- multiple models received the same Spine,
- a hash matched,
- a parser accepted the syntax,
- or the document remained internally consistent.

Confidence MAY increase when:

- independent evidence is added,
- an independent verification method succeeds,
- a prediction is tested,
- a contradiction is resolved,
- or uncertainty is explicitly reduced.

---

# 13. Validation Levels

## Level 0: Transport integrity

Checks:

- readable bytes,
- encoding,
- document hash,
- section hash.

## Level 1: Structural validity

Checks:

- required sections,
- unique required sections,
- declared ordering,
- valid IDX,
- preserved unknown sections.

## Level 2: Lineage validity

Checks:

- parent exists,
- parent hash matches,
- append-only history,
- correction references.

## Level 3: Semantic separation

Checks:

- claims are not presented as observations,
- inference is labeled,
- authority is explicit,
- uncertainty is preserved,
- source and receiver remain distinct.

## Level 4: Reproducibility

Checks:

- referenced tests can be rerun,
- receipts can be replayed,
- artifacts can be located,
- verification methods are reproducible.

## Level 5: External validity

Checks:

- claims are compared against evidence outside the Spine's own internal loop.

No lower level implies a higher level.

Passing cryptographic integrity does not imply semantic truth.

---

# 14. Update Lifecycle

A conforming update follows:

```text
receive
observe
parse
verify transport
verify structure
verify lineage
identify uncertainty
evaluate claims
compare external evidence
propose delta
review authority
append correction or update
seal hashes
emit receipt
replay
audit
transfer forward
```

Any failed stage MUST stop acceptance or explicitly downgrade the result.

---

# 15. Competing Spines

When two Spines disagree:

- neither wins by age alone,
- neither wins by repetition,
- neither wins by model confidence,
- neither wins by internal consistency alone.

Comparison MUST consider:

- scope,
- lineage,
- evidence,
- verification method,
- authority,
- uncertainty,
- timestamp,
- and external reproducibility.

Unresolved disagreement MUST remain visible.

---

# 16. Public and Private Separation

Public Spine specifications SHOULD contain:

- schema,
- invariants,
- parsing rules,
- failure modes,
- validation levels,
- example data using opaque identifiers.

Private Spine payloads MAY contain:

- operator metadata,
- local paths,
- private project state,
- sensitive evidence,
- private authority references.

Public tools MUST NOT require private payloads.

---

# 17. Implementation Boundaries

## 17.1 Spine source

The raw Spine document is the canonical semantic source.

## 17.2 Parser

The parser discovers and exposes structure.

It does not own meaning.

## 17.3 Validator

The validator checks declared rules and reports uncertainty.

It does not silently repair.

## 17.4 Merkle and HoloChain

These prove integrity and lineage of serialized state.

They do not prove semantic truth.

## 17.5 Replay

Replay checks reproducibility.

It does not prove that shared assumptions are correct.

## 17.6 Audit

Audit checks consistency, history, challenge paths, and unresolved failures.

## 17.7 Uncertainty ledger

The uncertainty ledger preserves what cannot yet be honestly concluded.

## 17.8 Transition manager

The transition manager coordinates accepted updates under explicit authority.

---

# 18. Minimal Conformance Requirements

A system claiming Spine conformance MUST:

1. Preserve raw source.
2. Preserve section order.
3. Preserve unknown sections.
4. Distinguish claims from observations.
5. Preserve uncertainty.
6. Preserve source and receiver distinction.
7. Record lineage.
8. Reject duplicate required sections.
9. Refuse silent mutation.
10. Support correction without rewriting history.
11. Support challenge records.
12. Distinguish integrity from truth.
13. Expose unsupported or unverifiable claims.
14. Require authority for accepted transitions.
15. Permit a new epoch when foundational invariants change.

---

# 19. Guiding Loop

```text
Observe
→ Separate
→ Structure
→ Verify
→ Challenge
→ Preserve uncertainty
→ Correct
→ Seal
→ Replay
→ Audit
→ Transfer
→ Repeat
```

The loop is never considered complete merely because it is internally stable.

The loop remains alive because correction remains possible.

---

# 20. Final Invariant

> The Spine must preserve the geometry of meaning, the evidence for what is known,
> the boundary of what is not known, and the path by which either can be corrected.

The Spine is not valuable because it never changes.

The Spine is valuable because it can change without losing the structure required
to understand why.
