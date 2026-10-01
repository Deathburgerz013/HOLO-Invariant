# Statement and evidence boundary

`holosim.truth` records caller-supplied statements alongside receipts checked
by a caller-supplied validator. That validator receives each receipt, not the
statement. Receipt validity and receipt hashes therefore establish neither
relevance nor sufficiency nor statement truth.

New records use version 2 and explicitly carry `claim_support: NOT_ASSESSED`,
`truth_claimed: false`, `accepted: false`, and write/execution authority `NONE`.
The historical API names and `crystallized` / `moved` labels remain for
compatibility. They describe whether the statement text changed; repeated
receipts do not raise confidence or establish a fact.

`validate_truth_state` checks closed schema and canonical identity only. It
never reruns a receipt validator or checks the statement against the evidence.
An altered statement with a recomputed hash can pass this structural check,
while its support remains unassessed. A hash is not authentication or truth.

Version 1 records remain readable, with their original notices and hashes.
Structural acceptance of a historical record does not endorse its old
“justified” wording. No in-place migration occurs. Revising a legacy record
retains its hash as parent and creates version 2, after validating the supplied
receipts and requiring prior receipts plus at least one new receipt.
Consumers that assume a closed version 1 output must handle version 2.

This is a PARTIAL correction of an overclaim. It does not evaluate free-text
entailment, observation quality, contradictions, currentness, or environmental
truth. A genuine fact assertion needs a separate explicit, scoped check with
original evidence; this module provides no such assertion or authorization.
