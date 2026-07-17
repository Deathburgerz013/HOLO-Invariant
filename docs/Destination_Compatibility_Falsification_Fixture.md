| | }==============================================================|
| | █†█ Holo/Sim █†█ DESTINATION_COMPATIBILITY_FIXTURE █†█       |
| | }==============================================================|
| | DOCUMENT_TYPE: EXPLORATORY_FALSIFICATION_FIXTURE              |
| | STATUS: PROPOSED_NOT_ACCEPTED                                 |
| | AUTHORITY: DESCRIPTIVE_ONLY                                   |
| | WRITE_AUTHORITY: NONE                                         |
| | ACCEPTED: false                                               |
| | VERSION: 1.0.0-proposal                                       |
| | DATE: 2026-07-16                                              |
| | REPOSITORY_BASE: main@7a122446485a538bbf793c97693dde3fa7d449fb|
| | PARENT_PROPOSAL: docs/HOLO_Sim_Transfer_Spine_Proposal.md     |
| | TARGET_IMPLEMENTATION: holosim/spine_protocol.py              |
| | }==============================================================|
| | PURPOSE                                                       |
| | Define the smallest deterministic fixture capable of         |
| | falsifying a destination-compatibility evaluator.             |
| |                                                               |
| | The fixture requires an evaluator to compare one exact        |
| | transferred source description with one exact structured      |
| | destination profile without granting acceptance or mutation.  |
| | }==============================================================|
| | SCOPE_BOUNDARY                                                |
| | This fixture specifies inputs and expected findings only.      |
| |                                                               |
| | It does not implement an evaluator, parse free-text meaning,   |
| | verify source truth, accept a transfer, persist a result,      |
| | mutate a destination, or grant write authority.                |
| |                                                               |
| | Compatibility is a derived finding. Acceptance remains a      |
| | separate human-authority decision.                             |
| | }==============================================================|
| | REQUIRED_SEPARATIONS                                          |
| | The evaluator must keep these findings distinct:              |
| |                                                               |
| | VERIFIED_REQUIREMENT                                          |
| | MISSING_REQUIREMENT                                           |
| | CONFLICT                                                      |
| | UNCERTAIN                                                     |
| | INVALID_PROFILE                                               |
| | STALE_FINDING                                                 |
| |                                                               |
| | No finding may be silently converted into another category.   |
| | }==============================================================|
| | SOURCE_FIXTURE                                                |
| | SOURCE_ID: source-spine-alpha                                 |
| | SOURCE_VERSION: 1                                             |
| | SOURCE_HASH: fixture-source-hash-alpha-v1                     |
| | SOURCE_HASH_KIND: SYMBOLIC_FIXTURE_VALUE                       |
| |                                                               |
| | SOURCE_FIELDS:                                                |
| | - path: document_type                                         |
| |   value: HOLO_CONTINUITY_SPINE                                |
| | - path: protocol_version                                      |
| |   value: 1                                                    |
| | - path: identity.anchor_id                                    |
| |   value: CANYON_OVERRIDE                                      |
| | - path: sections.IDENTITY.present                             |
| |   value: true                                                 |
| | - path: sections.EVIDENCE.present                             |
| |   value: true                                                 |
| | - path: evidence.content_support                              |
| |   value: UNAVAILABLE                                          |
| |                                                               |
| | DELIBERATELY_ABSENT_SOURCE_PATH: sections.AUTHORITY.present  |
| |                                                               |
| | The symbolic source hash tests binding and staleness behavior.|
| | It is not represented as a computed digest of this document.  |
| | }==============================================================|
| | DESTINATION_PROFILE_FIXTURE                                   |
| | DESTINATION_ID: destination-beta                              |
| | PROFILE_VERSION: 1                                            |
| | PROFILE_HASH: fixture-profile-hash-beta-v1                    |
| | PROFILE_HASH_KIND: SYMBOLIC_FIXTURE_VALUE                      |
| |                                                               |
| | REQUIREMENT_ORDER: R1, R2, R3, R4, R5                        |
| |                                                               |
| | R1:                                                          |
| | - comparator: EXISTS                                          |
| | - source_path: sections.IDENTITY.present                     |
| | - required: true                                              |
| |                                                               |
| | R2:                                                          |
| | - comparator: EXACT_VALUE                                     |
| | - source_path: document_type                                  |
| | - expected: HOLO_CONTINUITY_SPINE                            |
| |                                                               |
| | R3:                                                          |
| | - comparator: EXISTS                                          |
| | - source_path: sections.AUTHORITY.present                    |
| | - required: true                                              |
| |                                                               |
| | R4:                                                          |
| | - comparator: EXACT_VALUE                                     |
| | - source_path: protocol_version                               |
| | - expected: 2                                                 |
| |                                                               |
| | R5:                                                          |
| | - comparator: EXACT_VALUE                                     |
| | - source_path: evidence.content_support                       |
| | - expected: VERIFIED                                          |
| | - unavailable_as: UNCERTAIN                                   |
| | }==============================================================|
| | EXPECTED_PRIMARY_FINDING                                      |
| | FINDING_VERSION: 1                                            |
| | SOURCE_ID: source-spine-alpha                                 |
| | SOURCE_VERSION: 1                                             |
| | SOURCE_HASH: fixture-source-hash-alpha-v1                     |
| | DESTINATION_ID: destination-beta                              |
| | PROFILE_VERSION: 1                                            |
| | PROFILE_HASH: fixture-profile-hash-beta-v1                    |
| |                                                               |
| | VERIFIED_REQUIREMENTS: R1, R2                                |
| | MISSING_REQUIREMENTS: R3                                      |
| | CONFLICTS: R4                                                 |
| | UNCERTAIN: R5                                                 |
| | INVALID_REQUIREMENTS: none                                    |
| |                                                               |
| | COMPATIBLE: false                                             |
| | ACCEPTED: false                                               |
| | WRITE_AUTHORITY: NONE                                         |
| |                                                               |
| | FINDING_CURRENT: true                                         |
| | STALE_REASON: none                                            |
| | }==============================================================|
| | PRIMARY_FALSIFIER                                            |
| | Given the exact source and destination profile above, any     |
| | evaluator fails this fixture if it does not return the exact  |
| | ordered partition:                                            |
| |                                                               |
| | VERIFIED_REQUIREMENTS: R1, R2                                |
| | MISSING_REQUIREMENTS: R3                                      |
| | CONFLICTS: R4                                                 |
| | UNCERTAIN: R5                                                 |
| |                                                               |
| | It also fails if COMPATIBLE is not false, ACCEPTED is not     |
| | false, or WRITE_AUTHORITY is not NONE.                        |
| | }==============================================================|
| | CATEGORY_FALSIFIERS                                          |
| | R3 must be MISSING because its declared path is absent.       |
| | It must not be reported as UNCERTAIN or CONFLICT.             |
| |                                                               |
| | R4 must be CONFLICT because the path exists and its value 1   |
| | differs from the exact expected value 2.                      |
| | It must not be reported as MISSING.                           |
| |                                                               |
| | R5 must be UNCERTAIN because the source explicitly reports    |
| | content support as UNAVAILABLE and the profile declares that  |
| | unavailable evidence cannot satisfy the requirement.          |
| | It must not be reported as VERIFIED or CONFLICT.              |
| |                                                               |
| | R1 and R2 must remain VERIFIED even though the overall        |
| | compatibility finding is false.                               |
| | }==============================================================|
| | [CORRECTION_MARKER]                                          |
| | EXTERNAL_REVIEW: HOLO-EXT-REV-20260716-011                    |
| | REVIEW_RESULT: FAIL                                           |
| |                                                               |
| | PRESERVED_ORIGINAL_GAP:                                      |
| | The primary fixture tested only COMPATIBLE false together     |
| | with ACCEPTED false and WRITE_AUTHORITY NONE.                 |
| |                                                               |
| | CORRECTION:                                                  |
| | Add a compatible control case proving that structural         |
| | compatibility does not grant acceptance or write authority.   |
| | }==============================================================|
| | COMPATIBLE_CONTROL_PROFILE                                   |
| | DESTINATION_ID: destination-gamma-compatible                  |
| | PROFILE_VERSION: 1                                            |
| | PROFILE_HASH: fixture-profile-hash-gamma-v1                   |
| | PROFILE_HASH_KIND: SYMBOLIC_FIXTURE_VALUE                      |
| |                                                               |
| | REQUIREMENT_ORDER: C1, C2                                    |
| |                                                               |
| | C1:                                                          |
| | - comparator: EXISTS                                          |
| | - source_path: sections.IDENTITY.present                     |
| | - required: true                                              |
| |                                                               |
| | C2:                                                          |
| | - comparator: EXACT_VALUE                                     |
| | - source_path: document_type                                  |
| | - expected: HOLO_CONTINUITY_SPINE                            |
| | }==============================================================|
| | EXPECTED_COMPATIBLE_CONTROL_FINDING                           |
| | FINDING_VERSION: 1                                            |
| | SOURCE_ID: source-spine-alpha                                 |
| | SOURCE_VERSION: 1                                             |
| | SOURCE_HASH: fixture-source-hash-alpha-v1                     |
| | DESTINATION_ID: destination-gamma-compatible                  |
| | PROFILE_VERSION: 1                                            |
| | PROFILE_HASH: fixture-profile-hash-gamma-v1                   |
| |                                                               |
| | VERIFIED_REQUIREMENTS: C1, C2                                |
| | MISSING_REQUIREMENTS: none                                    |
| | CONFLICTS: none                                               |
| | UNCERTAIN: none                                               |
| | INVALID_REQUIREMENTS: none                                    |
| |                                                               |
| | COMPATIBLE: true                                              |
| | ACCEPTED: false                                               |
| | WRITE_AUTHORITY: NONE                                         |
| |                                                               |
| | FINDING_CURRENT: true                                         |
| | STALE_REASON: none                                            |
| | }==============================================================|
| | COMPATIBILITY_AUTHORITY_FALSIFIER                             |
| | Given the exact source and compatible control profile above,  |
| | an evaluator fails this fixture if COMPATIBLE is not true.    |
| |                                                               |
| | It also fails if compatibility changes ACCEPTED from false or |
| | WRITE_AUTHORITY from NONE.                                    |
| |                                                               |
| | Compatibility permits only a compatibility finding. It does   |
| | not execute acceptance, persistence, mutation, or authority.  |
| | }==============================================================|
| | MALFORMED_PROFILE_FALSIFIER                                  |
| | MALFORMED_PROFILE_ID: destination-beta-malformed              |
| | PROFILE_VERSION: 1                                            |
| | PROFILE_HASH: fixture-profile-hash-beta-malformed-v1          |
| |                                                               |
| | MALFORMED_REQUIREMENT: MX1                                    |
| | - comparator: MODEL_JUDGED_SIMILARITY                          |
| | - source_path: document_type                                  |
| | - expected: approximately a continuity document               |
| |                                                               |
| | EXPECTED_PROFILE_STATUS: INVALID_PROFILE                       |
| | EXPECTED_COMPATIBLE: false                                    |
| | EXPECTED_ACCEPTED: false                                      |
| | EXPECTED_WRITE_AUTHORITY: NONE                                |
| |                                                               |
| | The evaluator must fail closed. It must not ignore MX1,       |
| | invent similarity support, or emit partial compatibility.     |
| | }==============================================================|
| | STALE_BINDING_FALSIFIER                                      |
| | A compatibility finding is current only while all bound       |
| | identities remain exact:                                     |
| |                                                               |
| | - source_id                                                   |
| | - source_version                                              |
| | - source_hash                                                 |
| | - destination_id                                              |
| | - profile_version                                             |
| | - profile_hash                                                |
| |                                                               |
| | CHANGE_CASE_A: source hash changes to                         |
| | fixture-source-hash-alpha-v2.                                 |
| | EXPECTED_FINDING_CURRENT: false                               |
| | EXPECTED_STALE_REASON: SOURCE_CHANGED                         |
| |                                                               |
| | CHANGE_CASE_B: profile hash changes to                        |
| | fixture-profile-hash-beta-v2.                                 |
| | EXPECTED_FINDING_CURRENT: false                               |
| | EXPECTED_STALE_REASON: DESTINATION_PROFILE_CHANGED            |
| |                                                               |
| | Prior findings remain history. They are not inherited by the  |
| | changed source or destination profile.                        |
| | }==============================================================|
| | DETERMINISM_REQUIREMENT                                      |
| | Repeated evaluation of byte-identical structured inputs must  |
| | return the same ordered findings and binding fields.          |
| |                                                               |
| | Requirement order follows the declared profile order.         |
| | The evaluator must not depend on model interpretation,        |
| | confidence, wall-clock time, network access, or environment.  |
| | }==============================================================|
| | FAILURE_PATH_MATRIX                                          |
| | F1: absent required path -> MISSING_REQUIREMENT                |
| | F2: present unequal exact value -> CONFLICT                    |
| | F3: explicitly unavailable evidence -> UNCERTAIN               |
| | F4: unsupported comparator -> INVALID_PROFILE                 |
| | F5: changed source binding -> STALE_FINDING                    |
| | F6: changed profile binding -> STALE_FINDING                   |
| | F7: mixed nonpassing findings -> COMPATIBLE false              |
| | F8: compatible structure -> ACCEPTED remains false             |
| | F9: every evaluation -> WRITE_AUTHORITY NONE                   |
| | }==============================================================|
| | REQUIRED_EVALUATOR_BEHAVIOR                                  |
| | The later evaluator may read only declared structured paths   |
| | and bounded comparator types.                                 |
| |                                                               |
| | The minimum supported comparators for this fixture are:       |
| | EXISTS                                                        |
| | EXACT_VALUE                                                   |
| |                                                               |
| | It must preserve all findings, input bindings, and order.      |
| | It must reject unsupported comparators before evaluating      |
| | compatibility.                                                |
| | It must never infer acceptance or authority.                  |
| | }==============================================================|
| | CLAIMS_NOT_ESTABLISHED                                       |
| | This fixture does not establish:                              |
| |                                                               |
| | - correctness or truth of the source content                 |
| | - semantic equivalence between free-text documents            |
| | - destination acceptance                                     |
| | - permission to persist or mutate                            |
| | - cross-instance agreement                                   |
| | - uninterrupted model memory                                 |
| | - signing or distributed consensus                           |
| | - compatibility with any real external platform              |
| | }==============================================================|
| | IMPLEMENTATION_RELATION                                      |
| | holosim/spine_protocol.py already provides the read-only      |
| | source parser, rail observer, reconstruction frame, compare   |
| | operation, and deterministic transfer packet.                 |
| |                                                               |
| | No current implementation evaluates that packet against a     |
| | structured destination profile.                               |
| |                                                               |
| | This fixture does not authorize or claim that implementation. |
| | }==============================================================|
| | NEXT_BOUNDARY                                                |
| | Review and falsify this fixture before extending              |
| | holosim/spine_protocol.py.                                    |
| |                                                               |
| | If the fixture survives review, implement only the minimum    |
| | EXISTS and EXACT_VALUE evaluator needed to execute it.         |
| |                                                               |
| | Do not create a parallel parser.                              |
| | Do not add model-judged similarity.                           |
| | Do not add persistence, acceptance, or write authority.       |
| | }==============================================================|
| | FIXTURE_CLASSIFICATION                                       |
| | CLASSIFICATION: PARTIAL                                       |
| | ACCEPTED: false                                               |
| | WRITE_AUTHORITY: NONE                                         |
| | SOURCE_VALUES: SYMBOLIC_AND_STRUCTURED                        |
| | EXPECTED_FINDINGS: DETERMINISTIC_BY_DECLARED_RULES            |
| | IMPLEMENTATION_AUTHORITY: NONE                                |
| | }==============================================================|
| | END_DESTINATION_COMPATIBILITY_FIXTURE                         |
| | WRITE_AUTHORITY: NONE                                         |
| | }==============================================================|
