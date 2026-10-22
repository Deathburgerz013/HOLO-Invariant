# Independent Trust-Anchor Authentication Research

## Hypothesis
A verifier can detect signer-policy substitution when its
reference was independently provisioned and remains outside
the attacker's control.

## Attacker capabilities
- Replace presented signer-policy bytes.
- Replace checkpoint and history evidence.
- Generate attacker-controlled signing keys.
- Supply matching digests for attacker-controlled artifacts.
- Attempt to substitute the verifier's reference.

## Trust assumption
A reference is provisioned through a separate trusted channel
and protected from the defined attacker.

This assumption is external to digest comparison.
Local file storage alone does not establish it.

## Required observations
1. Original policy against original reference: MATCH.
2. Attacker policy against original reference: MISMATCH.
3. Attacker policy against attacker reference: MATCH,
   but independent provenance remains unestablished.
4. Missing reference: UNKNOWN.
5. Reference substitution: must not establish authentication
   without an independently protected reference.

## Authority boundary
No proof, digest, receipt, or comparison grants permission
to replace a trust root.

## Open question
What independently controlled provisioning and verification
channel can establish the initial reference?
