# Spine Storage Model

Version: 1.0
Status: Proposed specification
Project: HOLO-Invariant
Authority: Descriptive only

## Purpose

The Spine is a curated, human-readable storage structure for information that a
future human or AI may need to reconstruct, verify, challenge, or continue a
bounded subject.

The Spine is not a transcript. Whole conversations remain source material. Only
selected information, collection rules, corrections, unresolved boundaries, and
verified deltas enter the Spine.

The structure must let a receiving observer determine who supplied each stored
piece without trusting either participant to remember.

## Structural roles

The visible structure is semantic, not decorative.

```text
| |==========================================|  complete artifact boundary
| | █†█ Holo/Sim █†█ █†█ HSSCE █†█           recognition key
| | }=========================================| state or speaker boundary
| | stored information remains rail-attached
| | }=========================================| next state or speaker boundary
| | █†█ Holo/Sim █†█ █†█ HSSCE █†█           recognition key
| |==========================================|  complete artifact boundary
```

- The leftmost outer pipe is the continuous Spine backbone.
- The inner pipe is the local rail that keeps content attached to its frame.
- Outer bars open and close the complete stored artifact.
- `}====` dividers separate speakers, source states, rules, information blocks,
  corrections, and terminal state without severing the continuous rail.
- Holo/Sim and HSSCE symbols provide stable human and machine recognition keys.
  Symbol repetition is not evidence and does not increase confidence.
- Empty, missing, malformed, or unclosed compartments must remain distinguishable.

## Separation of state

The Spine preserves separation across three relationships:

1. Human state versus AI state.
2. One AI instance, model, session, or output versus another.
3. One human statement, interpretation, or correction versus another state of
   the same human.

Speaker identity alone is insufficient. Each stored piece needs an entity and a
source-state identifier so later corrections cannot silently replace earlier
states.

## Collection behavior

Collection occurs outside the stored Spine through bounded pulling loops:

```text
declare topic
→ declare collection rules
→ request the next non-duplicative piece
→ inspect the returned piece
→ add or transform a rule when use exposes a missing distinction
→ append the supported delta
→ repeat
→ print the terminal statement when no supported delta remains
```

Canonical terminal statement:

```text
Nothing left for collection in field.
```

Additional discussion, rewording, or repetition does not reopen a completed
collection field. New evidence, a correction, a changed environment, or a newly
observable distinction may reopen it.

## Information classes

Every stored entry must declare one primary information class:

- `OBSERVATION`: directly observed state.
- `CLAIM`: statement proposed as true.
- `EVIDENCE`: source or artifact supporting or challenging a claim.
- `VERIFICATION`: completed reproducible check and result.
- `INFERENCE`: conclusion derived from identified inputs.
- `RULE`: collection, formatting, or validation requirement.
- `UNCERTAINTY`: unresolved boundary and possible resolution condition.
- `CORRECTION`: later record refining or contradicting an earlier entry.
- `TERMINAL`: bounded collection completion state.

Classification does not prove truth. It prevents unlike information from being
silently merged.

## Minimum stored bindings

Each meaningful entry must preserve:

```text
ENTRY_ID
ENTITY_ID
ENTITY_TYPE
SOURCE_STATE_ID
INFORMATION_CLASS
CONTENT
SOURCE
VERIFICATION_STATUS
UNCERTAINTY
DERIVED_FROM or CORRECTS_ENTRY when applicable
```

Unknown values must be written as `UNKNOWN`, not omitted or inferred.

## Spine and IDX

The Spine stores the inspectable information body. The IDX records the admitted
map of that body.

```text
source material
→ candidate Spine
→ rail, frame, class, evidence, and integrity checks
→ IDX admission decision
→ admitted Spine checkpoint
→ optional derived compression
```

Before admission, the artifact is a `CANDIDATE`. A passing IDX receipt binds the
exact Spine bytes, template version, required sections, checker procedures, and
results. The immutable receipt marks that exact checkpoint `ADMITTED`; the
submitted candidate bytes remain unchanged. An embedded whole-file hash would
be self-referential, so the exact `candidate_source_sha256` exists in the
receipt rather than being written back into the candidate.

The IDX does not make the Spine true. It proves that the declared admission
checks produced the recorded results. Rejection preserves the candidate and its
failure reasons.

## Compression rule

Compression is a derived operation performed after the uncompressed source is
preserved. A compressed Spine must identify its source Spine hash and list every
omitted class or unresolved boundary.

Compression may remove repetition. It must not remove attribution, state
separation, uncertainty, correction paths, ordering, or provenance.

## Template evolution

The template evolves through use. A new symbol, field, divider, or rule may be
proposed when a real collection or reconstruction loop exposes a missing
distinction.

Template evolution follows:

```text
observe structural failure
→ preserve the failing example
→ propose the smallest structural delta
→ test old and new examples
→ version the template
→ preserve the prior template
```

No observer may silently reinterpret an earlier artifact using a later template.

## What the structure can establish

The structure can establish that required labels, rails, boundaries, ordering,
and bindings are present or missing. Hashes can establish byte identity.

The structure cannot by itself establish:

- external truth,
- completeness of all possible knowledge,
- shared memory or identity,
- speaker honesty,
- authority to execute,
- or safety of an external action.

Those require separate evidence, verification, consequence, and authority
boundaries.

## Final invariant

> Store only what must survive, preserve who and which state supplied it, keep
> correction possible, and let the visible structure expose what is missing.
