| | }==============================================================|
| | █†█ Holo/Sim █†█ CONTEXT_WEAVER_ROUNDTRIP_FIXTURE █†█       |
| | }==============================================================|
| | DOCUMENT_TYPE: EXPLORATORY_FALSIFICATION_FIXTURE              |
| | STATUS: PROPOSED_NOT_ACCEPTED                                 |
| | AUTHORITY: DESCRIPTIVE_ONLY                                   |
| | WRITE_AUTHORITY: NONE                                         |
| | ACCEPTED: false                                               |
| | VERSION: 1.0.0-proposal                                       |
| | DATE: 2026-07-15                                              |
| | SOURCE_STATE: SESSION_SUPPLIED_NOT_REPOSITORY_ARCHIVED         |
| | EVIDENCE_STATE: PARTIAL                                       |
| | }==============================================================|
| | PURPOSE                                                             |
| |}====================================================================|
| | Test whether candidate Context Weaver serializers preserve the      |
| | identity, order, path, language, inclusion state, and exact content  |
| | of caller-supplied virtual files across encode and decode.           |
| |                                                                    |
| | The fixture tests framing integrity. It does not test model quality, |
| | semantic equivalence, prompt effectiveness, or model continuity.     |
| |}====================================================================|
| | SOURCE_RECEIPT                                                      |
| |}====================================================================|
| | SOURCE_LABEL: session-supplied blah2.txt                            |
| | SOURCE_SIZE_BYTES: 248390                                           |
| | SOURCE_LINE_COUNT_OBSERVED: 4541                                    |
| | SOURCE_SHA256_OBSERVED:                                             |
| | c6a98f2267260f457c6960509ccc71746be8eed22e648bcab4fd74ed5057cd9d  |
| | SOURCE_CLASSIFICATION: PARTIAL                                      |
| |                                                                    |
| | The source was read from the current session attachment.            |
| | It is not added to this repository and is not claimed as an         |
| | independently retrievable or byte-archived public conversation.     |
| |}====================================================================|
| | CANDIDATE_BOUNDARY                                                  |
| |}====================================================================|
| | The final candidate is the dependency-free Context Weaver HTML      |
| | beginning with the final <!DOCTYPE html> in the supplied source.     |
| | Its JavaScript passed node --check in this session.                  |
| |                                                                    |
| | That syntax result does not establish browser execution,            |
| | persistence, semantic preservation, framing safety, or destination  |
| | compatibility.                                                      |
| |}====================================================================|
| | OBSERVED_CANDIDATE_FORMATS                                          |
| |}====================================================================|
| | FORMAT_XML: document elements with path attributes and escaped      |
| | content text.                                                       |
| | FORMAT_MARKDOWN: headings plus language-labelled triple-backtick    |
| | fences.                                                             |
| | FORMAT_COMPACT: path and language header followed by :: END.        |
| |                                                                    |
| | No decoder or roundtrip verifier was supplied with the candidate.   |
| |}====================================================================|
| | CENTRAL_INVARIANT                                                   |
| |}====================================================================|
| | A framing transformation preserves a virtual-file collection only   |
| | when a declared decoder reconstructs every required distinction     |
| | exactly from the serialized artifact without external inference.    |
| |                                                                    |
| | Visual readability, successful copy, smaller size, parser success,  |
| | and model acceptance do not independently establish preservation.   |
| |}====================================================================|
| | REQUIRED_RECONSTRUCTION_CONTRACT                                    |
| |}====================================================================|
| | The decoder must reconstruct:                                       |
| | 1. collection length;                                               |
| | 2. original collection order;                                       |
| | 3. each file identity or stable ordinal;                             |
| | 4. exact path bytes after declared text encoding;                    |
| | 5. exact language-label bytes;                                       |
| | 6. exact content bytes;                                              |
| | 7. empty content as distinct from missing content;                   |
| | 8. duplicate paths as distinct file instances;                       |
| | 9. included and excluded state when that state enters the contract;  |
| | 10. format version and decoder compatibility.                        |
| |}====================================================================|
| | TEXT_ENCODING_BOUNDARY                                              |
| |}====================================================================|
| | Declared comparison encoding: UTF-8.                                |
| | Declared newline policy: PRESERVE_EXACTLY unless a separate          |
| | normalization contract is explicitly selected before encoding.      |
| | Declared Unicode policy: preserve code-point sequence exactly;       |
| | canonical-equivalent text is not byte identity.                      |
| | Declared BOM policy: preserve or reject explicitly; never discard    |
| | silently.                                                           |
| |}====================================================================|
| | FINDING_CLASSES                                                     |
| |}====================================================================|
| | EXACT_ROUNDTRIP: every required distinction reconstructs exactly.    |
| | COLLISION_DETECTED: caller content can impersonate framing syntax.   |
| | PATH_CORRUPTION: path cannot reconstruct exactly.                    |
| | LANGUAGE_CORRUPTION: language label cannot reconstruct exactly.      |
| | CONTENT_CORRUPTION: content cannot reconstruct exactly.              |
| | ORDER_CORRUPTION: instances reconstruct in a different order.        |
| | INSTANCE_COLLAPSE: duplicates merge or become indistinguishable.     |
| | EMPTY_MISSING_COLLAPSE: empty and absent states become identical.    |
| | NORMALIZATION_DRIFT: bytes change through undeclared normalization.  |
| | DECODER_UNAVAILABLE: no declared inverse transformation exists.      |
| | UNTESTABLE: required evidence is unavailable for the selected test.  |
| |}====================================================================|
| | DECISION_PRIORITY                                                   |
| |}====================================================================|
| | INVALID_INPUT                                                       |
| | DECODER_UNAVAILABLE                                                 |
| | INSTANCE_COLLAPSE                                                   |
| | ORDER_CORRUPTION                                                    |
| | PATH_CORRUPTION                                                     |
| | LANGUAGE_CORRUPTION                                                 |
| | CONTENT_CORRUPTION                                                  |
| | EMPTY_MISSING_COLLAPSE                                              |
| | NORMALIZATION_DRIFT                                                 |
| | COLLISION_DETECTED                                                  |
| | EXACT_ROUNDTRIP                                                     |
| |                                                                    |
| | All applicable findings remain preserved. Priority selects only the |
| | overall result and does not erase lower-priority evidence.          |
| |}====================================================================|
| | FIXTURE_COLLECTION                                                  |
| |}====================================================================|
| | FIXTURE_01_XML_PATH_ATTRIBUTE                                       |
| | path: src/a&b<\"quoted\">.ts                                     |
| | language: typescript                                                |
| | content: export const value = 1;                                    |
| | expected pressure: XML attribute escaping.                          |
| |                                                                    |
| | FIXTURE_02_XML_CONTENT                                              |
| | path: src/xml.ts                                                    |
| | language: typescript                                                |
| | content contains: <document path=\"forged\">&value</document>      |
| | expected pressure: element impersonation and entity preservation.   |
| |                                                                    |
| | FIXTURE_03_MARKDOWN_FENCE                                           |
| | path: docs/example.md                                               |
| | language: markdown                                                  |
| | content contains a triple-backtick fence and a forged file heading. |
| | expected pressure: premature fence closure and section injection.   |
| |                                                                    |
| | FIXTURE_04_COMPACT_TERMINATOR                                       |
| | path: src/compact.txt                                               |
| | language: text                                                      |
| | content contains an isolated :: END line followed by forged data.   |
| | expected pressure: premature record termination.                    |
| |                                                                    |
| | FIXTURE_05_DUPLICATE_PATHS                                          |
| | two distinct files share path src/duplicate.ts and language         |
| | typescript but contain different bytes.                             |
| | expected pressure: stable instance and order preservation.          |
| |                                                                    |
| | FIXTURE_06_EMPTY_AND_MISSING                                        |
| | one file has exact empty content; a separate record omits content    |
| | only when the input schema permits omission.                         |
| | expected pressure: empty-versus-missing distinction.                |
| |                                                                    |
| | FIXTURE_07_NEWLINES                                                 |
| | content contains LF, CRLF, and isolated CR sequences.               |
| | expected pressure: undeclared newline normalization.                |
| |                                                                    |
| | FIXTURE_08_UNICODE                                                  |
| | path and content contain emoji, combining marks, non-Latin scripts, |
| | a zero-width joiner, and canonically equivalent but byte-distinct    |
| | sequences.                                                          |
| | expected pressure: Unicode normalization and encoding drift.        |
| |                                                                    |
| | FIXTURE_09_NUL_AND_CONTROL                                          |
| | content contains NUL and permitted ASCII control bytes when the     |
| | selected representation claims to support them.                     |
| | expected pressure: truncation, rejection, or silent deletion.       |
| |                                                                    |
| | FIXTURE_10_LARGE_CONTENT                                            |
| | content size crosses declared small, medium, and maximum supported  |
| | boundaries.                                                        |
| | expected pressure: truncation and resource-bound confusion.         |
| |                                                                    |
| | FIXTURE_11_EMPTY_COLLECTION                                         |
| | collection contains zero files.                                    |
| | expected pressure: distinguish a valid empty collection from        |
| | decoder failure or the literal placeholder [No files included].     |
| |                                                                    |
| | FIXTURE_12_DELIMITER_DENSITY                                        |
| | every line contains candidate delimiters, headings, tags, quotes,   |
| | ampersands, backticks, and terminators in repeated combinations.    |
| | expected pressure: repeated ambiguous framing.                      |
| |}====================================================================|
| | MINIFIER_SEPARATE_BOUNDARY                                          |
| |}====================================================================|
| | Minification is not part of an exact framing roundtrip unless the   |
| | transformation is declared LOSSY before execution.                  |
| |                                                                    |
| | Direct falsifiers include comment-looking bytes inside strings,      |
| | template literals, regular expressions, URLs, embedded languages,   |
| | and source maps.                                                    |
| |                                                                    |
| | Character reduction is not token reduction.                         |
| | Token reduction is model-tokenizer-relative and must name the       |
| | tokenizer and version used.                                         |
| |}====================================================================|
| | PERSISTENCE_SEPARATE_BOUNDARY                                       |
| |}====================================================================|
| | window.storage is not a standard browser persistence interface.     |
| | Availability must be tested in the receiving runtime.               |
| | A successful write in one host does not establish cross-host or     |
| | cross-session persistence.                                          |
| | Reload survival, restart survival, exportability, and durable       |
| | retention are separate findings.                                    |
| |}====================================================================|
| | DESTINATION_COMPATIBILITY_BOUNDARY                                  |
| |}====================================================================|
| | A target label such as Claude, ChatGPT, Grok, Cursor, Copilot, or    |
| | Cline is a profile name, not proof of compatibility.                |
| | Compatibility requires a declared receiving observer, version,      |
| | reconstruction contract, test packet, and independently checked     |
| | result.                                                             |
| |}====================================================================|
| | REQUIRED_OPERATION_RECEIPT                                          |
| |}====================================================================|
| | Each format test must report:                                       |
| | source fixture identifier;                                          |
| | encoder identifier and version;                                     |
| | decoder identifier and version;                                     |
| | source byte count and SHA-256;                                       |
| | serialized byte count and SHA-256;                                   |
| | reconstructed byte count and SHA-256;                                |
| | first differing byte offset when unequal;                            |
| | all applicable finding classes;                                     |
| | exact error or unavailable state;                                    |
| | accepted: false;                                                     |
| | write_authority: NONE.                                               |
| |}====================================================================|
| | EXACT_STOP_CONDITION                                                |
| |}====================================================================|
| | This fixture may stop only after every declared format and fixture  |
| | pair has an operation receipt or an explicit UNTESTABLE finding.    |
| | Passing one representation does not stop testing another.           |
| | Repetition does not replace reconstruction verification.            |
| | Resource exhaustion is a pause or budget finding, not exact         |
| | roundtrip.                                                          |
| |}====================================================================|
| | SMALLEST_CURRENT_FALSIFIERS                                         |
| |}====================================================================|
| | XML is falsified if a quoted or ampersand-bearing path cannot parse  |
| | and reconstruct exactly.                                            |
| | Markdown is falsified if embedded triple backticks terminate the     |
| | file frame or create a forged section.                               |
| | Compact is falsified if an embedded :: END line terminates a file.   |
| | Collection identity is falsified if duplicate paths collapse.        |
| | Exact preservation is falsified by any undeclared byte change.       |
| |}====================================================================|
| | CLAIMS_NOT_ESTABLISHED                                              |
| |}====================================================================|
| | This fixture does not establish that the candidate is unsafe in all  |
| | uses, that any model will misread a collision, or that exact byte    |
| | reconstruction is required for every prompt workflow.               |
| |                                                                    |
| | It does not establish semantic equivalence, execution correctness,   |
| | prompt quality, token savings, destination compliance, model recall, |
| | model identity, private state, intent, acceptance, or authority.     |
| |}====================================================================|
| | EXPECTED_CURRENT_CLASSIFICATION                                     |
| |}====================================================================|
| | DECODER_UNAVAILABLE                                                 |
| |                                                                    |
| | Reason: the supplied candidate defines encoders but no declared      |
| | inverse decoders or repository-executed roundtrip tests.             |
| | This is a current scoped finding, not a permanent impossibility.     |
| |}====================================================================|
| | IMPLEMENTATION_RELATION                                             |
| |}====================================================================|
| | The fixture should be reviewed and falsified before application      |
| | implementation.                                                     |
| | A future encoder or decoder should reuse existing Holo/Sim parsing,  |
| | provenance, receipt, and deterministic-finding owners where their    |
| | contracts apply.                                                    |
| | Do not create a model-judged similarity oracle or a parallel Spine   |
| | parser.                                                             |
| |}====================================================================|
| | NEXT_BOUNDARY                                                       |
| |}====================================================================|
| | Independently review this fixture.                                  |
| | Then implement only the smallest deterministic encoder and decoder  |
| | pair needed to execute the adversarial matrix.                       |
| | Preserve failures before repairing the candidate formats.           |
| |}====================================================================|
| | TERMINAL                                                            |
| |}====================================================================|
