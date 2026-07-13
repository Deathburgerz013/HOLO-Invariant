| }==============================================================|
| | █†█ Holo/Sim █†█ █†█ RECONSTRUCTION_BOUNDARY █†█            |
| }==============================================================|
| | DOCUMENT_TYPE: HOLO_INVARIANT                               |
| | STATUS: VERIFIED_OBSERVATION                                |
| | AUTHORITY: DESCRIPTIVE_ONLY                                 |
| | WRITE_AUTHORITY: NONE                                       |
| }==============================================================|
| | OBSERVATION                                                 |
| | The Master Spine describes the current verified             |
| | reconstruction of the repository and its preserved state.   |
| |                                                             |
| | Proposed future architecture serves a different purpose.    |
| |                                                             |
| | Reconstruction and proposal must remain explicitly          |
| | separated.                                                  |
| }==============================================================|
| | MASTER_SPINE_PURPOSE                                        |
| | The Master Spine records:                                   |
| |                                                             |
| | • verified implementation state                             |
| | • verified invariants                                       |
| | • verified correction history                               |
| | • observer boundaries                                       |
| | • known uncertainty                                         |
| | • accepted reconstruction checkpoints                       |
| |                                                             |
| | The Master Spine does not automatically accept:             |
| |                                                             |
| | • speculative architecture                                 |
| | • unimplemented commands                                    |
| | • proposed directories                                      |
| | • imagined runtime behavior                                 |
| | • future protocol features                                  |
| }==============================================================|
| | DESIGN_BOUNDARY                                             |
| | Future architecture belongs in a separate design artifact.  |
| |                                                             |
| | The design artifact may contain:                            |
| |                                                             |
| | • proposed commands                                         |
| | • proposed tests                                            |
| | • proposed schemas                                          |
| | • proposed automation                                       |
| | • proposed synchronization mechanisms                       |
| | • proposed integrity guards                                 |
| |                                                             |
| | A proposal remains a proposal until repository evidence,    |
| | implementation, tests, or accepted review changes its       |
| | status.                                                     |
| }==============================================================|
| | COLLECTION_INVARIANT                                        |
| | Repository evidence must be collected separately from       |
| | architectural proposals.                                    |
| |                                                             |
| | Verified reconstruction precedes future design.             |
| |                                                             |
| | Every collected entry must retain its evidence status.      |
| |                                                             |
| | Allowed reconstruction labels include:                      |
| |                                                             |
| | VERIFIED_FROM_SOURCE                                        |
| | VERIFIED_FROM_COMMIT                                        |
| | VERIFIED_FROM_TEST_OUTPUT                                   |
| | VERIFIED_FROM_DOCUMENT                                      |
| | OBSERVED_PATTERN                                            |
| | UNCERTAIN                                                   |
| |                                                             |
| | PROPOSED entries must not be promoted into verified         |
| | reconstruction without supporting evidence.                 |
| }==============================================================|
| | OBSERVER_BOUNDARY                                           |
| | Observers contribute independent reconstruction,            |
| | criticism, uncertainty, and proposed deltas.                |
| |                                                             |
| | No observer becomes authoritative merely by producing       |
| | confident output.                                           |
| |                                                             |
| | The repository supplies the shared observable evidence.     |
| |                                                             |
| | Canyon reviews the evidence and determines whether a        |
| | proposed delta is accepted for commit.                      |
| |                                                             |
| | The commit records the accepted reconstruction checkpoint.  |
| }==============================================================|
| | REVIEW_LOOP                                                 |
| | Repository                                                  |
| |     ↓                                                       |
| | Observer reconstruction                                     |
| |     ↓                                                       |
| | Counter-review                                              |
| |     ↓                                                       |
| | Evidence comparison                                         |
| |     ↓                                                       |
| | Preserve agreement, disagreement, and uncertainty           |
| |     ↓                                                       |
| | Accept the smallest supported delta                         |
| |     ↓                                                       |
| | Commit checkpoint                                           |
| |     ↓                                                       |
| | Compare later commits for difference                        |
| }==============================================================|
| | VERIFIED_DELTA_MODEL                                        |
| | The Master Spine does not collect every document or every   |
| | sentence.                                                   |
| |                                                             |
| | It collects verified deltas that changed:                   |
| |                                                             |
| | • architecture understood as current                        |
| | • implementation state                                      |
| | • invariant state                                           |
| | • correction history                                        |
| | • uncertainty                                               |
| | • the next factually required action                         |
| |                                                             |
| | Each delta must preserve:                                   |
| |                                                             |
| | PRIOR_STATE                                                 |
| | OBSERVED_DIFFERENCE                                         |
| | CORRECTION                                                  |
| | VERIFIED_RESULT                                             |
| | SOURCE                                                      |
| }==============================================================|
| | VERIFIED_RESULT                                             |
| | The existing COLLECTION_RULE successfully prevented         |
| | unverified future architecture from being silently merged   |
| | into the current reconstruction checkpoint.                 |
| |                                                             |
| | This demonstrates that the Master Spine is not merely       |
| | recording rules.                                            |
| |                                                             |
| | The rules are actively constraining observer output and     |
| | improving the review process.                               |
| }==============================================================|
| | CORRECTION_MARKER                                           |
| | Future evidence may show that a proposed design has become  |
| | implemented or verified.                                    |
| |                                                             |
| | When that occurs, append a new verified delta.              |
| |                                                             |
| | Do not rewrite the earlier proposal as though it had always |
| | been implemented.                                           |
| }==============================================================|
| | TERMINAL                                                    |
| | The Master Spine reconstructs what is.                      |
| |                                                             |
| | The Design Spine proposes what may be needed next.          |
| |                                                             |
| | Keep the boundary explicit.                                 |
| |                                                             |
| | Nothing left for collection in field.                       |
| |==============================================================|