| | }==============================================================|
| | █†█ Holo/Sim █†█ █†█ CORRECTION_TRIGGER_PROPOSAL █†█        |
| | }==============================================================|
| | DOCUMENT_TYPE: PROPOSED_FORMAL_MODEL                          |
| | STATUS: PROPOSED_NOT_IMPLEMENTED                              |
| | AUTHORITY: DESCRIPTIVE_ONLY                                   |
| | WRITE_AUTHORITY: NONE                                         |
| | DATE: 2026-07-14                                              |
| | }==============================================================|
| | PURPOSE                                                       |
| | Define when a completed environmental episode may make a      |
| | correction eligible for external review.                      |
| |                                                               |
| | This proposal does not grant acceptance, mutation, or merge   |
| | authority. It does not claim that correction can be reduced   |
| | to a universal scalar without an explicit measurement model.  |
| | }==============================================================|
| | CORE_DISTINCTION                                              |
| | Correction responds to demonstrated error, omission, or       |
| | contradiction.                                                |
| |                                                               |
| | Optimization seeks a preferred future without first proving   |
| | that the present state is defective.                          |
| |                                                               |
| | HOLO correction eligibility requires evidence of defect.      |
| | Desire for improvement alone is not a correction trigger.     |
| | }==============================================================|
| | SYMBOLS                                                       |
| | S_t       current verified state                              |
| | delta     proposed correction                                 |
| | S_t⊕delta candidate state; never acceptance by construction   |
| | B_t       environmental completion certificate               |
| | Omega_t   frozen evidence snapshot for the evaluation         |
| | V         completion-certificate verification                |
| | E         demonstrated defect measure                         |
| | E_min     minimum supported defect threshold                  |
| | L         correction-loss measure                             |
| | G         supported correction gain                           |
| | gamma     minimum meaningful gain threshold                   |
| | I         hard invariant predicate                            |
| | P         provenance-validity predicate                       |
| | H_t       explicit external acceptance record                |
| | }==============================================================|
| | ENVIRONMENT_COMPLETION_BOUNDARY                               |
| | The environment may declare that an observation episode has   |
| | ended or is complete enough to evaluate.                      |
| |                                                               |
| | Completion is an observation boundary. It is not proof of     |
| | truth, correction, acceptance, or write authority.            |
| |                                                               |
| | V(B_t, Omega_t) = 1 only when the completion certificate is   |
| | valid, traceable, and bound to the evaluated evidence.        |
| | }==============================================================|
| | FROZEN_EVIDENCE_BOUNDARY                                      |
| | The same Omega_t must be used to compare S_t and S_t⊕delta.   |
| |                                                               |
| | New evidence creates a new evaluation episode. It must not    |
| | silently change the scoring basis during a comparison.        |
| |                                                               |
| | Evidence hashes establish identity, not truth or sufficiency. |
| | }==============================================================|
| | CORRECTION_GAIN                                               |
| | Proposed definition:                                         |
| |                                                               |
| | G(S_t, delta, Omega_t) =                                      |
| |     L(S_t; Omega_t) - L(S_t⊕delta; Omega_t)                   |
| |                                                               |
| | G > 0 means the candidate has lower measured correction loss  |
| | under the same evidence snapshot.                             |
| |                                                               |
| | This comparison is meaningful only after L, its dimensions,   |
| | uncertainty, tolerances, and measurement procedures are       |
| | explicitly defined and tested.                               |
| | }==============================================================|
| | ELIGIBILITY_TRIGGER                                           |
| | A proposed correction is eligible for external review iff:    |
| |                                                               |
| | Eligible_t(delta) =                                           |
| |     V(B_t, Omega_t)                                           |
| |     AND E(S_t, Omega_t) >= E_min                              |
| |     AND G(S_t, delta, Omega_t) > gamma                        |
| |     AND I(S_t⊕delta, Omega_t) = 1                             |
| |     AND P(delta, Omega_t) = 1                                 |
| |                                                               |
| | Eligibility is an evaluator result.                           |
| | Eligibility remains accepted: false and write_authority: NONE.|
| | }==============================================================|
| | HARD_INVARIANT_PREDICATE                                      |
| | I represents constraints that may not be traded for a higher  |
| | correction score. Candidate dimensions include:              |
| |                                                               |
| | • stable artifact and anchor identity                        |
| | • verified append-only continuity                            |
| | • structured non-contradiction                               |
| | • explicit causal ordering                                   |
| | • source and evidence provenance                             |
| | • safety and authority separation                            |
| |                                                               |
| | The final set and its tests remain future implementation work.|
| | }==============================================================|
| | ACCEPTANCE_AND_COMMIT                                        |
| | Mutation requires a separate external acceptance record:      |
| |                                                               |
| | Commit_t(delta) = Eligible_t(delta) AND Valid(H_t)            |
| |                                                               |
| | H_t must identify the external reviewer and approval record.  |
| | The evaluator must not create, infer, or approve H_t.         |
| | }==============================================================|
| | VALID_CHAIN_EXTENSION                                        |
| | Append-only continuity does not mean an unchanged chain root. |
| | A valid accepted transition extends verified history:         |
| |                                                               |
| | Chain_(t+1) = Chain_t || receipt_t                            |
| | Verify(Chain_(t+1)) = 1                                      |
| |                                                               |
| | Tampering, truncation, invalid ancestry, or failed replay is  |
| | a hard failure.                                               |
| | }==============================================================|
| | POST_MUTATION_VERIFICATION                                   |
| | After an externally accepted mutation, calculate:             |
| |                                                               |
| | G_actual = L(S_t; Omega_t) - L(S_(t+1); Omega_t)              |
| |                                                               |
| | The receipt must record the before state, proposal, evidence,  |
| | external authority, resulting state, and measured outcome.     |
| |                                                               |
| | If hard invariants fail or supported gain is not observed, the |
| | result is flagged or quarantined. No silent success is allowed.|
| | }==============================================================|
| | MONOTONICITY_LIMIT                                            |
| | No global claim is made that every future state is objectively |
| | more corrected than every past state.                         |
| |                                                               |
| | New evidence may reveal that an earlier score was incomplete.  |
| | Non-worsening comparisons are defensible only relative to the   |
| | same evidence snapshot, declared metrics, and tolerances.       |
| | }==============================================================|
| | VECTOR_LOSS_RECOMMENDATION                                    |
| | A single correction score may hide harmful tradeoffs.         |
| | Prefer a declared loss vector such as:                        |
| |                                                               |
| | L = [identity_drift, continuity_loss, contradiction_count,    |
| |      provenance_uncertainty, causal_invalidity, safety_risk]  |
| |                                                               |
| | Hard invariant dimensions remain constraints, not weights that |
| | may be exchanged for improvement elsewhere.                   |
| | }==============================================================|
| | OPERATIONAL_SEQUENCE                                         |
| | 1. Environment closes an observation episode.                |
| | 2. Evidence snapshot and completion certificate are frozen.   |
| | 3. A defect, omission, or contradiction is demonstrated.      |
| | 4. A proposed delta is evaluated without mutation.            |
| | 5. Eligibility and uncertainty are reported.                  |
| | 6. External authority accepts or rejects the proposal.        |
| | 7. An accepted proposal mutates through a guarded path.       |
| | 8. Actual outcome and invariant preservation are verified.    |
| | 9. A receipt is appended; failure remains visible.            |
| | }==============================================================|
| | NON_CLAIMS                                                    |
| | • This proposal is not a proof of recursive-system safety.   |
| | • Environmental completion is not environmental truth.      |
| | • A positive predicted gain is not external acceptance.      |
| | • A hash is not evidence sufficiency.                        |
| | • Free-text semantic understanding is not assumed.          |
| | • L, E, thresholds, and tolerances are not yet implemented.  |
| | }==============================================================|
| | IMPLEMENTATION_PREREQUISITES                                 |
| | Before runtime implementation:                               |
| |                                                               |
| | • define a versioned completion-certificate schema           |
| | • define the frozen evidence snapshot schema                 |
| | • define measurable defect and loss dimensions               |
| | • define uncertainty and threshold calibration procedures    |
| | • define eligibility and postcondition receipts              |
| | • add adversarial and rollback-path tests                    |
| | • retain explicit external acceptance authority              |
| | }==============================================================|
| | STATUS_SUMMARY                                               |
| | FORMAL_MODEL: PROPOSED                                       |
| | RUNTIME_IMPLEMENTATION: NONE                                 |
| | EMPIRICAL_CALIBRATION: NONE                                  |
| | WRITE_AUTHORITY: NONE                                        |
| | }==============================================================|
| | END_CORRECTION_TRIGGER_PROPOSAL                              |
| | }==============================================================|