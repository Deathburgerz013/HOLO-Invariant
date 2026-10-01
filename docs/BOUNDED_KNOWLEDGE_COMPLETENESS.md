# Bounded knowledge completeness experiment

This PARTIAL research experiment tests whether all answers in a finite scope
can be learned, rather than claiming universal knowledge or evaluating an LLM.
Run `python -m holosim.bounded_knowledge_completeness` for seven controls.

## Meaning and assumptions

A world is a deterministic Boolean function over 1, 2, or 3 input bits: exactly
2, 4, or 8 possible inputs. Every output is supplied by the simulator's caller.
“Complete for epoch” means every predicted output is correct, with no unknowns,
against that exact supplied table. This is an exhaustive audit, not a sample.
It says nothing about other question types, physical reality, or future epochs.

The investigator gets only the scope, candidate family, accessible query
indices, budget, and answers to its chosen queries. It does not receive the
world table or world hash. It chooses a query that best divides the remaining
candidates, filters by the observed answer, and predicts only unanimous values.
The separate auditor sees the table after investigation and checks all inputs.
Audit answers do not feed back into the learner.

FULL enumerates every Boolean function in the scope (at most 256 candidates).
AFFINE enumerates bias XOR parity of a selected subset of input bits. The latter
can infer unqueried answers if the world really belongs to that family. Its
agreement is conditional: a misspecified family can agree and be wrong.

## What the controls establish

- FULL with access and a budget for every input learns every supplied table.
- Limited budget or access leaves alternatives indistinguishable and unanswered.
- AFFINE learns its rules with at most n+1 separating observations, including
  correct predictions on withheld inputs under the declared family assumption.
- A non-affine world can produce the same query answers and defeat that inference.
- After a world change, a formerly complete model can fail the current audit.
- New queries can reveal a change and a fresh investigation can recover.
- A change at an unqueried input can escape query-based detection entirely.

Tests enumerate all 256 three-bit worlds and all 16 three-bit affine rules.
Finite exhaustive tests establish only these finite software behaviors. Reaching
all correct answers once does not prove that later observations can only add
compatible knowledge. Environmental changes can require revised conclusions.

## History and replay

One to four epochs are allowed, with the same scope and a budget of 0..8 per
epoch. Each starts with the declared family anew; this is an explicit controlled
relearning experiment, not automatic change-point inference. Original queries
remain in append-only history, labeled by epoch and linked by event hashes.
Earlier evidence is not erased or treated as observations of a later world.
The receipt also retains each epoch's predictions and exhaustive audit.

Change detection compares new query answers with the previous predictions;
it does not use the auditor's knowledge of a changed table. Null predictions
cannot establish a detected contradiction. An audit mismatch reports a wrong
model; correction uses new observations, never secretly supplies audit answers.

Replay regenerates from original tables and all controls, then compares canonical
bytes. Rehashing flags, predictions, history, or authority cannot pass that replay.
Hashes identify bytes; they do not authenticate the simulator's observations.
Receipts remain accepted=false, truth_claimed=false, with write and execution
authority NONE, even when a finite epoch audit is complete.

## Limits

No language model is tested. No general intelligence, universal completeness,
real-world observation, continuous domain, noise tolerance, theorem discovery,
open-world coverage, production memory update, or infinite-horizon guarantee
is established. An auditor with the entire finite table is a deliberate test
fixture, not a real-world oracle. This experiment demonstrates both achievable
finite completeness and failure of unsupported completeness claims.
