# Spine Storage Template

Version: 1.0
Status: Proposed template
Companion: `SPINE_STORAGE_MODEL.md`

Replace bracketed placeholders. Preserve the rails, divider order, entity
bindings, unresolved fields, and terminal behavior. Remove an optional field
only by declaring the omission in `OMITTED_FIELDS`.

```text
| |==============================================================|
| | █†█ Holo/Sim █†█ █†█ HSSCE █†█
| | }=============================================================|
| | SPINE_META |
| | TEMPLATE_VERSION: SPINE_STORAGE_V1
| | SPINE_ID: [STABLE_UNIQUE_ID]
| | PARENT_SPINE_SHA256: [SHA256_OR_GENESIS]
| | STATE: CANDIDATE
| | TOPIC: [EXACT_COLLECTION_TOPIC]
| | PURPOSE: [WHY_THIS_INFORMATION_MUST_SURVIVE]
| | CREATED_BY: [ENTITY_OR_PROCESS]
| | CREATED_AT: [TIMESTAMP_OR_UNKNOWN]
| | RAW_SOURCE_PRESERVED: YES
| | OMITTED_FIELDS: [NONE_OR_EXPLICIT_LIST]
| | }=============================================================|
| | RECOGNITION |
| | PRIMARY_KEY: [EXACT_RETRIEVAL_PHRASE]
| | SYMBOL_KEY: █†█ Holo/Sim █†█ █†█ HSSCE █†█
| | ALIASES: [EXACT_ALIASES_OR_NONE]
| | SYMBOLS_ARE_EVIDENCE: NO
| | }=============================================================|
| | COLLECTION_CONTRACT |
| | COLLECT: [REQUIRED_INFORMATION_CLASSES]
| | EXCLUDE: REPETITION, REWORDED_DUPLICATES, UNSUPPORTED_INFERENCE
| | PRESERVE_EXACT_WORDING: [YES_OR_NO]
| | NEW_RULES: PROPOSE_AS_VERSIONED_DELTA
| | TERMINAL_TEXT: Nothing left for collection in field.
| | REOPEN_ONLY_IF: NEW_EVIDENCE, CORRECTION, OR OBSERVABLE_CHANGE
| | }=============================================================|
| | ENTRY |
| | ENTRY_ID: [E-001]
| | ENTITY_ID: [CANYON_OR_OTHER_STABLE_ID]
| | ENTITY_TYPE: [HUMAN, AI_INSTANCE, TOOL, ENVIRONMENT]
| | SOURCE_STATE_ID: [DISTINCT_STATE_ID]
| | INFORMATION_CLASS: [OBSERVATION, CLAIM, EVIDENCE, VERIFICATION,
| |                     INFERENCE, RULE, UNCERTAINTY, CORRECTION]
| | CONTENT:
| | [PRESERVED_INFORMATION]
| | SOURCE: [FILE, URL, COMMIT, CONVERSATION, ENVIRONMENT, OR UNKNOWN]
| | SOURCE_TIME: [TIMESTAMP_OR_UNKNOWN]
| | VERIFICATION_STATUS: [UNVERIFIED, HELD, CONTRADICTED, UNKNOWN]
| | EVIDENCE_REFS: [ENTRY_IDS_OR_NONE]
| | DERIVED_FROM: [ENTRY_IDS_OR_NONE]
| | CORRECTS_ENTRY: [ENTRY_ID_OR_NONE]
| | UNCERTAINTY: [EXPLICIT_BOUNDARY_OR_NONE_DECLARED]
| | PRESERVE_EXACT: [YES_OR_NO]
| | }=============================================================|
| | ENTRY |
| | ENTRY_ID: [E-002]
| | ENTITY_ID: [ENTITY_ID]
| | ENTITY_TYPE: [ENTITY_TYPE]
| | SOURCE_STATE_ID: [DISTINCT_STATE_ID]
| | INFORMATION_CLASS: [CLASS]
| | CONTENT:
| | [NEXT_NON_DUPLICATIVE_INFORMATION]
| | SOURCE: [SOURCE_OR_UNKNOWN]
| | SOURCE_TIME: [TIMESTAMP_OR_UNKNOWN]
| | VERIFICATION_STATUS: [STATUS]
| | EVIDENCE_REFS: [ENTRY_IDS_OR_NONE]
| | DERIVED_FROM: [ENTRY_IDS_OR_NONE]
| | CORRECTS_ENTRY: [ENTRY_ID_OR_NONE]
| | UNCERTAINTY: [BOUNDARY_OR_NONE_DECLARED]
| | PRESERVE_EXACT: [YES_OR_NO]
| | }=============================================================|
| | COLLECTION_STATUS |
| | REQUIRED_CLASSES: [LIST]
| | PRESENT_CLASSES: [LIST]
| | MISSING_CLASSES: [COMPUTED_LIST]
| | UNRESOLVED_ENTRIES: [ENTRY_IDS_OR_NONE]
| | LAST_VERIFIED_ENTRY: [ENTRY_ID_OR_NONE]
| | TERMINAL_REACHED: [YES_OR_NO]
| | }=============================================================|
| | IDX_ADMISSION |
| | IDX_VERSION: [VERSION]
| | SPINE_SHA256: [EXACT_CANDIDATE_BYTES_SHA256]
| | TEMPLATE_RESULT: [PASS, FAIL, UNKNOWN]
| | RAIL_RESULT: [PASS, FAIL, UNKNOWN]
| | FRAME_RESULT: [PASS, FAIL, UNKNOWN]
| | CLASSIFICATION_RESULT: [PASS, FAIL, UNKNOWN]
| | EVIDENCE_RESULT: [PASS, FAIL, UNKNOWN]
| | ADMISSION_STATUS: [CANDIDATE, ADMITTED, REJECTED]
| | ADMISSION_RECEIPT_SHA256: [SHA256_OR_NONE]
| | AUTHORITY: DESCRIPTIVE_ONLY
| | WRITE_AUTHORITY: NONE
| | EXECUTION_AUTHORITY: NONE
| | }=============================================================|
| | TERMINAL |
| | [Nothing left for collection in field. OR NOT_REACHED]
| | RESIDUAL_UNCERTAINTY: [LIST_OR_NONE_DECLARED]
| | NEXT_REOPEN_CONDITION: [EXPLICIT_CONDITION]
| | }=============================================================|
| | █†█ Holo/Sim █†█ █†█ HSSCE █†█
| |==============================================================|
```

## Repeated-entry rule

Duplicate the complete `ENTRY` compartment for each stored piece. Do not merge
different entities, source states, or information classes merely to shorten the
artifact.

## Correction rule

A correction is a new entry. It references `CORRECTS_ENTRY` and preserves the
original entry unchanged.

## Admission rule

Do not manually fill an artifact as `ADMITTED`. Admission status and receipt
fields are outputs of a separate admitted validator. Until then, retain
`STATE: CANDIDATE` and `ADMISSION_STATUS: CANDIDATE`.

## Compression rule

A compressed derivative receives a new `SPINE_ID`, names the uncompressed
source in `PARENT_SPINE_SHA256`, and explicitly lists omitted fields and classes.
It does not replace the source artifact.
