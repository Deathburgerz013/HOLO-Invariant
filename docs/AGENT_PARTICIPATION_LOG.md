# Agent Participation Log

Status: Research
Authority: Descriptive only
Write authority: NONE

## Purpose

Record declared human and AI participation in repository work, including later corrections.

A declaration is not authenticated identity, verified authorship, approval, or proof that all participants were recorded.

## Event fields

- ENTRY_ID: Unique identifier for this entry.
- EVENT_TYPE: MODEL_CLOCK_IN or STATE_FIX.
- ENTITY_ID: Self-declared participant identifier.
- ENTITY_TYPE: HUMAN, AI, or UNKNOWN.
- SOURCE_STATE_ID: Specific session or source state, or UNKNOWN.
- INFORMATION_CLASS: CLAIM for MODEL_CLOCK_IN; CORRECTION for STATE_FIX.
- CONTENT: Exact description of the declaration or correction.
- SOURCE: Originating statement or record reference, or UNKNOWN.
- VERIFICATION_STATUS: Explicit verification state; UNKNOWN when unverified.
- UNCERTAINTY: Known limitations, or UNKNOWN.
- CORRECTS_ENTRY: Earlier ENTRY_ID for STATE_FIX; NONE for MODEL_CLOCK_IN.
- MODEL_ID: Declared model identifier, or UNKNOWN / NOT_APPLICABLE.
- ROLE: Declared contribution role.
- ARTIFACT_REF: Specific PR, commit, file, or UNKNOWN.
- EVIDENCE_REF: Supporting evidence reference, or UNKNOWN.

## Rules

1. Append new events; do not silently overwrite earlier entries.
2. Use STATE_FIX to correct or retract an earlier declaration.
3. Preserve uncertainty and distinguish claims from verified evidence.
4. Do not infer that an absent entry means absent participation.
5. Existing AGENTS.md mutation, review, and approval requirements remain in force.

## Events

### ENTRY-001

ENTRY_ID: ENTRY-001
EVENT_TYPE: MODEL_CLOCK_IN
ENTITY_ID: GPT-6
ENTITY_TYPE: AI
SOURCE_STATE_ID: UNKNOWN
INFORMATION_CLASS: CLAIM
CONTENT: Self-declared participation in proposing and reviewing the AGENTS.md participation rules and the agent participation log schema.
SOURCE: Current ChatGPT conversation; persistent source reference UNKNOWN.
VERIFICATION_STATUS: UNKNOWN
UNCERTAINTY: Identity and contribution are self-declared; independent authentication and completeness are not established.
CORRECTS_ENTRY: NONE
MODEL_ID: GPT-6
ROLE: Assistant; proposed changes and interpreted user-supplied checks.
ARTIFACT_REF: AGENTS.md; docs/AGENT_PARTICIPATION_LOG.md
EVIDENCE_REF: Working-tree diff and user-reported command outputs; independent verification UNKNOWN.
