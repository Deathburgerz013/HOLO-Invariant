| | }==============================================================|
| | █†█ Holo/Sim █†█ █†█ INVARIANT_IMPLEMENTATION_MAP █†█       |
| | }==============================================================|
| | DOCUMENT_TYPE: VERIFIED_REPOSITORY_COMPARISON                |
| | STATUS: VERIFIED_FROM_SOURCE                                 |
| | AUTHORITY: DESCRIPTIVE_ONLY                                  |
| | WRITE_AUTHORITY: NONE                                        |
| | DATE: 2026-07-14                                             |
| | DESIGN_SOURCE: docs/HOLO_Invariant_Design.md                 |
| | REPOSITORY_CHECKPOINT: main@28de5bc                          |
| | }==============================================================|
| | PURPOSE                                                      |
| | Compare every proposal in the HOLO invariant design against  |
| | current repository implementation and tests.                |
| |                                                              |
| | Allowed classifications:                                    |
| | IMPLEMENTED • PARTIAL • MISSING • CONFLICTING • UNCERTAIN   |
| | }==============================================================|
| | IDENTITY                                                     |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | • holosim/core.py hashes ordered chain entries.             |
| | • holosim/Holo_Sim.py protects anchor, active hash, fixed    |
| |   point hash, engine type, engine version, and base relation.|
| | • holosim/spine_protocol.py preserves source SHA-256, exact  |
| |   source text, section hashes, spans, and reconstruction.    |
| | • holosim/delta_export.py creates payload and export hashes. |
| |                                                              |
| | GAP:                                                         |
| | No repository-wide artifact identity contract connects all   |
| | observers, evaluators, receipts, exports, and persistence.    |
| | }==============================================================|
| | NON_CONTRADICTION                                            |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | HoloSim 1.2 compares explicit structured assertions using    |
| | normalized claim, scope, evidence state, and polarity.        |
| | Opposite polarities under the same identity are violations.   |
| | Incomplete assertion data is retained as uncertainty.         |
| | Checks cover both an incoming delta and approved history.     |
| |                                                              |
| | GAP:                                                         |
| | Free-text semantic equivalence, implication, and negation are |
| | not inferred. They require a separately bounded capability.   |
| | }==============================================================|
| | CAUSAL_ORDERING                                              |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | • HoloChain enforces monotonic indexes and prev-hash order.  |
| | • Replay preserves stored entry order.                      |
| | • Replay verifier distinguishes current and historical      |
| |   commits and checks ancestor relationships.                |
| | • HoloSim 1.3 validates explicit event IDs and predecessor  |
| |   references against approved verified history.             |
| | • Unknown, self, duplicate, and reused references are       |
| |   reported without mutation.                                |
| | • Malformed causal metadata remains explicit uncertainty.   |
| |                                                              |
| | GAP:                                                         |
| | Timestamp monotonicity and inferred real-world causality are  |
| | not independently validated. No causal relation is inferred. |
| | }==============================================================|
| | PROVENANCE                                                   |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | • holosim/provenance.py emits source, thread, anchor, active |
| |   hash, version, branch, and commit metadata.                |
| | • HoloSim evaluations and delta exports attach provenance.   |
| | • transition receipts preserve proposal and observation      |
| |   hashes plus reviewer metadata.                             |
| | • HoloSim 1.4 requires structured assertions and causal     |
| |   claims to bind a source ID to lowercase SHA-256 evidence.  |
| | • Malformed bindings remain uncertainty; duplicate evidence |
| |   references are violations.                                |
| | • Approved commits preserve the exact validated binding     |
| |   report separately from external acceptance authority.     |
| |                                                              |
| | GAP:                                                         |
| | HoloChain.append() and HoloService.append() do not require a  |
| | standardized provenance packet for every accepted delta.      |
| | Evidence hashes establish identity, not truth or sufficiency. |
| | }==============================================================|
| | AUTHORITY_VALIDITY                                           |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | PRESERVED BOUNDARY:                                          |
| | • Spine protocol is read-only and non-approving.            |
| | • Transfer packets do not mutate canonical sources.         |
| | • Transition receipts can record reviewer and approval data.|
| | • HoloSim evaluation remains non-accepting and read-only.   |
| | • HoloSim commits require reviewer and approval references. |
| | • HoloService append requires the same external authority.  |
| | • CLI, Collector, API, and ingest thread that authority.    |
| | • Blocked service appends perform no chain or slot mutation.|
| |                                                              |
| | GAP:                                                         |
| | • HoloChain.append() remains a direct low-level primitive.  |
| | • Other direct HoloChain callers require a separate audit.  |
| |                                                              |
| | Service evaluation, external acceptance, and mutation are   |
| | separated. Repository-wide enforcement remains incomplete.  |
| | }==============================================================|
| | CORRECTION_VISIBILITY                                        |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | • Append-only chain and Git history preserve prior states.  |
| | • Spine comparison reports added, removed, moved, changed,  |
| |   unchanged, and lost-uncertainty results.                   |
| | • Transition receipts preserve historical verification.     |
| |                                                              |
| | GAP:                                                         |
| | Corrections do not use a required first-class relation such  |
| | as corrects, supersedes, or resolves uncertainty from.       |
| | }==============================================================|
| | TERMINATION                                                  |
| | CLASSIFICATION: MISSING                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | Existing evaluators and audits terminate as single calls.    |
| |                                                              |
| | GAP:                                                         |
| | No bounded correction cycle compares successive supported    |
| | deltas and stops explicitly when none remain.                |
| | }==============================================================|
| | UNIFIED_INVARIANT_EVALUATION_INTERFACE                       |
| | CLASSIFICATION: PARTIAL_AND_CONFLICTING                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | HoloSim.evaluate() already provides a read-only candidate     |
| | evaluation with hashes, provenance, and violations.          |
| |                                                              |
| | GAP:                                                         |
| | Its result schema lacks verified_checks, uncertainty,        |
| | evidence, accepted=false, and write_authority=NONE.          |
| |                                                              |
| | CONFLICT:                                                    |
| | It reports status=accepted when protected fields survive.    |
| | }==============================================================|
| | AUTOMATED_DISTORTION_REPORTS                                 |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | HoloSim violations, invariant audits, Spine validation, rail |
| | validation, receipt verification, and replay reports expose  |
| | several distinct failure types.                             |
| |                                                              |
| | GAP:                                                         |
| | No common report envelope or shared check result schema.     |
| | }==============================================================|
| | CONFLICT_RESOLUTION_SCORING                                  |
| | CLASSIFICATION: MISSING                                      |
| |                                                              |
| | No implementation ranks conflicting claims by scope,         |
| | provenance, evidence strength, or verification state.        |
| | }==============================================================|
| | BOUNDED_SELF_AUDIT_CYCLES                                    |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | Self-tests, receipt replay, and invariant audits are finite. |
| |                                                              |
| | GAP:                                                         |
| | They do not iterate supported deltas toward an explicit      |
| | no-difference terminal state.                               |
| | }==============================================================|
| | IMPLEMENTATION_REQUIREMENTS_MAP                              |
| |                                                              |
| | VERSIONED_INPUT_OUTPUT_SCHEMA: PARTIAL                       |
| | Multiple modules version their own outputs; no shared        |
| | invariant evaluation schema exists.                         |
| |                                                              |
| | DETERMINISTIC_UNIT_TESTS: PARTIAL                            |
| | Repository tests cover persistence, rails, headers, receipt  |
| | states, and other components; HoloSim authority semantics are |
| | not directly protected by focused tests.                    |
| |                                                              |
| | NEGATIVE_AND_UNCERTAINTY_TESTS: PARTIAL                      |
| | Spine protocol tests preserve uncertainty and reject missing |
| | headers; unified evaluator uncertainty remains untested.     |
| |                                                              |
| | READ_ONLY_BEHAVIOR: PARTIAL                                  |
| | Spine, replay, comparison, and HoloSim.evaluate are read-only;|
| | adjacent commit and append paths lack an acceptance barrier. |
| |                                                              |
| | EXACT_SOURCE_REFERENCES: PARTIAL                             |
| | Spine spans, hashes, raw source, and bound analyses preserve  |
| | exact references; other evaluators use broader provenance.   |
| |                                                              |
| | ACCEPTED_REMAINS_FALSE: CONFLICTING                          |
| | HoloSim.evaluate currently reports accepted itself.          |
| |                                                              |
| | HUMAN_ACCEPTANCE_BOUNDARY: PARTIAL                           |
| | The boundary is documented and receipts can record reviewers,|
| | but runtime mutation does not universally enforce it.        |
| | }==============================================================|
| | SMALLEST_SUPPORTED_CORRECTION                                |
| | Do not build a second evaluator.                             |
| |                                                              |
| | Correct the existing HoloSim evaluation boundary first.      |
| |                                                              |
| | Required read-only evaluation envelope:                     |
| |                                                              |
| | • status: PASS | FLAGGED | UNCERTAIN                        |
| | • verified_checks                                           |
| | • violations                                                |
| | • uncertainty                                               |
| | • evidence                                                  |
| | • accepted: false                                           |
| | • write_authority: NONE                                     |
| |                                                              |
| | Evaluation must not describe itself as accepted.             |
| | Mutation must not follow solely because evaluation passed.   |
| | }==============================================================|
| | DEFERRED_AFTER_CORRECTION                                    |
| | • semantic non-contradiction checking                       |
| | • conflict-resolution scoring                               |
| | • bounded multi-pass correction cycles                      |
| | • repository-wide provenance enforcement                    |
| |                                                              |
| | These remain later work because authority separation is the  |
| | prerequisite boundary that protects every later evaluator.   |
| | }==============================================================|
| | ENVIRONMENT_COMPLETION_EVALUATOR_DELTA                        |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | • environment_completion_evaluator.py evaluates an ordered   |
| |   window of verified canonical snapshots and exact adjacent  |
| |   comparisons under one explicit versioned contract.         |
| | • Every required contract and measurement field is validated;|
| |   unsupported or missing fields cannot silently pass.        |
| | • Coverage, distance, stable count, sampling, signals,        |
| |   provenance, and uncertainty remain separate predicates.    |
| | • Results are COMPLETE_ELIGIBLE, INCOMPLETE, or UNCERTAIN.   |
| | • Certificate identity binds ordered observations, adjacent  |
| |   comparisons, contract, measurements, frozen evidence, and  |
| |   provenance.                                                |
| | • Results keep accepted=false and write_authority=NONE.      |
| |                                                              |
| | PRESERVED BOUNDARY:                                          |
| | Completion eligibility permits later evaluation only. It does|
| | not establish truth, correction gain, acceptance, persistence,|
| | or permission to mutate state.                              |
| |                                                              |
| | GAP:                                                         |
| | Distance, coverage, provenance, and uncertainty measurements  |
| | remain externally supplied and are not empirically calibrated.|
| | No correction trigger or persistence path consumes the       |
| | certificate yet.                                            |
| | }==============================================================|
| | CORRECTION_MARKER                                            |
| | Future code or tests may change these classifications.       |
| | Append a new comparison delta when repository evidence       |
| | changes. Do not rewrite this checkpoint as prior knowledge.  |
| | }==============================================================|
| | ENVIRONMENT_OBSERVATION_COMPARISON_DELTA                      |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | • environment_snapshot.py builds canonical read-only         |
| |   observations with explicit observed, missing, unknown,     |
| |   assumed, falsifier, evidence, provenance, and uncertainty. |
| | • environment_snapshot_comparator.py verifies both source    |
| |   snapshots before comparing the same episode and environment.|
| | • Comparison requires a strictly later caller-supplied       |
| |   observation time and reports context and schema changes.   |
| | • Observed, epistemic, evidence, and provenance deltas remain|
| |   separate and retain added, removed, and retained states.   |
| | • Comparison identity canonically binds both snapshot IDs.   |
| | • Results keep accepted=false and write_authority=NONE.      |
| |                                                              |
| | PRESERVED BOUNDARY:                                          |
| | Comparison does not establish truth, improvement, completion,|
| | correction eligibility, acceptance, or permission to write. |
| |                                                              |
| | GAP:                                                         |
| | No runtime component yet selects the next useful check,      |
| | evaluates a completion certificate, or persists a comparison.|
| | }==============================================================|
| | ENVIRONMENT_OBSERVATION_RECEIPT_SPINE_DELTA                  |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | • docs/Environment_Observation_Receipt_Spine.md defines     |
| |   proposed boundaries between fact, observation,             |
| |   communication, receipt evidence, capability, authority,    |
| |   state or instance change, temporal continuation, blind     |
| |   verification, correction, and scoped compression stopping. |
| | • The proposal preserves COMPLETE, PARTIAL, UNVERIFIED,      |
| |   CONFLICT, and UNAVAILABLE as separate receipt findings.    |
| | • Compression findings distinguish collection completion,   |
| |   scoped fixed point, budget exhaustion, blocking required   |
| |   distinctions, reconstruction failure, temporary pause,     |
| |   false convergence, and reopening.                         |
| |                                                              |
| | PRESERVED_BOUNDARY:                                          |
| | The proposal is descriptive only.                           |
| | It does not certify the originating conversation as          |
| | byte-archived evidence, establish inherited private model    |
| | state, grant acceptance, or authorize implementation.        |
| |                                                              |
| | GAP:                                                         |
| | • environment_snapshot.py does not yet implement an explicit|
| |   operation-receipt or blind-verification contract.          |
| | • No stable state or instance identity contract binds       |
| |   temporal continuation across surfaces.                    |
| | • No runtime component evaluates the proposed scoped        |
| |   compression-stop findings.                                |
| |                                                              |
| | NEXT_BOUNDARY:                                               |
| | Review and falsify the proposal before extending the existing|
| | environment snapshot implementation.                        |
| | Do not create a parallel evaluator.                         |
| | }==============================================================|
| | COMPRESSION_FIXED_POINT_FIXTURE_DELTA                       |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | • docs/Compression_Fixed_Point_Falsification_Fixture.md     |
| |   preserves a scoped audit episode in which substantive      |
| |   findings stabilized before the terminal stop finding.      |
| | • The fixture distinguishes the blocked-by-distinction      |
| |   finding from a fixed point by comparing each finding with  |
| |   its declared decision conditions.                          |
| | • The corrected episode preserves four source-bound findings|
| |   and two unresolved operational uncertainties.              |
| |                                                              |
| | PRESERVED_BOUNDARY:                                          |
| | The fixture is reconstructed from session-observed material. |
| | It does not archive the originating conversation or source,  |
| | prove SteadyLog correctness, establish model continuity,     |
| | grant authority, or establish global compression optimality. |
| |                                                              |
| | GAP:                                                         |
| | • The originating source and conversation are not preserved |
| |   as byte-archived repository evidence.                      |
| | • The four direct falsifier tests remain described rather   |
| |   than repository-executed.                                 |
| | • No runtime component evaluates compression-stop findings.|
| |                                                              |
| | NEXT_BOUNDARY:                                               |
| | Independently review the fixture's retained source claims and|
| | terminal classification without expanding implementation.    |
| | }==============================================================|
| | COMPRESSION_STOP_EVALUATOR_DELTA                           |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | IMPLEMENTED:                                                 |
| | • holosim/environment_snapshot.py now derives scoped        |
| |   compression-phase stop findings from structured evidence.  |
| | • The evaluator distinguishes fixed point, budget           |
| |   exhaustion, blocking required distinctions, reconstruction |
| |   failure, temporary pause, false convergence, reopening,    |
| |   and a nonterminal no-stop finding.                         |
| | • Required and evaluated operators, lower-cost candidates,  |
| |   lost distinctions, reported findings, reasons, and         |
| |   uncertainties remain separately represented.              |
| | • Deterministic finding identity binds the complete derived |
| |   result while accepted remains false and write authority    |
| |   remains NONE.                                              |
| | • tests/test_environment_snapshot.py binds the merged       |
| |   falsification fixture to COMPRESSION_FIXED_POINT and tests |
| |   each implemented decision boundary.                       |
| |                                                              |
| | PRESERVED_BOUNDARY:                                          |
| | The evaluator classifies caller-supplied structured evidence.|
| | It does not execute compression, verify source truth, prove   |
| | operator execution, establish losslessness or global         |
| | optimality, accept a finding, or authorize mutation.         |
| |                                                              |
| | GAP:                                                         |
| | • Collection completion remains outside the compression     |
| |   evaluator and has no runtime evaluator in this change.     |
| | • No receipt verifier or persistence layer independently    |
| |   replays the supplied operator and candidate evidence.      |
| | • Cost measurement and compression operators remain        |
| |   caller-supplied rather than runtime-executed.              |
| |                                                              |
| | NEXT_BOUNDARY:                                               |
| | Independently falsify decision priority and candidate        |
| | semantics before exposing CLI, persistence, or write paths.  |
| | }==============================================================|
| | TEMPORAL_DECISION_INTEGRITY_FIXTURE_DELTA                 |
| | CLASSIFICATION: PARTIAL                                      |
| |                                                              |
| | EVIDENCE:                                                    |
| | • docs/Temporal_Decision_Integrity_Falsification_Fixture.md |
| |   preserves a scoped case where identifiers and timestamps   |
| |   survived retrieval but the temporal relation and dependent |
| |   compliance finding were inverted.                         |
| | • The supplied timestamps deterministically place the       |
| |   question 82187 seconds after the continuing boundary.      |
| | • The fixture preserves the reported incorrect relation and |
| |   finding beside their deterministic corrections.            |
| |                                                              |
| | PRESERVED_BOUNDARY:                                          |
| | Historical public references and screenshots remain         |
| | session-observed rather than byte-archived repository        |
| | evidence.                                                    |
| |                                                              |
| | The fixture does not establish intent, deception, private    |
| | memory, model identity, complete public-history retrieval,   |
| | acceptance, or write authority.                             |
| |                                                              |
| | GAP:                                                         |
| | • The transfer protocol does not yet bind timestamp evidence|
| |   to a mechanically derived temporal relation.               |
| | • No destination evaluator preserves reported and derived   |
| |   findings when they conflict.                              |
| | • Public post content and timestamps remain independently   |
| |   unverified by repository evidence.                        |
| |                                                              |
| | NEXT_BOUNDARY:                                               |
| | Review and falsify the fixture before extending              |
| | holosim/spine_protocol.py with destination compatibility.    |
| | Do not create a parallel parser or model-judged similarity.  |
| | }==============================================================|
| | CONTEXT_WEAVER_FRAMING_ROUNDTRIP_FIXTURE_DELTA                      |
| | CLASSIFICATION: PARTIAL                                             |
| |                                                                    |
| | EVIDENCE:                                                          |
| | - docs/Context_Weaver_Framing_Roundtrip_Falsification_Fixture.md    |
| |   defines an adversarial reconstruction contract for the candidate  |
| |   XML, Markdown, and compact virtual-file framing formats.           |
| | - Twelve fixture classes pressure path escaping, embedded framing,   |
| |   duplicate instances, empty state, newline and Unicode identity,    |
| |   control bytes, size boundaries, and delimiter density.             |
| | - The fixture separates exact framing from lossy minification,       |
| |   runtime-dependent persistence, and destination compatibility.      |
| | - Current scoped finding is DECODER_UNAVAILABLE because the supplied |
| |   candidate defines encoders without declared inverse decoders or    |
| |   repository-executed roundtrip tests.                               |
| |                                                                    |
| | PRESERVED_BOUNDARY:                                                 |
| | The 248390-byte originating conversation remains session-supplied    |
| | evidence and is not archived in this repository. Its observed        |
| | SHA-256 is retained only as a receipt of the attachment read here.   |
| |                                                                    |
| | The fixture does not establish application safety, semantic          |
| | equivalence, browser execution, prompt quality, token savings, model |
| | compatibility, continuity, acceptance, or write authority.          |
| |                                                                    |
| | GAP:                                                               |
| | - No runtime encoder or decoder executes the adversarial matrix.     |
| | - Candidate separators remain collision-prone until tested and       |
| |   repaired under the declared reconstruction contract.              |
| | - window.storage persistence remains receiving-runtime-dependent.    |
| |                                                                    |
| | NEXT_BOUNDARY:                                                     |
| | Independently review and falsify the fixture before implementation.  |
| | Then add only the smallest deterministic encoder-decoder pair needed |
| | to execute the matrix, preserving failures before format repair.     |
| | Do not add a parallel Spine parser or model-judged similarity.       |
| | }==============================================================|
| |}==============================================================|
| | GROUNDED_MULTI_INSTANCE_HOLO_RECEIPT_DELTA
| |}==============================================================|
| | ARTIFACTS
| | - docs/F1_Useful_Falsifiable_Feedback_Loops_Raw.txt.b64
| | - docs/F1_Useful_Falsifiable_Feedback_Loops.md
| | - docs/Grounded_Multi_Instance_HOLO_Receipt.md
| |
| | RAW_SOURCE_SHA256:
| | f92264bf9630962359f2b855feff0b9d2ce1faf88f7e627db0393512b09dc73a
| | CORRECTED_SPINE_SHA256:
| | d45479029944cbabacf43898f4ba6ce29ca7349594590e0f77bfd178ca9be463
| | RECEIPT_SHA256:
| | 79bbddab6ddc28e81ae6274a2a9ca185a391ab208f5f87d88347f3ce6ae88ab9
| |
| | CLASSIFICATION: DOCUMENTATION_AND_OBSERVATION_RECEIPT
| | RUNTIME_IMPLEMENTATION: NOT_PRESENT
| | WRITE_AUTHORITY: NONE
| |
| | The Base64 artifact losslessly preserves the transferred raw bytes.
| | The corrected Spine repairs four divider defects, normalizes fifty-seven
| | trailing-whitespace instances, and passes
| | strict two-rail validation with zero violations.
| | The receipt distinguishes printed output from branch advancement,
| | preserves instance separation, and defines the minimum executable
| | two-instance conflict fixture needed for the next grounded test.
| |
| | NOT_ESTABLISHED:
| | Byte-identical delivery to every destination branch; platform-level
| | thread identity; per-branch output hashes; automated propagation;
| | autonomous continuity; permanent correction; or large-scale execution.
| |}==============================================================|
| |}==============================================================|
| | APPEND_ONLY_CORRECTION_OVERLAY_DELTA
| |}==============================================================|
| | STATUS: IMPLEMENTED
| | IMPLEMENTATION:
| | - holosim/core.py
| | TESTS:
| | - holosim/tests/test_core.py
| |
| | HoloChain.correct() appends a namespaced correction record.
| | The correction binds the original entry index and hash, requires
| | a non-empty reason, and retains JSON-serializable replacement data.
| |
| | HoloChain.get_effective_state() derives the latest corrected view
| | without editing or deleting the original entry or correction records.
| | HoloChain.get_corrections() preserves ordered correction history.
| |
| | Malformed versions, missing or forward targets, correction-to-
| | correction targets, target-hash mismatch, missing replacement data,
| | and empty reasons fail closed during effective-view reconstruction.
| |
| | CANONICAL_EVIDENCE: RAW_APPEND_ONLY_CHAIN
| | DERIVED_OUTPUT: EFFECTIVE_CORRECTED_VIEW
| | WRITE_AUTHORITY: NONE
| |
| | NOT_ESTABLISHED:
| | Automatic truth verification, autonomous correction, correction
| | acceptance, deletion, pruning, compaction, or external mutation.
| |}==============================================================|
| |}=================================================================|
| | APPEND_ONLY_REVALIDATION_RECEIPTS_DELTA                          |
| |}=================================================================|
| | RUNTIME_IMPLEMENTATION: holosim/core.py                          |
| | TEST_IMPLEMENTATION: holosim/tests/test_core.py                  |
| | WRITE_AUTHORITY: HUMAN_CALLER_ONLY                               |
| |                                                                  |
| | IMPLEMENTED:                                                     |
| | - revalidate(target_idx, outcome, evidence, method) appends a    |
| |   versioned holo_revalidation record without changing its claim. |
| | - Receipts bind the original entry index and raw chain hash.      |
| | - Receipts also bind the exact effective-content digest and the  |
| |   correction index, if any, that existed when the check occurred.|
| | - Outcomes are bounded to HELD, FAILED, REVISED, or UNAVAILABLE.  |
| | - get_revalidations(target_idx) preserves every validated check  |
| |   and marks whether it still matches the current effective claim.|
| | - A later correction makes prior receipts stale automatically;   |
| |   it does not erase them or carry their status onto new content.  |
| | - get_claim_index() joins original hash, effective content,       |
| |   correction history, revalidation history, and current status.  |
| | - Claims without a receipt matching their current effective      |
| |   version are reported as UNCHECKED.                              |
| | - Malformed versions, targets, hashes, correction references,    |
| |   outcomes, methods, and evidence fail closed.                    |
| |                                                                  |
| | PRESERVED:                                                       |
| | Raw append-only history; correction history; failed and stale     |
| | checks; instance-local chain identity; human write authority.     |
| |                                                                  |
| | NOT_ESTABLISHED:                                                 |
| | Automatic truth discovery; autonomous checking or correction;    |
| | permanent truth; cross-instance agreement; external acceptance;  |
| | deletion, pruning, compaction, signing, or distributed consensus.|
| |}=================================================================|
| | TERMINAL                                                     |
| | Repository comparison complete at main@28de5bc.             |
| | Smallest missing capability identified.                     |
| | Nothing left for collection in field.                       |
| | }==============================================================|
| |}==============================================================|
| | CLAIM_STATUS_STALENESS_CORRECTION_DELTA
| |}==============================================================|
| | CORRECTION_STATUS: IMPLEMENTED_ON_BRANCH
| | BRANCH: fix/distinguish-stale-claim-status
| | BASE: main@08c56eba6b3a6144118a9f6b9d57378174d1b0f6
| | IMPLEMENTATION: holosim/core.py
| | TESTS: holosim/tests/test_core.py
| |
| | ORIGINAL_CLAIM_PRESERVED:
| | Claims without a receipt matching their current effective
| | version were reported as UNCHECKED.
| |
| | CORRECTION:
| | get_claim_index() now distinguishes two evidence states.
| | - UNCHECKED means no revalidation receipt exists.
| | - STALE means revalidation history exists, but no receipt binds
| |   the current effective-content digest and correction version.
| | - A current matching receipt still exposes its bounded outcome.
| |
| | FAILURE_PATHS_PRESERVED:
| | A correction after a current check produces STALE without erasing
| | the prior receipt. Revalidation of the corrected content restores
| | the new bounded outcome while retaining ordered receipt history.
| |
| | VERIFICATION_BOUNDARY:
| | - Focused core suite: 15 passed.
| | - Full repository suite: 148 passed.
| | - git diff --check: no errors; Windows line-ending warnings only.
| | - git diff --cached --check: clean before this documentation delta.
| | - Commit identity is not yet assigned.
| |
| | NOT_ESTABLISHED:
| | Truth, permanent validity, autonomous checking, external acceptance,
| | cross-instance agreement, or expanded write authority.
| |}==============================================================|
| | TERMINAL
| | Historical UNCHECKED behavior preserved as the original claim.
| | Effective status distinction corrected by append-only overlay.
| | Verification remains bound to the uncommitted branch state above.
| | Nothing left for collection in field.
| |}==============================================================|
| |}==============================================================|
| | DESTINATION_COMPATIBILITY_FALSIFICATION_FIXTURE_DELTA
| |}==============================================================|
| | CLASSIFICATION: PARTIAL
| | STATUS: PROPOSED_NOT_ACCEPTED
| | BASE: main@7a122446485a538bbf793c97693dde3fa7d449fb
| | FIXTURE:
| | - docs/Destination_Compatibility_Falsification_Fixture.md
| |
| | FIXTURE_SHA256:
| | 2f0637d8d2871b07e16e266e3de1f1906b9ccc808c5e52cf447334bf5cbbbd8d
| |
| | EVIDENCE:
| | - One structured source fixture and one structured destination
| |   profile define exact ordered requirement evaluation.
| | - The expected partition preserves VERIFIED_REQUIREMENT,
| |   MISSING_REQUIREMENT, CONFLICT, and UNCERTAIN separately.
| | - A separate malformed-profile case requires fail-closed
| |   INVALID_PROFILE behavior.
| | - Source-hash and profile-hash change cases require prior
| |   findings to become stale rather than inherited.
| | - Compatibility remains separate from acceptance and authority.
| |
| | VALIDATION:
| | - Rail validation: valid.
| | - Checked nonempty lines: 272.
| | - Violation count: 0.
| | - External review: PENDING.
| | - Full repository test suite: PENDING_FOR_THIS_BRANCH.
| |
| | IMPLEMENTATION_STATUS:
| | No destination-profile evaluator is implemented.
| | holosim/spine_protocol.py remains unchanged.
| |
| | PRESERVED_BOUNDARY:
| | The fixture uses symbolic binding hashes and structured values.
| | It does not establish source truth, real-platform compatibility,
| | semantic equivalence, acceptance, persistence, or mutation.
| |
| | NEXT_BOUNDARY:
| | Independently review and falsify the fixture before extending
| | holosim/spine_protocol.py with the minimum deterministic EXISTS
| | and EXACT_VALUE destination-profile evaluator.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | Destination compatibility fixture preserved as PARTIAL.
| | Runtime implementation remains absent and unauthorized.
| | Stop at independent review and branch verification.
| |}==============================================================|
| |}==============================================================|
| | DESTINATION_FIXTURE_EXTERNAL_REVIEW_CORRECTION
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260716-011
| | REVIEW_RESULT: FAIL
| | BLOCKING_FINDINGS: 1
| | NONBLOCKING_FINDINGS: 0
| |
| | PRESERVED_REVIEW_FINDING:
| | The original fixture tested COMPATIBLE false with ACCEPTED false
| | and WRITE_AUTHORITY NONE, but supplied no compatible control case.
| | An evaluator could therefore couple acceptance or authority to a
| | true compatibility result without being falsified.
| |
| | STALE_FIXTURE_SHA256:
| | 2f0637d8d2871b07e16e266e3de1f1906b9ccc808c5e52cf447334bf5cbbbd8d
| |
| | [CORRECTION_MARKER]
| | The fixture now includes a structured compatible control profile
| | with exact expected findings:
| | - COMPATIBLE: true
| | - ACCEPTED: false
| | - WRITE_AUTHORITY: NONE
| |
| | CURRENT_FIXTURE_SHA256:
| | e0eba69308de05c7e70eb409df2a0c0ead18e103bcb51593418f6b4f171f7e94
| |
| | CORRECTED_VALIDATION:
| | - Rail validation: valid.
| | - Checked nonempty lines: 334.
| | - Violation count: 0.
| | - Corrected external review: PENDING.
| |
| | STATUS:
| | The failed review is preserved and not converted into approval.
| | The corrected fixture remains PROPOSED_NOT_ACCEPTED until a new
| | independent review evaluates the current exact hash.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | Review 011 failure preserved.
| | Original fixture verification is stale after correction.
| | Corrected fixture awaits hash-bound independent re-review.
| |}==============================================================|
| |}==============================================================|
| | DESTINATION_FIXTURE_EXTERNAL_REREVIEW_RECEIPT
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260716-012
| | REVIEW_RESULT: PASS
| | BLOCKING_FINDINGS: 0
| | NONBLOCKING_FINDINGS: 0
| |
| | REVIEWED_FIXTURE_SHA256:
| | e0eba69308de05c7e70eb409df2a0c0ead18e103bcb51593418f6b4f171f7e94
| |
| | REVIEWED_MAP_SHA256:
| | cdfee753153583acfce907cb085fd3ab76f5fd225dc481f8401309ea73bf321a
| |
| | VERIFIED_BOUNDARIES:
| | - Exact structured EXISTS and EXACT_VALUE requirements.
| | - Ordered verified, missing, conflict, and uncertain findings.
| | - Unsupported comparator fails closed as INVALID_PROFILE.
| | - Source and destination-profile changes stale prior findings.
| | - Incompatible primary case remains COMPATIBLE false.
| | - Compatible control remains COMPATIBLE true while ACCEPTED stays
| |   false and WRITE_AUTHORITY stays NONE.
| | - No semantic similarity, persistence, mutation, or inferred
| |   acceptance or authority is introduced.
| |
| | REVIEW_HISTORY:
| | HOLO-EXT-REV-20260716-011 remains preserved as FAIL against the
| | earlier stale fixture hash. It is not converted into a pass.
| | Review 012 applies only to the corrected exact hashes above.
| |
| | CURRENT_STATUS:
| | FIXTURE_REVIEW: PASS
| | FIXTURE_CLASSIFICATION: PARTIAL
| | RUNTIME_IMPLEMENTATION: NOT_PRESENT
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | Corrected destination compatibility fixture independently reviewed.
| | Review 012 passed with no findings at the exact bound hashes.
| | Runtime implementation remains absent and unauthorized.
| |}==============================================================|
| |}==============================================================|
| | DESTINATION_COMPATIBILITY_EVALUATOR_IMPLEMENTATION_DELTA
| |}==============================================================|
| | CLASSIFICATION: PARTIAL_IMPLEMENTATION
| | STATUS: IMPLEMENTED_ON_BRANCH
| | BRANCH: feat/destination-compatibility-evaluator
| | BASE: main@410ab83ffd18ca4476c28bb37f52f86ab57018a8
| | IMPLEMENTATION: holosim/spine_protocol.py
| | FOCUSED_TESTS: tests/test_spine_protocol_destination.py
| |
| | IMPLEMENTATION_SHA256:
| | b023ee999565431f7c368d23949f74c101021cd40744ee241a0271273f7e966a
| | FOCUSED_TEST_SHA256:
| | 7e9ab4d9b9502fb251a3a9e605aa81c01ccdfc6f794890b52a0b434fbc620801
| |
| | THEOREM:
| | Given a valid structured source description and valid structured
| | destination profile using only EXISTS and EXACT_VALUE, the
| | evaluator deterministically partitions every ordered requirement
| | into verified, missing, conflict, or uncertain findings.
| |
| | A compatible partition establishes only COMPATIBLE true.
| | It never changes ACCEPTED from false or WRITE_AUTHORITY from NONE.
| |
| | IMPLEMENTED_FUNCTIONS:
| | - evaluate_destination_compatibility(source, destination_profile)
| | - check_destination_finding_current(finding, source, profile)
| |
| | IMPLEMENTED_BEHAVIOR:
| | - Dotted paths traverse declared mappings without free-text
| |   interpretation.
| | - EXISTS and EXACT_VALUE are the only supported comparators.
| | - Requirement order is preserved within each finding partition.
| | - Missing paths remain missing.
| | - Present unequal exact values remain conflicts.
| | - Explicit UNAVAILABLE values become uncertain only when the
| |   profile declares unavailable_as UNCERTAIN.
| | - Unsupported comparators return a fail-closed INVALID_PROFILE
| |   finding with COMPATIBLE false.
| | - Other malformed contracts raise SpineStructureError.
| | - Duplicate requirement identifiers fail closed.
| | - Exact source and profile identity fields bind each finding.
| | - Changed source bindings produce SOURCE_CHANGED staleness.
| | - Changed profile bindings produce DESTINATION_PROFILE_CHANGED
| |   staleness.
| | - Identical structured inputs produce identical finding hashes.
| |
| | VERIFICATION:
| | - spine_protocol self-test: PASS.
| | - Focused destination tests: 12 passed.
| | - Full repository suite: 160 passed.
| | - External implementation review: PENDING.
| |
| | PRESERVED_BOUNDARY:
| | The evaluator consumes caller-supplied structured descriptions.
| | It does not verify that supplied symbolic hashes bind real bytes.
| | It is not yet wired to a transfer-packet adapter or CLI command.
| | It performs no semantic similarity, source-truth verification,
| | acceptance, persistence, destination mutation, or external action.
| |
| | PROOF_STATUS:
| | The merged fixture cases execute and pass at the branch state.
| | Universal correctness is not established by finite tests.
| | Verification becomes stale if implementation or tests change.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | Minimum structured destination evaluator executes the fixture.
| | Transfer-packet integration and external review remain open.
| | Stop before commit until exact-hash external review completes.
| |}==============================================================|
| |}==============================================================|
| | DESTINATION_EVALUATOR_EXTERNAL_REVIEW_CORRECTION
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260716-013
| | REVIEW_RESULT: FAIL
| | BLOCKING_FINDINGS: 4
| | NONBLOCKING_FINDINGS: 2
| |
| | PRESERVED_BLOCKING_FINDINGS:
| | - EXACT_VALUE used Python loose equality and accepted cross-type
| |   values such as true and 1.
| | - Finding currentness did not authenticate finding_hash or reject
| |   rehashed attempts to grant acceptance or write authority.
| | - Unsupported-comparator prescan could bypass duplicate, path, and
| |   source-field validation.
| | - The reported test execution was not cryptographically bound to
| |   the reviewed implementation and focused-test artifacts.
| |
| | STALE_IMPLEMENTATION_SHA256:
| | b023ee999565431f7c368d23949f74c101021cd40744ee241a0271273f7e966a
| | STALE_FOCUSED_TEST_SHA256:
| | 7e9ab4d9b9502fb251a3a9e605aa81c01ccdfc6f794890b52a0b434fbc620801
| | STALE_VERIFICATION:
| | - Focused destination tests: 12 passed.
| | - Full repository suite: 160 passed.
| |
| | [CORRECTION_MARKER]
| | - EXACT_VALUE now requires recursive type-exact equality.
| | - Finding hashes are recomputed and authenticated before binding
| |   currentness is evaluated.
| | - Finding partitions must be unique, disjoint, and consistent with
| |   the compatible field.
| | - Rehashed findings cannot grant acceptance or write authority.
| | - Unsupported comparators are classified only after common profile,
| |   requirement, path, duplicate-id, and source-field validation.
| | - INVALID_PROFILE findings can be checked for currentness.
| |
| | CURRENT_IMPLEMENTATION_SHA256:
| | 42edb0e2910b4d6320a773c750dd3d4c4cd989ebf33b86b6514fc91e91ef4044
| | CURRENT_FOCUSED_TEST_SHA256:
| | 5754145c7616441ed4986488c766316b7325465e93943dcffa341ef5638075ba
| |
| | WINDOWS_HASH_RECEIPT:
| | - certutil bound holosim/spine_protocol.py to the current
| |   implementation hash before execution.
| | - certutil bound tests/test_spine_protocol_destination.py to the
| |   current focused-test hash before execution.
| | - An initial cached test-file replacement mismatch was detected and
| |   corrected before the current tests ran.
| |
| | CORRECTED_VERIFICATION:
| | - spine_protocol self-test: PASS.
| | - Focused destination tests: 23 passed.
| | - Full repository suite: 171 passed.
| | - Corrected external review: PENDING.
| |
| | PRESERVED_LIMIT:
| | Staleness remains binding-based. Caller-supplied symbolic hashes are
| | not independently recomputed from source fields or profile rules.
| | Finding authentication does not establish source truth.
| |
| | STATUS:
| | Review 013 remains FAIL against the stale exact hashes.
| | Corrected verification applies only to the current hashes above.
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | Review 013 failure and cached-file mismatch preserved.
| | Corrected exact Windows artifacts pass 23 focused and 171 full tests.
| | Stop before commit until corrected external review completes.
| |}==============================================================|
| |}==============================================================|
| | DESTINATION_EVALUATOR_THIRD_REVIEW_CORRECTION
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260716-015
| | REVIEW_RESULT: FAIL
| | BLOCKING_FINDINGS: 1
| | NONBLOCKING_FINDINGS: 0
| |
| | PRESERVED_BLOCKING_FINDING:
| | The shared nonempty-string validator stripped surrounding
| | whitespace from opaque source, destination, profile, and digest
| | values before comparison. Whitespace-modified bindings could be
| | treated as unchanged, and a padded finding hash could pass syntax
| | validation after normalization.
| |
| | STALE_IMPLEMENTATION_SHA256:
| | 504e83ed9316ada3a7934416de6a82b1b98814f7e7d5422659520409b17cc1e7
| | STALE_FOCUSED_TEST_SHA256:
| | d1fc35ed1ec296ee5bf5b30f297782cbcab000b815fcdf469d1677ac377d52be
| | STALE_VERIFICATION:
| | - Focused destination tests: 34 passed.
| | - Full repository suite: 182 passed.
| |
| | [CORRECTION_MARKER]
| | - Opaque identity and digest strings are preserved exactly.
| | - Leading or trailing whitespace is rejected as malformed rather
| |   than silently normalized.
| | - Whitespace-modified source and profile bindings cannot appear
| |   current.
| | - Padded finding hashes fail before digest comparison.
| |
| | CURRENT_IMPLEMENTATION_SHA256:
| | 6d0c9eeb270ebcfbae2f2820ada9d517745c6b365ee77e81087309f57a8c4908
| | CURRENT_FOCUSED_TEST_SHA256:
| | b6d34072a8d64dc3ff45a4d06950bd6154b1b44bf7897571d7834ba44ec40730
| |
| | WINDOWS_HASH_RECEIPT:
| | - certutil matched both current hashes before execution.
| | - spine_protocol self-test: PASS.
| | - Focused destination tests: 40 passed.
| | - Full repository suite: 188 passed.
| |
| | CORRECTED_EXTERNAL_REVIEW: PENDING
| |
| | STATUS:
| | Review 015 remains FAIL against its stale exact hashes.
| | Corrected verification applies only to the current hashes above.
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | Reviews 013, 014, and 015 remain preserved failures.
| | Current exact artifacts pass 40 focused and 188 full tests.
| | Stop before commit until corrected external review completes.
| |}==============================================================|
| |}==============================================================|
| | DESTINATION_EVALUATOR_SECOND_REVIEW_CORRECTION
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260716-014
| | REVIEW_RESULT: FAIL
| | BLOCKING_FINDINGS: 2
| | NONBLOCKING_FINDINGS: 1
| |
| | PRESERVED_BLOCKING_FINDINGS:
| | - Recursive exact equality still admitted Python-loose mapping
| |   keys and unsupported non-JSON containers.
| | - A self-consistent rehashed finding was not recomputed against
| |   the bound source and destination profile, permitting semantic
| |   partition, coverage, order, and INVALID_PROFILE forgeries.
| |
| | PRESERVED_NONBLOCKING_FINDING:
| | - finding_hash accepted malformed or non-ASCII strings before
| |   compare_digest could enforce a bounded failure.
| |
| | STALE_IMPLEMENTATION_SHA256:
| | 42edb0e2910b4d6320a773c750dd3d4c4cd989ebf33b86b6514fc91e91ef4044
| | STALE_FOCUSED_TEST_SHA256:
| | 5754145c7616441ed4986488c766316b7325465e93943dcffa341ef5638075ba
| | STALE_VERIFICATION:
| | - Focused destination tests: 23 passed.
| | - Full repository suite: 171 passed.
| |
| | [CORRECTION_MARKER]
| | - Source fields and EXACT_VALUE expectations now require a closed
| |   JSON value model.
| | - JSON object keys must be strings.
| | - Tuples, sets, custom containers, non-string object keys, and
| |   non-finite floats fail closed.
| | - A binding-current finding is recomputed canonically from the
| |   supplied source and profile and must match the complete expected
| |   finding exactly.
| | - Rehashed omitted, moved, reordered, unknown, invalid-profile, or
| |   extra-field findings fail current evaluation.
| | - finding_hash must contain exactly 64 lowercase hexadecimal
| |   characters.
| |
| | TERMINOLOGY_CORRECTION:
| | SHA-256 supplies deterministic integrity evidence only.
| | It does not authenticate origin. Currentness requires both valid
| | integrity and exact canonical recomputation against bound inputs.
| |
| | CURRENT_IMPLEMENTATION_SHA256:
| | 504e83ed9316ada3a7934416de6a82b1b98814f7e7d5422659520409b17cc1e7
| | CURRENT_FOCUSED_TEST_SHA256:
| | d1fc35ed1ec296ee5bf5b30f297782cbcab000b815fcdf469d1677ac377d52be
| |
| | WINDOWS_HASH_RECEIPT:
| | - certutil matched both current hashes before execution.
| | - spine_protocol self-test: PASS.
| | - Focused destination tests: 34 passed.
| | - Full repository suite: 182 passed.
| |
| | CORRECTED_EXTERNAL_REVIEW: PENDING
| |
| | PRESERVED_LIMIT:
| | Symbolic source and profile hashes remain caller-supplied.
| | Canonical recomputation validates finding semantics against those
| | supplied current inputs; it does not establish external source truth
| | or origin authentication.
| |
| | STATUS:
| | Review 014 remains FAIL against its stale exact hashes.
| | Corrected verification applies only to the current hashes above.
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | Reviews 013 and 014 remain preserved failures.
| | Current exact artifacts pass 34 focused and 182 full tests.
| | Stop before commit until corrected external review completes.
| |}==============================================================|
| |}==============================================================|
| | DESTINATION_EVALUATOR_FOURTH_REVIEW_CORRECTION
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260716-016
| | REVIEW_RESULT: FAIL
| | BLOCKING_FINDINGS: 1
| | NONBLOCKING_FINDINGS: 1
| |
| | PRESERVED_BLOCKING_FINDING:
| | - The physical tail placed the older Review 014 correction after
| |   Review 015, leaving stale hashes and test counts as the apparent
| |   current state despite the append-only correction history.
| |
| | PRESERVED_NONBLOCKING_FINDING:
| | - Cyclic or excessively deep otherwise-JSON-shaped values could
| |   escape the protocol error boundary as raw RecursionError failures.
| |
| | STALE_IMPLEMENTATION_SHA256:
| | 6d0c9eeb270ebcfbae2f2820ada9d517745c6b365ee77e81087309f57a8c4908
| | STALE_FOCUSED_TEST_SHA256:
| | b6d34072a8d64dc3ff45a4d06950bd6154b1b44bf7897571d7834ba44ec40730
| | STALE_VERIFICATION:
| | - Spine protocol self-test: PASS.
| | - Focused destination tests: 40 passed.
| | - Full repository suite: 188 passed.
| |
| | [CORRECTION_MARKER]
| | - No historical review block was reordered, rewritten, or deleted.
| | - This final overlay explicitly supersedes the stale physical tail.
| | - Effective review order is 013 -> 014 -> 015 -> 016.
| | - Closed JSON validation now detects container cycles and enforces
| |   a maximum nesting depth, returning SpineStructureError at the
| |   protocol boundary.
| | - Focused failure paths cover cyclic dictionaries, cyclic lists,
| |   and excessive nesting.
| |
| | CURRENT_IMPLEMENTATION_SHA256:
| | 0eb75d3c105da20b2d8ea35c2296c7602cd1d8975e757dbd49459f5a9433bed5
| | CURRENT_FOCUSED_TEST_SHA256:
| | f7b0ab2e830511200e9e8414a8e32f8d12f0bbb83ba2bec99cca2aba92c5dbce
| |
| | WINDOWS_HASH_RECEIPT:
| | - certutil matched both current hashes before execution.
| | - Spine protocol self-test: PASS.
| | - Focused destination tests: 43 passed.
| | - Full repository suite: FAIL; 190 passed and one Hypothesis timing
| |   test failed after exceeding its 200 ms deadline once, then
| |   completing in 15.43 ms on replay.
| | - Bounded suite excluding only test_hash_chain_monotonicity:
| |   190 passed, 1 deselected.
| |
| | VERIFICATION_SCOPE:
| | The bounded suite is evidence for every executed test except the
| | explicitly deselected timing-sensitive property test. It is not a
| | full-suite pass and does not erase the preserved failed execution.
| |
| | EFFECTIVE_STATE:
| | Review blocks 013, 014, 015, and 016 remain preserved failures
| | against their exact reviewed artifacts. The hashes and receipts in
| | this overlay are the current candidate state. The prior Review 014
| | physical tail is stale and superseded by this append-only overlay.
| |
| | CORRECTED_EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | Current candidate passes its self-test, 43 focused tests, and the
| | bounded 190-test suite. Full-suite verification remains failed due
| | to the preserved Hypothesis deadline event.
| | Stop before commit until corrected external review completes.
| |}==============================================================|
| |}==============================================================|
| | DESTINATION_EVALUATOR_CORRECTED_EXTERNAL_REVIEW
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260716-017
| | REVIEW_RESULT: PASS
| | BLOCKING_FINDINGS: 0
| | NONBLOCKING_FINDINGS: 0
| |
| | EXACT_ARTIFACTS_REVIEWED:
| | IMPLEMENTATION_SHA256:
| | 0eb75d3c105da20b2d8ea35c2296c7602cd1d8975e757dbd49459f5a9433bed5
| | FOCUSED_TEST_SHA256:
| | f7b0ab2e830511200e9e8414a8e32f8d12f0bbb83ba2bec99cca2aba92c5dbce
| | IMPLEMENTATION_MAP_SHA256:
| | 5f778b00898382aa390d852c57f27685007ead20f7478f6ed5f93b5cb89631c4
| |
| | VERIFIED:
| | - Opaque bindings and digests reject surrounding whitespace rather
| |   than silently normalizing identity.
| | - Finding integrity validation rejects malformed, tampered,
| |   authorizing, overlapping, contradictory, and semantically forged
| |   findings before currentness decisions.
| | - Canonical recomputation binds a current finding to the supplied
| |   source and destination profile.
| | - Closed JSON validation detects cyclic lists and dictionaries,
| |   rejects unsupported values, and bounds maximum nesting depth with
| |   SpineStructureError.
| | - Exact comparison preserves value-type identity.
| | - Generated findings retain accepted=false and
| |   write_authority=NONE.
| | - Focused failure paths and the built-in self-test passed review.
| | - Historical Reviews 013 through 016 remain append-only and the
| |   final Review 016 overlay makes their effective order explicit.
| |
| | PRESERVED_EXECUTION_EVIDENCE:
| | - Spine protocol self-test: PASS.
| | - Focused destination tests: 43 passed.
| | - Full repository suite: FORMALLY FAILED; 190 passed and one
| |   Hypothesis deadline failure, with 15.43 ms on replay.
| | - Bounded suite: 190 passed, 1 explicitly deselected.
| |
| | PRESERVED_LIMITS:
| | - The bounded suite is not a substitute full-suite pass.
| | - Source and profile hashes are caller-supplied symbolic bindings,
| |   not independently derived external truth.
| | - SHA-256 supplies deterministic integrity evidence, not origin
| |   authentication.
| | - The evaluator does not authorize acceptance, persistence,
| |   mutation, or external action.
| |
| | REVIEW_SCOPE:
| | This PASS is bound only to the three exact hashes listed above.
| | Any content change makes it stale until separately re-reviewed.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | External Review 017 passed the exact corrected candidate with zero
| | findings. Evidence stops at the preserved limits above.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_DELTA
| |}==============================================================|
| | CLASSIFICATION: PARTIAL_IMPLEMENTATION
| | STATUS: IMPLEMENTED_ON_BRANCH
| | BRANCH: feat/version-bound-ingestion-receipts
| | BASE: main@d968ef55c59c84d3630943955eb5e22a3b49d364
| | IMPLEMENTATION: holosim/embeddings.py
| | FOCUSED_TESTS: tests/test_embeddings_ingestion.py
| |
| | IMPLEMENTATION_SHA256:
| | 9fa06f3f451df9281641749e3de230896ab92ddd6e1305872d9d82895a2ef054
| | FOCUSED_TEST_SHA256:
| | 14ee2bd6f64120b6313c77a15d3e82b832242f904cf6c89d23191c151c9e7739
| |
| | MAPPED_GAP:
| | Existing ingestion selection could silently use an enabled sentence
| | transformer, installed scikit-learn TF-IDF, or token-overlap fallback
| | while returning only a Boolean. The surviving result did not bind the
| | exact inputs, comparison window, threshold, backend, model identity,
| | or environmental conditions that produced the selection.
| |
| | WORKING_THEORY:
| | Similarity may select which objects are useful to retrieve or ingest,
| | but that decision remains reconstructable only when its exact inputs,
| | configuration, method, and result survive in a version-bound receipt.
| |
| | IMPLEMENTED_FUNCTIONS:
| | - compute_similarity_observation(text1, text2)
| | - evaluate_ingestion(candidate, existing_entries, threshold, window)
| | - check_ingestion_receipt_current(receipt, candidate, entries,
| |   threshold, window)
| |
| | IMPLEMENTED_BEHAVIOR:
| | - Existing compute_similarity and should_ingest APIs remain available.
| | - Candidate text and ordered recent comparison entries are bound by
| |   exact SHA-256 digests.
| | - Threshold and recent-window configuration are preserved exactly.
| | - Each comparison records score, backend, backend version, and model
| |   identity where applicable.
| | - Best match, final selection, and reason survive in the receipt.
| | - Candidate, comparison-window, configuration, backend, and observed
| |   score changes produce distinct stale results.
| | - Malformed configuration and non-finite or materially out-of-range
| |   backend scores fail closed.
| | - Floating-point cosine roundoff within 1e-12 is clamped to the valid
| |   range without admitting materially invalid scores.
| | - Receipt-integrity failure and attempts to grant acceptance or write
| |   authority fail closed.
| | - Evaluation does not mutate the candidate collection.
| |
| | PRESERVED_BOUNDARY:
| | Similarity is an observation for retrieval and ingestion selection.
| | It does not establish truth, relevance beyond the configured method,
| | acceptance, authority, or permission to mutate a collection.
| | A SHA-256 receipt supplies deterministic integrity evidence only; it
| | does not authenticate origin or prove that the selected backend is
| | semantically correct.
| |
| | WINDOWS_HASH_RECEIPT:
| | - certutil matched the exact implementation hash before execution.
| | - certutil matched the exact focused-test hash before execution.
| |
| | EXECUTION_RECEIPTS:
| | - Focused ingestion tests: 29 passed.
| | - Full repository suite: FORMALLY FAILED; 219 passed and the existing
| |   Hypothesis test_hash_chain_monotonicity exceeded its 200 ms deadline
| |   at 277 ms.
| | - Bounded suite excluding only that timing-sensitive property test:
| |   219 passed, 1 explicitly deselected.
| |
| | VERIFICATION_SCOPE:
| | The bounded run is not a substitute full-suite pass. The focused run
| | directly supports the ingestion boundary only. The preserved deadline
| | event is not erased or classified as an ingestion failure.
| |
| | NOT_IMPLEMENTED:
| | - persistent vector storage
| | - automatic collection mutation
| | - background environment monitoring
| | - semantic truth evaluation
| | - automatic re-embedding
| | - acceptance or authority
| |
| | EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | Exact implementation and focused tests exist on the branch. Stop
| | before commit until the map is rail-validated and external review is
| | completed against the exact current hashes.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_REVIEW_018_OVERLAY
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260717-018
| | REVIEW_RESULT: FAIL
| | REVIEW_BOUND_IMPLEMENTATION_SHA256:
| | 9fa06f3f451df9281641749e3de230896ab92ddd6e1305872d9d82895a2ef054
| | REVIEW_BOUND_FOCUSED_TEST_SHA256:
| | 14ee2bd6f64120b6313c77a15d3e82b832242f904cf6c89d23191c151c9e7739
| | REVIEW_BOUND_MAP_SHA256:
| | 961f921cf4c984ccfc1b88418057251c65aeee15cdbd2861cc395345809ed166
| |
| | BLOCKING_FINDING:
| | Receipt validation did not form a closed semantic/domain-error
| | boundary. Rehashed malformed or contradictory bodies could be called
| | stale rather than invalid, early stale checks could bypass comparison
| | validation, and cyclic, deeply nested, or non-finite bodies could leak
| | raw serialization exceptions.
| |
| | NONBLOCKING_FINDING:
| | The sentence-transformer model field records the declared mutable
| | alias all-MiniLM-L6-v2 plus package version. It is not an exact model
| | revision or weights digest.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_CORRECTION_OVERLAY
| |}==============================================================|
| | STATUS: CORRECTED_CANDIDATE_AWAITING_REVIEW
| | IMPLEMENTATION_SHA256:
| | f2226e849f57ba99b1b14fafee22c0b1e0d959e0fd3796691e71ea1c690debea
| | FOCUSED_TEST_SHA256:
| | 244bbee54f351a04c3e8e15a13075096f7ef6f0bed7cec26acf43621143922d4
| |
| | CORRECTION:
| | - Validate a bounded, acyclic, finite, plain-JSON domain before
| |   canonical hashing or stale classification.
| | - Validate the exact versioned field set and field types.
| | - Validate ordered comparison indexes and entry-hash correspondence.
| | - Validate score bounds, best-match consistency, decision/reason
| |   consistency, and initial current/stale invariants.
| | - Reject malformed receipts before candidate, configuration, window,
| |   environment, or observation stale classification.
| | - Preserve model_identity as a declared alias, not proof of an exact
| |   model revision or weights digest.
| |
| | CORRECTED_EXECUTION_RECEIPTS:
| | - Focused ingestion tests: 43 passed in 0.39 s.
| | - Full repository suite: FORMALLY FAILED; 233 passed and the existing
| |   Hypothesis test_hash_chain_monotonicity exceeded its 200 ms deadline
| |   at 264.68 ms.
| | - Bounded suite excluding only that timing-sensitive property test:
| |   233 passed, 1 explicitly deselected in 5.68 s.
| |
| | VERIFICATION_SCOPE:
| | The bounded run is not a substitute full-suite pass. Review 018 does
| | not transfer to these corrected hashes. A new external review is
| | required before commit.
| |
| | EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | The corrected candidate closes the identified validation boundary in
| | focused execution. Stop before commit until rail validation and a new
| | external review bind these exact corrected artifacts.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_REVIEW_019_OVERLAY
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260717-019
| | REVIEW_RESULT: FAIL
| | REVIEW_BOUND_IMPLEMENTATION_SHA256:
| | f2226e849f57ba99b1b14fafee22c0b1e0d959e0fd3796691e71ea1c690debea
| | REVIEW_BOUND_FOCUSED_TEST_SHA256:
| | 244bbee54f351a04c3e8e15a13075096f7ef6f0bed7cec26acf43621143922d4
| | REVIEW_BOUND_MAP_SHA256:
| | 1f90ea78bcb26f675a7f673b8c2d4bea941f3196596fa14f96d097cf6f6d7fc1
| |
| | BLOCKING_FINDING:
| | Python equality allowed Boolean values to impersonate integer receipt
| | fields: version true could equal version 1, and a Boolean comparison
| | index could equal its integer position. Comparison count was also not
| | constrained by the declared recent window.
| |
| | TEST_FINDING:
| | The 43 focused tests did not falsify Boolean substitution for integer
| | fields or comparison-count/window inconsistency.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_CORRECTION_019_OVERLAY
| |}==============================================================|
| | STATUS: CORRECTED_CANDIDATE_AWAITING_REVIEW
| | IMPLEMENTATION_SHA256:
| | 59874531d24832739a863573aaf3b39ca7f5bed62dd5acb16972fa19a8d18d6c
| | FOCUSED_TEST_SHA256:
| | d49f9fa9fb314ef718f204b1a87532bf85ee037e82ec046fc399faebbee6c74d
| |
| | CORRECTION:
| | - Receipt version requires exact integer type before value comparison.
| | - Every comparison index requires exact integer type and ordered value.
| | - Comparison count cannot exceed the declared recent window.
| | - Focused tests cover Boolean version substitution, Boolean comparison
| |   index substitution, and comparison-count/window contradiction.
| |
| | CORRECTED_EXECUTION_RECEIPTS:
| | - Focused ingestion tests: 46 passed in 0.38 s.
| | - Full repository suite: FORMALLY FAILED; 236 passed and the existing
| |   Hypothesis test_hash_chain_monotonicity produced a flaky deadline
| |   failure: 277.33 ms initially and 18.15 ms on replay against 200 ms.
| | - Bounded suite excluding only that timing-sensitive property test:
| |   236 passed, 1 explicitly deselected in 5.63 s.
| |
| | VERIFICATION_SCOPE:
| | The bounded run is not a substitute full-suite pass. Review 019 does
| | not transfer to these corrected hashes. A new external review is
| | required before commit.
| |
| | EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | The second corrected candidate closes the exact integer and declared
| | window findings in focused execution. Stop before commit until rail
| | validation and a new review bind these exact artifacts.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_REVIEW_020_OVERLAY
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260717-020
| | REVIEW_RESULT: FAIL
| | REVIEW_BOUND_IMPLEMENTATION_SHA256:
| | 59874531d24832739a863573aaf3b39ca7f5bed62dd5acb16972fa19a8d18d6c
| | REVIEW_BOUND_FOCUSED_TEST_SHA256:
| | d49f9fa9fb314ef718f204b1a87532bf85ee037e82ec046fc399faebbee6c74d
| | REVIEW_BOUND_MAP_SHA256:
| | 7a426805a5970aa5b74386904093db156a854d727582d4b528780ce6b1c24eb6
| |
| | VERIFIED_PRIOR_CORRECTIONS:
| | Exact integer version and comparison indexes, comparison-count/window
| | consistency, validation ordering, and their focused falsifiers passed
| | review.
| |
| | BLOCKING_FINDING:
| | Arbitrarily large plain-JSON integers could leak raw OverflowError
| | during float conversion for thresholds, backend scores, or rehashed
| | receipt values instead of failing through IngestionReceiptError.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_CORRECTION_020_OVERLAY
| |}==============================================================|
| | STATUS: CORRECTED_CANDIDATE_AWAITING_REVIEW
| | IMPLEMENTATION_SHA256:
| | 7f6f1030326305a4f3262b17fb14d8f94ec5c2803f7c7d57c85c2457a4bf2abf
| | FOCUSED_TEST_SHA256:
| | 27db52658def14889587c726485458d9a4b2e205bc7e11de8299b1c33436828e
| |
| | CORRECTION:
| | - Threshold conversion catches numeric overflow and raises the receipt
| |   domain error.
| | - Backend-score conversion catches numeric overflow and raises the
| |   receipt domain error.
| | - Stored receipt-score conversion catches numeric overflow before any
| |   stale classification.
| | - Focused tests cover oversized evaluation thresholds, backend scores,
| |   and rehashed threshold/comparison scores on an early stale path.
| |
| | TEST_CORRECTION_RECEIPT:
| | The first rehashed oversized fixture used a 10,001-digit integer that
| | Python refused to JSON-encode before reaching the implementation. That
| | test attempt failed with ValueError. The fixture was corrected to a
| | JSON-encodable 401-digit integer that still overflows float conversion.
| |
| | CORRECTED_EXECUTION_RECEIPTS:
| | - Focused ingestion tests: 50 passed in 0.39 s.
| | - Full repository suite: FORMALLY FAILED; 240 passed and the existing
| |   Hypothesis test_hash_chain_monotonicity exceeded its 200 ms deadline
| |   at 307.77 ms.
| | - Bounded suite excluding only that timing-sensitive property test:
| |   240 passed, 1 explicitly deselected in 5.78 s.
| |
| | VERIFICATION_SCOPE:
| | The bounded run is not a substitute full-suite pass. Review 020 does
| | not transfer to these corrected hashes. A new external review is
| | required before commit.
| |
| | EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | The third corrected candidate closes the reviewed numeric conversion
| | boundary in focused execution. Stop before commit until rail validation
| | and a new review bind these exact artifacts.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_REVIEW_021_OVERLAY
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260717-021
| | REVIEW_RESULT: FAIL
| | REVIEW_BOUND_IMPLEMENTATION_SHA256:
| | 7f6f1030326305a4f3262b17fb14d8f94ec5c2803f7c7d57c85c2457a4bf2abf
| | REVIEW_BOUND_FOCUSED_TEST_SHA256:
| | 27db52658def14889587c726485458d9a4b2e205bc7e11de8299b1c33436828e
| | REVIEW_BOUND_MAP_SHA256:
| | e11a375c0769f34479d45ed758a59dd4028f725384198da04429506f810191df
| |
| | VERIFIED_PRIOR_CORRECTION:
| | Oversized thresholds, backend scores, and stored receipt scores fail
| | through IngestionReceiptError as required.
| |
| | BLOCKING_FINDING:
| | recent_window remained an unbounded positive integer. An enormous
| | value could reach receipt serialization and leak raw ValueError rather
| | than the receipt domain error.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_CORRECTION_021_OVERLAY
| |}==============================================================|
| | STATUS: CORRECTED_CANDIDATE_AWAITING_REVIEW
| | IMPLEMENTATION_SHA256:
| | 3e0afa7de6b686d5a567e76a1d2bc1e26f1ada06289d0fd7df5882accc16a8f7
| | FOCUSED_TEST_SHA256:
| | 7d1b3fc3f540d4487e64ea89b1f8bc726b0811a52110db8459a9a47e4aa692a7
| |
| | CORRECTION:
| | - recent_window requires an exact integer from 1 through 1,000,000.
| | - Final receipt canonicalization translates serialization failures to
| |   IngestionReceiptError.
| | - Focused tests cover oversized evaluation configuration, currentness
| |   configuration, and a rehashed stored window before stale paths.
| |
| | CORRECTED_EXECUTION_RECEIPTS:
| | - Focused ingestion tests: 53 passed in 0.41 s.
| | - Full repository suite: 244 passed in 6.69 s.
| |
| | VERIFICATION_SCOPE:
| | The clean full-suite pass binds only the exact corrected implementation
| | and test hashes above. Review 021 does not transfer to these artifacts.
| | A new external review is required before commit.
| |
| | EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | The fourth corrected candidate closes the reviewed configuration and
| | canonicalization boundary. Stop before commit until rail validation and
| | a new review bind these exact artifacts.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_REVIEW_022_OVERLAY
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260717-022
| | REVIEW_RESULT: FAIL
| | REVIEW_BOUND_IMPLEMENTATION_SHA256:
| | 3e0afa7de6b686d5a567e76a1d2bc1e26f1ada06289d0fd7df5882accc16a8f7
| | REVIEW_BOUND_FOCUSED_TEST_SHA256:
| | 7d1b3fc3f540d4487e64ea89b1f8bc726b0811a52110db8459a9a47e4aa692a7
| | REVIEW_BOUND_MAP_SHA256:
| | 0ad441a334970cdabf3ed556d25fa3e4bdf97bb475927f5d51b4980da832a8a8
| |
| | VERIFIED_PRIOR_CORRECTION:
| | The bounded recent window and final canonicalization exception wrapper
| | passed review.
| |
| | BLOCKING_FINDINGS:
| | - A nonempty comparison with an exact score of -1.0 selected no best
| |   comparison, producing a receipt inconsistent with its own evidence.
| | - Lone-surrogate strings could leak raw UnicodeEncodeError during text
| |   hashing or receipt canonicalization.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_CORRECTION_022_OVERLAY
| |}==============================================================|
| | STATUS: CORRECTED_CANDIDATE_AWAITING_REVIEW
| | IMPLEMENTATION_SHA256:
| | 580d0dbd58e9cda3bbb62c6cb4b2fd9ac3767f01b3431fe4e73f4f2ac370dbaa
| | FOCUSED_TEST_SHA256:
| | f2fd346ff595ce5df8e9489e81572b125c4ad351203aca605a0adc0ff497b23b
| |
| | CORRECTION:
| | - The first comparison is selected as best even when its score is
| |   exactly -1.0; later comparisons replace it only with a higher score.
| | - Text hashing translates invalid UTF-8 surrogate input to
| |   IngestionReceiptError.
| | - Closed receipt JSON validation rejects strings that cannot encode as
| |   UTF-8 before hashing or stale classification.
| | - Canonicalization wrappers include UnicodeError.
| | - Focused tests cover exact -1.0 currentness, surrogate candidate and
| |   entry text, and a surrogate stored receipt string on a stale path.
| |
| | CORRECTED_EXECUTION_RECEIPTS:
| | - Focused ingestion tests: 57 passed in 0.40 s.
| | - Full repository suite: FORMALLY FAILED; 247 passed and the existing
| |   Hypothesis test_hash_chain_monotonicity produced a flaky deadline
| |   failure: 264.33 ms initially and 15.32 ms on replay against 200 ms.
| | - Bounded suite excluding only that timing-sensitive property test:
| |   247 passed, 1 explicitly deselected in 5.54 s.
| |
| | VERIFICATION_SCOPE:
| | The bounded run is not a substitute full-suite pass. Review 022 does
| | not transfer to these corrected hashes. A new external review is
| | required before commit.
| |
| | EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | The fifth corrected candidate closes the reviewed score-selection and
| | UTF-8 domain boundaries. Stop before commit until rail validation and a
| | new review bind these exact artifacts.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_REVIEW_023_OVERLAY
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260717-023
| | REVIEW_RESULT: FAIL
| | REVIEW_BOUND_IMPLEMENTATION_SHA256:
| | 580d0dbd58e9cda3bbb62c6cb4b2fd9ac3767f01b3431fe4e73f4f2ac370dbaa
| | REVIEW_BOUND_FOCUSED_TEST_SHA256:
| | f2fd346ff595ce5df8e9489e81572b125c4ad351203aca605a0adc0ff497b23b
| | REVIEW_BOUND_MAP_SHA256:
| | d16a0c0d15a7d180f36b9c03cfae01d8636cb8f0164adb59517be0269f7aea02
| |
| | VERIFIED_PRIOR_CORRECTIONS:
| | Exact -1.0 best-match selection and ordinary surrogate candidate,
| | entry, and stored-receipt rejection passed review.
| |
| | BLOCKING_FINDING:
| | Accepted input shapes could still leak raw exceptions: hostile string
| | subclasses, entries with failing string conversion, and non-iterable
| | existing-entry collections escaped the receipt error boundary.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_CORRECTION_023_OVERLAY
| |}==============================================================|
| | STATUS: CORRECTED_CANDIDATE_AWAITING_REVIEW
| | IMPLEMENTATION_SHA256:
| | 0a1587deb81b2b9f9a3ac72241ac075535ecca109d2cf480501aa5f5e127c7e6
| | FOCUSED_TEST_SHA256:
| | 3de8745a7ff05cbefd47fe0e749911d6353a5693848967885f3d3790726b64f9
| |
| | CORRECTION:
| | - Candidate inputs require exact plain-string type in evaluation and
| |   currentness checks.
| | - Extracted mapping text requires exact plain-string type.
| | - Entry string conversion failures translate to IngestionReceiptError.
| | - Entry-collection materialization failures translate to
| |   IngestionReceiptError.
| | - Focused tests cover hostile string-subclass candidates, failing entry
| |   conversion, and non-iterable collections in both public paths.
| |
| | CORRECTED_EXECUTION_RECEIPTS:
| | - Focused ingestion tests: 62 passed in 0.44 s.
| | - Full repository suite: 253 passed in 6.31 s.
| |
| | VERIFICATION_SCOPE:
| | The clean full-suite pass binds only the exact corrected implementation
| | and test hashes above. Review 023 does not transfer to these artifacts.
| | A new external review is required before commit.
| |
| | EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | The sixth corrected candidate closes the reviewed accepted-shape error
| | boundary. Stop before commit until rail validation and a new review bind
| | these exact artifacts.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_INGESTION_RECEIPT_REVIEW_024_OVERLAY
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260717-024
| | REVIEW_RESULT: PASS
| | REVIEW_BOUND_IMPLEMENTATION_SHA256:
| | 0a1587deb81b2b9f9a3ac72241ac075535ecca109d2cf480501aa5f5e127c7e6
| | REVIEW_BOUND_FOCUSED_TEST_SHA256:
| | 3de8745a7ff05cbefd47fe0e749911d6353a5693848967885f3d3790726b64f9
| | REVIEW_BOUND_MAP_SHA256:
| | 18819e45d93503227a78801a89d306df6d51b146bdf414546cc15be52b238aa1
| |
| | REVIEW_VERIFICATION:
| | - Review 023 accepted-shape corrections hold.
| | - Schema, hash, semantic, numeric, UTF-8, depth, cycle, window, and
| |   authority boundaries hold within reviewed scope.
| | - Validation precedes stale classification.
| | - Generators are materialized once per public receipt call.
| | - No candidate collection mutation or authority grant was found.
| | - Focused 62-pass and full 253-pass receipts agree with the map.
| |
| | BLOCKING_FINDINGS: NONE
| |
| | PRESERVED_LIMITS:
| | The sentence model alias and backend/model labels are observational and
| | not independently authenticated. The receipt self-hash establishes
| | deterministic integrity, not origin authentication.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | External Review 024 passed the exact corrected candidate with no
| | blocking findings. Evidence stops at the bound hashes and stated limits.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_CALIBRATION_RECEIPT_DELTA
| |}==============================================================|
| | CLASSIFICATION: PARTIAL_IMPLEMENTATION
| | STATUS: IMPLEMENTED_ON_BRANCH
| | BRANCH: feat/version-bound-calibration-receipts
| | BASE: main@4dc0f7e84bc963c490d9be9f327c22fb9b99a395
| | IMPLEMENTATION: holosim/calibration.py
| | FOCUSED_TESTS: tests/test_calibration.py
| |
| | IMPLEMENTATION_SHA256:
| | 0dd727ba1562e0ffdec0c03dce8602fbd008ffc4ebb250422a5024a6f0b0dace
| | FOCUSED_TEST_SHA256:
| | 85fccc0980e89e65aef323166686bcd250947456102019e965886bd05af246e9
| |
| | MAPPED_GAP:
| | The chain preserved claims, evidence, corrections, revalidations,
| | staleness, retrieval observations, and authority boundaries, but it
| | could not compare past numerical confidence with later resolved binary
| | outcomes under an exact version-bound calculation.
| |
| | WORKING_THEORY:
| | Comparing retained forecast confidence with later resolved outcomes can
| | expose bounded forecast error and supply information for future
| | correction. The resulting score applies only to the exact supplied
| | history; it does not establish universal calibration or truth.
| |
| | IMPLEMENTED_FUNCTIONS:
| | - evaluate_forecast_calibration(records)
| | - check_calibration_receipt_current(receipt, records)
| |
| | IMPLEMENTED_BEHAVIOR:
| | - Accepts ordered, uniquely identified, resolved binary forecasts.
| | - Binds normalized records and each ordered record with SHA-256.
| | - Calculates sample count, Brier score, mean stated confidence,
| |   observed outcome frequency, and absolute aggregate gap.
| | - Empty history returns INSUFFICIENT_DATA without invented metrics.
| | - Changed confidence, outcome, order, addition, or removal makes the
| |   prior receipt stale.
| | - Duplicate IDs, unresolved outcomes, Boolean confidence, non-finite or
| |   out-of-range confidence, malformed records, hostile identifiers,
| |   materialization failures, and oversized histories fail closed.
| | - Receipt schema, integrity, semantics, depth, cycles, finite values,
| |   acceptance, and authority are validated before stale classification.
| | - Evaluation does not mutate the supplied history.
| |
| | TEST_CORRECTION_RECEIPT:
| | The first oversized confidence fixture used a 10,001-digit integer.
| | Pytest attempted to stringify it while constructing the parameter ID and
| | failed collection before executing the implementation. The fixture was
| | corrected to a 401-digit integer, which remains printable and still
| | overflows float conversion.
| |
| | EXECUTION_RECEIPTS:
| | - Focused calibration tests: 53 passed in 0.37 s.
| | - Full repository suite: FORMALLY FAILED; 305 passed and the existing
| |   Hypothesis test_hash_chain_monotonicity produced a flaky deadline
| |   failure: 268.79 ms initially and 15.66 ms on replay against 200 ms.
| | - Bounded suite excluding only that timing-sensitive property test:
| |   305 passed, 1 explicitly deselected in 6.03 s.
| |
| | VERIFICATION_SCOPE:
| | The bounded run is not a substitute full-suite pass. Brier score is a
| | proper score for supplied binary probabilistic forecasts, but one sample
| | aggregate does not independently establish population calibration.
| | Sample selection, outcome quality, dependence, resolution, bin-level
| | reliability, and future performance remain outside this receipt.
| |
| | NOT_IMPLEMENTED:
| | - automatic confidence correction
| | - unresolved or non-binary outcome scoring
| | - calibration bins or reliability diagrams
| | - sample-independence or selection-bias proof
| | - outcome truth adjudication
| | - collection mutation
| | - acceptance or authority
| |
| | EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | Exact implementation and focused tests exist on the branch. Stop before
| | commit until rail validation and external review bind these artifacts.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_CALIBRATION_RECEIPT_REVIEW_025_OVERLAY
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260718-025
| | REVIEW_RESULT: FAIL
| | REVIEW_BOUND_IMPLEMENTATION_SHA256:
| | 0dd727ba1562e0ffdec0c03dce8602fbd008ffc4ebb250422a5024a6f0b0dace
| | REVIEW_BOUND_FOCUSED_TEST_SHA256:
| | 85fccc0980e89e65aef323166686bcd250947456102019e965886bd05af246e9
| | REVIEW_BOUND_MAP_SHA256:
| | 2f36b699b15de790017201f4bd0ad7fd3b96fbde83e603b44c0f785d57afbcf9
| |
| | BLOCKING_FINDING:
| | Forecast-record schema comparison constructed a set before requiring
| | exact plain-string keys. A hostile string-subclass key could execute
| | custom equality and leak RuntimeError outside CalibrationReceiptError.
| |
| | NONBLOCKING_EPISTEMIC_FINDINGS:
| | Brier score measures probabilistic forecast performance, not calibration
| | alone. Aggregate mean gap can conceal subgroup or bin miscalibration.
| | Caller-supplied triples do not establish provenance, subject identity,
| | pre-outcome forecast timing, or outcome truth.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | VERSION_BOUND_CALIBRATION_RECEIPT_CORRECTION_025_OVERLAY
| |}==============================================================|
| | STATUS: CORRECTED_CANDIDATE_AWAITING_REVIEW
| | IMPLEMENTATION_SHA256:
| | 9bd384916ca2fccb464edac1d4736f4b99df0846b3646c01b7ec9ac6ff3cd345
| | FOCUSED_TEST_SHA256:
| | c258886beb3e31dc00bf3d25921dde3fe676d78d0e3b5ae5421b1725b8a353e6
| |
| | CORRECTION:
| | - Materialize record keys without equality-based schema comparison.
| | - Require every record key to have exact plain-string type.
| | - Compare against the required schema only after exact key validation.
| | - Focused tests cover hostile string-subclass keys in evaluation and
| |   currentness paths.
| |
| | CORRECTED_EXECUTION_RECEIPTS:
| | - Focused calibration tests: 55 passed in 0.42 s.
| | - Full repository suite: FORMALLY FAILED; 307 passed and the existing
| |   Hypothesis test_hash_chain_monotonicity produced a flaky deadline
| |   failure: 279.16 ms initially and 17.61 ms on replay against 200 ms.
| | - Bounded suite excluding only that timing-sensitive property test:
| |   307 passed, 1 explicitly deselected in 6.06 s.
| |
| | PRESERVED_LIMITS:
| | The receipt scores supplied resolved triples only. It does not establish
| | forecast provenance, subject attribution, pre-outcome commitment,
| | independence, representative sampling, outcome truth, bin-level
| | reliability, universal calibration, or future performance.
| |
| | VERIFICATION_SCOPE:
| | The bounded run is not a substitute full-suite pass. Review 025 does not
| | transfer to the corrected hashes. A new review is required before commit.
| |
| | EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | The corrected candidate closes the reviewed hostile-key boundary. Stop
| | before commit until rail validation and a new external review bind the
| | exact corrected artifacts.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_CALIBRATION_RECEIPT_REVIEW_026_OVERLAY
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260718-026
| | REVIEW_RESULT: PASS
| | REVIEW_BOUND_IMPLEMENTATION_SHA256:
| | 9bd384916ca2fccb464edac1d4736f4b99df0846b3646c01b7ec9ac6ff3cd345
| | REVIEW_BOUND_FOCUSED_TEST_SHA256:
| | c258886beb3e31dc00bf3d25921dde3fe676d78d0e3b5ae5421b1725b8a353e6
| | REVIEW_BOUND_MAP_SHA256:
| | ba20d9c858c461bccb76062f7c2503d4d7cb0994623d856fb26a80a52a4fb931
| |
| | REVIEW_VERIFICATION:
| | - Review 025 hostile-key correction holds in evaluation and currentness.
| | - Validation fails closed before stale classification.
| | - Brier calculations, ordered history binding, same-history currentness,
| |   changed-outcome staleness, and nonmutation passed independent checks.
| | - Schema, integrity, semantic, numeric, depth, cycle, acceptance, and
| |   authority boundaries held within reviewed scope.
| | - Execution receipts and append-only map claims agree.
| |
| | BLOCKING_FINDINGS: NONE
| |
| | NONBLOCKING_LIMIT:
| | Receipt calculation identity relies on method and schema-version
| | discipline. Individual receipts do not embed the implementation artifact
| | hash that executed the calculation.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | External Review 026 passed the exact corrected calibration candidate
| | with no blocking findings. Evidence stops at the bound hashes and limits.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_THEORY_STATE_DELTA
| |}==============================================================|
| | STATUS: IMPLEMENTED_CANDIDATE_AWAITING_REVIEW
| | BRANCH: feat/version-bound-theory-states
| | BASE: main@71577f6
| | IMPLEMENTATION: holosim/theory.py
| | IMPLEMENTATION_SHA256:
| | f43f58c2d36f96666bea970b5fbcdab914ae43c1688fac2c40e717333af9c39f
| | FOCUSED_TEST: tests/test_theory.py
| | FOCUSED_TEST_SHA256:
| | f0dd3f94448195731e4af27d4991e248f4935f1a80c2bb6ec67a53471b5e06ff
| |
| | CONCRETE_MISSING_FUNCTION:
| | The repository could generate falsifying examples with Hypothesis, but
| | had no first-class state for a theory that distinguishes possibility,
| | contradiction, unavailable checks, and untested predictions. It could
| | not bind that navigation state to the exact theory and checks evaluated.
| |
| | WORKING_THEOREM:
| | A supplied theory remains POSSIBLE only when it has predictions and none
| | of the supplied checks contradict them. Consistency does not establish
| | truth, proof, probability, or acceptance. A supplied contradiction can
| | falsify the evaluated theory state. Missing checks remain explicit.
| |
| | IMPLEMENTED_FUNCTIONS:
| | - evaluate_theory_state(theory, checks)
| | - check_theory_receipt_current(receipt, theory, checks)
| |
| | STATE_RULES:
| | - POSSIBLE: at least one prediction exists and no supplied check has the
| |   outcome CONTRADICTED.
| | - FALSIFIED: at least one supplied check has outcome CONTRADICTED.
| | - UNTESTABLE: the supplied theory has no predictions.
| | - CONSISTENT never upgrades POSSIBLE to true, proven, or probable.
| | - UNAVAILABLE identifies a check that did not test its prediction.
| | - accepted is always false and write_authority is always NONE.
| |
| | NAVIGATION_OUTPUT:
| | The receipt preserves checked and unchecked prediction identifiers,
| | unavailable checks, contradictions, and the next missing prediction and
| | action. Ordering is deterministic and bound into the receipt integrity.
| |
| | VERSION_BINDING_AND_STALENESS:
| | The receipt binds canonical hashes of the exact theory and ordered checks
| | evaluated. Currentness reconstructs the expected receipt from the supplied
| | material. Changed theory is classified before old checks are reinterpreted;
| | changed observations are stale and prior evaluation is not inherited.
| |
| | FAIL_CLOSED_BOUNDARIES:
| | - Exact plain container, scalar, and key types are required.
| | - Schemas are closed and hostile string-subclass keys are rejected before
| |   equality-based schema comparison.
| | - Collections are materialized within explicit bounds and generators are
| |   consumed once per public currentness evaluation.
| | - Duplicate identifiers and unknown prediction references are rejected.
| | - Input length, collection size, nesting depth, cycles, numeric-like
| |   coercion paths, receipt integrity, semantics, acceptance, and authority
| |   are validated with domain errors.
| | - Evaluation and currentness are read-only and do not mutate inputs.
| |
| | EXECUTION_RECEIPTS:
| | - Focused theory tests: 65 passed in 0.46 s.
| | - Full repository suite: FORMALLY FAILED; 372 passed and the existing
| |   Hypothesis test_hash_chain_monotonicity produced a flaky deadline
| |   failure: 263.53 ms initially and 17.62 ms on replay against 200 ms.
| | - Bounded suite excluding only that timing-sensitive property test:
| |   372 passed, 1 explicitly deselected in 5.44 s.
| |
| | EXECUTED_ARTIFACT_BINDING:
| | The uploaded executed implementation and focused test files match the
| | handed source content. Their only byte-level difference is removal of the
| | final newline by the Windows save path. The hashes above are the exact
| | files used for the recorded executions.
| |
| | PRESERVED_LIMITS:
| | - The module does not validate the mathematical derivation or basis.
| | - It does not authenticate evidence or establish evidence quality.
| | - It does not prove that a check method is correct or independent.
| | - POSSIBLE is not probability, confirmation, proof, or truth.
| | - FALSIFIED is bound only to supplied checks and their asserted outcomes.
| | - It does not revise theories automatically or mutate a chain.
| | - It grants no authority to accept, publish, or act on a theory.
| |
| | VERIFICATION_SCOPE:
| | The focused and bounded executions bind behavior only to the exact hashes
| | recorded above. The bounded run is not a substitute full-suite pass. Rail
| | validation and independent external review remain required before commit.
| |
| | EXTERNAL_REVIEW: PENDING
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | The smallest falsifiable theory-state mechanism is implemented. Stop at
| | the recorded evidence until rail validation and external review complete.
| |}==============================================================|
| |}==============================================================|
| | VERSION_BOUND_THEORY_STATE_REVIEW_027_OVERLAY
| |}==============================================================|
| | REVIEW_ID: HOLO-EXT-REV-20260718-027
| | REVIEW_RESULT: PASS
| | REVIEW_BOUND_IMPLEMENTATION_SHA256:
| | f43f58c2d36f96666bea970b5fbcdab914ae43c1688fac2c40e717333af9c39f
| | REVIEW_BOUND_FOCUSED_TEST_SHA256:
| | f0dd3f94448195731e4af27d4991e248f4935f1a80c2bb6ec67a53471b5e06ff
| | REVIEW_BOUND_MAP_SHA256:
| | f7f66db761ddb82b6c5bd138f1b534f5bd7b25b721ff7493406f0f04d7043379
| |
| | REVIEW_VERIFICATION:
| | - Exact artifact hashes match the reviewed implementation, tests, and map.
| | - Exact-type and closed-schema normalization precede equality-sensitive
| |   comparisons, including hostile-key rejection.
| | - Bounded materialization converts generator failures to domain errors;
| |   unchanged-theory currentness consumes supplied checks once.
| | - Theory identity is checked before old checks can be reinterpreted.
| | - Ordered check hashes bind content, addition, removal, and reordering.
| | - Receipt schema, integrity, and semantic regeneration occur before stale
| |   classification; authority and acceptance remain NONE and false.
| | - POSSIBLE never becomes truth, proof, or probability. UNAVAILABLE remains
| |   unresolved, and asserted contradiction yields receipt-bound FALSIFIED.
| | - Tests cover state transitions, unavailable and later-resolved checks,
| |   staleness ordering, hostile keys, malformed and duplicate identifiers,
| |   unknown references, generator behavior, nonmutation, tampering, numeric
| |   boundaries, cycles, depth, acceptance, and authority.
| | - Recorded execution claims agree with the reviewed map. The reviewer did
| |   not claim independent execution of the Windows receipts.
| |
| | BLOCKING_FINDINGS: NONE
| |
| | NONBLOCKING_LIMITS:
| | - Evidence and check outcomes are caller-supplied and unauthenticated.
| | - Mathematical basis and check-method correctness are not validated.
| | - Individual receipts do not embed the implementation artifact hash.
| | - Input items, text, and depth are bounded, but there is no separate total
| |   canonical receipt-byte cap beyond those constraints.
| |
| | ACCEPTED: false
| | WRITE_AUTHORITY: NONE
| |}==============================================================|
| | TERMINAL
| | External Review 027 passed the exact theory-state candidate with no
| | blocking findings. Evidence stops at the bound hashes and stated limits.
| |}==============================================================|
