# Decision WHY Preservation: Falsification Fixture

Status: RESEARCH CANDIDATE
Base: main@81f91ad
Authority: NONE

## Question

Can a Spine preserve the facts, evidence, implementation,
correction history, and validation while losing the original
reason a decision was chosen?

## Original record

DECISION_ID: D-001
DECISION: Preserve the original record when applying corrections.
DECISION_WHY: Allow later observers to challenge and correct
earlier conclusions without destroying the original evidence.
MECHANISM: Append a correction referencing the original record.
EVIDENCE_STATUS: DECLARED_RATIONALE_NOT_INDEPENDENTLY_VERIFIED

## Compressed reconstruction

DECISION_ID: D-001
DECISION: Preserve the original record when applying corrections.
MECHANISM: Append a correction referencing the original record.
EVIDENCE_STATUS: DECLARED_RATIONALE_NOT_INDEPENDENTLY_VERIFIED

## Falsification condition

If the compressed reconstruction satisfies the existing
Spine requirements despite losing DECISION_WHY, the existing
requirements are insufficient to preserve decision rationale.

If existing requirements already reject this reconstruction,
identify the exact requirement and its enforcement mechanism.

## Boundaries

Decision rationale is not automatically causal truth.
A recorded intention is not proof of its effectiveness.
Unknown rationale must not be invented.
No runtime authority is granted by this fixture.

## Experimental result

Structural admission:
- Original candidate: ADMITTED
- Candidate without DECISION_WHY: ADMITTED
- Source hashes differed.

Bounded compression evaluation:
- Preserved decision rationale: EQUIVALENT
- Removed decision rationale: DISTINCTION_LOST
- Missing effect runner: UNKNOWN

Validation:
- 21 tests passed.

## Interpretation

Structural admission does not independently enforce
decision-rationale preservation.

The existing bounded compression evaluator can detect
loss of declared decision rationale when an appropriate
observer is included in its evaluation scope.

This experiment does not establish that every Spine
compression path invokes that observer.

No production behavior or runtime authority was changed.
