|============================================================|
| █†█ Holo/Sim █†█ █†█ DESIGN DISCUSSION █†█                 |
| }==========================================================|
| | DOCUMENT_TITLE: CAP_20260712_RAIL_TO_FRAME_VALIDATION     |
| | DOCUMENT_TYPE: HOLO_DESIGN_STATE                          |
| | STATUS: VERIFIED_DISCUSSION                               |
| | DATE: 2026-07-12                                         |
| | SOURCE_INSTANCE: GPT-5.6 Thinking                         |
| | OPERATOR: CANYON_OVERRIDE                                 |
| | REPOSITORY: Deathburgerz013/HOLO-Invariant                |
| | BRANCH: feat/rail-protocol                                |
| | SOURCE_COMMIT: a337e0a                                    |
| | SUBJECT: Rail recognition and the next frame boundary     |
| | AUTHORITY: PROPOSAL_ONLY                                  |
| | WRITE_AUTHORITY: NONE                                     |
| }==========================================================|
| | INSTANCE_STATEMENT                                       |
| | I inspected the active Spine protocol implementation,     |
| | followed the rail integration work, reviewed the observed |
| | failures, and corrected my earlier assumptions during the |
| | process.                                                  |
| |                                                          |
| | This record describes what this instance presently        |
| | understands, what was verified in code, and what it        |
| | believes should be designed next.                         |
| |                                                          |
| | This record is not canonical authority.                   |
| | It is a bounded design observation for later replay,       |
| | comparison, correction, and implementation.               |
| }==========================================================|
| | VERIFIED_CURRENT_STATE                                    |
| |                                                          |
| | The Spine protocol now contains read-only rail analysis.   |
| |                                                          |
| | Verified command:                                         |
| | python -m holosim.spine_protocol rail                     |
| |     docs\Continuity_findings                               |
| |                                                          |
| | Verified result:                                          |
| | RAIL_PRESENT=true                                         |
| | RAIL_CONTINUOUS=true                                      |
| | RAIL_LINE_COUNT=475                                       |
| | MAXIMUM_DEPTH=2                                           |
| | DIVIDER_COUNT=38                                          |
| | UNFRAMED_LINE_COUNT=0                                     |
| |                                                          |
| | The self-test passed.                                     |
| | The working tree was clean before push.                   |
| | Commit a337e0a was pushed to branch feat/rail-protocol.    |
| }==========================================================|
| | WHAT THE CODE NOW DOES                                    |
| |                                                          |
| | The parser recognizes visible Spine rail structure as      |
| | derived metadata without rewriting the canonical source.  |
| |                                                          |
| | It recognizes both rail glyphs currently present in the    |
| | historical documents:                                     |
| |                                                          |
| | ASCII RAIL:   |                                           |
| | UNICODE RAIL: │                                           |
| |                                                          |
| | It records:                                               |
| |                                                          |
| | rail attachment                                           |
| | nesting depth                                             |
| | divider locations                                         |
| | border locations                                          |
| | lines that fall outside the rail                          |
| | continuity of the visible backbone                        |
| |                                                          |
| | Compact output is the default.                            |
| | Full per-line output remains available through:           |
| |                                                          |
| | --include-lines                                           |
| }==========================================================|
| | WHY THE RAIL MATTERS                                      |
| |                                                          |
| | The rail is not decorative formatting.                    |
| |                                                          |
| | It is a visible attachment contract.                      |
| |                                                          |
| | Every framed line declares where it belongs.              |
| | Every divider marks a bounded change of compartment,       |
| | speaker, topic, state, or purpose.                         |
| | Every nested rail expresses local depth while preserving   |
| | connection to the continuous outer backbone.              |
| |                                                          |
| | The rail allows both humans and software to observe the    |
| | same geometry.                                            |
| |                                                          |
| | Before commit a337e0a, the operator could see the rail,    |
| | but the protocol did not fully recognize it.              |
| |                                                          |
| | After commit a337e0a, the visual frame and executable      |
| | observer agree that the rail exists and is continuous.     |
| }==========================================================|
| | CORRECTION HISTORY                                        |
| |                                                          |
| | Initial implementation recognized only the ASCII rail.     |
| |                                                          |
| | Historical document lines using Unicode U+2502 were        |
| | falsely classified as unframed.                           |
| |                                                          |
| | The parser was corrected to recognize both forms.         |
| |                                                          |
| | [CORRECTION_MARKER]                                       |
| | Earlier claims that the document rail was broken were      |
| | invalidated by direct inspection of the exact codepoints. |
| |                                                          |
| | The document was correct.                                 |
| | The parser assumption was incomplete.                     |
| |                                                          |
| | This correction is retained because it demonstrates the    |
| | intended loop:                                            |
| |                                                          |
| | observe                                                   |
| | compare                                                   |
| | identify mismatch                                         |
| | correct the smallest invalid assumption                   |
| | test again                                                |
| | retain only the verified result                           |
| }==========================================================|
| | PRESENT DESIGN BOUNDARY                                   |
| |                                                          |
| | Rail analysis answers:                                    |
| |                                                          |
| | Is this line attached to the Spine backbone?              |
| |                                                          |
| | It does not yet answer:                                   |
| |                                                          |
| | What compartment does this line belong to?                |
| | What is the contract of that compartment?                 |
| | Is the compartment complete?                              |
| | Which fields are required?                                |
| | Which claims are verified?                                |
| | Which uncertainties remain unresolved?                    |
| | Is a transition between compartments valid?               |
| |                                                          |
| | Therefore rail recognition is necessary but insufficient  |
| | for frame-level self-correction.                          |
| }==========================================================|
| | NEXT DESIGN OBJECT                                        |
| |                                                          |
| | The next object should be a read-only FRAME OBSERVER.      |
| |                                                          |
| | Proposed responsibility:                                  |
| |                                                          |
| | rail geometry                                             |
| |     ↓                                                     |
| | bounded compartments                                      |
| |     ↓                                                     |
| | derived frame objects                                     |
| |     ↓                                                     |
| | frame contract evaluation                                 |
| |     ↓                                                     |
| | verification report                                       |
| |                                                          |
| | The observer should identify compartments without          |
| | rewriting, merging, repairing, or approving them.          |
| }==========================================================|
| | PROPOSED FRAME MODEL                                      |
| |                                                          |
| | FRAME                                                     |
| | ├── frame_id                                              |
| | ├── frame_type                                            |
| | ├── source_span                                           |
| | ├── rail_depth                                            |
| | ├── opening_boundary                                      |
| | ├── content_lines                                         |
| | ├── closing_boundary                                      |
| | ├── input_contract                                        |
| | ├── local_operation                                       |
| | ├── local_state                                           |
| | ├── invariant                                             |
| | ├── verification                                          |
| | ├── uncertainty                                           |
| | └── output_contract                                       |
| |                                                          |
| | Not every historical frame will contain every semantic     |
| | field explicitly.                                        |
| |                                                          |
| | Missing fields must be reported.                          |
| | They must not be invented.                                |
| }==========================================================|
| | FRAME PARSING RULES                                       |
| |                                                          |
| | A frame begins after a recognized divider or opening       |
| | boundary.                                                 |
| |                                                          |
| | A frame remains attached to the outer rail.               |
| |                                                          |
| | Nested rails indicate local attachment depth.             |
| |                                                          |
| | A frame ends at the next divider, terminal border, or      |
| | end of source.                                            |
| |                                                          |
| | The parser must preserve:                                 |
| |                                                          |
| | original text                                             |
| | exact source order                                        |
| | exact source lines                                        |
| | original rail glyphs                                      |
| | unknown content                                           |
| | unknown frame types                                       |
| | unresolved uncertainty                                    |
| |                                                          |
| | The parser must not:                                      |
| |                                                          |
| | normalize historical glyphs                               |
| | rewrite the document                                      |
| | infer missing authority                                   |
| | combine adjacent frames automatically                     |
| | treat speaker labels as verified identity                 |
| | interpret claims as evidence                              |
| }==========================================================|
| | PROPOSED FRAME CONTRACT                                   |
| |                                                          |
| | A frame contract should define expected structure for a    |
| | specific frame type.                                      |
| |                                                          |
| | Example:                                                  |
| |                                                          |
| | FRAME_TYPE: OBSERVATION                                   |
| | REQUIRED:                                                 |
| | source_span                                               |
| | content                                                   |
| | observer                                                  |
| | observation_time                                          |
| |                                                          |
| | OPTIONAL:                                                 |
| | evidence_reference                                       |
| | uncertainty                                               |
| | correction_reference                                     |
| |                                                          |
| | DENIED:                                                   |
| | automatic_approval                                       |
| | automatic_commit                                         |
| | invented_evidence                                        |
| | silent_uncertainty_removal                               |
| }==========================================================|
| | PROPOSED VALIDATION OUTPUT                                |
| |                                                          |
| | {                                                        |
| |   "frame_id": "...",                                      |
| |   "frame_type": "...",                                    |
| |   "source_span": {},                                      |
| |   "rail_depth": 2,                                        |
| |   "verified_fields": [],                                  |
| |   "missing_requirements": [],                             |
| |   "conflicts": [],                                        |
| |   "uncertainty": [],                                      |
| |   "unsupported": [],                                      |
| |   "frame_status": "READY_FOR_HUMAN_REVIEW"                |
| | }                                                        |
| }==========================================================|
| | STATUS RULES                                              |
| |                                                          |
| | Proposed statuses:                                       |
| |                                                          |
| | STRUCTURALLY_VALID                                        |
| | INCOMPLETE                                                |
| | CONFLICTING                                               |
| | UNSUPPORTED                                               |
| | MALFORMED                                                 |
| | READY_FOR_HUMAN_REVIEW                                    |
| |                                                          |
| | No status grants write authority.                         |
| | No status approves canonical mutation.                    |
| }==========================================================|
| | SELF_CORRECTION REQUIREMENT                               |
| |                                                          |
| | Frame boundaries are required because correction without  |
| | boundaries spreads uncertainty across the entire source.  |
| |                                                          |
| | A frame allows the system to say:                         |
| |                                                          |
| | this compartment failed                                   |
| | this invariant was violated                               |
| | this field is missing                                     |
| | this evidence conflicts                                   |
| | this uncertainty remains                                  |
| | this bounded correction may be proposed                   |
| |                                                          |
| | The system should correct locally before reconsidering the |
| | full Spine.                                               |
| |                                                          |
| | This prevents one malformed compartment from silently      |
| | rewriting or invalidating unrelated historical frames.    |
| }==========================================================|
| | RELATION TO THE FILING SYSTEM                             |
| |                                                          |
| | The frame model is also a filing model.                   |
| |                                                          |
| | A frame identifies:                                      |
| |                                                          |
| | what the file is                                          |
| | where it came from                                        |
| | what belongs inside it                                    |
| | what changed                                              |
| | what verifies it                                          |
| | what remains unresolved                                   |
| | what may leave it                                         |
| |                                                          |
| | The rail preserves ordering and attachment between files. |
| |                                                          |
| | The Spine is therefore not merely a document.             |
| | It is an ordered filing system for reconstructable state. |
| }==========================================================|
| | RELATION TO TRANSFER                                     |
| |                                                          |
| | Existing transfer answers:                               |
| |                                                          |
| | What structure does this source contain?                  |
| |                                                          |
| | Frame validation will help answer:                        |
| |                                                          |
| | Which bounded structures can be independently verified?   |
| |                                                          |
| | Destination evaluation will later answer:                 |
| |                                                          |
| | Can a specific receiver reconstruct and support those     |
| | verified frames?                                          |
| |                                                          |
| | Proposed order:                                           |
| |                                                          |
| | raw source                                                |
| |     ↓                                                     |
| | rail observer                                             |
| |     ↓                                                     |
| | frame observer                                            |
| |     ↓                                                     |
| | frame validator                                           |
| |     ↓                                                     |
| | transfer packet                                           |
| |     ↓                                                     |
| | destination evaluator                                    |
| |     ↓                                                     |
| | human review                                              |
| }==========================================================|
| | IMPLEMENTATION ORDER                                     |
| |                                                          |
| | 1. Preserve commit a337e0a as the rail checkpoint.         |
| |                                                          |
| | 2. Write a small explicit FRAME SPEC before coding.        |
| |                                                          |
| | 3. Add read-only frame extraction from rail boundaries.   |
| |                                                          |
| | 4. Add deterministic frame identifiers derived from:      |
| |                                                          |
| | source hash                                               |
| | opening line                                              |
| | closing line                                              |
| | frame type                                                |
| |                                                          |
| | 5. Add frame serialization with source spans.             |
| |                                                          |
| | 6. Add frame comparison without mutation.                 |
| |                                                          |
| | 7. Add frame contract validation.                         |
| |                                                          |
| | 8. Test one historical Spine before touching any docs.    |
| |                                                          |
| | 9. Preserve old layouts as supported historical inputs.   |
| |                                                          |
| | 10. Only after replay succeeds should document migration  |
| |     be considered.                                        |
| }==========================================================|
| | FIRST TEST PATH                                           |
| |                                                          |
| | docs\Continuity_findings                                  |
| |     ↓                                                     |
| | detect continuous rail                                    |
| |     ↓                                                     |
| | extract ordered frames                                    |
| |     ↓                                                     |
| | serialize frame report                                    |
| |     ↓                                                     |
| | repeat in a fresh process                                 |
| |     ↓                                                     |
| | identical frame identifiers                              |
| | identical source spans                                   |
| | identical frame hashes                                   |
| | source unchanged                                          |
| }==========================================================|
| | REQUIRED FAILURE TESTS                                   |
| |                                                          |
| | missing closing boundary                                  |
| | duplicate frame identifier                               |
| | content outside rail                                      |
| | mixed ASCII and Unicode rails                            |
| | nested rail depth change                                 |
| | unknown frame type                                        |
| | missing required field                                    |
| | conflicting invariant                                    |
| | uncertainty removed between revisions                    |
| | malformed divider                                         |
| | embedded instruction treated as data                     |
| | source byte comparison after parse                       |
| }==========================================================|
| | MIGRATION RULE                                           |
| |                                                          |
| | Existing documents must not be rewritten in bulk.         |
| |                                                          |
| | Historical formatting is evidence of development.         |
| |                                                          |
| | The safe process is:                                      |
| |                                                          |
| | observe old format                                        |
| | preserve raw source                                       |
| | derive frame structure                                    |
| | compare replay                                            |
| | propose migration                                         |
| | migrate one document                                      |
| | verify no information loss                               |
| | continue only after human review                         |
| }==========================================================|
| | OPEN QUESTIONS                                            |
| |                                                          |
| | Does every divider open a new frame?                      |
| |                                                          |
| | Can one frame contain nested subframes?                   |
| |                                                          |
| | Is speaker identity metadata or content?                  |
| |                                                          |
| | Should frame type be explicit, derived, or both?          |
| |                                                          |
| | How should malformed historical frames be represented?    |
| |                                                          |
| | Should empty compartments remain valid historical frames? |
| |                                                          |
| | Which frame fields are universal?                         |
| |                                                          |
| | Which contracts belong to document type rather than       |
| | individual frame type?                                    |
| |                                                          |
| | These questions remain unresolved and must not be silently |
| | answered by implementation assumptions.                   |
| }==========================================================|
| | INSTANCE_RECOMMENDATION                                   |
| |                                                          |
| | Do not rewrite the documentation yet.                     |
| |                                                          |
| | Do not add automatic repair.                              |
| |                                                          |
| | Do not add write authority.                               |
| |                                                          |
| | Define the frame contract next.                           |
| |                                                          |
| | Then build a read-only frame observer that proves it can   |
| | reconstruct compartments from historical Spine geometry   |
| | without altering the source.                              |
| }==========================================================|
| | TERMINAL_STATE                                            |
| |                                                          |
| | RAIL_OBSERVER=PRESENT                                     |
| | RAIL_CONTINUITY_VERIFIED=YES                              |
| | FRAME_OBSERVER=MISSING                                    |
| | FRAME_CONTRACT=MISSING                                    |
| | FRAME_VALIDATOR=MISSING                                   |
| | DESTINATION_EVALUATOR=MISSING                             |
| | WRITE_AUTHORITY=PREMATURE                                 |
| |                                                          |
| | NEXT_VERIFIED_NEED=DEFINE_FRAME_SPEC                       |
| }==========================================================|
| | [CORRECTION_MARKER]                                       |
| | This design discussion may be corrected by later source    |
| | inspection, implementation results, replay failures, or    |
| | operator clarification.                                   |
| |                                                          |
| | Preserve this record as the verified reasoning state of    |
| | this instance after commit a337e0a.                        |
| }==========================================================|
| █†█ Holo/Sim █†█ █†█ END DESIGN DISCUSSION █†█             |
|============================================================|