# INV Language Research

> **WORK IN PROGRESS**

INV is an experimental programming-language research project.

Its syntax, semantics, invariants, execution model, and name remain subject to correction as implementation and testing expose contradictions.

Nothing in this document is a finalized language specification. Claims become stable only to the extent that they survive implementation, testing, and independent verification.

## Initial Research Question

Can a programming language make explicit, checkable invariants and justified state transitions first-class parts of execution rather than conventions imposed only by surrounding software?

## Current Status

UNRESOLVED

No implementation claim is established by this document.

## Experiment 001: Invariant-Gated Transition

### Question

Can INV reject a proposed state transition when that transition violates an explicitly declared invariant?

### Minimum Concepts

- `state` — the current value being operated on.
- `invariant` — a condition that must remain satisfied.
- `transition` — a proposed change from one state to another.

### Required Behavior

Given a valid current state and a proposed transition:

1. Evaluate the proposed resulting state.
2. Check the declared invariant against that result.
3. Accept the transition only if the invariant remains satisfied.
4. Reject the transition if the invariant would be violated.

### Falsifiable Boundary

The experiment fails if INV accepts a transition that violates the declared invariant.

The experiment also fails if rejection depends on application-specific code rather than the INV execution mechanism itself.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- The minimal INV runtime rejected a proposed state that violated its declared invariant.
- The rejected transition preserved the previous valid state.
- An invalid starting state failed closed.
- `tests/test_inv_runtime.py`: 3 passed.
- Full repository suite: 3482 passed, 5 skipped.

This establishes only the behavior required by Experiment 001. It does not establish INV as a complete programming language or settle the broader research question.

## Experiment 002: Native INV Source Representation

### Question

Can the behavior established by Experiment 001 be expressed as INV source text without expressing the program in Python syntax?

### Minimum Source Concepts

The source representation must be able to declare:

- an initial `state`
- an `invariant`
- a proposed `transition`

### Initial Candidate Form

    state 5
    invariant state >= 0
    transition -1

This syntax is provisional and exists only to make the experiment executable. It is not a finalized INV syntax.

### Required Behavior

Given the candidate program above:

1. Parse the INV source into a bounded internal representation.
2. Establish the initial state as `5`.
3. Evaluate the declared invariant `state >= 0`.
4. Evaluate the proposed transition to `-1`.
5. Reject that transition because the resulting state violates the invariant.
6. Preserve the previous valid state as `5`.

### Falsifiable Boundary

The experiment fails if the INV source cannot be interpreted without using Python syntax as the source language.

The experiment fails if the proposed transition to `-1` is accepted.

The experiment fails if rejection does not preserve the previous valid state.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- INV source text was parsed without using Python syntax as the source language.
- The source declared an initial state, invariant, and proposed transition.
- The proposed transition from `5` to `-1` was rejected because it violated `state >= 0`.
- Rejection preserved the previous valid state as `5`.
- A transition preserving the invariant was accepted.
- Unsupported invariant syntax failed closed.
- INV runtime and source tests: 7 passed.
- Repository integration contracts: 33 passed.
- Full repository suite: 3486 passed, 5 skipped.

This establishes only the bounded native source behavior required by Experiment 002. The parser currently supports only the deliberately restricted syntax exercised by this experiment. It does not establish INV as a complete programming language.

## Experiment 003: Native Invariant Semantics

### Question

Can an INV invariant remain an explicit INV semantic object through execution rather than being converted into an arbitrary host-language callable?

### Required Behavior

Given an INV program containing:

    state 5
    invariant state >= 0
    transition -1

1. Parse the invariant into an explicit bounded INV representation.
2. Preserve the invariant representation through execution.
3. Evaluate the invariant using INV runtime semantics.
4. Reject the proposed transition to `-1`.
5. Preserve the previous valid state as `5`.
6. Do not require an arbitrary Python callable to express the invariant.

### Falsifiable Boundary

The experiment fails if execution requires converting the parsed invariant into an arbitrary host-language callback.

The experiment fails if unsupported invariant semantics are silently accepted or delegated to host-language evaluation.

The experiment fails if a violating transition is accepted or alters the previous valid state.

### Scope

Experiment 003 does not require a general expression language. The only required invariant semantic is the bounded greater-than-or-equal comparison already exercised by Experiment 002.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- The parser represented the declared invariant as an explicit INV semantic object.
- The invariant remained non-callable through parsing and execution.
- INV runtime semantics evaluated the supported greater-than-or-equal invariant directly.
- The proposed transition from `5` to `-1` was rejected.
- Rejection preserved the previous valid state as `5`.
- An invalid current state failed closed.
- An unsupported invariant semantic failed closed rather than being delegated to host-language evaluation.
- Targeted INV tests: 12 passed.
- Full repository suite: 3491 passed, 5 skipped.

This establishes only the bounded native invariant semantic required by Experiment 003. It does not establish a general INV expression system or a complete programming language.

## Experiment 004: Native Transition Semantics

### Question

Can INV represent a state transition as an explicit semantic operation, evaluate its proposed consequence, and check that consequence against an INV invariant before state changes?

### Required Behavior

Given an INV program containing:

    state 5
    invariant state >= 0
    transition subtract 6

1. Parse the transition into an explicit bounded INV semantic representation.
2. Preserve that transition representation through execution.
3. Evaluate the transition against the current state to produce a candidate state.
4. Evaluate the candidate state against the existing INV invariant semantic.
5. Reject the candidate state `-1` because it violates `state >= 0`.
6. Preserve the previous valid state as `5`.
7. Do not require an arbitrary host-language callable to express the transition.

### Falsifiable Boundary

The experiment fails if the parsed transition must be converted into an arbitrary host-language callback before execution.

The experiment fails if unsupported transition semantics are silently accepted or delegated to host-language evaluation.

The experiment fails if the transition mutates committed state before invariant validation.

The experiment fails if rejection does not preserve the previous valid state.

### Scope

Experiment 004 does not require a general expression or arithmetic system. The only required transition semantic is bounded integer subtraction.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- The parser represented bounded integer subtraction as an explicit INV transition semantic object.
- The transition representation remained non-callable through parsing and execution.
- INV runtime semantics evaluated the transition against the current state to produce a candidate state.
- `state 5` with `transition subtract 6` produced candidate state `-1` without mutating the committed state.
- The existing INV invariant semantic rejected candidate state `-1` against `state >= 0`.
- Rejection preserved the previous valid state as `5`.
- A valid subtraction transition was accepted and committed its candidate state.
- Unsupported transition source failed closed.
- An unsupported transition semantic failed closed rather than being delegated to host-language evaluation.
- Targeted INV tests: 19 passed.
- Full repository suite: 3498 passed, 5 skipped.

This establishes only the bounded native subtraction transition semantic required by Experiment 004. It does not establish a general arithmetic system, expression system, or complete programming language.

## Experiment 005: Unified Transition Semantics

### Question

Can every accepted INV transition declaration be represented and executed through one explicit transition-semantic path without a separate raw proposed-state execution path?

### Required Behavior

Given the existing INV programs:

    state 5
    invariant state >= 0
    transition -1

and:

    state 5
    invariant state >= 0
    transition subtract 6

1. Parse `transition -1` into an explicit bounded replacement-transition semantic.
2. Continue parsing `transition subtract 6` into its explicit subtraction-transition semantic.
3. Represent both declarations through the same transition field in the parsed INV program.
4. Evaluate both transition semantics through the same bounded transition-evaluation path.
5. Produce candidate state `-1` for both programs.
6. Reject both candidates against `state >= 0`.
7. Preserve the previous valid state as `5`.
8. Preserve the observable behavior established by the earlier experiments.

### Falsifiable Boundary

The experiment fails if an accepted transition declaration remains represented as a raw proposed state outside the explicit transition-semantic model.

The experiment fails if execution requires separate semantic and raw proposed-state transition paths.

The experiment fails if unifying the representation changes the established accept, reject, candidate-state, or preserved-state behavior.

The experiment fails if unsupported transition semantics are silently accepted or delegated to arbitrary host-language evaluation.

### Scope

Experiment 005 does not add new arithmetic operators or a general expression system. It only tests whether the two transition forms already established by earlier experiments can share one explicit semantic representation and execution path.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- `transition -1` is represented as an explicit `ReplaceTransition` semantic rather than a raw proposed-state field.
- `transition subtract 6` remains represented as an explicit `SubtractTransition` semantic.
- Both accepted transition forms are carried through the same `INVProgram.transition` field.
- Both transition forms are evaluated through the same bounded `evaluate_transition` semantic path.
- Both forms produce candidate state `-1` from the bounded test programs.
- Both candidates are rejected against `state >= 0` while preserving previous valid state `5`.
- Valid replacement transitions remain accepted through the unified native path.
- Unsupported transition semantics continue to fail closed.
- The legacy `proposed_state` field is no longer part of `INVProgram`.
- Targeted INV suite: 27 passed.
- Full repository suite: 3506 passed, 5 skipped.

This establishes only that the two transition forms already introduced by earlier experiments can share one explicit transition-semantic representation and execution path. It does not establish a general transition algebra, arithmetic system, expression system, or complete programming language.

## Experiment 006: Transition Decision Receipt

### Question

Can INV execution produce a bounded receipt that preserves the semantic transition, candidate state, invariant, decision, and resulting state needed to independently check why a transition was accepted or rejected?

### Required Behavior

Given:

    state 5
    invariant state >= 0
    transition subtract 6

1. Execute the existing bounded INV semantics.
2. Produce an explicit receipt containing the previous state.
3. Preserve the explicit transition semantic that produced the candidate state.
4. Preserve the candidate state produced by that transition.
5. Preserve the explicit invariant semantic used to gate the candidate.
6. Preserve the accept or reject decision.
7. Preserve the resulting committed state.
8. Permit a bounded independent verification step to recompute the candidate and invariant decision from the receipt.
9. Reject a receipt whose recorded candidate, decision, or resulting state does not match recomputation.

### Falsifiable Boundary

The experiment fails if the receipt records only the final decision without the semantics needed to recheck it.

The experiment fails if verification requires hidden execution state or arbitrary host-language callbacks.

The experiment fails if a changed candidate state, decision, or resulting state can pass verification when it contradicts recomputation from the preserved transition and invariant semantics.

The experiment fails if producing the receipt changes the established execution behavior.

### Scope

Experiment 006 tests only a bounded in-memory decision receipt for the existing INV state, invariant, and transition semantics. It does not establish serialization, cryptographic integrity, durable provenance, multi-step replay, distributed verification, or a complete programming language.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- Execution can produce an explicit bounded `TransitionDecisionReceipt`.
- The receipt preserves the previous state, explicit transition semantic, candidate state, explicit invariant semantic, accept or reject decision, and resulting committed state.
- Receipt production reuses the established INV execution path rather than introducing a second transition executor.
- `verify_transition_receipt` independently recomputes the candidate state from the preserved transition semantic and previous state.
- Verification independently reevaluates the preserved invariant against the previous state and candidate state.
- A valid receipt verifies successfully.
- A changed candidate state fails verification.
- A changed accept or reject decision fails verification.
- A changed resulting state fails verification.
- A changed transition semantic that contradicts the recorded candidate fails verification.
- A changed invariant semantic that contradicts the recorded decision fails verification.
- Unsupported receipt types fail closed.
- Existing INV execution behavior remains preserved.
- Targeted INV suite: 36 passed.
- Full repository suite: 3515 passed, 5 skipped.

This establishes only a bounded in-memory transition decision receipt and independent semantic recomputation for the existing INV semantics. It does not establish serialization, cryptographic integrity, durable provenance, multi-step replay, distributed verification, or a complete programming language.

## Experiment 007: Receipt Serialization and Reconstruction

### Question

Can a valid INV transition decision receipt be converted into a bounded, host-independent data representation and reconstructed without losing the semantics required for independent verification?

### Required Behavior

Given a valid transition decision receipt produced from:

    state 5
    invariant state >= 0
    transition subtract 6

1. Convert the receipt into a bounded data representation containing no live Python semantic objects.
2. Preserve the previous state.
3. Preserve the transition kind and its bounded semantic data.
4. Preserve the candidate state.
5. Preserve the invariant kind and its bounded semantic data.
6. Preserve the accept or reject decision.
7. Preserve the resulting committed state.
8. Reconstruct a new TransitionDecisionReceipt from that representation.
9. Verify the reconstructed receipt using the existing independent receipt verifier.
10. Preserve equivalent verification behavior for the existing replacement and subtraction transition semantics.

### Falsifiable Boundary

The experiment fails if reconstruction depends on retaining the original in-memory receipt or semantic objects.

The experiment fails if supported transition or invariant semantics cannot be distinguished after representation.

The experiment fails if reconstructed semantics differ from the semantics originally recorded.

The experiment fails if malformed, missing, extra, or unsupported semantic data is silently accepted.

The experiment fails if a reconstructed receipt that contradicts recomputation can pass the existing receipt verifier.

The experiment fails if serialization or reconstruction changes established INV execution behavior.

### Scope

Experiment 007 tests only bounded representation and reconstruction of the existing INV transition decision receipt semantics. It does not establish durable storage, cryptographic integrity, authenticity, provenance, schema evolution, multi-step replay, distributed verification, or a complete programming language.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- A bounded transition decision receipt can be converted into plain data containing no live INV semantic objects.
- Replacement and subtraction transitions preserve distinct explicit transition kinds and bounded semantic values.
- The existing greater-than-or-equal invariant preserves its explicit kind and minimum value.
- Previous state, candidate state, decision, and resulting committed state survive representation and reconstruction.
- Reconstruction creates a new TransitionDecisionReceipt without retaining the original receipt object.
- Reconstructed receipts preserve the original bounded INV semantics.
- Reconstructed valid receipts pass the existing independent receipt verifier.
- Missing receipt fields fail closed.
- Extra receipt fields fail closed.
- Missing transition or invariant fields fail closed.
- Unsupported transition and invariant kinds fail closed.
- Invalid decision types fail closed.
- A structurally reconstructable receipt containing a contradictory candidate remains rejected by the existing semantic verifier.
- Representation and reconstruction do not replace semantic verification or treat reconstructed data as authority.
- Targeted receipt suite: 20 passed.
- Full repository suite: 3526 passed, 5 skipped.

This establishes only bounded plain-data representation and reconstruction for the existing INV transition decision receipt semantics. It does not establish durable storage, cryptographic integrity, authenticity, provenance, schema evolution, multi-step replay, distributed verification, or a complete programming language.

## Experiment 008: Canonical Receipt Encoding

### Question

Can equivalent INV transition decision receipts produce exactly the same canonical byte representation, independent of object identity or mapping insertion order, and can those bytes reconstruct a receipt that still passes semantic verification?

### Required Behavior

Given equivalent valid transition decision receipts:

1. Convert each receipt through the existing bounded plain-data representation.
2. Encode that representation into a deterministic canonical byte sequence.
3. Equivalent receipt semantics must produce exactly identical canonical bytes.
4. Mapping insertion order must not change the canonical bytes.
5. The encoding must contain only the bounded data established by Experiment 007.
6. Decode canonical bytes back into bounded plain data.
7. Reconstruct a new TransitionDecisionReceipt using the existing reconstruction path.
8. Verify the reconstructed receipt using the existing semantic verifier.
9. Preserve equivalent behavior for replacement and subtraction transition semantics.
10. Malformed or unsupported encoded input must fail closed.

### Falsifiable Boundary

The experiment fails if equivalent receipt semantics can produce different canonical bytes because of object identity or mapping insertion order.

The experiment fails if decoding requires retaining the original receipt, plain-data object, or live semantic objects.

The experiment fails if encoding or decoding introduces semantic fields not established by the existing bounded representation.

The experiment fails if malformed or unsupported encoded input is silently accepted.

The experiment fails if a decoded and reconstructed valid receipt cannot pass the existing semantic verifier.

The experiment fails if canonical encoding changes established INV execution, receipt, representation, reconstruction, or verification behavior.

### Scope

Experiment 008 tests only deterministic canonical byte encoding and decoding of the bounded receipt representation established by Experiment 007. It does not establish durable storage, cryptographic integrity, authenticity, provenance, schema evolution, multi-step replay, distributed verification, or a complete programming language.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- Existing bounded receipt data can be encoded as deterministic canonical UTF-8 JSON bytes.
- Equivalent independently created receipts produce identical canonical bytes.
- Mapping insertion order does not change the canonical byte representation.
- Replacement and subtraction transition semantics survive canonical encoding, decoding, reconstruction, and semantic verification.
- Canonical decoding reconstructs only through the bounded plain-data representation established by Experiment 007.
- Decoding does not depend on retaining the original receipt, plain-data object, or live semantic objects.
- Empty, malformed, non-mapping, incomplete, unsupported, and invalid UTF-8 encoded inputs fail closed.
- Structurally valid but noncanonical JSON bytes fail closed.
- Changed bounded semantic data produces different canonical bytes.
- Canonical encoding does not confer semantic validity: a contradictory but structurally valid receipt can be canonically encoded and reconstructed while remaining rejected by the existing semantic verifier.
- Targeted INV receipt chain: 33 passed.
- Full repository suite: 3539 passed, 5 skipped.

This establishes only deterministic canonical byte encoding and decoding of the bounded receipt representation established by Experiment 007. It does not establish durable storage, cryptographic integrity, authenticity, provenance, schema evolution, multi-step replay, distributed verification, or a complete programming language.

## Experiment 009: Canonical Receipt Content Identity

### Question

Can INV derive a deterministic content identifier from canonical receipt bytes and use that identifier to detect any change to the canonical receipt representation without treating the identifier as semantic validity or authority?

### Required Behavior

Given canonical receipt bytes established by Experiment 008:

1. Derive a deterministic content identifier from the exact canonical bytes.
2. Equivalent canonical receipt bytes must produce exactly the same content identifier.
3. Changed canonical receipt bytes must produce a different content identifier.
4. Verify canonical receipt bytes against an expected content identifier.
5. Matching bytes and identifier must verify successfully.
6. Changed bytes against the prior identifier must fail verification.
7. A changed identifier against unchanged bytes must fail verification.
8. Content identity must operate on the canonical bytes established by Experiment 008 rather than independently re-encoding arbitrary structures.
9. Content-identity verification must remain separate from receipt semantic verification.
10. A semantically contradictory but structurally valid canonical receipt may have a valid content identifier while still failing the existing semantic verifier.

### Falsifiable Boundary

The experiment fails if equivalent canonical bytes can produce different content identifiers.

The experiment fails if changed canonical bytes can verify against the identifier of the prior bytes.

The experiment fails if a changed identifier can verify against unchanged canonical bytes.

The experiment fails if content identity depends on object identity, mapping insertion order, or noncanonical representation.

The experiment fails if matching content identity is treated as proof of semantic validity, authenticity, provenance, authorization, or origin.

The experiment fails if content-identity behavior changes established INV execution, receipt, reconstruction, canonical encoding, or semantic verification behavior.

### Scope

Experiment 009 tests only deterministic content identity and mismatch detection for the canonical receipt bytes established by Experiment 008. It does not establish authenticity, authorization, origin, provenance, durable storage, trusted publication, schema evolution, multi-step replay, distributed verification, or a complete programming language.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- Exact canonical receipt bytes can be assigned a deterministic SHA-256 content identifier.
- Equivalent canonical receipt bytes produce identical content identifiers.
- Changed canonical receipt bytes produce different content identifiers.
- Canonical bytes verify successfully against their matching expected content identifier.
- Changed canonical bytes fail verification against the prior content identifier.
- A changed content identifier fails verification against unchanged canonical bytes.
- Malformed content identifiers and unsupported input types fail closed.
- Content identity operates directly on the exact canonical bytes established by Experiment 008 and does not independently re-encode receipt structures.
- Content-identity verification remains separate from receipt semantic verification.
- A semantically contradictory but structurally valid canonical receipt can have a matching content identifier while still failing the existing semantic verifier.
- Matching content identity therefore establishes only identity of the checked byte content relative to the expected identifier. It does not establish semantic validity, authenticity, provenance, authorization, or origin.
- Targeted INV receipt chain: 46 passed.
- Full repository suite: 3552 passed, 5 skipped.

This establishes only deterministic content identity and mismatch detection for the canonical receipt bytes established by Experiment 008. It does not establish authenticity, authorization, origin, provenance, durable storage, trusted publication, schema evolution, multi-step replay, distributed verification, or a complete programming language.

## Experiment 010: Content-Bound Receipt Record

### Question

Can INV preserve canonical receipt bytes together with their derived content identifier as one bounded record, then reject reconstruction when either component no longer agrees with the other?

### Required Behavior

Given canonical receipt bytes and deterministic content identity established by Experiments 008 and 009:

1. Construct a bounded record containing the exact canonical receipt bytes and their derived content identifier.
2. The stored content identifier must be derived from the stored canonical bytes.
3. Verify the binding between the stored canonical bytes and stored content identifier.
4. An unchanged record must pass content-binding verification.
5. Changed canonical bytes with the prior content identifier must fail verification.
6. A changed content identifier with unchanged canonical bytes must fail verification.
7. A valid bound record must reconstruct the receipt through the existing canonical decoding path.
8. Receipt semantic verification must remain separate from content-binding verification.
9. A semantically contradictory but structurally valid canonical receipt may form a valid content-bound record while still failing the existing semantic verifier.
10. The record must not claim authenticity, authorization, provenance, origin, or trusted publication.

### Falsifiable Boundary

The experiment fails if canonical receipt bytes and their content identifier are not preserved together in one bounded record.

The experiment fails if changed bytes can remain valid against the prior stored content identifier.

The experiment fails if a changed stored content identifier can remain valid against unchanged bytes.

The experiment fails if reconstruction bypasses the canonical decoding boundary established by Experiment 008.

The experiment fails if content-binding verification is treated as semantic verification.

The experiment fails if a valid bound record is treated as evidence of authenticity, authorization, provenance, origin, or trusted publication.

The experiment fails if established INV execution, receipt, reconstruction, canonical encoding, content identity, or semantic verification behavior changes.

### Scope

Experiment 010 tests only bounded preservation and rechecking of the relationship between canonical receipt bytes and their deterministic content identifier. It does not establish authenticity, authorization, provenance, origin, trusted publication, durable storage, signatures, schema evolution, multi-step replay, distributed verification, or a complete programming language.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- Exact canonical receipt bytes and their derived content identifier can be preserved together in one bounded record.
- The content identifier stored by the binding operation is derived from the exact stored canonical bytes.
- An unchanged bound record passes content-binding verification.
- Changed canonical bytes with the prior content identifier fail content-binding verification.
- A changed content identifier with unchanged canonical bytes fails content-binding verification.
- A record with a failed content binding is rejected before receipt reconstruction.
- A valid bound record reconstructs through the canonical decoding path established by Experiment 008.
- Content-binding verification remains separate from receipt semantic verification.
- A semantically contradictory but structurally valid canonical receipt can form a valid content-bound record, reconstruct successfully, and still fail the existing semantic verifier.
- A valid content binding therefore establishes only agreement between the stored canonical bytes and stored content identifier. It does not establish semantic validity, authenticity, authorization, provenance, origin, or trusted publication.
- Targeted INV receipt chain: 56 passed.
- Full repository suite: 3562 passed, 5 skipped.

This establishes only bounded preservation and rechecking of the relationship between canonical receipt bytes and their deterministic content identifier. It does not establish authenticity, authorization, provenance, origin, trusted publication, durable storage, signatures, schema evolution, multi-step replay, distributed verification, or a complete programming language.

## Experiment 011: Bound Receipt Record Reconstruction

### Question

Can an INV content-bound receipt record be converted into bounded plain data and reconstructed by a later observer without access to the original in-memory record, while preserving its content binding?

### Required Behavior

Given the content-bound receipt record established by Experiment 010:

1. Convert a bound receipt record into bounded plain data containing its canonical receipt content and content identifier.
2. The plain representation must not contain live Python receipt, transition, invariant, or bound-record objects.
3. Reconstruct a new BoundReceiptRecord using only the bounded plain representation.
4. Reconstruction must not depend on access to the original in-memory BoundReceiptRecord.
5. An unchanged reconstructed record must preserve the exact receipt bytes and content identifier.
6. An unchanged reconstructed record must pass the existing content-binding verifier.
7. A reconstructed record must remain usable by the existing bound-receipt reconstruction path.
8. Changed serialized receipt content with the prior serialized content identifier must reconstruct as the stated record but fail the existing content-binding verifier.
9. A changed serialized content identifier with unchanged serialized receipt content must reconstruct as the stated record but fail the existing content-binding verifier.
10. Malformed, missing, extra, or unsupported representation fields must fail closed.
11. Record reconstruction must not confer semantic validity, authenticity, authorization, provenance, origin, or trusted publication.

### Falsifiable Boundary

The experiment fails if reconstruction requires the original in-memory BoundReceiptRecord or another hidden execution object.

The experiment fails if the bounded representation contains live INV semantic or receipt objects.

The experiment fails if reconstruction silently recomputes or repairs a mismatched stored content identifier instead of preserving the represented claim for verification.

The experiment fails if an unchanged reconstructed record does not preserve the exact content binding established before serialization.

The experiment fails if malformed, missing, extra, or unsupported representation data is silently accepted.

The experiment fails if reconstruction itself is treated as content-binding verification, semantic verification, authenticity, authorization, provenance, origin, or trusted publication.

The experiment fails if established INV behavior changes.

### Scope

Experiment 011 tests only bounded plain-data representation and reconstruction of the content-bound receipt record established by Experiment 010. It does not establish canonical encoding of the bound record, a content identity for the bound record itself, authenticity, authorization, provenance, origin, trusted publication, durable storage, signatures, schema evolution, multi-step replay, distributed verification, or a complete programming language.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- A content-bound receipt record can be converted into bounded plain data containing only hexadecimal receipt content and its content identifier.
- Reconstruction requires only that bounded representation and does not require access to the original in-memory BoundReceiptRecord.
- An unchanged reconstruction preserves the exact canonical receipt bytes and content identifier.
- An unchanged reconstructed record passes the existing content-binding verifier.
- A reconstructed record remains usable by the existing bound-receipt reconstruction path.
- Changed serialized receipt content with the prior content identifier is preserved as represented and subsequently fails content-binding verification.
- A changed serialized content identifier with unchanged receipt content is preserved as represented and subsequently fails content-binding verification.
- Reconstruction does not silently recompute, repair, or replace a mismatched content identifier.
- Malformed, missing, extra, non-hexadecimal, non-canonical hexadecimal, and unsupported representation data fail closed.
- Reconstruction remains separate from content-binding verification and semantic receipt verification.
- A represented contradiction can therefore survive reconstruction without being silently repaired, leaving correction authority downstream of independent verification.
- Targeted INV receipt chain: 74 passed.
- Full repository suite: 3580 passed, 5 skipped.

This establishes only bounded plain-data representation and reconstruction of a content-bound receipt record. It does not establish canonical encoding of the bound record, a content identity for the bound record itself, semantic validity, authenticity, authorization, provenance, origin, trusted publication, durable storage, signatures, schema evolution, multi-step replay, distributed verification, or a complete programming language.

## Experiment 012: Canonical Bound Receipt Record Encoding

### Question

Can equivalent INV content-bound receipt records produce exactly the same canonical byte representation, and can those bytes reconstruct the represented bound record without silently repairing or verifying its content binding?

### Required Behavior

Given the bounded plain-data representation established by Experiment 011:

1. Encode a supported bound receipt record representation into deterministic canonical bytes.
2. Equivalent bound receipt records must produce exactly identical canonical bytes.
3. Canonical encoding must not depend on mapping insertion order.
4. Canonical bytes must decode into the bounded plain-data representation established by Experiment 011.
5. Decoded data must reconstruct a new BoundReceiptRecord through the existing Experiment 011 reconstruction path.
6. Re-encoding decoded canonical data must reproduce the exact original canonical bytes.
7. Non-canonical byte representations of otherwise equivalent data must fail closed.
8. Malformed, unsupported, missing, or extra representation data must fail closed.
9. Canonical encoding and decoding must preserve a represented content-binding mismatch rather than silently repairing it.
10. Canonical encoding must remain separate from content-binding verification and semantic receipt verification.

### Falsifiable Boundary

The experiment fails if equivalent supported bound receipt records can produce different canonical bytes.

The experiment fails if mapping insertion order changes the canonical byte representation.

The experiment fails if decoding bypasses the bounded representation and reconstruction path established by Experiment 011.

The experiment fails if decoding silently recomputes, repairs, or replaces a represented content identifier.

The experiment fails if a non-canonical representation of otherwise equivalent data is accepted as canonical.

The experiment fails if canonical encoding or decoding is treated as content-binding verification, semantic verification, authenticity, authorization, provenance, origin, or trusted publication.

The experiment fails if established INV behavior changes.

### Scope

Experiment 012 tests only deterministic canonical byte encoding and decoding of the content-bound receipt record representation established by Experiment 011. It does not establish a content identity for the bound record itself, semantic validity, authenticity, authorization, provenance, origin, trusted publication, durable storage, signatures, schema evolution, multi-step replay, distributed verification, or a complete programming language.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- Equivalent supported content-bound receipt records produce exactly identical canonical byte representations.
- Mapping insertion order does not change the canonical byte representation.
- Canonical bytes decode into the bounded plain-data representation established by Experiment 011.
- Decoded canonical data reconstructs a new BoundReceiptRecord through the existing Experiment 011 reconstruction path.
- Decoding and re-encoding reproduces the exact original canonical bytes.
- Non-canonical byte representations of otherwise equivalent supported data fail closed.
- Malformed, unsupported, missing, and extra representation data fail closed.
- Canonical encoding and decoding preserve a represented content-binding mismatch rather than silently repairing it.
- A canonically encoded record with a mismatched content identifier reconstructs with that mismatch intact and subsequently fails the existing content-binding verifier.
- Canonicalization therefore normalizes representation without conferring content-binding validity or semantic validity.
- Targeted INV receipt chain: 96 passed.
- Full repository suite: 3602 passed, 5 skipped.

This establishes only deterministic canonical byte encoding and decoding of the content-bound receipt record representation established by Experiment 011. It does not establish a content identity for the bound record itself, semantic validity, authenticity, authorization, provenance, origin, trusted publication, durable storage, signatures, schema evolution, multi-step replay, distributed verification, or a complete programming language.

## Experiment 013: Canonical Bound Receipt Record Content Identity

### Question

Can INV derive a deterministic content identifier from canonical bound receipt record bytes and use that identifier to detect any change to the canonical record representation without treating that identifier as content-binding validity, semantic validity, authenticity, or authority?

### Required Behavior

Given canonical bound receipt record bytes established by Experiment 012:

1. Derive a deterministic content identifier from the exact canonical bound receipt record bytes.
2. Identical canonical bound receipt record bytes must produce exactly the same content identifier.
3. Changed canonical bound receipt record bytes must produce a different content identifier.
4. A matching expected content identifier must verify against unchanged canonical record bytes.
5. Changed canonical record bytes must fail verification against the prior content identifier.
6. A changed expected content identifier must fail verification against unchanged canonical record bytes.
7. Malformed expected content identifiers and unsupported input types must fail closed.
8. Content identity must apply to the canonical bound record representation as a whole, including both its represented receipt content and represented receipt content identifier.
9. A canonically encoded bound record containing an invalid inner content binding may still have a valid outer content identity.
10. Outer content identity must not confer inner content-binding validity, semantic receipt validity, authenticity, authorization, provenance, origin, or trusted publication.

### Falsifiable Boundary

The experiment fails if identical canonical bound receipt record bytes can produce different content identifiers.

The experiment fails if changed canonical bound receipt record bytes can retain the same identifier under the tested identity function.

The experiment fails if changed bytes verify against the prior content identifier.

The experiment fails if malformed identifiers or unsupported input types are silently accepted.

The experiment fails if outer content identity silently repairs or validates the inner receipt content binding.

The experiment fails if outer content identity is treated as semantic validity, authenticity, authorization, provenance, origin, or trusted publication.

The experiment fails if established INV behavior changes.

### Scope

Experiment 013 tests only deterministic content identity for the canonical bound receipt record bytes established by Experiment 012. It does not establish inner content-binding validity, semantic validity, authenticity, authorization, provenance, origin, trusted publication, durable storage, signatures, schema evolution, multi-step replay, distributed verification, or a complete programming language.

### Status

EXPERIMENTAL IMPLEMENTATION PASSED

Observed result:

- Identical canonical bound receipt record bytes produce exactly the same deterministic SHA-256 content identifier.
- A matching expected content identifier verifies against unchanged canonical bound receipt record bytes.
- Changed canonical bound receipt record bytes produce a different content identifier and fail verification against the prior identifier.
- A changed expected content identifier fails verification against unchanged canonical record bytes.
- Uppercase hexadecimal representation of the same expected identifier verifies equivalently.
- Malformed expected identifiers and unsupported input types fail closed.
- The outer content identity covers the canonical bound record representation as a whole, including its represented receipt content identifier.
- Changing the represented inner receipt content identifier changes the canonical bound record bytes and therefore changes the outer content identifier.
- A bound record with an invalid inner content binding can still possess and verify a valid outer content identity.
- Valid outer content identity does not repair or confer validity on the invalid inner content binding.
- Outer content identity therefore establishes identity of the canonical bound record bytes only; it does not establish inner content-binding validity or semantic validity.
- Targeted INV receipt chain: 115 passed.
- Full repository suite: 3621 passed, 5 skipped.

This establishes only deterministic content identity for the canonical bound receipt record bytes established by Experiment 012. It does not establish inner content-binding validity, semantic validity, authenticity, authorization, provenance, origin, trusted publication, durable storage, signatures, schema evolution, multi-step replay, distributed verification, or a complete programming language.
