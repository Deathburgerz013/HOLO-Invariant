| | }==============================================================|
| | █†█ Holo/Sim █†█ █†█ ENVIRONMENT_CHECK_LOOP █†█             |
| | }==============================================================|
| | DOCUMENT_TYPE: PROPOSED_FORMAL_MODEL                          |
| | STATUS: PROPOSED_NOT_IMPLEMENTED                              |
| | AUTHORITY: DESCRIPTIVE_ONLY                                   |
| | WRITE_AUTHORITY: NONE                                         |
| | VERSION: 1.0.0-proposal                                      |
| | DATE: 2026-07-14                                              |
| | PARENT_MODELS:                                                |
| | • docs/Correction_Trigger_Proposal.md                         |
| | • docs/Environment_Completion_Certificate_Proposal.md        |
| | }==============================================================|
| | PURPOSE                                                       |
| | Define the read-only loop that turns an environmental check   |
| | into an immutable observation snapshot, searches within bounds|
| | for what may have been missed, compares observations over time,|
| | and selects the most useful next check.                       |
| |                                                               |
| | This loop may identify an eligible next action. It does not    |
| | accept, authorize, or perform that action.                     |
| | }==============================================================|
| | CORE_LOOP                                                     |
| |                                                               |
| | current goal                                                  |
| | -> identify decision-relevant unknowns                        |
| | -> select the smallest useful allowed check                   |
| | -> produce an immutable observation snapshot                 |
| | -> compare with compatible prior snapshots                   |
| | -> audit bounded missingness                                  |
| | -> update completion, uncertainty, and reopen state           |
| | -> propose an action only when evidence supports one          |
| | -> stop or ask when no useful check remains                   |
| | }==============================================================|
| | CHECK_RESULT_MODEL                                            |
| | Every completed check q_t produces one immutable snapshot:     |
| |                                                               |
| | X_t = (O_t, M_t, U_t, A_t)                                   |
| |                                                               |
| | O_t observed values and events                               |
| | M_t known missing required observations                      |
| | U_t unknown, ambiguous, censored, or unsupported information |
| | A_t assumptions used to interpret or compare the observation |
| |                                                               |
| | Missing, unknown, and assumed are first-class result fields.  |
| | They must not be silently collapsed into observed or false.   |
| | }==============================================================|
| | PROPOSED_SNAPSHOT_FIELDS                                      |
| | type: environment_observation_snapshot                        |
| | version: 1                                                    |
| | snapshot_id: SHA-256 of canonical snapshot fields             |
| | episode_id: stable identity of the observation episode        |
| | environment_id: stable identity of the environment            |
| | check_id: identity and version of the performed check         |
| | check_purpose: decision-relevant question being tested        |
| | goal_reference: goal or decision the check may inform         |
| | observer_ids: identities of sensors, tools, or observers      |
| | clock_id: identity and version of the observation clock       |
| | observed_at: declared observation time                        |
| | feature_schema_id: identity of the observation schema         |
| | observed: O_t                                                 |
| | missing: M_t                                                  |
| | unknown: U_t                                                  |
| | assumptions: A_t                                              |
| | falsifiers: evidence that would challenge the interpretation  |
| | evidence_sha256: ordered or canonical evidence identities     |
| | provenance: source, transformation, tool, branch, and commit  |
| | uncertainty: explicit uncertainty records                     |
| | accepted: false                                               |
| | write_authority: NONE                                         |
| | }==============================================================|
| | CHECK_SELECTION                                               |
| | Let Q_allowed be checks within user scope and hard invariants. |
| | For each candidate check q, define proposed utility:           |
| |                                                               |
| | U(q) =                                                        |
| |     DecisionRelevance(q)                                      |
| |     + ExpectedUncertaintyReduction(q)                         |
| |     + RiskAvoided(q)                                          |
| |     + DependencyUnblocked(q)                                  |
| |     - Cost(q)                                                  |
| |     - CheckRisk(q)                                             |
| |                                                               |
| | Select:                                                       |
| |                                                               |
| | q_star = argmax over q in Q_allowed of U(q)                   |
| |                                                               |
| | Utility estimates remain evidence-bound proposals, not facts. |
| | }==============================================================|
| | USEFULNESS_BOUNDARY                                           |
| | A check is useful only relative to a declared goal or decision.|
| | Curiosity, activity, novelty, and assistant preference do not  |
| | independently justify a check.                                |
| |                                                               |
| | A useful check should materially improve at least one of:      |
| |                                                               |
| | • decision-relevant evidence                                 |
| | • uncertainty resolution                                     |
| | • risk detection or avoidance                                |
| | • dependency resolution                                      |
| | • verification of an asserted postcondition                  |
| | }==============================================================|
| | READ_ONLY_PREFERENCE                                          |
| | Prefer a read-only, reversible, bounded check when it can      |
| | answer the decision-relevant question.                         |
| |                                                               |
| | A check that mutates the subject being measured must declare   |
| | that intervention and requires separate authority.             |
| | Observation must not be mislabeled read-only when measurement  |
| | materially changes the environment.                            |
| | }==============================================================|
| | BOUNDED_MISSINGNESS_AUDIT                                     |
| | Every check asks what relevant information may have been missed|
| | under a declared audit budget.                                |
| |                                                               |
| | AuditBudget_t may bound:                                      |
| |                                                               |
| | • elapsed time                                               |
| | • number of observations or queries                          |
| | • required surfaces or sources                               |
| | • compute, storage, or monetary cost                          |
| | • risk or intervention exposure                              |
| |                                                               |
| | Exhausting the budget does not prove that nothing was missed. |
| | It records the boundary of the performed search.              |
| | }==============================================================|
| | FALSIFICATION_ALLOWANCE                                       |
| | Each snapshot records what evidence would make its current     |
| | interpretation incomplete or wrong.                           |
| |                                                               |
| | A check should seek disconfirming evidence when that evidence  |
| | is decision-relevant, allowed, and within the audit budget.    |
| |                                                               |
| | Failure to find a falsifier is not proof that none exists.     |
| | }==============================================================|
| | COMPARISON_OVER_TIME                                          |
| | X_t may be compared only with snapshots compatible in:         |
| |                                                               |
| | • environment and episode identity                           |
| | • feature-schema version                                     |
| | • metric and unit definitions                                |
| | • clock and sampling policy                                  |
| | • evidence and provenance requirements                       |
| |                                                               |
| | Incompatible comparisons yield UNCERTAIN unless a verified     |
| | mapping exists.                                                |
| | }==============================================================|
| | COMPLETION_UPDATE                                             |
| | Compatible snapshots feed the proposed environment completion  |
| | certificate. Completion remains bounded sufficiency to evaluate|
| | under the declared window and contract.                        |
| |                                                               |
| | Completion is not certainty, truth, acceptance, or finality.   |
| | }==============================================================|
| | REOPEN_CONDITION                                              |
| | A completed episode is eligible to reopen when:                |
| |                                                               |
| | Reopen_(t+1) =                                                |
| |     NewRelevantEvidence                                       |
| |     OR CoverageGapDiscovered                                  |
| |     OR ContradictionDetected                                  |
| |     OR SchemaChanged                                          |
| |     OR CalibrationFailed                                      |
| |     OR RequiredSignalChanged                                  |
| |     OR PriorAssumptionInvalidated                             |
| |                                                               |
| | Reopening creates a new evaluation episode or version.         |
| | }==============================================================|
| | REVISION_VISIBILITY                                           |
| | A reopened or superseded result is never deleted or silently   |
| | rewritten. The new record references the earlier result using  |
| | an explicit relation such as:                                  |
| |                                                               |
| | corrects                                                      |
| | supersedes                                                    |
| | reopens                                                       |
| | resolves_uncertainty_from                                     |
| |                                                               |
| | The earlier result remains historically valid only relative to |
| | its recorded evidence, schema, assumptions, and uncertainty.   |
| | }==============================================================|
| | ALLOWANCE_TO_BE_WRONG                                         |
| | A later supported conclusion that an earlier result was wrong, |
| | incomplete, or overconfident is a valid correction outcome.    |
| |                                                               |
| | The invariant failure is not being wrong. The invariant failure|
| | is hiding error, erasing uncertainty, blocking supported       |
| | revision, or silently rewriting history.                       |
| | }==============================================================|
| | NEXT_ACTION_BOUNDARY                                          |
| | A useful check may support a proposed next action.              |
| | It does not authorize the action.                               |
| |                                                               |
| | proposal_t = ProposedAction(check_results, goal, uncertainty)   |
| | proposal_t.accepted = false                                    |
| | proposal_t.write_authority = NONE                              |
| |                                                               |
| | Irreversible action requires explicit external acceptance.      |
| | }==============================================================|
| | POST_ACTION_CHECK                                             |
| | After an externally accepted action, perform a bounded check of |
| | declared postconditions and unintended effects.                |
| |                                                               |
| | The post-action snapshot must remain separate from the proposal |
| | that predicted the outcome.                                    |
| |                                                               |
| | Failed or uncertain outcomes remain visible and may reopen the  |
| | episode or activate a correction proposal.                     |
| | }==============================================================|
| | STOPPING_RULE                                                 |
| | Let U_min be the minimum useful-check threshold.                |
| |                                                               |
| | If max over q in Q_allowed of U(q) <= U_min:                   |
| |                                                               |
| | • stop the autonomous check loop                              |
| | • preserve unresolved uncertainty                             |
| | • report why no check cleared the threshold                   |
| | • request external direction when needed                      |
| |                                                               |
| | The system must not manufacture work merely to remain active.  |
| | }==============================================================|
| | FAILURE_AND_UNCERTAINTY                                       |
| | Missing goal reference: stop and request direction             |
| | No allowed checks: stop and report boundary                    |
| | Utility cannot be supported: UNCERTAIN                         |
| | Snapshot identity failure: FAIL                                |
| | Incompatible comparison contract: UNCERTAIN                    |
| | Missing required observation: preserve in M_t                  |
| | Ambiguous observation: preserve in U_t                         |
| | Unsupported assumption: preserve in A_t and flag               |
| | }==============================================================|
| | OPERATIONAL_SEQUENCE                                          |
| | 1. Bind the current goal and authorized scope.                 |
| | 2. Enumerate decision-relevant unknowns.                       |
| | 3. Generate bounded allowed candidate checks.                  |
| | 4. Estimate utility and uncertainty for each candidate.        |
| | 5. Select the smallest highest-utility supported check.        |
| | 6. Execute the check within its declared budget.               |
| | 7. Emit an immutable O/M/U/A observation snapshot.             |
| | 8. Compare compatible snapshots over time.                     |
| | 9. Audit what may have been missed.                            |
| | 10. Update completion, reopen, and uncertainty state.          |
| | 11. Propose a next action only when justified.                 |
| | 12. Stop or request direction when no useful check remains.    |
| | }==============================================================|
| | IMPLEMENTATION_PREREQUISITES                                  |
| | Before runtime implementation:                                 |
| |                                                               |
| | • define canonical snapshot serialization and hashing         |
| | • define goal and decision-reference schemas                  |
| | • define missing, unknown, assumption, and falsifier records  |
| | • define bounded audit-budget schemas                         |
| | • define utility dimensions without collapsing hard invariants|
| | • define reopen and supersession receipts                     |
| | • create adversarial, stale, missingness, and stopping tests  |
| | }==============================================================|
| | NON_CLAIMS                                                    |
| | • A useful check is not necessarily a sufficient check.       |
| | • A stable environment is not necessarily a truthful one.     |
| | • Completion is not finality.                                 |
| | • Being previously wrong does not erase prior history.        |
| | • A proposed next action is not external acceptance.          |
| | • This loop is not yet implemented or calibrated.             |
| | }==============================================================|
| | STATUS_SUMMARY                                               |
| | FORMAL_MODEL: PROPOSED                                       |
| | RUNTIME_IMPLEMENTATION: NONE                                 |
| | EMPIRICAL_CALIBRATION: NONE                                  |
| | ACCEPTED: false                                              |
| | WRITE_AUTHORITY: NONE                                        |
| | }==============================================================|
| | END_ENVIRONMENT_CHECK_LOOP                                   |
| | }==============================================================|