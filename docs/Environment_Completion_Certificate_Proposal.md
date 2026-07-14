| | }==============================================================|
| | █†█ Holo/Sim █†█ █†█ ENVIRONMENT_COMPLETION_CERTIFICATE █†█ |
| | }==============================================================|
| | DOCUMENT_TYPE: PROPOSED_SCHEMA                                |
| | STATUS: PROPOSED_NOT_IMPLEMENTED                              |
| | AUTHORITY: DESCRIPTIVE_ONLY                                   |
| | WRITE_AUTHORITY: NONE                                         |
| | VERSION: 1.0.0-proposal                                      |
| | DATE: 2026-07-14                                              |
| | PARENT_MODEL: docs/Correction_Trigger_Proposal.md             |
| | }==============================================================|
| | PURPOSE                                                       |
| | Define a versioned certificate showing that an ordered window |
| | of environmental observations is complete enough to evaluate  |
| | under declared features, metrics, thresholds, and uncertainty.|
| |                                                               |
| | The certificate grants evaluation eligibility only. It does   |
| | not establish truth, correction gain, acceptance, or mutation.|
| | }==============================================================|
| | CORE_MODEL                                                    |
| | Let X_t be the observed environment at time t.                |
| | Let phi_v be a versioned feature projection.                  |
| | Let d_v be a versioned distance function over phi_v(X).       |
| |                                                               |
| | For observation-window width w:                               |
| |                                                               |
| | W_t = [X_(t-w+1), ..., X_t]                                   |
| |                                                               |
| | Environmental change relative to the final observation:       |
| |                                                               |
| | D_t = max over X_i in W_t of d_v(phi_v(X_i), phi_v(X_t))      |
| | }==============================================================|
| | PROPOSED_COMPLETION_PREDICATE                                 |
| |                                                               |
| | Complete_t =                                                  |
| |     WindowValid(W_t)                                          |
| |     AND Coverage(W_t) >= coverage_min                         |
| |     AND D_t <= epsilon                                        |
| |     AND StableCount_t >= stable_count_min                     |
| |     AND UnresolvedRequiredSignals_t = empty                   |
| |     AND ProvenanceValid(W_t)                                  |
| |     AND UncertaintyBounded(W_t)                               |
| |                                                               |
| | Every term must be declared and observable. No missing term is|
| | inferred as passing.                                          |
| | }==============================================================|
| | COMPLETION_IS_NOT_TRUTH                                       |
| | A stable sensor may be consistently wrong.                    |
| | An unchanged environment may still be incompletely observed.  |
| | A selected feature projection may omit a relevant variable.   |
| | A low distance may result from an insensitive metric.         |
| |                                                               |
| | Therefore Complete_t means only:                              |
| |                                                               |
| | The declared observation window is complete enough to evaluate|
| | under this exact schema, evidence, metric, and tolerance.      |
| | }==============================================================|
| | CERTIFICATE_RESULT_STATES                                     |
| | COMPLETE_ELIGIBLE                                             |
| | All required predicates passed under the declared contract.   |
| | Evaluation may begin. Acceptance remains false.               |
| |                                                               |
| | INCOMPLETE                                                    |
| | At least one required predicate demonstrably failed.          |
| |                                                               |
| | UNCERTAIN                                                     |
| | Required data, provenance, calibration, or comparison support |
| | is missing, malformed, stale, or outside declared bounds.      |
| |                                                               |
| | No result state grants write authority.                       |
| | }==============================================================|
| | PROPOSED_CERTIFICATE_FIELDS                                   |
| | type: environment_completion_certificate                      |
| | version: 1                                                    |
| | certificate_id: deterministic SHA-256 of canonical fields     |
| | status: COMPLETE_ELIGIBLE | INCOMPLETE | UNCERTAIN            |
| | accepted: false                                               |
| | write_authority: NONE                                         |
| |                                                               |
| | episode_id: stable identity of the observed episode           |
| | environment_id: stable identity of the observed environment   |
| | observer_ids: ordered or canonicalized observer identities    |
| | clock_id: identity and version of the observation clock       |
| |                                                               |
| | window_start: first observation time                          |
| | window_end: final observation time                            |
| | observation_count: number of ordered observations             |
| | observation_hashes: ordered SHA-256 identities                |
| | evidence_snapshot_sha256: hash of the frozen evidence packet  |
| |                                                               |
| | feature_schema_id: identity and version of phi_v              |
| | distance_metric_id: identity and version of d_v               |
| | epsilon: maximum permitted declared distance                  |
| | observed_max_distance: measured D_t                           |
| |                                                               |
| | coverage_measure_id: declared coverage procedure              |
| | coverage_min: required minimum coverage                       |
| | observed_coverage: measured coverage                          |
| |                                                               |
| | stable_count_min: required consecutive stable comparisons     |
| | observed_stable_count: measured consecutive stable count      |
| | sampling_policy_id: sampling cadence and missing-sample rules |
| |                                                               |
| | required_signal_schema_id: declared required signals          |
| | unresolved_required_signals: explicit unresolved identifiers  |
| | uncertainty: explicit missing, weak, or ambiguous observations|
| | violations: explicit failed structural or metric predicates   |
| | provenance: source, tool, version, branch, and commit binding |
| | interpretation_notice: certificate limitation statement       |
| | }==============================================================|
| | ORDER_AND_TIME_REQUIREMENTS                                   |
| | Observation hashes preserve the evaluated order.              |
| | Observation times must be monotonic under the declared clock.  |
| | Duplicate observation identities must be explicitly handled.  |
| | Missing samples follow the versioned sampling policy.          |
| | Clock correction, drift, or reset remains visible.             |
| |                                                               |
| | Wall-clock ordering alone does not prove causal ordering.      |
| | }==============================================================|
| | FEATURE_PROJECTION_REQUIREMENTS                               |
| | phi_v must declare:                                           |
| |                                                               |
| | • included environmental features                            |
| | • excluded or unavailable features                           |
| | • units and normalization procedures                         |
| | • missing-value behavior                                     |
| | • categorical comparison behavior                            |
| | • schema and calibration version                             |
| |                                                               |
| | A certificate is not comparable across incompatible phi_v     |
| | versions unless an explicit verified mapping exists.          |
| | }==============================================================|
| | DISTANCE_METRIC_REQUIREMENTS                                  |
| | d_v must declare:                                             |
| |                                                               |
| | • input feature schema                                       |
| | • component distances                                        |
| | • aggregation behavior                                       |
| | • tolerances and units                                       |
| | • treatment of missing and censored values                   |
| | • calibration evidence                                       |
| |                                                               |
| | A convenient metric must not be treated as a universal metric.|
| | }==============================================================|
| | COVERAGE_REQUIREMENTS                                         |
| | Coverage must describe what portion of the required observation|
| | surface was actually observed.                                |
| |                                                               |
| | Stability with insufficient coverage yields UNCERTAIN, not     |
| | COMPLETE_ELIGIBLE.                                            |
| |                                                               |
| | Coverage thresholds must be schema-specific and versioned.     |
| | }==============================================================|
| | STABILITY_PERSISTENCE                                         |
| | D_t <= epsilon for one comparison is insufficient.             |
| | The predicate must persist for stable_count_min consecutive    |
| | comparisons under the same schema and sampling policy.         |
| |                                                               |
| | Oscillation, intermittent threshold crossing, or sample gaps   |
| | reset or qualify persistence according to declared policy.     |
| | }==============================================================|
| | REQUIRED_SIGNALS                                              |
| | Required signals represent observations that must be resolved  |
| | before an episode may be considered complete enough to judge.  |
| |                                                               |
| | Absence is not automatically resolution. Each signal must have |
| | an explicit observed, not-applicable, failed, or uncertain state.|
| | }==============================================================|
| | PROVENANCE_AND_EVIDENCE                                       |
| | Every observation and derived measure binds to source identity,|
| | evidence hash, tool version, and transformation procedure.     |
| |                                                               |
| | The certificate must bind the exact frozen evidence snapshot   |
| | used by the later correction-eligibility evaluation.           |
| |                                                               |
| | Recomputed certificates are new certificates. Prior results    |
| | remain visible and are not silently overwritten.               |
| | }==============================================================|
| | ANTI_REPLAY_AND_IDENTITY                                      |
| | certificate_id is derived from canonical certificate fields.   |
| | episode_id and evidence snapshot prevent cross-episode reuse.  |
| | Schema and metric versions prevent silent interpretation drift.|
| |                                                               |
| | Reuse under a different episode, evidence snapshot, or contract |
| | is invalid unless explicitly re-evaluated and recorded.         |
| | }==============================================================|
| | CONSUMER_RULE                                                 |
| | A correction evaluator may consume a certificate only when:    |
| |                                                               |
| | • its certificate identity verifies                          |
| | • status is COMPLETE_ELIGIBLE                                |
| | • the evidence snapshot hash matches exactly                 |
| | • the schema and metric versions are supported               |
| | • uncertainty remains within declared evaluator bounds       |
| |                                                               |
| | Consumption grants permission to evaluate only.                |
| | }==============================================================|
| | FAILURE_BEHAVIOR                                              |
| | Invalid identity or provenance: FAIL                          |
| | Demonstrated predicate failure: INCOMPLETE                    |
| | Missing or ambiguous required information: UNCERTAIN          |
| | Unsupported schema or metric: UNCERTAIN                       |
| | Evidence snapshot mismatch: FAIL                              |
| |                                                               |
| | No failure mode silently defaults to complete.                |
| | }==============================================================|
| | EXAMPLE_NON_NORMATIVE                                        |
| | An environment is sampled ten times under schema phi_1.       |
| | Nine required surfaces are observed and one remains missing.  |
| | All observed distances remain below epsilon.                  |
| |                                                               |
| | If required coverage includes the missing surface, the result |
| | is UNCERTAIN despite apparent stability.                       |
| | }==============================================================|
| | IMPLEMENTATION_PREREQUISITES                                  |
| | Before runtime implementation:                                |
| |                                                               |
| | • define canonical serialization and certificate hashing      |
| | • define initial feature, metric, and coverage schemas         |
| | • define clock and sampling policies                          |
| | • define uncertainty and stale-evidence rules                 |
| | • create valid, incomplete, uncertain, adversarial, replay,   |
| |   clock-drift, missing-sample, and oscillation test fixtures  |
| | • retain accepted: false and write_authority: NONE            |
| | }==============================================================|
| | NON_CLAIMS                                                    |
| | • Environmental stability is not environmental truth.        |
| | • Completion is not correction gain.                         |
| | • Completion is not acceptance.                              |
| | • Completion is not mutation authority.                      |
| | • The proposed metric is not universally applicable.         |
| | • This schema is not yet implemented or calibrated.          |
| | }==============================================================|
| | STATUS_SUMMARY                                               |
| | FORMAL_SCHEMA: PROPOSED                                      |
| | RUNTIME_IMPLEMENTATION: NONE                                 |
| | EMPIRICAL_CALIBRATION: NONE                                  |
| | ACCEPTED: false                                              |
| | WRITE_AUTHORITY: NONE                                        |
| | }==============================================================|
| | END_ENVIRONMENT_COMPLETION_CERTIFICATE                       |
| | }==============================================================|