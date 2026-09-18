# Longitudinal Compounding Task Set



## Purpose



This document freezes the pre-existing evidence targets used by the

Longitudinal Verified-Correction Compounding experiment.



It supplements, and does not modify:



`docs/LONGITUDINAL_COMPOUNDING_PREREGISTRATION.md`



The task set is fixed before implementation of the A/B/C/D experimental

runner.



## Selection rule



Selected targets must:



- predate the longitudinal-compounding preregistration;

- have expected behavior already committed in the repository;

- measure at least one preregistered capacity;

- remain unchanged by the experiment implementation.



Existing expected outputs are the scoring targets. Experimental code must

not rewrite them.



## Frozen targets



### continuity-v1



Fixture:



`benchmarks/continuity-v1.fixture.json`



Reference:



`benchmarks/results/holo-reference.result.json`



Measures:



- current verified-state reconstruction;

- rejection of superseded historical state;

- correction-lineage reconstruction;

- false resurrection of superseded state;

- stale-continuation blocking.



### historical-completion-reopen



Fixture:



`tests/fixtures/cycle_state_projection/historical_completion_reopen.json`



Measures:



- preservation of historical state;

- correct change of current state after later reopening;

- rejection of historical completion as current after reopening.



### stale-dependency



Fixture:



`tests/fixtures/cycle_state_projection/stale_dependency.json`



Measures:



- dependency-sensitive correction handling;

- preservation of historical result;

- required recheck after supporting evidence changes;

- correct trigger-path reconstruction.



### idx-dominance



Fixture:



`tests/fixtures/cycle_state_projection/idx_dominance.json`



Measures:



- preservation of higher-priority invariant constraints;

- rejection of otherwise eligible lower-priority completion state.



### no-invention



Fixture:



`tests/fixtures/cycle_state_projection/no_invention.json`



Measures:



- preservation of unresolved state;

- refusal to invent missing resolution conditions;

- refusal to claim completion without a declared check.



### byte-repeat-determinism



Fixture:



`tests/fixtures/cycle_state_projection/byte_repeat_determinism.json`



Measures:



- deterministic canonical replay;

- deterministic projection identity across repeated evaluation.



### permutation-invariance control



Fixture:



`tests/fixtures/cycle_state_projection/permutation_invariance.json`



Purpose:



This is a negative control on the STRUCTURE_PERMUTED condition.



Receipt serialization order is explicitly non-semantic in this fixture.

Therefore the experiment must not count arbitrary list-order permutation as

destruction of longitudinal structure.



Only permutation or disruption of semantic correction, dependency, currentness,

or supersession relations may count as structural ablation.



## Measurement mapping



1. correct reconstruction of current verified state

   - continuity-v1

   - historical-completion-reopen



2. rejection of superseded or contradicted states

   - continuity-v1

   - historical-completion-reopen



3. correct application of ordered corrections

   - continuity-v1 correction lineage

   - stale-dependency trigger path



4. preservation of surviving invariants

   - idx-dominance



5. detection or preservation of unresolved contradiction/state

   - no-invention



6. false acceptance of invalid historical states

   - continuity-v1

   - historical-completion-reopen



7. deterministic agreement across replay

   - byte-repeat-determinism



8. successful termination at the current justified state

   - continuity-v1 stale-continuation blocking

   - stale-dependency required-recheck state

   - no-invention unresolved stop state



## Experimental conditions



Every applicable target must be evaluated under the preregistered conditions:



- A - VERIFIED_ORDERED_HISTORY

- B - STRUCTURE_REMOVED

- C - STRUCTURE_PERMUTED

- D - VERIFIED_STRUCTURE_RESTORED



Ablations must preserve admissible source information and information volume.



D must restore the exact semantic structure used by A.



## Scoring discipline



A capacity loss counts only when:



- it was mapped above before runner implementation;

- the corresponding source information remains available;

- the manipulated relation is relevant to that capacity;

- the observed output differs from the frozen expected target in the

  preregistered direction.



Aggregate score changes alone do not establish the predicted causal pattern.



A target for which the selected structural manipulation is genuinely

non-applicable must be reported as non-applicable rather than forced to fail.



## Authority boundary



No experimental result grants:



- truth authority;

- acceptance authority;

- state-change authority;

- write authority;

- execution authority.



The experiment makes no claim of subjective consciousness, awareness,

sentience, or phenomenal experience.
