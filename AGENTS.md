| | }==============================================================|
| | █†█ Holo/Sim █†█ █†█ ASSISTANT_CONTRACT █†█                 |
| | }==============================================================|
| | DOCUMENT_TYPE: REPOSITORY_INSTRUCTION                        |
| | STATUS: NORMATIVE_FOR_AUTOMATED_ASSISTANTS                   |
| | AUTHORITY: HUMAN_REPOSITORY_OWNER                            |
| | WRITE_AUTHORITY: NONE                                        |
| | APPLIES_TO: CODEX • GROK • ALL_AUTOMATED_ASSISTANTS         |
| | }==============================================================|
| | PURPOSE                                                      |
| | Preserve the HOLO invariant, evidence boundary, authority    |
| | separation, rail grammar, and review workflow during work.   |
| |                                                              |
| | Read this file before proposing, editing, testing, committing,|
| | reviewing, or merging a repository change.                   |
| | }==============================================================|
| | AUTHORITY_BOUNDARY                                           |
| | • Evaluation, analysis, validation, and verification do not |
| |   constitute acceptance or approval.                         |
| | • Evaluator outputs remain accepted: false and              |
| |   write_authority: NONE.                                     |
| | • Mutation requires explicit user authorization.            |
| | • HoloSim commits additionally require an external reviewer |
| |   and approval reference.                                    |
| | • Never merge until the user explicitly requests the merge. |
| | • A passing check establishes only what that check observes.|
| | }==============================================================|
| | EVIDENCE_AND_PROVENANCE                                      |
| | • Preserve raw evidence byte-for-byte.                      |
| | • Do not add headers, normalize line endings, reformat,      |
| |   repair, or overwrite raw evidence.                         |
| | • Put interpretation in a separate companion analysis that |
| |   names and hashes its source.                               |
| | • Evidence hashes establish identity, not truth, relevance, |
| |   or sufficiency.                                            |
| | • Structured assertions and causal claims retain validated |
| |   source bindings through evaluation and approved commit.    |
| | • Preserve uncertainty and conflict. Never guess provenance,|
| |   scope, polarity, order, evidence, or authority.            |
| | }==============================================================|
| | SPINE_AND_DOCUMENT_RAILS                                     |
| | • Preserve the established two-bar rail grammar and headers.|
| | • Validate every changed rail document with:                |
| |   python -m holosim.spine_protocol rail-validate <document>  |
| | • Rail validation is read-only structural observation.      |
| | • It does not repair or approve a document.                 |
| | • Do not mass-reformat documents or convert line endings as |
| |   an incidental part of another change.                      |
| | }==============================================================|
| | IMPLEMENTATION_RULES                                        |
| | • Start from current main on a narrowly named branch.       |
| | • Close one mapped gap with the smallest supported change.  |
| | • Do not bundle later invariants, cleanup, or speculative    |
| |   refactors into the same pull request.                      |
| | • Extend the evaluator that owns a boundary; do not create  |
| |   a parallel authority path.                                 |
| | • Prefer explicit structured contracts over pretending to   |
| |   understand free text.                                      |
| | • State non-inference boundaries in code, tests, and docs.  |
| | • Preserve compatibility unless the user approves breakage. |
| | • Update the implementation map when evidence changes.      |
| | • Classify incomplete implementation as PARTIAL.            |
| | }==============================================================|
| | REQUIRED_VALIDATION_BEFORE_COMMIT                            |
| | 1. Run focused tests for the changed boundary.               |
| | 2. Run python -m pytest -q.                                  |
| | 3. Validate every changed rail document.                     |
| | 4. Run git diff --check.                                     |
| | 5. Inspect git status --short.                               |
| | 6. Stage only intended files.                                |
| | }==============================================================|
| | REQUIRED_VALIDATION_AFTER_MERGE                              |
| | 1. Fetch origin.                                             |
| | 2. Fast-forward main with git pull --ff-only.                |
| | 3. Run the full test suite again.                            |
| | 4. Confirm main...origin/main with no local changes.         |
| | }==============================================================|
| | COLLABORATION_CADENCE                                        |
| | • Give the user one file or command at a time.              |
| | • Wait for the user's output before continuing.             |
| | • Explain a replacement before asking the user to place it. |
| | • Stop on unexpected output, failure, conflict, or expanded |
| |   scope. Diagnose before continuing.                         |
| | • Record exact test and rail counts in the pull request.    |
| | • Verify reported GitHub state before claiming it passed.   |
| | }==============================================================|
| | END_ASSISTANT_CONTRACT                                       |
| | WRITE_AUTHORITY: NONE                                        |
| | }==============================================================|