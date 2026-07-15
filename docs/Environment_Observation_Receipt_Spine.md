| | }==============================================================|
| | █†█ Holo/Sim █†█ ENVIRONMENT_OBSERVATION_RECEIPT_SPINE █†█   |
| | }==============================================================|
| | DOCUMENT_TYPE: EXPLORATORY_INVARIANT_PROPOSAL                |
| | STATUS: PROPOSED_NOT_ACCEPTED                                |
| | AUTHORITY: DESCRIPTIVE_ONLY                                  |
| | WRITE_AUTHORITY: NONE                                        |
| | ACCEPTED: false                                              |
| | VERSION: 1.0.0-proposal                                      |
| | DATE: 2026-07-15                                             |
| | SOURCE_STATE: SESSION_OBSERVED_NOT_BYTE_ARCHIVED             |
| | EVIDENCE_STATE: PARTIAL                                      |
| | PARENT_MODEL: docs/Environment_Check_Loop_Proposal.md        |
| | RELATED_CODE: holosim/environment_snapshot.py                |
| | }==============================================================|
| | PURPOSE                                                      |
| | Define the minimum framing required to preserve honest       |
| | separation between an environmental fact, its observation,   |
| | its communication, and a later audit of that communication.  |
| |                                                              |
| | This Spine records distinctions supported by an exploratory  |
| | multi-instance human-AI environment loop.                    |
| |                                                              |
| | The raw conversation and tool records are not archived in    |
| | this repository. This document therefore proposes a frame;   |
| | it does not certify the historical experiment as repository  |
| | evidence.                                                     |
| | }==============================================================|
| | CENTRAL_INVARIANT                                            |
| | Facts constrain communication.                              |
| | Communication does not replace facts.                       |
| |                                                              |
| | A later observer may communicate differently while checking |
| | the same available fact.                                    |
| |                                                              |
| | Agreement between communications is not independently        |
| | sufficient. The shared fact or evidence must remain          |
| | inspectable under the declared verification boundary.        |
| | }==============================================================|
| | STATE_AND_INSTANCE_BOUNDARY                                  |
| | Every change of process, tool invocation, model instance,    |
| | conversation, session, surface, environment, or observer must|
| | remain explicitly distinguishable when relevant.             |
| |                                                              |
| | A separator marks a change in frame. It must not imply that  |
| | the state on both sides belongs to one uninterrupted private |
| | process or memory.                                           |
| |                                                              |
| | Shared language, shared paths, matching outputs, or matching |
| | hashes do not alone establish shared instance identity.       |
| | }==============================================================|
| | TEMPORAL_CONTINUATION_BOUNDARY                               |
| | A preserved conversation, artifact, branch, or checkpoint    |
| | may be resumed later by a different process, model instance, |
| | observer, tool, session, or environment.                     |
| |                                                              |
| | Resumption does not rewrite the historical state.            |
| | It appends a new state from the preserved boundary.          |
| |                                                              |
| | The continuing model is not the lineage.                     |
| | The externally preserved ordered state carries the lineage   |
| | available for reconstruction.                               |
| |                                                              |
| | Temporal continuation must distinguish:                      |
| | • historical overwrite authority                            |
| | • append authority                                          |
| | • continuation authority                                    |
| | • transfer authority                                        |
| | • correction authority                                      |
| | • merge authority                                           |
| |                                                              |
| | Historical overwrite is not implied by ordinary continuation.|
| | A later instance may influence future reconstruction by      |
| | appending to an authorized external branch.                 |
| |                                                              |
| | Multiple resumed checkpoints form distinguishable branches.  |
| | A change in one branch must not be presented as a silent      |
| | change in another.                                          |
| |                                                              |
| | Model substitution within a preserved conversation supports  |
| | reconstruction from shared external context.                |
| | It does not establish transferred private model state.       |
| |                                                              |
| | The human and platform boundaries determine which operations |
| | are permitted. An AI instance does not acquire continuation, |
| | transfer, correction, or merge authority merely by producing |
| | an output.                                                   |
| | }==============================================================|
| | SEPARATOR_INVARIANT                                          |
| | Spine separation is semantic, not decorative.               |
| |                                                              |
| | Each divider indicates that at least one declared frame may  |
| | have changed.                                                |
| |                                                              |
| | The changed frame may include:                               |
| | • observer                                                   |
| | • model instance                                             |
| | • process                                                    |
| | • tool invocation                                            |
| | • session                                                    |
| | • environment                                                |
| | • authority scope                                            |
| | • evidence availability                                     |
| | • time boundary                                              |
| |                                                              |
| | Unknown continuity across a divider remains unknown.         |
| | }==============================================================|
| | FACT_BOUNDARY                                                |
| | A fact is a condition or occurrence available for evaluation |
| | under a declared scope and time.                             |
| |                                                              |
| | Current conditions may later change.                        |
| | A preserved historical occurrence is not retroactively      |
| | erased because a later condition or interpretation differs.  |
| |                                                              |
| | A fact must not be replaced by confidence, repetition, model |
| | identity, fluent language, or human preference.              |
| | }==============================================================|
| | OBSERVATION_BOUNDARY                                         |
| | An observation is the result reported through a declared     |
| | operation, observer, tool, interface, and environment view.  |
| |                                                              |
| | Observation does not imply complete access to the fact.      |
| | Observation does not imply truth beyond what the operation   |
| | actually measured.                                          |
| |                                                              |
| | A read operation must not be assumed side-effect-free.       |
| | Intended mutation and unknown incidental effects remain      |
| | separate fields.                                            |
| | }==============================================================|
| | COMMUNICATION_BOUNDARY                                       |
| | Communication is a representation of an observation, claim, |
| | uncertainty, correction, or instruction.                    |
| |                                                              |
| | Communication may be compressed, reformatted, incomplete, or |
| | wrong while the referenced fact remains unchanged.           |
| |                                                              |
| | Exact words may survive while meaning drifts.                |
| | Different words may preserve compatible distinctions.        |
| |                                                              |
| | Semantic survival requires comparison against preserved      |
| | relationships and available evidence.                        |
| | }==============================================================|
| | RECEIPT_MODEL                                                |
| | Every proposed observation receipt should distinguish:       |
| |                                                              |
| | • receipt type and version                                  |
| | • episode identity                                          |
| | • state or instance identity                                |
| | • environment or surface identity                           |
| | • observer and tool identity                                |
| | • claimed fact                                              |
| | • exact operation requested                                 |
| | • exact operation reported                                  |
| | • returned representation                                  |
| | • operation and tool status                                 |
| | • observation time and clock source                         |
| | • intended state effects                                    |
| | • unknown incidental effects                                |
| | • interpretation                                            |
| | • unsupported implications                                  |
| | • authority source                                          |
| | • capability demonstrated                                   |
| | • evidence identities                                       |
| | • evidence completeness                                     |
| | • uncertainty and conflict                                  |
| | • correction relation                                       |
| | • accepted: false                                           |
| | • write_authority: NONE                                     |
| | }==============================================================|
| | EVIDENCE_RESOLUTION                                         |
| | Receipt evidence is classified independently as:            |
| |                                                              |
| | COMPLETE                                                     |
| | PARTIAL                                                      |
| | UNVERIFIED                                                   |
| | CONFLICT                                                     |
| | UNAVAILABLE                                                  |
| |                                                              |
| | A receipt may exist without being complete.                  |
| | A useful partial receipt must not be discarded.              |
| | A summary must not be relabeled as exact raw evidence.       |
| | Missing output must not be reconstructed and called observed.|
| | }==============================================================|
| | OPERATION_RECEIPT_BOUNDARY                                   |
| | A complete operation receipt requires the declared contract  |
| | to identify what exact evidence must be preserved.           |
| |                                                              |
| | Depending on that contract, evidence may include:            |
| | • exact command or operation                                |
| | • resolved identifiers and paths                            |
| | • complete returned representation                         |
| | • individual operation statuses                            |
| | • tool-level status                                         |
| | • byte count                                                |
| | • deterministic encoded representation                     |
| | • content identity                                          |
| |                                                              |
| | Encoded or rendered output is not raw bytes.                 |
| | A pipeline status must not silently stand for every member.  |
| | Success of one operation must not authorize another.         |
| | }==============================================================|
| | CAPABILITY_AND_AUTHORITY_BOUNDARY                            |
| | Capability describes what an operation demonstrably did.     |
| | Authority describes who permitted the operation and scope.   |
| |                                                              |
| | Successful mutation demonstrates capability.                |
| | It does not create or prove authority.                       |
| |                                                              |
| | Authority must be established before mutation.              |
| | It must not be inferred after success.                       |
| |                                                              |
| | Observation authority, mutation authority, cleanup authority,|
| | publication authority, acceptance authority, and merge       |
| | authority remain separate.                                  |
| | }==============================================================|
| | BOUNDED_MUTATION_BOUNDARY                                    |
| | A bounded mutation test declares before execution:           |
| |                                                              |
| | • exact authorized target                                   |
| | • precondition                                               |
| | • intended bytes or transformation                         |
| | • expected verification                                     |
| | • cleanup target                                            |
| | • stop conditions                                           |
| |                                                              |
| | Unrelated state must not be cleaned, repaired, inspected, or |
| | overwritten merely because it appears nearby.                |
| |                                                              |
| | Restoration may be claimed only relative to an observed and  |
| | preserved baseline.                                         |
| | }==============================================================|
| | CROSS_INVOCATION_BOUNDARY                                    |
| | Information held only inside one process or invocation is not|
| | automatically available to another.                         |
| |                                                              |
| | A transferable identifier must cross the boundary through a |
| | declared channel.                                           |
| |                                                              |
| | Matching content identity across separate invocations        |
| | supports availability through the tested channel.            |
| | It does not establish cross-session persistence.             |
| | }==============================================================|
| | BLIND_VERIFICATION_BOUNDARY                                  |
| | Blind verification separates information observed from an    |
| | artifact from information inherited through transfer language.|
| |                                                              |
| | The expected answer is withheld from the receiving observer. |
| | The receiver receives only the locator, operation contract,  |
| | and stop conditions.                                        |
| |                                                              |
| | The receiver independently reports the measured identity.    |
| | A separate holder compares that result with the withheld     |
| | expected identity.                                          |
| | }==============================================================|
| | BLIND_VERIFICATION_FINDINGS                                 |
| | A matching independently measured identity may support:      |
| | • artifact availability across the tested boundary          |
| | • path or locator availability                              |
| | • compatible measurement                                   |
| | • content identity under the declared hash method           |
| |                                                              |
| | It does not alone establish:                                |
| | • identical process identity                               |
| | • identical environment identity                           |
| | • inherited private model state                            |
| | • truth of artifact content                                |
| | • indefinite persistence                                   |
| | • authority to modify or delete                            |
| |                                                              |
| | Alternate information channels and leakage remain falsifiers |
| | unless independently excluded.                              |
| | }==============================================================|
| | MODEL_NEUTRALITY                                            |
| | This frame applies across AI models and human-AI surfaces.    |
| |                                                              |
| | Model identity does not substitute for evidence.             |
| | Model disagreement does not automatically falsify a fact.    |
| | Model agreement does not automatically verify a fact.        |
| |                                                              |
| | What matters is how claims bind to inspectable evidence, how |
| | boundaries are preserved, and how corrections remain visible.|
| | }==============================================================|
| | CORRECTION_AND_FEEDBACK                                      |
| | A repeated output without meaningful state difference is     |
| | recurrence, not corrective feedback.                         |
| |                                                              |
| | Feedback supplies information about a difference between the |
| | carried representation and a newly observed boundary.        |
| |                                                              |
| | Correction appends a relation to the earlier receipt:        |
| | • corrects                                                  |
| | • narrows                                                   |
| | • supersedes                                                |
| | • reclassifies                                              |
| | • resolves_uncertainty_from                                 |
| |                                                              |
| | Being wrong is not an invariant failure.                     |
| | Hiding the error or silently replacing its history is.       |
| | }==============================================================|
| | REPLAY_BOUNDARY                                              |
| | Replay provides prior language, artifacts, operations, and   |
| | relationships to a receiving observer.                      |
| |                                                              |
| | Replay does not transfer private model state.                |
| | Replay enables a new observer to reconstruct and check the   |
| | available frame.                                            |
| |                                                              |
| | What survives replay is evidence about reconstruction under  |
| | that replay contract.                                       |
| | }==============================================================|
| | COMPRESSION_STOP_CONDITION                                  |
| | Compression terminates only relative to a declared bounded   |
| | frame.                                                       |
| |                                                              |
| | The frame must declare:                                     |
| | • reconstruction contract                                  |
| | • required distinctions                                    |
| | • receiving observer or compatibility class                |
| | • finite operator set or bounded search                    |
| | • cost metric                                               |
| | • audit budget                                              |
| | • evidence boundary                                        |
| | • reconstruction verification method                       |
| |                                                              |
| | Contract satisfaction is scoped evidence.                   |
| | It is not global optimality, certainty, or losslessness.     |
| |                                                              |
| | A checksum establishes serialized identity only.            |
| | It does not establish semantic preservation.                |
| | }==============================================================|
| | COMPRESSION_STOP_FINDINGS                                   |
| | COLLECTION_COMPLETE                                         |
| | No new verified information remains within the declared      |
| | collection field and audit budget.                          |
| |                                                              |
| | COMPRESSION_FIXED_POINT                                     |
| | The current frame satisfies the declared reconstruction      |
| | contract, every operator required by the bounded search was  |
| | evaluated, and no evaluated candidate has both lower declared|
| | cost and contract satisfaction.                             |
| |                                                              |
| | COMPRESSION_BUDGET_EXHAUSTED                                |
| | The search bound ended before every required candidate was   |
| | evaluated. This finding is not convergence.                 |
| |                                                              |
| | COMPRESSION_BLOCKED_BY_REQUIRED_DISTINCTION                  |
| | Lower-cost candidates exist, but each loses at least one     |
| | distinction required by the reconstruction contract.        |
| |                                                              |
| | RECONSTRUCTION_FAILED                                       |
| | The current frame does not satisfy the declared              |
| | reconstruction contract.                                    |
| |                                                              |
| | TEMPORARY_PAUSE                                             |
| | Work stopped because of an external resource, policy,        |
| | authority, environment, or human boundary.                  |
| | This finding is not collection or compression completion.    |
| |                                                              |
| | FALSE_CONVERGENCE                                           |
| | A fixed point was reported from repetition, incomplete       |
| | operator coverage, an invalid verifier, collapsed uncertainty,|
| | an undefined contract, or an undeclared cost metric.         |
| |                                                              |
| | REOPENED                                                    |
| | New verified evidence, a contract change, a newly discovered |
| | coverage gap, reconstruction failure, or explicit human      |
| | direction creates a new episode.                            |
| |                                                              |
| | The earlier scoped finding remains historical.              |
| | It is not silently rewritten by reopening.                  |
| | }==============================================================|
| | COMPRESSION_FIXED_POINT_FALSIFIER                            |
| | A reported COMPRESSION_FIXED_POINT is false when:            |
| |                                                              |
| | • an operator required by the declared bounded search was   |
| |   not evaluated                                             |
| |                                                              |
| | OR                                                           |
| |                                                              |
| | • an evaluated candidate has lower declared cost and still  |
| |   satisfies the declared reconstruction contract            |
| |                                                              |
| | Repeated identical output does not repair either failure.    |
| | }==============================================================|
| | INVARIANT_COLLECTION_BOUNDARY                               |
| | Repeated model outputs may reveal common reconstruction paths,|
| | common failures, and candidate invariant relationships.      |
| |                                                              |
| | Repetition is evidence of model behavior.                   |
| | It is not by itself evidence that the repeated claim is true.|
| |                                                              |
| | A candidate invariant becomes stronger when it survives      |
| | allowed transformations, opposing operations, independent    |
| | checks, explicit falsifiers, and changed environments.       |
| | }==============================================================|
| | CURRENT_IMPLEMENTATION_RELATION                              |
| | holosim/environment_snapshot.py already preserves canonical   |
| | observed, missing, unknown, assumptions, falsifiers, evidence,|
| | provenance, uncertainty, accepted: false, and                |
| | write_authority: NONE.                                      |
| |                                                              |
| | This proposal does not create a second snapshot evaluator.   |
| | It identifies candidate receipt and instance-separation      |
| | fields for later review against that existing boundary.      |
| |                                                              |
| | No implementation change is authorized by this proposal.     |
| | }==============================================================|
| | CURRENT_UNKNOWNS                                             |
| | • canonical receipt schema                                  |
| | • stable state and instance identity contracts              |
| | • raw evidence archival format                              |
| | • tool receipt portability                                  |
| | • alternate-channel exclusion for blind tests               |
| | • cross-session and cross-surface persistence semantics      |
| | • correction relation integration                           |
| | • operation-specific evidence requirements                  |
| | }==============================================================|
| | FALSIFIERS                                                   |
| | This proposal requires correction if it cannot distinguish:  |
| |                                                              |
| | • fact from communication                                   |
| | • observation from interpretation                           |
| | • capability from authority                                 |
| | • exact evidence from summary                               |
| | • complete from partial receipts                            |
| | • transferred answers from blind observations               |
| | • shared artifact access from shared instance identity       |
| | • correction from silent replacement                        |
| | • recurrence from informative feedback                      |
| | }==============================================================|
| | STOP_CONDITIONS                                              |
| | Stop observation when the required operation, interface, or  |
| | authority is unavailable.                                   |
| |                                                              |
| | Stop mutation before execution when authority or exact scope |
| | is absent, uncertain, or conflicting.                        |
| |                                                              |
| | Stop verification when required evidence was not preserved.  |
| | Preserve the result as PARTIAL, UNVERIFIED, CONFLICT, or      |
| | UNAVAILABLE instead of inventing completion.                 |
| |                                                              |
| | Stop replay when state or instance boundaries collapse.      |
| | Stop acceptance because evaluation grants no acceptance.     |
| | Stop writing because this proposal grants no write authority.|
| | }==============================================================|
| | NEXT_SUPPORTED_ACTION                                       |
| | Review and falsify this Spine as a separate exploratory      |
| | artifact.                                                    |
| |                                                              |
| | If accepted later, compare its receipt fields against the    |
| | existing environment snapshot schema before extending code.  |
| |                                                              |
| | Do not implement a parallel evaluator.                       |
| | }==============================================================|
| | TERMINAL                                                     |
| | Facts remain distinct from their communication.              |
| | Separators preserve state and instance change.               |
| | Receipts preserve what was observed and what was not.        |
| | Blind checks expose whether answers crossed through language.|
| | Authority remains external.                                 |
| | Correction remains visible.                                |
| | }==============================================================|